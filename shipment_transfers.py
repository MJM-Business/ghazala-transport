"""Branch handoff records alongside the existing route manifest.

Every operation participates in the caller's transaction. Vehicle arrival
only makes a parcel eligible for an explicit destination-office receipt.
"""
import authorization as auth
import foundation_schema as schema
import transitions
from audit import write_audit


class PendingTransferError(ValueError):
    """A parcel cannot belong to two unconfirmed handoffs."""


def migration4(con):
    con.execute("""CREATE TABLE shipment_transfers (
        route_id INTEGER NOT NULL,
        shipment_id INTEGER NOT NULL,
        origin_branch_id INTEGER NOT NULL REFERENCES branches(id),
        destination_branch_id INTEGER NOT NULL REFERENCES branches(id),
        status TEXT NOT NULL CHECK(status IN
            ('planned','in_transit','awaiting_receipt','received','cancelled')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        dispatched_at TEXT, arrived_at TEXT, received_at TEXT,
        received_by INTEGER REFERENCES users(id),
        PRIMARY KEY(route_id,shipment_id),
        FOREIGN KEY(route_id,shipment_id)
            REFERENCES route_shipments(route_id,shipment_id) ON DELETE CASCADE,
        CHECK((status='received' AND received_at IS NOT NULL AND received_by IS NOT NULL)
            OR (status!='received' AND received_at IS NULL AND received_by IS NULL)))""")
    con.execute("""CREATE UNIQUE INDEX shipment_transfers_pending
        ON shipment_transfers(shipment_id)
        WHERE status IN ('planned','in_transit','awaiting_receipt')""")
    # Adopt active manifests only; historical arrivals are not receipt evidence.
    for route in con.execute("SELECT * FROM route_runs WHERE status IN ('مجدولة','في الطريق')").fetchall():
        pair = schema.resolve_route_offices(con, route)
        if None in pair:
            raise ValueError('Resolve active route offices before adding shipment transfers.')
        for row in con.execute("""SELECT s.* FROM shipments s JOIN route_shipments rs
            ON rs.shipment_id=s.id WHERE rs.route_id=?""", (route['id'],)).fetchall():
            if transitions.canonical(row['status']) == 'delivered':
                continue
            load(con, route['id'], row['id'], pair)
        if route['status'] == 'في الطريق':
            con.execute("""UPDATE shipment_transfers SET status='in_transit',dispatched_at=?
                WHERE route_id=?""", (route['started_at'], route['id']))


def pending(con, shipment_id):
    return con.execute("""SELECT * FROM shipment_transfers WHERE shipment_id=?
        AND status IN ('planned','in_transit','awaiting_receipt')""", (shipment_id,)).fetchone()


def load(con, route_id, shipment_id, offices, ctx=None, request=None):
    if con.execute('SELECT 1 FROM shipment_transfers WHERE route_id=? AND shipment_id=?',
                   (route_id, shipment_id)).fetchone():
        return
    if pending(con, shipment_id):
        raise PendingTransferError('Shipment already has a pending branch transfer.')
    con.execute("""INSERT INTO shipment_transfers
        (route_id,shipment_id,origin_branch_id,destination_branch_id,status)
        VALUES(?,?,?,?,'planned')""", (route_id, shipment_id, *offices))
    if ctx:
        write_audit(con, ctx, 'transfer.created', 'shipment', shipment_id,
                    after={'route_id': route_id, 'status': 'planned'}, request=request)


def advance(con, route, status, ctx, request=None):
    next_status, timestamp = {
        'في الطريق': ('in_transit', 'dispatched_at'),
        'وصلت': ('awaiting_receipt', 'arrived_at'),
        'ملغاة': ('cancelled', None),
    }[status]
    for row in con.execute('SELECT * FROM shipment_transfers WHERE route_id=?', (route['id'],)).fetchall():
        if row['status'] in ('received', 'cancelled'):
            continue
        time_sql = f', {timestamp}=CURRENT_TIMESTAMP' if timestamp else ''
        con.execute(f'UPDATE shipment_transfers SET status=?{time_sql} WHERE route_id=? AND shipment_id=?',
                    (next_status, route['id'], row['shipment_id']))
        write_audit(con, ctx, 'transfer.' + next_status, 'shipment', row['shipment_id'],
                    before={'status': row['status']},
                    after={'route_id': route['id'], 'status': next_status}, request=request)


def authorize_receipt(con, ctx, route, awb):
    if ctx['role'] not in ('system_admin', 'branch_manager', 'office_employee'):
        raise auth.AccessDenied('Receiving office staff must confirm the shipment.')
    row = con.execute("""SELECT t.* FROM shipment_transfers t JOIN shipments s
        ON s.id=t.shipment_id WHERE t.route_id=? AND s.awb=?""", (route['id'], awb)).fetchone()
    if not row:
        raise ValueError('Shipment is not in this route transfer.')
    if not ctx['global_scope'] and row['destination_branch_id'] not in ctx['branch_ids']:
        raise auth.AccessDenied('Only the receiving office can confirm this transfer.')
    return row


def receive(con, ctx, route, transfer, request=None):
    if transfer['status'] == 'received':
        return False
    if route['status'] != 'وصلت' or transfer['status'] != 'awaiting_receipt':
        raise ValueError('Confirm receipt after the vehicle has arrived.')
    con.execute("""UPDATE shipment_transfers SET status='received',
        received_at=CURRENT_TIMESTAMP,received_by=?
        WHERE route_id=? AND shipment_id=?""",
        (ctx['user_id'], route['id'], transfer['shipment_id']))
    write_audit(con, ctx, 'transfer.received', 'shipment', transfer['shipment_id'],
                before={'status': transfer['status']},
                after={'route_id': route['id'], 'status': 'received',
                       'destination_branch_id': transfer['destination_branch_id']}, request=request)
    return True


def receipt_details(con, route_id, shipment_id):
    """Serialize a receipt after the caller has authorized this route and parcel.

    Origin and receiving actor come from the existing transfer record; expose
    only the actor ID/display name, never account credentials or private fields.
    """
    row = con.execute("""SELECT t.route_id,t.shipment_id,t.origin_branch_id,
        t.destination_branch_id AS receiving_branch_id,t.status AS transfer_status,
        t.received_at,t.received_by,u.display_name AS received_by_name
        FROM shipment_transfers t LEFT JOIN users u ON u.id=t.received_by
        WHERE t.route_id=? AND t.shipment_id=?""", (route_id, shipment_id)).fetchone()
    if row is None:
        raise ValueError('Shipment is not in this route transfer.')
    return dict(row)
