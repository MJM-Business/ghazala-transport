"""Customer-only profiles and explicit ownership, alongside unchanged staff RBAC.

Callers own transactions. Session/token/password handling stays in server.py.
Future invoices/payments and pickup requests can reference customer_accounts;
this foundation does not implement those modules or claim shipments by AWB.
"""
import re
import authorization as auth
from foundation_schema import set_user_access
from security import LoginThrottle, validate_password
from audit import write_audit

REGISTRATION_THROTTLE = LoginThrottle()


class CustomerConflict(ValueError):
    pass


class CustomerShipmentNotFound(ValueError):
    pass


def migration5(con):
    con.execute("""CREATE TABLE customer_accounts (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        address TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE customer_shipments (
        shipment_id INTEGER PRIMARY KEY REFERENCES shipments(id),
        customer_user_id INTEGER NOT NULL REFERENCES customer_accounts(user_id),
        linked_by INTEGER NOT NULL REFERENCES users(id),
        linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    con.execute('CREATE INDEX customer_shipments_owner ON customer_shipments(customer_user_id,shipment_id)')
    # Adopt previously reserved customer roles without changing users/access or
    # inferring ownership of any authentic shipment from contact information.
    con.execute("""INSERT INTO customer_accounts(user_id)
        SELECT user_id FROM user_access WHERE role='customer'""")


def ensure_account(con, user_id):
    con.execute('INSERT OR IGNORE INTO customer_accounts(user_id) VALUES(?)', (user_id,))


def is_customer(con, user):
    ctx = auth.context(con, user) if user else None
    return bool(ctx and ctx['role'] == 'customer' and ctx['is_active']
                and con.execute('SELECT 1 FROM customer_accounts WHERE user_id=?', (user['id'],)).fetchone())


def require_customer(con, user):
    if not is_customer(con, user):
        raise auth.AccessDenied('An active customer account is required.')


def profile(con, user):
    require_customer(con, user)
    row = con.execute("""SELECT u.id,u.username,u.display_name,u.mobile,
        a.address,a.created_at,a.updated_at FROM users u
        JOIN customer_accounts a ON a.user_id=u.id WHERE u.id=?""", (user['id'],)).fetchone()
    result = dict(row)
    result.update(role='customer', access_role='customer', permissions=[])
    return result


def _profile_fields(data, registration=False):
    permitted = {'display_name', 'mobile', 'address'}
    if registration:
        permitted |= {'username', 'password'}
    if not data or set(data) - permitted:
        raise ValueError('Unsupported customer account fields.')
    result = {}
    for key, limit in (('display_name', 160), ('mobile', 60), ('address', 1000)):
        if key in data:
            value = data[key]
            if not isinstance(value, str) or len(value.strip()) > limit:
                raise ValueError('Invalid customer profile field.')
            result[key] = value.strip()
    if ('display_name' in result and not result['display_name']) or (registration and not result.get('display_name')):
        raise ValueError('Enter a customer display name.')
    return result


def register(con, data, password_hash, request=None):
    fields = _profile_fields(data, registration=True)
    username = data.get('username')
    if not isinstance(username, str) or not re.fullmatch(r'\S{3,160}', username.strip()):
        raise ValueError('Enter a valid customer username.')
    username = username.strip().casefold()
    validate_password(data.get('password'))
    if con.execute('SELECT 1 FROM users WHERE lower(username)=lower(?)', (username,)).fetchone():
        raise CustomerConflict('This username is already registered.')
    cur = con.execute("""INSERT INTO users(username,display_name,role,password_hash,mobile)
        VALUES(?,?,'employee',?,?)""", (username, fields['display_name'], password_hash(data['password']), fields.get('mobile', '')))
    uid = cur.lastrowid
    set_user_access(con, uid, 'customer', [], None, global_scope=False)
    con.execute('INSERT INTO customer_accounts(user_id,address) VALUES(?,?)', (uid, fields.get('address', '')))
    user = dict(con.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
    write_audit(con, auth.context(con, user), 'customer.registered', 'user', uid, request=request)
    return profile(con, user)


def update_profile(con, user, data, request=None):
    require_customer(con, user)
    fields = _profile_fields(data)
    before = profile(con, user)
    con.execute('UPDATE users SET display_name=?,mobile=? WHERE id=?',
                (fields.get('display_name', before['display_name']), fields.get('mobile', before['mobile']), user['id']))
    con.execute('UPDATE customer_accounts SET address=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?',
                (fields.get('address', before['address']), user['id']))
    result = profile(con, user)
    write_audit(con, auth.context(con, user), 'customer.profile_updated', 'user', user['id'], before=before, after=result, request=request)
    return result


def owns_shipment(con, user, shipment_id):
    require_customer(con, user)
    return bool(con.execute('SELECT 1 FROM customer_shipments WHERE customer_user_id=? AND shipment_id=?',
                            (user['id'], shipment_id)).fetchone())


def shipments(con, user, awb=None):
    require_customer(con, user)
    where = 'cs.customer_user_id=?'
    args = [user['id']]
    if awb is not None:
        where += ' AND s.awb=?'
        args.append(awb.strip().upper())
    # Explicit customer projection: no staff identity, GPS, proof evidence,
    # internal notes, IDs/phones or finance fields from the general shipment API.
    rows = con.execute("""SELECT s.id,s.awb,s.recipient,s.origin,s.destination,
        s.status,s.stage,s.eta,s.package_type,s.package_description,s.pieces,s.weight,
        s.created_at,s.updated_at FROM customer_shipments cs
        JOIN shipments s ON s.id=cs.shipment_id WHERE """ + where + ' ORDER BY s.id DESC', args).fetchall()
    result = [dict(row) for row in rows]
    if awb is not None:
        if not result:
            raise CustomerShipmentNotFound('Shipment not found.')
        return result[0]
    return result



def link_created_shipment(con, user, shipment_id, request=None):
    """Link a newly customer-created shipment to the authenticated customer.

    This is intentionally separate from the staff-side link_shipment() helper:
    customer self-service creation must not require staff permissions, but it
    still writes the same authoritative customer_shipments ownership row.
    """
    require_customer(con, user)
    try:
        shipment_id=int(shipment_id)
    except (TypeError,ValueError):
        raise ValueError('Invalid shipment.') from None

    shipment=con.execute(
        'SELECT id,awb FROM shipments WHERE id=?',
        (shipment_id,)
    ).fetchone()
    if not shipment:
        raise CustomerShipmentNotFound('Shipment not found.')

    current=con.execute(
        'SELECT * FROM customer_shipments WHERE shipment_id=?',
        (shipment_id,)
    ).fetchone()
    if current:
        if current['customer_user_id'] != user['id']:
            raise CustomerConflict('Shipment is already linked to another customer.')
        return dict(current), False

    con.execute(
        'INSERT INTO customer_shipments(shipment_id,customer_user_id,linked_by) VALUES(?,?,?)',
        (shipment_id,user['id'],user['id'])
    )
    result=dict(con.execute(
        'SELECT * FROM customer_shipments WHERE shipment_id=?',
        (shipment_id,)
    ).fetchone())

    write_audit(
        con,
        auth.context(con,user),
        'shipment.customer_linked',
        'shipment',
        shipment_id,
        after=result,
        request=request
    )
    return result, True

def link_shipment(con, actor, shipment, data, request=None):
    if not auth.allowed(actor, 'shipments.edit'):
        raise auth.AccessDenied()
    auth.require_object(con, actor, 'shipments', shipment)
    if set(data) != {'customer_user_id'}:
        raise ValueError('Select only the customer account to link.')
    uid = data['customer_user_id']
    if isinstance(uid, bool) or not re.fullmatch(r'[1-9][0-9]*', str(uid)):
        raise ValueError('Select a valid customer account.')
    target = con.execute('SELECT * FROM users WHERE id=?', (int(uid),)).fetchone()
    if not is_customer(con, target):
        raise ValueError('Select an active customer account.')
    current = con.execute('SELECT * FROM customer_shipments WHERE shipment_id=?', (shipment['id'],)).fetchone()
    if current:
        if current['customer_user_id'] != int(uid):
            raise CustomerConflict('Shipment is already linked to another customer.')
        return dict(current), False
    con.execute('INSERT INTO customer_shipments(shipment_id,customer_user_id,linked_by) VALUES(?,?,?)',
                (shipment['id'], int(uid), actor['user_id']))
    result = dict(con.execute('SELECT * FROM customer_shipments WHERE shipment_id=?', (shipment['id'],)).fetchone())
    write_audit(con, actor, 'shipment.customer_linked', 'shipment', shipment['id'], after=result, request=request)
    return result, True
