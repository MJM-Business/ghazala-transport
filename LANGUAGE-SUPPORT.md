# Application languages

The interface supports English, Arabic, Urdu and Hindi. Select a language in the header. The browser remembers the choice. Arabic and Urdu use RTL; English and Hindi use LTR.

The catalogs cover the landing page, navigation, forms, dialogs, validation, notifications, shipment tracking, waybills and report labels. Language changes update open forms in place, preserving entered details, uploaded photos and delivery signatures.

Names, addresses, identifiers, email addresses and tracking numbers are record data. Their saved spelling and values are retained. System status, route, location and ETA descriptions are localized for display; canonical values are used by the backend.

## Editing translations

Edit the primary files in `static/`:

- `landing-locales.js`: landing page and service dialogs.
- `workflow-locales.js`: operational screens and messages.
- `i18n.js`: shared labels and the reversible translation engine.
- `locales.js` and `ops-locales.js`: original catalogs.

After editing, a developer can run `node scripts/sync-locales.cjs` to update the root/public copies and `assets/ui-translations.json` used by PDF and Excel reports. Node.js is needed only for this editing helper; the Python app itself uses the generated files.

Translations are bundled locally. The app does not call an AI or online translation service.
