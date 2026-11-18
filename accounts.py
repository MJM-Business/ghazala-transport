"""Account administration, using the existing users/password/session structures."""
import sqlite3
import authorization as auth
import customer_accounts as customers
from foundation_schema import set_user_access, branch_for_city
from security import validate_password
from audit import write_audit

def _assigned_access(con, row):
    """Account administration shows stored assignments, including inactive users.

    Authorization context still removes effective access when an account or an
    office is inactive. Those filtered scopes must never erase configuration.
    """
    row=dict(row)
    access=con.execute('SELECT role,primary_branch_id,global_scope FROM user_access WHERE user_id=?',(row['id'],)).fetchone()
    memberships=[r['branch_id'] for r in con.execute('SELECT branch_id FROM user_branches WHERE user_id=? ORDER BY branch_id',(row['id'],))]
    return {'access_role':auth.canonical_role(access['role'] if access else row['role']),
        'branch_ids':memberships,'primary_branch_id':access['primary_branch_id'] if access else None,
        'global_scope':bool(access['global_scope']) if access else False}

def safe_user(con, row):
    row=dict(row); ctx=auth.context(con,row)
    assigned=_assigned_access(con,row); assigned_role=assigned['access_role']
    result={k:row.get(k) for k in ('id','username','display_name','mobile','national_id','driver_id','is_active')}
    result.update(role=auth.legacy_role(assigned_role), access_role=assigned_role,
        permissions=sorted(auth.ROLE_PERMISSIONS.get(ctx['role'],())) if ctx['is_active'] else [],
        primary_branch_id=assigned['primary_branch_id'],branch_ids=assigned['branch_ids'],global_scope=assigned['global_scope'])
    if assigned['branch_ids']:
        marks=','.join('?' for _ in assigned['branch_ids'])
        result['branches']=[dict(b) for b in con.execute(f'SELECT id,code,name,city FROM branches WHERE id IN ({marks}) ORDER BY id',assigned['branch_ids'])]
    else: result['branches']=[]
    return result

def _assignment(con, data, existing=None):
    old=dict(existing or {}); assigned=_assigned_access(con,old) if old else None
    role_value=data.get('role',assigned['access_role'] if assigned else '')
    if isinstance(role_value,str): role_value=role_value.strip().lower()
    if role_value not in auth.ROLE_ALIASES: raise ValueError('Unsupported user role.')
    role=auth.canonical_role(role_value)
    driver_id=data.get('driver_id',old.get('driver_id') if role=='courier' else None) or None
    if driver_id is not None:
        try: driver_id=int(driver_id)
        except (ValueError,TypeError): raise ValueError('Select a valid driver.') from None
        driver=con.execute('SELECT * FROM drivers WHERE id=?',(driver_id,)).fetchone()
        if role!='courier' or not driver: raise ValueError('Only a courier can be linked to a valid driver.')
        if driver['user_id'] not in (None,old.get('id')): raise ValueError('This driver is already linked to another account.')
    else: driver=None
    branches=data.get('branch_ids',list(assigned['branch_ids']) if assigned else [])
    if not isinstance(branches,list) or len(branches)>100: raise ValueError('Branch memberships must be a list of active offices.')
    if driver and 'branch_ids' not in data and (not branches or driver_id!=old.get('driver_id')):
        scope=con.execute('SELECT branch_id FROM driver_scope WHERE driver_id=?',(driver_id,)).fetchone()
        branch=scope['branch_id'] if scope else branch_for_city(con,driver['branch'],driver['branch'])
        if branch: branches=[branch]
    if not branches and not assigned and 'branch_ids' not in data and role in ('branch_manager','office_employee','accountant') and role_value in ('admin','manager','employee'):
        default=con.execute("SELECT id FROM branches WHERE is_active=1 ORDER BY CASE WHEN code='JED-MAIN' THEN 0 ELSE 1 END,id LIMIT 1").fetchone()
        branches=[default['id']] if default else []
    old_primary=assigned['primary_branch_id'] if assigned else None
    primary=data.get('primary_branch_id',old_primary if any(str(x)==str(old_primary) for x in branches) else None)
    if primary=='': primary=None
    if primary is None and branches: primary=branches[0]
    return role,driver_id,branches,primary

def create_user(con, actor, data, password_hash, request):
    if not auth.allowed(actor,'users.manage'): raise auth.AccessDenied()
    username=str(data.get('username','')).strip(); name=str(data.get('display_name','')).strip()
    if not username or len(username)>160 or not name or len(name)>160: raise ValueError('Enter a valid account name and username.')
    if con.execute('SELECT 1 FROM users WHERE lower(username)=lower(?)',(username,)).fetchone(): raise ValueError('This username is already registered.')
    validate_password(data.get('password'))
    role,did,branches,primary=_assignment(con,data)
    active=data.get('is_active',True)
    if active not in (True,False,0,1): raise ValueError('Active state must be true or false.')
    cur=con.execute('INSERT INTO users(username,display_name,role,password_hash,mobile,national_id,driver_id,is_active) VALUES(?,?,?,?,?,?,?,?)',
        (username,name,auth.legacy_role(role),password_hash(data['password']),str(data.get('mobile',''))[:60],str(data.get('national_id',''))[:60],did,int(active)))
    uid=cur.lastrowid
    set_user_access(con,uid,role,branches,primary,global_scope=role=='system_admin')
    if role=='customer': customers.ensure_account(con,uid)
    if did: con.execute('UPDATE drivers SET user_id=? WHERE id=?',(uid,did))
    result=safe_user(con,con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())
    write_audit(con,actor,'user.created','user',uid,after=result,request=request)
    write_audit(con,actor,'user.role_changed','user',uid,after={'role':role},request=request)
    if branches: write_audit(con,actor,'user.branches_changed','user',uid,after={'branch_ids':branches,'primary_branch_id':primary},request=request)
    if did: write_audit(con,actor,'driver.account_assigned','driver',did,after={'user_id':uid},request=request)
    return result

def update_user(con, actor, uid, data, request, password_hash=None):
    if not auth.allowed(actor,'users.manage'): raise auth.AccessDenied()
    row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not row: raise ValueError('User not found.')
    before=safe_user(con,row)
    permitted={'display_name','mobile','national_id','role','driver_id','branch_ids','primary_branch_id','is_active','revoke_sessions','password'}
    if not data or set(data)-permitted: raise ValueError('Unsupported account fields.')
    if data.get('is_active',True) not in (True,False,0,1) or data.get('revoke_sessions',False) not in (True,False,0,1): raise ValueError('Active and session-revocation states must be true or false.')
    reset_password='password' in data
    new_hash=None
    if reset_password:
        validate_password(data['password'])
        if not callable(password_hash): raise ValueError('Password reset is unavailable without the configured hash helper.')
        new_hash=password_hash(data['password'])
    role,did,branches,primary=_assignment(con,data,row)
    active=int(data.get('is_active',row['is_active']))
    if row['id']==actor['user_id'] and (not active or role!='system_admin'):
        raise auth.AccessDenied('You cannot disable or demote your own administrator account.')
    if before['access_role']=='system_admin' and row['is_active'] and (not active or role!='system_admin'):
        others=con.execute("SELECT count(*) FROM users u JOIN user_access a ON a.user_id=u.id WHERE u.is_active=1 AND a.role='system_admin' AND a.global_scope=1 AND u.id<>?",(row['id'],)).fetchone()[0]
        if not others: raise ValueError('Keep at least one active system administrator.')
    name=str(data.get('display_name',row['display_name'])).strip()
    if not name or len(name)>160: raise ValueError('Enter a valid account display name.')
    con.execute('UPDATE users SET display_name=?,mobile=?,national_id=?,role=?,driver_id=?,is_active=? WHERE id=?',
        (name,str(data.get('mobile',row['mobile']))[:60],str(data.get('national_id',row['national_id']))[:60],auth.legacy_role(role),did,active,row['id']))
    if reset_password:
        con.execute('UPDATE users SET password_hash=? WHERE id=?',(new_hash,row['id']))
        write_audit(con,actor,'password.changed','user',row['id'],metadata={'reason':'administrator reset'},request=request)
    set_user_access(con,row['id'],role,branches,primary,global_scope=role=='system_admin')
    if role=='customer': customers.ensure_account(con,row['id'])
    if did!=row['driver_id'] or role!='courier':
        con.execute('UPDATE drivers SET user_id=NULL WHERE user_id=?',(row['id'],))
        if did: con.execute('UPDATE drivers SET user_id=? WHERE id=?',(row['id'],did))
        write_audit(con,actor,'driver.account_assigned','user',row['id'],before={'driver_id':row['driver_id']},after={'driver_id':did},request=request)
    result=safe_user(con,con.execute('SELECT * FROM users WHERE id=?',(row['id'],)).fetchone())
    access_changed=any(before[k]!=result[k] for k in ('access_role','branch_ids','primary_branch_id','driver_id','is_active'))
    if access_changed or data.get('revoke_sessions') or reset_password:
        count=con.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],)).rowcount
        write_audit(con,actor,'user.sessions_revoked','user',row['id'],metadata={'revoked_count':count},request=request)
    if before['access_role']!=role: write_audit(con,actor,'user.role_changed','user',row['id'],before={'role':before['access_role']},after={'role':role},request=request)
    if any(before[k]!=result[k] for k in ('branch_ids','primary_branch_id')):
        write_audit(con,actor,'user.branches_changed','user',row['id'],before={k:before[k] for k in ('branch_ids','primary_branch_id')},after={k:result[k] for k in ('branch_ids','primary_branch_id')},request=request)
    write_audit(con,actor,'user.updated','user',row['id'],before=before,after=result,request=request)
    if before['is_active']!=active: write_audit(con,actor,'user.activated' if active else 'user.deactivated','user',row['id'],request=request)
    return result
