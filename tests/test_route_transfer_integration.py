"""Route/branch-transfer integration only; disposable database copies.

Run: python -m unittest discover -s tests -p test_route_transfer_integration.py -v
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_authorization_regression as fixtures
import test_baseline_regression as baseline


class RouteTransferIntegration(unittest.TestCase):
    # Reuse fixture helpers without inheriting any baseline/Phase 3 tests.
    setUpClass = classmethod(fixtures.AuthorizationRegression.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AuthorizationRegression.tearDownClass.__func__)

    def make_route(self, count=1):
        self.office_fixtures()
        driver = self.office_driver('jed_a', 'own')
        shipments = [self.new_office_shipment('jed_a', 'jaz_a') for _ in range(count)]
        route = self.office_route(shipments[0], driver, 'jed_a', 'jaz_a')
        for shipment in shipments[1:]:
            self.require('admin', 'POST', f"/api/routes/{route['id']}/scan", {'awb': shipment['awb']}, status=201)
        return route, shipments, driver

    def receiver(self):
        branch = self.office_fixtures()['jaz_a']['id']
        self.create_account('receiver', 'office_employee', [branch], branch)
        return 'receiver'

    def start(self, route):
        return self.require('admin', 'POST', f"/api/routes/{route['id']}", {'status': 'في الطريق'})[0]

    def arrive(self, route):
        return self.require('admin', 'POST', f"/api/routes/{route['id']}", {'status': 'وصلت'})[0]

    def receive(self, route, shipment, role='receiver', status=200):
        return self.require(role, 'POST', f"/api/routes/{route['id']}/receive", {'awb': shipment['awb']}, status=status)[0]

    def transfer(self, route, shipment):
        return self.query('SELECT * FROM shipment_transfers WHERE route_id=? AND shipment_id=?',
                          (route['id'], shipment['id']))[0]

    def snapshot(self):
        return {table: baseline.table_snapshot(self.db, table) for table in
                ('route_runs', 'route_shipments', 'shipment_transfers', 'shipments',
                 'shipment_events', 'audit_events', 'drivers', 'vehicles')}

    def test_creation_and_batch_scan_keep_existing_manifest_and_link_transfers(self):
        route, shipments, _ = self.make_route(2)
        self.assertEqual(self.query('SELECT shipment_id FROM route_shipments WHERE route_id=? ORDER BY shipment_id',
                                   (route['id'],)), [{'shipment_id': row['id']} for row in shipments])
        for shipment in shipments:
            transfer = self.transfer(route, shipment)
            self.assertEqual(transfer['status'], 'planned')
            self.assertEqual(transfer['origin_branch_id'], self.offices['jed_a']['id'])
            self.assertEqual(transfer['destination_branch_id'], self.offices['jaz_a']['id'])
            self.assertIsNone(transfer['received_by'])
        listed, _ = self.require('admin', 'GET', '/api/routes')
        record = next(row for row in listed if row['id'] == route['id'])
        self.assertEqual([row['transfer_status'] for row in record['shipments']], ['planned', 'planned'])

    def test_dispatch_requires_arrival_before_receipt(self):
        route, (shipment,), _ = self.make_route()
        self.receiver()
        self.client('receiver')
        before = self.snapshot()
        self.receive(route, shipment, status=409)
        self.assertEqual(self.snapshot(), before)
        self.start(route)
        transfer = self.transfer(route, shipment)
        self.assertEqual(transfer['status'], 'in_transit')
        self.assertIsNotNone(transfer['dispatched_at'])
        self.assertIsNone(transfer['received_at'])
        before = self.snapshot()
        self.receive(route, shipment, status=409)
        self.assertEqual(self.snapshot(), before)

    def test_vehicle_arrival_waits_for_each_parcel_receipt(self):
        route, shipments, _ = self.make_route(2)
        self.receiver()
        self.start(route)
        parcels_before = {row['id']: self.shipment_snapshot(row) for row in shipments}
        arrived = self.arrive(route)
        self.assertEqual(arrived['shipments_updated'], 0)
        for shipment in shipments:
            self.assertEqual(self.shipment_snapshot(shipment), parcels_before[shipment['id']])
            transfer = self.transfer(route, shipment)
            self.assertEqual(transfer['status'], 'awaiting_receipt')
            self.assertIsNotNone(transfer['arrived_at'])
            self.assertIsNone(transfer['received_at'])
            self.assertIsNone(transfer['received_by'])
        self.receive(route, shipments[0])
        confirmed = self.transfer(route, shipments[0])
        self.assertEqual(confirmed['status'], 'received')
        self.assertEqual(confirmed['received_by'], self.accounts['receiver']['id'])
        self.assertIsNotNone(confirmed['received_at'])
        self.assertEqual(self.query('SELECT status FROM shipments WHERE id=?', (shipments[0]['id'],))[0]['status'], 'جاهز للتسليم')
        self.assertEqual(self.transfer(route, shipments[1])['status'], 'awaiting_receipt')
        self.assertEqual(self.query('SELECT status FROM shipments WHERE id=?', (shipments[1]['id'],))[0]['status'], 'قيد النقل')

    def test_origin_other_office_and_courier_cannot_confirm_receipt(self):
        route, (shipment,), driver = self.make_route()
        for label, office, role in (('sender', 'jed_a', 'branch_manager'),
                                    ('other_receiver', 'jaz_b', 'office_employee'),
                                    ('courier', 'jaz_a', 'courier')):
            branch = self.offices[office]['id']
            self.create_account(label, role, [branch], branch, driver['id'] if role == 'courier' else None)
            self.client(label)  # Authenticate before comparing business state.
        self.start(route)
        self.arrive(route)
        before = self.snapshot()
        for label in ('sender', 'other_receiver', 'courier'):
            self.receive(route, shipment, role=label, status=403)
            self.assertEqual(self.snapshot(), before)

    def test_pending_receipt_cannot_be_bypassed_or_loaded_on_another_route(self):
        route, (shipment,), _ = self.make_route()
        self.receiver()
        self.start(route)
        self.arrive(route)
        before = self.snapshot()
        for state in ('جاهز للتسليم', 'قيد التوصيل', 'تم الاستلام'):
            self.require('admin', 'PATCH', f"/api/shipments/{shipment['awb']}", {'status': state}, status=409)
            self.assertEqual(self.snapshot(), before)
        driver = self.office_driver('jed_a', 'unrelated')
        vehicle = self.office_vehicle('jed_a')
        payload = self.route_payload([shipment], driver, vehicle,
            origin_branch_id=self.offices['jed_a']['id'], destination_branch_id=self.offices['jaz_a']['id'])
        before = self.snapshot()
        self.require('admin', 'POST', '/api/routes', payload, status=409)
        self.assertEqual(self.snapshot(), before)
        other = self.new_office_shipment('jed_a', 'jaz_a')
        payload['awbs'] = [other['awb']]
        other_route, _ = self.require('admin', 'POST', '/api/routes', payload, status=201)
        before = self.snapshot()
        self.require('admin', 'POST', f"/api/routes/{other_route['id']}/scan", {'awb': shipment['awb']}, status=409)
        self.assertEqual(self.snapshot(), before)
        self.receive(route, shipment)
        self.require('receiver', 'PATCH', f"/api/shipments/{shipment['awb']}", {'status': 'قيد التوصيل'})

    def test_repeated_start_arrival_and_receipt_are_noops(self):
        route, (shipment,), _ = self.make_route()
        self.receiver()
        self.client('receiver')
        self.start(route)
        before = self.snapshot()
        self.assertEqual(self.start(route)['shipments_updated'], 0)
        self.assertEqual(self.snapshot(), before)
        self.arrive(route)
        before = self.snapshot()
        self.arrive(route)
        self.assertEqual(self.snapshot(), before)
        self.receive(route, shipment)
        self.require('receiver', 'PATCH', f"/api/shipments/{shipment['awb']}", {'status': 'قيد التوصيل'})
        before = self.snapshot()
        self.assertEqual(self.receive(route, shipment)['shipments_updated'], 0)
        self.arrive(route)
        self.assertEqual(self.snapshot(), before)

    def test_cancellation_releases_transfer_and_never_confirms_receipt(self):
        route, (shipment,), driver = self.make_route()
        self.receiver()
        self.require('admin', 'POST', f"/api/routes/{route['id']}", {'status': 'ملغاة'})
        transfer = self.transfer(route, shipment)
        self.assertEqual(transfer['status'], 'cancelled')
        self.assertIsNone(transfer['received_at'])
        self.receive(route, shipment, status=409)
        new_route = self.office_route(shipment, driver, 'jed_a', 'jaz_a')
        self.assertEqual(self.transfer(new_route, shipment)['status'], 'planned')

    def test_dispatch_and_arrival_preserve_completed_child(self):
        route, (shipment,), _ = self.make_route()
        self.execute("UPDATE shipments SET status='Delivered' WHERE id=?", (shipment['id'],))
        before = self.shipment_snapshot(shipment)
        self.start(route)
        self.arrive(route)
        self.assertEqual(self.shipment_snapshot(shipment), before)
        self.assertIsNone(self.transfer(route, shipment)['received_at'])

    def test_additive_migration_adopts_active_manifests_without_rewriting_routes(self):
        scheduled, (first,), _ = self.make_route()
        running, (second,), _ = self.make_route()
        self.start(running)
        historical, _, _ = self.make_route()
        self.start(historical)
        self.arrive(historical)
        before = {table: baseline.table_snapshot(self.db, table) for table in
                  ('route_runs', 'route_shipments', 'shipments', 'shipment_events', 'audit_events')}
        # Simulate the pre-transfer schema only inside this disposable fixture.
        self.execute('DROP TABLE shipment_transfers')
        self.execute('DELETE FROM schema_migrations WHERE version=4')
        baseline.SERVER.init_db()
        for table, snapshot in before.items():
            self.assertEqual(baseline.table_snapshot(self.db, table), snapshot)
        self.assertEqual(self.transfer(scheduled, first)['status'], 'planned')
        self.assertEqual(self.transfer(running, second)['status'], 'in_transit')
        self.assertEqual(self.query('SELECT * FROM shipment_transfers WHERE route_id=?', (historical['id'],)), [])


    def test_transfer_api_uses_recorded_origin_not_current_route_scope(self):
        route, (shipment,), _ = self.make_route()
        original = self.transfer(route, shipment)
        # Deliberately disagree with the current route scope in this disposable DB.
        self.execute('UPDATE route_scope SET origin_branch_id=? WHERE route_id=?',
                     (self.offices['jed_b']['id'], route['id']))
        listed, _ = self.require('admin', 'GET', '/api/routes')
        parcel = next(row for row in listed if row['id'] == route['id'])['shipments'][0]
        self.assertEqual(parcel['origin_branch_id'], original['origin_branch_id'])
        self.assertEqual(parcel['receiving_branch_id'], original['destination_branch_id'])
        self.assertIsNone(parcel['received_by'])
        self.assertIsNone(parcel['received_by_name'])
        self.assertEqual(self.transfer(route, shipment), original)

    def test_receipt_api_returns_authenticated_actor_and_preserves_actor_on_retry(self):
        route, (shipment,), _ = self.make_route()
        self.receiver()
        branch = self.offices['jaz_a']['id']
        self.create_account('second_receiver', 'office_employee', [branch], branch)
        self.client('receiver')
        self.client('second_receiver')
        self.start(route)
        self.arrive(route)
        receipt, _ = self.require('receiver', 'POST', f"/api/routes/{route['id']}/receive",
                                 {'awb': shipment['awb'], 'received_by': self.accounts['second_receiver']['id'],
                                  'received_by_name': 'Forged actor', 'origin_branch_id': self.offices['jed_b']['id']})
        self.assertEqual(receipt['received_by'], self.accounts['receiver']['id'])
        self.assertEqual(receipt['received_by_name'], self.accounts['receiver']['display_name'])
        self.assertEqual(receipt['origin_branch_id'], self.offices['jed_a']['id'])
        self.assertEqual(receipt['receiving_branch_id'], branch)
        self.assertEqual(receipt['route_id'], route['id'])
        self.assertEqual(receipt['shipment_id'], shipment['id'])
        self.assertIsNotNone(receipt['received_at'])
        for secret in ('password_hash', 'password', 'username', 'mobile', 'national_id'):
            self.assertNotIn(secret, receipt)
        before = self.snapshot()
        retry = self.receive(route, shipment, role='second_receiver')
        self.assertEqual(retry['shipments_updated'], 0)
        for field in ('received_by', 'received_by_name', 'received_at', 'origin_branch_id', 'receiving_branch_id'):
            self.assertEqual(retry[field], receipt[field])
        self.assertEqual(self.snapshot(), before)
        listed, _ = self.require('receiver', 'GET', '/api/routes')
        detail = next(row for row in listed if row['id'] == route['id'])['shipments'][0]
        for field in ('origin_branch_id', 'receiving_branch_id', 'received_by', 'received_by_name', 'received_at'):
            self.assertEqual(detail[field], receipt[field])
        self.assertEqual(self.snapshot(), before)

    def test_transfer_metadata_respects_both_office_memberships_and_existing_read_permissions(self):
        route, (shipment,), _ = self.make_route()
        both = [self.offices['jed_a']['id'], self.offices['jaz_a']['id']]
        self.create_account('both_offices', 'branch_manager', both, both[0])
        other = self.offices['jaz_b']['id']
        self.create_account('same_city_other', 'office_employee', [other], other)
        self.create_account('accountant', 'accountant', [both[1]], both[1])
        self.create_account('customer', 'customer')
        unrelated_driver = self.office_driver('jed_b', 'unrelated')
        unrelated_shipment = self.new_office_shipment('jed_b', 'jaz_b')
        unrelated = self.office_route(unrelated_shipment, unrelated_driver, 'jed_b', 'jaz_b')
        listed, _ = self.require('both_offices', 'GET', '/api/routes')
        self.assertNotIn(unrelated['id'], [row['id'] for row in listed])
        parcel = next(row for row in listed if row['id'] == route['id'])['shipments'][0]
        self.assertEqual(parcel['origin_branch_id'], both[0])
        self.assertEqual(parcel['receiving_branch_id'], both[1])
        outside, _ = self.require('same_city_other', 'GET', '/api/routes')
        self.assertNotIn(route['id'], [row['id'] for row in outside])
        for role in ('accountant', 'customer'):
            self.require(role, 'GET', '/api/routes', status=403)


for name in ('setUp', 'tearDown', 'assertIsolatedDB', 'query', 'execute', 'require',
             'suffix', 'client', 'new_driver', 'new_vehicle', 'assign_employee',
             'shipment_payload', 'new_shipment', 'route_payload', 'new_route',
             'shipment_snapshot', 'create_account', 'office_fixtures', 'office_driver',
             'office_vehicle', 'new_office_shipment', 'office_route'):
    setattr(RouteTransferIntegration, name, getattr(fixtures.AuthorizationRegression, name))


if __name__ == '__main__':
    unittest.main()
