"""Compatibility-aware state graph. Existing stored statuses are never rewritten."""
STATUS_NAMES = {
    'created':'تم إنشاء الشحنة', 'received':'تم استلام الشحنة',
    'at_origin':'في مكتب الإرسال', 'dispatched':'تم الترحيل للنقل',
    'in_transit':'قيد النقل', 'at_destination':'جاهز للتسليم',
    'out_for_delivery':'قيد التوصيل', 'delivered':'تم الاستلام', 'delayed':'تأخير',
}
STATUS_STAGES = {
    'created':'تم الإنشاء', 'received':'تم الاستلام في المكتب',
    'at_origin':'في مكتب الإرسال', 'dispatched':'تم الترحيل للنقل',
    'in_transit':'في الطريق', 'at_destination':'في الفرع',
    'out_for_delivery':'مندوب بالطريق', 'delivered':'تم التسليم', 'delayed':'مطلوب متابعة',
}
ALIASES = {value:key for key,value in STATUS_NAMES.items()}
ALIASES.update({key:key for key in STATUS_NAMES})
ALIASES.update({'Shipment Created':'created','Shipment Received':'received',
    'At Origin Office':'at_origin','Dispatched for Transport':'dispatched',
    'In Transit':'in_transit','Arrived at Destination Office':'at_destination',
    'Out for Delivery':'out_for_delivery','Delivered':'delivered',
    'وصلت إلى مكتب الوجهة':'at_destination'})
GRAPH = {
    'created':{'received','at_origin','dispatched','in_transit','out_for_delivery'},
    'received':{'at_origin','dispatched','in_transit','out_for_delivery'},
    'at_origin':{'dispatched','in_transit','out_for_delivery'},
    'dispatched':{'in_transit','out_for_delivery'},
    'in_transit':{'at_destination','out_for_delivery'},
    'at_destination':{'out_for_delivery','delivered'},
    'out_for_delivery':{'at_destination','delivered'},
    'delivered':set(),
}

def canonical(value):
    return ALIASES.get(value)

def storage_status(value):
    state=canonical(value)
    if state is None: raise ValueError('Invalid status')
    return STATUS_NAMES[state]

def check_transition(con, shipment, next_status, source='status'):
    current=canonical(shipment['status']); next_state=canonical(next_status)
    if next_state is None: raise ValueError('Invalid status')
    if current==next_state: return False
    if current=='delivered': raise ValueError('Completed deliveries cannot be reopened.')
    if source not in ('route','transfer') and next_state in ('at_destination','out_for_delivery','delivered'):
        pending=con.execute("""SELECT 1 FROM shipment_transfers WHERE shipment_id=?
            AND status IN ('planned','in_transit','awaiting_receipt')""",(shipment['id'],)).fetchone()
        if pending: raise ValueError('Receiving branch confirmation is required before delivery progress.')
    if next_state=='delayed': return True
    # Older dispatch screens permit reloading undelivered parcels. This exception
    # belongs only to a validated route action and is captured in its audit event.
    if source=='route' and next_state in ('in_transit','at_destination'): return True
    if source=='transfer' and next_state=='at_destination': return True
    if current=='delayed':
        events=con.execute('SELECT status FROM shipment_events WHERE shipment_id=? ORDER BY id DESC',(shipment['id'],)).fetchall()
        prior=next((canonical(r['status']) for r in events if canonical(r['status']) not in (None,'delayed')),None)
        if prior:
            return_allowed=next_state==prior or next_state in GRAPH.get(prior,set())
        else:
            # Legacy delayed rows do not always have a previous milestone.
            return_allowed=next_state in ('in_transit','at_destination','out_for_delivery')
        if return_allowed: return True
    elif next_state in GRAPH.get(current,set()): return True
    raise ValueError('Invalid shipment transition. Follow the shipment workflow.')

def ready_for_pod(con, shipment):
    if canonical(shipment['status'])!='out_for_delivery':
        raise ValueError('Set the shipment to Out for Delivery before requesting OTP or completing POD.')

def check_route_transition(route, next_status):
    """A repeated trip action never reassigns/reverts parcels or changes times."""
    if next_status not in ('في الطريق','وصلت','ملغاة'):
        raise ValueError('Invalid route status.')
    if route['status']==next_status: return False
    allowed={'مجدولة':{'في الطريق','ملغاة'},'في الطريق':{'وصلت','ملغاة'}}
    if next_status not in allowed.get(route['status'],set()):
        raise ValueError('Invalid route transition. Start a scheduled route before marking arrival.')
    return True
