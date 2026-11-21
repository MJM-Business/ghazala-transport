"""Canonical roles and branch predicates. Callers own transactions and HTTP responses."""
import re

ROLES = ("system_admin", "branch_manager", "office_employee", "courier", "accountant", "customer")
ROLE_ALIASES = {"admin": "system_admin", "manager": "branch_manager", "employee": "courier"}
ROLE_ALIASES.update({role: role for role in ROLES})
LEGACY_ROLES = {role: "employee" for role in ROLES}
LEGACY_ROLES.update(system_admin="admin", branch_manager="manager")

PERMISSIONS = frozenset({
    "shipments.read", "shipments.create", "shipments.edit", "shipments.status",
    "shipments.assign", "shipments.payment", "drivers.read", "drivers.manage",
    "drivers.location", "routes.read", "routes.manage", "branches.read", "branches.manage",
    "clients.read", "clients.manage", "pricing.read", "pricing.manage", "campaigns.read",
    "campaigns.manage", "reports.read", "users.manage", "audit.read", "pod.read", "pod.create",
    "stats.read", "vehicles.read", "vehicles.manage", "demo.reset",
})
ROLE_PERMISSIONS = {
    "system_admin": PERMISSIONS,
    "branch_manager": frozenset({
        "shipments.read", "shipments.create", "shipments.edit", "shipments.status", "shipments.assign",
        "drivers.read", "drivers.manage", "drivers.location", "routes.read", "routes.manage",
        "branches.read", "clients.read", "clients.manage", "pricing.read", "campaigns.read", "shipments.payment",
        "reports.read", "pod.read", "pod.create", "stats.read", "vehicles.read",
    }),
    "office_employee": frozenset({
        "shipments.read", "shipments.create", "shipments.edit", "shipments.status", "shipments.assign", "drivers.read",
        "routes.read", "branches.read", "clients.read", "pricing.read", "campaigns.read",
        "pod.read", "pod.create", "stats.read", "vehicles.read",
    }),
    "courier": frozenset({
        "shipments.read", "shipments.status", "drivers.read", "drivers.location", "routes.read",
        "branches.read", "pod.read", "pod.create", "stats.read", "vehicles.read",
    }),
    "accountant": frozenset({
        "shipments.read", "shipments.payment", "branches.read", "clients.read", "pricing.read",
        "reports.read", "stats.read",
    }),
    "customer": frozenset(),
}

ENTITY_TABLES = {
    "shipments": "shipments", "drivers": "drivers", "routes": "route_runs",
    "branches": "branches", "clients": "clients", "vehicles": "vehicles",
    "notifications": "branch_notifications", "campaigns": "campaigns",
}
ENTITY_ALIASES = {**{key: key for key in ENTITY_TABLES},
                  **{key.rstrip("s"): key for key in ENTITY_TABLES},
                  "branch": "branches", "route_runs": "routes", "branch_notifications": "notifications"}


class AccessDenied(PermissionError):
    pass


def canonical_role(value):
    return ROLE_ALIASES.get(str(value or "").strip().lower(), "customer")


def legacy_role(value):
    """Value compatible with the unchanged users.role CHECK constraint."""
    return LEGACY_ROLES[canonical_role(value)]


def context(con, user):
    user = dict(user or {})
    user_id = user.get("id")
    access = con.execute("SELECT * FROM user_access WHERE user_id=?", (user_id,)).fetchone()
    access = dict(access) if access else {}
    role = canonical_role(access.get("role", user.get("role")))
    active = bool(user.get("is_active", 1))
    branch_ids = tuple(row[0] for row in con.execute("""SELECT ub.branch_id FROM user_branches ub
        JOIN branches b ON b.id=ub.branch_id WHERE ub.user_id=? AND b.is_active=1 ORDER BY ub.branch_id""", (user_id,)))
    # Preserve Phase 2: employee access comes only from drivers.user_id, never
    # an unchecked users.driver_id supplied by an account payload.
    driver_ids = tuple(row[0] for row in con.execute("SELECT id FROM drivers WHERE user_id=? ORDER BY id", (user_id,)))
    primary = access.get("primary_branch_id")
    if primary not in branch_ids:
        primary = None
    return {"user_id": user_id, "role": role if active else "customer", "legacy_role": legacy_role(role),
            "actor_name": str(user.get("display_name") or ""), "branch_ids": branch_ids if active else (),
            "primary_branch_id": primary if active else None,
            "global_scope": active and role == "system_admin" and access.get("global_scope") == 1,
            "courier_driver_ids": driver_ids if active else (), "is_active": active}


def allowed(ctx, permission):
    return bool(ctx and ctx.get("is_active", True) and
                permission in ROLE_PERMISSIONS.get(canonical_role(ctx.get("role")), ()))


def _entity(value):
    try:
        return ENTITY_ALIASES[value]
    except KeyError:
        raise ValueError("Unsupported scoped entity") from None


def _column(alias, name):
    if alias and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias):
        raise ValueError("Invalid SQL alias")
    return (alias + "." if alias else "") + name


def _branch_for_city(city_sql):
    return f"(SELECT b_scope.id FROM branches b_scope WHERE b_scope.city={city_sql} AND b_scope.is_active=1 ORDER BY b_scope.id LIMIT 1)"


def _shipment_offices(alias):
    identity = _column(alias, "id")
    origin = f"COALESCE((SELECT ss.origin_branch_id FROM shipment_scope ss WHERE ss.shipment_id={identity}),{_branch_for_city(_column(alias, 'origin'))})"
    destination = f"COALESCE((SELECT ss.destination_branch_id FROM shipment_scope ss WHERE ss.shipment_id={identity}),(SELECT b_scope.id FROM branches b_scope WHERE b_scope.code={_column(alias, 'recipient_branch')} AND b_scope.is_active=1 ORDER BY b_scope.id LIMIT 1),{_branch_for_city(_column(alias, 'destination'))})"
    return origin, destination


def _route_offices(alias):
    identity = _column(alias, "id")
    return tuple(f"COALESCE((SELECT rs_scope.{side}_branch_id FROM route_scope rs_scope WHERE rs_scope.route_id={identity}),{_branch_for_city(_column(alias, side))})" for side in ("origin", "destination"))


def _membership(expressions, branch_ids):
    marks = ",".join("?" for _ in branch_ids)
    return "(" + " OR ".join(f"{expr} IN ({marks})" for expr in expressions) + ")", list(branch_ids) * len(expressions)


def sql_scope(ctx, entity, alias=""):
    """Return a parameterized WHERE predicate; use the actual query's table alias.

    Unknown entities/invalid aliases raise ValueError. Missing memberships and
    customer access fail closed. Role permissions must also be checked separately.
    """
    entity = _entity(entity)
    alias = alias or ENTITY_TABLES[entity]
    _column(alias, "id")
    role = canonical_role((ctx or {}).get("role"))
    if not ctx or not ctx.get("is_active", True) or role == "customer":
        return "0=1", []
    # Campaign templates are shared across offices. Their read permission still
    # applies when the caller has no branch memberships.
    if entity == "campaigns":
        return ("1=1", []) if allowed(ctx, "campaigns.read") else ("0=1", [])
    if role == "system_admin" and ctx.get("global_scope") is True:
        return "1=1", []
    branches = tuple(ctx.get("branch_ids") or ())
    drivers = tuple(ctx.get("courier_driver_ids") or ())
    if role == "courier" and entity in ("shipments", "drivers"):
        if not drivers:
            return "0=1", []
        field = "driver_id" if entity == "shipments" else "id"
        return f"{_column(alias, field)} IN ({','.join('?' for _ in drivers)})", list(drivers)
    if not branches:
        return "0=1", []
    if entity == "shipments":
        return _membership(_shipment_offices(alias), branches)
    if entity == "routes":
        predicate, args = _membership(_route_offices(alias), branches)
        if role == "courier":
            if not drivers:
                return "0=1", []
            predicate += f" AND {_column(alias, 'driver_id')} IN ({','.join('?' for _ in drivers)})"
            args.extend(drivers)
        return predicate, args
    if entity == "branches":
        return _membership((_column(alias, "id"),), branches)
    if entity == "drivers":
        branch = _column(alias, "branch")
        office = f"COALESCE((SELECT ds_scope.branch_id FROM driver_scope ds_scope WHERE ds_scope.driver_id={_column(alias, 'id')}),(SELECT b_scope.id FROM branches b_scope WHERE b_scope.code={branch} AND b_scope.is_active=1 ORDER BY b_scope.id LIMIT 1),{_branch_for_city(branch)})"
        return _membership((office,), branches)
    if entity == "clients":
        office = f"COALESCE((SELECT cs.branch_id FROM client_scope cs WHERE cs.client_id={_column(alias, 'id')}),{_branch_for_city(_column(alias, 'city'))})"
        return _membership((office,), branches)
    if entity == "notifications":
        predicate, args = _membership((_column(alias, "branch_id"),), branches)
        if role == "courier":
            route_predicate, route_args = sql_scope(ctx, "routes", "r_notice")
            predicate += f" AND EXISTS (SELECT 1 FROM route_runs r_notice WHERE r_notice.id={_column(alias, 'route_id')} AND {route_predicate})"
            args.extend(route_args)
        return predicate, args
    # Vehicles are explicitly attached to offices or visible through a scoped
    # trip. Only system administrators have vehicles.manage permission.
    marks = ",".join("?" for _ in branches)
    explicit = f"EXISTS (SELECT 1 FROM vehicle_branches vb_scope WHERE vb_scope.vehicle_id={_column(alias, 'id')} AND vb_scope.branch_id IN ({marks}))"
    route_predicate, route_args = sql_scope(ctx, "routes", "r_vehicle")
    linked = f"EXISTS (SELECT 1 FROM route_runs r_vehicle WHERE r_vehicle.vehicle_id={_column(alias, 'id')} AND {route_predicate})"
    if role == "courier":
        return linked, route_args
    return f"({explicit} OR {linked})", list(branches) + route_args


def require_object(con, ctx, entity, row):
    """Recheck the persisted object, avoiding authorization from payload fields."""
    if row is None:
        raise AccessDenied("Object is unavailable in your branch scope.")
    entity = _entity(entity)
    identity = dict(row).get("id")
    if identity is None:
        raise AccessDenied("Object is unavailable in your branch scope.")
    predicate, args = sql_scope(ctx, entity, "auth_object")
    exists = con.execute(f"SELECT 1 FROM {ENTITY_TABLES[entity]} auth_object WHERE auth_object.id=? AND ({predicate})", [identity] + args).fetchone()
    if not exists:
        raise AccessDenied("Object is unavailable in your branch scope.")
    return row


COURIER_SHIPMENT_FIELDS = frozenset({
    "id", "awb", "recipient", "phone", "origin", "destination", "status", "stage", "cod", "eta",
    "recipient_branch", "recipient_address", "recipient_latitude", "recipient_longitude", "sender_name",
    "package_type", "package_description", "pieces", "weight",
    "length_cm", "width_cm", "height_cm", "driver_id", "driver_name", "driver_mobile", "driver_location",
    "driver_latitude", "driver_longitude", "driver_location_updated", "payment_method", "payment_status",
    "created_at", "updated_at", "tracking_url", "events",
})
ACCOUNTANT_SHIPMENT_FIELDS = frozenset({
    "id", "awb", "origin", "destination", "status", "stage", "cod", "eta", "recipient_branch",
    "sender_name", "recipient", "package_type", "pieces", "weight", "payment_method", "shipping_fee",
    "vat_amount", "cod_fee", "insurance_fee", "total_fee", "payment_status", "company_account",
    "created_at", "updated_at",
})


def scoped_shipment(ctx, row):
    row = dict(row)
    role = canonical_role((ctx or {}).get("role"))
    if role == "customer" or not allowed(ctx, "shipments.read"):
        return {}
    if role == "courier":
        return {key: value for key, value in row.items() if key in COURIER_SHIPMENT_FIELDS}
    if role == "accountant":
        return {key: value for key, value in row.items() if key in ACCOUNTANT_SHIPMENT_FIELDS}
    return row
