"""Baseline regression checks, using disposable database copies only.

Run with the application's Python environment::

    python tests/test_baseline_regression.py
    python tests/test_baseline_regression.py --json-output outputs/baseline-tests.json

No production HTTP requests are made. The master SQLite database is opened in
read-only mode solely to make a consistent SQLite backup. Every write, login,
demo SMS, and migration runs against a temporary copy on an ephemeral loopback
port. Report/QR generation uses the application's installed dependencies; the
test harness itself uses only Python's standard library.
"""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
import zipfile
import zlib


PROJECT = Path(__file__).resolve().parents[1]
MASTER_DB = PROJECT / "work" / "ghazala.sqlite3"
BUSINESS_TABLES = (
    "shipments", "shipment_events", "drivers", "users", "sessions", "branches",
    "vehicles", "clients", "campaigns", "route_runs", "route_shipments",
    "delivery_otps", "pod_records", "service_settings", "sms_outbox",
    "branch_notifications",
)
CREDENTIALS = {
    "admin": ("admin@ghazala.sa", "Admin123!"),
    "manager": ("manager@ghazala.sa", "Manager123!"),
    "employee": ("employee@ghazala.sa", "Employee123!"),
}
DELIVERED = "تم الاستلام"
REPORT_MONEY_LABELS = {
    "ar": ("مبالغ التحصيل المطلوبة", "قيمة رسوم الشحن المسجلة (شاملة الضريبة)"),
    "en": ("Requested COD amounts", "Recorded shipment charges (incl. VAT)"),
    "ur": ("مطلوبہ COD رقوم", "درج شدہ شپنگ چارجز (VAT سمیت)"),
    "hi": ("वसूली के लिए माँगी गई COD राशि", "दर्ज शिपिंग शुल्क (VAT सहित)"),
}
def signature_png_bytes():
    """Generate a valid PNG with a small synthetic ink stroke using stdlib only."""
    width, height = 64, 32

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    pixels = bytearray()
    for y in range(height):
        pixels.append(0)  # PNG filter: none.
        for x in range(width):
            stroke_y = 8 + (x % 20) // 2
            ink = 5 <= x <= 58 and abs(y - stroke_y) <= 1
            pixels.extend((18, 28, 42, 255) if ink else (255, 255, 255, 255))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(pixels))) + chunk(b"IEND", b"")


VALID_PNG_BYTES = signature_png_bytes()
PNG = "data:image/png;base64," + base64.b64encode(VALID_PNG_BYTES).decode("ascii")
SERVER = None


def consistent_backup(source: Path, target: Path, *, read_only: bool = False):
    """SQLite backup captures WAL changes without copying an open database file."""
    if read_only:
        connection = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(source)
    with closing(connection) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def table_snapshot(db: Path, table: str, *, columns=None, where="", params=()):
    """Compare exact stored values without writing personal records to test logs."""
    with closing(sqlite3.connect(db)) as con:
        columns = columns or tuple(row[1] for row in con.execute(f'PRAGMA table_info("{table}")'))
        names = ",".join('"' + name.replace('"', '""') + '"' for name in columns)
        rows = con.execute(f'SELECT {names} FROM "{table}" {where}', params).fetchall()
    encoded = []
    for row in rows:
        values = [
            {"bytes": base64.b64encode(value).decode("ascii")}
            if isinstance(value, bytes) else value
            for value in row
        ]
        encoded.append(json.dumps(values, ensure_ascii=False, sort_keys=True))
    digest = hashlib.sha256("\n".join(sorted(encoded)).encode("utf-8")).hexdigest()
    return {"columns": tuple(columns), "count": len(rows), "sha256": digest}


def business_snapshot(db: Path, *, reference=None):
    with closing(sqlite3.connect(db)) as con:
        present = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    tables = reference.keys() if reference is not None else BUSINESS_TABLES
    return {
        table: table_snapshot(db, table, columns=reference[table]["columns"] if reference else None)
        for table in tables if table in present
    }


def external_http_forbidden(*_args, **_kwargs):
    raise AssertionError("External HTTP/SMS is disabled for this isolated regression suite")


class APIClient:
    def __init__(self, port: int, cookie: str = ""):
        self.port = port
        self.cookie = cookie

    def request(self, method, path, data=None):
        headers = {}
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.cookie:
            headers["Cookie"] = self.cookie
        with closing(http.client.HTTPConnection("127.0.0.1", self.port, timeout=45)) as con:
            con.request(method, path, body=body, headers=headers)
            response = con.getresponse()
            raw = response.read()
            result_headers = {key.lower(): value for key, value in response.getheaders()}
            if "set-cookie" in result_headers:
                self.cookie = result_headers["set-cookie"].split(";", 1)[0]
            content_type = result_headers.get("content-type", "")
            result = json.loads(raw.decode("utf-8")) if "application/json" in content_type else raw
            return response.status, result, result_headers


class BaselineRegression(unittest.TestCase):
    """Serial unittest cases; each receives a fresh copy of the master snapshot."""

    @classmethod
    def setUpClass(cls):
        if not MASTER_DB.is_file():
            raise RuntimeError(f"Master database not found: {MASTER_DB}")
        cls.suite_tmp = tempfile.TemporaryDirectory(prefix="ghazala-baseline-")
        cls.suite_dir = Path(cls.suite_tmp.name).resolve()
        cls.base_db = cls.suite_dir / "read-only-master-backup.sqlite3"
        consistent_backup(MASTER_DB, cls.base_db, read_only=True)
        cls.env_patch = mock.patch.dict(os.environ, {
            "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "",
            "TWILIO_FROM_NUMBER": "", "PUBLIC_BASE_URL": "",
        })
        cls.env_patch.start()
        sys.path.insert(0, str(PROJECT))
        global SERVER
        spec = importlib.util.spec_from_file_location("ghazala_baseline_server", PROJECT / "server.py")
        SERVER = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = SERVER
        spec.loader.exec_module(SERVER)
        cls.original_db = SERVER.DB
        cls.network_patch = mock.patch.object(SERVER, "urlopen", external_http_forbidden)
        cls.network_patch.start()

    @classmethod
    def tearDownClass(cls):
        SERVER.DB = cls.original_db
        cls.network_patch.stop()
        cls.env_patch.stop()
        cls.suite_tmp.cleanup()

    def setUp(self):
        self.case_tmp = tempfile.TemporaryDirectory(prefix="case-", dir=self.suite_dir)
        self.case_dir = Path(self.case_tmp.name).resolve()
        self.db = self.case_dir / "isolated.sqlite3"
        consistent_backup(self.base_db, self.db)
        self.before_startup = business_snapshot(self.db)
        SERVER.DB = self.db
        self.assertIsolatedDB()
        SERVER.init_db()
        SERVER.REPORT_DOWNLOADS.clear()
        self.httpd = SERVER.ThreadingHTTPServer(("127.0.0.1", 0), SERVER.Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.worker = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.worker.start()
        self.clients = {}
        self.guest = APIClient(self.port)
        self.sequence = 0

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.worker.join(timeout=10)
        SERVER.DB = self.base_db
        self.case_tmp.cleanup()

    def assertIsolatedDB(self):
        selected = Path(SERVER.DB).resolve()
        self.assertTrue(selected.is_relative_to(self.suite_dir))
        self.assertNotEqual(selected, MASTER_DB.resolve())

    def query(self, sql, params=()):
        self.assertIsolatedDB()
        with closing(sqlite3.connect(SERVER.DB)) as con:
            con.row_factory = sqlite3.Row
            return [dict(row) for row in con.execute(sql, params)]

    def execute(self, sql, params=()):
        self.assertIsolatedDB()
        with closing(sqlite3.connect(SERVER.DB)) as con, con:
            con.execute("PRAGMA foreign_keys=ON")
            con.execute(sql, params)

    def client(self, role="admin"):
        if role not in self.clients:
            client = APIClient(self.port)
            username, password = CREDENTIALS[role]
            status, result, headers = client.request("POST", "/api/login", {
                "username": username, "password": password,
            })
            self.assertEqual(status, 200, result)
            self.assertEqual(result["user"]["role"], role)
            self.assertIn("HttpOnly", headers.get("set-cookie", ""))
            self.clients[role] = client
        return self.clients[role]

    def require(self, role, method, path, data=None, status=200):
        client = self.guest if role is None else self.client(role)
        actual, result, headers = client.request(method, path, data)
        self.assertEqual(actual, status, result if isinstance(result, dict) else path)
        return result, headers

    def suffix(self):
        self.sequence += 1
        return f"{self.sequence:04d}-{self.case_dir.name[-6:]}"

    def new_driver(self):
        suffix = self.suffix()
        record, _ = self.require("admin", "POST", "/api/drivers", {
            "name": "Isolated regression driver " + suffix,
            "national_id": "TEST-ID-" + suffix,
            "mobile": "+966500000001", "branch": "جدة", "status": "متاح",
            "location_text": "Isolated Jeddah fixture", "latitude": 21.5433,
            "longitude": 39.1728,
        }, status=201)
        return record

    def new_vehicle(self, capacity=100):
        record, _ = self.require("admin", "POST", "/api/vehicles", {
            "plate": "TEST-" + self.suffix(), "vehicle_type": "شاحنة نقل",
            "capacity_kg": capacity, "status": "متاح",
        }, status=201)
        return record

    def assign_employee(self, driver):
        employee = self.query("SELECT id FROM users WHERE lower(username)=lower(?)", (CREDENTIALS["employee"][0],))[0]
        tables = {row["name"] for row in self.query("SELECT name FROM sqlite_master WHERE type='table'")}
        if "user_access" in tables:
            offices = self.query("SELECT branch_id FROM driver_scope WHERE driver_id=?", (driver["id"],))
            if not offices:
                offices = self.query("SELECT id AS branch_id FROM branches WHERE city=? AND is_active=1 ORDER BY id LIMIT 1", (driver["branch"],))
            branch_id = offices[0]["branch_id"]
            # Phase 3 requires both an assigned driver and explicit membership
            # for trip access; use the real authorized account-update endpoint.
            self.require("admin", "PATCH", f'/api/users/{employee["id"]}', {
                "driver_id": driver["id"], "branch_ids": [branch_id], "primary_branch_id": branch_id,
            })
            return
        self.execute("UPDATE drivers SET user_id=NULL WHERE user_id=?", (employee["id"],))
        self.execute("UPDATE drivers SET user_id=? WHERE id=?", (employee["id"], driver["id"]))
        self.execute("UPDATE users SET driver_id=? WHERE id=?", (driver["id"], employee["id"]))

    def shipment_payload(self, **overrides):
        data = {
            "sender_name": "Isolated sender " + self.suffix(), "sender_id": "1000000011",
            "sender_phone": "+966500000002", "sender_address": "Test warehouse, Jeddah",
            "recipient": "Isolated recipient", "recipient_id": "1000004091",
            "phone": "+966500000003", "recipient_address": "Test street, Jaazan",
            "origin": "جدة", "destination": "جازان", "eta": "Regression ETA",
            "cod": 125.0, "payment_method": "cod", "pieces": 1, "weight": 2.0,
            "length_cm": 10, "width_cm": 15, "height_cm": 20, "declared_value": 100,
            "insured": False, "package_type": "طرد تجاري سريع",
            "package_description": "Synthetic test parcel",
        }
        data.update(overrides)
        return data

    def new_shipment(self, role="admin", **overrides):
        shipment, _ = self.require(role, "POST", "/api/shipments", self.shipment_payload(**overrides), status=201)
        self.assertEqual(shipment["is_demo"], 0)
        self.assertEqual(shipment["tracking_sms"], "demo")
        return shipment

    def route_payload(self, shipments, driver, vehicle, **overrides):
        data = {
            "origin": "جدة", "destination": "جازان",
            "departure_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "driver_id": driver["id"], "vehicle_id": vehicle["id"],
            "capacity_kg": vehicle["capacity_kg"], "notification_minutes": 30,
            "awbs": [shipment["awb"] for shipment in shipments],
        }
        data.update(overrides)
        return data

    def new_route(self, shipments, driver, vehicle):
        route, _ = self.require("manager", "POST", "/api/routes", self.route_payload(shipments, driver, vehicle), status=201)
        return route

    def otp(self, shipment, role="admin"):
        # Prepare a valid delivery state using authorized transitions. This
        # setup is independent of the role whose OTP/POD authorization is tested.
        sequence = ("تم إنشاء الشحنة", "قيد النقل", "جاهز للتسليم", "قيد التوصيل")
        status = self.query("SELECT status FROM shipments WHERE id=?", (shipment["id"],))[0]["status"]
        if status in sequence:
            for next_status in sequence[sequence.index(status) + 1:]:
                self.require("admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": next_status})
        result, _ = self.require(role, "POST", f'/api/shipments/{shipment["awb"]}/otp', {})
        self.assertEqual(result["delivery"], "demo")
        self.assertRegex(result["demo_code"], r"^\d{6}$")
        return result["demo_code"]

    def pod_payload(self, code, **overrides):
        data = {
            "recipient_name": "Isolated receiving customer", "recipient_id_suffix": "4091",
            "otp": code, "signature_data": PNG, "photo_data": PNG,
            "latitude": 16.8894, "longitude": 42.5706, "note": "Synthetic delivery proof",
        }
        data.update(overrides)
        return data

    def finish(self, shipment, role="admin"):
        code = self.otp(shipment, role)
        result, _ = self.require(role, "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(code))
        self.assertEqual(result["sms_delivery"], "demo")
        return result

    def shipment_snapshot(self, shipment):
        sid = shipment["id"]
        return {
            "shipment": table_snapshot(self.db, "shipments", where="WHERE id=?", params=(sid,)),
            "events": table_snapshot(self.db, "shipment_events", where="WHERE shipment_id=?", params=(sid,)),
            "proof": table_snapshot(self.db, "pod_records", where="WHERE shipment_id=?", params=(sid,)),
            "otp": table_snapshot(self.db, "delivery_otps", where="WHERE shipment_id=?", params=(sid,)),
        }

    def test_existing_role_logins_and_logout(self):
        for role in CREDENTIALS:
            with self.subTest(role=role):
                client = self.client(role)
                me, _ = self.require(role, "GET", "/api/me")
                self.assertEqual(me["user"]["role"], role)
                self.assertEqual(client.request("POST", "/api/logout", {})[0], 200)
                self.assertIsNone(client.request("GET", "/api/me")[1]["user"])
        self.require(None, "POST", "/api/login", {"username": CREDENTIALS["admin"][0], "password": "incorrect"}, status=401)

    def test_existing_startup_preserves_all_business_values(self):
        self.assertEqual(business_snapshot(self.db, reference=self.before_startup), self.before_startup)
        before = business_snapshot(self.db)
        SERVER.init_db()
        self.assertEqual(business_snapshot(self.db, reference=before), before)

    def test_existing_migrations_are_idempotent(self):
        ledger = table_snapshot(self.db, "schema_migrations")
        settings = table_snapshot(self.db, "app_settings")
        self.assertGreaterEqual(ledger["count"], 1)
        self.assertEqual(self.query("SELECT value FROM app_settings WHERE key='bootstrap_completed'")[0]["value"], "1")
        SERVER.init_db()
        SERVER.init_db()
        self.assertEqual(table_snapshot(self.db, "schema_migrations"), ledger)
        self.assertEqual(table_snapshot(self.db, "app_settings"), settings)

    def test_fresh_bootstrap_and_migrations_run_once(self):
        original = SERVER.DB
        fresh = self.case_dir / "fresh.sqlite3"
        SERVER.DB = fresh
        try:
            SERVER.init_db()
            first = business_snapshot(fresh)
            ledger = table_snapshot(fresh, "schema_migrations")
            settings = table_snapshot(fresh, "app_settings")
            self.assertEqual(self.query("SELECT count(*) n FROM shipments")[0]["n"], len(SERVER.SEED_SHIPMENTS))
            self.assertEqual(self.query("SELECT count(*) n FROM users")[0]["n"], len(SERVER.DEMO_USERS))
            SERVER.init_db()
            SERVER.init_db()
            self.assertEqual(business_snapshot(fresh, reference=first), first)
            self.assertEqual(table_snapshot(fresh, "schema_migrations"), ledger)
            self.assertEqual(table_snapshot(fresh, "app_settings"), settings)
            self.execute("DELETE FROM shipments")
            self.execute("DELETE FROM clients")
            self.execute("DELETE FROM campaigns")
            self.execute("DELETE FROM drivers")
            empty = business_snapshot(fresh)
            SERVER.init_db()
            self.assertEqual(business_snapshot(fresh, reference=empty), empty)
        finally:
            SERVER.DB = original

    def test_migration_callback_failure_rolls_back_and_retry_is_idempotent(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                database = self.case_dir / ("migration-existing.sqlite3" if existing else "migration-fresh.sqlite3")
                calls = {"baseline": 0, "addition": 0}
                fail = True

                def baseline(con):
                    calls["baseline"] += 1
                    con.execute("CREATE TABLE fixture_business(id INTEGER PRIMARY KEY, value TEXT)")
                    con.execute("INSERT INTO fixture_business VALUES(1,'preserved baseline')")

                def addition(con):
                    calls["addition"] += 1
                    con.execute("CREATE TABLE fixture_addition(id INTEGER PRIMARY KEY, value TEXT)")
                    con.execute("INSERT INTO fixture_addition VALUES(1,'new additive record')")
                    if fail:
                        raise RuntimeError("Intentional isolated migration callback failure")

                registry = [(1, "test_baseline", baseline), (2, "test_addition", addition)]
                if existing:
                    with closing(sqlite3.connect(database)) as con, con:
                        con.execute("BEGIN IMMEDIATE")
                        SERVER.apply_migrations(con, registry[:1])
                    preserved = table_snapshot(database, "fixture_business")
                    old_ledger = table_snapshot(database, "schema_migrations")
                with self.assertRaisesRegex(RuntimeError, "Intentional isolated"):
                    with closing(sqlite3.connect(database)) as con, con:
                        con.execute("BEGIN IMMEDIATE")
                        SERVER.apply_migrations(con, registry)
                with closing(sqlite3.connect(database)) as con:
                    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertNotIn("fixture_addition", tables)
                if existing:
                    self.assertEqual(table_snapshot(database, "fixture_business"), preserved)
                    self.assertEqual(table_snapshot(database, "schema_migrations"), old_ledger)
                else:
                    self.assertNotIn("fixture_business", tables)
                    self.assertNotIn("schema_migrations", tables)
                fail = False
                with closing(sqlite3.connect(database)) as con, con:
                    con.execute("BEGIN IMMEDIATE")
                    SERVER.apply_migrations(con, registry)
                ledger = table_snapshot(database, "schema_migrations")
                records = {table: table_snapshot(database, table) for table in ("fixture_business", "fixture_addition")}
                self.assertEqual(ledger["count"], 2)
                self.assertEqual(records["fixture_business"]["count"], 1)
                self.assertEqual(records["fixture_addition"]["count"], 1)
                callbacks_after_retry = dict(calls)
                with closing(sqlite3.connect(database)) as con, con:
                    con.execute("BEGIN IMMEDIATE")
                    SERVER.apply_migrations(con, registry)
                self.assertEqual(calls, callbacks_after_retry)
                self.assertEqual(table_snapshot(database, "schema_migrations"), ledger)
                for table, record in records.items():
                    self.assertEqual(table_snapshot(database, table), record)

    def test_shipments_create_list_detail_tracking_and_employee_scope(self):
        driver = self.new_driver()
        self.assign_employee(driver)
        shipment = self.new_shipment(role="manager", driver_id=driver["id"])
        other = self.new_shipment()
        for role in ("admin", "manager", "employee"):
            with self.subTest(role=role):
                rows, _ = self.require(role, "GET", "/api/shipments")
                self.assertIn(shipment["awb"], {row["awb"] for row in rows})
                detail, _ = self.require(role, "GET", f'/api/shipments/{shipment["awb"]}')
                self.assertEqual(detail["sender_name"], shipment["sender_name"])
                self.assertEqual(detail["tracking_url"], shipment["tracking_url"])
        employee_rows, _ = self.require("employee", "GET", "/api/shipments")
        self.assertNotIn(other["awb"], {row["awb"] for row in employee_rows})
        self.require("employee", "GET", f'/api/shipments/{other["awb"]}', status=403)
        self.require("employee", "POST", "/api/shipments", self.shipment_payload(), status=403)
        self.require(None, "GET", "/api/shipments", status=401)
        public, _ = self.require(None, "GET", f'/api/public/tracking/{shipment["awb"]}')
        self.assertEqual(public["awb"], shipment["awb"])
        self.assertEqual(public["origin"], "جدة")
        self.assertEqual(public["destination"], "جازان")
        self.assertTrue(public["events"])
        forbidden = {"sender_name", "sender_id", "sender_phone", "recipient", "recipient_id", "phone", "otp", "signature_data", "photo_data"}
        self.assertFalse(forbidden.intersection(public))
        self.require(None, "GET", "/api/public/tracking/GHZ-NOT-FOUND", status=404)

    def test_shipment_route_and_numeric_validation(self):
        for changes in (
            {"destination": "الرياض"}, {"origin": "جازان", "destination": "جازان"},
            {"cod": "invalid"}, {"cod": "NaN"}, {"length_cm": "invalid"},
            {"weight": "invalid"}, {"pieces": "invalid"}, {"recipient_address": ""},
        ):
            with self.subTest(changes=changes):
                self.require("admin", "POST", "/api/shipments", self.shipment_payload(**changes), status=400)

    def test_route_creation_batch_scan_start_and_arrival(self):
        driver, vehicle = self.new_driver(), self.new_vehicle()
        first, second = self.new_shipment(), self.new_shipment()
        route = self.new_route([first], driver, vehicle)
        self.require("manager", "POST", f'/api/routes/{route["id"]}/scan', {"awb": second["awb"]}, status=201)
        self.require("manager", "POST", f'/api/routes/{route["id"]}/scan', {"awb": second["awb"]}, status=409)
        routes, _ = self.require("admin", "GET", "/api/routes")
        record = next(item for item in routes if item["id"] == route["id"])
        self.assertEqual({item["awb"] for item in record["shipments"]}, {first["awb"], second["awb"]})
        self.assertEqual(record["load_kg"], first["weight"] + second["weight"])
        self.require("manager", "POST", f'/api/routes/{route["id"]}', {"status": "في الطريق"})
        for shipment in (first, second):
            detail, _ = self.require("admin", "GET", f'/api/shipments/{shipment["awb"]}')
            self.assertEqual(detail["status"], "قيد النقل")
            self.assertEqual(detail["driver_id"], driver["id"])
        self.require("manager", "POST", f'/api/routes/{route["id"]}', {"status": "وصلت"})
        for shipment in (first, second):
            self.assertEqual(self.query("SELECT status FROM shipments WHERE id=?", (shipment["id"],))[0]["status"], "قيد النقل")
            self.require("admin", "POST", f'/api/routes/{route["id"]}/receive', {"awb": shipment["awb"]})
            self.assertEqual(self.query("SELECT status FROM shipments WHERE id=?", (shipment["id"],))[0]["status"], "جاهز للتسليم")
        arrived_driver = self.query("SELECT branch,status FROM drivers WHERE id=?", (driver["id"],))[0]
        self.assertEqual(arrived_driver, {"branch": "جازان", "status": "متاح"})
        self.assertEqual(self.query("SELECT status FROM vehicles WHERE id=?", (vehicle["id"],))[0]["status"], "متاح")

    def test_route_graph_terminal_actions_and_repeated_start_are_true_noops(self):
        driver, vehicle = self.new_driver(), self.new_vehicle()
        shipment = self.new_shipment()
        route = self.new_route([shipment], driver, vehicle)
        endpoint = f'/api/routes/{route["id"]}'

        def snapshot():
            return business_snapshot(self.db) | {"audit_events": table_snapshot(self.db, "audit_events")}

        scheduled = snapshot()
        self.require("manager", "POST", endpoint, {"status": "وصلت"}, status=409)
        self.assertEqual(snapshot(), scheduled)
        self.require("manager", "POST", endpoint, {"status": "في الطريق"})
        # Repeating a start after a later shipment milestone must not rewind
        # that parcel, change route/driver timestamps, or append audit/events.
        self.require("admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": "تأخير"})
        started = snapshot()
        response, _ = self.require("manager", "POST", endpoint, {"status": "في الطريق"})
        self.assertEqual(response["shipments_updated"], 0)
        self.assertEqual(snapshot(), started)
        self.require("manager", "POST", endpoint, {"status": "وصلت"})
        # An arrived trip may be retried after the driver is transferred for
        # another job. The retry must not silently restore the old office.
        next_office = self.query("SELECT id FROM branches WHERE city='جدة' AND is_active=1 ORDER BY id LIMIT 1")[0]["id"]
        self.require("admin", "PATCH", f'/api/drivers/{driver["id"]}', {
            "branch": "جدة", "branch_id": next_office, "location_text": "Next authorized assignment",
        })
        arrived = snapshot()
        self.require("manager", "POST", endpoint, {"status": "وصلت"})
        self.assertEqual(snapshot(), arrived)
        for status in ("في الطريق", "ملغاة"):
            with self.subTest(terminal="arrived", requested=status):
                self.require("manager", "POST", endpoint, {"status": status}, status=409)
                self.assertEqual(snapshot(), arrived)
        cancelled = self.new_route([self.new_shipment()], self.new_driver(), self.new_vehicle())
        endpoint = f'/api/routes/{cancelled["id"]}'
        self.require("manager", "POST", endpoint, {"status": "ملغاة"})
        cancelled_state = snapshot()
        self.require("manager", "POST", endpoint, {"status": "ملغاة"})
        self.assertEqual(snapshot(), cancelled_state)
        for status in ("في الطريق", "وصلت"):
            with self.subTest(terminal="cancelled", requested=status):
                self.require("manager", "POST", endpoint, {"status": status}, status=409)
                self.assertEqual(snapshot(), cancelled_state)

    def test_english_delivered_legacy_rows_cannot_load_and_are_skipped_by_routes(self):
        driver, vehicle = self.new_driver(), self.new_vehicle()
        complete, pending = self.new_shipment(), self.new_shipment()
        route = self.new_route([complete, pending], driver, vehicle)
        # This simulates a historical English stored enum in an isolated copy;
        # migration and validated route propagation must preserve it verbatim.
        self.execute("UPDATE shipments SET status='Delivered' WHERE id=?", (complete["id"],))
        before = self.shipment_snapshot(complete)
        other = self.new_shipment()
        self.execute("UPDATE shipments SET status='Delivered' WHERE id=?", (other["id"],))
        self.require("admin", "POST", "/api/routes", self.route_payload([other], self.new_driver(), self.new_vehicle()), status=400)
        self.require("manager", "POST", f'/api/routes/{route["id"]}/scan', {"awb": other["awb"]}, status=400)
        for status in ("في الطريق", "وصلت"):
            self.require("manager", "POST", f'/api/routes/{route["id"]}', {"status": status})
            self.assertEqual(self.shipment_snapshot(complete), before)

    def test_employee_routes_exclude_unassigned_routes_and_contacts(self):
        own_driver, other_driver = self.new_driver(), self.new_driver()
        self.assign_employee(own_driver)
        other_name, other_mobile = "Private unrelated route driver", "+966500000099"
        self.execute("UPDATE drivers SET name=?,mobile=? WHERE id=?", (other_name, other_mobile, other_driver["id"]))
        own_shipment = self.new_shipment(driver_id=own_driver["id"])
        other_recipient = "Private unrelated route recipient"
        other_shipment = self.new_shipment(driver_id=other_driver["id"], recipient=other_recipient)
        own_route = self.new_route([own_shipment], own_driver, self.new_vehicle())
        other_route = self.new_route([other_shipment], other_driver, self.new_vehicle())
        routes, _ = self.require("employee", "GET", "/api/routes")
        self.assertEqual({route["id"] for route in routes}, {own_route["id"]})
        visible = json.dumps(routes, ensure_ascii=False)
        for private_value in (other_name, other_mobile, other_recipient, other_route["code"], other_shipment["awb"]):
            self.assertNotIn(private_value, visible)
        for role in ("admin", "manager"):
            all_routes, _ = self.require(role, "GET", "/api/routes")
            self.assertTrue({own_route["id"], other_route["id"]}.issubset({route["id"] for route in all_routes}))
        employee_id = self.query("SELECT id FROM users WHERE lower(username)=lower(?)", (CREDENTIALS["employee"][0],))[0]["id"]
        self.execute("UPDATE drivers SET user_id=NULL WHERE user_id=?", (employee_id,))
        self.execute("UPDATE users SET driver_id=NULL WHERE id=?", (employee_id,))
        unlinked_routes, _ = self.require("employee", "GET", "/api/routes")
        self.assertEqual(unlinked_routes, [])

    def test_route_direction_capacity_availability_and_completed_rejection(self):
        driver, vehicle = self.new_driver(), self.new_vehicle(capacity=5)
        first = self.new_shipment(weight=3)
        reverse = self.new_shipment(origin="جازان", destination="جدة")
        heavy = self.new_shipment(weight=10)
        complete = self.new_shipment()
        self.finish(complete)
        for shipments in ([reverse], [heavy], [complete]):
            with self.subTest(awbs=[row["awb"] for row in shipments]):
                # Use global scope to exercise validation independently of the
                # new manager-origin-office restriction on reverse routes.
                self.require("admin", "POST", "/api/routes", self.route_payload(shipments, driver, vehicle), status=400)
        route = self.new_route([first], driver, vehicle)
        self.require("manager", "POST", "/api/routes", self.route_payload([self.new_shipment()], driver, vehicle), status=409)
        self.require("manager", "POST", f'/api/routes/{route["id"]}/scan', {"awb": heavy["awb"]}, status=400)
        self.require("manager", "POST", f'/api/routes/{route["id"]}/scan', {"awb": reverse["awb"]}, status=400)
        self.require("manager", "POST", f'/api/routes/{route["id"]}/scan', {"awb": complete["awb"]}, status=400)

    def test_driver_location_updates_and_employee_permissions(self):
        driver = self.new_driver()
        self.assign_employee(driver)
        shipment = self.new_shipment(driver_id=driver["id"])
        location, _ = self.require("employee", "PATCH", f'/api/drivers/{driver["id"]}/location', {
            "location_text": "Isolated Jaazan checkpoint", "latitude": 16.8894, "longitude": 42.5706,
        })
        self.assertEqual(location["latitude"], 16.8894)
        detail, _ = self.require("admin", "GET", f'/api/shipments/{shipment["awb"]}')
        self.assertEqual(detail["driver_location"], location["location_text"])
        other = self.new_driver()
        self.require("employee", "PATCH", f'/api/drivers/{other["id"]}/location', {"location_text": "Forbidden fixture"}, status=403)

    def test_malformed_driver_gps_returns_400_without_changes(self):
        driver = self.new_driver()
        before = table_snapshot(self.db, "drivers", where="WHERE id=?", params=(driver["id"],))
        for coordinates in (
            {"latitude": "invalid", "longitude": 42}, {"latitude": "NaN", "longitude": 42},
            {"latitude": 91, "longitude": 42}, {"latitude": 16, "longitude": -181},
        ):
            with self.subTest(coordinates=coordinates):
                self.require("admin", "PATCH", f'/api/drivers/{driver["id"]}/location', {"location_text": "Invalid GPS fixture", **coordinates}, status=400)
                self.assertEqual(table_snapshot(self.db, "drivers", where="WHERE id=?", params=(driver["id"],)), before)

    def test_qr_and_barcode_svg_signatures(self):
        shipment = self.new_shipment()
        for kind in ("qr", "barcode"):
            with self.subTest(kind=kind):
                svg, headers = self.require("admin", "GET", f'/api/shipments/{shipment["awb"]}/{kind}')
                self.assertIn("image/svg+xml", headers["content-type"])
                self.assertIn(b"<svg", svg)
                self.assertEqual(ET.fromstring(svg).tag.split("}")[-1], "svg")
                if kind == "barcode":
                    self.assertIn(shipment["awb"].encode("ascii"), svg)
                self.require(None, "GET", f'/api/shipments/{shipment["awb"]}/{kind}', status=401)

    def test_report_pdf_xlsx_signatures_and_locales(self):
        shipment = self.new_shipment()
        for role in ("admin", "manager"):
            for lang in ("ar", "en", "ur", "hi"):
                for fmt in ("pdf", "xlsx"):
                    with self.subTest(role=role, lang=lang, format=fmt):
                        query = urlencode({"format": fmt, "lang": lang, "period": "year", "start": "2000-01-01T00:00:00Z", "end": "2100-01-01T00:00:00Z"})
                        raw, headers = self.require(role, "GET", "/api/reports/shipments?" + query)
                        self.assertIn("attachment", headers["content-disposition"])
                        self.assertIn("." + fmt, headers["content-disposition"])
                        if fmt == "pdf":
                            self.assertEqual(headers["content-type"], "application/pdf")
                            self.assertTrue(raw.startswith(b"%PDF-"))
                            self.assertIn(b"%%EOF", raw[-100:])
                        else:
                            self.assertEqual(headers["content-type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                            with zipfile.ZipFile(BytesIO(raw)) as workbook:
                                self.assertIsNone(workbook.testzip())
                                self.assertIn("[Content_Types].xml", workbook.namelist())
                                ET.fromstring(workbook.read("xl/workbook.xml"))
                                sheets = [name for name in workbook.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")]
                                self.assertTrue(sheets)
                                xml = b"".join(workbook.read(name) for name in sheets)
                                headings = []
                                for name in sheets:
                                    root = ET.fromstring(workbook.read(name))
                                    headings.extend(node.text for node in root.iter() if node.tag.split("}")[-1] == "t")
                                if "xl/sharedStrings.xml" in workbook.namelist():
                                    xml += workbook.read("xl/sharedStrings.xml")
                                    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
                                    headings.extend(node.text for node in root.iter() if node.tag.split("}")[-1] == "t")
                                for heading in REPORT_MONEY_LABELS[lang]:
                                    self.assertIn(heading, headings)
                                self.assertIn(shipment["awb"].encode("ascii"), xml)
        denied_query = "?format=pdf&lang=en&period=year&start=2000-01-01&end=2100-01-01"
        self.require(None, "GET", "/api/reports/shipments" + denied_query, status=401)
        self.require("employee", "GET", "/api/reports/shipments" + denied_query, status=403)

    def test_direct_delivered_patch_is_blocked_for_every_role(self):
        driver = self.new_driver()
        self.assign_employee(driver)
        shipment = self.new_shipment(driver_id=driver["id"])
        before = self.shipment_snapshot(shipment)
        for role in ("admin", "manager", "employee"):
            with self.subTest(role=role):
                self.require(role, "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": DELIVERED}, status=409)
                self.assertEqual(self.shipment_snapshot(shipment), before)
        self.require("admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": DELIVERED, "eta": "Must not be written"}, status=409)
        self.assertEqual(self.shipment_snapshot(shipment), before)

    def test_complete_pod_via_otp_signature_and_photo(self):
        driver = self.new_driver()
        self.assign_employee(driver)
        shipment = self.new_shipment(driver_id=driver["id"])
        self.finish(shipment, role="employee")
        detail, _ = self.require("admin", "GET", f'/api/shipments/{shipment["awb"]}')
        self.assertEqual(detail["status"], DELIVERED)
        self.assertEqual(detail["payment_status"], "تم التحصيل عند التسليم")
        proof, _ = self.require("employee", "GET", f'/api/shipments/{shipment["awb"]}/pod')
        self.assertEqual(proof["recipient_name"], "Isolated receiving customer")
        self.assertEqual(proof["signature_data"], PNG)
        self.assertEqual(proof["photo_data"], PNG)
        self.assertIsNotNone(self.query("SELECT verified_at FROM delivery_otps WHERE shipment_id=?", (shipment["id"],))[0]["verified_at"])
        self.assertEqual(len(self.query("SELECT id FROM shipment_events WHERE shipment_id=? AND status=?", (shipment["id"], DELIVERED))), 1)

    def test_latest_otp_supersedes_old_and_invalid_attempt_is_counted(self):
        shipment = self.new_shipment()
        with mock.patch.object(SERVER.secrets, "randbelow", side_effect=[111111, 222222]):
            old = self.otp(shipment)
            fresh = self.otp(shipment)
        self.assertNotEqual(old, fresh)
        self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(old), status=400)
        challenges = self.query("SELECT attempts,verified_at FROM delivery_otps WHERE shipment_id=? ORDER BY id", (shipment["id"],))
        self.assertEqual(challenges[-1]["attempts"], 1)
        self.assertIsNone(challenges[-1]["verified_at"])
        self.assertEqual(self.query("SELECT count(*) n FROM pod_records WHERE shipment_id=?", (shipment["id"],))[0]["n"], 0)
        self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(fresh))

    def test_pod_validation_does_not_complete_or_consume_valid_otp(self):
        shipment = self.new_shipment()
        code = self.otp(shipment)
        before = self.shipment_snapshot(shipment)
        for changes in (
            {"signature_data": ""}, {"signature_data": "invalid"},
            {"recipient_id_suffix": "0000"}, {"latitude": "invalid"},
            {"latitude": 91}, {"longitude": "NaN"}, {"longitude": 181},
        ):
            with self.subTest(changes=changes):
                self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(code, **changes), status=400)
                self.assertEqual(self.shipment_snapshot(shipment), before)
        self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(code))

    def test_fake_or_corrupt_png_signature_rejected_without_consuming_otp(self):
        shipment = self.new_shipment()
        code = self.otp(shipment)
        before = self.shipment_snapshot(shipment)
        invalid_images = (
            b"This is not an image, despite its data URL MIME type.",
            b"\x89PNG\r\n\x1a\ninvalid PNG chunks",
            VALID_PNG_BYTES[:24],
            VALID_PNG_BYTES[:29] + bytes([VALID_PNG_BYTES[29] ^ 0xFF]) + VALID_PNG_BYTES[30:],
        )
        for index, image in enumerate(invalid_images):
            with self.subTest(image=index):
                data_url = "data:image/png;base64," + base64.b64encode(image).decode("ascii")
                result, _ = self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(code, signature_data=data_url), status=400)
                self.assertEqual(result["error"], "Signature must be a valid PNG image.")
                self.assertEqual(self.shipment_snapshot(shipment), before)
        self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(code))

    def test_expired_otp_cannot_complete_delivery(self):
        shipment = self.new_shipment()
        code = self.otp(shipment)
        self.execute("UPDATE delivery_otps SET expires_at=0 WHERE shipment_id=?", (shipment["id"],))
        before = self.shipment_snapshot(shipment)
        self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(code), status=400)
        self.assertEqual(self.shipment_snapshot(shipment), before)

    def test_sender_payment_required_before_otp(self):
        shipment = self.new_shipment(payment_method="sender", cod=0)
        self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/otp', {}, status=409)
        self.require("admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"payment_status": "مدفوع"})
        self.finish(shipment)

    def test_completed_rollback_and_repeated_pod_preserve_all_evidence(self):
        driver = self.new_driver()
        self.assign_employee(driver)
        shipment = self.new_shipment(driver_id=driver["id"])
        self.finish(shipment)
        before = self.shipment_snapshot(shipment)
        for role in ("admin", "manager", "employee"):
            with self.subTest(role=role):
                rollback_status = "جاهز للتسليم" if role == "employee" else "قيد النقل"
                self.require(role, "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": rollback_status}, status=409)
                self.assertEqual(self.shipment_snapshot(shipment), before)
                self.require(role, "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": DELIVERED})
                self.assertEqual(self.shipment_snapshot(shipment), before)
        self.require("admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": "جاهز للتسليم", "eta": "Must not be written"}, status=409)
        self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload("123456", note="Must not replace original proof"), status=409)
        self.require("admin", "POST", f'/api/shipments/{shipment["awb"]}/otp', {}, status=409)
        self.assertEqual(self.shipment_snapshot(shipment), before)

    def test_completed_assignment_and_eta_changes_are_blocked_without_partial_writes(self):
        driver, replacement = self.new_driver(), self.new_driver()
        shipment = self.new_shipment(driver_id=driver["id"])
        self.finish(shipment)
        before = self.shipment_snapshot(shipment)
        for role in ("admin", "manager"):
            for payload in ({"driver_id": replacement["id"]}, {"eta": "Must not replace completed ETA"},
                            {"status": DELIVERED, "eta": "Must not replace completed ETA"},
                            {"status": DELIVERED, "driver_id": replacement["id"]}):
                with self.subTest(role=role, fields=tuple(payload)):
                    self.require(role, "PATCH", f'/api/shipments/{shipment["awb"]}', payload, status=409)
                    self.assertEqual(self.shipment_snapshot(shipment), before)

    def test_legacy_completed_records_remain_untouched_and_noop(self):
        existing = self.query("SELECT id,awb FROM shipments WHERE status=? ORDER BY id LIMIT 1", (DELIVERED,))
        self.assertTrue(existing, "Master fixture should retain an existing completed delivery")
        shipment = existing[0]
        before = self.shipment_snapshot(shipment)
        self.require("admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": DELIVERED})
        self.require("manager", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": "قيد النقل"}, status=409)
        SERVER.init_db()
        self.assertEqual(self.shipment_snapshot(shipment), before)

    def test_route_start_and_arrival_preserve_completed_child(self):
        driver, vehicle = self.new_driver(), self.new_vehicle()
        complete, pending = self.new_shipment(), self.new_shipment()
        route = self.new_route([complete, pending], driver, vehicle)
        # Historical completed manifest children remain immutable. New parcels
        # must be received by the branch before entering the POD workflow.
        self.execute("UPDATE shipments SET status='تم الاستلام',stage='تم التسليم' WHERE id=?", (complete['id'],))
        before = self.shipment_snapshot(complete)
        for route_status, shipment_status in (("في الطريق", "قيد النقل"), ("وصلت", "قيد النقل")):
            self.require("manager", "POST", f'/api/routes/{route["id"]}', {"status": route_status})
            self.assertEqual(self.shipment_snapshot(complete), before)
            self.assertEqual(self.query("SELECT status FROM shipments WHERE id=?", (pending["id"],))[0]["status"], shipment_status)

    def test_parallel_pod_creates_one_immutable_proof(self):
        shipment = self.new_shipment()
        code = self.otp(shipment)
        cookie = self.client("admin").cookie
        barrier = threading.Barrier(2)

        def submit():
            client = APIClient(self.port, cookie)
            barrier.wait(timeout=10)
            return client.request("POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload(code))[0]

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit), pool.submit(submit)]
            statuses = sorted(future.result(timeout=45) for future in futures)
        self.assertEqual(statuses, [200, 409])
        self.assertEqual(self.query("SELECT count(*) n FROM pod_records WHERE shipment_id=?", (shipment["id"],))[0]["n"], 1)
        self.assertEqual(self.query("SELECT count(*) n FROM shipment_events WHERE shipment_id=? AND status=?", (shipment["id"], DELIVERED))[0]["n"], 1)
        self.assertEqual(self.query("SELECT count(*) n FROM sms_outbox WHERE purpose='delivery_confirmation' AND message LIKE ?", ("%" + shipment["awb"] + "%",))[0]["n"], 1)

    def test_demo_reset_is_admin_only_and_preserves_real_records_users(self):
        driver = self.new_driver()
        shipment = self.new_shipment(driver_id=driver["id"])
        self.require("admin", "POST", "/api/clients", {"name": "Real test client", "mobile": "+966500000005", "city": "جدة"}, status=201)
        self.require("admin", "POST", "/api/campaigns", {"name": "Real test campaign", "campaign_type": "خصم", "status": "مسودة", "discount_percent": 5}, status=201)
        # A demo-marked driver referenced by a remaining real shipment must stay.
        self.execute("UPDATE drivers SET is_demo=1 WHERE id=?", (driver["id"],))
        protected = table_snapshot(self.db, "drivers", where="WHERE id=?", params=(driver["id"],))
        users = table_snapshot(self.db, "users")
        real = {table: table_snapshot(self.db, table, where="WHERE is_demo=0") for table in ("shipments", "drivers", "clients", "campaigns")}
        for role in (None, "employee", "manager"):
            self.require(role, "POST", "/api/admin/reset-demo", {}, status=401 if role is None else 403)
        reset, _ = self.require("admin", "POST", "/api/admin/reset-demo", {})
        self.assertTrue(reset["ok"])
        self.assertEqual(table_snapshot(self.db, "users"), users)
        for table, snapshot in real.items():
            self.assertEqual(table_snapshot(self.db, table, where="WHERE is_demo=0"), snapshot)
        self.assertEqual(table_snapshot(self.db, "drivers", where="WHERE id=?", params=(driver["id"],)), protected)
        self.assertEqual(self.query("SELECT count(*) n FROM shipments WHERE is_demo=1")[0]["n"], 0)
        self.assertEqual(self.query("SELECT value FROM app_settings WHERE key='demo_data_disabled'")[0]["value"], "1")
        self.assertEqual(self.query("SELECT awb FROM shipments WHERE id=?", (shipment["id"],))[0]["awb"], shipment["awb"])
        after = business_snapshot(self.db)
        SERVER.init_db()
        SERVER.init_db()
        self.assertEqual(business_snapshot(self.db, reference=after), after)

    def test_demo_reset_keeps_driver_referenced_by_remaining_route(self):
        driver, vehicle = self.new_driver(), self.new_vehicle()
        shipment = self.new_shipment()
        route = self.new_route([shipment], driver, vehicle)
        self.execute("UPDATE drivers SET is_demo=1 WHERE id=?", (driver["id"],))
        self.execute("UPDATE shipments SET is_demo=1 WHERE id=?", (shipment["id"],))
        before = table_snapshot(self.db, "route_runs", where="WHERE id=?", params=(route["id"],))
        self.require("admin", "POST", "/api/admin/reset-demo", {})
        self.assertEqual(table_snapshot(self.db, "route_runs", where="WHERE id=?", params=(route["id"],)), before)
        self.assertEqual(self.query("SELECT count(*) n FROM drivers WHERE id=?", (driver["id"],))[0]["n"], 1)
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_demo_reset_keeps_driver_referenced_by_user(self):
        driver = self.new_driver()
        self.assign_employee(driver)
        self.execute("UPDATE drivers SET is_demo=1 WHERE id=?", (driver["id"],))
        before_driver = table_snapshot(self.db, "drivers", where="WHERE id=?", params=(driver["id"],))
        before_users = table_snapshot(self.db, "users")
        self.require("admin", "POST", "/api/admin/reset-demo", {})
        self.assertEqual(table_snapshot(self.db, "drivers", where="WHERE id=?", params=(driver["id"],)), before_driver)
        self.assertEqual(table_snapshot(self.db, "users"), before_users)

    def test_sms_transport_remains_explicitly_demo_only(self):
        shipment = self.new_shipment()
        self.finish(shipment)
        rows = self.query("SELECT delivery FROM sms_outbox WHERE message LIKE ?", ("%" + shipment["awb"] + "%",))
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(row["delivery"] == "demo" for row in rows))
        self.assertEqual(os.environ.get("TWILIO_ACCOUNT_SID"), "")
        self.assertEqual(os.environ.get("TWILIO_AUTH_TOKEN"), "")
        self.assertEqual(os.environ.get("TWILIO_FROM_NUMBER"), "")


class JSONTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.checks = []
        self.started = {}

    def startTest(self, test):
        self.started[test.id()] = time.monotonic()
        super().startTest(test)

    def record(self, test, outcome, detail=""):
        self.checks.append({
            "test": test.id(), "outcome": outcome,
            "seconds": round(time.monotonic() - self.started.get(test.id(), time.monotonic()), 3),
            "detail": detail,
        })

    def addSuccess(self, test):
        self.record(test, "passed")
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.record(test, "failed", self._exc_info_to_string(err, test))
        super().addFailure(test, err)

    def addError(self, test, err):
        self.record(test, "error", self._exc_info_to_string(err, test))
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.record(test, "skipped", reason)
        super().addSkip(test, reason)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.record(subtest, "failed", self._exc_info_to_string(err, test))
        super().addSubTest(test, subtest, err)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, help="Optional result JSON under an outputs directory")
    args = parser.parse_args()
    if args.json_output is not None:
        destination = args.json_output.resolve()
        # This project is itself an output. Also accept its own outputs folder.
        if not destination.is_relative_to(PROJECT) or "outputs" not in destination.parts:
            parser.error("Result JSON must be inside this project's outputs location")
        if destination == MASTER_DB.resolve() or destination.suffix.lower() != ".json":
            parser.error("Result destination must be a .json file, never the database")
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BaselineRegression)
    result = unittest.TextTestRunner(verbosity=2, resultclass=JSONTestResult).run(suite)
    if args.json_output is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": str(PROJECT), "master_access": "SQLite read-only backup only",
            "http_target": "ephemeral loopback server with disposable DB",
            "external_sms": "disabled; demo outbox in isolated database only",
            "successful": result.wasSuccessful(), "tests_run": result.testsRun,
            "failure_count": len(result.failures), "error_count": len(result.errors),
            "skipped_count": len(result.skipped), "seconds": round(time.monotonic() - started, 3),
            "checks": result.checks,
        }
        destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Result JSON: {destination}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
