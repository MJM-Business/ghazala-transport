import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import {defineConfig, loadEnv, type Plugin, type ProxyOptions} from 'vite';
import {demoMessages, previewSettings} from './src/preview-safety.ts';

export default defineConfig(({mode, command, isPreview}) => {
  const environment = {...loadEnv(mode, process.cwd(), ''), ...process.env};
  const settings = previewSettings(mode, environment, command, isPreview);
  const proxy: Record<string, ProxyOptions> | undefined = settings.demo ? undefined : {
    '/api': {
      target: settings.backendUrl,
      // Keep the browser origin for tracking links and session cookies.
      changeOrigin: false,
      configure(proxyServer) {
        proxyServer.on('error', (_error, _req, res) => {
          if ('setHeader' in res && !res.headersSent && !res.writableEnded) {
            res.statusCode = 503;
            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.setHeader('Cache-Control', 'no-store');
            res.end(JSON.stringify({error: 'Python backend unavailable. Start the Python server or check GHAZALA_BACKEND_URL.'}));
          }
        });
      },
    },
  };
  const demoPlugin: Plugin = {
    name: 'ghazala-explicit-demo',
    async configureServer(server) {
      const {handlePreviewApi} = await import('./src/preview-api-shim.ts');
      server.middlewares.use(async (req, res, next) => {
        try {
          if (!await handlePreviewApi(req, res, {enabled: true})) next();
        } catch (error) {
          console.error('Demo API error', error);
          if (!res.headersSent) {
            res.statusCode = 503;
            res.setHeader('Content-Type', 'application/json; charset=utf-8');
            res.setHeader('Cache-Control', 'no-store');
            res.end(JSON.stringify({error: 'Demo preview request failed.'}));
          } else if (!res.writableEnded) res.end();
        }
      });
    },
    transformIndexHtml() {
      return [
        {tag: 'style', children: '#ghz-demo-banner{position:fixed;z-index:10000;bottom:calc(74px + env(safe-area-inset-bottom));inset-inline:12px;max-width:720px;margin-inline:auto;padding:10px 14px;border:2px solid #b45309;border-radius:10px;background:#fffbeb;color:#78350f;font:600 13px/1.7 Arial,sans-serif;text-align:center;box-shadow:0 3px 14px #0002}', injectTo: 'head'},
        {tag: 'aside', attrs: {id: 'ghz-demo-banner', 'data-no-i18n': '', role: 'status'}, children: demoMessages.ar, injectTo: 'body'},
        {tag: 'script', children: `(() => {
          const messages = ${JSON.stringify(demoMessages)};
          const banner = document.getElementById('ghz-demo-banner');
          const update = language => {
            const selected = Object.hasOwn(messages, language) ? language : 'ar';
            banner.textContent = messages[selected];
            banner.lang = selected;
            banner.dir = ['ar', 'ur'].includes(selected) ? 'rtl' : 'ltr';
          };
          let language = 'ar';
          try { language = localStorage.getItem('ghz-language') || 'ar'; } catch {}
          update(language);
          window.addEventListener('ghazala:languagechange', event => update(event.detail?.language));
        })();`, injectTo: 'body'},
      ];
    },
  };
  return {
    plugins: [react(), tailwindcss(), ...(settings.demo ? [demoPlugin] : [])],
    resolve: {alias: {'@': path.resolve(import.meta.dirname, '.')}},
    server: {
      host: settings.host,
      port: settings.port,
      strictPort: true,
      proxy,
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
    preview: {host: settings.host, port: 4173, strictPort: true, proxy},
  };
});
