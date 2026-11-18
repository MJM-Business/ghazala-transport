/* Developer build helper. The running app does not need Node.js or any AI service. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '..');
const names = ['locales.js', 'ops-locales.js', 'landing-locales.js', 'workflow-locales.js'];
const context = { window: {} };
vm.createContext(context);
for (const name of names) vm.runInContext(fs.readFileSync(path.join(root, 'static', name), 'utf8'), context, { filename: name });
const commonSource = fs.readFileSync(path.join(root, 'static', 'i18n.js'), 'utf8');
const rows = vm.runInNewContext(commonSource.match(/const rows = (\[[\s\S]*?\n  \]);/)[1]);
const packs = context.window.LOCALES;
for (const [source, en, ur, hi, ar] of rows) {
  for (const [language, value] of Object.entries({ ar: ar || source, en, ur, hi })) packs[language].phrases[source] = value;
}
const canonical = [...new Set(Object.values(packs).flatMap(p => Object.keys(p.phrases)))].filter(key => /[\u0600-\u06ff]/u.test(key) && !/[\u0900-\u097f]/u.test(key));
for (const language of ['en', 'ur', 'hi']) {
  const missing = canonical.filter(key => !Object.hasOwn(packs[language].phrases, key));
  if (missing.length) throw new Error(language + ' translations missing: ' + missing.join(', '));
}
fs.mkdirSync(path.join(root, 'assets'), { recursive: true });
fs.writeFileSync(path.join(root, 'assets', 'ui-translations.json'), JSON.stringify(Object.fromEntries(Object.entries(packs).map(([language, pack]) => [language, pack.phrases])), null, 2), 'utf8');
for (const name of [...names, 'i18n.js', 'app.js', 'ops.js', 'index.html', 'style.css']) {
  for (const target of [root, path.join(root, 'public')]) fs.copyFileSync(path.join(root, 'static', name), path.join(target, name));
}
console.log('Language catalogs synchronized: ' + Object.entries(packs).map(([language, pack]) => language + '=' + Object.keys(pack.phrases).length).join(', '));
