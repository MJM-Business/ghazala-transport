"""Migration 3: additive role, branch-scope and append-only audit relations.

Callbacks never commit and never rewrite existing users/business rows.
"""
from authorization import ROLES, canonical_role
import re


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS user_access (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK(role IN ('system_admin','branch_manager','office_employee','courier','accountant','customer')),
        primary_branch_id INTEGER REFERENCES branches(id) ON DELETE SET NULL,
        global_scope INTEGER NOT NULL DEFAULT 0 CHECK(global_scope IN (0,1)),
        CHECK(global_scope=0 OR role='system_admin'))""",
    """CREATE TABLE IF NOT EXISTS user_branches (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        branch_id INTEGER NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
        is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0,1)),
        PRIMARY KEY(user_id,branch_id))""",
    "CREATE UNIQUE INDEX IF NOT EXISTS user_branches_primary ON user_branches(user_id) WHERE is_primary=1",
    "CREATE INDEX IF NOT EXISTS user_branches_branch ON user_branches(branch_id,user_id)",
    """CREATE TABLE IF NOT EXISTS driver_scope (
        driver_id INTEGER PRIMARY KEY REFERENCES drivers(id) ON DELETE CASCADE,
        branch_id INTEGER REFERENCES branches(id))""",
    "CREATE INDEX IF NOT EXISTS driver_scope_branch ON driver_scope(branch_id,driver_id)",
    """CREATE TABLE IF NOT EXISTS shipment_scope (
        shipment_id INTEGER PRIMARY KEY REFERENCES shipments(id) ON DELETE CASCADE,
        origin_branch_id INTEGER REFERENCES branches(id),
        destination_branch_id INTEGER REFERENCES branches(id))""",
    "CREATE INDEX IF NOT EXISTS shipment_scope_origin ON shipment_scope(origin_branch_id,shipment_id)",
    "CREATE INDEX IF NOT EXISTS shipment_scope_destination ON shipment_scope(destination_branch_id,shipment_id)",
    """CREATE TABLE IF NOT EXISTS route_scope (
        route_id INTEGER PRIMARY KEY REFERENCES route_runs(id) ON DELETE CASCADE,
        origin_branch_id INTEGER REFERENCES branches(id),
        destination_branch_id INTEGER REFERENCES branches(id))""",
    "CREATE INDEX IF NOT EXISTS route_scope_origin ON route_scope(origin_branch_id,route_id)",
    "CREATE INDEX IF NOT EXISTS route_scope_destination ON route_scope(destination_branch_id,route_id)",
    """CREATE TABLE IF NOT EXISTS client_scope (
        client_id INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
        branch_id INTEGER REFERENCES branches(id))""",
    "CREATE INDEX IF NOT EXISTS client_scope_branch ON client_scope(branch_id,client_id)",
    """CREATE TABLE IF NOT EXISTS vehicle_branches (
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
        branch_id INTEGER NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
        PRIMARY KEY(vehicle_id,branch_id))""",
    "CREATE INDEX IF NOT EXISTS vehicle_branches_branch ON vehicle_branches(branch_id,vehicle_id)",
    # Audit identity/branch values are historical snapshots, deliberately not
    # foreign keys that would rewrite or erase evidence on an entity deletion.
    """CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        actor_user_id INTEGER, actor_name TEXT NOT NULL DEFAULT '',
        actor_role TEXT NOT NULL DEFAULT '', branch_id INTEGER,
        action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT,
        request_id TEXT NOT NULL DEFAULT '', request_method TEXT NOT NULL DEFAULT '',
        request_path TEXT NOT NULL DEFAULT '', ip_address TEXT NOT NULL DEFAULT '',
        before_json TEXT NOT NULL DEFAULT '{}', after_json TEXT NOT NULL DEFAULT '{}',
        metadata_json TEXT NOT NULL DEFAULT '{}')""",
    "CREATE INDEX IF NOT EXISTS audit_events_created ON audit_events(created_at,id)",
    "CREATE INDEX IF NOT EXISTS audit_events_actor ON audit_events(actor_user_id,id)",
    "CREATE INDEX IF NOT EXISTS audit_events_entity ON audit_events(entity_type,entity_id,id)",
    "CREATE INDEX IF NOT EXISTS audit_events_branch ON audit_events(branch_id,id)",
    """CREATE TRIGGER IF NOT EXISTS audit_events_no_update BEFORE UPDATE ON audit_events
        BEGIN SELECT RAISE(ABORT,'Audit events are append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_events_no_delete BEFORE DELETE ON audit_events
        BEGIN SELECT RAISE(ABORT,'Audit events are append-only'); END""",
)


def _dict_rows(con, sql, args=()):
    cursor = con.execute(sql, args)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def branch_for_city(con, city, code=None):
    """Resolve a legacy city/code to its lowest active office, or None."""
    if code:
        row = con.execute("SELECT id FROM branches WHERE code=? AND is_active=1 ORDER BY id LIMIT 1", (code,)).fetchone()
        if row:
            return row[0]
    row = con.execute("SELECT id FROM branches WHERE city=? AND is_active=1 ORDER BY id LIMIT 1", (city,)).fetchone()
    return row[0] if row else None


def _active_branch(con, branch_id):
    if isinstance(branch_id, bool) or not re.fullmatch(r"[1-9][0-9]*", str(branch_id or "").strip()):
        raise ValueError("Branch must be an active office.")
    try:
        branch_id = int(branch_id)
    except (TypeError, ValueError):
        raise ValueError("Branch must be an active office.") from None
    if not con.execute("SELECT 1 FROM branches WHERE id=? AND is_active=1", (branch_id,)).fetchone():
        raise ValueError("Branch must be an active office.")
    return branch_id


def ensure_legacy_access(con):
    """Adopt unassigned legacy users once; also call after pristine demo seeds.

    Existing canonical assignments and legacy users rows are left untouched.
    Couriers without a linked driver retain no shipment/trip access.
    """
    primary = con.execute("""SELECT id FROM branches WHERE is_active=1
        ORDER BY CASE WHEN code='JED-MAIN' THEN 0 ELSE 1 END,id LIMIT 1""").fetchone()
    default_branch = primary[0] if primary else None
    users = _dict_rows(con, "SELECT u.id,u.role FROM users u LEFT JOIN user_access a ON a.user_id=u.id WHERE a.user_id IS NULL ORDER BY u.id")
    for user in users:
        role = canonical_role(user["role"])
        branch_id = default_branch if role in ("branch_manager", "office_employee", "accountant") else None
        memberships = []
        if role == "courier":
            for driver in _dict_rows(con, """SELECT d.branch,ds.branch_id FROM drivers d
                LEFT JOIN driver_scope ds ON ds.driver_id=d.id WHERE d.user_id=? ORDER BY d.id""", (user["id"],)):
                office = driver["branch_id"]
                if office is not None and not con.execute("SELECT 1 FROM branches WHERE id=? AND is_active=1", (office,)).fetchone():
                    office = None
                elif office is None:
                    office = branch_for_city(con, driver["branch"], driver["branch"])
                if office is not None and office not in memberships:
                    memberships.append(office)
            branch_id = memberships[0] if memberships else None
        elif branch_id is not None:
            memberships.append(branch_id)
        con.execute("INSERT OR IGNORE INTO user_access(user_id,role,primary_branch_id,global_scope) VALUES(?,?,?,?)",
                    (user["id"], role, branch_id, int(role == "system_admin")))
        for office in memberships:
            con.execute("INSERT OR IGNORE INTO user_branches(user_id,branch_id,is_primary) VALUES(?,?,?)",
                        (user["id"], office, int(office == branch_id)))


def set_user_access(con, user_id, role, branch_ids=(), primary_branch_id=None, global_scope=False):
    """Apply a validated canonical assignment; caller must require users.manage.

    Only supplemental access tables are mutated; users.role stays legacy-compatible.
    """
    if str(role or "").lower().strip() not in (*ROLES, "admin", "manager", "employee"):
        raise ValueError("Unsupported user role.")
    role = canonical_role(role)
    if not isinstance(global_scope, (bool, int)) or global_scope not in (0, 1):
        raise ValueError("Global scope must be a boolean flag.")
    if global_scope and role != "system_admin":
        raise ValueError("Only a system administrator can have global scope.")
    if not con.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
        raise ValueError("User not found.")
    branches = list(dict.fromkeys(_active_branch(con, value) for value in branch_ids))
    if primary_branch_id is not None:
        primary_branch_id = _active_branch(con, primary_branch_id)
        if primary_branch_id not in branches:
            raise ValueError("Primary office must be included in the user's memberships.")
    elif branches:
        primary_branch_id = branches[0]
    if role in ("branch_manager", "office_employee", "accountant") and not branches:
        raise ValueError("This role requires an active office membership.")
    con.execute("""INSERT INTO user_access(user_id,role,primary_branch_id,global_scope) VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,primary_branch_id=excluded.primary_branch_id,global_scope=excluded.global_scope""",
        (user_id, role, primary_branch_id, int(bool(global_scope))))
    con.execute("DELETE FROM user_branches WHERE user_id=?", (user_id,))
    for branch_id in branches:
        con.execute("INSERT INTO user_branches(user_id,branch_id,is_primary) VALUES(?,?,?)", (user_id, branch_id, int(branch_id == primary_branch_id)))
    return {"user_id": user_id, "role": role, "branch_ids": tuple(branches),
            "primary_branch_id": primary_branch_id, "global_scope": bool(global_scope)}


def resolve_shipment_offices(con, row):
    """Resolve the same supplemental/legacy IDs used by sql_scope."""
    row = dict(row)
    existing = con.execute("SELECT origin_branch_id,destination_branch_id FROM shipment_scope WHERE shipment_id=?", (row.get("id"),)).fetchone()
    origin = existing[0] if existing else None
    destination = existing[1] if existing else None
    if row.get("id") is None:
        origin = _active_branch(con, row["origin_branch_id"]) if row.get("origin_branch_id") is not None else None
        destination = _active_branch(con, row["destination_branch_id"]) if row.get("destination_branch_id") is not None else None
    return (origin if origin is not None else branch_for_city(con, row.get("origin")),
            destination if destination is not None else branch_for_city(con, row.get("destination"), row.get("recipient_branch")))


def resolve_route_offices(con, row):
    """Resolve the same supplemental/legacy IDs used by sql_scope."""
    row = dict(row)
    existing = con.execute("SELECT origin_branch_id,destination_branch_id FROM route_scope WHERE route_id=?", (row.get("id"),)).fetchone()
    origin = existing[0] if existing else None
    destination = existing[1] if existing else None
    if row.get("id") is None:
        origin = _active_branch(con, row["origin_branch_id"]) if row.get("origin_branch_id") is not None else None
        destination = _active_branch(con, row["destination_branch_id"]) if row.get("destination_branch_id") is not None else None
    return (origin if origin is not None else branch_for_city(con, row.get("origin")),
            destination if destination is not None else branch_for_city(con, row.get("destination")))


def persist_driver_scope(con, driver_id, branch_id):
    branch_id = _active_branch(con, branch_id)
    if not con.execute("SELECT 1 FROM drivers WHERE id=?", (driver_id,)).fetchone():
        raise ValueError("Driver not found.")
    con.execute("""INSERT INTO driver_scope(driver_id,branch_id) VALUES(?,?)
        ON CONFLICT(driver_id) DO UPDATE SET branch_id=excluded.branch_id""", (driver_id, branch_id))
    return branch_id


def persist_shipment_scope(con, shipment_id, origin_branch_id, destination_branch_id):
    origin_branch_id = _active_branch(con, origin_branch_id)
    destination_branch_id = _active_branch(con, destination_branch_id)
    if not con.execute("SELECT 1 FROM shipments WHERE id=?", (shipment_id,)).fetchone():
        raise ValueError("Shipment not found.")
    con.execute("""INSERT INTO shipment_scope(shipment_id,origin_branch_id,destination_branch_id) VALUES(?,?,?)
        ON CONFLICT(shipment_id) DO UPDATE SET origin_branch_id=excluded.origin_branch_id,destination_branch_id=excluded.destination_branch_id""",
        (shipment_id, origin_branch_id, destination_branch_id))
    return origin_branch_id, destination_branch_id


def persist_route_scope(con, route_id, origin_branch_id, destination_branch_id):
    origin_branch_id = _active_branch(con, origin_branch_id)
    destination_branch_id = _active_branch(con, destination_branch_id)
    if not con.execute("SELECT 1 FROM route_runs WHERE id=?", (route_id,)).fetchone():
        raise ValueError("Trip not found.")
    con.execute("""INSERT INTO route_scope(route_id,origin_branch_id,destination_branch_id) VALUES(?,?,?)
        ON CONFLICT(route_id) DO UPDATE SET origin_branch_id=excluded.origin_branch_id,destination_branch_id=excluded.destination_branch_id""",
        (route_id, origin_branch_id, destination_branch_id))
    return origin_branch_id, destination_branch_id


def persist_client_scope(con, client_id, branch_id):
    branch_id = _active_branch(con, branch_id)
    if not con.execute("SELECT 1 FROM clients WHERE id=?", (client_id,)).fetchone():
        raise ValueError("Client not found.")
    con.execute("""INSERT INTO client_scope(client_id,branch_id) VALUES(?,?)
        ON CONFLICT(client_id) DO UPDATE SET branch_id=excluded.branch_id""", (client_id, branch_id))
    return branch_id


def persist_vehicle_branches(con, vehicle_id, branch_ids):
    branches = list(dict.fromkeys(_active_branch(con, value) for value in branch_ids))
    if not con.execute("SELECT 1 FROM vehicles WHERE id=?", (vehicle_id,)).fetchone():
        raise ValueError("Vehicle not found.")
    con.execute("DELETE FROM vehicle_branches WHERE vehicle_id=?", (vehicle_id,))
    for branch_id in branches:
        con.execute("INSERT INTO vehicle_branches(vehicle_id,branch_id) VALUES(?,?)", (vehicle_id, branch_id))
    return tuple(branches)


def migration3(con):
    for statement in SCHEMA:
        con.execute(statement)
    adopt_pristine_seed_scope(con)


def adopt_pristine_seed_scope(con):
    """Adopt missing supplemental ownership after original pristine seeds.

    No DDL, version changes, legacy row updates, existing ownership replacement
    or commits. The caller owns the startup transaction. Return inserted counts.
    """
    tables = ("user_access", "user_branches", "driver_scope", "shipment_scope",
              "route_scope", "client_scope", "vehicle_branches")
    before = {table: con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables}
    # Deterministic supplemental backfills do not modify any legacy columns.
    con.execute("""INSERT OR IGNORE INTO driver_scope(driver_id,branch_id)
        SELECT d.id,COALESCE((SELECT b.id FROM branches b WHERE b.code=d.branch AND b.is_active=1 ORDER BY b.id LIMIT 1),
                            (SELECT b.id FROM branches b WHERE b.city=d.branch AND b.is_active=1 ORDER BY b.id LIMIT 1))
        FROM drivers d""")
    con.execute("""INSERT OR IGNORE INTO shipment_scope(shipment_id,origin_branch_id,destination_branch_id)
        SELECT s.id,
          (SELECT b.id FROM branches b WHERE b.city=s.origin AND b.is_active=1 ORDER BY b.id LIMIT 1),
          COALESCE((SELECT b.id FROM branches b WHERE b.code=s.recipient_branch AND b.is_active=1 ORDER BY b.id LIMIT 1),
                   (SELECT b.id FROM branches b WHERE b.city=s.destination AND b.is_active=1 ORDER BY b.id LIMIT 1))
        FROM shipments s""")
    con.execute("""INSERT OR IGNORE INTO route_scope(route_id,origin_branch_id,destination_branch_id)
        SELECT r.id,
          (SELECT b.id FROM branches b WHERE b.city=r.origin AND b.is_active=1 ORDER BY b.id LIMIT 1),
          (SELECT b.id FROM branches b WHERE b.city=r.destination AND b.is_active=1 ORDER BY b.id LIMIT 1)
        FROM route_runs r""")
    con.execute("""INSERT OR IGNORE INTO client_scope(client_id,branch_id)
        SELECT c.id,(SELECT b.id FROM branches b WHERE b.city=c.city AND b.is_active=1 ORDER BY b.id LIMIT 1)
        FROM clients c""")
    missing_vehicles = [row[0] for row in con.execute("""SELECT v.id FROM vehicles v
        WHERE NOT EXISTS(SELECT 1 FROM vehicle_branches vb WHERE vb.vehicle_id=v.id) ORDER BY v.id""")]
    default = con.execute("""SELECT id FROM branches WHERE is_active=1
        ORDER BY CASE WHEN code='JED-MAIN' THEN 0 ELSE 1 END,id LIMIT 1""").fetchone()
    for vehicle_id in missing_vehicles:
        offices = [row[0] for row in con.execute("""SELECT rs.origin_branch_id FROM route_runs r
            JOIN route_scope rs ON rs.route_id=r.id JOIN branches b ON b.id=rs.origin_branch_id
            WHERE r.vehicle_id=? AND b.is_active=1
            UNION SELECT rs.destination_branch_id FROM route_runs r JOIN route_scope rs ON rs.route_id=r.id
            JOIN branches b ON b.id=rs.destination_branch_id WHERE r.vehicle_id=? AND b.is_active=1""", (vehicle_id, vehicle_id))]
        if not offices and default:
            offices = [default[0]]
        for office in offices:
            con.execute("INSERT OR IGNORE INTO vehicle_branches(vehicle_id,branch_id) VALUES(?,?)", (vehicle_id, office))
    ensure_legacy_access(con)
    return {table: con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] - before[table] for table in tables}


foundation_migration = migration3
set_access = set_user_access
adopt_seed_scope = adopt_pristine_seed_scope
