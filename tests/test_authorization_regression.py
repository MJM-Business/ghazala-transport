"""Phase 3 authorization regression suite; all writes use disposable DBs.

Run with the application environment after Phase 3 contracts are integrated::

    python tests/test_authorization_regression.py
    python tests/test_authorization_regression.py --json-output outputs/authorization-tests.json

The inherited fixture utilities create a SQLite read-only backup of the master,
then direct every API request to an ephemeral loopback server with a temporary
database. Twilio credentials are blank and external transports are blocked.
"""

from contextlib import closing
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import sqlite3
import sys
import time
import unittest
from io import BytesIO
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_baseline_regression as baseline


ALL_PERMISSIONS = {
    "shipments.read", "shipments.create", "shipments.edit", "shipments.status", "shipments.assign", "shipments.payment",
    "pod.read", "pod.create", "drivers.read", "drivers.manage", "drivers.location", "routes.read", "routes.manage",
    "branches.read", "branches.manage", "vehicles.read", "vehicles.manage", "clients.read", "clients.manage",
    "pricing.read", "pricing.manage", "campaigns.read", "campaigns.manage", "reports.read", "users.manage", "audit.read",
    "stats.read", "demo.reset",
}
EXPECTED_PERMISSIONS = {
    "system_admin": ALL_PERMISSIONS,
    "branch_manager": {
        "shipments.read", "shipments.create", "shipments.edit", "shipments.status", "shipments.assign", "shipments.payment",
        "pod.read", "pod.create", "drivers.read", "drivers.manage", "drivers.location", "routes.read", "routes.manage",
        "branches.read", "branches.manage", "vehicles.read", "clients.read", "clients.manage", "pricing.read", "campaigns.read", "reports.read", "stats.read",
    },
    "office_employee": {
        "shipments.read", "shipments.create", "shipments.edit", "shipments.status", "shipments.assign", "pod.read", "pod.create",
        "drivers.read", "routes.read", "branches.read", "vehicles.read", "clients.read", "pricing.read", "campaigns.read", "stats.read",
    },
    "courier": {
        "shipments.read", "shipments.status", "pod.read", "pod.create", "drivers.read", "drivers.location", "routes.read",
        "branches.read", "vehicles.read", "stats.read",
    },
    "accountant": {"shipments.read", "shipments.payment", "branches.read", "clients.read", "pricing.read", "reports.read", "stats.read"},
    "customer": set(),
}


class AuthorizationClient(baseline.APIClient):
    """Request-level browser headers for Origin and Fetch Metadata checks."""

    def request(self, method, path, data=None, *, extra_headers=None):
        headers = dict(extra_headers or {})
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
            result = json.loads(raw.decode("utf-8")) if "application/json" in result_headers.get("content-type", "") else raw
            return response.status, result, result_headers


class AuthorizationRegression(unittest.TestCase):
    """Reuse fixture helpers, deliberately without inheriting Phase 2 tests."""

    setUpClass = classmethod(baseline.BaselineRegression.setUpClass.__func__)
    tearDownClass = classmethod(baseline.BaselineRegression.tearDownClass.__func__)
    tearDown = baseline.BaselineRegression.tearDown
    assertIsolatedDB = baseline.BaselineRegression.assertIsolatedDB
    query = baseline.BaselineRegression.query
    execute = baseline.BaselineRegression.execute
    require = baseline.BaselineRegression.require
    suffix = baseline.BaselineRegression.suffix
    new_driver = baseline.BaselineRegression.new_driver
    new_vehicle = baseline.BaselineRegression.new_vehicle
    assign_employee = baseline.BaselineRegression.assign_employee
    shipment_payload = baseline.BaselineRegression.shipment_payload
    new_shipment = baseline.BaselineRegression.new_shipment
    route_payload = baseline.BaselineRegression.route_payload
    new_route = baseline.BaselineRegression.new_route
    otp = baseline.BaselineRegression.otp
    pod_payload = baseline.BaselineRegression.pod_payload
    finish = baseline.BaselineRegression.finish
    shipment_snapshot = baseline.BaselineRegression.shipment_snapshot

    def setUp(self):
        baseline.BaselineRegression.setUp(self)
        self.accounts = {}
        self.account_clients = {}

    def client(self, role="admin"):
        if role in self.accounts:
            if role not in self.account_clients:
                account = self.accounts[role]
                client = AuthorizationClient(self.port)
                status, result, _ = client.request("POST", "/api/login", {
                    "username": account["username"], "password": account["test_password"],
                })
                self.assertEqual(status, 200, result)
                self.account_clients[role] = client
            return self.account_clients[role]
        client = baseline.BaselineRegression.client(self, role)
        # Preserve the authenticated cookie while adding browser-header support.
        if not isinstance(client, AuthorizationClient):
            client = AuthorizationClient(self.port, client.cookie)
            self.clients[role] = client
        return client

    def create_account(self, label, role, branch_ids=None, primary_branch_id=None, driver_id=None, password="TestAccount123!"):
        suffix = self.suffix().replace("-", "")
        data = {
            "username": f"phase3-{label}-{suffix}@example.invalid", "display_name": "Isolated " + label,
            "password": password, "role": role, "branch_ids": list(branch_ids or []),
            "primary_branch_id": primary_branch_id, "driver_id": driver_id,
            "mobile": "+966500000010", "national_id": "P3-" + suffix,
        }
        account, _ = self.require("admin", "POST", "/api/users", data, status=201)
        self.assertNotIn("password_hash", account)
        account["test_password"] = password
        self.accounts[label] = account
        return account

    def office_fixtures(self):
        if hasattr(self, "offices"):
            return self.offices
        self.offices = {}
        for label, city in (("jed_a", "جدة"), ("jed_b", "جدة"), ("jaz_a", "جازان"), ("jaz_b", "جازان")):
            branch, _ = self.require("admin", "POST", "/api/branches", {
                "code": "P3-" + label.upper() + "-" + self.suffix(), "name": "Isolated office " + label,
                "city": city, "address": "Test-only office address", "phone": "+966500000020",
                "coverage": city,
            }, status=201)
            self.offices[label] = branch
        return self.offices

    def office_driver(self, office, label):
        branch = self.office_fixtures()[office]
        driver, _ = self.require("admin", "POST", "/api/drivers", {
            "name": "Isolated driver " + label, "national_id": "P3DR-" + self.suffix(),
            "mobile": "+966500000041" if label == "own" else "+966500000049",
            "branch": branch["city"], "branch_id": branch["id"], "status": "متاح",
            "location_text": "Isolated office checkpoint " + label,
        }, status=201)
        return driver

    def office_vehicle(self, office):
        vehicle, _ = self.require("admin", "POST", "/api/vehicles", {
            "plate": "P3VEH-" + self.suffix(), "vehicle_type": "شاحنة نقل", "capacity_kg": 100,
            "branch_ids": [self.office_fixtures()[office]["id"]],
        }, status=201)
        return vehicle

    def canonical_fixtures(self):
        if hasattr(self, "role_fixtures"):
            return self.role_fixtures
        offices = self.office_fixtures()
        own_driver = self.office_driver("jed_a", "own")
        other_driver = self.office_driver("jed_b", "unrelated")
        for role in EXPECTED_PERMISSIONS:
            branches = [] if role in ("system_admin", "customer") else [offices["jed_a"]["id"]]
            self.create_account(role, role, branches, branches[0] if branches else None,
                                own_driver["id"] if role == "courier" else None)
        own = self.new_office_shipment("jed_a", "jaz_a", driver_id=own_driver["id"])
        incoming = self.new_office_shipment("jaz_a", "jed_a", driver_id=other_driver["id"])
        other = self.new_office_shipment("jed_b", "jaz_b", driver_id=other_driver["id"],
                                         sender_name="Private other-office sender", recipient="Private other-office recipient")
        mixed = self.new_office_shipment("jed_b", "jaz_a", driver_id=other_driver["id"])
        self.role_fixtures = {"offices": offices, "own_driver": own_driver, "other_driver": other_driver,
                              "own": own, "incoming": incoming, "other": other, "mixed": mixed}
        return self.role_fixtures

    def office_route(self, shipment, driver, origin, destination):
        offices = self.office_fixtures()
        vehicle = self.office_vehicle(origin)
        payload = self.route_payload([shipment], driver, vehicle,
                                     origin=offices[origin]["city"], destination=offices[destination]["city"],
                                     origin_branch_id=offices[origin]["id"], destination_branch_id=offices[destination]["id"])
        route, _ = self.require("admin", "POST", "/api/routes", payload, status=201)
        return route

    def deny_outside(self, role, method, path, data=None):
        status, result, _ = self.client(role).request(method, path, data)
        self.assertIn(status, (403, 404), result)
        return result

    def workbook_text(self, raw):
        with zipfile.ZipFile(BytesIO(raw)) as workbook:
            text = []
            for name in workbook.namelist():
                if name == "xl/sharedStrings.xml" or (name.startswith("xl/worksheets/") and name.endswith(".xml")):
                    text.extend(node.text or "" for node in ET.fromstring(workbook.read(name)).iter() if node.tag.split("}")[-1] == "t")
        return "\n".join(text)

    def new_office_shipment(self, origin, destination, *, role="admin", **overrides):
        offices = self.office_fixtures()
        return self.new_shipment(role=role, origin=offices[origin]["city"], destination=offices[destination]["city"],
                                 sender_branch_id=offices[origin]["id"], recipient_branch=offices[destination]["code"], **overrides)

    def audit_entries(self):
        rows, _ = self.require("admin", "GET", "/api/audit?limit=100")
        self.assertIsInstance(rows, list)
        return rows

    def test_legacy_accounts_extend_safe_identity_without_changing_credentials(self):
        expected = {"admin": "system_admin", "manager": "branch_manager", "employee": "courier"}
        for legacy, canonical in expected.items():
            with self.subTest(legacy=legacy):
                me, _ = self.require(legacy, "GET", "/api/me")
                user = me["user"]
                self.assertEqual(user["role"], legacy)
                self.assertEqual(user["access_role"], canonical)
                self.assertIsInstance(user["permissions"], list)
                self.assertIsInstance(user["branches"], list)
                self.assertIn("primary_branch_id", user)
                self.assertNotIn("password_hash", user)

    def test_six_canonical_roles_have_exact_permissions_and_office_memberships(self):
        self.canonical_fixtures()
        for role, permissions in EXPECTED_PERMISSIONS.items():
            with self.subTest(role=role):
                user = self.require(role, "GET", "/api/me")[0]["user"]
                self.assertEqual(user["access_role"], role)
                self.assertEqual(set(user["permissions"]), permissions)
                branch_ids = {branch["id"] for branch in user["branches"]}
                expected = set() if role in ("system_admin", "customer") else {self.offices["jed_a"]["id"]}
                self.assertEqual(branch_ids, expected)
                if expected:
                    self.assertEqual(user["primary_branch_id"], self.offices["jed_a"]["id"])
                self.assertNotIn("password_hash", user)

    def test_operational_read_api_permission_matrix_for_all_roles(self):
        self.canonical_fixtures()
        endpoints = {
            "/api/shipments": "shipments.read", "/api/drivers": "drivers.read", "/api/routes": "routes.read",
            "/api/branches": "branches.read", "/api/vehicles": "vehicles.read", "/api/clients": "clients.read",
            "/api/notifications": "routes.read",
            "/api/pricing": "pricing.read", "/api/campaigns": "campaigns.read", "/api/stats": "stats.read",
            "/api/users": "users.manage", "/api/audit": "audit.read",
            "/api/reports/shipments?format=xlsx&lang=en&period=year&start=2000-01-01&end=2100-01-01": "reports.read",
        }
        for role, permissions in EXPECTED_PERMISSIONS.items():
            for path, permission in endpoints.items():
                with self.subTest(role=role, path=path):
                    self.require(role, "GET", path, status=200 if permission in permissions else 403)

    def test_same_city_office_scope_is_precise_for_lists_and_search(self):
        fixtures = self.canonical_fixtures()
        own, incoming, other, mixed = (fixtures[key] for key in ("own", "incoming", "other", "mixed"))
        for role in ("branch_manager", "office_employee", "accountant"):
            with self.subTest(role=role):
                rows, _ = self.require(role, "GET", "/api/shipments")
                awbs = {row["awb"] for row in rows}
                self.assertEqual(awbs, {own["awb"], incoming["awb"]})
                for hidden in (other, mixed):
                    found, _ = self.require(role, "GET", "/api/shipments?" + urlencode({"q": hidden["awb"]}))
                    self.assertEqual(found, [])
                    self.deny_outside(role, "GET", f'/api/shipments/{hidden["awb"]}')
        courier, _ = self.require("courier", "GET", "/api/shipments")
        self.assertEqual({row["awb"] for row in courier}, {own["awb"]})
        system, _ = self.require("system_admin", "GET", "/api/shipments")
        self.assertTrue({row["awb"] for row in (own, incoming, other, mixed)}.issubset({row["awb"] for row in system}))

    def test_courier_and_accountant_projections_hide_restricted_data(self):
        fixtures = self.canonical_fixtures()
        for endpoint in ("/api/shipments", f'/api/shipments/{fixtures["own"]["awb"]}'):
            for role in ("courier", "accountant"):
                with self.subTest(role=role, endpoint=endpoint):
                    payload, _ = self.require(role, "GET", endpoint)
                    rows = payload if isinstance(payload, list) else [payload]
                    for row in rows:
                        self.assertFalse({"sender_id", "recipient_id", "driver_national_id"}.intersection(row))
                        if role == "courier":
                            self.assertFalse({"sender_phone", "sender_address", "shipping_fee", "vat_amount", "total_fee", "insurance_fee"}.intersection(row))
                            self.assertIn("phone", row)
                            self.assertIn("recipient_address", row)
                            self.assertIn("cod", row)
                        else:
                            self.assertFalse({"sender_phone", "phone", "recipient_address", "signature_data", "photo_data"}.intersection(row))
                            self.assertIn("cod", row)
                            self.assertIn("total_fee", row)
                            self.assertIn("payment_status", row)

    def test_scoped_creation_requires_owned_origin_and_valid_destination_office(self):
        fixtures = self.canonical_fixtures()
        for role in ("branch_manager", "office_employee"):
            with self.subTest(role=role):
                self.new_office_shipment("jed_a", "jaz_b", role=role)
                outside = self.shipment_payload(sender_branch_id=self.offices["jed_b"]["id"], recipient_branch=self.offices["jaz_a"]["code"])
                before = baseline.table_snapshot(self.db, "shipments")
                self.deny_outside(role, "POST", "/api/shipments", outside)
                self.assertEqual(baseline.table_snapshot(self.db, "shipments"), before)
                invalid = self.shipment_payload(sender_branch_id=self.offices["jed_a"]["id"], recipient_branch=self.offices["jed_b"]["code"])
                self.require(role, "POST", "/api/shipments", invalid, status=400)
        for role in ("courier", "accountant", "customer"):
            self.require(role, "POST", "/api/shipments", self.shipment_payload(sender_branch_id=self.offices["jed_a"]["id"], recipient_branch=self.offices["jaz_a"]["code"]), status=403)

    def test_shipment_edit_assignment_payment_and_status_permission_matrix(self):
        fixtures = self.canonical_fixtures()
        actions = (
            ("shipments.edit", {"eta": "Permission matrix ETA"}),
            ("shipments.assign", {"driver_id": fixtures["own_driver"]["id"]}),
            ("shipments.payment", {"payment_status": "مدفوع"}),
            ("shipments.status", {"status": "قيد النقل"}),
        )
        for role, permissions in EXPECTED_PERMISSIONS.items():
            for permission, data in actions:
                with self.subTest(role=role, permission=permission):
                    shipment = self.new_office_shipment("jed_a", "jaz_a", driver_id=fixtures["own_driver"]["id"], payment_method="sender", cod=0)
                    if role == "courier" and permission == "shipments.status":
                        self.require("admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": "قيد النقل"})
                        self.require("admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": "جاهز للتسليم"})
                        data = {"status": "قيد التوصيل"}
                    before = self.shipment_snapshot(shipment)
                    self.require(role, "PATCH", f'/api/shipments/{shipment["awb"]}', data, status=200 if permission in permissions else 403)
                    if permission not in permissions:
                        self.assertEqual(self.shipment_snapshot(shipment), before)

    def test_object_scope_blocks_read_write_qr_barcode_and_pod_access(self):
        fixtures = self.canonical_fixtures()
        other = fixtures["other"]
        before = self.shipment_snapshot(other)
        for role in ("branch_manager", "office_employee", "courier", "accountant"):
            for path in (f'/api/shipments/{other["awb"]}', f'/api/shipments/{other["awb"]}/qr',
                         f'/api/shipments/{other["awb"]}/barcode', f'/api/shipments/{other["awb"]}/pod'):
                with self.subTest(role=role, path=path):
                    self.deny_outside(role, "GET", path)
            with self.subTest(role=role, action="write"):
                self.deny_outside(role, "PATCH", f'/api/shipments/{other["awb"]}', {"status": "قيد النقل", "eta": "Forbidden update"})
                self.deny_outside(role, "POST", f'/api/shipments/{other["awb"]}/otp', {})
                self.deny_outside(role, "POST", f'/api/shipments/{other["awb"]}/pod', self.pod_payload("000000"))
        self.assertEqual(self.shipment_snapshot(other), before)

    def test_route_and_driver_lists_follow_precise_office_and_assignment_scope(self):
        fixtures = self.canonical_fixtures()
        own_route = self.office_route(fixtures["own"], fixtures["own_driver"], "jed_a", "jaz_a")
        other_route = self.office_route(fixtures["other"], fixtures["other_driver"], "jed_b", "jaz_b")
        for role in ("branch_manager", "office_employee", "courier"):
            with self.subTest(role=role):
                routes, _ = self.require(role, "GET", "/api/routes")
                self.assertEqual({route["id"] for route in routes}, {own_route["id"]})
                self.assertNotIn(other_route["code"], json.dumps(routes, ensure_ascii=False))
                drivers, _ = self.require(role, "GET", "/api/drivers")
                self.assertEqual({driver["id"] for driver in drivers}, {fixtures["own_driver"]["id"]})
                self.deny_outside(role, "POST", f'/api/routes/{other_route["id"]}', {"status": "في الطريق"})
                self.deny_outside(role, "PATCH", f'/api/drivers/{fixtures["other_driver"]["id"]}/location', {"location_text": "Forbidden location"})

    def test_manager_route_creation_valid_trip_path_and_wrong_office_loading(self):
        fixtures = self.canonical_fixtures()
        vehicle = self.office_vehicle("jed_a")
        payload = self.route_payload([fixtures["own"]], fixtures["own_driver"], vehicle,
                                     origin_branch_id=self.offices["jed_a"]["id"], destination_branch_id=self.offices["jaz_a"]["id"])
        for role in ("office_employee", "courier", "accountant", "customer"):
            self.require(role, "POST", "/api/routes", payload, status=403)
        route, _ = self.require("branch_manager", "POST", "/api/routes", payload, status=201)
        wrong_office = self.new_office_shipment("jed_a", "jaz_b")
        before = self.shipment_snapshot(wrong_office)
        status, _, _ = self.client("branch_manager").request("POST", f'/api/routes/{route["id"]}/scan', {"awb": wrong_office["awb"]})
        self.assertIn(status, (400, 403, 409))
        self.assertEqual(self.shipment_snapshot(wrong_office), before)
        self.require("branch_manager", "POST", f'/api/routes/{route["id"]}', {"status": "في الطريق"})
        self.assertEqual(self.query("SELECT status FROM shipments WHERE id=?", (fixtures["own"]["id"],))[0]["status"], "قيد النقل")
        self.require("branch_manager", "POST", f'/api/routes/{route["id"]}', {"status": "وصلت"})
        self.assertEqual(self.query("SELECT status FROM shipments WHERE id=?", (fixtures["own"]["id"],))[0]["status"], "جاهز للتسليم")

    def test_manager_driver_management_requires_actual_office_scope(self):
        fixtures = self.canonical_fixtures()
        data = {
            "name": "Scoped manager driver", "national_id": "MANAGER-" + self.suffix(), "mobile": "+966500000088",
            "branch": "جدة", "branch_id": self.offices["jed_a"]["id"], "location_text": "Manager checkpoint",
        }
        driver, _ = self.require("branch_manager", "POST", "/api/drivers", data, status=201)
        self.require("branch_manager", "PATCH", f'/api/drivers/{driver["id"]}', {"name": "Updated owned driver"})
        for role in ("office_employee", "courier", "accountant", "customer"):
            self.require(role, "POST", "/api/drivers", {**data, "national_id": "DENIED-" + self.suffix()}, status=403)
        self.deny_outside("branch_manager", "POST", "/api/drivers", {**data, "national_id": "OTHER-" + self.suffix(), "branch_id": self.offices["jed_b"]["id"]})
        shipment = self.new_office_shipment("jed_a", "jaz_a")
        before = self.shipment_snapshot(shipment)
        self.deny_outside("branch_manager", "PATCH", f'/api/shipments/{shipment["awb"]}', {"driver_id": fixtures["other_driver"]["id"]})
        self.assertEqual(self.shipment_snapshot(shipment), before)

    def test_clients_scope_and_accountant_limited_projection(self):
        self.canonical_fixtures()
        own, _ = self.require("admin", "POST", "/api/clients", {
            "name": "Owned office client", "mobile": "+966500000060", "city": "جدة",
            "branch_id": self.offices["jed_a"]["id"], "national_id": "Client-private-ID", "credit_limit": 1000,
        }, status=201)
        other, _ = self.require("admin", "POST", "/api/clients", {
            "name": "Hidden same-city client", "mobile": "+966500000069", "city": "جدة",
            "branch_id": self.offices["jed_b"]["id"], "credit_limit": 1000,
        }, status=201)
        for role in ("branch_manager", "office_employee", "accountant"):
            rows, _ = self.require(role, "GET", "/api/clients")
            self.assertEqual({row["id"] for row in rows}, {own["id"]})
            self.deny_outside(role, "PATCH", f'/api/clients/{other["id"]}', {"name": "Forbidden name"})
            if role == "accountant":
                self.assertNotIn("national_id", rows[0])
                self.assertIn("credit_limit", rows[0])
        self.require("branch_manager", "PATCH", f'/api/clients/{own["id"]}', {"notes": "Scoped manager edit"})
        for role in ("office_employee", "accountant", "courier", "customer"):
            self.require(role, "POST", "/api/clients", {"name": "Forbidden client", "mobile": "+966500000070", "city": "جدة", "branch_id": self.offices["jed_a"]["id"]}, status=403)

    def test_branch_directory_exposes_only_minimal_destination_fields(self):
        self.canonical_fixtures()
        for role in ("branch_manager", "office_employee", "courier", "accountant"):
            with self.subTest(role=role):
                branches, _ = self.require(role, "GET", "/api/branches")
                self.assertEqual({branch["id"] for branch in branches}, {self.offices["jed_a"]["id"]})
                if role in ("branch_manager", "office_employee"):
                    directory, _ = self.require(role, "GET", "/api/branch-directory")
                    self.assertTrue({branch["id"] for branch in self.offices.values()}.issubset({branch["id"] for branch in directory}))
                    for branch in directory:
                        self.assertTrue(set(branch).issubset({"id", "code", "name", "city"}))
                else:
                    self.require(role, "GET", "/api/branch-directory", status=403)
        self.require("customer", "GET", "/api/branch-directory", status=403)

    def test_manager_can_edit_only_owned_branch_basic_fields(self):
        self.canonical_fixtures()
        own, other = self.offices["jed_a"], self.offices["jed_b"]
        updated, _ = self.require("branch_manager", "PATCH", f'/api/branches/{own["id"]}', {
            "name": "Updated owned branch", "address": "Updated branch address", "phone": "+966500000081", "coverage": "Updated coverage",
        })
        self.assertEqual(updated["name"], "Updated owned branch")
        before_other = baseline.table_snapshot(self.db, "branches", where="WHERE id=?", params=(other["id"],))
        self.deny_outside("branch_manager", "PATCH", f'/api/branches/{other["id"]}', {"name": "Forbidden branch edit"})
        self.assertEqual(baseline.table_snapshot(self.db, "branches", where="WHERE id=?", params=(other["id"],)), before_other)
        for data in ({"code": "REWRITE-CODE"}, {"city": "جازان"}, {"is_active": False}):
            with self.subTest(data=data):
                before = baseline.table_snapshot(self.db, "branches", where="WHERE id=?", params=(own["id"],))
                status, _, _ = self.client("branch_manager").request("PATCH", f'/api/branches/{own["id"]}', data)
                self.assertIn(status, (400, 403, 409))
                self.assertEqual(baseline.table_snapshot(self.db, "branches", where="WHERE id=?", params=(own["id"],)), before)

    def test_reports_and_stats_include_only_scoped_records(self):
        fixtures = self.canonical_fixtures()
        path = "/api/reports/shipments?" + urlencode({"format": "xlsx", "lang": "en", "period": "year", "start": "2000-01-01", "end": "2100-01-01"})
        for role in ("branch_manager", "accountant"):
            with self.subTest(role=role):
                stats, _ = self.require(role, "GET", "/api/stats")
                self.assertEqual(stats["total"], 2)
                raw, _ = self.require(role, "GET", path)
                text = self.workbook_text(raw)
                self.assertIn(fixtures["own"]["awb"], text)
                self.assertIn(fixtures["incoming"]["awb"], text)
                self.assertNotIn(fixtures["other"]["awb"], text)
                self.assertNotIn(fixtures["mixed"]["awb"], text)
                if role == "accountant":
                    self.assertNotIn(fixtures["own"]["phone"], text)
                    self.assertNotIn(fixtures["own"]["sender_phone"], text)

    def test_only_system_admin_can_manage_accounts_global_config_or_demo_reset(self):
        self.canonical_fixtures()
        protected = self.accounts["system_admin"]
        for role in ("branch_manager", "office_employee", "courier", "accountant", "customer"):
            endpoints = (
                ("GET", "/api/users", None), ("GET", "/api/audit", None),
                ("POST", "/api/users", {"username": "forged-" + self.suffix() + "@example.invalid", "display_name": "Forbidden admin", "role": "system_admin", "password": "StrongPassword123!"}),
                ("PATCH", f'/api/users/{protected["id"]}', {"role": "system_admin", "is_active": False}),
                ("POST", "/api/vehicles", {"plate": "FORBIDDEN-" + self.suffix(), "capacity_kg": 100}),
                ("POST", "/api/branches", {"code": "FORBIDDEN-" + self.suffix(), "name": "Forbidden branch", "city": "جدة"}),
                ("PATCH", "/api/pricing", {"base_fee": 1}),
                ("POST", "/api/campaigns", {"name": "Forbidden campaign", "campaign_type": "خصم", "discount_percent": 90}),
                ("POST", "/api/admin/reset-demo", {}),
            )
            for method, path, data in endpoints:
                with self.subTest(role=role, method=method, path=path):
                    self.require(role, method, path, data, status=403)
            me = self.require(role, "GET", "/api/me")[0]["user"]
            self.assertEqual(me["access_role"], role)
        self.assertEqual(self.client("system_admin").request("GET", "/api/users")[0], 200)

    def test_membership_update_revokes_old_scope_session_and_preserves_legacy_role(self):
        self.canonical_fixtures()
        account = self.accounts["branch_manager"]
        old = self.client("branch_manager")
        updated, _ = self.require("admin", "PATCH", f'/api/users/{account["id"]}', {
            "branch_ids": [self.offices["jed_b"]["id"]], "primary_branch_id": self.offices["jed_b"]["id"],
        })
        self.assertEqual(updated["role"], "manager")
        self.assertEqual(old.request("GET", "/api/shipments")[0], 401)
        self.account_clients.pop("branch_manager")
        me = self.require("branch_manager", "GET", "/api/me")[0]["user"]
        self.assertEqual({branch["id"] for branch in me["branches"]}, {self.offices["jed_b"]["id"]})
        rows, _ = self.require("branch_manager", "GET", "/api/shipments")
        self.assertEqual({row["awb"] for row in rows}, {self.role_fixtures["other"]["awb"], self.role_fixtures["mixed"]["awb"]})

    def test_invalid_state_jumps_return_conflict_without_partial_writes(self):
        self.canonical_fixtures()
        shipment = self.new_office_shipment("jed_a", "jaz_a")
        before = self.shipment_snapshot(shipment)
        for status in ("جاهز للتسليم", "قيد التوصيل", "تم الاستلام"):
            with self.subTest(status=status):
                self.require("branch_manager", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": status, "eta": "Must not change"}, status=409)
                self.assertEqual(self.shipment_snapshot(shipment), before)
        for status in ("تم استلام الشحنة", "في مكتب الإرسال", "تم الترحيل للنقل", "قيد النقل", "جاهز للتسليم", "قيد التوصيل"):
            self.require("branch_manager", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": status})
        before = self.shipment_snapshot(shipment)
        self.require("branch_manager", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": "قيد النقل"}, status=409)
        self.assertEqual(self.shipment_snapshot(shipment), before)
        self.finish(shipment, role="branch_manager")
        completed = self.shipment_snapshot(shipment)
        self.require("system_admin", "PATCH", f'/api/shipments/{shipment["awb"]}', {"status": "تأخير"}, status=409)
        self.assertEqual(self.shipment_snapshot(shipment), completed)

    def test_otp_and_pod_require_out_for_delivery_and_role_permission(self):
        fixtures = self.canonical_fixtures()
        shipment = fixtures["own"]
        before = self.shipment_snapshot(shipment)
        self.require("branch_manager", "POST", f'/api/shipments/{shipment["awb"]}/otp', {}, status=409)
        self.assertEqual(self.shipment_snapshot(shipment), before)
        for role in ("accountant", "customer"):
            self.require(role, "POST", f'/api/shipments/{shipment["awb"]}/otp', {}, status=403)
            self.require(role, "POST", f'/api/shipments/{shipment["awb"]}/pod', self.pod_payload("000000"), status=403)
        for role in ("system_admin", "branch_manager", "office_employee", "courier"):
            with self.subTest(role=role):
                own = self.new_office_shipment("jed_a", "jaz_a", driver_id=fixtures["own_driver"]["id"])
                self.finish(own, role=role)
                self.require(role, "GET", f'/api/shipments/{own["awb"]}/pod')
                self.require("accountant", "GET", f'/api/shipments/{own["awb"]}/pod', status=403)

    def test_origin_and_fetch_metadata_block_cross_site_mutations(self):
        client = self.client("admin")
        original = baseline.table_snapshot(self.db, "clients")
        payload = {"name": "Cross-site attempt", "mobile": "+966500000030", "city": "جدة"}
        for headers in ({"Origin": "https://example.invalid"}, {"Sec-Fetch-Site": "cross-site"}, {"Origin": "null"}):
            with self.subTest(headers=headers):
                status, result, _ = client.request("POST", "/api/clients", payload, extra_headers=headers)
                self.assertEqual(status, 403, result)
                self.assertEqual(baseline.table_snapshot(self.db, "clients"), original)
        same_origin = {"Origin": f"http://127.0.0.1:{self.port}", "Sec-Fetch-Site": "same-origin"}
        status, result, _ = client.request("POST", "/api/clients", payload, extra_headers=same_origin)
        self.assertEqual(status, 201, result)
        # Origin-less requests used by local scripts remain supported.
        self.require("admin", "POST", "/api/clients", {**payload, "name": "Local script creation"}, status=201)

    def test_login_failure_throttling_is_scoped_to_username_and_ip(self):
        client = AuthorizationClient(self.port)
        username = "unknown-throttle-" + self.suffix() + "@example.invalid"
        for index in range(5):
            with self.subTest(failure=index + 1):
                status, _, _ = client.request("POST", "/api/login", {"username": username, "password": "Wrong123!"})
                self.assertIn(status, (401, 429) if index == 4 else (401,))
        status, result, _ = client.request("POST", "/api/login", {"username": username, "password": "Wrong123!"})
        self.assertEqual(status, 429, result)
        other = "other-throttle-" + self.suffix() + "@example.invalid"
        self.assertEqual(client.request("POST", "/api/login", {"username": other, "password": "Wrong123!"})[0], 401)
        self.assertEqual(self.client("admin").request("GET", "/api/me")[0], 200)

    def test_weak_new_passwords_rejected_and_legacy_passwords_still_work(self):
        for password in ("Aa1", "Abc12345", "Abc123456", "password123", "PASSWORD123", "PasswordOnly", "12345678", "A" + "a" * 255 + "1"):
            with self.subTest(password=password):
                self.require("admin", "POST", "/api/users", {
                    "username": "weak-" + self.suffix() + "@example.invalid", "display_name": "Weak password fixture",
                    "role": "admin", "password": password,
                }, status=400)
        account = self.create_account("strong", "admin")
        self.assertEqual(self.client("strong").request("GET", "/api/me")[1]["user"]["id"], account["id"])
        self.require("strong", "POST", "/api/password", {"current_password": account["test_password"], "new_password": "weakpassword"}, status=400)

    def test_account_deactivation_reactivation_and_explicit_session_revocation(self):
        account = self.create_account("managed", "admin")
        authenticated = self.client("managed")
        updated, _ = self.require("admin", "PATCH", f'/api/users/{account["id"]}', {"is_active": False})
        self.assertEqual(updated["is_active"], 0)
        self.assertEqual(authenticated.request("GET", "/api/shipments")[0], 401)
        self.assertIsNone(authenticated.request("GET", "/api/me")[1]["user"])
        blocked = AuthorizationClient(self.port)
        self.assertEqual(blocked.request("POST", "/api/login", {"username": account["username"], "password": account["test_password"]})[0], 401)
        self.require("admin", "PATCH", f'/api/users/{account["id"]}', {"is_active": True})
        self.assertEqual(authenticated.request("GET", "/api/shipments")[0], 401)
        self.account_clients.pop("managed")
        authenticated = self.client("managed")
        self.require("admin", "PATCH", f'/api/users/{account["id"]}', {"revoke_sessions": True})
        self.assertEqual(authenticated.request("GET", "/api/shipments")[0], 401)

    def test_admin_password_update_revokes_existing_sessions_and_audits_without_secrets(self):
        account = self.create_account("password-change", "admin")
        authenticated = self.client("password-change")
        old_cookie = authenticated.cookie.split("=", 1)[1]
        new_password = "UpdatedPassword456!"
        self.require("admin", "PATCH", f'/api/users/{account["id"]}', {"password": new_password})
        self.assertEqual(authenticated.request("GET", "/api/shipments")[0], 401)
        replacement = AuthorizationClient(self.port)
        self.assertEqual(replacement.request("POST", "/api/login", {"username": account["username"], "password": account["test_password"]})[0], 401)
        self.assertEqual(replacement.request("POST", "/api/login", {"username": account["username"], "password": new_password})[0], 200)
        serialized = json.dumps(self.audit_entries(), ensure_ascii=False)
        for secret in (account["test_password"], new_password, old_cookie, "pbkdf2_sha256$"):
            self.assertNotIn(secret, serialized)

    def test_audit_is_append_only_in_database_and_has_no_mutation_api(self):
        self.create_account("audit-record", "admin")
        rows = self.audit_entries()
        self.assertTrue(rows)
        before = baseline.table_snapshot(self.db, "audit_events")
        for sql in ("UPDATE audit_events SET action=action", "DELETE FROM audit_events"):
            with self.subTest(sql=sql):
                with self.assertRaises(sqlite3.DatabaseError):
                    self.execute(sql)
                self.assertEqual(baseline.table_snapshot(self.db, "audit_events"), before)
        for method in ("PATCH", "DELETE", "POST"):
            with self.subTest(method=method):
                status = self.client("admin").request(method, "/api/audit", {})[0]
                self.assertIn(status, (403, 404, 405, 501))
        self.require(None, "GET", "/api/audit", status=401)

    def test_campaign_otp_scan_and_route_assets_generate_sanitized_audit_events(self):
        fixtures = self.canonical_fixtures()
        campaign, _ = self.require("system_admin", "POST", "/api/campaigns", {
            "name": "Isolated audit campaign " + self.suffix(), "campaign_type": "خصم",
            "status": "مسودة", "discount_percent": 5, "message": "Synthetic campaign message",
        }, status=201)
        self.require("system_admin", "PATCH", f'/api/campaigns/{campaign["id"]}', {"discount_percent": 10, "status": "نشطة"})
        route = self.office_route(fixtures["own"], fixtures["own_driver"], "jed_a", "jaz_a")
        parcel = self.new_office_shipment("jed_a", "jaz_a")
        self.require("branch_manager", "POST", f'/api/routes/{route["id"]}/scan', {"awb": parcel["awb"]}, status=201)
        self.require("branch_manager", "POST", f'/api/routes/{route["id"]}', {"status": "في الطريق"})
        self.require("branch_manager", "POST", f'/api/routes/{route["id"]}', {"status": "وصلت"})
        self.require("system_admin", "PATCH", f'/api/shipments/{fixtures["own"]["awb"]}', {"status": "قيد التوصيل"})
        issued, _ = self.require("system_admin", "POST", f'/api/shipments/{fixtures["own"]["awb"]}/otp', {})
        events = self.audit_entries()

        def matching(action, identity):
            return [row for row in events if row["action"] == action and str(row["entity_id"]) == str(identity)]

        for action in ("campaign.created", "campaign.updated"):
            self.assertTrue(matching(action, campaign["id"]), action)
        scanned = matching("route.parcel_scanned", route["id"])
        self.assertEqual(len(scanned), 1)
        scan_metadata = json.loads(scanned[0]["metadata_json"])
        self.assertEqual(scan_metadata, {"shipment_id": parcel["id"], "awb": parcel["awb"]})
        otp_events = matching("pod.otp_issued", fixtures["own"]["id"])
        self.assertEqual(len(otp_events), 1)
        otp_metadata = json.loads(otp_events[0]["metadata_json"])
        self.assertEqual(otp_metadata["delivery"], "demo")
        self.assertEqual(set(otp_metadata), {"expires_in", "delivery"})
        self.assertNotIn(issued["demo_code"], json.dumps(otp_events, ensure_ascii=False))
        driver_events = matching("driver.updated", fixtures["own_driver"]["id"])
        vehicle_id = self.query("SELECT vehicle_id FROM route_runs WHERE id=?", (route["id"],))[0]["vehicle_id"]
        vehicle_events = matching("vehicle.updated", vehicle_id)
        self.assertGreaterEqual(len(driver_events), 2)
        self.assertGreaterEqual(len(vehicle_events), 2)
        self.assertTrue(matching("driver.branch_changed", fixtures["own_driver"]["id"]))
        for row in driver_events + vehicle_events:
            metadata = json.loads(row["metadata_json"])
            self.assertEqual(metadata.get("route_id"), route["id"])
            self.assertEqual(metadata.get("reason"), "route propagation")
        serialized = json.dumps(events, ensure_ascii=False)
        for restricted in (fixtures["own"]["sender_id"], fixtures["own"]["recipient_id"], fixtures["own"]["phone"], fixtures["own"]["sender_phone"]):
            self.assertNotIn(restricted, serialized)

    def test_scope_helpers_match_aliased_and_unaliased_sql(self):
        import authorization
        fixtures = self.canonical_fixtures()
        own_route = self.office_route(fixtures["own"], fixtures["own_driver"], "jed_a", "jaz_a")
        other_route = self.office_route(fixtures["other"], fixtures["other_driver"], "jed_b", "jaz_b")
        own_vehicle_id = self.query("SELECT vehicle_id FROM route_runs WHERE id=?", (own_route["id"],))[0]["vehicle_id"]
        other_vehicle_id = self.query("SELECT vehicle_id FROM route_runs WHERE id=?", (other_route["id"],))[0]["vehicle_id"]
        entities = {"shipments": "shipments", "drivers": "drivers", "routes": "route_runs", "branches": "branches", "vehicles": "vehicles", "clients": "clients", "notifications": "branch_notifications", "campaigns": "campaigns"}
        for role in ("branch_manager", "courier", "accountant", "customer", "system_admin"):
            with closing(sqlite3.connect(self.db)) as con:
                con.row_factory = sqlite3.Row
                user = con.execute("SELECT * FROM users WHERE id=?", (self.accounts[role]["id"],)).fetchone()
                ctx = authorization.context(con, user)
                for entity, table in entities.items():
                    with self.subTest(role=role, entity=entity):
                        plain, plain_args = authorization.sql_scope(ctx, entity)
                        aliased, alias_args = authorization.sql_scope(ctx, entity, "fixture_object")
                        plain_ids = {row[0] for row in con.execute(f'SELECT id FROM "{table}" WHERE ({plain})', plain_args)}
                        aliased_ids = {row[0] for row in con.execute(f'SELECT fixture_object.id FROM "{table}" fixture_object WHERE ({aliased})', alias_args)}
                        self.assertEqual(plain_ids, aliased_ids)
                        if role == "customer":
                            self.assertEqual(plain_ids, set())
                        if role in ("branch_manager", "courier") and entity == "vehicles":
                            self.assertIn(own_vehicle_id, plain_ids)
                            self.assertNotIn(other_vehicle_id, plain_ids)
                        if role in ("branch_manager", "courier") and entity == "routes":
                            self.assertEqual(plain_ids, {own_route["id"]})
                        if role == "courier" and entity == "shipments":
                            self.assertEqual(plain_ids, {fixtures["own"]["id"]})
                with self.assertRaises(ValueError):
                    authorization.sql_scope(ctx, "shipments", "unsafe;DROP TABLE users")

    def test_nested_audit_payload_removes_secrets_contacts_binary_and_query_tokens(self):
        from audit import write_audit
        import authorization
        self.canonical_fixtures()
        secret = "NestedSecretPassword789!"
        phone, email, national_id = "+966555555555", "secret-person@example.invalid", "1000007777"
        values = {
            "status": "safe-status", "password": secret, "access_token": "private-token-marker",
            "nested": {"otp": "739211", "sender_id": national_id, "safe_note": "keep this note", "email": email},
            "history": [{"signature_data": baseline.PNG, "photo_data": baseline.PNG, "mobile": phone, "value": "safe-history"},
                        {"field": "password", "old": secret, "new": "DescriptorSecret456!"}],
            "free_text": "email " + email + " phone " + phone + " OTP=739211",
            "binary": b"private binary marker", "oversized": "x" * 4096,
        }
        with closing(sqlite3.connect(self.db)) as con, con:
            con.row_factory = sqlite3.Row
            user = con.execute("SELECT * FROM users WHERE id=?", (self.accounts["system_admin"]["id"],)).fetchone()
            ctx = authorization.context(con, user)
            identifier = write_audit(con, ctx, "regression.sanitization", "regression", "fixture", before=values,
                                     after={"status": "safe-after"}, metadata={"nested": values},
                                     request={"request_id": "regression-request", "method": "POST", "path": "/api/regression?token=private-query-marker", "ip": "127.0.0.1"})
        row = self.query("SELECT * FROM audit_events WHERE id=?", (identifier,))[0]
        self.assertEqual(row["request_path"], "/api/regression")
        self.assertEqual(row["ip_address"], "127.0.0.1")
        stored = json.dumps(row, ensure_ascii=False)
        for restricted in (secret, "DescriptorSecret456!", "private-token-marker", "739211", phone, email, national_id, baseline.PNG, "private-query-marker", "private binary marker"):
            self.assertNotIn(restricted, stored)
        before = json.loads(row["before_json"])
        self.assertEqual(before["status"], "safe-status")
        self.assertEqual(before["nested"]["safe_note"], "keep this note")
        self.assertEqual(before["history"][0]["value"], "safe-history")
        self.assertFalse({"password", "access_token"}.intersection(before))


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    if args.json_output is not None:
        destination = args.json_output.resolve()
        if not destination.is_relative_to(baseline.PROJECT) or "outputs" not in destination.parts or destination.suffix.lower() != ".json":
            parser.error("Result JSON must be inside this project's outputs location")
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AuthorizationRegression)
    result = unittest.TextTestRunner(verbosity=2, resultclass=baseline.JSONTestResult).run(suite)
    if args.json_output is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(), "project": str(baseline.PROJECT),
            "master_access": "SQLite read-only backup only", "http_target": "ephemeral loopback server with disposable DB",
            "external_sms": "disabled; demo outbox in isolated database only", "successful": result.wasSuccessful(),
            "tests_run": result.testsRun, "failure_count": len(result.failures), "error_count": len(result.errors),
            "skipped_count": len(result.skipped), "seconds": round(time.monotonic() - started, 3), "checks": result.checks,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Result JSON: {destination}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
