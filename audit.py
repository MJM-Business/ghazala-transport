"""Sanitized append-only audit inserts. The caller owns the transaction."""
from collections.abc import Mapping
from datetime import date, datetime
import ipaddress
import json
import math
import re
from urllib.parse import urlsplit
import uuid

from authorization import canonical_role

_SENSITIVE = re.compile(
    r"password|passwd|pwd|secret|token|session|otp|credential|apikey|authorization|"
    r"signature|photo|image|nationalid|recipientid|senderid|identitynumber|idnumber|"
    r"phone|mobile|telephone|email|username|codehash|passwordhash|verificationcode|democode|hash",
    re.IGNORECASE,
)
_CONTACT = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|(?<!\w)(?:\+\d[\d ()-]{6,}\d|\d{10,15})(?!\w)")
_INLINE_SECRET = re.compile(r"\b(password|passwd|token|secret|otp|verification_code)\s*[:=]\s*[^\s,;]+", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,100}\Z")


def _text(value, limit=2048):
    value = str(value or "")
    if len(value) > limit:
        return "[large value omitted]"
    if value.lstrip().lower().startswith(("data:image/", "data:application/octet-stream")):
        return "[binary omitted]"
    value = _CONTROL.sub("", value)
    value = _CONTACT.sub("[contact redacted]", value)
    return _INLINE_SECRET.sub(lambda match: match.group(1) + "=[redacted]", value)


def sanitize(value, _depth=0):
    """Remove sensitive keys recursively; omit binary/oversized payloads.

    Identifiers such as a failed-login identifier_digest are permitted; raw
    usernames, contact fields and credentials are never retained as keys.
    """
    if _depth > 8:
        return "[nested value omitted]"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "[binary omitted]"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping) or hasattr(value, "keys"):
        mapping = dict(value)
        # Some change summaries encode a column name separately from its value.
        # Redact the entire sensitive change object rather than trusting its
        # generic old/new/value keys to carry no credentials or evidence data.
        for field_key in ("field", "column", "attribute"):
            field = mapping.get(field_key)
            if isinstance(field, str) and _SENSITIVE.search(re.sub(r"[^A-Za-z0-9]", "", field)):
                return {field_key: "[sensitive field omitted]"}
        result = {}
        for key, item in list(mapping.items())[:200]:
            key = str(key)
            normalized = re.sub(r"[^A-Za-z0-9]", "", key)
            if _SENSITIVE.search(normalized):
                continue
            result[_text(key, 120)] = sanitize(item, _depth + 1)
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize(item, _depth + 1) for item in list(value)[:200]]
    return "[unsupported value omitted]"


def _request_fields(request):
    if request is None:
        return "", "", "", ""
    if isinstance(request, Mapping):
        request_id = request.get("request_id", "")
        method = request.get("method", request.get("request_method", ""))
        path = request.get("path", request.get("request_path", ""))
        address = request.get("ip", request.get("ip_address", ""))
    else:
        request_id = getattr(request, "audit_request_id", "")
        if not request_id:
            request_id = uuid.uuid4().hex
            try:
                request.audit_request_id = request_id
            except (AttributeError, TypeError):
                pass
        method = getattr(request, "command", "")
        path = getattr(request, "path", "")
        client = getattr(request, "client_address", ())
        address = client[0] if client else ""
    request_id = str(request_id or "")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", request_id):
        request_id = uuid.uuid4().hex
    method = str(method or "").upper()
    if not re.fullmatch(r"[A-Z]{1,12}", method):
        method = ""
    try:
        path = urlsplit(str(path or "")).path  # Queries can contain OTPs/tokens.
    except ValueError:
        path = ""
    try:
        address = str(ipaddress.ip_address(str(address)))
    except ValueError:
        address = ""
    return request_id, method, _text(path, 300), address


def write_audit(con, ctx, action, entity, entity_id=None, before=None, after=None,
                metadata=None, request=None, branch_id=None):
    """Append one event; return its ID. No commit, update or delete is performed.

    ctx is an authorization context. request accepts an HTTP handler or a dict
    containing request_id, method, path and ip. IP comes from the connection,
    never an untrusted forwarded header. Database triggers reject later edits.
    """
    action, entity = str(action), str(entity)
    if not _NAME.fullmatch(action) or not _NAME.fullmatch(entity):
        raise ValueError("Invalid audit action or entity type.")
    ctx = ctx or {}
    request_id, method, path, address = _request_fields(request)
    branch_id = branch_id if branch_id is not None else ctx.get("primary_branch_id")
    if branch_id is not None:
        if isinstance(branch_id, bool):
            raise ValueError("Invalid audit branch.")
        branch_id = int(branch_id)
    serialize = lambda value: json.dumps(sanitize(value if value is not None else {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    result = con.execute("""INSERT INTO audit_events(
        actor_user_id,actor_name,actor_role,branch_id,action,entity_type,entity_id,
        request_id,request_method,request_path,ip_address,before_json,after_json,metadata_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        ctx.get("user_id"), _text(ctx.get("actor_name", ""), 200), canonical_role(ctx.get("role")) if ctx.get("role") else "",
        branch_id, action, entity, str(entity_id)[:160] if entity_id is not None else None,
        request_id, method, path, address, serialize(before), serialize(after), serialize(metadata),
    ))
    return result.lastrowid


sanitize_audit = sanitize
