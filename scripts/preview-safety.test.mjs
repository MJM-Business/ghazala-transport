import assert from 'node:assert/strict';
import {after, before, test} from 'node:test';
import {createServer} from 'node:http';
import {EventEmitter} from 'node:events';
import {registerHooks} from 'node:module';
import {runInNewContext} from 'node:vm';
import {previewSettings, demoMessages} from '../src/preview-safety.ts';
import {handlePreviewApi} from '../src/preview-api-shim.ts';

let server;
let origin;
let viteConfig;
before(async () => {
  // Exercise our actual config without installing Vite or its transform plugins.
  // These small adapters do not claim to test Vite's own server implementation.
  const adapters = {
    vite: 'export const defineConfig = value => value; export const loadEnv = () => ({});',
    '@vitejs/plugin-react': 'export default () => ({name: "react-test-adapter"});',
    '@tailwindcss/vite': 'export default () => ({name: "tailwind-test-adapter"});',
  };
  const hooks = registerHooks({
    resolve(specifier, context, nextResolve) {
      if (Object.hasOwn(adapters, specifier)) {
        return {url: 'data:text/javascript,' + encodeURIComponent(adapters[specifier]), shortCircuit: true};
      }
      return nextResolve(specifier, context);
    },
  });
  try { viteConfig = (await import('../vite.config.ts')).default; }
  finally { hooks.deregister(); }
  server = createServer(async (request, response) => {
    try {
      if (!await handlePreviewApi(request, response, {enabled: true})) {
        response.writeHead(404).end();
      }
    } catch (error) {
      response.writeHead(500).end(String(error));
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
});
after(async () => {
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
});

async function request(path, {cookie, body, method = body ? 'POST' : 'GET'} = {}) {
  const headers = {};
  if (cookie) headers.Cookie = cookie;
  if (body) headers['Content-Type'] = 'application/json';
  const response = await fetch(origin + path, {method, headers, body: body ? JSON.stringify(body) : undefined});
  return {status: response.status, headers: response.headers, data: await response.json()};
}
async function login(username = 'admin@ghazala.sa', password = 'Admin123!') {
  const result = await request('/api/login', {body: {username, password}});
  assert.equal(result.status, 200);
  return result.headers.get('set-cookie').split(';')[0];
}

test('persistent proxy is the default and both runtimes bind locally', () => {
  for (const mode of ['development', 'production', 'test', '']) {
    assert.deepEqual(previewSettings(mode, {}), {
      demo: false, backendUrl: 'http://127.0.0.1:8010', host: '127.0.0.1', port: 3000,
    });
  }
  assert.deepEqual(previewSettings('demo', {}), {
    demo: true, backendUrl: 'http://127.0.0.1:8010', host: '127.0.0.1', port: 3001,
  });
  assert.throws(() => previewSettings('demo', {}, 'build'), /only through npm run dev:demo/);
  assert.throws(() => previewSettings('demo', {}, 'serve', true), /only through npm run dev:demo/);
});

test('backend configuration accepts origins and rejects paths or embedded credentials', () => {
  assert.equal(previewSettings('development', {GHAZALA_BACKEND_URL: 'http://127.0.0.1:8123/'}).backendUrl, 'http://127.0.0.1:8123');
  for (const value of ['file:///tmp/api', 'http://user:secret@localhost:8010', 'http://localhost:8010/api', 'http://localhost:8010/?token=x', 'http://localhost:8010/#api']) {
    assert.throws(() => previewSettings('development', {GHAZALA_BACKEND_URL: value}));
  }
});

test('demo notice has all four languages', () => {
  assert.deepEqual(Object.keys(demoMessages), ['ar', 'en', 'ur', 'hi']);
  for (const message of Object.values(demoMessages)) assert.match(message, /PDF/);
  assert.doesNotMatch(demoMessages.en, /[\u0600-\u06ff]/u);
  assert.doesNotMatch(demoMessages.hi, /[\u0600-\u06ff]/u);
});

test('Vite config wires the Python proxy in dev and build preview without a demo plugin', () => {
  for (const context of [
    {mode: 'development', command: 'serve', isPreview: false},
    {mode: 'production', command: 'serve', isPreview: true},
    {mode: 'production', command: 'build', isPreview: false},
  ]) {
    const config = viteConfig(context);
    assert.equal(config.server.host, '127.0.0.1');
    assert.equal(config.preview.host, '127.0.0.1');
    assert.equal(config.server.strictPort, true);
    assert.equal(config.preview.strictPort, true);
    assert.equal(config.server.proxy, config.preview.proxy);
    assert.equal(config.server.proxy['/api'].target, previewSettings(context.mode, process.env).backendUrl);
    assert.equal(config.server.proxy['/api'].changeOrigin, false);
    assert.equal(config.plugins.some(plugin => plugin.name === 'ghazala-explicit-demo'), false);
  }
});

test('proxy failures return a JSON error and never create a demo response', () => {
  const proxy = new EventEmitter();
  viteConfig({mode: 'development', command: 'serve'}).server.proxy['/api'].configure(proxy);
  const headers = {};
  let result;
  const response = {
    headersSent: false, writableEnded: false,
    setHeader(key, value) {headers[key] = value;},
    end(value) {result = value; this.headersSent = this.writableEnded = true;},
  };
  proxy.emit('error', new Error('isolated unavailable backend'), {}, response);
  assert.equal(response.statusCode, 503);
  assert.match(headers['Content-Type'], /^application\/json/);
  assert.match(JSON.parse(result).error, /Python backend unavailable/);
  assert.equal(headers['X-Ghazala-Preview'], undefined);
});

test('explicit demo config has no proxy and its visible notice follows language changes', async () => {
  const config = viteConfig({mode: 'demo', command: 'serve'});
  assert.equal(config.server.port, 3001);
  assert.equal(config.server.proxy, undefined);
  const plugin = config.plugins.find(item => item.name === 'ghazala-explicit-demo');
  assert.ok(plugin);
  const tags = plugin.transformIndexHtml();
  const notice = tags.find(tag => tag.attrs?.id === 'ghz-demo-banner');
  assert.equal(notice.tag, 'aside');
  assert.ok(Object.hasOwn(notice.attrs, 'data-no-i18n'));
  const banner = {};
  const listeners = {};
  runInNewContext(tags.find(tag => tag.tag === 'script').children, {
    document: {getElementById() {return banner;}},
    localStorage: {getItem() {return 'hi';}},
    window: {addEventListener(event, callback) {listeners[event] = callback;}},
  });
  assert.equal(banner.textContent, demoMessages.hi);
  assert.equal(banner.dir, 'ltr');
  for (const language of ['ar', 'en', 'ur', 'hi']) {
    listeners['ghazala:languagechange']({detail: {language}});
    assert.equal(banner.textContent, demoMessages[language]);
    assert.equal(banner.lang, language);
  }
  let middleware;
  await plugin.configureServer({middlewares: {use(value) {middleware = value;}}});
  assert.equal(typeof middleware, 'function');
});

test('demo handler remains disabled without explicit opt-in', async () => {
  const response = {setHeader() {assert.fail('disabled handler must not write headers');}};
  assert.equal(await handlePreviewApi({url: '/api/me', headers: {}}, response), false);
});

test('anonymous requests never gain admin access and Python cookies are ignored', async () => {
  assert.equal((await request('/api/me')).data.user, null);
  assert.equal((await request('/api/shipments')).status, 401);
  assert.equal((await request('/api/shipments', {cookie: 'ghz_session=mock_preview_token'})).status, 401);
  assert.equal((await request('/api/shipments', {cookie: 'ghz_preview_session=invalid'})).status, 401);
  assert.equal((await request('/api/public/tracking/GHZ-000125')).status, 200);
});

test('login identities remain separate and logout revokes only its own session', async () => {
  const admin = await login();
  const manager = await login('manager@ghazala.sa', 'Manager123!');
  assert.match(admin, /^ghz_preview_session=[a-f0-9]{64}$/);
  assert.notEqual(admin, manager);
  assert.equal((await request('/api/me', {cookie: admin})).data.user.role, 'admin');
  assert.equal((await request('/api/me', {cookie: manager})).data.user.role, 'manager');
  assert.equal((await request('/api/me')).data.user, null);
  assert.equal((await request('/api/logout', {method: 'POST', cookie: admin})).status, 200);
  assert.equal((await request('/api/shipments', {cookie: admin})).status, 401);
  assert.equal((await request('/api/me', {cookie: manager})).data.user.role, 'manager');
});

test('a repeated login rotates the browser session token', async () => {
  const oldCookie = await login();
  const result = await request('/api/login', {cookie: oldCookie, body: {username: 'admin@ghazala.sa', password: 'Admin123!'}});
  assert.equal(result.status, 200);
  const newCookie = result.headers.get('set-cookie').split(';')[0];
  assert.notEqual(newCookie, oldCookie);
  assert.equal((await request('/api/shipments', {cookie: oldCookie})).status, 401);
  assert.equal((await request('/api/shipments', {cookie: newCookie})).status, 200);
});

test('PDF, Excel and ticket requests cannot create placeholder attachments', async () => {
  const cookie = await login();
  for (const format of ['pdf', 'xlsx']) {
    for (const language of ['ar', 'en', 'ur', 'hi']) {
      for (const prepare of ['0', '1']) {
        const result = await request(`/api/reports/shipments?format=${format}&lang=${language}&prepare=${prepare}`, {cookie});
        assert.equal(result.status, 503);
        assert.match(result.headers.get('content-type'), /^application\/json/);
        assert.equal(result.headers.get('content-disposition'), null);
        assert.equal(result.headers.get('x-ghazala-preview'), 'demo-memory');
        assert.match(result.data.error, /Python/);
        if (language === 'en') assert.match(result.data.error, /require the Python backend/);
        if (language === 'hi') assert.doesNotMatch(result.data.error, /[\u0600-\u06ff]/u);
        assert.equal(result.data.url, undefined);
      }
    }
  }
  assert.equal((await request('/api/reports/shipments?ticket=preview_ticket_old', {cookie})).status, 503);
});
