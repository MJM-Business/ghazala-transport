"""One authoritative API permission/object-scope boundary and mutation auditing."""
import authorization as auth
from audit import write_audit
import foundation_schema as schema
import transitions
import shipment_transfers as transfers
import re

AUDIT_ENTITY={'shipments':'shipment','drivers':'driver','routes':'route','branches':'branch',
    'vehicles':'vehicle','clients':'client','campaigns':'campaign','users':'user','notifications':'notification'}

def require(ctx, permission):
    if not auth.allowed(ctx,permission): raise auth.AccessDenied('You do not have permission for this action.')

def read_permission(ctx, parts):
    if parts==['api','branch-directory']:
        if not (auth.allowed(ctx,'shipments.create') or auth.allowed(ctx,'routes.manage')): raise auth.AccessDenied()
        return
    entity=parts[1] if len(parts)>1 else ''
    permission={'shipments':'shipments.read','drivers':'drivers.read','routes':'routes.read','branches':'branches.read',
        'vehicles':'vehicles.read','clients':'clients.read','campaigns':'campaigns.read','pricing':'pricing.read',
        'users':'users.manage','stats':'stats.read','reports':'reports.read','notifications':'routes.read','audit':'audit.read'}.get(entity)
    if permission: require(ctx,permission)
    if entity=='shipments' and len(parts)==4 and parts[3]=='pod': require(ctx,'pod.read')

def rows(con,ctx,entity,select='*',alias='x',extra='1=1',args=(),order=''):
    table=auth.ENTITY_TABLES[entity]
    predicate,params=auth.sql_scope(ctx,entity,alias)
    return con.execute(f'SELECT {select} FROM {table} {alias} WHERE ({predicate}) AND ({extra}) {order}',[*params,*args]).fetchall()

def object_row(con,ctx,entity,identity,field='id'):
    if field not in ('id','awb'): raise ValueError('Unsupported object identifier')
    table=auth.ENTITY_TABLES[entity]; predicate,args=auth.sql_scope(ctx,entity,'x')
    row=con.execute(f'SELECT x.* FROM {table} x WHERE x.{field}=? AND ({predicate})',[identity,*args]).fetchone()
    if not row: raise auth.AccessDenied('Object is unavailable in your branch scope.')
    return row

def office(con,value,city=None):
    if isinstance(value,bool) or not re.fullmatch(r'[1-9][0-9]*',str(value or '').strip()):
        raise ValueError('Branch must be an active office.')
    try: value=int(value)
    except (TypeError,ValueError): raise ValueError('Branch must be an active office.') from None
    row=con.execute('SELECT * FROM branches WHERE id=? AND is_active=1',(value,)).fetchone()
    if not row or (city is not None and row['city']!=city): raise ValueError('Branch must match the selected city.')
    return row['id']

def _default_office(con,ctx,city):
    memberships=tuple(ctx.get('branch_ids') or ())
    if not ctx['global_scope'] and memberships:
        marks=','.join('?' for _ in memberships)
        row=con.execute(f'SELECT id FROM branches WHERE is_active=1 AND id IN ({marks}) AND (city=? OR code=?) ORDER BY id LIMIT 1',
            [*memberships,city,city]).fetchone()
        if row: return row['id']
    return schema.branch_for_city(con,city,city)

def origin_office(con,ctx,data,city,key='sender_branch_id'):
    selected=data.get(key) if data.get(key) is not None else data.get('origin_branch_id')
    if selected is None and ctx.get('primary_branch_id'):
        row=con.execute('SELECT city FROM branches WHERE id=? AND is_active=1',(ctx['primary_branch_id'],)).fetchone()
        if row and row['city']==city: selected=ctx['primary_branch_id']
    selected=office(con,selected,city) if selected is not None else _default_office(con,ctx,city)
    if selected is None: raise ValueError('Branch must be an active office.')
    if not ctx['global_scope'] and selected not in ctx['branch_ids']: raise auth.AccessDenied('Origin office is outside your branch scope.')
    return selected

def destination_office(con,data,city):
    if data.get('destination_branch_id') is not None: return office(con,data['destination_branch_id'],city)
    code=data.get('recipient_branch')
    if code:
        row=con.execute('SELECT id FROM branches WHERE code=? AND city=? AND is_active=1',(code,city)).fetchone()
        if not row: raise ValueError('Branch must match the selected city.')
        return row['id']
    branch=schema.branch_for_city(con,city)
    if branch is None: raise ValueError('Branch must be an active office.')
    return branch

def branch_for_payload(con,ctx,data,city_key='branch'):
    if data.get('branch_id') is not None:
        selected=office(con,data['branch_id'])
        b=con.execute('SELECT city,code FROM branches WHERE id=?',(selected,)).fetchone()
        if data.get(city_key) and data[city_key] not in (b['city'],b['code']): raise ValueError('Branch must match the selected city.')
    else:
        city=data.get(city_key)
        primary=con.execute('SELECT id,city,code FROM branches WHERE id=? AND is_active=1',(ctx.get('primary_branch_id'),)).fetchone()
        if primary and (not city or city in (primary['city'],primary['code'])):
            selected=primary['id']
        else:
            # Match the legacy default when the caller omitted a city, while
            # refusing to silently assign an unrelated office for an unknown city.
            selected=_default_office(con,ctx,city or 'جدة')
    if selected is None: raise ValueError('Branch must be an active office.')
    if not ctx['global_scope'] and selected not in ctx['branch_ids']: raise auth.AccessDenied('Object is unavailable in your branch scope.')
    return selected

def authorize_mutation(con,ctx,method,parts,data):
    entity=parts[1] if len(parts)>1 else ''; planned={}
    if entity=='password': return planned
    if entity=='admin': require(ctx,'demo.reset'); return planned
    if entity=='users': require(ctx,'users.manage'); return planned
    if entity in ('audit','audit_events'): raise auth.AccessDenied('Audit events are append-only.')
    action=parts[3] if len(parts)>3 else None
    permissions={'shipments':'shipments.create' if method=='POST' and len(parts)==2 else 'shipments.edit',
        'drivers':'drivers.manage','routes':'routes.manage','branches':'branches.manage','vehicles':'vehicles.manage',
        'clients':'clients.manage','campaigns':'campaigns.manage','pricing':'pricing.manage'}
    if entity=='routes' and action=='receive': permission='shipments.status'
    elif entity=='shipments' and action in ('otp','pod'): permission='pod.create'
    elif entity=='shipments' and method=='PATCH':
        permission='shipments.read'
        checks={'status':'shipments.status','eta':'shipments.edit','driver_id':'shipments.assign','payment_status':'shipments.payment'}
        if not data or set(data)-set(checks): raise ValueError('Unsupported shipment fields.')
        for key in data: require(ctx,checks[key])
        if ctx['role']=='courier' and ('status' not in data or transitions.canonical(data['status']) not in ('at_destination','out_for_delivery','delayed','delivered')): raise auth.AccessDenied()
    elif entity=='drivers' and action=='location': permission='drivers.location'
    else: permission=permissions.get(entity)
    if permission: require(ctx,permission)
    if len(parts)>2 and entity in auth.ENTITY_TABLES:
        row=object_row(con,ctx,entity,parts[2].upper() if entity=='shipments' else parts[2], 'awb' if entity=='shipments' else 'id')
        planned['existing']=dict(row)
    if entity=='branches' and method=='POST' and not ctx['global_scope']: raise auth.AccessDenied()
    if entity=='shipments':
        if len(parts)==2:
            planned['offices']=(origin_office(con,ctx,data,data.get('origin')),destination_office(con,data,data.get('destination')))
        if data.get('driver_id'):
            require(ctx,'shipments.assign'); object_row(con,ctx,'drivers',data['driver_id'])
    if entity=='routes':
        if len(parts)==2:
            awbs=list(dict.fromkeys(str(x).strip().upper() for x in data.get('awbs',[])))
            shipments=[object_row(con,ctx,'shipments',awb,'awb') for awb in awbs]
            if any(transfers.pending(con,row['id']) for row in shipments):
                raise transfers.PendingTransferError('Shipment already has a pending branch transfer.')
            if shipments:
                pair=schema.resolve_shipment_offices(con,shipments[0])
                if data.get('origin_branch_id') is not None: pair=(office(con,data['origin_branch_id'],data.get('origin')),pair[1])
                if data.get('destination_branch_id') is not None: pair=(pair[0],office(con,data['destination_branch_id'],data.get('destination')))
                if not ctx['global_scope'] and pair[0] not in ctx['branch_ids']: raise auth.AccessDenied('Origin office is outside your branch scope.')
                if any(schema.resolve_shipment_offices(con,row)!=pair for row in shipments): raise ValueError('Route parcels must belong to the same origin and destination offices.')
                planned['offices']=pair
            if data.get('driver_id'): object_row(con,ctx,'drivers',data['driver_id'])
            if data.get('vehicle_id'): object_row(con,ctx,'vehicles',data['vehicle_id'])
        else:
            # A scoped trip must never give authority to mutate a parcel that is
            # unrelated or has since been reassigned to another office/task.
            route=planned['existing']; pair=schema.resolve_route_offices(con,route)
            if action=='receive':
                awb=str(data.get('awb','')).strip().upper()
                if not awb: raise ValueError('Select the shipment to receive.')
                planned['receipt_transfer']=dict(transfers.authorize_receipt(con,ctx,route,awb))
            children=con.execute('SELECT s.* FROM shipments s JOIN route_shipments rs ON rs.shipment_id=s.id WHERE rs.route_id=?',(route['id'],)).fetchall()
            for child in children: auth.require_object(con,ctx,'shipments',child)
            if action=='scan' and data.get('awb'):
                child=object_row(con,ctx,'shipments',str(data['awb']).upper(),'awb')
                if transfers.pending(con,child['id']): raise transfers.PendingTransferError('Shipment already has a pending branch transfer.')
                if schema.resolve_shipment_offices(con,child)!=pair: raise ValueError('Route parcels must belong to the same origin and destination offices.')
                planned['scan_shipment']=dict(child)
    if entity=='drivers' and ('branch' in data or 'branch_id' in data or len(parts)==2):
        planned['branch_id']=branch_for_payload(con,ctx,data)
    if entity=='clients' and (len(parts)==2 or 'city' in data or 'branch_id' in data):
        planned['branch_id']=branch_for_payload(con,ctx,data,'city')
    if entity=='vehicles' and len(parts)==2:
        ids=data.get('branch_ids')
        if ids is None:
            default=ctx['primary_branch_id'] or schema.branch_for_city(con,'جدة')
            ids=[default] if default else []
        if not isinstance(ids,list) or not ids: raise ValueError('Assign the vehicle to at least one active office.')
        planned['branch_ids']=[office(con,x) for x in ids]
    return planned

def _snapshot(con,entity,row):
    row=dict(row)
    if entity=='drivers':
        scope=con.execute('SELECT branch_id FROM driver_scope WHERE driver_id=?',(row['id'],)).fetchone()
        row['branch_id']=scope['branch_id'] if scope and scope['branch_id'] is not None else schema.branch_for_city(con,row.get('branch'),row.get('branch'))
    elif entity=='clients':
        scope=con.execute('SELECT branch_id FROM client_scope WHERE client_id=?',(row['id'],)).fetchone()
        row['branch_id']=scope['branch_id'] if scope and scope['branch_id'] is not None else schema.branch_for_city(con,row.get('city'))
    elif entity=='shipments':
        row['origin_branch_id'],row['destination_branch_id']=schema.resolve_shipment_offices(con,row)
    elif entity=='routes':
        row['origin_branch_id'],row['destination_branch_id']=schema.resolve_route_offices(con,row)
    elif entity=='vehicles':
        row['branch_ids']=[r[0] for r in con.execute('SELECT branch_id FROM vehicle_branches WHERE vehicle_id=? ORDER BY branch_id',(row['id'],))]
    return row

def prepare_audit(con,parts,data,planned):
    entity=parts[1] if len(parts)>1 else ''; before=[]
    if planned.get('existing') is not None: before.append((entity,planned['existing']['id'],_snapshot(con,entity,planned['existing'])))
    if entity=='routes':
        if len(parts)==2:
            awbs=list(dict.fromkeys(str(x).strip().upper() for x in data.get('awbs',[])))
            if awbs:
                marks=','.join('?' for _ in awbs)
                before.extend(('shipments',r['id'],_snapshot(con,'shipments',r)) for r in con.execute(f'SELECT * FROM shipments WHERE awb IN ({marks})',awbs))
        elif planned.get('existing'):
            before.extend(('shipments',r['id'],_snapshot(con,'shipments',r)) for r in con.execute('SELECT s.* FROM shipments s JOIN route_shipments rs ON rs.shipment_id=s.id WHERE rs.route_id=?',(planned['existing']['id'],)))
        if planned.get('scan_shipment'): before.append(('shipments',planned['scan_shipment']['id'],_snapshot(con,'shipments',planned['scan_shipment'])))
        route=planned.get('existing',data)
        for kind,key in (('drivers','driver_id'),('vehicles','vehicle_id')):
            if route.get(key):
                row=con.execute(f'SELECT * FROM {auth.ENTITY_TABLES[kind]} WHERE id=?',(route[key],)).fetchone()
                if row: before.append((kind,row['id'],_snapshot(con,kind,row)))
    if entity=='pricing': before.append(('pricing','global',dict(con.execute('SELECT key,value FROM service_settings').fetchall())))
    if entity=='admin': before.append(('demo','global',{t:con.execute(f'SELECT count(*) FROM {t} WHERE is_demo=1').fetchone()[0] for t in ('shipments','drivers','clients','campaigns')}))
    return before

def finish_mutation(con,ctx,parts,data,planned,before,result,request):
    entity=parts[1] if len(parts)>1 else ''; identity=result.get('id') if isinstance(result,dict) else None
    created=request.command=='POST' and len(parts)==2
    if created and entity in auth.ENTITY_TABLES and identity:
        if entity=='shipments': schema.persist_shipment_scope(con,identity,*planned['offices'])
        if entity=='routes' and planned.get('offices'): schema.persist_route_scope(con,identity,*planned['offices'])
        if entity=='drivers': schema.persist_driver_scope(con,identity,planned['branch_id'])
        if entity=='clients': schema.persist_client_scope(con,identity,planned['branch_id'])
        if entity=='vehicles': schema.persist_vehicle_branches(con,identity,planned['branch_ids'])
        after=_snapshot(con,entity,con.execute(f'SELECT * FROM {auth.ENTITY_TABLES[entity]} WHERE id=?',(identity,)).fetchone())
        kind=AUDIT_ENTITY.get(entity,entity)
        write_audit(con,ctx,kind+'.created',kind,identity,after=after,metadata=planned,request=request)
    route_id=identity if created and entity=='routes' else planned.get('existing',{}).get('id')
    route_metadata={'reason':'route propagation','route_id':route_id} if entity=='routes' else {}
    if entity=='routes' and len(parts)==3 and data.get('status')=='وصلت' and planned.get('existing',{}).get('driver_id'):
        route=planned['existing']; pair=schema.resolve_route_offices(con,route)
        if pair[1]: schema.persist_driver_scope(con,route['driver_id'],pair[1])
    for kind,uid,old in before:
        if kind=='pricing':
            new=dict(con.execute('SELECT key,value FROM service_settings').fetchall())
            write_audit(con,ctx,'pricing.changed','pricing',uid,before=old,after=new,request=request); continue
        if kind=='demo':
            new={t:con.execute(f'SELECT count(*) FROM {t} WHERE is_demo=1').fetchone()[0] for t in old}
            write_audit(con,ctx,'demo.reset','demo',uid,before=old,after=new,metadata={'demo_data_disabled':True},request=request); continue
        if entity=='drivers' and kind=='drivers' and planned.get('branch_id'): schema.persist_driver_scope(con,uid,planned['branch_id'])
        if entity=='clients' and kind=='clients' and planned.get('branch_id'): schema.persist_client_scope(con,uid,planned['branch_id'])
        new=_snapshot(con,kind,con.execute(f'SELECT * FROM {auth.ENTITY_TABLES[kind]} WHERE id=?',(uid,)).fetchone())
        if old==new: continue
        singular=AUDIT_ENTITY.get(kind,kind)
        action=singular+'.updated'
        if kind in ('drivers','clients') and old.get('branch_id')!=new.get('branch_id'):
            write_audit(con,ctx,singular+'.branch_changed',singular,uid,before={'branch_id':old.get('branch_id')},after={'branch_id':new.get('branch_id')},metadata=route_metadata,request=request)
        if kind=='shipments':
            if old['status']!=new['status']:
                action='shipment.status_changed'
                write_audit(con,ctx,action,'shipment',uid,before={'status':old['status'],'stage':old['stage']},after={'status':new['status'],'stage':new['stage']},request=request)
            if old['driver_id']!=new['driver_id']:
                write_audit(con,ctx,'shipment.driver_assigned','shipment',uid,before={'driver_id':old['driver_id']},after={'driver_id':new['driver_id']},request=request)
            if old['payment_status']!=new['payment_status']:
                write_audit(con,ctx,'shipment.payment_recorded','shipment',uid,before={'payment_status':old['payment_status']},after={'payment_status':new['payment_status']},request=request)
        write_audit(con,ctx,singular+'.updated',singular,uid,before=old,after=new,metadata=route_metadata if kind!=entity else {},request=request)
    if entity=='routes' and len(parts)==4 and parts[3]=='scan':
        parcel=planned['scan_shipment']
        write_audit(con,ctx,'route.parcel_scanned','route',planned['existing']['id'],metadata={'shipment_id':parcel['id'],'awb':parcel['awb']},request=request)
    if entity=='shipments' and len(parts)==4 and parts[3]=='otp':
        write_audit(con,ctx,'pod.otp_issued','shipment',planned['existing']['id'],metadata={'expires_in':result.get('expires_in'),'delivery':result.get('delivery')},request=request)
    if entity=='shipments' and len(parts)==4 and parts[3]=='pod':
        row=planned['existing']; proof=con.execute('SELECT id,verified_at FROM pod_records WHERE shipment_id=?',(row['id'],)).fetchone()
        write_audit(con,ctx,'pod.completed','shipment',row['id'],metadata={'proof_id':proof['id'],'verified_at':proof['verified_at']},request=request)
