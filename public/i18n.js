/* Offline, reversible UI translation. Form values and stored records stay canonical. */
(() => {
  'use strict';
  const packs = window.LOCALES;
  const rows = [
    ['العربية', 'Arabic', 'عربی', 'अरबी'],
    ['English', 'English', 'انگریزی', 'अंग्रेज़ी', 'الإنجليزية'],
    ['اردو', 'Urdu', 'اردو', 'उर्दू', 'الأردية'],
    ['हिन्दी', 'Hindi', 'ہندی', 'हिन्दी', 'الهندية'],
    ['Language', 'Language', 'زبان', 'भाषा', 'اللغة'],
    ['Ghazala Transport', 'Ghazala Transport', 'غزالا ٹرانسپورٹ', 'ग़ज़ाला ट्रांसपोर्ट', 'غزالا ترانسبورت'],
    ['GHAZALA TRANSPORT · KSA', 'Ghazala Transport · Saudi Arabia', 'غزالا ٹرانسپورٹ · سعودی عرب', 'ग़ज़ाला ट्रांसपोर्ट · सऊदी अरब', 'غزالا ترانسبورت · المملكة العربية السعودية'],
    ['KSA', 'Saudi Arabia', 'سعودی عرب', 'सऊदी अरब', 'المملكة العربية السعودية'],
    ['Saudi Arabia', 'Saudi Arabia', 'سعودی عرب', 'सऊदी अरब', 'المملكة العربية السعودية'],
    ['Admin · مدير نظام', 'Administrator', 'منتظم', 'प्रशासक', 'مدير النظام'],
    ['Manager · مدير', 'Manager', 'مینیجر', 'प्रबंधक', 'مدير'],
    ['Employee · موظف', 'Employee', 'ملازم', 'कर्मचारी', 'موظف'],
    ['Admin', 'Administrator', 'منتظم', 'प्रशासक', 'مدير النظام'],
    ['Manager', 'Manager', 'مینیجر', 'प्रबंधक', 'مدير العمليات'],
    ['Employee', 'Employee', 'ملازم', 'कर्मचारी', 'موظف'],
    ['غ', 'G', 'گ', 'ग'],
    ['التقاط أو اختيار صورة', 'Take or choose a photo', 'تصویر لیں یا منتخب کریں', 'फोटो लें या चुनें'],
    ['تغيير الصورة', 'Change photo', 'تصویر بدلیں', 'फोटो बदलें'],
    ['KB', 'KB', 'کلو بائٹ', 'किलोबाइट', 'كيلوبايت'],
    ['مؤسسة تجريبية للشحن', 'Demo shipping company', 'نمونہ شپنگ کمپنی', 'डेमो शिपिंग कंपनी'],
    ['غزالا ترانسبورت لخدمات الشحن والتوصيل بين جدة وجازان. متابعة تشغيلية للشحنات وخيارات الدفع عند الاستلام.', 'Ghazala Transport shipping and delivery between Jeddah and Jaazan, with shipment tracking and cash-on-delivery options.', 'جدہ اور جازان کے درمیان غزالا ٹرانسپورٹ کی شپنگ اور ڈیلیوری، شپمنٹ کی نگرانی اور وصولی پر ادائیگی کے ساتھ۔', 'जेद्दा और जाज़ान के बीच ग़ज़ाला ट्रांसपोर्ट की शिपिंग और डिलीवरी, शिपमेंट ट्रैकिंग और डिलीवरी पर भुगतान के विकल्पों के साथ।'],
    ['شحن موثوق بين جدة وجازان مع إدارة ومتابعة واضحة للشحنات.', 'Reliable shipping between Jeddah and Jaazan with clear shipment management and tracking.', 'جدہ اور جازان کے درمیان قابلِ اعتماد شپنگ، شپمنٹس کے واضح انتظام اور نگرانی کے ساتھ۔', 'जेद्दा और जाज़ान के बीच विश्वसनीय शिपिंग, स्पष्ट शिपमेंट प्रबंधन और ट्रैकिंग के साथ।'],
    ['GPS', 'GPS', 'جی پی ایس', 'जीपीएस', 'نظام تحديد الموقع'],
    ['Live GPS', 'Live GPS tracking', 'براہ راست مقام کی نگرانی', 'लाइव स्थान ट्रैकिंग', 'تتبع الموقع المباشر'],
    ['Batch Scan', 'Batch scan', 'اجتماعی اسکین', 'एक साथ स्कैन', 'المسح الجماعي'],
    ['Barcode', 'Barcode', 'بارکوڈ', 'बारकोड', 'الباركود'],
    ['barcode', 'Barcode', 'بارکوڈ', 'बारकोड', 'الباركود'],
    ['QR', 'QR code', 'کیو آر کوڈ', 'क्यूआर कोड', 'رمز الاستجابة السريعة'],
    ['الشاحنة', 'Truck', 'ٹرک', 'ट्रक'],
    ['شاحنة نقل', 'Transport truck', 'مال بردار ٹرک', 'मालवाहक ट्रक'],
    ['الجمعة', 'Friday', 'جمعہ', 'शुक्रवार'],
    ['الخميس', 'Thursday', 'جمعرات', 'गुरुवार'],
    ['الأربعاء', 'Wednesday', 'بدھ', 'बुधवार'],
    ['الثلاثاء', 'Tuesday', 'منگل', 'मंगलवार'],
    ['الإثنين', 'Monday', 'پیر', 'सोमवार'],
    ['الأحد', 'Sunday', 'اتوار', 'रविवार'],
    ['السبت', 'Saturday', 'ہفتہ', 'शनिवार'],
    ['يرجى تعبئة هذا الحقل.', 'Please fill in this field.', 'براہ کرم یہ خانہ پُر کریں۔', 'कृपया यह फ़ील्ड भरें।'],
    ['يرجى إدخال بريد إلكتروني صحيح.', 'Please enter a valid email address.', 'براہ کرم درست ای میل درج کریں۔', 'कृपया सही ईमेल पता दर्ज करें।'],
    ['يرجى إدخال رابط صحيح.', 'Please enter a valid URL.', 'براہ کرم درست لنک درج کریں۔', 'कृपया सही लिंक दर्ज करें।'],
    ['يرجى إدخال رقم صحيح.', 'Please enter a valid number.', 'براہ کرم درست عدد درج کریں۔', 'कृपया सही संख्या दर्ज करें।'],
    ['القيمة المدخلة لا تطابق التنسيق المطلوب.', 'The entered value does not match the required format.', 'درج کردہ قدر مطلوبہ شکل کے مطابق نہیں۔', 'दर्ज किया गया मान आवश्यक प्रारूप से मेल नहीं खाता।'],
    ['القيمة أقصر من الحد الأدنى المطلوب.', 'The value is shorter than the required minimum.', 'درج کردہ قدر مطلوبہ کم سے کم لمبائی سے چھوٹی ہے۔', 'मान आवश्यक न्यूनतम लंबाई से छोटा है।'],
    ['القيمة أطول من الحد الأقصى المسموح.', 'The value exceeds the allowed length.', 'درج کردہ قدر اجازت شدہ لمبائی سے بڑی ہے۔', 'मान अनुमत लंबाई से अधिक है।'],
    ['القيمة أقل من الحد الأدنى المسموح.', 'The value is below the allowed minimum.', 'درج کردہ قدر اجازت شدہ کم سے کم حد سے چھوٹی ہے۔', 'मान अनुमत न्यूनतम से कम है।'],
    ['القيمة أكبر من الحد الأقصى المسموح.', 'The value is above the allowed maximum.', 'درج کردہ قدر اجازت شدہ زیادہ سے زیادہ حد سے بڑی ہے۔', 'मान अनुमत अधिकतम से अधिक है।'],
    ['يرجى إدخال قيمة ضمن الزيادات المحددة.', 'Please enter a value in the specified increments.', 'براہ کرم مقررہ وقفوں کے مطابق قدر درج کریں۔', 'कृपया निर्धारित अंतराल के अनुसार मान दर्ज करें।']
  ];
  for (const [source, en, ur, hi, ar] of rows) {
    for (const [lang, value] of Object.entries({ ar: ar || source, en, ur, hi })) {
      packs[lang].phrases[source] = value;
    }
  }

  let language = 'ar', aliases, matcher;
  const cache = new Map(), textMemory = new WeakMap(), attributeMemory = new WeakMap();
  const skip = 'script,style,noscript,textarea,pre,code,[data-no-i18n],[translate="no"]';
  const attributes = ['placeholder', 'title', 'aria-label', 'aria-description', 'aria-valuetext', 'alt', 'data-label', 'content'];
  const normalize = value => String(value ?? '').replace(/\s+/gu, ' ').trim();
  const escapePattern = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  function compile() {
    aliases = new Map();
    const keys = [...new Set(Object.values(packs).flatMap(p => Object.keys(p.phrases)))].filter(key => !(/[\u0600-\u06ff]/u.test(key) && /[\u0900-\u097f]/u.test(key)));
    // Prefer the complete Arabic source when multiple labels share a translation.
    const coverage = key => Object.values(packs).filter(pack => Object.hasOwn(pack.phrases, key)).length;
    keys.sort((a, b) => coverage(b) - coverage(a) || Number(/[\u0600-\u06ff]/u.test(b)) - Number(/[\u0600-\u06ff]/u.test(a)) || b.length - a.length);
    const records = [];
    for (const key of keys) {
      const source = normalize(key);
      if (!source) continue;
      const translations = {};
      for (const [lang, pack] of Object.entries(packs)) {
        translations[lang] = pack.phrases[key] ?? (lang === 'ar' ? key : packs.en.phrases[key] ?? key);
      }
      const record = { source, translations };
      records.push(record);
      if (!aliases.has(source)) aliases.set(source, record);
    }
    // Direct source labels take precedence over another phrase's translated alias.
    for (const record of records) {
      for (const value of Object.values(record.translations)) {
        const alias = normalize(value);
        if (alias && !aliases.has(alias)) aliases.set(alias, record);
      }
    }
    const alternatives = [...aliases.keys()].sort((a, b) => b.length - a.length).map(escapePattern);
    matcher = new RegExp('(?<![\\p{L}\\p{M}\\p{N}_])(?:' + alternatives.join('|') + ')(?![\\p{L}\\p{M}\\p{N}_])', 'gu');
    cache.clear();
  }

  function translate(value, selected = language) {
    const text = String(value ?? '');
    if (!text.trim()) return text;
    const lang = packs[selected] ? selected : 'ar';
    const cacheKey = lang + '\u0000' + text;
    if (cache.has(cacheKey)) return cache.get(cacheKey);
    if (!aliases) compile();
    const core = normalize(text), exact = aliases.get(core);
    // One replacement pass prevents translating the newly inserted output again.
    const translated = exact ? exact.translations[lang] : core.replace(matcher, match => aliases.get(match).translations[lang]);
    const result = (text.match(/^\s*/u)?.[0] || '') + translated + (text.match(/\s*$/u)?.[0] || '');
    if (cache.size > 5000) cache.clear();
    cache.set(cacheKey, result);
    return result;
  }

  function updateText(node) {
    if (!node.parentElement || node.parentElement.closest(skip)) return;
    const current = node.nodeValue;
    if (!current?.trim()) return;
    let saved = textMemory.get(node);
    if (!saved || current !== saved.applied) saved = { source: translate(current, 'ar'), applied: current };
    const target = formatDateText(translate(saved.source));
    saved.applied = target;
    textMemory.set(node, saved);
    if (current !== target) node.nodeValue = target;
  }

  function updateAttributes(element) {
    if (element.closest(skip)) return;
    let saved = attributeMemory.get(element);
    if (!saved) { saved = {}; attributeMemory.set(element, saved); }
    for (const name of attributes) {
      if (name === 'content' && !element.matches('meta[name="description"],meta[property^="og:"],meta[name^="twitter:"]')) continue;
      if (!element.hasAttribute(name)) continue;
      const current = element.getAttribute(name);
      if (!saved[name] || current !== saved[name].applied) saved[name] = { source: translate(current, 'ar'), applied: current };
      const target = translate(saved[name].source);
      saved[name].applied = target;
      if (current !== target) element.setAttribute(name, target);
    }
    // Only explicitly marked default fields may translate a value. User input is never rewritten.
    if (element.hasAttribute('data-i18n-value') && !element.dataset.i18nEdited) {
      element.value = translate(element.getAttribute('data-i18n-value'));
    }
  }

  function localize(root = document) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) return updateText(root);
    if (root.nodeType === Node.ELEMENT_NODE) {
      if (root.closest(skip)) return;
      updateAttributes(root);
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) updateText(walker.currentNode);
    const selector = attributes.map(a => '[' + a + ']').concat('[data-i18n-value]').join(',');
    root.querySelectorAll?.(selector).forEach(updateAttributes);
  }

  function formatDate(value) {
    const raw = String(value || '');
    if (!/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/u.test(raw)) return raw;
    const hasTime = raw.length > 10;
    // datetime-local ETA/departures are Saudi wall time; SQLite space timestamps are UTC.
    const zone = hasTime && !/(?:Z|[+-]\d{2}:?\d{2})$/u.test(raw) ? (raw.includes('T') ? '+03:00' : 'Z') : '';
    const iso = raw.replace(' ', 'T') + zone;
    const date = new Date(iso);
    if (!Number.isFinite(date.getTime())) return raw;
    const locale = { ar: 'ar-SA-u-ca-gregory', en: 'en-GB', ur: 'ur-PK-u-ca-gregory', hi: 'hi-IN' }[language];
    return new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'Asia/Riyadh', ...(hasTime ? { hour: '2-digit', minute: '2-digit' } : {}) }).format(date);
  }

  function formatDateText(value) {
    return value.replace(/\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b/gu, formatDate);
  }

  function validationMessage(field) {
    const validity = field.validity;
    if (validity.valueMissing) return 'يرجى تعبئة هذا الحقل.';
    if (validity.typeMismatch) return field.type === 'email' ? 'يرجى إدخال بريد إلكتروني صحيح.' : 'يرجى إدخال رابط صحيح.';
    if (validity.badInput) return 'يرجى إدخال رقم صحيح.';
    if (validity.tooShort) return 'القيمة أقصر من الحد الأدنى المطلوب.';
    if (validity.tooLong) return 'القيمة أطول من الحد الأقصى المسموح.';
    if (validity.rangeUnderflow) return 'القيمة أقل من الحد الأدنى المسموح.';
    if (validity.rangeOverflow) return 'القيمة أكبر من الحد الأقصى المسموح.';
    if (validity.stepMismatch) return 'يرجى إدخال قيمة ضمن الزيادات المحددة.';
    if (validity.patternMismatch) return 'القيمة المدخلة لا تطابق التنسيق المطلوب.';
    return '';
  }

  function setLanguage(next) {
    language = packs[next] ? next : 'ar';
    const pack = packs[language];
    document.documentElement.lang = pack.lang;
    document.documentElement.dir = pack.dir;
    document.querySelectorAll('[data-i18n-validation]').forEach(field => {
      field.setCustomValidity(translate(field.dataset.i18nValidation));
    });
  }

  function observe() {
    let queued = false;
    const roots = new Set();
    new MutationObserver(changes => {
      for (const change of changes) {
        if (change.type === 'childList') change.addedNodes.forEach(node => roots.add(node));
        else roots.add(change.target);
      }
      if (!queued && roots.size) {
        queued = true;
        queueMicrotask(() => {
          queued = false;
          const pending = [...roots]; roots.clear();
          pending.filter(node => node.isConnected).forEach(localize);
        });
      }
    }).observe(document.body, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: attributes });
    document.addEventListener('invalid', event => {
      const field = event.target;
      if (!field.setCustomValidity || (field.validity.customError && !field.dataset.i18nValidation)) return;
      const message = validationMessage(field) || field.dataset.i18nValidation;
      if (message) { field.dataset.i18nValidation = message; field.setCustomValidity(translate(message)); }
    }, true);
    const clearValidation = event => {
      const field = event.target;
      // A payment change may hide a required field: custom errors must not keep it blocked.
      const fields = field.closest('form')?.querySelectorAll('[data-i18n-validation]') || [field];
      fields.forEach(input => {
        if (input.dataset.i18nValidation) { delete input.dataset.i18nValidation; input.setCustomValidity(''); }
      });
      if (field.hasAttribute('data-i18n-value')) field.dataset.i18nEdited = 'true';
    };
    document.addEventListener('input', clearValidation, true);
    document.addEventListener('change', clearValidation, true);
    localize(document.body);
  }

  for (const name of ['alert', 'confirm', 'prompt']) {
    const native = window[name].bind(window);
    window[name] = (message, ...args) => native(translate(message), ...args);
  }
  window.GhazalaI18n = { translate, canonical: value => translate(value, 'ar'), localize, setLanguage, formatDate, refresh: compile };
  compile();
  setLanguage(localStorage.getItem('ghz-language') || 'ar');
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', observe, { once: true });
  else observe();
})();
