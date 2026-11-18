/** Development runtime selection; the persistent backend is always the default. */
export function previewSettings(
  mode: string,
  environment: Record<string, string | undefined>,
  command = 'serve',
  isPreview = false,
) {
  const demo = mode === 'demo';
  if (demo && (command === 'build' || isPreview)) {
    throw new Error('The in-memory demo is available only through npm run dev:demo.');
  }
  const backendUrl = new URL(environment.GHAZALA_BACKEND_URL || 'http://127.0.0.1:8010');
  if (!['http:', 'https:'].includes(backendUrl.protocol) || backendUrl.username || backendUrl.password ||
      backendUrl.pathname !== '/' || backendUrl.search || backendUrl.hash) {
    throw new Error('GHAZALA_BACKEND_URL must be an HTTP(S) origin, for example http://127.0.0.1:8010.');
  }
  return { demo, backendUrl: backendUrl.origin, host: '127.0.0.1', port: demo ? 3001 : 3000 };
}

export const demoMessages = {
  ar: 'معاينة تجريبية · التغييرات تُفقد عند إعادة التشغيل · تقارير PDF وExcel تتطلب خادم Python',
  en: 'Demo preview · changes reset on restart · PDF and Excel reports require the Python server',
  ur: 'ڈیمو پیش نظارہ · دوبارہ شروع کرنے پر تبدیلیاں مٹ جاتی ہیں · PDF اور Excel رپورٹوں کے لیے Python سرور درکار ہے',
  hi: 'डेमो प्रीव्यू · दोबारा शुरू करने पर बदलाव मिट जाते हैं · PDF और Excel रिपोर्ट के लिए Python सर्वर आवश्यक है',
};
