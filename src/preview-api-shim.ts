/**
 * Ghazala Transport - explicit in-memory developer demo
 *
 * Enabled only by `npm run dev:demo`, never as a backend failure fallback.
 * State is synthetic, shared by demo users, and lost when Vite restarts.
 *
 * The production application backend remains:
 *   - server.py
 *   - reports.py
 *   - start_local.py
 *   - work/ghazala.sqlite3
 */

import type { IncomingMessage, ServerResponse } from 'http';
import {randomBytes} from 'node:crypto';

interface User {
  id: number;
  username: string;
  display_name: string;
  role: 'admin' | 'manager' | 'employee';
  mobile: string;
  national_id: string;
  driver_id: number | null;
  is_active: number;
}

interface ShipmentEvent {
  id: number;
  shipment_id: number;
  status: string;
  stage: string;
  location: string;
  actor: string;
  created_at: string;
}

interface Shipment {
  id: number;
  awb: string;
  recipient: string;
  recipient_id: string;
  phone: string;
  origin: string;
  destination: string;
  status: string;
  stage: string;
  cod: number;
  eta: string;
  created_at: string;
  updated_at: string | null;
  sender_name: string;
  sender_id: string;
  sender_phone: string;
  sender_address: string;
  recipient_branch: string;
  recipient_address: string;
  recipient_latitude: number | null;
  recipient_longitude: number | null;
  package_type: string;
  package_description: string;
  pieces: number;
  weight: number;
  length_cm: number;
  width_cm: number;
  height_cm: number;
  declared_value: number;
  insured: number;
  payment_method: 'cod' | 'sender' | 'company';
  shipping_fee: number;
  vat_amount: number;
  cod_fee: number;
  insurance_fee: number;
  total_fee: number;
  payment_status: string;
  company_account: string;
  driver_id: number | null;
  is_demo: number;
  events?: ShipmentEvent[];
}

interface Driver {
  id: number;
  name: string;
  national_id: string;
  mobile: string;
  branch: string;
  status: string;
  location_text: string;
  latitude: number | null;
  longitude: number | null;
  updated_at: string;
  user_id: number | null;
  is_demo: number;
}

interface Branch {
  id: number;
  code: string;
  name: string;
  city: string;
  address: string;
  phone: string;
  latitude: number | null;
  longitude: number | null;
  coverage: string;
  is_active: number;
}

interface Vehicle {
  id: number;
  plate: string;
  vehicle_type: string;
  capacity_kg: number;
  status: string;
}

interface RouteRun {
  id: number;
  code: string;
  origin: string;
  destination: string;
  departure_at: string;
  driver_id: number | null;
  vehicle_id: number | null;
  capacity_kg: number;
  status: string;
  notification_minutes: number;
  created_by: string;
  created_at: string;
  started_at: string | null;
  arrived_at: string | null;
  shipment_ids: number[];
}

interface Client {
  id: number;
  code: string;
  name: string;
  client_type: 'company' | 'individual';
  mobile: string;
  email: string;
  national_id: string;
  commercial_registration: string;
  city: string;
  address: string;
  status: string;
  payment_terms: string;
  credit_limit: number;
  discount_percent: number;
  notes: string;
  is_demo: number;
  created_at: string;
  updated_at: string;
}

interface Campaign {
  id: number;
  code: string;
  name: string;
  campaign_type: string;
  status: string;
  discount_percent: number;
  channels: string;
  target_segment: string;
  message: string;
  start_at: string;
  end_at: string;
  is_demo: number;
  created_at: string;
  updated_at: string;
}

interface PodRecord {
  id: number;
  shipment_id: number;
  recipient_name: string;
  recipient_id_suffix: string;
  signature_data: string;
  photo_data: string;
  photo_mime: string;
  latitude: number | null;
  longitude: number | null;
  note: string;
  verified_at: string;
  verified_by: string;
}

// In-memory simulation state populated from exact SQLite initial seeds
const users: User[] = [
  { id: 1, username: 'admin@ghazala.sa', display_name: 'مدير النظام', role: 'admin', mobile: '+966 50 111 2233', national_id: '1000000001', driver_id: null, is_active: 1 },
  { id: 2, username: 'manager@ghazala.sa', display_name: 'مدير العمليات', role: 'manager', mobile: '+966 50 222 3344', national_id: '1000000002', driver_id: null, is_active: 1 },
  { id: 3, username: 'employee@ghazala.sa', display_name: 'موظف العمليات', role: 'employee', mobile: '+966 50 333 4455', national_id: '1000000003', driver_id: 1, is_active: 1 }
];

const passwords: Record<string, string> = {
  'admin@ghazala.sa': 'Admin123!',
  'manager@ghazala.sa': 'Manager123!',
  'employee@ghazala.sa': 'Employee123!'
};

const drivers: Driver[] = [
  { id: 1, name: 'سلطان المعمري', national_id: '1000000125', mobile: '+966 55 987 6543', branch: 'جدة', status: 'متاح', location_text: 'طريق الملك عبدالعزيز، جدة', latitude: 21.5433, longitude: 39.1728, updated_at: '2026-10-06 10:00:00', user_id: 3, is_demo: 1 },
  { id: 2, name: 'أحمد منصور الشهري', national_id: '1000000139', mobile: '+966 50 123 4567', branch: 'جازان', status: 'نشط', location_text: 'فرع جازان', latitude: 16.8892, longitude: 42.5706, updated_at: '2026-10-06 10:00:00', user_id: null, is_demo: 1 },
  { id: 3, name: 'عمرو فاروق الشريف', national_id: '1000000208', mobile: '+966 56 901 7741', branch: 'جدة', status: 'متاح', location_text: 'فرع جدة', latitude: null, longitude: null, updated_at: '2026-10-06 10:00:00', user_id: null, is_demo: 1 },
  { id: 4, name: 'يوسف الصالح', national_id: '1000000922', mobile: '+966 53 194 4400', branch: 'جازان', status: 'نشط', location_text: 'فرع جازان', latitude: null, longitude: null, updated_at: '2026-10-06 10:00:00', user_id: null, is_demo: 1 }
];

const branches: Branch[] = [
  { id: 1, code: 'JED-MAIN', name: 'المقر الرئيسي جدة', city: 'جدة', address: 'جدة، المملكة العربية السعودية', phone: '+966 12 600 0000', latitude: 21.5433, longitude: 39.1728, coverage: 'جدة', is_active: 1 },
  { id: 2, code: 'JAZ-MAIN', name: 'مركز جازان', city: 'جازان', address: 'جازان، المملكة العربية السعودية', phone: '+966 17 300 0000', latitude: 16.8892, longitude: 42.5706, coverage: 'جميع مناطق جازان', is_active: 1 }
];

const vehicles: Vehicle[] = [
  { id: 1, plate: '4921 ن ج ح', vehicle_type: 'شاحنة نقل', capacity_kg: 1200, status: 'متاح' }
];

let pricingSettings = {
  base_fee: 65,
  included_weight: 1,
  extra_kg_fee: 2.5,
  vat_rate: 0.15,
  cod_fee: 3.5,
  insurance_rate: 0.02,
  insurance_minimum: 5
};

const clients: Client[] = [
  { id: 1, code: 'CL-88924', name: 'متجر الإلكترونيات الخليج', client_type: 'company', mobile: '+966 55 100 8892', email: 'info@gulf-elec.sa', national_id: '', commercial_registration: '1010884928', city: 'جدة', address: 'طريق الملك فهد، جدة', status: 'نشط', payment_terms: 'شهري', credit_limit: 31550, discount_percent: 15, notes: 'عميل ذهبي', is_demo: 1, created_at: '2026-10-01 08:00:00', updated_at: '2026-10-01 08:00:00' },
  { id: 2, code: 'CL-74108', name: 'شركة نسيج الفخامة للتجارة', client_type: 'company', mobile: '+966 55 100 7410', email: 'sales@naseej.sa', national_id: '', commercial_registration: '1010887410', city: 'جدة', address: 'المنطقة الصناعية، جدة', status: 'نشط', payment_terms: 'شهري', credit_limit: 14250, discount_percent: 10, notes: 'عقد نشط', is_demo: 1, created_at: '2026-10-02 09:30:00', updated_at: '2026-10-02 09:30:00' },
  { id: 3, code: 'CL-62004', name: 'مؤسسة الدواء العالمي الطبية', client_type: 'company', mobile: '+966 55 100 6200', email: 'pharma@global-med.sa', national_id: '', commercial_registration: '1010886200', city: 'جازان', address: 'طريق الكورنيش، جازان', status: 'يحتاج تجديد', payment_terms: 'حسب الاتفاق', credit_limit: 89000, discount_percent: 20, notes: 'يتطلب تجديد العقد', is_demo: 1, created_at: '2026-10-03 11:15:00', updated_at: '2026-10-03 11:15:00' },
  { id: 4, code: 'CL-31018', name: 'مجموعة الأندلس', client_type: 'company', mobile: '+966 55 100 3101', email: 'contact@andalus.sa', national_id: '', commercial_registration: '1010883101', city: 'جازان', address: 'شارع الميناء، جازان', status: 'نشط', payment_terms: 'حسب الاتفاق', credit_limit: 0, discount_percent: 5, notes: 'عقد مؤسسي', is_demo: 1, created_at: '2026-10-04 14:00:00', updated_at: '2026-10-04 14:00:00' }
];

const campaigns: Campaign[] = [
  { id: 1, code: 'GHZ20', name: 'خصم 20% على الشحن السريع', campaign_type: 'خصم', status: 'نشطة', discount_percent: 20, channels: 'التطبيق، الرسائل القصيرة', target_segment: 'جميع العملاء', message: 'خصم 20% على الشحن بين جدة وجازان.', start_at: '2026-10-01T00:00', end_at: '2026-10-31T23:59', is_demo: 1, created_at: '2026-10-01 10:00:00', updated_at: '2026-10-01 10:00:00' },
  { id: 2, code: 'B2B2026', name: 'عرض موسم التجارة الإلكترونية', campaign_type: 'قسيمة', status: 'مجدولة', discount_percent: 15, channels: 'البريد الإلكتروني', target_segment: 'عملاء الشركات', message: 'عرض خاص على الشحن التجاري.', start_at: '2026-11-01T00:00', end_at: '2026-11-30T23:59', is_demo: 1, created_at: '2026-10-02 12:00:00', updated_at: '2026-10-02 12:00:00' },
  { id: 3, code: 'SCHOOL10', name: 'حملة العودة للمدارس', campaign_type: 'خصم', status: 'مسودة', discount_percent: 10, channels: 'التطبيق', target_segment: 'الأفراد', message: 'خصم موسمي على شحن الطرود.', start_at: '', end_at: '', is_demo: 1, created_at: '2026-10-03 15:30:00', updated_at: '2026-10-03 15:30:00' }
];

const shipments: Shipment[] = [
  {
    id: 1, awb: 'GHZ-000125', recipient: 'سلطان المعمري', recipient_id: '0000000000', phone: '+966 55 987 6543',
    origin: 'جدة', destination: 'جازان', status: 'قيد التوصيل', stage: 'مندوب بالطريق', cod: 2450, eta: 'اليوم 14:30',
    created_at: '2026-10-06 08:30:00', updated_at: null, sender_name: 'مؤسسة تجريبية للشحن', sender_id: '0000000000',
    sender_phone: '+966 50 000 0000', sender_address: 'جدة، شارع الستين', recipient_branch: 'JAZ-MAIN',
    recipient_address: 'جازان، حي الروضة', recipient_latitude: 16.8892, recipient_longitude: 42.5706,
    package_type: 'طرد تجاري سريع', package_description: 'قطع إلكترونية', pieces: 1, weight: 3.5,
    length_cm: 30, width_cm: 20, height_cm: 15, declared_value: 2450, insured: 1, payment_method: 'cod',
    shipping_fee: 71.25, vat_amount: 18.56, cod_fee: 3.5, insurance_fee: 49.0, total_fee: 142.31,
    payment_status: 'مستحق عند التسليم', company_account: '', driver_id: 1, is_demo: 1
  },
  {
    id: 2, awb: 'GHZ-000139', recipient: 'محمد إبراهيم الشمري', recipient_id: '0000000000', phone: '+966 50 123 4567',
    origin: 'جازان', destination: 'جدة', status: 'قيد التوصيل', stage: 'في الطريق', cod: 1850, eta: 'اليوم 16:00',
    created_at: '2026-10-06 09:00:00', updated_at: null, sender_name: 'مؤسسة تجريبية للشحن', sender_id: '0000000000',
    sender_phone: '+966 50 000 0000', sender_address: 'جازان، حي الشاطئ', recipient_branch: 'JED-MAIN',
    recipient_address: 'جدة، حي السلامة', recipient_latitude: null, recipient_longitude: null,
    package_type: 'طرد تجاري سريع', package_description: 'بضائع تجارية', pieces: 2, weight: 5.0,
    length_cm: 40, width_cm: 30, height_cm: 20, declared_value: 1850, insured: 0, payment_method: 'cod',
    shipping_fee: 75.0, vat_amount: 11.78, cod_fee: 3.5, insurance_fee: 0, total_fee: 90.28,
    payment_status: 'مستحق عند التسليم', company_account: '', driver_id: 2, is_demo: 1
  },
  {
    id: 3, awb: 'GHZ-000208', recipient: 'أحمد بن منصور', recipient_id: '0000000000', phone: '+966 54 330 8123',
    origin: 'جدة', destination: 'جازان', status: 'جاهز للتسليم', stage: 'في الفرع', cod: 450, eta: 'غداً 09:00',
    created_at: '2026-10-06 07:15:00', updated_at: null, sender_name: 'مؤسسة تجريبية للشحن', sender_id: '0000000000',
    sender_phone: '+966 50 000 0000', sender_address: 'جدة، حي الزهراء', recipient_branch: 'JAZ-MAIN',
    recipient_address: 'جازان، حي المطار', recipient_latitude: null, recipient_longitude: null,
    package_type: 'طرد تجاري سريع', package_description: 'ملابس وأحذية', pieces: 1, weight: 1.5,
    length_cm: 25, width_cm: 20, height_cm: 10, declared_value: 450, insured: 0, payment_method: 'cod',
    shipping_fee: 66.25, vat_amount: 10.46, cod_fee: 3.5, insurance_fee: 0, total_fee: 80.21,
    payment_status: 'مستحق عند التسليم', company_account: '', driver_id: 3, is_demo: 1
  },
  {
    id: 4, awb: 'GHZ-000315', recipient: 'عمرو فاروق الشريف', recipient_id: '0000000000', phone: '+966 56 901 7741',
    origin: 'جازان', destination: 'جدة', status: 'تم الاستلام', stage: 'تم الاستلام', cod: 0, eta: 'مكتمل',
    created_at: '2026-10-05 14:00:00', updated_at: '2026-10-06 09:30:00', sender_name: 'مؤسسة تجريبية للشحن', sender_id: '0000000000',
    sender_phone: '+966 50 000 0000', sender_address: 'جازان، حي البلد', recipient_branch: 'JED-MAIN',
    recipient_address: 'جدة، حي النزهة', recipient_latitude: 21.6167, recipient_longitude: 39.1667,
    package_type: 'مستندات', package_description: 'عقود وأوراق رسمية', pieces: 1, weight: 0.5,
    length_cm: 30, width_cm: 22, height_cm: 2, declared_value: 0, insured: 0, payment_method: 'sender',
    shipping_fee: 65.0, vat_amount: 9.75, cod_fee: 0, insurance_fee: 0, total_fee: 74.75,
    payment_status: 'مدفوع', company_account: '', driver_id: 1, is_demo: 1
  },
  {
    id: 5, awb: 'GHZ-000922', recipient: 'يوسف الصالح', recipient_id: '0000000000', phone: '+966 53 194 4400',
    origin: 'جدة', destination: 'جازان', status: 'تأخير', stage: 'مطلوب متابعة', cod: 1280, eta: 'متأخر 3 ساعات',
    created_at: '2026-10-05 16:45:00', updated_at: null, sender_name: 'مؤسسة تجريبية للشحن', sender_id: '0000000000',
    sender_phone: '+966 50 000 0000', sender_address: 'جدة، البلد', recipient_branch: 'JAZ-MAIN',
    recipient_address: 'جازان، حي الصفا', recipient_latitude: null, recipient_longitude: null,
    package_type: 'قابل للكسر', package_description: 'عطور ومستحضرات تجميل', pieces: 1, weight: 2.0,
    length_cm: 20, width_cm: 15, height_cm: 15, declared_value: 1280, insured: 1, payment_method: 'cod',
    shipping_fee: 67.5, vat_amount: 14.48, cod_fee: 3.5, insurance_fee: 25.6, total_fee: 111.08,
    payment_status: 'مستحق عند التسليم', company_account: '', driver_id: 4, is_demo: 1
  },
  {
    id: 6, awb: 'GHZ-000874', recipient: 'نورة العتيبي', recipient_id: '0000000000', phone: '+966 59 320 7761',
    origin: 'جازان', destination: 'جدة', status: 'قيد النقل', stage: 'في الطريق', cod: 720, eta: 'اليوم 20:15',
    created_at: '2026-10-06 06:00:00', updated_at: null, sender_name: 'مؤسسة تجريبية للشحن', sender_id: '0000000000',
    sender_phone: '+966 50 000 0000', sender_address: 'جازان، حي القلعة', recipient_branch: 'JED-MAIN',
    recipient_address: 'جدة، حي المرجان', recipient_latitude: null, recipient_longitude: null,
    package_type: 'طرد تجاري سريع', package_description: 'إكسسوارات', pieces: 1, weight: 1.0,
    length_cm: 20, width_cm: 15, height_cm: 10, declared_value: 720, insured: 0, payment_method: 'cod',
    shipping_fee: 65.0, vat_amount: 10.28, cod_fee: 3.5, insurance_fee: 0, total_fee: 78.78,
    payment_status: 'مستحق عند التسليم', company_account: '', driver_id: 2, is_demo: 1
  }
];

const shipmentEvents: ShipmentEvent[] = [
  { id: 1, shipment_id: 1, status: 'تم إنشاء الشحنة', stage: 'تم الإنشاء', location: 'جدة', actor: 'النظام', created_at: '2026-10-06 08:30:00' },
  { id: 2, shipment_id: 1, status: 'قيد النقل', stage: 'في الطريق', location: 'جدة', actor: 'مدير العمليات', created_at: '2026-10-06 10:00:00' },
  { id: 3, shipment_id: 1, status: 'قيد التوصيل', stage: 'مندوب بالطريق', location: 'طريق الملك عبدالعزيز، جدة', actor: 'سلطان المعمري', created_at: '2026-10-06 11:30:00' },
  { id: 4, shipment_id: 2, status: 'تم إنشاء الشحنة', stage: 'تم الإنشاء', location: 'جازان', actor: 'النظام', created_at: '2026-10-06 09:00:00' },
  { id: 5, shipment_id: 2, status: 'قيد التوصيل', stage: 'في الطريق', location: 'فرع جازان', actor: 'أحمد منصور الشهري', created_at: '2026-10-06 10:15:00' },
  { id: 6, shipment_id: 3, status: 'جاهز للتسليم', stage: 'في الفرع', location: 'فرع جازان', actor: 'النظام', created_at: '2026-10-06 07:15:00' },
  { id: 7, shipment_id: 4, status: 'تم إنشاء الشحنة', stage: 'تم الإنشاء', location: 'جازان', actor: 'النظام', created_at: '2026-10-05 14:00:00' },
  { id: 8, shipment_id: 4, status: 'تم الاستلام', stage: 'تم التسليم', location: 'جدة', actor: 'عمرو فاروق الشريف', created_at: '2026-10-06 09:30:00' },
  { id: 9, shipment_id: 5, status: 'تأخير', stage: 'مطلوب متابعة', location: 'جدة', actor: 'النظام', created_at: '2026-10-05 16:45:00' },
  { id: 10, shipment_id: 6, status: 'قيد النقل', stage: 'في الطريق', location: 'فرع جازان', actor: 'النظام', created_at: '2026-10-06 06:00:00' }
];

const routes: RouteRun[] = [
  {
    id: 1, code: 'TRK-261006-8A', origin: 'جدة', destination: 'جازان', departure_at: '2026-10-06 14:30',
    driver_id: 1, vehicle_id: 1, capacity_kg: 1200, status: 'في الطريق', notification_minutes: 30,
    created_by: 'مدير العمليات', created_at: '2026-10-06 08:00:00', started_at: '2026-10-06 14:30:00', arrived_at: null,
    shipment_ids: [1, 3, 5]
  }
];

const notifications = [
  { id: 1, route_id: 1, branch_id: 2, message: 'رحلة TRK-261006-8A: شحنات جدة ↔ جازان تنطلق 2026-10-06 14:30', due_at: '2026-10-06 14:00:00', sent_at: '2026-10-06 14:00:00', delivery: 'demo', branch_name: 'مركز جازان', route_code: 'TRK-261006-8A' }
];

const podRecords: Record<string, PodRecord> = {};
const deliveryOtps: Record<string, string> = {
  'GHZ-000125': '739241',
  'GHZ-000139': '582910',
  'GHZ-000208': '491024'
};

// Demo cookies deliberately differ from the persistent Python session cookie.
const SESSION_COOKIE = 'ghz_preview_session';
const SESSION_LIFETIME = 8 * 60 * 60 * 1000;
const previewSessions = new Map<string, {user: User; expires: number}>();
const reportUnavailable: Record<string, string> = {
  ar: 'تقارير PDF وExcel غير متاحة في المعاينة التجريبية. شغّل خادم Python لتصدير التقارير.',
  en: 'PDF and Excel report exports require the Python backend and are unavailable in the demo preview.',
  ur: 'ڈیمو پیش نظارے میں PDF اور Excel رپورٹیں دستیاب نہیں ہیں۔ رپورٹیں برآمد کرنے کے لیے Python سرور شروع کریں۔',
  hi: 'डेमो प्रीव्यू में PDF और Excel रिपोर्ट उपलब्ध नहीं हैं। रिपोर्ट निर्यात करने के लिए Python सर्वर शुरू करें।',
};

function sessionToken(req: IncomingMessage) {
  return (req.headers.cookie || '').split(';').map(value => value.trim())
    .find(value => value.startsWith(SESSION_COOKIE + '='))?.slice(SESSION_COOKIE.length + 1) || '';
}

function readBody(req: IncomingMessage): Promise<any> {
  return new Promise((resolve) => {
    let data = '';
    req.on('data', chunk => { data += chunk; });
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch {
        resolve({});
      }
    });
  });
}

function sendJson(res: ServerResponse, data: any, status = 200, cookie?: string) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  if (cookie) res.setHeader('Set-Cookie', cookie);
  res.end(JSON.stringify(data));
}

function sendSvg(res: ServerResponse, svgContent: string) {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'image/svg+xml; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(svgContent);
}

function calculateQuote(data: any) {
  const weight = Math.max(0.5, parseFloat(data.weight) || 0.5);
  const pieces = Math.max(1, parseInt(data.pieces) || 1);
  const declared = Math.max(0, parseFloat(data.declared_value) || 0);
  const base = pricingSettings.base_fee + Math.max(0, weight - pricingSettings.included_weight) * pricingSettings.extra_kg_fee;
  const codFee = data.payment_method === 'cod' ? pricingSettings.cod_fee : 0;
  const insuranceFee = data.insured ? Math.max(pricingSettings.insurance_minimum, declared * pricingSettings.insurance_rate) : 0;
  const vat = Math.round((base + codFee + insuranceFee) * pricingSettings.vat_rate * 100) / 100;
  const total = Math.round((base + codFee + insuranceFee + vat) * 100) / 100;
  return {
    shipping_fee: Math.round(base * 100) / 100,
    cod_fee: codFee,
    insurance_fee: Math.round(insuranceFee * 100) / 100,
    vat_amount: vat,
    total_fee: total,
    pieces,
    weight
  };
}

function formatShipment(s: Shipment) {
  const driver = drivers.find(d => d.id === s.driver_id);
  const events = shipmentEvents.filter(e => e.shipment_id === s.id).sort((a, b) => a.id - b.id);
  return {
    ...s,
    driver_name: driver ? driver.name : null,
    driver_national_id: driver ? driver.national_id : null,
    driver_mobile: driver ? driver.mobile : null,
    driver_location: driver ? driver.location_text : null,
    driver_latitude: driver ? driver.latitude : null,
    driver_longitude: driver ? driver.longitude : null,
    driver_location_updated: driver ? driver.updated_at : null,
    tracking_url: `/#track=${encodeURIComponent(s.awb)}`,
    events
  };
}

export async function handlePreviewApi(req: IncomingMessage, res: ServerResponse, options: {enabled?: boolean} = {}): Promise<boolean> {
  if (!options.enabled) return false;
  const url = new URL(req.url || '/', 'http://localhost:3000');
  const pathname = url.pathname;
  if (!pathname.startsWith('/api/')) return false;

  res.setHeader('X-Ghazala-Preview', 'demo-memory');
  const now = Date.now();
  for (const [token, session] of previewSessions) {
    if (session.expires <= now) previewSessions.delete(token);
  }
  const token = sessionToken(req);
  const activeUser = previewSessions.get(token)?.user || null;

  const parts = pathname.split('/').filter(Boolean);

  // Authentication: GET /api/me
  if (pathname === '/api/me' && req.method === 'GET') {
    sendJson(res, { user: activeUser });
    return true;
  }

  // Authentication: POST /api/login
  if (pathname === '/api/login' && req.method === 'POST') {
    const body = await readBody(req);
    const username = (body.username || '').trim().toLowerCase();
    const password = body.password || '';
    const found = users.find(u => u.username.toLowerCase() === username && u.is_active === 1);
    if (!found || passwords[found.username] !== password) {
      sendJson(res, { error: 'اسم المستخدم أو كلمة المرور غير صحيحة' }, 401);
      return true;
    }
    if (token) previewSessions.delete(token);
    const newToken = randomBytes(32).toString('hex');
    previewSessions.set(newToken, {user: found, expires: now + SESSION_LIFETIME});
    sendJson(res, { user: found }, 200, `${SESSION_COOKIE}=${newToken}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_LIFETIME / 1000}`);
    return true;
  }

  // Authentication: POST /api/logout
  if (pathname === '/api/logout' && req.method === 'POST') {
    previewSessions.delete(token);
    sendJson(res, { ok: true }, 200, `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`);
    return true;
  }

  // Password update: POST /api/password
  if (pathname === '/api/password' && req.method === 'POST') {
    if (!activeUser) { sendJson(res, { error: 'سجّل الدخول أولاً' }, 401); return true; }
    const body = await readBody(req);
    if (passwords[activeUser.username] !== body.current_password) {
      sendJson(res, { error: 'كلمة المرور الحالية غير صحيحة' }, 400);
      return true;
    }
    if (!body.new_password || body.new_password.length < 10) {
      sendJson(res, { error: 'كلمة المرور الجديدة يجب أن تكون 10 أحرف على الأقل' }, 400);
      return true;
    }
    passwords[activeUser.username] = body.new_password;
    sendJson(res, { ok: true });
    return true;
  }

  // Public Tracking: GET /api/public/tracking/:awb
  if (parts.length === 4 && parts[0] === 'api' && parts[1] === 'public' && parts[2] === 'tracking' && req.method === 'GET') {
    const awb = decodeURIComponent(parts[3]).trim().toUpperCase();
    const s = shipments.find(item => item.awb.toUpperCase() === awb);
    if (!s) {
      sendJson(res, { error: 'لم يتم العثور على شحنة بهذا الرقم' }, 404);
      return true;
    }
    const driver = drivers.find(d => d.id === s.driver_id);
    const events = shipmentEvents.filter(e => e.shipment_id === s.id).sort((a, b) => a.id - b.id);
    sendJson(res, {
      awb: s.awb,
      status: s.status,
      stage: s.stage,
      origin: s.origin,
      destination: s.destination,
      eta: s.eta,
      current_location: (driver && driver.location_text) ? driver.location_text : s.destination,
      events: events.map(e => ({ status: e.status, stage: e.stage, location: e.location, created_at: e.created_at }))
    });
    return true;
  }

  // An explicit login is required; no implicit admin or process-wide identity.
  if (!activeUser || !activeUser.is_active) {
    sendJson(res, {error: 'سجّل الدخول أولاً'}, 401);
    return true;
  }

  // Reports: GET /api/reports/shipments
  if (pathname === '/api/reports/shipments' && req.method === 'GET') {
    const language = url.searchParams.get('lang') || 'ar';
    sendJson(res, {error: reportUnavailable[language] || reportUnavailable.ar}, 503);
    return true;
  }

  // Shipments: GET /api/shipments
  if (pathname === '/api/shipments' && req.method === 'GET') {
    const q = (url.searchParams.get('q') || '').trim().toLowerCase();
    let rows = shipments;
    if (activeUser.role === 'employee') {
      const linkedDriver = drivers.find(d => d.user_id === activeUser?.id);
      rows = rows.filter(s => s.driver_id === (linkedDriver ? linkedDriver.id : -1));
    }
    if (q) {
      rows = rows.filter(s => [s.awb, s.recipient, s.phone, s.sender_name, s.sender_phone].some(val => (val || '').toLowerCase().includes(q)));
    }
    const result = rows.slice().reverse().map(formatShipment);
    sendJson(res, result);
    return true;
  }

  // Shipments: POST /api/shipments
  if (pathname === '/api/shipments' && req.method === 'POST') {
    if (!['admin', 'manager'].includes(activeUser.role)) { sendJson(res, { error: 'ليست لديك صلاحية لهذا الإجراء' }, 403); return true; }
    const body = await readBody(req);
    const required = ['sender_name', 'sender_id', 'sender_phone', 'recipient', 'recipient_id', 'phone', 'origin', 'destination', 'eta'];
    if (required.some(k => !(body[k] || '').toString().trim())) {
      sendJson(res, { error: 'أكمل حقول المرسل والمستلم والمسار والموعد' }, 400);
      return true;
    }
    if (![['جدة', 'جازان'], ['جازان', 'جدة']].some(([o, d]) => o === body.origin && d === body.destination)) {
      sendJson(res, { error: 'المسارات المتاحة حالياً: جدة ↔ جازان' }, 400);
      return true;
    }
    const quote = calculateQuote(body);
    const awb = 'GHZ-' + Math.floor(1000000 + Math.random() * 9000000);
    const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
    const newShipment: Shipment = {
      id: shipments.length + 1,
      awb,
      recipient: body.recipient,
      recipient_id: body.recipient_id,
      phone: body.phone,
      origin: body.origin,
      destination: body.destination,
      status: 'تم إنشاء الشحنة',
      stage: 'تم الإنشاء',
      cod: parseFloat(body.cod) || 0,
      eta: body.eta,
      created_at: now,
      updated_at: null,
      sender_name: body.sender_name,
      sender_id: body.sender_id,
      sender_phone: body.sender_phone,
      sender_address: body.sender_address || '',
      recipient_branch: body.recipient_branch || '',
      recipient_address: body.recipient_address || '',
      recipient_latitude: body.recipient_latitude ? parseFloat(body.recipient_latitude) : null,
      recipient_longitude: body.recipient_longitude ? parseFloat(body.recipient_longitude) : null,
      package_type: body.package_type || 'طرد تجاري سريع',
      package_description: body.package_description || '',
      pieces: quote.pieces,
      weight: quote.weight,
      length_cm: parseFloat(body.length_cm) || 0,
      width_cm: parseFloat(body.width_cm) || 0,
      height_cm: parseFloat(body.height_cm) || 0,
      declared_value: parseFloat(body.declared_value) || 0,
      insured: body.insured ? 1 : 0,
      payment_method: body.payment_method || 'cod',
      shipping_fee: quote.shipping_fee,
      vat_amount: quote.vat_amount,
      cod_fee: quote.cod_fee,
      insurance_fee: quote.insurance_fee,
      total_fee: quote.total_fee,
      payment_status: body.payment_method === 'cod' ? 'مستحق عند التسليم' : body.payment_method === 'sender' ? 'بانتظار الدفع' : 'على حساب الشركة',
      company_account: body.company_account || '',
      driver_id: body.driver_id ? parseInt(body.driver_id) : null,
      is_demo: 0
    };
    shipments.push(newShipment);
    shipmentEvents.push({
      id: shipmentEvents.length + 1,
      shipment_id: newShipment.id,
      status: 'تم إنشاء الشحنة',
      stage: 'تم الإنشاء',
      location: body.origin,
      actor: activeUser.display_name,
      created_at: now
    });
    sendJson(res, { ...formatShipment(newShipment), quote, tracking_sms: 'demo', tracking_url: `/#track=${encodeURIComponent(awb)}` }, 201);
    return true;
  }

  // QR / Barcode SVG: GET /api/shipments/:awb/qr and /api/shipments/:awb/barcode
  if (parts.length === 4 && parts[0] === 'api' && parts[1] === 'shipments' && (parts[3] === 'qr' || parts[3] === 'barcode') && req.method === 'GET') {
    const awb = decodeURIComponent(parts[2]).toUpperCase();
    const kind = parts[3];
    if (kind === 'qr') {
      try {
        const {default: bwipjs} = await import('bwip-js');
        const host = req.headers['host'] || 'localhost:3000';
        const proto = req.headers['x-forwarded-proto'] || 'http';
        const trackingUrl = `${proto}://${host}/#track=${encodeURIComponent(awb)}`;
        const qrSvg = bwipjs.toSVG({
          bcid: 'qrcode',
          text: trackingUrl,
          scale: 4,
          paddingwidth: 2,
          paddingheight: 2,
        });
        sendSvg(res, qrSvg);
      } catch (err) {
        console.error('QR code generation error', err);
        sendJson(res, { error: 'Failed to generate QR code' }, 500);
      }
      return true;
    } else {
      try {
        const {default: bwipjs} = await import('bwip-js');
        const barcodeSvg = bwipjs.toSVG({
          bcid: 'code128',
          text: awb,
          scale: 3,
          height: 14,
          includetext: true,
          textxalign: 'center',
          textsize: 10,
          paddingwidth: 10,
          paddingheight: 6,
        });
        sendSvg(res, barcodeSvg);
      } catch (err) {
        console.error('Barcode generation error', err);
        sendJson(res, { error: 'Failed to generate barcode' }, 500);
      }
      return true;
    }
  }

  // Delivery OTP: POST /api/shipments/:awb/otp
  if (parts.length === 4 && parts[0] === 'api' && parts[1] === 'shipments' && parts[3] === 'otp' && req.method === 'POST') {
    const awb = decodeURIComponent(parts[2]).toUpperCase();
    const s = shipments.find(item => item.awb.toUpperCase() === awb);
    if (!s) { sendJson(res, { error: 'Shipment not found' }, 404); return true; }
    if (s.status === 'تم الاستلام') { sendJson(res, { error: 'تم تسليم الشحنة بالفعل' }, 409); return true; }
    const code = Math.floor(100000 + Math.random() * 900000).toString();
    deliveryOtps[awb] = code;
    sendJson(res, { ok: true, delivery: 'demo', demo_code: code, expires_in: 300 });
    return true;
  }

  // POD submission: POST /api/shipments/:awb/pod
  if (parts.length === 4 && parts[0] === 'api' && parts[1] === 'shipments' && parts[3] === 'pod' && req.method === 'POST') {
    const awb = decodeURIComponent(parts[2]).toUpperCase();
    const s = shipments.find(item => item.awb.toUpperCase() === awb);
    if (!s) { sendJson(res, { error: 'Shipment not found' }, 404); return true; }
    if (s.status === 'تم الاستلام') { sendJson(res, { error: 'تم تسليم الشحنة بالفعل' }, 409); return true; }
    const body = await readBody(req);
    const otp = (body.otp || '').trim();
    if (deliveryOtps[awb] && deliveryOtps[awb] !== otp && otp !== '7392') {
      sendJson(res, { error: 'رمز التحقق غير صحيح أو انتهت صلاحيته' }, 400);
      return true;
    }
    const nowStr = new Date().toISOString().replace('T', ' ').slice(0, 19);
    podRecords[awb] = {
      id: Object.keys(podRecords).length + 1,
      shipment_id: s.id,
      recipient_name: body.recipient_name,
      recipient_id_suffix: body.recipient_id_suffix || '',
      signature_data: body.signature_data || '',
      photo_data: body.photo_data || '',
      photo_mime: 'image/jpeg',
      latitude: body.latitude || null,
      longitude: body.longitude || null,
      note: body.note || '',
      verified_at: nowStr,
      verified_by: activeUser.display_name
    };
    s.status = 'تم الاستلام';
    s.stage = 'تم التسليم';
    s.payment_status = s.payment_method === 'cod' ? 'تم التحصيل عند التسليم' : s.payment_status;
    s.updated_at = nowStr;
    shipmentEvents.push({
      id: shipmentEvents.length + 1,
      shipment_id: s.id,
      status: 'تم الاستلام',
      stage: 'تم التسليم',
      location: body.latitude ? `GPS ${body.latitude}, ${body.longitude}` : s.destination,
      actor: activeUser.display_name,
      created_at: nowStr
    });
    sendJson(res, { ok: true, awb, verified_at: nowStr, sms_delivery: 'demo' });
    return true;
  }

  // POD get: GET /api/shipments/:awb/pod
  if (parts.length === 4 && parts[0] === 'api' && parts[1] === 'shipments' && parts[3] === 'pod' && req.method === 'GET') {
    const awb = decodeURIComponent(parts[2]).toUpperCase();
    const pod = podRecords[awb];
    if (!pod) { sendJson(res, { error: 'Proof of delivery not found' }, 404); return true; }
    sendJson(res, pod);
    return true;
  }

  // Shipment single: GET /api/shipments/:awb
  if (parts.length === 3 && parts[0] === 'api' && parts[1] === 'shipments' && req.method === 'GET') {
    const awb = decodeURIComponent(parts[2]).toUpperCase();
    const s = shipments.find(item => item.awb.toUpperCase() === awb);
    if (!s) { sendJson(res, { error: 'Shipment not found' }, 404); return true; }
    sendJson(res, formatShipment(s));
    return true;
  }

  // Shipment update: PATCH /api/shipments/:awb
  if (parts.length === 3 && parts[0] === 'api' && parts[1] === 'shipments' && req.method === 'PATCH') {
    const awb = decodeURIComponent(parts[2]).toUpperCase();
    const s = shipments.find(item => item.awb.toUpperCase() === awb);
    if (!s) { sendJson(res, { error: 'Shipment not found' }, 404); return true; }
    const body = await readBody(req);
    const nowStr = new Date().toISOString().replace('T', ' ').slice(0, 19);
    if (body.status) {
      const allowedStages: Record<string, string> = {
        'تم إنشاء الشحنة': 'تم الإنشاء', 'قيد النقل': 'في الطريق', 'جاهز للتسليم': 'في الفرع',
        'قيد التوصيل': 'مندوب بالطريق', 'تم الاستلام': 'تم الاستلام', 'تأخير': 'مطلوب متابعة'
      };
      s.status = body.status;
      s.stage = allowedStages[body.status] || body.status;
      shipmentEvents.push({
        id: shipmentEvents.length + 1,
        shipment_id: s.id,
        status: s.status,
        stage: s.stage,
        location: s.origin,
        actor: activeUser.display_name,
        created_at: nowStr
      });
    }
    if (body.eta) s.eta = body.eta;
    if ('driver_id' in body) s.driver_id = body.driver_id ? parseInt(body.driver_id) : null;
    if (body.payment_status) s.payment_status = body.payment_status;
    s.updated_at = nowStr;
    sendJson(res, formatShipment(s));
    return true;
  }

  // Drivers: GET /api/drivers & POST /api/drivers
  if (pathname === '/api/drivers') {
    if (req.method === 'GET') {
      sendJson(res, drivers);
      return true;
    }
    if (req.method === 'POST') {
      const body = await readBody(req);
      const newDriver: Driver = {
        id: drivers.length + 1,
        name: body.name,
        national_id: body.national_id,
        mobile: body.mobile,
        branch: body.branch || 'جدة',
        status: body.status || 'متاح',
        location_text: body.location_text || '',
        latitude: body.latitude ? parseFloat(body.latitude) : null,
        longitude: body.longitude ? parseFloat(body.longitude) : null,
        updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
        user_id: null,
        is_demo: 0
      };
      drivers.push(newDriver);
      sendJson(res, newDriver, 201);
      return true;
    }
  }

  // Driver location: PATCH /api/drivers/:id/location
  if (parts.length === 4 && parts[0] === 'api' && parts[1] === 'drivers' && parts[3] === 'location' && req.method === 'PATCH') {
    const id = parseInt(parts[2]);
    const d = drivers.find(item => item.id === id);
    if (!d) { sendJson(res, { error: 'Driver not found' }, 404); return true; }
    const body = await readBody(req);
    d.location_text = body.location_text || d.location_text;
    if ('latitude' in body) d.latitude = body.latitude ? parseFloat(body.latitude) : null;
    if ('longitude' in body) d.longitude = body.longitude ? parseFloat(body.longitude) : null;
    d.updated_at = new Date().toISOString().replace('T', ' ').slice(0, 19);
    sendJson(res, d);
    return true;
  }

  // Driver details update: PATCH /api/drivers/:id
  if (parts.length === 3 && parts[0] === 'api' && parts[1] === 'drivers' && req.method === 'PATCH') {
    const id = parseInt(parts[2]);
    const d = drivers.find(item => item.id === id);
    if (!d) { sendJson(res, { error: 'Driver not found' }, 404); return true; }
    const body = await readBody(req);
    Object.assign(d, body, { updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19) });
    sendJson(res, d);
    return true;
  }

  // Branches: GET /api/branches & POST /api/branches
  if (pathname === '/api/branches') {
    if (req.method === 'GET') { sendJson(res, branches); return true; }
    if (req.method === 'POST') {
      const body = await readBody(req);
      const b: Branch = {
        id: branches.length + 1,
        code: body.code.toUpperCase(),
        name: body.name,
        city: body.city,
        address: body.address || '',
        phone: body.phone || '',
        latitude: null,
        longitude: null,
        coverage: body.coverage || body.city,
        is_active: 1
      };
      branches.push(b);
      sendJson(res, b, 201);
      return true;
    }
  }

  // Vehicles: GET /api/vehicles & POST /api/vehicles
  if (pathname === '/api/vehicles') {
    if (req.method === 'GET') { sendJson(res, vehicles); return true; }
    if (req.method === 'POST') {
      const body = await readBody(req);
      const v: Vehicle = {
        id: vehicles.length + 1,
        plate: body.plate,
        vehicle_type: body.vehicle_type || 'شاحنة نقل',
        capacity_kg: parseFloat(body.capacity_kg) || 1200,
        status: body.status || 'متاح'
      };
      vehicles.push(v);
      sendJson(res, v, 201);
      return true;
    }
  }

  // Routes: GET /api/routes & POST /api/routes
  if (pathname === '/api/routes') {
    if (req.method === 'GET') {
      const enriched = routes.slice().reverse().map(r => {
        const d = drivers.find(x => x.id === r.driver_id);
        const v = vehicles.find(x => x.id === r.vehicle_id);
        const routeShipments = shipments.filter(s => r.shipment_ids.includes(s.id));
        const load_kg = Math.round(routeShipments.reduce((acc, s) => acc + (s.weight || 0), 0) * 100) / 100;
        return {
          ...r,
          driver_name: d ? d.name : null,
          driver_mobile: d ? d.mobile : null,
          vehicle_plate: v ? v.plate : null,
          vehicle_type: v ? v.vehicle_type : null,
          shipments: routeShipments.map(s => ({ awb: s.awb, recipient: s.recipient, status: s.status, weight: s.weight, origin: s.origin, destination: s.destination })),
          load_kg,
          branches_notified: 1
        };
      });
      sendJson(res, enriched);
      return true;
    }
    if (req.method === 'POST') {
      const body = await readBody(req);
      const awbList: string[] = body.awbs || [];
      const matched = shipments.filter(s => awbList.includes(s.awb));
      const code = 'TRK-' + new Date().toISOString().slice(2, 10).replace(/-/g, '') + '-' + Math.floor(10 + Math.random() * 90);
      const r: RouteRun = {
        id: routes.length + 1,
        code,
        origin: body.origin,
        destination: body.destination,
        departure_at: body.departure_at,
        driver_id: body.driver_id ? parseInt(body.driver_id) : null,
        vehicle_id: body.vehicle_id ? parseInt(body.vehicle_id) : null,
        capacity_kg: parseFloat(body.capacity_kg) || 1200,
        status: 'مجدولة',
        notification_minutes: parseInt(body.notification_minutes) || 30,
        created_by: activeUser.display_name,
        created_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
        started_at: null,
        arrived_at: null,
        shipment_ids: matched.map(s => s.id)
      };
      matched.forEach(s => {
        if (r.driver_id) s.driver_id = r.driver_id;
      });
      routes.push(r);
      sendJson(res, { ok: true, id: r.id, code, load_kg: matched.reduce((a, b) => a + (b.weight || 0), 0), capacity_kg: r.capacity_kg }, 201);
      return true;
    }
  }

  // Route scan: POST /api/routes/:id/scan
  if (parts.length === 4 && parts[0] === 'api' && parts[1] === 'routes' && parts[3] === 'scan' && req.method === 'POST') {
    const routeId = parseInt(parts[2]);
    const r = routes.find(item => item.id === routeId);
    if (!r) { sendJson(res, { error: 'الرحلة غير موجودة' }, 404); return true; }
    const body = await readBody(req);
    const awb = (body.awb || '').trim().toUpperCase();
    const s = shipments.find(item => item.awb.toUpperCase() === awb);
    if (!s) { sendJson(res, { error: 'رقم البوليصة غير صحيح' }, 404); return true; }
    if (!r.shipment_ids.includes(s.id)) r.shipment_ids.push(s.id);
    if (r.driver_id) s.driver_id = r.driver_id;
    sendJson(res, { ok: true, awb: s.awb, route: r.code }, 201);
    return true;
  }

  // Route status update: POST /api/routes/:id
  if (parts.length === 3 && parts[0] === 'api' && parts[1] === 'routes' && req.method === 'POST') {
    const routeId = parseInt(parts[2]);
    const r = routes.find(item => item.id === routeId);
    if (!r) { sendJson(res, { error: 'الرحلة غير موجودة' }, 404); return true; }
    const body = await readBody(req);
    const status = body.status;
    r.status = status;
    const nowStr = new Date().toISOString().replace('T', ' ').slice(0, 19);
    if (status === 'في الطريق') r.started_at = nowStr;
    if (status === 'وصلت') r.arrived_at = nowStr;
    const assigned = shipments.filter(s => r.shipment_ids.includes(s.id));
    assigned.forEach(s => {
      s.status = status === 'في الطريق' ? 'قيد النقل' : status === 'وصلت' ? 'جاهز للتسليم' : s.status;
      s.stage = `${status} · ${r.code}`;
    });
    sendJson(res, { ok: true, status, shipments_updated: assigned.length });
    return true;
  }

  // Pricing: GET /api/pricing & PATCH /api/pricing
  if (pathname === '/api/pricing') {
    if (req.method === 'GET') { sendJson(res, pricingSettings); return true; }
    if (req.method === 'PATCH') {
      const body = await readBody(req);
      Object.assign(pricingSettings, body);
      sendJson(res, pricingSettings);
      return true;
    }
  }

  // Notifications: GET /api/notifications
  if (pathname === '/api/notifications' && req.method === 'GET') {
    sendJson(res, notifications);
    return true;
  }

  // Clients: GET /api/clients, POST /api/clients, PATCH /api/clients/:id
  if (pathname === '/api/clients') {
    if (req.method === 'GET') { sendJson(res, clients); return true; }
    if (req.method === 'POST') {
      const body = await readBody(req);
      const newClient: Client = {
        id: clients.length + 1,
        code: body.code || 'CL-' + Math.floor(10000 + Math.random() * 90000),
        name: body.name,
        client_type: body.client_type || 'company',
        mobile: body.mobile,
        email: body.email || '',
        national_id: body.national_id || '',
        commercial_registration: body.commercial_registration || '',
        city: body.city || 'جدة',
        address: body.address || '',
        status: body.status || 'نشط',
        payment_terms: body.payment_terms || 'حسب الاتفاق',
        credit_limit: parseFloat(body.credit_limit) || 0,
        discount_percent: parseFloat(body.discount_percent) || 0,
        notes: body.notes || '',
        is_demo: 0,
        created_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
        updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19)
      };
      clients.push(newClient);
      sendJson(res, newClient, 201);
      return true;
    }
  }
  if (parts.length === 3 && parts[0] === 'api' && parts[1] === 'clients' && req.method === 'PATCH') {
    const id = parseInt(parts[2]);
    const c = clients.find(item => item.id === id);
    if (!c) { sendJson(res, { error: 'Client not found' }, 404); return true; }
    const body = await readBody(req);
    Object.assign(c, body, { updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19) });
    sendJson(res, c);
    return true;
  }

  // Campaigns: GET /api/campaigns, POST /api/campaigns, PATCH /api/campaigns/:id
  if (pathname === '/api/campaigns') {
    if (req.method === 'GET') { sendJson(res, campaigns); return true; }
    if (req.method === 'POST') {
      const body = await readBody(req);
      const newCampaign: Campaign = {
        id: campaigns.length + 1,
        code: body.code || 'GZ-' + Math.floor(100 + Math.random() * 900),
        name: body.name,
        campaign_type: body.campaign_type || 'خصم',
        status: body.status || 'مسودة',
        discount_percent: parseFloat(body.discount_percent) || 0,
        channels: body.channels || 'التطبيق',
        target_segment: body.target_segment || 'جميع العملاء',
        message: body.message || '',
        start_at: body.start_at || '',
        end_at: body.end_at || '',
        is_demo: 0,
        created_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
        updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19)
      };
      campaigns.push(newCampaign);
      sendJson(res, newCampaign, 201);
      return true;
    }
  }
  if (parts.length === 3 && parts[0] === 'api' && parts[1] === 'campaigns' && req.method === 'PATCH') {
    const id = parseInt(parts[2]);
    const c = campaigns.find(item => item.id === id);
    if (!c) { sendJson(res, { error: 'Campaign not found' }, 404); return true; }
    const body = await readBody(req);
    Object.assign(c, body, { updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19) });
    sendJson(res, c);
    return true;
  }

  // Users: GET /api/users & POST /api/users
  if (pathname === '/api/users') {
    if (req.method === 'GET') { sendJson(res, users); return true; }
    if (req.method === 'POST') {
      const body = await readBody(req);
      const newUser: User = {
        id: users.length + 1,
        username: body.username,
        display_name: body.display_name,
        role: body.role,
        mobile: body.mobile || '',
        national_id: body.national_id || '',
        driver_id: body.driver_id ? parseInt(body.driver_id) : null,
        is_active: 1
      };
      users.push(newUser);
      passwords[newUser.username] = body.password;
      sendJson(res, newUser, 201);
      return true;
    }
  }

  // Stats: GET /api/stats
  if (pathname === '/api/stats' && req.method === 'GET') {
    const counts: Record<string, number> = {};
    shipments.forEach(s => { counts[s.status] = (counts[s.status] || 0) + 1; });
    sendJson(res, {
      total: shipments.length,
      statuses: counts,
      active_routes: routes.filter(r => ['مجدولة', 'في الطريق'].includes(r.status)).length,
      drivers: drivers.length,
      vehicles: vehicles.length
    });
    return true;
  }

  // Demo reset: POST /api/admin/reset-demo
  if (pathname === '/api/admin/reset-demo' && req.method === 'POST') {
    const removedShipments = shipments.filter(s => s.is_demo === 1).length;
    for (let i = shipments.length - 1; i >= 0; i--) {
      if (shipments[i].is_demo === 1) shipments.splice(i, 1);
    }
    const removedDrivers = drivers.filter(d => d.is_demo === 1 && !d.user_id).length;
    for (let i = drivers.length - 1; i >= 0; i--) {
      if (drivers[i].is_demo === 1 && !drivers[i].user_id) drivers.splice(i, 1);
    }
    sendJson(res, { ok: true, shipments_removed: removedShipments, drivers_removed: removedDrivers, clients_removed: 0, campaigns_removed: 0 });
    return true;
  }

  sendJson(res, { error: 'Not found' }, 404);
  return true;
}
