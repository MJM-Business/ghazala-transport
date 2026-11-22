"""Ghazala Transport operational portal: Python API with persistent SQLite."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import traceback
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote, urlencode, quote
from urllib.request import Request, urlopen
from datetime import datetime, timezone, timedelta
import argparse, base64, hashlib, hmac, io, json, math, os, re, secrets, sqlite3, threading, time, uuid
from migrations import apply_migrations
import authorization as auth
import request_policy as policy
import transitions
import shipment_transfers as transfers
import accounts
import customer_accounts as customers
from audit import write_audit
from foundation_schema import migration3, adopt_seed_scope
from security import LOGIN_THROTTLE, validate_password, same_origin, session_cookie
try:
    import reports  # Set up optional local report dependencies before font libraries load.
except ImportError:
    reports = None

REPORT_DOWNLOADS = {}
REPORT_DOWNLOAD_LOCK = threading.Lock()

def keep_report_download(user_id, raw, mime, filename, scope_key=None):
    """Short-lived, session-protected file links also work in mobile webviews."""
    ticket = secrets.token_urlsafe(32)
    with REPORT_DOWNLOAD_LOCK:
        now=time.time()
        for old in list(REPORT_DOWNLOADS):
            if REPORT_DOWNLOADS[old]["expires"]<=now:
                del REPORT_DOWNLOADS[old]
        while REPORT_DOWNLOADS and (len(REPORT_DOWNLOADS)>=20 or sum(len(item["raw"]) for item in REPORT_DOWNLOADS.values())+len(raw)>32*1024*1024):
            del REPORT_DOWNLOADS[next(iter(REPORT_DOWNLOADS))]
        REPORT_DOWNLOADS[ticket]={"user_id":user_id,"raw":raw,"mime":mime,"filename":filename,"scope_key":scope_key,"expires":now+180}
    return "/api/reports/shipments?ticket="+ticket

ROOT = Path(__file__).parent
DB = ROOT / "work" / "ghazala.sqlite3"
DB.parent.mkdir(exist_ok=True)
ROLES = {"admin", "manager", "employee"}
DEMO_USERS = [
    ("admin@ghazala.sa", 'مدير النظام', "admin", "Admin123!"),
    ("manager@ghazala.sa", 'مدير العمليات', "manager", "Manager123!"),
    ("employee@ghazala.sa", 'موظف العمليات', "employee", "Employee123!"),
]
SEED_SHIPMENTS = [
    ("GHZ-000125", 'سلطان المعمري', "+966 55 987 6543", 'جدة', 'جازان', 'قيد التوصيل', 'مندوب بالطريق', 2450, 'اليوم 14:30'),
    ("GHZ-000139", 'محمد إبراهيم الشمري', "+966 50 123 4567", 'جازان', 'جدة', 'قيد التوصيل', 'في الطريق', 1850, 'اليوم 16:00'),
    ("GHZ-000208", 'أحمد بن منصور', "+966 54 330 8123", 'جدة', 'جازان', 'جاهز للتسليم', 'في الفرع', 450, 'غداً 09:00'),
    ("GHZ-000315", 'عمرو فاروق الشريف', "+966 56 901 7741", 'جازان', 'جدة', 'تم الاستلام', 'تم الاستلام', 0, 'مكتمل'),
    ("GHZ-000922", 'يوسف الصالح', "+966 53 194 4400", 'جدة', 'جازان', 'تأخير', 'مطلوب متابعة', 1280, 'متأخر 3 ساعات'),
    ("GHZ-000874", 'نورة العتيبي', "+966 59 320 7761", 'جازان', 'جدة', 'قيد النقل', 'في الطريق', 720, 'اليوم 20:15'),
]
SEED_DRIVERS = [
    ('سلطان المعمري', "1000000125", "+966 55 987 6543", 'جدة', 'متاح', 'طريق الملك عبدالعزيز، جدة', 21.5433, 39.1728),
    ('أحمد منصور الشهري', "1000000139", "+966 50 123 4567", 'جازان', 'نشط', 'فرع جازان', None, None),
    ('عمرو فاروق الشريف', "1000000208", "+966 56 901 7741", 'جدة', 'متاح', 'فرع جدة', None, None),
    ('يوسف الصالح', "1000000922", "+966 53 194 4400", 'جازان', 'نشط', 'فرع جازان', None, None),
]

class OperationalConnection(sqlite3.Connection):
    """Commit/rollback normally, then release the SQLite handle on every exit."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect():
    con = sqlite3.connect(DB, factory=OperationalConnection)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 240_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"

def verify_password(password, encoded):
    try:
        _, salt, digest = encoded.split("$")
        return hmac.compare_digest(password_hash(password, salt).split("$")[-1], digest)
    except (ValueError, AttributeError):
        return False

def setting(con, key, default):
    row=con.execute("SELECT value FROM service_settings WHERE key=?",(key,)).fetchone()
    try: return float(row["value"]) if row else float(default)
    except (TypeError,ValueError): return float(default)

PRICING_DEFAULTS={
    "base_fee":65,
    "included_weight":1,
    "extra_kg_fee":2.5,
    "vat_rate":0.15,
    "cod_fee":3.5,
    "insurance_rate":0.02,
    "insurance_minimum":5,
}

def pricing_sizes(con, active_only=False):
    where=" WHERE is_active=1" if active_only else ""
    return [dict(row) for row in con.execute(
        """SELECT id,code,label_en,label_ar,length_cm,width_cm,height_cm,
                  examples_en,examples_ar,base_fee,is_active,manual_only,sort_order,
                  created_at,updated_at
           FROM pricing_sizes"""+where+"""
           ORDER BY sort_order,id"""
    ).fetchall()]

def pricing_payload(con):
    payload={key:setting(con,key,value) for key,value in PRICING_DEFAULTS.items()}
    payload["sizes"]=pricing_sizes(con)
    return payload

def _normalized_dimensions(length_cm,width_cm,height_cm):
    dims=[float(length_cm or 0),float(width_cm or 0),float(height_cm or 0)]
    if any(not math.isfinite(value) or value<0 for value in dims):
        raise ValueError("Check the shipment dimensions.")
    if any(dims) and not all(value>0 for value in dims):
        raise ValueError("Enter length, width and height together.")
    return sorted(dims)

def _size_fits(row,dims):
    if not dims or not any(dims):
        return True
    limits=sorted([
        float(row["length_cm"] or 0),
        float(row["width_cm"] or 0),
        float(row["height_cm"] or 0),
    ])
    return all(value<=limit+1e-9 for value,limit in zip(dims,limits))

def recommend_pricing_size(con, length_cm=0, width_cm=0, height_cm=0, requested_code=""):
    dims=_normalized_dimensions(length_cm,width_cm,height_cm)
    requested=str(requested_code or "").strip().upper()
    if requested:
        row=con.execute(
            "SELECT * FROM pricing_sizes WHERE upper(code)=upper(?) AND is_active=1",
            (requested,)
        ).fetchone()
        if not row:
            raise ValueError("Selected parcel size is not available.")
        row=dict(row)
        if dims and any(dims) and not _size_fits(row,dims):
            raise ValueError("Shipment dimensions exceed the selected parcel size.")
        return row

    if not dims or not any(dims):
        return None

    rows=con.execute(
        """SELECT * FROM pricing_sizes
           WHERE is_active=1 AND manual_only=0
           ORDER BY sort_order,id"""
    ).fetchall()
    for row in rows:
        candidate=dict(row)
        if _size_fits(candidate,dims):
            return candidate

    raise ValueError(
        "Shipment dimensions exceed the automatic size categories. "
        "Select Pallet if appropriate or contact Ghazala Transport."
    )

def calculate_quote(con, data, customer_user_id=None):
    weight=max(0.5,float(data.get("weight",0.5) or 0.5))
    pieces=max(1,int(data.get("pieces",1) or 1))
    declared=max(0,float(data.get("declared_value",0) or 0))
    if not math.isfinite(weight) or weight>100000 or pieces>100 or not math.isfinite(declared):
        raise ValueError("Check shipment weight, pieces and declared value.")

    size=recommend_pricing_size(
        con,
        data.get("length_cm",0),
        data.get("width_cm",0),
        data.get("height_cm",0),
        data.get("pricing_size_code",""),
    )
    size_fee=float(size["base_fee"]) if size else setting(con,"base_fee",65)
    weight_surcharge=max(
        0,
        weight-setting(con,"included_weight",1)
    )*setting(con,"extra_kg_fee",2.5)
    base=size_fee+weight_surcharge

    cod_fee=setting(con,"cod_fee",3.5) if data.get("payment_method","cod")=="cod" else 0
    insurance_fee=max(
        setting(con,"insurance_minimum",5),
        declared*setting(con,"insurance_rate",0.02)
    ) if data.get("insured") else 0
    base=round(base,2)
    size_fee=round(size_fee,2)
    weight_surcharge=round(weight_surcharge,2)
    cod_fee=round(cod_fee,2)
    insurance_fee=round(insurance_fee,2)

    promo=campaign_coupon_quote(
        con,
        data.get("promo_code",""),
        base,
        base+cod_fee+insurance_fee,
        customer_user_id=customer_user_id,
    )
    discount_amount=round(float(promo.get("discount_amount",0) or 0),2)
    taxable=max(0,base+cod_fee+insurance_fee-discount_amount)
    vat=round(taxable*setting(con,"vat_rate",0.15),2)

    return {
        "shipping_fee":base,
        "size_fee":size_fee,
        "weight_surcharge":weight_surcharge,
        "cod_fee":cod_fee,
        "insurance_fee":insurance_fee,
        "discount_amount":discount_amount,
        "promo_code":promo.get("promo_code",""),
        "campaign_id":promo.get("campaign_id"),
        "campaign_name":promo.get("campaign_name",""),
        "vat_amount":vat,
        "total_fee":round(taxable+vat,2),
        "pieces":pieces,
        "weight":weight,
        "size_code":size["code"] if size else "",
        "size_label":(size["label_en"] or size["code"]) if size else "",
        "size":({
            "id":size["id"],
            "code":size["code"],
            "label_en":size["label_en"],
            "label_ar":size["label_ar"],
            "length_cm":size["length_cm"],
            "width_cm":size["width_cm"],
            "height_cm":size["height_cm"],
            "examples_en":size["examples_en"],
            "examples_ar":size["examples_ar"],
            "base_fee":size["base_fee"],
            "manual_only":bool(size["manual_only"]),
        } if size else None),
    }


def validate_campaign_dates(start_at, end_at):
    dates=[]
    try:
        for value in (start_at,end_at):
            if not value:
                dates.append(None)
                continue
            date=datetime.fromisoformat(str(value))
            dates.append(date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc))
    except (TypeError,ValueError):
        raise ValueError('تحقق من تواريخ بداية ونهاية الحملة')
    if dates[0] and dates[1] and dates[1]<dates[0]:
        raise ValueError('تاريخ نهاية الحملة يجب أن يكون بعد تاريخ البداية')

def send_sms(con, phone, purpose, message):
    sid=os.environ.get("TWILIO_ACCOUNT_SID","").strip()
    token=os.environ.get("TWILIO_AUTH_TOKEN","").strip()
    sender=os.environ.get("TWILIO_FROM_NUMBER","").strip()
    delivery="demo"; error=""
    if sid and token and sender:
        try:
            body=urlencode({"To":phone,"From":sender,"Body":message}).encode()
            auth=base64.b64encode(f"{sid}:{token}".encode()).decode()
            request=Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",data=body,
              headers={"Authorization":f"Basic {auth}","Content-Type":"application/x-www-form-urlencoded"})
            with urlopen(request,timeout=10) as response: response.read()
            delivery="sent"
        except Exception as exc:
            delivery="failed"; error=str(exc)[:300]
    con.execute("INSERT INTO sms_outbox(phone,purpose,message,delivery,provider_error) VALUES(?,?,?,?,?)",
      (phone,purpose,message,delivery,error))
    return {"delivery":delivery,"error":error}

def decode_data_url(value, allowed_mimes, max_bytes=3_000_000):
    if not value: return None,""
    if not isinstance(value,str) or ";base64," not in value: raise ValueError("Invalid image data")
    header,payload=value.split(",",1); mime=header[5:].split(";",1)[0]
    if mime not in allowed_mimes: raise ValueError("Unsupported image type")
    data=base64.b64decode(payload,validate=True)
    if len(data)>max_bytes: raise ValueError("Image exceeds the size limit")
    return data,mime

def validate_signature_image(raw):
    """Validate the stored PNG bytes, rather than trusting a data URL's MIME label."""
    from PIL import Image
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG" or image.width * image.height > 4_000_000:
                raise ValueError()
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise ValueError("Signature must be a valid PNG image.") from None

def create_operational_status_notification(con, shipment_id, status):
    """Create/update one management in-app alert per shipment lifecycle status.

    The notification type is status-specific, so the same status is deduplicated
    while a genuine move to a new lifecycle state creates a new unread alert.
    Customer-facing notifications remain handled separately by add_shipment_event().
    """
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='operational_notifications'"
    ).fetchone():
        return None

    canonical=transitions.canonical(status)
    lifecycle={
        "created",
        "received",
        "at_origin",
        "dispatched",
        "in_transit",
        "at_destination",
        "out_for_delivery",
        "delivered",
        "delayed",
    }
    if canonical not in lifecycle:
        return None

    shipment=con.execute(
        "SELECT id,awb FROM shipments WHERE id=?",(shipment_id,)
    ).fetchone()
    if not shipment:
        return None

    branch_id=None
    if con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='shipment_scope'"
    ).fetchone():
        scope=con.execute(
            "SELECT origin_branch_id,destination_branch_id FROM shipment_scope WHERE shipment_id=?",
            (shipment_id,)
        ).fetchone()
        if scope:
            destination_states={"dispatched","in_transit","at_destination","out_for_delivery","delivered","delayed"}
            branch_id=(
                scope["destination_branch_id"]
                if canonical in destination_states
                else scope["origin_branch_id"]
            )

    notification_type=f"shipment_status_{canonical}"
    con.execute(
        """INSERT INTO operational_notifications(
             notification_type,shipment_id,branch_id,title,message
           ) VALUES(?,?,?,?,?)
           ON CONFLICT(notification_type,shipment_id) DO UPDATE SET
             branch_id=excluded.branch_id,title=excluded.title,message=excluded.message,
             created_at=CURRENT_TIMESTAMP""",
        (notification_type,shipment_id,branch_id,"",str(status or ""))
    )
    notification=con.execute(
        """SELECT id FROM operational_notifications
           WHERE notification_type=? AND shipment_id=?""",
        (notification_type,shipment_id)
    ).fetchone()
    if notification:
        # A repeated transition to the same lifecycle state re-opens the existing
        # logical alert instead of producing duplicate notification rows.
        con.execute(
            "DELETE FROM operational_notification_reads WHERE notification_id=?",
            (notification["id"],)
        )
        return notification["id"]
    return None


def add_shipment_event(con, shipment_id, status, stage, location, actor):
    cur=con.execute("INSERT INTO shipment_events(shipment_id,status,stage,location,actor) VALUES(?,?,?,?,?)",
      (shipment_id,status,stage,location,actor))
    create_operational_status_notification(con,shipment_id,status)
    # Customer-facing event notifications share one durable source key so the
    # in-app notice and any configured external channels stay deduplicated.
    linked_customer=False
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='customer_notifications'").fetchone():
        owner=con.execute(
            """SELECT cs.customer_user_id,s.awb
               FROM customer_shipments cs JOIN shipments s ON s.id=cs.shipment_id
               WHERE cs.shipment_id=?""",(shipment_id,)
        ).fetchone()
        if owner:
            linked_customer=True
            title=f"Shipment {owner['awb']} · {status}"
            message=" · ".join(part for part in (str(stage or "").strip(),str(location or "").strip()) if part) or str(status)
            source_key=f"shipment-event:{cur.lastrowid}"
            create_customer_notification(
                con,owner["customer_user_id"],title,message,
                category="shipment",shipment_id=shipment_id,
                source_key=source_key
            )
            if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='notification_delivery_log'").fetchone():
                dispatch_customer_notification_channels(
                    con,owner["customer_user_id"],title,message,
                    category="shipment",shipment_id=shipment_id,source_key=source_key,
                    include_sms=False,include_whatsapp=False
                )
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='notification_delivery_log'").fetchone():
        dispatch_shipment_contact_whatsapp(con,shipment_id,status,"")

class DeliveryPolicyError(ValueError):
    pass


def require_delivery_eligible(shipment):
    if shipment["status"] == 'تم الاستلام':
        raise DeliveryPolicyError("This shipment has already been delivered.")
    try: transitions.ready_for_pod(None, shipment)
    except ValueError as exc: raise DeliveryPolicyError(str(exc)) from None
    if shipment["payment_method"] == "sender" and shipment["payment_status"] != 'مدفوع':
        raise DeliveryPolicyError("Record prepaid shipping fees before completing delivery.")


def validate_coordinates(latitude, longitude):
    if (latitude is None) != (longitude is None):
        raise ValueError("Location coordinates must be a valid latitude/longitude pair.")
    if latitude is None:
        return None, None
    try:
        latitude, longitude = float(latitude), float(longitude)
    except (TypeError, ValueError):
        raise ValueError("Location coordinates must be a valid latitude/longitude pair.") from None
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Location coordinates must be a valid latitude/longitude pair.")
    return latitude, longitude


def validate_shipment_transition(con, shipment, next_status, source="status"):
    """One completion rule, shared by status changes, POD and trip propagation.

    Historical delivered rows remain valid even if they predate POD enforcement.
    A new delivery requires persisted signature evidence and a verified OTP in
    the same transaction; client payload flags can never authorize completion.
    Returns False for an unchanged historical completed status.
    """
    if shipment["status"] == 'تم الاستلام':
        if next_status != 'تم الاستلام':
            raise DeliveryPolicyError("Completed deliveries cannot be reopened.")
        return False
    try:
        changed=transitions.check_transition(con,shipment,next_status,source=source)
    except ValueError as exc: raise DeliveryPolicyError(str(exc)) from None
    if not changed: return False
    if next_status == 'تم الاستلام':
        require_delivery_eligible(shipment)
        proof = con.execute("SELECT recipient_name,signature_data FROM pod_records WHERE shipment_id=?",(shipment["id"],)).fetchone()
        verified = con.execute("SELECT 1 FROM delivery_otps WHERE shipment_id=? AND verified_at IS NOT NULL AND verified_at<=expires_at LIMIT 1",(shipment["id"],)).fetchone()
        if not proof or not str(proof["recipient_name"]).strip() or not proof["signature_data"] or not verified:
            raise DeliveryPolicyError("Complete delivery through the POD screen with a valid OTP and signature.")
        try: validate_signature_image(proof["signature_data"])
        except ValueError as exc: raise DeliveryPolicyError(str(exc)) from None
    return True


def code_svg(value, kind):
    from reportlab.graphics import renderSVG
    if kind=="barcode":
        from reportlab.graphics.barcode import createBarcodeDrawing
        drawing=createBarcodeDrawing("Code128",value=value,barWidth=2,barHeight=46,humanReadable=True,quiet=True)
    else:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        widget=QrCodeWidget(value); bounds=widget.getBounds()
        width,height=bounds[2]-bounds[0],bounds[3]-bounds[1]
        drawing=Drawing(width,height,transform=[1,0,0,1,-bounds[0],-bounds[1]])
        drawing.add(widget)
    return renderSVG.drawToString(drawing).encode()


NOTIFICATION_CHANNELS=("in_app","sms","whatsapp","email")
NOTIFICATION_CATEGORIES=("shipment","payment","delivery","pickup","marketing","general")


def notification_provider_status():
    twilio=bool(os.environ.get("TWILIO_ACCOUNT_SID","").strip() and
                os.environ.get("TWILIO_AUTH_TOKEN","").strip())
    return {
        "in_app":{"configured":True,"provider":"Ghazala"},
        "sms":{"configured":bool(twilio and os.environ.get("TWILIO_FROM_NUMBER","").strip()),"provider":"Twilio"},
        "whatsapp":{"configured":bool(twilio and os.environ.get("TWILIO_WHATSAPP_FROM","").strip()),"provider":"Twilio WhatsApp"},
        "email":{"configured":bool(os.environ.get("SMTP_HOST","").strip() and os.environ.get("SMTP_FROM","").strip()),"provider":"SMTP"},
    }


def _notification_center_v16(c):
    """Version 16: durable multichannel notification center and preferences."""
    c.execute("""CREATE TABLE IF NOT EXISTS notification_preferences(
      user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
      in_app_enabled INTEGER NOT NULL DEFAULT 1 CHECK(in_app_enabled IN (0,1)),
      sms_enabled INTEGER NOT NULL DEFAULT 1 CHECK(sms_enabled IN (0,1)),
      whatsapp_enabled INTEGER NOT NULL DEFAULT 1 CHECK(whatsapp_enabled IN (0,1)),
      email_enabled INTEGER NOT NULL DEFAULT 1 CHECK(email_enabled IN (0,1)),
      shipment_updates INTEGER NOT NULL DEFAULT 1 CHECK(shipment_updates IN (0,1)),
      payment_updates INTEGER NOT NULL DEFAULT 1 CHECK(payment_updates IN (0,1)),
      delivery_updates INTEGER NOT NULL DEFAULT 1 CHECK(delivery_updates IN (0,1)),
      pickup_updates INTEGER NOT NULL DEFAULT 1 CHECK(pickup_updates IN (0,1)),
      marketing_updates INTEGER NOT NULL DEFAULT 1 CHECK(marketing_updates IN (0,1)),
      preferred_language TEXT NOT NULL DEFAULT 'en',
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS route_notification_reads(
      notification_id INTEGER NOT NULL REFERENCES branch_notifications(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      read_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(notification_id,user_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS notification_delivery_log(
      id INTEGER PRIMARY KEY,
      user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      customer_user_id INTEGER REFERENCES customer_accounts(user_id) ON DELETE SET NULL,
      shipment_id INTEGER REFERENCES shipments(id) ON DELETE SET NULL,
      category TEXT NOT NULL DEFAULT 'general',
      event_type TEXT NOT NULL DEFAULT '',
      source_key TEXT NOT NULL,
      channel TEXT NOT NULL CHECK(channel IN ('in_app','sms','whatsapp','email')),
      recipient TEXT NOT NULL DEFAULT '',
      title TEXT NOT NULL DEFAULT '',
      message TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','sent','demo','failed','not_configured','skipped')),
      provider TEXT NOT NULL DEFAULT '',
      provider_message_id TEXT NOT NULL DEFAULT '',
      provider_error TEXT NOT NULL DEFAULT '',
      attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
      max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 10),
      last_attempt_at TEXT,
      next_attempt_at TEXT,
      sent_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(source_key,channel,recipient)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS notification_templates(
      template_key TEXT PRIMARY KEY,
      category TEXT NOT NULL,
      title_en TEXT NOT NULL DEFAULT '', body_en TEXT NOT NULL DEFAULT '',
      title_ar TEXT NOT NULL DEFAULT '', body_ar TEXT NOT NULL DEFAULT '',
      default_channels TEXT NOT NULL DEFAULT 'in_app',
      is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_route_notification_reads_user ON route_notification_reads(user_id,read_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notification_delivery_user ON notification_delivery_log(user_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notification_delivery_customer ON notification_delivery_log(customer_user_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notification_delivery_shipment ON notification_delivery_log(shipment_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notification_delivery_retry ON notification_delivery_log(status,next_attempt_at,id)")
    c.execute("""INSERT OR IGNORE INTO notification_preferences(user_id)
                 SELECT id FROM users""")
    templates=[
      ("shipment_status","shipment","Shipment update","Your shipment status has changed.","تحديث الشحنة","تم تحديث حالة شحنتك.","in_app,email,whatsapp"),
      ("payment_received","payment","Payment received","Your payment has been recorded.","تم استلام الدفعة","تم تسجيل دفعتك بنجاح.","in_app,sms,email,whatsapp"),
      ("delivery_exception","delivery","Delivery exception","A delivery attempt needs attention.","تعذر التسليم","تحتاج محاولة التسليم إلى متابعة.","in_app,sms,email,whatsapp"),
      ("delivery_completed","delivery","Delivery completed","Your shipment was delivered successfully.","اكتمل التسليم","تم تسليم شحنتك بنجاح.","in_app,sms,email,whatsapp"),
      ("pickup_update","pickup","Pickup update","Your pickup request has been updated.","تحديث الاستلام","تم تحديث طلب استلام الشحنة.","in_app,sms,email,whatsapp"),
      ("campaign_offer","marketing","New offer","A new Ghazala offer is available.","عرض جديد","يوجد عرض جديد من غزالا.","in_app,email,whatsapp"),
    ]
    c.executemany("""INSERT OR IGNORE INTO notification_templates(
        template_key,category,title_en,body_en,title_ar,body_ar,default_channels)
        VALUES(?,?,?,?,?,?,?)""",templates)


def notification_preferences(con,user_id):
    con.execute("INSERT OR IGNORE INTO notification_preferences(user_id) VALUES(?)",(user_id,))
    row=con.execute("SELECT * FROM notification_preferences WHERE user_id=?",(user_id,)).fetchone()
    item=dict(row)
    for key in ("in_app_enabled","sms_enabled","whatsapp_enabled","email_enabled","shipment_updates","payment_updates","delivery_updates","pickup_updates","marketing_updates"):
        item[key]=bool(item[key])
    return item


def update_notification_preferences(con,user_id,data):
    allowed={"in_app_enabled","sms_enabled","whatsapp_enabled","email_enabled",
             "shipment_updates","payment_updates","delivery_updates","pickup_updates",
             "marketing_updates","preferred_language"}
    if not isinstance(data,dict) or not data or set(data)-allowed:
        raise ValueError("Unsupported notification preference fields.")
    current=notification_preferences(con,user_id)
    updates={}
    for key in allowed:
        if key not in data: continue
        if key=="preferred_language":
            lang=str(data[key] or "en").strip().lower()
            if lang not in ("ar","en","ur","hi","bn"):
                raise ValueError("Unsupported notification language.")
            updates[key]=lang
        else:
            value=data[key]
            if isinstance(value,str):
                value=value.strip().lower() in ("1","true","yes","on")
            updates[key]=1 if bool(value) else 0
    if updates:
        con.execute("UPDATE notification_preferences SET "+",".join(k+"=?" for k in updates)+",updated_at=CURRENT_TIMESTAMP WHERE user_id=?",[*updates.values(),user_id])
    return notification_preferences(con,user_id)


def _notification_category_enabled(pref,category):
    key={"shipment":"shipment_updates","payment":"payment_updates","delivery":"delivery_updates",
         "pickup":"pickup_updates","marketing":"marketing_updates"}.get(category)
    return True if not key else bool(pref.get(key,True))


def _customer_contact(con,user_id):
    row=con.execute("""SELECT u.id,u.username,u.mobile,u.display_name,
                    COALESCE(bp.email,'') AS profile_email
             FROM users u LEFT JOIN customer_business_profiles bp ON bp.user_id=u.id
             WHERE u.id=?""",(user_id,)).fetchone()
    if not row: return {"mobile":"","email":"","display_name":""}
    email=str(row["profile_email"] or "").strip()
    if not email and "@" in str(row["username"] or ""):
        email=str(row["username"]).strip()
    return {"mobile":str(row["mobile"] or "").strip(),"email":email,"display_name":row["display_name"]}


def _notification_log_upsert(con,*,user_id=None,customer_user_id=None,shipment_id=None,category="general",event_type="",source_key,channel,recipient,title,message,status="queued",provider="",provider_error="",attempt_count=0,sent_at=None,next_attempt_at=None):
    con.execute("""INSERT INTO notification_delivery_log(
        user_id,customer_user_id,shipment_id,category,event_type,source_key,channel,recipient,title,message,
        status,provider,provider_error,attempt_count,last_attempt_at,next_attempt_at,sent_at
      ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,CASE WHEN ?>0 THEN CURRENT_TIMESTAMP ELSE NULL END,?,?)
      ON CONFLICT(source_key,channel,recipient) DO UPDATE SET
        status=excluded.status,provider=excluded.provider,provider_error=excluded.provider_error,
        attempt_count=MAX(notification_delivery_log.attempt_count,excluded.attempt_count),
        last_attempt_at=excluded.last_attempt_at,next_attempt_at=excluded.next_attempt_at,
        sent_at=COALESCE(notification_delivery_log.sent_at,excluded.sent_at)""",
      (user_id,customer_user_id,shipment_id,str(category or "general")[:80],str(event_type or "")[:120],
       str(source_key)[:240],channel,str(recipient or "")[:320],str(title or "")[:240],str(message or "")[:2000],
       status,str(provider or "")[:80],str(provider_error or "")[:500],int(attempt_count or 0),int(attempt_count or 0),
       next_attempt_at,sent_at))


def _send_whatsapp(con,recipient,message):
    sid=os.environ.get("TWILIO_ACCOUNT_SID","").strip(); token=os.environ.get("TWILIO_AUTH_TOKEN","").strip()
    sender=os.environ.get("TWILIO_WHATSAPP_FROM","").strip()
    if not sid or not token or not sender:
        return {"delivery":"not_configured","error":"WhatsApp provider is not configured.","provider":"Twilio WhatsApp"}
    try:
        to=recipient if str(recipient).startswith("whatsapp:") else "whatsapp:"+str(recipient)
        from_value=sender if sender.startswith("whatsapp:") else "whatsapp:"+sender
        body=urlencode({"To":to,"From":from_value,"Body":message}).encode()
        auth_header=base64.b64encode(f"{sid}:{token}".encode()).decode()
        request=Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",data=body,
                        headers={"Authorization":f"Basic {auth_header}","Content-Type":"application/x-www-form-urlencoded"})
        with urlopen(request,timeout=10) as response: response.read()
        return {"delivery":"sent","error":"","provider":"Twilio WhatsApp"}
    except Exception as exc:
        return {"delivery":"failed","error":str(exc)[:300],"provider":"Twilio WhatsApp"}


def _shipment_whatsapp_text(shipment,status,tracking_url):
    language=str(shipment.get("notification_language") or "ar").strip().lower()
    awb=str(shipment.get("awb") or "")
    canonical=transitions.canonical(status)
    templates={
        "ar":{
            "created":f"غزالا ترانسبورت: تم تسجيل شحنتك {awb} وهي جاهزة للإرسال. التتبع: {tracking_url}",
            "dispatched":f"غزالا ترانسبورت: تم إرسال شحنتك {awb} وهي الآن في الطريق. التتبع: {tracking_url}",
            "in_transit":f"غزالا ترانسبورت: شحنتك {awb} في الطريق إلى فرع الوجهة. التتبع: {tracking_url}",
            "at_destination":f"غزالا ترانسبورت: وصلت شحنتك {awb} إلى فرع الوجهة وأصبحت جاهزة للاستلام أو للخطوة التالية. التتبع: {tracking_url}",
            "out_for_delivery":f"غزالا ترانسبورت: شحنتك {awb} خرجت للتسليم. التتبع: {tracking_url}",
            "delivered":f"غزالا ترانسبورت: تم تسليم شحنتك {awb} بنجاح. شكراً لاستخدامك غزالا.",
            "delayed":f"غزالا ترانسبورت: يوجد تحديث على شحنتك {awb} وقد يحدث تأخير. التتبع: {tracking_url}",
        },
        "en":{
            "created":f"Ghazala Transport: Shipment {awb} has been registered and is ready to dispatch. Track: {tracking_url}",
            "dispatched":f"Ghazala Transport: Shipment {awb} has been dispatched and is on the way. Track: {tracking_url}",
            "in_transit":f"Ghazala Transport: Shipment {awb} is in transit to the destination branch. Track: {tracking_url}",
            "at_destination":f"Ghazala Transport: Shipment {awb} has arrived at the destination branch and is ready for pickup or the next delivery step. Track: {tracking_url}",
            "out_for_delivery":f"Ghazala Transport: Shipment {awb} is out for delivery. Track: {tracking_url}",
            "delivered":f"Ghazala Transport: Shipment {awb} has been delivered successfully. Thank you.",
            "delayed":f"Ghazala Transport: Shipment {awb} has an update and may be delayed. Track: {tracking_url}",
        },
        "ur":{
            "created":f"Ghazala Transport: Aap ki shipment {awb} system mein register ho chuki hai aur dispatch ke liye ready hai. Track: {tracking_url}",
            "dispatched":f"Ghazala Transport: Aap ki shipment {awb} dispatch ho chuki hai aur raste mein hai. Track: {tracking_url}",
            "in_transit":f"Ghazala Transport: Aap ki shipment {awb} destination branch ki taraf ja rahi hai. Track: {tracking_url}",
            "at_destination":f"Ghazala Transport: Aap ki shipment {awb} destination branch pohanch gayi hai aur pickup ya next delivery step ke liye ready hai. Track: {tracking_url}",
            "out_for_delivery":f"Ghazala Transport: Aap ki shipment {awb} delivery ke liye nikal chuki hai. Track: {tracking_url}",
            "delivered":f"Ghazala Transport: Aap ki shipment {awb} successfully deliver ho gayi hai. Shukriya.",
            "delayed":f"Ghazala Transport: Aap ki shipment {awb} mein delay update hai. Track: {tracking_url}",
        },
        "hi":{
            "created":f"Ghazala Transport: Aapki shipment {awb} register ho gayi hai aur dispatch ke liye ready hai. Track: {tracking_url}",
            "dispatched":f"Ghazala Transport: Aapki shipment {awb} dispatch ho gayi hai aur raste mein hai. Track: {tracking_url}",
            "in_transit":f"Ghazala Transport: Shipment {awb} destination branch ki taraf transit mein hai. Track: {tracking_url}",
            "at_destination":f"Ghazala Transport: Shipment {awb} destination branch pahunch gayi hai. Track: {tracking_url}",
            "out_for_delivery":f"Ghazala Transport: Shipment {awb} delivery ke liye nikal chuki hai. Track: {tracking_url}",
            "delivered":f"Ghazala Transport: Shipment {awb} successfully deliver ho gayi hai. Dhanyavaad.",
            "delayed":f"Ghazala Transport: Shipment {awb} mein delay update hai. Track: {tracking_url}",
        },
        "bn":{
            "created":f"Ghazala Transport: Shipment {awb} register hoyeche ebong dispatch-er jonno ready. Track: {tracking_url}",
            "dispatched":f"Ghazala Transport: Shipment {awb} dispatch hoyeche ebong pothe ache. Track: {tracking_url}",
            "in_transit":f"Ghazala Transport: Shipment {awb} destination branch-er dike jacche. Track: {tracking_url}",
            "at_destination":f"Ghazala Transport: Shipment {awb} destination branch-e pouchheche. Track: {tracking_url}",
            "out_for_delivery":f"Ghazala Transport: Shipment {awb} delivery-r jonno ber hoyeche. Track: {tracking_url}",
            "delivered":f"Ghazala Transport: Shipment {awb} successfully delivered. Dhonnobad.",
            "delayed":f"Ghazala Transport: Shipment {awb}-e delay update ache. Track: {tracking_url}",
        },
    }
    if canonical not in ("created","dispatched","in_transit","at_destination","out_for_delivery","delivered","delayed"):
        return ""
    return (templates.get(language) or templates["en"]).get(canonical,"")


def dispatch_shipment_contact_whatsapp(con,shipment_id,status,tracking_url):
    shipment=con.execute("SELECT id,awb,phone,notification_language FROM shipments WHERE id=?",(shipment_id,)).fetchone()
    if not shipment or not str(shipment["phone"] or "").strip():
        return None
    item=dict(shipment)
    if not tracking_url:
        base=(os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        tracking_url=(f"{base}/#track={quote(str(item['awb']))}" if base else str(item["awb"]))
    message=_shipment_whatsapp_text(item,status,tracking_url)
    if not message:
        return None
    canonical=transitions.canonical(status)
    source_key=f"shipment-contact:{shipment_id}:{canonical}"
    recipient=str(item["phone"]).strip()
    existing=con.execute("""SELECT status FROM notification_delivery_log
        WHERE source_key=? AND channel='whatsapp' AND recipient=?""",(source_key,recipient)).fetchone()
    if existing and existing["status"] in ("sent","demo","not_configured","queued"):
        return dict(existing)
    result=_send_whatsapp(con,recipient,message)
    status_value=result["delivery"]
    attempts=1 if status_value in ("sent","failed") else 0
    next_retry=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(timespec="seconds") if status_value=="failed" else None
    _notification_log_upsert(con,shipment_id=shipment_id,category="shipment",event_type=canonical,
        source_key=source_key,channel="whatsapp",recipient=recipient,title="Ghazala Transport",
        message=message,status=status_value,provider=result.get("provider",""),
        provider_error=result.get("error",""),attempt_count=attempts,
        sent_at=datetime.now(timezone.utc).isoformat(timespec="seconds") if status_value=="sent" else None,
        next_attempt_at=next_retry)
    return result


def _send_email(recipient,title,message):
    host=os.environ.get("SMTP_HOST","").strip(); sender=os.environ.get("SMTP_FROM","").strip()
    if not host or not sender:
        return {"delivery":"not_configured","error":"Email provider is not configured.","provider":"SMTP"}
    try:
        import smtplib
        from email.message import EmailMessage
        port=int(os.environ.get("SMTP_PORT","587") or 587)
        username=os.environ.get("SMTP_USERNAME","").strip(); password=os.environ.get("SMTP_PASSWORD","")
        use_ssl=os.environ.get("SMTP_SSL","0").strip().lower() in ("1","true","yes")
        starttls=os.environ.get("SMTP_STARTTLS","1").strip().lower() in ("1","true","yes")
        msg=EmailMessage(); msg["From"]=sender; msg["To"]=recipient; msg["Subject"]=title or "Ghazala Transport"
        msg.set_content(message)
        client=smtplib.SMTP_SSL(host,port,timeout=10) if use_ssl else smtplib.SMTP(host,port,timeout=10)
        with client:
            if starttls and not use_ssl: client.starttls()
            if username: client.login(username,password)
            client.send_message(msg)
        return {"delivery":"sent","error":"","provider":"SMTP"}
    except Exception as exc:
        return {"delivery":"failed","error":str(exc)[:300],"provider":"SMTP"}


def dispatch_customer_notification_channels(con,customer_user_id,title,message,*,category="general",shipment_id=None,source_key,event_type="",include_sms=True,include_whatsapp=True):
    pref=notification_preferences(con,customer_user_id)
    if not _notification_category_enabled(pref,category):
        return []
    contact=_customer_contact(con,customer_user_id); results=[]
    channels=[]
    if include_sms and pref.get("sms_enabled"): channels.append(("sms",contact["mobile"]))
    if include_whatsapp and pref.get("whatsapp_enabled"): channels.append(("whatsapp",contact["mobile"]))
    if pref.get("email_enabled"): channels.append(("email",contact["email"]))
    for channel,recipient in channels:
        if not recipient:
            result={"delivery":"skipped","error":"Recipient contact is not available.","provider":""}
        elif channel=="sms":
            sms=send_sms(con,recipient,event_type or category,message)
            result={"delivery":sms["delivery"],"error":sms.get("error","") or "","provider":"Twilio" if sms["delivery"] in ("sent","failed") else "Demo"}
        elif channel=="whatsapp": result=_send_whatsapp(con,recipient,message)
        else: result=_send_email(recipient,title,message)
        status=result["delivery"]
        attempts=1 if status in ("sent","demo","failed") else 0
        next_retry=None
        if status=="failed": next_retry=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(timespec="seconds")
        _notification_log_upsert(con,customer_user_id=customer_user_id,shipment_id=shipment_id,
            category=category,event_type=event_type,source_key=source_key,channel=channel,recipient=recipient,
            title=title,message=message,status=status,provider=result.get("provider",""),provider_error=result.get("error",""),
            attempt_count=attempts,sent_at=datetime.now(timezone.utc).isoformat(timespec="seconds") if status in ("sent","demo") else None,
            next_attempt_at=next_retry)
        results.append({"channel":channel,"recipient":recipient,"status":status})
    return results


def process_notification_delivery_retries(con):
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows=con.execute("""SELECT * FROM notification_delivery_log
        WHERE status='failed' AND attempt_count<max_attempts
          AND (next_attempt_at IS NULL OR next_attempt_at<=?)
        ORDER BY id LIMIT 20""",(now,)).fetchall()
    for row in rows:
        if row["channel"]=="sms":
            result=send_sms(con,row["recipient"],row["event_type"] or row["category"],row["message"])
            provider="Twilio" if result["delivery"] in ("sent","failed") else "Demo"
        elif row["channel"]=="whatsapp":
            result=_send_whatsapp(con,row["recipient"],row["message"]); provider=result.get("provider","")
        elif row["channel"]=="email":
            result=_send_email(row["recipient"],row["title"],row["message"]); provider=result.get("provider","")
        else:
            continue
        attempts=int(row["attempt_count"] or 0)+1; status=result["delivery"]
        retry=None
        if status=="failed" and attempts<int(row["max_attempts"] or 3):
            retry=(datetime.now(timezone.utc)+timedelta(minutes=min(30,5*attempts))).isoformat(timespec="seconds")
        con.execute("""UPDATE notification_delivery_log SET status=?,provider=?,provider_error=?,
            attempt_count=?,last_attempt_at=CURRENT_TIMESTAMP,next_attempt_at=?,
            sent_at=CASE WHEN ? IN ('sent','demo') THEN COALESCE(sent_at,CURRENT_TIMESTAMP) ELSE sent_at END
            WHERE id=?""",(status,provider,result.get("error","")[:500],attempts,retry,status,row["id"]))


def notification_delivery_rows(con,ctx,user,limit=100):
    limit=max(1,min(200,int(limit or 100)))
    role=ctx.get("role")
    if role=="system_admin":
        rows=con.execute("SELECT * FROM notification_delivery_log ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
    else:
        ship_pred,ship_args=auth.sql_scope(ctx,'shipments','s')
        rows=con.execute("""SELECT d.* FROM notification_delivery_log d
             LEFT JOIN shipments s ON s.id=d.shipment_id
             WHERE d.user_id=? OR d.customer_user_id=? OR (d.shipment_id IS NOT NULL AND ("""+ship_pred+"""))
             ORDER BY d.id DESC LIMIT ?""",[user["id"],user["id"],*ship_args,limit]).fetchall()
    return [dict(r) for r in rows]


def notification_summary(con,ctx,user):
    pref=notification_preferences(con,user["id"])
    role=ctx.get("role")
    if role=="customer":
        unread=con.execute("SELECT count(*) FROM customer_notifications WHERE customer_user_id=? AND status='unread'",(user["id"],)).fetchone()[0]
        total=con.execute("SELECT count(*) FROM customer_notifications WHERE customer_user_id=?",(user["id"],)).fetchone()[0]
    else:
        ship_pred,ship_args=auth.sql_scope(ctx,'shipments','s')
        unread_ops=con.execute("""SELECT count(*) FROM operational_notifications o JOIN shipments s ON s.id=o.shipment_id
             LEFT JOIN operational_notification_reads rr ON rr.notification_id=o.id AND rr.user_id=?
             WHERE rr.notification_id IS NULL AND ("""+ship_pred+")",[user["id"],*ship_args]).fetchone()[0]
        route_pred,route_args=auth.sql_scope(ctx,'notifications','n')
        # One route can have multiple physical branch-delivery rows. The inbox
        # treats them as one logical Route Update.
        unread_routes=con.execute("""SELECT count(DISTINCT n.route_id) FROM branch_notifications n
             LEFT JOIN route_notification_reads rr ON rr.notification_id=n.id AND rr.user_id=?
             WHERE rr.notification_id IS NULL AND ("""+route_pred+")",[user["id"],*route_args]).fetchone()[0]
        visible_ops=con.execute("""SELECT count(*) FROM operational_notifications o
             JOIN shipments s ON s.id=o.shipment_id
             WHERE """+ship_pred,ship_args).fetchone()[0]
        visible_routes=con.execute("""SELECT count(DISTINCT n.route_id) FROM branch_notifications n
             WHERE """+route_pred,route_args).fetchone()[0]
        unread=unread_ops+unread_routes
        total=visible_ops+visible_routes
    return {"unread_count":int(unread),"total_count":int(total),"providers":notification_provider_status(),"preferences":pref}

def process_due_notifications():
    with connect() as c:
        due=c.execute("SELECT n.id,n.message,b.phone FROM branch_notifications n\n          LEFT JOIN branches b ON b.id=n.branch_id JOIN route_runs r ON r.id=n.route_id\n          WHERE n.sent_at IS NULL AND n.due_at<=? AND r.status!='ملغاة' ORDER BY n.due_at LIMIT 100",
          (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()
        for item in due:
            if not item["phone"]:
                c.execute("UPDATE branch_notifications SET delivery='in_app' WHERE id=?",(item["id"],)); continue
            result=send_sms(c,item["phone"],"route_departure",item["message"])
            if result["delivery"] in ("sent","demo"):
                c.execute("UPDATE branch_notifications SET sent_at=CURRENT_TIMESTAMP,delivery=? WHERE id=? AND sent_at IS NULL",(result["delivery"],item["id"]))
            else: c.execute("UPDATE branch_notifications SET delivery='failed' WHERE id=?",(item["id"],))
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='notification_delivery_log'").fetchone():
            process_notification_delivery_retries(c)

def notification_worker():
    while True:
        try: process_due_notifications()
        except Exception: pass
        time.sleep(30)

def ensure_columns(con, table, columns):
    present = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in present:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

def _baseline_schema(c):
    """Version 1: adopt existing tables; add missing columns without rewriting rows."""
    c.execute("""CREATE TABLE IF NOT EXISTS shipments (
      id INTEGER PRIMARY KEY, awb TEXT UNIQUE, recipient TEXT, phone TEXT,
      origin TEXT, destination TEXT, status TEXT, stage TEXT, cod REAL,
      eta TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    ensure_columns(c, "shipments", {
        "sender_name":"TEXT NOT NULL DEFAULT ''", "sender_id":"TEXT NOT NULL DEFAULT ''",
        "sender_phone":"TEXT NOT NULL DEFAULT ''", "recipient_id":"TEXT NOT NULL DEFAULT ''", "driver_id":"INTEGER",
        "is_demo":"INTEGER NOT NULL DEFAULT 1", "updated_at":"TEXT",
        "sender_address":"TEXT NOT NULL DEFAULT ''", "recipient_branch":"TEXT NOT NULL DEFAULT ''",
        "recipient_address":"TEXT NOT NULL DEFAULT ''", "recipient_latitude":"REAL", "recipient_longitude":"REAL",
        "package_type":"TEXT NOT NULL DEFAULT 'طرد تجاري سريع'", "package_description":"TEXT NOT NULL DEFAULT ''",
        "pieces":"INTEGER NOT NULL DEFAULT 1", "weight":"REAL NOT NULL DEFAULT 0.5",
        "length_cm":"REAL NOT NULL DEFAULT 0", "width_cm":"REAL NOT NULL DEFAULT 0", "height_cm":"REAL NOT NULL DEFAULT 0",
        "declared_value":"REAL NOT NULL DEFAULT 0", "insured":"INTEGER NOT NULL DEFAULT 0",
        "payment_method":"TEXT NOT NULL DEFAULT 'cod'", "shipping_fee":"REAL NOT NULL DEFAULT 65",
        "vat_amount":"REAL NOT NULL DEFAULT 9.75", "cod_fee":"REAL NOT NULL DEFAULT 0",
        "insurance_fee":"REAL NOT NULL DEFAULT 0", "total_fee":"REAL NOT NULL DEFAULT 74.75",
        "payment_status":"TEXT NOT NULL DEFAULT 'غير مدفوع'", "company_account":"TEXT NOT NULL DEFAULT ''"})
    c.execute("""CREATE TABLE IF NOT EXISTS shipment_events (
      id INTEGER PRIMARY KEY, shipment_id INTEGER NOT NULL, status TEXT NOT NULL,
      stage TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '', actor TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE)""")
    c.execute("CREATE TABLE IF NOT EXISTS drivers (\n      id INTEGER PRIMARY KEY, name TEXT NOT NULL, national_id TEXT NOT NULL UNIQUE,\n      mobile TEXT NOT NULL, branch TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'متاح',\n      location_text TEXT NOT NULL DEFAULT '', latitude REAL, longitude REAL,\n      updated_at TEXT DEFAULT CURRENT_TIMESTAMP, user_id INTEGER, is_demo INTEGER NOT NULL DEFAULT 0)")
    c.execute("""CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('admin','manager','employee')),
      password_hash TEXT NOT NULL, mobile TEXT NOT NULL DEFAULT '', national_id TEXT NOT NULL DEFAULT '',
      driver_id INTEGER, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
      token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS branches (
      id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, city TEXT NOT NULL,
      address TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', latitude REAL, longitude REAL,
      coverage TEXT NOT NULL DEFAULT '', is_active INTEGER NOT NULL DEFAULT 1)""")
    c.execute("CREATE TABLE IF NOT EXISTS vehicles (\n      id INTEGER PRIMARY KEY, plate TEXT UNIQUE NOT NULL, vehicle_type TEXT NOT NULL DEFAULT 'شاحنة',\n      capacity_kg REAL NOT NULL DEFAULT 1200, status TEXT NOT NULL DEFAULT 'متاح')")
    c.execute("CREATE TABLE IF NOT EXISTS clients (\n      id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,\n      client_type TEXT NOT NULL DEFAULT 'company', mobile TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',\n      national_id TEXT NOT NULL DEFAULT '', commercial_registration TEXT NOT NULL DEFAULT '',\n      city TEXT NOT NULL DEFAULT 'جدة', address TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'نشط',\n      payment_terms TEXT NOT NULL DEFAULT 'حسب الاتفاق', credit_limit REAL NOT NULL DEFAULT 0,\n      discount_percent REAL NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', is_demo INTEGER NOT NULL DEFAULT 0,\n      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS campaigns (\n      id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,\n      campaign_type TEXT NOT NULL DEFAULT 'خصم', status TEXT NOT NULL DEFAULT 'مسودة',\n      discount_percent REAL NOT NULL DEFAULT 0, channels TEXT NOT NULL DEFAULT 'التطبيق',\n      target_segment TEXT NOT NULL DEFAULT 'جميع العملاء', message TEXT NOT NULL DEFAULT '',\n      start_at TEXT NOT NULL DEFAULT '', end_at TEXT NOT NULL DEFAULT '', is_demo INTEGER NOT NULL DEFAULT 0,\n      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS route_runs (\n      id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL,\n      departure_at TEXT NOT NULL, driver_id INTEGER, vehicle_id INTEGER, capacity_kg REAL NOT NULL DEFAULT 1200,\n      status TEXT NOT NULL DEFAULT 'مجدولة', notification_minutes INTEGER NOT NULL DEFAULT 30,\n      created_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n      started_at TEXT, arrived_at TEXT,\n      FOREIGN KEY(driver_id) REFERENCES drivers(id), FOREIGN KEY(vehicle_id) REFERENCES vehicles(id))")
    c.execute("""CREATE TABLE IF NOT EXISTS route_shipments (
      route_id INTEGER NOT NULL, shipment_id INTEGER NOT NULL, scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      scanned_by TEXT NOT NULL DEFAULT '', PRIMARY KEY(route_id,shipment_id),
      FOREIGN KEY(route_id) REFERENCES route_runs(id) ON DELETE CASCADE,
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS delivery_otps (
      id INTEGER PRIMARY KEY, shipment_id INTEGER NOT NULL, code_hash TEXT NOT NULL,
      expires_at INTEGER NOT NULL, verified_at INTEGER, created_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE)""")
    ensure_columns(c,"delivery_otps",{"attempts":"INTEGER NOT NULL DEFAULT 0"})
    c.execute("""CREATE TABLE IF NOT EXISTS pod_records (
      id INTEGER PRIMARY KEY, shipment_id INTEGER NOT NULL UNIQUE, recipient_name TEXT NOT NULL,
      recipient_id_suffix TEXT NOT NULL DEFAULT '', signature_data BLOB, photo_data BLOB,
      photo_mime TEXT NOT NULL DEFAULT '', latitude REAL, longitude REAL, note TEXT NOT NULL DEFAULT '',
      verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, verified_by TEXT NOT NULL DEFAULT '',
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS service_settings (
      key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sms_outbox (
      id INTEGER PRIMARY KEY, phone TEXT NOT NULL, purpose TEXT NOT NULL, message TEXT NOT NULL,
      delivery TEXT NOT NULL DEFAULT 'demo', provider_error TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS branch_notifications (
      id INTEGER PRIMARY KEY, route_id INTEGER NOT NULL, branch_id INTEGER,
      message TEXT NOT NULL, due_at TEXT NOT NULL, sent_at TEXT, delivery TEXT NOT NULL DEFAULT 'pending',
      FOREIGN KEY(route_id) REFERENCES route_runs(id) ON DELETE CASCADE,
      FOREIGN KEY(branch_id) REFERENCES branches(id) ON DELETE SET NULL)""")
    ensure_columns(c,"branch_notifications",{"delivery":"TEXT NOT NULL DEFAULT 'pending'"})
    for setting, value in {"base_fee":"65","included_weight":"1","extra_kg_fee":"2.5","vat_rate":"0.15","cod_fee":"3.5","insurance_rate":"0.02","insurance_minimum":"5"}.items():
        c.execute("INSERT OR IGNORE INTO service_settings(key,value) VALUES(?,?)", (setting,value))


def _persistent_demo_state(c):
    """Version 2: operational metadata only, never business/demo normalization."""
    c.execute("""CREATE TABLE IF NOT EXISTS app_settings (
      key TEXT PRIMARY KEY, value TEXT NOT NULL,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    for key, value in {"bootstrap_completed":"1", "bootstrap_mode":"adopted",
                       "demo_data_disabled":"0"}.items():
        c.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES(?,?)",(key,value))


def _operational_notifications(c):
    """Version 6: shipment/customer booking notifications with per-user read state."""
    c.execute("""CREATE TABLE IF NOT EXISTS operational_notifications (
      id INTEGER PRIMARY KEY,
      notification_type TEXT NOT NULL,
      shipment_id INTEGER,
      branch_id INTEGER,
      title TEXT NOT NULL DEFAULT '',
      message TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
      FOREIGN KEY(branch_id) REFERENCES branches(id) ON DELETE SET NULL,
      UNIQUE(notification_type, shipment_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS operational_notification_reads (
      notification_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      read_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(notification_id,user_id),
      FOREIGN KEY(notification_id) REFERENCES operational_notifications(id) ON DELETE CASCADE,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_operational_notifications_created ON operational_notifications(created_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_operational_notifications_shipment ON operational_notifications(shipment_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_operational_notification_reads_user ON operational_notification_reads(user_id)")




def _shipment_documents(c):
    """Version 7: electronic waybills, parcel stickers and immutable document events."""
    c.execute("""CREATE TABLE IF NOT EXISTS waybills (
      id INTEGER PRIMARY KEY,
      shipment_id INTEGER NOT NULL UNIQUE,
      waybill_number TEXT NOT NULL UNIQUE,
      issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      issued_by_user_id INTEGER,
      archived_at TEXT,
      download_count INTEGER NOT NULL DEFAULT 0 CHECK(download_count>=0),
      print_count INTEGER NOT NULL DEFAULT 0 CHECK(print_count>=0),
      last_downloaded_at TEXT,
      last_printed_at TEXT,
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
      FOREIGN KEY(issued_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS parcel_stickers (
      id INTEGER PRIMARY KEY,
      shipment_id INTEGER NOT NULL,
      parcel_number INTEGER NOT NULL CHECK(parcel_number>=1),
      total_parcels INTEGER NOT NULL CHECK(total_parcels>=1),
      sticker_number TEXT NOT NULL UNIQUE,
      special_instructions TEXT NOT NULL DEFAULT '',
      is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      download_count INTEGER NOT NULL DEFAULT 0 CHECK(download_count>=0),
      print_count INTEGER NOT NULL DEFAULT 0 CHECK(print_count>=0),
      last_downloaded_at TEXT,
      last_printed_at TEXT,
      UNIQUE(shipment_id,parcel_number),
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS shipment_document_events (
      id INTEGER PRIMARY KEY,
      shipment_id INTEGER NOT NULL,
      waybill_id INTEGER,
      sticker_id INTEGER,
      event_type TEXT NOT NULL,
      actor_user_id INTEGER,
      actor_name TEXT NOT NULL DEFAULT '',
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
      FOREIGN KEY(waybill_id) REFERENCES waybills(id) ON DELETE SET NULL,
      FOREIGN KEY(sticker_id) REFERENCES parcel_stickers(id) ON DELETE SET NULL,
      FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE SET NULL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_waybills_shipment ON waybills(shipment_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_waybills_number ON waybills(waybill_number)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_stickers_shipment ON parcel_stickers(shipment_id,is_active,parcel_number)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_document_events_shipment ON shipment_document_events(shipment_id,id)")
    c.execute("""CREATE TRIGGER IF NOT EXISTS shipment_document_events_no_update
      BEFORE UPDATE ON shipment_document_events
      BEGIN SELECT RAISE(ABORT,'Shipment document events are append-only'); END""")
    c.execute("""CREATE TRIGGER IF NOT EXISTS shipment_document_events_no_delete
      BEFORE DELETE ON shipment_document_events
      BEGIN SELECT RAISE(ABORT,'Shipment document events are append-only'); END""")

    # Adopt all existing shipments without changing their AWB identity.
    c.execute("""INSERT OR IGNORE INTO waybills(shipment_id,waybill_number)
      SELECT id,'WB-'||awb FROM shipments""")
    c.execute("""WITH RECURSIVE parcel_seq(shipment_id,awb,n,total) AS (
        SELECT id,awb,1,
          CASE
            WHEN pieces IS NULL OR CAST(pieces AS INTEGER)<1 THEN 1
            WHEN CAST(pieces AS INTEGER)>100 THEN 100
            ELSE CAST(pieces AS INTEGER)
          END
        FROM shipments
        UNION ALL
        SELECT shipment_id,awb,n+1,total FROM parcel_seq WHERE n<total
      )
      INSERT OR IGNORE INTO parcel_stickers(
        shipment_id,parcel_number,total_parcels,sticker_number,is_active
      )
      SELECT shipment_id,n,total,awb||'-P'||printf('%03d',n),1
      FROM parcel_seq""")



def _legacy_text_encoding_cleanup(c):
    """Version 8: repair legacy UTF-8/Windows-1252 mojibake already stored in operational text."""
    suspicious=("Ã","Â","â","™","€","˜","Ø","Ù","Å","Ë","Œ","ž")

    def score(value):
        return sum(value.count(marker) for marker in suspicious)

    def to_legacy_bytes(value):
        out=bytearray()
        for char in value:
            code=ord(char)
            if code<=255:
                out.append(code)
            else:
                try:
                    out.extend(char.encode("cp1252"))
                except UnicodeEncodeError:
                    return None
        return bytes(out)

    def repair(value):
        if not isinstance(value,str) or not any(marker in value for marker in suspicious):
            return value
        current=value
        for _ in range(6):
            raw=to_legacy_bytes(current)
            if raw is None:
                break
            try:
                candidate=raw.decode("utf-8")
            except UnicodeDecodeError:
                break
            if candidate==current or score(candidate)>score(current):
                break
            current=candidate
        return current

    skip_tables={
        "schema_migrations",
        "audit_events",
        "shipment_document_events",
        "sessions",
    }

    tables=[
        row[0] for row in c.execute(
            """SELECT name FROM sqlite_master
               WHERE type='table' AND name NOT LIKE 'sqlite_%'
               ORDER BY name"""
        ).fetchall()
        if row[0] not in skip_tables and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",row[0])
    ]

    for table in tables:
        columns=[
            row[1] for row in c.execute(f'PRAGMA table_info("{table}")').fetchall()
            if "TEXT" in str(row[2] or "").upper()
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",row[1])
        ]
        if not columns:
            continue

        column_sql=",".join(f'"{column}"' for column in columns)
        try:
            rows=c.execute(f'SELECT rowid AS __rowid__,{column_sql} FROM "{table}"').fetchall()
        except sqlite3.OperationalError:
            continue

        for row in rows:
            updates=[]
            values=[]
            for column in columns:
                before=row[column]
                after=repair(before)
                if after!=before:
                    updates.append(f'"{column}"=?')
                    values.append(after)
            if updates:
                values.append(row["__rowid__"])
                c.execute(
                    f'UPDATE "{table}" SET {",".join(updates)} WHERE rowid=?',
                    values
                )



def _customer_commercial_module(c):
    """Version 9: customer business profile, invoices, payments and courier pickup requests."""
    c.execute("""CREATE TABLE IF NOT EXISTS customer_business_profiles (
      user_id INTEGER PRIMARY KEY,
      account_type TEXT NOT NULL DEFAULT 'individual'
        CHECK(account_type IN ('individual','company')),
      email TEXT NOT NULL DEFAULT '',
      company_name TEXT NOT NULL DEFAULT '',
      commercial_registration TEXT NOT NULL DEFAULT '',
      vat_number TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES customer_accounts(user_id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS invoices (
      id INTEGER PRIMARY KEY,
      invoice_number TEXT NOT NULL UNIQUE,
      shipment_id INTEGER NOT NULL UNIQUE,
      customer_user_id INTEGER NOT NULL,
      subtotal REAL NOT NULL DEFAULT 0 CHECK(subtotal>=0),
      vat_amount REAL NOT NULL DEFAULT 0 CHECK(vat_amount>=0),
      total_amount REAL NOT NULL DEFAULT 0 CHECK(total_amount>=0),
      amount_paid REAL NOT NULL DEFAULT 0 CHECK(amount_paid>=0),
      balance REAL NOT NULL DEFAULT 0 CHECK(balance>=0),
      currency TEXT NOT NULL DEFAULT 'SAR',
      status TEXT NOT NULL DEFAULT 'issued'
        CHECK(status IN ('issued','partially_paid','paid','void')),
      issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      due_at TEXT,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
      FOREIGN KEY(customer_user_id) REFERENCES customer_accounts(user_id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS payments (
      id INTEGER PRIMARY KEY,
      payment_number TEXT NOT NULL UNIQUE,
      invoice_id INTEGER NOT NULL,
      customer_user_id INTEGER NOT NULL,
      amount REAL NOT NULL CHECK(amount>0),
      currency TEXT NOT NULL DEFAULT 'SAR',
      method TEXT NOT NULL DEFAULT 'other',
      status TEXT NOT NULL DEFAULT 'paid'
        CHECK(status IN ('pending','paid','failed','refunded')),
      reference TEXT NOT NULL DEFAULT '',
      provider TEXT NOT NULL DEFAULT 'manual',
      recorded_by_user_id INTEGER,
      note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      paid_at TEXT,
      FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
      FOREIGN KEY(customer_user_id) REFERENCES customer_accounts(user_id) ON DELETE CASCADE,
      FOREIGN KEY(recorded_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS pickup_requests (
      id INTEGER PRIMARY KEY,
      pickup_number TEXT NOT NULL UNIQUE,
      customer_user_id INTEGER NOT NULL,
      branch_id INTEGER NOT NULL,
      contact_name TEXT NOT NULL,
      contact_mobile TEXT NOT NULL,
      city TEXT NOT NULL,
      address TEXT NOT NULL,
      preferred_at TEXT,
      pieces INTEGER NOT NULL DEFAULT 1 CHECK(pieces BETWEEN 1 AND 100),
      weight REAL NOT NULL DEFAULT 1 CHECK(weight>0),
      notes TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'requested'
        CHECK(status IN ('requested','assigned','picked_up','completed','cancelled')),
      driver_id INTEGER,
      shipment_id INTEGER,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(customer_user_id) REFERENCES customer_accounts(user_id) ON DELETE CASCADE,
      FOREIGN KEY(branch_id) REFERENCES branches(id),
      FOREIGN KEY(driver_id) REFERENCES drivers(id) ON DELETE SET NULL,
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE SET NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS pickup_request_events (
      id INTEGER PRIMARY KEY,
      pickup_request_id INTEGER NOT NULL,
      status TEXT NOT NULL,
      actor_user_id INTEGER,
      actor_name TEXT NOT NULL DEFAULT '',
      note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(pickup_request_id) REFERENCES pickup_requests(id) ON DELETE CASCADE,
      FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE SET NULL
    )""")

    c.execute("CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_user_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_user_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pickups_customer ON pickup_requests(customer_user_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pickups_branch_status ON pickup_requests(branch_id,status,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pickup_events_request ON pickup_request_events(pickup_request_id,id)")

    c.execute("""CREATE TRIGGER IF NOT EXISTS pickup_request_events_no_update
      BEFORE UPDATE ON pickup_request_events
      BEGIN SELECT RAISE(ABORT,'Pickup request events are append-only'); END""")
    c.execute("""CREATE TRIGGER IF NOT EXISTS pickup_request_events_no_delete
      BEFORE DELETE ON pickup_request_events
      BEGIN SELECT RAISE(ABORT,'Pickup request events are append-only'); END""")

    c.execute("""INSERT OR IGNORE INTO customer_business_profiles(user_id)
      SELECT user_id FROM customer_accounts""")

    # Existing customer-owned shipments receive invoices without changing shipment identity.
    c.execute("""INSERT OR IGNORE INTO invoices(
        invoice_number,shipment_id,customer_user_id,subtotal,vat_amount,total_amount,
        amount_paid,balance,status,issued_at,due_at
      )
      SELECT
        'INV-'||s.awb,
        s.id,
        cs.customer_user_id,
        MAX(0,COALESCE(s.shipping_fee,0)+COALESCE(s.cod_fee,0)+COALESCE(s.insurance_fee,0)),
        MAX(0,COALESCE(s.vat_amount,0)),
        MAX(0,COALESCE(s.total_fee,0)),
        CASE
          WHEN s.payment_status IN ('مدفوع','تم التحصيل عند التسليم') THEN MAX(0,COALESCE(s.total_fee,0))
          ELSE 0
        END,
        CASE
          WHEN s.payment_status IN ('مدفوع','تم التحصيل عند التسليم') THEN 0
          ELSE MAX(0,COALESCE(s.total_fee,0))
        END,
        CASE
          WHEN s.payment_status IN ('مدفوع','تم التحصيل عند التسليم') THEN 'paid'
          ELSE 'issued'
        END,
        COALESCE(s.created_at,CURRENT_TIMESTAMP),
        CASE WHEN s.payment_method='cod' THEN NULLIF(s.eta,'') ELSE COALESCE(s.created_at,CURRENT_TIMESTAMP) END
      FROM customer_shipments cs
      JOIN shipments s ON s.id=cs.shipment_id""")

    # Make already-paid migrated invoices auditable in the payments ledger.
    c.execute("""INSERT OR IGNORE INTO payments(
        payment_number,invoice_id,customer_user_id,amount,currency,method,status,
        reference,provider,recorded_by_user_id,note,created_at,paid_at
      )
      SELECT
        'PMT-MIG-'||i.id,
        i.id,
        i.customer_user_id,
        i.total_amount,
        i.currency,
        'legacy',
        'paid',
        'Imported from shipment payment status',
        'legacy',
        NULL,
        'Opening payment imported during commercial-module migration.',
        i.issued_at,
        i.issued_at
      FROM invoices i
      WHERE i.status='paid' AND i.total_amount>0
        AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.invoice_id=i.id)""")



def _three_d_pricing_sizes(c):
    """Version 10: 3D parcel-size tariff catalog and shipment pricing snapshot."""
    c.execute("""CREATE TABLE IF NOT EXISTS pricing_sizes (
      id INTEGER PRIMARY KEY,
      code TEXT NOT NULL UNIQUE,
      label_en TEXT NOT NULL,
      label_ar TEXT NOT NULL DEFAULT '',
      length_cm REAL NOT NULL CHECK(length_cm>0),
      width_cm REAL NOT NULL CHECK(width_cm>0),
      height_cm REAL NOT NULL CHECK(height_cm>0),
      examples_en TEXT NOT NULL DEFAULT '',
      examples_ar TEXT NOT NULL DEFAULT '',
      base_fee REAL NOT NULL CHECK(base_fee>=0),
      is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
      manual_only INTEGER NOT NULL DEFAULT 0 CHECK(manual_only IN (0,1)),
      sort_order INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pricing_sizes_active_order ON pricing_sizes(is_active,sort_order,id)")
    shipment_columns={row[1] for row in c.execute("PRAGMA table_info(shipments)").fetchall()}
    if "pricing_size_code" not in shipment_columns:
        c.execute("ALTER TABLE shipments ADD COLUMN pricing_size_code TEXT NOT NULL DEFAULT ''")
    if "pricing_size_fee" not in shipment_columns:
        c.execute("ALTER TABLE shipments ADD COLUMN pricing_size_fee REAL NOT NULL DEFAULT 0")
    seed=[('XXS', 'Micro', 'مايكرو', 10, 10, 10, 'Rings, small watches', 'خواتم، ساعات صغيرة', 10, 1, 0, 10), ('XS', 'Extra Small', 'صغير جداً', 15, 10, 10, 'Jewelry and small accessories', 'مجوهرات وإكسسوارات صغيرة', 15, 1, 0, 20), ('S', 'Small', 'صغير', 30, 20, 15, 'Perfumes, personal accessories', 'عطور وإكسسوارات شخصية', 25, 1, 0, 30), ('S+', 'Small Plus', 'صغير بلس', 35, 25, 20, 'Books, small electronics', 'كتب وإلكترونيات صغيرة', 30, 1, 0, 40), ('M', 'Medium', 'متوسط', 40, 30, 30, 'Clothing, small home appliances', 'ملابس وأجهزة منزلية صغيرة', 40, 1, 0, 50), ('M+', 'Medium Plus', 'متوسط بلس', 45, 35, 35, 'Multiple devices, larger home appliances', 'عدة أجهزة وأجهزة منزلية أكبر', 48, 1, 0, 60), ('L', 'Large', 'كبير', 55, 45, 40, 'Electronics, multiple large items', 'إلكترونيات وعدة قطع كبيرة', 65, 1, 0, 70), ('L+', 'Large Plus', 'كبير بلس', 75, 55, 50, 'Multiple desktop PCs, large artworks', 'عدة حواسيب مكتبية ولوحات كبيرة', 85, 1, 0, 80), ('XL', 'Extra Large', 'كبير جداً', 80, 60, 50, 'TV screens, unassembled furniture', 'شاشات تلفزيون وأثاث غير مركب', 90, 1, 0, 90), ('XL+', 'Extra Large Plus', 'كبير جداً بلس', 95, 70, 60, 'Large artworks, multiple consolidated cartons', 'لوحات كبيرة وعدة كراتين مجمعة', 105, 1, 0, 100), ('XXL', 'Double Extra Large', 'كبير مزدوج', 110, 80, 60, 'Large musical instruments, bicycles', 'آلات موسيقية كبيرة ودراجات', 115, 1, 0, 110), ('XL++', 'Advanced Extra Large', 'كبير متقدم', 120, 80, 75, 'Large sectional furniture pieces', 'قطع أثاث كبيرة متعددة الأقسام', 145, 1, 0, 120), ('3XL+', 'Triple Extra Large Plus', 'ثلاثي كبير بلس', 160, 110, 100, 'Multiple-piece furniture sets, raw industrial components', 'أطقم أثاث متعددة القطع ومكونات صناعية', 215, 1, 0, 130), ('4XL', 'Four Extra Large', 'رباعي كبير', 180, 120, 130, 'Vehicle engines, small automotive spare parts', 'محركات مركبات وقطع غيار سيارات', 245, 1, 0, 140), ('4XL++', 'Ultra Advanced Extra Large', 'رباعي كبير متقدم جداً', 250, 180, 150, 'Large industrial machinery and oversized freight components', 'معدات صناعية كبيرة وشحنات ضخمة', 320, 1, 0, 150), ('PALLET', 'Pallet (P – Shipping Pallet)', 'طبالي شحن', 120, 80, 180, 'Full commercial shipping pallets and bulk-stacked goods', 'طبالي تجارية كاملة وبضائع مكدسة', 400, 1, 1, 160)]
    c.executemany(
        """INSERT INTO pricing_sizes(
             code,label_en,label_ar,length_cm,width_cm,height_cm,
             examples_en,examples_ar,base_fee,is_active,manual_only,sort_order
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(code) DO NOTHING""",
        seed
    )

def _courier_delivery_operations(c):
    """Version 11: courier tasks, delivery attempts and delivery exceptions."""
    c.execute("""CREATE TABLE IF NOT EXISTS delivery_attempts (
      id INTEGER PRIMARY KEY,
      shipment_id INTEGER NOT NULL,
      driver_id INTEGER,
      attempt_number INTEGER NOT NULL CHECK(attempt_number>=1),
      outcome TEXT NOT NULL DEFAULT 'in_progress'
        CHECK(outcome IN ('in_progress','failed','delivered')),
      failure_reason_code TEXT NOT NULL DEFAULT '',
      failure_reason_text TEXT NOT NULL DEFAULT '',
      recipient_name TEXT NOT NULL DEFAULT '',
      note TEXT NOT NULL DEFAULT '',
      latitude REAL,
      longitude REAL,
      location_text TEXT NOT NULL DEFAULT '',
      photo_data BLOB,
      photo_mime TEXT NOT NULL DEFAULT '',
      next_attempt_at TEXT,
      started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      completed_at TEXT,
      created_by_user_id INTEGER,
      completed_by_user_id INTEGER,
      created_by_name TEXT NOT NULL DEFAULT '',
      completed_by_name TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(shipment_id,attempt_number),
      FOREIGN KEY(shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
      FOREIGN KEY(driver_id) REFERENCES drivers(id) ON DELETE SET NULL,
      FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
      FOREIGN KEY(completed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_delivery_attempts_shipment ON delivery_attempts(shipment_id,attempt_number DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_delivery_attempts_driver ON delivery_attempts(driver_id,outcome,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_delivery_attempts_outcome ON delivery_attempts(outcome,id DESC)")

    # Adopt historical POD rows as completed attempts without changing their
    # shipment/POD identity or rewriting any existing operational history.
    c.execute("""INSERT OR IGNORE INTO delivery_attempts(
        shipment_id,driver_id,attempt_number,outcome,recipient_name,
        latitude,longitude,location_text,started_at,completed_at,
        created_by_name,completed_by_name
      )
      SELECT p.shipment_id,s.driver_id,1,'delivered',p.recipient_name,
             p.latitude,p.longitude,
             CASE
               WHEN p.latitude IS NOT NULL AND p.longitude IS NOT NULL
                 THEN 'GPS '||printf('%.5f',p.latitude)||', '||printf('%.5f',p.longitude)
               ELSE s.destination
             END,
             COALESCE(p.verified_at,s.updated_at,s.created_at,CURRENT_TIMESTAMP),
             COALESCE(p.verified_at,s.updated_at,s.created_at,CURRENT_TIMESTAMP),
             COALESCE(NULLIF(p.verified_by,''),'Historical POD'),
             COALESCE(NULLIF(p.verified_by,''),'Historical POD')
      FROM pod_records p
      JOIN shipments s ON s.id=p.shipment_id
      WHERE NOT EXISTS (
        SELECT 1 FROM delivery_attempts da WHERE da.shipment_id=p.shipment_id
      )""")



def _fleet_management(c):
    """Version 12: operational fleet records, maintenance, inspections,
    documents and append-only availability history.
    """
    ensure_columns(c,"vehicles",{
        "make":"TEXT NOT NULL DEFAULT ''",
        "model":"TEXT NOT NULL DEFAULT ''",
        "model_year":"INTEGER",
        "vin":"TEXT NOT NULL DEFAULT ''",
        "color":"TEXT NOT NULL DEFAULT ''",
        "fuel_type":"TEXT NOT NULL DEFAULT 'diesel'",
        "odometer_km":"REAL NOT NULL DEFAULT 0",
        "registration_expiry":"TEXT NOT NULL DEFAULT ''",
        "insurance_expiry":"TEXT NOT NULL DEFAULT ''",
        "inspection_expiry":"TEXT NOT NULL DEFAULT ''",
        "notes":"TEXT NOT NULL DEFAULT ''",
        "is_active":"INTEGER NOT NULL DEFAULT 1",
        "created_at":"TEXT NOT NULL DEFAULT ''",
        "updated_at":"TEXT NOT NULL DEFAULT ''",
    })
    c.execute("UPDATE vehicles SET created_at=CURRENT_TIMESTAMP WHERE created_at='' OR created_at IS NULL")
    c.execute("UPDATE vehicles SET updated_at=CURRENT_TIMESTAMP WHERE updated_at='' OR updated_at IS NULL")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_vehicles_vin_unique ON vehicles(vin) WHERE vin<>''")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_status_active ON vehicles(status,is_active,id)")

    c.execute("""CREATE TABLE IF NOT EXISTS vehicle_maintenance(
      id INTEGER PRIMARY KEY,
      vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
      maintenance_type TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK(status IN ('scheduled','in_progress','completed','cancelled')),
      description TEXT NOT NULL DEFAULT '',
      scheduled_at TEXT,
      completed_at TEXT,
      odometer_km REAL,
      cost REAL NOT NULL DEFAULT 0,
      vendor TEXT NOT NULL DEFAULT '',
      next_due_at TEXT,
      next_due_km REAL,
      notes TEXT NOT NULL DEFAULT '',
      created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_by_name TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_maintenance_vehicle ON vehicle_maintenance(vehicle_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_maintenance_due ON vehicle_maintenance(status,scheduled_at,next_due_at)")

    c.execute("""CREATE TABLE IF NOT EXISTS vehicle_inspections(
      id INTEGER PRIMARY KEY,
      vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
      inspection_type TEXT NOT NULL,
      result TEXT NOT NULL DEFAULT 'pending'
        CHECK(result IN ('pending','passed','failed')),
      inspected_at TEXT,
      expiry_at TEXT,
      odometer_km REAL,
      inspector TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '',
      created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_by_name TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_inspections_vehicle ON vehicle_inspections(vehicle_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_inspections_expiry ON vehicle_inspections(expiry_at,result)")

    c.execute("""CREATE TABLE IF NOT EXISTS vehicle_documents(
      id INTEGER PRIMARY KEY,
      vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
      document_type TEXT NOT NULL,
      title TEXT NOT NULL,
      document_number TEXT NOT NULL DEFAULT '',
      issue_date TEXT NOT NULL DEFAULT '',
      expiry_date TEXT NOT NULL DEFAULT '',
      file_name TEXT NOT NULL DEFAULT '',
      file_mime TEXT NOT NULL DEFAULT '',
      file_data BLOB,
      notes TEXT NOT NULL DEFAULT '',
      created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      created_by_name TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_documents_vehicle ON vehicle_documents(vehicle_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_documents_expiry ON vehicle_documents(expiry_date,document_type)")

    c.execute("""CREATE TABLE IF NOT EXISTS vehicle_status_history(
      id INTEGER PRIMARY KEY,
      vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
      old_status TEXT,
      new_status TEXT NOT NULL,
      reason TEXT NOT NULL DEFAULT '',
      route_id INTEGER REFERENCES route_runs(id) ON DELETE SET NULL,
      driver_id INTEGER REFERENCES drivers(id) ON DELETE SET NULL,
      odometer_km REAL,
      actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      actor_name TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_status_history_vehicle ON vehicle_status_history(vehicle_id,id DESC)")
    c.execute("""CREATE TRIGGER IF NOT EXISTS vehicle_status_history_no_update
      BEFORE UPDATE ON vehicle_status_history
      BEGIN SELECT RAISE(ABORT,'Vehicle status history is append-only'); END""")
    c.execute("""CREATE TRIGGER IF NOT EXISTS vehicle_status_history_no_delete
      BEFORE DELETE ON vehicle_status_history
      BEGIN SELECT RAISE(ABORT,'Vehicle status history is append-only'); END""")

    # Existing vehicles keep their business values; only an opening history event is added.
    c.execute("""INSERT INTO vehicle_status_history(vehicle_id,old_status,new_status,reason,odometer_km,actor_name)
      SELECT v.id,NULL,v.status,'Opening fleet status',v.odometer_km,'Migration 12'
      FROM vehicles v
      WHERE NOT EXISTS (
        SELECT 1 FROM vehicle_status_history h WHERE h.vehicle_id=v.id
      )""")


FLEET_STATUSES={"متاح","في الطريق","صيانة","خارج الخدمة"}
FLEET_STATUS_ALIASES={
    "available":"متاح","ready":"متاح",
    "in_transit":"في الطريق","on_route":"في الطريق","in transit":"في الطريق",
    "maintenance":"صيانة",
    "out_of_service":"خارج الخدمة","inactive":"خارج الخدمة","out of service":"خارج الخدمة",
}
FLEET_FUEL_TYPES={"diesel","petrol","electric","hybrid","other"}


def _fleet_text(value, limit, field, required=False):
    value=str(value or "").strip()
    if required and not value:
        raise ValueError(f"{field} is required.")
    if len(value)>limit:
        raise ValueError(f"{field} exceeds the allowed size.")
    return value


def _fleet_number(value, field, minimum=0, maximum=None, allow_none=False):
    if value in (None,"") and allow_none:
        return None
    try:
        value=float(value)
    except (TypeError,ValueError):
        raise ValueError(f"{field} must be a valid number.") from None
    if not math.isfinite(value) or value<minimum or (maximum is not None and value>maximum):
        raise ValueError(f"{field} is outside the allowed range.")
    return value


def _fleet_date(value, field, allow_blank=True):
    value=str(value or "").strip()
    if not value and allow_blank:
        return ""
    try:
        datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise ValueError(f"{field} must be a valid date or date/time.") from None
    return value


def normalize_fleet_status(value):
    value=str(value or "").strip()
    if not value:
        return "متاح"
    canonical=FLEET_STATUS_ALIASES.get(value.casefold(),value)
    if canonical not in FLEET_STATUSES:
        raise ValueError("Select a valid vehicle status.")
    return canonical


def vehicle_fields(data, creating=False):
    allowed={
        "plate","vehicle_type","capacity_kg","status","make","model","model_year","vin",
        "color","fuel_type","odometer_km","registration_expiry","insurance_expiry",
        "inspection_expiry","notes","is_active","branch_ids","status_reason",
    }
    if not isinstance(data,dict) or set(data)-allowed:
        raise ValueError("Unsupported vehicle fields.")
    fields={}
    if creating or "plate" in data:
        fields["plate"]=_fleet_text(data.get("plate"),40,"Vehicle plate",required=True)
    if creating or "vehicle_type" in data:
        fields["vehicle_type"]=_fleet_text(data.get("vehicle_type") or "شاحنة نقل",120,"Vehicle type",required=True)
    if creating or "capacity_kg" in data:
        fields["capacity_kg"]=_fleet_number(data.get("capacity_kg"),"Vehicle capacity",0.1,1_000_000)
    if "status" in data or creating:
        fields["status"]=normalize_fleet_status(data.get("status") or "متاح")
    for key,label,limit in (
        ("make","Make",120),("model","Model",120),("vin","VIN",64),("color","Color",80),
        ("notes","Vehicle notes",2000),
    ):
        if key in data:
            value=_fleet_text(data.get(key),limit,label)
            fields[key]=value.upper() if key=="vin" else value
    if "fuel_type" in data:
        fuel=str(data.get("fuel_type") or "").strip().lower()
        if fuel not in FLEET_FUEL_TYPES:
            raise ValueError("Select a valid fuel type.")
        fields["fuel_type"]=fuel
    if "model_year" in data:
        if data.get("model_year") in (None,""):
            fields["model_year"]=None
        else:
            year=int(_fleet_number(data.get("model_year"),"Model year",1980,datetime.now().year+1))
            fields["model_year"]=year
    if "odometer_km" in data:
        fields["odometer_km"]=_fleet_number(data.get("odometer_km"),"Odometer",0,20_000_000)
    for key,label in (
        ("registration_expiry","Registration expiry"),
        ("insurance_expiry","Insurance expiry"),
        ("inspection_expiry","Inspection expiry"),
    ):
        if key in data:
            fields[key]=_fleet_date(data.get(key),label)
    if "is_active" in data:
        fields["is_active"]=1 if bool(data.get("is_active")) else 0
    return fields


def vehicle_branch_ids(con, ctx, data, required=False):
    if "branch_ids" not in data:
        if required and not ctx.get("global_scope"):
            default=ctx.get("primary_branch_id") or next(iter(ctx.get("branch_ids") or ()),None)
            return [int(default)] if default else []
        return None
    raw=data.get("branch_ids")
    if not isinstance(raw,list):
        raise ValueError("Vehicle branch_ids must be a list.")
    branch_ids=[]
    for value in raw:
        try:
            branch_id=int(value)
        except (TypeError,ValueError):
            raise ValueError("Vehicle branch id is invalid.") from None
        if branch_id not in branch_ids:
            branch_ids.append(branch_id)
    if not branch_ids:
        raise ValueError("Assign the vehicle to at least one active branch.")
    marks=",".join("?" for _ in branch_ids)
    active={row["id"] for row in con.execute(
        f"SELECT id FROM branches WHERE is_active=1 AND id IN ({marks})",branch_ids
    ).fetchall()}
    if set(branch_ids)!=active:
        raise ValueError("Select active Ghazala branches only.")
    if not ctx.get("global_scope"):
        allowed=set(ctx.get("branch_ids") or ())
        if not set(branch_ids).issubset(allowed):
            raise auth.AccessDenied("Vehicle branch assignment is outside your allowed branch scope.")
    return branch_ids


def persist_fleet_vehicle_branches(con, vehicle_id, branch_ids):
    if branch_ids is None:
        return
    con.execute("DELETE FROM vehicle_branches WHERE vehicle_id=?",(vehicle_id,))
    con.executemany(
        "INSERT INTO vehicle_branches(vehicle_id,branch_id) VALUES(?,?)",
        [(vehicle_id,branch_id) for branch_id in branch_ids]
    )


def fleet_vehicle_scoped(con, ctx, vehicle_id):
    try:
        vehicle_id=int(vehicle_id)
    except (TypeError,ValueError):
        raise ValueError("Vehicle not found.") from None
    return policy.object_row(con,ctx,"vehicles",vehicle_id,"id")


def set_vehicle_status(con, vehicle_id, status, user=None, reason="", route_id=None,
                       driver_id=None, odometer_km=None, force_history=False):
    status=normalize_fleet_status(status)
    row=con.execute("SELECT * FROM vehicles WHERE id=?",(vehicle_id,)).fetchone()
    if not row:
        raise ValueError("Vehicle not found.")
    old_status=row["status"]
    if odometer_km is None:
        odometer=float(row["odometer_km"] or 0)
    else:
        odometer=_fleet_number(odometer_km,"Odometer",0,20_000_000)
        if odometer+1e-9<float(row["odometer_km"] or 0):
            raise ValueError("Odometer cannot move backwards.")
    if old_status!=status or odometer!=float(row["odometer_km"] or 0):
        con.execute(
            "UPDATE vehicles SET status=?,odometer_km=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status,odometer,vehicle_id)
        )
    if old_status!=status or force_history:
        con.execute(
            """INSERT INTO vehicle_status_history(
                 vehicle_id,old_status,new_status,reason,route_id,driver_id,odometer_km,
                 actor_user_id,actor_name
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                vehicle_id,old_status,status,str(reason or "")[:1000],route_id,driver_id,odometer,
                user["id"] if user else None,(user.get("display_name","") if user else "System")
            )
        )
    return status


def vehicle_fleet_payload(con, ctx, vehicle_id=None):
    if not auth.allowed(ctx,"vehicles.read"):
        raise auth.AccessDenied("You do not have permission to access vehicles.")
    if vehicle_id is None:
        rows=policy.rows(con,ctx,"vehicles",order="ORDER BY x.plate")
    else:
        scoped=fleet_vehicle_scoped(con,ctx,vehicle_id)
        rows=[con.execute("SELECT * FROM vehicles WHERE id=?",(scoped["id"],)).fetchone()]
    result=[]
    for row in rows:
        item=dict(row)
        branches=[dict(branch) for branch in con.execute(
            """SELECT b.id,b.code,b.name,b.city
               FROM vehicle_branches vb JOIN branches b ON b.id=vb.branch_id
               WHERE vb.vehicle_id=? ORDER BY b.city,b.name,b.id""",(row["id"],)
        ).fetchall()]
        route=con.execute(
            """SELECT r.id,r.code,r.origin,r.destination,r.departure_at,r.status,
                      d.id AS driver_id,d.name AS driver_name
               FROM route_runs r LEFT JOIN drivers d ON d.id=r.driver_id
               WHERE r.vehicle_id=? ORDER BY r.id DESC LIMIT 1""",(row["id"],)
        ).fetchone()
        active_route=con.execute(
            """SELECT r.id,r.code,r.origin,r.destination,r.departure_at,r.status,
                      d.id AS driver_id,d.name AS driver_name
               FROM route_runs r LEFT JOIN drivers d ON d.id=r.driver_id
               WHERE r.vehicle_id=? AND r.status NOT IN ('وصلت','ملغاة')
               ORDER BY r.id DESC LIMIT 1""",(row["id"],)
        ).fetchone()
        last_maintenance=con.execute(
            """SELECT id,maintenance_type,status,completed_at,odometer_km,cost,vendor,next_due_at,next_due_km
               FROM vehicle_maintenance
               WHERE vehicle_id=? AND status='completed' ORDER BY id DESC LIMIT 1""",(row["id"],)
        ).fetchone()
        next_maintenance=con.execute(
            """SELECT id,maintenance_type,status,scheduled_at,next_due_at,next_due_km,description
               FROM vehicle_maintenance
               WHERE vehicle_id=? AND status IN ('scheduled','in_progress')
               ORDER BY CASE WHEN scheduled_at IS NULL THEN 1 ELSE 0 END,scheduled_at,id LIMIT 1""",(row["id"],)
        ).fetchone()
        last_inspection=con.execute(
            """SELECT id,inspection_type,result,inspected_at,expiry_at,inspector
               FROM vehicle_inspections WHERE vehicle_id=? ORDER BY id DESC LIMIT 1""",(row["id"],)
        ).fetchone()
        documents_count=con.execute(
            "SELECT count(*) FROM vehicle_documents WHERE vehicle_id=?",(row["id"],)
        ).fetchone()[0]
        expiring_documents=con.execute(
            """SELECT count(*) FROM vehicle_documents
               WHERE vehicle_id=? AND expiry_date<>''
                 AND date(expiry_date)>=date('now') AND date(expiry_date)<=date('now','+30 days')""",
            (row["id"],)
        ).fetchone()[0]
        item.update(
            branches=branches,
            branch_ids=[branch["id"] for branch in branches],
            last_route=dict(route) if route else None,
            active_route=dict(active_route) if active_route else None,
            last_maintenance=dict(last_maintenance) if last_maintenance else None,
            next_maintenance=dict(next_maintenance) if next_maintenance else None,
            last_inspection=dict(last_inspection) if last_inspection else None,
            documents_count=documents_count,
            expiring_documents=expiring_documents,
            history_count=con.execute(
                "SELECT count(*) FROM vehicle_status_history WHERE vehicle_id=?",(row["id"],)
            ).fetchone()[0],
        )
        result.append(item)
    if vehicle_id is not None:
        if not result:
            raise ValueError("Vehicle not found.")
        return result[0]
    return result


def fleet_summary(con, ctx):
    rows=vehicle_fleet_payload(con,ctx)
    return {
        "total":len(rows),
        "available":sum(1 for row in rows if row["is_active"] and row["status"]=="متاح"),
        "on_route":sum(1 for row in rows if row["is_active"] and row["status"]=="في الطريق"),
        "maintenance":sum(1 for row in rows if row["is_active"] and row["status"]=="صيانة"),
        "out_of_service":sum(1 for row in rows if row["status"]=="خارج الخدمة"),
        "inactive":sum(1 for row in rows if not row["is_active"]),
        "maintenance_due":sum(1 for row in rows if row["next_maintenance"]),
        "expiring_documents":sum(int(row["expiring_documents"] or 0) for row in rows),
    }


def vehicle_maintenance_rows(con, ctx, vehicle_id):
    vehicle=fleet_vehicle_scoped(con,ctx,vehicle_id)
    return [dict(row) for row in con.execute(
        """SELECT * FROM vehicle_maintenance
           WHERE vehicle_id=? ORDER BY id DESC""",(vehicle["id"],)
    ).fetchall()]


def vehicle_inspection_rows(con, ctx, vehicle_id):
    vehicle=fleet_vehicle_scoped(con,ctx,vehicle_id)
    return [dict(row) for row in con.execute(
        """SELECT * FROM vehicle_inspections
           WHERE vehicle_id=? ORDER BY id DESC""",(vehicle["id"],)
    ).fetchall()]


def vehicle_document_rows(con, ctx, vehicle_id):
    vehicle=fleet_vehicle_scoped(con,ctx,vehicle_id)
    rows=[]
    for row in con.execute(
        """SELECT id,vehicle_id,document_type,title,document_number,issue_date,expiry_date,
                  file_name,file_mime,
                  CASE WHEN file_data IS NULL THEN 0 ELSE 1 END AS has_file,
                  notes,created_by_user_id,created_by_name,created_at,updated_at
           FROM vehicle_documents WHERE vehicle_id=? ORDER BY id DESC""",(vehicle["id"],)
    ).fetchall():
        item=dict(row); item["has_file"]=bool(item["has_file"]); rows.append(item)
    return rows


def vehicle_status_rows(con, ctx, vehicle_id):
    vehicle=fleet_vehicle_scoped(con,ctx,vehicle_id)
    return [dict(row) for row in con.execute(
        """SELECT h.*,r.code AS route_code,d.name AS driver_name
           FROM vehicle_status_history h
           LEFT JOIN route_runs r ON r.id=h.route_id
           LEFT JOIN drivers d ON d.id=h.driver_id
           WHERE h.vehicle_id=? ORDER BY h.id DESC""",(vehicle["id"],)
    ).fetchall()]



CAMPAIGN_CHANNEL_KEYS=("in_app","sms","whatsapp","email")


def _campaign_notifications_v13(c):
    """Version 13: publishable offers, campaign delivery ledger, customer notifications and coupons."""
    ensure_columns(c,"campaigns",{
        "is_published":"INTEGER NOT NULL DEFAULT 0",
        "published_at":"TEXT",
        "published_by_user_id":"INTEGER",
        "placement":"TEXT NOT NULL DEFAULT 'website'",
        "coupon_code":"TEXT NOT NULL DEFAULT ''",
        "max_redemptions":"INTEGER NOT NULL DEFAULT 0",
        "per_customer_limit":"INTEGER NOT NULL DEFAULT 1",
        "min_order_amount":"REAL NOT NULL DEFAULT 0",
        "max_discount_amount":"REAL",
        "branch_id":"INTEGER",
        "auto_expire":"INTEGER NOT NULL DEFAULT 1",
        "last_dispatched_at":"TEXT",
    })
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_coupon_unique ON campaigns(upper(coupon_code)) WHERE coupon_code<>''")
    c.execute("CREATE INDEX IF NOT EXISTS idx_campaign_publish_state ON campaigns(is_published,status,start_at,end_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_campaign_branch ON campaigns(branch_id,id DESC)")

    c.execute("""CREATE TABLE IF NOT EXISTS campaign_deliveries(
      id INTEGER PRIMARY KEY,
      campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
      customer_user_id INTEGER REFERENCES customer_accounts(user_id) ON DELETE SET NULL,
      dispatch_key TEXT NOT NULL,
      channel TEXT NOT NULL CHECK(channel IN ('in_app','sms','whatsapp','email')),
      recipient TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'queued',
      provider TEXT NOT NULL DEFAULT '',
      provider_message_id TEXT NOT NULL DEFAULT '',
      provider_error TEXT NOT NULL DEFAULT '',
      sent_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_campaign_deliveries_campaign ON campaign_deliveries(campaign_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_campaign_deliveries_customer ON campaign_deliveries(customer_user_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_campaign_deliveries_dispatch ON campaign_deliveries(dispatch_key,id)")

    c.execute("""CREATE TABLE IF NOT EXISTS campaign_redemptions(
      id INTEGER PRIMARY KEY,
      campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
      customer_user_id INTEGER REFERENCES customer_accounts(user_id) ON DELETE SET NULL,
      shipment_id INTEGER REFERENCES shipments(id) ON DELETE SET NULL,
      promo_code TEXT NOT NULL DEFAULT '',
      discount_amount REAL NOT NULL DEFAULT 0 CHECK(discount_amount>=0),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(campaign_id,shipment_id)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_campaign_redemptions_campaign ON campaign_redemptions(campaign_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_campaign_redemptions_customer ON campaign_redemptions(customer_user_id,campaign_id,id DESC)")

    c.execute("""CREATE TABLE IF NOT EXISTS customer_notifications(
      id INTEGER PRIMARY KEY,
      customer_user_id INTEGER NOT NULL REFERENCES customer_accounts(user_id) ON DELETE CASCADE,
      campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
      shipment_id INTEGER REFERENCES shipments(id) ON DELETE SET NULL,
      category TEXT NOT NULL DEFAULT 'general',
      channel TEXT NOT NULL DEFAULT 'in_app',
      title TEXT NOT NULL,
      message TEXT NOT NULL,
      source_key TEXT NOT NULL UNIQUE,
      status TEXT NOT NULL DEFAULT 'unread' CHECK(status IN ('unread','read')),
      sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      read_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_customer_notifications_owner ON customer_notifications(customer_user_id,status,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_customer_notifications_campaign ON customer_notifications(campaign_id,id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_customer_notifications_shipment ON customer_notifications(shipment_id,id DESC)")

    # Shipment/invoice support for authoritative coupon application.
    ensure_columns(c,"shipments",{
        "campaign_id":"INTEGER",
        "promo_code":"TEXT NOT NULL DEFAULT ''",
        "discount_amount":"REAL NOT NULL DEFAULT 0",
    })
    c.execute("CREATE INDEX IF NOT EXISTS idx_shipments_campaign ON shipments(campaign_id,id DESC)")


def _campaign_dispatch_dedupe_v14(c):
    """Version 14: prevent accidental repeat delivery of the same campaign/channel to a customer."""
    c.execute("""CREATE TABLE IF NOT EXISTS campaign_delivery_guards(
      campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
      customer_user_id INTEGER NOT NULL REFERENCES customer_accounts(user_id) ON DELETE CASCADE,
      channel TEXT NOT NULL CHECK(channel IN ('in_app','sms','whatsapp','email')),
      first_delivery_id INTEGER REFERENCES campaign_deliveries(id) ON DELETE SET NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(campaign_id,customer_user_id,channel)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_campaign_delivery_guards_customer ON campaign_delivery_guards(customer_user_id,campaign_id)")

    # Protect campaigns that were already successfully sent before this migration.
    # Old duplicate history is intentionally preserved for auditability.
    c.execute("""INSERT OR IGNORE INTO campaign_delivery_guards(
                   campaign_id,customer_user_id,channel,first_delivery_id,created_at,updated_at
                 )
                 SELECT cd.campaign_id,cd.customer_user_id,cd.channel,MIN(cd.id),
                        MIN(COALESCE(cd.sent_at,cd.created_at)),
                        MAX(COALESCE(cd.sent_at,cd.created_at))
                 FROM campaign_deliveries cd
                 WHERE cd.customer_user_id IS NOT NULL
                   AND cd.status IN ('sent','demo')
                 GROUP BY cd.campaign_id,cd.customer_user_id,cd.channel""")


def normalize_campaign_channels(value):
    if isinstance(value,(list,tuple,set)):
        raw=[str(item or "").strip() for item in value]
    else:
        raw=re.split(r"[,|;+]+",str(value or "").strip())
    result=[]
    for item in raw:
        key=item.strip().casefold()
        if not key:
            continue
        if key in ("in_app","app","application","push","التطبيق","إشعار push","اشعار push"):
            channel="in_app"
        elif key in ("sms","رسالة sms","رساله sms"):
            channel="sms"
        elif key in ("whatsapp","واتساب","واتس اب"):
            channel="whatsapp"
        elif key in ("email","e-mail","البريد","بريد إلكتروني","بريد الكتروني"):
            channel="email"
        else:
            continue
        if channel not in result:
            result.append(channel)
    return ",".join(result or ["in_app"])


CAMPAIGN_LOCAL_TZ=timezone(timedelta(hours=3))  # Saudi Arabia (Asia/Riyadh), UTC+03:00


def _campaign_datetime(value):
    """Parse campaign form datetimes as Saudi local time when no offset is supplied."""
    value=str(value or "").strip()
    if not value:
        return None
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed=parsed.replace(tzinfo=CAMPAIGN_LOCAL_TZ)
    return parsed.astimezone(timezone.utc)


def refresh_campaign_states(con):
    now=datetime.now(timezone.utc)
    rows=con.execute(
        """SELECT id,status,start_at,end_at,is_published,auto_expire
           FROM campaigns
           WHERE is_published=1 OR status IN ('مجدولة','نشطة')"""
    ).fetchall()
    for row in rows:
        start=_campaign_datetime(row["start_at"])
        end=_campaign_datetime(row["end_at"])
        if row["auto_expire"] and end and end<now:
            con.execute(
                "UPDATE campaigns SET status='منتهية',is_published=0,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (row["id"],)
            )
        elif row["is_published"]:
            next_status="مجدولة" if start and start>now else "نشطة"
            if row["status"] not in ("متوقفة","منتهية") and row["status"]!=next_status:
                con.execute(
                    "UPDATE campaigns SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (next_status,row["id"])
                )


def campaign_branch_value(con,ctx,value):
    if value in (None,"",0,"0"):
        return None
    try:
        branch_id=int(value)
    except (TypeError,ValueError):
        raise ValueError("Select a valid campaign branch.") from None
    row=con.execute("SELECT id FROM branches WHERE id=? AND is_active=1",(branch_id,)).fetchone()
    if not row:
        raise ValueError("Select an active Ghazala branch.")
    if not ctx.get("global_scope") and branch_id not in set(ctx.get("branch_ids") or ()):
        raise auth.AccessDenied("Campaign branch is outside your allowed branch scope.")
    return branch_id


def campaign_settings_fields(con,ctx,data,creating=False):
    allowed={
        "placement","coupon_code","max_redemptions","per_customer_limit",
        "min_order_amount","max_discount_amount","branch_id","auto_expire"
    }
    fields={}
    if not isinstance(data,dict):
        return fields
    if "placement" in data:
        placement=str(data.get("placement") or "website").strip().lower()
        if placement not in ("website","customer_portal","both","none"):
            raise ValueError("Select a valid campaign placement.")
        fields["placement"]=placement
    if "coupon_code" in data:
        coupon=str(data.get("coupon_code") or "").strip().upper()
        if coupon and not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,31}",coupon):
            raise ValueError("Coupon code must use 3-32 letters, numbers, hyphens or underscores.")
        fields["coupon_code"]=coupon
    for key,label,maximum in (
        ("max_redemptions","Maximum redemptions",1_000_000),
        ("per_customer_limit","Per-customer redemption limit",1000),
    ):
        if key in data:
            try:
                value=int(data.get(key) or 0)
            except (TypeError,ValueError):
                raise ValueError(f"{label} must be a whole number.") from None
            minimum=1 if key=="per_customer_limit" else 0
            if not minimum<=value<=maximum:
                raise ValueError(f"{label} is outside the allowed range.")
            fields[key]=value
    for key,label in (
        ("min_order_amount","Minimum order amount"),
        ("max_discount_amount","Maximum discount amount"),
    ):
        if key in data:
            raw=data.get(key)
            if raw in (None,"") and key=="max_discount_amount":
                fields[key]=None
            else:
                try:
                    value=float(raw or 0)
                except (TypeError,ValueError):
                    raise ValueError(f"{label} must be a valid amount.") from None
                if not math.isfinite(value) or value<0 or value>100_000_000:
                    raise ValueError(f"{label} is outside the allowed range.")
                fields[key]=round(value,2)
    if "branch_id" in data:
        fields["branch_id"]=campaign_branch_value(con,ctx,data.get("branch_id"))
    if "auto_expire" in data:
        fields["auto_expire"]=1 if bool(data.get("auto_expire")) else 0
    return fields


def campaign_payload(con,row):
    item=dict(row)
    campaign_id=item["id"]
    delivery=con.execute(
        """SELECT count(*) AS total,
                  sum(CASE WHEN status IN ('sent','demo') THEN 1 ELSE 0 END) AS delivered,
                  sum(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
                  sum(CASE WHEN status='not_configured' THEN 1 ELSE 0 END) AS not_configured
           FROM campaign_deliveries WHERE campaign_id=?""",
        (campaign_id,)
    ).fetchone()
    redemptions=con.execute(
        "SELECT count(*) AS n,COALESCE(sum(discount_amount),0) AS amount FROM campaign_redemptions WHERE campaign_id=?",
        (campaign_id,)
    ).fetchone()
    branch=con.execute("SELECT id,name,city FROM branches WHERE id=?",(item.get("branch_id"),)).fetchone() if item.get("branch_id") else None
    item["channels"]=normalize_campaign_channels(item.get("channels",""))
    item["branch"]=dict(branch) if branch else None
    item["metrics"]={
        "deliveries":int(delivery["total"] or 0),
        "delivered":int(delivery["delivered"] or 0),
        "failed":int(delivery["failed"] or 0),
        "not_configured":int(delivery["not_configured"] or 0),
        "redemptions":int(redemptions["n"] or 0),
        "discount_total":round(float(redemptions["amount"] or 0),2),
    }
    max_redemptions=int(item.get("max_redemptions") or 0)
    item["remaining_redemptions"]=max(0,max_redemptions-item["metrics"]["redemptions"]) if max_redemptions else None
    return item


def campaign_rows(con,campaign_id=None):
    refresh_campaign_states(con)
    if campaign_id is None:
        rows=con.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
        return [campaign_payload(con,row) for row in rows]
    try:
        campaign_id=int(campaign_id)
    except (TypeError,ValueError):
        raise ValueError("Campaign not found.") from None
    row=con.execute("SELECT * FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
    if not row:
        raise ValueError("Campaign not found.")
    return campaign_payload(con,row)


def public_offer_rows(con):
    refresh_campaign_states(con)
    now=datetime.now(timezone.utc)
    rows=con.execute(
        """SELECT * FROM campaigns
           WHERE is_published=1 AND status='نشطة'
             AND campaign_type IN ('خصم','قسيمة')
             AND placement IN ('website','both')
           ORDER BY id DESC LIMIT 20"""
    ).fetchall()
    result=[]
    for row in rows:
        start=_campaign_datetime(row["start_at"]); end=_campaign_datetime(row["end_at"])
        if start and start>now: continue
        if end and end<now: continue
        item=campaign_payload(con,row)
        result.append({
            "id":item["id"],"code":item["code"],"name":item["name"],
            "campaign_type":item["campaign_type"],"message":item["message"],
            "discount_percent":item["discount_percent"],"coupon_code":item["coupon_code"],
            "start_at":item["start_at"],"end_at":item["end_at"],
            "placement":item["placement"],"min_order_amount":item["min_order_amount"],
            "max_discount_amount":item["max_discount_amount"],
            "remaining_redemptions":item["remaining_redemptions"],
            "branch":item["branch"],
        })
    return result


def campaign_coupon_quote(con,code,shipping_fee,subtotal,customer_user_id=None):
    code=str(code or "").strip().upper()
    if not code:
        return {"discount_amount":0,"promo_code":"","campaign_id":None,"campaign_name":""}
    refresh_campaign_states(con)
    row=con.execute(
        """SELECT * FROM campaigns
           WHERE is_published=1 AND status='نشطة'
             AND campaign_type IN ('خصم','قسيمة')
             AND (upper(coupon_code)=upper(?) OR upper(code)=upper(?))
           ORDER BY CASE WHEN upper(coupon_code)=upper(?) THEN 0 ELSE 1 END,id DESC LIMIT 1""",
        (code,code,code)
    ).fetchone()
    if not row:
        raise ValueError("Promo code is not active.")
    now=datetime.now(timezone.utc)
    start=_campaign_datetime(row["start_at"]); end=_campaign_datetime(row["end_at"])
    if start and start>now:
        raise ValueError("Promo code is not active yet.")
    if end and end<now:
        raise ValueError("Promo code has expired.")
    subtotal=max(0,float(subtotal or 0))
    if subtotal+1e-9<float(row["min_order_amount"] or 0):
        raise ValueError("Order total does not meet the promo minimum.")
    total_redemptions=con.execute(
        "SELECT count(*) FROM campaign_redemptions WHERE campaign_id=?",(row["id"],)
    ).fetchone()[0]
    max_redemptions=int(row["max_redemptions"] or 0)
    if max_redemptions and total_redemptions>=max_redemptions:
        raise ValueError("Promo code redemption limit has been reached.")
    if customer_user_id is not None:
        customer_count=con.execute(
            "SELECT count(*) FROM campaign_redemptions WHERE campaign_id=? AND customer_user_id=?",
            (row["id"],customer_user_id)
        ).fetchone()[0]
        if customer_count>=int(row["per_customer_limit"] or 1):
            raise ValueError("This customer has already used the promo code.")
    percent=max(0,min(100,float(row["discount_percent"] or 0)))
    discount=max(0,float(shipping_fee or 0))*percent/100
    if row["max_discount_amount"] is not None:
        discount=min(discount,max(0,float(row["max_discount_amount"] or 0)))
    return {
        "discount_amount":round(discount,2),
        "promo_code":row["coupon_code"] or row["code"],
        "campaign_id":row["id"],
        "campaign_name":row["name"],
        "discount_percent":percent,
    }


def record_campaign_redemption(con,campaign_id,customer_user_id,shipment_id,promo_code,discount_amount):
    if not campaign_id or not shipment_id or float(discount_amount or 0)<=0:
        return None
    cur=con.execute(
        """INSERT OR IGNORE INTO campaign_redemptions(
             campaign_id,customer_user_id,shipment_id,promo_code,discount_amount
           ) VALUES(?,?,?,?,?)""",
        (campaign_id,customer_user_id,shipment_id,str(promo_code or "").upper(),round(float(discount_amount),2))
    )
    return cur.lastrowid if cur.rowcount else None


def campaign_audience(con,campaign):
    sql="""SELECT u.id AS customer_user_id,u.display_name,u.mobile,
                  COALESCE(bp.email,'') AS email,
                  COALESCE(bp.account_type,'individual') AS account_type
           FROM customer_accounts ca
           JOIN users u ON u.id=ca.user_id AND u.is_active=1
           LEFT JOIN customer_business_profiles bp ON bp.user_id=u.id
           WHERE 1=1"""
    args=[]
    segment=str(campaign["target_segment"] or "").casefold()
    if "company" in segment or "شرك" in segment:
        sql+=" AND COALESCE(bp.account_type,'individual')='company'"
    elif "individual" in segment or "فرد" in segment:
        sql+=" AND COALESCE(bp.account_type,'individual')='individual'"
    if campaign["branch_id"]:
        sql+=""" AND EXISTS(
          SELECT 1 FROM customer_shipments cs
          JOIN shipment_scope ss ON ss.shipment_id=cs.shipment_id
          WHERE cs.customer_user_id=u.id
            AND (ss.origin_branch_id=? OR ss.destination_branch_id=?)
        )"""
        args.extend([campaign["branch_id"],campaign["branch_id"]])
    sql+=" ORDER BY u.id"
    return [dict(row) for row in con.execute(sql,args).fetchall()]


def customer_notification_rows(con,user,unread_only=False):
    customers.require_customer(con,user)
    where="customer_user_id=?"
    args=[user["id"]]
    if unread_only:
        where+=" AND status='unread'"
    rows=con.execute(
        """SELECT id,campaign_id,shipment_id,category,channel,title,message,status,
                  sent_at,read_at,created_at
           FROM customer_notifications WHERE """+where+" ORDER BY id DESC LIMIT 100",
        args
    ).fetchall()
    return [dict(row) for row in rows]


def create_customer_notification(con,customer_user_id,title,message,category="general",
                                 campaign_id=None,shipment_id=None,source_key=None):
    if not customer_user_id:
        return None
    source_key=str(source_key or f"notice:{uuid.uuid4().hex}")
    cur=con.execute(
        """INSERT OR IGNORE INTO customer_notifications(
             customer_user_id,campaign_id,shipment_id,category,channel,title,message,source_key
           ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            customer_user_id,campaign_id,shipment_id,str(category or "general")[:80],
            "in_app",str(title or "")[:240],str(message or "")[:2000],source_key[:240]
        )
    )
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='notification_delivery_log'").fetchone():
        _notification_log_upsert(
            con,customer_user_id=customer_user_id,shipment_id=shipment_id,category=category,
            event_type=category,source_key=source_key,channel="in_app",recipient=str(customer_user_id),
            title=title,message=message,status="sent",provider="Ghazala",attempt_count=1,
            sent_at=datetime.now(timezone.utc).isoformat(timespec="seconds")
        )
    return cur.lastrowid if cur.rowcount else None


def dispatch_campaign(con,campaign,user,request=None):
    refresh_campaign_states(con)
    campaign=dict(con.execute("SELECT * FROM campaigns WHERE id=?",(campaign["id"],)).fetchone())
    if not campaign["is_published"] or campaign["status"]!="نشطة":
        raise ValueError("Publish the campaign and wait until its active period before dispatching it.")

    channels=normalize_campaign_channels(campaign["channels"]).split(",")
    audience=campaign_audience(con,campaign)
    dispatch_key="DSP-"+uuid.uuid4().hex[:12].upper()
    stats={
        "audience":len(audience),
        "deliveries":0,
        "sent":0,
        "demo":0,
        "failed":0,
        "not_configured":0,
        "skipped":0,
    }
    title=campaign["name"]
    message=campaign["message"] or (
        f"{campaign['name']} · {campaign['discount_percent']}% discount"
        if float(campaign["discount_percent"] or 0)>0 else campaign["name"]
    )

    for customer in audience:
        customer_id=customer["customer_user_id"]

        for channel in channels:
            # Atomic idempotency guard. Once a campaign has been successfully
            # delivered to this customer over this channel, normal Dispatch Now
            # will not send it again.
            lock=con.execute(
                """INSERT OR IGNORE INTO campaign_delivery_guards(
                     campaign_id,customer_user_id,channel
                   ) VALUES(?,?,?)""",
                (campaign["id"],customer_id,channel)
            )
            if lock.rowcount==0:
                stats["skipped"]+=1
                continue

            recipient=""
            status="queued"
            provider=""
            error=""

            try:
                if channel=="in_app":
                    recipient=str(customer_id)
                    create_customer_notification(
                        con,customer_id,title,message,
                        category="campaign",campaign_id=campaign["id"],
                        # Stable key is a second safety layer against duplicate
                        # customer notifications for the same campaign.
                        source_key=f"campaign:{campaign['id']}:customer:{customer_id}"
                    )
                    status="sent"
                    provider="ghazala"

                elif channel=="sms":
                    recipient=str(customer.get("mobile") or "").strip()
                    if not recipient:
                        status="failed"
                        error="Customer mobile is not available."
                    else:
                        result=send_sms(con,recipient,"campaign",message)
                        status=result["delivery"]
                        provider="twilio" if status in ("sent","failed") else "demo"
                        error=result.get("error","")

                elif channel=="email":
                    recipient=str(customer.get("email") or "").strip()
                    status="not_configured"
                    provider="email"
                    error="Email provider is not configured."

                elif channel=="whatsapp":
                    recipient=str(customer.get("mobile") or "").strip()
                    status="not_configured"
                    provider="whatsapp"
                    error="WhatsApp provider is not configured."

                sent_at=datetime.now(timezone.utc).isoformat(timespec="seconds") if status in ("sent","demo") else None
                cur=con.execute(
                    """INSERT INTO campaign_deliveries(
                         campaign_id,customer_user_id,dispatch_key,channel,recipient,status,
                         provider,provider_error,sent_at
                       ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        campaign["id"],customer_id,dispatch_key,channel,
                        recipient,status,provider,error[:500],sent_at
                    )
                )
                stats["deliveries"]+=1
                if status in stats:
                    stats[status]+=1

                if status in ("sent","demo"):
                    con.execute(
                        """UPDATE campaign_delivery_guards
                           SET first_delivery_id=COALESCE(first_delivery_id,?),
                               updated_at=CURRENT_TIMESTAMP
                           WHERE campaign_id=? AND customer_user_id=? AND channel=?""",
                        (cur.lastrowid,campaign["id"],customer_id,channel)
                    )
                else:
                    # Failed / not-configured attempts are retryable later.
                    con.execute(
                        """DELETE FROM campaign_delivery_guards
                           WHERE campaign_id=? AND customer_user_id=? AND channel=?""",
                        (campaign["id"],customer_id,channel)
                    )

            except Exception:
                # Never leave a permanent lock behind when the actual attempt
                # did not complete.
                con.execute(
                    """DELETE FROM campaign_delivery_guards
                       WHERE campaign_id=? AND customer_user_id=? AND channel=?""",
                    (campaign["id"],customer_id,channel)
                )
                raise

    con.execute(
        "UPDATE campaigns SET last_dispatched_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (campaign["id"],)
    )
    if request is not None:
        write_audit(
            con,auth.context(con,user),"campaign.dispatched","campaign",campaign["id"],
            metadata={"dispatch_key":dispatch_key,**stats},request=request
        )
    return {"dispatch_key":dispatch_key,**stats}


def campaign_delivery_rows(con,campaign_id):
    return [dict(row) for row in con.execute(
        """SELECT cd.*,u.display_name AS customer_name
           FROM campaign_deliveries cd
           LEFT JOIN users u ON u.id=cd.customer_user_id
           WHERE cd.campaign_id=? ORDER BY cd.id DESC LIMIT 500""",
        (campaign_id,)
    ).fetchall()]


def campaign_redemption_rows(con,campaign_id):
    return [dict(row) for row in con.execute(
        """SELECT cr.*,u.display_name AS customer_name,s.awb
           FROM campaign_redemptions cr
           LEFT JOIN users u ON u.id=cr.customer_user_id
           LEFT JOIN shipments s ON s.id=cr.shipment_id
           WHERE cr.campaign_id=? ORDER BY cr.id DESC LIMIT 500""",
        (campaign_id,)
    ).fetchall()]


def _central_search_pattern(value):
    value=re.sub(r"\s+"," ",str(value or "").strip())[:120]
    if not value:
        return "", ""
    escaped=value.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
    return value,"%"+escaped+"%"


def central_search_payload(con,ctx,value,limit=8):
    """RBAC + branch-scoped cross-module search for the management portal."""
    query,pattern=_central_search_pattern(value)
    try:
        limit=max(1,min(20,int(limit or 8)))
    except (TypeError,ValueError):
        limit=8

    groups={
        "shipments":[],
        "clients":[],
        "invoices":[],
        "payments":[],
        "drivers":[],
        "vehicles":[],
        "routes":[],
        "staff":[],
        "campaigns":[],
    }
    if len(query)<2:
        return {"query":query,"total":0,"counts":{key:0 for key in groups},"groups":groups}

    like=" LIKE ? ESCAPE '\\'"

    if auth.allowed(ctx,"shipments.read"):
        pred,args=auth.sql_scope(ctx,"shipments","s")
        rows=con.execute(
            f"""SELECT s.id,s.awb,s.recipient,s.phone,s.sender_name,s.sender_phone,
                       s.origin,s.destination,s.status,s.stage,s.total_fee,s.payment_status,
                       s.created_at,d.name AS driver_name
                FROM shipments s
                LEFT JOIN drivers d ON d.id=s.driver_id
                WHERE ({pred}) AND (
                  COALESCE(s.awb,''){like} OR COALESCE(s.recipient,''){like} OR
                  COALESCE(s.phone,''){like} OR COALESCE(s.sender_name,''){like} OR
                  COALESCE(s.sender_phone,''){like} OR COALESCE(s.origin,''){like} OR
                  COALESCE(s.destination,''){like} OR COALESCE(d.name,''){like}
                )
                ORDER BY s.id DESC LIMIT ?""",
            [*args,*([pattern]*8),limit]
        ).fetchall()
        groups["shipments"]=[{
            "type":"shipment","id":row["id"],"key":row["awb"],
            "title":row["awb"],"subtitle":f'{row["origin"]} → {row["destination"]}',
            "status":row["status"],"recipient":row["recipient"],"sender":row["sender_name"],
            "phone":row["phone"],"payment_status":row["payment_status"],
            "total_fee":row["total_fee"],"created_at":row["created_at"],
            "driver_name":row["driver_name"],
        } for row in rows]

    if auth.allowed(ctx,"clients.read"):
        pred,args=auth.sql_scope(ctx,"clients","cl")
        rows=con.execute(
            f"""SELECT cl.id,cl.code,cl.name,cl.client_type,cl.city,cl.status,
                       cl.mobile,cl.email,cl.created_at
                FROM clients cl
                WHERE ({pred}) AND (
                  COALESCE(cl.code,''){like} OR COALESCE(cl.name,''){like} OR
                  COALESCE(cl.city,''){like} OR COALESCE(cl.mobile,''){like} OR
                  COALESCE(cl.email,''){like} OR COALESCE(cl.commercial_registration,''){like}
                )
                ORDER BY cl.id DESC LIMIT ?""",
            [*args,*([pattern]*6),limit]
        ).fetchall()
        groups["clients"]=[{
            "type":"client","id":row["id"],"key":row["code"],"title":row["name"],
            "subtitle":f'{row["code"]} · {row["city"]}',"status":row["status"],
            "client_type":row["client_type"],
            # Keep customer PII out of the normalized result for lower-privilege roles.
            "mobile":row["mobile"] if ctx.get("role") in ("system_admin","branch_manager") else "",
            "email":row["email"] if ctx.get("role") in ("system_admin","branch_manager") else "",
            "created_at":row["created_at"],
        } for row in rows]

    if auth.allowed(ctx,"shipments.payment") or auth.allowed(ctx,"reports.read"):
        pred,args=auth.sql_scope(ctx,"shipments","s")
        rows=con.execute(
            f"""SELECT i.id,i.invoice_number,i.total_amount,i.amount_paid,i.balance,i.currency,
                       i.status,i.issued_at,s.awb,u.display_name AS customer_name
                FROM invoices i
                JOIN shipments s ON s.id=i.shipment_id
                LEFT JOIN users u ON u.id=i.customer_user_id
                WHERE ({pred}) AND (
                  COALESCE(i.invoice_number,''){like} OR COALESCE(s.awb,''){like} OR
                  COALESCE(u.display_name,''){like}
                )
                ORDER BY i.id DESC LIMIT ?""",
            [*args,*([pattern]*3),limit]
        ).fetchall()
        groups["invoices"]=[{
            "type":"invoice","id":row["id"],"key":row["invoice_number"],
            "title":row["invoice_number"],"subtitle":row["awb"],"status":row["status"],
            "customer_name":row["customer_name"],"total_amount":row["total_amount"],
            "amount_paid":row["amount_paid"],"balance":row["balance"],
            "currency":row["currency"],"created_at":row["issued_at"],
        } for row in rows]

        rows=con.execute(
            f"""SELECT p.id,p.payment_number,p.amount,p.currency,p.method,p.status,
                       p.reference,p.provider,p.created_at,i.invoice_number,s.awb,
                       u.display_name AS customer_name
                FROM payments p
                JOIN invoices i ON i.id=p.invoice_id
                JOIN shipments s ON s.id=i.shipment_id
                LEFT JOIN users u ON u.id=p.customer_user_id
                WHERE ({pred}) AND (
                  COALESCE(p.payment_number,''){like} OR COALESCE(p.reference,''){like} OR
                  COALESCE(i.invoice_number,''){like} OR COALESCE(s.awb,''){like} OR
                  COALESCE(u.display_name,''){like}
                )
                ORDER BY p.id DESC LIMIT ?""",
            [*args,*([pattern]*5),limit]
        ).fetchall()
        groups["payments"]=[{
            "type":"payment","id":row["id"],"key":row["payment_number"],
            "title":row["payment_number"],"subtitle":f'{row["invoice_number"]} · {row["awb"]}',
            "status":row["status"],"customer_name":row["customer_name"],
            "amount":row["amount"],"currency":row["currency"],"method":row["method"],
            "provider":row["provider"],"created_at":row["created_at"],
        } for row in rows]

    if auth.allowed(ctx,"drivers.read"):
        pred,args=auth.sql_scope(ctx,"drivers","d")
        high=ctx.get("role") in ("system_admin","branch_manager")
        sensitive=(" OR COALESCE(d.national_id,'')"+like) if high else ""
        rows=con.execute(
            f"""SELECT d.id,d.name,d.mobile,d.branch,d.status,d.location_text,d.updated_at
                FROM drivers d
                WHERE ({pred}) AND (
                  COALESCE(d.name,''){like} OR COALESCE(d.mobile,''){like} OR
                  COALESCE(d.branch,''){like} OR COALESCE(d.location_text,''){like}
                  {sensitive}
                )
                ORDER BY d.id DESC LIMIT ?""",
            [*args,*([pattern]*(5 if high else 4)),limit]
        ).fetchall()
        groups["drivers"]=[{
            "type":"driver","id":row["id"],"key":str(row["id"]),"title":row["name"],
            "subtitle":row["branch"],"status":row["status"],"mobile":row["mobile"],
            "location":row["location_text"],"updated_at":row["updated_at"],
        } for row in rows]

    if auth.allowed(ctx,"vehicles.read"):
        pred,args=auth.sql_scope(ctx,"vehicles","v")
        rows=con.execute(
            f"""SELECT v.id,v.plate,v.vehicle_type,v.status,v.capacity_kg,
                       COALESCE(v.make,'') AS make,COALESCE(v.model,'') AS model,
                       COALESCE(v.model_year,'') AS model_year,COALESCE(v.updated_at,'') AS updated_at
                FROM vehicles v
                WHERE ({pred}) AND (
                  COALESCE(v.plate,''){like} OR COALESCE(v.vehicle_type,''){like} OR
                  COALESCE(v.make,''){like} OR COALESCE(v.model,''){like} OR
                  COALESCE(v.vin,''){like}
                )
                ORDER BY v.id DESC LIMIT ?""",
            [*args,*([pattern]*5),limit]
        ).fetchall()
        groups["vehicles"]=[{
            "type":"vehicle","id":row["id"],"key":row["plate"],"title":row["plate"],
            "subtitle":" ".join(str(x) for x in (row["make"],row["model"],row["model_year"]) if x).strip() or row["vehicle_type"],
            "status":row["status"],"vehicle_type":row["vehicle_type"],
            "capacity_kg":row["capacity_kg"],"updated_at":row["updated_at"],
        } for row in rows]

    if auth.allowed(ctx,"routes.read"):
        pred,args=auth.sql_scope(ctx,"routes","r")
        rows=con.execute(
            f"""SELECT r.id,r.code,r.origin,r.destination,r.status,r.departure_at,
                       r.started_at,r.arrived_at,d.name AS driver_name,v.plate AS vehicle_plate
                FROM route_runs r
                LEFT JOIN drivers d ON d.id=r.driver_id
                LEFT JOIN vehicles v ON v.id=r.vehicle_id
                WHERE ({pred}) AND (
                  COALESCE(r.code,''){like} OR COALESCE(r.origin,''){like} OR
                  COALESCE(r.destination,''){like} OR COALESCE(d.name,''){like} OR
                  COALESCE(v.plate,''){like}
                )
                ORDER BY r.id DESC LIMIT ?""",
            [*args,*([pattern]*5),limit]
        ).fetchall()
        groups["routes"]=[{
            "type":"route","id":row["id"],"key":row["code"],"title":row["code"],
            "subtitle":f'{row["origin"]} → {row["destination"]}',"status":row["status"],
            "driver_name":row["driver_name"],"vehicle_plate":row["vehicle_plate"],
            "departure_at":row["departure_at"],"started_at":row["started_at"],
            "arrived_at":row["arrived_at"],
        } for row in rows]

    if auth.allowed(ctx,"users.manage"):
        # Staff search must work with the names administrators actually see in
        # the RBAC / Human Resources UI, not only with the raw legacy users
        # table values.  Older databases can still store role="admin" and an
        # Arabic display name while the access layer exposes that same account
        # as "System Administrator" / system_admin.
        role_search_labels={
            "system_admin":(
                "System Administrator","System Admin","Administrator","Admin",
                "مدير النظام","مدير النظام الشامل",
            ),
            "branch_manager":(
                "Branch Manager","Manager","مدير الفرع","مدير العمليات",
            ),
            "office_employee":(
                "Office Employee","Office Staff","Staff","Employee",
                "موظف المكتب","موظف العمليات",
            ),
            "courier":(
                "Courier","Delivery Courier","Driver","مندوب","مندوب التوصيل",
            ),
            "accountant":(
                "Accountant","Finance","Finance Staff","المحاسب",
            ),
            "customer":(
                "Customer","العميل",
            ),
        }

        def staff_search_text(value):
            # Treat spaces, underscores and hyphens as equivalent so searches
            # such as "system admin", "system_admin" and "System-Admin" match.
            return re.sub(r"[\s_-]+"," ",str(value or "").strip()).casefold()

        needle=staff_search_text(query)
        matches=[]
        rows=con.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
        for row in rows:
            item=safe_user(row,con)
            access_role=str(item.get("access_role") or row["role"] or "")
            # Central Search's "Staff" group should not turn into a customer
            # account directory. Customer accounts remain handled by their
            # dedicated portal/CRM flows.
            if access_role=="customer":
                continue

            role_labels=role_search_labels.get(access_role,())
            branches=item.get("branches") or []
            branch_values=[]
            for branch in branches:
                if isinstance(branch,dict):
                    branch_values.extend((
                        branch.get("name",""),branch.get("code",""),branch.get("city","")
                    ))

            haystack=staff_search_text(" ".join(str(value or "") for value in (
                row["username"],row["display_name"],row["mobile"],row["national_id"],
                row["role"],access_role,*role_labels,*branch_values
            )))
            if needle and needle in haystack:
                matches.append((row,item,role_labels))
                if len(matches)>=limit:
                    break

        groups["staff"]=[]
        for row,item,role_labels in matches:
            access_role=str(item.get("access_role") or row["role"] or "")
            friendly_role=role_labels[0] if role_labels else access_role.replace("_"," ").title()
            subtitle=row["username"]
            if friendly_role:
                subtitle=f"{subtitle} · {friendly_role}"
            groups["staff"].append({
                "type":"staff","id":row["id"],"key":row["username"],
                "title":row["display_name"] or friendly_role or row["username"],
                "subtitle":subtitle,
                "status":"active" if row["is_active"] else "inactive",
                "role":access_role,
                "mobile":row["mobile"],
                "created_at":row["created_at"],
            })

    if auth.allowed(ctx,"campaigns.read"):
        rows=con.execute(
            f"""SELECT id,code,name,campaign_type,status,discount_percent,coupon_code,
                       is_published,start_at,end_at
                FROM campaigns
                WHERE COALESCE(code,''){like} OR COALESCE(name,''){like} OR
                      COALESCE(coupon_code,''){like} OR COALESCE(status,''){like}
                ORDER BY id DESC LIMIT ?""",
            [*([pattern]*4),limit]
        ).fetchall()
        groups["campaigns"]=[{
            "type":"campaign","id":row["id"],"key":row["code"],"title":row["name"],
            "subtitle":row["coupon_code"] or row["code"],"status":row["status"],
            "campaign_type":row["campaign_type"],"discount_percent":row["discount_percent"],
            "is_published":bool(row["is_published"]),"start_at":row["start_at"],"end_at":row["end_at"],
        } for row in rows]

    counts={key:len(rows) for key,rows in groups.items()}
    return {"query":query,"total":sum(counts.values()),"counts":counts,"groups":groups}


def audit_rows_payload(con,query):
    """Enriched immutable audit feed with actor/branch labels and safe filters."""
    where=[]; args=[]
    for key,column in (
        ("action","ae.action"),("entity_type","ae.entity_type"),("entity_id","ae.entity_id"),
        ("actor_user_id","ae.actor_user_id"),("branch_id","ae.branch_id")
    ):
        value=query.get(key)
        if value:
            where.append(column+"=?"); args.append(value[0])

    text=str(query.get("q",[""])[0] or "").strip()[:120]
    if text:
        _,pattern=_central_search_pattern(text)
        like=" LIKE ? ESCAPE '\\'"
        where.append("("+" OR ".join([
            "COALESCE(ae.action,'')"+like,
            "COALESCE(ae.entity_type,'')"+like,
            "COALESCE(ae.entity_id,'')"+like,
            "COALESCE(u.display_name,'')"+like,
            "COALESCE(u.username,'')"+like,
            "COALESCE(b.name,'')"+like,
            "COALESCE(b.code,'')"+like,
        ])+")")
        args.extend([pattern]*7)

    start=str(query.get("from",[""])[0] or "").strip()
    end=str(query.get("to",[""])[0] or "").strip()
    if start:
        where.append("ae.created_at>=?"); args.append(start)
    if end:
        where.append("ae.created_at<=?"); args.append(end)

    try:
        limit=max(1,min(200,int(query.get("limit",["100"])[0])))
        before=int(query.get("before_id",["0"])[0])
    except (TypeError,ValueError):
        raise ValueError("Invalid audit filter.")
    if before:
        where.append("ae.id<?"); args.append(before)

    sql="""SELECT ae.*,
                  u.display_name AS actor_name,u.username AS actor_username,
                  b.name AS branch_name,b.code AS branch_code,b.city AS branch_city
           FROM audit_events ae
           LEFT JOIN users u ON u.id=ae.actor_user_id
           LEFT JOIN branches b ON b.id=ae.branch_id"""
    if where:
        sql+=" WHERE "+" AND ".join(where)
    sql+=" ORDER BY ae.id DESC LIMIT ?"
    return [dict(row) for row in con.execute(sql,[*args,limit]).fetchall()]


def audit_summary_payload(con):
    """Compact security/operations summary for the Audit Log UI."""
    total=con.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    last_24h=con.execute(
        "SELECT count(*) FROM audit_events WHERE datetime(created_at)>=datetime('now','-24 hours')"
    ).fetchone()[0]
    last_hour=con.execute(
        "SELECT count(*) FROM audit_events WHERE datetime(created_at)>=datetime('now','-1 hour')"
    ).fetchone()[0]
    actions=[dict(row) for row in con.execute(
        """SELECT action,count(*) AS count
           FROM audit_events GROUP BY action ORDER BY count DESC,action LIMIT 8"""
    ).fetchall()]
    entities=[dict(row) for row in con.execute(
        """SELECT entity_type,count(*) AS count
           FROM audit_events GROUP BY entity_type ORDER BY count DESC,entity_type LIMIT 8"""
    ).fetchall()]
    actors=[dict(row) for row in con.execute(
        """SELECT ae.actor_user_id,u.display_name AS actor_name,u.username AS actor_username,count(*) AS count
           FROM audit_events ae LEFT JOIN users u ON u.id=ae.actor_user_id
           GROUP BY ae.actor_user_id,u.display_name,u.username
           ORDER BY count DESC LIMIT 8"""
    ).fetchall()]
    return {
        "total":total,"last_24h":last_24h,"last_hour":last_hour,
        "top_actions":actions,"top_entities":entities,"top_actors":actors,
    }


# ---------------------------------------------------------------------------
# Executive Dashboard + Management Reports
# ---------------------------------------------------------------------------

DASHBOARD_PERIODS = {
    "today": 1,
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "365d": 365,
    "all": None,
}


def _dashboard_period_window(value):
    key=str(value or "30d").strip().lower()
    if key not in DASHBOARD_PERIODS:
        key="30d"
    days=DASHBOARD_PERIODS[key]
    now=datetime.now(timezone.utc)
    ksa=timezone(timedelta(hours=3))

    if key=="today":
        local_now=now.astimezone(ksa)
        local_start=local_now.replace(hour=0,minute=0,second=0,microsecond=0)
        start=local_start.astimezone(timezone.utc)
    elif days is None:
        start=None
    else:
        start=now-timedelta(days=days)

    previous_start=None
    previous_end=None
    if start is not None:
        duration=now-start
        previous_end=start
        previous_start=start-duration

    def stamp(dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None

    return {
        "key":key,
        "days":days,
        "start":stamp(start),
        "end":stamp(now),
        "previous_start":stamp(previous_start),
        "previous_end":stamp(previous_end),
        "timezone":"Asia/Riyadh",
    }


def _dashboard_time_filter(column,window,previous=False):
    if previous:
        start=window.get("previous_start")
        end=window.get("previous_end")
    else:
        start=window.get("start")
        end=window.get("end")
    if not start:
        return "",[]
    return f" AND datetime({column})>=datetime(?) AND datetime({column})<datetime(?)",[start,end]


def _dashboard_scalar(con,sql,args=()):
    row=con.execute(sql,args).fetchone()
    if row is None:
        return 0
    value=row[0]
    return 0 if value is None else value


def _dashboard_growth(current,previous):
    current=float(current or 0)
    previous=float(previous or 0)
    if previous==0:
        return 100.0 if current>0 else 0.0
    return round(((current-previous)/previous)*100,1)


def _dashboard_money(value):
    return round(float(value or 0),2)


def _dashboard_delivered_from_distribution(rows):
    """Return the delivered count from the normalized status distribution.

    Dashboard KPI cards and status-distribution charts must use one authoritative
    delivery definition.  _dashboard_status_distribution() already normalizes
    durable POD evidence and legacy delivered status aliases to 'تم الاستلام';
    derive the KPI from those exact rows instead of repeating a second SQL rule.
    """
    return sum(
        int(row.get("count",0) or 0)
        for row in (rows or [])
        if str(row.get("status","")).strip()=="تم الاستلام"
    )


def _dashboard_previous_window(window):
    previous=dict(window or {})
    previous["start"]=(window or {}).get("previous_start")
    previous["end"]=(window or {}).get("previous_end")
    return previous


def _dashboard_status_distribution(con,shipment_pred,shipment_args,window):
    period_sql,period_args=_dashboard_time_filter("s.created_at",window)
    # Historical rows can legitimately predate POD enforcement.  Treat a
    # shipment as delivered when either its status says delivered or durable
    # POD evidence exists, then use that same rule everywhere on dashboards.
    delivered_sql="""(
        EXISTS(SELECT 1 FROM pod_records p WHERE p.shipment_id=s.id)
        OR lower(trim(COALESCE(s.status,'')))='delivered'
        OR trim(COALESCE(s.status,'')) IN ('تم الاستلام','تم التسليم')
    )"""
    rows=con.execute(
        """SELECT CASE WHEN """+delivered_sql+"""
                         THEN 'تم الاستلام'
                         ELSE COALESCE(s.status,'Unknown')
                    END AS status,
                  count(*) AS count
           FROM shipments s
           WHERE ("""+shipment_pred+")"+period_sql+
        """ GROUP BY CASE WHEN """+delivered_sql+"""
                            THEN 'تم الاستلام'
                            ELSE COALESCE(s.status,'Unknown')
                       END
            ORDER BY count DESC,status""",
        [*shipment_args,*period_args],
    ).fetchall()
    return [dict(row) for row in rows]


def _dashboard_daily_series(con,shipment_pred,shipment_args,window,finance_enabled):
    requested_days=window.get("days")
    chart_days=30 if requested_days is None else max(1,min(int(requested_days),90))
    ksa=timezone(timedelta(hours=3))
    today=datetime.now(ksa).date()
    days=[today-timedelta(days=offset) for offset in range(chart_days-1,-1,-1)]
    labels=[day.isoformat() for day in days]
    chart_start=(datetime.combine(days[0],datetime.min.time(),tzinfo=ksa)
                 .astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    chart_end=(datetime.now(timezone.utc)+timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")

    created_rows=con.execute(
        """SELECT date(datetime(s.created_at,'+3 hours')) AS day,count(*) AS count
           FROM shipments s
           WHERE ("""+shipment_pred+""")
             AND datetime(s.created_at)>=datetime(?) AND datetime(s.created_at)<datetime(?)
           GROUP BY day""",
        [*shipment_args,chart_start,chart_end],
    ).fetchall()
    created={row["day"]:int(row["count"] or 0) for row in created_rows}

    delivered_rows=con.execute(
        """SELECT date(datetime(p.verified_at,'+3 hours')) AS day,count(*) AS count
           FROM pod_records p
           JOIN shipments s ON s.id=p.shipment_id
           WHERE ("""+shipment_pred+""")
             AND datetime(p.verified_at)>=datetime(?) AND datetime(p.verified_at)<datetime(?)
           GROUP BY day""",
        [*shipment_args,chart_start,chart_end],
    ).fetchall()
    delivered={row["day"]:int(row["count"] or 0) for row in delivered_rows}

    invoiced={}
    collected={}
    if finance_enabled:
        invoiced_rows=con.execute(
            """SELECT date(datetime(i.issued_at,'+3 hours')) AS day,
                      COALESCE(sum(i.total_amount),0) AS total
               FROM invoices i
               JOIN shipments s ON s.id=i.shipment_id
               WHERE ("""+shipment_pred+""")
                 AND datetime(i.issued_at)>=datetime(?) AND datetime(i.issued_at)<datetime(?)
               GROUP BY day""",
            [*shipment_args,chart_start,chart_end],
        ).fetchall()
        invoiced={row["day"]:_dashboard_money(row["total"]) for row in invoiced_rows}

        collected_rows=con.execute(
            """SELECT date(datetime(COALESCE(p.paid_at,p.created_at),'+3 hours')) AS day,
                      COALESCE(sum(p.amount),0) AS total
               FROM payments p
               JOIN invoices i ON i.id=p.invoice_id
               JOIN shipments s ON s.id=i.shipment_id
               WHERE ("""+shipment_pred+""") AND p.status='paid'
                 AND datetime(COALESCE(p.paid_at,p.created_at))>=datetime(?)
                 AND datetime(COALESCE(p.paid_at,p.created_at))<datetime(?)
               GROUP BY day""",
            [*shipment_args,chart_start,chart_end],
        ).fetchall()
        collected={row["day"]:_dashboard_money(row["total"]) for row in collected_rows}

    return {
        "days":chart_days,
        "truncated":requested_days is None or (requested_days is not None and requested_days>90),
        "rows":[{
            "date":day,
            "shipments":created.get(day,0),
            "delivered":delivered.get(day,0),
            "invoiced":invoiced.get(day,0),
            "collected":collected.get(day,0),
        } for day in labels],
    }


def _dashboard_branch_performance(con,ctx,shipment_pred,shipment_args,window,finance_enabled):
    if not auth.allowed(ctx,"branches.read"):
        return []
    branch_pred,branch_args=auth.sql_scope(ctx,"branches","b")
    branches=con.execute(
        """SELECT b.id,b.code,b.name,b.city
           FROM branches b
           WHERE ("""+branch_pred+""") AND b.is_active=1
           ORDER BY b.city,b.name,b.id""",
        branch_args,
    ).fetchall()

    period_sql,period_args=_dashboard_time_filter("s.created_at",window)
    result=[]
    for branch in branches:
        origin_expr="""COALESCE(
          ss.origin_branch_id,
          (SELECT bx.id FROM branches bx
           WHERE bx.city=s.origin AND bx.is_active=1 ORDER BY bx.id LIMIT 1)
        )"""
        destination_expr="""COALESCE(
          ss.destination_branch_id,
          (SELECT bx.id FROM branches bx
           WHERE bx.code=s.recipient_branch AND bx.is_active=1
           ORDER BY bx.id LIMIT 1),
          (SELECT bx.id FROM branches bx
           WHERE bx.city=s.destination AND bx.is_active=1
           ORDER BY bx.id LIMIT 1)
        )"""

        originated=_dashboard_scalar(
            con,
            """SELECT count(*)
               FROM shipments s
               LEFT JOIN shipment_scope ss ON ss.shipment_id=s.id
               WHERE ("""+shipment_pred+") AND "+origin_expr+"=?"+period_sql,
            [*shipment_args,branch["id"],*period_args],
        )
        received=_dashboard_scalar(
            con,
            """SELECT count(*)
               FROM shipments s
               LEFT JOIN shipment_scope ss ON ss.shipment_id=s.id
               WHERE ("""+shipment_pred+") AND "+destination_expr+"=?"+period_sql,
            [*shipment_args,branch["id"],*period_args],
        )
        delivered=_dashboard_scalar(
            con,
            """SELECT count(*)
               FROM shipments s
               LEFT JOIN shipment_scope ss ON ss.shipment_id=s.id
               WHERE ("""+shipment_pred+") AND "+destination_expr+"""=?
                 AND EXISTS(SELECT 1 FROM pod_records p WHERE p.shipment_id=s.id)"""+period_sql,
            [*shipment_args,branch["id"],*period_args],
        )

        invoiced=0
        if finance_enabled:
            invoice_period_sql,invoice_period_args=_dashboard_time_filter("i.issued_at",window)
            invoiced=_dashboard_scalar(
                con,
                """SELECT COALESCE(sum(i.total_amount),0)
                   FROM invoices i
                   JOIN shipments s ON s.id=i.shipment_id
                   LEFT JOIN shipment_scope ss ON ss.shipment_id=s.id
                   WHERE ("""+shipment_pred+") AND "+origin_expr+"=?"+invoice_period_sql,
                [*shipment_args,branch["id"],*invoice_period_args],
            )

        result.append({
            "branch_id":branch["id"],
            "code":branch["code"],
            "name":branch["name"],
            "city":branch["city"],
            "originated":int(originated or 0),
            "received":int(received or 0),
            "delivered":int(delivered or 0),
            "delivery_rate":round((float(delivered or 0)/float(received or 1))*100,1) if received else 0,
            "invoiced":_dashboard_money(invoiced),
        })
    return result


def _dashboard_courier_performance(con,ctx,shipment_pred,shipment_args,window):
    if not auth.allowed(ctx,"drivers.read"):
        return {"total":0,"active":0,"rows":[]}
    driver_pred,driver_args=auth.sql_scope(ctx,"drivers","d")
    drivers=con.execute(
        """SELECT d.id,d.name,d.branch,d.status,d.mobile
           FROM drivers d
           WHERE ("""+driver_pred+""")
           ORDER BY d.id""",
        driver_args,
    ).fetchall()

    attempt_sql,attempt_args=_dashboard_time_filter("da.started_at",window)
    rows=[]
    for driver in drivers:
        aggregate=con.execute(
            """SELECT count(DISTINCT da.shipment_id) AS attempted_shipments,
                      sum(CASE WHEN da.outcome='delivered' THEN 1 ELSE 0 END) AS delivered_attempts,
                      sum(CASE WHEN da.outcome='failed' THEN 1 ELSE 0 END) AS failed_attempts
               FROM delivery_attempts da
               JOIN shipments s ON s.id=da.shipment_id
               WHERE ("""+shipment_pred+""") AND da.driver_id=?"""+attempt_sql,
            [*shipment_args,driver["id"],*attempt_args],
        ).fetchone()
        delivered=int(aggregate["delivered_attempts"] or 0)
        failed=int(aggregate["failed_attempts"] or 0)
        attempts=delivered+failed
        rows.append({
            "driver_id":driver["id"],
            "name":driver["name"],
            "branch":driver["branch"],
            "status":driver["status"],
            "attempted_shipments":int(aggregate["attempted_shipments"] or 0),
            "delivered_attempts":delivered,
            "failed_attempts":failed,
            "success_rate":round((delivered/max(attempts,1))*100,1) if attempts else 0,
        })
    rows.sort(key=lambda row:(row["delivered_attempts"],row["attempted_shipments"]),reverse=True)
    active=sum(1 for row in rows if str(row["status"] or "") not in ("متاح","غير نشط","inactive"))
    return {"total":len(rows),"active":active,"rows":rows[:10]}


def _dashboard_fleet(con,ctx,window):
    if not auth.allowed(ctx,"vehicles.read"):
        return None
    vehicle_pred,vehicle_args=auth.sql_scope(ctx,"vehicles","v")
    status_rows=con.execute(
        """SELECT COALESCE(v.status,'Unknown') AS status,count(*) AS count
           FROM vehicles v
           WHERE ("""+vehicle_pred+""") AND COALESCE(v.is_active,1)=1
           GROUP BY COALESCE(v.status,'Unknown')
           ORDER BY count DESC""",
        vehicle_args,
    ).fetchall()
    total=sum(int(row["count"] or 0) for row in status_rows)
    available=sum(int(row["count"] or 0) for row in status_rows if row["status"]=="متاح")
    maintenance=sum(int(row["count"] or 0) for row in status_rows if row["status"]=="صيانة")
    on_route=sum(int(row["count"] or 0) for row in status_rows if row["status"]=="في الطريق")

    maintenance_in_progress=_dashboard_scalar(
        con,
        """SELECT count(*)
           FROM vehicle_maintenance vm
           JOIN vehicles v ON v.id=vm.vehicle_id
           WHERE ("""+vehicle_pred+""") AND vm.status='in_progress'""",
        vehicle_args,
    )
    maintenance_due=_dashboard_scalar(
        con,
        """SELECT count(*)
           FROM vehicle_maintenance vm
           JOIN vehicles v ON v.id=vm.vehicle_id
           WHERE ("""+vehicle_pred+""") AND vm.status='scheduled'
             AND vm.scheduled_at IS NOT NULL
             AND datetime(vm.scheduled_at)<=datetime('now','+30 days')""",
        vehicle_args,
    )
    expiring_documents=_dashboard_scalar(
        con,
        """SELECT count(*)
           FROM vehicle_documents vd
           JOIN vehicles v ON v.id=vd.vehicle_id
           WHERE ("""+vehicle_pred+""")
             AND vd.expiry_date IS NOT NULL AND trim(vd.expiry_date)<>''
             AND date(vd.expiry_date)<=date('now','+30 days')""",
        vehicle_args,
    )

    route_pred,route_args=auth.sql_scope(ctx,"routes","r")
    route_period_sql,route_period_args=_dashboard_time_filter("r.created_at",window)
    route_count=_dashboard_scalar(
        con,
        """SELECT count(*) FROM route_runs r
           WHERE ("""+route_pred+")"+route_period_sql,
        [*route_args,*route_period_args],
    )

    return {
        "total":total,
        "available":available,
        "on_route":on_route,
        "maintenance":maintenance,
        "maintenance_in_progress":int(maintenance_in_progress or 0),
        "maintenance_due_30d":int(maintenance_due or 0),
        "documents_expiring_30d":int(expiring_documents or 0),
        "routes_in_period":int(route_count or 0),
        "utilization_rate":round((on_route/max(total,1))*100,1) if total else 0,
        "status_distribution":[dict(row) for row in status_rows],
    }


def _dashboard_finance(con,ctx,shipment_pred,shipment_args,window):
    if not (auth.allowed(ctx,"shipments.payment") or auth.allowed(ctx,"reports.read")):
        return None

    invoice_period_sql,invoice_period_args=_dashboard_time_filter("i.issued_at",window)
    invoiced=_dashboard_scalar(
        con,
        """SELECT COALESCE(sum(i.total_amount),0)
           FROM invoices i JOIN shipments s ON s.id=i.shipment_id
           WHERE ("""+shipment_pred+")"+invoice_period_sql,
        [*shipment_args,*invoice_period_args],
    )
    invoice_count=_dashboard_scalar(
        con,
        """SELECT count(*)
           FROM invoices i JOIN shipments s ON s.id=i.shipment_id
           WHERE ("""+shipment_pred+")"+invoice_period_sql,
        [*shipment_args,*invoice_period_args],
    )

    payment_period_sql,payment_period_args=_dashboard_time_filter("COALESCE(p.paid_at,p.created_at)",window)
    collected=_dashboard_scalar(
        con,
        """SELECT COALESCE(sum(p.amount),0)
           FROM payments p
           JOIN invoices i ON i.id=p.invoice_id
           JOIN shipments s ON s.id=i.shipment_id
           WHERE ("""+shipment_pred+") AND p.status='paid'"+payment_period_sql,
        [*shipment_args,*payment_period_args],
    )

    outstanding=_dashboard_scalar(
        con,
        """SELECT COALESCE(sum(i.balance),0)
           FROM invoices i JOIN shipments s ON s.id=i.shipment_id
           WHERE ("""+shipment_pred+") AND i.status IN ('issued','partially_paid')",
        shipment_args,
    )
    unpaid_count=_dashboard_scalar(
        con,
        """SELECT count(*)
           FROM invoices i JOIN shipments s ON s.id=i.shipment_id
           WHERE ("""+shipment_pred+") AND i.status IN ('issued','partially_paid') AND i.balance>0",
        shipment_args,
    )

    shipment_period_sql,shipment_period_args=_dashboard_time_filter("s.created_at",window)
    discounts=_dashboard_scalar(
        con,
        """SELECT COALESCE(sum(COALESCE(s.discount_amount,0)),0)
           FROM shipments s
           WHERE ("""+shipment_pred+")"+shipment_period_sql,
        [*shipment_args,*shipment_period_args],
    )

    methods=con.execute(
        """SELECT COALESCE(p.method,'other') AS method,count(*) AS count,
                  COALESCE(sum(p.amount),0) AS amount
           FROM payments p
           JOIN invoices i ON i.id=p.invoice_id
           JOIN shipments s ON s.id=i.shipment_id
           WHERE ("""+shipment_pred+") AND p.status='paid'"+payment_period_sql+
        """ GROUP BY COALESCE(p.method,'other') ORDER BY amount DESC""",
        [*shipment_args,*payment_period_args],
    ).fetchall()

    previous_invoiced=0
    previous_collected=0
    if window.get("previous_start"):
        prev_invoice_sql,prev_invoice_args=_dashboard_time_filter("i.issued_at",window,True)
        previous_invoiced=_dashboard_scalar(
            con,
            """SELECT COALESCE(sum(i.total_amount),0)
               FROM invoices i JOIN shipments s ON s.id=i.shipment_id
               WHERE ("""+shipment_pred+")"+prev_invoice_sql,
            [*shipment_args,*prev_invoice_args],
        )
        prev_payment_sql,prev_payment_args=_dashboard_time_filter("COALESCE(p.paid_at,p.created_at)",window,True)
        previous_collected=_dashboard_scalar(
            con,
            """SELECT COALESCE(sum(p.amount),0)
               FROM payments p
               JOIN invoices i ON i.id=p.invoice_id
               JOIN shipments s ON s.id=i.shipment_id
               WHERE ("""+shipment_pred+") AND p.status='paid'"+prev_payment_sql,
            [*shipment_args,*prev_payment_args],
        )

    return {
        "currency":"SAR",
        "invoice_count":int(invoice_count or 0),
        "invoiced":_dashboard_money(invoiced),
        "collected":_dashboard_money(collected),
        "outstanding":_dashboard_money(outstanding),
        "outstanding_invoice_count":int(unpaid_count or 0),
        "discounts":_dashboard_money(discounts),
        "collection_rate":round((float(collected or 0)/max(float(invoiced or 0),1))*100,1) if invoiced else 0,
        "invoiced_growth":_dashboard_growth(invoiced,previous_invoiced) if window.get("previous_start") else None,
        "collected_growth":_dashboard_growth(collected,previous_collected) if window.get("previous_start") else None,
        "payment_methods":[
            {"method":row["method"],"count":int(row["count"] or 0),"amount":_dashboard_money(row["amount"])}
            for row in methods
        ],
    }


def _dashboard_campaigns(con,ctx,window):
    if not auth.allowed(ctx,"campaigns.read"):
        return None
    refresh_campaign_states(con)
    total=_dashboard_scalar(con,"SELECT count(*) FROM campaigns")
    published=_dashboard_scalar(con,"SELECT count(*) FROM campaigns WHERE is_published=1")
    active=_dashboard_scalar(con,"SELECT count(*) FROM campaigns WHERE is_published=1 AND status='نشطة'")

    delivery_sql,delivery_args=_dashboard_time_filter("cd.created_at",window)
    deliveries=_dashboard_scalar(
        con,
        "SELECT count(*) FROM campaign_deliveries cd WHERE 1=1"+delivery_sql,
        delivery_args,
    )
    sent=_dashboard_scalar(
        con,
        "SELECT count(*) FROM campaign_deliveries cd WHERE cd.status IN ('sent','demo')"+delivery_sql,
        delivery_args,
    )
    failed=_dashboard_scalar(
        con,
        "SELECT count(*) FROM campaign_deliveries cd WHERE cd.status='failed'"+delivery_sql,
        delivery_args,
    )

    redemption_sql,redemption_args=_dashboard_time_filter("cr.created_at",window)
    redemptions=_dashboard_scalar(
        con,
        "SELECT count(*) FROM campaign_redemptions cr WHERE 1=1"+redemption_sql,
        redemption_args,
    )
    discount=_dashboard_scalar(
        con,
        "SELECT COALESCE(sum(cr.discount_amount),0) FROM campaign_redemptions cr WHERE 1=1"+redemption_sql,
        redemption_args,
    )

    top=con.execute(
        """SELECT c.id,c.code,c.name,c.status,c.is_published,
                  COALESCE((SELECT count(*) FROM campaign_deliveries cd
                            WHERE cd.campaign_id=c.id),0) AS deliveries,
                  COALESCE((SELECT count(*) FROM campaign_deliveries cd
                            WHERE cd.campaign_id=c.id AND cd.status IN ('sent','demo')),0) AS sent,
                  COALESCE((SELECT count(*) FROM campaign_redemptions cr
                            WHERE cr.campaign_id=c.id),0) AS redemptions,
                  COALESCE((SELECT sum(cr.discount_amount) FROM campaign_redemptions cr
                            WHERE cr.campaign_id=c.id),0) AS discount_total
           FROM campaigns c
           ORDER BY redemptions DESC,sent DESC,c.id DESC
           LIMIT 8"""
    ).fetchall()

    return {
        "total":int(total or 0),
        "published":int(published or 0),
        "active":int(active or 0),
        "deliveries":int(deliveries or 0),
        "sent":int(sent or 0),
        "failed":int(failed or 0),
        "redemptions":int(redemptions or 0),
        "discount_total":_dashboard_money(discount),
        "delivery_success_rate":round((float(sent or 0)/max(float(deliveries or 0),1))*100,1) if deliveries else 0,
        "top":[{
            "id":row["id"],"code":row["code"],"name":row["name"],
            "status":row["status"],"is_published":bool(row["is_published"]),
            "deliveries":int(row["deliveries"] or 0),
            "sent":int(row["sent"] or 0),
            "redemptions":int(row["redemptions"] or 0),
            "discount_total":_dashboard_money(row["discount_total"]),
        } for row in top],
    }


def executive_dashboard_payload(con,ctx,period="30d"):
    window=_dashboard_period_window(period)
    shipment_pred,shipment_args=auth.sql_scope(ctx,"shipments","s")
    period_sql,period_args=_dashboard_time_filter("s.created_at",window)

    shipments=_dashboard_scalar(
        con,
        "SELECT count(*) FROM shipments s WHERE ("+shipment_pred+")"+period_sql,
        [*shipment_args,*period_args],
    )
    status_distribution=_dashboard_status_distribution(
        con,shipment_pred,shipment_args,window
    )
    delivered=_dashboard_delivered_from_distribution(status_distribution)
    failed_open=_dashboard_scalar(
        con,
        """SELECT count(DISTINCT s.id)
           FROM shipments s
           JOIN delivery_attempts da ON da.shipment_id=s.id AND da.outcome='failed'
           WHERE ("""+shipment_pred+""")
             AND NOT EXISTS(SELECT 1 FROM pod_records p WHERE p.shipment_id=s.id)"""+period_sql,
        [*shipment_args,*period_args],
    )
    pieces=_dashboard_scalar(
        con,
        "SELECT COALESCE(sum(s.pieces),0) FROM shipments s WHERE ("+shipment_pred+")"+period_sql,
        [*shipment_args,*period_args],
    )
    weight=_dashboard_scalar(
        con,
        "SELECT COALESCE(sum(s.weight),0) FROM shipments s WHERE ("+shipment_pred+")"+period_sql,
        [*shipment_args,*period_args],
    )

    previous_shipments=0
    previous_delivered=0
    if window.get("previous_start"):
        prev_sql,prev_args=_dashboard_time_filter("s.created_at",window,True)
        previous_shipments=_dashboard_scalar(
            con,
            "SELECT count(*) FROM shipments s WHERE ("+shipment_pred+")"+prev_sql,
            [*shipment_args,*prev_args],
        )
        previous_distribution=_dashboard_status_distribution(
            con,shipment_pred,shipment_args,_dashboard_previous_window(window)
        )
        previous_delivered=_dashboard_delivered_from_distribution(previous_distribution)

    avg_delivery_hours=_dashboard_scalar(
        con,
        """SELECT avg((julianday(p.verified_at)-julianday(s.created_at))*24.0)
           FROM pod_records p
           JOIN shipments s ON s.id=p.shipment_id
           WHERE ("""+shipment_pred+""") AND p.verified_at IS NOT NULL"""+
        (_dashboard_time_filter("p.verified_at",window)[0]),
        [*shipment_args,*(_dashboard_time_filter("p.verified_at",window)[1])],
    )

    finance=_dashboard_finance(con,ctx,shipment_pred,shipment_args,window)
    fleet=_dashboard_fleet(con,ctx,window)
    couriers=_dashboard_courier_performance(con,ctx,shipment_pred,shipment_args,window)
    campaigns=_dashboard_campaigns(con,ctx,window)
    branches=_dashboard_branch_performance(
        con,ctx,shipment_pred,shipment_args,window,finance is not None
    )

    route_pred,route_args=auth.sql_scope(ctx,"routes","r") if auth.allowed(ctx,"routes.read") else ("0=1",[])
    route_period_sql,route_period_args=_dashboard_time_filter("r.created_at",window)
    routes_in_period=_dashboard_scalar(
        con,
        "SELECT count(*) FROM route_runs r WHERE ("+route_pred+")"+route_period_sql,
        [*route_args,*route_period_args],
    ) if auth.allowed(ctx,"routes.read") else 0
    active_routes=_dashboard_scalar(
        con,
        """SELECT count(*) FROM route_runs r
           WHERE ("""+route_pred+""") AND r.status IN ('مجدولة','في الطريق')""",
        route_args,
    ) if auth.allowed(ctx,"routes.read") else 0

    recent=con.execute(
        shipment_query()+""" WHERE ("""+shipment_pred+""")
          ORDER BY s.id DESC LIMIT 10""",
        shipment_args,
    ).fetchall()
    recent_shipments=[]
    for row in recent:
        item=auth.scoped_shipment(ctx,row)
        recent_shipments.append({
            "id":item.get("id"),
            "awb":item.get("awb"),
            "recipient":item.get("recipient"),
            "origin":item.get("origin"),
            "destination":item.get("destination"),
            "status":item.get("status"),
            "stage":item.get("stage"),
            "payment_status":item.get("payment_status"),
            "total_fee":item.get("total_fee"),
            "created_at":item.get("created_at"),
        })

    alerts={
        "failed_delivery_open":int(failed_open or 0),
        "outstanding_invoices":int((finance or {}).get("outstanding_invoice_count",0)),
        "maintenance_in_progress":int((fleet or {}).get("maintenance_in_progress",0)),
        "maintenance_due_30d":int((fleet or {}).get("maintenance_due_30d",0)),
        "vehicle_documents_expiring_30d":int((fleet or {}).get("documents_expiring_30d",0)),
    }

    return {
        "generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period":window,
        "scope":{
            "role":ctx.get("role"),
            "global_scope":bool(ctx.get("global_scope")),
            "branch_ids":list(ctx.get("branch_ids") or []),
        },
        "kpis":{
            "shipments":int(shipments or 0),
            "shipments_growth":_dashboard_growth(shipments,previous_shipments) if window.get("previous_start") else None,
            "delivered":int(delivered or 0),
            "delivered_growth":_dashboard_growth(delivered,previous_delivered) if window.get("previous_start") else None,
            "delivery_rate":round((float(delivered or 0)/max(float(shipments or 0),1))*100,1) if shipments else 0,
            "failed_delivery_open":int(failed_open or 0),
            "pieces":int(pieces or 0),
            "weight_kg":round(float(weight or 0),2),
            "avg_delivery_hours":round(float(avg_delivery_hours or 0),1) if avg_delivery_hours else 0,
            "routes":int(routes_in_period or 0),
            "active_routes":int(active_routes or 0),
        },
        "status_distribution":status_distribution,
        "trend":_dashboard_daily_series(
            con,shipment_pred,shipment_args,window,finance is not None
        ),
        "finance":finance,
        "branches":branches,
        "couriers":couriers,
        "fleet":fleet,
        "campaigns":campaigns,
        "alerts":alerts,
        "recent_shipments":recent_shipments,
    }


def management_reports_payload(con,ctx,period="30d"):
    dashboard=executive_dashboard_payload(con,ctx,period)
    return {
        "generated_at":dashboard["generated_at"],
        "period":dashboard["period"],
        "scope":dashboard["scope"],
        "operations":{
            "kpis":dashboard["kpis"],
            "status_distribution":dashboard["status_distribution"],
            "trend":dashboard["trend"],
            "recent_shipments":dashboard["recent_shipments"],
        },
        "finance":dashboard["finance"],
        "branch_performance":dashboard["branches"],
        "courier_performance":dashboard["couriers"],
        "fleet":dashboard["fleet"],
        "campaigns":dashboard["campaigns"],
        "alerts":dashboard["alerts"],
        "exports":{
            "shipments":{
                "pdf":"/api/reports/shipments?format=pdf",
                "xlsx":"/api/reports/shipments?format=xlsx",
            }
        },
    }


# ---------------------------------------------------------------------------
# RBAC / Roles & Access Control overview
# ---------------------------------------------------------------------------

ACCESS_PERMISSION_GROUPS = {
    "shipments": (
        "shipments.read","shipments.create","shipments.edit","shipments.status",
        "shipments.assign","shipments.payment",
    ),
    "delivery": ("pod.read","pod.create"),
    "dispatch": ("routes.read","routes.manage"),
    "drivers": ("drivers.read","drivers.manage","drivers.location"),
    "fleet": ("vehicles.read","vehicles.manage"),
    "branches": ("branches.read","branches.manage"),
    "clients": ("clients.read","clients.manage"),
    "pricing": ("pricing.read","pricing.manage"),
    "campaigns": ("campaigns.read","campaigns.manage"),
    "reports": ("reports.read","stats.read"),
    "administration": ("users.manage","audit.read","demo.reset"),
}

ACCESS_ROLE_ORDER = (
    "system_admin","branch_manager","office_employee","courier","accountant","customer"
)


def access_control_overview(con,ctx):
    """Authoritative RBAC snapshot for the Human Resources / Access Center."""
    if not auth.allowed(ctx,"users.manage"):
        raise auth.AccessDenied("You do not have permission to manage user access.")

    rows=con.execute("SELECT * FROM users ORDER BY id").fetchall()
    users=[safe_user(row,con) for row in rows]
    branches=[dict(row) for row in con.execute(
        "SELECT id,code,name,city,is_active FROM branches ORDER BY city,name,id"
    ).fetchall()]

    roles=[]
    for role in ACCESS_ROLE_ORDER:
        permissions=sorted(auth.ROLE_PERMISSIONS.get(role,()))
        assigned=[item for item in users if item.get("access_role")==role]
        active=[item for item in assigned if item.get("is_active")]
        inactive=[item for item in assigned if not item.get("is_active")]

        if role=="system_admin":
            scope_mode="global"
        elif role=="courier":
            scope_mode="assigned_driver_and_branches"
        elif role=="customer":
            scope_mode="owned_customer_records"
        else:
            scope_mode="assigned_branches"

        roles.append({
            "role":role,
            "permissions":permissions,
            "permission_count":len(permissions),
            "scope_mode":scope_mode,
            "account_count":len(assigned),
            "active_account_count":len(active),
            "inactive_account_count":len(inactive),
        })

    active_users=[item for item in users if item.get("is_active")]
    inactive_users=[item for item in users if not item.get("is_active")]
    courier_users=[item for item in users if item.get("access_role")=="courier"]
    linked_couriers=[item for item in courier_users if item.get("driver_id")]
    global_admins=[item for item in users
                   if item.get("access_role")=="system_admin"
                   and item.get("global_scope") is True]
    branch_scoped=[item for item in users
                   if item.get("access_role") not in ("system_admin","customer")
                   and item.get("branch_ids")]

    permission_groups=[]
    all_permissions=set()
    for group,permissions in ACCESS_PERMISSION_GROUPS.items():
        known=[permission for permission in permissions if permission in auth.PERMISSIONS]
        all_permissions.update(known)
        permission_groups.append({"group":group,"permissions":known})

    # Preserve any future permissions that are added to authorization.py but
    # not yet assigned to a UI group.
    remaining=sorted(set(auth.PERMISSIONS)-all_permissions)
    if remaining:
        permission_groups.append({"group":"other","permissions":remaining})

    return {
        "generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "roles":roles,
        "permission_groups":permission_groups,
        "permissions":sorted(auth.PERMISSIONS),
        "users":users,
        "branches":branches,
        "summary":{
            "total_accounts":len(users),
            "active_accounts":len(active_users),
            "inactive_accounts":len(inactive_users),
            "global_admins":len(global_admins),
            "branch_scoped_accounts":len(branch_scoped),
            "courier_accounts":len(courier_users),
            "linked_couriers":len(linked_couriers),
            "active_branches":sum(1 for branch in branches if branch.get("is_active")),
        },
    }


def _pod_recipient_id_suffix_integrity(c):
    """Repair legacy blank POD ID suffixes and keep proof identity data consistent.

    Older POD UI showed a sample placeholder (4091), so operators could complete a
    proof without actually entering the last four ID digits. Existing immutable
    proofs are repaired only from the shipment's already-registered recipient ID;
    no guessed/sample value is ever written.
    """
    c.execute("""
        UPDATE pod_records
           SET recipient_id_suffix = substr(
               trim((SELECT s.recipient_id FROM shipments s WHERE s.id=pod_records.shipment_id)),
               -4
           )
         WHERE trim(COALESCE(recipient_id_suffix,''))=''
           AND EXISTS (
               SELECT 1
                 FROM shipments s
                WHERE s.id=pod_records.shipment_id
                  AND length(trim(COALESCE(s.recipient_id,'')))>=4
                  AND trim(s.recipient_id) NOT GLOB '*[^0-9]*'
           )
    """)



def _customer_shipment_pickup_link_v17(c):
    """Version 17: link customer-created shipments to operational pickup tasks.

    Existing customer shipments that are still in the created state and have no
    linked pickup request are adopted once. Delivered/in-progress historical
    shipments are never rewritten.
    """
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_pickups_shipment "
        "ON pickup_requests(shipment_id,id DESC)"
    )

    rows=c.execute(
        """SELECT s.id AS shipment_id,s.awb,s.status,s.origin,s.sender_address,
                  s.sender_name,s.sender_phone,s.pieces,s.weight,s.created_at,
                  cs.customer_user_id,ss.origin_branch_id,
                  u.display_name AS customer_name,u.mobile AS customer_mobile
           FROM customer_shipments cs
           JOIN shipments s ON s.id=cs.shipment_id
           JOIN users u ON u.id=cs.customer_user_id
           LEFT JOIN shipment_scope ss ON ss.shipment_id=s.id
           WHERE NOT EXISTS(
                 SELECT 1 FROM pickup_requests pr WHERE pr.shipment_id=s.id
           )
           ORDER BY s.id"""
    ).fetchall()

    for row in rows:
        if transitions.canonical(row["status"])!="created":
            continue
        branch_id=row["origin_branch_id"]
        address=str(row["sender_address"] or "").strip()
        if not branch_id or not address:
            continue
        branch=c.execute(
            "SELECT id FROM branches WHERE id=? AND is_active=1",
            (branch_id,)
        ).fetchone()
        if not branch:
            continue

        pickup_number="PUP-"+uuid.uuid4().hex[:10].upper()
        contact_name=str(row["sender_name"] or row["customer_name"] or "").strip()
        contact_mobile=str(row["sender_phone"] or row["customer_mobile"] or "").strip()
        pieces=max(1,min(100,int(row["pieces"] or 1)))
        weight=max(0.01,float(row["weight"] or 1))
        note=f"Auto-created from customer shipment {row['awb']}"
        created_at=row["created_at"] or datetime.now(timezone.utc).isoformat(timespec="seconds")

        cur=c.execute(
            """INSERT INTO pickup_requests(
                 pickup_number,customer_user_id,branch_id,contact_name,contact_mobile,
                 city,address,preferred_at,pieces,weight,notes,status,driver_id,
                 shipment_id,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,NULL,?,?,?,'requested',NULL,?,?,?)""",
            (
                pickup_number,row["customer_user_id"],branch_id,contact_name,
                contact_mobile,row["origin"],address,pieces,round(weight,2),note,
                row["shipment_id"],created_at,created_at
            )
        )
        c.execute(
            """INSERT INTO pickup_request_events(
                 pickup_request_id,status,actor_user_id,actor_name,note,created_at
               ) VALUES(?,'requested',?,?,?,?)""",
            (
                cur.lastrowid,row["customer_user_id"],contact_name,
                note,created_at
            )
        )


def _pickup_completion_shipment_receipt_v18(c):
    """Adopt completed linked pickups whose shipments are still at Created.

    Completion means the parcel has physically reached the pickup/origin office.
    Shipments that have already progressed beyond Created are never moved backward.
    """
    rows=c.execute(
        """SELECT pr.id AS pickup_id,pr.pickup_number,pr.shipment_id,pr.branch_id,
                  s.awb,s.status,s.stage,b.name AS branch_name,b.city AS branch_city
           FROM pickup_requests pr
           JOIN shipments s ON s.id=pr.shipment_id
           LEFT JOIN branches b ON b.id=pr.branch_id
           WHERE pr.status='completed' AND pr.shipment_id IS NOT NULL
           ORDER BY pr.id"""
    ).fetchall()
    received_status=transitions.storage_status('received')
    received_stage=transitions.STATUS_STAGES['received']
    for row in rows:
        if transitions.canonical(row['status'])!='created':
            continue
        location=str(row['branch_name'] or row['branch_city'] or 'Origin Office').strip()
        c.execute(
            """UPDATE shipments
               SET status=?,stage=?,updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (received_status,received_stage,row['shipment_id'])
        )
        exists=c.execute(
            """SELECT 1 FROM shipment_events
               WHERE shipment_id=? AND status=? AND stage=?
               ORDER BY id DESC LIMIT 1""",
            (row['shipment_id'],received_status,received_stage)
        ).fetchone()
        if not exists:
            add_shipment_event(
                c,row['shipment_id'],received_status,received_stage,
                location,'System Migration'
            )


def _invoice_customer_ownership_integrity_v19(c):
    """Repair invoice/payment ownership from the shipment's customer link."""
    mismatches=c.execute(
        """SELECT i.id AS invoice_id,i.shipment_id,i.customer_user_id AS invoice_owner,
                  cs.customer_user_id AS shipment_owner
           FROM invoices i
           JOIN customer_shipments cs ON cs.shipment_id=i.shipment_id
           WHERE i.customer_user_id<>cs.customer_user_id"""
    ).fetchall()
    for row in mismatches:
        c.execute(
            """UPDATE invoices
               SET customer_user_id=?,updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (row["shipment_owner"],row["invoice_id"])
        )
        c.execute(
            "UPDATE payments SET customer_user_id=? WHERE invoice_id=?",
            (row["shipment_owner"],row["invoice_id"])
        )
    c.execute(
        """UPDATE payments
           SET customer_user_id=(
               SELECT i.customer_user_id FROM invoices i WHERE i.id=payments.invoice_id
           )
           WHERE EXISTS(
               SELECT 1 FROM invoices i
               WHERE i.id=payments.invoice_id
                 AND i.customer_user_id<>payments.customer_user_id
           )"""
    )



def _route_notification_integrity_v20(c):
    """Harden route departure notifications against exact duplicate rows.

    One physical row per branch is intentional because each branch can have its
    own SMS/in-app delivery state. Exact duplicates for the same route+branch+
    due time+message are merged here.
    """
    has_reads = c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='route_notification_reads'"
    ).fetchone() is not None

    groups = c.execute(
        """SELECT route_id,branch_id,message,due_at,MIN(id) AS keep_id,COUNT(*) AS row_count
           FROM branch_notifications
           GROUP BY route_id,branch_id,message,due_at
           HAVING COUNT(*)>1"""
    ).fetchall()

    for group in groups:
        keep_id = int(group["keep_id"])
        duplicate_rows = c.execute(
            """SELECT id,sent_at,delivery
               FROM branch_notifications
               WHERE route_id=? AND branch_id IS ? AND message=? AND due_at=?
               ORDER BY id""",
            (group["route_id"], group["branch_id"], group["message"], group["due_at"])
        ).fetchall()

        ids = [int(row["id"]) for row in duplicate_rows]
        duplicate_ids = [item_id for item_id in ids if item_id != keep_id]

        deliveries = {str(row["delivery"] or "pending") for row in duplicate_rows}
        if "sent" in deliveries:
            merged_delivery = "sent"
        elif "demo" in deliveries:
            merged_delivery = "demo"
        elif "in_app" in deliveries:
            merged_delivery = "in_app"
        elif "failed" in deliveries:
            merged_delivery = "failed"
        else:
            merged_delivery = "pending"

        sent_values = [row["sent_at"] for row in duplicate_rows if row["sent_at"]]
        merged_sent_at = max(sent_values) if sent_values else None
        c.execute(
            """UPDATE branch_notifications
               SET sent_at=COALESCE(?,sent_at),delivery=?
               WHERE id=?""",
            (merged_sent_at, merged_delivery, keep_id)
        )

        if has_reads:
            for duplicate_id in duplicate_ids:
                c.execute(
                    """INSERT INTO route_notification_reads(notification_id,user_id,read_at)
                       SELECT ?,user_id,read_at
                       FROM route_notification_reads
                       WHERE notification_id=?
                       ON CONFLICT(notification_id,user_id)
                       DO UPDATE SET read_at=MAX(route_notification_reads.read_at,excluded.read_at)""",
                    (keep_id, duplicate_id)
                )

        for duplicate_id in duplicate_ids:
            c.execute("DELETE FROM branch_notifications WHERE id=?", (duplicate_id,))

    c.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_branch_notifications_exact_event
           ON branch_notifications(
             route_id,
             IFNULL(branch_id,-1),
             due_at,
             message
           )"""
    )


def _jazan_branch_manager_login_v22(c):
    """Create one dedicated Jazan branch manager test login on existing databases."""
    branch=c.execute("SELECT id FROM branches WHERE code='JAZ-MAIN' AND is_active=1").fetchone()
    if not branch:
        return
    username="jazan.manager@ghazala.sa"
    row=c.execute("SELECT id FROM users WHERE lower(username)=lower(?)",(username,)).fetchone()
    if row:
        user_id=row["id"]
    else:
        cur=c.execute("""INSERT INTO users(username,display_name,role,password_hash,is_active)
                         VALUES(?,?,?,?,1)""",
                      (username,"Jazan Branch Manager","manager",password_hash("GhazalaJazan2026!")))
        user_id=cur.lastrowid
    foundation_schema_setter=getattr(__import__("foundation_schema"),"set_user_access")
    foundation_schema_setter(c,user_id,"branch_manager",[branch["id"]],branch["id"],False)


def _jeddah_hq_master_admin_v23(c):
    """Make the existing system administrator the global Jeddah HQ master admin."""
    hq=c.execute("SELECT id FROM branches WHERE code='JED-MAIN' ORDER BY id LIMIT 1").fetchone()
    if not hq:
        return
    admin_rows=c.execute("""SELECT u.id FROM users u
        JOIN user_access a ON a.user_id=u.id
        WHERE a.role='system_admin' AND u.is_active=1
        ORDER BY u.id""").fetchall()
    for row in admin_rows:
        user_id=row["id"]
        c.execute("""UPDATE user_access
            SET primary_branch_id=?,global_scope=1
            WHERE user_id=? AND role='system_admin'""",(hq["id"],user_id))
        c.execute("""INSERT INTO user_branches(user_id,branch_id,is_primary)
            VALUES(?,?,1)
            ON CONFLICT(user_id,branch_id) DO UPDATE SET is_primary=1""",
            (user_id,hq["id"]))
        c.execute("UPDATE user_branches SET is_primary=0 WHERE user_id=? AND branch_id<>?",
                  (user_id,hq["id"]))



def _shipment_branch_handoff_v24(c):
    """Simple shipment-level branch handoff, independent of route manifests."""
    c.execute("""CREATE TABLE IF NOT EXISTS shipment_branch_handoffs (
        shipment_id INTEGER PRIMARY KEY REFERENCES shipments(id) ON DELETE CASCADE,
        origin_branch_id INTEGER NOT NULL REFERENCES branches(id),
        destination_branch_id INTEGER NOT NULL REFERENCES branches(id),
        acknowledged_at TEXT,
        acknowledged_by INTEGER REFERENCES users(id),
        received_at TEXT,
        received_by INTEGER REFERENCES users(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""INSERT OR IGNORE INTO shipment_branch_handoffs(
        shipment_id,origin_branch_id,destination_branch_id
    )
    SELECT shipment_id,origin_branch_id,destination_branch_id
      FROM shipment_scope
     WHERE origin_branch_id IS NOT NULL AND destination_branch_id IS NOT NULL""")

def create_branch_handoff_notification(c, shipment_id, branch_id, kind, awb, destination_name):
    if not c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='operational_notifications'"
    ).fetchone():
        return None
    notification_type=f"shipment_handoff_{kind}"
    title=(
        f"Shipment {awb} acknowledged by destination branch"
        if kind=="acknowledged"
        else f"Shipment {awb} received at destination branch"
    )
    message=(
        f"{destination_name} acknowledged incoming shipment {awb}."
        if kind=="acknowledged"
        else f"{destination_name} confirmed physical receipt of shipment {awb}."
    )
    c.execute("""INSERT INTO operational_notifications(
        notification_type,shipment_id,branch_id,title,message
    ) VALUES(?,?,?,?,?)
    ON CONFLICT(notification_type,shipment_id) DO UPDATE SET
      branch_id=excluded.branch_id,title=excluded.title,message=excluded.message,
      created_at=CURRENT_TIMESTAMP""",
      (notification_type,shipment_id,branch_id,title,message))
    row=c.execute("""SELECT id FROM operational_notifications
        WHERE notification_type=? AND shipment_id=?""",
        (notification_type,shipment_id)).fetchone()
    if row:
        c.execute("DELETE FROM operational_notification_reads WHERE notification_id=?",(row["id"],))
        return row["id"]
    return None


def ensure_shipment_branch_handoff(c, shipment_id):
    scope=c.execute("""SELECT origin_branch_id,destination_branch_id
        FROM shipment_scope WHERE shipment_id=?""",(shipment_id,)).fetchone()
    if not scope or scope["origin_branch_id"] is None or scope["destination_branch_id"] is None:
        return None
    c.execute("""INSERT OR IGNORE INTO shipment_branch_handoffs(
        shipment_id,origin_branch_id,destination_branch_id
    ) VALUES(?,?,?)""",(shipment_id,scope["origin_branch_id"],scope["destination_branch_id"]))
    return c.execute("SELECT * FROM shipment_branch_handoffs WHERE shipment_id=?",(shipment_id,)).fetchone()


MIGRATIONS = (
    (1, "adopt_python_sqlite_baseline", _baseline_schema),
    (2, "persistent_bootstrap_demo_state", _persistent_demo_state),
    (3, "authorization_branch_audit_foundation", migration3),
    (4, "route_shipment_transfers", transfers.migration4),
    (5, "customer_accounts_ownership", customers.migration5),
    (6, "operational_customer_booking_notifications", _operational_notifications),
    (7, "electronic_waybills_parcel_stickers", _shipment_documents),
    (8, "repair_legacy_text_encoding", _legacy_text_encoding_cleanup),
    (9, "customer_commercial_invoices_payments_pickups", _customer_commercial_module),
    (10, "three_d_parcel_size_pricing", _three_d_pricing_sizes),
    (11, "courier_delivery_attempts_exceptions", _courier_delivery_operations),
    (12, "fleet_management_maintenance_documents", _fleet_management),
    (13, "campaigns_customer_notifications_offers", _campaign_notifications_v13),
    (14, "campaign_dispatch_duplicate_protection", _campaign_dispatch_dedupe_v14),
    (15, "pod_recipient_id_suffix_integrity", _pod_recipient_id_suffix_integrity),
    (16, "multichannel_notification_center", _notification_center_v16),
    (17, "customer_shipment_pickup_link", _customer_shipment_pickup_link_v17),
    (18, "pickup_completion_shipment_receipt", _pickup_completion_shipment_receipt_v18),
    (19, "invoice_customer_ownership_integrity", _invoice_customer_ownership_integrity_v19),
    (20, "route_notification_exact_duplicate_integrity", _route_notification_integrity_v20),
    (21, "branch_handoff_acknowledgements_whatsapp_language", transfers.migration21),
    (22, "dedicated_jazan_branch_manager_login", _jazan_branch_manager_login_v22),
    (23, "jeddah_hq_master_admin_scope", _jeddah_hq_master_admin_v23),
    (24, "shipment_level_branch_handoff", _shipment_branch_handoff_v24),
)


def _seed_pristine_demo(c):
    """Called once, only for a database with no existing application tables."""
    if c.execute("SELECT count(*) FROM branches").fetchone()[0] == 0:
        c.executemany("INSERT INTO branches(code,name,city,address,coverage) VALUES(?,?,?,?,?)", [
            ("JED-MAIN",'المقر الرئيسي جدة','جدة','جدة، المملكة العربية السعودية','جدة'),
            ("JAZ-MAIN",'مركز جازان','جازان','جازان، المملكة العربية السعودية','جميع مناطق جازان')])
    if c.execute("SELECT count(*) FROM vehicles").fetchone()[0] == 0:
        c.execute("INSERT INTO vehicles(plate,vehicle_type,capacity_kg,status) VALUES(?,?,?,?)", ('4921 ن ج ح','شاحنة نقل',1200,'متاح'))
    if c.execute("SELECT count(*) FROM clients").fetchone()[0] == 0:
        c.executemany("""INSERT INTO clients(code,name,client_type,mobile,commercial_registration,city,status,payment_terms,credit_limit,is_demo)
          VALUES(?,?,?,?,?,?,?,?,?,1)""", [
            ("CL-88924",'متجر الإلكترونيات الخليج',"company","+966 55 100 8892","1010884928",'جدة','نشط','شهري',31550),
            ("CL-74108",'شركة نسيج الفخامة للتجارة',"company","+966 55 100 7410","1010887410",'جدة','نشط','شهري',14250),
            ("CL-62004",'مؤسسة الدواء العالمي الطبية',"company","+966 55 100 6200","1010886200",'جازان','يحتاج تجديد','حسب الاتفاق',89000),
            ("CL-31018",'مجموعة الأندلس',"company","+966 55 100 3101","1010883101",'جازان','نشط','حسب الاتفاق',0)])
    if c.execute("SELECT count(*) FROM campaigns").fetchone()[0] == 0:
        c.executemany("""INSERT INTO campaigns(code,name,campaign_type,status,discount_percent,channels,target_segment,message,is_demo)
          VALUES(?,?,?,?,?,?,?,?,1)""", [
            ("GHZ20",'خصم 20% على الشحن السريع','خصم','نشطة',20,'التطبيق، الرسائل القصيرة','جميع العملاء','خصم 20% على الشحن بين جدة وجازان.'),
            ("B2B2026",'عرض موسم التجارة الإلكترونية','قسيمة','مجدولة',15,'البريد الإلكتروني','عملاء الشركات','عرض خاص على الشحن التجاري.'),
            ("SCHOOL10",'حملة العودة للمدارس','خصم','مسودة',10,'التطبيق','الأفراد','خصم موسمي على شحن الطرود.')])
    if c.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
        for username, name, role, password in DEMO_USERS:
            c.execute("INSERT INTO users(username,display_name,role,password_hash) VALUES(?,?,?,?)", (username,name,role,password_hash(password)))
    if c.execute("SELECT count(*) FROM drivers").fetchone()[0] == 0:
        for row in SEED_DRIVERS:
            c.execute("INSERT INTO drivers(name,national_id,mobile,branch,status,location_text,latitude,longitude,is_demo) VALUES(?,?,?,?,?,?,?,?,1)", row)
    if c.execute("SELECT count(*) FROM shipments").fetchone()[0] == 0:
        drivers = c.execute("SELECT id FROM drivers ORDER BY id").fetchall()
        for i, row in enumerate(SEED_SHIPMENTS):
            c.execute("""INSERT INTO shipments(awb,recipient,phone,origin,destination,status,stage,cod,eta,
              sender_name,sender_id,sender_phone,recipient_id,driver_id,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
              (*row, 'مؤسسة تجريبية للشحن', "0000000000", "+966 50 000 0000", "0000000000", drivers[i % len(drivers)][0] if drivers else None))
    c.execute("INSERT INTO shipment_events(shipment_id,status,stage,location,actor,created_at)\n      SELECT s.id,s.status,s.stage,COALESCE(d.location_text,s.origin),'النظام',COALESCE(s.updated_at,s.created_at,CURRENT_TIMESTAMP)\n      FROM shipments s LEFT JOIN drivers d ON d.id=s.driver_id\n      WHERE NOT EXISTS (SELECT 1 FROM shipment_events e WHERE e.shipment_id=s.id)")


def init_db():
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        existing = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        pristine = not existing
        apply_migrations(c, MIGRATIONS)
        disabled = c.execute("SELECT value FROM app_settings WHERE key='demo_data_disabled'").fetchone()
        if pristine and (not disabled or disabled["value"] != "1"):
            _seed_pristine_demo(c)
            adopt_seed_scope(c)
            c.execute("UPDATE app_settings SET value='demo_seeded',updated_at=CURRENT_TIMESTAMP WHERE key='bootstrap_mode'")
        # Existing databases are adopted as-is. Empty tables never trigger seeds.
        # Future schema changes belong in a new migration, never startup updates.


def safe_user(row, con):
    return accounts.safe_user(con,row)

def shipment_query():
    return """SELECT s.*,
      (SELECT ss.origin_branch_id FROM shipment_scope ss WHERE ss.shipment_id=s.id) AS origin_branch_id,
      (SELECT ss.destination_branch_id FROM shipment_scope ss WHERE ss.shipment_id=s.id) AS destination_branch_id,
      cs.customer_user_id,cu.display_name AS customer_account_name,
      cu.username AS customer_account_username,cu.mobile AS customer_account_mobile,
      d.name AS driver_name,d.national_id AS driver_national_id,d.mobile AS driver_mobile,d.location_text AS driver_location,
      d.latitude AS driver_latitude,d.longitude AS driver_longitude,d.updated_at AS driver_location_updated,
      CASE
        WHEN s.status IN ('تم إنشاء الشحنة','تم استلام الشحنة','تم الاستلام في المكتب','في مكتب الإرسال','تم الترحيل للنقل')
          THEN s.origin
        WHEN s.status IN ('جاهز للتسليم','في الفرع','قيد التوصيل','تم الاستلام','تم التسليم')
          THEN s.destination
        WHEN s.status IN ('قيد النقل','في الطريق')
          THEN COALESCE(
            NULLIF(TRIM(d.location_text),''),
            (SELECT e.location FROM shipment_events e
             WHERE e.shipment_id=s.id AND trim(COALESCE(e.location,''))<>''
             ORDER BY e.id DESC LIMIT 1),
            s.origin
          )
        ELSE COALESCE(
          (SELECT e.location FROM shipment_events e
           WHERE e.shipment_id=s.id AND trim(COALESCE(e.location,''))<>''
           ORDER BY e.id DESC LIMIT 1),
          NULLIF(TRIM(d.location_text),''),
          s.origin,
          s.destination
        )
      END AS operational_location
      FROM shipments s
      LEFT JOIN customer_shipments cs ON cs.shipment_id=s.id
      LEFT JOIN users cu ON cu.id=cs.customer_user_id
      LEFT JOIN drivers d ON d.id=s.driver_id"""


def shipment_event_payload(shipment, event):
    """Normalize event location for UI/history without rewriting stored history."""
    item=dict(event)
    canonical=transitions.canonical(item.get("status"))
    if canonical in {"created","received","at_origin","dispatched"}:
        item["location"]=shipment["origin"]
    elif canonical in {"at_destination","out_for_delivery"}:
        item["location"]=shipment["destination"]
    elif canonical=="delivered" and not str(item.get("location") or "").strip():
        item["location"]=shipment["destination"]
    return item


def active_branch_for_city(con, city, code=None):
    """Resolve an active Ghazala office for a served city."""
    city=str(city or "").strip()
    code=str(code or "").strip().upper()
    if not city:
        return None
    if code:
        row=con.execute(
            "SELECT * FROM branches WHERE code=? AND city=? AND is_active=1 ORDER BY id LIMIT 1",
            (code,city),
        ).fetchone()
        if row:
            return row
    return con.execute(
        "SELECT * FROM branches WHERE city=? AND is_active=1 ORDER BY id LIMIT 1",
        (city,),
    ).fetchone()


def active_branch_reference(con, value):
    """Accept either a branch code or a served city for legacy-compatible forms."""
    value=str(value or "").strip()
    if not value:
        return None
    upper=value.upper()
    return con.execute(
        """SELECT * FROM branches
           WHERE is_active=1 AND (code=? OR city=?)
           ORDER BY CASE WHEN code=? THEN 0 ELSE 1 END,id
           LIMIT 1""",
        (upper,value,upper),
    ).fetchone()


def public_branch_directory(con):
    """Public-safe office directory used by website/customer city selectors."""
    rows=con.execute(
        """SELECT id,code,name,city,coverage
           FROM branches
           WHERE is_active=1
           ORDER BY city,name,id"""
    ).fetchall()
    return [dict(row) for row in rows]


def persist_shipment_offices(con, shipment_id, origin_city, destination_city, destination_code=""):
    """Persist deterministic office ownership for branch-scoped shipment access."""
    origin=active_branch_for_city(con,origin_city)
    destination=active_branch_for_city(con,destination_city,destination_code)
    if not origin or not destination:
        raise ValueError("Origin and destination must be served by active Ghazala branches.")
    con.execute(
        """INSERT INTO shipment_scope(shipment_id,origin_branch_id,destination_branch_id)
           VALUES(?,?,?)
           ON CONFLICT(shipment_id) DO UPDATE SET
             origin_branch_id=excluded.origin_branch_id,
             destination_branch_id=excluded.destination_branch_id""",
        (shipment_id,origin["id"],destination["id"]),
    )
    return origin["id"],destination["id"]


def persist_route_offices(con, route_id, origin_city, destination_city):
    """Persist deterministic office ownership for a route."""
    origin=active_branch_for_city(con,origin_city)
    destination=active_branch_for_city(con,destination_city)
    if not origin or not destination:
        raise ValueError("Route cities must be served by active Ghazala branches.")
    con.execute(
        """INSERT INTO route_scope(route_id,origin_branch_id,destination_branch_id)
           VALUES(?,?,?)
           ON CONFLICT(route_id) DO UPDATE SET
             origin_branch_id=excluded.origin_branch_id,
             destination_branch_id=excluded.destination_branch_id""",
        (route_id,origin["id"],destination["id"]),
    )
    return origin["id"],destination["id"]



def customer_business_profile(con, user):
    customers.require_customer(con,user)
    con.execute(
        "INSERT OR IGNORE INTO customer_business_profiles(user_id) VALUES(?)",
        (user["id"],)
    )
    row=con.execute(
        """SELECT bp.*,u.display_name,u.username,u.mobile,ca.address
           FROM customer_business_profiles bp
           JOIN users u ON u.id=bp.user_id
           JOIN customer_accounts ca ON ca.user_id=bp.user_id
           WHERE bp.user_id=?""",
        (user["id"],)
    ).fetchone()
    return dict(row)


def update_customer_business_profile(con, user, data, request=None):
    customers.require_customer(con,user)
    allowed={"account_type","email","company_name","commercial_registration","vat_number"}
    if not data or set(data)-allowed:
        raise ValueError("Unsupported commercial profile fields.")
    current=customer_business_profile(con,user)
    values={key:str(data.get(key,current.get(key,"")) or "").strip() for key in allowed}
    if values["account_type"] not in ("individual","company"):
        raise ValueError("Account type must be individual or company.")
    if values["email"] and not re.fullmatch(r"[^@\s]{1,120}@[^@\s]{1,120}\.[^@\s]{2,40}",values["email"]):
        raise ValueError("Enter a valid email address.")
    limits={"email":280,"company_name":200,"commercial_registration":80,"vat_number":80}
    if any(len(values[key])>limit for key,limit in limits.items()):
        raise ValueError("A commercial profile field exceeds the allowed size.")
    if values["account_type"]=="company" and not values["company_name"]:
        raise ValueError("Company name is required for a company account.")
    con.execute(
        """UPDATE customer_business_profiles
           SET account_type=?,email=?,company_name=?,commercial_registration=?,vat_number=?,
               updated_at=CURRENT_TIMESTAMP
           WHERE user_id=?""",
        (
            values["account_type"],values["email"],values["company_name"],
            values["commercial_registration"],values["vat_number"],user["id"]
        )
    )
    result=customer_business_profile(con,user)
    write_audit(
        con,auth.context(con,user),"customer.commercial_profile_updated","customer_profile",
        user["id"],before=current,after=result,request=request
    )
    return result


def _invoice_number(awb):
    return "INV-"+str(awb)


def recalculate_invoice(con, invoice_id):
    invoice=con.execute("SELECT * FROM invoices WHERE id=?",(invoice_id,)).fetchone()
    if not invoice:
        raise ValueError("Invoice not found.")
    if invoice["status"]=="void":
        return dict(invoice)
    paid=con.execute(
        """SELECT COALESCE(sum(amount),0) FROM payments
           WHERE invoice_id=? AND status='paid'""",
        (invoice_id,)
    ).fetchone()[0] or 0
    paid=max(0,float(paid))
    total=max(0,float(invoice["total_amount"] or 0))
    paid=min(paid,total)
    balance=max(0,total-paid)
    status="paid" if balance<=0.005 else ("partially_paid" if paid>0 else "issued")
    con.execute(
        """UPDATE invoices
           SET amount_paid=?,balance=?,status=?,updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (round(paid,2),round(balance,2),status,invoice_id)
    )
    return dict(con.execute("SELECT * FROM invoices WHERE id=?",(invoice_id,)).fetchone())


def invoice_customer_owner(con, shipment_id, fallback_user_id=None):
    """Return the authoritative customer owner for a shipment.

    customer_shipments is the ownership source of truth. A fallback is accepted
    only for legacy callers before a link exists.
    """
    owner=con.execute(
        "SELECT customer_user_id FROM customer_shipments WHERE shipment_id=?",
        (shipment_id,)
    ).fetchone()
    customer_user_id=owner["customer_user_id"] if owner else fallback_user_id
    if not customer_user_id or not con.execute(
        "SELECT 1 FROM customer_accounts WHERE user_id=?",(customer_user_id,)
    ).fetchone():
        raise ValueError("Customer account not found.")
    return int(customer_user_id)


def ensure_customer_invoice(con, shipment_id, customer_user_id):
    shipment=con.execute("SELECT * FROM shipments WHERE id=?",(shipment_id,)).fetchone()
    if not shipment:
        raise ValueError("Shipment not found.")
    customer_user_id=invoice_customer_owner(con,shipment_id,customer_user_id)
    subtotal=max(
        0,
        float(shipment["shipping_fee"] or 0)
        +float(shipment["cod_fee"] or 0)
        +float(shipment["insurance_fee"] or 0)
        -float(shipment["discount_amount"] or 0)
    )
    vat=max(0,float(shipment["vat_amount"] or 0))
    total=max(0,float(shipment["total_fee"] or 0))
    due_at=shipment["eta"] if shipment["payment_method"]=="cod" else shipment["created_at"]
    con.execute(
        """INSERT INTO invoices(
             invoice_number,shipment_id,customer_user_id,subtotal,vat_amount,total_amount,
             amount_paid,balance,status,issued_at,due_at
           ) VALUES(?,?,?,?,?,?,0,?,'issued',COALESCE(?,CURRENT_TIMESTAMP),?)
           ON CONFLICT(shipment_id) DO UPDATE SET
             customer_user_id=excluded.customer_user_id,
             subtotal=excluded.subtotal,
             vat_amount=excluded.vat_amount,
             total_amount=excluded.total_amount,
             balance=CASE
               WHEN invoices.status='paid' THEN 0
               ELSE MAX(0,excluded.total_amount-invoices.amount_paid)
             END,
             due_at=excluded.due_at,
             updated_at=CURRENT_TIMESTAMP""",
        (
            _invoice_number(shipment["awb"]),shipment_id,customer_user_id,
            round(subtotal,2),round(vat,2),round(total,2),round(total,2),
            shipment["created_at"],due_at
        )
    )
    row=con.execute("SELECT id FROM invoices WHERE shipment_id=?",(shipment_id,)).fetchone()
    return recalculate_invoice(con,row["id"])


def invoice_payload(row):
    item=dict(row)
    item["customer_account_name"]=item.get("customer_name") or ""
    item["billing_company_name"]=item.get("company_name") or ""
    item["pdf_url"]=f'/api/invoices/{item["invoice_number"]}/pdf'
    return item


def customer_invoice_rows(con, user, invoice_number=None):
    customers.require_customer(con,user)
    sql="""SELECT i.*,s.awb,s.payment_method,s.payment_status,
                  s.origin,s.destination,s.created_at AS shipment_created_at,
                  s.shipping_fee,s.cod_fee,s.insurance_fee,
                  u.display_name AS customer_name,u.mobile AS customer_mobile,
                  bp.account_type,bp.email,bp.company_name,
                  bp.commercial_registration,bp.vat_number
           FROM invoices i
           JOIN shipments s ON s.id=i.shipment_id
           JOIN users u ON u.id=i.customer_user_id
           LEFT JOIN customer_business_profiles bp ON bp.user_id=i.customer_user_id
           WHERE i.customer_user_id=?"""
    args=[user["id"]]
    if invoice_number:
        sql+=" AND i.invoice_number=?"
        args.append(invoice_number)
    sql+=" ORDER BY i.id DESC"
    rows=[invoice_payload(row) for row in con.execute(sql,args).fetchall()]
    if invoice_number:
        if not rows:
            raise ValueError("Invoice not found.")
        return rows[0]
    return rows


def staff_invoice_rows(con, ctx, invoice_number=None):
    if not auth.allowed(ctx,"shipments.payment"):
        raise auth.AccessDenied("You do not have permission to access invoices.")
    pred,args=auth.sql_scope(ctx,"shipments","s")
    sql="""SELECT i.*,s.awb,s.payment_method,s.payment_status,
                  s.origin,s.destination,s.created_at AS shipment_created_at,
                  s.shipping_fee,s.cod_fee,s.insurance_fee,
                  u.display_name AS customer_name,u.mobile AS customer_mobile,
                  bp.account_type,bp.email,bp.company_name,
                  bp.commercial_registration,bp.vat_number
           FROM invoices i
           JOIN shipments s ON s.id=i.shipment_id
           JOIN users u ON u.id=i.customer_user_id
           LEFT JOIN customer_business_profiles bp ON bp.user_id=i.customer_user_id
           WHERE ("""+pred+")"
    params=list(args)
    if invoice_number:
        sql+=" AND i.invoice_number=?"
        params.append(invoice_number)
    sql+=" ORDER BY i.id DESC"
    rows=[invoice_payload(row) for row in con.execute(sql,params).fetchall()]
    if invoice_number:
        if not rows:
            raise ValueError("Invoice not found.")
        return rows[0]
    return rows


def customer_payment_rows(con, user):
    customers.require_customer(con,user)
    rows=con.execute(
        """SELECT p.*,i.invoice_number,s.awb
           FROM payments p
           JOIN invoices i ON i.id=p.invoice_id
           JOIN shipments s ON s.id=i.shipment_id
           WHERE p.customer_user_id=?
           ORDER BY p.id DESC""",
        (user["id"],)
    ).fetchall()
    return [dict(row) for row in rows]


def staff_payment_rows(con, ctx):
    if not auth.allowed(ctx,"shipments.payment"):
        raise auth.AccessDenied("You do not have permission to access payments.")
    pred,args=auth.sql_scope(ctx,"shipments","s")
    rows=con.execute(
        """SELECT p.*,i.invoice_number,s.awb,u.display_name AS customer_name
           FROM payments p
           JOIN invoices i ON i.id=p.invoice_id
           JOIN shipments s ON s.id=i.shipment_id
           JOIN users u ON u.id=p.customer_user_id
           WHERE ("""+pred+""")
           ORDER BY p.id DESC""",
        args
    ).fetchall()
    return [dict(row) for row in rows]


def _pickup_scope(con, ctx, alias="pr"):
    if ctx.get("role")=="system_admin" and ctx.get("global_scope"):
        return "1=1",[]
    branch_ids=tuple(ctx.get("branch_ids") or ())
    if not branch_ids:
        return "0=1",[]
    marks=",".join("?" for _ in branch_ids)
    return f"{alias}.branch_id IN ({marks})",list(branch_ids)


def pickup_payload(row):
    return dict(row)


def customer_pickup_rows(con, user, pickup_number=None):
    customers.require_customer(con,user)
    sql="""SELECT pr.*,b.code AS branch_code,b.name AS branch_name,
                  d.name AS driver_name,d.mobile AS driver_mobile,
                  s.awb
           FROM pickup_requests pr
           JOIN branches b ON b.id=pr.branch_id
           LEFT JOIN drivers d ON d.id=pr.driver_id
           LEFT JOIN shipments s ON s.id=pr.shipment_id
           WHERE pr.customer_user_id=?"""
    args=[user["id"]]
    if pickup_number:
        sql+=" AND pr.pickup_number=?"
        args.append(pickup_number)
    sql+=" ORDER BY pr.id DESC"
    rows=[pickup_payload(row) for row in con.execute(sql,args).fetchall()]
    if pickup_number:
        if not rows:
            raise ValueError("Pickup request not found.")
        return rows[0]
    return rows


def staff_pickup_rows(con, ctx, pickup_number=None):
    if ctx.get("role") not in ("system_admin","branch_manager","office_employee"):
        raise auth.AccessDenied("You do not have permission to access pickup requests.")
    pred,args=_pickup_scope(con,ctx,"pr")
    sql="""SELECT pr.*,b.code AS branch_code,b.name AS branch_name,
                  d.name AS driver_name,d.mobile AS driver_mobile,
                  s.awb,u.display_name AS customer_name,u.mobile AS customer_mobile
           FROM pickup_requests pr
           JOIN branches b ON b.id=pr.branch_id
           JOIN users u ON u.id=pr.customer_user_id
           LEFT JOIN drivers d ON d.id=pr.driver_id
           LEFT JOIN shipments s ON s.id=pr.shipment_id
           WHERE ("""+pred+")"
    params=list(args)
    if pickup_number:
        sql+=" AND pr.pickup_number=?"
        params.append(pickup_number)
    sql+=" ORDER BY pr.id DESC"
    rows=[pickup_payload(row) for row in con.execute(sql,params).fetchall()]
    if pickup_number:
        if not rows:
            raise ValueError("Pickup request not found.")
        return rows[0]
    return rows


DELIVERY_FAILURE_REASONS={
    "no_answer":{"en":"No answer","ar":"لا يوجد رد"},
    "recipient_unavailable":{"en":"Recipient unavailable","ar":"المستلم غير متاح"},
    "wrong_address":{"en":"Wrong or incomplete address","ar":"العنوان غير صحيح أو غير مكتمل"},
    "refused":{"en":"Recipient refused shipment","ar":"رفض المستلم الشحنة"},
    "payment_issue":{"en":"Payment or COD issue","ar":"مشكلة في الدفع أو التحصيل"},
    "access_issue":{"en":"Could not access delivery location","ar":"تعذر الوصول إلى موقع التسليم"},
    "damaged":{"en":"Parcel condition issue","ar":"مشكلة في حالة الطرد"},
    "other":{"en":"Other","ar":"سبب آخر"},
}


def delivery_failure_reason_payload():
    return [
        {"code":code,"label_en":labels["en"],"label_ar":labels["ar"]}
        for code,labels in DELIVERY_FAILURE_REASONS.items()
    ]


def delivery_attempt_payload(row):
    item=dict(row)
    item["has_photo"]=bool(item.pop("has_photo",0))
    return item


def delivery_attempt_rows(con, shipment_id):
    rows=con.execute(
        """SELECT da.id,da.shipment_id,da.driver_id,da.attempt_number,da.outcome,
                  da.failure_reason_code,da.failure_reason_text,da.recipient_name,da.note,
                  da.latitude,da.longitude,da.location_text,
                  CASE WHEN da.photo_data IS NULL THEN 0 ELSE 1 END AS has_photo,
                  da.photo_mime,da.next_attempt_at,da.started_at,da.completed_at,
                  da.created_by_user_id,da.completed_by_user_id,
                  da.created_by_name,da.completed_by_name,da.created_at,da.updated_at,
                  d.name AS driver_name,d.mobile AS driver_mobile
           FROM delivery_attempts da
           LEFT JOIN drivers d ON d.id=da.driver_id
           WHERE da.shipment_id=?
           ORDER BY da.attempt_number DESC,da.id DESC""",
        (shipment_id,)
    ).fetchall()
    return [delivery_attempt_payload(row) for row in rows]


def _delivery_open_attempt(con, shipment_id):
    return con.execute(
        """SELECT * FROM delivery_attempts
           WHERE shipment_id=? AND outcome='in_progress'
           ORDER BY attempt_number DESC,id DESC LIMIT 1""",
        (shipment_id,)
    ).fetchone()


def _next_delivery_attempt_number(con, shipment_id):
    return int(con.execute(
        "SELECT COALESCE(MAX(attempt_number),0)+1 FROM delivery_attempts WHERE shipment_id=?",
        (shipment_id,)
    ).fetchone()[0])


def _courier_shipment_for_action(con, ctx, awb):
    if ctx.get("role") not in ("system_admin","branch_manager","office_employee","courier"):
        raise auth.AccessDenied("You do not have permission to manage courier delivery tasks.")
    if not auth.allowed(ctx,"shipments.status"):
        raise auth.AccessDenied("You do not have permission to update shipment delivery status.")
    shipment=policy.object_row(con,ctx,"shipments",str(awb).upper(),"awb")
    if not shipment["driver_id"]:
        raise ValueError("Assign a courier before starting a delivery attempt.")
    if ctx.get("role")=="courier" and shipment["driver_id"] not in tuple(ctx.get("courier_driver_ids") or ()):
        raise auth.AccessDenied("This shipment is not assigned to your courier account.")
    return shipment


def courier_delivery_tasks(con, ctx, include_completed=False):
    if ctx.get("role") not in ("system_admin","branch_manager","office_employee","courier"):
        raise auth.AccessDenied("You do not have permission to access courier tasks.")
    if not auth.allowed(ctx,"shipments.read"):
        raise auth.AccessDenied("You do not have permission to access courier tasks.")
    pred,args=auth.sql_scope(ctx,"shipments","s")
    rows=con.execute(
        shipment_query()+" WHERE ("+pred+") AND s.driver_id IS NOT NULL ORDER BY s.id DESC",
        args
    ).fetchall()
    result=[]
    for row in rows:
        if not include_completed and transitions.canonical(row["status"])=="delivered":
            continue
        item=auth.scoped_shipment(ctx,row)
        attempts=delivery_attempt_rows(con,row["id"])
        item["attempt_count"]=max((int(a["attempt_number"]) for a in attempts),default=0)
        item["failed_attempts"]=sum(1 for a in attempts if a["outcome"]=="failed")
        item["active_attempt"]=next((a for a in attempts if a["outcome"]=="in_progress"),None)
        item["last_attempt"]=attempts[0] if attempts else None
        item["pod_complete"]=bool(con.execute(
            "SELECT 1 FROM pod_records WHERE shipment_id=?",(row["id"],)
        ).fetchone())
        result.append(item)
    return result


def courier_pickup_tasks(con, ctx, include_completed=False):
    role=ctx.get("role")
    args=[]
    if role=="courier":
        driver_ids=tuple(ctx.get("courier_driver_ids") or ())
        if not driver_ids:
            return []
        marks=",".join("?" for _ in driver_ids)
        pred=f"pr.driver_id IN ({marks})"
        args=list(driver_ids)
    elif role in ("system_admin","branch_manager","office_employee"):
        pred,args=_pickup_scope(con,ctx,"pr")
    else:
        raise auth.AccessDenied("You do not have permission to access courier pickup tasks.")
    if not include_completed:
        pred=f"({pred}) AND pr.status NOT IN ('completed','cancelled')"
    rows=con.execute(
        """SELECT pr.*,b.code AS branch_code,b.name AS branch_name,
                  d.name AS driver_name,d.mobile AS driver_mobile,
                  s.awb,u.display_name AS customer_name,u.mobile AS customer_mobile
           FROM pickup_requests pr
           JOIN branches b ON b.id=pr.branch_id
           JOIN users u ON u.id=pr.customer_user_id
           LEFT JOIN drivers d ON d.id=pr.driver_id
           LEFT JOIN shipments s ON s.id=pr.shipment_id
           WHERE """+pred+" ORDER BY pr.id DESC",
        args
    ).fetchall()
    return [dict(row) for row in rows]


def courier_pickup_task(con, ctx, pickup_number):
    rows=courier_pickup_tasks(con,ctx,include_completed=True)
    row=next((item for item in rows if item["pickup_number"]==str(pickup_number).upper()),None)
    if not row:
        raise ValueError("Pickup request not found.")
    return row


def _normalize_next_attempt(value):
    value=str(value or "").strip()
    if not value:
        return None
    try:
        date=datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid next-attempt date and time.") from None
    if date.tzinfo is None:
        date=date.astimezone()
    return date.isoformat(timespec="minutes")


def generate_invoice_pdf(invoice, payments):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
    except ImportError as exc:
        raise ImportError("Install reportlab to generate invoice PDFs.") from exc

    out=io.BytesIO()
    pdf=canvas.Canvas(out,pagesize=A4)
    page_w,page_h=A4
    font=_pdf_font_name()
    pdf.setTitle(f'Ghazala Invoice {invoice["invoice_number"]}')
    _draw_pdf_logo(pdf,18*mm,page_h-33*mm,18*mm,18*mm)
    pdf.setFont(font,17)
    pdf.drawString(42*mm,page_h-20*mm,"GHAZALA TRANSPORT")
    pdf.setFont(font,9)
    pdf.drawString(42*mm,page_h-26*mm,"Customer Invoice")
    pdf.setFont(font,12)
    pdf.drawRightString(page_w-18*mm,page_h-20*mm,_pdf_display(invoice["invoice_number"]))
    pdf.setFont(font,9)
    pdf.drawRightString(page_w-18*mm,page_h-26*mm,_pdf_display(invoice["awb"]))
    pdf.line(18*mm,page_h-36*mm,page_w-18*mm,page_h-36*mm)

    def row(label,value,y,bold=False):
        pdf.setFont(font,8)
        pdf.drawString(18*mm,y,label)
        pdf.setFont(font,11 if bold else 9)
        pdf.drawRightString(page_w-18*mm,y,_pdf_display(value))
        return y-7*mm

    y=page_h-49*mm
    billed_to=invoice.get("company_name") or invoice.get("customer_name") or ""
    y=row("Billed to",billed_to,y,True)
    if invoice.get("email"):
        y=row("Email",invoice.get("email"),y)
    y=row("Shipment",invoice.get("awb"),y)
    y=row("Route",f'{invoice.get("origin") or ""} -> {invoice.get("destination") or ""}',y)
    y=row("Issued",invoice.get("issued_at"),y)
    y=row("Due",invoice.get("due_at") or "On delivery",y)
    y-=3*mm
    pdf.line(18*mm,y,page_w-18*mm,y)
    y-=8*mm
    y=row("Shipping / service subtotal",f'{float(invoice.get("subtotal") or 0):.2f} SAR',y)
    y=row("VAT",f'{float(invoice.get("vat_amount") or 0):.2f} SAR',y)
    y=row("Invoice total",f'{float(invoice.get("total_amount") or 0):.2f} SAR',y,True)
    y=row("Paid",f'{float(invoice.get("amount_paid") or 0):.2f} SAR',y)
    y=row("Balance",f'{float(invoice.get("balance") or 0):.2f} SAR',y,True)
    y=row("Status",str(invoice.get("status") or "").replace("_"," ").title(),y)

    y-=8*mm
    pdf.setFont(font,10)
    pdf.drawString(18*mm,y,"Payment history")
    y-=6*mm
    pdf.setFont(font,8)
    if payments:
        for payment in payments[:12]:
            label=f'{payment.get("payment_number")} · {payment.get("method")} · {payment.get("paid_at") or payment.get("created_at")}'
            pdf.drawString(18*mm,y,_pdf_display(label)[:85])
            pdf.drawRightString(page_w-18*mm,y,f'{float(payment.get("amount") or 0):.2f} SAR')
            y-=6*mm
    else:
        pdf.drawString(18*mm,y,"No recorded payments.")
    pdf.setFont(font,7)
    pdf.drawString(18*mm,14*mm,"Generated by GHAZALA TRANSPORT")
    pdf.save()
    return out.getvalue()



def ensure_shipment_documents(con, shipment_id, issued_by_user_id=None):
    """Ensure one waybill and one active sticker per current parcel."""
    shipment=con.execute(
        "SELECT id,awb,pieces FROM shipments WHERE id=?",
        (shipment_id,)
    ).fetchone()
    if not shipment:
        raise ValueError("Shipment not found.")

    waybill_number="WB-"+str(shipment["awb"])
    con.execute(
        """INSERT OR IGNORE INTO waybills(shipment_id,waybill_number,issued_by_user_id)
           VALUES(?,?,?)""",
        (shipment_id,waybill_number,issued_by_user_id)
    )
    if issued_by_user_id is not None:
        con.execute(
            """UPDATE waybills
               SET issued_by_user_id=COALESCE(issued_by_user_id,?)
               WHERE shipment_id=?""",
            (issued_by_user_id,shipment_id)
        )

    try:
        pieces=int(shipment["pieces"] or 1)
    except (TypeError,ValueError):
        pieces=1
    pieces=max(1,min(100,pieces))

    # Keep old sticker identities for history; only current parcel numbers stay active.
    con.execute(
        "UPDATE parcel_stickers SET is_active=0 WHERE shipment_id=?",
        (shipment_id,)
    )
    for parcel_number in range(1,pieces+1):
        sticker_number=f'{shipment["awb"]}-P{parcel_number:03d}'
        con.execute(
            """INSERT INTO parcel_stickers(
                 shipment_id,parcel_number,total_parcels,sticker_number,is_active
               ) VALUES(?,?,?,?,1)
               ON CONFLICT(shipment_id,parcel_number) DO UPDATE SET
                 total_parcels=excluded.total_parcels,
                 sticker_number=excluded.sticker_number,
                 is_active=1""",
            (shipment_id,parcel_number,pieces,sticker_number)
        )

    waybill=dict(con.execute(
        "SELECT * FROM waybills WHERE shipment_id=?",(shipment_id,)
    ).fetchone())
    stickers=[dict(row) for row in con.execute(
        """SELECT * FROM parcel_stickers
           WHERE shipment_id=? AND is_active=1
           ORDER BY parcel_number""",
        (shipment_id,)
    ).fetchall()]
    return {"waybill":waybill,"stickers":stickers}


def shipment_document_context(con, shipment_id):
    row=con.execute(
        shipment_query()+""" WHERE s.id=?""",
        (shipment_id,)
    ).fetchone()
    if not row:
        raise ValueError("Shipment not found.")
    result=dict(row)
    offices=con.execute(
        """SELECT bo.name AS origin_office,bo.code AS origin_office_code,
                  bd.name AS destination_office,bd.code AS destination_office_code
           FROM shipment_scope ss
           LEFT JOIN branches bo ON bo.id=ss.origin_branch_id
           LEFT JOIN branches bd ON bd.id=ss.destination_branch_id
           WHERE ss.shipment_id=?""",
        (shipment_id,)
    ).fetchone()
    if offices:
        result.update(dict(offices))
    else:
        result.update({
            "origin_office":"",
            "origin_office_code":"",
            "destination_office":"",
            "destination_office_code":"",
        })
    return result


def shipment_document_links(awb, customer=False):
    base=f"/api/customer/shipments/{awb}" if customer else f"/api/shipments/{awb}"
    return {
        "documents":base+"/documents",
        "waybill":base+"/waybill",
        "waybill_pdf":base+"/waybill/pdf",
        "stickers":base+"/stickers",
        "stickers_pdf":base+"/stickers/pdf",
    }


def shipment_document_payload(con, shipment_id, tracking_url, customer=False):
    shipment=shipment_document_context(con,shipment_id)
    docs=ensure_shipment_documents(con,shipment_id)
    awb=shipment["awb"]
    return {
        "shipment":{
            key:shipment.get(key) for key in (
                "id","awb","sender_name","sender_phone","sender_address",
                "recipient","phone","recipient_address","recipient_branch",
                "origin","destination","package_type","package_description",
                "pieces","weight","length_cm","width_cm","height_cm",
                "pricing_size_code","pricing_size_fee",
                "declared_value","shipping_fee","total_fee","payment_method",
                "payment_status","driver_name","created_at",
                "origin_office","origin_office_code",
                "destination_office","destination_office_code"
            )
        },
        "waybill":docs["waybill"],
        "stickers":docs["stickers"],
        "tracking_url":tracking_url,
        "links":shipment_document_links(awb,customer),
    }


def record_shipment_document_event(
    con, shipment_id, event_type, user=None, waybill_id=None, sticker_id=None,
    metadata=None, request=None
):
    actor_id=user.get("id") if isinstance(user,dict) else None
    actor_name=str(user.get("display_name") or "") if isinstance(user,dict) else ""
    raw=json.dumps(metadata or {},ensure_ascii=False,separators=(",",":"))
    con.execute(
        """INSERT INTO shipment_document_events(
             shipment_id,waybill_id,sticker_id,event_type,
             actor_user_id,actor_name,metadata_json
           ) VALUES(?,?,?,?,?,?,?)""",
        (shipment_id,waybill_id,sticker_id,event_type,actor_id,actor_name,raw)
    )
    if user:
        try:
            write_audit(
                con,auth.context(con,user),event_type,"shipment_document",shipment_id,
                metadata=metadata or {},request=request
            )
        except Exception:
            # Document-event history is still authoritative if the generic
            # audit helper rejects a future/unknown event name.
            pass


def _pdf_font_name():
    """Use an installed Unicode font with Arabic glyphs on Windows/Linux/macOS."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        name="GhazalaUnicode"
        if name in pdfmetrics.getRegisteredFontNames():
            return name

        windir=os.environ.get("WINDIR","C:\\Windows")
        candidates=(
            # Windows fonts commonly present on Windows 10/11.
            str(Path(windir)/"Fonts"/"arial.ttf"),
            str(Path(windir)/"Fonts"/"tahoma.ttf"),
            str(Path(windir)/"Fonts"/"segoeui.ttf"),
            str(Path(windir)/"Fonts"/"arialuni.ttf"),
            str(Path(windir)/"Fonts"/"NotoNaskhArabic-Regular.ttf"),
            str(Path(windir)/"Fonts"/"NotoSansArabic-Regular.ttf"),
            # Linux fallbacks used by development/test environments.
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
            # Common macOS locations.
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        )
        path=next((candidate for candidate in candidates if Path(candidate).is_file()),None)
        if not path:
            return "Helvetica"
        pdfmetrics.registerFont(TTFont(name,path))
        return name
    except Exception:
        return "Helvetica"


def _pdf_display(value):
    """Shape Arabic/Urdu for ReportLab when shaping helpers are installed."""
    text=str(value or "")
    if not text:
        return "—"
    if any("\u0600"<=ch<="\u06ff" for ch in text):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            # A Unicode TTF still prevents square/black-box glyphs even when
            # optional shaping helpers are unavailable.
            return text
    return text


def _draw_pdf_logo(pdf, x, y, width=36, height=36):
    candidates=(
        ROOT/"static"/"logo.png",
        ROOT/"static"/"assets"/"logo.png",
        ROOT/"static"/"ghazala-logo.png",
        ROOT/"static"/"assets"/"ghazala-logo.png",
    )
    logo=next((path for path in candidates if path.is_file()),None)
    if logo:
        try:
            pdf.drawImage(str(logo),x,y,width=width,height=height,preserveAspectRatio=True,mask="auto")
            return
        except Exception:
            pass
    pdf.setFont("Helvetica-Bold",12)
    pdf.drawString(x,y+height/2,"GHAZALA")


def _draw_qr_pdf(pdf, value, x, y, size):
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    widget=QrCodeWidget(value)
    bounds=widget.getBounds()
    width=bounds[2]-bounds[0]
    height=bounds[3]-bounds[1]
    drawing=Drawing(size,size,transform=[
        size/width,0,0,size/height,
        -bounds[0]*size/width,-bounds[1]*size/height
    ])
    drawing.add(widget)
    renderPDF.draw(drawing,pdf,x,y)


def generate_waybill_pdf(shipment, waybill, tracking_url):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.graphics.barcode import code128
    except ImportError as exc:
        raise ImportError("Install reportlab to generate waybill PDFs.") from exc

    out=io.BytesIO()
    pdf=canvas.Canvas(out,pagesize=A4)
    page_w,page_h=A4
    font=_pdf_font_name()
    pdf.setTitle(f'Ghazala Waybill {waybill["waybill_number"]}')
    _draw_pdf_logo(pdf,18*mm,page_h-33*mm,18*mm,18*mm)
    pdf.setFont(font,17)
    pdf.drawString(42*mm,page_h-20*mm,"GHAZALA TRANSPORT")
    pdf.setFont(font,9)
    pdf.drawString(42*mm,page_h-26*mm,"Electronic Waybill")
    pdf.setFont(font,11)
    pdf.drawRightString(page_w-18*mm,page_h-20*mm,_pdf_display(waybill["waybill_number"]))
    pdf.drawRightString(page_w-18*mm,page_h-26*mm,_pdf_display(shipment["awb"]))
    pdf.line(18*mm,page_h-36*mm,page_w-18*mm,page_h-36*mm)

    def row(label,value,y):
        pdf.setFont(font,8)
        pdf.drawString(18*mm,y,label)
        pdf.setFont(font,10)
        pdf.drawString(58*mm,y,_pdf_display(value)[:90])
        return y-7*mm

    y=page_h-47*mm
    fields=(
        ("Sender",shipment.get("sender_name")),
        ("Sender mobile",shipment.get("sender_phone")),
        ("Sender address",shipment.get("sender_address")),
        ("Recipient",shipment.get("recipient")),
        ("Recipient mobile",shipment.get("phone")),
        ("Recipient address",shipment.get("recipient_address")),
        ("Origin city",shipment.get("origin")),
        ("Destination city",shipment.get("destination")),
        ("Issuing office",shipment.get("origin_office") or shipment.get("origin_office_code")),
        ("Receiving office",shipment.get("destination_office") or shipment.get("recipient_branch")),
        ("Courier",shipment.get("driver_name") or "Unassigned"),
        ("Parcels",shipment.get("pieces")),
        ("Parcel size",shipment.get("pricing_size_code") or "—"),
        ("Weight",f'{shipment.get("weight") or 0} kg'),
        ("Contents",shipment.get("package_description") or shipment.get("package_type")),
        ("Shipping value",f'{shipment.get("total_fee") or 0} SAR'),
        ("Payment status",shipment.get("payment_status")),
        ("Created",shipment.get("created_at")),
    )
    for label,value in fields:
        if y<58*mm:
            pdf.showPage()
            y=page_h-25*mm
        y=row(label,value,y)

    barcode=code128.Code128(str(shipment["awb"]),barHeight=14*mm,barWidth=.36*mm,humanReadable=True)
    barcode.drawOn(pdf,18*mm,20*mm)
    _draw_qr_pdf(pdf,tracking_url,page_w-49*mm,16*mm,30*mm)
    pdf.setFont(font,7)
    pdf.drawRightString(page_w-18*mm,11*mm,"Scan QR to track shipment")
    pdf.save()
    return out.getvalue()


def generate_stickers_pdf(shipment, stickers, tracking_url):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.graphics.barcode import code128
    except ImportError as exc:
        raise ImportError("Install reportlab to generate sticker PDFs.") from exc

    page=(100*mm,150*mm)
    out=io.BytesIO()
    pdf=canvas.Canvas(out,pagesize=page)
    font=_pdf_font_name()
    office=shipment.get("destination_office") or shipment.get("recipient_branch") or shipment.get("destination")

    for sticker in stickers:
        w,h=page
        _draw_pdf_logo(pdf,8*mm,h-27*mm,18*mm,18*mm)
        pdf.setFont(font,12)
        pdf.drawString(30*mm,h-15*mm,"GHAZALA TRANSPORT")
        pdf.setFont(font,7)
        pdf.drawString(30*mm,h-21*mm,"PARCEL LABEL")
        pdf.line(8*mm,h-31*mm,w-8*mm,h-31*mm)

        pdf.setFont(font,15)
        pdf.drawString(8*mm,h-42*mm,_pdf_display(shipment["awb"]))
        pdf.setFont(font,14)
        pdf.drawRightString(w-8*mm,h-42*mm,f'{sticker["parcel_number"]} of {sticker["total_parcels"]}')

        pdf.setFont(font,8)
        pdf.drawString(8*mm,h-54*mm,"Recipient")
        pdf.setFont(font,11)
        pdf.drawString(8*mm,h-61*mm,_pdf_display(shipment.get("recipient"))[:45])
        pdf.setFont(font,9)
        pdf.drawString(8*mm,h-68*mm,_pdf_display(shipment.get("phone"))[:45])

        pdf.setFont(font,8)
        pdf.drawString(8*mm,h-80*mm,"Destination")
        pdf.setFont(font,13)
        pdf.drawString(8*mm,h-88*mm,_pdf_display(shipment.get("destination"))[:35])
        pdf.setFont(font,9)
        pdf.drawString(8*mm,h-95*mm,_pdf_display(office)[:45])

        # Keep barcode and QR physically separated for thermal-label printing.
        barcode=code128.Code128(
            str(sticker["sticker_number"]),
            barHeight=15*mm,barWidth=.20*mm,humanReadable=True
        )
        barcode.drawOn(pdf,8*mm,28*mm)
        _draw_qr_pdf(pdf,tracking_url,w-33*mm,23*mm,25*mm)

        instruction=sticker.get("special_instructions") or shipment.get("package_description") or ""
        if instruction:
            pdf.setFont(font,7)
            pdf.drawString(8*mm,17*mm,_pdf_display(instruction)[:70])
        pdf.setFont(font,6)
        pdf.drawString(8*mm,9*mm,_pdf_display(sticker["sticker_number"]))
        pdf.showPage()

    pdf.save()
    return out.getvalue()



class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200, cookie=None):
        con=getattr(self,'_audit_con',None)
        if status<400 and con is not None and getattr(self,'_audit_pending',False):
            policy.finish_mutation(con,self.auth_ctx,self.mutation_parts,self.mutation_data,self.mutation_plan,self.mutation_before,value,self)
            self._audit_pending=False
            con.commit()  # Commit the business change and audit atomically before acknowledging it.
            if self.mutation_parts[1]=='shipments' and isinstance(value,dict) and 'recipient' in value:
                value=auth.scoped_shipment(self.auth_ctx,value)
            if self.mutation_parts[1]=='drivers' and self.auth_ctx['role']=='courier' and isinstance(value,dict):
                value=dict(value); value.pop('national_id',None)
        raw = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if getattr(self,'audit_request_id',None): self.send_header('X-Request-ID',self.audit_request_id)
        if cookie: self.send_header("Set-Cookie", cookie)
        self.end_headers(); self.wfile.write(raw)

    def send_svg(self, raw):
        self.send_response(200); self.send_header("Content-Type","image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def send_download(self, raw, mime, filename):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers(); self.wfile.write(raw)

    def tracking_url(self, awb):
        base=(os.environ.get("PUBLIC_BASE_URL") or f"http://{self.headers.get('Host','localhost:8000')}").strip().rstrip("/")
        return f"{base}/#{urlencode({'track':awb})}"

    def read_json(self):
        try: size=int(self.headers.get('Content-Length','0'))
        except ValueError: raise ValueError('Invalid JSON request.') from None
        if not 0<=size<=6_000_000: raise ValueError('Request body exceeds the size limit.')
        try: value=json.loads(self.rfile.read(size) or b'{}')
        except (ValueError,UnicodeError): raise ValueError('Invalid JSON request.') from None
        if not isinstance(value,dict): raise ValueError('Request body must be a JSON object.')
        return value

    def scope_key(self,ctx):
        return hashlib.sha256(json.dumps({k:ctx[k] for k in ('role','branch_ids','primary_branch_id','global_scope','courier_driver_ids')},sort_keys=True).encode()).hexdigest()

    def handle_api(self,callback,mutating=False):
        self._audit_con=None; self._audit_pending=False; self.audit_request_id=uuid.uuid4().hex
        try:
            if mutating and not same_origin(self.headers):
                return self.send_json({'error':'Cross-origin state changes are not allowed.'},403)
            return callback()
        except auth.AccessDenied as exc: return self.send_json({'error':str(exc) or 'You do not have permission for this action.'},403)
        except DeliveryPolicyError as exc: return self.send_json({'error':str(exc),'code':'delivery_policy'},409)
        except transfers.PendingTransferError as exc: return self.send_json({'error':str(exc),'code':'transfer_pending'},409)
        except customers.CustomerConflict as exc: return self.send_json({'error':str(exc)},409)
        except customers.CustomerShipmentNotFound as exc: return self.send_json({'error':str(exc)},404)
        except (ValueError,TypeError,OverflowError) as exc: return self.send_json({'error':str(exc) or 'Invalid request.'},400)
        except sqlite3.IntegrityError: return self.send_json({'error':'This change conflicts with existing records.'},409)
        except Exception as exc:
            print(
                f'API request failed {self.audit_request_id}: {type(exc).__name__}: {exc} '
                f'[{getattr(self,"command","?")} {getattr(self,"path","?")}]',
                flush=True
            )
            traceback.print_exc()
            return self.send_json({'error':'The request could not be completed.','request_id':self.audit_request_id},500)

    def prepare_mutation(self,con,user,method,parts,data):
        self.auth_ctx=auth.context(con,user)
        self.mutation_plan=policy.authorize_mutation(con,self.auth_ctx,method,parts,data)
        self.mutation_parts=parts; self.mutation_data=data
        self.mutation_before=policy.prepare_audit(con,parts,data,self.mutation_plan)
        self._audit_con=con; self._audit_pending=parts[1] not in ('users','password')

    def do_GET(self): return self.handle_api(self._get)
    def do_POST(self): return self.handle_api(self._post,True)
    def do_PATCH(self): return self.handle_api(self._patch,True)
    def do_DELETE(self): return self.handle_api(self._delete,True)

    def current_user(self, con):
        raw = self.headers.get("Cookie", "")
        token = next((part.strip().split("=",1)[1] for part in raw.split(";") if part.strip().startswith("ghz_session=")), "")
        if not token: return None
        row = con.execute("""SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
          WHERE s.token_hash=? AND s.expires_at>? AND u.is_active=1""", (hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
        return dict(row) if row else None

    def unauthorized(self): self.send_json({"error":'سجّل الدخول أولاً'},401)
    def forbidden(self): self.send_json({"error":'ليست لديك صلاحية لهذا الإجراء'},403)

    def do_OPTIONS(self):
        self.send_response(204); self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type"); self.end_headers()

    def _delete(self):
        url=urlparse(self.path); path=url.path; parts=[unquote(p) for p in path.split('/') if p]
        if len(parts)!=3 or parts[:2]!=['api','branches']:
            return self.send_json({'error':'Deletion is not supported for this record.'},403)
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            user=self.current_user(c)
            if not user:
                return self.unauthorized()
            ctx=auth.context(c,user)
            if ctx.get('role')!='system_admin' or ctx.get('global_scope') is not True:
                raise auth.AccessDenied('Only the Jeddah Headquarters Super Admin can permanently delete a branch.')
            try:
                length=int(self.headers.get('Content-Length','0') or 0)
            except ValueError:
                length=0
            raw=self.rfile.read(length) if length>0 else b''
            try:
                data=json.loads(raw.decode() or '{}')
            except (ValueError,UnicodeDecodeError):
                return self.send_json({'error':'Invalid delete request.'},400)
            password=str(data.get('password') or '')
            if not password or not verify_password(password,user.get('password_hash')):
                return self.send_json({'error':'Super Admin password is incorrect.','code':'password_verification_failed'},403)
            branch=c.execute('SELECT * FROM branches WHERE id=?',(parts[2],)).fetchone()
            if not branch:
                return self.send_json({'error':'Branch not found.'},404)
            if str(branch['code'] or '').upper()=='JED-MAIN':
                return self.send_json({'error':'Jeddah Headquarters is the protected master branch and cannot be deleted.','code':'master_branch_protected'},409)
            if int(branch['is_active'] or 0)!=0:
                return self.send_json({'error':'Deactivate the branch before permanent deletion.','code':'branch_must_be_inactive'},409)

            dependency_queries={
                'shipments':("""SELECT COUNT(*) FROM shipment_scope
                    WHERE origin_branch_id=? OR destination_branch_id=?""",(branch['id'],branch['id'])),
                'routes':("""SELECT COUNT(*) FROM route_scope
                    WHERE origin_branch_id=? OR destination_branch_id=?""",(branch['id'],branch['id'])),
                'users':("SELECT COUNT(*) FROM user_branches WHERE branch_id=?",(branch['id'],)),
                'drivers':("SELECT COUNT(*) FROM driver_scope WHERE branch_id=?",(branch['id'],)),
                'vehicles':("SELECT COUNT(*) FROM vehicle_branches WHERE branch_id=?",(branch['id'],)),
                'pickups':("SELECT COUNT(*) FROM pickup_requests WHERE branch_id=?",(branch['id'],)),
                'notifications':("SELECT COUNT(*) FROM branch_notifications WHERE branch_id=?",(branch['id'],)),
            }
            dependencies={}
            for key,(sql,args) in dependency_queries.items():
                try:
                    count=int(c.execute(sql,args).fetchone()[0])
                except sqlite3.OperationalError:
                    count=0
                if count:
                    dependencies[key]=count
            if dependencies:
                return self.send_json({
                    'error':'This branch has linked operational or historical records and cannot be permanently deleted. Keep it inactive to preserve history.',
                    'code':'branch_delete_dependencies',
                    'dependencies':dependencies,
                },409)

            before=dict(branch)
            c.execute('DELETE FROM branches WHERE id=?',(branch['id'],))
            write_audit(c,ctx,'branch.deleted','branch',branch['id'],before=before,
                        metadata={'verified_by_password':True,'branch_code':branch['code']},request=self)
            c.commit()
            return self.send_json({'ok':True,'deleted_branch_id':branch['id'],'deleted_branch_code':branch['code']})

    def _get(self):
        url=urlparse(self.path); path=url.path; parts=[unquote(p) for p in path.split('/') if p]
        if not path.startswith('/api/'):
            static=ROOT/'static'; file=static/('index.html' if path=='/' else path.lstrip('/'))
            if not file.resolve().is_relative_to(static.resolve()) or not file.is_file(): return self.send_error(404)
            data=file.read_bytes(); mime={'.html':'text/html','.css':'text/css','.js':'text/javascript'}.get(file.suffix,'application/octet-stream')
            self.send_response(200); self.send_header('Content-Type',mime+'; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(data); return
        with connect() as c:
            c.execute('BEGIN')
            user=self.current_user(c)
            if path=='/api/me': return self.send_json({'user':safe_user(user,c) if user else None})
            if path=='/api/public/branch-directory':
                return self.send_json(public_branch_directory(c))
            if path=='/api/public/cities':
                cities=[row["city"] for row in c.execute(
                    "SELECT city FROM branches WHERE is_active=1 GROUP BY city ORDER BY city"
                ).fetchall()]
                return self.send_json(cities)
            if path=='/api/public/pricing':
                payload=pricing_payload(c)
                payload["sizes"]=[row for row in payload["sizes"] if row["is_active"]]
                return self.send_json(payload)
            if path=='/api/public/offers':
                return self.send_json(public_offer_rows(c))
            # Public QR for customer receipts. The QR contains only the public
            # tracking URL; private shipment documents still require customer login.
            if len(parts)==5 and parts[:3]==['api','public','tracking'] and parts[4]=='qr':
                awb=parts[3].strip().upper()
                row=c.execute('SELECT id,awb FROM shipments WHERE awb=?',(awb,)).fetchone()
                if not row: return self.send_json({'error':'لم يتم العثور على شحنة بهذا الرقم'},404)
                try:
                    return self.send_svg(code_svg(self.tracking_url(awb),'qr'))
                except ImportError:
                    return self.send_json({'error':'QR renderer unavailable; install reportlab in this Python environment'},503)

            if len(parts)==4 and parts[:3]==['api','public','tracking']:
                awb=parts[3].strip().upper(); row=c.execute(shipment_query()+' WHERE s.awb=?',(awb,)).fetchone()
                if not row: return self.send_json({'error':'لم يتم العثور على شحنة بهذا الرقم'},404)
                if user and auth.context(c,user)['role']=='customer' and not customers.owns_shipment(c,user,row['id']):
                    return self.send_json({'error':'لم يتم العثور على شحنة بهذا الرقم'},404)

                events=c.execute(
                    'SELECT status,stage,location,created_at FROM shipment_events WHERE shipment_id=? ORDER BY created_at,id',
                    (row['id'],)
                ).fetchall()

                # A completed POD is the authoritative final-delivery source.
                # Do not keep advertising an old ETA or the courier's later
                # branch location after the parcel has already been delivered.
                proof=c.execute(
                    """SELECT latitude,longitude,verified_at
                       FROM pod_records WHERE shipment_id=? ORDER BY id DESC LIMIT 1""",
                    (row['id'],)
                ).fetchone()
                delivered=bool(proof) or transitions.canonical(row['status'])=='delivered'
                delivery_event=c.execute(
                    """SELECT location,created_at FROM shipment_events
                       WHERE shipment_id=? AND status='تم الاستلام'
                       ORDER BY created_at DESC,id DESC LIMIT 1""",
                    (row['id'],)
                ).fetchone() if delivered else None

                delivery_latitude=proof['latitude'] if proof else None
                delivery_longitude=proof['longitude'] if proof else None
                delivered_at=(proof['verified_at'] if proof else None) or (
                    delivery_event['created_at'] if delivery_event else None
                )

                latest_failed_attempt=None
                if not delivered:
                    latest_failed_attempt=c.execute(
                        """SELECT attempt_number,failure_reason_code,failure_reason_text,
                                  next_attempt_at,completed_at
                           FROM delivery_attempts
                           WHERE shipment_id=? AND outcome='failed'
                           ORDER BY attempt_number DESC,id DESC LIMIT 1""",
                        (row['id'],)
                    ).fetchone()

                if delivered and delivery_latitude is not None and delivery_longitude is not None:
                    current_location=f"GPS {float(delivery_latitude):.6f}, {float(delivery_longitude):.6f}"
                elif delivered and delivery_event and str(delivery_event['location'] or '').strip():
                    current_location=delivery_event['location']
                elif delivered:
                    current_location=row['destination']
                else:
                    current_location=(row['operational_location'] or row['driver_location'] or row['origin'] or row['destination'])

                return self.send_json({
                    'awb':row['awb'],'status':row['status'],'stage':row['stage'],
                    'origin':row['origin'],'destination':row['destination'],
                    # Keep the stored operational ETA untouched in the database,
                    # but never expose it as a live ETA after final delivery.
                    'eta':'' if delivered else row['eta'],
                    'is_delivered':delivered,
                    'delivered_at':delivered_at,
                    'delivery_latitude':delivery_latitude,
                    'delivery_longitude':delivery_longitude,
                    'current_location':current_location,
                    # A future retry is meaningful only while the shipment is
                    # still unresolved. Once delivered, never expose stale retry data.
                    'next_attempt_at':(
                        latest_failed_attempt['next_attempt_at']
                        if latest_failed_attempt and latest_failed_attempt['next_attempt_at']
                        else ''
                    ),
                    'failed_attempt_number':(
                        latest_failed_attempt['attempt_number'] if latest_failed_attempt else None
                    ),
                    'failure_reason_code':(
                        latest_failed_attempt['failure_reason_code'] if latest_failed_attempt else ''
                    ),
                    'failure_reason_text':(
                        latest_failed_attempt['failure_reason_text'] if latest_failed_attempt else ''
                    ),
                    'events':[shipment_event_payload(row,ev) for ev in events],
                })
            if not user: return self.unauthorized()
            ctx=auth.context(c,user)
            if parts[:2]==['api','customer']:
                customers.require_customer(c,user)
                if parts==['api','customer','profile']: return self.send_json(customers.profile(c,user))
                if parts==['api','customer','commercial-profile']:
                    return self.send_json(customer_business_profile(c,user))
                if parts==['api','customer','invoices']:
                    return self.send_json(customer_invoice_rows(c,user))
                if len(parts)==4 and parts[:3]==['api','customer','invoices']:
                    return self.send_json(customer_invoice_rows(c,user,parts[3].upper()))
                if len(parts)==5 and parts[:3]==['api','customer','invoices'] and parts[4]=='pdf':
                    invoice=customer_invoice_rows(c,user,parts[3].upper())
                    payments=[dict(row) for row in c.execute(
                        "SELECT * FROM payments WHERE invoice_id=? ORDER BY id DESC",(invoice["id"],)
                    ).fetchall()]
                    raw=generate_invoice_pdf(invoice,payments)
                    return self.send_download(raw,"application/pdf",f'{invoice["invoice_number"]}.pdf')
                if parts==['api','customer','payments']:
                    return self.send_json(customer_payment_rows(c,user))
                if parts==['api','customer','notifications']:
                    query=parse_qs(url.query)
                    unread=str(query.get("unread",["0"])[0]).lower() in ("1","true","yes")
                    return self.send_json(customer_notification_rows(c,user,unread))
                if parts==['api','customer','notification-center']:
                    query=parse_qs(url.query)
                    unread=str(query.get("unread",["0"])[0]).lower() in ("1","true","yes")
                    return self.send_json({
                        "summary":notification_summary(c,ctx,user),
                        "notifications":customer_notification_rows(c,user,unread),
                        "deliveries":notification_delivery_rows(c,ctx,user,query.get("limit",["100"])[0]),
                    })
                if parts==['api','customer','notification-preferences']:
                    result=notification_preferences(c,user["id"])
                    result["providers"]=notification_provider_status()
                    return self.send_json(result)
                if parts==['api','customer','offers']:
                    offers=public_offer_rows(c)
                    # Customer portal can show website and customer-portal placements.
                    portal=[]
                    for item in campaign_rows(c):
                        if not item["is_published"] or item["status"]!="نشطة":
                            continue
                        if item["campaign_type"] not in ("خصم","قسيمة") or item["placement"] not in ("customer_portal","both"):
                            continue
                        portal.append({
                            "id":item["id"],"code":item["code"],"name":item["name"],
                            "message":item["message"],"discount_percent":item["discount_percent"],
                            "coupon_code":item["coupon_code"],"start_at":item["start_at"],"end_at":item["end_at"],
                            "min_order_amount":item["min_order_amount"],"max_discount_amount":item["max_discount_amount"],
                            "remaining_redemptions":item["remaining_redemptions"],"branch":item["branch"],
                        })
                    return self.send_json(portal)
                if parts==['api','customer','pickup-requests']:
                    return self.send_json(customer_pickup_rows(c,user))
                if len(parts)==4 and parts[:3]==['api','customer','pickup-requests']:
                    return self.send_json(customer_pickup_rows(c,user,parts[3].upper()))
                if parts==['api','customer','shipments']: return self.send_json(customers.shipments(c,user))
                if len(parts)>=5 and parts[:3]==['api','customer','shipments']:
                    awb=parts[3].strip().upper()
                    owned=customers.shipments(c,user,awb)
                    shipment=shipment_document_context(c,owned["id"])
                    docs=ensure_shipment_documents(c,owned["id"],user["id"])
                    links=shipment_document_links(awb,True)
                    if len(parts)==5 and parts[4]=='documents':
                        return self.send_json(shipment_document_payload(
                            c,owned["id"],self.tracking_url(awb),True
                        ))
                    if len(parts)==5 and parts[4]=='waybill':
                        return self.send_json({"waybill":docs["waybill"],"links":links})
                    if len(parts)==6 and parts[4:]==['waybill','pdf']:
                        raw=generate_waybill_pdf(shipment,docs["waybill"],self.tracking_url(awb))
                        c.execute("""UPDATE waybills SET download_count=download_count+1,
                            last_downloaded_at=CURRENT_TIMESTAMP WHERE id=?""",(docs["waybill"]["id"],))
                        record_shipment_document_event(
                            c,owned["id"],"waybill.downloaded",user,
                            waybill_id=docs["waybill"]["id"],
                            metadata={"awb":awb},request=self
                        )
                        return self.send_download(raw,"application/pdf",f'{docs["waybill"]["waybill_number"]}.pdf')
                    if len(parts)==5 and parts[4]=='stickers':
                        return self.send_json({"stickers":docs["stickers"],"links":links})
                    if len(parts)==6 and parts[4:]==['stickers','pdf']:
                        raw=generate_stickers_pdf(shipment,docs["stickers"],self.tracking_url(awb))
                        ids=[item["id"] for item in docs["stickers"]]
                        if ids:
                            marks=",".join("?" for _ in ids)
                            c.execute(f"""UPDATE parcel_stickers SET download_count=download_count+1,
                                last_downloaded_at=CURRENT_TIMESTAMP WHERE id IN ({marks})""",ids)
                        record_shipment_document_event(
                            c,owned["id"],"stickers.downloaded",user,
                            waybill_id=docs["waybill"]["id"],
                            metadata={"awb":awb,"pieces":len(docs["stickers"])},request=self
                        )
                        return self.send_download(raw,"application/pdf",f'{awb}-stickers.pdf')
                    return self.send_json({'error':'Customer document endpoint not found.'},404)
                if len(parts)==4 and parts[:3]==['api','customer','shipments']:
                    return self.send_json(customers.shipments(c,user,parts[3]))
                return self.send_json({'error':'Customer endpoint not found.'},404)
            if ctx['role']=='customer': return self.forbidden()

            # Commercial module endpoints use shipment/branch scopes directly.
            if path=='/api/invoices':
                return self.send_json(staff_invoice_rows(c,ctx))
            if len(parts)==3 and parts[:2]==['api','invoices']:
                return self.send_json(staff_invoice_rows(c,ctx,parts[2].upper()))
            if len(parts)==4 and parts[:2]==['api','invoices'] and parts[3]=='pdf':
                invoice=staff_invoice_rows(c,ctx,parts[2].upper())
                payments=[dict(row) for row in c.execute(
                    "SELECT * FROM payments WHERE invoice_id=? ORDER BY id DESC",(invoice["id"],)
                ).fetchall()]
                raw=generate_invoice_pdf(invoice,payments)
                return self.send_download(raw,"application/pdf",f'{invoice["invoice_number"]}.pdf')
            if path=='/api/payments':
                return self.send_json(staff_payment_rows(c,ctx))
            if path=='/api/pickup-requests':
                return self.send_json(staff_pickup_rows(c,ctx))
            if len(parts)==3 and parts[:2]==['api','pickup-requests']:
                return self.send_json(staff_pickup_rows(c,ctx,parts[2].upper()))


            if path=='/api/courier/tasks':
                if ctx.get("role") not in ("system_admin","branch_manager","office_employee","courier"):
                    raise auth.AccessDenied("You do not have permission to access courier tasks.")
                query=parse_qs(url.query)
                include_completed=str(query.get("include_completed",["0"])[0]).lower() in ("1","true","yes")

                # Display-normalize legacy English city aliases at the API boundary.
                # Historical rows may still contain "Jaazan" / "Jizan" in driver or
                # attempt location text; keep the stored data untouched while every
                # current courier screen receives the canonical English spelling "Jazan".
                def normalize_courier_place(value):
                    if not isinstance(value,str):
                        return value
                    return re.sub(r"\b(?:Jaazan|Jizan)\b","Jazan",value,flags=re.IGNORECASE)

                def normalize_courier_rows(rows):
                    normalized=[]
                    for row in rows or []:
                        item=dict(row)
                        for key in (
                            "origin","destination","driver_location","current_location",
                            "location_text","city","branch_name"
                        ):
                            if key in item:
                                item[key]=normalize_courier_place(item.get(key))
                        normalized.append(item)
                    return normalized

                delivery_tasks=normalize_courier_rows(courier_delivery_tasks(c,ctx,include_completed))
                pickup_tasks=normalize_courier_rows(courier_pickup_tasks(c,ctx,include_completed))
                return self.send_json({
                    "delivery_tasks":delivery_tasks,
                    "pickup_tasks":pickup_tasks,
                    "failure_reasons":delivery_failure_reason_payload(),
                })
            if len(parts)==4 and parts[:2]==['api','shipments'] and parts[3]=='delivery-attempts':
                if not auth.allowed(ctx,"pod.read"):
                    raise auth.AccessDenied("You do not have permission to read delivery attempts.")
                shipment=policy.object_row(c,ctx,'shipments',parts[2].upper(),'awb')
                attempts=[]
                for row in delivery_attempt_rows(c,shipment["id"]):
                    item=dict(row)
                    if isinstance(item.get("location_text"),str):
                        item["location_text"]=re.sub(
                            r"\b(?:Jaazan|Jizan)\b","Jazan",item["location_text"],flags=re.IGNORECASE
                        )
                    attempts.append(item)
                return self.send_json({
                    "awb":shipment["awb"],
                    "attempts":attempts,
                    "failure_reasons":delivery_failure_reason_payload(),
                })

            if parts[:2]==['api','campaigns']:
                if not auth.allowed(ctx,'campaigns.read'):
                    raise auth.AccessDenied("You do not have permission to read campaigns.")
                if len(parts)==2:
                    return self.send_json(campaign_rows(c))
                if len(parts)>=3:
                    try: campaign_id=int(parts[2])
                    except ValueError: return self.send_json({"error":"Campaign not found."},404)
                    if len(parts)==3:
                        return self.send_json(campaign_rows(c,campaign_id))
                    if len(parts)==4 and parts[3]=='deliveries':
                        campaign_rows(c,campaign_id)
                        return self.send_json(campaign_delivery_rows(c,campaign_id))
                    if len(parts)==4 and parts[3]=='redemptions':
                        campaign_rows(c,campaign_id)
                        return self.send_json(campaign_redemption_rows(c,campaign_id))
                    return self.send_json({"error":"Campaign endpoint not found."},404)

            if path=='/api/search':
                searchable=(
                    "shipments.read","clients.read","shipments.payment","reports.read",
                    "drivers.read","vehicles.read","routes.read","users.manage","campaigns.read"
                )
                if not any(auth.allowed(ctx,permission) for permission in searchable):
                    raise auth.AccessDenied("You do not have permission to use central search.")
                search_query=parse_qs(url.query)
                value=search_query.get("q",[""])[0]
                try:
                    result=central_search_payload(
                        c,ctx,value,search_query.get("limit",["8"])[0]
                    )
                except (TypeError,ValueError):
                    return self.send_json({"error":"Invalid search request."},400)
                return self.send_json(result)

            if path=='/api/audit/summary':
                if not auth.allowed(ctx,"audit.read"):
                    raise auth.AccessDenied("You do not have permission to read the audit log.")
                return self.send_json(audit_summary_payload(c))

            if path=='/api/dashboard/executive':
                if not auth.allowed(ctx,"stats.read"):
                    raise auth.AccessDenied("You do not have permission to view dashboard statistics.")
                dashboard_query=parse_qs(url.query)
                period=dashboard_query.get("period",["30d"])[0]
                return self.send_json(executive_dashboard_payload(c,ctx,period))

            if path in ('/api/reports/overview','/api/reports/management'):
                if not auth.allowed(ctx,"reports.read"):
                    raise auth.AccessDenied("You do not have permission to view management reports.")
                report_query=parse_qs(url.query)
                period=report_query.get("period",["30d"])[0]
                return self.send_json(management_reports_payload(c,ctx,period))

            if path=='/api/access-control/overview':
                if not auth.allowed(ctx,"users.manage"):
                    raise auth.AccessDenied("You do not have permission to manage user access.")
                return self.send_json(access_control_overview(c,ctx))

            if path=='/api/customer-accounts':
                # Shipment ownership is explicit: only staff allowed to edit shipments
                # may browse customer accounts for linking. Never infer ownership from
                # sender/recipient names, mobile numbers or AWBs.
                if not auth.allowed(ctx,"shipments.edit"):
                    raise auth.AccessDenied("You do not have permission to link customer accounts.")
                accounts=[]
                for account_row in c.execute(
                    """SELECT u.* FROM customer_accounts ca
                       JOIN users u ON u.id=ca.user_id
                       ORDER BY lower(u.display_name),lower(u.username),u.id"""
                ).fetchall():
                    if not customers.is_customer(c,account_row):
                        continue
                    accounts.append({
                        "id":account_row["id"],
                        "display_name":account_row["display_name"] or account_row["username"],
                        "username":account_row["username"],
                        "mobile":account_row["mobile"] or "",
                    })
                return self.send_json(accounts)

            policy.read_permission(ctx,parts)
            if path=='/api/branch-directory':
                return self.send_json([dict(r) for r in c.execute(
                    'SELECT id,code,name,city,address,phone,coverage,latitude,longitude FROM branches WHERE is_active=1 ORDER BY city,name,id'
                )])
            if path=='/api/audit':
                try:
                    return self.send_json(audit_rows_payload(c,parse_qs(url.query)))
                except ValueError as exc:
                    return self.send_json({'error':str(exc)},400)
            if path=='/api/reports/shipments':
                query=parse_qs(url.query); scope_key=self.scope_key(ctx)
                if 'ticket' in query:
                    with REPORT_DOWNLOAD_LOCK: download=REPORT_DOWNLOADS.get(query['ticket'][0])
                    if not download or download['expires']<=time.time(): return self.send_json({'error':'Report link expired. Export the report again.'},404)
                    if download['user_id']!=user['id'] or download.get('scope_key')!=scope_key: return self.forbidden()
                    return self.send_download(download['raw'],download['mime'],download['filename'])
                try:
                    from reports import report_options, generate_report, MIME
                    fmt,lang,period,start,end=report_options(query)
                    pred,args=auth.sql_scope(ctx,'shipments','s')
                    rows=[auth.scoped_shipment(ctx,r) for r in c.execute(shipment_query()+' WHERE '+pred+' ORDER BY s.id DESC',args)]
                    raw=generate_report(rows,fmt,lang,period,start,end)
                except ValueError as exc: return self.send_json({'error':str(exc)},400)
                except ImportError: return self.send_json({'error':'Report dependencies unavailable; install requirements.txt in this Python environment'},503)
                except Exception as exc:
                    print(f'Report export failed: {type(exc).__name__}',flush=True)
                    return self.send_json({'error':'Could not generate this report. Please try again.'},500)
                filename=f'ghazala-shipments-{period}-{end.strftime("%Y-%m-%d")}-{lang}.{fmt}'
                if query.get('prepare',[''])[0]=='1': return self.send_json({'url':keep_report_download(user['id'],raw,MIME[fmt],filename,scope_key),'filename':filename})
                return self.send_download(raw,MIME[fmt],filename)
            if path=='/api/shipments':
                q=parse_qs(url.query).get('q',[''])[0]; pred,args=auth.sql_scope(ctx,'shipments','s')
                sql=shipment_query()+' WHERE ('+pred+') AND (s.awb LIKE ? OR s.recipient LIKE ? OR s.phone LIKE ? OR s.sender_name LIKE ? OR s.sender_phone LIKE ?) ORDER BY s.id DESC'
                rows=c.execute(sql,[*args,*([f'%{q}%']*5)]).fetchall(); result=[]
                for row in rows:
                    item=auth.scoped_shipment(ctx,row); item['tracking_url']=self.tracking_url(row['awb'])
                    item['document_links']=shipment_document_links(row['awb'])
                    canonical_status=transitions.canonical(row['status'])
                    destination_branch_id=row['destination_branch_id']
                    origin_branch_id=row['origin_branch_id']
                    branch_ids=tuple(ctx.get('branch_ids') or ())
                    is_global=ctx.get('role')=='system_admin' and ctx.get('global_scope') is True
                    is_destination=destination_branch_id in branch_ids
                    is_origin=origin_branch_id in branch_ids
                    handoff=ensure_shipment_branch_handoff(c,row['id'])
                    item['branch_relation']='global' if is_global else ('destination' if is_destination else ('origin' if is_origin else ''))
                    item['destination_acknowledged']=bool(handoff and handoff['acknowledged_at'])
                    item['destination_acknowledged_at']=handoff['acknowledged_at'] if handoff else None
                    item['destination_received_at']=handoff['received_at'] if handoff else None
                    item['can_acknowledge_at_branch']=bool(
                        not is_global and is_destination and canonical_status!='delivered'
                        and handoff and not handoff['acknowledged_at']
                    )
                    item['can_receive_at_branch']=bool(
                        not is_global and is_destination and canonical_status!='delivered'
                        and handoff and handoff['acknowledged_at'] and not handoff['received_at']
                    )
                    item['booking_source']='customer' if c.execute(
                        'SELECT 1 FROM customer_shipments WHERE shipment_id=? LIMIT 1',(row['id'],)
                    ).fetchone() else 'staff'
                    if ctx['role']!='accountant':
                        item['events']=[shipment_event_payload(row,ev) for ev in c.execute('SELECT status,stage,location,created_at FROM shipment_events WHERE shipment_id=? ORDER BY created_at,id',(row['id'],))]
                    result.append(item)
                return self.send_json(result)
            if len(parts)>=3 and parts[:2]==['api','shipments']:
                shipment=policy.object_row(c,ctx,'shipments',parts[2].upper(),'awb')
                if len(parts)==3:
                    row=c.execute(shipment_query()+' WHERE s.id=?',(shipment['id'],)).fetchone()
                    item=auth.scoped_shipment(ctx,row)|{'tracking_url':self.tracking_url(row['awb'])}
                    item['document_links']=shipment_document_links(row['awb'])
                    item['booking_source']='customer' if c.execute(
                        'SELECT 1 FROM customer_shipments WHERE shipment_id=? LIMIT 1',(row['id'],)
                    ).fetchone() else 'staff'
                    return self.send_json(item)
                if len(parts)==4 and parts[3] in ('qr','barcode'):
                    value=self.tracking_url(shipment['awb']) if parts[3]=='qr' else shipment['awb']
                    try: return self.send_svg(code_svg(value,parts[3]))
                    except ImportError: return self.send_json({'error':'Barcode renderer unavailable; install reportlab in this Python environment'},503)
                docs=ensure_shipment_documents(c,shipment['id'],user['id'])
                doc_shipment=shipment_document_context(c,shipment['id'])
                doc_links=shipment_document_links(shipment['awb'])
                if len(parts)==4 and parts[3]=='documents':
                    return self.send_json(shipment_document_payload(
                        c,shipment['id'],self.tracking_url(shipment['awb'])
                    ))
                if len(parts)==4 and parts[3]=='waybill':
                    return self.send_json({"waybill":docs["waybill"],"links":doc_links})
                if len(parts)==5 and parts[3:]==['waybill','pdf']:
                    raw=generate_waybill_pdf(
                        doc_shipment,docs["waybill"],self.tracking_url(shipment['awb'])
                    )
                    c.execute("""UPDATE waybills SET download_count=download_count+1,
                        last_downloaded_at=CURRENT_TIMESTAMP WHERE id=?""",(docs["waybill"]["id"],))
                    record_shipment_document_event(
                        c,shipment["id"],"waybill.downloaded",user,
                        waybill_id=docs["waybill"]["id"],
                        metadata={"awb":shipment["awb"]},request=self
                    )
                    return self.send_download(
                        raw,"application/pdf",f'{docs["waybill"]["waybill_number"]}.pdf'
                    )
                if len(parts)==4 and parts[3]=='stickers':
                    return self.send_json({"stickers":docs["stickers"],"links":doc_links})
                if len(parts)==5 and parts[3:]==['stickers','pdf']:
                    raw=generate_stickers_pdf(
                        doc_shipment,docs["stickers"],self.tracking_url(shipment['awb'])
                    )
                    ids=[item["id"] for item in docs["stickers"]]
                    if ids:
                        marks=",".join("?" for _ in ids)
                        c.execute(f"""UPDATE parcel_stickers SET download_count=download_count+1,
                            last_downloaded_at=CURRENT_TIMESTAMP WHERE id IN ({marks})""",ids)
                    record_shipment_document_event(
                        c,shipment["id"],"stickers.downloaded",user,
                        waybill_id=docs["waybill"]["id"],
                        metadata={"awb":shipment["awb"],"pieces":len(docs["stickers"])},request=self
                    )
                    return self.send_download(raw,"application/pdf",f'{shipment["awb"]}-stickers.pdf')
                if len(parts)==6 and parts[3]=='stickers' and parts[5]=='pdf':
                    try: parcel_number=int(parts[4])
                    except ValueError: return self.send_json({'error':'Invalid parcel number.'},400)
                    sticker=next(
                        (item for item in docs["stickers"] if item["parcel_number"]==parcel_number),
                        None
                    )
                    if not sticker: return self.send_json({'error':'Parcel sticker not found.'},404)
                    raw=generate_stickers_pdf(
                        doc_shipment,[sticker],self.tracking_url(shipment['awb'])
                    )
                    c.execute("""UPDATE parcel_stickers SET download_count=download_count+1,
                        last_downloaded_at=CURRENT_TIMESTAMP WHERE id=?""",(sticker["id"],))
                    record_shipment_document_event(
                        c,shipment["id"],"sticker.downloaded",user,
                        waybill_id=docs["waybill"]["id"],sticker_id=sticker["id"],
                        metadata={"awb":shipment["awb"],"parcel_number":parcel_number},request=self
                    )
                    return self.send_download(
                        raw,"application/pdf",f'{sticker["sticker_number"]}.pdf'
                    )
                if len(parts)==4 and parts[3]=='pod':
                    row=c.execute('SELECT * FROM pod_records WHERE shipment_id=?',(shipment['id'],)).fetchone()
                    if not row: return self.send_json({'error':'Proof of delivery not found'},404)
                    result={k:row[k] for k in row.keys() if k not in ('signature_data','photo_data')}
                    result['signature_data']='data:image/png;base64,'+base64.b64encode(row['signature_data']).decode() if row['signature_data'] else ''
                    result['photo_data']=f"data:{row['photo_mime']};base64,"+base64.b64encode(row['photo_data']).decode() if row['photo_data'] else ''
                    return self.send_json(result)
            if path=='/api/routes':
                pred,args=auth.sql_scope(ctx,'routes','r')
                runs=c.execute('SELECT r.*,d.name AS driver_name,d.mobile AS driver_mobile,v.plate AS vehicle_plate,v.vehicle_type FROM route_runs r LEFT JOIN drivers d ON d.id=r.driver_id LEFT JOIN vehicles v ON v.id=r.vehicle_id WHERE '+pred+' ORDER BY r.id DESC LIMIT 50',args).fetchall()
                payload=[]; ship_pred,ship_args=auth.sql_scope(ctx,'shipments','s')
                for run in runs:
                    item=dict(run)
                    children=c.execute('SELECT s.id,s.awb,s.recipient,s.status,s.weight,s.origin,s.destination,t.status AS transfer_status,t.origin_branch_id,t.destination_branch_id AS receiving_branch_id,t.received_at,t.received_by,u.display_name AS received_by_name,t.destination_ack_at,t.destination_ack_by,dua.display_name AS destination_ack_by_name,t.origin_ack_at,t.origin_ack_by,oua.display_name AS origin_ack_by_name FROM route_shipments rs JOIN shipments s ON s.id=rs.shipment_id LEFT JOIN shipment_transfers t ON t.route_id=rs.route_id AND t.shipment_id=rs.shipment_id LEFT JOIN users u ON u.id=t.received_by LEFT JOIN users dua ON dua.id=t.destination_ack_by LEFT JOIN users oua ON oua.id=t.origin_ack_by WHERE rs.route_id=? AND ('+ship_pred+') ORDER BY rs.scanned_at',[run['id'],*ship_args]).fetchall()
                    item['shipments']=[dict(r) for r in children]; item['load_kg']=round(sum(float(r['weight'] or 0) for r in children),2)
                    n_pred,n_args=auth.sql_scope(ctx,'notifications','n')
                    item['branches_notified']=c.execute('SELECT count(*) FROM branch_notifications n WHERE n.route_id=? AND ('+n_pred+')',[run['id'],*n_args]).fetchone()[0]
                    payload.append(item)
                return self.send_json(payload)
            if path=='/api/notifications/summary':
                return self.send_json(notification_summary(c,ctx,user))
            if path=='/api/notifications/preferences':
                return self.send_json(notification_preferences(c,user['id']))
            if path=='/api/notifications/deliveries':
                query=parse_qs(url.query)
                return self.send_json(notification_delivery_rows(c,ctx,user,query.get('limit',['100'])[0]))
            if path=='/api/notification-center':
                query=parse_qs(url.query)
                # Full inbox payload while the legacy /api/notifications list remains backward compatible.
                route_pred,route_args=auth.sql_scope(ctx,'notifications','n')
                ship_pred,ship_args=auth.sql_scope(ctx,'shipments','s')
                route_rows=c.execute(
                    '''SELECT MIN(n.id) AS id,n.route_id,MAX(n.message) AS message,
                              MIN(n.due_at) AS due_at,MAX(n.sent_at) AS sent_at,
                              CASE
                                WHEN SUM(CASE WHEN n.delivery='failed' THEN 1 ELSE 0 END)>0 THEN 'failed'
                                WHEN SUM(CASE WHEN n.delivery='sent' THEN 1 ELSE 0 END)>0 THEN 'sent'
                                WHEN SUM(CASE WHEN n.delivery='demo' THEN 1 ELSE 0 END)>0 THEN 'demo'
                                WHEN SUM(CASE WHEN n.delivery='in_app' THEN 1 ELSE 0 END)>0 THEN 'in_app'
                                ELSE 'pending'
                              END AS delivery,
                              GROUP_CONCAT(DISTINCT b.name) AS branch_name,
                              r.code AS route_code,
                              MAX(rr.read_at) AS read_at,
                              CASE WHEN SUM(CASE WHEN rr.notification_id IS NULL THEN 1 ELSE 0 END)=0
                                   THEN 1 ELSE 0 END AS is_read
                       FROM branch_notifications n
                       LEFT JOIN branches b ON b.id=n.branch_id
                       JOIN route_runs r ON r.id=n.route_id
                       LEFT JOIN route_notification_reads rr ON rr.notification_id=n.id AND rr.user_id=?
                       WHERE '''+route_pred+'''
                       GROUP BY n.route_id,r.code
                       ORDER BY MIN(n.due_at) DESC LIMIT 50''',[user['id'],*route_args]
                ).fetchall()
                route_items=[]
                for row in route_rows:
                    item=dict(row); item['id']='route-'+str(item['id']); item['type']='route_departure'; item['is_read']=bool(item['is_read']); route_items.append(item)
                op_rows=c.execute(
                    '''SELECT o.id,o.notification_type AS type,o.shipment_id,o.branch_id,o.title,o.message,o.created_at,s.awb,b.name AS branch_name,
                              rr.read_at,CASE WHEN rr.notification_id IS NULL THEN 0 ELSE 1 END AS is_read
                       FROM operational_notifications o JOIN shipments s ON s.id=o.shipment_id
                       LEFT JOIN branches b ON b.id=o.branch_id
                       LEFT JOIN operational_notification_reads rr ON rr.notification_id=o.id AND rr.user_id=?
                       WHERE '''+ship_pred+''' ORDER BY o.id DESC LIMIT 50''',[user['id'],*ship_args]
                ).fetchall()
                op_items=[]
                for row in op_rows:
                    item=dict(row); item['id']='op-'+str(item['id']); item['is_read']=bool(item['is_read']); op_items.append(item)
                merged=op_items+route_items
                merged.sort(key=lambda item:str(item.get('created_at') or item.get('due_at') or ''),reverse=True)
                return self.send_json({
                    'summary':notification_summary(c,ctx,user),
                    'notifications':merged[:100],
                    'deliveries':notification_delivery_rows(c,ctx,user,query.get('limit',['100'])[0]),
                })
            if path=='/api/notifications':
                # Keep the existing route-departure alerts and merge in
                # operational shipment notifications (for example customer bookings).
                route_pred,route_args=auth.sql_scope(ctx,'notifications','n')
                route_rows=c.execute(
                    '''SELECT MIN(n.id) AS id,n.route_id,MAX(n.message) AS message,
                              MIN(n.due_at) AS due_at,MAX(n.sent_at) AS sent_at,
                              CASE
                                WHEN SUM(CASE WHEN n.delivery='failed' THEN 1 ELSE 0 END)>0 THEN 'failed'
                                WHEN SUM(CASE WHEN n.delivery='sent' THEN 1 ELSE 0 END)>0 THEN 'sent'
                                WHEN SUM(CASE WHEN n.delivery='demo' THEN 1 ELSE 0 END)>0 THEN 'demo'
                                WHEN SUM(CASE WHEN n.delivery='in_app' THEN 1 ELSE 0 END)>0 THEN 'in_app'
                                ELSE 'pending'
                              END AS delivery,
                              GROUP_CONCAT(DISTINCT b.name) AS branch_name,
                              r.code AS route_code,
                              MAX(rr.read_at) AS read_at,
                              CASE WHEN SUM(CASE WHEN rr.notification_id IS NULL THEN 1 ELSE 0 END)=0
                                   THEN 1 ELSE 0 END AS is_read
                       FROM branch_notifications n
                       LEFT JOIN branches b ON b.id=n.branch_id
                       JOIN route_runs r ON r.id=n.route_id
                       LEFT JOIN route_notification_reads rr ON rr.notification_id=n.id AND rr.user_id=?
                       WHERE '''+route_pred+'''
                       GROUP BY n.route_id,r.code
                       ORDER BY MIN(n.due_at) DESC LIMIT 30''',
                    [user['id'],*route_args]
                ).fetchall()
                route_notifications=[]
                for row in route_rows:
                    item=dict(row)
                    item['id']='route-'+str(item['id'])
                    item['type']='route_departure'
                    item['is_read']=bool(item.get('is_read'))
                    route_notifications.append(item)

                ship_pred,ship_args=auth.sql_scope(ctx,'shipments','s')
                operational_rows=c.execute(
                    '''SELECT o.id,o.notification_type AS type,o.shipment_id,o.branch_id,o.title,o.message,
                              o.created_at,s.awb,b.name AS branch_name,
                              rr.read_at,
                              CASE WHEN rr.notification_id IS NULL THEN 0 ELSE 1 END AS is_read
                       FROM operational_notifications o
                       JOIN shipments s ON s.id=o.shipment_id
                       LEFT JOIN branches b ON b.id=o.branch_id
                       LEFT JOIN operational_notification_reads rr
                         ON rr.notification_id=o.id AND rr.user_id=?
                       WHERE '''+ship_pred+'''
                       ORDER BY o.id DESC LIMIT 30''',
                    [user['id'],*ship_args]
                ).fetchall()
                operational_notifications=[]
                for row in operational_rows:
                    item=dict(row)
                    item['id']='op-'+str(item['id'])
                    item['is_read']=bool(item['is_read'])
                    operational_notifications.append(item)

                merged=operational_notifications+route_notifications
                merged.sort(
                    key=lambda item: str(item.get('created_at') or item.get('due_at') or ''),
                    reverse=True
                )
                return self.send_json(merged[:30])
            if path=='/api/branches':
                branch_query=parse_qs(url.query)
                include_inactive=str(branch_query.get('include_inactive',['0'])[0]).lower() in ('1','true','yes')
                if include_inactive and not auth.allowed(ctx,'branches.manage'):
                    include_inactive=False
                # Do not pass an empty `extra` predicate into the generic row helper.
                # Some authorization-policy builds assume `extra` is a real SQL clause.
                # Build the scoped query explicitly when the management view requests
                # both active and inactive branches.
                if include_inactive:
                    branch_pred,branch_args=auth.sql_scope(ctx,'branches','x')
                    rows=c.execute(
                        'SELECT x.* FROM branches x WHERE ('+branch_pred+') ORDER BY x.city,x.name,x.id',
                        branch_args
                    ).fetchall()
                else:
                    rows=policy.rows(c,ctx,'branches',extra='x.is_active=1',order='ORDER BY x.city,x.name,x.id')
                return self.send_json([dict(r) for r in rows])
            if path=='/api/vehicles':
                return self.send_json(vehicle_fleet_payload(c,ctx))
            if path=='/api/fleet/summary':
                return self.send_json(fleet_summary(c,ctx))
            if len(parts)>=3 and parts[:2]==['api','vehicles']:
                vehicle_id=parts[2]
                if len(parts)==3:
                    return self.send_json(vehicle_fleet_payload(c,ctx,vehicle_id))
                if len(parts)==4 and parts[3]=='maintenance':
                    return self.send_json(vehicle_maintenance_rows(c,ctx,vehicle_id))
                if len(parts)==4 and parts[3]=='inspections':
                    return self.send_json(vehicle_inspection_rows(c,ctx,vehicle_id))
                if len(parts)==4 and parts[3]=='documents':
                    return self.send_json(vehicle_document_rows(c,ctx,vehicle_id))
                if len(parts)==4 and parts[3]=='history':
                    return self.send_json(vehicle_status_rows(c,ctx,vehicle_id))
                if len(parts)==6 and parts[3]=='documents' and parts[5]=='file':
                    vehicle=fleet_vehicle_scoped(c,ctx,vehicle_id)
                    try: document_id=int(parts[4])
                    except ValueError: return self.send_json({'error':'Vehicle document not found.'},404)
                    row=c.execute(
                        'SELECT * FROM vehicle_documents WHERE id=? AND vehicle_id=?',
                        (document_id,vehicle['id'])
                    ).fetchone()
                    if not row or not row['file_data']:
                        return self.send_json({'error':'Vehicle document file not found.'},404)
                    filename=row['file_name'] or f"vehicle-{vehicle['id']}-document-{document_id}"
                    return self.send_download(row['file_data'],row['file_mime'] or 'application/octet-stream',filename)
            if path=='/api/drivers':
                rows=policy.rows(c,ctx,'drivers',order='ORDER BY x.id DESC'); payload=[]
                for r in rows:
                    item=dict(r)
                    if ctx['role'] not in ('system_admin','branch_manager'): item.pop('national_id',None)
                    if ctx['role']=='courier': item.pop('employee_name',None)
                    payload.append(item)
                return self.send_json(payload)
            if path=='/api/users': return self.send_json([safe_user(r,c) for r in c.execute('SELECT * FROM users ORDER BY id')])
            if path=='/api/clients':
                result=[dict(r) for r in policy.rows(c,ctx,'clients',order='ORDER BY x.id DESC')]
                if ctx['role'] in ('office_employee','accountant'):
                    for row in result:
                        for key in ('national_id','commercial_registration','mobile','email','notes'): row.pop(key,None)
                return self.send_json(result)
            if path=='/api/campaigns': return self.send_json(campaign_rows(c))
            if path=='/api/pricing': return self.send_json(pricing_payload(c))
            if path=='/api/stats':
                pred,args=auth.sql_scope(ctx,'shipments','s')
                statuses=c.execute('SELECT s.status,count(*) n FROM shipments s WHERE '+pred+' GROUP BY s.status',args).fetchall()
                route_pred,route_args=auth.sql_scope(ctx,'routes','r')
                def count(entity):
                    p,a=auth.sql_scope(ctx,entity,'x'); return c.execute('SELECT count(*) FROM '+auth.ENTITY_TABLES[entity]+' x WHERE '+p,a).fetchone()[0]
                return self.send_json({'total':sum(r['n'] for r in statuses),'statuses':{r['status']:r['n'] for r in statuses},
                    'active_routes':c.execute("SELECT count(*) FROM route_runs r WHERE ("+route_pred+") AND r.status IN ('مجدولة','في الطريق')",route_args).fetchone()[0],
                    'drivers':count('drivers') if auth.allowed(ctx,'drivers.read') else 0,'vehicles':count('vehicles') if auth.allowed(ctx,'vehicles.read') else 0})
            return self.send_json({'error':'Not found'},404)


    def _post(self):
        path=urlparse(self.path).path; data=self.read_json()
        if path=="/api/public/pricing-quote":
            with connect() as c:
                c.execute("BEGIN")
                try:
                    return self.send_json(calculate_quote(c,data))
                except ValueError as exc:
                    return self.send_json({"error":str(exc)},400)
        if path=="/api/public/coupons/validate":
            with connect() as c:
                c.execute("BEGIN")
                try:
                    subtotal=float(data.get("subtotal",0) or 0)
                    shipping_fee=float(data.get("shipping_fee",subtotal) or subtotal)
                    result=campaign_coupon_quote(c,data.get("code",""),shipping_fee,subtotal)
                except (ValueError,TypeError,OverflowError) as exc:
                    return self.send_json({"valid":False,"error":str(exc)},400)
                return self.send_json({"valid":True,**result})
        if path=="/api/customer/register":
            username=str(data.get('username',''))[:160]; ip=self.client_address[0]
            if customers.REGISTRATION_THROTTLE.blocked(ip,username):
                return self.send_json({'error':'Too many registration attempts. Try again in 10 minutes.'},429)
            customers.REGISTRATION_THROTTLE.record(ip,username,False)
            with connect() as c:
                c.execute('BEGIN IMMEDIATE')
                if self.current_user(c): return self.forbidden()
                result=customers.register(c,data,password_hash,self)
                c.commit(); return self.send_json({'user':result},201)
        if path in ("/api/login","/api/customer/login"):
            username=str(data.get('username','')).strip()[:160]; ip=self.client_address[0]
            with connect() as c:
                c.execute('BEGIN IMMEDIATE')
                row=c.execute('SELECT * FROM users WHERE lower(username)=lower(?) AND is_active=1',(username,)).fetchone()
                ctx=auth.context(c,dict(row)) if row else None
                metadata={'identifier_digest':hashlib.sha256(username.casefold().encode()).hexdigest()}
                if LOGIN_THROTTLE.blocked(ip,username):
                    write_audit(c,ctx,'login.throttled','authentication',row['id'] if row else None,metadata=metadata,request=self)
                    c.commit(); return self.send_json({'error':'Too many login attempts. Try again in 10 minutes.'},429)
                eligible=path!='/api/customer/login' or customers.is_customer(c,dict(row) if row else None)
                success=bool(row and eligible and verify_password(str(data.get('password','')),row['password_hash']))
                LOGIN_THROTTLE.record(ip,username,success)
                if not success:
                    write_audit(c,ctx,'login.failed','authentication',row['id'] if row else None,metadata=metadata,request=self)
                    c.commit(); return self.send_json({'error':'اسم المستخدم أو كلمة المرور غير صحيحة'},401)
                token=secrets.token_urlsafe(32)
                c.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],int(time.time())+60*60*24*14))
                write_audit(c,ctx,'login.succeeded','authentication',row['id'],request=self)
                result={'user':customers.profile(c,dict(row)) if path=='/api/customer/login' else safe_user(row,c)}; c.commit()
                return self.send_json(result,cookie=session_cookie(token))
        if path=="/api/logout":
            raw=self.headers.get('Cookie',''); token=next((p.strip().split('=',1)[1] for p in raw.split(';') if p.strip().startswith('ghz_session=')),'')
            with connect() as c:
                c.execute('BEGIN IMMEDIATE'); user=self.current_user(c)
                if token: c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
                if user: write_audit(c,auth.context(c,user),'logout','authentication',user['id'],request=self)
                c.commit()
            return self.send_json({'ok':True},cookie='ghz_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0')
        with connect() as c:
            c.execute("BEGIN IMMEDIATE")
            user=self.current_user(c)
            if not user: return self.unauthorized()
            parts=[unquote(p) for p in path.split("/") if p]

            if path=="/api/customer/coupons/validate":
                customers.require_customer(c,user)
                try:
                    subtotal=float(data.get("subtotal",0) or 0)
                    shipping_fee=float(data.get("shipping_fee",subtotal) or subtotal)
                    result=campaign_coupon_quote(
                        c,data.get("code",""),shipping_fee,subtotal,customer_user_id=user["id"]
                    )
                except (ValueError,TypeError,OverflowError) as exc:
                    return self.send_json({"valid":False,"error":str(exc)},400)
                return self.send_json({"valid":True,**result})
            if len(parts)==5 and parts[:3]==['api','customer','notifications'] and parts[4]=='read':
                customers.require_customer(c,user)
                try: notification_id=int(parts[3])
                except ValueError: return self.send_json({"error":"Notification not found."},404)
                row=c.execute(
                    "SELECT id FROM customer_notifications WHERE id=? AND customer_user_id=?",
                    (notification_id,user["id"])
                ).fetchone()
                if not row:
                    return self.send_json({"error":"Notification not found."},404)
                c.execute(
                    "UPDATE customer_notifications SET status='read',read_at=CURRENT_TIMESTAMP WHERE id=?",
                    (notification_id,)
                )
                c.commit()
                return self.send_json({"ok":True,"id":notification_id})
            if parts==['api','customer','notifications','read-all']:
                customers.require_customer(c,user)
                count=c.execute(
                    """UPDATE customer_notifications
                       SET status='read',read_at=COALESCE(read_at,CURRENT_TIMESTAMP)
                       WHERE customer_user_id=? AND status='unread'""",
                    (user["id"],)
                ).rowcount
                c.commit()
                return self.send_json({"ok":True,"updated":count})
            if parts==['api','customer','notification-center','read-all']:
                customers.require_customer(c,user)
                count=c.execute(
                    """UPDATE customer_notifications SET status='read',read_at=COALESCE(read_at,CURRENT_TIMESTAMP)
                       WHERE customer_user_id=? AND status='unread'""",(user["id"],)
                ).rowcount
                c.commit(); return self.send_json({"ok":True,"updated":count})

            # Customer courier pickup requests.
            if path=="/api/customer/pickup-requests":
                customers.require_customer(c,user)
                allowed={"city","branch_code","address","preferred_at","pieces","weight","notes"}
                if not data or set(data)-allowed:
                    return self.send_json({"error":"Unsupported pickup request fields."},400)
                profile=customers.profile(c,user)
                city=str(data.get("city","")).strip()
                branch_code=str(data.get("branch_code","")).strip().upper()
                address=str(data.get("address") or profile.get("address") or "").strip()
                preferred_at=str(data.get("preferred_at","")).strip()
                notes=str(data.get("notes","")).strip()
                if not city or not address:
                    return self.send_json({"error":"Pickup city and address are required."},400)
                if len(city)>120 or len(address)>1000 or len(preferred_at)>120 or len(notes)>2000:
                    return self.send_json({"error":"A pickup request field exceeds the allowed size."},400)
                branch=active_branch_for_city(c,city,branch_code)
                if not branch:
                    return self.send_json({"error":"Select a city served by an active Ghazala branch."},400)
                try:
                    pieces=int(data.get("pieces",1) or 1)
                    weight=float(data.get("weight",1) or 1)
                    if not 1<=pieces<=100 or not math.isfinite(weight) or weight<=0 or weight>100000:
                        raise ValueError()
                except (TypeError,ValueError,OverflowError):
                    return self.send_json({"error":"Check the parcel count and estimated weight."},400)
                pickup_number="PUP-"+uuid.uuid4().hex[:10].upper()
                cur=c.execute(
                    """INSERT INTO pickup_requests(
                         pickup_number,customer_user_id,branch_id,contact_name,contact_mobile,
                         city,address,preferred_at,pieces,weight,notes,status
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?,'requested')""",
                    (
                        pickup_number,user["id"],branch["id"],profile.get("display_name",""),
                        profile.get("mobile",""),city,address,preferred_at or None,
                        pieces,round(weight,2),notes
                    )
                )
                c.execute(
                    """INSERT INTO pickup_request_events(
                         pickup_request_id,status,actor_user_id,actor_name,note
                       ) VALUES(?,?,?,?,?)""",
                    (cur.lastrowid,"requested",user["id"],profile.get("display_name",""),notes)
                )
                write_audit(
                    c,auth.context(c,user),"pickup.requested","pickup_request",cur.lastrowid,
                    metadata={"pickup_number":pickup_number,"branch_id":branch["id"]},request=self
                )
                result=customer_pickup_rows(c,user,pickup_number)
                c.commit()
                return self.send_json(result,201)

            if len(parts)==5 and parts[:3]==['api','customer','pickup-requests'] and parts[4]=='cancel':
                customers.require_customer(c,user)
                pickup_number=parts[3].upper()
                row=c.execute(
                    """SELECT * FROM pickup_requests
                       WHERE pickup_number=? AND customer_user_id=?""",
                    (pickup_number,user["id"])
                ).fetchone()
                if not row:
                    return self.send_json({"error":"Pickup request not found."},404)
                if row["status"]!="requested":
                    return self.send_json({"error":"Only a requested pickup can be cancelled by the customer."},409)
                c.execute(
                    "UPDATE pickup_requests SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (row["id"],)
                )
                profile=customers.profile(c,user)
                c.execute(
                    """INSERT INTO pickup_request_events(
                         pickup_request_id,status,actor_user_id,actor_name,note
                       ) VALUES(?,?,?,?,?)""",
                    (row["id"],"cancelled",user["id"],profile.get("display_name",""),"Cancelled by customer")
                )
                write_audit(
                    c,auth.context(c,user),"pickup.cancelled","pickup_request",row["id"],
                    metadata={"pickup_number":pickup_number},request=self
                )
                result=customer_pickup_rows(c,user,pickup_number)
                c.commit()
                return self.send_json(result)

            # Customer self-service shipment booking.
            # This route is intentionally handled before the general customer
            # POST guard because customer accounts cannot use staff mutation APIs.
            if path=="/api/customer/shipments":
                customers.require_customer(c,user)

                allowed_fields={
                    "sender_id","sender_phone","sender_address",
                    "recipient","recipient_id","phone",
                    "origin","destination","eta",
                    "recipient_branch","recipient_address",
                    "recipient_latitude","recipient_longitude",
                    "package_type","package_description",
                    "pieces","weight",
                    "length_cm","width_cm","height_cm",
                    "declared_value","insured",
                    "payment_method","cod","pricing_size_code","promo_code"
                }
                extra_fields=set(data)-allowed_fields
                if extra_fields:
                    return self.send_json({
                        "error":"Unsupported customer shipment fields: "+", ".join(sorted(extra_fields))
                    },400)

                customer_profile=customers.profile(c,user)

                sender_name=str(customer_profile.get("display_name","")).strip()
                sender_phone=str(
                    data.get("sender_phone")
                    or customer_profile.get("mobile","")
                    or ""
                ).strip()
                sender_id=str(data.get("sender_id","")).strip()
                sender_address=str(
                    data.get("sender_address")
                    or customer_profile.get("address")
                    or ""
                ).strip()

                recipient=str(data.get("recipient","")).strip()
                recipient_id=str(data.get("recipient_id","")).strip()
                recipient_phone=str(data.get("phone","")).strip()
                origin=str(data.get("origin","")).strip()
                destination=str(data.get("destination","")).strip()
                eta=str(data.get("eta","")).strip()
                recipient_address=str(data.get("recipient_address","")).strip()
                recipient_branch=str(data.get("recipient_branch","")).strip().upper()

                required_values={
                    "customer name":sender_name,
                    "customer mobile":sender_phone,
                    "sender ID":sender_id,
                    "pickup address":sender_address,
                    "recipient":recipient,
                    "recipient ID":recipient_id,
                    "recipient mobile":recipient_phone,
                    "origin":origin,
                    "destination":destination,
                    "ETA":eta,
                    "recipient address":recipient_address,
                }
                missing=[name for name,value in required_values.items() if not value]
                if missing:
                    return self.send_json({
                        "error":"Complete the required booking fields: "+", ".join(missing)
                    },400)

                limits={
                    "sender_id":80,
                    "recipient":160,
                    "recipient_id":80,
                    "phone":60,
                    "origin":120,
                    "destination":120,
                    "eta":120,
                    "sender_address":1000,
                    "recipient_address":1000,
                    "recipient_branch":120,
                    "package_type":160,
                    "package_description":2000,
                }
                length_values={
                    "sender_id":sender_id,
                    "recipient":recipient,
                    "recipient_id":recipient_id,
                    "phone":recipient_phone,
                    "origin":origin,
                    "destination":destination,
                    "eta":eta,
                    "sender_address":sender_address,
                    "recipient_address":recipient_address,
                    "recipient_branch":recipient_branch,
                    "package_type":str(data.get("package_type","")),
                    "package_description":str(data.get("package_description","")),
                }
                if any(len(length_values[key])>limit for key,limit in limits.items()):
                    return self.send_json({"error":"A booking field exceeds the allowed size."},400)

                if origin==destination:
                    return self.send_json({"error":"Origin and destination must be different."},400)

                origin_ok=c.execute(
                    "SELECT 1 FROM branches WHERE city=? AND is_active=1 LIMIT 1",
                    (origin,)
                ).fetchone()
                destination_ok=c.execute(
                    "SELECT 1 FROM branches WHERE city=? AND is_active=1 LIMIT 1",
                    (destination,)
                ).fetchone()
                if not origin_ok or not destination_ok:
                    return self.send_json({
                        "error":"Select an origin and destination served by an active Ghazala branch."
                    },400)

                if recipient_branch and not c.execute(
                    "SELECT 1 FROM branches WHERE code=? AND city=? AND is_active=1",
                    (recipient_branch,destination)
                ).fetchone():
                    return self.send_json({
                        "error":"The selected destination branch does not match the destination city."
                    },400)

                method=str(data.get("payment_method","sender")).strip().lower()
                if method not in ("sender","cod"):
                    return self.send_json({
                        "error":"Customer bookings support sender payment or cash on delivery."
                    },400)

                try:
                    cod_amount=float(data.get("cod",0) or 0)
                    if not math.isfinite(cod_amount) or cod_amount<0:
                        raise ValueError("cod")

                    dimensions={
                        key:float(data.get(key,0) or 0)
                        for key in ("length_cm","width_cm","height_cm","declared_value")
                    }
                    if any(
                        not math.isfinite(value) or value<0
                        for value in dimensions.values()
                    ):
                        raise ValueError("dimensions")

                    recipient_latitude,recipient_longitude=validate_coordinates(
                        data.get("recipient_latitude"),
                        data.get("recipient_longitude")
                    )

                    quote=calculate_quote(c,data,customer_user_id=user["id"])
                    if any(
                        isinstance(value,(int,float)) and not math.isfinite(value)
                        for value in quote.values()
                    ):
                        raise ValueError("quote")
                except ValueError as exc:
                    message=str(exc)
                    if "promo" in message.lower() or "customer has already used" in message.lower() or "redemption limit" in message.lower() or "order total" in message.lower():
                        return self.send_json({"error":message},400)
                    return self.send_json({
                        "error":"Check the COD amount, weight, pieces, dimensions and declared value."
                    },400)
                except (TypeError,OverflowError):
                    return self.send_json({
                        "error":"Check the COD amount, weight, pieces, dimensions and declared value."
                    },400)

                if method=="cod" and cod_amount<=0:
                    return self.send_json({
                        "error":"Enter the cash-on-delivery amount."
                    },400)

                awb="GHZ-"+str(uuid.uuid4().int)[:7]
                payment_status={
                    "cod":'مستحق عند التسليم',
                    "sender":'بانتظار الدفع',
                }[method]

                package_type=str(
                    data.get("package_type") or 'طرد تجاري سريع'
                ).strip()
                package_description=str(
                    data.get("package_description","")
                ).strip()

                cur=c.execute(
                    """INSERT INTO shipments(
                        awb,recipient,recipient_id,phone,
                        origin,destination,status,stage,cod,eta,
                        sender_name,sender_id,sender_phone,driver_id,
                        sender_address,recipient_branch,recipient_address,
                        recipient_latitude,recipient_longitude,
                        package_type,package_description,pieces,weight,
                        length_cm,width_cm,height_cm,declared_value,insured,
                        payment_method,shipping_fee,vat_amount,cod_fee,
                        insurance_fee,total_fee,payment_status,
                        pricing_size_code,pricing_size_fee,
                        campaign_id,promo_code,discount_amount,
                        company_account,is_demo
                    )
                    VALUES(
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,NULL,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,?,?,'',0
                    )""",
                    (
                        awb,recipient,recipient_id,recipient_phone,
                        origin,destination,'تم إنشاء الشحنة','تم الإنشاء',
                        cod_amount,eta,
                        sender_name,sender_id,sender_phone,
                        sender_address,recipient_branch,recipient_address,
                        recipient_latitude,recipient_longitude,
                        package_type,package_description,
                        quote["pieces"],quote["weight"],
                        dimensions["length_cm"],dimensions["width_cm"],
                        dimensions["height_cm"],dimensions["declared_value"],
                        1 if data.get("insured") else 0,
                        method,quote["shipping_fee"],quote["vat_amount"],
                        quote["cod_fee"],quote["insurance_fee"],
                        quote["total_fee"],payment_status,
                        quote["size_code"],quote["size_fee"],
                        quote.get("campaign_id"),quote.get("promo_code",""),quote.get("discount_amount",0)
                    )
                )

                shipment_id=cur.lastrowid
                notification_language=str(data.get("notification_language") or "ar").strip().lower()
                if notification_language not in ("ar","en","ur","hi","bn"):
                    notification_language="ar"
                c.execute("UPDATE shipments SET notification_language=? WHERE id=?",
                          (notification_language,shipment_id))
                redemption_id=record_campaign_redemption(
                    c,quote.get("campaign_id"),user["id"],shipment_id,
                    quote.get("promo_code",""),quote.get("discount_amount",0)
                )
                if redemption_id:
                    write_audit(
                        c,auth.context(c,user),"campaign.redeemed","campaign",quote.get("campaign_id"),
                        metadata={
                            "redemption_id":redemption_id,"awb":awb,
                            "promo_code":quote.get("promo_code",""),
                            "discount_amount":quote.get("discount_amount",0)
                        },request=self
                    )

                customers.link_created_shipment(
                    c,
                    user,
                    shipment_id,
                    request=self
                )
                issued_invoice=ensure_customer_invoice(c,shipment_id,user["id"])
                write_audit(
                    c,auth.context(c,user),"invoice.issued","invoice",issued_invoice["id"],
                    metadata={"invoice_number":issued_invoice["invoice_number"],"awb":awb},request=self
                )

                origin_branch_id,destination_branch_id=persist_shipment_offices(
                    c,shipment_id,origin,destination,recipient_branch
                )

                # Customer bookings automatically enter the pickup workflow.
                pickup_number="PUP-"+uuid.uuid4().hex[:10].upper()
                pickup_note=f"Auto-created from customer shipment {awb}"
                pickup_cur=c.execute(
                    """INSERT INTO pickup_requests(
                         pickup_number,customer_user_id,branch_id,contact_name,contact_mobile,
                         city,address,preferred_at,pieces,weight,notes,status,driver_id,shipment_id
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?,'requested',NULL,?)""",
                    (
                        pickup_number,user["id"],origin_branch_id,sender_name,sender_phone,
                        origin,sender_address,"",quote["pieces"],quote["weight"],pickup_note,
                        shipment_id
                    )
                )
                c.execute(
                    """INSERT INTO pickup_request_events(
                         pickup_request_id,status,actor_user_id,actor_name,note
                       ) VALUES(?,'requested',?,?,?)""",
                    (pickup_cur.lastrowid,user["id"],sender_name,pickup_note)
                )
                write_audit(
                    c,auth.context(c,user),"pickup.requested","pickup_request",
                    pickup_cur.lastrowid,
                    metadata={
                        "pickup_number":pickup_number,
                        "awb":awb,
                        "branch_id":origin_branch_id,
                        "preferred_at":"",
                        "auto_created":True
                    },
                    request=self
                )

                issued_docs=ensure_shipment_documents(c,shipment_id,user["id"])
                record_shipment_document_event(
                    c,shipment_id,"documents.issued",user,
                    waybill_id=issued_docs["waybill"]["id"],
                    metadata={"awb":awb,"pieces":len(issued_docs["stickers"])},request=self
                )

                # Management receives the booking inside the same branch scope.
                c.execute(
                    """INSERT OR IGNORE INTO operational_notifications(
                           notification_type,shipment_id,branch_id,title,message
                       ) VALUES(?,?,?,?,?)""",
                    (
                        "customer_booking",
                        shipment_id,
                        origin_branch_id,
                        "",
                        ""
                    )
                )

                add_shipment_event(
                    c,
                    shipment_id,
                    'تم إنشاء الشحنة',
                    'تم الإنشاء',
                    origin,
                    sender_name
                )

                sms=send_sms(
                    c,
                    recipient_phone,
                    "tracking_link",
                    f"Ghazala shipment {awb} is registered. Track: {self.tracking_url(awb)}"
                )

                result=customers.shipments(c,user,awb)
                result["quote"]=quote
                result["tracking_sms"]=sms["delivery"]
                result["tracking_url"]=self.tracking_url(awb)
                result["documents"]=shipment_document_payload(
                    c,shipment_id,self.tracking_url(awb),True
                )
                result["invoice"]=invoice_payload(issued_invoice)
                result["pickup_request"]=customer_pickup_rows(c,user,pickup_number)

                c.commit()
                return self.send_json(result,201)

            ctx=auth.context(c,user)
            if ctx['role']=='customer' and path!='/api/password': return self.forbidden()

            if path=="/api/campaigns":
                if not auth.allowed(ctx,'campaigns.manage'):
                    raise auth.AccessDenied("You do not have permission to manage campaigns.")
                allowed={
                    "code","name","campaign_type","status","discount_percent","channels",
                    "target_segment","message","start_at","end_at",
                    "placement","coupon_code","max_redemptions","per_customer_limit",
                    "min_order_amount","max_discount_amount","branch_id","auto_expire"
                }
                if not isinstance(data,dict) or not data or set(data)-allowed:
                    return self.send_json({"error":"Unsupported campaign fields."},400)
                name=str(data.get("name","")).strip()
                campaign_type=str(data.get("campaign_type","خصم")).strip()
                status=str(data.get("status","مسودة")).strip()
                channels=normalize_campaign_channels(data.get("channels","in_app"))
                target_segment=str(data.get("target_segment","جميع العملاء")).strip()
                message=str(data.get("message","")).strip()
                start_at=str(data.get("start_at","")).strip()
                end_at=str(data.get("end_at","")).strip()
                if not name or len(name)>160:
                    return self.send_json({"error":"Campaign name is required and must be 160 characters or less."},400)
                if campaign_type not in ('خصم','قسيمة','إشعار Push','رسالة SMS'):
                    return self.send_json({"error":"Select a valid campaign type."},400)
                if status not in ('مسودة','مجدولة','نشطة','متوقفة','منتهية'):
                    return self.send_json({"error":"Select a valid campaign status."},400)
                if len(target_segment)>160 or len(message)>2000:
                    return self.send_json({"error":"Campaign audience or message is too long."},400)
                try:
                    discount=float(data.get("discount_percent",0) or 0)
                except (TypeError,ValueError):
                    return self.send_json({"error":"Enter a valid discount percentage."},400)
                if not 0<=discount<=100:
                    return self.send_json({"error":"Discount percentage must be between 0 and 100."},400)
                validate_campaign_dates(start_at,end_at)
                code=str(data.get("code","")).strip().upper() or f"GZ-{secrets.token_hex(3).upper()}"
                if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,31}",code):
                    return self.send_json({"error":"Campaign code must use 3-32 letters, numbers, hyphens or underscores."},400)
                settings=campaign_settings_fields(c,ctx,data,creating=True)
                try:
                    cur=c.execute(
                        """INSERT INTO campaigns(
                             code,name,campaign_type,status,discount_percent,channels,
                             target_segment,message,start_at,end_at,is_demo
                           ) VALUES(?,?,?,?,?,?,?,?,?,?,0)""",
                        (
                            code,name,campaign_type,status,discount,channels,
                            target_segment,message,start_at,end_at
                        )
                    )
                    if settings:
                        c.execute(
                            "UPDATE campaigns SET "+",".join(key+"=?" for key in settings)+
                            ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            [*settings.values(),cur.lastrowid]
                        )
                except sqlite3.IntegrityError:
                    return self.send_json({"error":"Campaign or coupon code is already in use."},409)
                write_audit(
                    c,ctx,"campaign.created","campaign",cur.lastrowid,
                    metadata={"code":code,"campaign_type":campaign_type,"channels":channels},request=self
                )
                result=campaign_rows(c,cur.lastrowid)
                c.commit()
                return self.send_json(result,201)

            if len(parts)==4 and parts[:2]==['api','campaigns']:
                if not auth.allowed(ctx,'campaigns.manage'):
                    raise auth.AccessDenied("You do not have permission to manage campaigns.")
                try: campaign_id=int(parts[2])
                except ValueError: return self.send_json({"error":"Campaign not found."},404)
                campaign=c.execute("SELECT * FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
                if not campaign:
                    return self.send_json({"error":"Campaign not found."},404)
                action=parts[3]
                if action=='publish':
                    settings=campaign_settings_fields(c,ctx,data)
                    if settings:
                        c.execute(
                            "UPDATE campaigns SET "+",".join(key+"=?" for key in settings)+
                            ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            [*settings.values(),campaign_id]
                        )
                    campaign=c.execute("SELECT * FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
                    start=_campaign_datetime(campaign["start_at"])
                    end=_campaign_datetime(campaign["end_at"])
                    now=datetime.now(timezone.utc)
                    if end and end<now:
                        return self.send_json({"error":"Campaign end date has already passed."},409)
                    status="مجدولة" if start and start>now else "نشطة"
                    c.execute(
                        """UPDATE campaigns
                           SET is_published=1,status=?,published_at=COALESCE(published_at,CURRENT_TIMESTAMP),
                               published_by_user_id=?,updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (status,user["id"],campaign_id)
                    )
                    write_audit(
                        c,ctx,"campaign.published","campaign",campaign_id,
                        metadata={"status":status},request=self
                    )
                    result=campaign_rows(c,campaign_id)
                    c.commit()
                    return self.send_json(result)
                if action=='unpublish':
                    c.execute(
                        """UPDATE campaigns
                           SET is_published=0,
                               status=CASE WHEN status='منتهية' THEN status ELSE 'متوقفة' END,
                               updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (campaign_id,)
                    )
                    write_audit(c,ctx,"campaign.unpublished","campaign",campaign_id,request=self)
                    result=campaign_rows(c,campaign_id)
                    c.commit()
                    return self.send_json(result)
                if action=='dispatch':
                    try:
                        result=dispatch_campaign(c,campaign,user,self)
                    except ValueError as exc:
                        return self.send_json({"error":str(exc)},409)
                    campaign_result=campaign_rows(c,campaign_id)
                    c.commit()
                    return self.send_json({"campaign":campaign_result,"dispatch":result},201)
                return self.send_json({"error":"Campaign action not found."},404)

            # Accounting records a payment against a scoped customer invoice.
            if len(parts)==4 and parts[:2]==['api','invoices'] and parts[3]=='payments':
                if not auth.allowed(ctx,"shipments.payment"):
                    raise auth.AccessDenied("You do not have permission to record payments.")
                invoice=staff_invoice_rows(c,ctx,parts[2].upper())
                if invoice["status"]=="void":
                    return self.send_json({"error":"A void invoice cannot receive payments."},409)
                try:
                    amount=float(data.get("amount",0) or 0)
                except (TypeError,ValueError):
                    amount=0
                if not math.isfinite(amount) or amount<=0:
                    return self.send_json({"error":"Enter a valid payment amount."},400)
                if amount>float(invoice["balance"] or 0)+0.005:
                    return self.send_json({"error":"Payment amount exceeds the invoice balance."},400)
                method=str(data.get("method","cash")).strip().lower()
                if method not in ("cash","card","bank_transfer","online","other"):
                    return self.send_json({"error":"Unsupported payment method."},400)
                reference=str(data.get("reference","")).strip()
                note=str(data.get("note","")).strip()
                if len(reference)>160 or len(note)>1000:
                    return self.send_json({"error":"Payment reference or note is too long."},400)
                payment_number="PMT-"+uuid.uuid4().hex[:10].upper()
                cur=c.execute(
                    """INSERT INTO payments(
                         payment_number,invoice_id,customer_user_id,amount,currency,method,status,
                         reference,provider,recorded_by_user_id,note,paid_at
                       ) VALUES(?,?,?,?,? ,?,'paid',?,'manual',?,?,CURRENT_TIMESTAMP)""",
                    (
                        payment_number,invoice["id"],invoice["customer_user_id"],round(amount,2),
                        invoice["currency"],method,reference,user["id"],note
                    )
                )
                updated_invoice=recalculate_invoice(c,invoice["id"])
                if updated_invoice["status"]=="paid" and invoice["payment_method"] in ("sender","company"):
                    c.execute(
                        "UPDATE shipments SET payment_status='مدفوع',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (invoice["shipment_id"],)
                    )
                write_audit(
                    c,ctx,"payment.recorded","payment",cur.lastrowid,
                    metadata={
                        "payment_number":payment_number,
                        "invoice_number":invoice["invoice_number"],
                        "amount":round(amount,2),
                        "method":method
                    },request=self
                )
                payment=dict(c.execute(
                    """SELECT p.*,i.invoice_number,s.awb
                       FROM payments p
                       JOIN invoices i ON i.id=p.invoice_id
                       JOIN shipments s ON s.id=i.shipment_id
                       WHERE p.id=?""",
                    (cur.lastrowid,)
                ).fetchone())
                if invoice.get("customer_user_id"):
                    notice_title=f"Payment received · {invoice['invoice_number']}"
                    notice_message=f"{round(amount,2):.2f} {invoice['currency']} · Shipment {payment['awb']}"
                    source_key=f"payment:{cur.lastrowid}"
                    create_customer_notification(c,invoice["customer_user_id"],notice_title,notice_message,
                        category="payment",shipment_id=invoice["shipment_id"],source_key=source_key)
                    dispatch_customer_notification_channels(c,invoice["customer_user_id"],notice_title,notice_message,
                        category="payment",shipment_id=invoice["shipment_id"],source_key=source_key,
                        event_type="payment_received",include_sms=True)
                c.commit()
                return self.send_json({"payment":payment,"invoice":invoice_payload(updated_invoice)},201)

            # Branch/courier operations update the lifecycle of pickup requests.
            if len(parts)==4 and parts[:2]==['api','pickup-requests'] and parts[3]=='status':
                role=ctx.get("role")
                if role not in ("system_admin","branch_manager","office_employee","courier"):
                    raise auth.AccessDenied("You do not have permission to update pickup requests.")
                pickup=(courier_pickup_task(c,ctx,parts[2].upper())
                        if role=="courier" else staff_pickup_rows(c,ctx,parts[2].upper()))
                status=str(data.get("status","")).strip().lower()
                allowed_statuses={"requested","assigned","picked_up","completed","cancelled"}
                if status not in allowed_statuses:
                    return self.send_json({"error":"Invalid pickup request status."},400)
                current_status=pickup["status"]
                transitions_allowed={
                    "requested":{"assigned","cancelled"},
                    "assigned":{"picked_up","cancelled"},
                    "picked_up":{"completed"},
                    "completed":set(),
                    "cancelled":set(),
                }
                if status!=current_status and status not in transitions_allowed.get(current_status,set()):
                    return self.send_json({
                        "error":f"Pickup request cannot move from {current_status} to {status}."
                    },409)
                driver_id=pickup.get("driver_id")
                if role=="courier":
                    if "driver_id" in data and data.get("driver_id") not in (None,"",driver_id):
                        raise auth.AccessDenied("A courier cannot reassign a pickup request.")
                    if status!=current_status and not (current_status=="assigned" and status=="picked_up"):
                        raise auth.AccessDenied("Courier accounts can only confirm an assigned pickup as picked up.")
                    if driver_id not in tuple(ctx.get("courier_driver_ids") or ()):
                        raise auth.AccessDenied("This pickup request is not assigned to your courier account.")
                elif "driver_id" in data:
                    if role not in ("system_admin","branch_manager"):
                        raise auth.AccessDenied("Only management can assign a courier to a pickup.")
                    driver_id=data.get("driver_id") or None
                    if driver_id is not None:
                        d_pred,d_args=auth.sql_scope(ctx,"drivers","d")
                        driver=c.execute(
                            "SELECT d.id FROM drivers d WHERE d.id=? AND ("+d_pred+")",
                            [driver_id,*d_args]
                        ).fetchone()
                        if not driver:
                            return self.send_json({"error":"Courier is outside your branch scope."},403)
                if status=="assigned" and not driver_id:
                    return self.send_json({"error":"Assign a courier before marking the pickup assigned."},400)
                note=str(data.get("note","")).strip()
                if len(note)>1000:
                    return self.send_json({"error":"Pickup note is too long."},400)
                if status==current_status and driver_id==pickup.get("driver_id") and not note:
                    c.commit()
                    return self.send_json(pickup)
                c.execute(
                    """UPDATE pickup_requests
                       SET status=?,driver_id=?,updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (status,driver_id,pickup["id"])
                )
                c.execute(
                    """INSERT INTO pickup_request_events(
                         pickup_request_id,status,actor_user_id,actor_name,note
                       ) VALUES(?,?,?,?,?)""",
                    (pickup["id"],status,user["id"],user.get("display_name",""),note)
                )
                write_audit(
                    c,ctx,"pickup.status_updated","pickup_request",pickup["id"],
                    before={"status":current_status,"driver_id":pickup.get("driver_id")},
                    after={"status":status,"driver_id":driver_id},
                    metadata={"pickup_number":pickup["pickup_number"],"note":note},request=self
                )

                # Completing a customer pickup is the origin-office receipt milestone.
                # Only advance an untouched Created shipment; never rewind later states.
                if status=="completed" and pickup.get("shipment_id"):
                    shipment=c.execute(
                        "SELECT * FROM shipments WHERE id=?",
                        (pickup["shipment_id"],)
                    ).fetchone()
                    if shipment and transitions.canonical(shipment["status"])=="created":
                        received_status=transitions.storage_status("received")
                        received_stage=transitions.STATUS_STAGES["received"]
                        transitions.check_transition(c,shipment,received_status,source="pickup")
                        branch=c.execute(
                            "SELECT name,city FROM branches WHERE id=?",
                            (pickup.get("branch_id"),)
                        ).fetchone()
                        receipt_location=str(
                            (branch["name"] if branch else "")
                            or (branch["city"] if branch else "")
                            or pickup.get("city")
                            or shipment["origin"]
                            or "Origin Office"
                        ).strip()
                        c.execute(
                            """UPDATE shipments
                               SET status=?,stage=?,updated_at=CURRENT_TIMESTAMP
                               WHERE id=?""",
                            (received_status,received_stage,shipment["id"])
                        )
                        add_shipment_event(
                            c,shipment["id"],received_status,received_stage,
                            receipt_location,user.get("display_name","")
                        )
                        write_audit(
                            c,ctx,"shipment.received_from_pickup","shipment",shipment["id"],
                            before={"status":shipment["status"],"stage":shipment["stage"]},
                            after={
                                "status":received_status,
                                "stage":received_stage,
                                "location":receipt_location
                            },
                            metadata={
                                "awb":shipment["awb"],
                                "pickup_number":pickup["pickup_number"],
                                "pickup_request_id":pickup["id"],
                                "branch_id":pickup.get("branch_id")
                            },
                            request=self
                        )

                customer_user_id=pickup.get("customer_user_id")
                if customer_user_id:
                    notice_title=f"Pickup {pickup['pickup_number']} · {status.replace('_',' ').title()}"
                    notice_message=note or f"Your pickup request is now {status.replace('_',' ')}."
                    source_key=f"pickup:{pickup['id']}:{status}"
                    create_customer_notification(c,customer_user_id,notice_title,notice_message,
                        category="pickup",source_key=source_key)
                    dispatch_customer_notification_channels(c,customer_user_id,notice_title,notice_message,
                        category="pickup",source_key=source_key,event_type="pickup_update",include_sms=True)
                result=(courier_pickup_task(c,ctx,pickup["pickup_number"])
                        if role=="courier" else staff_pickup_rows(c,ctx,pickup["pickup_number"]))
                c.commit()
                return self.send_json(result)

            # Per-user acknowledgement for operational notifications.
            # Route notifications keep their existing sent/pending semantics.
            if len(parts)==4 and parts[:2]==['api','notifications'] and parts[3]=='read':
                raw_id=str(parts[2])
                if raw_id.startswith('route-'):
                    try: notification_id=int(raw_id[6:])
                    except ValueError: return self.send_json({'error':'Notification not found.'},404)
                    route_pred,route_args=auth.sql_scope(ctx,'notifications','n')
                    visible=c.execute(
                        'SELECT n.route_id FROM branch_notifications n WHERE n.id=? AND ('+route_pred+')',
                        [notification_id,*route_args]
                    ).fetchone()
                    if not visible: return self.send_json({'error':'Notification not found.'},404)
                    route_id=visible['route_id']
                    visible_ids=[row['id'] for row in c.execute(
                        'SELECT n.id FROM branch_notifications n WHERE n.route_id=? AND ('+route_pred+')',
                        [route_id,*route_args]
                    ).fetchall()]
                    for route_notification_id in visible_ids:
                        c.execute("""INSERT INTO route_notification_reads(notification_id,user_id,read_at)
                                     VALUES(?,?,CURRENT_TIMESTAMP)
                                     ON CONFLICT(notification_id,user_id) DO UPDATE SET read_at=CURRENT_TIMESTAMP""",
                                  (route_notification_id,user['id']))
                    c.commit(); return self.send_json({'ok':True,'updated':len(visible_ids)})
                if not raw_id.startswith('op-'):
                    return self.send_json({'error':'Notification not found.'},404)
                try:
                    notification_id=int(raw_id[3:])
                except ValueError:
                    return self.send_json({'error':'Notification not found.'},404)

                ship_pred,ship_args=auth.sql_scope(ctx,'shipments','s')
                visible=c.execute(
                    '''SELECT o.id
                       FROM operational_notifications o
                       JOIN shipments s ON s.id=o.shipment_id
                       WHERE o.id=? AND ('''+ship_pred+')',
                    [notification_id,*ship_args]
                ).fetchone()
                if not visible:
                    return self.send_json({'error':'Notification not found.'},404)

                c.execute(
                    '''INSERT INTO operational_notification_reads(notification_id,user_id,read_at)
                       VALUES(?,?,CURRENT_TIMESTAMP)
                       ON CONFLICT(notification_id,user_id)
                       DO UPDATE SET read_at=CURRENT_TIMESTAMP''',
                    (notification_id,user['id'])
                )
                c.commit()
                return self.send_json({'ok':True})

            if parts in (['api','notifications','read-all'],['api','notification-center','read-all']):
                ship_pred,ship_args=auth.sql_scope(ctx,'shipments','s')
                op_ids=[r['id'] for r in c.execute(
                    'SELECT o.id FROM operational_notifications o JOIN shipments s ON s.id=o.shipment_id WHERE '+ship_pred,
                    ship_args
                ).fetchall()]
                route_pred,route_args=auth.sql_scope(ctx,'notifications','n')
                route_ids=[r['id'] for r in c.execute('SELECT n.id FROM branch_notifications n WHERE '+route_pred,route_args).fetchall()]
                for notification_id in op_ids:
                    c.execute("""INSERT INTO operational_notification_reads(notification_id,user_id,read_at)
                                 VALUES(?,?,CURRENT_TIMESTAMP)
                                 ON CONFLICT(notification_id,user_id) DO UPDATE SET read_at=CURRENT_TIMESTAMP""",
                              (notification_id,user['id']))
                for notification_id in route_ids:
                    c.execute("""INSERT INTO route_notification_reads(notification_id,user_id,read_at)
                                 VALUES(?,?,CURRENT_TIMESTAMP)
                                 ON CONFLICT(notification_id,user_id) DO UPDATE SET read_at=CURRENT_TIMESTAMP""",
                              (notification_id,user['id']))
                c.commit(); return self.send_json({'ok':True,'updated':len(op_ids)+len(route_ids)})

            # Waybill/sticker operational actions are scoped to the shipment and
            # handled before the generic mutation policy because they have their
            # own immutable document-event trail.
            if len(parts)>=5 and parts[:2]==['api','shipments'] and parts[3] in ('waybill','stickers'):
                shipment=policy.object_row(c,ctx,'shipments',parts[2].upper(),'awb')
                if not (auth.allowed(ctx,'shipments.create') or auth.allowed(ctx,'shipments.edit')):
                    raise auth.AccessDenied("You do not have permission to manage shipment documents.")
                docs=ensure_shipment_documents(c,shipment["id"],user["id"])
                if parts[3:] == ['waybill','print']:
                    c.execute("""UPDATE waybills SET print_count=print_count+1,
                        last_printed_at=CURRENT_TIMESTAMP WHERE id=?""",(docs["waybill"]["id"],))
                    record_shipment_document_event(
                        c,shipment["id"],"waybill.printed",user,
                        waybill_id=docs["waybill"]["id"],
                        metadata={"awb":shipment["awb"]},request=self
                    )
                    c.commit()
                    return self.send_json({"ok":True,"waybill":dict(c.execute(
                        "SELECT * FROM waybills WHERE id=?",(docs["waybill"]["id"],)
                    ).fetchone())})
                if parts[3:] == ['waybill','archive']:
                    c.execute("UPDATE waybills SET archived_at=CURRENT_TIMESTAMP WHERE id=?",(docs["waybill"]["id"],))
                    record_shipment_document_event(
                        c,shipment["id"],"waybill.archived",user,
                        waybill_id=docs["waybill"]["id"],
                        metadata={"awb":shipment["awb"]},request=self
                    )
                    c.commit()
                    return self.send_json({"ok":True})
                if parts[3:] == ['waybill','restore']:
                    if accessRole := ctx.get("role"):
                        if accessRole!="system_admin":
                            raise auth.AccessDenied("Only the system administrator can restore an archived waybill.")
                    c.execute("UPDATE waybills SET archived_at=NULL WHERE id=?",(docs["waybill"]["id"],))
                    record_shipment_document_event(
                        c,shipment["id"],"waybill.restored",user,
                        waybill_id=docs["waybill"]["id"],
                        metadata={"awb":shipment["awb"]},request=self
                    )
                    c.commit()
                    return self.send_json({"ok":True})
                if parts[3:] == ['stickers','print']:
                    requested=data.get("parcel_numbers")
                    if requested is None:
                        selected=docs["stickers"]
                    else:
                        if not isinstance(requested,list):
                            return self.send_json({"error":"parcel_numbers must be a list."},400)
                        wanted=set()
                        for value in requested:
                            try: wanted.add(int(value))
                            except (TypeError,ValueError): return self.send_json({"error":"Invalid parcel number."},400)
                        selected=[item for item in docs["stickers"] if item["parcel_number"] in wanted]
                        if len(selected)!=len(wanted):
                            return self.send_json({"error":"One or more parcel stickers were not found."},404)
                    ids=[item["id"] for item in selected]
                    if ids:
                        marks=",".join("?" for _ in ids)
                        c.execute(f"""UPDATE parcel_stickers SET print_count=print_count+1,
                            last_printed_at=CURRENT_TIMESTAMP WHERE id IN ({marks})""",ids)
                    record_shipment_document_event(
                        c,shipment["id"],"stickers.printed",user,
                        waybill_id=docs["waybill"]["id"],
                        metadata={
                            "awb":shipment["awb"],
                            "parcel_numbers":[item["parcel_number"] for item in selected]
                        },request=self
                    )
                    c.commit()
                    return self.send_json({"ok":True,"count":len(selected)})
                return self.send_json({"error":"Shipment document action not found."},404)


            # Courier delivery attempt actions are explicit, scoped mutations with
            # their own attempt history and audit records.
            if len(parts)==5 and parts[:2]==['api','shipments'] and parts[3]=='delivery' and parts[4] in ('start','fail'):
                action=parts[4]
                shipment=_courier_shipment_for_action(c,ctx,parts[2].upper())
                awb=shipment["awb"]
                if transitions.canonical(shipment["status"])=="delivered":
                    return self.send_json({"error":"This shipment has already been delivered."},409)

                if action=="start":
                    allowed={"latitude","longitude","location_text","note"}
                    if set(data)-allowed:
                        return self.send_json({"error":"Unsupported delivery-start fields."},400)
                    open_attempt=_delivery_open_attempt(c,shipment["id"])
                    if open_attempt:
                        c.commit()
                        return self.send_json({
                            "ok":True,
                            "already_started":True,
                            "attempt":delivery_attempt_rows(c,shipment["id"])[0],
                        })
                    try:
                        latitude,longitude=validate_coordinates(data.get("latitude"),data.get("longitude"))
                    except ValueError as exc:
                        return self.send_json({"error":str(exc)},400)
                    location_text=str(data.get("location_text","")).strip()
                    note=str(data.get("note","")).strip()
                    if len(location_text)>1000 or len(note)>1000:
                        return self.send_json({"error":"Delivery-start note or location is too long."},400)
                    if transitions.canonical(shipment["status"])!="out_for_delivery":
                        try:
                            validate_shipment_transition(c,shipment,'قيد التوصيل',source="status")
                        except DeliveryPolicyError as exc:
                            return self.send_json({"error":str(exc),"code":"delivery_policy"},409)
                    number=_next_delivery_attempt_number(c,shipment["id"])
                    driver=c.execute("SELECT * FROM drivers WHERE id=?",(shipment["driver_id"],)).fetchone()
                    if not location_text:
                        location_text=(driver["location_text"] if driver else "") or shipment["destination"]
                    cur=c.execute(
                        """INSERT INTO delivery_attempts(
                             shipment_id,driver_id,attempt_number,outcome,note,latitude,longitude,
                             location_text,created_by_user_id,created_by_name
                           ) VALUES(?,?,?,'in_progress',?,?,?,?,?,?)""",
                        (
                            shipment["id"],shipment["driver_id"],number,note,latitude,longitude,
                            location_text,user["id"],user.get("display_name","")
                        )
                    )
                    stage=f"محاولة تسليم رقم {number}"
                    c.execute(
                        """UPDATE shipments
                           SET status='قيد التوصيل',stage=?,updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (stage,shipment["id"])
                    )
                    if driver:
                        driver_updates=["status='نشط'","updated_at=CURRENT_TIMESTAMP"]
                        values=[]
                        if location_text:
                            driver_updates.append("location_text=?"); values.append(location_text)
                        if latitude is not None:
                            driver_updates.extend(["latitude=?","longitude=?"])
                            values.extend([latitude,longitude])
                        values.append(driver["id"])
                        c.execute("UPDATE drivers SET "+",".join(driver_updates)+" WHERE id=?",values)
                    add_shipment_event(
                        c,shipment["id"],'قيد التوصيل',stage,location_text,user.get("display_name","")
                    )
                    sms=send_sms(
                        c,shipment["phone"],"out_for_delivery",
                        f"Ghazala shipment {awb} is out for delivery. Delivery attempt #{number}."
                    )
                    write_audit(
                        c,ctx,"delivery.attempt_started","shipment",shipment["id"],
                        before={"status":shipment["status"]},
                        after={"status":'قيد التوصيل',"attempt_number":number},
                        metadata={"awb":awb,"driver_id":shipment["driver_id"],"sms":sms["delivery"]},
                        request=self
                    )
                    attempt=next(
                        row for row in delivery_attempt_rows(c,shipment["id"]) if row["id"]==cur.lastrowid
                    )
                    c.commit()
                    return self.send_json({
                        "ok":True,"attempt":attempt,"sms_delivery":sms["delivery"]
                    },201)

                allowed={"reason_code","reason_text","latitude","longitude","location_text",
                         "photo_data","next_attempt_at","note"}
                if set(data)-allowed:
                    return self.send_json({"error":"Unsupported delivery-failure fields."},400)
                open_attempt=_delivery_open_attempt(c,shipment["id"])
                if not open_attempt:
                    return self.send_json({
                        "error":"Start a delivery attempt before recording a failed attempt."
                    },409)
                reason_code=str(data.get("reason_code","")).strip().lower()
                if reason_code not in DELIVERY_FAILURE_REASONS:
                    return self.send_json({"error":"Select a valid failed-delivery reason."},400)
                reason_text=str(data.get("reason_text","")).strip()
                note=str(data.get("note","")).strip()
                if reason_code=="other" and not reason_text:
                    return self.send_json({"error":"Enter the failed-delivery reason."},400)
                if len(reason_text)>1000 or len(note)>1000:
                    return self.send_json({"error":"Delivery exception note is too long."},400)
                try:
                    latitude,longitude=validate_coordinates(data.get("latitude"),data.get("longitude"))
                    photo,photo_mime=decode_data_url(
                        data.get("photo_data"),{"image/jpeg","image/png","image/webp"},3_000_000
                    )
                    next_attempt_at=_normalize_next_attempt(data.get("next_attempt_at"))
                except (ValueError,base64.binascii.Error) as exc:
                    return self.send_json({"error":str(exc)},400)
                location_text=str(data.get("location_text","")).strip()
                if len(location_text)>1000:
                    return self.send_json({"error":"Delivery location is too long."},400)
                if not location_text:
                    driver=c.execute("SELECT location_text FROM drivers WHERE id=?",(shipment["driver_id"],)).fetchone()
                    location_text=(driver["location_text"] if driver else "") or shipment["destination"]
                if transitions.canonical(shipment["status"])!="delayed":
                    try:
                        validate_shipment_transition(c,shipment,'تأخير',source="status")
                    except DeliveryPolicyError as exc:
                        return self.send_json({"error":str(exc),"code":"delivery_policy"},409)
                c.execute(
                    """UPDATE delivery_attempts
                       SET outcome='failed',failure_reason_code=?,failure_reason_text=?,note=?,
                           latitude=?,longitude=?,location_text=?,photo_data=?,photo_mime=?,
                           next_attempt_at=?,completed_at=CURRENT_TIMESTAMP,
                           completed_by_user_id=?,completed_by_name=?,updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (
                        reason_code,reason_text,note,latitude,longitude,location_text,
                        photo,photo_mime,next_attempt_at,user["id"],user.get("display_name",""),
                        open_attempt["id"]
                    )
                )
                reason_labels=DELIVERY_FAILURE_REASONS[reason_code]
                stage=f"محاولة تسليم فاشلة · {reason_labels['ar']}"
                c.execute(
                    """UPDATE shipments
                       SET status='تأخير',stage=?,updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (stage,shipment["id"])
                )
                add_shipment_event(
                    c,shipment["id"],'تأخير',stage,location_text,user.get("display_name","")
                )
                branch_row=c.execute(
                    "SELECT destination_branch_id FROM shipment_scope WHERE shipment_id=?",
                    (shipment["id"],)
                ).fetchone()
                branch_id=branch_row["destination_branch_id"] if branch_row else None
                message=(
                    f"{awb} · {reason_labels['en']}"
                    + (f" · Next attempt {next_attempt_at}" if next_attempt_at else "")
                )
                c.execute(
                    """INSERT INTO operational_notifications(
                         notification_type,shipment_id,branch_id,title,message
                       ) VALUES('delivery_exception',?,?,?,?)
                       ON CONFLICT(notification_type,shipment_id) DO UPDATE SET
                         branch_id=excluded.branch_id,title=excluded.title,message=excluded.message,
                         created_at=CURRENT_TIMESTAMP""",
                    (shipment["id"],branch_id,"Delivery exception",message)
                )
                notification=c.execute(
                    """SELECT id FROM operational_notifications
                       WHERE notification_type='delivery_exception' AND shipment_id=?""",
                    (shipment["id"],)
                ).fetchone()
                if notification:
                    c.execute(
                        "DELETE FROM operational_notification_reads WHERE notification_id=?",
                        (notification["id"],)
                    )
                customer_message=(
                    f"Ghazala: delivery attempt for shipment {awb} was not completed. "
                    f"Reason: {reason_labels['en']}."
                )
                if next_attempt_at:
                    customer_message+=f" Next attempt: {next_attempt_at}."
                sms=send_sms(c,shipment["phone"],"delivery_exception",customer_message)
                write_audit(
                    c,ctx,"delivery.attempt_failed","shipment",shipment["id"],
                    before={"status":shipment["status"],"attempt_number":open_attempt["attempt_number"]},
                    after={"status":'تأخير',"attempt_number":open_attempt["attempt_number"],
                           "reason_code":reason_code},
                    metadata={"awb":awb,"next_attempt_at":next_attempt_at,"sms":sms["delivery"]},
                    request=self
                )
                attempt=next(
                    row for row in delivery_attempt_rows(c,shipment["id"])
                    if row["id"]==open_attempt["id"]
                )
                c.commit()
                return self.send_json({
                    "ok":True,"attempt":attempt,"sms_delivery":sms["delivery"]
                })

            # Fleet-management mutations use the existing vehicles.manage RBAC
            # and vehicle branch scope, while keeping their own audit entries.
            if parts[:2]==['api','vehicles']:
                ctx=auth.context(c,user)
                if not auth.allowed(ctx,'vehicles.manage'):
                    raise auth.AccessDenied("You do not have permission to manage vehicles.")

                if parts==['api','vehicles']:
                    fields=vehicle_fields(data,creating=True)
                    branches=vehicle_branch_ids(c,ctx,data,required=True)
                    columns=list(fields)
                    try:
                        cur=c.execute(
                            "INSERT INTO vehicles("+",".join(columns)+",created_at,updated_at) "
                            "VALUES("+",".join("?" for _ in columns)+",CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
                            [fields[key] for key in columns]
                        )
                    except sqlite3.IntegrityError:
                        return self.send_json({"error":"Vehicle plate or VIN is already in use."},409)
                    vehicle_id=cur.lastrowid
                    persist_fleet_vehicle_branches(c,vehicle_id,branches or [])
                    set_vehicle_status(
                        c,vehicle_id,fields.get("status","متاح"),user,
                        reason="Vehicle created",odometer_km=fields.get("odometer_km",0),
                        force_history=True
                    )
                    write_audit(
                        c,ctx,"vehicle.created","vehicle",vehicle_id,
                        after={key:fields[key] for key in fields if key not in ("notes",)},
                        metadata={"branch_ids":branches or []},request=self
                    )
                    result=vehicle_fleet_payload(c,ctx,vehicle_id)
                    c.commit()
                    return self.send_json(result,201)

                if len(parts)>=4:
                    vehicle=fleet_vehicle_scoped(c,ctx,parts[2])
                    vehicle_id=vehicle["id"]

                    if len(parts)==4 and parts[3]=='branches':
                        branches=vehicle_branch_ids(c,ctx,data,required=True)
                        before=[row["branch_id"] for row in c.execute(
                            "SELECT branch_id FROM vehicle_branches WHERE vehicle_id=? ORDER BY branch_id",
                            (vehicle_id,)
                        ).fetchall()]
                        persist_fleet_vehicle_branches(c,vehicle_id,branches)
                        write_audit(
                            c,ctx,"vehicle.branches_updated","vehicle",vehicle_id,
                            before={"branch_ids":before},after={"branch_ids":branches},request=self
                        )
                        result=vehicle_fleet_payload(c,ctx,vehicle_id)
                        c.commit()
                        return self.send_json(result)

                    if len(parts)==4 and parts[3]=='maintenance':
                        allowed={
                            "maintenance_type","status","description","scheduled_at","completed_at",
                            "odometer_km","cost","vendor","next_due_at","next_due_km","notes"
                        }
                        if not isinstance(data,dict) or not data or set(data)-allowed:
                            return self.send_json({"error":"Unsupported maintenance fields."},400)
                        maintenance_type=_fleet_text(data.get("maintenance_type"),160,"Maintenance type",required=True)
                        status=str(data.get("status") or "scheduled").strip().lower()
                        if status not in ("scheduled","in_progress","completed","cancelled"):
                            return self.send_json({"error":"Select a valid maintenance status."},400)
                        description=_fleet_text(data.get("description"),2000,"Maintenance description")
                        scheduled_at=_fleet_date(data.get("scheduled_at"),"Scheduled maintenance date") or None
                        completed_at=_fleet_date(data.get("completed_at"),"Maintenance completion date") or None
                        if status=="completed" and not completed_at:
                            completed_at=datetime.now(timezone.utc).isoformat(timespec="minutes")
                        odometer=_fleet_number(data.get("odometer_km"),"Maintenance odometer",0,20_000_000,allow_none=True)
                        if odometer is not None and odometer+1e-9<float(vehicle["odometer_km"] or 0):
                            return self.send_json({"error":"Maintenance odometer cannot be lower than the vehicle odometer."},409)
                        cost=_fleet_number(data.get("cost",0),"Maintenance cost",0,100_000_000)
                        vendor=_fleet_text(data.get("vendor"),240,"Maintenance vendor")
                        next_due_at=_fleet_date(data.get("next_due_at"),"Next maintenance date") or None
                        next_due_km=_fleet_number(data.get("next_due_km"),"Next maintenance odometer",0,20_000_000,allow_none=True)
                        notes=_fleet_text(data.get("notes"),2000,"Maintenance notes")
                        cur=c.execute(
                            """INSERT INTO vehicle_maintenance(
                                 vehicle_id,maintenance_type,status,description,scheduled_at,completed_at,
                                 odometer_km,cost,vendor,next_due_at,next_due_km,notes,
                                 created_by_user_id,created_by_name
                               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                vehicle_id,maintenance_type,status,description,scheduled_at,completed_at,
                                odometer,cost,vendor,next_due_at,next_due_km,notes,
                                user["id"],user.get("display_name","")
                            )
                        )
                        if odometer is not None:
                            c.execute(
                                "UPDATE vehicles SET odometer_km=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                (odometer,vehicle_id)
                            )
                        if status=="in_progress":
                            set_vehicle_status(c,vehicle_id,"صيانة",user,reason=f"Maintenance: {maintenance_type}",odometer_km=odometer)
                        elif status=="completed" and vehicle["status"]=="صيانة":
                            set_vehicle_status(c,vehicle_id,"متاح",user,reason=f"Maintenance completed: {maintenance_type}",odometer_km=odometer)
                        write_audit(
                            c,ctx,"vehicle.maintenance_created","vehicle",vehicle_id,
                            metadata={"maintenance_id":cur.lastrowid,"status":status,"type":maintenance_type},
                            request=self
                        )
                        result=dict(c.execute("SELECT * FROM vehicle_maintenance WHERE id=?",(cur.lastrowid,)).fetchone())
                        c.commit()
                        return self.send_json(result,201)

                    if len(parts)==4 and parts[3]=='inspections':
                        allowed={"inspection_type","result","inspected_at","expiry_at","odometer_km","inspector","notes"}
                        if not isinstance(data,dict) or not data or set(data)-allowed:
                            return self.send_json({"error":"Unsupported inspection fields."},400)
                        inspection_type=_fleet_text(data.get("inspection_type"),160,"Inspection type",required=True)
                        result_code=str(data.get("result") or "pending").strip().lower()
                        if result_code not in ("pending","passed","failed"):
                            return self.send_json({"error":"Select a valid inspection result."},400)
                        inspected_at=_fleet_date(data.get("inspected_at"),"Inspection date") or None
                        expiry_at=_fleet_date(data.get("expiry_at"),"Inspection expiry") or None
                        odometer=_fleet_number(data.get("odometer_km"),"Inspection odometer",0,20_000_000,allow_none=True)
                        if odometer is not None and odometer+1e-9<float(vehicle["odometer_km"] or 0):
                            return self.send_json({"error":"Inspection odometer cannot be lower than the vehicle odometer."},409)
                        inspector=_fleet_text(data.get("inspector"),240,"Inspector")
                        notes=_fleet_text(data.get("notes"),2000,"Inspection notes")
                        cur=c.execute(
                            """INSERT INTO vehicle_inspections(
                                 vehicle_id,inspection_type,result,inspected_at,expiry_at,odometer_km,
                                 inspector,notes,created_by_user_id,created_by_name
                               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                            (
                                vehicle_id,inspection_type,result_code,inspected_at,expiry_at,odometer,
                                inspector,notes,user["id"],user.get("display_name","")
                            )
                        )
                        if odometer is not None:
                            c.execute(
                                "UPDATE vehicles SET odometer_km=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                (odometer,vehicle_id)
                            )
                        write_audit(
                            c,ctx,"vehicle.inspection_created","vehicle",vehicle_id,
                            metadata={"inspection_id":cur.lastrowid,"result":result_code,"type":inspection_type},
                            request=self
                        )
                        result=dict(c.execute("SELECT * FROM vehicle_inspections WHERE id=?",(cur.lastrowid,)).fetchone())
                        c.commit()
                        return self.send_json(result,201)

                    if len(parts)==4 and parts[3]=='documents':
                        allowed={
                            "document_type","title","document_number","issue_date","expiry_date",
                            "file_name","document_data","notes"
                        }
                        if not isinstance(data,dict) or not data or set(data)-allowed:
                            return self.send_json({"error":"Unsupported vehicle document fields."},400)
                        document_type=_fleet_text(data.get("document_type"),120,"Document type",required=True)
                        title=_fleet_text(data.get("title") or document_type,240,"Document title",required=True)
                        document_number=_fleet_text(data.get("document_number"),160,"Document number")
                        issue_date=_fleet_date(data.get("issue_date"),"Document issue date")
                        expiry_date=_fleet_date(data.get("expiry_date"),"Document expiry date")
                        file_name=_fleet_text(data.get("file_name"),255,"Document filename")
                        notes=_fleet_text(data.get("notes"),2000,"Document notes")
                        try:
                            file_data,file_mime=decode_data_url(
                                data.get("document_data"),
                                {"application/pdf","image/jpeg","image/png","image/webp"},
                                5_000_000
                            )
                        except (ValueError,base64.binascii.Error) as exc:
                            return self.send_json({"error":str(exc)},400)
                        cur=c.execute(
                            """INSERT INTO vehicle_documents(
                                 vehicle_id,document_type,title,document_number,issue_date,expiry_date,
                                 file_name,file_mime,file_data,notes,created_by_user_id,created_by_name
                               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                vehicle_id,document_type,title,document_number,issue_date,expiry_date,
                                file_name,file_mime,file_data,notes,user["id"],user.get("display_name","")
                            )
                        )
                        write_audit(
                            c,ctx,"vehicle.document_created","vehicle",vehicle_id,
                            metadata={"document_id":cur.lastrowid,"document_type":document_type,"has_file":bool(file_data)},
                            request=self
                        )
                        result=next(row for row in vehicle_document_rows(c,ctx,vehicle_id) if row["id"]==cur.lastrowid)
                        c.commit()
                        return self.send_json(result,201)

            if len(parts)==4 and parts[:2]==['api','routes'] and parts[3] in ('ack-destination','ack-origin'):
                ctx=auth.context(c,user)
                if not auth.allowed(ctx,'routes.read'):
                    raise auth.AccessDenied("You do not have permission to acknowledge branch transfers.")
                route=c.execute("SELECT * FROM route_runs WHERE id=?",(parts[2],)).fetchone()
                if not route:
                    return self.send_json({"error":"Route not found."},404)
                awb=str(data.get("awb","")).strip().upper()
                if not awb:
                    return self.send_json({"error":"Shipment AWB is required."},400)
                kind='destination' if parts[3]=='ack-destination' else 'origin'
                transfer=transfers.authorize_acknowledgement(c,ctx,route,awb,kind)
                transfers.acknowledge(c,ctx,route,transfer,kind,self)
                details=transfers.receipt_details(c,route["id"],transfer["shipment_id"])
                c.commit()
                return self.send_json({"ok":True,"acknowledgement":kind}|details)

            if len(parts)==4 and parts[:2]==['api','shipments'] and parts[3] in ('acknowledge-branch','receive-branch'):
                ctx=auth.context(c,user)
                if not auth.allowed(ctx,'shipments.status'):
                    raise auth.AccessDenied("You do not have permission to update shipment handoff status.")
                awb=str(parts[2] or '').strip().upper()
                shipment=c.execute("SELECT * FROM shipments WHERE awb=?",(awb,)).fetchone()
                if not shipment:
                    return self.send_json({"error":"Shipment not found."},404)
                handoff=ensure_shipment_branch_handoff(c,shipment["id"])
                if not handoff:
                    return self.send_json({"error":"Shipment branch scope is missing."},409)
                is_global=ctx.get('role')=='system_admin' and ctx.get('global_scope') is True
                destination_allowed=handoff["destination_branch_id"] in tuple(ctx.get("branch_ids") or ())
                if not (is_global or destination_allowed):
                    raise auth.AccessDenied("Only the destination branch can perform this shipment handoff action.")
                destination_branch=c.execute("SELECT id,code,name,city FROM branches WHERE id=?",(handoff["destination_branch_id"],)).fetchone()

                if parts[3]=='acknowledge-branch':
                    if not handoff["acknowledged_at"]:
                        c.execute("""UPDATE shipment_branch_handoffs
                            SET acknowledged_at=CURRENT_TIMESTAMP,acknowledged_by=?
                            WHERE shipment_id=?""",(user["id"],shipment["id"]))
                        write_audit(
                            c,ctx,'shipment.destination_acknowledged','shipment',shipment["id"],
                            metadata={"awb":awb,"destination_branch_id":handoff["destination_branch_id"]},
                            request=self
                        )
                        create_branch_handoff_notification(
                            c,shipment["id"],handoff["origin_branch_id"],"acknowledged",awb,
                            destination_branch["name"] if destination_branch else shipment["destination"]
                        )
                    c.commit()
                    updated=ensure_shipment_branch_handoff(c,shipment["id"])
                    return self.send_json({
                        "ok":True,"awb":awb,"acknowledged":True,
                        "acknowledged_at":updated["acknowledged_at"],
                        "destination_branch":dict(destination_branch) if destination_branch else None
                    })

                if not handoff["acknowledged_at"]:
                    return self.send_json({
                        "error":"Destination branch must acknowledge this shipment before receiving it.",
                        "code":"shipment_not_acknowledged"
                    },409)
                canonical=transitions.canonical(shipment["status"])
                if handoff["received_at"]:
                    c.commit()
                    return self.send_json({
                        "ok":True,"awb":awb,"status":shipment["status"],
                        "already_received":True,"received_at":handoff["received_at"]
                    })
                if canonical=='delivered':
                    return self.send_json({"error":"Delivered shipments cannot be received into a branch again."},409)

                destination_status=transitions.storage_status('at_destination')
                stage=transitions.STATUS_STAGES['at_destination']
                if canonical!='at_destination':
                    validate_shipment_transition(c,shipment,destination_status,source='transfer')
                    c.execute("""UPDATE shipments
                        SET status=?,stage=?,updated_at=CURRENT_TIMESTAMP
                        WHERE id=?""",(destination_status,stage,shipment["id"]))
                    add_shipment_event(
                        c,shipment["id"],destination_status,stage,
                        destination_branch["city"] if destination_branch else shipment["destination"],
                        user["display_name"]
                    )
                c.execute("""UPDATE shipment_branch_handoffs
                    SET received_at=CURRENT_TIMESTAMP,received_by=?
                    WHERE shipment_id=?""",(user["id"],shipment["id"]))
                write_audit(
                    c,ctx,'shipment.destination_received','shipment',shipment["id"],
                    before={"status":shipment["status"],"stage":shipment["stage"]},
                    after={"status":destination_status,"stage":stage},
                    metadata={"awb":awb,"destination_branch_id":handoff["destination_branch_id"]},
                    request=self
                )
                create_branch_handoff_notification(
                    c,shipment["id"],handoff["origin_branch_id"],"received",awb,
                    destination_branch["name"] if destination_branch else shipment["destination"]
                )
                c.commit()
                updated=ensure_shipment_branch_handoff(c,shipment["id"])
                return self.send_json({
                    "ok":True,"awb":awb,"status":destination_status,"stage":stage,
                    "received_at":updated["received_at"],
                    "destination_branch":dict(destination_branch) if destination_branch else None
                })

            self.prepare_mutation(c,user,'POST',parts,data)
            if len(parts)==4 and parts[:2]==['api','shipments'] and parts[3]=='customer':
                shipment_for_link=self.mutation_plan['existing']
                result,changed=customers.link_shipment(c,self.auth_ctx,shipment_for_link,data,self)
                invoice=ensure_customer_invoice(
                    c,shipment_for_link["id"],result["customer_user_id"]
                )
                if changed:
                    # When an older/admin-created shipment is linked after lifecycle
                    # activity already happened, give the new owner one durable
                    # current-state notification. Future shipment events then flow
                    # through the normal customer notification pipeline.
                    title=f"Shipment {shipment_for_link['awb']} · {shipment_for_link['status']}"
                    message=" · ".join(part for part in (
                        "Linked to your customer account",
                        str(shipment_for_link["stage"] or "").strip(),
                        str(shipment_for_link["destination"] or "").strip(),
                    ) if part)
                    source_key=f"shipment-link:{shipment_for_link['id']}:{result['customer_user_id']}"
                    create_customer_notification(
                        c,result["customer_user_id"],title,message,
                        category="shipment",shipment_id=shipment_for_link["id"],
                        source_key=source_key
                    )
                    dispatch_customer_notification_channels(
                        c,result["customer_user_id"],title,message,
                        category="shipment",shipment_id=shipment_for_link["id"],
                        source_key=source_key,event_type="shipment_linked",include_sms=False
                    )
                self._audit_pending=False
                c.commit()
                return self.send_json(
                    dict(result)|{"invoice":invoice_payload(invoice)},
                    201 if changed else 200
                )
            if path=="/api/password":
                current=str(data.get('current_password','')); new=str(data.get('new_password',''))
                if not verify_password(current,user['password_hash']): return self.send_json({'error':'كلمة المرور الحالية غير صحيحة'},400)
                validate_password(new)
                c.execute('UPDATE users SET password_hash=? WHERE id=?',(password_hash(new),user['id']))
                revoked=c.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],)).rowcount
                token=secrets.token_urlsafe(32)
                c.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],int(time.time())+60*60*24*14))
                write_audit(c,self.auth_ctx,'password.changed','user',user['id'],request=self)
                write_audit(c,self.auth_ctx,'user.sessions_revoked','user',user['id'],metadata={'count':revoked},request=self)
                c.commit(); return self.send_json({'ok':True},cookie=session_cookie(token))
            if len(parts)==4 and parts[:2]==["api","shipments"] and parts[3]=="otp":
                awb=parts[2].upper(); shipment=c.execute("SELECT * FROM shipments WHERE awb=?",(awb,)).fetchone()
                if not shipment: return self.send_json({"error":"Shipment not found"},404)
                if shipment["status"]=='تم الاستلام': return self.send_json({"error":'تم تسليم الشحنة بالفعل'},409)
                try: require_delivery_eligible(shipment)
                except DeliveryPolicyError as exc: return self.send_json({"error":str(exc)},409)
                now=int(time.time())
                if c.execute("SELECT count(*) FROM delivery_otps WHERE shipment_id=? AND created_at>?",(shipment["id"],now-600)).fetchone()[0]>=3:
                    return self.send_json({"error":'تم إرسال عدة رموز مؤخراً؛ حاول بعد عشر دقائق'},429)
                code=f"{secrets.randbelow(1_000_000):06d}"
                c.execute("INSERT INTO delivery_otps(shipment_id,code_hash,expires_at,created_at) VALUES(?,?,?,?)",
                  (shipment["id"],password_hash(code),now+300,now))
                sms=send_sms(c,shipment["phone"],"delivery_otp",f"Ghazala delivery verification code: {code}. Expires in 5 minutes.")
                result={"ok":True,"delivery":sms["delivery"],"expires_in":300}
                if sms["delivery"]!="sent": result["demo_code"]=code
                return self.send_json(result)
            if len(parts)==4 and parts[:2]==["api","shipments"] and parts[3]=="pod":
                awb=parts[2].upper(); shipment=c.execute("SELECT * FROM shipments WHERE awb=?",(awb,)).fetchone()
                if not shipment: return self.send_json({"error":"Shipment not found"},404)
                if shipment["status"]=='تم الاستلام': return self.send_json({"error":'تم تسليم الشحنة بالفعل'},409)
                try: require_delivery_eligible(shipment)
                except DeliveryPolicyError as exc: return self.send_json({"error":str(exc)},409)
                name=str(data.get("recipient_name","")).strip(); suffix=str(data.get("recipient_id_suffix","")).strip()
                code=str(data.get("otp","")).strip(); challenge=c.execute("SELECT * FROM delivery_otps WHERE shipment_id=? ORDER BY id DESC LIMIT 1",(shipment["id"],)).fetchone()
                if not name or not code: return self.send_json({"error":'أدخل اسم المستلم ورمز التحقق'},400)
                if not re.fullmatch(r"\d{4}",suffix):
                    return self.send_json({"error":"Enter the recipient's actual last 4 ID digits."},400)
                if shipment["recipient_id"] and not str(shipment["recipient_id"]).strip().endswith(suffix):
                    return self.send_json({"error":'آخر أرقام الهوية لا تطابق بيانات المستلم'},400)
                if not challenge or challenge["verified_at"] is not None or challenge["expires_at"]<=int(time.time()) or challenge["attempts"]>=5: return self.send_json({"error":'رمز التحقق غير صحيح أو انتهت صلاحيته'},400)
                if not verify_password(code,challenge["code_hash"]):
                    c.execute("UPDATE delivery_otps SET attempts=attempts+1 WHERE id=?",(challenge["id"],))
                    return self.send_json({"error":'رمز التحقق غير صحيح أو انتهت صلاحيته'},400)
                try:
                    signature,signature_mime=decode_data_url(data.get("signature_data"),{"image/png"},500_000)
                    photo,photo_mime=decode_data_url(data.get("photo_data"),{"image/jpeg","image/png","image/webp"},3_000_000)
                except (ValueError,base64.binascii.Error) as exc: return self.send_json({"error":str(exc)},400)
                if not signature: return self.send_json({"error":'أضف توقيع المستلم قبل تأكيد التسليم'},400)
                try: validate_signature_image(signature)
                except ValueError as exc: return self.send_json({"error":str(exc)},400)
                try:
                    latitude,longitude=validate_coordinates(data.get("latitude"),data.get("longitude"))
                except (TypeError,ValueError): return self.send_json({"error":"Delivery coordinates must be a valid latitude/longitude pair."},400)
                if c.execute("SELECT 1 FROM pod_records WHERE shipment_id=?",(shipment["id"],)).fetchone():
                    return self.send_json({"error":"Saved delivery proof cannot be replaced."},409)
                now_text=datetime.now(timezone.utc).isoformat(timespec="seconds")
                c.execute("""INSERT INTO pod_records(shipment_id,recipient_name,recipient_id_suffix,signature_data,photo_data,photo_mime,latitude,longitude,note,verified_at,verified_by)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                  (shipment["id"],name,suffix,signature,photo,photo_mime,latitude,longitude,str(data.get("note", ""))[:1000],now_text,user["display_name"]))
                c.execute("UPDATE delivery_otps SET verified_at=? WHERE id=?",(int(time.time()),challenge["id"]))
                try: validate_shipment_transition(c,shipment,'تم الاستلام')
                except DeliveryPolicyError as exc:
                    c.rollback()
                    return self.send_json({"error":str(exc)},409)
                location=(f"GPS {latitude:.5f}, {longitude:.5f}" if latitude is not None else shipment["destination"])
                active_attempt=_delivery_open_attempt(c,shipment["id"])
                if active_attempt:
                    c.execute(
                        """UPDATE delivery_attempts
                           SET outcome='delivered',recipient_name=?,latitude=?,longitude=?,location_text=?,
                               completed_at=?,completed_by_user_id=?,completed_by_name=?,
                               updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (
                            name,latitude,longitude,location,now_text,user["id"],
                            user.get("display_name",""),active_attempt["id"]
                        )
                    )
                    delivery_attempt_id=active_attempt["id"]
                else:
                    attempt_number=_next_delivery_attempt_number(c,shipment["id"])
                    cur_attempt=c.execute(
                        """INSERT INTO delivery_attempts(
                             shipment_id,driver_id,attempt_number,outcome,recipient_name,
                             latitude,longitude,location_text,started_at,completed_at,
                             created_by_user_id,completed_by_user_id,created_by_name,completed_by_name
                           ) VALUES(?,?,?,'delivered',?,?,?,?,?,?,?,?,?,?)""",
                        (
                            shipment["id"],shipment["driver_id"],attempt_number,name,
                            latitude,longitude,location,now_text,now_text,user["id"],user["id"],
                            user.get("display_name",""),user.get("display_name","")
                        )
                    )
                    delivery_attempt_id=cur_attempt.lastrowid
                payment_status='تم التحصيل عند التسليم' if shipment["payment_method"]=="cod" and float(shipment["cod"] or 0)>0 else shipment["payment_status"]
                c.execute("UPDATE shipments SET status='تم الاستلام',stage='تم التسليم',payment_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(payment_status,shipment["id"]))
                add_shipment_event(c,shipment["id"],'تم الاستلام','تم التسليم',location,user["display_name"])
                if payment_status=='تم التحصيل عند التسليم': add_shipment_event(c,shipment["id"],'تم التحصيل عند التسليم',f"{float(shipment['cod']):g} ر.س",location,user["display_name"])
                sms=send_sms(c,shipment["phone"],"delivery_confirmation",f"Ghazala: shipment {awb} was delivered at {now_text}.")
                return self.send_json({"ok":True,"awb":awb,"verified_at":now_text,"sms_delivery":sms["delivery"],"delivery_attempt_id":delivery_attempt_id})
            if path=="/api/shipments":
                customer_user_id=data.get("customer_user_id") or None
                required=["sender_name","sender_id","sender_phone","recipient","recipient_id","phone","origin","destination","eta"]
                if any(not str(data.get(k," ")).strip() for k in required): return self.send_json({"error":'أكمل حقول المرسل والمستلم والمسار والموعد'},400)
                data["origin"]=str(data["origin"]).strip()
                data["destination"]=str(data["destination"]).strip()
                data["recipient_branch"]=str(data.get("recipient_branch","")).strip().upper()
                if data["origin"]==data["destination"]:
                    return self.send_json({"error":"Origin and destination must be different."},400)
                if not active_branch_for_city(c,data["origin"]) or not active_branch_for_city(c,data["destination"]):
                    return self.send_json({"error":"Select cities served by active Ghazala branches."},400)
                if not str(data.get("sender_address","")).strip() or not str(data.get("recipient_address","")).strip(): return self.send_json({"error":'أدخل عنوان المرسل والمستلم بالتفصيل'},400)
                method=data.get("payment_method","cod")
                if method not in ("sender","cod","company"): return self.send_json({"error":'طريقة الدفع غير صحيحة'},400)
                if method=="company" and not str(data.get("company_account","")).strip(): return self.send_json({"error":'أدخل اسم/رقم حساب الشركة'},400)
                try:
                    cod_amount=float(data.get("cod",0) or 0)
                    if not math.isfinite(cod_amount) or cod_amount<0: raise ValueError("cod")
                except (TypeError,ValueError): return self.send_json({"error":'أدخل مبلغ التحصيل عند الاستلام'},400)
                if method=="cod" and cod_amount<=0: return self.send_json({"error":'أدخل مبلغ التحصيل عند الاستلام'},400)
                driver_id=data.get("driver_id") or None
                if driver_id and not c.execute("SELECT id FROM drivers WHERE id=?",(driver_id,)).fetchone(): return self.send_json({"error":'السائق المحدد غير موجود'},400)
                if data.get("recipient_branch") and not c.execute("SELECT id FROM branches WHERE code=? AND city=? AND is_active=1",(data["recipient_branch"],data["destination"])).fetchone(): return self.send_json({"error":'فرع الوجهة غير مطابق للمدينة المحددة'},400)
                try:
                    dimensions={key:float(data.get(key,0) or 0) for key in ("length_cm","width_cm","height_cm","declared_value")}
                    if any(not math.isfinite(value) or value<0 for value in dimensions.values()): raise ValueError("dimensions")
                    quote=calculate_quote(c,data)
                    if any(not math.isfinite(float(quote[key])) for key in ("shipping_fee","cod_fee","insurance_fee","vat_amount","total_fee")): raise ValueError("quote")
                except (ValueError,TypeError): return self.send_json({"error":'تحقق من الوزن والكمية والقيمة المعلنة'},400)
                awb="GHZ-"+str(uuid.uuid4().int)[:7]
                payment_status={"cod":'مستحق عند التسليم',"sender":'بانتظار الدفع',"company":'على حساب الشركة'}[method]
                c.execute("""INSERT INTO shipments(awb,recipient,recipient_id,phone,origin,destination,status,stage,cod,eta,
                  sender_name,sender_id,sender_phone,driver_id,sender_address,recipient_branch,recipient_address,recipient_latitude,recipient_longitude,
                  package_type,package_description,pieces,weight,length_cm,width_cm,height_cm,declared_value,insured,payment_method,shipping_fee,vat_amount,cod_fee,insurance_fee,total_fee,payment_status,pricing_size_code,pricing_size_fee,company_account,is_demo)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                  (awb,data["recipient"],data["recipient_id"],data["phone"],data["origin"],data["destination"],'تم إنشاء الشحنة','تم الإنشاء',cod_amount,data["eta"],
                   data["sender_name"],data["sender_id"],data["sender_phone"],driver_id,data.get("sender_address",""),data.get("recipient_branch",""),data["recipient_address"],
                   data.get("recipient_latitude"),data.get("recipient_longitude"),data.get("package_type",'طرد تجاري سريع'),data.get("package_description",""),quote["pieces"],quote["weight"],
                   dimensions["length_cm"],dimensions["width_cm"],dimensions["height_cm"],dimensions["declared_value"],1 if data.get("insured") else 0,
                   method,quote["shipping_fee"],quote["vat_amount"],quote["cod_fee"],quote["insurance_fee"],quote["total_fee"],payment_status,quote["size_code"],quote["size_fee"],data.get("company_account","")))
                shipment=c.execute("SELECT id FROM shipments WHERE awb=?",(awb,)).fetchone()
                notification_language=str(data.get("notification_language") or "ar").strip().lower()
                if notification_language not in ("ar","en","ur","hi","bn"):
                    notification_language="ar"
                c.execute("UPDATE shipments SET notification_language=? WHERE id=?",
                          (notification_language,shipment["id"]))
                persist_shipment_offices(
                    c,shipment["id"],data["origin"],data["destination"],data.get("recipient_branch","")
                )
                linked_customer=None
                linked_invoice=None
                if customer_user_id is not None:
                    shipment_for_link=c.execute("SELECT * FROM shipments WHERE id=?",(shipment["id"],)).fetchone()
                    linked_customer,_=customers.link_shipment(
                        c,self.auth_ctx,shipment_for_link,{"customer_user_id":customer_user_id},self
                    )
                    linked_invoice=ensure_customer_invoice(
                        c,shipment["id"],linked_customer["customer_user_id"]
                    )
                issued_docs=ensure_shipment_documents(c,shipment["id"],user["id"])
                record_shipment_document_event(
                    c,shipment["id"],"documents.issued",user,
                    waybill_id=issued_docs["waybill"]["id"],
                    metadata={"awb":awb,"pieces":len(issued_docs["stickers"])},request=self
                )
                add_shipment_event(c,shipment["id"],'تم إنشاء الشحنة','تم الإنشاء',data["origin"],user["display_name"])
                sms=send_sms(c,data["phone"],"tracking_link",f"Ghazala shipment {awb} is registered. Track: {self.tracking_url(awb)}")
                row=c.execute(shipment_query()+" WHERE s.awb=?",(awb,)).fetchone()
                return self.send_json(dict(row)|{
                    "quote":quote,
                    "tracking_sms":sms["delivery"],
                    "tracking_url":self.tracking_url(awb),
                    "documents":shipment_document_payload(c,shipment["id"],self.tracking_url(awb)),
                    "customer_link":dict(linked_customer) if linked_customer else None,
                    "invoice":invoice_payload(linked_invoice) if linked_invoice else None
                },201)
            if path=="/api/routes":
                origin=str(data.get("origin","")); destination=str(data.get("destination","")); awbs=list(dict.fromkeys(str(x).strip().upper() for x in data.get("awbs",[]) if str(x).strip()))
                if not origin or not destination or origin==destination:
                    return self.send_json({"error":"Select two different served cities for the route."},400)
                if not active_branch_for_city(c,origin) or not active_branch_for_city(c,destination):
                    return self.send_json({"error":"Route cities must be served by active Ghazala branches."},400)
                if not awbs: return self.send_json({"error":'أضف شحنة واحدة على الأقل إلى الرحلة'},400)
                driver_id=data.get("driver_id") or None; vehicle_id=data.get("vehicle_id") or None
                if not driver_id: return self.send_json({"error":'حدد سائقاً للرحلة'},400)
                if driver_id and not c.execute("SELECT id FROM drivers WHERE id=?",(driver_id,)).fetchone(): return self.send_json({"error":'السائق غير موجود'},400)
                vehicle=c.execute("SELECT * FROM vehicles WHERE id=?",(vehicle_id,)).fetchone() if vehicle_id else None
                if not vehicle: return self.send_json({"error":'اختر مركبة صالحة للرحلة'},400)
                if c.execute("SELECT 1 FROM route_runs WHERE driver_id=? AND status IN ('مجدولة','في الطريق')",(driver_id,)).fetchone(): return self.send_json({"error":'السائق مرتبط برحلة نشطة أو مجدولة بالفعل'},409)
                if c.execute("SELECT 1 FROM route_runs WHERE vehicle_id=? AND status IN ('مجدولة','في الطريق')",(vehicle_id,)).fetchone(): return self.send_json({"error":'المركبة مرتبطة برحلة نشطة أو مجدولة بالفعل'},409)
                placeholders=",".join("?" for _ in awbs)
                rows=c.execute(f"SELECT * FROM shipments WHERE awb IN ({placeholders})",awbs).fetchall()
                if len(rows)!=len(awbs): return self.send_json({"error":'تأكد من أرقام جميع الشحنات'},400)
                if any(r["origin"]!=origin or r["destination"]!=destination for r in rows): return self.send_json({"error":'اتجاه إحدى الشحنات لا يطابق اتجاه الرحلة'},400)
                if any(transitions.canonical(r['status'])=='delivered' for r in rows): return self.send_json({"error":'تم تسليم الشحنة بالفعل'},400)
                occupied=c.execute(f"""SELECT s.awb FROM route_shipments rs JOIN route_runs r ON r.id=rs.route_id
                  JOIN shipments s ON s.id=rs.shipment_id WHERE s.awb IN ({placeholders}) AND r.status IN ('مجدولة','في الطريق')""",awbs).fetchall()
                if occupied: return self.send_json({"error":'إحدى الشحنات مرتبطة برحلة نشطة بالفعل'},409)
                weight=sum(float(r["weight"] or 0) for r in rows)
                try: capacity=float(data.get("capacity_kg") or vehicle["capacity_kg"])
                except (TypeError,ValueError): return self.send_json({"error":'أدخل سعة حمولة صحيحة'},400)
                if capacity<=0 or capacity>float(vehicle["capacity_kg"]): return self.send_json({"error":'سعة الرحلة لا يمكن أن تتجاوز سعة المركبة المحددة'},400)
                if weight>capacity: return self.send_json({"error":f"وزن الحمولة {weight:g} كجم يتجاوز السعة {capacity:g} كجم"},400)
                try:
                    departure=datetime.fromisoformat(str(data.get("departure_at","")))
                    if departure.tzinfo is None: departure=departure.astimezone()
                except ValueError: return self.send_json({"error":'حدد موعد انطلاق صحيحاً'},400)
                code="TRK-"+datetime.now().strftime("%y%m%d")+"-"+secrets.token_hex(2).upper()
                cur=c.execute("INSERT INTO route_runs(code,origin,destination,departure_at,driver_id,vehicle_id,capacity_kg,created_by) VALUES(?,?,?,?,?,?,?,?)",
                  (code,origin,destination,departure.isoformat(timespec="minutes"),driver_id,vehicle_id,capacity,user["display_name"]))
                route_id=cur.lastrowid
                route_offices=persist_route_offices(c,route_id,origin,destination)
                for row in rows:
                    c.execute("INSERT INTO route_shipments(route_id,shipment_id,scanned_by) VALUES(?,?,?)",(route_id,row["id"],user["display_name"]))
                    transfers.load(c,route_id,row['id'],route_offices,self.auth_ctx,self)
                    c.execute("UPDATE shipments SET driver_id=? WHERE id=?",(driver_id,row["id"]))
                    add_shipment_event(c,row["id"],row["status"],f"تم تحميل الشحنة على الرحلة {code}",origin,user["display_name"])
                notice_minutes=max(0,int(data.get("notification_minutes",30)))
                due=departure-timedelta(minutes=notice_minutes)
                due_text=due.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                for branch in c.execute("SELECT id,phone,city FROM branches WHERE id IN (?,?) AND is_active=1",route_offices).fetchall():
                    c.execute("INSERT OR IGNORE INTO branch_notifications(route_id,branch_id,message,due_at) VALUES(?,?,?,?)",
                      (route_id,branch["id"],f"رحلة {code}: شحنات {origin} ↔ {destination} تنطلق {departure.strftime('%Y-%m-%d %H:%M')}",due_text))
                return self.send_json({"ok":True,"id":route_id,"code":code,"load_kg":weight,"capacity_kg":capacity,"notification_due_at":due_text},201)
            if len(parts)==4 and parts[:2]==["api","routes"] and parts[3]=="scan":
                route=c.execute("SELECT * FROM route_runs WHERE id=?",(parts[2],)).fetchone(); awb=str(data.get("awb","")).strip().upper()
                shipment=c.execute("SELECT * FROM shipments WHERE awb=?",(awb,)).fetchone() if route else None
                if not route: return self.send_json({"error":'الرحلة غير موجودة'},404)
                if route["status"]!='مجدولة': return self.send_json({"error":'لا يمكن إضافة طرود بعد انطلاق الرحلة'},400)
                if not shipment: return self.send_json({"error":'رقم البوليصة غير صحيح'},404)
                if transitions.canonical(shipment['status'])=='delivered': return self.send_json({"error":'تم تسليم الشحنة بالفعل'},400)
                if (shipment["origin"],shipment["destination"])!=(route["origin"],route["destination"]): return self.send_json({"error":'اتجاه الشحنة لا يطابق مسار الرحلة'},400)
                already=c.execute("SELECT 1 FROM route_shipments rs JOIN route_runs r ON r.id=rs.route_id\n                  WHERE rs.shipment_id=? AND r.status IN ('مجدولة','في الطريق')",(shipment["id"],)).fetchone()
                if already: return self.send_json({"error":'الشحنة مضافة مسبقاً إلى رحلة'},409)
                weight=c.execute("SELECT coalesce(sum(s.weight),0) FROM route_shipments rs JOIN shipments s ON s.id=rs.shipment_id WHERE rs.route_id=?",(route["id"],)).fetchone()[0]
                if float(weight)+float(shipment["weight"] or 0)>route["capacity_kg"]: return self.send_json({"error":'إضافة هذه الشحنة ستتجاوز سعة المركبة'},400)
                c.execute("INSERT INTO route_shipments(route_id,shipment_id,scanned_by) VALUES(?,?,?)",(route["id"],shipment["id"],user["display_name"]))
                transfers.load(c,route['id'],shipment['id'],policy.schema.resolve_route_offices(c,route),self.auth_ctx,self)
                if route["driver_id"]: c.execute("UPDATE shipments SET driver_id=? WHERE id=?",(route["driver_id"],shipment["id"]))
                add_shipment_event(c,shipment["id"],shipment["status"],f"تم المسح وتحميلها على الرحلة {route['code']}",route["origin"],user["display_name"])
                return self.send_json({"ok":True,"awb":awb,"route":route["code"]},201)
            if len(parts)==4 and parts[:2]==['api','routes'] and parts[3]=='receive':
                route=self.mutation_plan['existing']; transfer=self.mutation_plan['receipt_transfer']
                shipment=c.execute('SELECT * FROM shipments WHERE id=?',(transfer['shipment_id'],)).fetchone()
                changed=transitions.canonical(shipment['status'])!='delivered'
                delivered_status=transitions.storage_status('delivered')
                if transfer['status']=='received':
                    self._audit_pending=False
                    if changed:
                        validate_shipment_transition(c,shipment,delivered_status,source='transfer')
                        stage=transitions.STATUS_STAGES['delivered']
                        c.execute("UPDATE shipments SET status=?,stage=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(delivered_status,stage,shipment['id']))
                        add_shipment_event(c,shipment['id'],delivered_status,stage,route['destination'],user['display_name'])
                    return self.send_json({'ok':True,'shipments_updated':int(changed)}|transfers.receipt_details(c,route['id'],transfer['shipment_id']))
                if route['status']!='وصلت' or transfer['status']!='awaiting_receipt':
                    return self.send_json({'error':'Confirm receipt after the vehicle has arrived.','code':'transfer_receipt'},409)
                if changed: validate_shipment_transition(c,shipment,delivered_status,source='transfer')
                transfers.receive(c,self.auth_ctx,route,transfer,self)
                if changed:
                    stage=transitions.STATUS_STAGES['delivered']
                    c.execute("UPDATE shipments SET status=?,stage=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(delivered_status,stage,shipment['id']))
                    add_shipment_event(c,shipment['id'],delivered_status,stage,route['destination'],user['display_name'])
                return self.send_json({'ok':True,'shipments_updated':int(changed)}|transfers.receipt_details(c,route['id'],transfer['shipment_id']))
            if len(parts)==3 and parts[:2]==["api","routes"]:
                route=c.execute("SELECT * FROM route_runs WHERE id=?",(parts[2],)).fetchone()
                if not route: return self.send_json({"error":'الرحلة غير موجودة'},404)
                status=data.get("status")
                if status not in ('في الطريق','وصلت','ملغاة'): return self.send_json({"error":'حالة الرحلة غير صحيحة'},400)
                try: changed=transitions.check_route_transition(route,status)
                except ValueError as exc: return self.send_json({'error':str(exc),'code':'route_transition'},409)
                if not changed:
                    self._audit_pending=False
                    c.commit()
                    return self.send_json({'ok':True,'status':status,'shipments_updated':0})
                if status=='في الطريق': c.execute("UPDATE route_runs SET status=?,started_at=CURRENT_TIMESTAMP WHERE id=?",(status,route["id"]))
                elif status=='وصلت': c.execute("UPDATE route_runs SET status=?,arrived_at=CURRENT_TIMESTAMP WHERE id=?",(status,route["id"]))
                else:
                    c.execute("UPDATE route_runs SET status=? WHERE id=?",(status,route["id"]))
                    c.execute("UPDATE branch_notifications SET sent_at=CURRENT_TIMESTAMP,delivery='cancelled' WHERE route_id=? AND sent_at IS NULL",(route["id"],))
                shipments=c.execute("SELECT s.* FROM route_shipments rs JOIN shipments s ON s.id=rs.shipment_id WHERE rs.route_id=?",(route["id"],)).fetchall()
                transfers.advance(c,route,status,self.auth_ctx,self)
                shipments_updated=0
                for shipment in shipments:
                    if status=='وصلت': continue
                    if transitions.canonical(shipment["status"])=='delivered': continue
                    next_status='قيد النقل' if status=='في الطريق' else ('جاهز للتسليم' if status=='وصلت' else shipment["status"])
                    validate_shipment_transition(c,shipment,next_status,source="route")
                    shipments_updated+=1
                    stage=f"{status} · {route['code']}"
                    c.execute("UPDATE shipments SET status=?,stage=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(next_status,stage,shipment["id"]))
                    add_shipment_event(c,shipment["id"],next_status,stage,route["destination"] if status=='وصلت' else route["origin"],user["display_name"])
                if status=='وصلت' and route["driver_id"]:
                    c.execute("UPDATE drivers SET branch=?,location_text=?,status='متاح',updated_at=CURRENT_TIMESTAMP WHERE id=?",(route["destination"],f"فرع {route['destination']}",route["driver_id"]))
                elif status=='في الطريق' and route["driver_id"]:
                    c.execute("UPDATE drivers SET status='نشط',updated_at=CURRENT_TIMESTAMP WHERE id=?",(route["driver_id"],))
                elif status=='ملغاة':
                    if route["driver_id"]: c.execute("UPDATE drivers SET status='متاح',updated_at=CURRENT_TIMESTAMP WHERE id=?",(route["driver_id"],))
                    if route["vehicle_id"]:
                        set_vehicle_status(c,route["vehicle_id"],'متاح',user,reason=f"Route cancelled: {route['code']}",route_id=route["id"],driver_id=route["driver_id"])
                if status=='في الطريق' and route["vehicle_id"]:
                    set_vehicle_status(c,route["vehicle_id"],'في الطريق',user,reason=f"Route started: {route['code']}",route_id=route["id"],driver_id=route["driver_id"])
                if status=='وصلت' and route["vehicle_id"]:
                    set_vehicle_status(c,route["vehicle_id"],'متاح',user,reason=f"Route arrived: {route['code']}",route_id=route["id"],driver_id=route["driver_id"])
                return self.send_json({"ok":True,"status":status,"shipments_updated":shipments_updated})
            if path=="/api/drivers":
                required=["name","national_id","mobile","branch","location_text"]
                if any(not str(data.get(k," ")).strip() for k in required): return self.send_json({"error":'أكمل الاسم ورقم الهوية والجوال والفرع والموقع'},400)
                if not active_branch_reference(c,data["branch"]): return self.send_json({"error":"Select an active Ghazala branch or served city."},400)
                try:
                    cur=c.execute("INSERT INTO drivers(name,national_id,mobile,branch,status,location_text,latitude,longitude,is_demo) VALUES(?,?,?,?,?,?,?,?,0)",(data["name"],data["national_id"],data["mobile"],data["branch"],data.get("status",'متاح'),data["location_text"],data.get("latitude") or None,data.get("longitude") or None))
                except sqlite3.IntegrityError: return self.send_json({"error":'رقم الهوية مسجل مسبقاً'},409)
                return self.send_json(dict(c.execute("SELECT * FROM drivers WHERE id=?",(cur.lastrowid,)).fetchone()),201)
            if path=="/api/users":
                result=accounts.create_user(c,self.auth_ctx,data,password_hash,self)
                c.commit(); return self.send_json(result,201)
            if path=="/api/vehicles":
                plate=str(data.get("plate","")).strip(); kind=str(data.get("vehicle_type",'شاحنة نقل')).strip()
                try: capacity=float(data.get("capacity_kg",0))
                except (TypeError,ValueError): capacity=0
                if not plate or capacity<=0: return self.send_json({"error":'أدخل رقم اللوحة وسعة المركبة الصحيحة'},400)
                try: cur=c.execute("INSERT INTO vehicles(plate,vehicle_type,capacity_kg,status) VALUES(?,?,?,?)",(plate,kind,capacity,data.get("status",'متاح')))
                except sqlite3.IntegrityError: return self.send_json({"error":'رقم اللوحة مسجل مسبقاً'},409)
                return self.send_json(dict(c.execute("SELECT * FROM vehicles WHERE id=?",(cur.lastrowid,)).fetchone()),201)
            if path=="/api/branches":
                code=str(data.get("code","")).strip().upper(); name=str(data.get("name","")).strip(); city=str(data.get("city","")).strip()
                address=str(data.get("address","")).strip(); phone=str(data.get("phone","")).strip(); coverage=str(data.get("coverage",city)).strip()
                if not code or not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,31}",code):
                    return self.send_json({"error":"Branch code must use 2-32 letters, numbers or hyphens."},400)
                if not name or not city:
                    return self.send_json({"error":"Branch name and city are required."},400)
                if len(name)>160 or len(city)>120 or len(address)>1000 or len(phone)>60 or len(coverage)>1000:
                    return self.send_json({"error":"A branch field exceeds the allowed size."},400)
                try: cur=c.execute("INSERT INTO branches(code,name,city,address,phone,coverage) VALUES(?,?,?,?,?,?)",(code,name,city,address,phone,coverage))
                except sqlite3.IntegrityError: return self.send_json({"error":'رمز الفرع مستخدم مسبقاً'},409)
                return self.send_json(dict(c.execute("SELECT * FROM branches WHERE id=?",(cur.lastrowid,)).fetchone()),201)
            if path=="/api/clients":
                name=str(data.get("name"," ")).strip(); mobile=str(data.get("mobile"," ")).strip()
                client_type=str(data.get("client_type","company")).strip(); city=str(data.get("city","")).strip()
                if not name or len(name)>160 or not mobile or len(mobile)>40: return self.send_json({"error":'أدخل اسم العميل ورقم جوال صحيحاً'},400)
                if client_type not in ("company","individual") or not active_branch_for_city(c,city): return self.send_json({"error":"Select a valid client type and an active served city."},400)
                try:
                    credit_limit=float(data.get("credit_limit",0) or 0); discount=float(data.get("discount_percent",0) or 0)
                except (TypeError,ValueError): return self.send_json({"error":'تحقق من حد الائتمان والخصم'},400)
                if not 0<=credit_limit<=100000000 or not 0<=discount<=100: return self.send_json({"error":'قيمة حد الائتمان أو الخصم خارج النطاق'},400)
                code=str(data.get("code","")).strip().upper() or f"CL-{secrets.token_hex(3).upper()}"
                values=(code,name,client_type,mobile,str(data.get("email","")).strip(),str(data.get("national_id","")).strip(),
                  str(data.get("commercial_registration","")).strip(),city,str(data.get("address","")).strip(),
                  str(data.get("status",'نشط')).strip(),str(data.get("payment_terms",'حسب الاتفاق')).strip(),credit_limit,discount,str(data.get("notes","")).strip())
                if values[9] not in ('نشط','معلق','يحتاج تجديد'): return self.send_json({"error":'حالة حساب العميل غير صالحة'},400)
                try: cur=c.execute("""INSERT INTO clients(code,name,client_type,mobile,email,national_id,commercial_registration,city,address,status,payment_terms,credit_limit,discount_percent,notes,is_demo)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",values)
                except sqlite3.IntegrityError: return self.send_json({"error":'رمز العميل مسجل مسبقاً'},409)
                return self.send_json(dict(c.execute("SELECT * FROM clients WHERE id=?",(cur.lastrowid,)).fetchone()),201)
            if path=="/api/campaigns":
                name=str(data.get("name","")).strip(); campaign_type=str(data.get("campaign_type",'خصم')).strip()
                status=str(data.get("status",'مسودة')).strip(); channels=normalize_campaign_channels(data.get("channels",'التطبيق'))
                try: discount=float(data.get("discount_percent",0) or 0)
                except (TypeError,ValueError): return self.send_json({"error":'أدخل نسبة خصم صحيحة'},400)
                if not name or len(name)>160 or campaign_type not in ('خصم','قسيمة','إشعار Push','رسالة SMS'):
                    return self.send_json({"error":'أدخل اسم الحملة واختر نوعاً صحيحاً'},400)
                if status not in ('مسودة','مجدولة','نشطة','متوقفة','منتهية') or not 0<=discount<=100:
                    return self.send_json({"error":'تحقق من حالة الحملة ونسبة الخصم'},400)
                start_at=str(data.get("start_at","")).strip(); end_at=str(data.get("end_at","")).strip()
                try: validate_campaign_dates(start_at,end_at)
                except ValueError as exc: return self.send_json({"error":str(exc)},400)
                code=str(data.get("code","")).strip().upper() or f"GZ-{secrets.token_hex(3).upper()}"
                try: cur=c.execute("""INSERT INTO campaigns(code,name,campaign_type,status,discount_percent,channels,target_segment,message,start_at,end_at,is_demo)
                  VALUES(?,?,?,?,?,?,?,?,?,?,0)""",(code,name,campaign_type,status,discount,channels,
                  str(data.get("target_segment",'جميع العملاء')).strip(),str(data.get("message","")).strip(),
                  start_at,end_at))
                except sqlite3.IntegrityError: return self.send_json({"error":'رمز الحملة مستخدم مسبقاً'},409)
                try:
                    settings=campaign_settings_fields(c,ctx,data,creating=True)
                    if settings:
                        c.execute(
                            "UPDATE campaigns SET "+",".join(key+"=?" for key in settings)+
                            ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            [*settings.values(),cur.lastrowid]
                        )
                except (ValueError,auth.AccessDenied):
                    c.execute("DELETE FROM campaigns WHERE id=?",(cur.lastrowid,))
                    raise
                row=campaign_rows(c,cur.lastrowid)
                return self.send_json(row,201)
            if path=="/api/admin/reset-demo":
                c.execute("INSERT INTO app_settings(key,value) VALUES('demo_data_disabled','1') ON CONFLICT(key) DO UPDATE SET value='1',updated_at=CURRENT_TIMESTAMP")
                shipments=c.execute("DELETE FROM shipments WHERE is_demo=1").rowcount
                drivers=c.execute("""DELETE FROM drivers WHERE is_demo=1 AND user_id IS NULL
                  AND NOT EXISTS(SELECT 1 FROM shipments s WHERE s.driver_id=drivers.id)
                  AND NOT EXISTS(SELECT 1 FROM route_runs r WHERE r.driver_id=drivers.id)
                  AND NOT EXISTS(SELECT 1 FROM users u WHERE u.driver_id=drivers.id)""").rowcount
                clients=c.execute("DELETE FROM clients WHERE is_demo=1").rowcount
                campaigns=c.execute("DELETE FROM campaigns WHERE is_demo=1").rowcount
                return self.send_json({"ok":True,"shipments_removed":shipments,"drivers_removed":drivers,"clients_removed":clients,"campaigns_removed":campaigns})
        return self.send_json({"error":"Not found"},404)

    def _patch(self):
        parts=[unquote(p) for p in urlparse(self.path).path.split("/") if p]; data=self.read_json()
        with connect() as c:
            c.execute("BEGIN IMMEDIATE")
            user=self.current_user(c)
            if not user: return self.unauthorized()
            if parts==['api','customer','profile']:
                result=customers.update_profile(c,user,data,self)
                c.commit(); return self.send_json(result)
            if parts==['api','customer','commercial-profile']:
                result=update_customer_business_profile(c,user,data,self)
                c.commit(); return self.send_json(result)
            if parts in (['api','customer','notification-preferences'],['api','notifications','preferences']):
                ctx=auth.context(c,user)
                if parts[1]=='customer': customers.require_customer(c,user)
                try: result=update_notification_preferences(c,user['id'],data)
                except ValueError as exc: return self.send_json({'error':str(exc)},400)
                result["providers"]=notification_provider_status()
                c.commit(); return self.send_json(result)
            if auth.context(c,user)['role']=='customer': return self.forbidden()
            ctx=auth.context(c,user)
            if parts==["api","pricing"]:
                if not auth.allowed(ctx,'pricing.manage'):
                    raise auth.AccessDenied("You do not have permission to manage pricing.")
                limits={"base_fee":(0,100000),"included_weight":(0,1000),"extra_kg_fee":(0,10000),"vat_rate":(0,1),"cod_fee":(0,10000),"insurance_rate":(0,1),"insurance_minimum":(0,10000)}
                updates={}
                settings=data.get("settings") if isinstance(data.get("settings"),dict) else data
                try:
                    for key,(low,high) in limits.items():
                        if key in settings:
                            value=float(settings[key])
                            if not low<=value<=high: raise ValueError(key)
                            updates[key]=value
                except (TypeError,ValueError):
                    return self.send_json({"error":'تحقق من قيم التعرفة المدخلة'},400)

                size_updates=data.get("sizes")
                if size_updates is not None and not isinstance(size_updates,list):
                    return self.send_json({"error":"Pricing sizes must be a list."},400)
                if not updates and size_updates is None:
                    return self.send_json({"error":'لا توجد قيم لتحديثها'},400)

                for key,value in updates.items():
                    c.execute(
                        "INSERT INTO service_settings(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key,str(value))
                    )

                if size_updates is not None:
                    for item in size_updates:
                        if not isinstance(item,dict):
                            return self.send_json({"error":"Invalid pricing size row."},400)
                        code=str(item.get("code","")).strip().upper()
                        label_en=str(item.get("label_en") or code).strip()
                        label_ar=str(item.get("label_ar") or "").strip()
                        examples_en=str(item.get("examples_en") or "").strip()
                        examples_ar=str(item.get("examples_ar") or "").strip()
                        if not re.fullmatch(r"[A-Z0-9+_-]{1,20}",code):
                            return self.send_json({"error":"Use a short valid pricing size code."},400)
                        if not label_en or len(label_en)>120 or len(label_ar)>120:
                            return self.send_json({"error":"Check the pricing size labels."},400)
                        if len(examples_en)>1000 or len(examples_ar)>1000:
                            return self.send_json({"error":"Pricing example text is too long."},400)
                        try:
                            length=float(item.get("length_cm",0))
                            width=float(item.get("width_cm",0))
                            height=float(item.get("height_cm",0))
                            fee=float(item.get("base_fee",0))
                            sort_order=int(item.get("sort_order",0) or 0)
                            active=1 if bool(item.get("is_active",True)) else 0
                            manual_only=1 if bool(item.get("manual_only",False)) else 0
                            if not all(math.isfinite(value) and 0<value<=5000 for value in (length,width,height)):
                                raise ValueError("dimensions")
                            if not math.isfinite(fee) or not 0<=fee<=1000000:
                                raise ValueError("fee")
                            if not -100000<=sort_order<=100000:
                                raise ValueError("sort")
                        except (TypeError,ValueError,OverflowError):
                            return self.send_json({"error":"Check size dimensions, price and order."},400)

                        row_id=item.get("id")
                        if row_id not in (None,""):
                            if not c.execute("SELECT id FROM pricing_sizes WHERE id=?",(row_id,)).fetchone():
                                return self.send_json({"error":"Pricing size was not found."},404)
                            try:
                                c.execute(
                                    """UPDATE pricing_sizes
                                       SET code=?,label_en=?,label_ar=?,length_cm=?,width_cm=?,height_cm=?,
                                           examples_en=?,examples_ar=?,base_fee=?,is_active=?,manual_only=?,
                                           sort_order=?,updated_at=CURRENT_TIMESTAMP
                                       WHERE id=?""",
                                    (code,label_en,label_ar,length,width,height,examples_en,examples_ar,
                                     fee,active,manual_only,sort_order,row_id)
                                )
                            except sqlite3.IntegrityError:
                                return self.send_json({"error":"Pricing size code is already in use."},409)
                        else:
                            try:
                                c.execute(
                                    """INSERT INTO pricing_sizes(
                                         code,label_en,label_ar,length_cm,width_cm,height_cm,
                                         examples_en,examples_ar,base_fee,is_active,manual_only,sort_order
                                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                                    (code,label_en,label_ar,length,width,height,examples_en,examples_ar,
                                     fee,active,manual_only,sort_order)
                                )
                            except sqlite3.IntegrityError:
                                return self.send_json({"error":"Pricing size code is already in use."},409)

                write_audit(
                    c,ctx,"pricing.updated","pricing","catalog",
                    metadata={
                        "settings":sorted(updates),
                        "sizes_count":len(size_updates) if isinstance(size_updates,list) else 0,
                    },
                    request=self
                )
                result=pricing_payload(c)
                c.commit()
                return self.send_json(result)
            if len(parts)==3 and parts[:2]==['api','vehicles']:
                if not auth.allowed(ctx,'vehicles.manage'):
                    raise auth.AccessDenied("You do not have permission to manage vehicles.")
                vehicle=fleet_vehicle_scoped(c,ctx,parts[2])
                vehicle_id=vehicle["id"]
                fields=vehicle_fields(data,creating=False)
                branches=vehicle_branch_ids(c,ctx,data) if "branch_ids" in data else None
                reason=_fleet_text(data.get("status_reason"),1000,"Status reason")
                if not fields and branches is None:
                    return self.send_json({"error":"No vehicle changes were supplied."},400)

                before=dict(vehicle)
                status=fields.pop("status",None)
                if "odometer_km" in fields and fields["odometer_km"]+1e-9<float(vehicle["odometer_km"] or 0):
                    return self.send_json({"error":"Odometer cannot move backwards."},409)
                if fields.get("is_active") == 0:
                    active_route=c.execute(
                        "SELECT id FROM route_runs WHERE vehicle_id=? AND status NOT IN ('وصلت','ملغاة') LIMIT 1",
                        (vehicle_id,)
                    ).fetchone()
                    if active_route:
                        return self.send_json({"error":"A vehicle assigned to an active route cannot be deactivated."},409)
                    if status is None:
                        status="خارج الخدمة"

                if fields:
                    try:
                        c.execute(
                            "UPDATE vehicles SET "+",".join(key+"=?" for key in fields)+
                            ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            [*fields.values(),vehicle_id]
                        )
                    except sqlite3.IntegrityError:
                        return self.send_json({"error":"Vehicle plate or VIN is already in use."},409)
                if status is not None:
                    set_vehicle_status(
                        c,vehicle_id,status,user,reason=reason or "Vehicle status updated",
                        odometer_km=fields.get("odometer_km")
                    )
                if branches is not None:
                    persist_fleet_vehicle_branches(c,vehicle_id,branches)
                result=vehicle_fleet_payload(c,ctx,vehicle_id)
                write_audit(
                    c,ctx,"vehicle.updated","vehicle",vehicle_id,
                    before={key:before.get(key) for key in (
                        "plate","vehicle_type","capacity_kg","status","odometer_km","is_active"
                    )},
                    after={key:result.get(key) for key in (
                        "plate","vehicle_type","capacity_kg","status","odometer_km","is_active"
                    )},
                    metadata={"branch_ids":result.get("branch_ids",[])},request=self
                )
                c.commit()
                return self.send_json(result)

            if len(parts)==5 and parts[:2]==['api','vehicles'] and parts[3]=='maintenance':
                if not auth.allowed(ctx,'vehicles.manage'):
                    raise auth.AccessDenied("You do not have permission to manage vehicles.")
                vehicle=fleet_vehicle_scoped(c,ctx,parts[2])
                try: maintenance_id=int(parts[4])
                except ValueError: return self.send_json({"error":"Maintenance record not found."},404)
                record=c.execute(
                    "SELECT * FROM vehicle_maintenance WHERE id=? AND vehicle_id=?",
                    (maintenance_id,vehicle["id"])
                ).fetchone()
                if not record:
                    return self.send_json({"error":"Maintenance record not found."},404)
                allowed={
                    "status","description","scheduled_at","completed_at","odometer_km","cost",
                    "vendor","next_due_at","next_due_km","notes"
                }
                if not isinstance(data,dict) or not data or set(data)-allowed:
                    return self.send_json({"error":"Unsupported maintenance update fields."},400)
                fields={}
                if "status" in data:
                    status=str(data.get("status") or "").strip().lower()
                    if status not in ("scheduled","in_progress","completed","cancelled"):
                        return self.send_json({"error":"Select a valid maintenance status."},400)
                    fields["status"]=status
                for key,label,limit in (
                    ("description","Maintenance description",2000),
                    ("vendor","Maintenance vendor",240),
                    ("notes","Maintenance notes",2000),
                ):
                    if key in data: fields[key]=_fleet_text(data.get(key),limit,label)
                for key,label in (
                    ("scheduled_at","Scheduled maintenance date"),
                    ("completed_at","Maintenance completion date"),
                    ("next_due_at","Next maintenance date"),
                ):
                    if key in data: fields[key]=_fleet_date(data.get(key),label) or None
                for key,label,max_value in (
                    ("odometer_km","Maintenance odometer",20_000_000),
                    ("next_due_km","Next maintenance odometer",20_000_000),
                    ("cost","Maintenance cost",100_000_000),
                ):
                    if key in data:
                        fields[key]=_fleet_number(data.get(key),label,0,max_value,allow_none=(key!="cost"))
                if fields.get("status")=="completed" and "completed_at" not in fields:
                    fields["completed_at"]=datetime.now(timezone.utc).isoformat(timespec="minutes")
                if fields.get("odometer_km") is not None and fields["odometer_km"]+1e-9<float(vehicle["odometer_km"] or 0):
                    return self.send_json({"error":"Maintenance odometer cannot be lower than the vehicle odometer."},409)
                c.execute(
                    "UPDATE vehicle_maintenance SET "+",".join(key+"=?" for key in fields)+
                    ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    [*fields.values(),maintenance_id]
                )
                if fields.get("odometer_km") is not None:
                    c.execute(
                        "UPDATE vehicles SET odometer_km=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (fields["odometer_km"],vehicle["id"])
                    )
                new_status=fields.get("status")
                if new_status=="in_progress":
                    set_vehicle_status(
                        c,vehicle["id"],"صيانة",user,
                        reason=f"Maintenance: {record['maintenance_type']}",
                        odometer_km=fields.get("odometer_km")
                    )
                elif new_status in ("completed","cancelled"):
                    # Release the vehicle only when there is no other active maintenance.
                    other_active=c.execute(
                        """SELECT 1 FROM vehicle_maintenance
                           WHERE vehicle_id=? AND id<>? AND status='in_progress'
                           LIMIT 1""",
                        (vehicle["id"],maintenance_id)
                    ).fetchone()
                    if not other_active:
                        active_route=c.execute(
                            """SELECT id,driver_id FROM route_runs
                               WHERE vehicle_id=? AND status NOT IN ('وصلت','ملغاة')
                               ORDER BY id DESC LIMIT 1""",
                            (vehicle["id"],)
                        ).fetchone()
                        next_vehicle_status="في الطريق" if active_route else "متاح"
                        reason_text=(
                            f"Maintenance completed: {record['maintenance_type']}"
                            if new_status=="completed"
                            else f"Maintenance cancelled: {record['maintenance_type']}"
                        )
                        set_vehicle_status(
                            c,vehicle["id"],next_vehicle_status,user,
                            reason=reason_text,
                            route_id=active_route["id"] if active_route else None,
                            driver_id=active_route["driver_id"] if active_route else None,
                            odometer_km=fields.get("odometer_km")
                        )
                write_audit(
                    c,ctx,"vehicle.maintenance_updated","vehicle",vehicle["id"],
                    metadata={"maintenance_id":maintenance_id,"fields":sorted(fields)},request=self
                )
                result=dict(c.execute("SELECT * FROM vehicle_maintenance WHERE id=?",(maintenance_id,)).fetchone())
                c.commit()
                return self.send_json(result)

            if len(parts)==3 and parts[:2]==['api','campaigns']:
                if not auth.allowed(ctx,'campaigns.manage'):
                    raise auth.AccessDenied("You do not have permission to manage campaigns.")
                try: campaign_id=int(parts[2])
                except ValueError: return self.send_json({"error":"Campaign not found."},404)
                existing=c.execute("SELECT * FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
                if not existing:
                    return self.send_json({"error":"Campaign not found."},404)
                allowed={
                    "name","campaign_type","status","discount_percent","channels",
                    "target_segment","message","start_at","end_at",
                    "placement","coupon_code","max_redemptions","per_customer_limit",
                    "min_order_amount","max_discount_amount","branch_id","auto_expire"
                }
                if not isinstance(data,dict) or not data or set(data)-allowed:
                    return self.send_json({"error":"Unsupported campaign fields."},400)
                fields={k:v for k,v in data.items() if k in {
                    "name","campaign_type","status","discount_percent","channels",
                    "target_segment","message","start_at","end_at"
                }}
                settings=campaign_settings_fields(c,ctx,data)
                if "name" in fields:
                    fields["name"]=str(fields["name"] or "").strip()
                    if not fields["name"] or len(fields["name"])>160:
                        return self.send_json({"error":"Campaign name is required and must be 160 characters or less."},400)
                if "campaign_type" in fields:
                    fields["campaign_type"]=str(fields["campaign_type"] or "").strip()
                    if fields["campaign_type"] not in ('خصم','قسيمة','إشعار Push','رسالة SMS'):
                        return self.send_json({"error":"Select a valid campaign type."},400)
                if "status" in fields:
                    fields["status"]=str(fields["status"] or "").strip()
                    if fields["status"] not in ('مسودة','مجدولة','نشطة','متوقفة','منتهية'):
                        return self.send_json({"error":"Select a valid campaign status."},400)
                if "discount_percent" in fields:
                    try: fields["discount_percent"]=float(fields["discount_percent"])
                    except (TypeError,ValueError):
                        return self.send_json({"error":"Enter a valid discount percentage."},400)
                    if not 0<=fields["discount_percent"]<=100:
                        return self.send_json({"error":"Discount percentage must be between 0 and 100."},400)
                if "channels" in fields:
                    fields["channels"]=normalize_campaign_channels(fields["channels"])
                for key,limit in (("target_segment",160),("message",2000)):
                    if key in fields:
                        fields[key]=str(fields[key] or "").strip()
                        if len(fields[key])>limit:
                            return self.send_json({"error":"Campaign audience or message is too long."},400)
                for key in ("start_at","end_at"):
                    if key in fields:
                        fields[key]=str(fields[key] or "").strip()
                validate_campaign_dates(
                    fields.get("start_at",existing["start_at"]),
                    fields.get("end_at",existing["end_at"])
                )
                combined={**fields,**settings}
                try:
                    c.execute(
                        "UPDATE campaigns SET "+",".join(key+"=?" for key in combined)+
                        ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        [*combined.values(),campaign_id]
                    )
                except sqlite3.IntegrityError:
                    return self.send_json({"error":"Campaign coupon code is already in use."},409)
                write_audit(
                    c,ctx,"campaign.updated","campaign",campaign_id,
                    metadata={"fields":sorted(combined)},request=self
                )
                result=campaign_rows(c,campaign_id)
                c.commit()
                return self.send_json(result)

            self.prepare_mutation(c,user,'PATCH',parts,data)
            if len(parts)==3 and parts[:2]==['api','users']:
                result=accounts.update_user(c,self.auth_ctx,parts[2],data,self,password_hash=password_hash)
                c.commit(); return self.send_json(result)
            if len(parts)==3 and parts[:2]==['api','branches']:
                branch=c.execute('SELECT * FROM branches WHERE id=?',(parts[2],)).fetchone()
                if not branch: return self.send_json({'error':'Branch not found.'},404)
                allowed={'name','address','phone','coverage','is_active'}
                if not data or set(data)-allowed: raise ValueError('Only branch name, address, phone, coverage and active status can be updated.')
                fields={}
                for key in ('name','address','phone','coverage'):
                    if key in data:
                        value=str(data.get(key,'')).strip()
                        if key=='name' and not value: raise ValueError('Branch name is required.')
                        if len(value)>(160 if key=='name' else 1000): raise ValueError('Branch field exceeds the size limit.')
                        fields[key]=value
                if 'is_active' in data:
                    raw=data.get('is_active')
                    if isinstance(raw,bool): active=1 if raw else 0
                    elif raw in (0,1,'0','1'): active=int(raw)
                    else: raise ValueError('Invalid branch active status.')
                    if not active and str(branch['code'] or '').upper()=='JED-MAIN':
                        return self.send_json({'error':'Jeddah HQ is the master branch and cannot be removed.','code':'master_branch_protected'},409)
                    if not active and int(branch['is_active'] or 0)!=0:
                        active_shipments=0
                        for item in c.execute(
                            '''SELECT s.status FROM shipment_scope ss JOIN shipments s ON s.id=ss.shipment_id
                               WHERE ss.origin_branch_id=? OR ss.destination_branch_id=?''',
                            (parts[2],parts[2])
                        ).fetchall():
                            if transitions.canonical(item['status'])!='delivered':
                                active_shipments+=1
                        active_routes=c.execute(
                            '''SELECT COUNT(*) FROM route_scope rs JOIN route_runs r ON r.id=rs.route_id
                               WHERE (rs.origin_branch_id=? OR rs.destination_branch_id=?)
                                 AND r.status IN ('مجدولة','في الطريق')''',
                            (parts[2],parts[2])
                        ).fetchone()[0]
                        active_pickups=c.execute(
                            '''SELECT COUNT(*) FROM pickup_requests
                               WHERE branch_id=? AND status IN ('requested','assigned','picked_up')''',
                            (parts[2],)
                        ).fetchone()[0]
                        if active_shipments or active_routes or active_pickups:
                            return self.send_json({
                                'error':'This branch cannot be deactivated while active shipments, routes or pickup tasks are linked to it.',
                                'code':'branch_active_dependencies',
                                'active_shipments':int(active_shipments),
                                'active_routes':int(active_routes),
                                'active_pickups':int(active_pickups),
                            },409)
                    fields['is_active']=active
                if not fields: return self.send_json({'error':'No branch changes were provided.'},400)
                c.execute('UPDATE branches SET '+','.join(key+'=?' for key in fields)+' WHERE id=?',[*fields.values(),parts[2]])
                return self.send_json(dict(c.execute('SELECT * FROM branches WHERE id=?',(parts[2],)).fetchone()))
            if len(parts)==3 and parts[:2]==["api","clients"]:
                fields={k:v for k,v in data.items() if k in {"name","client_type","mobile","email","national_id","commercial_registration","city","address","status","payment_terms","credit_limit","discount_percent","notes"}}
                if 'branch_id' in data:
                    fields['city']=c.execute('SELECT city FROM branches WHERE id=?',(self.mutation_plan['branch_id'],)).fetchone()['city']
                if not fields: return self.send_json({"error":'لا توجد تغييرات'},400)
                if "status" in fields and fields["status"] not in ('نشط','معلق','يحتاج تجديد'): return self.send_json({"error":'حالة حساب العميل غير صالحة'},400)
                if "client_type" in fields and fields["client_type"] not in ("company","individual"): return self.send_json({"error":'نوع العميل غير صالح'},400)
                if "city" in fields and not active_branch_for_city(c,str(fields["city"]).strip()): return self.send_json({"error":"Select an active served city."},400)
                try:
                    for key in ("credit_limit","discount_percent"):
                        if key in fields:
                            fields[key]=float(fields[key])
                            if not 0<=fields[key]<=(100000000 if key=="credit_limit" else 100): raise ValueError(key)
                except (TypeError,ValueError): return self.send_json({"error":'قيمة حد الائتمان أو الخصم خارج النطاق'},400)
                assignments=",".join(f"{key}=?" for key in fields)
                cur=c.execute(f"UPDATE clients SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=?",[*fields.values(),parts[2]])
                row=c.execute("SELECT * FROM clients WHERE id=?",(parts[2],)).fetchone()
                return self.send_json(dict(row) if row else {"error":"Client not found"},200 if row else 404)
            if len(parts)==3 and parts[:2]==["api","campaigns"]:
                existing=c.execute("SELECT * FROM campaigns WHERE id=?",(parts[2],)).fetchone()
                if not existing: return self.send_json({"error":"Campaign not found"},404)
                fields={k:v for k,v in data.items() if k in {"name","campaign_type","status","discount_percent","channels","target_segment","message","start_at","end_at"}}
                settings=campaign_settings_fields(c,self.auth_ctx,data)
                if not fields and not settings: return self.send_json({"error":'لا توجد تغييرات'},400)
                if "status" in fields and fields["status"] not in ('مسودة','مجدولة','نشطة','متوقفة','منتهية'): return self.send_json({"error":'حالة الحملة غير صالحة'},400)
                if "campaign_type" in fields and fields["campaign_type"] not in ('خصم','قسيمة','إشعار Push','رسالة SMS'): return self.send_json({"error":'نوع الحملة غير صالح'},400)
                if "discount_percent" in fields:
                    try: fields["discount_percent"]=float(fields["discount_percent"])
                    except (TypeError,ValueError): return self.send_json({"error":'نسبة الخصم غير صالحة'},400)
                    if not 0<=fields["discount_percent"]<=100: return self.send_json({"error":'نسبة الخصم خارج النطاق'},400)
                if "channels" in fields:
                    fields["channels"]=normalize_campaign_channels(fields["channels"])
                for key in ("start_at","end_at"):
                    if key in fields: fields[key]=str(fields[key] or "").strip()
                try: validate_campaign_dates(fields.get("start_at",existing["start_at"]),fields.get("end_at",existing["end_at"]))
                except ValueError as exc: return self.send_json({"error":str(exc)},400)
                combined={**fields,**settings}
                assignments=",".join(f"{key}=?" for key in combined)
                try:
                    c.execute(f"UPDATE campaigns SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=?",[*combined.values(),parts[2]])
                except sqlite3.IntegrityError:
                    return self.send_json({"error":"Campaign coupon code is already in use."},409)
                row=campaign_rows(c,parts[2])
                return self.send_json(row)
            if len(parts)==3 and parts[:2]==["api","shipments"]:
                awb=parts[2]; row=c.execute("SELECT * FROM shipments WHERE awb=?",(awb,)).fetchone()
                if not row: return self.send_json({"error":"Shipment not found"},404)
                if transitions.canonical(row['status'])=='delivered' and any(key in data and data[key]!=row[key] for key in ('driver_id','eta')):
                    return self.send_json({'error':'Completed delivery assignment and ETA cannot be changed.'},409)
                updates=[]; values=[]
                if "status" in data:
                    data['status']=transitions.storage_status(data['status'])
                    allowed={transitions.STATUS_NAMES[key]:stage for key,stage in transitions.STATUS_STAGES.items()}
                    if data["status"] not in allowed: return self.send_json({"error":"Invalid status"},400)
                    target_canonical=transitions.canonical(data["status"])
                    try: changed=validate_shipment_transition(c,row,data["status"])
                    except DeliveryPolicyError as exc: return self.send_json({"error":str(exc),"code":"delivery_policy"},409)
                    if changed:
                        updates.extend(["status=?","stage=?"]); values.extend([data["status"],allowed[data["status"]]])
                if "eta" in data: updates.append("eta=?"); values.append(str(data["eta"]).strip())
                if "driver_id" in data:
                    did=data["driver_id"] or None
                    if did and not c.execute("SELECT id FROM drivers WHERE id=?",(did,)).fetchone(): return self.send_json({"error":'السائق المحدد غير موجود'},400)
                    updates.append("driver_id=?"); values.append(did)
                if "payment_status" in data:
                    allowed_payments={"sender":{'بانتظار الدفع','مدفوع'},"cod":{'مستحق عند التسليم','تم التحصيل عند التسليم'},"company":{'على حساب الشركة','مدفوع'}}
                    if data["payment_status"] not in allowed_payments.get(row["payment_method"],set()): return self.send_json({"error":'حالة الدفع غير صالحة لطريقة الدفع المحددة'},400)
                    updates.append("payment_status=?"); values.append(data["payment_status"])
                if not updates:
                    if 'status' in data and transitions.canonical(data['status'])==transitions.canonical(row['status']):
                        return self.send_json(dict(c.execute(shipment_query()+" WHERE s.awb=?",(awb,)).fetchone()))
                    return self.send_json({"error":'لا توجد تغييرات'},400)
                updates.append("updated_at=CURRENT_TIMESTAMP"); values.append(awb)
                c.execute(f"UPDATE shipments SET {','.join(updates)} WHERE awb=?",values)
                if "status" in data and data["status"] != row["status"]:
                    updated=c.execute(shipment_query()+" WHERE s.awb=?",(awb,)).fetchone()
                    canonical=transitions.canonical(data["status"])
                    if canonical in {"created","received","at_origin","dispatched"}:
                        location=updated["origin"]
                    elif canonical in {"at_destination","out_for_delivery","delivered"}:
                        location=updated["destination"]
                    elif canonical=="in_transit":
                        location=updated["driver_location"] or updated["operational_location"] or updated["origin"]
                    else:
                        location=updated["operational_location"] or updated["driver_location"] or updated["destination"] or updated["origin"]
                    add_shipment_event(c,row["id"],data["status"],allowed[data["status"]],location,user["display_name"])
                if "payment_status" in data and data["payment_status"] != row["payment_status"]:
                    add_shipment_event(c,row["id"],data["payment_status"],f"تحديث الدفع · {row['awb']}",row["origin"],user["display_name"])
                    invoice_row=c.execute("SELECT * FROM invoices WHERE shipment_id=?",(row["id"],)).fetchone()
                    if invoice_row and data["payment_status"] in ('مدفوع','تم التحصيل عند التسليم') and invoice_row["status"]!="paid":
                        invoice=recalculate_invoice(c,invoice_row["id"])
                        balance=float(invoice["balance"] or 0)
                        if balance>0.005:
                            payment_number="PMT-"+uuid.uuid4().hex[:10].upper()
                            c.execute(
                                """INSERT INTO payments(
                                     payment_number,invoice_id,customer_user_id,amount,currency,method,status,
                                     reference,provider,recorded_by_user_id,note,paid_at
                                   ) VALUES(?,?,?,?,?,'other','paid',?,'shipment_status',?,?,CURRENT_TIMESTAMP)""",
                                (
                                    payment_number,invoice["id"],invoice["customer_user_id"],round(balance,2),
                                    invoice["currency"],row["awb"],user["id"],
                                    "Payment completed through shipment payment-status update."
                                )
                            )
                            recalculate_invoice(c,invoice["id"])
                return self.send_json(dict(c.execute(shipment_query()+" WHERE s.awb=?",(awb,)).fetchone()))
            if len(parts)==4 and parts[:2]==["api","drivers"] and parts[3]=="location":
                did=parts[2]; driver=c.execute("SELECT * FROM drivers WHERE id=?",(did,)).fetchone()
                if not driver: return self.send_json({"error":"Driver not found"},404)
                location=str(data.get("location_text","")).strip()
                if not location: return self.send_json({"error":'أدخل وصف الموقع الحالي'},400)
                try: latitude,longitude=validate_coordinates(data.get("latitude"),data.get("longitude"))
                except ValueError as exc: return self.send_json({"error":str(exc)},400)
                c.execute("UPDATE drivers SET location_text=?,latitude=?,longitude=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(location,latitude,longitude,did))
                return self.send_json(dict(c.execute("SELECT * FROM drivers WHERE id=?",(did,)).fetchone()))
            if len(parts)==3 and parts[:2]==["api","drivers"]:
                did=parts[2]; allowed={"name","national_id","mobile","branch","status","location_text","latitude","longitude"}
                fields={k:v for k,v in data.items() if k in allowed}
                if 'branch_id' in data:
                    fields['branch']=c.execute('SELECT city FROM branches WHERE id=?',(self.mutation_plan['branch_id'],)).fetchone()['city']
                if not fields: return self.send_json({"error":'لا توجد تغييرات'},400)
                if "branch" in fields and not active_branch_reference(c,fields["branch"]): return self.send_json({"error":"Select an active Ghazala branch or served city."},400)
                if "latitude" in fields or "longitude" in fields:
                    existing=c.execute("SELECT latitude,longitude FROM drivers WHERE id=?",(did,)).fetchone()
                    if not existing: return self.send_json({"error":"Driver not found"},404)
                    try:
                        fields["latitude"],fields["longitude"]=validate_coordinates(fields.get("latitude",existing["latitude"]),fields.get("longitude",existing["longitude"]))
                    except ValueError as exc: return self.send_json({"error":str(exc)},400)
                fields["updated_at"]=None; assignments=",".join(f"{k}=?" if k!="updated_at" else "updated_at=CURRENT_TIMESTAMP" for k in fields)
                vals=[v for k,v in fields.items() if k!="updated_at"]+[did]
                c.execute(f"UPDATE drivers SET {assignments} WHERE id=?",vals); row=c.execute("SELECT * FROM drivers WHERE id=?",(did,)).fetchone()
                return self.send_json(dict(row) if row else {"error":"Driver not found"},200 if row else 404)
        return self.send_json({"error":"Not found"},404)

    def log_message(self, *_): pass

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Run the Ghazala Transport portal")
    render_port=os.environ.get("PORT")
    default_host="0.0.0.0" if render_port else "127.0.0.1"
    default_port=int(render_port or 8000)
    parser.add_argument("--host",default=default_host,help="Use 0.0.0.0 for network/hosted access")
    parser.add_argument("--port",type=int,default=default_port)
    args=parser.parse_args(); init_db()
    threading.Thread(target=notification_worker,daemon=True,name="route-notification-worker").start()
    print(f"Ghazala Transport running on {args.host}:{args.port}")
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
