# Ghazala Transport

The local application uses `server.py` with SQLite. Its browser interface is the HTML, CSS and JavaScript in `static/`, with Arabic, English, Urdu and Hindi catalogs. Node.js and AI service credentials are not required to run the Python application.

## Run the persistent application

Use Python 3.11 or newer, or the portable Python provided with the standalone package. Install `requirements.txt` in that Python environment for PDF, Excel and barcode support:

```powershell
python -m pip install -r requirements.txt
python start_local.py --port 8010
```

The launcher prints the actual address and opens the browser. If port 8010 is occupied, it selects a nearby free port. Keep the Python process open; use `--no-browser` to suppress automatic browser opening. Both Python launchers bind to `127.0.0.1` by default.

`work/ghazala.sqlite3` holds the application's persistent records. `server.py` owns API validation, authentication and database writes; `reports.py` generates authenticated shipment reports. Optional SMS credentials and `PUBLIC_BASE_URL` are listed in `.env.example`. Python reads them from its process environment and does not load `.env` files automatically.

Report summaries show **requested COD amounts** and **recorded shipment charges including VAT**. These are sums of stored shipment fields. They do not establish cash collection, settlement, invoices or recognized revenue.

## Vite development with the Python backend

Use Node.js 24 for the development commands and focused preview tests:

```powershell
npm install
npm run sync:static
npm run dev
```

Vite listens on `http://127.0.0.1:3000` and forwards `/api` requests to `http://127.0.0.1:8010`. Start the Python application separately. If Python prints a different port, set `GHAZALA_BACKEND_URL` in `.env.local` or the Vite process environment to that origin, then restart Vite. For example:

```powershell
$env:GHAZALA_BACKEND_URL = "http://127.0.0.1:8011"
npm run dev
```

This mode uses the Python database, sessions and real report downloads. If Python is unavailable, API requests fail; Vite never substitutes demo records. The server uses a strict port so an occupied port produces an error instead of silently opening a different runtime.

`npm run build` synchronizes the static sources and builds the Vite distribution. `npm run preview` serves that build on `http://127.0.0.1:4173` with the same Python API proxy. Vite preview is a local build review server; deployment of the Python application continues to use `server.py` and `static/`.

## Explicit temporary demo

```powershell
npm run dev:demo
```

This separate command opens `http://127.0.0.1:3001` with an always-visible demo notice in the selected UI language. The demo is synthetic and held in Vite memory. Changes disappear when Vite restarts, and demo users share those sample records. It does not read or write SQLite, send real SMS, or represent the Python backend's validation and authorization rules.

An explicit login is required. The existing sample accounts are `admin@ghazala.sa` / `Admin123!`, `manager@ghazala.sa` / `Manager123!`, and `employee@ghazala.sa` / `Employee123!`. The demo uses a separate `ghz_preview_session` cookie; it does not accept or replace the Python `ghz_session` cookie. PDF and Excel exports return an unavailable error instead of placeholder attachments. Building or previewing a distribution in demo mode is disabled.

## Source ownership and synchronization

Edit the browser interface in `static/`. Run `npm run sync:static` after changes. `scripts/sync-locales.cjs` checks the language catalogs, generates `assets/ui-translations.json` for report translation, and copies the canonical browser files to the project root and `public/` for Vite. Those copies are generated mirrors; editing them independently creates drift. Vite configuration and its explicit demo handler live in `vite.config.ts` and `src/preview-api-shim.ts`.

Run `npm run test:preview` for focused mode, configuration, session and report safeguards. These tests use isolated local HTTP servers and in-memory sample data; configuration tests use small adapters for Vite's transform plugins. They neither import the Python application nor access the application's SQLite database. A full Vite build requires the installed Node dependencies.

## Database migrations and baseline safety

Python startup runs `migrations.py` through the ordered `MIGRATIONS` registry in `server.py`, inside one explicit SQLite transaction. The `schema_migrations` ledger records each applied version once. Existing databases are adopted without seeding or rewriting shipment, AWB, user or delivery history. Fresh sample data is created only on first initialization of a completely empty database.

Every future schema change must be a new, uniquely named migration with a version higher than every applied version. Keep applied migration versions/names immutable. Use additive changes and preserve existing tables and data; do not add unversioned startup schema changes, drop/recreate tables or reinitialize the database. A failed callback rolls back its schema and ledger changes together. Do not run an older server against a newer ledger.

The admin-only demo removal action deletes only records marked `is_demo=1` and saves `app_settings.demo_data_disabled=1` in the same transaction. Users and drivers referenced by retained shipments, routes or user accounts are preserved. Restarting does not restore removed demo data. Never use the reset action as a production regression test.

The generic shipment status endpoint cannot complete delivery without saved POD evidence and a verified, unexpired-at-verification OTP. Complete new deliveries through the POD screen. Historical completed deliveries remain intact, and completed proof cannot be replaced or reopened through generic status changes.

Run regression checks from the project directory:

```powershell
python tests/test_baseline_regression.py --json-output outputs/baseline-regression-results.json
node tests/frontend_baseline_smoke.cjs
node tests/frontend_ops_cache_smoke.cjs
npm run test:preview
```

The Python harness backs up the operational database in read-only mode into disposable test directories before starting an isolated HTTP server. All creation, OTP, status, route, location, demo reset and restart checks use those copies. It never runs migrations or writes test records against the operational database. Outbound SMS transport is disabled in the harness. The frontend fixtures verify shipment-specific evidence and stale-response isolation without accessing SQLite.
