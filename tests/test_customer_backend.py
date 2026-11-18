"""Targeted customer backend tests; fixtures write only to disposable DBs."""
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_authorization_regression as fixtures
import test_baseline_regression as baseline


class CustomerBackend(unittest.TestCase):
    setUpClass = classmethod(fixtures.AuthorizationRegression.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AuthorizationRegression.tearDownClass.__func__)

    def setUp(self):
        fixtures.AuthorizationRegression.setUp(self)
        for throttle in (baseline.SERVER.LOGIN_THROTTLE, baseline.SERVER.customers.REGISTRATION_THROTTLE):
            with throttle.lock:
                throttle.failures.clear()

    def registration(self, **overrides):
        data = {'username': 'customer-' + self.suffix() + '@example.invalid',
                'display_name': 'Synthetic customer', 'password': 'CustomerTest123!',
                'mobile': '+966500000101', 'address': 'Synthetic customer address'}
        data.update(overrides)
        return data

    def register(self, data=None):
        data = data or self.registration()
        client = fixtures.AuthorizationClient(self.port)
        status, result, headers = client.request('POST', '/api/customer/register', data)
        self.assertEqual(status, 201, result)
        self.assertNotIn('set-cookie', headers)
        return result['user'], client, data

    def customer(self):
        user, client, data = self.register()
        status, result, _ = client.request('POST', '/api/customer/login', {
            'username': data['username'], 'password': data['password']})
        self.assertEqual(status, 200, result)
        return user, client, data

    def request(self, client, method, path, data=None, status=200, **kwargs):
        actual, result, headers = client.request(method, path, data, **kwargs)
        self.assertEqual(actual, status, result)
        return result, headers

    def link(self, shipment, customer, role='admin', status=201):
        return self.require(role, 'POST', f"/api/shipments/{shipment['awb']}/customer",
                            {'customer_user_id': customer['id']}, status=status)[0]

    def snapshots(self, *tables):
        return {table: baseline.table_snapshot(self.db, table) for table in tables}

    def test_registration_reuses_users_with_customer_role_and_preserves_existing_staff(self):
        before = self.snapshots('users', 'user_access', 'user_branches', 'sessions')
        customer, _, data = self.register()
        row = self.query('SELECT * FROM users WHERE id=?', (customer['id'],))[0]
        self.assertEqual(row['role'], 'employee')  # Legacy CHECK stays unchanged.
        self.assertNotEqual(row['password_hash'], data['password'])
        self.assertTrue(baseline.SERVER.verify_password(data['password'], row['password_hash']))
        self.assertEqual(customer['access_role'], 'customer')
        self.assertEqual(customer['permissions'], [])
        self.assertNotIn('password_hash', customer)
        self.assertNotIn('national_id', customer)
        access = self.query('SELECT * FROM user_access WHERE user_id=?', (customer['id'],))[0]
        self.assertEqual(access['role'], 'customer')
        self.assertEqual(access['global_scope'], 0)
        self.assertIsNone(access['primary_branch_id'])
        for table, column in (('users', 'id'), ('user_access', 'user_id'), ('user_branches', 'user_id')):
            self.assertEqual(baseline.table_snapshot(self.db, table, where=f'WHERE {column}<>?', params=(customer['id'],)), before[table])
        self.assertEqual(baseline.table_snapshot(self.db, 'sessions'), before['sessions'])
        self.assertEqual(self.query('SELECT * FROM customer_shipments'), [])

    def test_registration_rejects_role_scope_ownership_injection_and_invalid_passwords(self):
        for key, value in (('role', 'system_admin'), ('global_scope', True), ('branch_ids', [1]),
                           ('driver_id', 1), ('user_id', 1), ('customer_user_id', 1), ('shipments', ['GHZ-000125'])):
            data = self.registration(**{key: value})
            before = self.snapshots('users', 'user_access', 'customer_accounts')
            self.request(self.guest, 'POST', '/api/customer/register', data, status=400)
            self.assertEqual(self.snapshots(*before), before)
        for password in ('short', 'nouppercase123', 'NOLOWERCASE123', 'NoDigitsHere!'):
            self.request(self.guest, 'POST', '/api/customer/register', self.registration(password=password), status=400)

    def test_registration_case_insensitive_duplicates_never_replace_staff(self):
        user, _, data = self.register()
        before = self.snapshots('users', 'user_access', 'customer_accounts')
        self.request(self.guest, 'POST', '/api/customer/register', {**data, 'username': data['username'].upper()}, status=409)
        self.request(self.guest, 'POST', '/api/customer/register', self.registration(username='ADMIN@GHAZALA.SA'), status=409)
        self.assertEqual(self.snapshots(*before), before)
        self.require('admin', 'GET', '/api/users')

    def test_profile_is_session_owned_and_rejects_identifier_role_and_password_changes(self):
        one, client, _ = self.customer()
        two, _, _ = self.customer()
        result, _ = self.request(client, 'GET', '/api/customer/profile?user_id=' + str(two['id']))
        self.assertEqual(result['id'], one['id'])
        before_other = self.query('SELECT * FROM users WHERE id=?', (two['id'],))[0]
        result, _ = self.request(client, 'PATCH', '/api/customer/profile', {
            'display_name': 'Updated customer', 'mobile': '+966500000102', 'address': 'Updated address'})
        self.assertEqual(result['id'], one['id'])
        self.assertEqual(result['address'], 'Updated address')
        self.assertEqual(result['display_name'], 'Updated customer')
        for data in ({'user_id': two['id']}, {'role': 'system_admin'}, {'username': 'other'},
                     {'permissions': ['users.manage']}, {'password': 'Malicious123!'}, {'display_name': ''}):
            before = self.snapshots('users', 'user_access', 'customer_accounts')
            self.request(client, 'PATCH', '/api/customer/profile', data, status=400)
            self.assertEqual(self.snapshots(*before), before)
        self.assertEqual(self.query('SELECT * FROM users WHERE id=?', (two['id'],))[0], before_other)
        self.request(client, 'GET', '/api/customer/profile/' + str(two['id']), status=404)

    def test_customer_login_rejects_staff_and_staff_cannot_use_customer_profile(self):
        guest = fixtures.AuthorizationClient(self.port)
        before = len(self.query('SELECT * FROM sessions'))
        self.request(guest, 'POST', '/api/customer/login', {'username': 'admin@ghazala.sa', 'password': 'Admin123!'}, status=401)
        self.assertEqual(len(self.query('SELECT * FROM sessions')), before)
        admin = self.client('admin')
        self.request(admin, 'GET', '/api/customer/profile', status=403)
        self.request(admin, 'PATCH', '/api/customer/profile', {'display_name': 'Hijack'}, status=403)
        self.request(admin, 'POST', '/api/customer/register', self.registration(), status=403)
        self.require('admin', 'GET', '/api/users')

    def test_customer_sessions_use_existing_hash_cookie_expiry_and_logout(self):
        user, client, data = self.register()
        _, headers = self.request(client, 'POST', '/api/customer/login', {'username': data['username'], 'password': data['password']})
        for flag in ('HttpOnly', 'SameSite=Lax', 'Path=/'):
            self.assertIn(flag, headers['set-cookie'])
        token = client.cookie.split('=', 1)[1]
        self.assertEqual(self.query('SELECT token_hash FROM sessions WHERE user_id=?', (user['id'],))[0]['token_hash'], hashlib.sha256(token.encode()).hexdigest())
        me, _ = self.request(client, 'GET', '/api/me')
        self.assertEqual(me['user']['access_role'], 'customer')
        self.assertEqual(me['user']['permissions'], [])
        self.request(client, 'POST', '/api/logout', {})
        self.request(client, 'GET', '/api/customer/profile', status=401)
        self.request(client, 'POST', '/api/login', {'username': data['username'], 'password': data['password']})
        self.request(client, 'GET', '/api/customer/profile')
        self.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?', (user['id'],))
        self.request(client, 'GET', '/api/customer/profile', status=401)

    def test_customer_password_change_rotates_own_sessions_and_preserves_other_customer(self):
        one, client, data = self.customer()
        two, other, other_data = self.customer()
        stale = fixtures.AuthorizationClient(self.port)
        self.request(stale, 'POST', '/api/customer/login', {'username': data['username'], 'password': data['password']})
        before_two = self.query('SELECT password_hash FROM users WHERE id=?', (two['id'],))[0]
        self.request(client, 'POST', '/api/password', {'current_password': data['password'], 'new_password': 'NewCustomer123!', 'user_id': two['id']})
        self.request(stale, 'GET', '/api/customer/profile', status=401)
        self.request(client, 'GET', '/api/customer/profile')
        self.request(other, 'GET', '/api/customer/profile')
        self.assertEqual(self.query('SELECT password_hash FROM users WHERE id=?', (two['id'],))[0], before_two)
        self.request(stale, 'POST', '/api/customer/login', {'username': data['username'], 'password': data['password']}, status=401)
        self.request(stale, 'POST', '/api/customer/login', {'username': data['username'], 'password': 'NewCustomer123!'})

    def test_inactive_customer_and_throttled_login_cannot_create_sessions(self):
        user, client, data = self.customer()
        self.require('admin', 'PATCH', f"/api/users/{user['id']}", {'is_active': False})
        self.request(client, 'GET', '/api/customer/profile', status=401)
        self.request(client, 'POST', '/api/customer/login', {'username': data['username'], 'password': data['password']}, status=401)
        active, _, active_data = self.register()
        guest = fixtures.AuthorizationClient(self.port)
        for _ in range(5):
            self.request(guest, 'POST', '/api/customer/login', {'username': active_data['username'], 'password': 'WrongPassword123!'}, status=401)
        self.request(guest, 'POST', '/api/customer/login', {'username': active_data['username'], 'password': active_data['password']}, status=429)
        self.assertEqual(self.query('SELECT * FROM sessions WHERE user_id=?', (active['id'],)), [])

    def test_registration_is_throttled_without_partial_accounts(self):
        data = self.registration(password='weak')
        for _ in range(5):
            self.request(self.guest, 'POST', '/api/customer/register', data, status=400)
        self.request(self.guest, 'POST', '/api/customer/register', {**data, 'password': 'ValidCustomer123!'}, status=429)
        self.assertEqual(self.query('SELECT * FROM users WHERE username=?', (data['username'],)), [])

    def test_shipments_require_explicit_staff_link_and_never_contact_or_awb_claims(self):
        user, client, data = self.customer()
        shipment = self.new_shipment(sender_name=user['display_name'], sender_phone=data['mobile'])
        self.assertEqual(self.request(client, 'GET', '/api/customer/shipments')[0], [])
        self.request(client, 'POST', f"/api/shipments/{shipment['awb']}/customer", {'customer_user_id': user['id']}, status=403)
        self.request(client, 'PATCH', '/api/customer/profile', {'awb': shipment['awb']}, status=400)
        self.link(shipment, user)
        rows, _ = self.request(client, 'GET', '/api/customer/shipments')
        self.assertEqual([row['id'] for row in rows], [shipment['id']])

    def test_customer_shipment_lists_detail_and_authenticated_tracking_are_owner_only(self):
        one, client, _ = self.customer()
        two, other, _ = self.customer()
        owned, foreign = self.new_shipment(), self.new_shipment()
        self.link(owned, one)
        self.link(foreign, two)
        rows, _ = self.request(client, 'GET', '/api/customer/shipments?customer_user_id=' + str(two['id']))
        self.assertEqual([row['id'] for row in rows], [owned['id']])
        detail, _ = self.request(client, 'GET', '/api/customer/shipments/' + owned['awb'].lower())
        self.assertEqual(detail['id'], owned['id'])
        for field in ('phone', 'recipient_id', 'sender_id', 'driver_id', 'driver_name', 'driver_mobile',
                      'driver_latitude', 'driver_longitude', 'cod', 'shipping_fee', 'total_fee', 'payment_status'):
            self.assertNotIn(field, detail)
        self.request(client, 'GET', '/api/customer/shipments/' + foreign['awb'], status=404)
        self.request(other, 'GET', '/api/customer/shipments/' + owned['awb'], status=404)
        self.request(client, 'GET', '/api/customer/shipments/GHZ-NOT-FOUND', status=404)
        self.request(client, 'GET', '/api/public/tracking/' + foreign['awb'], status=404)
        self.request(client, 'GET', '/api/public/tracking/' + owned['awb'])
        self.require(None, 'GET', '/api/public/tracking/' + foreign['awb'])

    def test_staff_link_requires_edit_permission_and_existing_branch_scope(self):
        customer, _, _ = self.customer()
        offices = self.office_fixtures()
        shipment = self.new_office_shipment('jed_a', 'jaz_a')
        for label, role, office in (('editor', 'office_employee', 'jed_a'), ('wrong_office', 'office_employee', 'jed_b'),
                                    ('courier', 'courier', 'jed_a'), ('accountant', 'accountant', 'jed_a')):
            branch = offices[office]['id']
            self.create_account(label, role, [branch], branch)
        before = self.snapshots('shipments', 'shipment_scope', 'customer_shipments')
        for role in ('wrong_office', 'courier', 'accountant'):
            self.link(shipment, customer, role=role, status=403)
            self.assertEqual(self.snapshots(*before), before)
        admin = self.query("SELECT id FROM users WHERE username='admin@ghazala.sa'")[0]
        self.link(shipment, admin, status=400)
        self.link(shipment, {'id': 999999}, status=400)
        linked = self.link(shipment, customer, role='editor')
        self.assertEqual(linked['linked_by'], self.accounts['editor']['id'])

    def test_ownership_relink_conflicts_and_repeated_same_owner_is_a_true_noop(self):
        one, _, _ = self.customer()
        two, _, _ = self.customer()
        shipment = self.new_shipment()
        linked = self.link(shipment, one)
        before = self.snapshots('customer_shipments', 'shipments', 'shipment_events', 'audit_events')
        self.assertEqual(self.link(shipment, one, status=200), linked)
        self.assertEqual(self.snapshots(*before), before)
        self.link(shipment, two, status=409)
        self.assertEqual(self.snapshots(*before), before)

    def test_customer_cannot_read_or_mutate_internal_staff_endpoints(self):
        user, client, _ = self.customer()
        paths = ['/api/shipments', '/api/users', '/api/audit', '/api/routes', '/api/drivers', '/api/branches',
                 '/api/branch-directory', '/api/vehicles', '/api/clients', '/api/pricing', '/api/campaigns',
                 '/api/stats', '/api/reports/shipments', '/api/notifications']
        for path in paths:
            self.request(client, 'GET', path, status=403)
        for path, method, data in (('/api/users', 'POST', {'role': 'admin'}), ('/api/shipments', 'POST', {}),
                                   (f"/api/users/{user['id']}", 'PATCH', {'role': 'admin'}),
                                   ('/api/admin/reset-demo', 'POST', {}), ('/api/routes/1/receive', 'POST', {'awb': 'GHZ-000125'})):
            self.request(client, method, path, data, status=403)
        for path in ('/api/customer/invoices', '/api/customer/payments', '/api/customer/pickup-requests'):
            self.request(client, 'GET', path, status=404)
        self.request(self.guest, 'GET', '/api/customer/profile', status=401)
        self.request(self.guest, 'GET', '/api/customer/shipments', status=401)

    def test_same_origin_customer_mutations_and_login_remain_protected(self):
        user, client, data = self.customer()
        before = self.snapshots('users', 'sessions', 'customer_accounts', 'customer_shipments')
        cross = {'Origin': 'https://untrusted.invalid', 'Sec-Fetch-Site': 'cross-site'}
        guest = fixtures.AuthorizationClient(self.port)
        self.request(guest, 'POST', '/api/customer/register', self.registration(), status=403, extra_headers=cross)
        self.request(guest, 'POST', '/api/customer/login', {'username': data['username'], 'password': data['password']}, status=403, extra_headers=cross)
        self.request(client, 'PATCH', '/api/customer/profile', {'display_name': 'Blocked'}, status=403, extra_headers=cross)
        self.assertEqual(self.snapshots(*before), before)

    def test_migration5_adopts_reserved_customers_and_preserves_migrations1_to4_and_history(self):
        offices = self.office_fixtures()
        driver = self.office_driver('jed_a', 'own')
        shipment = self.new_office_shipment('jed_a', 'jaz_a')
        route = self.office_route(shipment, driver, 'jed_a', 'jaz_a')
        reserved = self.create_account('reserved_customer', 'customer')
        self.execute('DROP TABLE customer_shipments')
        self.execute('DROP TABLE customer_accounts')
        self.execute('DELETE FROM schema_migrations WHERE version=5')
        tables = ('users', 'user_access', 'user_branches', 'sessions', 'shipments', 'shipment_events', 'route_runs',
                  'route_shipments', 'shipment_transfers', 'audit_events', 'pod_records', 'drivers', 'vehicles')
        before = self.snapshots(*tables)
        migrations = self.query('SELECT * FROM schema_migrations ORDER BY version')
        baseline.SERVER.init_db()
        self.assertEqual(self.snapshots(*tables), before)
        self.assertEqual(self.query('SELECT * FROM schema_migrations WHERE version<5 ORDER BY version'), migrations)
        self.assertEqual([row['version'] for row in self.query('SELECT version FROM schema_migrations ORDER BY version')], [1, 2, 3, 4, 5])
        self.assertEqual(self.query('SELECT user_id FROM customer_accounts'), [{'user_id': reserved['id']}])
        self.assertEqual(self.query('SELECT * FROM customer_shipments'), [])
        after = self.snapshots(*tables, 'schema_migrations', 'customer_accounts')
        baseline.SERVER.init_db()
        self.assertEqual(self.snapshots(*after), after)

    def test_admin_created_or_reclassified_customers_get_profiles_without_staff_portal_access(self):
        account = self.create_account('managed_customer', 'customer')
        client = self.client('managed_customer')
        self.request(client, 'GET', '/api/customer/profile')
        branch = self.office_fixtures()['jed_a']['id']
        self.require('admin', 'PATCH', f"/api/users/{account['id']}", {'role': 'office_employee', 'branch_ids': [branch], 'primary_branch_id': branch})
        self.request(client, 'GET', '/api/customer/profile', status=401)
        self.account_clients.pop('managed_customer', None)
        staff = self.client('managed_customer')
        self.request(staff, 'GET', '/api/customer/profile', status=403)
        self.request(staff, 'POST', '/api/customer/login', {'username': account['username'], 'password': account['test_password']}, status=401)
        self.require('admin', 'PATCH', f"/api/users/{account['id']}", {'role': 'customer', 'branch_ids': [], 'primary_branch_id': None})
        self.account_clients.pop('managed_customer', None)
        customer = self.client('managed_customer')
        self.request(customer, 'GET', '/api/customer/profile')
        self.request(customer, 'GET', '/api/shipments', status=403)


for name in ('tearDown', 'assertIsolatedDB', 'query', 'execute', 'require', 'suffix', 'client',
             'new_driver', 'new_vehicle', 'shipment_payload', 'new_shipment', 'route_payload',
             'create_account', 'office_fixtures', 'office_driver', 'office_vehicle', 'office_route', 'new_office_shipment'):
    setattr(CustomerBackend, name, getattr(fixtures.AuthorizationRegression, name))


if __name__ == '__main__':
    unittest.main()
