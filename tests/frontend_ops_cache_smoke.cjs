'use strict';
/* Offline fixtures only: no HTTP requests, browsers, server starts, or database writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'static', 'ops.js'), 'utf8');
const appSource = fs.readFileSync(path.join(__dirname, '..', 'static', 'app.js'), 'utf8');
const permissionHelpers = appSource.slice(appSource.indexOf('const accessRoleLabels='), appSource.indexOf('function applyLanguage('));
const stateDeclaration = source.match(/^\s*const state=\{[^\r\n]+\};/m)?.[0];
assert.ok(stateDeclaration, 'Extract the real operations state declaration');

function section(start, end) {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  assert.ok(first >= 0 && last > first, `Extract real source between ${start} and ${end}`);
  return source.slice(first, last);
}

const cacheFunctions = section('  function opsOwnerKey(', '  function baseFeeQuote(');
const renderWrapper = section('  window.render=function()', "  window.addEventListener('hashchange'");
assert.match(renderWrapper, /^\s*window\.render=function\(\)\{\s*syncOpsOwner\(\);/,
  'The real render wrapper synchronizes ownership before rendering');
assert.ok(renderWrapper.indexOf('syncOpsOwner()') < renderWrapper.indexOf('baseRender()'));

const arrayKeys = ['routes', 'branches', 'branchDirectory', 'vehicles', 'clients', 'campaigns', 'users', 'notifications'];
const commonPaths = ['/api/routes', '/api/branches', '/api/vehicles', '/api/pricing', '/api/notifications'];
const adminPaths = [...commonPaths, '/api/clients', '/api/campaigns', '/api/users', '/api/branch-directory'];

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function responseFor(url, owner) {
  return url === '/api/pricing' ? { owner, base_fee: 77 } : [{ id: `${owner}:${url}`, owner }];
}

function settle(requests, owner, error = null) {
  requests.forEach((request, index) => {
    if (error && index === 0) request.reject(error);
    else request.resolve(responseFor(request.url, owner));
  });
}

function fixture(initialUser = { id: 1, role: 'admin' }) {
  const calls = [], modal = { innerHTML: '' };
  let now = 1000000, renders = 0, binds = 0, renderObserver = () => {};
  const context = {
    user: initialUser, page: 'home', tracking: '', window: {}, app: { dataset: {} },
    Date: { now: () => now },
    $: selector => selector === '#modalRoot' ? modal : null,
    trackingFragment: () => null,
    location: { pathname: '/', search: '' }, history: { replaceState() {} },
    baseRender() { renders++; renderObserver(); },
    bindOps() { binds++; },
    api(url) {
      const pending = deferred();
      calls.push({ url, ...pending });
      return pending.promise;
    }
  };
  vm.createContext(context);
  vm.runInContext(`${permissionHelpers}\n${stateDeclaration}\n${cacheFunctions}\n${renderWrapper}\n` +
    'globalThis.cache={state,opsOwnerKey,syncOpsOwner,refreshOps};', context,
    { filename: 'ops-cache-extracted.js' });
  return {
    context, cache: context.cache, calls, modal,
    get renders() { return renders; }, get binds() { return binds; },
    get now() { return now; }, setTime(value) { now = value; },
    setUser(value) { context.user = value; },
    observeRender(callback) { renderObserver = callback; },
    start(force = false) {
      const first = calls.length;
      const promise = context.cache.refreshOps(force);
      return { promise, requests: calls.slice(first), pending: context.cache.state.pending };
    }
  };
}

function assertEmpty(state, label, checkRequest = true) {
  for (const key of arrayKeys) assert.equal(state[key].length, 0, `${label}: ${key} cleared`);
  assert.equal(Object.keys(state.pricing).length, 0, `${label}: pricing cleared`);
  assert.equal(state.last, 0, `${label}: cache timestamp cleared`);
  assert.equal(state.lastError, null, `${label}: error cleared`);
  assert.equal(state.location, null, `${label}: location cleared`);
  assert.equal(state.documentPreview, null, `${label}: preview cleared`);
  if (checkRequest) {
    assert.equal(state.busy, false, `${label}: busy cleared`);
    assert.equal(state.pending, null, `${label}: pending cleared`);
  }
}

function assertOwned(state, owner, role) {
  for (const key of arrayKeys) {
    const privileged = ['clients', 'campaigns', 'users'].includes(key);
    const accessible = key==='branchDirectory'?role!=='employee':!privileged || role === 'admin' || (role === 'manager' && key !== 'users');
    assert.equal(state[key].length, accessible ? 1 : 0, `${owner}: ${key} access`);
    if (accessible) assert.equal(state[key][0].owner, owner, `${owner}: ${key} belongs to current owner`);
  }
  assert.equal(state.pricing.owner, owner);
  assert.equal(state.busy, false);
  assert.equal(state.pending, null);
  assert.equal(state.lastError, null);
}

async function logoutClearsBeforeRender() {
  const f = fixture(), request = f.start();
  assert.deepEqual(request.requests.map(item => item.url), adminPaths);
  settle(request.requests, 'admin'); await request.promise;
  assertOwned(f.cache.state, 'admin', 'admin');
  f.cache.state.location = { latitude: 21, longitude: 39 };
  f.cache.state.documentPreview = { kind: 'waybill', id: 'ADMIN-ONLY' };
  f.cache.state.lastError = new Error('Previous owner error');
  f.modal.innerHTML = '<iframe>Authenticated document</iframe>';
  const revision = f.cache.state.ownerRevision, count = f.calls.length;
  let observed = false;
  f.observeRender(() => {
    observed = true;
    assert.equal(f.cache.state.ownerKey, null);
    assertEmpty(f.cache.state, 'Logout before baseRender');
    assert.equal(f.modal.innerHTML, '', 'Authenticated modal clears before baseRender');
  });
  f.setUser(null); f.context.window.render();
  assert.equal(observed, true);
  assert.equal(f.cache.opsOwnerKey(), null);
  assert.equal(f.cache.state.ownerRevision, revision + 1);
  assert.equal(f.calls.length, count, 'Logged-out render makes no cache request');
  await f.cache.refreshOps(true);
  assert.equal(f.calls.length, count, 'Logged-out refresh makes no request');
  assert.equal(f.cache.state.ownerRevision, revision + 1, 'Repeated logout does not increment revision');
}

async function pendingLogoutDiscardsResponse() {
  const f = fixture(), old = f.start(), revision = f.cache.state.ownerRevision;
  f.cache.state.location = { latitude: 1, longitude: 2 };
  f.cache.state.documentPreview = { kind: 'manifest', id: 1 };
  f.modal.innerHTML = '<section>Private account modal</section>';
  f.setUser(null); f.context.window.render();
  assertEmpty(f.cache.state, 'Logout while refreshing');
  assert.equal(f.modal.innerHTML, '');
  const renders = f.renders, binds = f.binds;
  settle(old.requests, 'stale-admin'); await old.promise;
  assertEmpty(f.cache.state, 'Delayed admin response after logout');
  assert.equal(f.cache.state.ownerRevision, revision + 1);
  assert.equal(f.renders, renders, 'Delayed response cannot render after logout');
  assert.equal(f.binds, binds, 'Delayed response cannot bind after logout');
}

async function ownerSwitchDiscardsSuccess(nextUser) {
  const f = fixture(), old = f.start();
  const oldRevision = f.cache.state.ownerRevision;
  f.setUser(nextUser);
  const current = f.start();
  assert.equal(f.cache.state.ownerKey, `${nextUser.id}:${nextUser.role}`);
  assert.equal(f.cache.state.ownerRevision, oldRevision + 1);
  assert.equal(current.requests.length, nextUser.role === 'admin' ? 9 : 5,
    'The new owner starts a request without waiting for the old owner');
  assert.notEqual(current.pending, old.pending);
  assertEmpty(f.cache.state, 'Switch before results', false);
  settle(old.requests, 'stale-admin'); await old.promise;
  assertEmpty(f.cache.state, 'Stale success cannot fill new cache', false);
  assert.equal(f.cache.state.busy, true, 'Old success/finally cannot release the new request');
  assert.equal(f.cache.state.pending, current.pending);
  assert.equal(f.renders, 0, 'Stale success does not render');
  settle(current.requests, 'current-owner'); await current.promise;
  assertOwned(f.cache.state, 'current-owner', nextUser.role);
  assert.equal(f.renders, 1);
  assert.equal(f.binds, 1);
}

async function staleFailureCannotReleaseNewRequest() {
  const f = fixture(), old = f.start();
  f.setUser({ id: 2, role: 'employee' });
  const current = f.start();
  settle(old.requests, 'old', new Error('Old administrator request failed'));
  await old.promise;
  assertEmpty(f.cache.state, 'Stale failure ignored', false);
  assert.equal(f.cache.state.busy, true, 'Old failure/finally cannot release the new request');
  assert.equal(f.cache.state.pending, current.pending);
  const failure = new Error('Current employee request failed');
  settle(current.requests, 'current', failure); await current.promise;
  assert.equal(f.cache.state.lastError, failure, 'Current owner receives its own failure');
  assert.equal(f.cache.state.busy, false);
  assert.equal(f.cache.state.pending, null);
  const retry = f.start(true);
  settle(retry.requests, 'recovered-employee'); await retry.promise;
  assertOwned(f.cache.state, 'recovered-employee', 'employee');
}

async function liveOwnerGuard() {
  for (const failed of [false, true]) {
    const f = fixture(), old = f.start();
    f.setUser({ id: 7, role: 'employee' });
    // No render or refresh has synchronized the new owner yet: the live user check is essential.
    settle(old.requests, 'stale-live-user', failed ? new Error('Stale live-user failure') : null);
    await old.promise;
    for (const key of arrayKeys) assert.equal(f.cache.state[key].length, 0);
    assert.equal(f.cache.state.last, 0);
    assert.equal(f.cache.state.lastError, null);
    assert.equal(f.renders, 0);
    f.cache.syncOpsOwner();
    assertEmpty(f.cache.state, 'Synchronizing a live user change releases old busy state');
  }
}

async function sameAccountReturnUsesRevision() {
  const f = fixture(), old = f.start(), oldKey = f.cache.state.ownerKey;
  const revision = f.cache.state.ownerRevision;
  f.setUser(null); f.cache.syncOpsOwner();
  f.setUser({ id: 1, role: 'admin' });
  const current = f.start();
  assert.equal(f.cache.state.ownerKey, oldKey, 'Account returns to the same owner key');
  assert.equal(f.cache.state.ownerRevision, revision + 2);
  settle(old.requests, 'before-logout'); await old.promise;
  assertEmpty(f.cache.state, 'Same-key stale session cannot fill cache', false);
  assert.equal(f.cache.state.busy, true);
  assert.equal(f.cache.state.pending, current.pending, 'Revision prevents old session finally from releasing the new request');
  settle(current.requests, 'after-login'); await current.promise;
  assertOwned(f.cache.state, 'after-login', 'admin');
}

async function roleChangeForSameIdResetsCache() {
  const f = fixture(), admin = f.start();
  settle(admin.requests, 'admin'); await admin.promise;
  const revision = f.cache.state.ownerRevision;
  f.cache.state.location = { latitude: 4, longitude: 5 };
  f.cache.state.documentPreview = { kind: 'waybill', id: 'PRIVATE' };
  f.modal.innerHTML = 'Administrator document';
  f.setUser({ id: 1, role: 'employee' });
  const employee = f.start();
  assert.equal(f.cache.opsOwnerKey(), '1:employee');
  assert.equal(f.cache.state.ownerRevision, revision + 1);
  assert.deepEqual(employee.requests.map(item => item.url), commonPaths,
    'Fresh role bypasses the previous role cache and requests only authorized resources');
  assertEmpty(f.cache.state, 'Role change clears previous owner state', false);
  assert.equal(f.modal.innerHTML, '');
  settle(employee.requests, 'employee'); await employee.promise;
  assertOwned(f.cache.state, 'employee', 'employee');
}

async function sameOwnerCacheAndDedup() {
  const f = fixture(), first = f.start(), revision = f.cache.state.ownerRevision;
  const duplicate = f.start(), forcedDuplicate = f.start(true);
  assert.equal(f.calls.length, 9, 'Repeated refreshes deduplicate an in-flight request');
  assert.equal(duplicate.pending, first.pending);
  assert.equal(forcedDuplicate.pending, first.pending, 'Forced refresh also deduplicates while busy');
  f.cache.syncOpsOwner();
  assert.equal(f.cache.state.ownerRevision, revision);
  assert.equal(f.cache.state.pending, first.pending, 'Same-owner sync retains the active request');
  settle(first.requests, 'same-owner');
  await Promise.all([first.promise, duplicate.promise, forcedDuplicate.promise]);
  assertOwned(f.cache.state, 'same-owner', 'admin');
  assert.equal(f.cache.state.last, f.now);
  const cachedAt = f.now;
  f.setUser({ id: 1, role: 'admin', name: 'Updated display name' });
  f.setTime(cachedAt + 14999); await f.cache.refreshOps();
  assert.equal(f.calls.length, 9, 'Same owner retains cache for 15 seconds');
  assert.equal(f.cache.state.ownerRevision, revision);
  f.setTime(cachedAt + 15000);
  const expired = f.start();
  assert.equal(expired.requests.length, 9, 'Cache expires at 15 seconds');
  settle(expired.requests, 'expired-refresh'); await expired.promise;
  const forced = f.start(true);
  assert.equal(forced.requests.length, 9, 'Forced refresh bypasses a completed fresh cache');
  settle(forced.requests, 'forced-refresh'); await forced.promise;
  assertOwned(f.cache.state, 'forced-refresh', 'admin');
  assert.equal(f.cache.state.ownerRevision, revision);
}

async function permissionAndBranchChangesResetCache() {
  const initial={id:5,role:'employee',access_role:'office_employee',permissions:['shipments.read','shipments.create','branches.read','pricing.read'],branches:[{id:10},{id:20}],primary_branch_id:10};
  const changes=[
    {...initial,access_role:'accountant'},
    {...initial,permissions:['shipments.read','branches.read','pricing.read']},
    {...initial,branches:[{id:30}],primary_branch_id:30},
    {...initial,primary_branch_id:20}
  ];
  for(const next of changes){
    const f=fixture(initial),old=f.start(),revision=f.cache.state.ownerRevision,oldKey=f.cache.state.ownerKey;
    assert.deepEqual(old.requests.map(request=>request.url),['/api/branches','/api/pricing','/api/branch-directory'],'Request only permitted resources');
    f.setUser({...initial,permissions:[...initial.permissions].reverse(),branches:[...initial.branches].reverse()});
    assert.equal(f.cache.opsOwnerKey(),oldKey,'Order changes preserve the same access scope');
    f.setUser(next);const current=f.start();
    assert.equal(f.cache.state.ownerRevision,revision+1,'Canonical role, permission or office change invalidates cache');
    assert.notEqual(f.cache.state.ownerKey,oldKey);
    assert.notEqual(current.pending,old.pending);
    settle(old.requests,'old-scope');await old.promise;
    assertEmpty(f.cache.state,'Old scope is discarded',false);
    assert.equal(f.cache.state.busy,true);assert.equal(f.cache.state.pending,current.pending);
    settle(current.requests,'new-scope');await current.promise;
    assert.equal(f.cache.state.branches[0].owner,'new-scope');
    assert.equal(f.cache.state.pricing.owner,'new-scope');
    assert.equal(f.cache.state.users.length,0);assert.equal(f.cache.state.clients.length,0);
    assert.equal(f.cache.state.busy,false);assert.equal(f.cache.state.pending,null);
  }
}

(async () => {
  await logoutClearsBeforeRender();
  await pendingLogoutDiscardsResponse();
  await ownerSwitchDiscardsSuccess({ id: 2, role: 'employee' });
  await ownerSwitchDiscardsSuccess({ id: 9, role: 'admin' });
  await staleFailureCannotReleaseNewRequest();
  await liveOwnerGuard();
  await sameAccountReturnUsesRevision();
  await roleChangeForSameIdResetsCache();
  await sameOwnerCacheAndDedup();
  await permissionAndBranchChangesResetCache();
  console.log(JSON.stringify({ ok: true, offline: true, scenarios: 14,
    coverage: ['render clears before baseRender', 'logout clears populated and pending caches',
      'account and role switches discard stale success and failure', 'stale finally preserves new request',
      'live user and session revision guards', 'same-owner cache expiry, forced refresh and dedup',
      'permission, canonical role, office membership and primary-office invalidation'] }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
