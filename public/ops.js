/* Connected workflows for shipment creation, dispatch, public tracking and delivery proof. */
(()=>{
  const state={routes:[],branches:[],branchDirectory:[],vehicles:[],fleetSummary:{},clients:[],campaigns:[],users:[],pricing:{},courier:{delivery_tasks:[],pickup_tasks:[],failure_reasons:[]},busy:false,pending:null,last:0,lastError:null,location:null,notifications:[],publicRequestSequence:0,analyticsPeriod:'month',analyticsRange:null,exporting:null,ownerKey:null,ownerRevision:0,transferView:'incoming',transferPending:new Set(),transferCamera:null,notificationTimer:null,lastNotificationSignature:'',lastShipmentSignature:'',lastUnreadCount:null,executivePeriod:'30d',executiveDashboard:null,executiveDashboardPeriod:null,executiveLoading:false,executiveError:null,managementReport:null,managementReportPeriod:null,managementReportLoading:false,managementReportError:null,accessOverview:null,accessOverviewLoading:false,accessOverviewError:null};
  const $=(q,root=document)=>root.querySelector(q), $$=(q,root=document)=>[...root.querySelectorAll(q)];
  const tr=s=>typeof phrase==='function'?phrase(s):s;
  const fmt=n=>Number(n||0).toLocaleString({ar:'ar-SA',en:'en-GB',ur:'ur-PK',hi:'hi-IN',bn:'bn-BD'}[currentLang]||'en-GB',{maximumFractionDigits:2});
  const OPS_UI_OVERRIDES={
    ar:{
      exec:{
        executiveEyebrow:'المملكة العربية السعودية · ذكاء الإدارة التنفيذية',
        reportingEyebrow:'المملكة العربية السعودية · تقارير الإدارة'
      },
      audit:{
        searchEyebrow:'بحث غزالا المركزي',
        securityEyebrow:'الأمن · العمليات'
      },
      campaign:{
        campaignEyebrow:'حملات غزالا'
      }
    },
    ur:{
      exec:{
        dashboard:'ایگزیکٹو مینجمنٹ ڈیش بورڈ',
        dashboardSub:'حقیقی ریکارڈز سے آپریشن، فنانس، برانچ، فلیٹ، کوریئر اور کیمپین کی لائیو کارکردگی۔',
        reports:'مینجمنٹ رپورٹس',
        reportsSub:'فلٹر ہونے والی آپریشنل اور مالی رپورٹنگ، ڈاؤن لوڈ ہونے والی شپمنٹ رپورٹس کے ساتھ۔',
        today:'آج',d7:'7 دن',d30:'30 دن',d90:'90 دن',d365:'365 دن',all:'تمام مدت',
        shipments:'شپمنٹس',delivered:'ڈیلیورڈ',deliveryRate:'ڈیلیوری ریٹ',activeRoutes:'فعال روٹس',
        failedOpen:'اوپن ڈیلیوری ایکسیپشنز',pieces:'پارسلز',weight:'وزن',avgDelivery:'اوسط ڈیلیوری وقت',
        hours:'گھنٹے',finance:'مالی کارکردگی',invoiced:'انوائس شدہ',collected:'وصول شدہ',
        outstanding:'بقایا',collectionRate:'وصولی کی شرح',discounts:'ڈسکاؤنٹس',currency:'SAR',
        trend:'آپریشنل رجحان',created:'بنائی گئی شپمنٹس',status:'شپمنٹ اسٹیٹس تقسیم',
        branches:'برانچ کارکردگی',originated:'روانہ',received:'موصول',branchDelivered:'ڈیلیورڈ',
        branchRate:'ڈیلیوری ریٹ',couriers:'کوریئر کارکردگی',attempts:'کوشش شدہ شپمنٹس',
        success:'کامیاب',failed:'ناکام',successRate:'کامیابی کی شرح',fleet:'فلیٹ',vehicles:'گاڑیاں',
        available:'دستیاب',onRoute:'روٹ پر',maintenance:'مینٹیننس',
        maintenanceDue:'30 دن میں مینٹیننس واجب',docsExpiring:'30 دن میں ختم ہونے والے دستاویزات',
        campaigns:'کیمپین کارکردگی',published:'پبلشڈ',campaignSent:'بھیجے گئے',
        redemptions:'کوپن استعمال',alerts:'مینجمنٹ الرٹس',recent:'حالیہ شپمنٹس',
        refresh:'ریفریش',loading:'ایگزیکٹو ڈیش بورڈ لوڈ ہو رہا ہے…',
        loadingReports:'مینجمنٹ رپورٹس لوڈ ہو رہی ہیں…',shipmentPdf:'شپمنٹ PDF رپورٹ',
        shipmentExcel:'شپمنٹ Excel رپورٹ',paymentMethods:'ادائیگی کے طریقے',noData:'اس مدت کے لیے ڈیٹا موجود نہیں۔',
        period:'مدت',generated:'آخری اپ ڈیٹ',routes:'روٹس',fleetUtilization:'فلیٹ استعمال',
        campaignDelivery:'کیمپین ڈیلیوری کامیابی',outstandingInvoices:'بقایا انوائسز',
        operationalSummary:'آپریشنل خلاصہ',
        executiveEyebrow:'سعودی عرب · ایگزیکٹو انٹیلیجنس',
        reportingEyebrow:'سعودی عرب · مینجمنٹ رپورٹنگ'
      },
      audit:{
        searchTitle:'مرکزی تلاش',searchSub:'شپمنٹس، کلائنٹس، انوائسز، ادائیگیاں، ڈرائیورز، گاڑیاں، روٹس، اسٹاف اور کیمپینز تلاش کریں۔',
        searchPlaceholder:'AWB، کسٹمر، موبائل، انوائس، ادائیگی، ڈرائیور، گاڑی نمبر تلاش کریں…',
        typeAtLeast:'تلاش کے لیے کم از کم 2 حروف لکھیں۔',noResults:'کوئی مماثل نتیجہ نہیں ملا۔',
        results:'نتائج',open:'کھولیں',audit:'آڈٹ لاگ',
        auditSub:'حساس کارروائیوں اور آپریشنل تبدیلیوں کا مرکزی ناقابلِ ترمیم ریکارڈ۔',
        refresh:'ریفریش',total:'کل ایونٹس',last24:'گزشتہ 24 گھنٹے',lastHour:'گزشتہ گھنٹہ',
        topActors:'سب سے فعال صارفین',actor:'صارف',branch:'برانچ',action:'کارروائی',entity:'اینٹیٹی',
        date:'تاریخ',filters:'فلٹرز',from:'سے',to:'تک',allActions:'تمام کارروائیاں',
        allEntities:'تمام اینٹیٹیز',auditSearch:'کارروائی، صارف، برانچ یا اینٹیٹی تلاش کریں…',
        details:'تفصیلات',loadMore:'مزید لوڈ کریں',noAudit:'کوئی مماثل آڈٹ ریکارڈ نہیں۔',
        skipped:'اسکپ کیا گیا',alreadySent:'پہلے بھیجا جا چکا ہے',
        group_shipments:'شپمنٹس',group_clients:'کلائنٹس',group_invoices:'انوائسز',
        group_payments:'ادائیگیاں',group_drivers:'ڈرائیورز',group_vehicles:'گاڑیاں',
        group_routes:'روٹس',group_staff:'اسٹاف',group_campaigns:'کیمپینز',
        searchEyebrow:'غزالا کمانڈ سرچ',securityEyebrow:'سیکیورٹی · آپریشنز'
      },
      campaign:{
        center:'کیمپینز اور آفرز سینٹر',sub:'آفرز، کوپنز، آڈینس، چینلز اور ڈیلیوری نتائج ایک جگہ مینیج کریں۔',
        newCampaign:'نئی کیمپین',total:'کل کیمپینز',published:'پبلشڈ',deliveries:'ڈیلیوریز',
        redemptions:'کوپن استعمال',records:'کیمپین ریکارڈز',noCampaigns:'ابھی کوئی کیمپین نہیں۔',
        manage:'مینیج',edit:'ایڈٹ',publish:'پبلش',unpublish:'ان پبلش',dispatch:'ابھی بھیجیں',
        results:'نتائج',publishedBadge:'پبلشڈ',notPublished:'پبلش نہیں',discount:'ڈسکاؤنٹ',
        channels:'چینلز',audience:'آڈینس',placement:'پلیسمنٹ',branch:'برانچ ٹارگٹ',
        allBranches:'تمام برانچز',coupon:'کوپن کوڈ',redemptionsLimit:'زیادہ سے زیادہ استعمال',
        perCustomer:'فی کسٹمر حد',minOrder:'کم از کم آرڈر',maxDiscount:'زیادہ سے زیادہ ڈسکاؤنٹ',
        unlimited:'لامحدود',autoExpire:'اختتامی تاریخ پر کیمپین خودکار ختم کریں',
        name:'کیمپین نام',type:'کیمپین قسم',status:'اسٹیٹس',code:'کیمپین کوڈ',
        percent:'ڈسکاؤنٹ %',start:'شروع',end:'اختتام',message:'کیمپین پیغام',
        save:'کیمپین محفوظ کریں',saveChanges:'تبدیلیاں محفوظ کریں',cancel:'منسوخ',
        createTitle:'نئی کیمپین بنائیں',editTitle:'کیمپین مینیج کریں',inApp:'اِن ایپ',
        sms:'SMS',whatsapp:'واٹس ایپ',email:'ای میل',website:'پبلک ویب سائٹ',
        customerPortal:'کسٹمر پورٹل',both:'ویب سائٹ + کسٹمر پورٹل',none:'کوئی پبلک پلیسمنٹ نہیں',
        allCustomers:'تمام کسٹمرز',companies:'کمپنی کسٹمرز',individuals:'انفرادی کسٹمرز',
        active:'فعال',scheduled:'شیڈیولڈ',draft:'ڈرافٹ',stopped:'روکی گئی',expired:'ختم شدہ',
        discountType:'ڈسکاؤنٹ',couponType:'کوپن',pushType:'پش نوٹیفکیشن',smsType:'SMS کیمپین',
        publishSuccess:'کیمپین پبلش ہو گئی',unpublishSuccess:'کیمپین ان پبلش ہو گئی',
        saveSuccess:'کیمپین محفوظ ہو گئی',updateSuccess:'کیمپین اپ ڈیٹ ہو گئی',
        dispatchSuccess:'کیمپین ڈسپیچ مکمل',dispatchConfirm:'کیمپین منتخب آڈینس کو ابھی بھیجی جائے گی۔ جاری رکھیں؟',
        publishConfirm:'کیا آپ اس کیمپین کو ابھی پبلش کرنا چاہتے ہیں؟',resultsTitle:'کیمپین نتائج',
        deliveryHistory:'ڈیلیوری ہسٹری',redemptionHistory:'کوپن استعمال ہسٹری',sent:'بھیجا گیا',
        failed:'ناکام',notConfigured:'کنفیگر نہیں',demo:'ڈیمو',customer:'کسٹمر',
        recipient:'وصول کنندہ',provider:'پرووائیڈر',date:'تاریخ',awb:'AWB',amount:'ڈسکاؤنٹ رقم',
        noDeliveries:'ابھی کوئی کیمپین ڈیلیوری نہیں۔',noRedemptions:'ابھی کوئی کوپن استعمال نہیں ہوا۔',
        remaining:'باقی',lastDispatch:'آخری ڈسپیچ',
        liveChannelsNote:'اِن ایپ فوراً کام کرتا ہے۔ SMS کنفیگرڈ پرووائیڈر استعمال کرتا ہے۔ واٹس ایپ اور ای میل حقیقی پرووائیڈر جڑنے تک Not Configured رہیں گے۔',
        campaignEyebrow:'غزالا کیمپینز'
      }
    },
    hi:{
      exec:{
        dashboard:'एग्जीक्यूटिव मैनेजमेंट डैशबोर्ड',
        dashboardSub:'वास्तविक रिकॉर्ड से ऑपरेशन, फाइनेंस, ब्रांच, फ्लीट, कूरियर और कैंपेन का लाइव प्रदर्शन।',
        reports:'मैनेजमेंट रिपोर्ट्स',reportsSub:'डाउनलोड योग्य शिपमेंट रिपोर्ट्स के साथ फ़िल्टर योग्य ऑपरेशनल और वित्तीय विश्लेषण।',
        today:'आज',d7:'7 दिन',d30:'30 दिन',d90:'90 दिन',d365:'365 दिन',all:'पूरी अवधि',
        shipments:'शिपमेंट्स',delivered:'डिलीवर',deliveryRate:'डिलीवरी दर',activeRoutes:'सक्रिय रूट्स',
        failedOpen:'खुले डिलीवरी अपवाद',pieces:'पार्सल',weight:'वज़न',avgDelivery:'औसत डिलीवरी समय',
        hours:'घंटे',finance:'वित्तीय प्रदर्शन',invoiced:'इनवॉइस',collected:'वसूला गया',
        outstanding:'बकाया',collectionRate:'वसूली दर',discounts:'छूट',currency:'SAR',
        trend:'ऑपरेशनल ट्रेंड',created:'बनाए गए शिपमेंट',status:'शिपमेंट स्थिति वितरण',
        branches:'ब्रांच प्रदर्शन',originated:'प्रेषित',received:'प्राप्त',branchDelivered:'डिलीवर',
        branchRate:'डिलीवरी दर',couriers:'कूरियर प्रदर्शन',attempts:'प्रयास किए शिपमेंट',
        success:'सफल',failed:'विफल',successRate:'सफलता दर',fleet:'फ्लीट',vehicles:'वाहन',
        available:'उपलब्ध',onRoute:'रूट पर',maintenance:'मेंटेनेंस',
        maintenanceDue:'30 दिनों में मेंटेनेंस देय',docsExpiring:'30 दिनों में समाप्त होने वाले दस्तावेज़',
        campaigns:'कैंपेन प्रदर्शन',published:'प्रकाशित',campaignSent:'भेजे गए',
        redemptions:'कूपन उपयोग',alerts:'मैनेजमेंट अलर्ट',recent:'हाल के शिपमेंट',
        refresh:'रीफ्रेश',loading:'एग्जीक्यूटिव डैशबोर्ड लोड हो रहा है…',
        loadingReports:'मैनेजमेंट रिपोर्ट्स लोड हो रही हैं…',shipmentPdf:'शिपमेंट PDF रिपोर्ट',
        shipmentExcel:'शिपमेंट Excel रिपोर्ट',paymentMethods:'भुगतान विधियाँ',noData:'इस अवधि के लिए कोई डेटा नहीं।',
        period:'अवधि',generated:'अंतिम अपडेट',routes:'रूट्स',fleetUtilization:'फ्लीट उपयोग',
        campaignDelivery:'कैंपेन डिलीवरी सफलता',outstandingInvoices:'बकाया इनवॉइस',
        operationalSummary:'ऑपरेशनल सारांश',
        executiveEyebrow:'सऊदी अरब · एग्जीक्यूटिव इंटेलिजेंस',
        reportingEyebrow:'सऊदी अरब · मैनेजमेंट रिपोर्टिंग'
      },
      audit:{
        searchTitle:'केंद्रीय खोज',searchSub:'शिपमेंट, क्लाइंट, इनवॉइस, भुगतान, ड्राइवर, वाहन, रूट, स्टाफ और कैंपेन खोजें।',
        searchPlaceholder:'AWB, ग्राहक, मोबाइल, इनवॉइस, भुगतान, ड्राइवर, वाहन प्लेट खोजें…',
        typeAtLeast:'खोजने के लिए कम से कम 2 अक्षर लिखें।',noResults:'कोई मिलान परिणाम नहीं।',
        results:'परिणाम',open:'खोलें',audit:'ऑडिट लॉग',
        auditSub:'संवेदनशील कार्रवाइयों और ऑपरेशनल बदलावों का केंद्रीय अपरिवर्तनीय रिकॉर्ड।',
        refresh:'रीफ्रेश',total:'कुल इवेंट्स',last24:'पिछले 24 घंटे',lastHour:'पिछला घंटा',
        topActors:'सबसे सक्रिय उपयोगकर्ता',actor:'उपयोगकर्ता',branch:'ब्रांच',action:'कार्रवाई',entity:'एंटिटी',
        date:'तारीख',filters:'फ़िल्टर',from:'से',to:'तक',allActions:'सभी कार्रवाइयाँ',
        allEntities:'सभी एंटिटीज',auditSearch:'कार्रवाई, उपयोगकर्ता, ब्रांच या एंटिटी खोजें…',
        details:'विवरण',loadMore:'और लोड करें',noAudit:'कोई मिलान ऑडिट रिकॉर्ड नहीं।',
        skipped:'स्किप किया',alreadySent:'पहले भेजा गया',
        group_shipments:'शिपमेंट्स',group_clients:'क्लाइंट्स',group_invoices:'इनवॉइस',
        group_payments:'भुगतान',group_drivers:'ड्राइवर',group_vehicles:'वाहन',
        group_routes:'रूट्स',group_staff:'स्टाफ',group_campaigns:'कैंपेन',
        searchEyebrow:'ग़ज़ाला कमांड सर्च',securityEyebrow:'सिक्योरिटी · ऑपरेशंस'
      },
      campaign:{
        center:'कैंपेन और ऑफ़र्स सेंटर',sub:'ऑफ़र, कूपन, ऑडियंस, चैनल और डिलीवरी परिणाम एक जगह मैनेज करें।',
        newCampaign:'नया कैंपेन',total:'कुल कैंपेन',published:'प्रकाशित',deliveries:'डिलीवरी',
        redemptions:'कूपन उपयोग',records:'कैंपेन रिकॉर्ड',noCampaigns:'अभी कोई कैंपेन नहीं।',
        manage:'मैनेज',edit:'एडिट',publish:'प्रकाशित करें',unpublish:'अप्रकाशित करें',dispatch:'अभी भेजें',
        results:'परिणाम',publishedBadge:'प्रकाशित',notPublished:'प्रकाशित नहीं',discount:'छूट',
        channels:'चैनल',audience:'ऑडियंस',placement:'प्लेसमेंट',branch:'ब्रांच टार्गेट',
        allBranches:'सभी ब्रांच',coupon:'कूपन कोड',redemptionsLimit:'अधिकतम उपयोग',
        perCustomer:'प्रति ग्राहक सीमा',minOrder:'न्यूनतम ऑर्डर',maxDiscount:'अधिकतम छूट',
        unlimited:'असीमित',autoExpire:'अंतिम तारीख पर कैंपेन स्वतः समाप्त करें',
        name:'कैंपेन नाम',type:'कैंपेन प्रकार',status:'स्थिति',code:'कैंपेन कोड',
        percent:'छूट %',start:'शुरू',end:'समाप्त',message:'कैंपेन संदेश',
        save:'कैंपेन सेव करें',saveChanges:'बदलाव सेव करें',cancel:'रद्द करें',
        createTitle:'नया कैंपेन बनाएं',editTitle:'कैंपेन मैनेज करें',inApp:'इन-ऐप',
        sms:'SMS',whatsapp:'WhatsApp',email:'ईमेल',website:'पब्लिक वेबसाइट',
        customerPortal:'कस्टमर पोर्टल',both:'वेबसाइट + कस्टमर पोर्टल',none:'कोई पब्लिक प्लेसमेंट नहीं',
        allCustomers:'सभी ग्राहक',companies:'कंपनी ग्राहक',individuals:'व्यक्तिगत ग्राहक',
        active:'सक्रिय',scheduled:'शेड्यूल',draft:'ड्राफ्ट',stopped:'रुका हुआ',expired:'समाप्त',
        discountType:'छूट',couponType:'कूपन',pushType:'पुश नोटिफिकेशन',smsType:'SMS कैंपेन',
        publishSuccess:'कैंपेन प्रकाशित हो गया',unpublishSuccess:'कैंपेन अप्रकाशित हो गया',
        saveSuccess:'कैंपेन सेव हो गया',updateSuccess:'कैंपेन अपडेट हो गया',
        dispatchSuccess:'कैंपेन डिस्पैच पूरा',dispatchConfirm:'कैंपेन चयनित ऑडियंस को अभी भेजा जाएगा। जारी रखें?',
        publishConfirm:'क्या आप इस कैंपेन को अभी प्रकाशित करना चाहते हैं?',resultsTitle:'कैंपेन परिणाम',
        deliveryHistory:'डिलीवरी इतिहास',redemptionHistory:'कूपन उपयोग इतिहास',sent:'भेजा गया',
        failed:'विफल',notConfigured:'कॉन्फ़िगर नहीं',demo:'डेमो',customer:'ग्राहक',
        recipient:'प्राप्तकर्ता',provider:'प्रोवाइडर',date:'तारीख',awb:'AWB',amount:'छूट राशि',
        noDeliveries:'अभी कोई कैंपेन डिलीवरी नहीं।',noRedemptions:'अभी कोई कूपन उपयोग नहीं हुआ।',
        remaining:'शेष',lastDispatch:'अंतिम डिस्पैच',
        liveChannelsNote:'इन-ऐप तुरंत काम करता है। SMS कॉन्फ़िगर किए गए प्रोवाइडर का उपयोग करता है। WhatsApp और ईमेल वास्तविक प्रोवाइडर जुड़ने तक Not Configured रहेंगे।',
        campaignEyebrow:'ग़ज़ाला कैंपेन्स'
      }
    }
  };

  function opsLocaleTag(){
    return ({ar:'ar-SA',en:'en-GB',ur:'ur-PK',hi:'hi-IN',bn:'bn-BD'})[currentLang]||'en-GB';
  }
  function opsIsRtl(){
    return ['ar','ur'].includes(currentLang);
  }
  function opsDictText(scope,key,row){
    row=row||{};
    if(row[currentLang])return row[currentLang];
    const extra=OPS_UI_OVERRIDES?.[currentLang]?.[scope]?.[key];
    if(extra)return extra;
    if(currentLang!=='ar'&&row.ar){
      try{
        const translated=opsTr(row.ar);
        if(translated&&translated!==row.ar)return translated;
      }catch(_){}
    }
    return row.en||row.ar||String(key);
  }
  function fixResidualOpsLanguage(root=document){
    if(currentLang==='ar'||!root)return;
    const map=currentLang==='ur'?{...OPS_AR_FALLBACK_EN,...OPS_AR_FALLBACK_UR}:
              currentLang==='hi'?{...OPS_AR_FALLBACK_EN,...OPS_AR_FALLBACK_HI}:OPS_AR_FALLBACK_EN;
    const entries=Object.entries(map).sort((a,b)=>b[0].length-a[0].length);
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    const nodes=[];
    while(walker.nextNode())nodes.push(walker.currentNode);
    nodes.forEach(node=>{
      const parent=node.parentElement;
      if(!parent||parent.closest('input,textarea,select,option,[contenteditable="true"],script,style'))return;
      let text=node.nodeValue||'';
      if(!/[\\u0600-\\u06FF]/.test(text))return;
      entries.forEach(([source,target])=>{if(text.includes(source))text=text.split(source).join(target)});
      node.nodeValue=text;
    });
  }

  function fixStaffLanguageShell(){
    if(!user||accessRole()==='customer')return;
    const customerBar=document.querySelector('#customerLanguageBar');
    if(customerBar)customerBar.hidden=true;
    const select=document.querySelector('#langSelect');
    if(select&&select.value!==currentLang)select.value=currentLang;
    document.documentElement.lang=currentLang;
    document.documentElement.dir=opsIsRtl()?'rtl':'ltr';
  }

  const OPS_AR_FALLBACK_EN={
    'التسعير والعقود':'Pricing & Contracts',
    'التسعير وأحجام الطرود':'Pricing & Parcel Sizes',
    'تعرفة موحدة تربط العميل وإنشاء الشحنة والفاتورة بنفس محرك التسعير':'A unified tariff links customers, shipment creation and invoicing to the same pricing engine.',
    'إضافة حجم':'Add Size',
    'اختر الحجم · احسب السعر · أنشئ الشحنة':'Choose a size · Calculate the rate · Create the shipment',
    'الأحجام والأسعار مستوردة من جدول غزالا وتدار مركزياً من هذه الصفحة.':'Parcel sizes and rates are managed centrally from this page.',
    'حاسبة سعر الشحن':'Shipping Price Calculator',
    'الطول (سم)':'Length (cm)',
    'العرض (سم)':'Width (cm)',
    'الارتفاع (سم)':'Height (cm)',
    'الوزن الإجمالي (كجم)':'Total Weight (kg)',
    'إعداد تعرفة النظام':'System Rate Settings',
    'تعرفة احتياطية بدون أبعاد':'Fallback rate without dimensions',
    'الوزن المشمول (كجم)':'Included Weight (kg)',
    'رسوم كل كجم إضافي':'Fee per Extra kg',
    'ضريبة القيمة المضافة %':'VAT Rate %',
    'رسوم الدفع عند الاستلام':'COD Fee',
    'نسبة التأمين %':'Insurance Rate %',
    'أقل رسوم تأمين':'Minimum Insurance Fee',
    'حفظ تعرفة النظام':'Save System Rates',
    'كتالوج الأحجام والأسعار':'Parcel Size & Rate Catalog',
    'كل بطاقة تمثل حجماً تقريبياً وسعراً أساسياً للشحن.':'Each card represents an approximate parcel size and its base shipping rate.',
    'اختيار يدوي فقط':'Manual Selection Only',
    'اقتراح تلقائي':'Automatic Recommendation',
    'نشط':'Active',
    'غير نشط':'Inactive',
    'تعديل الحجم والسعر':'Edit Size & Rate',
    'إضافة حجم وتعرفة':'Add Size & Rate',
    'تعديل حجم وتعرفة':'Edit Size & Rate',
    'رمز الحجم':'Size Code',
    'الاسم العربي':'Arabic Name',
    'الاسم الإنجليزي':'English Name',
    'أمثلة بالعربية':'Arabic Examples',
    'أمثلة بالإنجليزية':'English Examples',
    'السعر الأساسي':'Base Price',
    'ترتيب العرض':'Display Order',
    'اختيار يدوي':'Manual Selection',
    'حفظ':'Save',
    'إلغاء':'Cancel',
    'تم حفظ حجم وتعرفة الشحن':'Parcel size and shipping rate saved',
    'اختر الحجم أو أدخل الأبعاد ليقترح النظام الحجم المناسب':'Choose a parcel size or enter dimensions and the system will recommend the best fit.',
    'الأبعاد التقريبية':'Approx. Dimensions',
    'مناسب لـ':'Suitable for',
    'السعر الأساسي':'Base Price',
    'رسوم الوزن الإضافية':'Additional Weight Fee',
    'أجور الشحن':'Shipping Fee',
    'ضريبة القيمة المضافة':'VAT',
    'الإجمالي شامل الضريبة':'Total incl. VAT',
    'ر.س':'SAR',
    'الشحنات':'Shipments',
    'تتبع الشحنات':'Tracking',
    'الرحلات بين الفروع':'Inter-Branch Routes',
    'الرحلات':'Routes',
    'السائقون':'Drivers',
    'المناديب':'Couriers',
    'إدارة العملاء والشركات':'Clients & Companies',
    'التسويق والنمو':'Marketing & Growth',
    'التقارير التنفيذية':'Executive Reports',
    'الموارد البشرية':'Human Resources',
    'إدارة الموارد البشرية':'Human Resources Management',
    'إثبات التسليم الذكي (POD)':'Smart Proof of Delivery (POD)',
    'بيانات السائقين وأرقام التواصل والمواقع الحالية':'Driver records, contact details and current locations',
    'ملفات السائقين وأرقام التواصل والحسابات المرتبطة':'Driver profiles, contact numbers and linked accounts',
    'حسابات المستخدمين والصلاحيات':'User Accounts & Permissions',
    'إضافة عميل جديد':'Add New Client',
    'إضافة شركة':'Add Company',
    'عميل جديد':'New Client',
    'اسم العميل':'Client Name',
    'نوع الحساب':'Account Type',
    'شركة':'Company',
    'فرد':'Individual',
    'رقم السجل':'Registration Number',
    'السجل التجاري / الهوية':'Commercial Registration / ID',
    'رقم الجوال':'Mobile Number',
    'البريد الإلكتروني':'Email',
    'المدينة':'City',
    'العنوان':'Address',
    'حد الائتمان':'Credit Limit',
    'شروط الدفع':'Payment Terms',
    'حفظ بيانات العميل':'Save Client',
    'إدارة الفروع والتوزيع':'Branch & Distribution Management',
    'إضافة فرع / منطقة تغطية':'Add Branch / Coverage Area',
    'اسم الفرع':'Branch Name',
    'رمز الفرع':'Branch Code',
    'رقم هاتف الفرع':'Branch Phone Number',
    'مناطق التغطية':'Coverage Areas',
    'حفظ الفرع':'Save Branch',
    'إدارة الأسطول':'Fleet Management',
    'إضافة مركبة':'Add Vehicle',
    'إضافة مركبة إلى الأسطول':'Add Vehicle to Fleet',
    'رقم اللوحة':'Plate Number',
    'نوع المركبة':'Vehicle Type',
    'سعة الحمولة (كجم)':'Load Capacity (kg)',
    'حفظ المركبة':'Save Vehicle',
    'السائق':'Driver',
    'إضافة سائق':'Add Driver',
    'تعديل السائق':'Edit Driver',
    'رقم التواصل غير متوفر':'Contact number unavailable',
    'الموقع الحالي':'Current Location',
    'تحديث الموقع':'Update Location',
    'تحديث موقع السائق':'Update Driver Location',
    'جدولة رحلة':'Schedule Route',
    'جدولة رحلة نقل':'Schedule Transport Route',
    'إنشاء رحلة ومسح طرود Batch':'Create Route & Batch Scan Parcels',
    'تشمل السائق والمركبة والحمولة والتنبيه قبل الانطلاق':'Includes driver, vehicle, load and pre-departure alert.',
    'من مدينة':'From City',
    'إلى مدينة':'To City',
    'موعد الانطلاق':'Departure Time',
    'مركبة النقل':'Transport Vehicle',
    'إنشاء الرحلة وإسناد الشحنات':'Create Route & Assign Shipments',
    'بدء الرحلة':'Start Route',
    'تأكيد الوصول':'Confirm Arrival',
    'إلغاء الرحلة':'Cancel Route',
    'مسح / إضافة بوليصة':'Scan / Add Waybill',
    'طباعة كشف الحمولة':'Print Load Manifest',
    'كشف الحمولة':'Load Manifest',
    'الشحنات غير المحملة':'Shipments Not Loaded',
    'بانتظار تأكيد الفرع المستلم':'Awaiting Receiving Branch Confirmation',
    'تأكيد استلام الشحنة':'Confirm Shipment Receipt',
    'تم تأكيد استلام الفرع':'Branch Receipt Confirmed',
    'التنبيهات التشغيلية':'Operational Alerts',
    'التنبيهات':'Notifications',
    'لا توجد تنبيهات جديدة':'No new notifications',
    'عرض كل التنبيهات':'View All Notifications',
    'إجمالي الشحنات':'Total Shipments',
    'الشحنات النشطة':'Active Shipments',
    'الشحنات الأخيرة':'Recent Shipments',
    'معدل التسليم':'Delivery Rate',
    'حالات متأخرة':'Delayed Cases',
    'حالات تأخير':'Delayed Cases',
    'حالة الشحنة':'Shipment Status',
    'حالة الدفع':'Payment Status',
    'الموقع التشغيلي الحالي':'Current Operational Location',
    'تتبع الشحنة':'Track Shipment',
    'رقم البوليصة':'Waybill Number',
    'بوليصة الشحن':'Shipping Waybill',
    'بيانات الشحنة الجديدة':'New Shipment Details',
    'بيانات المرسل':'Sender Details',
    'بيانات المستلم':'Recipient Details',
    'اسم المرسل':'Sender Name',
    'اسم المستلم':'Recipient Name',
    'جوال المرسل':'Sender Mobile',
    'جوال المستلم':'Recipient Mobile',
    'رقم هوية المرسل':'Sender ID / Iqama',
    'رقم هوية المستلم':'Recipient ID / Iqama',
    'عنوان المرسل':'Pickup Address',
    'عنوان المستلم بالتفصيل':'Delivery Address',
    'نوع الشحنة':'Shipment Type',
    'عدد الطرود':'Pieces',
    'القيمة المعلنة':'Declared Value',
    'وصف محتوى الشحنة':'Shipment Contents Description',
    'تأمين الشحنة على القيمة المعلنة':'Add Shipment Insurance',
    'خيارات الدفع والتحصيل':'Payment & Collection Options',
    'طريقة الدفع':'Payment Method',
    'الدفع عند الاستلام COD':'Cash on Delivery (COD)',
    'يدفع المرسل':'Sender Pays',
    'حساب الشركات المتعاقدة':'Corporate Account',
    'مبلغ التحصيل عند الاستلام':'COD Amount',
    'رقم / اسم حساب الشركة':'Company Account Number / Name',
    'السائق المكلّف':'Assigned Driver',
    'غير معيّن':'Unassigned',
    'حفظ وإصدار البوليصة':'Save & Issue Waybill',
    'تم إنشاء الشحنة':'Shipment created',
    'ليست لديك صلاحية لهذا الإجراء':'You do not have permission for this action',
    'تعذر فتح الإجراء. أعد تحميل الصفحة وحاول مرة أخرى.':'Could not open the action. Reload the page and try again.',
    'تأكيد التسليم بأمان':'Confirm Delivery Securely',
    'الشحنة المطلوب تسليمها':'Shipment for Delivery',
    'اسم المستلم الفعلي':'Actual Recipient Name',
    'آخر 4 أرقام من الهوية':'Last 4 ID Digits',
    'رمز التحقق OTP':'One-Time Verification Code (OTP)',
    'إرسال رمز OTP إلى المستلم':'Send OTP to Recipient',
    'توقيع المستلم':'Recipient Signature',
    'مسح التوقيع':'Clear Signature',
    'صورة الطرد عند باب المستلم':'Photo of Parcel at Recipient’s Door',
    'التقاط أو اختيار صورة':'Take or choose a photo',
    'لم يتم اختيار صورة':'No photo selected',
    'تحديد موقع التسليم عبر GPS':'Save Delivery GPS',
    'ملاحظة التسليم':'Delivery Note',
    'أضف ملاحظة اختيارية':'Add an optional note',
    'تأكيد التسليم وحفظ الإثبات':'Confirm Delivery and Save Proof',
    'سجل المهام والطرود':'Task & Parcel History',
    'تم التسليم':'Delivered',
    'في الطريق':'In Transit',
    'جاهزة للتسليم':'Ready for Delivery',
    'متأخرة':'Delayed',
    'مجدولة':'Scheduled',
    'وصلت':'Arrived',
    'التتبع العام':'Public Tracking',
    'أدخل رقم البوليصة لمعرفة آخر تحديث وموقع الشحنة':'Enter a waybill number to see the latest shipment update and location.',
    'أدخل رقم بوليصة غزالا لمعرفة حالة الشحنة والوقت المتوقع وموقعها التشغيلي.':'Enter a Ghazala waybill number to view status, ETA and operational location.',
    'لم نعثر على الشحنة':'Shipment not found',
    'لم نعثر على شحنة بهذا الرقم. تحقق من رقم البوليصة وحاول مرة أخرى.':'No shipment was found with this waybill. Check the number and try again.',
    'تحديث':'Refresh',
    'إغلاق':'Close',
    'تعديل':'Edit',
    'تعديل البيانات':'Edit Details',
    'عرض الكل ←':'View All →',
    'المملكة العربية السعودية':'Saudi Arabia',
    'المركز الإقليمي · KSA':'Regional Center · KSA',
    'مركز العمليات اللوجستية':'Logistics Operations Center',
    'مركز التنبيهات':'Notification Center',
    'بوابة الأعمال':'Business Portal',
    'غزالا ترانسبورت':'Ghazala Transport',
    'قراءة فقط':'Read Only'
  };

  const OPS_AR_FALLBACK_UR={
    'التسعير والعقود':'پرائسنگ اور کنٹریکٹس',
    'التسعير وأحجام الطرود':'پرائسنگ اور پارسل سائزز',
    'تعرفة موحدة تربط العميل وإنشاء الشحنة والفاتورة بنفس محرك التسعير':'ایک ہی پرائسنگ انجن کسٹمر، شپمنٹ کریئیشن اور انوائسنگ کو جوڑتا ہے۔',
    'إضافة حجم':'سائز شامل کریں',
    'اختر الحجم · احسب السعر · أنشئ الشحنة':'سائز منتخب کریں · قیمت نکالیں · شپمنٹ بنائیں',
    'الأحجام والأسعار مستوردة من جدول غزالا وتدار مركزياً من هذه الصفحة.':'پارسل سائز اور ریٹس اس صفحے سے مرکزی طور پر مینیج ہوتے ہیں۔',
    'حاسبة سعر الشحن':'شپنگ پرائس کیلکولیٹر',
    'الطول (سم)':'لمبائی (cm)','العرض (سم)':'چوڑائی (cm)','الارتفاع (سم)':'اونچائی (cm)',
    'الوزن الإجمالي (كجم)':'کل وزن (kg)','إعداد تعرفة النظام':'سسٹم ریٹ سیٹنگز',
    'تعرفة احتياطية بدون أبعاد':'ڈائمینشنز کے بغیر بیک اپ ریٹ','الوزن المشمول (كجم)':'شامل وزن (kg)',
    'رسوم كل كجم إضافي':'فی اضافی kg فیس','ضريبة القيمة المضافة %':'VAT ریٹ %','رسوم الدفع عند الاستلام':'COD فیس',
    'نسبة التأمين %':'انشورنس ریٹ %','أقل رسوم تأمين':'کم از کم انشورنس فیس','حفظ تعرفة النظام':'سسٹم ریٹس محفوظ کریں',
    'كتالوج الأحجام والأسعار':'پارسل سائز اور ریٹ کیٹلاگ',
    'كل بطاقة تمثل حجماً تقريبياً وسعراً أساسياً للشحن.':'ہر کارڈ ایک تقریبی پارسل سائز اور بنیادی شپنگ ریٹ دکھاتا ہے۔',
    'اختيار يدوي فقط':'صرف مینوئل سلیکشن','اقتراح تلقائي':'خودکار تجویز','نشط':'فعال','غير نشط':'غیر فعال',
    'تعديل الحجم والسعر':'سائز اور ریٹ ایڈٹ کریں','الأبعاد التقريبية':'تقریبی ڈائمینشنز','مناسب لـ':'مناسب برائے',
    'السعر الأساسي':'بنیادی قیمت','رسوم الوزن الإضافية':'اضافی وزن فیس','أجور الشحن':'شپنگ فیس',
    'ضريبة القيمة المضافة':'VAT','الإجمالي شامل الضريبة':'VAT سمیت کل','ر.س':'SAR','قراءة فقط':'صرف پڑھنے کے لیے'
  };

  const OPS_AR_FALLBACK_HI={
    'التسعير والعقود':'प्राइसिंग और कॉन्ट्रैक्ट्स',
    'التسعير وأحجام الطرود':'प्राइसिंग और पार्सल साइज़',
    'تعرفة موحدة تربط العميل وإنشاء الشحنة والفاتورة بنفس محرك التسعير':'एक ही प्राइसिंग इंजन ग्राहक, शिपमेंट निर्माण और इनवॉइसिंग को जोड़ता है।',
    'إضافة حجم':'साइज़ जोड़ें',
    'اختر الحجم · احسب السعر · أنشئ الشحنة':'साइज़ चुनें · कीमत निकालें · शिपमेंट बनाएं',
    'الأحجام والأسعار مستوردة من جدول غزالا وتدار مركزياً من هذه الصفحة.':'पार्सल साइज़ और दरें इस पेज से केंद्रीय रूप से मैनेज होती हैं।',
    'حاسبة سعر الشحن':'शिपिंग प्राइस कैलकुलेटर',
    'الطول (سم)':'लंबाई (cm)','العرض (سم)':'चौड़ाई (cm)','الارتفاع (سم)':'ऊंचाई (cm)',
    'الوزن الإجمالي (كجم)':'कुल वजन (kg)','إعداد تعرفة النظام':'सिस्टम रेट सेटिंग्स',
    'تعرفة احتياطية بدون أبعاد':'आयाम के बिना बैकअप रेट','الوزن المشمول (كجم)':'शामिल वजन (kg)',
    'رسوم كل كجم إضافي':'प्रति अतिरिक्त kg शुल्क','ضريبة القيمة المضافة %':'VAT दर %','رسوم الدفع عند الاستلام':'COD शुल्क',
    'نسبة التأمين %':'बीमा दर %','أقل رسوم تأمين':'न्यूनतम बीमा शुल्क','حفظ تعرفة النظام':'सिस्टम रेट सेव करें',
    'كتالوج الأحجام والأسعار':'पार्सल साइज़ और रेट कैटलॉग',
    'كل بطاقة تمثل حجماً تقريبياً وسعراً أساسياً للشحن.':'हर कार्ड अनुमानित पार्सल साइज़ और बेस शिपिंग रेट दिखाता है।',
    'اختيار يدوي فقط':'केवल मैनुअल चयन','اقتراح تلقائي':'ऑटो सुझाव','نشط':'सक्रिय','غير نشط':'निष्क्रिय',
    'تعديل الحجم والسعر':'साइज़ और रेट एडिट करें','الأبعاد التقريبية':'लगभग आयाम','مناسب لـ':'उपयुक्त',
    'السعر الأساسي':'बेस कीमत','رسوم الوزن الإضافية':'अतिरिक्त वजन शुल्क','أجور الشحن':'शिपिंग शुल्क',
    'ضريبة القيمة المضافة':'VAT','الإجمالي شامل الضريبة':'VAT सहित कुल','ر.س':'SAR','قراءة فقط':'केवल पढ़ने के लिए'
  };

  function installOpsLanguageFallbacks(){
    const packs={en:OPS_AR_FALLBACK_EN,ur:OPS_AR_FALLBACK_UR,hi:OPS_AR_FALLBACK_HI};
    if(!window.LOCALES)return;
    Object.entries(packs).forEach(([lang,phrases])=>{
      const locale=window.LOCALES[lang];
      if(!locale)return;
      locale.phrases=locale.phrases||{};
      Object.entries(phrases).forEach(([source,target])=>{
        // Exact operational phrases should win over partial substring translation.
        locale.phrases[source]=target;
      });
    });
  }
  installOpsLanguageFallbacks();

  const baseOpsTr=typeof tr==='function'?tr:(value=>String(value??''));
  function opsTr(value){
    const source=String(value??'');
    if(currentLang==='ar')return baseOpsTr(source);
    const exact=(currentLang==='ur'?OPS_AR_FALLBACK_UR:currentLang==='hi'?OPS_AR_FALLBACK_HI:OPS_AR_FALLBACK_EN)[source];
    if(exact)return exact;
    const translated=baseOpsTr(source);
    if(!/[\u0600-\u06FF]/.test(translated))return translated;
    return OPS_AR_FALLBACK_EN[source]||translated;
  }

  const PAYMENT_TEXT={
    title:{ar:'تسجيل دفعة على الفاتورة',en:'Record Invoice Payment'},
    invoice:{ar:'الفاتورة',en:'Invoice'},
    shipment:{ar:'الشحنة',en:'Shipment'},
    total:{ar:'إجمالي الفاتورة',en:'Invoice Total'},
    paid:{ar:'المدفوع',en:'Paid'},
    balance:{ar:'المتبقي',en:'Outstanding'},
    status:{ar:'الحالة',en:'Status'},
    amount:{ar:'مبلغ الدفعة',en:'Payment Amount'},
    method:{ar:'طريقة الدفع',en:'Payment Method'},
    reference:{ar:'المرجع',en:'Reference'},
    referencePlaceholder:{ar:'أدخل رقم الإيصال أو مرجع العملية (اختياري)',en:'Enter receipt / transaction reference (optional)',ur:'رسید یا ٹرانزیکشن ریفرنس درج کریں (اختیاری)',hi:'रसीद / ट्रांज़ैक्शन रेफरेंस दर्ज करें (वैकल्पिक)'},
    note:{ar:'ملاحظات',en:'Notes'},
    notePlaceholder:{ar:'أضف ملاحظة محاسبية اختيارية',en:'Add an optional accounting note',ur:'اختیاری اکاؤنٹنگ نوٹ شامل کریں',hi:'वैकल्पिक अकाउंटिंग नोट जोड़ें'},
    customer:{ar:'حساب العميل',en:'Customer Account',ur:'کسٹمر اکاؤنٹ',hi:'ग्राहक खाता'},
    company:{ar:'ملف الشركة',en:'Company Profile',ur:'کمپنی پروفائل',hi:'कंपनी प्रोफ़ाइल'},
    date:{ar:'التاريخ',en:'Date',ur:'تاریخ',hi:'तारीख'},
    cash:{ar:'نقداً',en:'Cash'},
    card:{ar:'بطاقة',en:'Card'},
    bank_transfer:{ar:'تحويل بنكي',en:'Bank Transfer'},
    online:{ar:'دفع إلكتروني',en:'Online'},
    other:{ar:'أخرى',en:'Other'},
    submit:{ar:'تسجيل الدفعة',en:'Record Payment'},
    history:{ar:'سجل المدفوعات',en:'Payment History'},
    noPayments:{ar:'لا توجد مدفوعات مسجلة لهذه الفاتورة',en:'No payments recorded for this invoice.'},
    fullyPaid:{ar:'تم سداد هذه الفاتورة بالكامل',en:'This invoice is fully paid.'},
    paymentNumber:{ar:'رقم الدفعة',en:'Payment Number'},
    recorded:{ar:'تم تسجيل الدفعة',en:'Payment recorded'},
    invoiceMissing:{ar:'لا توجد فاتورة عميل مرتبطة بهذه الشحنة',en:'No customer invoice is linked to this shipment.'},
    loading:{ar:'جارٍ تحميل بيانات الفاتورة…',en:'Loading invoice details…'},
    legacy:{ar:'تحديث حالة دفع الشحنة',en:'Shipment Payment Status'},
    close:{ar:'إغلاق',en:'Close'},
    invalidAmount:{ar:'أدخل مبلغاً صحيحاً لا يتجاوز الرصيد المتبقي',en:'Enter a valid amount that does not exceed the outstanding balance.'},
    partial:{ar:'مدفوعة جزئياً',en:'Partially Paid'},
    issued:{ar:'صادرة',en:'Issued'},
    paidStatus:{ar:'مدفوعة',en:'Paid'},
    void:{ar:'ملغاة',en:'Void'},
    button:{ar:'الدفع / الفاتورة',en:'Payment / Invoice'}
  };
  function pt(key){
    return opsDictText('payment',key,PAYMENT_TEXT[key]);
  }
  function paymentMoney(value,currency='SAR'){
    return `${Number(value||0).toLocaleString(opsLocaleTag(),{minimumFractionDigits:2,maximumFractionDigits:2})} ${currency||'SAR'}`;
  }
  function paymentStatusLabel(status){
    const map={issued:'issued',partially_paid:'partial',paid:'paidStatus',void:'void'};
    return pt(map[status]||status);
  }

  function networkBranches(){
    const rows=state.branchDirectory.length?state.branchDirectory:state.branches;
    return Array.isArray(rows)?rows.filter(branch=>branch&&branch.city&&branch.code):[];
  }
  function cityNames(){
    return [...new Set(networkBranches().map(branch=>String(branch.city||'').trim()).filter(Boolean))]
      .sort((a,b)=>a.localeCompare(b,'ar'));
  }
  const CITY_DISPLAY_NAMES={
    'الرياض':{ar:'الرياض',en:'Riyadh',ur:'ریاض',hi:'रियाद',bn:'রিয়াদ'},
    'Riyadh':{ar:'الرياض',en:'Riyadh',ur:'ریاض',hi:'रियाद',bn:'রিয়াদ'},
    'جدة':{ar:'جدة',en:'Jeddah',ur:'جدہ',hi:'जेद्दा',bn:'জেদ্দা'},
    'Jeddah':{ar:'جدة',en:'Jeddah',ur:'جدہ',hi:'जेद्दा',bn:'জেদ্দা'},
    'جازان':{ar:'جازان',en:'Jazan',ur:'جازان',hi:'जाज़ान',bn:'জাজান'},
    'جيزان':{ar:'جازان',en:'Jazan',ur:'جازان',hi:'जाज़ान',bn:'জাজান'},
    'Jaazan':{ar:'جازان',en:'Jazan',ur:'جازان',hi:'जाज़ान',bn:'জাজান'},
    'Jazan':{ar:'جازان',en:'Jazan',ur:'جازان',hi:'जाज़ान',bn:'জাজান'},
    'Jizan':{ar:'جازان',en:'Jazan',ur:'جازان',hi:'जाज़ान',bn:'জাজান'},
    'مكة':{ar:'مكة',en:'Makkah',ur:'مکہ',hi:'मक्का',bn:'মক্কা'},
    'Makkah':{ar:'مكة',en:'Makkah',ur:'مکہ',hi:'मक्का',bn:'মক্কা'},
    'الطائف':{ar:'الطائف',en:'Taif',ur:'طائف',hi:'ताइफ़',bn:'তায়েফ'},
    'Taif':{ar:'الطائف',en:'Taif',ur:'طائف',hi:'ताइफ़',bn:'তায়েফ'},
    'المدينة':{ar:'المدينة',en:'Madinah',ur:'مدینہ',hi:'मदीना',bn:'মদিনা'},
    'المدينة المنورة':{ar:'المدينة المنورة',en:'Madinah',ur:'مدینہ',hi:'मदीना',bn:'মদিনা'},
    'Madinah':{ar:'المدينة المنورة',en:'Madinah',ur:'مدینہ',hi:'मदीना',bn:'মদিনা'},
    'الدمام':{ar:'الدمام',en:'Dammam',ur:'دمام',hi:'दम्माम',bn:'দাম্মাম'},
    'Dammam':{ar:'الدمام',en:'Dammam',ur:'دمام',hi:'दम्माम',bn:'দাম্মাম'},
    'أبها':{ar:'أبها',en:'Abha',ur:'ابہا',hi:'अबहा',bn:'আভা'},
    'Abha':{ar:'أبها',en:'Abha',ur:'ابہا',hi:'अबहा',bn:'আভা'}
  };
  function opsUiLanguage(){
    // currentLang is the authoritative staff/operations UI language used by opsTr().
    // #langSelect can be stale/hidden after customer/staff portal switches, so it
    // must not override the actual rendered operations language.
    const selected=String(currentLang||document.documentElement.lang||document.querySelector('#langSelect')?.value||'en').trim().toLowerCase();
    return ['ar','en','ur','hi','bn'].includes(selected)?selected:'en';
  }
  function cityAliasKey(value){
    return String(value||'').normalize('NFKC').trim()
      .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\u0640]/g,'')
      .replace(/[\u064b-\u065f\u0670]/g,'')
      .replace(/[إأآٱ]/g,'ا')
      .replace(/ى/g,'ي')
      .replace(/ی/g,'ي')
      .replace(/ک/g,'ك')
      .replace(/ؤ/g,'و')
      .replace(/ئ/g,'ي')
      .replace(/ة/g,'ه')
      .replace(/\s+/g,' ')
      .toLocaleLowerCase('en');
  }
  function cityDisplayRow(city){
    const raw=String(city||'').trim();
    try{
      const shared=window.GhazalaCityI18n?.row?.(raw);
      if(shared)return shared;
    }catch(_){}
    if(CITY_DISPLAY_NAMES[raw])return CITY_DISPLAY_NAMES[raw];
    const key=cityAliasKey(raw);
    const match=Object.keys(CITY_DISPLAY_NAMES).find(name=>cityAliasKey(name)===key);
    return match?CITY_DISPLAY_NAMES[match]:null;
  }
  function cityDisplayName(city){
    const raw=String(city||'').trim().replace(/\bJaazan\b/gi,'Jazan').replace(/\bJizan\b/gi,'Jazan');
    const lang=opsUiLanguage();
    try{
      const shared=window.GhazalaCityI18n?.display?.(raw,lang);
      if(shared&&shared!==raw)return shared;
    }catch(_){}
    const row=cityDisplayRow(raw);
    if(row)return row[lang]||row.en||raw;
    const translated=opsTr(raw);
    return translated&&translated!==raw?translated:raw;
  }
  function cityPlaceDisplay(value){
    const raw=String(value||'').trim().replace(/\bJaazan\b/gi,'Jazan').replace(/\bJizan\b/gi,'Jazan');
    if(!raw)return '';
    const direct=cityDisplayRow(raw);
    if(direct)return cityDisplayName(raw);
    const match=raw.match(/^(.+?)\s+(branch|centre|center|headquarters)$/i);
    if(match){
      const city=cityDisplayName(match[1]);
      const key=match[2].toLowerCase();
      const lang=opsUiLanguage();
      const labels={
        branch:{ar:'فرع',en:'Branch',ur:'برانچ',hi:'शाखा',bn:'শাখা'},
        centre:{ar:'مركز',en:'Centre',ur:'مرکز',hi:'केंद्र',bn:'কেন্দ্র'},
        center:{ar:'مركز',en:'Center',ur:'مرکز',hi:'केंद्र',bn:'কেন্দ্র'},
        headquarters:{ar:'المقر الرئيسي',en:'Headquarters',ur:'ہیڈکوارٹرز',hi:'मुख्यालय',bn:'সদর দপ্তর'}
      };
      const label=(labels[key]||labels.branch)[lang]||(labels[key]||labels.branch).en;
      return lang==='ar'?`${label} ${city}`:`${city} ${label}`;
    }
    return raw.replace(/\bJaazan\b/gi,'Jazan').replace(/\bJizan\b/gi,'Jazan');
  }

  function cityStoredValue(input,cities=cityNames()){
    const typed=String(input||'').trim();
    const lang=opsUiLanguage();
    const locale=lang==='ar'?'ar':'en';
    const folded=cityAliasKey(typed);
    const match=cities.find(city=>cityAliasKey(cityDisplayName(city))===folded||cityAliasKey(city)===folded);
    return match||typed;
  }
  function cityOptionMarkup(selected=''){
    return cityNames().map(city=>`<option value="${safe(city)}" ${city===selected?'selected':''}>${safe(cityDisplayName(city))}</option>`).join('');
  }
  function otherCity(current){
    return cityNames().find(city=>city!==current)||'';
  }
  async function ensureNetworkReady(){
    if(cityNames().length)return true;
    await refreshOps(true);
    return cityNames().length>0;
  }
  async function refreshSharedNetwork(){
    state.last=0;
    await refreshOps(true);
    if(typeof window.loadGhazalaNetwork==='function'){
      try{await window.loadGhazalaNetwork(true)}catch(_){}
    }
  }
  const safe=s=>esc(s??'');
  const DOCUMENT_TEXT={
    documents:{ar:'مستندات الشحنة',en:'Shipment Documents'},
    waybill:{ar:'البوليصة الإلكترونية',en:'Electronic Waybill'},
    waybillNumber:{ar:'رقم البوليصة',en:'Waybill Number'},
    issued:{ar:'تاريخ الإصدار',en:'Issued'},
    archived:{ar:'مؤرشفة',en:'Archived'},
    active:{ar:'نشطة',en:'Active'},
    preview:{ar:'عرض',en:'View'},
    downloadPdf:{ar:'تنزيل PDF',en:'Download PDF'},
    print:{ar:'طباعة / إعادة طباعة',en:'Print / Reprint'},
    archive:{ar:'أرشفة البوليصة',en:'Archive Waybill'},
    restore:{ar:'استعادة البوليصة',en:'Restore Waybill'},
    stickers:{ar:'استكرات الطرود',en:'Parcel Stickers'},
    allStickers:{ar:'جميع الاستكرات',en:'All Stickers'},
    downloadAll:{ar:'تنزيل جميع الاستكرات PDF',en:'Download All Stickers PDF'},
    printAll:{ar:'طباعة جميع الاستكرات',en:'Print All Stickers'},
    parcel:{ar:'الطرد',en:'Parcel'},
    of:{ar:'من',en:'of'},
    downloads:{ar:'مرات التنزيل',en:'Downloads'},
    prints:{ar:'مرات الطباعة',en:'Prints'},
    loading:{ar:'جارٍ تحميل مستندات الشحنة…',en:'Loading shipment documents…'},
    loadError:{ar:'تعذر تحميل مستندات الشحنة',en:'Could not load shipment documents'},
    downloaded:{ar:'تم تنزيل الملف',en:'File downloaded'},
    printOpened:{ar:'تم فتح ملف الطباعة',en:'Print file opened'},
    archiveDone:{ar:'تمت أرشفة البوليصة',en:'Waybill archived'},
    restoreDone:{ar:'تمت استعادة البوليصة',en:'Waybill restored'},
    close:{ar:'إغلاق',en:'Close'},
    issuingOffice:{ar:'المكتب المصدر',en:'Issuing Office'},
    receivingOffice:{ar:'المكتب المستلم',en:'Receiving Office'},
    courier:{ar:'المندوب',en:'Courier'},
    created:{ar:'تاريخ الإنشاء',en:'Created'},
    noStickers:{ar:'لا توجد استكرات لهذه الشحنة',en:'No parcel stickers found'},
    stickerPreview:{ar:'معاينة الاستكر',en:'Sticker Preview'},
    documentCenter:{ar:'مركز مستندات الشحنة',en:'Shipment Document Center'}
  };
  function dt(key){
    return opsDictText('document',key,DOCUMENT_TEXT[key]);
  }
  const baseLanding=window.landingPage,baseRender=window.render,baseHome=window.home,baseAction=window.action;
  function localizeNow(root=document){if(typeof localize==='function')localize(root)}
  function opsOwnerKey(){if(!user)return null;const scoped=user.access_role||Array.isArray(user.permissions)||Array.isArray(user.branches);const scope=scoped?JSON.stringify([user.access_role||null,[...(user.permissions||[])].sort(),(user.branch_ids||user.branches?.map(branch=>branch.id)||[]).map(String).sort(),user.primary_branch_id??null,user.global_scope===true]):'';return `${user.id}:${user.role}`+scope}
  function syncOpsOwner(){
    const ownerKey=opsOwnerKey();
    if(state.ownerKey===ownerKey)return;
    state.ownerKey=ownerKey;state.ownerRevision++;
    for(const key of ['routes','branches','branchDirectory','vehicles','clients','campaigns','users','notifications'])state[key]=[];
    state.pricing={};state.fleetSummary={};state.courier={delivery_tasks:[],pickup_tasks:[],failure_reasons:[]};state.last=0;state.lastError=null;state.location=null;state.documentPreview=null;state.lastNotificationSignature='';state.lastShipmentSignature='';state.lastUnreadCount=null;state.executiveDashboard=null;state.executiveDashboardPeriod=null;state.executiveLoading=false;state.executiveError=null;state.managementReport=null;state.managementReportPeriod=null;state.managementReportLoading=false;state.managementReportError=null;state.accessOverview=null;state.accessOverviewLoading=false;state.accessOverviewError=null;
    state.busy=false;state.pending=null;state.transferView='incoming';state.transferPending=new Set();state.customerAccounts=[];state.customerAccountsLoadedAt=0;
    if(state.transferCamera)stopTransferCamera();
    const modal=$('#modalRoot');if(modal)modal.innerHTML='';
  }
  async function refreshOps(force=false){
    syncOpsOwner();
    if(!user)return;
    if(state.busy)return state.pending;
    if(!force&&Date.now()-state.last<15000)return;
    const ownerKey=state.ownerKey,ownerRevision=state.ownerRevision;
    const current=()=>state.ownerKey===ownerKey&&state.ownerRevision===ownerRevision&&opsOwnerKey()===ownerKey;
    state.busy=true;
    state.pending=(async()=>{try{
      const read=(permission,url,empty=[])=>hasPermission(permission)?api(url):Promise.resolve(empty);
      const opsRole=typeof accessRole==='function'?accessRole():(user?.access_role||user?.role||'');
      const canCourierTasks=['system_admin','branch_manager','office_employee','courier'].includes(opsRole)&&hasPermission('shipments.read');
      const [routes,branches,vehicles,fleetSummary,pricing,notifications,clients,campaigns,users,branchDirectory,courier]=await Promise.all([
        read('routes.read','/api/routes'),read('branches.read','/api/branches'),read('vehicles.read','/api/vehicles'),read('vehicles.read','/api/fleet/summary',{}),read('pricing.read','/api/pricing',{}),(hasPermission('shipments.read')||hasPermission('routes.read'))?api('/api/notifications'):Promise.resolve([]),
        read('clients.read','/api/clients'),read('campaigns.read','/api/campaigns'),read('users.manage','/api/users'),(hasPermission('shipments.create')||hasPermission('routes.manage'))?api('/api/branch-directory'):Promise.resolve([]),
        canCourierTasks?api('/api/courier/tasks?include_completed=1'):Promise.resolve({delivery_tasks:[],pickup_tasks:[],failure_reasons:[]})
      ]);
      if(!current())return;
      state.routes=routes;state.branches=branches;state.branchDirectory=branchDirectory;state.vehicles=vehicles;state.fleetSummary=fleetSummary||{};state.pricing=pricing;state.courier=courier&&typeof courier==='object'?courier:{delivery_tasks:[],pickup_tasks:[],failure_reasons:[]};state.notifications=Array.isArray(notifications)?notifications:[];state.clients=clients;state.campaigns=campaigns;state.users=users;state.last=Date.now();state.lastError=null;updateNoticeBadge();
      if(!$('#modalRoot')?.innerHTML&&['dispatch','pricing','home','clients','campaigns','staff','analytics','proof','drivers'].includes(page)){baseRender();bindOps()}
    }catch(e){if(current())state.lastError=e;}
    finally{if(current()){state.busy=false;state.pending=null}}})();
    return state.pending;
  }
  function pricingRows(activeOnly=true){
    const rows=Array.isArray(state.pricing?.sizes)?state.pricing.sizes:[];
    return rows.filter(row=>!activeOnly||row.is_active!==0);
  }
  function pricingSizeLabel(row){
    if(!row)return '';
    return currentLang==='ar'?(row.label_ar||row.label_en||row.code):(row.label_en||row.code);
  }
  function pricingExamples(row){
    if(!row)return '';
    return currentLang==='ar'?(row.examples_ar||row.examples_en||''):(row.examples_en||row.examples_ar||'');
  }
  function normalizedDims(length,width,height){
    const dims=[Number(length||0),Number(width||0),Number(height||0)];
    if(dims.some(value=>!Number.isFinite(value)||value<0))return null;
    if(dims.some(Boolean)&&!dims.every(value=>value>0))return null;
    return dims.sort((a,b)=>a-b);
  }
  function pricingSizeFits(row,dims){
    if(!row||!dims||!dims.some(Boolean))return true;
    const limits=[Number(row.length_cm||0),Number(row.width_cm||0),Number(row.height_cm||0)].sort((a,b)=>a-b);
    return dims.every((value,index)=>value<=limits[index]+1e-9);
  }
  function recommendPricingSize(length,width,height){
    const dims=normalizedDims(length,width,height);
    if(!dims||!dims.some(Boolean))return null;
    return pricingRows(true)
      .filter(row=>!row.manual_only)
      .sort((a,b)=>Number(a.sort_order||0)-Number(b.sort_order||0))
      .find(row=>pricingSizeFits(row,dims))||null;
  }
  function selectedPricingSize(code){
    const wanted=String(code||'').toUpperCase();
    return pricingRows(false).find(row=>String(row.code||'').toUpperCase()===wanted)||null;
  }
  function baseFeeQuote(weight,pieces,value,insured,method,sizeCode='',length=0,width=0,height=0){
    const p=state.pricing||{}, w=Math.max(.5,Number(weight)||.5),v=Math.max(0,Number(value)||0);
    const dims=normalizedDims(length,width,height);
    let size=selectedPricingSize(sizeCode);
    if(size&&dims&&dims.some(Boolean)&&!pricingSizeFits(size,dims))size=null;
    if(!size)size=recommendPricingSize(length,width,height);
    const sizeFee=size?Number(size.base_fee||0):Number(p.base_fee??65);
    const surcharge=Math.max(0,w-Number(p.included_weight??1))*Number(p.extra_kg_fee??2.5);
    const shipping=sizeFee+surcharge;
    const cod=method==='cod'?Number(p.cod_fee??3.5):0;
    const insurance=insured?Math.max(Number(p.insurance_minimum??5),v*Number(p.insurance_rate??.02)):0;
    const vat=(shipping+cod+insurance)*Number(p.vat_rate??.15);
    return {shipping,sizeFee,surcharge,cod,insurance,vat,total:shipping+cod+insurance+vat,pieces:Math.max(1,Number(pieces)||1),size};
  }
  function quoteMarkup(q){return `<div class="ops-quote"><div><span>${opsTr('الحجم')}</span><b>${q.size?`${safe(q.size.code)} · ${safe(pricingSizeLabel(q.size))}`:'—'}</b></div><div><span>${opsTr('السعر الأساسي')}</span><b>${fmt(q.sizeFee)} ${opsTr('ر.س')}</b></div><div><span>${opsTr('رسوم الوزن الإضافية')}</span><b>${fmt(q.surcharge)} ${opsTr('ر.س')}</b></div><div><span>${opsTr('أجور الشحن')}</span><b>${fmt(q.shipping)} ${opsTr('ر.س')}</b></div><div><span>${opsTr('رسوم الدفع عند الاستلام')}</span><b>${fmt(q.cod)} ${opsTr('ر.س')}</b></div><div><span>${opsTr('التأمين')}</span><b>${fmt(q.insurance)} ${opsTr('ر.س')}</b></div><div><span>${opsTr('ضريبة القيمة المضافة')}</span><b>${fmt(q.vat)} ${opsTr('ر.س')}</b></div><strong><span>${opsTr('الإجمالي شامل الضريبة')}</span><b>${fmt(q.total)} ${opsTr('ر.س')}</b></strong></div>`}
  const OPS_PARCEL_PHOTO="data:image/png;base64,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";
  const OPS_PALLET_PHOTO="data:image/png;base64,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";

  const OPS_PARCEL_OUTLET_PROFILES={
    'XXS':   {rank:1, scale:.50, shape:'cube',   theme:'sky'},
    'XS':    {rank:2, scale:.57, shape:'cube',   theme:'sky'},
    'S':     {rank:3, scale:.65, shape:'wide',   theme:'mint'},
    'S+':    {rank:4, scale:.71, shape:'wide',   theme:'mint'},
    'M':     {rank:5, scale:.77, shape:'cube',   theme:'yellow'},
    'M+':    {rank:6, scale:.82, shape:'cube',   theme:'yellow'},
    'L':     {rank:7, scale:.87, shape:'wide',   theme:'amber'},
    'L+':    {rank:8, scale:.91, shape:'wide',   theme:'amber'},
    'XL':    {rank:9, scale:.95, shape:'wide',   theme:'coral'},
    'XL+':   {rank:10,scale:.98, shape:'wide',   theme:'coral'},
    'XXL':   {rank:11,scale:1.00,shape:'wide',   theme:'rose'},
    'XL++':  {rank:12,scale:1.02,shape:'wide',   theme:'rose'},
    '3XL+':  {rank:13,scale:1.04,shape:'crate',  theme:'violet'},
    '4XL':   {rank:14,scale:1.06,shape:'crate',  theme:'violet'},
    '4XL++': {rank:15,scale:1.08,shape:'crate',  theme:'magenta'},
    'PALLET':{rank:16,scale:1.00,shape:'pallet', theme:'blue'}
  };

  function opsParcelOutletProfile(row){
    const code=String(row?.code||'').trim().toUpperCase();
    const direct=OPS_PARCEL_OUTLET_PROFILES[code];
    if(direct)return {...direct,code};
    const rows=pricingRows(false);
    const index=Math.max(0,rows.findIndex(item=>String(item.code||'').trim().toUpperCase()===code));
    const ratio=rows.length>1?index/(rows.length-1):0;
    return {
      code,
      rank:index+1,
      scale:Number((.55+ratio*.52).toFixed(3)),
      shape:ratio>.72?'crate':ratio>.35?'wide':'cube',
      theme:ratio>.72?'violet':ratio>.45?'amber':'sky'
    };
  }

  function opsPricingSecondaryLabel(row){
    if(!row)return '';
    if(currentLang==='ar')return row.label_en||row.code||'';
    if(currentLang==='en')return '';
    return row.label_en||row.code||'';
  }

  function pricingUi(ar,en){
    if(currentLang==='ar')return ar;
    if(currentLang==='en')return en;
    const map=currentLang==='ur'?OPS_AR_FALLBACK_UR:currentLang==='hi'?OPS_AR_FALLBACK_HI:null;
    if(map?.[ar])return map[ar];
    try{
      const translated=opsTr(ar);
      if(translated&&!/[\u0600-\u06FF]/.test(translated))return translated;
    }catch(_){}
    return en;
  }

  function pricing3DCard(row,selected=''){
    const active=String(row.code)===String(selected);
    const visual=opsParcelOutletProfile(row);
    const isPallet=String(row.code||'').trim().toUpperCase()==='PALLET';
    const imageSrc=isPallet?OPS_PALLET_PHOTO:OPS_PARCEL_PHOTO;
    const secondary=opsPricingSecondaryLabel(row);
    const price=Number(row.base_fee||0).toLocaleString(opsLocaleTag(),{maximumFractionDigits:2});
    const dims=`${fmt(row.length_cm)} × ${fmt(row.width_cm)} × ${fmt(row.height_cm)} cm`;
    const safeCode=safe(row.code);
    const safeLabel=safe(pricingSizeLabel(row));
    const level=Math.max(1,Math.min(5,Math.ceil(visual.rank/3.2)));

    return `<button type="button"
      class="pricing-3d-card customer-pricing-3d-card customer-parcel-size-card parcel-outlet-card management-parcel-outlet-card parcel-size-level-${level} parcel-theme-${visual.theme} parcel-shape-${visual.shape} ${active?'is-selected':''} ${row.is_active===0?'is-disabled':''}"
      data-pricing-size="${safeCode}"
      data-parcel-rank="${visual.rank}"
      data-parcel-shape="${visual.shape}"
      aria-pressed="${active?'true':'false'}"
      style="--parcel-outlet-scale:${visual.scale.toFixed(3)}">

      <span class="parcel-card-main parcel-outlet-main">
        <span class="pricing-3d-scene parcel-box-stage parcel-outlet-stage" aria-hidden="true">
          <span class="parcel-box-floor-shadow"></span>
          <span class="pricing-cube parcel-box-visual parcel-outlet-photo" style="background-image:none">
            <img class="parcel-outlet-image" src="${imageSrc}" alt="" draggable="false" loading="lazy">
            ${isPallet?'':`<span class="parcel-box-code parcel-outlet-code">${safeCode}</span>`}
          </span>
        </span>

        <span class="pricing-card-copy parcel-card-copy parcel-outlet-copy">
          <span class="parcel-size-title parcel-outlet-title">
            <strong>${safeCode}</strong>
            <b>${safeLabel}</b>
          </span>
          ${secondary&&secondary!==pricingSizeLabel(row)?`<span class="parcel-size-secondary">${safe(secondary)}</span>`:''}
          <span class="parcel-dimensions">
            <small>${pricingUi('الأبعاد التقريبية','Approx. Dimensions')}</small>
            <b>${dims}</b>
          </span>
          <span class="parcel-examples">
            <small>${pricingUi('مناسب لـ','Suitable for')}</small>
            <span>${safe(pricingExamples(row))}</span>
          </span>
          ${row.manual_only?`<span class="pricing-manual-tag">${pricingUi('اختيار يدوي','Manual Selection')}</span>`:''}
        </span>
      </span>

      <span class="parcel-card-topline parcel-outlet-footer">
        <span class="parcel-price-tag">SAR ${price}</span>
        <span class="pricing-selected-tick">${active?'✓':''}</span>
      </span>
    </button>`;
  }
  function pricing3DGrid(selected='',activeOnly=true){return pricingRows(activeOnly).map(row=>pricing3DCard(row,selected)).join('')}
  function bindPricing3DCards(root,form,onSelect){
    $$('[data-pricing-size]',root).forEach(card=>card.onclick=()=>{
      const code=card.dataset.pricingSize;
      const hidden=form?.elements?.pricing_size_code;
      if(hidden)hidden.value=code;
      $$('[data-pricing-size]',root).forEach(row=>{const active=row.dataset.pricingSize===code;row.classList.toggle('is-selected',active);row.setAttribute('aria-pressed',active?'true':'false');const tick=$('.pricing-selected-tick',row);if(tick)tick.textContent=active?'✓':''});
      onSelect?.(code);
    });
  }
  function refreshQuote(root=document){
    const f=$('#createForm',root);if(!f)return;
    const q=baseFeeQuote(
      f.elements.weight.value,f.elements.pieces.value,f.elements.declared_value.value,
      f.elements.insured.checked,f.elements.payment_method.value,
      f.elements.pricing_size_code?.value||'',
      f.elements.length_cm.value,f.elements.width_cm.value,f.elements.height_cm.value
    );
    if(f.elements.pricing_size_code&&!f.elements.pricing_size_code.value&&q.size)f.elements.pricing_size_code.value=q.size.code;
    const out=$('#quoteSummary',root);if(out)out.innerHTML=quoteMarkup(q);
    const grid=$('#shipmentPricing3DGrid',root);
    if(grid&&q.size){
      grid.innerHTML=pricing3DGrid(q.size.code,true);
      bindPricing3DCards(grid,f,()=>refreshQuote(root));
    }
  }
  function localDT(offsetHours=1){const d=new Date(Date.now()+offsetHours*3600000);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)}
  function branchOptions(city,selected='') {const wanted=String(selected||'').toUpperCase();const rows=networkBranches().filter(b=>b.city===city);return `<option value="">${opsTr('اختر فرع الوجهة')}</option>`+rows.map(b=>`<option value="${safe(b.code)}" ${String(b.code).toUpperCase()===wanted?'selected':''}>${safe(b.name)} · ${safe(b.coverage||b.city)}</option>`).join('')}
  const CUSTOMER_LINK_TEXT={
    account:{ar:'حساب العميل',en:'Customer Account',ur:'کسٹمر اکاؤنٹ',hi:'Customer Account',bn:'Customer Account'},
    optional:{ar:'اختياري — اربط الشحنة بحساب العميل الصحيح',en:'Optional — link this shipment to the correct customer account',ur:'اختیاری — درست کسٹمر اکاؤنٹ منتخب کریں',hi:'Optional — select the correct customer account',bn:'Optional — select the correct customer account'},
    none:{ar:'بدون حساب عميل',en:'No Customer Account',ur:'کوئی کسٹمر اکاؤنٹ نہیں',hi:'No Customer Account',bn:'No Customer Account'},
    link:{ar:'ربط حساب العميل',en:'Link Customer Account',ur:'کسٹمر اکاؤنٹ لنک کریں',hi:'Link Customer Account',bn:'Link Customer Account'},
    linked:{ar:'حساب العميل مرتبط',en:'Customer Linked',ur:'کسٹمر اکاؤنٹ لنک ہے',hi:'Customer Linked',bn:'Customer Linked'},
    select:{ar:'اختر حساب العميل الصحيح',en:'Select the correct customer account',ur:'درست کسٹمر اکاؤنٹ منتخب کریں',hi:'Select the correct customer account',bn:'Select the correct customer account'},
    save:{ar:'حفظ وربط الحساب',en:'Save & Link Account',ur:'محفوظ کریں اور لنک کریں',hi:'Save & Link Account',bn:'Save & Link Account'},
    noAccounts:{ar:'لا توجد حسابات عملاء نشطة.',en:'No active customer accounts are available.',ur:'کوئی فعال کسٹمر اکاؤنٹ موجود نہیں۔',hi:'No active customer accounts are available.',bn:'No active customer accounts are available.'},
    linkedSuccess:{ar:'تم ربط الشحنة بحساب العميل',en:'Shipment linked to customer account',ur:'شپمنٹ کسٹمر اکاؤنٹ سے لنک ہو گئی',hi:'Shipment linked to customer account',bn:'Shipment linked to customer account'},
    already:{ar:'هذه الشحنة مرتبطة بالفعل بحساب عميل.',en:'This shipment is already linked to a customer account.',ur:'یہ شپمنٹ پہلے ہی کسٹمر اکاؤنٹ سے لنک ہے۔',hi:'This shipment is already linked to a customer account.',bn:'This shipment is already linked to a customer account.'}
  };
  function clt(key){return CUSTOMER_LINK_TEXT[key]?.[currentLang]||CUSTOMER_LINK_TEXT[key]?.en||key}
  async function managementCustomerAccounts(force=false){
    if(!hasPermission('shipments.edit'))return [];
    if(!force&&Array.isArray(state.customerAccounts)&&state.customerAccounts.length&&Date.now()-Number(state.customerAccountsLoadedAt||0)<60000)return state.customerAccounts;
    const rows=await api('/api/customer-accounts');
    state.customerAccounts=Array.isArray(rows)?rows:[];
    state.customerAccountsLoadedAt=Date.now();
    return state.customerAccounts;
  }
  function customerAccountOptionMarkup(rows,selected=''){
    const wanted=String(selected||'');
    return `<option value="">${safe(clt('none'))}</option>`+(rows||[]).map(account=>{
      const label=[account.display_name||account.username,account.mobile,account.username].filter(Boolean).join(' · ');
      return `<option value="${safe(account.id)}" ${String(account.id)===wanted?'selected':''}>${safe(label)}</option>`;
    }).join('');
  }
  async function linkCustomerAccountModal(awb){
    if(!requirePermission('shipments.edit'))return;
    const shipment=(Array.isArray(shipments)?shipments:[]).find(item=>String(item.awb||'').toUpperCase()===String(awb||'').toUpperCase());
    if(!shipment)return toast(opsTr('لم نعثر على الشحنة'));
    if(shipment.customer_user_id)return toast(clt('already'));
    let accounts=[];
    try{accounts=await managementCustomerAccounts(true)}catch(error){return toast(opsTr(error.message||clt('noAccounts')))}
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:680px">
      <div class="modal-head"><div><div class="eyebrow">CUSTOMER OWNERSHIP</div><h2>${safe(clt('link'))}</h2></div><button class="icon-btn" data-close>×</button></div>
      <div class="awb" style="margin-bottom:14px">${safe(shipment.awb)}</div>
      <p class="kpi-note" style="margin:0 0 16px">${safe(clt('select'))}. ${safe(shipment.sender_name||'')} · ${safe(shipment.sender_phone||'')}</p>
      ${accounts.length?`<form id="customerLinkForm" class="form-grid">
        <label class="field span-2"><span>${safe(clt('account'))} *</span><select name="customer_user_id" required>${customerAccountOptionMarkup(accounts)}</select></label>
        <div class="field span-2 ops-form-actions"><button type="button" class="btn light" data-close>${opsTr('إلغاء')}</button><button class="btn primary" type="submit">${safe(clt('save'))}</button></div>
      </form>`:`<div class="card empty">${safe(clt('noAccounts'))}</div>`}
    </section></div>`;
    wireModal();localizeNow(root);
    const form=$('#customerLinkForm',root);if(!form)return;
    form.onsubmit=async event=>{
      event.preventDefault();
      const customerUserId=String(form.elements.customer_user_id.value||'').trim();
      if(!customerUserId)return toast(clt('select'));
      const button=form.querySelector('[type="submit"]');button.disabled=true;
      try{
        await api(`/api/shipments/${encodeURIComponent(shipment.awb)}/customer`,{method:'POST',body:JSON.stringify({customer_user_id:Number(customerUserId)})});
        closeModal();toast(`${clt('linkedSuccess')} · ${shipment.awb}`);state.customerAccountsLoadedAt=0;await load();render();
      }catch(error){toast(opsTr(error.message||'Unable to link customer account.'));button.disabled=false}
    };
  }
  async function createShipmentModal(){
    if(!requirePermission('shipments.create'))return;
    try{if(!await ensureNetworkReady())return toast(opsTr('أضف فرعين نشطين على الأقل قبل إنشاء شحنة'))}
    catch(e){return toast(opsTr('تعذر تحميل المدن والفروع'))}
    const cities=cityNames();
    if(cities.length<2)return toast(opsTr('يجب إضافة مدينتين نشطتين على الأقل قبل إنشاء شحنة'));
    const originDefault=cities[0],destinationDefault=otherCity(originDefault);
    let customerAccounts=[];
    if(hasPermission('shipments.edit')){try{customerAccounts=await managementCustomerAccounts()}catch(_){customerAccounts=[]}}

    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal"><div class="modal-head"><div><div class="eyebrow">${opsTr('إنشاء شحنة')}</div><h2>${opsTr('بيانات الشحنة الجديدة')}</h2></div><button class="icon-btn" data-close>×</button></div>
      <form id="createForm" class="form-grid ops-form">
        <h3 class="field span-2">${opsTr('بيانات المرسل')}</h3>
        <label class="field"><span>${opsTr('اسم المرسل')} *</span><input name="sender_name" required autocomplete="name"></label><label class="field"><span>${opsTr('رقم هوية المرسل')} (${safe(clt('optional'))})</span><input name="sender_id" inputmode="numeric"></label>
        <label class="field"><span>${opsTr('جوال المرسل')} *</span><input name="sender_phone" type="tel" required autocomplete="tel"></label><label class="field span-2"><span>${opsTr('عنوان المرسل')} *</span><textarea name="sender_address" required></textarea></label>
        ${hasPermission('shipments.edit')?`<h3 class="field span-2">${safe(clt('account'))}</h3><label class="field span-2"><span>${safe(clt('optional'))}</span><select name="customer_user_id">${customerAccountOptionMarkup(customerAccounts)}</select></label>`:''}
        <h3 class="field span-2">${opsTr('بيانات المستلم ووجهة الوصول')}</h3>
        <label class="field"><span>${opsTr('اسم المستلم')} *</span><input name="recipient" required></label><label class="field"><span>${opsTr('رقم هوية المستلم')} (${safe(clt('optional'))})</span><input name="recipient_id" inputmode="numeric"></label>
        <label class="field"><span>${opsTr('جوال المستلم')} *</span><input name="phone" type="tel" required></label><label class="field"><span>${opsTr('من مدينة')}</span><select name="origin" required>${cityOptionMarkup(originDefault)}</select></label>
        <label class="field"><span>${opsTr('إلى مدينة')}</span><select name="destination" required>${cityOptionMarkup(destinationDefault)}</select></label><label class="field"><span>${opsTr('فرع الوجهة')}</span><select name="recipient_branch">${branchOptions(destinationDefault)}</select></label>
        <h3 class="field span-2">${opsTr('تفاصيل الطرد والشحنة')}</h3>
        <label class="field"><span>${opsTr('نوع الشحنة')}</span><select name="package_type">${['طرد تجاري سريع','مستندات','قابل للكسر','شحنة كبيرة'].map(type=>`<option value="${safe(type)}">${opsTr(type)}</option>`).join('')}</select></label><label class="field"><span>${opsTr('عدد الطرود')}</span><input name="pieces" type="number" min="1" max="100" value="1" required></label>
        <label class="field"><span>${opsTr('الوزن الإجمالي (كجم)')}</span><input name="weight" type="number" min="0.5" step="0.1" value="1" required></label><label class="field"><span>${opsTr('وقت الوصول المتوقع ETA')} *</span><input name="eta" type="datetime-local" value="${localDT(24)}" required></label>
        <label class="field"><span>${opsTr('الطول (سم)')}</span><input name="length_cm" type="number" min="0" step="0.1" value="0"></label><label class="field"><span>${opsTr('العرض (سم)')}</span><input name="width_cm" type="number" min="0" step="0.1" value="0"></label><label class="field"><span>${opsTr('الارتفاع (سم)')}</span><input name="height_cm" type="number" min="0" step="0.1" value="0"></label><label class="field"><span>${opsTr('القيمة المعلنة')}</span><input name="declared_value" type="number" min="0" step="0.01" value="0"></label>
        <input type="hidden" name="pricing_size_code" value="">
        <section class="field span-2 pricing-3d-panel">
          <div class="pricing-3d-title"><div><small>GHAZALA SMART PRICING</small><h3>${pricingUi('أحجام الطرود','Parcel Sizes')}</h3><p>${opsTr('اختر الحجم أو أدخل الأبعاد ليقترح النظام الحجم المناسب')}</p></div><span class="pricing-orbit">◈</span></div>
          <div class="pricing-3d-grid customer-pricing-3d-grid management-pricing-outlet-grid" id="shipmentPricing3DGrid">${pricing3DGrid('',true)}</div>
        </section>
        <label class="field span-2"><span>${opsTr('وصف محتوى الشحنة')}</span><textarea name="package_description"></textarea></label><label class="field check-field span-2"><input name="insured" type="checkbox"><span>${opsTr('تأمين الشحنة على القيمة المعلنة')}</span></label>
        <h3 class="field span-2">${opsTr('خيارات الدفع والتحصيل')}</h3>
        <label class="field"><span>${opsTr('طريقة الدفع')}</span><select name="payment_method"><option value="cod">${opsTr('الدفع عند الاستلام COD')}</option><option value="sender">${opsTr('يدفع المرسل')}</option><option value="company">${opsTr('حساب الشركات المتعاقدة')}</option></select></label>
        <label class="field" id="codField"><span>${opsTr('مبلغ التحصيل عند الاستلام')} *</span><input name="cod" type="number" min="0.01" step="0.01" value=""></label><label class="field span-2" id="companyField" hidden><span>${opsTr('رقم / اسم حساب الشركة')} *</span><input name="company_account"></label>
        <div class="field span-2" id="quoteSummary">${quoteMarkup(baseFeeQuote(1,1,0,false,'cod'))}</div>
        <label class="field"><span>${opsTr('السائق المكلّف')}</span><select name="driver_id"><option value="">${opsTr('غير معيّن')}</option>${drivers.map(d=>`<option value="${d.id}">${safe(d.name)} · ${safe(d.mobile)}</option>`).join('')}</select></label>
        <div class="field span-2 ops-form-actions"><button class="btn light" type="button" data-close>${opsTr('إلغاء')}</button><button class="btn primary">${opsTr('حفظ وإصدار البوليصة')}</button></div>
      </form></section></div>`;

    wireModal();localizeNow($('#modalRoot'));const f=$('#createForm');
    const pricingGrid=$('#shipmentPricing3DGrid');
    bindPricing3DCards(pricingGrid,f,()=>refreshQuote($('#modalRoot')));
    const syncPricingRecommendation=()=>{
      const selected=selectedPricingSize(f.elements.pricing_size_code.value);
      const dims=normalizedDims(f.elements.length_cm.value,f.elements.width_cm.value,f.elements.height_cm.value);
      if(selected&&pricingSizeFits(selected,dims))return;
      const next=recommendPricingSize(f.elements.length_cm.value,f.elements.width_cm.value,f.elements.height_cm.value);
      f.elements.pricing_size_code.value=next?.code||'';
    };
    ['length_cm','width_cm','height_cm'].forEach(name=>f.elements[name].addEventListener('input',syncPricingRecommendation));
    f.addEventListener('input',()=>refreshQuote($('#modalRoot')));
    const syncPaymentFields=()=>{const cod=f.elements.payment_method.value==='cod',company=f.elements.payment_method.value==='company';$('#codField').hidden=!cod;$('#companyField').hidden=!company;f.elements.cod.required=cod;f.elements.company_account.required=company;refreshQuote($('#modalRoot'))};
    f.elements.payment_method.onchange=syncPaymentFields;syncPaymentFields();

    const syncBranches=()=>{const city=f.elements.destination.value,select=f.elements.recipient_branch;select.innerHTML=branchOptions(city,select.value);localizeNow(select)};
    const keepDifferent=(changed)=>{
      const origin=f.elements.origin,destination=f.elements.destination;
      if(origin.value!==destination.value)return;
      if(changed==='origin')destination.value=otherCity(origin.value);
      else origin.value=otherCity(destination.value);
    };
    f.elements.destination.onchange=()=>{keepDifferent('destination');syncBranches()};
    f.elements.origin.onchange=()=>{keepDifferent('origin');syncBranches()};
    syncBranches();

    const refreshMap=()=>{const lat=Number(f.elements.recipient_latitude.value),lng=Number(f.elements.recipient_longitude.value),preview=$('#shipMapPreview'),link=$('#shipMapLink');if(!Number.isFinite(lat)||!Number.isFinite(lng)||!lat||!lng){preview.hidden=true;link.hidden=true;return}preview.hidden=false;preview.innerHTML=`<span>⌖</span><b>${lat.toFixed(5)}, ${lng.toFixed(5)}</b><small>${opsTr('إحداثيات الموقع محفوظة في سجل الشحنة')}</small>`;link.hidden=false;link.href=`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=16/${lat}/${lng}`};
    f.elements.recipient_latitude.oninput=refreshMap;f.elements.recipient_longitude.oninput=refreshMap;
    $('#shipGps').onclick=()=>gps((lat,lng)=>{f.elements.recipient_latitude.value=lat;f.elements.recipient_longitude.value=lng;refreshMap();toast(opsTr('تم تحديد إحداثيات الموقع'))});

    f.onsubmit=async e=>{
      e.preventDefault();
      if(f.elements.origin.value===f.elements.destination.value)return toast(opsTr('مدينة الإرسال والوصول يجب أن تكون مختلفة'));
      const data=Object.fromEntries(new FormData(f));
      data.driver_id=data.driver_id||null;
      if(Object.prototype.hasOwnProperty.call(data,'customer_user_id')){
        const owner=String(data.customer_user_id||'').trim();
        if(owner)data.customer_user_id=Number(owner);else delete data.customer_user_id;
      }
      data.recipient_branch=String(data.recipient_branch||'').trim().toUpperCase();
      data.insured=f.elements.insured.checked;
      ['pieces','weight','length_cm','width_cm','height_cm','declared_value','recipient_latitude','recipient_longitude','cod'].forEach(k=>{if(data[k]!==''&&data[k]!=null)data[k]=Number(data[k]);else if(k.includes('latitude')||k.includes('longitude'))data[k]=null});
      if(f.elements.payment_method.value==='sender'||f.elements.payment_method.value==='company')data.cod=0;
      try{
        const created=await api('/api/shipments',{method:'POST',body:JSON.stringify(data)});
        closeModal();toast(`${opsTr('تم إنشاء الشحنة')} ${created.awb}`);await load();page='shipments';render();
      }catch(err){toast(opsTr(err.message))}
    };
  }
  function wireModal(){if(typeof window.wireModal==='function')window.wireModal();else $$('[data-close]',$('#modalRoot')).forEach(b=>b.onclick=closeModal)}
  function gps(callback){if(!navigator.geolocation)return toast(opsTr('الموقع غير متاح في هذا المتصفح'));navigator.geolocation.getCurrentPosition(p=>callback(p.coords.latitude.toFixed(6),p.coords.longitude.toFixed(6)),()=>toast(opsTr('تعذر الحصول على GPS. تحقق من HTTPS وصلاحية الموقع.')),{enableHighAccuracy:true,timeout:15000,maximumAge:10000})}
  function notificationUnread(n){
    if(!n)return false;
    if(Object.prototype.hasOwnProperty.call(n,'is_read'))return !(n.is_read===true||n.is_read===1||n.is_read==='1');
    if(Object.prototype.hasOwnProperty.call(n,'read_at'))return !n.read_at;
    return !n.sent_at;
  }
  function notificationAwb(n){
    return String(n?.awb||n?.shipment_awb||n?.shipment?.awb||'').trim().toUpperCase();
  }
  function notificationRoute(n){
    return String(n?.route_code||n?.route?.code||'').trim();
  }
  const NOTIFICATION_UI_TEXT={
    newCustomerBooking:{ar:'حجز عميل جديد',en:'New Customer Booking'},
    shipmentUpdate:{ar:'تحديث شحنة',en:'Shipment Update'},
    routeUpdate:{ar:'تحديث رحلة',en:'Route Update'},
    operationalAlert:{ar:'تنبيه تشغيلي',en:'Operational Alert'},
    customerPortalCreated:{ar:'تم إنشاء شحنة جديدة من بوابة العميل',en:'A new shipment was created from the Customer Portal'},
    routeNeedsAttention:{ar:'يوجد تحديث جديد على الرحلة',en:'There is a new route update'},
    needsAttention:{ar:'يوجد تحديث جديد يحتاج إلى المتابعة',en:'There is a new update that needs attention'},
    new:{ar:'جديد',en:'New'},
    recipient:{ar:'المستلم',en:'Recipient'},
    route:{ar:'المسار',en:'Route'},
    open:{ar:'فتح',en:'Open'},
    unread:{ar:'غير مقروء',en:'Unread'},
    totalNotifications:{ar:'إجمالي التنبيهات',en:'Total Notifications'}
  };
  function nt(key){
    return opsDictText('notification',key,NOTIFICATION_UI_TEXT[key]);
  }
  function notificationIsCustomerBooking(n){
    const kind=String(n?.type||n?.kind||'').trim().toLowerCase().replace(/[\s-]+/g,'_');
    if(kind==='customer_booking')return true;
    const raw=`${n?.title||''} ${n?.message||''}`.toLowerCase();
    return !!notificationAwb(n)&&(raw.includes('customer')||raw.includes('client')||raw.includes('عميل')||raw.includes('بوابة العميل'));
  }
  function notificationShipment(n){
    const awb=notificationAwb(n);
    if(!awb)return null;
    return (Array.isArray(shipments)?shipments:[]).find(item=>String(item?.awb||'').trim().toUpperCase()===awb)||null;
  }
  function notificationTitle(n){
    if(notificationIsCustomerBooking(n))return nt('newCustomerBooking');
    if(notificationRoute(n)&&!n?.title)return nt('routeUpdate');
    if(notificationAwb(n)&&!n?.title)return nt('shipmentUpdate');
    if(n?.title)return String(opsTr(n.title)||n.title);
    return nt('operationalAlert');
  }
  function notificationMessage(n){
    if(notificationIsCustomerBooking(n))return nt('customerPortalCreated');
    if(n?.message)return String(opsTr(n.message)||n.message);
    if(notificationRoute(n))return nt('routeNeedsAttention');
    return nt('needsAttention');
  }
  function notificationTime(n){
    return n?.created_at||n?.due_at||n?.updated_at||'';
  }
  function notificationTimeLabel(n){
    const raw=notificationTime(n);
    if(!raw)return '';
    const date=new Date(raw);
    if(Number.isNaN(date.getTime()))return String(raw);
    try{
      return date.toLocaleString(opsLocaleTag(),{
        day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'
      });
    }catch(_){return String(raw)}
  }
  function notificationContext(n){
    const shipment=notificationShipment(n);
    const recipient=String(shipment?.recipient||n?.recipient||n?.customer_name||'').trim();
    const origin=String(shipment?.origin||n?.origin||'').trim();
    const destination=String(shipment?.destination||n?.destination||'').trim();
    return {
      recipient,
      route:origin&&destination?`${opsTr(origin)} → ${opsTr(destination)}`:'',
      awb:notificationAwb(n),
      routeCode:notificationRoute(n)
    };
  }
  function unreadNotifications(){
    return state.notifications.filter(notificationUnread);
  }
  function notificationSignature(rows=state.notifications){
    return JSON.stringify((rows||[]).map(n=>[
      n.id??null,n.type??n.kind??null,notificationAwb(n),notificationRoute(n),
      n.is_read??null,n.read_at??null,n.sent_at??null,n.created_at??n.due_at??null
    ]));
  }
  function shipmentSignature(rows=shipments){
    return JSON.stringify((rows||[]).map(s=>[
      s.id??null,s.awb,s.status,s.updated_at??s.created_at??null,
      s.customer_user_id??null,s.booking_source??null
    ]));
  }
  function isCustomerBooking(s){
    return !!(s&&(s.booking_source==='customer'||s.source==='customer'||s.customer_user_id||s.customer_account_id));
  }
  function updateNoticeBadge(){
    const notice=$('.notice');
    if(!notice)return;
    const count=unreadNotifications().length;
    let badge=$('em',notice);
    if(!badge){
      badge=document.createElement('em');
      notice.appendChild(badge);
    }
    badge.textContent=count>99?'99+':String(count);
    badge.hidden=count===0;
    notice.title=count?`${opsTr('التنبيهات')} · ${count}`:opsTr('لا توجد تنبيهات جديدة');
    notice.setAttribute('aria-label',notice.title);
  }
  function notificationRow(n){
    const awb=notificationAwb(n),route=notificationRoute(n),unread=notificationUnread(n),context=notificationContext(n);
    const dir=opsIsRtl()?'rtl':'ltr';
    const contextBits=[
      context.recipient?`<span><b>${nt('recipient')}:</b> <span dir="auto">${safe(context.recipient)}</span></span>`:'',
      context.route?`<span><b>${nt('route')}:</b> <span dir="auto">${safe(context.route)}</span></span>`:''
    ].filter(Boolean).join('');
    return `<article class="ops-notification-row ${unread?'is-unread':''}" data-notification-id="${safe(n.id??'')}" dir="${dir}">
      <div class="ops-notification-icon" aria-hidden="true">${awb?'📦':route?'⇄':'🔔'}</div>
      <div class="ops-notification-copy">
        <div class="ops-notification-title">
          <strong dir="auto">${safe(notificationTitle(n))}</strong>
          ${awb?`<span class="ops-notification-awb" dir="ltr">${safe(awb)}</span>`:''}
          ${route?`<span class="ops-notification-route-code" dir="ltr">${safe(route)}</span>`:''}
          ${unread?`<span class="ops-notification-new">${nt('new')}</span>`:''}
        </div>
        <p class="ops-notification-message" dir="auto">${safe(notificationMessage(n))}</p>
        ${contextBits?`<div class="ops-notification-context">${contextBits}</div>`:''}
        <small class="ops-notification-time" dir="auto">${safe(notificationTimeLabel(n))}</small>
      </div>
      ${(awb||route)?`<button type="button" class="btn light small ops-notification-open" data-notification-open data-awb="${safe(awb)}" data-route="${safe(route)}">${nt('open')}</button>`:''}
    </article>`;
  }
  async function markNotificationRead(id){
    if(id==null||id==='')return;
    const item=state.notifications.find(n=>String(n.id)===String(id));
    if(item&&Object.prototype.hasOwnProperty.call(item,'is_read'))item.is_read=true;
    if(item&&Object.prototype.hasOwnProperty.call(item,'read_at'))item.read_at=item.read_at||new Date().toISOString();
    updateNoticeBadge();
    try{
      await api(`/api/notifications/${encodeURIComponent(id)}/read`,{method:'POST',body:'{}'});
    }catch(_){
      // Legacy route notifications do not yet expose a read endpoint.
    }
  }
  function openNotificationTarget(awb,route,id){
    markNotificationRead(id);
    closeModal();
    if(awb){
      query=awb;
      filter='الكل';
      page='shipments';
      render();
      requestAnimationFrame(()=>$('#shipSearch')?.focus());
      return;
    }
    if(route){
      page='dispatch';
      render();
      return;
    }
  }
  function openNotificationCenter(){
    if(!user||accessRole()==='customer')return;
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal ops-notification-modal">
      <div class="modal-head">
        <div><div class="eyebrow">${opsTr('مركز التنبيهات')}</div><h2>${opsTr('التنبيهات التشغيلية')}</h2></div>
        <button class="icon-btn" data-close>×</button>
      </div>
      <div class="ops-notification-summary">
        <span>${nt('unread')}</span><b>${unreadNotifications().length}</b>
        <span>${nt('totalNotifications')}</span><b>${state.notifications.length}</b>
      </div>
      <div class="ops-notification-list">
        ${state.notifications.slice(0,30).map(notificationRow).join('')||`<div class="card empty">${opsTr('لا توجد تنبيهات جديدة')}</div>`}
      </div>
    </section></div>`;
    wireModal();
    localizeNow(root);
    $$('[data-notification-open]',root).forEach(button=>{
      button.onclick=()=>openNotificationTarget(button.dataset.awb,button.dataset.route,button.closest('[data-notification-id]')?.dataset.notificationId);
    });
    $$('[data-notification-id]',root).forEach(row=>{
      row.onclick=e=>{
        if(e.target.closest('button'))return;
        const n=state.notifications.find(item=>String(item.id)===String(row.dataset.notificationId));
        if(n)markNotificationRead(n.id);
        row.classList.remove('is-unread');
      };
    });
  }
  function homeNotificationRow(n){
    const awb=notificationAwb(n),route=notificationRoute(n),unread=notificationUnread(n),context=notificationContext(n);
    const dir=opsIsRtl()?'rtl':'ltr';
    const meta=[context.recipient,context.route].filter(Boolean);
    return `<button type="button" class="ops-home-notification ${unread?'is-unread':''}" data-home-notification data-id="${safe(n.id??'')}" data-awb="${safe(awb)}" data-route="${safe(route)}" dir="${dir}">
      <span class="ops-home-notification-icon" aria-hidden="true">${awb?'📦':route?'⇄':'🔔'}</span>
      <span class="ops-home-notification-content">
        <span class="ops-home-notification-head">
          <b dir="auto">${safe(notificationTitle(n))}</b>
          ${awb?`<span class="ops-notification-awb" dir="ltr">${safe(awb)}</span>`:''}
          ${route?`<span class="ops-notification-route-code" dir="ltr">${safe(route)}</span>`:''}
          ${unread?`<span class="ops-notification-new">${nt('new')}</span>`:''}
        </span>
        <small class="ops-home-notification-message" dir="auto">${safe(notificationMessage(n))}</small>
        ${meta.length?`<span class="ops-home-notification-meta">${meta.map(value=>`<span dir="auto">${safe(value)}</span>`).join('')}</span>`:''}
        <span class="ops-home-notification-time" dir="auto">${safe(notificationTimeLabel(n))}</span>
      </span>
    </button>`;
  }
  function homeNotificationPanel(){
    const canRead=hasPermission('shipments.read')||hasPermission('routes.read');
    if(!canRead)return '';
    const rows=state.notifications.slice(0,5);
    return `<aside class="card ops-home-notifications">
      <div class="section-title ops-home-notifications-head" style="margin-top:0">
        <h2>${opsTr('التنبيهات')}</h2>
        <span class="badge ${unreadNotifications().length?'red':'green'}">${unreadNotifications().length}</span>
      </div>
      <div class="ops-home-notification-list">
        ${rows.map(homeNotificationRow).join('')||`<p class="ops-notification-empty">${opsTr('لا توجد تنبيهات جديدة')}</p>`}
      </div>
      <button class="btn light full ops-notifications-all" type="button" data-open-notifications>${opsTr('عرض كل التنبيهات')}</button>
    </aside>`;
  }
  async function refreshManagementFeed(){
    if(!user||accessRole()==='customer'||document.hidden)return;
    if(!hasPermission('shipments.read')&&!hasPermission('routes.read'))return;
    try{
      const owner=opsOwnerKey(),revision=state.ownerRevision;
      const [nextNotifications,nextShipments]=await Promise.all([
        (hasPermission('shipments.read')||hasPermission('routes.read'))?api('/api/notifications'):Promise.resolve([]),
        hasPermission('shipments.read')?api('/api/shipments'):Promise.resolve(shipments)
      ]);
      if(owner!==opsOwnerKey()||revision!==state.ownerRevision)return;

      const nRows=Array.isArray(nextNotifications)?nextNotifications:[];
      const sRows=Array.isArray(nextShipments)?nextShipments:shipments;
      const nSig=notificationSignature(nRows),sSig=shipmentSignature(sRows);
      const oldUnread=unreadNotifications().length;
      const nextUnread=nRows.filter(notificationUnread).length;
      const notificationsChanged=nSig!==state.lastNotificationSignature;
      const shipmentsChanged=sSig!==state.lastShipmentSignature;

      state.notifications=nRows;
      if(hasPermission('shipments.read'))shipments=sRows;
      state.lastNotificationSignature=nSig;
      state.lastShipmentSignature=sSig;
      updateNoticeBadge();

      if(state.lastUnreadCount!=null&&nextUnread>state.lastUnreadCount){
        toast(`${opsTr('تنبيه جديد')} · ${nextUnread-state.lastUnreadCount}`);
      }
      state.lastUnreadCount=nextUnread;

      if((notificationsChanged||shipmentsChanged)&&!$('#modalRoot')?.innerHTML&&['home','shipments','dispatch','tracking'].includes(page)){
        baseRender();
        bindOps();
      }
    }catch(_){}
  }

  function liveHome(){
    const total=shipments.length,ready=shipments.filter(s=>['جاهز للتسليم','في الفرع'].includes(s.status)).length,delayed=shipments.filter(s=>s.status==='تأخير').length,active=state.routes.filter(r=>['مجدولة','في الطريق'].includes(r.status)).length,canReadRoutes=hasPermission('routes.read'),canReadDrivers=hasPermission('drivers.read');
    if(accessRole()==='courier'){const deliveryCount=courierDeliveryRows().length,pickupCount=courierPickupRows().length,attemptCount=courierDeliveryRows().filter(row=>row.active_attempt).length;return `${head(`KSA · ${opsTr('تطبيق المندوب')}`,opsTr('مهام اليوم'),ct('operationsSub'))}<div class="grid kpis">${kpi(ct('deliveryTasks'),deliveryCount,opsTr('تم تحديث البيانات الآن'),'▤')}${kpi(ct('pickupTasks'),pickupCount,ct('pickupNumber'),'⌂')}${kpi(ct('activeAttempts'),attemptCount,ct('inProgress'),'▶','positive')}${kpi(opsTr('متأخرة'),delayed,opsTr('تواصل مع مدير العمليات'),'⚠','negative')}</div><div class="ops-inline-actions"><button class="btn primary" data-page="proof">▤ ${ct('operations')}</button><button class="btn light" data-driver-location="1">◎ ${opsTr('تحديث موقع السائق')}</button></div><div class="shipment-grid">${shipments.map(shipmentCard).join('')}</div>`;}
    return `${head(`KSA · ${opsTr('مركز العمليات اللوجستية')}`,opsTr('مركز العمليات اللوجستية'),opsTr('شحنات جميع المدن والفروع وحالة التشغيل الفعلية'),`<button class="btn primary" data-action="create">＋ ${opsTr('إنشاء شحنة')}</button>`)}<div class="grid kpis">${kpi(opsTr('إجمالي الشحنات'),total,opsTr('في قاعدة البيانات'),'▤')}${kpi(opsTr('جاهزة للتسليم'),ready,opsTr('في الفروع'),'✓','positive')}${canReadRoutes?kpi(opsTr('الرحلات النشطة'),active,opsTr('مجدولة أو في الطريق'),'⇄'):''}${kpi(opsTr('حالات متأخرة'),delayed,opsTr('تحتاج إلى متابعة فورية'),'⚠','negative')}</div><div class="grid ${canReadRoutes?'dashboard-grid':''}"><section><div class="dark-card"><div class="eyebrow" style="color:#e7c3a5">KSA · NATIONAL NETWORK</div><h2>${opsTr('أهلاً بك في غزالا ترانسبورت')}</h2><p>${opsTr('مركز التشغيل الوطني للفروع والمسارات')}</p><div class="dark-kpis"><div><b>${fmt(total)}</b><span>${opsTr('إجمالي الشحنات')}</span></div>${canReadRoutes?`<div><b>${fmt(active)}</b><span>${opsTr('رحلات نشطة')}</span></div>`:''}${canReadDrivers?`<div><b>${fmt(drivers.length)}</b><span>${opsTr('المناديب')}</span></div>`:''}</div></div><div class="section-title"><h2>${opsTr('الشحنات الأخيرة')}</h2><button class="link" data-page="shipments">${opsTr('عرض الكل ←')}</button></div><div class="shipment-list">${shipments.slice(0,4).map(shipmentCard).join('')}</div></section>${homeNotificationPanel()}</div>`;
  }
  function publicTrackBlock(id='publicTrackForm',resultId='publicTrackResult') {return `<section class="card public-track"><div class="section-title" style="margin-top:0"><div><div class="eyebrow">${opsTr('التتبع العام')}</div><h2>${opsTr('تتبع شحنتك خطوة بخطوة')}</h2></div><span class="icon-square">⌕</span></div><p>${opsTr('أدخل رقم بوليصة غزالا لمعرفة حالة الشحنة والوقت المتوقع وموقعها التشغيلي.')}</p><form id="${id}" class="ops-track-form"><input name="awb" value="${safe(tracking)}" placeholder="GHZ-000125" aria-label="${opsTr('رقم البوليصة')}" required><button class="btn accent">${opsTr('تتبع الشحنة')}</button></form><div id="${resultId}"></div></section>`}
  function trackingFragment(){
    const hash=location.hash;if(!hash.startsWith('#track='))return null;
    try{const awb=decodeURIComponent(hash.slice(7)).trim().toUpperCase();return {hash,awb,error:!awb}}
    catch(e){return {hash,awb:'',error:true}}
  }
  function customerTrackingLanding(fragment){
    return '<div id="customerTrackingView" class="landing-shell"><div class="landing-wrap">'+head('KSA · '+opsTr('خدمة العملاء'),opsTr('تتبع الشحنات'),opsTr('أدخل رقم البوليصة لمعرفة آخر تحديث وموقع الشحنة'),'<button type="button" class="btn light small" data-tracking-home>← '+opsTr('العودة إلى الصفحة الرئيسية')+'</button>')+(fragment.error?'<p class="notice-error">'+opsTr('تعذر قراءة رابط التتبع. أدخل رقم البوليصة أدناه.')+'</p>':'')+publicTrackBlock()+'</div></div>';
  }
  function landingWithTracker(){const fragment=trackingFragment();if(fragment)return customerTrackingLanding(fragment);const html=baseLanding(),mark='<section class="landing-cta">',at=html.indexOf(mark),block=publicTrackBlock('landingTrackForm','landingTrackResult');return at<0?html+block:html.slice(0,at)+block+html.slice(at)}
  function trackingHome(){history.replaceState(null,'',location.pathname+location.search);tracking='';page='landing';render();window.scrollTo(0,0)}
  function autoTrackFragment(){
    const fragment=trackingFragment();if(!fragment?.awb)return;
    const field=$('#publicTrackForm [name=awb],#landingTrackForm [name=awb]');if(!field)return;
    const form=field.form;if(form.dataset.autoTrackHash===fragment.hash)return;
    form.dataset.autoTrackHash=fragment.hash;field.value=fragment.awb;form.requestSubmit();
  }
  function trackingWithPublic(){return `${head(`KSA · ${opsTr('خدمة العملاء')}`,opsTr('تتبع الشحنات'),opsTr('أدخل رقم البوليصة لمعرفة آخر تحديث وموقع الشحنة'))}${publicTrackBlock()}<div class="section-title"><h2>${opsTr('الشحنات النشطة')}</h2></div><div class="shipment-grid">${shipments.slice(0,4).map(shipmentCard).join('')}</div>`}
  const COURIER_TEXT={
    operations:{ar:'عمليات المندوب والتسليم',en:'Courier & Delivery Operations'},
    operationsSub:{ar:'إدارة مهام التوصيل والاستلام ومحاولات التسليم وإثبات الاستلام',en:'Manage delivery tasks, pickup tasks, delivery attempts and proof of delivery.'},
    deliveryTasks:{ar:'مهام التوصيل',en:'Delivery Tasks'},
    completedDeliveries:{ar:'عمليات التسليم المكتملة',en:'Completed Deliveries'},
    completedDeliveriesSub:{ar:'سجل التسليمات المكتملة ومحاولاتها السابقة وإثباتات التسليم',en:'Review completed deliveries, previous attempts and saved proof of delivery.'},
    pickupTasks:{ar:'مهام الاستلام من العميل',en:'Pickup Tasks'},
    pickupHistory:{ar:'سجل مهام الاستلام',en:'Pickup History'},
    activeAttempts:{ar:'محاولات نشطة',en:'Active Attempts'},
    failedAttempts:{ar:'محاولات فاشلة',en:'Failed Attempts'},
    startAttempt:{ar:'بدء محاولة التسليم',en:'Start Delivery Attempt'},
    failAttempt:{ar:'تسجيل تعذر التسليم',en:'Record Failed Delivery'},
    attemptHistory:{ar:'سجل المحاولات',en:'Attempt History'},
    completePod:{ar:'إكمال إثبات التسليم',en:'Complete POD'},
    refresh:{ar:'تحديث المهام',en:'Refresh Tasks'},
    attempt:{ar:'المحاولة',en:'Attempt'},
    attempts:{ar:'المحاولات',en:'Attempts'},
    failed:{ar:'فشلت',en:'Failed'},
    inProgress:{ar:'قيد التنفيذ',en:'In Progress'},
    delivered:{ar:'تم التسليم',en:'Delivered'},
    driver:{ar:'المندوب',en:'Courier'},
    recipient:{ar:'المستلم',en:'Recipient'},
    location:{ar:'الموقع الحالي',en:'Current Location'},
    useGps:{ar:'استخدام GPS الحالي',en:'Use Current GPS'},
    note:{ar:'ملاحظة',en:'Note'},
    startNow:{ar:'بدء التوصيل الآن',en:'Start Delivery Now'},
    failureReason:{ar:'سبب تعذر التسليم',en:'Failure Reason'},
    otherReason:{ar:'تفاصيل السبب',en:'Reason Details'},
    nextAttempt:{ar:'موعد المحاولة القادمة',en:'Next Attempt'},
    failurePhoto:{ar:'صورة حالة التسليم',en:'Delivery Exception Photo'},
    saveFailure:{ar:'حفظ المحاولة الفاشلة',en:'Save Failed Attempt'},
    noDelivery:{ar:'لا توجد مهام توصيل مسندة حالياً',en:'No assigned delivery tasks right now.'},
    noPickup:{ar:'لا توجد مهام استلام نشطة حالياً',en:'No active pickup tasks right now.'},
    assigned:{ar:'تم الإسناد',en:'Assigned'},
    requested:{ar:'مطلوب',en:'Requested'},
    pickedUp:{ar:'تم الاستلام من العميل',en:'Picked Up'},
    completed:{ar:'مكتمل',en:'Completed'},
    cancelled:{ar:'ملغي',en:'Cancelled'},
    assignCourier:{ar:'إسناد مندوب',en:'Assign Courier'},
    confirmPickup:{ar:'تأكيد استلام الطرد',en:'Confirm Picked Up'},
    completePickup:{ar:'إكمال طلب الاستلام',en:'Complete Pickup'},
    pickupNumber:{ar:'رقم طلب الاستلام',en:'Pickup Number'},
    customer:{ar:'العميل',en:'Customer'},
    branch:{ar:'الفرع',en:'Branch'},
    preferred:{ar:'الوقت المفضل',en:'Preferred Time'},
    pieces:{ar:'الطرود',en:'Parcels'},
    weight:{ar:'الوزن',en:'Weight'},
    address:{ar:'العنوان',en:'Address'},
    assignmentNote:{ar:'ملاحظة الإسناد',en:'Assignment Note'},
    updatePickup:{ar:'تحديث طلب الاستلام',en:'Update Pickup'},
    noHistory:{ar:'لا توجد محاولات تسليم مسجلة لهذه الشحنة',en:'No delivery attempts have been recorded for this shipment.'},
    started:{ar:'بدأت محاولة التسليم',en:'Delivery attempt started'},
    failureSaved:{ar:'تم تسجيل تعذر التسليم',en:'Failed delivery recorded'},
    pickupUpdated:{ar:'تم تحديث طلب الاستلام',en:'Pickup request updated'},
    photoAttached:{ar:'صورة مرفقة',en:'Photo attached'},
    noPhoto:{ar:'بدون صورة',en:'No photo'},
    smsSent:{ar:'تم إنشاء إشعار العميل',en:'Customer notification generated'},
    waitingWorkflow:{ar:'بانتظار وصول الشحنة لمرحلة جاهز للتسليم',en:'Waiting for Ready for Delivery'},
    readyNow:{ar:'جاهزة لبدء التوصيل',en:'Ready to Start Delivery'},
    workflowStatus:{ar:'مرحلة الشحنة',en:'Shipment Stage'},
    viewPod:{ar:'عرض إثبات التسليم',en:'View POD'},
    proofTitle:{ar:'إثبات التسليم المحفوظ',en:'Saved Proof of Delivery'},
    actualRecipient:{ar:'المستلم الفعلي',en:'Actual Recipient'},
    idSuffix:{ar:'آخر 4 أرقام من الهوية',en:'Last 4 ID Digits'},
    verifiedBy:{ar:'تم التحقق بواسطة',en:'Verified By'},
    verifiedAt:{ar:'وقت التحقق',en:'Verified At'},
    coordinates:{ar:'إحداثيات التسليم',en:'Delivery Coordinates'},
    failureDetails:{ar:'تفاصيل تعذر التسليم',en:'Failure Details'},
    failureGps:{ar:'إحداثيات محاولة التسليم الفاشلة',en:'Failed Attempt GPS'},
    failureRecordedAt:{ar:'وقت تسجيل التعذر',en:'Failure Recorded At'},
    attemptStartedAt:{ar:'وقت بدء المحاولة',en:'Attempt Started At'},
    attemptCompletedAt:{ar:'وقت إغلاق المحاولة',en:'Attempt Closed At'},
    signature:{ar:'توقيع المستلم',en:'Recipient Signature'},
    parcelPhoto:{ar:'صورة الطرد عند التسليم',en:'Parcel Delivery Photo'},
    noParcelPhoto:{ar:'لم يتم حفظ صورة للطرد',en:'No parcel photo was saved'},
    proofNote:{ar:'ملاحظة التسليم',en:'Delivery Note'},
    immutableProof:{ar:'إثبات التسليم محفوظ للقراءة فقط ولا يمكن استبداله',en:'Saved delivery proof is read-only and cannot be replaced.'}
  };
  function ct(key){return opsDictText('courier',key,COURIER_TEXT[key])}
  function courierPayload(){return state.courier&&typeof state.courier==='object'?state.courier:{delivery_tasks:[],pickup_tasks:[],failure_reasons:[]}}
  function courierDeliveryRows(){return Array.isArray(courierPayload().delivery_tasks)?courierPayload().delivery_tasks:[]}
  function courierPickupRows(){return Array.isArray(courierPayload().pickup_tasks)?courierPayload().pickup_tasks:[]}
  function courierFailureReasons(){return Array.isArray(courierPayload().failure_reasons)?courierPayload().failure_reasons:[]}
  function courierReasonLabel(code){
    const row=courierFailureReasons().find(item=>item.code===code);
    const ar=row?.label_ar||'',en=row?.label_en||code;
    if(currentLang==='ar')return ar||en;
    if(ar){try{const translated=opsTr(ar);if(translated&&translated!==ar)return translated}catch(_){}}
    return en||ar||code;
  }
  function courierOutcomeLabel(value){return ({in_progress:ct('inProgress'),failed:ct('failed'),delivered:ct('delivered')})[value]||opsTr(value||'—')}
  function pickupStatusLabel(value){return ({requested:ct('requested'),assigned:ct('assigned'),picked_up:ct('pickedUp'),completed:ct('completed'),cancelled:ct('cancelled')})[value]||opsTr(value||'—')}
  function courierRole(){return typeof accessRole==='function'?accessRole():(user?.access_role||user?.role||'')}
  function courierStatusKey(task){
    return String(task?.status||'').trim().toLowerCase();
  }
  function courierTaskCanStart(task){
    if(!task||task.active_attempt||task.pod_complete)return false;
    const status=courierStatusKey(task);
    return [
      'جاهز للتسليم','ready for delivery',
      'في فرع الوجهة','at destination',
      'تأخير','delayed',
      'قيد التوصيل','out for delivery'
    ].some(value=>status===value||status.includes(value));
  }
  function canCourierTaskScreen(){return ['system_admin','branch_manager','office_employee','courier'].includes(courierRole())&&hasPermission('shipments.read')}
  async function refreshCourierTasks(repaint=true){
    if(!canCourierTaskScreen()){state.courier={delivery_tasks:[],pickup_tasks:[],failure_reasons:[]};return state.courier}
    state.courier=await api('/api/courier/tasks?include_completed=1');
    const normalizeCourierPlace=value=>String(value??'').replace(/\bJaazan\b/gi,'Jazan').replace(/\bJizan\b/gi,'Jazan');
    for(const bucket of ['delivery_tasks','pickup_tasks']){
      if(Array.isArray(state.courier?.[bucket])){
        state.courier[bucket]=state.courier[bucket].map(row=>({
          ...row,
          origin:normalizeCourierPlace(row.origin),
          destination:normalizeCourierPlace(row.destination),
          driver_location:normalizeCourierPlace(row.driver_location),
          current_location:normalizeCourierPlace(row.current_location),
          location_text:normalizeCourierPlace(row.location_text)
        }));
      }
    }
    if(repaint&&page==='proof'){baseRender();bindOps()}
    return state.courier;
  }
  function courierTaskCard(task){
    const active=task.active_attempt,failed=Number(task.failed_attempts||0),attempts=Number(task.attempt_count||0);
    const location=task.driver_location||task.current_location||task.destination||'—';
    const canStart=courierTaskCanStart(task);
    const waiting=!active&&!task.pod_complete&&!canStart;
    return `<article class="card courier-task-card ${waiting?'is-waiting-workflow':''}" data-courier-awb="${safe(task.awb)}">
      <div class="shipment-top"><span class="awb">${safe(task.awb)}</span><div><b class="ship-name">${safe(task.recipient||ct('recipient'))}</b><div class="ship-phone">${safe(task.phone||'')}</div></div><span class="push"></span>${badge(task.status)}</div>
      <div class="ship-route"><span>${safe(cityDisplayName(task.origin||'—'))}</span><span class="route-arrow">→</span><span>${safe(cityDisplayName(task.destination||'—'))}</span></div>
      <div class="record-meta courier-task-meta">
        <span>${ct('driver')}: <b>${safe(task.driver_name||opsTr('غير معيّن'))}</b></span>
        <span>${ct('attempts')}: <b>${attempts}</b></span>
        <span>${ct('failedAttempts')}: <b>${failed}</b></span>
        <span>${ct('location')}: <b>${safe(cityPlaceDisplay(location))}</b></span>
      </div>
      ${active?`<div class="notice-ok courier-active-attempt">${ct('inProgress')} · #${safe(active.attempt_number)}${active.started_at?` · ${safe(active.started_at)}`:''}</div>`:''}
      ${waiting?`<div class="courier-workflow-wait"><b>${ct('workflowStatus')}:</b> <span>${ct('waitingWorkflow')}</span></div>`:''}
      <div class="ship-bottom courier-task-actions">
        ${canStart?`<button type="button" class="btn primary small" data-delivery-start="${safe(task.awb)}">▶ ${ct('startAttempt')}</button>`:''}
        ${waiting?`<button type="button" class="btn light small" disabled title="${safe(ct('waitingWorkflow'))}">⌛ ${ct('waitingWorkflow')}</button>`:''}
        ${active?`<button type="button" class="btn danger small" data-delivery-fail="${safe(task.awb)}">⚠ ${ct('failAttempt')}</button>`:''}
        ${hasPermission('pod.read')?`<button type="button" class="btn light small" data-delivery-history="${safe(task.awb)}">◷ ${ct('attemptHistory')}</button>`:''}
        ${active&&!task.pod_complete&&hasPermission('pod.create')?`<button type="button" class="btn accent small" data-delivery-pod="${safe(task.awb)}">✓ ${ct('completePod')}</button>`:''}
        ${task.pod_complete?`<span class="badge green">✓ ${ct('delivered')}</span>`:''}
      </div>
    </article>`;
  }
  function pickupTaskCard(task){
    const role=courierRole(),canAssign=['system_admin','branch_manager'].includes(role),canManage=['system_admin','branch_manager','office_employee'].includes(role),canCourier=role==='courier';
    const actions=[];
    if(task.status==='requested'&&canAssign)actions.push(`<button type="button" class="btn primary small" data-pickup-action="assign" data-pickup-number="${safe(task.pickup_number)}">＋ ${ct('assignCourier')}</button>`);
    if(task.status==='assigned'&&(canCourier||canManage))actions.push(`<button type="button" class="btn primary small" data-pickup-action="picked_up" data-pickup-number="${safe(task.pickup_number)}">✓ ${ct('confirmPickup')}</button>`);
    if(task.status==='picked_up'&&canManage)actions.push(`<button type="button" class="btn accent small" data-pickup-action="completed" data-pickup-number="${safe(task.pickup_number)}">✓ ${ct('completePickup')}</button>`);
    return `<article class="card courier-pickup-card" data-pickup-card="${safe(task.pickup_number)}">
      <div class="shipment-top"><span class="awb">${safe(task.pickup_number)}</span><div><b class="ship-name">${safe(task.customer_name||task.contact_name||ct('customer'))}</b><div class="ship-phone">${safe(task.contact_mobile||task.customer_mobile||'')}${task.awb?` · ${safe(task.awb)}`:''}</div></div><span class="push"></span><span class="badge ${task.status==='completed'?'green':task.status==='cancelled'?'red':'blue'}">${safe(pickupStatusLabel(task.status))}</span></div>
      <div class="record-meta courier-task-meta">
        <span>${ct('branch')}: <b>${safe(task.branch_name||task.city||'—')}</b></span>
        <span>${ct('driver')}: <b>${safe(task.driver_name||opsTr('غير معيّن'))}</b></span>
        <span>${ct('pieces')}: <b>${fmt(task.pieces||1)}</b></span>
        <span>${ct('weight')}: <b>${fmt(task.weight||0)} kg</b></span>
        <span>${ct('preferred')}: <b>${safe(task.preferred_at||'—')}</b></span>
      </div>
      <div class="ops-location"><b>⌖ ${ct('address')}</b><span>${safe(task.address||task.city||'—')}</span>${task.notes?`<small>${safe(task.notes)}</small>`:''}</div>
      ${actions.length?`<div class="ship-bottom courier-task-actions">${actions.join('')}</div>`:''}
    </article>`;
  }
  function courierOperationsPanel(){
    if(!canCourierTaskScreen())return '';
    const allDeliveries=courierDeliveryRows();
    const completedDeliveries=allDeliveries.filter(row=>row.pod_complete||courierStatusKey(row)==='تم الاستلام'||courierStatusKey(row)==='delivered');
    const deliveries=allDeliveries.filter(row=>!completedDeliveries.includes(row));
    const pickupRows=courierPickupRows();
    const pickups=pickupRows.filter(row=>!['completed','cancelled'].includes(String(row.status||'').toLowerCase()));
    const pickupHistory=pickupRows.filter(row=>['completed','cancelled'].includes(String(row.status||'').toLowerCase()));
    const active=deliveries.filter(row=>row.active_attempt).length,failed=deliveries.reduce((sum,row)=>sum+Number(row.failed_attempts||0),0),ready=deliveries.filter(courierTaskCanStart).length;
    return `<section class="courier-operations-shell">
      <div class="grid kpis courier-kpis">
        ${kpi(ct('deliveryTasks'),deliveries.length,`${ready} · ${ct('readyNow')}`,'▤')}
        ${kpi(ct('pickupTasks'),pickups.length,ct('pickupNumber'),'⌂')}
        ${kpi(ct('activeAttempts'),active,ct('inProgress'),'▶','positive')}
        ${kpi(ct('failedAttempts'),failed,ct('failedAttempts'),'⚠',failed?'negative':'')}
      </div>
      <div class="section-title"><div><div class="eyebrow">GHAZALA COURIER OPS</div><h2>${ct('deliveryTasks')}</h2></div><button type="button" class="btn light small" data-courier-refresh>↻ ${ct('refresh')}</button></div>
      <div class="shipment-grid courier-delivery-grid">${deliveries.map(courierTaskCard).join('')||`<div class="card empty">${ct('noDelivery')}</div>`}</div>
      ${completedDeliveries.length?`<div class="section-title"><div><div class="eyebrow">GHAZALA DELIVERY ARCHIVE</div><h2>${ct('completedDeliveries')}</h2><p>${ct('completedDeliveriesSub')}</p></div><span class="badge green">${completedDeliveries.length}</span></div>
      <div class="shipment-grid courier-completed-grid">${completedDeliveries.map(courierTaskCard).join('')}</div>`:''}
      <div class="section-title"><div><h2>${ct('pickupTasks')}</h2><p>${ct('operationsSub')}</p></div><span class="badge">${pickups.length}</span></div>
      <div class="shipment-grid courier-pickup-grid">${pickups.map(pickupTaskCard).join('')||`<div class="card empty">${ct('noPickup')}</div>`}</div>
      ${pickupHistory.length?`<div class="section-title"><div><h2>${ct('pickupHistory')}</h2></div><span class="badge">${pickupHistory.length}</span></div>
      <div class="shipment-grid courier-pickup-history-grid">${pickupHistory.map(pickupTaskCard).join('')}</div>`:''}
    </section>`;
  }
  function startDeliveryAttemptModal(awb){
    const task=courierDeliveryRows().find(row=>row.awb===awb);
    if(!task)return toast(opsTr('لم نعثر على الشحنة'));
    if(!courierTaskCanStart(task))return toast(ct('waitingWorkflow'));
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal courier-action-modal">
      <div class="modal-head"><div><div class="eyebrow">${safe(awb)}</div><h2>${ct('startAttempt')}</h2></div><button class="icon-btn" data-close>×</button></div>
      <form id="deliveryStartForm" class="form-grid ops-form">
        <div class="field span-2 ops-recipient-card"><span>${ct('recipient')}</span><b>${safe(task.recipient||'—')}</b><small>${safe(cityDisplayName(task.origin||'—'))} → ${safe(cityDisplayName(task.destination||'—'))}</small></div>
        <label class="field span-2"><span>${ct('location')}</span><input name="location_text" value="${safe(cityPlaceDisplay(task.driver_location||task.destination||''))}"></label>
        <input type="hidden" name="latitude"><input type="hidden" name="longitude">
        <div class="field span-2"><button type="button" class="btn light full" id="deliveryStartGps">◎ ${ct('useGps')}</button><small id="deliveryStartGpsLabel">—</small></div>
        <label class="field span-2"><span>${ct('note')}</span><textarea name="note" placeholder="${ct('note')}"></textarea></label>
        <div class="field span-2 ops-form-actions"><button class="btn light" type="button" data-close>${pt('close')}</button><button class="btn primary">▶ ${ct('startNow')}</button></div>
      </form>
    </section></div>`;
    wireModal();localizeNow($('#modalRoot'));const form=$('#deliveryStartForm');
    $('#deliveryStartGps').onclick=()=>gps((lat,lng)=>{form.elements.latitude.value=lat;form.elements.longitude.value=lng;$('#deliveryStartGpsLabel').textContent=`${lat}, ${lng}`});
    form.onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(form));['latitude','longitude'].forEach(key=>{data[key]=data[key]===''?null:Number(data[key])});try{await api(`/api/shipments/${encodeURIComponent(awb)}/delivery/start`,{method:'POST',body:JSON.stringify(data)});closeModal();toast(ct('started'));await refreshCourierTasks(false);await load();render()}catch(error){toast(opsTr(error.message))}};
  }
  function failDeliveryAttemptModal(awb){
    const task=courierDeliveryRows().find(row=>row.awb===awb);if(!task?.active_attempt)return toast(ct('startAttempt'));
    const reasons=courierFailureReasons();
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal courier-action-modal">
      <div class="modal-head"><div><div class="eyebrow">${safe(awb)}</div><h2>${ct('failAttempt')}</h2></div><button class="icon-btn" data-close>×</button></div>
      <form id="deliveryFailForm" class="form-grid ops-form">
        <label class="field"><span>${ct('failureReason')} *</span><select name="reason_code" required>${reasons.map(row=>`<option value="${safe(row.code)}">${safe(currentLang==='ar'?(row.label_ar||row.label_en):(row.label_en||row.label_ar))}</option>`).join('')}</select></label>
        <label class="field"><span>${ct('nextAttempt')}</span><input name="next_attempt_at" type="datetime-local" value="${localDT(24)}"></label>
        <label class="field span-2"><span>${ct('otherReason')}</span><input name="reason_text" placeholder="${ct('otherReason')}"></label>
        <label class="field span-2"><span>${ct('location')}</span><input name="location_text" value="${safe(cityPlaceDisplay(task.driver_location||task.destination||''))}"></label>
        <input type="hidden" name="latitude"><input type="hidden" name="longitude">
        <div class="field span-2"><button type="button" class="btn light full" id="deliveryFailGps">◎ ${ct('useGps')}</button><small id="deliveryFailGpsLabel">—</small></div>
        <div class="field span-2"><span>${ct('failurePhoto')}</span><input name="photo" type="file" accept="image/*" capture="environment"></div>
        <label class="field span-2"><span>${ct('note')}</span><textarea name="note"></textarea></label>
        <div class="field span-2 ops-form-actions"><button class="btn light" type="button" data-close>${pt('close')}</button><button class="btn danger">⚠ ${ct('saveFailure')}</button></div>
      </form>
    </section></div>`;
    wireModal();localizeNow($('#modalRoot'));const form=$('#deliveryFailForm');
    $('#deliveryFailGps').onclick=()=>gps((lat,lng)=>{form.elements.latitude.value=lat;form.elements.longitude.value=lng;$('#deliveryFailGpsLabel').textContent=`${lat}, ${lng}`});
    form.onsubmit=async event=>{event.preventDefault();const raw=new FormData(form),file=raw.get('photo');const data={reason_code:String(raw.get('reason_code')||''),reason_text:String(raw.get('reason_text')||''),location_text:String(raw.get('location_text')||''),next_attempt_at:String(raw.get('next_attempt_at')||''),note:String(raw.get('note')||''),latitude:raw.get('latitude')?Number(raw.get('latitude')):null,longitude:raw.get('longitude')?Number(raw.get('longitude')):null};if(file&&file.size)data.photo_data=await compressPhoto(file);try{await api(`/api/shipments/${encodeURIComponent(awb)}/delivery/fail`,{method:'POST',body:JSON.stringify(data)});closeModal();toast(ct('failureSaved'));await refreshCourierTasks(false);await load();render()}catch(error){toast(opsTr(error.message))}};
  }
  async function deliveryAttemptHistoryModal(awb){
    try{
      const data=await api(`/api/shipments/${encodeURIComponent(awb)}/delivery-attempts`),rows=Array.isArray(data.attempts)?data.attempts:[];
      $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal courier-history-modal">
        <div class="modal-head"><div><div class="eyebrow">${safe(awb)}</div><h2>${ct('attemptHistory')}</h2></div><button class="icon-btn" data-close>×</button></div>
        <div class="courier-history-list">${rows.map(row=>{
          const hasGps=row.latitude!==null&&row.latitude!==undefined&&row.latitude!==''&&
            row.longitude!==null&&row.longitude!==undefined&&row.longitude!=='';
          const isFailed=String(row.outcome||'').toLowerCase()==='failed';
          const startedText=podDateText(row.started_at||row.created_at||'');
          const closedText=podDateText(row.completed_at||'');
          const nextText=podDateText(row.next_attempt_at||'');
          const gpsText=hasGps?`${Number(row.latitude).toFixed(6)}, ${Number(row.longitude).toFixed(6)}`:'—';
          return `<article class="card courier-history-row">
            <div class="section-title" style="margin-top:0">
              <h3>#${safe(row.attempt_number)} · ${safe(courierOutcomeLabel(row.outcome))}</h3>
              <span class="badge ${row.outcome==='delivered'?'green':row.outcome==='failed'?'red':'blue'}">${safe(courierOutcomeLabel(row.outcome))}</span>
            </div>

            <div class="record-meta">
              <span>${ct('driver')}: <b>${safe(row.driver_name||'—')}</b></span>
              <span>${ct('location')}: <b>${safe(cityPlaceDisplay(row.location_text||'—'))}</b></span>
              <span>${ct('attemptStartedAt')}: <b>${safe(startedText)}</b></span>
              ${row.completed_at?`<span>${ct('attemptCompletedAt')}: <b>${safe(closedText)}</b></span>`:''}
            </div>

            ${isFailed?`<div class="card" style="margin-top:12px;padding:14px;border:1px solid rgba(220,53,69,.20);background:rgba(220,53,69,.035)">
              <div style="font-weight:900;margin-bottom:10px">${ct('failureDetails')}</div>
              <div class="record-meta">
                <span>${ct('failureReason')}: <b>${safe(row.failure_reason_code?courierReasonLabel(row.failure_reason_code):'—')}</b></span>
                <span>${ct('otherReason')}: <b>${safe(row.failure_reason_text||'—')}</b></span>
                <span>${ct('failureGps')}: <b>${safe(gpsText)}</b></span>
                <span>${ct('failureRecordedAt')}: <b>${safe(closedText||startedText)}</b></span>
                <span>${ct('nextAttempt')}: <b>${safe(nextText)}</b></span>
                <span>${ct('failurePhoto')}: <b>${row.has_photo?safe(ct('photoAttached')):safe(ct('noPhoto'))}</b></span>
              </div>
            </div>`:
            `${hasGps?`<div class="record-meta" style="margin-top:10px"><span>${ct('coordinates')}: <b>${safe(gpsText)}</b></span></div>`:''}`}

            ${row.note?`<p style="margin-top:12px"><b>${ct('note')}:</b> ${safe(row.note)}</p>`:''}
          </article>`;
        }).join('')||`<div class="card empty">${ct('noHistory')}</div>`}</div>
      </section></div>`;wireModal();localizeNow($('#modalRoot'));
    }catch(error){toast(opsTr(error.message))}
  }

  function isDeliveredShipment(shipment){
    const status=String(shipment?.status||'').trim().toLowerCase();
    return status==='تم الاستلام'||status==='تم التسليم'||status==='delivered';
  }
  function podEvidenceImage(value,kind='photo'){
    const text=String(value||'').trim();
    if(kind==='signature'){
      return /^data:image\/png;base64,[a-z0-9+/=\s]+$/i.test(text)?text:'';
    }
    return /^data:image\/(?:png|jpe?g|webp);base64,[a-z0-9+/=\s]+$/i.test(text)?text:'';
  }
  function podDateText(value){
    if(!value)return '—';
    const parsed=new Date(value);
    if(Number.isNaN(parsed.getTime()))return String(value);
    try{
      return parsed.toLocaleString(opsLocaleTag(),{
        year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'
      });
    }catch(_){return String(value)}
  }
  async function openSavedPodModal(awb){
    if(!hasPermission('pod.read'))return requirePermission('pod.read');
    const normalized=String(awb||'').trim().toUpperCase();
    if(!normalized)return;
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:780px">
      <div class="modal-head"><div><div class="eyebrow">${safe(normalized)}</div><h2>${ct('proofTitle')}</h2></div><button class="icon-btn" type="button" data-close>×</button></div>
      <div class="card" style="padding:18px"><div class="kpi-note">${dt('loading')}</div></div>
    </section></div>`;
    wireModal();
    try{
      const proof=await api(`/api/shipments/${encodeURIComponent(normalized)}/pod`);
      const signature=podEvidenceImage(proof.signature_data,'signature');
      const photo=podEvidenceImage(proof.photo_data,'photo');
      const latitude=proof.latitude!=null&&proof.latitude!==''?Number(proof.latitude):null;
      const longitude=proof.longitude!=null&&proof.longitude!==''?Number(proof.longitude):null;
      const coordinates=Number.isFinite(latitude)&&Number.isFinite(longitude)
        ?`${latitude.toFixed(6)}, ${longitude.toFixed(6)}`
        :'—';
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal courier-history-modal" style="max-width:820px">
        <div class="modal-head">
          <div><div class="eyebrow">${safe(normalized)}</div><h2>${ct('proofTitle')}</h2></div>
          <button class="icon-btn" type="button" data-close>×</button>
        </div>
        <div class="notice-ok" style="margin-bottom:14px">✓ ${ct('immutableProof')}</div>
        <div class="record-meta" style="grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:14px">
          <span>${ct('actualRecipient')}: <b>${safe(proof.recipient_name||'—')}</b></span>
          <span>${ct('idSuffix')}: <b>${safe(proof.recipient_id_suffix||'—')}</b></span>
          <span>${ct('verifiedBy')}: <b>${safe(proof.verified_by||'—')}</b></span>
          <span>${ct('verifiedAt')}: <b>${safe(podDateText(proof.verified_at))}</b></span>
          <span>${ct('coordinates')}: <b>${safe(coordinates)}</b></span>
          <span>${ct('proofNote')}: <b>${safe(proof.note||'—')}</b></span>
        </div>
        <div class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr));gap:12px">
          <article class="card" style="padding:14px;min-height:170px">
            <div class="section-title" style="margin-top:0"><h3 style="margin:0">${ct('signature')}</h3></div>
            ${signature
              ?`<div style="display:grid;place-items:center;min-height:120px;border:1px dashed #d7dee7;border-radius:10px;background:#fff"><img src="${signature}" alt="${safe(ct('signature'))}" style="max-width:100%;max-height:150px;object-fit:contain"></div>`
              :`<div class="card empty" style="box-shadow:none">${ct('signature')} —</div>`}
          </article>
          <article class="card" style="padding:14px;min-height:170px">
            <div class="section-title" style="margin-top:0"><h3 style="margin:0">${ct('parcelPhoto')}</h3></div>
            ${photo
              ?`<div style="display:grid;place-items:center;min-height:120px;border-radius:10px;overflow:hidden;background:#f8fafc"><img src="${photo}" alt="${safe(ct('parcelPhoto'))}" style="width:100%;max-height:230px;object-fit:contain"></div>`
              :`<div class="card empty" style="box-shadow:none">${ct('noParcelPhoto')}</div>`}
          </article>
        </div>
        <div class="ops-form-actions" style="margin-top:14px">
          <button type="button" class="btn light" data-pod-attempt-history="${safe(normalized)}">◷ ${ct('attemptHistory')}</button>
          <button type="button" class="btn primary" data-close>${pt('close')}</button>
        </div>
      </section></div>`;
      wireModal();
      const historyButton=$('[data-pod-attempt-history]',root);
      if(historyButton)historyButton.onclick=()=>deliveryAttemptHistoryModal(normalized);
      localizeNow(root);
    }catch(error){
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:620px">
        <div class="modal-head"><div><div class="eyebrow">${safe(normalized)}</div><h2>${ct('proofTitle')}</h2></div><button class="icon-btn" type="button" data-close>×</button></div>
        <div class="notice-error">${safe(opsTr(error.message||'Proof of delivery not found'))}</div>
      </section></div>`;
      wireModal();
    }
  }

  function selectPodShipment(awb){
    const select=$('#proofAwb');if(!select||![...select.options].some(option=>option.value===awb))return toast(opsTr('لم نعثر على الشحنة'));
    select.value=awb;select.dispatchEvent(new Event('change',{bubbles:true}));$('.ops-pod-card')?.scrollIntoView({behavior:'smooth',block:'start'});
  }
  function pickupActionModal(number,action){
    const row=courierPickupRows().find(item=>item.pickup_number===number);if(!row)return toast(opsTr('لم نعثر على الطلب'));
    if(action==='assign'){
      const options=drivers.map(driver=>`<option value="${safe(driver.id)}" ${String(driver.id)===String(row.driver_id||'')?'selected':''}>${safe(driver.name)} · ${safe(driver.mobile||'')}</option>`).join('');
      $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal"><div class="modal-head"><div><div class="eyebrow">${safe(number)}</div><h2>${ct('assignCourier')}</h2></div><button class="icon-btn" data-close>×</button></div><form id="pickupActionForm" class="form-grid"><label class="field span-2"><span>${ct('driver')} *</span><select name="driver_id" required><option value="">—</option>${options}</select></label><label class="field span-2"><span>${ct('assignmentNote')}</span><textarea name="note"></textarea></label><div class="field span-2 ops-form-actions"><button type="button" class="btn light" data-close>${pt('close')}</button><button class="btn primary">${ct('assignCourier')}</button></div></form></section></div>`;
      wireModal();localizeNow($('#modalRoot'));const form=$('#pickupActionForm');form.onsubmit=async event=>{event.preventDefault();const data={status:'assigned',driver_id:Number(form.elements.driver_id.value),note:form.elements.note.value};try{await api(`/api/pickup-requests/${encodeURIComponent(number)}/status`,{method:'POST',body:JSON.stringify(data)});closeModal();toast(ct('pickupUpdated'));await refreshCourierTasks();}catch(error){toast(opsTr(error.message))}};return;
    }
    const nextStatus=action==='picked_up'?'picked_up':'completed';
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal" style="max-width:520px"><div class="modal-head"><div><div class="eyebrow">${safe(number)}</div><h2>${action==='picked_up'?ct('confirmPickup'):ct('completePickup')}</h2></div><button class="icon-btn" data-close>×</button></div><form id="pickupActionForm"><label class="field"><span>${ct('note')}</span><textarea name="note"></textarea></label><div class="ops-form-actions" style="margin-top:14px"><button type="button" class="btn light" data-close>${pt('close')}</button><button class="btn primary">✓ ${ct('updatePickup')}</button></div></form></section></div>`;
    wireModal();localizeNow($('#modalRoot'));const form=$('#pickupActionForm');form.onsubmit=async event=>{event.preventDefault();try{await api(`/api/pickup-requests/${encodeURIComponent(number)}/status`,{method:'POST',body:JSON.stringify({status:nextStatus,note:form.elements.note.value})});closeModal();toast(ct('pickupUpdated'));await refreshCourierTasks();}catch(error){toast(opsTr(error.message))}};
  }
  function proofLive(){
    const active=shipments.filter(s=>s.status!=='تم الاستلام');
    return `${head(`KSA · ${opsTr('تطبيق المندوب')}`,ct('operations'),ct('operationsSub'),`<button class="btn light" type="button" data-courier-refresh>↻ ${ct('refresh')}</button>`)}
      ${courierOperationsPanel()}
      <div class="section-title"><div><div class="eyebrow">GHAZALA POD</div><h2>${opsTr('إثبات التسليم الذكي (POD)')}</h2></div><span class="badge">${opsTr('خطوة إلزامية')}</span></div>
      <div class="card ops-pod-card"><div class="section-title" style="margin-top:0"><div><div class="eyebrow">${opsTr('الشحنة المطلوب تسليمها')}</div><h2>${opsTr('تأكيد التسليم بأمان')}</h2></div><span class="icon-square">✓</span></div>
      <form id="podForm" class="form-grid ops-form"><label class="field span-2"><span>${opsTr('رقم البوليصة')}</span><select id="proofAwb" required>${active.map(s=>`<option value="${safe(s.awb)}">${safe(s.awb)} · ${safe(s.recipient)} · ${opsTr(s.destination)}</option>`).join('')}</select></label>
      ${active.length?`<div class="field span-2 ops-recipient-card"><span>${opsTr('المستلم')}</span><b>${safe(active[0].recipient)}</b><small>${opsTr(active[0].origin)} → ${opsTr(active[0].destination)} · ${safe(active[0].eta)}</small></div>`:`<div class="field span-2 notice-ok">${opsTr('لا توجد شحنات بانتظار إثبات التسليم')}</div>`}
      <label class="field"><span>${opsTr('اسم المستلم الفعلي')} *</span><input id="receiverName" value="${safe(active[0]?.recipient||'')}" required></label><label class="field"><span>${opsTr('آخر 4 أرقام من الهوية')} *</span><input id="receiverId" inputmode="numeric" maxlength="4" pattern="[0-9]{4}" autocomplete="off" required></label>
      <div class="field span-2"><span>${opsTr('رمز التحقق OTP')} *</span><div class="ops-otp-row"><input id="otp" inputmode="numeric" maxlength="6" placeholder="000000" required><button type="button" id="sendOtp" class="btn light">${opsTr('إرسال رمز OTP إلى المستلم')}</button></div><small>${opsTr('في وضع العرض التجريبي يظهر الرمز هنا، وعند ربط SMS يصل إلى جوال المستلم.')}</small><div id="podSmsState" class="ops-sms-state" aria-live="polite"></div></div>
      <div class="field span-2"><div class="ops-label-line"><span>${opsTr('توقيع المستلم')} *</span><button type="button" class="link" id="clearSignature">${opsTr('مسح التوقيع')}</button></div><canvas id="signatureCanvas" class="ops-signature" aria-label="${opsTr('توقيع المستلم')}"></canvas></div>
      <div class="field span-2"><span>${opsTr('صورة الطرد عند باب المستلم')}</span><input id="podPhoto" type="file" accept="image/*" capture="environment" aria-label="${opsTr('صورة الطرد عند باب المستلم')}" hidden><button id="podPhotoButton" class="btn light" type="button" aria-describedby="podPhotoLabel">📷 <span id="podPhotoButtonLabel">${opsTr('التقاط أو اختيار صورة')}</span></button><small id="podPhotoLabel" aria-live="polite">${opsTr('لم يتم اختيار صورة')}</small></div>
      <div class="field span-2"><button type="button" class="btn light full" id="podGps">◎ ${opsTr('تحديد موقع التسليم عبر GPS')}</button><small>${opsTr('إحداثيات التسليم')}: <b id="podLocationLabel">${opsTr('لم يتم تحديد الموقع')}</b></small></div>
      <label class="field span-2"><span>${opsTr('ملاحظة التسليم')}</span><textarea id="podNote" placeholder="${opsTr('أضف ملاحظة اختيارية')}"></textarea></label>
      <div class="field span-2"><button type="submit" id="submitPod" class="btn primary full" ${active.length?'':'disabled'}>✓ ${opsTr('تأكيد التسليم وحفظ الإثبات')}</button></div></form></div>
      <div class="section-title"><h2>${opsTr('سجل المهام والطرود')}</h2></div><div class="shipment-grid">${shipments.map(shipmentCard).join('')}</div>`;
  }
  async function compressPhoto(file){
    if(file.size<=1_500_000)return await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)});
    const bitmap=await createImageBitmap(file),scale=Math.min(1,1400/Math.max(bitmap.width,bitmap.height)),canvas=document.createElement('canvas');canvas.width=Math.max(1,bitmap.width*scale);canvas.height=Math.max(1,bitmap.height*scale);canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close?.();return await new Promise(resolve=>canvas.toBlob(blob=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.readAsDataURL(blob)},'image/jpeg',.78));
  }
  const PUBLIC_TRACKING_EN={
    'تم إنشاء الشحنة':'Shipment Created','تم الإنشاء':'Created','قيد النقل':'In Transit',
    'جاهز للتسليم':'Ready for Delivery','في فرع الوجهة':'At Destination Branch',
    'قيد التوصيل':'Out for Delivery','تم الاستلام':'Delivered','تم التسليم':'Delivered',
    'تأخير':'Delayed','متأخرة':'Delayed','تم التحصيل عند التسليم':'Payment Collected on Delivery',
    'في الطريق':'In Transit','وصلت':'Arrived','مجدولة':'Scheduled','مطلوب متابعة':'Follow-up Required',
    'في الفرع':'At Branch','مندوب بالطريق':'Courier En Route',
    'لا يوجد رد':'No answer','المستلم غير متاح':'Recipient unavailable',
    'العنوان غير صحيح أو غير مكتمل':'Wrong or incomplete address',
    'رفض المستلم الشحنة':'Recipient refused shipment','مشكلة في الدفع أو التحصيل':'Payment or COD issue',
    'تعذر الوصول إلى موقع التسليم':'Could not access delivery location',
    'مشكلة في حالة الطرد':'Parcel condition issue','سبب آخر':'Other'
  };
  function publicTrackingText(value){
    const raw=String(value??'').trim();
    if(!raw)return '';
    if(currentLang!=='en')return opsTr(raw);
    if(PUBLIC_TRACKING_EN[raw])return PUBLIC_TRACKING_EN[raw];
    let match=raw.match(/^محاولة تسليم رقم\s*(\d+)$/);
    if(match)return `Delivery Attempt #${match[1]}`;
    match=raw.match(/^محاولة تسليم فاشلة\s*·\s*(.+)$/);
    if(match)return `Failed Delivery Attempt · ${publicTrackingText(match[1])}`;
    match=raw.match(/^تم تحميل الشحنة على الرحلة\s+(.+)$/);
    if(match)return `Loaded onto Route ${match[1]}`;
    match=raw.match(/^تم المسح وتحميلها على الرحلة\s+(.+)$/);
    if(match)return `Scanned and Loaded onto Route ${match[1]}`;
    match=raw.match(/^تحديث الدفع\s*·\s*(.+)$/);
    if(match)return `Payment Update · ${match[1]}`;
    match=raw.match(/^(في الطريق|وصلت|مجدولة)\s*·\s*(.+)$/);
    if(match)return `${publicTrackingText(match[1])} · ${match[2]}`;
    match=raw.match(/^فرع\s+(.+)$/);
    if(match)return `${opsTr(match[1])} Branch`;
    return opsTr(raw).replace(/ر\.س/g,'SAR');
  }
  function publicTrackingLabel(key){
    const labels={
      deliveredAt:{ar:'تم التسليم في',en:'Delivered at',ur:'ڈیلیور ہوا',hi:'डिलीवर हुआ',bn:'ডেলিভার করা হয়েছে'},
      deliveryLocation:{ar:'موقع التسليم',en:'Delivery Location',ur:'ڈیلیوری لوکیشن',hi:'डिलीवरी स्थान',bn:'ডেলিভারি লোকেশন'},
      eta:{ar:'وقت الوصول المتوقع ETA',en:'Estimated Arrival (ETA)',ur:'متوقعہ آمد (ETA)',hi:'अनुमानित आगमन (ETA)',bn:'আনুমানিক পৌঁছানোর সময় (ETA)'},
      nextAttempt:{ar:'موعد محاولة التسليم القادمة',en:'Next Delivery Attempt',ur:'اگلی ڈیلیوری کوشش',hi:'अगला डिलीवरी प्रयास',bn:'পরবর্তী ডেলিভারি প্রচেষ্টা'},
      exceptionTitle:{ar:'تعذر التسليم',en:'Delivery Exception',ur:'ڈیلیوری میں رکاوٹ',hi:'डिलीवरी अपवाद',bn:'ডেলিভারি ব্যতিক্রম'},
      attemptNumber:{ar:'رقم المحاولة',en:'Attempt',ur:'کوشش',hi:'प्रयास',bn:'প্রচেষ্টা'},
      failureReason:{ar:'سبب تعذر التسليم',en:'Reason',ur:'وجہ',hi:'कारण',bn:'কারণ'},
      failureDetails:{ar:'تفاصيل السبب',en:'Reason Details',ur:'وجہ کی تفصیل',hi:'कारण का विवरण',bn:'কারণের বিস্তারিত'}
    };
    return labels[key]?.[currentLang]||labels[key]?.en||key;
  }
  function publicFailureReasonFromCode(code){
    const labels={
      no_answer:{ar:'لا يوجد رد',en:'No answer'},recipient_unavailable:{ar:'المستلم غير متاح',en:'Recipient unavailable'},
      wrong_address:{ar:'العنوان غير صحيح أو غير مكتمل',en:'Wrong or incomplete address'},refused:{ar:'رفض المستلم الشحنة',en:'Recipient refused shipment'},
      payment_issue:{ar:'مشكلة في الدفع أو التحصيل',en:'Payment or COD issue'},access_issue:{ar:'تعذر الوصول إلى موقع التسليم',en:'Could not access delivery location'},
      damaged:{ar:'مشكلة في حالة الطرد',en:'Parcel condition issue'},other:{ar:'سبب آخر',en:'Other'}
    };
    const row=labels[String(code||'').trim()];
    if(!row)return '';
    return currentLang==='ar'?row.ar:row.en;
  }
  function publicTrackingTime(value){
    if(!value)return '—';
    try{return typeof saDate==='function'?saDate(value):String(value)}catch(_){return String(value)}
  }
  async function searchPublic(input,target){
    if(!input||!target)return;
    const requestId=String(++state.publicRequestSequence);target.dataset.trackingRequest=requestId;
    target.innerHTML='<p class="ops-loading">'+opsTr('جارٍ جلب آخر تحديث…')+'</p>';
    const numbers=[...new Set(String(input).split(/[\s,;]+/).map(x=>x.trim().toUpperCase()).filter(Boolean))];
    const cards=await Promise.all(numbers.map(async awb=>{
      try{
        const d=await api('/api/public/tracking/'+encodeURIComponent(awb));
        const delivered=Boolean(d.is_delivered)||['تم الاستلام','delivered'].includes(String(d.status||'').toLowerCase());
        const locationLabel=delivered?publicTrackingLabel('deliveryLocation'):opsTr('الموقع التشغيلي الحالي');
        const timing=delivered
          ?publicTrackingLabel('deliveredAt')+': '+safe(publicTrackingTime(d.delivered_at))
          :(!d.next_attempt_at?publicTrackingLabel('eta')+': '+safe(publicTrackingText(d.eta||'—')):'');
        const nextAttempt=(!delivered&&d.next_attempt_at)
          ?'<small><b>'+safe(publicTrackingLabel('nextAttempt'))+':</b> '+safe(publicTrackingTime(d.next_attempt_at))+'</small>'
          :'';
        const failureReason=publicFailureReasonFromCode(d.failure_reason_code);
        const exception=(!delivered&&(d.next_attempt_at||d.failure_reason_code||d.failure_reason_text))
          ?'<div class="ops-location" style="border-color:rgba(234,88,12,.25);background:rgba(255,247,237,.78)"><b>⚠ '+safe(publicTrackingLabel('exceptionTitle'))+'</b>'+
            (d.failed_attempt_number?'<span><b>'+safe(publicTrackingLabel('attemptNumber'))+':</b> #'+safe(d.failed_attempt_number)+'</span>':'')+
            (failureReason?'<span><b>'+safe(publicTrackingLabel('failureReason'))+':</b> '+safe(failureReason)+'</span>':'')+
            (d.failure_reason_text?'<span><b>'+safe(publicTrackingLabel('failureDetails'))+':</b> '+safe(d.failure_reason_text)+'</span>':'')+
            nextAttempt+'</div>'
          :'';
        const timeline=((d.events||[]).slice().reverse().map(ev=>'<div class="timeline-row"><div class="timeline-dot">✓</div><div class="timeline-text"><b>'+safe(publicTrackingText(ev.stage||ev.status))+'</b><small>'+safe(publicTrackingText(ev.status))+' · '+safe(publicTrackingText(ev.location))+' · '+safe(publicTrackingTime(ev.created_at))+'</small></div></div>').join('')||'<div class="timeline-row"><div class="timeline-dot">•</div><div class="timeline-text"><b>'+safe(publicTrackingText(d.status))+'</b><small>'+safe(publicTrackingText(d.stage))+' · '+safe(publicTrackingText(d.current_location))+'</small></div></div>');
        return '<article class="ops-tracking-result"><header><div><span class="eyebrow">'+opsTr('حالة الشحنة')+'</span><h3>'+safe(d.awb)+'</h3></div>'+badge(d.status)+'</header><div class="ops-track-route"><div><small>'+opsTr('من')+'</small><b>'+safe(opsTr(d.origin))+'</b></div><span>⇄</span><div><small>'+opsTr('إلى')+'</small><b>'+safe(opsTr(d.destination))+'</b></div></div><div class="ops-location"><b>◎ '+locationLabel+'</b><span>'+safe(publicTrackingText(d.current_location))+'</span>'+(timing?'<small>'+timing+'</small>':'')+'</div>'+exception+'<div class="timeline">'+timeline+'</div></article>';
      }catch(e){return '<div class="notice-error">'+safe(awb)+' · '+opsTr('لم نعثر على شحنة بهذا الرقم. تحقق من رقم البوليصة وحاول مرة أخرى.')+'</div>'}
    }));
    if(target.isConnected===false||target.dataset.trackingRequest!==requestId)return;
    target.innerHTML=cards.join('');localizeNow(target);fixResidualOpsLanguage(target);
  }
  function syncRouteShipments(){const f=$('#routeForm');if(!f)return;const o=f.elements.origin.value,d=f.elements.destination.value,rows=$$('[data-route-awb]',f);rows.forEach(row=>{row.hidden=row.dataset.origin!==o||row.dataset.destination!==d||row.dataset.assigned==='1';const checkbox=$('input[type="checkbox"]',row);checkbox.disabled=row.hidden;if(row.hidden)checkbox.checked=false});const available=rows.filter(row=>!row.hidden),notice=$('#routeShipmentNotice',f),submit=$('button[type="submit"]',f);if(notice)notice.hidden=available.length>0;if(submit)submit.disabled=available.length===0}
  function routePrerequisiteModal(){const noShipments=!shipments.length,missing=[!drivers.length&&opsTr('أضف سائقاً للرحلة أولاً'),!state.vehicles.length&&opsTr('أضف مركبة إلى الأسطول أولاً'),noShipments&&opsTr('أنشئ شحنة واحدة على الأقل قبل جدولة الرحلة')].filter(Boolean);$('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal" style="max-width:500px"><div class="modal-head"><h2>${opsTr('قبل جدولة الرحلة')}</h2><button class="icon-btn" data-close>×</button></div><p>${missing.join('<br>')}</p><div class="ops-inline-actions">${!drivers.length?`<button class="btn primary" data-action="driver">＋ ${opsTr('إضافة سائق')}</button>`:''}${!state.vehicles.length?`<button class="btn primary" data-action="vehicle">＋ ${opsTr('إضافة مركبة')}</button>`:''}${noShipments?`<button class="btn accent" data-action="create">＋ ${opsTr('إنشاء شحنة')}</button>`:''}</div></section></div>`;wireModal();localizeNow($('#modalRoot'));$$('[data-action]',$('#modalRoot')).forEach(b=>b.onclick=()=>window.action(b.dataset.action,b))}
  async function routeCreateModal(){if(!requirePermission('routes.manage'))return;$('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section id="routeLoading" class="modal" style="max-width:420px"><div class="modal-head"><h2>${opsTr('جدولة رحلة نقل')}</h2><button class="icon-btn" data-close>×</button></div><p class="ops-loading">${opsTr('جارٍ تجهيز بيانات الرحلة…')}</p></section></div>`;wireModal();localizeNow($('#modalRoot'));if(state.busy&&state.pending)await state.pending;else if(!state.last)await refreshOps(true);if(!$('#routeLoading'))return;if(state.lastError&&!state.last)throw new Error('تعذر تحميل بيانات الرحلة. تحقق من الاتصال وسجّل الدخول مجدداً.');if(cityNames().length<2)return toast(opsTr('يجب إضافة مدينتين نشطتين على الأقل قبل جدولة رحلة'));if(!state.vehicles.length||!drivers.length||!shipments.length)return routePrerequisiteModal();
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal"><div class="modal-head"><div><div class="eyebrow">${opsTr('النقل بين الفروع')}</div><h2>${opsTr('جدولة رحلة نقل')}</h2></div><button class="icon-btn" data-close>×</button></div><form id="routeForm" class="form-grid ops-form">
      <label class="field"><span>${opsTr('من مدينة')}</span><select name="origin">${cityOptionMarkup(cityNames()[0])}</select></label><label class="field"><span>${opsTr('إلى مدينة')}</span><select name="destination">${cityOptionMarkup(otherCity(cityNames()[0]))}</select></label>
      <label class="field"><span>${opsTr('موعد الانطلاق')}</span><input name="departure_at" type="datetime-local" value="${localDT(2)}" required></label><label class="field"><span>${opsTr('السائق')}</span><select name="driver_id" required>${drivers.map(d=>`<option value="${d.id}">${safe(d.name)} · ${safe(d.mobile)}</option>`).join('')}</select></label>
      <label class="field"><span>${opsTr('مركبة النقل')}</span><select name="vehicle_id">${state.vehicles.map(v=>`<option value="${v.id}" data-capacity="${safe(v.capacity_kg)}">${safe(v.plate)} · ${safe(v.vehicle_type)} (${fmt(v.capacity_kg)} ${opsTr('كجم')})</option>`).join('')}</select></label><label class="field"><span>${opsTr('سعة الحمولة (كجم)')}</span><input name="capacity_kg" type="number" min="1" value="${safe(state.vehicles[0].capacity_kg)}" readonly></label>
      <label class="field"><span>${opsTr('تنبيه الفرع قبل الانطلاق (دقيقة)')}</span><input name="notification_minutes" type="number" min="0" value="30"></label><div class="field span-2"><b>${opsTr('اختر الشحنات المطابقة للمسار')}</b><small>${opsTr('اختر شحنة واحدة على الأقل لإضافتها إلى الرحلة.')}</small><div id="routeShipmentNotice" class="notice-error" hidden>${opsTr('لا توجد شحنات متاحة لهذا الاتجاه. غيّر الاتجاه أو أنشئ شحنة جديدة.')}</div><div class="ops-check-list">${shipments.filter(s=>s.status!=='تم الاستلام').map(s=>`<label data-route-awb data-origin="${safe(s.origin)}" data-destination="${safe(s.destination)}" data-assigned="${state.routes.some(r=>['مجدولة','في الطريق'].includes(r.status)&&r.shipments.some(x=>x.awb===s.awb))?'1':'0'}" class="ops-awb-check"><input type="checkbox" name="awbs" value="${safe(s.awb)}"><span><b>${safe(s.awb)}</b> · ${safe(s.recipient)}</span><small>${opsTr(s.origin)} → ${opsTr(s.destination)} · ${fmt(s.weight)} ${opsTr('كجم')}</small></label>`).join('')||`<p>${opsTr('لا توجد شحنات')}</p>`}</div></div><div class="field span-2"><button type="submit" class="btn primary full">${opsTr('إنشاء الرحلة وإسناد الشحنات')}</button></div></form></section></div>`;
    wireModal();localizeNow($('#modalRoot'));const f=$('#routeForm'),vehicleSelect=f.elements.vehicle_id,capacityInput=f.elements.capacity_kg;vehicleSelect.onchange=()=>{const selected=vehicleSelect.selectedOptions[0];capacityInput.value=selected?.dataset.capacity||''};f.elements.origin.onchange=()=>{if(f.elements.origin.value===f.elements.destination.value)f.elements.destination.value=otherCity(f.elements.origin.value);syncRouteShipments()};f.elements.destination.onchange=()=>{if(f.elements.origin.value===f.elements.destination.value)f.elements.origin.value=otherCity(f.elements.destination.value);syncRouteShipments()};syncRouteShipments();
    f.onsubmit=async e=>{e.preventDefault();const formData=new FormData(f),data=Object.fromEntries(formData);data.awbs=formData.getAll('awbs');if(!data.awbs.length)return toast(opsTr('اختر شحنة واحدة على الأقل لإضافتها إلى الرحلة.'));data.driver_id=data.driver_id||null;data.vehicle_id=Number(data.vehicle_id);data.capacity_kg=Number(data.capacity_kg);data.notification_minutes=Number(data.notification_minutes);try{const r=await api('/api/routes',{method:'POST',body:JSON.stringify(data)});closeModal();toast(`${opsTr('تم إنشاء الرحلة')} ${r.code}`);state.last=0;await refreshOps(true)}catch(err){toast(opsTr(err.message))}};
  }
  function transferBranches(){return (user?.branch_ids||user?.branches?.map(b=>b.id)||[]).map(String)}
  function transferGlobal(){return accessRole()==='system_admin'&&user?.global_scope===true}
  function transferRows(direction){
    if(!hasPermission('routes.read')||accessRole()==='customer')return [];
    const branches=transferBranches();
    return state.routes.flatMap(route=>(route.shipments||[]).filter(shipment=>['planned','in_transit','awaiting_receipt','received','cancelled'].includes(shipment.transfer_status)).map(shipment=>({route,shipment}))).filter(({route,shipment})=>{
      if(transferGlobal())return true;
      if(direction==='incoming')return branches.includes(String(shipment.receiving_branch_id));
      // A transfer between two assigned offices belongs in both scoped lists.
      return branches.includes(String(shipment.origin_branch_id));
    });
  }
  function transferLabel(status){return opsTr(({planned:'بانتظار الإرسال',in_transit:'قيد النقل',awaiting_receipt:'بانتظار تأكيد الفرع المستلم',received:'تم تأكيد استلام الفرع',cancelled:'ملغاة'})[status]||status)}
  function transferBranchName(id){return [...state.branchDirectory,...state.branches,...(user?.branches||[])].find(b=>String(b.id)===String(id))?.name||`${opsTr('الفرع')} #${id}`}
  function transferCustody(route,shipment){
    if(shipment.transfer_status==='received')return `${opsTr('تم تسليم العهدة إلى الفرع')}: ${transferBranchName(shipment.receiving_branch_id)}`;
    if(['in_transit','awaiting_receipt'].includes(shipment.transfer_status))return `${opsTr('عهدة النقل')}: ${route.driver_name||opsTr('غير معيّن')} · ${route.vehicle_plate||'—'}`;
    return shipment.transfer_status==='planned'?`${opsTr('بانتظار الإرسال')} · ${opsTr(route.origin)}`:opsTr('تم إلغاء التحويل');
  }
  function canReceiveTransfer(route,shipment){return !!user&&hasPermission('routes.read')&&hasPermission('shipments.status')&&['system_admin','branch_manager','office_employee'].includes(accessRole())&&(transferGlobal()||transferBranches().includes(String(shipment.receiving_branch_id)))&&route.status==='وصلت'&&shipment.transfer_status==='awaiting_receipt'}
  function canDispatchTransfer(route,shipment){return hasPermission('routes.read')&&hasPermission('routes.manage')&&route.status==='مجدولة'&&shipment.transfer_status==='planned'}
  function transferButtons(route,shipment){return `${canDispatchTransfer(route,shipment)?`<button class="btn primary small" data-transfer-dispatch="${safe(route.id)}">${opsTr('بدء الرحلة')}</button>`:''}${canReceiveTransfer(route,shipment)?`<button class="btn primary small" data-route-receive="${safe(route.id)}" data-receive-awb="${safe(shipment.awb)}">${opsTr('تأكيد استلام الشحنة')}</button>`:''}`}
  function transferPanel(){
    if(!hasPermission('routes.read')||accessRole()==='customer')return '';
    const rows=transferRows(state.transferView),receivable=transferRows('incoming').some(({route,shipment})=>canReceiveTransfer(route,shipment));
    return `<div class="section-title"><h2>${opsTr('تحويلات الشحنات')}</h2>${receivable?`<button class="btn primary small" data-transfer-receive-scan>▦ ${opsTr('مسح بوليصة للاستلام')}</button>`:''}</div><div class="tabs" role="tablist">${[['incoming','التحويلات الواردة'],['outgoing','التحويلات الصادرة']].map(([id,label])=>`<button class="tab ${state.transferView===id?'active':''}" role="tab" aria-selected="${state.transferView===id}" data-transfer-view="${id}">${opsTr(label)} (${transferRows(id).length})</button>`).join('')}</div><div class="ops-route-list">${rows.map(({route,shipment})=>`<article class="card ops-route-card"><header><div><span class="badge ${shipment.transfer_status==='received'?'green':shipment.transfer_status==='in_transit'?'blue':''}">${transferLabel(shipment.transfer_status)}</span><h3>${safe(shipment.awb)}</h3></div><span>${safe(route.code)}</span></header><div class="ops-route-info"><span>${safe(opsTr(route.origin))} → ${safe(opsTr(route.destination))}</span><span>${opsTr('الفرع المرسل')}: <b>${safe(transferBranchName(shipment.origin_branch_id))}</b></span><span>${opsTr('الفرع المستلم')}: <b>${safe(transferBranchName(shipment.receiving_branch_id))}</b></span><span>${safe(transferCustody(route,shipment))}</span></div><div class="ops-route-actions"><button class="btn light small" data-transfer-detail="${safe(route.id)}" data-transfer-awb="${safe(shipment.awb)}">${opsTr('تفاصيل التحويل')}</button>${transferButtons(route,shipment)}</div></article>`).join('')||`<div class="card empty">${opsTr('لا توجد تحويلات ضمن نطاقك')}</div>`}</div>`;
  }
  function normalizeTransferAwb(value){return String(value||'').trim().toUpperCase().match(/(?:^|[/?#=&\s])(GHZ-[A-Z0-9-]+)(?=$|[/?#=&\s])/)?.[1]||''}
  function findTransfer(routeId,awb){
    if(!hasPermission('routes.read')||accessRole()==='customer')return null;
    const route=state.routes.find(r=>String(r.id)===String(routeId)),shipment=route?.shipments?.find(s=>s.awb===awb&&s.transfer_status);
    return route&&shipment?{route,shipment}:null;
  }
  function stopTransferCamera(){const camera=state.transferCamera;state.transferCamera=null;if(camera){camera.cancelled=true;camera.stream?.getTracks().forEach(track=>track.stop());if(camera.timer)clearTimeout(camera.timer);if(camera.video)camera.video.srcObject=null}}
  function wireTransferModal(){
    wireModal();const root=$('#modalRoot');localizeNow(root);bindTransferControls(root);
    $$('[data-close]',root).forEach(b=>b.onclick=e=>{if(e.target===b||b.tagName==='BUTTON'){stopTransferCamera();closeModal()}});
  }
  function transferHistoryMarkup(events){return `<div class="timeline">${events.map(ev=>`<div class="timeline-row"><div class="timeline-dot">•</div><div class="timeline-text"><b>${safe(opsTr(ev.stage||ev.status||''))}</b><small>${safe(opsTr(ev.status||''))} · ${safe(opsTr(ev.location||''))} · ${safe(ev.created_at||'')}</small></div></div>`).join('')||`<p>${opsTr('لا يوجد سجل متاح')}</p>`}</div>`}
  async function openTransferDetail(routeId,awb){
    const entry=findTransfer(routeId,awb);if(!entry)return;
    stopTransferCamera();const {route,shipment}=entry,root=$('#modalRoot'),owner=opsOwnerKey(),revision=state.ownerRevision;
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal"><div class="modal-head"><div><div class="eyebrow">${opsTr('تفاصيل التحويل')} · ${safe(route.code)}</div><h2>${safe(awb)}</h2></div><button class="icon-btn" data-close>×</button></div><div class="ops-route-info"><span>${safe(opsTr(route.origin))} → ${safe(opsTr(route.destination))}</span><span>${opsTr('الفرع المرسل')}: <b>${safe(transferBranchName(shipment.origin_branch_id))}</b></span><span>${opsTr('الفرع المستلم')}: <b>${safe(transferBranchName(shipment.receiving_branch_id))}</b></span><span>${opsTr('حالة التحويل')}: <b>${transferLabel(shipment.transfer_status)}</b></span><span>${opsTr('حالة الشحنة')}: <b>${safe(opsTr(shipment.status))}</b></span><span>${opsTr('عهدة التحويل')}: <b>${safe(transferCustody(route,shipment))}</b></span>${shipment.received_by!=null?`<span>${opsTr('تأكيد الاستلام بواسطة')}: <b>${safe(shipment.received_by_name||opsTr('المستخدم'))} · #${safe(shipment.received_by)}</b></span>`:''}</div>${shipment.transfer_status==='awaiting_receipt'?`<p class="notice-error">${opsTr('وصول المركبة لا يؤكد استلام الشحنة. يلزم تأكيد الفرع المستلم لكل بوليصة.')}</p>`:''}<div class="timeline">${[[opsTr('بدء الرحلة'),route.started_at],[opsTr('تأكيد الوصول'),route.arrived_at],[opsTr('تم تأكيد استلام الفرع'),shipment.received_at]].filter(([,at])=>at).map(([label,at])=>`<div class="timeline-row"><div class="timeline-dot">✓</div><div class="timeline-text"><b>${label}</b><small>${safe(at)}</small></div></div>`).join('')}</div><div class="ops-inline-actions">${transferButtons(route,shipment)}${canReceiveTransfer(route,shipment)?`<button class="btn light small" data-transfer-receive-scan="${safe(route.id)}">▦ ${opsTr('مسح بوليصة للاستلام')}</button>`:''}</div><div class="section-title"><h3>${opsTr('سجل الشحنة')}</h3></div><div id="transferHistory">${opsTr('جاري تحميل السجل')}</div></section></div>`;
    wireTransferModal();const history=$('#transferHistory',root);
    const current=()=>opsOwnerKey()===owner&&state.ownerRevision===revision&&history?.isConnected;
    if(!hasPermission('shipments.read')){history.textContent=opsTr('لا يوجد سجل متاح');return}
    try{const rows=await api(`/api/shipments?q=${encodeURIComponent(awb)}`);if(current()){const full=rows.find(s=>s.awb===awb);history.innerHTML=transferHistoryMarkup(full?.events||[]);localizeNow(history)}}
    catch(e){if(current())history.textContent=opsTr('تعذر تحميل السجل')}
  }
  async function confirmTransferReceipt(routeId,value){
    const awb=normalizeTransferAwb(value),entry=findTransfer(routeId,awb);
    if(!entry||!canReceiveTransfer(entry.route,entry.shipment)){toast(opsTr('لا توجد شحنة بانتظار الاستلام في فروعك'));return false}
    const owner=opsOwnerKey(),revision=state.ownerRevision,key=`${owner}:${routeId}:${awb}`,pending=state.transferPending;
    if(pending.has(key))return false;pending.add(key);
    const current=()=>opsOwnerKey()===owner&&state.ownerRevision===revision;
    try{
      const receipt=await api(`/api/routes/${routeId}/receive`,{method:'POST',body:JSON.stringify({awb})});
      if(!current())return false;
      // Invalidate the local parcel immediately after the server confirms receipt.
      Object.assign(entry.shipment,{transfer_status:'received',received_at:receipt.received_at??null,received_by:receipt.received_by??null,received_by_name:receipt.received_by_name??null});state.last=0;await refreshOps(true);
      if(!current())return false;await load();if(!current())return false;
      toast(opsTr('تم تأكيد استلام الفرع'));return true;
    }catch(e){if(current())toast(opsTr(e.message));return false}finally{pending.delete(key)}
  }
  function promptTransferReceiveScan(routeId=''){
    const eligible=()=>transferRows('incoming').filter(({route,shipment})=>(!routeId||String(route.id)===String(routeId))&&canReceiveTransfer(route,shipment));
    if(!eligible().length)return toast(opsTr('لا توجد شحنة بانتظار الاستلام في فروعك'));
    stopTransferCamera();const root=$('#modalRoot'),owner=opsOwnerKey(),revision=state.ownerRevision;
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal"><div class="modal-head"><h2>${opsTr('مسح بوليصة للاستلام')}</h2><button class="icon-btn" data-close>×</button></div><p>${opsTr('المسح يؤكد استلام بوليصة واحدة في الفرع المستلم.')}</p><form id="transferReceiveForm"><label class="field"><span>${opsTr('رقم البوليصة')}</span><input name="awb" placeholder="GHZ-000125" autocomplete="off" required autofocus></label><button class="btn primary full" type="submit">${opsTr('تأكيد استلام الشحنة')}</button></form><p id="transferReceiveResult" role="status" aria-live="polite"></p><button class="btn light full" type="button" id="transferReceiveCamera">◉ ${opsTr('استخدام الكاميرا لمسح الباركود')}</button><video id="transferReceiveVideo" playsinline muted hidden></video></section></div>`;
    wireTransferModal();const form=$('#transferReceiveForm',root),result=$('#transferReceiveResult',root),submit=$('button[type="submit"]',form);
    form.elements.awb.focus();let busy=false;
    const current=()=>opsOwnerKey()===owner&&state.ownerRevision===revision&&form.isConnected;
    form.onsubmit=async e=>{
      e.preventDefault();if(busy||!current())return;
      const awb=normalizeTransferAwb(form.elements.awb.value),entry=eligible().find(item=>item.shipment.awb===awb);
      if(!entry){result.textContent=opsTr('لا توجد شحنة بانتظار الاستلام في فروعك');return}
      busy=true;submit.disabled=true;stopTransferCamera();
      try{const received=await confirmTransferReceipt(entry.route.id,awb);if(current()){result.textContent=received?`${awb} · ${opsTr('تم تأكيد استلام الفرع')}`:opsTr('تعذر تأكيد الاستلام');if(received)form.reset();form.elements.awb.focus()}}
      finally{busy=false;if(current())submit.disabled=false}
    };
    $('#transferReceiveCamera',root).onclick=()=>startTransferReceiveCamera(form);
  }
  async function startTransferReceiveCamera(form){
    if(!('BarcodeDetector' in window)||!navigator.mediaDevices?.getUserMedia)return toast(opsTr('المتصفح لا يدعم المسح بالكاميرا. استخدم رقم البوليصة.'));
    stopTransferCamera();const camera={cancelled:false,stream:null,video:$('#transferReceiveVideo'),owner:opsOwnerKey(),revision:state.ownerRevision,timer:null};state.transferCamera=camera;
    const current=()=>!camera.cancelled&&state.transferCamera===camera&&opsOwnerKey()===camera.owner&&state.ownerRevision===camera.revision&&form.isConnected;
    try{
      const detector=new BarcodeDetector({formats:['code_128','qr_code']}),stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});
      if(!current()){stream.getTracks().forEach(track=>track.stop());return}
      camera.stream=stream;camera.video.srcObject=stream;camera.video.hidden=false;await camera.video.play();
      const tick=async()=>{
        if(!current()){if(state.transferCamera===camera)stopTransferCamera();return}
        try{const codes=await detector.detect(camera.video);if(!current()){if(state.transferCamera===camera)stopTransferCamera();return}
          const awb=codes.map(code=>normalizeTransferAwb(code.rawValue)).find(Boolean);
          if(awb){stopTransferCamera();form.elements.awb.value=awb;form.requestSubmit();return}
          camera.timer=setTimeout(tick,350);
        }catch(e){if(state.transferCamera===camera){stopTransferCamera();toast(opsTr('تعذر تشغيل الكاميرا'))}}
      };await tick();
    }catch(e){if(state.transferCamera===camera){stopTransferCamera();toast(opsTr('تعذر تشغيل الكاميرا'))}}
  }
  function bindTransferControls(root){
    $$('[data-transfer-view]',root).forEach(b=>b.onclick=()=>{if(['incoming','outgoing'].includes(b.dataset.transferView)){state.transferView=b.dataset.transferView;render()}});
    $$('[data-transfer-detail]',root).forEach(b=>b.onclick=()=>openTransferDetail(b.dataset.transferDetail,b.dataset.transferAwb));
    $$('[data-transfer-receive-scan]',root).forEach(b=>b.onclick=()=>promptTransferReceiveScan(b.dataset.transferReceiveScan));
    $$('[data-transfer-dispatch]',root).forEach(b=>b.onclick=async()=>{
      const entry=state.routes.find(r=>String(r.id)===b.dataset.transferDispatch);
      if(!entry?.shipments?.some(s=>canDispatchTransfer(entry,s)))return;
      b.disabled=true;try{await routeStatus(entry.id,'في الطريق');if(b.isConnected&&state.routes.some(r=>String(r.id)===String(entry.id)&&r.status==='في الطريق'))closeModal()}finally{if(b.isConnected)b.disabled=false}
    });
    $$('[data-route-receive]',root).forEach(b=>b.onclick=async()=>{
      b.disabled=true;try{if(await confirmTransferReceipt(b.dataset.routeReceive,b.dataset.receiveAwb)){
        const detail=$('#transferHistory');if(detail?.isConnected)await openTransferDetail(b.dataset.routeReceive,b.dataset.receiveAwb);
      }}finally{if(b.isConnected)b.disabled=false}
    });
  }
  function routeTransferParcel(route,shipment){
    const pending=shipment.transfer_status==='awaiting_receipt',received=shipment.transfer_status==='received';
    return `<span>${safe(shipment.awb)}${pending?` · ${opsTr('بانتظار تأكيد الفرع المستلم')}`:received?` · ${opsTr('تم تأكيد استلام الفرع')}`:''}</span>${shipment.transfer_status?`<button class="btn light small" data-transfer-detail="${safe(route.id)}" data-transfer-awb="${safe(shipment.awb)}">${opsTr('تفاصيل التحويل')}</button>`:''}${canReceiveTransfer(route,shipment)?`<button class="btn primary small" data-route-receive="${safe(route.id)}" data-receive-awb="${safe(shipment.awb)}">${opsTr('تأكيد استلام الشحنة')}</button>`:''}`;
  }
  function routeCard(r){const canManage=hasPermission('routes.manage');return `<article class="card ops-route-card" data-route-code="${safe(r.code)}"><header><div><span class="badge ${r.status==='في الطريق'?'blue':r.status==='وصلت'?'green':''}">${opsTr(r.status)}</span><h3>${safe(r.code)}</h3></div><span class="ops-route-icon">⇄</span></header><div class="ops-track-route"><div><small>${opsTr('من')}</small><b>${opsTr(r.origin)}</b></div><span>→</span><div><small>${opsTr('إلى')}</small><b>${opsTr(r.destination)}</b></div></div><div class="ops-route-info"><span>♙ ${opsTr('السائق')}: <b>${safe(r.driver_name||opsTr('غير معيّن'))}</b></span><span>▣ ${opsTr('المركبة')}: <b>${safe(r.vehicle_plate||'—')}</b></span><span>◷ ${opsTr('موعد الانطلاق')}: <b>${safe(r.departure_at)}</b></span><span>▤ ${opsTr('الحمولة')}: <b>${fmt(r.load_kg)} / ${fmt(r.capacity_kg)} ${opsTr('كجم')}</b></span></div><div class="ops-capacity"><i style="width:${Math.min(100,r.capacity_kg?100*r.load_kg/r.capacity_kg:0)}%"></i></div><div class="ops-route-parcels">${(r.shipments||[]).map(s=>routeTransferParcel(r,s)).join('')||opsTr('لم تتم إضافة شحنات')}</div><div class="ops-route-actions">${canManage?`<button class="btn light small" data-route-scan="${r.id}">▦ ${opsTr('مسح / إضافة بوليصة')}</button>`:''}<button class="btn light small" data-route-manifest="${r.id}">▤ ${opsTr('كشف الحمولة')}</button>${canManage?(r.status==='مجدولة'?`<button class="btn primary small" data-route-status="${r.id}" data-status-value="في الطريق">${opsTr('بدء الرحلة')}</button><button class="btn danger small" data-route-status="${r.id}" data-status-value="ملغاة">${opsTr('إلغاء الرحلة')}</button>`:r.status==='في الطريق'?`<button class="btn primary small" data-route-status="${r.id}" data-status-value="وصلت">${opsTr('تأكيد الوصول')}</button>`:''):''}</div></article>`}
  const BRANCH_UI={
    manage:{ar:'إدارة الفروع',en:'Manage Branches',ur:'برانچز مینیج کریں',hi:'शाखाएँ प्रबंधित करें',bn:'শাখা পরিচালনা'},
    registry:{ar:'دليل الفروع والمكاتب',en:'Branch & Office Registry',ur:'برانچ اور آفس رجسٹری',hi:'शाखा और कार्यालय रजिस्ट्री',bn:'শাখা ও অফিস রেজিস্ট্রি'},
    registrySub:{ar:'تعديل بيانات الفروع وتفعيلها أو إيقافها بأمان.',en:'Edit branch details and safely activate or deactivate offices.',ur:'برانچ کی تفصیلات تبدیل کریں اور محفوظ طریقے سے فعال یا غیر فعال کریں۔',hi:'शाखा विवरण संपादित करें और सुरक्षित रूप से सक्रिय या निष्क्रिय करें।',bn:'শাখার তথ্য সম্পাদনা করুন এবং নিরাপদে সক্রিয় বা নিষ্ক্রিয় করুন।'},
    add:{ar:'إضافة فرع جديد',en:'Add New Branch',ur:'نئی برانچ شامل کریں',hi:'नई शाखा जोड़ें',bn:'নতুন শাখা যোগ করুন'},
    edit:{ar:'تعديل الفرع',en:'Edit Branch',ur:'برانچ میں ترمیم',hi:'शाखा संपादित करें',bn:'শাখা সম্পাদনা'},
    active:{ar:'نشط',en:'Active',ur:'فعال',hi:'सक्रिय',bn:'সক্রিয়'},
    inactive:{ar:'موقوف',en:'Inactive',ur:'غیر فعال',hi:'निष्क्रिय',bn:'নিষ্ক্রিয়'},
    activate:{ar:'تفعيل',en:'Activate',ur:'فعال کریں',hi:'सक्रिय करें',bn:'সক্রিয় করুন'},
    deactivate:{ar:'إيقاف',en:'Deactivate',ur:'غیر فعال کریں',hi:'निष्क्रिय करें',bn:'নিষ্ক্রিয় করুন'},
    save:{ar:'حفظ التعديلات',en:'Save Changes',ur:'تبدیلیاں محفوظ کریں',hi:'बदलाव सहेजें',bn:'পরিবর্তন সংরক্ষণ করুন'},
    code:{ar:'رمز الفرع',en:'Branch Code',ur:'برانچ کوڈ',hi:'शाखा कोड',bn:'শাখা কোড'},
    name:{ar:'اسم الفرع',en:'Branch Name',ur:'برانچ کا نام',hi:'शाखा का नाम',bn:'শাখার নাম'},
    city:{ar:'المدينة',en:'City',ur:'شہر',hi:'शहर',bn:'শহর'},
    phone:{ar:'هاتف الفرع',en:'Branch Phone',ur:'برانچ فون',hi:'शाखा फोन',bn:'শাখার ফোন'},
    address:{ar:'العنوان',en:'Address',ur:'پتہ',hi:'पता',bn:'ঠিকানা'},
    coverage:{ar:'مناطق التغطية',en:'Coverage Areas',ur:'کوریج ایریاز',hi:'कवरेज क्षेत्र',bn:'কভারেজ এলাকা'},
    status:{ar:'الحالة',en:'Status',ur:'حالت',hi:'स्थिति',bn:'স্ট্যাটাস'},
    created:{ar:'تم إنشاء الفرع',en:'Branch created',ur:'برانچ بن گئی',hi:'शाखा बनाई गई',bn:'শাখা তৈরি হয়েছে'},
    updated:{ar:'تم تحديث الفرع',en:'Branch updated',ur:'برانچ اپڈیٹ ہوگئی',hi:'शाखा अपडेट हुई',bn:'শাখা আপডেট হয়েছে'},
    noBranches:{ar:'لا توجد فروع مسجلة.',en:'No branches are registered.',ur:'کوئی برانچ رجسٹرڈ نہیں۔',hi:'कोई शाखा पंजीकृत नहीं है।',bn:'কোনো শাখা নিবন্ধিত নেই।'},
    deactivateBlocked:{ar:'لا يمكن إيقاف هذا الفرع لوجود عمليات نشطة مرتبطة به.',en:'This branch cannot be deactivated while active operations are linked to it.',ur:'فعال آپریشنز کی وجہ سے اس برانچ کو غیر فعال نہیں کیا جا سکتا۔',hi:'सक्रिय संचालन जुड़े होने पर इस शाखा को निष्क्रिय नहीं किया जा सकता।',bn:'সক্রিয় অপারেশন যুক্ত থাকায় এই শাখা নিষ্ক্রিয় করা যাবে না।'},
    immutableRoute:{ar:'المدينة والرمز ثابتان بعد إنشاء الفرع لحماية الشحنات والرحلات السابقة.',en:'Branch code and city are locked after creation to protect shipment and route history.',ur:'تاریخی ریکارڈ محفوظ رکھنے کے لیے برانچ کوڈ اور شہر بعد میں تبدیل نہیں ہوتے۔',hi:'इतिहास सुरक्षित रखने के लिए शाखा कोड और शहर बनने के बाद लॉक रहते हैं।',bn:'ইতিহাস সুরক্ষার জন্য তৈরির পর শাখার কোড ও শহর লক থাকে।'},
    cityExample:{ar:'مثال: الرياض',en:'Example: Riyadh',ur:'مثال: ریاض',hi:'उदाहरण: रियाद',bn:'উদাহরণ: রিয়াদ'},
    newCityHelp:{ar:'يمكنك كتابة مدينة جديدة غير موجودة حالياً، وستظهر تلقائياً في جميع قوائم المدن بعد حفظ الفرع.',en:'You can enter a new city that is not currently listed. It will automatically appear in all city lists after the branch is saved.',ur:'آپ ایسا نیا شہر درج کر سکتے ہیں جو ابھی فہرست میں موجود نہ ہو۔ برانچ محفوظ ہونے کے بعد یہ خودکار طور پر تمام شہر کی فہرستوں میں نظر آئے گا۔',hi:'आप ऐसा नया शहर दर्ज कर सकते हैं जो अभी सूची में नहीं है। शाखा सहेजने के बाद यह सभी शहर सूचियों में अपने आप दिखाई देगा।',bn:'আপনি এমন একটি নতুন শহর লিখতে পারেন যা বর্তমানে তালিকায় নেই। শাখা সংরক্ষণের পর এটি স্বয়ংক্রিয়ভাবে সব শহরের তালিকায় দেখা যাবে।'}
  };
  function bt(key){const row=BRANCH_UI[key]||{};return row[currentLang]||row.en||row.ar||key}

  function dispatchLive(){const scheduled=state.routes.filter(r=>r.status==='مجدولة').length,active=state.routes.filter(r=>r.status==='في الطريق').length,canRoutes=hasPermission('routes.manage'),canVehicles=hasPermission('vehicles.manage'),canBranches=hasPermission('branches.manage');return `${head(`KSA · ${opsTr('المركز الإقليمي · KSA')}`,opsTr('إدارة الفروع والتوزيع'),opsTr('رحلات الشحن الفعلية بين المدن والفروع مع متابعة الحمولة والسائق والمركبة'),canRoutes?`<button class="btn primary" data-action="route">＋ ${opsTr('جدولة رحلة')}</button>`:'')}<div class="grid kpis">${kpi(opsTr('الشحنات النشطة'),shipments.filter(s=>!['تم الاستلام'].includes(s.status)).length,opsTr('بين المدن والفروع'),'▤')}${kpi(opsTr('رحلات مجدولة'),scheduled,opsTr('بانتظار تحميل المركبة'),'◷')}${kpi(opsTr('رحلات في الطريق'),active,opsTr('تتبع حالة الرحلة'),'⇄','positive')}${kpi(opsTr('جاهزة للتسليم'),shipments.filter(s=>['جاهز للتسليم','في الفرع'].includes(s.status)).length,opsTr('في فروع الوجهة'),'✓')}</div>${canRoutes||canVehicles||canBranches?`<div class="ops-inline-actions">${canRoutes?`<button class="btn accent" data-action="route">▦ ${opsTr('إنشاء رحلة ومسح طرود Batch')}</button>`:''}${canVehicles?`<button class="btn light" data-action="vehicle">＋ ${opsTr('إضافة مركبة')}</button>`:''}${canBranches?`<button class="btn light" data-action="branch">＋ ${opsTr('إضافة فرع / منطقة تغطية')}</button><button class="btn light" data-branch-manage>⚙ ${bt('manage')}</button>`:''}</div>`:''}${transferPanel()}<div class="section-title"><div><h2>${opsTr('الرحلات بين الفروع')}</h2><p>${opsTr('تشمل السائق والمركبة والحمولة والتنبيه قبل الانطلاق')}</p></div><button class="btn light small" data-route-refresh>↻ ${opsTr('تحديث')}</button></div><div class="ops-route-list">${state.routes.map(routeCard).join('')||`<div class="card empty">${opsTr('لا توجد رحلات مسجلة بعد. أنشئ رحلة لربط الشحنات بالسائق والمركبة.')}</div>`}</div><div class="section-title"><h2>${opsTr('الشحنات غير المحملة')}</h2></div><div class="shipment-grid">${shipments.filter(s=>s.status!=='تم الاستلام'&&!state.routes.some(r=>['مجدولة','في الطريق'].includes(r.status)&&r.shipments.some(x=>x.awb===s.awb))).map(shipmentCard).join('')}</div>`}
  function promptRouteScan(id){if(!requirePermission('routes.manage'))return;$('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal" style="max-width:540px"><div class="modal-head"><div><div class="eyebrow">${opsTr('مسح طرود الرحلة')}</div><h2>${opsTr('إضافة بوليصة إلى الحمولة')}</h2></div><button class="icon-btn" data-close>×</button></div><form id="scanForm"><label class="field"><span>${opsTr('رقم البوليصة')}</span><input name="awb" placeholder="GHZ-000125" autocomplete="off" required autofocus></label><small>${opsTr('أدخل رقم بوليصة واحداً. امسح عدة أرقام بالتتابع قبل إغلاق النافذة.')}</small><button class="btn primary full" style="margin-top:14px">▦ ${opsTr('مسح وإضافة')}</button></form><div id="scanHistory" class="ops-route-parcels"></div><button type="button" class="btn light full" id="cameraScan" style="margin-top:12px">◉ ${opsTr('استخدام كاميرا الباركود')}</button><video id="scanVideo" playsinline hidden></video></section></div>`;wireModal();localizeNow($('#modalRoot'));const f=$('#scanForm'),history=$('#scanHistory');f.onsubmit=async e=>{e.preventDefault();const input=f.elements.awb;try{const result=await api(`/api/routes/${id}/scan`,{method:'POST',body:JSON.stringify({awb:input.value})});history.insertAdjacentHTML('beforeend',`<span>${safe(result.awb)} ✓</span>`);input.value='';input.focus();toast(opsTr('تم مسح الشحنة وتحميلها'));state.last=0;await refreshOps(true)}catch(err){toast(opsTr(err.message))}};$('#cameraScan').onclick=()=>startCameraScan(id)}
  async function startCameraScan(routeId){const video=$('#scanVideo');if(!('BarcodeDetector'in window)||!navigator.mediaDevices?.getUserMedia)return toast(opsTr('الكاميرا غير متاحة؛ أدخل رقم البوليصة يدوياً أو افتح التطبيق عبر HTTPS.'));try{const detector=new BarcodeDetector({formats:['code_128','qr_code']});video.hidden=false;video.srcObject=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});await video.play();const tick=async()=>{if(!video.isConnected||video.hidden)return;try{const codes=await detector.detect(video);if(codes[0]?.rawValue){const v=codes[0].rawValue.match(/GHZ-[A-Z0-9-]+/i)?.[0];if(v){$('#scanForm').elements.awb.value=v;$('#scanForm').requestSubmit();video.hidden=true;video.srcObject?.getTracks().forEach(t=>t.stop());return}}}catch(e){}requestAnimationFrame(tick)};tick()}catch(e){toast(opsTr('تعذر تشغيل الكاميرا. تحقق من صلاحية الموقع والكاميرا.'))}}
  async function routeStatus(id,status){if(!requirePermission('routes.manage'))return;try{await api(`/api/routes/${id}`,{method:'POST',body:JSON.stringify({status})});toast(opsTr('تم تحديث حالة الرحلة'));state.last=0;await refreshOps(true);await load()}catch(e){toast(opsTr(e.message))}}

  const FLEET_TEXT={
    fleet:{ar:'إدارة الأسطول',en:'Fleet Management'}, fleetSub:{ar:'المركبات والصيانة والفحص والوثائق وسجل الجاهزية',en:'Vehicles, maintenance, inspections, documents and availability history'},
    vehicles:{ar:'إجمالي المركبات',en:'Total Vehicles'}, available:{ar:'متاحة',en:'Available'}, onRoute:{ar:'في الطريق',en:'On Route'}, maintenance:{ar:'صيانة',en:'Maintenance'}, outOfService:{ar:'خارج الخدمة',en:'Out of Service'},
    due:{ar:'صيانة مستحقة',en:'Maintenance Due'}, addVehicle:{ar:'إضافة مركبة',en:'Add Vehicle'}, editVehicle:{ar:'تعديل المركبة',en:'Edit Vehicle'}, details:{ar:'تفاصيل الأسطول',en:'Fleet Details'},
    plate:{ar:'رقم اللوحة',en:'Plate Number'}, type:{ar:'نوع المركبة',en:'Vehicle Type'}, capacity:{ar:'سعة الحمولة (كجم)',en:'Capacity (kg)'}, make:{ar:'الشركة المصنعة',en:'Make'}, model:{ar:'الموديل',en:'Model'}, year:{ar:'سنة الصنع',en:'Model Year'},
    vin:{ar:'رقم الهيكل VIN',en:'VIN'}, color:{ar:'اللون',en:'Color'}, fuel:{ar:'نوع الوقود',en:'Fuel Type'}, odometer:{ar:'عداد المسافة (كم)',en:'Odometer (km)'}, regExpiry:{ar:'انتهاء الاستمارة',en:'Registration Expiry'},
    insuranceExpiry:{ar:'انتهاء التأمين',en:'Insurance Expiry'}, inspectionExpiry:{ar:'انتهاء الفحص',en:'Inspection Expiry'}, branches:{ar:'الفروع المخصصة',en:'Assigned Branches'}, status:{ar:'حالة المركبة',en:'Vehicle Status'},
    active:{ar:'مركبة نشطة',en:'Vehicle Active'}, notes:{ar:'ملاحظات',en:'Notes'}, save:{ar:'حفظ المركبة',en:'Save Vehicle'}, route:{ar:'الرحلة الحالية',en:'Current Route'}, noRoute:{ar:'لا توجد رحلة نشطة',en:'No active route'},
    maintenanceRecords:{ar:'سجل الصيانة',en:'Maintenance Records'}, inspections:{ar:'الفحوصات',en:'Inspections'}, documents:{ar:'وثائق المركبة',en:'Vehicle Documents'}, history:{ar:'سجل الجاهزية',en:'Availability History'},
    addMaintenance:{ar:'إضافة صيانة',en:'Add Maintenance'}, addInspection:{ar:'إضافة فحص',en:'Add Inspection'}, addDocument:{ar:'إضافة وثيقة',en:'Add Document'}, maintenanceType:{ar:'نوع الصيانة',en:'Maintenance Type'},
    description:{ar:'الوصف',en:'Description'}, scheduledAt:{ar:'موعد الصيانة',en:'Scheduled At'}, completedAt:{ar:'تاريخ الإكمال',en:'Completed At'}, cost:{ar:'التكلفة',en:'Cost'}, vendor:{ar:'مقدم الخدمة',en:'Vendor'},
    nextDueAt:{ar:'الصيانة القادمة',en:'Next Due Date'}, nextDueKm:{ar:'الصيانة القادمة عند (كم)',en:'Next Due Odometer'}, createMaintenance:{ar:'حفظ سجل الصيانة',en:'Save Maintenance Record'}, updateMaintenance:{ar:'تحديث الصيانة',en:'Update Maintenance'},
    inspectionType:{ar:'نوع الفحص',en:'Inspection Type'}, result:{ar:'النتيجة',en:'Result'}, inspectedAt:{ar:'تاريخ الفحص',en:'Inspected At'}, expiryAt:{ar:'تاريخ الانتهاء',en:'Expiry At'}, inspector:{ar:'الفاحص / الجهة',en:'Inspector / Provider'},
    createInspection:{ar:'حفظ الفحص',en:'Save Inspection'}, documentType:{ar:'نوع الوثيقة',en:'Document Type'}, title:{ar:'عنوان الوثيقة',en:'Document Title'}, documentNumber:{ar:'رقم الوثيقة',en:'Document Number'},
    issueDate:{ar:'تاريخ الإصدار',en:'Issue Date'}, expiryDate:{ar:'تاريخ الانتهاء',en:'Expiry Date'}, file:{ar:'ملف PDF / صورة',en:'PDF / Image File'}, createDocument:{ar:'حفظ الوثيقة',en:'Save Document'}, download:{ar:'تحميل',en:'Download'},
    refresh:{ar:'تحديث الأسطول',en:'Refresh Fleet'}, noVehicles:{ar:'لا توجد مركبات في الأسطول',en:'No fleet vehicles found'}, noMaintenance:{ar:'لا توجد سجلات صيانة',en:'No maintenance records'}, noInspections:{ar:'لا توجد سجلات فحص',en:'No inspection records'},
    noDocuments:{ar:'لا توجد وثائق للمركبة',en:'No vehicle documents'}, noHistory:{ar:'لا يوجد سجل جاهزية',en:'No availability history'}, edit:{ar:'تعديل',en:'Edit'}, close:{ar:'إغلاق',en:'Close'},
    scheduled:{ar:'مجدولة',en:'Scheduled'}, in_progress:{ar:'قيد التنفيذ',en:'In Progress'}, completed:{ar:'مكتملة',en:'Completed'}, cancelled:{ar:'ملغاة',en:'Cancelled'}, pending:{ar:'بانتظار الفحص',en:'Pending'},
    passed:{ar:'ناجح',en:'Passed'}, failed:{ar:'غير ناجح',en:'Failed'}, diesel:{ar:'ديزل',en:'Diesel'}, petrol:{ar:'بنزين',en:'Petrol'}, electric:{ar:'كهربائي',en:'Electric'}, hybrid:{ar:'هجين',en:'Hybrid'}, other:{ar:'أخرى',en:'Other'},
    saved:{ar:'تم حفظ بيانات الأسطول',en:'Fleet record saved'}
  };
  function ft(key){return opsDictText('fleet',key,FLEET_TEXT[key])}
  function fleetDate(value){if(!value)return '—';const d=new Date(value);if(Number.isNaN(d.getTime()))return String(value);try{return d.toLocaleDateString(opsLocaleTag(),{year:'numeric',month:'short',day:'2-digit'})}catch(_){return String(value)}}
  function fleetStatusText(value){const map={'متاح':'available','في الطريق':'onRoute','صيانة':'maintenance','خارج الخدمة':'outOfService'};return ft(map[value]||value)}
  function fleetStatusBadge(value){const cls=value==='متاح'?'green':value==='في الطريق'?'blue':value==='صيانة'?'orange':'red';return `<span class="badge ${cls}">${safe(fleetStatusText(value))}</span>`}
  function fleetBranches(){const rows=(state.branchDirectory?.length?state.branchDirectory:state.branches)||[];return rows.filter((row,index,array)=>array.findIndex(item=>String(item.id)===String(row.id))===index)}
  function fleetBranchChecks(selected=[]){const chosen=new Set((selected||[]).map(String));return `<div class="fleet-branch-picker" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px">${fleetBranches().map(branch=>`<label class="card" style="padding:10px;box-shadow:none;display:flex;gap:8px;align-items:center"><input type="checkbox" name="branch_ids" value="${safe(branch.id)}" ${chosen.has(String(branch.id))?'checked':''}><span><b>${safe(branch.name)}</b><small style="display:block">${safe(branch.city||'')}</small></span></label>`).join('')}</div>`}

  function fleetVehicleCard(v){
    const route=v.active_route,branches=(v.branches||[]).map(b=>b.name||b.city).filter(Boolean).join(' · ')||'—';
    return `<article class="card fleet-vehicle-card">
      <div class="shipment-top"><span class="icon-square">▣</span><div><div class="ship-name">${safe(v.plate)}</div><div class="ship-phone">${safe(v.vehicle_type||'—')} · ${safe([v.make,v.model,v.model_year].filter(Boolean).join(' ')||'—')}</div></div><span class="push"></span>${fleetStatusBadge(v.status)}</div>
      <div class="record-meta"><span>${ft('capacity')}: <b>${fmt(v.capacity_kg)} kg</b></span><span>${ft('odometer')}: <b>${fmt(v.odometer_km||0)} km</b></span><span>${ft('branches')}: <b>${safe(branches)}</b></span><span>${ft('documents')}: <b>${Number(v.documents_count||0)}${Number(v.expiring_documents||0)?` · ⚠ ${Number(v.expiring_documents)}`:''}</b></span></div>
      <div class="ship-route"><span>${ft('route')}</span><b>${route?`${safe(route.code)} · ${safe(route.origin)} → ${safe(route.destination)}`:ft('noRoute')}</b></div>
      ${v.next_maintenance?`<div class="notice-warning" style="margin-top:10px">${ft('maintenance')}: ${safe(v.next_maintenance.maintenance_type||'—')} · ${fleetDate(v.next_maintenance.scheduled_at||v.next_maintenance.next_due_at)}</div>`:''}
      <div class="ship-bottom"><button class="btn light small" data-fleet-view="${safe(v.id)}">◉ ${ft('details')}</button>${hasPermission('vehicles.manage')?`<button class="btn light small" data-fleet-edit="${safe(v.id)}">✎ ${ft('edit')}</button><button class="btn light small" data-fleet-maintenance="${safe(v.id)}">⚙ ${ft('maintenance')}</button><button class="btn light small" data-fleet-inspection="${safe(v.id)}">✓ ${ft('inspections')}</button><button class="btn light small" data-fleet-document="${safe(v.id)}">▤ ${ft('documents')}</button>`:''}</div>
    </article>`;
  }

  function driversFleetPage(){
    const rows=drivers||[],fleet=state.vehicles||[],s=state.fleetSummary||{},canDrivers=hasPermission('drivers.manage'),canFleet=hasPermission('vehicles.manage');
    return `${head(`KSA · ${opsTr('إدارة الأسطول')}`,`${opsTr('المناديب')} & ${ft('fleet')}`,ft('fleetSub'),`<div class="ops-inline-actions">${canDrivers?`<button class="btn light" data-action="driver">＋ ${opsTr('إضافة سائق')}</button>`:''}${canFleet?`<button class="btn primary" data-fleet-add>＋ ${ft('addVehicle')}</button>`:''}</div>`)}
      <div class="grid kpis">${kpi(opsTr('إجمالي السائقين'),rows.length,opsTr('سجلات السائقين'),'♙')}${kpi(ft('vehicles'),s.total??fleet.length,ft('fleet'),'▣')}${kpi(ft('available'),s.available??fleet.filter(v=>v.status==='متاح').length,ft('vehicles'),'✓','positive')}${kpi(ft('maintenance'),s.maintenance??fleet.filter(v=>v.status==='صيانة').length,`${ft('due')}: ${s.maintenance_due??0}`,'⚙')}</div>
      <div class="section-title"><div><h2>${ft('fleet')}</h2><p>${ft('fleetSub')}</p></div><div class="ops-inline-actions"><button class="btn light small" data-fleet-refresh>↻ ${ft('refresh')}</button>${canFleet?`<button class="btn primary small" data-fleet-add>＋ ${ft('addVehicle')}</button>`:''}</div></div>
      <div class="grid shipment-grid fleet-grid">${fleet.map(fleetVehicleCard).join('')||`<div class="card empty">${ft('noVehicles')}</div>`}</div>
      <div class="section-title"><div><h2>${opsTr('ملفات السائقين')}</h2><p>${opsTr('بيانات السائقين وأرقام التواصل والمواقع الحالية')}</p></div></div>
      <div class="grid shipment-grid">${rows.map(d=>`<article class="card"><div class="shipment-top"><span class="avatar">${safe(d.name?.[0]||'♙')}</span><div class="ship-name">${safe(d.name)}<div class="ship-phone">${safe(d.branch)} · ${safe(d.national_id)}</div></div><span class="badge ${d.status==='متاح'?'green':'blue'} push">${opsTr(d.status)}</span></div><div class="record-meta"><span>${opsTr('رقم الجوال')}: <b>${safe(d.mobile)}</b></span><span>${opsTr('الموقع الحالي')}: <b>${safe(d.location_text||'—')}</b></span></div><div class="ship-bottom">${hasPermission('drivers.location')?`<button class="btn light small" data-location="${d.id}">${opsTr('تحديث الموقع')}</button>`:''}${canDrivers?`<button class="btn light small" data-assign-driver="${d.id}">${opsTr('تعديل السائق')}</button>`:''}</div></article>`).join('')||`<div class="card empty">${opsTr('لا توجد سجلات سائقين')}</div>`}</div>`;
  }

  async function fleetRefresh(repaint=true){if(!hasPermission('vehicles.read'))return;const [vehicles,summary]=await Promise.all([api('/api/vehicles'),api('/api/fleet/summary')]);state.vehicles=Array.isArray(vehicles)?vehicles:[];state.fleetSummary=summary||{};state.last=Date.now();if(repaint&&page==='drivers')render()}

  async function vehicleFleetModal(id=null){
    if(!requirePermission('vehicles.manage'))return;
    if(!state.branchDirectory?.length){try{state.branchDirectory=await api('/api/branch-directory')}catch(_){}}
    const row=(id?state.vehicles.find(v=>String(v.id)===String(id)):null)||{plate:'',vehicle_type:'شاحنة نقل',capacity_kg:1200,status:'متاح',make:'',model:'',model_year:'',vin:'',color:'',fuel_type:'diesel',odometer_km:0,registration_expiry:'',insurance_expiry:'',inspection_expiry:'',notes:'',is_active:1,branch_ids:[]};
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:880px;max-height:92vh;overflow:auto"><div class="modal-head"><div><div class="eyebrow">GHAZALA FLEET</div><h2>${id?ft('editVehicle'):ft('addVehicle')}</h2></div><button class="icon-btn" data-close>×</button></div>
      <form id="fleetVehicleForm" class="form-grid">
        <label class="field"><span>${ft('plate')} *</span><input name="plate" required value="${safe(row.plate)}"></label><label class="field"><span>${ft('type')} *</span><input name="vehicle_type" required value="${safe(row.vehicle_type)}"></label>
        <label class="field"><span>${ft('capacity')} *</span><input name="capacity_kg" type="number" min=".1" step=".1" required value="${safe(row.capacity_kg)}"></label><label class="field"><span>${ft('status')}</span><select name="status">${['متاح','في الطريق','صيانة','خارج الخدمة'].map(v=>`<option value="${v}" ${row.status===v?'selected':''}>${fleetStatusText(v)}</option>`).join('')}</select></label>
        <label class="field"><span>${ft('make')}</span><input name="make" value="${safe(row.make||'')}"></label><label class="field"><span>${ft('model')}</span><input name="model" value="${safe(row.model||'')}"></label>
        <label class="field"><span>${ft('year')}</span><input name="model_year" type="number" min="1980" max="${new Date().getFullYear()+1}" value="${safe(row.model_year||'')}"></label><label class="field"><span>${ft('vin')}</span><input name="vin" value="${safe(row.vin||'')}"></label>
        <label class="field"><span>${ft('color')}</span><input name="color" value="${safe(row.color||'')}"></label><label class="field"><span>${ft('fuel')}</span><select name="fuel_type">${['diesel','petrol','electric','hybrid','other'].map(v=>`<option value="${v}" ${row.fuel_type===v?'selected':''}>${ft(v)}</option>`).join('')}</select></label>
        <label class="field"><span>${ft('odometer')}</span><input name="odometer_km" type="number" min="0" step="1" value="${safe(row.odometer_km||0)}"></label><label class="field"><span>${ft('regExpiry')}</span><input name="registration_expiry" type="date" value="${safe(String(row.registration_expiry||'').slice(0,10))}"></label>
        <label class="field"><span>${ft('insuranceExpiry')}</span><input name="insurance_expiry" type="date" value="${safe(String(row.insurance_expiry||'').slice(0,10))}"></label><label class="field"><span>${ft('inspectionExpiry')}</span><input name="inspection_expiry" type="date" value="${safe(String(row.inspection_expiry||'').slice(0,10))}"></label>
        <div class="field span-2"><span>${ft('branches')} *</span>${fleetBranchChecks(row.branch_ids||[])}</div><label class="field span-2"><span>${ft('notes')}</span><textarea name="notes">${safe(row.notes||'')}</textarea></label>
        <label class="field span-2" style="display:flex;flex-direction:row;gap:10px;align-items:center"><input name="is_active" type="checkbox" ${row.is_active!==0?'checked':''}><span>${ft('active')}</span></label><div class="field span-2"><button class="btn primary full">${ft('save')}</button></div>
      </form></section></div>`;
    wireModal();
    $('#fleetVehicleForm').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,d=Object.fromEntries(new FormData(f));d.capacity_kg=Number(d.capacity_kg);d.odometer_km=Number(d.odometer_km||0);d.model_year=d.model_year?Number(d.model_year):null;d.is_active=f.elements.is_active.checked;d.branch_ids=$$('input[name="branch_ids"]:checked',f).map(x=>Number(x.value));try{await api(id?`/api/vehicles/${id}`:'/api/vehicles',{method:id?'PATCH':'POST',body:JSON.stringify(d)});closeModal();toast(ft('saved'));await fleetRefresh(true)}catch(err){toast(opsTr(err.message))}};
  }

  async function fleetMaintenanceModal(vehicleId,id=null){
    if(!requirePermission('vehicles.manage'))return;let row=null;if(id){const list=await api(`/api/vehicles/${vehicleId}/maintenance`);row=(list||[]).find(x=>String(x.id)===String(id))}row=row||{maintenance_type:'Preventive Service',status:'scheduled',description:'',scheduled_at:'',completed_at:'',odometer_km:'',cost:0,vendor:'',next_due_at:'',next_due_km:'',notes:''};
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:760px;max-height:92vh;overflow:auto"><div class="modal-head"><h2>${id?ft('updateMaintenance'):ft('addMaintenance')}</h2><button class="icon-btn" data-close>×</button></div><form id="fleetMaintenanceForm" class="form-grid">
      <label class="field span-2"><span>${ft('maintenanceType')} *</span><input name="maintenance_type" required value="${safe(row.maintenance_type||'')}"></label><label class="field"><span>${ft('status')}</span><select name="status">${['scheduled','in_progress','completed','cancelled'].map(v=>`<option value="${v}" ${row.status===v?'selected':''}>${ft(v)}</option>`).join('')}</select></label>
      <label class="field"><span>${ft('odometer')}</span><input name="odometer_km" type="number" min="0" value="${safe(row.odometer_km??'')}"></label><label class="field"><span>${ft('scheduledAt')}</span><input name="scheduled_at" type="datetime-local" value="${safe(String(row.scheduled_at||'').slice(0,16))}"></label>
      <label class="field"><span>${ft('completedAt')}</span><input name="completed_at" type="datetime-local" value="${safe(String(row.completed_at||'').slice(0,16))}"></label><label class="field"><span>${ft('cost')}</span><input name="cost" type="number" min="0" step=".01" value="${safe(row.cost||0)}"></label>
      <label class="field"><span>${ft('vendor')}</span><input name="vendor" value="${safe(row.vendor||'')}"></label><label class="field"><span>${ft('nextDueAt')}</span><input name="next_due_at" type="date" value="${safe(String(row.next_due_at||'').slice(0,10))}"></label>
      <label class="field"><span>${ft('nextDueKm')}</span><input name="next_due_km" type="number" min="0" value="${safe(row.next_due_km??'')}"></label><label class="field span-2"><span>${ft('description')}</span><textarea name="description">${safe(row.description||'')}</textarea></label>
      <label class="field span-2"><span>${ft('notes')}</span><textarea name="notes">${safe(row.notes||'')}</textarea></label><div class="field span-2"><button class="btn primary full">${id?ft('updateMaintenance'):ft('createMaintenance')}</button></div></form></section></div>`;
    wireModal();$('#fleetMaintenanceForm').onsubmit=async e=>{e.preventDefault();const raw=Object.fromEntries(new FormData(e.currentTarget)),d={...raw};for(const k of ['cost','odometer_km','next_due_km'])d[k]=raw[k]===''?null:Number(raw[k]);if(id)delete d.maintenance_type;try{await api(id?`/api/vehicles/${vehicleId}/maintenance/${id}`:`/api/vehicles/${vehicleId}/maintenance`,{method:id?'PATCH':'POST',body:JSON.stringify(d)});closeModal();toast(ft('saved'));await fleetRefresh(true)}catch(err){toast(opsTr(err.message))}};
  }

  async function fleetInspectionModal(vehicleId){
    if(!requirePermission('vehicles.manage'))return;$('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:700px"><div class="modal-head"><h2>${ft('addInspection')}</h2><button class="icon-btn" data-close>×</button></div><form id="fleetInspectionForm" class="form-grid">
      <label class="field span-2"><span>${ft('inspectionType')} *</span><input name="inspection_type" required value="Periodic Vehicle Inspection"></label><label class="field"><span>${ft('result')}</span><select name="result">${['pending','passed','failed'].map(v=>`<option value="${v}">${ft(v)}</option>`).join('')}</select></label>
      <label class="field"><span>${ft('odometer')}</span><input name="odometer_km" type="number" min="0"></label><label class="field"><span>${ft('inspectedAt')}</span><input name="inspected_at" type="datetime-local"></label><label class="field"><span>${ft('expiryAt')}</span><input name="expiry_at" type="date"></label>
      <label class="field span-2"><span>${ft('inspector')}</span><input name="inspector"></label><label class="field span-2"><span>${ft('notes')}</span><textarea name="notes"></textarea></label><div class="field span-2"><button class="btn primary full">${ft('createInspection')}</button></div></form></section></div>`;wireModal();
    $('#fleetInspectionForm').onsubmit=async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.currentTarget));d.odometer_km=d.odometer_km===''?null:Number(d.odometer_km);try{await api(`/api/vehicles/${vehicleId}/inspections`,{method:'POST',body:JSON.stringify(d)});closeModal();toast(ft('saved'));await fleetRefresh(true)}catch(err){toast(opsTr(err.message))}};
  }

  function fleetFileDataUrl(file){if(!file||!file.size)return Promise.resolve('');if(file.size>5000000)return Promise.reject(new Error('File must be 5 MB or smaller.'));return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)})}
  async function fleetDocumentModal(vehicleId){
    if(!requirePermission('vehicles.manage'))return;$('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:700px"><div class="modal-head"><h2>${ft('addDocument')}</h2><button class="icon-btn" data-close>×</button></div><form id="fleetDocumentForm" class="form-grid">
      <label class="field"><span>${ft('documentType')} *</span><select name="document_type"><option value="registration">Registration</option><option value="insurance">Insurance</option><option value="inspection">Inspection</option><option value="permit">Permit</option><option value="other">Other</option></select></label><label class="field"><span>${ft('title')} *</span><input name="title" required></label>
      <label class="field span-2"><span>${ft('documentNumber')}</span><input name="document_number"></label><label class="field"><span>${ft('issueDate')}</span><input name="issue_date" type="date"></label><label class="field"><span>${ft('expiryDate')}</span><input name="expiry_date" type="date"></label>
      <label class="field span-2"><span>${ft('file')}</span><input name="file" type="file" accept=".pdf,image/jpeg,image/png,image/webp"></label><label class="field span-2"><span>${ft('notes')}</span><textarea name="notes"></textarea></label><div class="field span-2"><button class="btn primary full">${ft('createDocument')}</button></div></form></section></div>`;wireModal();
    $('#fleetDocumentForm').onsubmit=async e=>{e.preventDefault();const raw=new FormData(e.currentTarget),file=raw.get('file'),d={document_type:String(raw.get('document_type')||''),title:String(raw.get('title')||''),document_number:String(raw.get('document_number')||''),issue_date:String(raw.get('issue_date')||''),expiry_date:String(raw.get('expiry_date')||''),notes:String(raw.get('notes')||''),file_name:file&&file.size?file.name:'',document_data:file&&file.size?await fleetFileDataUrl(file):''};try{await api(`/api/vehicles/${vehicleId}/documents`,{method:'POST',body:JSON.stringify(d)});closeModal();toast(ft('saved'));await fleetRefresh(true)}catch(err){toast(opsTr(err.message))}};
  }

  async function fleetDetailsModal(vehicleId){
    if(!requirePermission('vehicles.read'))return;const root=$('#modalRoot');root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal"><div class="modal-head"><h2>${ft('details')}</h2><button class="icon-btn" data-close>×</button></div><p>${opsTr('جارٍ تحميل البيانات…')}</p></section></div>`;wireModal();
    try{const [v,m,i,d,h]=await Promise.all([api(`/api/vehicles/${vehicleId}`),api(`/api/vehicles/${vehicleId}/maintenance`),api(`/api/vehicles/${vehicleId}/inspections`),api(`/api/vehicles/${vehicleId}/documents`),api(`/api/vehicles/${vehicleId}/history`)]);
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:1040px;max-height:94vh;overflow:auto"><div class="modal-head"><div><div class="eyebrow">GHAZALA FLEET · ${safe(v.plate)}</div><h2>${ft('details')}</h2></div><button class="icon-btn" data-close>×</button></div>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px"><div class="card" style="padding:12px"><small>${ft('status')}</small><b style="display:block">${fleetStatusText(v.status)}</b></div><div class="card" style="padding:12px"><small>${ft('capacity')}</small><b style="display:block">${fmt(v.capacity_kg)} kg</b></div><div class="card" style="padding:12px"><small>${ft('odometer')}</small><b style="display:block">${fmt(v.odometer_km||0)} km</b></div><div class="card" style="padding:12px"><small>${ft('branches')}</small><b style="display:block">${safe((v.branches||[]).map(x=>x.name).join(' · ')||'—')}</b></div></div>
      <div class="section-title"><h3>${ft('maintenanceRecords')}</h3>${hasPermission('vehicles.manage')?`<button class="btn primary small" data-fleet-maintenance="${v.id}">＋ ${ft('addMaintenance')}</button>`:''}</div><div class="grid" style="gap:8px">${m.map(x=>`<article class="card" style="padding:12px;box-shadow:none"><div class="shipment-top"><b>${safe(x.maintenance_type)}</b><span class="push"></span><span class="badge">${ft(x.status)}</span></div><div class="record-meta"><span>${ft('scheduledAt')}: <b>${fleetDate(x.scheduled_at)}</b></span><span>${ft('cost')}: <b>${fmt(x.cost||0)} SAR</b></span><span>${ft('vendor')}: <b>${safe(x.vendor||'—')}</b></span><span>${ft('nextDueAt')}: <b>${fleetDate(x.next_due_at)}</b></span></div>${hasPermission('vehicles.manage')?`<div class="ship-bottom"><button class="btn light small" data-fleet-maintenance-edit="${x.id}" data-vehicle-id="${v.id}">${ft('edit')}</button></div>`:''}</article>`).join('')||`<div class="card empty">${ft('noMaintenance')}</div>`}</div>
      <div class="section-title"><h3>${ft('inspections')}</h3>${hasPermission('vehicles.manage')?`<button class="btn primary small" data-fleet-inspection="${v.id}">＋ ${ft('addInspection')}</button>`:''}</div><div class="grid" style="gap:8px">${i.map(x=>`<article class="card" style="padding:12px;box-shadow:none"><div class="shipment-top"><b>${safe(x.inspection_type)}</b><span class="push"></span><span class="badge ${x.result==='passed'?'green':x.result==='failed'?'red':''}">${ft(x.result)}</span></div><div class="record-meta"><span>${ft('inspectedAt')}: <b>${fleetDate(x.inspected_at)}</b></span><span>${ft('expiryAt')}: <b>${fleetDate(x.expiry_at)}</b></span><span>${ft('inspector')}: <b>${safe(x.inspector||'—')}</b></span></div></article>`).join('')||`<div class="card empty">${ft('noInspections')}</div>`}</div>
      <div class="section-title"><h3>${ft('documents')}</h3>${hasPermission('vehicles.manage')?`<button class="btn primary small" data-fleet-document="${v.id}">＋ ${ft('addDocument')}</button>`:''}</div><div class="grid" style="gap:8px">${d.map(x=>`<article class="card" style="padding:12px;box-shadow:none"><div class="shipment-top"><b>${safe(x.title)}</b><span class="push"></span><span class="badge">${safe(x.document_type)}</span></div><div class="record-meta"><span>${ft('documentNumber')}: <b>${safe(x.document_number||'—')}</b></span><span>${ft('expiryDate')}: <b>${fleetDate(x.expiry_date)}</b></span></div>${x.has_file?`<div class="ship-bottom"><a class="btn light small" target="_blank" rel="noopener" href="/api/vehicles/${v.id}/documents/${x.id}/file">↓ ${ft('download')}</a></div>`:''}</article>`).join('')||`<div class="card empty">${ft('noDocuments')}</div>`}</div>
      <div class="section-title"><h3>${ft('history')}</h3></div><div class="courier-history-list">${h.slice(0,12).map(x=>`<article class="card courier-history-row"><div class="shipment-top"><b>${safe(x.old_status?fleetStatusText(x.old_status):'—')} → ${safe(fleetStatusText(x.new_status))}</b><span class="push"></span><small>${safe(x.created_at||'')}</small></div><div class="record-meta"><span>${ft('route')}: <b>${safe(x.route_code||'—')}</b></span><span>${ft('odometer')}: <b>${fmt(x.odometer_km||0)} km</b></span><span>${ft('notes')}: <b>${safe(x.reason||'—')}</b></span></div></article>`).join('')||`<div class="card empty">${ft('noHistory')}</div>`}</div></section></div>`;wireModal();
      $$('[data-fleet-maintenance]',root).forEach(b=>b.onclick=()=>fleetMaintenanceModal(b.dataset.fleetMaintenance));$$('[data-fleet-maintenance-edit]',root).forEach(b=>b.onclick=()=>fleetMaintenanceModal(b.dataset.vehicleId,b.dataset.fleetMaintenanceEdit));$$('[data-fleet-inspection]',root).forEach(b=>b.onclick=()=>fleetInspectionModal(b.dataset.fleetInspection));$$('[data-fleet-document]',root).forEach(b=>b.onclick=()=>fleetDocumentModal(b.dataset.fleetDocument));
    }catch(err){toast(opsTr(err.message))}
  }

  function vehicleModal(){if(!requirePermission('vehicles.manage'))return;const f=`<div class="modal-backdrop" data-close><section class="modal" style="max-width:540px"><div class="modal-head"><h2>${opsTr('إضافة مركبة إلى الأسطول')}</h2><button class="icon-btn" data-close>×</button></div><form id="vehicleForm" class="form-grid"><label class="field"><span>${opsTr('رقم اللوحة')}</span><input name="plate" required></label><label class="field"><span>${opsTr('نوع المركبة')}</span><input name="vehicle_type" value="${opsTr('شاحنة نقل')}" data-i18n-value="شاحنة نقل" required></label><label class="field"><span>${opsTr('سعة الحمولة (كجم)')}</span><input name="capacity_kg" type="number" min="1" value="1200" required></label><div class="field span-2"><button class="btn primary full">${opsTr('حفظ المركبة')}</button></div></form></section></div>`;$('#modalRoot').innerHTML=f;wireModal();localizeNow($('#modalRoot'));$('#vehicleForm').onsubmit=async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.currentTarget));d.capacity_kg=Number(d.capacity_kg);d.vehicle_type=window.GhazalaI18n.canonical(d.vehicle_type);try{await api('/api/vehicles',{method:'POST',body:JSON.stringify(d)});closeModal();toast(opsTr('تم حفظ بيانات المركبة'));state.last=0;refreshOps(true)}catch(err){toast(opsTr(err.message))}}}
  async function branchModal(branch=null){
    if(!canAction('branch'))return toast(opsTr('ليست لديك صلاحية لهذا الإجراء'));
    if(!requirePermission('branches.manage'))return;
    try{await ensureNetworkReady()}catch(_){}
    const editing=!!branch;
    const cities=cityNames();
    const row=branch||{code:'',name:'',city:'',phone:'',address:'',coverage:'',is_active:1};
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal" style="max-width:660px"><div class="modal-head"><div><div class="eyebrow">${bt('registry')}</div><h2>${editing?bt('edit'):opsTr('إضافة فرع / منطقة تغطية')}</h2></div><button class="icon-btn" data-close>×</button></div>
      <form id="branchForm" class="form-grid" autocomplete="off">
        <label class="field"><span>${bt('code')}</span><input name="code" placeholder="RUH-NORTH" ${editing?'readonly':''} required value="${safe(row.code||'')}"></label>
        <label class="field"><span>${bt('name')}</span><input name="name" required maxlength="160" value="${safe(row.name||'')}"></label>
        <label class="field" style="position:relative"><span>${bt('city')}</span><input id="branchCityInput" name="city" data-no-i18n translate="no" placeholder="${bt('cityExample')}" autocomplete="off" autocapitalize="none" spellcheck="false" ${editing?'readonly':''} required value="${safe(editing?cityDisplayName(row.city):(row.city||''))}"><div id="branchCitySuggestions" data-no-i18n translate="no" hidden style="position:absolute;z-index:80;top:100%;left:0;right:0;margin-top:4px;background:#fff;border:1px solid #d8e1ec;border-radius:12px;box-shadow:0 12px 30px rgba(15,35,55,.18);padding:6px;max-height:220px;overflow:auto"></div></label>
        <label class="field"><span>${bt('phone')}</span><input name="phone" type="tel" maxlength="60" value="${safe(row.phone||'')}"></label>
        <label class="field span-2"><span>${bt('address')}</span><input name="address" maxlength="1000" value="${safe(row.address||'')}"></label>
        <label class="field span-2"><span>${bt('coverage')}</span><input name="coverage" maxlength="1000" autocomplete="off" placeholder="${opsTr('اسم الحي أو المنطقة')}" value="${safe(row.coverage||'')}"></label>
        ${editing?`<label class="field span-2" style="display:flex;flex-direction:row;gap:10px;align-items:center"><input name="is_active" type="checkbox" ${row.is_active!==0?'checked':''}><span>${bt('active')}</span></label><div class="field span-2"><small>${bt('immutableRoute')}</small></div>`:`<div class="field span-2"><small>${bt('newCityHelp')}</small></div>`}
        <div class="field span-2"><button class="btn primary full">${editing?bt('save'):opsTr('حفظ الفرع')}</button></div>
      </form></section></div>`;
    wireModal();localizeNow($('#modalRoot'));
    const cityInput=$('#branchCityInput'),cityMenu=$('#branchCitySuggestions');
    const renderBranchCitySuggestions=()=>{
      if(editing||!cityInput||!cityMenu)return;
      const lang=opsUiLanguage();
      const typed=cityAliasKey(cityInput.value||'');
      const items=cities.map(city=>({stored:city,label:cityDisplayName(city)})).filter(item=>!typed||cityAliasKey(item.label).includes(typed)||cityAliasKey(item.stored).includes(typed)).slice(0,12);
      cityMenu.innerHTML=items.map((item,index)=>`<button type="button" data-no-i18n translate="no" data-branch-city-choice="${index}" data-city-display="${safe(item.label)}" style="display:block;width:100%;border:0;background:transparent;text-align:${lang==='ar'?'right':'left'};padding:9px 10px;border-radius:8px;cursor:pointer;font:inherit;color:#14263b">${safe(item.label)}</button>`).join('');
      cityMenu.hidden=!items.length;
      $$('[data-branch-city-choice]',cityMenu).forEach((button,index)=>{
        if(items[index])button.textContent=items[index].label;
        button.onmousedown=event=>{
        event.preventDefault();
        const item=items[Number(button.dataset.branchCityChoice)];
        if(!item)return;
        cityInput.value=item.label;
        cityMenu.hidden=true;
        };
      });
    };
    if(cityInput&&!editing){
      cityInput.addEventListener('focus',renderBranchCitySuggestions);
      cityInput.addEventListener('input',renderBranchCitySuggestions);
      cityInput.addEventListener('blur',()=>setTimeout(()=>{if(cityMenu)cityMenu.hidden=true},120));
    }
    $('#branchForm').onsubmit=async e=>{
      e.preventDefault();
      const form=e.currentTarget,d=Object.fromEntries(new FormData(form));
      d.code=String(d.code||'').trim().toUpperCase();
      d.city=cityStoredValue(d.city,cities);
      if(!d.city)return toast(opsTr('أدخل المدينة'));
      if(editing){
        const payload={name:String(d.name||'').trim(),phone:String(d.phone||'').trim(),address:String(d.address||'').trim(),coverage:String(d.coverage||'').trim(),is_active:form.elements.is_active.checked};
        try{
          await api(`/api/branches/${encodeURIComponent(row.id)}`,{method:'PATCH',body:JSON.stringify(payload)});
          closeModal();toast(bt('updated'));await refreshSharedNetwork();await branchManagementModal();
        }catch(err){toast(opsTr(err.message||bt('deactivateBlocked')))}
      }else{
        try{
          await api('/api/branches',{method:'POST',body:JSON.stringify(d)});
          closeModal();toast(bt('created'));await refreshSharedNetwork();render();
        }catch(err){toast(opsTr(err.message))}
      }
    };
  }

  async function branchManagementModal(){
    if(!requirePermission('branches.manage'))return;
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:980px;max-height:92vh;overflow:auto"><div class="modal-head"><div><div class="eyebrow">GHAZALA NETWORK</div><h2>${bt('registry')}</h2><p>${bt('registrySub')}</p></div><button class="icon-btn" data-close>×</button></div><div class="card empty">${opsTr('جارٍ تحميل البيانات…')}</div></section></div>`;
    wireModal();
    try{
      const rows=await api('/api/branches?include_inactive=1');
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:980px;max-height:92vh;overflow:auto"><div class="modal-head"><div><div class="eyebrow">GHAZALA NETWORK</div><h2>${bt('registry')}</h2><p>${bt('registrySub')}</p></div><button class="icon-btn" data-close>×</button></div>
        <div class="ops-inline-actions" style="margin-bottom:14px"><button class="btn primary" data-branch-new>＋ ${bt('add')}</button></div>
        <div class="grid shipment-grid">${(rows||[]).map(branch=>`<article class="card">
          <div class="shipment-top"><span class="icon-square">⌂</span><div class="ship-name">${safe(branch.name)}<div class="ship-phone">${safe(branch.code)} · ${safe(opsTr(branch.city))}</div></div><span class="badge ${branch.is_active!==0?'green':'red'} push">${branch.is_active!==0?bt('active'):bt('inactive')}</span></div>
          <div class="record-meta"><span>${bt('phone')}: <b>${safe(branch.phone||'—')}</b></span><span>${bt('coverage')}: <b>${safe(branch.coverage||'—')}</b></span><span>${bt('address')}: <b>${safe(branch.address||'—')}</b></span></div>
          <div class="ship-bottom"><button class="btn light small" data-branch-edit="${safe(branch.id)}">${bt('edit')}</button><button class="btn ${branch.is_active!==0?'danger':'primary'} small" data-branch-toggle="${safe(branch.id)}" data-next-active="${branch.is_active===0?'true':'false'}">${branch.is_active!==0?bt('deactivate'):bt('activate')}</button></div>
        </article>`).join('')||`<div class="card empty">${bt('noBranches')}</div>`}</div>
      </section></div>`;
      wireModal();localizeNow(root);
      $('[data-branch-new]',root)?.addEventListener('click',()=>branchModal());
      $$('[data-branch-edit]',root).forEach(button=>button.onclick=()=>branchModal((rows||[]).find(x=>String(x.id)===String(button.dataset.branchEdit))));
      $$('[data-branch-toggle]',root).forEach(button=>button.onclick=async()=>{
        button.disabled=true;
        try{
          await api(`/api/branches/${encodeURIComponent(button.dataset.branchToggle)}`,{method:'PATCH',body:JSON.stringify({is_active:button.dataset.nextActive==='true'})});
          await refreshSharedNetwork();toast(bt('updated'));await branchManagementModal();
        }catch(err){toast(opsTr(err.message||bt('deactivateBlocked')));button.disabled=false}
      });
    }catch(err){
      const message=opsTr(err.message||'Unable to load branches.');
      toast(message);
      const body=$('.ops-modal .card.empty',root);
      if(body)body.innerHTML=`<b>${safe(message)}</b><div style="margin-top:12px"><button class="btn light" data-branch-retry>${opsTr('إعادة المحاولة')}</button></div>`;
      $('[data-branch-retry]',root)?.addEventListener('click',()=>branchManagementModal());
    }
  }

  function clientCard(c){const canManage=hasPermission('clients.manage');return `<article class="card"><div class="shipment-top"><span class="icon-square">${c.client_type==='company'?'▣':'♙'}</span><div class="ship-name">${safe(c.name)}<div class="ship-phone">${safe(c.code)} · ${opsTr(c.city)}</div></div><span class="badge ${c.status==='نشط'?'green':'red'} push">${opsTr(c.status)}</span></div><div class="ship-route">${c.commercial_registration||c.national_id?`<span>${opsTr('رقم السجل')} · ${safe(c.commercial_registration||c.national_id)}</span>`:''}<b>${fmt(c.credit_limit)} ${opsTr('ر.س')}</b></div><div class="ship-route"><span>${opsTr('شروط الدفع')} · ${safe(opsTr(c.payment_terms))}</span>${c.mobile?`<a href="tel:${safe(c.mobile)}">${safe(c.mobile)}</a>`:''}</div><div class="ship-bottom"><button class="btn light small" data-client-view="${c.id}">${opsTr('عرض الحساب')}</button>${canManage?`<button class="btn light small" data-client-edit="${c.id}">${opsTr('تعديل')}</button>`:''}</div></article>`}
  function clientsLivePage(){const rows=state.clients||[],active=rows.filter(c=>c.status==='نشط').length,companies=rows.filter(c=>c.client_type==='company').length,credit=rows.reduce((n,c)=>n+Number(c.credit_limit||0),0),canManage=hasPermission('clients.manage');return `${head(`KSA · ${opsTr('بوابة الأعمال')}`,opsTr('إدارة العملاء والشركات'),opsTr('حسابات العملاء ووسائل التواصل وشروط الدفع'),canManage?`<button class="btn primary" data-action="client">＋ ${opsTr('عميل جديد')}</button>`:'')}<div class="grid kpis">${kpi(opsTr('إجمالي العملاء'),rows.length,opsTr('حساب محفوظ في قاعدة البيانات'),'▣')}${kpi(opsTr('الشركات'),companies,opsTr('عملاء الأعمال'),'▤')}${kpi(opsTr('الحسابات النشطة'),active,opsTr('جاهزة للتعامل'),'✓','positive')}${kpi(opsTr('حدود الائتمان'),fmt(credit),opsTr('إجمالي الحدود المسجلة'),'ر.س')}</div><div class="toolbar"><label class="search">⌕ <input id="clientSearch" placeholder="${opsTr('ابحث باسم العميل أو السجل أو الجوال')}" autocomplete="off"></label>${canManage?`<button class="btn accent" data-action="client">＋ ${opsTr('إضافة شركة')}</button>`:''}</div><div class="grid shipment-grid" id="clientsGrid">${rows.map(clientCard).join('')||`<div class="card empty">${opsTr('لا توجد حسابات عملاء بعد')}</div>`}</div>`}
  function clientFormModal(id=null){if(!requirePermission('clients.manage'))return;const c=state.clients.find(x=>String(x.id)===String(id))||{};$('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal"><div class="modal-head"><div><div class="eyebrow">${opsTr('بوابة الأعمال')}</div><h2>${id?opsTr('تعديل بيانات العميل'):opsTr('إضافة عميل جديد')}</h2></div><button class="icon-btn" data-close>×</button></div><form id="clientForm" class="form-grid"><label class="field"><span>${opsTr('اسم العميل')} *</span><input name="name" required maxlength="160" value="${safe(c.name||'')}"></label><label class="field"><span>${opsTr('نوع الحساب')}</span><select name="client_type"><option value="company" ${c.client_type!=='individual'?'selected':''}>${opsTr('شركة')}</option><option value="individual" ${c.client_type==='individual'?'selected':''}>${opsTr('فرد')}</option></select></label><label class="field"><span>رقم الجوال *</span><input name="mobile" type="tel" required value="${safe(c.mobile||'')}"></label><label class="field"><span>البريد الإلكتروني</span><input name="email" type="email" value="${safe(c.email||'')}"></label><label class="field"><span>رقم السجل التجاري</span><input name="commercial_registration" value="${safe(c.commercial_registration||'')}"></label><label class="field"><span>رقم الهوية</span><input name="national_id" value="${safe(c.national_id||'')}"></label><label class="field"><span>المدينة</span><select name="city" required>${cityNames().map(x=>`<option value="${safe(x)}" ${c.city===x?'selected':''}>${opsTr(x)}</option>`).join('')}</select></label><label class="field"><span>حالة الحساب</span><select name="status">${['نشط','معلق','يحتاج تجديد'].map(x=>`<option value="${safe(x)}" ${c.status===x?'selected':''}>${opsTr(x)}</option>`).join('')}</select></label><label class="field span-2"><span>العنوان</span><input name="address" value="${safe(c.address||'')}"></label><label class="field"><span>شروط الدفع</span><select name="payment_terms">${['حسب الاتفاق','مسبق الدفع','شهري','حسب الاستلام'].map(x=>`<option value="${safe(x)}" ${c.payment_terms===x?'selected':''}>${opsTr(x)}</option>`).join('')}</select></label><label class="field"><span>حد الائتمان (ر.س)</span><input name="credit_limit" type="number" min="0" step="0.01" value="${safe(c.credit_limit||0)}"></label><label class="field"><span>خصم العقد %</span><input name="discount_percent" type="number" min="0" max="100" step="0.1" value="${safe(c.discount_percent||0)}"></label><label class="field span-2"><span>ملاحظات</span><textarea name="notes">${safe(c.notes||'')}</textarea></label><div class="field span-2 ops-form-actions"><button type="button" class="btn light" data-close>${opsTr('إلغاء')}</button><button class="btn primary">${opsTr('حفظ بيانات العميل')}</button></div></form></section></div>`;wireModal();localizeNow($('#modalRoot'));const f=$('#clientForm');f.onsubmit=async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(f));d.credit_limit=Number(d.credit_limit||0);d.discount_percent=Number(d.discount_percent||0);try{await api(id?`/api/clients/${id}`:'/api/clients',{method:id?'PATCH':'POST',body:JSON.stringify(d)});closeModal();toast(opsTr(id?'تم تحديث بيانات العميل':'تم حفظ بيانات العميل'));state.last=0;await refreshOps(true)}catch(err){toast(opsTr(err.message))}}}
  function clientDetailsModal(id){if(!requirePermission('clients.read'))return;const c=state.clients.find(x=>String(x.id)===String(id));if(!c)return toast(opsTr('لم يتم العثور على حساب العميل'));$('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal"><div class="modal-head"><div><div class="eyebrow">${safe(c.code)}</div><h2>${safe(c.name)}</h2></div><button class="icon-btn" data-close>×</button></div><div class="summary-row"><span>${opsTr('رقم الجوال')}</span><a href="tel:${safe(c.mobile)}">${safe(c.mobile)}</a></div><div class="summary-row"><span>${opsTr('البريد الإلكتروني')}</span><b>${safe(c.email||'—')}</b></div><div class="summary-row"><span>${opsTr('السجل التجاري / الهوية')}</span><b>${safe(c.commercial_registration||c.national_id||'—')}</b></div><div class="summary-row"><span>${opsTr('العنوان')}</span><b>${safe(c.city)} · ${safe(c.address||'—')}</b></div><div class="summary-row"><span>${opsTr('شروط الدفع')}</span><b>${opsTr(c.payment_terms)}</b></div><div class="summary-row"><span>${opsTr('حد الائتمان')}</span><b>${fmt(c.credit_limit)} ${opsTr('ر.س')}</b></div><div class="summary-row"><span>${opsTr('حالة الحساب')}</span><b>${opsTr(c.status)}</b></div><p>${safe(c.notes||'')}</p>${hasPermission('clients.manage')?`<div class="ops-inline-actions"><button class="btn light" data-client-edit="${c.id}">${opsTr('تعديل البيانات')}</button><button class="btn ${c.status==='نشط'?'danger':'primary'}" data-client-toggle="${c.id}">${opsTr(c.status==='نشط'?'تعليق الحساب':'تفعيل الحساب')}</button></div>`:''}</section></div>`;wireModal();localizeNow($('#modalRoot'));$('[data-client-edit]',$('#modalRoot'))?.addEventListener('click',()=>clientFormModal(c.id));$('[data-client-toggle]',$('#modalRoot'))?.addEventListener('click',async()=>{if(!requirePermission('clients.manage'))return;const status=c.status==='نشط'?'معلق':'نشط';try{await api(`/api/clients/${c.id}`,{method:'PATCH',body:JSON.stringify({status})});closeModal();state.last=0;await refreshOps(true);toast(opsTr('تم تحديث حالة الحساب'))}catch(e){toast(opsTr(e.message))}});applyPermissionControls($('#modalRoot'))}
  const CAMPAIGN_TEXT={
    center:{ar:'مركز الحملات والعروض',en:'Campaigns & Offers Center'},
    sub:{ar:'إدارة العروض والقسائم والاستهداف والقنوات ونتائج الإرسال من مكان واحد.',en:'Manage offers, coupons, audiences, channels and delivery results from one place.'},
    newCampaign:{ar:'حملة جديدة',en:'New Campaign'},
    total:{ar:'إجمالي الحملات',en:'Total Campaigns'},
    published:{ar:'منشورة',en:'Published'},
    deliveries:{ar:'عمليات الإرسال',en:'Deliveries'},
    redemptions:{ar:'استخدامات القسائم',en:'Redemptions'},
    records:{ar:'الحملات المسجلة',en:'Campaign Records'},
    noCampaigns:{ar:'لا توجد حملات بعد',en:'No campaigns yet'},
    manage:{ar:'إدارة',en:'Manage'},
    edit:{ar:'تعديل',en:'Edit'},
    publish:{ar:'نشر',en:'Publish'},
    unpublish:{ar:'إيقاف النشر',en:'Unpublish'},
    dispatch:{ar:'إرسال الآن',en:'Dispatch Now'},
    results:{ar:'النتائج',en:'Results'},
    publishedBadge:{ar:'منشورة',en:'Published'},
    notPublished:{ar:'غير منشورة',en:'Not Published'},
    discount:{ar:'الخصم',en:'Discount'},
    channels:{ar:'القنوات',en:'Channels'},
    audience:{ar:'الجمهور',en:'Audience'},
    placement:{ar:'مكان العرض',en:'Placement'},
    branch:{ar:'استهداف الفرع',en:'Branch Target'},
    allBranches:{ar:'جميع الفروع',en:'All Branches'},
    coupon:{ar:'رمز القسيمة',en:'Coupon Code'},
    redemptionsLimit:{ar:'الحد الأقصى للاستخدام',en:'Maximum Redemptions'},
    perCustomer:{ar:'الحد لكل عميل',en:'Per-customer Limit'},
    minOrder:{ar:'الحد الأدنى للطلب',en:'Minimum Order'},
    maxDiscount:{ar:'الحد الأعلى للخصم',en:'Maximum Discount'},
    unlimited:{ar:'غير محدود',en:'Unlimited'},
    autoExpire:{ar:'إنهاء الحملة تلقائياً عند انتهاء التاريخ',en:'Automatically expire campaign at the end date'},
    name:{ar:'اسم الحملة',en:'Campaign Name'},
    type:{ar:'نوع الحملة',en:'Campaign Type'},
    status:{ar:'الحالة',en:'Status'},
    code:{ar:'رمز الحملة',en:'Campaign Code'},
    percent:{ar:'نسبة الخصم %',en:'Discount %'},
    start:{ar:'بداية الحملة',en:'Start Date'},
    end:{ar:'نهاية الحملة',en:'End Date'},
    message:{ar:'رسالة الحملة',en:'Campaign Message'},
    save:{ar:'حفظ الحملة',en:'Save Campaign'},
    saveChanges:{ar:'حفظ التغييرات',en:'Save Changes'},
    cancel:{ar:'إلغاء',en:'Cancel'},
    createTitle:{ar:'إنشاء حملة جديدة',en:'Create Campaign'},
    editTitle:{ar:'إدارة الحملة',en:'Manage Campaign'},
    inApp:{ar:'داخل التطبيق',en:'In-app'},
    sms:{ar:'رسائل SMS',en:'SMS'},
    whatsapp:{ar:'واتساب',en:'WhatsApp'},
    email:{ar:'البريد الإلكتروني',en:'Email'},
    website:{ar:'الموقع العام',en:'Public Website'},
    customerPortal:{ar:'بوابة العميل',en:'Customer Portal'},
    both:{ar:'الموقع + بوابة العميل',en:'Website + Customer Portal'},
    none:{ar:'بدون عرض عام',en:'No Public Placement'},
    allCustomers:{ar:'جميع العملاء',en:'All Customers'},
    companies:{ar:'عملاء الشركات',en:'Company Customers'},
    individuals:{ar:'الأفراد',en:'Individual Customers'},
    active:{ar:'نشطة',en:'Active'},
    scheduled:{ar:'مجدولة',en:'Scheduled'},
    draft:{ar:'مسودة',en:'Draft'},
    stopped:{ar:'متوقفة',en:'Stopped'},
    expired:{ar:'منتهية',en:'Expired'},
    discountType:{ar:'خصم',en:'Discount'},
    couponType:{ar:'قسيمة',en:'Coupon'},
    pushType:{ar:'إشعار Push',en:'Push Notification'},
    smsType:{ar:'رسالة SMS',en:'SMS Campaign'},
    publishSuccess:{ar:'تم نشر الحملة',en:'Campaign published'},
    unpublishSuccess:{ar:'تم إيقاف نشر الحملة',en:'Campaign unpublished'},
    saveSuccess:{ar:'تم حفظ الحملة',en:'Campaign saved'},
    updateSuccess:{ar:'تم تحديث الحملة',en:'Campaign updated'},
    dispatchSuccess:{ar:'تم تنفيذ إرسال الحملة',en:'Campaign dispatch completed'},
    dispatchConfirm:{ar:'سيتم إرسال الحملة الآن إلى الجمهور المستهدف عبر القنوات المختارة. هل تريد المتابعة؟',en:'This will dispatch the campaign now to the selected audience using the chosen channels. Continue?'},
    publishConfirm:{ar:'هل تريد نشر هذه الحملة الآن؟',en:'Publish this campaign now?'},
    resultsTitle:{ar:'نتائج الحملة',en:'Campaign Results'},
    deliveryHistory:{ar:'سجل الإرسال',en:'Delivery History'},
    redemptionHistory:{ar:'سجل استخدام القسائم',en:'Redemption History'},
    sent:{ar:'تم الإرسال',en:'Sent'},
    failed:{ar:'فشل',en:'Failed'},
    notConfigured:{ar:'غير مربوط',en:'Not Configured'},
    demo:{ar:'وضع تجريبي',en:'Demo'},
    customer:{ar:'العميل',en:'Customer'},
    recipient:{ar:'المستلم',en:'Recipient'},
    provider:{ar:'المزود',en:'Provider'},
    date:{ar:'التاريخ',en:'Date'},
    awb:{ar:'رقم الشحنة',en:'AWB'},
    amount:{ar:'قيمة الخصم',en:'Discount Amount'},
    noDeliveries:{ar:'لا توجد عمليات إرسال لهذه الحملة بعد.',en:'No campaign deliveries yet.'},
    noRedemptions:{ar:'لم يتم استخدام القسيمة بعد.',en:'No coupon redemptions yet.'},
    remaining:{ar:'المتبقي',en:'Remaining'},
    lastDispatch:{ar:'آخر إرسال',en:'Last Dispatch'},
    liveChannelsNote:{ar:'In-app يعمل مباشرة. SMS يستخدم مزود الرسائل عند ربطه. WhatsApp والبريد سيظهران كـ غير مربوط حتى يتم إعداد المزود الحقيقي.',en:'In-app works immediately. SMS uses the configured messaging provider. WhatsApp and Email remain Not Configured until their real providers are connected.'}
  };
  function cmt(key){return opsDictText('campaign',key,CAMPAIGN_TEXT[key])}
  function campaignStatusLabel(value){return ({'نشطة':cmt('active'),'مجدولة':cmt('scheduled'),'مسودة':cmt('draft'),'متوقفة':cmt('stopped'),'منتهية':cmt('expired')})[value]||value||'—'}
  function campaignTypeLabel(value){return ({'خصم':cmt('discountType'),'قسيمة':cmt('couponType'),'إشعار Push':cmt('pushType'),'رسالة SMS':cmt('smsType')})[value]||value||'—'}
  function campaignChannelLabel(value){return ({in_app:cmt('inApp'),sms:cmt('sms'),whatsapp:cmt('whatsapp'),email:cmt('email')})[value]||value}
  function campaignPlacementLabel(value){return ({website:cmt('website'),customer_portal:cmt('customerPortal'),both:cmt('both'),none:cmt('none')})[value]||value||'—'}
  function campaignStatusClass(value){return value==='نشطة'?'green':value==='متوقفة'||value==='منتهية'?'red':value==='مجدولة'?'blue':''}
  function campaignChannels(c){const value=Array.isArray(c?.channels)?c.channels.join(','):String(c?.channels||'');return value.split(',').map(x=>x.trim()).filter(Boolean)}
  function campaignInputDate(value){if(!value)return '';const text=String(value).trim().replace('Z','');return text.length>=16?text.slice(0,16):text}
  function campaignDate(value){if(!value)return '—';const d=new Date(value);if(Number.isNaN(d.getTime()))return safe(value);try{return d.toLocaleString(opsLocaleTag(),{year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'})}catch(_){return safe(value)}}
  function campaignBranchOptions(selected=''){const rows=(state.branchDirectory?.length?state.branchDirectory:state.branches)||[];const unique=rows.filter((row,index,array)=>array.findIndex(item=>String(item.id)===String(row.id))===index);return `<option value="">${cmt('allBranches')}</option>`+unique.map(branch=>`<option value="${safe(branch.id)}" ${String(selected||'')===String(branch.id)?'selected':''}>${safe(branch.name)} · ${safe(branch.city||'')}</option>`).join('')}

  function campaignCard(c){
    const metrics=c.metrics||{},channels=campaignChannels(c),canManage=hasPermission('campaigns.manage');
    return `<article class="card campaign-live-card" style="margin-bottom:14px">
      <div class="shipment-top">
        <span class="icon-square">${c.campaign_type==='إشعار Push'?'♧':c.campaign_type==='رسالة SMS'?'✉':'◇'}</span>
        <div class="ship-name">${safe(c.name)}<div class="ship-phone">${safe(c.code)} · ${safe(campaignTypeLabel(c.campaign_type))}</div></div>
        <span class="badge ${campaignStatusClass(c.status)} push">${safe(campaignStatusLabel(c.status))}</span>
        <span class="badge ${c.is_published?'green':''}">${c.is_published?cmt('publishedBadge'):cmt('notPublished')}</span>
      </div>
      <div class="record-meta" style="margin-top:12px">
        <span>${cmt('discount')}: <b>${fmt(c.discount_percent||0)}%</b></span>
        <span>${cmt('channels')}: <b>${safe(channels.map(campaignChannelLabel).join(' · ')||cmt('inApp'))}</b></span>
        <span>${cmt('audience')}: <b>${safe(c.target_segment||cmt('allCustomers'))}</b></span>
        <span>${cmt('placement')}: <b>${safe(campaignPlacementLabel(c.placement))}</b></span>
        <span>${cmt('branch')}: <b>${safe(c.branch?.name||cmt('allBranches'))}</b></span>
        <span>${cmt('coupon')}: <b>${safe(c.coupon_code||'—')}</b></span>
      </div>
      <div class="ship-route" style="margin-top:10px">
        <span>${cmt('deliveries')}: <b>${Number(metrics.deliveries||0)}</b> · ${cmt('sent')}: <b>${Number(metrics.delivered||0)}</b> · ${cmt('failed')}: <b>${Number(metrics.failed||0)}</b></span>
        <span class="push">${cmt('redemptions')}: <b>${Number(metrics.redemptions||0)}</b>${c.remaining_redemptions!==null&&c.remaining_redemptions!==undefined?` · ${cmt('remaining')}: <b>${Number(c.remaining_redemptions)}</b>`:''}</span>
      </div>
      <div class="ship-phone" style="margin-top:8px">${c.start_at?`${cmt('start')}: ${safe(campaignDate(c.start_at))}`:''}${c.end_at?` · ${cmt('end')}: ${safe(campaignDate(c.end_at))}`:''}${c.last_dispatched_at?` · ${cmt('lastDispatch')}: ${safe(campaignDate(c.last_dispatched_at))}`:''}</div>
      ${c.message?`<div class="card" style="padding:10px;margin-top:10px;box-shadow:none;background:#f8fafc">${safe(c.message)}</div>`:''}
      <div class="ship-bottom">
        <button class="btn light small" data-campaign-results="${safe(c.id)}">◉ ${cmt('results')}</button>
        ${canManage?`<button class="btn light small" data-campaign-manage="${safe(c.id)}">✎ ${cmt('edit')}</button>
          ${c.is_published?`<button class="btn light small" data-campaign-unpublish="${safe(c.id)}">${cmt('unpublish')}</button>`:`<button class="btn primary small" data-campaign-publish="${safe(c.id)}">${cmt('publish')}</button>`}
          ${c.is_published&&c.status==='نشطة'?`<button class="btn primary small" data-campaign-dispatch="${safe(c.id)}">➤ ${cmt('dispatch')}</button>`:''}`:''}
      </div>
    </article>`;
  }

  function campaignsLivePage(){
    const rows=state.campaigns||[];
    const totals=rows.reduce((acc,c)=>{const m=c.metrics||{};acc.deliveries+=Number(m.deliveries||0);acc.redemptions+=Number(m.redemptions||0);if(c.is_published)acc.published++;return acc},{published:0,deliveries:0,redemptions:0});
    return `${head(`KSA · ${opsTr('التسويق والنمو')}`,cmt('center'),cmt('sub'),hasPermission('campaigns.manage')?`<button class="btn primary" data-action="campaign">＋ ${cmt('newCampaign')}</button>`:'')}
      <div class="grid kpis">
        ${kpi(cmt('total'),rows.length,cmt('records'),'◇')}
        ${kpi(cmt('published'),totals.published,cmt('active'),'◈','positive')}
        ${kpi(cmt('deliveries'),totals.deliveries,cmt('sent'),'✉')}
        ${kpi(cmt('redemptions'),totals.redemptions,cmt('coupon'),'％')}
      </div>
      ${hasPermission('campaigns.manage')?`<div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:20px">
        <button class="card btn light" data-campaign-type="قسيمة">＋ ${cmt('couponType')}</button>
        <button class="card btn light" data-campaign-type="إشعار Push">＋ ${cmt('pushType')}</button>
        <button class="card btn light" data-campaign-type="رسالة SMS">＋ ${cmt('smsType')}</button>
      </div>`:''}
      <div class="notice-warning" style="margin-bottom:16px">${cmt('liveChannelsNote')}</div>
      <div class="section-title"><div><h2>${cmt('records')}</h2><p>${cmt('sub')}</p></div><span class="badge">${rows.length}</span></div>
      <div id="campaignList">${rows.map(campaignCard).join('')||`<div class="card empty">${cmt('noCampaigns')}</div>`}</div>`;
  }

  function campaignModal(type='خصم',id=null){
    if(!requirePermission('campaigns.manage'))return;
    const c=state.campaigns.find(x=>String(x.id)===String(id))||{};
    type=c.campaign_type||type;
    const selectedChannels=new Set(campaignChannels(c).length?campaignChannels(c):['in_app']);
    const target=c.target_segment||'جميع العملاء';
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:920px;max-height:94vh;overflow:auto">
      <div class="modal-head"><div><div class="eyebrow">${safe(OPS_UI_OVERRIDES?.[currentLang]?.campaign?.campaignEyebrow||'GHAZALA CAMPAIGNS')}</div><h2>${id?cmt('editTitle'):cmt('createTitle')}</h2></div><button class="icon-btn" data-close>×</button></div>
      <form id="campaignForm" class="form-grid">
        <label class="field span-2"><span>${cmt('name')} *</span><input name="name" required maxlength="160" value="${safe(c.name||'')}"></label>
        <label class="field"><span>${cmt('type')}</span><select name="campaign_type">${['خصم','قسيمة','إشعار Push','رسالة SMS'].map(x=>`<option value="${safe(x)}" ${type===x?'selected':''}>${safe(campaignTypeLabel(x))}</option>`).join('')}</select></label>
        <label class="field"><span>${cmt('status')}</span><select name="status">${['مسودة','مجدولة','نشطة','متوقفة','منتهية'].map(x=>`<option value="${safe(x)}" ${(c.status||'مسودة')===x?'selected':''}>${safe(campaignStatusLabel(x))}</option>`).join('')}</select></label>
        <label class="field"><span>${cmt('code')}</span><input name="code" value="${safe(c.code||'')}" ${id?'readonly':''} placeholder="GHZ20"></label>
        <label class="field"><span>${cmt('coupon')}</span><input name="coupon_code" value="${safe(c.coupon_code||'')}" placeholder="SAVE20"></label>
        <label class="field"><span>${cmt('percent')}</span><input name="discount_percent" type="number" min="0" max="100" step="0.1" value="${safe(c.discount_percent||0)}"></label>
        <label class="field"><span>${cmt('placement')}</span><select name="placement">${[['website','website'],['customer_portal','customerPortal'],['both','both'],['none','none']].map(([v,k])=>`<option value="${v}" ${(c.placement||'website')===v?'selected':''}>${cmt(k)}</option>`).join('')}</select></label>
        <label class="field"><span>${cmt('audience')}</span><select name="target_segment">${[['جميع العملاء','allCustomers'],['عملاء الشركات','companies'],['الأفراد','individuals']].map(([v,k])=>`<option value="${v}" ${target===v?'selected':''}>${cmt(k)}</option>`).join('')}</select></label>
        <label class="field"><span>${cmt('branch')}</span><select name="branch_id">${campaignBranchOptions(c.branch_id)}</select></label>
        <label class="field"><span>${cmt('start')}</span><input name="start_at" type="datetime-local" value="${safe(campaignInputDate(c.start_at))}"></label>
        <label class="field"><span>${cmt('end')}</span><input name="end_at" type="datetime-local" value="${safe(campaignInputDate(c.end_at))}"></label>
        <label class="field"><span>${cmt('redemptionsLimit')}</span><input name="max_redemptions" type="number" min="0" step="1" value="${safe(c.max_redemptions??0)}"><small>0 = ${cmt('unlimited')}</small></label>
        <label class="field"><span>${cmt('perCustomer')}</span><input name="per_customer_limit" type="number" min="1" max="1000" step="1" value="${safe(c.per_customer_limit??1)}"></label>
        <label class="field"><span>${cmt('minOrder')} (SAR)</span><input name="min_order_amount" type="number" min="0" step="0.01" value="${safe(c.min_order_amount??0)}"></label>
        <label class="field"><span>${cmt('maxDiscount')} (SAR)</span><input name="max_discount_amount" type="number" min="0" step="0.01" value="${safe(c.max_discount_amount??'')}" placeholder="${cmt('unlimited')}"></label>
        <div class="field span-2"><span>${cmt('channels')}</span><div class="grid" style="grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px">
          ${[['in_app','inApp'],['sms','sms'],['whatsapp','whatsapp'],['email','email']].map(([v,k])=>`<label class="card" style="padding:10px;box-shadow:none;display:flex;gap:8px;align-items:center"><input type="checkbox" name="campaign_channel" value="${v}" ${selectedChannels.has(v)?'checked':''}><b>${cmt(k)}</b></label>`).join('')}
        </div></div>
        <label class="field span-2"><span>${cmt('message')}</span><textarea name="message" maxlength="2000">${safe(c.message||'')}</textarea></label>
        <label class="field span-2" style="display:flex;flex-direction:row;gap:10px;align-items:center"><input name="auto_expire" type="checkbox" ${(c.auto_expire??1)?'checked':''}><span>${cmt('autoExpire')}</span></label>
        <div class="field span-2"><small>${cmt('liveChannelsNote')}</small></div>
        <div class="field span-2 ops-form-actions"><button type="button" class="btn light" data-close>${cmt('cancel')}</button><button type="submit" class="btn primary">${id?cmt('saveChanges'):cmt('save')}</button></div>
      </form></section></div>`;
    wireModal();
    const f=$('#campaignForm');
    f.onsubmit=async e=>{
      e.preventDefault();
      const fd=new FormData(f),d=Object.fromEntries(fd);
      d.discount_percent=Number(d.discount_percent||0);
      d.max_redemptions=Number(d.max_redemptions||0);
      d.per_customer_limit=Number(d.per_customer_limit||1);
      d.min_order_amount=Number(d.min_order_amount||0);
      d.max_discount_amount=d.max_discount_amount===''?null:Number(d.max_discount_amount);
      d.branch_id=d.branch_id?Number(d.branch_id):null;
      d.auto_expire=f.elements.auto_expire.checked;
      d.channels=$$('input[name="campaign_channel"]:checked',f).map(input=>input.value);
      if(!d.channels.length)d.channels=['in_app'];
      delete d.campaign_channel;
      if(id)delete d.code;
      if(d.start_at&&d.end_at&&new Date(d.end_at)<new Date(d.start_at))return toast(opsTr('تاريخ نهاية الحملة يجب أن يكون بعد تاريخ البداية'));
      const button=f.querySelector('[type="submit"]')||f.querySelector('.btn.primary');if(button)button.disabled=true;
      try{
        await api(id?`/api/campaigns/${id}`:'/api/campaigns',{method:id?'PATCH':'POST',body:JSON.stringify(d)});
        closeModal();toast(id?cmt('updateSuccess'):cmt('saveSuccess'));state.last=0;await refreshOps(true)
      }catch(err){toast(opsTr(err.message))}
      finally{if(button?.isConnected)button.disabled=false}
    };
  }

  async function campaignPublish(id,publish=true){
    if(!requirePermission('campaigns.manage'))return;
    if(publish&&!confirm(cmt('publishConfirm')))return;
    try{
      const result=await api(`/api/campaigns/${encodeURIComponent(id)}/${publish?'publish':'unpublish'}`,{method:'POST',body:JSON.stringify({})});
      toast(publish?cmt('publishSuccess'):cmt('unpublishSuccess'));
      state.last=0;await refreshOps(true);return result
    }catch(error){toast(opsTr(error.message))}
  }

  async function campaignDispatch(id){
    if(!requirePermission('campaigns.manage'))return;
    if(!confirm(cmt('dispatchConfirm')))return;
    try{
      const result=await api(`/api/campaigns/${encodeURIComponent(id)}/dispatch`,{method:'POST',body:JSON.stringify({})});
      const stats=result?.dispatch||{};
      toast(`${cmt('dispatchSuccess')} · ${cmt('audience')}: ${Number(stats.audience||0)} · ${cmt('sent')}: ${Number(stats.sent||0)+Number(stats.demo||0)} · ${cmt('failed')}: ${Number(stats.failed||0)} · ${sat('skipped')}: ${Number(stats.skipped||0)}`);
      state.last=0;await refreshOps(true);setTimeout(()=>campaignResultsModal(id),0)
    }catch(error){toast(opsTr(error.message))}
  }

  async function campaignResultsModal(id){
    if(!requirePermission('campaigns.read'))return;
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:1050px;max-height:94vh;overflow:auto"><div class="modal-head"><h2>${cmt('resultsTitle')}</h2><button class="icon-btn" data-close>×</button></div><div class="card empty">${opsTr('جارٍ تحميل البيانات…')}</div></section></div>`;wireModal();
    try{
      const [campaign,deliveries,redemptions]=await Promise.all([
        api(`/api/campaigns/${id}`),api(`/api/campaigns/${id}/deliveries`),api(`/api/campaigns/${id}/redemptions`)
      ]);
      const m=campaign.metrics||{};
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:1050px;max-height:94vh;overflow:auto">
        <div class="modal-head"><div><div class="eyebrow">${safe(campaign.code)}</div><h2>${safe(campaign.name)}</h2></div><button class="icon-btn" data-close>×</button></div>
        <div class="grid kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))">
          ${kpi(cmt('deliveries'),m.deliveries||0,cmt('deliveryHistory'),'✉')}
          ${kpi(cmt('sent'),m.delivered||0,cmt('publishedBadge'),'✓','positive')}
          ${kpi(cmt('failed'),m.failed||0,cmt('notConfigured')+': '+Number(m.not_configured||0),'⚠')}
          ${kpi(cmt('redemptions'),m.redemptions||0,`${fmt(m.discount_total||0)} SAR`,'％')}
        </div>
        <div class="section-title"><h3>${cmt('deliveryHistory')}</h3><span class="badge">${deliveries.length}</span></div>
        <div class="grid" style="gap:8px">${deliveries.slice(0,100).map(row=>`<article class="card" style="padding:12px;box-shadow:none">
          <div class="shipment-top"><b>${safe(row.customer_name||cmt('customer'))}</b><span class="push"></span><span class="badge ${row.status==='sent'||row.status==='demo'?'green':row.status==='failed'?'red':''}">${safe(({sent:cmt('sent'),demo:cmt('demo'),failed:cmt('failed'),not_configured:cmt('notConfigured')})[row.status]||row.status)}</span></div>
          <div class="record-meta"><span>${cmt('channels')}: <b>${safe(campaignChannelLabel(row.channel))}</b></span><span>${cmt('recipient')}: <b>${safe(row.recipient||'—')}</b></span><span>${cmt('provider')}: <b>${safe(row.provider||'—')}</b></span><span>${cmt('date')}: <b>${safe(campaignDate(row.sent_at||row.created_at))}</b></span></div>
          ${row.provider_error?`<div class="notice-error" style="margin-top:8px">${safe(row.provider_error)}</div>`:''}
        </article>`).join('')||`<div class="card empty">${cmt('noDeliveries')}</div>`}</div>
        <div class="section-title"><h3>${cmt('redemptionHistory')}</h3><span class="badge">${redemptions.length}</span></div>
        <div class="grid" style="gap:8px">${redemptions.slice(0,100).map(row=>`<article class="card" style="padding:12px;box-shadow:none"><div class="shipment-top"><b>${safe(row.customer_name||cmt('customer'))}</b><span class="push"></span><span class="badge green">${fmt(row.discount_amount||0)} SAR</span></div><div class="record-meta"><span>${cmt('coupon')}: <b>${safe(row.promo_code||'—')}</b></span><span>${cmt('awb')}: <b>${safe(row.awb||'—')}</b></span><span>${cmt('date')}: <b>${safe(campaignDate(row.created_at))}</b></span></div></article>`).join('')||`<div class="card empty">${cmt('noRedemptions')}</div>`}</div>
      </section></div>`;
      wireModal();
    }catch(error){
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:620px"><div class="modal-head"><h2>${cmt('resultsTitle')}</h2><button class="icon-btn" data-close>×</button></div><div class="notice-error">${safe(opsTr(error.message))}</div></section></div>`;wireModal()
    }
  }

  async function openUserAccount(id=null){
    if(!requirePermission('users.manage'))return;
    const owner=opsOwnerKey();await refreshOps();
    if(owner!==opsOwnerKey()||!hasPermission('users.manage'))return;
    const account=id==null?null:state.users.find(item=>String(item.id)===String(id));
    userModal(id,account,state.branches,async()=>{await load();state.last=0;await refreshOps(true)});
  }
  async function updateUserAccount(id,changes){
    if(!requirePermission('users.manage'))return;
    if(String(id)===String(user.id)&&changes.is_active===false)return toast(opsTr('لا يمكنك تعطيل حسابك الحالي'));
    try{await api(`/api/users/${id}`,{method:'PATCH',body:JSON.stringify(changes)});toast(opsTr(changes.revoke_sessions?'تم إنهاء جلسات الحساب':'تم تحديث حساب المستخدم'));await load();state.last=0;await refreshOps(true)}catch(error){toast(opsTr(error.message))}
  }

  const RBAC_TEXT={
    title:{ar:'مركز الأدوار والصلاحيات',en:'Roles & Access Control Center',ur:'رولز اور ایکسیس کنٹرول سینٹر',hi:'रोल्स और एक्सेस कंट्रोल सेंटर'},
    sub:{ar:'إدارة الحسابات، نطاق الفروع، الأدوار والصلاحيات الفعلية من نظام RBAC.',en:'Manage accounts, branch scope, roles and effective permissions from the live RBAC policy.',ur:'لائیو RBAC پالیسی سے اکاؤنٹس، برانچ اسکوپ، رولز اور مؤثر اجازتیں مینیج کریں۔',hi:'लाइव RBAC पॉलिसी से अकाउंट, ब्रांच स्कोप, रोल और प्रभावी अनुमतियाँ मैनेज करें।'},
    refresh:{ar:'تحديث الوصول',en:'Refresh Access',ur:'ایکسس ریفریش',hi:'एक्सेस रीफ्रेश'},
    addUser:{ar:'إضافة مستخدم',en:'Add User',ur:'یوزر شامل کریں',hi:'यूज़र जोड़ें'},
    total:{ar:'إجمالي الحسابات',en:'Total Accounts',ur:'کل اکاؤنٹس',hi:'कुल अकाउंट'},
    active:{ar:'حسابات نشطة',en:'Active Accounts',ur:'فعال اکاؤنٹس',hi:'सक्रिय अकाउंट'},
    inactive:{ar:'حسابات معطلة',en:'Inactive Accounts',ur:'غیر فعال اکاؤنٹس',hi:'निष्क्रिय अकाउंट'},
    branches:{ar:'الفروع النشطة',en:'Active Branches',ur:'فعال برانچز',hi:'सक्रिय ब्रांच'},
    roleSummary:{ar:'ملخص الأدوار',en:'Role Summary',ur:'رول خلاصہ',hi:'रोल सारांश'},
    matrix:{ar:'مصفوفة الصلاحيات',en:'Permission Matrix',ur:'پرمیشن میٹرکس',hi:'परमिशन मैट्रिक्स'},
    accounts:{ar:'الحسابات ونطاق الوصول',en:'Accounts & Access Scope',ur:'اکاؤنٹس اور ایکسیس اسکوپ',hi:'अकाउंट और एक्सेस स्कोप'},
    drivers:{ar:'ملفات السائقين',en:'Driver Records',ur:'ڈرائیور ریکارڈز',hi:'ड्राइवर रिकॉर्ड'},
    permissions:{ar:'الصلاحيات',en:'Permissions',ur:'اجازتیں',hi:'अनुमतियाँ'},
    effective:{ar:'الصلاحيات الفعلية',en:'Effective Permissions',ur:'مؤثر اجازتیں',hi:'प्रभावी अनुमतियाँ'},
    permissionCount:{ar:'عدد الصلاحيات',en:'Permission Count',ur:'اجازتوں کی تعداد',hi:'अनुमति संख्या'},
    scope:{ar:'نطاق الوصول',en:'Access Scope',ur:'ایکسس اسکوپ',hi:'एक्सेस स्कोप'},
    global:{ar:'كامل النظام',en:'Global / All Branches',ur:'گلوبل / تمام برانچز',hi:'ग्लोबल / सभी ब्रांच'},
    assignedBranches:{ar:'الفروع المخصصة',en:'Assigned Branches',ur:'مقررہ برانچز',hi:'असाइन ब्रांच'},
    driverScope:{ar:'السائق المرتبط + الفروع',en:'Assigned Driver + Branches',ur:'مقررہ ڈرائیور + برانچز',hi:'असाइन ड्राइवर + ब्रांच'},
    ownedOnly:{ar:'بيانات العميل فقط',en:'Owned Customer Records Only',ur:'صرف اپنے کسٹمر ریکارڈز',hi:'केवल अपने ग्राहक रिकॉर्ड'},
    noBranch:{ar:'بدون فرع',en:'No Branch Assigned',ur:'کوئی برانچ مقرر نہیں',hi:'कोई ब्रांच असाइन नहीं'},
    primary:{ar:'الفرع الرئيسي',en:'Primary Branch',ur:'پرائمری برانچ',hi:'प्राइमरी ब्रांच'},
    linkedDriver:{ar:'السائق المرتبط',en:'Linked Driver',ur:'لنکڈ ڈرائیور',hi:'लिंक्ड ड्राइवर'},
    viewAccess:{ar:'عرض الوصول',en:'View Access',ur:'ایکسس دیکھیں',hi:'एक्सेस देखें'},
    edit:{ar:'تعديل الحساب',en:'Edit Account',ur:'اکاؤنٹ ایڈٹ',hi:'अकाउंट एडिट'},
    revoke:{ar:'إنهاء الجلسات',en:'Revoke Sessions',ur:'سیشن ختم کریں',hi:'सेशन रद्द करें'},
    deactivate:{ar:'تعطيل الحساب',en:'Deactivate',ur:'غیر فعال کریں',hi:'निष्क्रिय करें'},
    activate:{ar:'تفعيل الحساب',en:'Activate',ur:'فعال کریں',hi:'सक्रिय करें'},
    all:{ar:'الكل',en:'All',ur:'تمام',hi:'सभी'},
    allowed:{ar:'مسموح',en:'Allowed',ur:'اجازت',hi:'अनुमत'},
    denied:{ar:'غير مسموح',en:'Not Allowed',ur:'اجازت نہیں',hi:'अनुमति नहीं'},
    systemAdmin:{ar:'مدير النظام',en:'System Administrator',ur:'سسٹم ایڈمن',hi:'सिस्टम एडमिन'},
    branchManager:{ar:'مدير الفرع',en:'Branch Manager',ur:'برانچ مینیجر',hi:'ब्रांच मैनेजर'},
    officeEmployee:{ar:'موظف المكتب',en:'Office Employee',ur:'آفس ایمپلائی',hi:'ऑफिस कर्मचारी'},
    courier:{ar:'المندوب',en:'Courier',ur:'کوریئر',hi:'कूरियर'},
    accountant:{ar:'المحاسب',en:'Accountant',ur:'اکاؤنٹنٹ',hi:'अकाउंटेंट'},
    customer:{ar:'العميل',en:'Customer',ur:'کسٹمر',hi:'ग्राहक'},
    group_shipments:{ar:'الشحنات',en:'Shipments',ur:'شپمنٹس',hi:'शिपमेंट'},
    group_delivery:{ar:'التسليم',en:'Delivery / POD',ur:'ڈیلیوری / POD',hi:'डिलीवरी / POD'},
    group_dispatch:{ar:'النقل والرحلات',en:'Dispatch & Routes',ur:'ڈسپیچ اور روٹس',hi:'डिस्पैच और रूट'},
    group_drivers:{ar:'السائقون',en:'Drivers',ur:'ڈرائیورز',hi:'ड्राइवर'},
    group_fleet:{ar:'الأسطول',en:'Fleet',ur:'فلیٹ',hi:'फ्लीट'},
    group_branches:{ar:'الفروع',en:'Branches',ur:'برانچز',hi:'ब्रांच'},
    group_clients:{ar:'العملاء',en:'Clients',ur:'کلائنٹس',hi:'क्लाइंट'},
    group_pricing:{ar:'التسعير',en:'Pricing',ur:'پرائسنگ',hi:'प्राइसिंग'},
    group_campaigns:{ar:'الحملات',en:'Campaigns',ur:'کیمپینز',hi:'कैंपेन'},
    group_reports:{ar:'التقارير',en:'Reports & Dashboard',ur:'رپورٹس اور ڈیش بورڈ',hi:'रिपोर्ट और डैशबोर्ड'},
    group_administration:{ar:'الإدارة والأمان',en:'Administration & Security',ur:'ایڈمن اور سیکیورٹی',hi:'एडमिन और सिक्योरिटी'},
    group_other:{ar:'أخرى',en:'Other',ur:'دیگر',hi:'अन्य'},
    users:{ar:'مستخدمون',en:'users',ur:'یوزرز',hi:'यूज़र'},
    activeUsers:{ar:'نشط',en:'active',ur:'فعال',hi:'सक्रिय'},
    inactiveUsers:{ar:'معطل',en:'inactive',ur:'غیر فعال',hi:'निष्क्रिय'},
    loading:{ar:'جارٍ تحميل سياسة الوصول…',en:'Loading access policy…',ur:'ایکسس پالیسی لوڈ ہو رہی ہے…',hi:'एक्सेस पॉलिसी लोड हो रही है…'},
    noPermission:{ar:'لا تملك صلاحية إدارة المستخدمين.',en:'You do not have permission to manage users.',ur:'آپ کو یوزرز مینیج کرنے کی اجازت نہیں۔',hi:'आपको यूज़र मैनेज करने की अनुमति नहीं है।'},
    noUsers:{ar:'لا توجد حسابات مستخدمين.',en:'No user accounts found.',ur:'کوئی یوزر اکاؤنٹ نہیں۔',hi:'कोई यूज़र अकाउंट नहीं मिला।'},
    role:{ar:'الدور',en:'Role',ur:'رول',hi:'रोल'},
    status:{ar:'الحالة',en:'Status',ur:'اسٹیٹس',hi:'स्थिति'},
    branchScoped:{ar:'حسابات محددة بالفروع',en:'Branch-scoped Accounts',ur:'برانچ اسکوپڈ اکاؤنٹس',hi:'ब्रांच-स्कोप्ड अकाउंट'},
    globalAdmins:{ar:'مديرو النظام الشاملون',en:'Global Admins',ur:'گلوبل ایڈمنز',hi:'ग्लोबल एडमिन'},
    linkedCouriers:{ar:'مندوبون مرتبطون',en:'Linked Couriers',ur:'لنکڈ کوریئرز',hi:'लिंक्ड कूरियर'},
    generated:{ar:'آخر مزامنة',en:'Last Synced',ur:'آخری سنک',hi:'अंतिम सिंक'}
  };
  function rt(key){
    const row=RBAC_TEXT[key]||{};
    return row[currentLang]||row.en||row.ar||String(key);
  }
  function rbacRoleLabel(role){
    let raw=String(role||'').trim().replace(/\s+/g,' ');
    if(!raw)return '—';
    // Normalize both machine-role keys and older human-readable aliases.
    // This also collapses the legacy duplicate label "System System Administrator".
    raw=raw.replace(/^System\s+System\s+Administrator$/i,'System Administrator');
    const normalized=raw.toLowerCase().replace(/[\s-]+/g,'_');
    const map={
      system_admin:'systemAdmin',
      system_administrator:'systemAdmin',
      administrator:'systemAdmin',
      branch_manager:'branchManager',
      office_employee:'officeEmployee',
      courier:'courier',
      accountant:'accountant',
      customer:'customer'
    };
    return rt(map[normalized]||raw);
  }
  function rbacScopeLabel(role,scopeMode){
    if(scopeMode==='global'||role==='system_admin')return rt('global');
    if(scopeMode==='assigned_driver_and_branches'||role==='courier')return rt('driverScope');
    if(scopeMode==='owned_customer_records'||role==='customer')return rt('ownedOnly');
    return rt('assignedBranches');
  }
  function rbacGroupLabel(group){return rt('group_'+group)}
  function rbacRoleCard(role){
    return `<article class="card" style="padding:14px;box-shadow:none">
      <div class="shipment-top">
        <span class="avatar">${safe(rbacRoleLabel(role.role).slice(0,1))}</span>
        <div class="ship-name"><b>${safe(rbacRoleLabel(role.role))}</b><div class="ship-phone">${safe(rbacScopeLabel(role.role,role.scope_mode))}</div></div>
        <span class="badge ${role.active_account_count?'green':''} push">${fmt(role.account_count||0)} ${rt('users')}</span>
      </div>
      <div class="record-meta" style="margin-top:9px">
        <span>${rt('permissionCount')}: <b>${fmt(role.permission_count||0)}</b></span>
        <span>${rt('activeUsers')}: <b>${fmt(role.active_account_count||0)}</b></span>
        <span>${rt('inactiveUsers')}: <b>${fmt(role.inactive_account_count||0)}</b></span>
      </div>
    </article>`;
  }
  function rbacPermissionMatrix(data){
    const roles=Array.isArray(data?.roles)?data.roles:[];
    const groups=Array.isArray(data?.permission_groups)?data.permission_groups:[];
    if(!roles.length||!groups.length)return `<div class="card empty">${rt('noUsers')}</div>`;
    const roleMap=Object.fromEntries(roles.map(role=>[role.role,new Set(role.permissions||[])]));
    return `<div style="overflow:auto">
      <table class="data-table" style="min-width:900px;width:100%">
        <thead><tr><th>${rt('permissions')}</th>${roles.map(role=>`<th>${safe(rbacRoleLabel(role.role))}</th>`).join('')}</tr></thead>
        <tbody>${groups.map(group=>`<tr>
          <td><b>${safe(rbacGroupLabel(group.group))}</b><div class="ship-phone">${(group.permissions||[]).map(permission=>safe(permission)).join('<br>')}</div></td>
          ${roles.map(role=>{
            const allowed=(group.permissions||[]).filter(permission=>roleMap[role.role]?.has(permission)).length;
            const total=(group.permissions||[]).length;
            const full=total>0&&allowed===total;
            const none=allowed===0;
            return `<td><span class="badge ${full?'green':none?'red':'blue'}">${allowed}/${total}</span></td>`;
          }).join('')}
        </tr>`).join('')}</tbody>
      </table>
    </div>`;
  }
  function rbacAccountCard(account,data){
    const active=account.is_active!==0&&account.is_active!==false;
    const self=String(account.id)===String(user?.id);
    const role=account.access_role||accessRole(account);
    const branches=Array.isArray(account.branches)?account.branches:[];
    const primary=branches.find(branch=>String(branch.id)===String(account.primary_branch_id));
    const permissions=Array.isArray(account.permissions)?account.permissions:[];
    const scope=account.global_scope?rt('global'):(branches.length?branches.map(branch=>safe(branch.name||branch.code)).join(' · '):role==='customer'?rt('ownedOnly'):rt('noBranch'));
    return `<article class="card">
      <div class="shipment-top">
        <span class="avatar">${safe(account.display_name?.[0]||'♙')}</span>
        <div class="ship-name"><b>${safe(account.display_name||'—')}</b><div class="ship-phone" translate="no">${safe(account.username||'')}</div></div>
        <span class="badge ${active?'green':'red'} push">${rt(active?'active':'inactive')}</span>
      </div>
      <div class="record-meta">
        <span>${rt('role')}: <b>${safe(rbacRoleLabel(role))}</b></span>
        <span>${rt('scope')}: <b>${scope}</b></span>
        <span>${rt('primary')}: <b>${safe(primary?.name||primary?.code||'—')}</b></span>
        <span>${rt('permissionCount')}: <b>${fmt(permissions.length)}</b></span>
        ${account.driver_id?`<span>${rt('linkedDriver')}: <b>#${safe(account.driver_id)}</b></span>`:''}
      </div>
      <div class="ship-bottom">
        <button class="btn light small" data-rbac-access="${account.id}">◉ ${rt('viewAccess')}</button>
        <button class="btn light small" data-user-edit="${account.id}">✎ ${rt('edit')}</button>
        <button class="btn ${active?'danger':'primary'} small" data-user-toggle="${account.id}" data-next-active="${!active}" ${self?'disabled':''}>${rt(active?'deactivate':'activate')}</button>
        <button class="btn light small" data-user-revoke="${account.id}">${rt('revoke')}</button>
      </div>
    </article>`;
  }
  function rbacOverviewMarkup(data){
    const summary=data?.summary||{};
    const roles=Array.isArray(data?.roles)?data.roles:[];
    const accounts=Array.isArray(data?.users)?data.users:[];
    return `<div class="section-title"><div><h2>${rt('title')}</h2><p>${rt('sub')}</p></div>
      <div class="ops-inline-actions">
        <button class="btn light" data-rbac-refresh>↻ ${rt('refresh')}</button>
        <button class="btn primary" data-action="staff">＋ ${rt('addUser')}</button>
      </div></div>
      <p class="kpi-note">${rt('generated')}: ${safe(execDate(data?.generated_at))}</p>
      <div class="grid kpis">
        ${kpi(rt('total'),summary.total_accounts||0,`${fmt(summary.branch_scoped_accounts||0)} ${rt('branchScoped')}`,'♙')}
        ${kpi(rt('active'),summary.active_accounts||0,`${fmt(summary.global_admins||0)} ${rt('globalAdmins')}`,'✓','positive')}
        ${kpi(rt('inactive'),summary.inactive_accounts||0,rt('status'),'◷',Number(summary.inactive_accounts||0)?'negative':'')}
        ${kpi(rt('branches'),summary.active_branches||0,`${fmt(summary.linked_couriers||0)} ${rt('linkedCouriers')}`,'⌂')}
      </div>
      <div class="section-title"><h2>${rt('roleSummary')}</h2></div>
      <div class="grid shipment-grid">${roles.map(rbacRoleCard).join('')}</div>
      <div class="section-title"><h2>${rt('matrix')}</h2></div>
      <section class="card">${rbacPermissionMatrix(data)}</section>
      <div class="section-title"><h2>${rt('accounts')}</h2></div>
      <div class="grid shipment-grid">${accounts.map(account=>rbacAccountCard(account,data)).join('')||`<div class="card empty">${rt('noUsers')}</div>`}</div>`;
  }
  function rbacAccessModal(id){
    const data=state.accessOverview;
    const account=(data?.users||[]).find(item=>String(item.id)===String(id));
    if(!account)return toast(rt('noUsers'));
    const role=(data?.roles||[]).find(item=>item.role===(account.access_role||accessRole(account)));
    const branches=Array.isArray(account.branches)?account.branches:[];
    const permissions=Array.isArray(account.permissions)?account.permissions:[];
    const grouped=(data?.permission_groups||[]).map(group=>{
      const allowed=(group.permissions||[]).filter(permission=>permissions.includes(permission));
      if(!allowed.length)return '';
      return `<div class="card" style="padding:11px;box-shadow:none"><b>${safe(rbacGroupLabel(group.group))}</b><div class="record-meta" style="margin-top:7px">${allowed.map(permission=>`<span><b>✓</b> ${safe(permission)}</span>`).join('')}</div></div>`;
    }).join('');
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:900px;max-height:92vh;overflow:auto">
      <div class="modal-head"><div><div class="eyebrow">GHAZALA RBAC</div><h2>${safe(account.display_name||account.username)}</h2><p>${rt('effective')}</p></div><button class="icon-btn" data-close>×</button></div>
      <div class="grid kpis" style="grid-template-columns:repeat(3,minmax(0,1fr))">
        ${kpi(rt('role'),safe(rbacRoleLabel(account.access_role||accessRole(account))),rt('scope'),'♙')}
        ${kpi(rt('permissionCount'),permissions.length,rbacScopeLabel(account.access_role,role?.scope_mode),'✓')}
        ${kpi(rt('branches'),branches.length,account.global_scope?rt('global'):rt('assignedBranches'),'⌂')}
      </div>
      <section class="card" style="margin-top:12px">
        <div class="summary-row"><span>${rt('scope')}</span><b>${account.global_scope?rt('global'):(branches.map(branch=>safe(branch.name||branch.code)).join(' · ')||rt('noBranch'))}</b></div>
        <div class="summary-row"><span>${rt('primary')}</span><b>${safe(branches.find(branch=>String(branch.id)===String(account.primary_branch_id))?.name||'—')}</b></div>
        ${account.driver_id?`<div class="summary-row"><span>${rt('linkedDriver')}</span><b>#${safe(account.driver_id)}</b></div>`:''}
      </section>
      <div class="section-title"><h3>${rt('effective')}</h3><span class="badge">${permissions.length}</span></div>
      <div class="grid" style="gap:8px">${grouped||`<div class="card empty">${rt('noPermission')}</div>`}</div>
      <div class="modal-actions"><button class="btn light" data-close>${opsTr('إغلاق')}</button><button class="btn primary" data-rbac-edit="${account.id}">${rt('edit')}</button></div>
    </section></div>`;
    wireModal();
    $('#modalRoot [data-rbac-edit]')?.addEventListener('click',()=>{
      closeModal();
      openUserAccount(Number(id));
    });
  }
  async function loadAccessOverview(force=false){
    if(!user||!hasPermission('users.manage'))return;
    if(state.accessOverviewLoading)return;
    if(!force&&state.accessOverview)return;
    state.accessOverviewLoading=true;state.accessOverviewError=null;
    try{
      state.accessOverview=await api('/api/access-control/overview');
    }catch(error){
      state.accessOverviewError=error;
      toast(opsTr(error.message||'Could not load access control.'));
    }finally{
      state.accessOverviewLoading=false;
      if(page==='staff'&&!state.auditOpen)window.render();
    }
  }
  function bindAccessControlUI(){
    if(page!=='staff'||!hasPermission('users.manage'))return;
    $$('[data-rbac-refresh]',app).forEach(button=>button.onclick=async()=>{
      button.disabled=true;
      state.accessOverview=null;
      await loadAccessOverview(true);
    });
    $$('[data-rbac-access]',app).forEach(button=>button.onclick=()=>rbacAccessModal(button.dataset.rbacAccess));
    if(!state.accessOverview&&!state.accessOverviewLoading&&!state.accessOverviewError)loadAccessOverview(false);
    if(state.accessOverviewError&&!state.accessOverviewLoading){
      $('[data-rbac-retry]',app)?.addEventListener('click',()=>{
        state.accessOverviewError=null;
        loadAccessOverview(true);
      });
    }
  }

  function accountMarkup(){return `<div class="section-title"><h2>${opsTr('حسابات المستخدمين والصلاحيات')}</h2></div><div class="grid shipment-grid">${state.users.map(account=>{const active=account.is_active!==0&&account.is_active!==false,self=String(account.id)===String(user?.id),role=accessRole(account);return `<article class="card"><div class="shipment-top"><span class="avatar">${safe(account.display_name?.[0]||'♙')}</span><div class="ship-name">${safe(account.display_name)}<div class="ship-phone" translate="no">${safe(account.username)}</div></div><span class="badge ${active?'green':'red'} push">${opsTr(active?'نشط':'معطل')}</span></div><div class="record-meta"><span>${opsTr('الدور')}: <b>${opsTr(accessRoleLabels[role]||'موظف')}</b></span><span>${opsTr('الفروع المسموح بها')}: <b>${(account.branches||[]).map(branch=>safe(branch.name)).join(' · ')||opsTr(role==='system_admin'?'جميع الفروع':'بدون فرع')}</b></span><span>${opsTr('رقم الجوال')}: <b translate="no">${safe(account.mobile||'—')}</b></span></div><div class="ship-bottom"><button class="btn light small" data-user-edit="${account.id}">${opsTr('تعديل الحساب')}</button><button class="btn ${active?'danger':'primary'} small" data-user-toggle="${account.id}" data-next-active="${!active}" ${self?'disabled':''}>${opsTr(active?'تعطيل الحساب':'تفعيل الحساب')}</button><button class="btn light small" data-user-revoke="${account.id}">${opsTr('إنهاء الجلسات')}</button></div></article>`}).join('')||`<div class="card empty">${opsTr('لا توجد حسابات مستخدمين')}</div>`}</div>`}
  function staffLivePage(){
    const rows=drivers||[];
    const header=head(
      `KSA · ${opsTr('إدارة الموارد البشرية')}`,
      opsTr('الموارد البشرية'),
      opsTr('ملفات السائقين وأرقام التواصل والحسابات المرتبطة'),
      hasPermission('users.manage')?`<button class="btn primary" data-action="staff">＋ ${rt('addUser')}</button>`:''
    );
    if(hasPermission('users.manage')){
      let access='';
      if(state.accessOverview){
        access=rbacOverviewMarkup(state.accessOverview);
      }else if(state.accessOverviewError){
        access=`<div class="card"><div class="notice-error">${safe(opsTr(state.accessOverviewError.message||'The request could not be completed.'))}</div><button class="btn primary" data-rbac-retry style="margin-top:10px">${rt('refresh')}</button></div>`;
      }else{
        access=`<div class="card empty">${rt('loading')}</div>`;
      }
      return `${header}${access}
        <div class="section-title"><h2>${rt('drivers')}</h2></div>
        <div class="grid shipment-grid">${rows.map(d=>`<article class="card">
          <div class="shipment-top"><span class="avatar">${safe(d.name?.[0]||'♙')}</span><div class="ship-name">${safe(d.name)}<div class="ship-phone">${safe(d.branch)} · ${safe(d.national_id)}</div></div><span class="badge ${d.status==='متاح'?'green':'blue'} push">${opsTr(d.status)}</span></div>
          <div class="ship-route"><span>${opsTr('الموقع الحالي')}</span><b>${safe(d.location_text||'—')}</b></div>
          <div class="ship-bottom"><a class="btn light small" href="tel:${safe(d.mobile)}">☎ ${safe(d.mobile)}</a><button class="btn light small" data-location="${d.id}">${opsTr('تحديث الموقع')}</button></div>
        </article>`).join('')||`<div class="card empty">${opsTr('لا توجد سجلات سائقين')}</div>`}</div>`;
    }
    return `${header}<div class="grid kpis">
      ${kpi(opsTr('السائقون'),rows.length,opsTr('سجلات السائقين'),'♙')}
      ${kpi(opsTr('السائقون المتاحون'),rows.filter(d=>d.status==='متاح').length,opsTr('جاهزون للتكليف'),'✓','positive')}
    </div>
    <div class="section-title"><h2>${rt('drivers')}</h2></div>
    <div class="grid shipment-grid">${rows.map(d=>`<article class="card"><div class="shipment-top"><span class="avatar">${safe(d.name?.[0]||'♙')}</span><div class="ship-name">${safe(d.name)}<div class="ship-phone">${safe(d.branch)}</div></div><span class="badge push">${opsTr(d.status)}</span></div></article>`).join('')}</div>`;
  }
  const analyticsPeriodLabels={today:'اليوم','7d':'آخر 7 أيام',month:'هذا الشهر',quarter:'هذا الربع',year:'هذا العام'};
  function analyticsRange(period=state.analyticsPeriod||'month',now=new Date()){
    if(!Object.prototype.hasOwnProperty.call(analyticsPeriodLabels,period))period='month';
    const end=new Date(now),start=new Date(end);
    start.setHours(0,0,0,0);
    if(period==='7d')start.setDate(start.getDate()-6);
    else if(period==='month')start.setDate(1);
    else if(period==='quarter'){start.setDate(1);start.setMonth(Math.floor(start.getMonth()/3)*3)}
    else if(period==='year'){start.setDate(1);start.setMonth(0)}
    return {period,start,end};
  }
  function shipmentCreatedDate(value){
    let text=String(value||'').trim().replace(' ','T');
    if(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(text))text+='Z';
    return new Date(text);
  }
  function reportExportLabel(format,working=false){return opsTr(working?(format==='pdf'?'جارٍ تجهيز تقرير PDF…':'جارٍ تجهيز تقرير Excel…'):(format==='pdf'?'تصدير PDF':'تصدير Excel'))}
  function reportExportButtons(){
    if(!hasPermission('reports.read'))return '';
    return '<div class="ops-inline-actions report-export-actions" style="margin:0">'+['pdf','xlsx'].map(format=>'<button type="button" class="btn light small" data-action="export-'+format+'" data-report-format="'+format+'" '+(state.exporting?'disabled':'')+' aria-busy="'+String(state.exporting===format)+'">⇩ '+reportExportLabel(format,state.exporting===format)+'</button>').join('')+'</div>';
  }
  function syncReportExportButtons(){
    $$('[data-report-format]',app).forEach(button=>{const format=button.dataset.reportFormat;button.disabled=!!state.exporting;button.setAttribute('aria-busy',String(state.exporting===format));button.textContent='⇩ '+reportExportLabel(format,state.exporting===format)});
  }
  function analyticsLivePage(){const range=analyticsRange();state.analyticsRange=range;const {period,start,end:now}=range;const rows=shipments.filter(s=>{const d=shipmentCreatedDate(s.created_at);return Number.isFinite(d.getTime())&&d>=start&&d<=now}),delivered=rows.filter(isDeliveredShipment).length,delayed=rows.filter(s=>s.status==='تأخير').length,fees=rows.reduce((n,s)=>n+Number(s.total_fee||0),0),cod=rows.reduce((n,s)=>n+Number(s.cod||0),0),rate=rows.length?Math.round(100*delivered/rows.length):0;const dayStarts=Array.from({length:7},(_,i)=>{const d=new Date(now);d.setHours(0,0,0,0);d.setDate(d.getDate()-(6-i));return d}),counts=dayStarts.map(d=>rows.filter(s=>{const t=shipmentCreatedDate(s.created_at);return t.getFullYear()===d.getFullYear()&&t.getMonth()===d.getMonth()&&t.getDate()===d.getDate()}).length),max=Math.max(1,...counts);const periodLabels=analyticsPeriodLabels;return `${head(`KSA · ${opsTr('التقارير التنفيذية')}`,opsTr('الرسوم البيانية والتحليلات'),opsTr('مؤشرات فعلية محسوبة من سجلات الشحنات'),reportExportButtons())}<div class="tabs">${Object.entries(periodLabels).map(([key,label])=>`<button class="tab analytics-period ${period===key?'active':''}" data-period="${key}">${opsTr(label)}</button>`).join('')}</div><p id="analyticsPeriodNote" class="kpi-note">${opsTr('الفترة المحددة')}: ${opsTr(periodLabels[period])} · ${fmt(rows.length)} ${opsTr('شحنات')}</p><div class="grid kpis">${kpi(opsTr('الشحنات'),rows.length,opsTr('ضمن الفترة'),'▤')}${kpi(opsTr('معدل التسليم'),`${rate}%`,`${fmt(delivered)} ${opsTr('تم التسليم')}`,'✓','positive')}${kpi(opsTr('قيمة رسوم الشحن المسجلة (شاملة الضريبة)'),`${fmt(fees)} ${opsTr('ر.س')}`,opsTr('حسب السجلات'),'ر.س')}${kpi(opsTr('مبالغ التحصيل المطلوبة'),`${fmt(cod)} ${opsTr('ر.س')}`,`${fmt(delayed)} ${opsTr('حالات تأخير')}`,'⚠',delayed?'negative':'')}</div><div class="card"><div class="section-title" style="margin-top:0"><h2>${opsTr('الشحنات المنشأة خلال آخر 7 أيام')}</h2></div><div class="bar-chart">${counts.map((v,i)=>`<i style="height:${Math.max(5,100*v/max)}%" data-label="${dayStarts[i].toLocaleDateString(currentLang==='ar'?'ar-SA':currentLang,{weekday:'short'})}" title="${fmt(v)} ${opsTr('شحنات')}"></i>`).join('')}</div></div><div class="grid dashboard-grid"><section class="card"><div class="section-title" style="margin-top:0"><h2>${opsTr('حالة الشحنات')}</h2></div>${['تم إنشاء الشحنة','قيد النقل','جاهز للتسليم','قيد التوصيل','تم الاستلام','تأخير'].map(status=>`<div class="summary-row"><span>${opsTr(status)}</span><b>${fmt((status==='تم الاستلام'?rows.filter(isDeliveredShipment).length:rows.filter(s=>s.status===status).length))}</b></div>`).join('')}</section><section class="card"><div class="section-title" style="margin-top:0"><h2>${opsTr('الرحلات')}</h2></div><div class="summary-row"><span>${opsTr('مجدولة')}</span><b>${fmt(state.routes.filter(r=>r.status==='مجدولة').length)}</b></div><div class="summary-row"><span>${opsTr('في الطريق')}</span><b>${fmt(state.routes.filter(r=>r.status==='في الطريق').length)}</b></div><div class="summary-row"><span>${opsTr('وصلت')}</span><b>${fmt(state.routes.filter(r=>r.status==='وصلت').length)}</b></div></section></div>`}
  function activeReportExportRange(){
    const requested=state.executivePeriod||'30d';
    const report=page==='analytics'&&state.managementReportPeriod===requested?state.managementReport:null;
    const reportPeriod=report?.period;
    const parseUtc=value=>{
      if(!value)return null;
      let text=String(value).trim().replace(' ','T');
      if(!/[zZ]|[+-]\d{2}:?\d{2}$/.test(text))text+='Z';
      const parsed=new Date(text);
      return Number.isFinite(parsed.getTime())?parsed:null;
    };
    if(reportPeriod&&String(reportPeriod.key||'')===requested){
      const start=parseUtc(reportPeriod.start),end=parseUtc(reportPeriod.end);
      if(end&&(start||requested==='all')){
        return {period:requested,start:start||new Date(0),end};
      }
    }
    // Legacy analytics view fallback. Never reuse a stale Management Reports range.
    const selectedRange=analyticsRange();
    return state.analyticsRange?.period===selectedRange.period?state.analyticsRange:selectedRange;
  }
  async function exportReport(format='pdf'){
    if(!requirePermission('reports.read'))return;
    if(state.exporting)return;
    if(!['pdf','xlsx'].includes(format))throw new Error('Unsupported report format');
    const range=activeReportExportRange();
    const lang=currentLang;
    const params=new URLSearchParams({format,lang,start:range.start.toISOString(),end:range.end.toISOString(),period:range.period,prepare:'1'});
    state.exporting=format;syncReportExportButtons();toast(reportExportLabel(format,true));
    try{
      const response=await fetch('/api/reports/shipments?'+params,{credentials:'same-origin',headers:{Accept:'application/json'}});
      if(!response.ok){let message='تعذر تنزيل التقرير. حاول مرة أخرى.';try{message=(await response.json()).error||message}catch(e){}if(response.status===401)message='انتهت الجلسة. سجّل الدخول لتنزيل التقرير.';throw new Error(message)}
      const result=await response.json();
      if(typeof result.url!=='string'||!/^\/api\/reports\/shipments\?ticket=[A-Za-z0-9_-]+$/.test(result.url)||typeof result.filename!=='string'||/[\\/\x00\r\n]/.test(result.filename)||!result.filename.toLowerCase().endsWith('.'+format))throw new Error('تعذر تنزيل التقرير. حاول مرة أخرى.');
      const link=document.createElement('a');link.href=result.url;link.download=result.filename;
      document.body.appendChild(link);link.click();link.remove();
      toast(opsTr(format==='pdf'?'تم تنزيل تقرير PDF':'تم تنزيل تقرير Excel'));
    }catch(err){console.error('Report download failed',err);const message=err.message||'تعذر تنزيل التقرير. حاول مرة أخرى.',translated=opsTr(message);toast(currentLang==='ar'||translated!==message?translated:opsTr('تعذر تنزيل التقرير. حاول مرة أخرى.'))}
    finally{state.exporting=null;syncReportExportButtons()}
  }
  function documentFilename(response,fallback){
    const disposition=response.headers.get('Content-Disposition')||'';
    const match=disposition.match(/filename="?([^";]+)"?/i);
    return (match?.[1]||fallback||'document.pdf').replace(/[\\/\x00\r\n]/g,'_');
  }
  async function fetchDocumentBlob(url){
    const response=await fetch(url,{credentials:'same-origin',headers:{Accept:'application/pdf'}});
    if(!response.ok){
      let message=dt('loadError');
      try{message=(await response.json()).error||message}catch(_){}
      throw new Error(message);
    }
    return {blob:await response.blob(),filename:documentFilename(response)};
  }
  async function downloadServerPdf(url,fallback){
    const {blob,filename}=await fetchDocumentBlob(url);
    const href=URL.createObjectURL(blob);
    try{
      const link=document.createElement('a');
      link.href=href;link.download=filename||fallback||'document.pdf';
      document.body.appendChild(link);link.click();link.remove();
      toast(dt('downloaded'));
    }finally{
      setTimeout(()=>URL.revokeObjectURL(href),30000);
    }
  }
  async function openServerPdf(url,fallback){
    const popup=window.open('about:blank','_blank');
    try{
      const {blob,filename}=await fetchDocumentBlob(url);
      const href=URL.createObjectURL(blob);
      if(popup){popup.location.href=href;popup.document.title=filename||fallback||'Ghazala Document'}
      else{
        const link=document.createElement('a');link.href=href;link.target='_blank';link.rel='noopener';
        document.body.appendChild(link);link.click();link.remove();
      }
      setTimeout(()=>URL.revokeObjectURL(href),120000);
      return true;
    }catch(error){
      try{popup?.close()}catch(_){}
      throw error;
    }
  }
  async function documentPost(url,data={}){
    return api(url,{method:'POST',body:JSON.stringify(data)});
  }
  async function loadShipmentDocuments(awb){
    return api(`/api/shipments/${encodeURIComponent(awb)}/documents`);
  }

  async function fetchCodeSvg(awb,kind){
    const response=await fetch(`/api/shipments/${encodeURIComponent(awb)}/${kind}`,{credentials:'same-origin'});
    if(!response.ok)throw new Error(opsTr('تعذر تحميل رموز البوليصة'));
    const svg=await response.text();
    if(!svg.includes('<svg'))throw new Error(opsTr('تعذر تحميل رموز البوليصة'));
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  }
  function waybillHtml(s,qr,bar,waybill={}){
    const track=s.tracking_url||`${location.origin}/#track=${encodeURIComponent(s.awb)}`;
    return `<!doctype html><html lang="${document.documentElement.lang}" dir="${document.documentElement.dir}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${safe(s.awb)} · Ghazala Transport</title><script src="${location.origin}/pdf-tools.js?v=1"><\/script><style>body{font:14px 'Plus Jakarta Sans','IBM Plex Sans Arabic',Arial,sans-serif;color:#0d1e33;max-width:780px;margin:16px auto;padding:16px;background:#f8fafc}.sheet{background:#fff;border:1px solid #e2e8f0;border-top:8px solid #ea580c;border-radius:16px;padding:26px;box-shadow:0 8px 30px rgba(13,30,51,0.06)}.top{display:flex;align-items:center;gap:14px;border-bottom:1px solid #e2e8f0;padding-bottom:16px}.top img{width:70px;height:70px;object-fit:contain;border-radius:50%;box-shadow:0 4px 12px rgba(13,30,51,0.1)}.top h1{margin:3px 0 0;font-size:24px;font-weight:800;color:#0d1e33}.top small{color:#ea580c;font-weight:700;font-size:11px;letter-spacing:0.04em}.awb{text-align:center;font:800 22px 'JetBrains Mono',monospace;margin:18px;color:#0d1e33;letter-spacing:0.04em}.codes{text-align:center;display:flex;flex-direction:column;align-items:center;gap:14px;margin:18px 0}.codes img:first-child{width:160px;height:160px;object-fit:contain;background:#fff;padding:6px;border-radius:10px;border:1px solid #e2e8f0}.codes img:last-child{width:380px;max-width:95%;height:88px;object-fit:contain;background:#fff;padding:6px 12px;border-radius:10px;border:1px solid #e2e8f0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.block{background:#f8fafc;border:1px solid #edf2f7;padding:16px;border-radius:12px;margin:10px 0}.block h3{margin:0 0 10px;font-size:13px;font-weight:800;color:#ea580c;border-bottom:1px solid #e2e8f0;padding-bottom:6px}.row{display:flex;justify-content:space-between;gap:8px;margin:7px 0;font-size:12px}.row span{color:#64748b}.row b{color:#0d1e33;font-weight:700}.tools{display:flex;gap:10px;justify-content:center;margin:16px 0 20px;flex-wrap:wrap}.tools button{padding:10px 18px;border:0;border-radius:10px;font-weight:700;font-size:13px;cursor:pointer;transition:all .18s;display:inline-flex;align-items:center;gap:6px}.tools button.primary{background:linear-gradient(135deg,#0d1e33,#1a3459);color:#fff;box-shadow:0 4px 14px rgba(13,30,51,0.2)}.tools button.accent{background:linear-gradient(135deg,#f97316,#ea580c);color:#fff;box-shadow:0 4px 14px rgba(234,88,12,0.3)}.tools button.light{background:#ffffff;color:#1e293b;border:1px solid #cbd5e1}.tools button:hover{transform:translateY(-2px);filter:brightness(1.08)}footer{margin-top:20px;padding-top:14px;border-top:1px solid #e2e8f0;text-align:center;color:#64748b;font-size:11px;font-weight:600}@media print{.tools{display:none!important}body{margin:0;padding:0;background:#fff}.sheet{border:0;box-shadow:none;padding:10px}}@media(max-width:600px){body{margin:0;padding:8px}.sheet{padding:15px}.grid{grid-template-columns:1fr}}</style></head><body><div class="tools"><button type="button" class="accent" id="printBtn" onclick="doPrint()">🖨️ ${opsTr('طباعة / حفظ PDF')}</button><button type="button" class="primary" id="savePdfBtn" onclick="doSavePdf()">📥 ${opsTr('تنزيل PDF')}</button><button type="button" class="light" onclick="shareLabel()">🔗 ${opsTr('مشاركة')}</button></div><main class="sheet" data-document-kind="waybill" data-document-id="${safe(waybill.waybill_number||s.awb)}"><header class="top"><img src="${location.origin}/ghazala-logo.png?v=2" alt="${safe(opsTr('غزالا ترانسبورت'))}"><div><small>${opsTr('GHAZALA TRANSPORT · KSA')}</small><h1>${opsTr('بوليصة الشحن')}</h1></div><b style="margin-inline-start:auto;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;padding:4px 10px;border-radius:20px;font-size:11px">${safe(opsTr(s.status))}</b></header><div class="awb">${safe(waybill.waybill_number||('WB-'+s.awb))}<div style="font-size:11px;color:#64748b;margin-top:5px">${safe(s.awb)}</div></div><div class="codes"><img src="${qr}" alt="${opsTr('QR')}"><img src="${bar}" alt="${opsTr('barcode')}"></div><div class="grid"><section class="block"><h3>${opsTr('بيانات المرسل')}</h3><div class="row"><span>${opsTr('الاسم')}</span><b>${safe(s.sender_name)}</b></div><div class="row"><span>${opsTr('رقم الجوال')}</span><b>${safe(s.sender_phone)}</b></div><p style="font-size:11px;color:#475569;margin:6px 0">${safe(s.sender_address)}</p><b style="font-size:12px;color:#0d1e33">◉ ${opsTr(s.origin)}</b></section><section class="block"><h3>${opsTr('بيانات المستلم')}</h3><div class="row"><span>${opsTr('الاسم')}</span><b>${safe(s.recipient)}</b></div><div class="row"><span>${opsTr('رقم الجوال')}</span><b>${safe(s.phone)}</b></div><p style="font-size:11px;color:#475569;margin:6px 0">${safe(s.recipient_address)}</p><b style="font-size:12px;color:#0d1e33">◉ ${opsTr(s.destination)} · ${safe(opsTr(s.recipient_branch||''))}</b></section></div><section class="block"><h3>${opsTr('تفاصيل الطرد والدفع')}</h3><div class="row"><span>${opsTr('نوع الشحنة')}</span><b>${safe(opsTr(s.package_type))}</b></div><div class="row"><span>${opsTr('عدد الطرود / الوزن')}</span><b>${safe(s.pieces)} / ${safe(s.weight)} ${opsTr('كجم')}</b></div><div class="row"><span>${opsTr('التحصيل عند الاستلام COD')}</span><b style="color:#ea580c">${fmt(s.cod)} ${opsTr('ر.س')}</b></div><div class="row"><span>${opsTr('حالة الدفع')}</span><b>${opsTr(s.payment_status||'غير مدفوع')}</b></div><div class="row"><span>${opsTr('رسوم الشحن والضريبة')}</span><b>${fmt(s.total_fee)} ${opsTr('ر.س')}</b></div><div class="row"><span>${opsTr('وقت الوصول المتوقع ETA')}</span><b>${safe(opsTr(s.eta))}</b></div></section><section class="block"><h3>${dt('documents')}</h3><div class="row"><span>${dt('issuingOffice')}</span><b>${safe(s.origin_office||s.origin_office_code||s.origin)}</b></div><div class="row"><span>${dt('receivingOffice')}</span><b>${safe(s.destination_office||s.destination_office_code||s.recipient_branch||s.destination)}</b></div><div class="row"><span>${dt('courier')}</span><b>${safe(s.driver_name||opsTr('غير معيّن'))}</b></div><div class="row"><span>${dt('created')}</span><b>${safe(s.created_at||'—')}</b></div></section><footer>${safe(opsTr(s.origin))} → ${safe(opsTr(s.destination))} · ${opsTr('غزالا ترانسبورت')} · ${opsTr('المملكة العربية السعودية')}</footer></main><script>
async function doSavePdf(){
  try{window.parent.postMessage({action:'save-waybill-pdf',awb:${JSON.stringify(s.awb)}},'*');}catch(e){}
}

async function doPrint(){
  try{window.parent.postMessage({action:'print-waybill',awb:${JSON.stringify(s.awb)}},'*');}catch(e){}
}

async function shareLabel(){
  const t=${JSON.stringify(track)};
  try{if(navigator.share){await navigator.share({title:${JSON.stringify(s.awb)},url:t});return;}}catch(e){if(e.name==='AbortError')return;}
  try{if(navigator.clipboard){await navigator.clipboard.writeText(t);alert(${JSON.stringify(opsTr('تم نسخ رابط التتبع'))});return;}}catch(e){}
  prompt(${JSON.stringify(opsTr('انسخ رابط التتبع'))},t);
}
<\/script></body></html>`
  }

  async function triggerWaybillPdfDownload(awb){
    try{
      await downloadServerPdf(
        `/api/shipments/${encodeURIComponent(awb)}/waybill/pdf`,
        `WB-${awb}.pdf`
      );
    }catch(error){
      console.warn('Waybill PDF download failed',error);
      toast(opsTr(error.message||dt('loadError')));
    }
  }

  async function triggerWaybillParentPrint(awb){
    try{
      await documentPost(`/api/shipments/${encodeURIComponent(awb)}/waybill/print`);
      const frame=document.querySelector('#documentFrame');
      let printed=false;
      try{
        if(frame?.contentWindow){
          frame.contentWindow.focus();
          frame.contentWindow.print();
          printed=true;
        }
      }catch(_){}
      if(!printed){
        await openServerPdf(
          `/api/shipments/${encodeURIComponent(awb)}/waybill/pdf`,
          `WB-${awb}.pdf`
        );
        toast(dt('printOpened'));
      }
    }catch(error){
      console.warn('Waybill print failed',error);
      toast(opsTr(error.message||dt('loadError')));
    }
  }

  window.addEventListener('message',e=>{
    if(!e.data||typeof e.data!=='object'||e.source!==$('#documentFrame')?.contentWindow)return;
    if(e.data.action==='print-waybill'){
      triggerWaybillParentPrint(e.data.awb);
    }else if(e.data.action==='save-waybill-pdf'){
      triggerWaybillPdfDownload(e.data.awb);
    }
  });

  function documentPreview(title,s){
    const awb=s?.awb||s?.code||'';
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-document-modal"><div class="modal-head"><h2>${safe(title)}</h2><div style="display:flex;align-items:center;gap:8px;margin-inline-start:auto;margin-inline-end:10px"><button type="button" class="btn primary small" id="topPrintWaybillBtn" title="${opsTr('طباعة / حفظ PDF')}">🖨️ ${opsTr('طباعة / حفظ PDF')}</button><button type="button" class="btn light small" id="topSaveWaybillPdfBtn" title="${opsTr('تنزيل PDF')}">📥 ${opsTr('تنزيل PDF')}</button></div><button class="icon-btn" data-close>×</button></div><p id="documentLoading" class="ops-loading">${opsTr('جارٍ تجهيز المستند…')}</p><iframe id="documentFrame" class="ops-document-frame" title="${safe(title)}" hidden></iframe></section></div>`;
    wireModal();
    const topPrint=$('#topPrintWaybillBtn');
    if(topPrint)topPrint.onclick=()=>triggerWaybillParentPrint(awb);
    const topPdf=$('#topSaveWaybillPdfBtn');
    if(topPdf)topPdf.onclick=()=>triggerWaybillPdfDownload(awb);
    return $('#documentFrame')
  }
  function previewDocument(frame,html){if(!frame.isConnected)return;frame.srcdoc=html;frame.hidden=false;$('#documentLoading')?.remove()}
  function documentError(frame,err){if(!frame.isConnected)return;const loading=$('#documentLoading');if(loading){loading.textContent=opsTr(err.message);loading.className='notice-error'}toast(opsTr(err.message))}
  async function showWaybill(awb){
    if(!requirePermission('shipments.read'))return;
    const base=shipments.find(x=>x.awb===awb);
    if(!base)return toast(opsTr('لم نعثر على الشحنة'));
    const frame=documentPreview(`${dt('waybill')} · ${awb}`,base);
    state.documentPreview={kind:'waybill',id:awb};
    try{
      const [documents,qr,bar]=await Promise.all([
        loadShipmentDocuments(awb),
        fetchCodeSvg(awb,'qr'),
        fetchCodeSvg(awb,'barcode')
      ]);
      const shipment={...base,...(documents.shipment||{}),tracking_url:documents.tracking_url||base.tracking_url};
      previewDocument(frame,waybillHtml(shipment,qr,bar,documents.waybill||{}));
    }catch(e){documentError(frame,e)}
  }

  function canManageDocuments(){
    return hasPermission('shipments.create')||hasPermission('shipments.edit');
  }
  function documentSummaryCard(label,value,note=''){
    return `<div class="card" style="padding:14px;min-width:0"><small style="display:block;color:#64748b;margin-bottom:5px">${safe(label)}</small><b style="display:block;overflow-wrap:anywhere">${safe(value||'—')}</b>${note?`<small style="display:block;margin-top:5px;color:#64748b">${safe(note)}</small>`:''}</div>`;
  }
  async function downloadStickerPdf(awb,parcelNumber=null){
    const path=parcelNumber==null
      ?`/api/shipments/${encodeURIComponent(awb)}/stickers/pdf`
      :`/api/shipments/${encodeURIComponent(awb)}/stickers/${encodeURIComponent(parcelNumber)}/pdf`;
    const fallback=parcelNumber==null?`${awb}-stickers.pdf`:`${awb}-P${String(parcelNumber).padStart(3,'0')}.pdf`;
    try{await downloadServerPdf(path,fallback)}
    catch(error){toast(opsTr(error.message||dt('loadError')))}
  }
  async function printStickers(awb,parcelNumbers=null){
    if(!canManageDocuments())return toast(opsTr('ليست لديك صلاحية لهذا الإجراء'));
    const body=parcelNumbers==null?{}:{parcel_numbers:parcelNumbers};
    try{
      await documentPost(`/api/shipments/${encodeURIComponent(awb)}/stickers/print`,body);
      const path=parcelNumbers?.length===1
        ?`/api/shipments/${encodeURIComponent(awb)}/stickers/${encodeURIComponent(parcelNumbers[0])}/pdf`
        :`/api/shipments/${encodeURIComponent(awb)}/stickers/pdf`;
      await openServerPdf(path,`${awb}-stickers.pdf`);
      toast(dt('printOpened'));
    }catch(error){toast(opsTr(error.message||dt('loadError')))}
  }
  async function previewSticker(awb,parcelNumber){
    const root=$('#modalRoot');
    const popup=window.open('about:blank','_blank');
    try{
      const {blob}=await fetchDocumentBlob(
        `/api/shipments/${encodeURIComponent(awb)}/stickers/${encodeURIComponent(parcelNumber)}/pdf`
      );
      const href=URL.createObjectURL(blob);
      if(popup)popup.location.href=href;
      else{
        const link=document.createElement('a');link.href=href;link.target='_blank';link.rel='noopener';
        document.body.appendChild(link);link.click();link.remove();
      }
      setTimeout(()=>URL.revokeObjectURL(href),120000);
    }catch(error){
      try{popup?.close()}catch(_){}
      toast(opsTr(error.message||dt('loadError')));
    }
  }
  async function archiveWaybill(awb,restore=false){
    if(!canManageDocuments())return toast(opsTr('ليست لديك صلاحية لهذا الإجراء'));
    if(restore&&accessRole()!=='system_admin')return toast(opsTr('ليست لديك صلاحية لهذا الإجراء'));
    try{
      await documentPost(`/api/shipments/${encodeURIComponent(awb)}/waybill/${restore?'restore':'archive'}`);
      toast(restore?dt('restoreDone'):dt('archiveDone'));
      await openShipmentDocuments(awb);
    }catch(error){toast(opsTr(error.message||dt('loadError')))}
  }
  async function openShipmentDocuments(awb){
    if(!requirePermission('shipments.read'))return;
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:920px"><div class="modal-head"><div><div class="eyebrow">${safe(awb)}</div><h2>${dt('documentCenter')}</h2></div><button class="icon-btn" data-close>×</button></div><p class="ops-loading">${dt('loading')}</p></section></div>`;
    wireModal();localizeNow(root);
    try{
      const documents=await loadShipmentDocuments(awb);
      if(!root.isConnected)return;
      const shipment=documents.shipment||{};
      const waybill=documents.waybill||{};
      const stickers=Array.isArray(documents.stickers)?documents.stickers:[];
      const archived=!!waybill.archived_at;
      const manage=canManageDocuments();
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:920px;max-height:92vh;overflow:auto">
        <div class="modal-head"><div><div class="eyebrow">${safe(awb)}</div><h2>${dt('documentCenter')}</h2></div><button class="icon-btn" data-close>×</button></div>
        <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:16px">
          ${documentSummaryCard(dt('waybillNumber'),waybill.waybill_number)}
          ${documentSummaryCard(dt('issued'),waybill.issued_at)}
          ${documentSummaryCard(dt('prints'),String(waybill.print_count||0))}
          ${documentSummaryCard(dt('downloads'),String(waybill.download_count||0))}
        </div>
        <div class="card" style="padding:16px;margin-bottom:16px">
          <div class="section-title" style="margin-top:0"><div><h3 style="margin:0">${dt('waybill')}</h3><small>${archived?dt('archived'):dt('active')}</small></div><span class="badge ${archived?'red':'green'}">${archived?dt('archived'):dt('active')}</span></div>
          <div class="record-meta" style="margin-bottom:12px">
            <span>${dt('issuingOffice')}: <b>${safe(shipment.origin_office||shipment.origin_office_code||shipment.origin||'—')}</b></span>
            <span>${dt('receivingOffice')}: <b>${safe(shipment.destination_office||shipment.destination_office_code||shipment.recipient_branch||shipment.destination||'—')}</b></span>
            <span>${dt('courier')}: <b>${safe(shipment.driver_name||opsTr('غير معيّن'))}</b></span>
          </div>
          <div class="ops-inline-actions" style="flex-wrap:wrap">
            <button class="btn light" type="button" data-doc-preview>▤ ${dt('preview')}</button>
            <button class="btn light" type="button" data-doc-download>📥 ${dt('downloadPdf')}</button>
            ${manage?`<button class="btn primary" type="button" data-doc-print>🖨️ ${dt('print')}</button>`:''}
            ${accessRole()==='system_admin'?(archived
              ?`<button class="btn light" type="button" data-doc-restore>↺ ${dt('restore')}</button>`
              :`<button class="btn danger" type="button" data-doc-archive>⌁ ${dt('archive')}</button>`):''}
          </div>
        </div>
        <div class="card" style="padding:16px">
          <div class="section-title" style="margin-top:0"><div><h3 style="margin:0">${dt('stickers')}</h3><small>${stickers.length} ${dt('parcel')}</small></div></div>
          <div class="ops-inline-actions" style="margin-bottom:14px;flex-wrap:wrap">
            <button class="btn light" type="button" data-stickers-download-all>📥 ${dt('downloadAll')}</button>
            ${manage?`<button class="btn primary" type="button" data-stickers-print-all>🖨️ ${dt('printAll')}</button>`:''}
          </div>
          <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px">
            ${stickers.map(sticker=>`<article class="card" style="padding:13px">
              <div class="shipment-top"><div><b translate="no">${safe(sticker.sticker_number)}</b><div class="ship-phone">${dt('parcel')} ${safe(sticker.parcel_number)} ${dt('of')} ${safe(sticker.total_parcels)}</div></div><span class="badge green">${safe(sticker.parcel_number)}/${safe(sticker.total_parcels)}</span></div>
              <div class="record-meta"><span>${dt('prints')}: <b>${safe(sticker.print_count||0)}</b></span><span>${dt('downloads')}: <b>${safe(sticker.download_count||0)}</b></span></div>
              <div class="ship-bottom">
                <button class="btn light small" type="button" data-sticker-preview="${safe(sticker.parcel_number)}">${dt('preview')}</button>
                <button class="btn light small" type="button" data-sticker-download="${safe(sticker.parcel_number)}">PDF</button>
                ${manage?`<button class="btn primary small" type="button" data-sticker-print="${safe(sticker.parcel_number)}">🖨️ ${dt('print')}</button>`:''}
              </div>
            </article>`).join('')||`<div class="empty">${dt('noStickers')}</div>`}
          </div>
        </div>
      </section></div>`;
      wireModal();localizeNow(root);
      $('[data-doc-preview]',root)?.addEventListener('click',()=>showWaybill(awb));
      $('[data-doc-download]',root)?.addEventListener('click',()=>triggerWaybillPdfDownload(awb));
      $('[data-doc-print]',root)?.addEventListener('click',()=>triggerWaybillParentPrint(awb));
      $('[data-doc-archive]',root)?.addEventListener('click',()=>archiveWaybill(awb,false));
      $('[data-doc-restore]',root)?.addEventListener('click',()=>archiveWaybill(awb,true));
      $('[data-stickers-download-all]',root)?.addEventListener('click',()=>downloadStickerPdf(awb));
      $('[data-stickers-print-all]',root)?.addEventListener('click',()=>printStickers(awb));
      $$('[data-sticker-preview]',root).forEach(button=>button.onclick=()=>previewSticker(awb,Number(button.dataset.stickerPreview)));
      $$('[data-sticker-download]',root).forEach(button=>button.onclick=()=>downloadStickerPdf(awb,Number(button.dataset.stickerDownload)));
      $$('[data-sticker-print]',root).forEach(button=>button.onclick=()=>printStickers(awb,[Number(button.dataset.stickerPrint)]));
    }catch(error){
      if(!root.isConnected)return;
      const loading=$('.ops-loading',root);
      if(loading){loading.className='notice-error';loading.textContent=opsTr(error.message||dt('loadError'))}
      toast(opsTr(error.message||dt('loadError')));
    }
  }

  async function printManifest(id){if(!requirePermission('routes.read'))return;const r=state.routes.find(x=>String(x.id)===String(id));if(!r)return toast(opsTr('لم نعثر على الرحلة'));const frame=documentPreview(`${opsTr('كشف الحمولة')} · ${r.code}`,r);state.documentPreview={kind:'manifest',id};try{const bars=await Promise.all(r.shipments.map(s=>fetchCodeSvg(s.awb,'barcode')));const cards=r.shipments.map((s,i)=>`<div class="row"><b>${safe(s.awb)}</b><span>${safe(s.recipient)}</span><span>${fmt(s.weight)} ${opsTr('كجم')}</span><img src="${bars[i]}" alt="${opsTr('barcode')}"></div>`).join('');previewDocument(frame,`<!doctype html><html lang="${document.documentElement.lang}" dir="${document.documentElement.dir}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${safe(r.code)}</title><style>body{font:16px Arial;margin:25px;color:#101e31}h1{border-bottom:4px solid #875832;padding:14px}.row{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #ddd;padding:12px;gap:10px;flex-wrap:wrap;break-inside:avoid}.row img{width:180px;max-width:100%;height:50px;object-fit:contain}@media print{button{display:none}}</style><button onclick="print()">${opsTr('طباعة كشف الحمولة')}</button><main class="sheet" data-document-kind="manifest" data-document-id="${safe(r.code)}"><h1 style="display:flex;align-items:center;gap:14px"><img src="${location.origin}/ghazala-logo.png?v=2" alt="${safe(opsTr('غزالا ترانسبورت'))}" style="width:56px;height:56px;object-fit:contain"><span>${opsTr('غزالا ترانسبورت')} · ${safe(r.code)}</span></h1><p>${opsTr(r.origin)} → ${opsTr(r.destination)} · ${opsTr('السائق')}: ${safe(r.driver_name)} · ${opsTr('المركبة')}: ${safe(r.vehicle_plate)}</p>${cards}</main></html>`)}catch(e){documentError(frame,e)}}
  function bindPodForm(pf){
    if(pf.dataset.podBound)return;
    pf.dataset.podBound='1';
    const canvas=$('#signatureCanvas',pf),ctx=canvas?.getContext('2d'),select=$('#proofAwb',pf);
    const photo=$('#podPhoto',pf),photoButton=$('#podPhotoButton',pf),send=$('#sendOtp',pf),loc=$('#podGps',pf),submit=$('#submitPod',pf);
    const draft={awb:select.value,hasInk:false,drawing:false,location:null,revision:0,submitting:false,savedProof:null,loadingProof:false};
    pf.podDraft=draft;
    const clearSignature=()=>{if(ctx)ctx.clearRect(0,0,canvas.width,canvas.height);draft.hasInk=false;draft.drawing=false};
    const syncPhoto=()=>{const file=photo?.files?.[0],label=$('#podPhotoLabel',pf),buttonLabel=$('#podPhotoButtonLabel',pf);if(buttonLabel)buttonLabel.textContent=opsTr(file?'تغيير الصورة':'التقاط أو اختيار صورة');if(label){if(file)label.innerHTML=`<span translate="no">${safe(file.name)}</span> · ${fmt(file.size/1024)} KB`;else label.textContent=opsTr('لم يتم اختيار صورة')}};
    const resetShipment=()=>{
      draft.awb=select.value;draft.revision++;draft.location=null;draft.savedProof=null;clearSignature();
      $$('input,textarea,button',pf).forEach(field=>field.disabled=!hasPermission('pod.create'));
      submit.textContent='✓ '+opsTr('تأكيد التسليم وحفظ الإثبات');
      const shipment=shipments.find(item=>item.awb===draft.awb);
      $('#receiverName',pf).value=shipment?.recipient||'';
      ['#receiverId','#otp','#podNote'].forEach(id=>$(id,pf).value='');
      if(photo)photo.value='';syncPhoto();
      const sms=$('#podSmsState',pf);sms.textContent='';sms.classList.remove('visible');
      $('#podLocationLabel',pf).textContent=opsTr('لم يتم تحديد الموقع');send.disabled=!hasPermission('pod.create');
      const summary=$('.ops-recipient-card',pf);
      if(summary&&shipment){summary.innerHTML=`<span>${opsTr('المستلم')}</span><b>${safe(shipment.recipient)}</b><small>${safe(opsTr(shipment.origin))} → ${safe(opsTr(shipment.destination))} · ${safe(opsTr(shipment.eta))}</small>`;localizeNow(summary)}
      loadSavedProof();
    };
    async function loadSavedProof(){
      if(!draft.awb){draft.loadingProof=false;$$('input,textarea,button',pf).forEach(field=>field.disabled=true);return}
      const awb=draft.awb,revision=draft.revision;draft.loadingProof=true;submit.disabled=true;
      const current=()=>pf.isConnected&&draft.awb===awb&&draft.revision===revision;
      try{
        const proof=await api(`/api/shipments/${encodeURIComponent(awb)}/pod`);
        if(!current())return;
        draft.savedProof=proof;$('#receiverName',pf).value=proof.recipient_name||'';$('#receiverId',pf).value=proof.recipient_id_suffix||'';$('#podNote',pf).value=proof.note||'';
        if(proof.latitude!=null&&proof.longitude!=null){draft.location={latitude:Number(proof.latitude),longitude:Number(proof.longitude)};$('#podLocationLabel',pf).textContent=`${proof.latitude}, ${proof.longitude}`;}
        if(proof.signature_data&&ctx){const image=new Image();image.onload=()=>{if(!current())return;clearSignature();ctx.drawImage(image,0,0,canvas.width/Math.min(window.devicePixelRatio||1,2),160);draft.hasInk=true};image.src=proof.signature_data}
        if(proof.photo_data)$('#podPhotoLabel',pf).textContent=opsTr('صورة إثبات التسليم محفوظة');
        const sms=$('#podSmsState',pf);sms.textContent=opsTr('إثبات التسليم محفوظ (للقراءة فقط)');sms.classList.add('visible');
        $$('input,textarea,button',pf).forEach(field=>field.disabled=true);submit.textContent=opsTr('إثبات التسليم محفوظ (للقراءة فقط)');
      }catch(err){if(current()&&err.status!==404)toast(opsTr(err.message))}
      finally{if(current()){draft.loadingProof=false;submit.disabled=!!draft.savedProof||!awb||!hasPermission('pod.create')}}
    }
    if(canvas&&ctx){
      const ratio=Math.min(window.devicePixelRatio||1,2),rect=canvas.getBoundingClientRect();
      canvas.width=Math.max(1,rect.width*ratio);canvas.height=160*ratio;
      ctx.scale(ratio,ratio);ctx.lineWidth=3;ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle='#101e31';
      const point=e=>{const r=canvas.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top]};
      canvas.onpointerdown=e=>{if(draft.submitting||draft.savedProof||!hasPermission('pod.create'))return;draft.drawing=true;canvas.setPointerCapture(e.pointerId);const [x,y]=point(e);ctx.beginPath();ctx.moveTo(x,y)};
      canvas.onpointermove=e=>{if(!draft.drawing)return;const [x,y]=point(e);ctx.lineTo(x,y);ctx.stroke();draft.hasInk=true};
      canvas.onpointerup=canvas.onpointercancel=()=>{draft.drawing=false};
      $('#clearSignature',pf).onclick=()=>{if(!draft.submitting&&!draft.savedProof&&hasPermission('pod.create'))clearSignature()};
    }
    select.onchange=()=>{if(draft.submitting){select.value=draft.awb;return}resetShipment()};
    loc.onclick=()=>{if(!requirePermission('pod.create'))return;const awb=draft.awb,revision=draft.revision;gps((lat,lng)=>{if(!pf.isConnected||draft.awb!==awb||draft.revision!==revision||draft.savedProof||draft.submitting)return;draft.location={latitude:Number(lat),longitude:Number(lng)};$('#podLocationLabel',pf).textContent=`${lat}, ${lng}`;toast(opsTr('تم تحديد موقع التسليم'))})};
    send.onclick=async()=>{
      if(!requirePermission('pod.create'))return;
      const awb=draft.awb,revision=draft.revision;send.disabled=true;
      try{const result=await api(`/api/shipments/${encodeURIComponent(awb)}/otp`,{method:'POST',body:'{}'});if(!pf.isConnected||draft.awb!==awb||draft.revision!==revision||draft.savedProof)return;const msg=$('#podSmsState',pf);msg.textContent=result.delivery==='sent'?opsTr('تم إرسال رمز التحقق إلى جوال المستلم'):`${opsTr('رمز تجريبي لعدم ربط SMS')}: ${result.demo_code}`;msg.classList.add('visible');toast(result.delivery==='sent'?opsTr('تم إرسال رمز التحقق'):`${opsTr('رمز تجريبي')}: ${result.demo_code}`)}
      catch(err){if(pf.isConnected&&draft.revision===revision)toast(opsTr(err.message))}
      finally{if(pf.isConnected&&draft.revision===revision)send.disabled=!!draft.savedProof||!hasPermission('pod.create')}
    };
    if(photo){if(photoButton)photoButton.onclick=()=>photo.click();photo.onchange=syncPhoto;syncPhoto()}
    pf.onsubmit=async e=>{
      e.preventDefault();if(!requirePermission('pod.create')||draft.submitting||draft.savedProof||draft.loadingProof)return;
      if(!draft.hasInk)return toast(opsTr('أضف توقيع المستلم قبل تأكيد التسليم'));
      const awb=draft.awb,file=photo?.files?.[0],payload={recipient_name:$('#receiverName',pf).value.trim(),recipient_id_suffix:$('#receiverId',pf).value.trim(),otp:$('#otp',pf).value.trim(),signature_data:canvas.toDataURL('image/png'),photo_data:'',note:$('#podNote',pf).value,latitude:draft.location?.latitude??null,longitude:draft.location?.longitude??null};
      draft.submitting=true;draft.revision++;[select,submit,send,loc,photo,photoButton].filter(Boolean).forEach(field=>field.disabled=true);
      try{
        if(file){try{payload.photo_data=await compressPhoto(file)}catch(err){throw new Error(opsTr('تعذر تجهيز صورة إثبات التسليم'))}}
        await api(`/api/shipments/${encodeURIComponent(awb)}/pod`,{method:'POST',body:JSON.stringify(payload)});
        toast(opsTr('تم تأكيد التسليم وحفظ إثباته'));await load();
      }catch(err){toast(opsTr(err.message))}
      finally{draft.submitting=false;[select,submit,send,loc,photo,photoButton].filter(Boolean).forEach(field=>{if(field.isConnected)field.disabled=field!==select&&!hasPermission('pod.create')})}
    };
    resetShipment();
  }
  async function openPaymentLedger(awb){
    if(!requirePermission('shipments.payment'))return;
    const normalized=String(awb||'').trim().toUpperCase();
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:780px"><div class="modal-head"><div><div class="eyebrow">${safe(normalized)}</div><h2>${pt('title')}</h2></div><button class="icon-btn" type="button" data-close>×</button></div><p>${pt('loading')}</p></section></div>`;
    wireModal();

    try{
      const [invoiceRows,paymentRows]=await Promise.all([
        api('/api/invoices'),
        api('/api/payments')
      ]);
      const invoices=Array.isArray(invoiceRows)?invoiceRows:[];
      const payments=Array.isArray(paymentRows)?paymentRows:[];
      const invoice=invoices.find(row=>String(row.awb||'').trim().toUpperCase()===normalized);

      if(!invoice){
        root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:620px">
          <div class="modal-head"><div><div class="eyebrow">${safe(normalized)}</div><h2>${pt('legacy')}</h2></div><button class="icon-btn" type="button" data-close>×</button></div>
          <div class="notice-error">${pt('invoiceMissing')}</div>
          <div class="ops-form-actions" style="margin-top:16px"><button class="btn light" type="button" data-close>${pt('close')}</button></div>
        </section></div>`;
        wireModal();
        return;
      }

      const invoicePayments=payments.filter(row=>String(row.invoice_number||'')===String(invoice.invoice_number||''));
      const balance=Number(invoice.balance||0);
      const fullyPaid=invoice.status==='paid'||balance<=0.005;
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:820px;max-height:92vh;overflow:auto">
        <div class="modal-head">
          <div><div class="eyebrow">${safe(normalized)}</div><h2>${pt('title')}</h2></div>
          <button class="icon-btn" type="button" data-close>×</button>
        </div>

        <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:16px">
          <div class="card" style="padding:13px"><small>${pt('invoice')}</small><b style="display:block;margin-top:5px">${safe(invoice.invoice_number)}</b></div>
          <div class="card" style="padding:13px"><small>${pt('total')}</small><b style="display:block;margin-top:5px">${paymentMoney(invoice.total_amount,invoice.currency)}</b></div>
          <div class="card" style="padding:13px"><small>${pt('paid')}</small><b style="display:block;margin-top:5px">${paymentMoney(invoice.amount_paid,invoice.currency)}</b></div>
          <div class="card" style="padding:13px"><small>${pt('balance')}</small><b style="display:block;margin-top:5px">${paymentMoney(invoice.balance,invoice.currency)}</b></div>
        </div>

        <div class="card" style="padding:14px;margin-bottom:16px">
          <div class="summary-row"><span>${pt('shipment')}</span><b>${safe(invoice.awb||normalized)}</b></div>
          <div class="summary-row"><span>${pt('status')}</span><b>${safe(paymentStatusLabel(invoice.status))}</b></div>
          <div class="summary-row"><span>${pt('customer')}</span><b>${safe(invoice.customer_account_name||invoice.customer_name||'—')}</b></div>
          ${(invoice.billing_company_name||invoice.company_name) && String(invoice.billing_company_name||invoice.company_name)!==String(invoice.customer_account_name||invoice.customer_name||'')
            ?`<div class="summary-row"><span>${pt('company')}</span><b>${safe(invoice.billing_company_name||invoice.company_name)}</b></div>`:''}
        </div>

        ${fullyPaid
          ?`<div class="notice-success" style="margin-bottom:16px">${pt('fullyPaid')}</div>`
          :`<form id="invoicePaymentForm" class="form-grid card" style="padding:16px;margin-bottom:16px">
              <label class="field"><span>${pt('amount')} *</span><input name="amount" type="number" min="0.01" step="0.01" max="${safe(balance.toFixed(2))}" value="${safe(balance.toFixed(2))}" required></label>
              <label class="field"><span>${pt('method')} *</span>
                <select name="method" required>
                  <option value="cash">${pt('cash')}</option>
                  <option value="card">${pt('card')}</option>
                  <option value="bank_transfer">${pt('bank_transfer')}</option>
                  <option value="online">${pt('online')}</option>
                  <option value="other">${pt('other')}</option>
                </select>
              </label>
              <label class="field span-2"><span>${pt('reference')}</span><input name="reference" maxlength="160" placeholder="${safe(pt('referencePlaceholder'))}" autocomplete="off"></label>
              <label class="field span-2"><span>${pt('note')}</span><textarea name="note" maxlength="1000" placeholder="${safe(pt('notePlaceholder'))}"></textarea></label>
              <div class="field span-2"><button class="btn primary full" type="submit">✓ ${pt('submit')}</button></div>
            </form>`}

        <div class="card" style="padding:16px">
          <div class="section-title" style="margin-top:0"><h3>${pt('history')}</h3><span class="badge">${invoicePayments.length}</span></div>
          <div style="display:grid;gap:9px">
            ${invoicePayments.map(payment=>`
              <div class="record-meta" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px">
                <span><small>${pt('paymentNumber')}</small><b style="display:block">${safe(payment.payment_number||'')}</b></span>
                <span><small>${pt('amount')}</small><b style="display:block">${paymentMoney(payment.amount,payment.currency)}</b></span>
                <span><small>${pt('method')}</small><b style="display:block">${safe(pt(payment.method)||payment.method||'—')}</b></span>
                <span><small>${pt('reference')}</small><b style="display:block">${safe(payment.reference||'—')}</b></span>
                <span><small>${pt('date')}</small><b style="display:block">${safe(payment.paid_at||payment.created_at||'—')}</b></span>
                ${payment.note?`<span style="grid-column:1/-1"><small>${pt('note')}</small><b style="display:block">${safe(payment.note)}</b></span>`:''}
              </div>`).join('')||`<p class="kpi-note">${pt('noPayments')}</p>`}
          </div>
        </div>
      </section></div>`;
      wireModal();
      localizeNow(root);

      const form=$('#invoicePaymentForm',root);
      if(form){
        form.onsubmit=async event=>{
          event.preventDefault();
          const data={
            amount:form.elements.amount?.value??'',
            method:form.elements.method?.value??'cash',
            reference:form.elements.reference?.value??'',
            note:form.elements.note?.value??''
          };
          const amount=Number(data.amount||0);
          if(!Number.isFinite(amount)||amount<=0||amount>balance+0.005){
            return toast(pt('invalidAmount'));
          }
          data.amount=Number(amount.toFixed(2));
          data.reference=String(data.reference||'').trim();
          data.note=String(data.note||'').trim();
          const button=form.querySelector('[type="submit"]');
          button.disabled=true;
          try{
            const result=await api(`/api/invoices/${encodeURIComponent(invoice.invoice_number)}/payments`,{
              method:'POST',
              body:JSON.stringify(data)
            });
            toast(`${pt('recorded')} · ${safe(result?.payment?.payment_number||'')}`);
            await load();
            setTimeout(()=>openPaymentLedger(normalized),0);
          }catch(error){
            toast(opsTr(error.message));
          }finally{
            if(button?.isConnected)button.disabled=false;
          }
        };
      }
    }catch(error){
      root.innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal" style="max-width:620px"><div class="modal-head"><h2>${pt('title')}</h2><button class="icon-btn" type="button" data-close>×</button></div><div class="notice-error">${safe(opsTr(error.message||'Could not load invoice.'))}</div></section></div>`;
      wireModal();
    }
  }


  const SEARCH_AUDIT_TEXT={
    searchTitle:{ar:'البحث المركزي',en:'Central Search'},
    searchSub:{ar:'ابحث في الشحنات والعملاء والفواتير والمدفوعات والسائقين والمركبات والرحلات والموظفين والحملات.',en:'Search shipments, clients, invoices, payments, drivers, vehicles, routes, staff and campaigns.'},
    searchPlaceholder:{ar:'اكتب رقم شحنة، اسم عميل، جوال، فاتورة، دفعة، سائق، لوحة مركبة...',en:'Search AWB, customer, mobile, invoice, payment, driver, vehicle plate...'},
    typeAtLeast:{ar:'اكتب حرفين على الأقل للبحث.',en:'Type at least 2 characters to search.'},
    noResults:{ar:'لا توجد نتائج مطابقة.',en:'No matching results.'},
    results:{ar:'النتائج',en:'Results'},
    open:{ar:'فتح',en:'Open'},
    audit:{ar:'سجل التدقيق',en:'Audit Log'},
    auditSub:{ar:'سجل مركزي غير قابل للتعديل للأحداث الحساسة والتغييرات التشغيلية.',en:'Central immutable record of sensitive actions and operational changes.'},
    refresh:{ar:'تحديث',en:'Refresh'},
    total:{ar:'إجمالي الأحداث',en:'Total Events'},
    last24:{ar:'آخر 24 ساعة',en:'Last 24 Hours'},
    lastHour:{ar:'آخر ساعة',en:'Last Hour'},
    topActors:{ar:'أكثر المستخدمين نشاطاً',en:'Top Actors'},
    actor:{ar:'المستخدم',en:'Actor'},
    branch:{ar:'الفرع',en:'Branch'},
    action:{ar:'الإجراء',en:'Action'},
    entity:{ar:'الكيان',en:'Entity'},
    date:{ar:'التاريخ',en:'Date'},
    filters:{ar:'الفلاتر',en:'Filters'},
    from:{ar:'من',en:'From'},
    to:{ar:'إلى',en:'To'},
    allActions:{ar:'كل الإجراءات',en:'All Actions'},
    allEntities:{ar:'كل الكيانات',en:'All Entities'},
    auditSearch:{ar:'ابحث بالإجراء أو المستخدم أو الفرع أو الكيان...',en:'Search action, actor, branch or entity...'},
    details:{ar:'التفاصيل',en:'Details'},
    loadMore:{ar:'تحميل المزيد',en:'Load More'},
    noAudit:{ar:'لا توجد سجلات مطابقة.',en:'No matching audit records.'},
    skipped:{ar:'تم التخطي',en:'Skipped'},
    alreadySent:{ar:'أرسل مسبقاً',en:'Already Sent'},
    entityShipment:{ar:'شحنة',en:'Shipment'},
    entityRoute:{ar:'رحلة',en:'Route'},
    entityDriver:{ar:'سائق',en:'Driver'},
    entityVehicle:{ar:'مركبة',en:'Vehicle'},
    entityClient:{ar:'عميل',en:'Client'},
    entityInvoice:{ar:'فاتورة',en:'Invoice'},
    entityPayment:{ar:'دفعة',en:'Payment'},
    entityUser:{ar:'مستخدم',en:'User'},
    entityCampaign:{ar:'حملة',en:'Campaign'},
  };
  function sat(key){return opsDictText('audit',key,SEARCH_AUDIT_TEXT[key])}
  function saDate(value){
    if(!value)return '—';
    const raw=String(value).trim();
    const d=new Date(raw.includes('T')||raw.endsWith('Z')?raw:raw.replace(' ','T')+'Z');
    if(Number.isNaN(d.getTime()))return safe(value);
    try{
      return d.toLocaleString(opsLocaleTag(),{
        calendar:'gregory',numberingSystem:currentLang==='ar'?'arab':'latn',
        year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'
      });
    }catch(_){return safe(value)}
  }
  function centralSearchGroupLabel(key){
    const labels={
      shipments:{ar:'الشحنات',en:'Shipments'},
      clients:{ar:'العملاء',en:'Clients'},
      invoices:{ar:'الفواتير',en:'Invoices'},
      payments:{ar:'المدفوعات',en:'Payments'},
      drivers:{ar:'السائقون',en:'Drivers'},
      vehicles:{ar:'المركبات',en:'Vehicles'},
      routes:{ar:'الرحلات',en:'Routes'},
      staff:{ar:'الموظفون',en:'Staff'},
      campaigns:{ar:'الحملات',en:'Campaigns'}
    };
    return opsDictText('audit','group_'+key,labels[key]);
  }
  function centralSearchIcon(type){
    return ({shipment:'▤',client:'◉',invoice:'▧',payment:'✓',driver:'♟',vehicle:'▣',route:'⇄',staff:'♙',campaign:'◇'})[type]||'⌕';
  }
  function centralSearchResultCard(row,index){
    const extras=[];
    if(row.status)extras.push(`<span class="badge">${safe(opsTr(row.status))}</span>`);
    if(row.recipient)extras.push(`<span>${safe(row.recipient)}</span>`);
    if(row.customer_name)extras.push(`<span>${safe(row.customer_name)}</span>`);
    if(row.amount!=null)extras.push(`<span>${fmt(row.amount)} ${safe(row.currency||'SAR')}</span>`);
    if(row.total_amount!=null)extras.push(`<span>${fmt(row.total_amount)} ${safe(row.currency||'SAR')}</span>`);
    if(row.vehicle_plate)extras.push(`<span>${safe(row.vehicle_plate)}</span>`);
    if(row.driver_name)extras.push(`<span>${safe(row.driver_name)}</span>`);
    if(row.role)extras.push(`<span>${safe(opsTr(accessRoleLabels?.[row.role]||row.role))}</span>`);
    if(row.mobile)extras.push(`<span translate="no">${safe(row.mobile)}</span>`);
    return `<article class="card" style="padding:12px;box-shadow:none">
      <div class="shipment-top">
        <span class="icon-square">${centralSearchIcon(row.type)}</span>
        <div class="ship-name" style="min-width:0">
          <b>${safe(row.title||row.key||'—')}</b>
          <div class="ship-phone">${safe(row.subtitle||'')}</div>
        </div>
        <span class="push"></span>
        <button class="btn light small" data-central-index="${Number(index)}">${sat('open')}</button>
      </div>
      ${extras.length?`<div class="record-meta" style="margin-top:8px">${extras.join('')}</div>`:''}
    </article>`;
  }

  function centralSearchWithStaffFallback(payload,searchValue){
    const groups={...(payload?.groups||{})};
    if(hasPermission('users.manage')){
      const term=String(searchValue||payload?.query||'').trim().toLowerCase();
      const local=(state.users||[]).filter(account=>{
        const role=typeof accessRole==='function'?accessRole(account):(account.access_role||account.role||'');
        return [account.display_name,account.username,account.mobile,account.national_id,role,accessRoleLabels?.[role]]
          .some(value=>String(value||'').toLowerCase().includes(term));
      }).map(account=>{
        const role=typeof accessRole==='function'?accessRole(account):(account.access_role||account.role||'');
        return {
          type:'staff',
          id:account.id,
          key:account.username||String(account.id),
          title:account.display_name||account.username||String(account.id),
          subtitle:[account.username,opsTr(accessRoleLabels?.[role]||role||'')].filter(Boolean).join(' · '),
          status:account.is_active===0||account.is_active===false?'inactive':'active',
          role,
          mobile:account.mobile||''
        };
      });
      const existing=Array.isArray(groups.staff)?groups.staff:[];
      const merged=[...existing];
      local.forEach(row=>{
        if(!merged.some(item=>String(item.id)===String(row.id)))merged.push(row);
      });
      groups.staff=merged.slice(0,8);
    }
    const counts={...(payload?.counts||{})};
    Object.keys(groups).forEach(key=>{counts[key]=Array.isArray(groups[key])?groups[key].length:0});
    return {
      ...(payload||{}),
      query:String(payload?.query??searchValue??''),
      groups,
      counts,
      total:Object.values(counts).reduce((sum,value)=>sum+Number(value||0),0)
    };
  }

  function renderCentralSearchResults(root,payload){
    if(!root)return;
    const q=String(payload?.query||'');
    if(q.length<2){
      root.innerHTML=`<div class="card empty">${sat('typeAtLeast')}</div>`;
      return;
    }
    const groups=payload?.groups||{};
    const indexedRows=[];
    const html=Object.entries(groups).filter(([,rows])=>Array.isArray(rows)&&rows.length).map(([key,rows])=>`
      <section style="margin-top:14px">
        <div class="section-title" style="margin:0 0 8px"><h3>${centralSearchGroupLabel(key)}</h3><span class="badge">${rows.length}</span></div>
        <div class="grid" style="gap:8px">${rows.map(row=>{
          const index=indexedRows.push(row)-1;
          return centralSearchResultCard(row,index);
        }).join('')}</div>
      </section>`).join('');
    root.innerHTML=html||`<div class="card empty">${sat('noResults')}</div>`;
    root.querySelectorAll('[data-central-index]').forEach(button=>{
      button.onclick=()=>{
        const row=indexedRows[Number(button.dataset.centralIndex)];
        if(row)openCentralSearchResult(row);
      };
    });
  }

  function centralDriverDetailsModal(id){
    const driver=(drivers||[]).find(item=>String(item.id)===String(id));
    if(!driver)return toast(opsTr('لم يتم العثور على السائق'));
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close>
      <section class="modal ops-modal" style="max-width:720px">
        <div class="modal-head">
          <div><div class="eyebrow">GHAZALA DRIVER · ${safe(driver.id)}</div><h2>${safe(driver.name||'—')}</h2></div>
          <button class="icon-btn" type="button" data-close>×</button>
        </div>
        <div class="card" style="padding:14px">
          <div class="summary-row"><span>${opsTr('رقم الهوية')}</span><b>${safe(driver.national_id||'—')}</b></div>
          <div class="summary-row"><span>${opsTr('رقم الجوال')}</span><b>${safe(driver.mobile||'—')}</b></div>
          <div class="summary-row"><span>${opsTr('الفرع')}</span><b>${safe(driver.branch||'—')}</b></div>
          <div class="summary-row"><span>${opsTr('الحالة')}</span><b>${safe(opsTr(driver.status||'—'))}</b></div>
          <div class="summary-row"><span>${opsTr('الموقع الحالي')}</span><b>${safe(cityPlaceDisplay(driver.location_text||'—'))}</b></div>
          ${(driver.latitude!=null&&driver.longitude!=null)?`<div class="summary-row"><span>GPS</span><b>${safe(driver.latitude)}, ${safe(driver.longitude)}</b></div>`:''}
        </div>
        <div class="ops-inline-actions" style="margin-top:14px">
          ${hasPermission('drivers.manage')?`<button class="btn primary" type="button" data-central-driver-edit="${safe(driver.id)}">${opsTr('تعديل السائق')}</button>`:''}
          ${hasPermission('drivers.location')?`<button class="btn light" type="button" data-central-driver-location="${safe(driver.id)}">${opsTr('تحديث الموقع')}</button>`:''}
          ${driver.mobile?`<a class="btn light" href="tel:${safe(driver.mobile)}">☎ ${safe(driver.mobile)}</a>`:''}
        </div>
      </section>
    </div>`;
    wireModal();
    localizeNow(root);
    $('[data-central-driver-edit]',root)?.addEventListener('click',()=>{
      closeModal();
      driverModal(Number(driver.id));
    });
    $('[data-central-driver-location]',root)?.addEventListener('click',()=>{
      closeModal();
      locationModal(Number(driver.id));
    });
  }

  async function centralFinanceAwb(row){
    const direct=String(row?.awb||row?.shipment_awb||'').trim().toUpperCase();
    if(direct)return direct;
    const embedded=JSON.stringify(row||{}).match(/GHZ-\d+/i);
    if(embedded)return embedded[0].toUpperCase();
    try{
      if(row?.type==='invoice'){
        const invoices=await api('/api/invoices');
        const invoice=(Array.isArray(invoices)?invoices:[]).find(item=>
          String(item.id)===String(row.id)||
          String(item.invoice_number||'').toUpperCase()===String(row.key||row.title||'').toUpperCase()
        );
        return String(invoice?.awb||'').trim().toUpperCase();
      }
      if(row?.type==='payment'){
        const payments=await api('/api/payments');
        const payment=(Array.isArray(payments)?payments:[]).find(item=>
          String(item.id)===String(row.id)||
          String(item.payment_number||'').toUpperCase()===String(row.key||row.title||'').toUpperCase()
        );
        if(payment?.awb)return String(payment.awb).trim().toUpperCase();
        const invoiceNumber=String(payment?.invoice_number||row?.invoice_number||'').trim();
        if(invoiceNumber){
          const invoices=await api('/api/invoices');
          const invoice=(Array.isArray(invoices)?invoices:[]).find(item=>String(item.invoice_number||'')===invoiceNumber);
          return String(invoice?.awb||'').trim().toUpperCase();
        }
      }
    }catch(error){
      toast(opsTr(error.message));
    }
    return '';
  }

  function centralSearchFocusText(value,scope=document){
    const needle=String(value||'').trim().toLowerCase();
    if(!needle)return null;
    const candidates=[...scope.querySelectorAll('article,.card,.record-meta,.summary-row')];
    const target=candidates.find(node=>String(node.textContent||'').toLowerCase().includes(needle));
    if(!target)return null;
    const previousOutline=target.style.outline;
    const previousShadow=target.style.boxShadow;
    const previousRadius=target.style.borderRadius;
    target.scrollIntoView?.({behavior:'smooth',block:'center'});
    target.style.outline='3px solid #f97316';
    target.style.boxShadow='0 0 0 6px rgba(249,115,22,.15)';
    target.style.borderRadius=target.style.borderRadius||'12px';
    setTimeout(()=>{
      if(!target.isConnected)return;
      target.style.outline=previousOutline;
      target.style.boxShadow=previousShadow;
      target.style.borderRadius=previousRadius;
    },2400);
    return target;
  }

  async function centralSearchOpenFinance(row){
    const awb=await centralFinanceAwb(row);
    if(!awb){
      return toast(row?.type==='invoice'
        ?opsTr('تعذر العثور على الشحنة المرتبطة بالفاتورة')
        :opsTr('تعذر العثور على الشحنة المرتبطة بالدفعة'));
    }
    await openPaymentLedger(awb);
    const exact=String(row?.key||row?.title||'').trim();
    if(exact){
      setTimeout(()=>centralSearchFocusText(exact,$('#modalRoot')||document),80);
    }
  }

  function centralSearchFocusPage(value){
    const exact=String(value||'').trim();
    if(!exact)return;
    setTimeout(()=>centralSearchFocusText(exact,app||document),140);
  }

  function centralSearchFocusRoute(value){
    const code=String(value||'').trim();
    if(!code)return;
    setTimeout(()=>{
      let target=null;
      try{
        target=(app||document).querySelector(`.ops-route-card[data-route-code="${CSS.escape(code)}"]`);
      }catch(_){ }
      if(!target){
        target=[...(app||document).querySelectorAll('.ops-route-card')].find(card=>{
          const heading=card.querySelector('h3');
          return String(heading?.textContent||'').trim()===code;
        })||null;
      }
      if(!target){
        toast(opsTr('تعذر تحديد بطاقة الرحلة المطلوبة'));
        return;
      }
      const previousOutline=target.style.outline;
      const previousShadow=target.style.boxShadow;
      const previousRadius=target.style.borderRadius;
      target.scrollIntoView?.({behavior:'smooth',block:'center'});
      target.style.outline='3px solid #f97316';
      target.style.boxShadow='0 0 0 6px rgba(249,115,22,.15), 0 18px 42px rgba(15,23,42,.12)';
      target.style.borderRadius=target.style.borderRadius||'12px';
      setTimeout(()=>{
        if(!target.isConnected)return;
        target.style.outline=previousOutline;
        target.style.boxShadow=previousShadow;
        target.style.borderRadius=previousRadius;
      },2400);
    },180);
  }

  async function openCentralSearchResult(row){
    const type=String(row?.type||'');
    const id=row?.id;
    const key=row?.key;
    closeModal();
    state.auditOpen=false;

    if(type==='shipment'){
      const awb=String(row?.awb||key||'').trim().toUpperCase();
      if(!awb)return;
      tracking=awb;
      const hash='#track='+encodeURIComponent(awb);
      history.replaceState(null,'',location.pathname+location.search+hash);
      page='tracking';
      window.render();
      requestAnimationFrame(()=>autoTrackFragment());
      // A second guarded pass covers slower DOM paints and guarantees that an
      // Open action does not stop at merely prefilling the AWB field.
      setTimeout(()=>{
        if(page==='tracking'&&String(tracking||'').trim().toUpperCase()===awb)autoTrackFragment();
      },180);
      return;
    }
    if(type==='client'){
      page='clients';window.render();
      setTimeout(()=>{if(id)clientDetailsModal(id)},100);
      return;
    }
    if(type==='vehicle'){
      page='drivers';window.render();
      setTimeout(()=>{if(id)fleetDetailsModal(id)},100);
      return;
    }
    if(type==='driver'){
      // Refresh the scoped driver collection before opening so a stale local
      // list cannot route the user to the wrong driver record.
      try{
        const fresh=await api('/api/drivers');
        if(Array.isArray(fresh))drivers=fresh;
      }catch(_){}
      page='drivers';window.render();
      setTimeout(()=>{if(id)centralDriverDetailsModal(id)},100);
      return;
    }
    if(type==='route'){
      page='dispatch';window.render();
      centralSearchFocusRoute(key||row?.title);
      return;
    }
    if(type==='staff'){
      page='staff';window.render();
      setTimeout(()=>{if(id)openUserAccount(Number(id))},120);
      return;
    }
    if(type==='campaign'){
      page='campaigns';window.render();
      centralSearchFocusPage(row?.title||key);
      return;
    }
    if(type==='invoice'||type==='payment'){
      await centralSearchOpenFinance(row);
      return;
    }
    page='home';window.render();
  }
  function centralSearchModal(initial=''){
    if(!user||accessRole()==='customer')return;
    const root=$('#modalRoot');
    root.innerHTML=`<div class="modal-backdrop" data-close>
      <section class="modal ops-modal" style="max-width:980px;max-height:94vh;overflow:auto">
        <div class="modal-head">
          <div><div class="eyebrow">${safe(OPS_UI_OVERRIDES?.[currentLang]?.audit?.searchEyebrow||'GHAZALA COMMAND SEARCH')}</div><h2>${sat('searchTitle')}</h2><p>${sat('searchSub')}</p></div>
          <button class="icon-btn" data-close>×</button>
        </div>
        <label class="search" style="width:100%;margin:8px 0 14px">⌕
          <input id="centralSearchInput" autocomplete="off" placeholder="${safe(sat('searchPlaceholder'))}" value="${safe(initial)}">
        </label>
        <div id="centralSearchResults"><div class="card empty">${sat('typeAtLeast')}</div></div>
      </section>
    </div>`;
    wireModal();
    const input=$('#centralSearchInput',root);
    const output=$('#centralSearchResults',root);
    let timer=0,seq=0;
    const run=async()=>{
      const value=String(input?.value||'').trim();
      if(value.length<2){
        renderCentralSearchResults(output,{query:value,groups:{}});
        return;
      }
      const request=++seq;
      output.innerHTML=`<div class="card empty">${opsTr('جارٍ تحميل البيانات…')}</div>`;
      try{
        if(hasPermission('users.manage')&&(!Array.isArray(state.users)||!state.users.length)){
          try{await refreshOps(true)}catch(_){}
        }
        const data=await api(`/api/search?q=${encodeURIComponent(value)}&limit=8`);
        const enriched=centralSearchWithStaffFallback(data,value);
        if(request===seq)renderCentralSearchResults(output,enriched);
      }catch(error){
        if(request===seq)output.innerHTML=`<div class="notice-error">${safe(opsTr(error.message))}</div>`;
      }
    };
    input.oninput=()=>{
      clearTimeout(timer);
      timer=setTimeout(run,260);
    };
    input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();clearTimeout(timer);run()}};
    setTimeout(()=>{input?.focus();if(String(initial).trim().length>=2)run()},20);
  }

  function auditEntityTypeLabel(type){
    const normalized=String(type||'').trim().toLowerCase().replace(/[\s-]+/g,'_');
    const map={
      shipment:'entityShipment',shipments:'entityShipment',
      route:'entityRoute',route_run:'entityRoute',routes:'entityRoute',
      driver:'entityDriver',drivers:'entityDriver',
      vehicle:'entityVehicle',vehicles:'entityVehicle',
      client:'entityClient',customer:'entityClient',clients:'entityClient',
      invoice:'entityInvoice',invoices:'entityInvoice',
      payment:'entityPayment',payments:'entityPayment',
      user:'entityUser',staff:'entityUser',users:'entityUser',
      campaign:'entityCampaign',campaigns:'entityCampaign'
    };
    return sat(map[normalized]||'entity')+(map[normalized]?'':` (${String(type||'—')})`);
  }

  function auditEntityReference(row){
    const type=String(row?.entity_type||'').trim().toLowerCase().replace(/[\s-]+/g,'_');
    const id=String(row?.entity_id??'').trim();

    // Prefer any business reference already supplied by the API.
    const direct={
      shipment:row?.awb||row?.shipment_awb,
      route:row?.route_code,
      route_run:row?.route_code,
      vehicle:row?.plate||row?.vehicle_plate,
      driver:row?.driver_name,
      client:row?.client_code||row?.customer_code,
      customer:row?.client_code||row?.customer_code,
      invoice:row?.invoice_number,
      payment:row?.payment_number,
      user:row?.username||row?.display_name,
      staff:row?.username||row?.display_name,
      campaign:row?.campaign_code||row?.promo_code
    }[type];
    if(direct)return String(direct);

    // Fall back to the already-loaded operational records.
    if((type==='shipment'||type==='shipments')&&id){
      const item=(Array.isArray(shipments)?shipments:[]).find(x=>String(x?.id)===id);
      if(item?.awb)return String(item.awb);
    }
    if((type==='route'||type==='route_run'||type==='routes')&&id){
      const item=(Array.isArray(state.routes)?state.routes:[]).find(x=>String(x?.id)===id);
      if(item?.code)return String(item.code);
    }
    if((type==='vehicle'||type==='vehicles')&&id){
      const item=(Array.isArray(state.vehicles)?state.vehicles:[]).find(x=>String(x?.id)===id);
      if(item?.plate)return String(item.plate);
    }
    if((type==='client'||type==='customer'||type==='clients')&&id){
      const item=(Array.isArray(state.clients)?state.clients:[]).find(x=>String(x?.id)===id);
      if(item?.client_code)return String(item.client_code);
      if(item?.name)return String(item.name);
    }
    if((type==='user'||type==='staff'||type==='users')&&id){
      const item=(Array.isArray(state.users)?state.users:[]).find(x=>String(x?.id)===id);
      if(item?.username)return String(item.username);
      if(item?.display_name)return String(item.display_name);
    }
    if((type==='campaign'||type==='campaigns')&&id){
      const item=(Array.isArray(state.campaigns)?state.campaigns:[]).find(x=>String(x?.id)===id);
      if(item?.code)return String(item.code);
      if(item?.name)return String(item.name);
    }
    return id||'—';
  }

  function auditEntityLabel(row){
    const typeLabel=auditEntityTypeLabel(row?.entity_type);
    const reference=auditEntityReference(row);
    return reference&&reference!=='—'?`${typeLabel} · ${reference}`:typeLabel;
  }

  function auditMetaMarkup(row){
    const ignored=new Set([
      'id','action','entity_type','entity_id','actor_user_id','branch_id','actor_name','actor_username',
      'branch_name','branch_code','branch_city','created_at'
    ]);
    const details=Object.entries(row||{}).filter(([key,value])=>!ignored.has(key)&&value!==null&&value!==''&&value!==undefined);
    if(!details.length)return '';
    return `<details style="margin-top:8px"><summary class="link" style="cursor:pointer">${sat('details')}</summary>
      <div class="record-meta" style="margin-top:8px">${details.map(([key,value])=>{
        let shown=value;
        if(typeof value==='string'&&(value.trim().startsWith('{')||value.trim().startsWith('['))){
          try{shown=JSON.stringify(JSON.parse(value),null,2)}catch(_){}
        }
        return `<span style="overflow-wrap:anywhere"><b>${safe(key)}</b>: ${safe(typeof shown==='string'?shown:JSON.stringify(shown))}</span>`;
      }).join('')}</div>
    </details>`;
  }
  function auditRowMarkup(row){
    const actor=row.actor_name||row.actor_username||`User ${row.actor_user_id||'—'}`;
    const branch=row.branch_name||row.branch_code||row.branch_city||'—';
    const entity=auditEntityLabel(row);
    return `<article class="card" style="padding:13px;box-shadow:none">
      <div class="shipment-top">
        <span class="icon-square">⌁</span>
        <div class="ship-name"><b>${safe(row.action||'—')}</b><div class="ship-phone">${safe(entity)}</div></div>
        <span class="push"></span>
        <span class="badge">${safe(saDate(row.created_at))}</span>
      </div>
      <div class="record-meta" style="margin-top:9px">
        <span>${sat('actor')}: <b>${safe(actor)}</b></span>
        <span>${sat('branch')}: <b>${safe(branch)}</b></span>
        <span>${sat('entity')}: <b>${safe(entity)}</b></span>
      </div>
      ${auditMetaMarkup(row)}
    </article>`;
  }
  function auditActionOptions(summary,selected=''){
    const rows=summary?.top_actions||[];
    return `<option value="">${sat('allActions')}</option>`+
      rows.map(row=>`<option value="${safe(row.action)}" ${String(selected)===String(row.action)?'selected':''}>${safe(row.action)} (${Number(row.count||0)})</option>`).join('');
  }
  function auditEntityOptions(summary,selected=''){
    const rows=summary?.top_entities||[];
    return `<option value="">${sat('allEntities')}</option>`+
      rows.map(row=>`<option value="${safe(row.entity_type)}" ${String(selected)===String(row.entity_type)?'selected':''}>${safe(row.entity_type)} (${Number(row.count||0)})</option>`).join('');
  }
  function auditScreenMarkup(summary,rows,filters={}){
    return `${head((OPS_UI_OVERRIDES?.[currentLang]?.audit?.securityEyebrow||'SECURITY · OPERATIONS'),sat('audit'),sat('auditSub'),`<button class="btn primary" data-audit-refresh>↻ ${sat('refresh')}</button>`)}
      <div class="grid kpis">
        ${kpi(sat('total'),Number(summary?.total||0),sat('audit'),'⌁')}
        ${kpi(sat('last24'),Number(summary?.last_24h||0),sat('date'),'◷','positive')}
        ${kpi(sat('lastHour'),Number(summary?.last_hour||0),sat('date'),'◴')}
        ${kpi(sat('topActors'),Number((summary?.top_actors||[]).length),sat('actor'),'♙')}
      </div>
      <section class="card" style="margin-bottom:16px">
        <div class="section-title" style="margin-top:0"><h2>${sat('filters')}</h2></div>
        <form id="auditFilterForm" class="form-grid">
          <label class="field span-2"><span>${sat('searchTitle')}</span><input name="q" value="${safe(filters.q||'')}" placeholder="${safe(sat('auditSearch'))}"></label>
          <label class="field"><span>${sat('action')}</span><select name="action">${auditActionOptions(summary,filters.action)}</select></label>
          <label class="field"><span>${sat('entity')}</span><select name="entity_type">${auditEntityOptions(summary,filters.entity_type)}</select></label>
          <label class="field"><span>${sat('from')}</span><input type="date" name="from" value="${safe(filters.from||'')}"></label>
          <label class="field"><span>${sat('to')}</span><input type="date" name="to" value="${safe(filters.to||'')}"></label>
          <div class="field span-2"><button class="btn primary full">${sat('searchTitle')}</button></div>
        </form>
      </section>
      <div class="section-title"><div><h2>${sat('audit')}</h2><p>${sat('auditSub')}</p></div><span class="badge">${rows.length}</span></div>
      <div id="auditRows" class="grid" style="gap:9px">
        ${rows.map(auditRowMarkup).join('')||`<div class="card empty">${sat('noAudit')}</div>`}
      </div>
      ${rows.length>=100?`<div style="margin-top:12px"><button class="btn light full" data-audit-more="${safe(rows[rows.length-1]?.id||'')}">${sat('loadMore')}</button></div>`:''}`;
  }
  function markAuditNavActive(){
    const nav=$('#sideNav');
    if(!nav)return;
    nav.querySelectorAll('.nav-item').forEach(item=>item.classList.remove('active'));
    nav.querySelector('[data-audit-screen]')?.classList.add('active');
  }
  function installAuditNavigation(){
    const nav=$('#sideNav');
    if(!nav||!user||!hasPermission('audit.read'))return;
    if(!nav.querySelector('[data-audit-screen]')){
      const button=document.createElement('button');
      button.className='nav-item';
      button.type='button';
      button.dataset.auditScreen='1';
      button.innerHTML=`<span class="nav-icon nav-icon-3d" aria-hidden="true" data-no-i18n>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <path d="M6 3h12v18H6z"/><path d="M9 7h6M9 11h6M9 15h4"/>
        </svg></span><span>${sat('audit')}</span>`;
      button.onclick=()=>openAuditLogScreen();
      nav.appendChild(button);
    }
    if(state.auditOpen)markAuditNavActive();
  }
  function auditNormalizeSearch(value){
    return String(value??'').normalize('NFKC').trim().toLocaleLowerCase('en');
  }
  function auditCompactSearch(value){
    return auditNormalizeSearch(value).replace(/[\s\-_/\.]+/g,'');
  }
  function auditSearchHaystack(row){
    const parts=[
      row?.action,row?.entity_type,row?.entity_id,
      row?.actor_name,row?.actor_username,row?.actor_user_id,
      row?.branch_name,row?.branch_code,row?.branch_city,
      row?.awb,row?.shipment_awb,row?.route_code,row?.transfer_code,row?.transfer_id,
      row?.plate,row?.vehicle_plate,row?.driver_name,
      row?.client_code,row?.customer_code,row?.invoice_number,row?.payment_number,
      row?.username,row?.display_name,row?.campaign_code,row?.promo_code,
      auditEntityReference(row),auditEntityLabel(row)
    ];
    try{parts.push(JSON.stringify(row))}catch(_){}
    return parts.filter(value=>value!==null&&value!==undefined&&value!=='').join(' ');
  }
  function auditRowMatchesQuery(row,query){
    const needle=auditNormalizeSearch(query);
    if(!needle)return true;
    const haystack=auditNormalizeSearch(auditSearchHaystack(row));
    if(haystack.includes(needle))return true;
    const compactNeedle=auditCompactSearch(query);
    return compactNeedle.length>=3&&auditCompactSearch(haystack).includes(compactNeedle);
  }
  function auditQueryString(filters={},before='',options={}){
    const p=new URLSearchParams();
    if(filters.q&&options.includeQ!==false)p.set('q',filters.q);
    if(filters.action)p.set('action',filters.action);
    if(filters.entity_type)p.set('entity_type',filters.entity_type);
    if(filters.from)p.set('from',filters.from+'T00:00:00');
    if(filters.to)p.set('to',filters.to+'T23:59:59');
    if(before)p.set('before_id',before);
    p.set('limit','100');
    return p.toString();
  }
  async function fetchAuditRows(filters={}){
    const query=String(filters.q||'').trim();
    if(!query)return api('/api/audit?'+auditQueryString(filters));

    // The backend audit search historically searched only a subset of fields.
    // Resolve business references (AWB, route/transfer IDs, plates, etc.) on the
    // client by paging through the already-filtered audit stream without q.
    const baseFilters={...filters,q:''};
    const matches=[];
    const seen=new Set();
    let before='';
    const maxPages=50; // up to 5,000 recent audit rows for one explicit search

    for(let pageIndex=0;pageIndex<maxPages;pageIndex++){
      const batch=await api('/api/audit?'+auditQueryString(baseFilters,before,{includeQ:false}));
      if(!Array.isArray(batch)||!batch.length)break;
      batch.forEach((row,index)=>{
        const key=String(row?.id??`${pageIndex}:${index}`);
        if(seen.has(key))return;
        seen.add(key);
        if(auditRowMatchesQuery(row,query))matches.push(row);
      });
      if(batch.length<100)break;
      const nextBefore=String(batch[batch.length-1]?.id||'');
      if(!nextBefore||nextBefore===before)break;
      before=nextBefore;
    }
    return matches;
  }
  async function openAuditLogScreen(filters={}){
    if(!requirePermission('audit.read'))return;
    state.auditOpen=true;
    app.innerHTML=`${head((OPS_UI_OVERRIDES?.[currentLang]?.audit?.securityEyebrow||'SECURITY · OPERATIONS'),sat('audit'),sat('auditSub'))}<div class="card empty">${opsTr('جارٍ تحميل البيانات…')}</div>`;
    installAuditNavigation();markAuditNavActive();
    try{
      const [summary,rows]=await Promise.all([
        api('/api/audit/summary'),
        fetchAuditRows(filters)
      ]);
      if(!state.auditOpen)return;
      app.innerHTML=auditScreenMarkup(summary,Array.isArray(rows)?rows:[],filters);
      localizeNow(app);installAuditNavigation();markAuditNavActive();
      bindAuditScreen(summary,Array.isArray(rows)?rows:[],filters);
    }catch(error){
      app.innerHTML=`${head((OPS_UI_OVERRIDES?.[currentLang]?.audit?.securityEyebrow||'SECURITY · OPERATIONS'),sat('audit'),sat('auditSub'))}<div class="notice-error">${safe(opsTr(error.message))}</div>`;
      installAuditNavigation();markAuditNavActive();
    }
  }
  function bindAuditScreen(summary,rows,filters){
    const form=$('#auditFilterForm',app);
    if(form)form.onsubmit=e=>{
      e.preventDefault();
      const data=Object.fromEntries(new FormData(form));
      openAuditLogScreen(data);
    };
    $('[data-audit-refresh]',app)?.addEventListener('click',()=>openAuditLogScreen(filters));
    const more=$('[data-audit-more]',app);
    if(more)more.onclick=async()=>{
      const before=more.dataset.auditMore;
      more.disabled=true;
      try{
        const extra=await api('/api/audit?'+auditQueryString(filters,before));
        const target=$('#auditRows',app);
        if(Array.isArray(extra)&&extra.length&&target){
          target.insertAdjacentHTML('beforeend',extra.map(auditRowMarkup).join(''));
          more.dataset.auditMore=String(extra[extra.length-1].id||'');
          if(extra.length<100)more.remove();
        }else more.remove();
      }catch(error){toast(opsTr(error.message));more.disabled=false}
    };
  }
  function installCentralSearch(){
    const button=$('#globalSearch');
    if(!button||!user||accessRole()==='customer')return;
    button.title=sat('searchTitle');
    button.onclick=()=>centralSearchModal();
  }
  function installSearchAuditUI(){
    installCentralSearch();
    installAuditNavigation();
  }



  const EXEC_TEXT={
    dashboard:{ar:'لوحة الإدارة التنفيذية',en:'Executive Management Dashboard'},
    dashboardSub:{ar:'مؤشرات التشغيل والمالية والفروع والأسطول والمندوبين والحملات من البيانات الفعلية.',en:'Live operational, finance, branch, fleet, courier and campaign performance from actual records.'},
    reports:{ar:'تقارير الإدارة',en:'Management Reports'},
    reportsSub:{ar:'تحليل تشغيلي ومالي قابل للتصفية مع تقارير الشحن القابلة للتنزيل.',en:'Filterable operational and financial analysis with downloadable shipment reports.'},
    today:{ar:'اليوم',en:'Today'},d7:{ar:'٧ أيام',en:'7 Days'},d30:{ar:'٣٠ يوماً',en:'30 Days'},
    d90:{ar:'٩٠ يوماً',en:'90 Days'},d365:{ar:'٣٦٥ يوماً',en:'365 Days'},all:{ar:'الكل',en:'All Time'},
    shipments:{ar:'الشحنات',en:'Shipments'},delivered:{ar:'تم التسليم',en:'Delivered'},
    deliveryRate:{ar:'معدل التسليم',en:'Delivery Rate'},activeRoutes:{ar:'الرحلات النشطة',en:'Active Routes'},
    failedOpen:{ar:'تعذر التسليم المفتوح',en:'Open Delivery Exceptions'},pieces:{ar:'الطرود',en:'Parcels'},
    weight:{ar:'الوزن',en:'Weight'},avgDelivery:{ar:'متوسط وقت التسليم',en:'Avg. Delivery Time'},
    hours:{ar:'ساعة',en:'hours'},finance:{ar:'الأداء المالي',en:'Finance Performance'},
    invoiced:{ar:'قيمة الفواتير',en:'Invoiced'},collected:{ar:'المحصل',en:'Collected'},
    outstanding:{ar:'المستحق',en:'Outstanding'},collectionRate:{ar:'معدل التحصيل',en:'Collection Rate'},
    discounts:{ar:'الخصومات',en:'Discounts'},currency:{ar:'ر.س',en:'SAR'},
    trend:{ar:'اتجاه التشغيل',en:'Operational Trend'},created:{ar:'شحنات منشأة',en:'Shipments Created'},
    status:{ar:'توزيع حالات الشحنات',en:'Shipment Status Distribution'},
    branches:{ar:'أداء الفروع',en:'Branch Performance'},originated:{ar:'صادرة',en:'Originated'},
    received:{ar:'واردة',en:'Received'},branchDelivered:{ar:'مسلمة',en:'Delivered'},
    branchRate:{ar:'معدل التسليم',en:'Delivery Rate'},couriers:{ar:'أداء المندوبين',en:'Courier Performance'},
    attempts:{ar:'الشحنات المحاولة',en:'Attempted Shipments'},success:{ar:'ناجحة',en:'Delivered'},
    failed:{ar:'فاشلة',en:'Failed'},successRate:{ar:'نسبة النجاح',en:'Success Rate'},
    fleet:{ar:'الأسطول',en:'Fleet'},vehicles:{ar:'المركبات',en:'Vehicles'},
    available:{ar:'متاحة',en:'Available'},onRoute:{ar:'في الطريق',en:'On Route'},
    maintenance:{ar:'صيانة',en:'Maintenance'},maintenanceDue:{ar:'صيانة مستحقة خلال 30 يوماً',en:'Maintenance Due in 30 Days'},
    docsExpiring:{ar:'مستندات تنتهي خلال 30 يوماً',en:'Documents Expiring in 30 Days'},
    campaigns:{ar:'أداء الحملات',en:'Campaign Performance'},published:{ar:'منشورة',en:'Published'},
    campaignSent:{ar:'مرسلة',en:'Sent'},redemptions:{ar:'استخدام القسائم',en:'Redemptions'},
    alerts:{ar:'تنبيهات الإدارة',en:'Management Alerts'},recent:{ar:'أحدث الشحنات',en:'Recent Shipments'},
    refresh:{ar:'تحديث',en:'Refresh'},loading:{ar:'جارٍ تحميل لوحة الإدارة…',en:'Loading executive dashboard…'},
    loadingReports:{ar:'جارٍ تحميل التقارير…',en:'Loading management reports…'},
    shipmentPdf:{ar:'تقرير الشحنات PDF',en:'Shipment PDF'},shipmentExcel:{ar:'تقرير الشحنات Excel',en:'Shipment Excel'},
    paymentMethods:{ar:'طرق الدفع',en:'Payment Methods'},noData:{ar:'لا توجد بيانات لهذه الفترة.',en:'No data for this period.'},
    period:{ar:'الفترة',en:'Period'},generated:{ar:'آخر تحديث',en:'Generated'},
    routes:{ar:'الرحلات',en:'Routes'},fleetUtilization:{ar:'استخدام الأسطول',en:'Fleet Utilization'},
    campaignDelivery:{ar:'نجاح إرسال الحملات',en:'Campaign Delivery Success'},
    outstandingInvoices:{ar:'فواتير مستحقة',en:'Outstanding Invoices'},
    operationalSummary:{ar:'الملخص التشغيلي',en:'Operational Summary'}
  };
  function et(key){return opsDictText('exec',key,EXEC_TEXT[key])}
  const EXEC_PERIODS=[['today','today'],['7d','d7'],['30d','d30'],['90d','d90'],['365d','d365'],['all','all']];
  function execPeriodTabs(){
    return `<div class="tabs" style="margin-bottom:12px">${EXEC_PERIODS.map(([value,key])=>`<button class="tab exec-period ${state.executivePeriod===value?'active':''}" data-exec-period="${value}">${et(key)}</button>`).join('')}</div>`;
  }
  function execGrowth(value){
    if(value===null||value===undefined)return '';
    const n=Number(value||0);
    const sign=n>0?'+':'';
    return `${sign}${fmt(n)}%`;
  }
  function execMoney(value){return `${fmt(Number(value||0))} ${et('currency')}`}
  function execPaymentMethodLabel(value){
    const raw=String(value||'').trim();
    if(!raw)return currentLang==='ar'?'أخرى':'Other';
    const key=raw.toLowerCase().replace(/[\s-]+/g,'_');
    const labels={
      cash:{ar:'نقداً',en:'Cash'},
      card:{ar:'بطاقة',en:'Card'},
      bank_transfer:{ar:'تحويل بنكي',en:'Bank Transfer'},
      transfer:{ar:'تحويل بنكي',en:'Bank Transfer'},
      online:{ar:'دفع إلكتروني',en:'Online'},
      sender:{ar:'يدفع المرسل',en:'Sender Pays'},
      cod:{ar:'الدفع عند الاستلام',en:'Cash on Delivery'},
      company:{ar:'على حساب الشركة',en:'Company Account'},
      other:{ar:'أخرى',en:'Other'}
    };
    const item=labels[key];
    if(!item)return raw;
    return item[currentLang]||item.en||raw;
  }
  const EXEC_AR_CITIES={
    Riyadh:'الرياض',Jeddah:'جدة',Jaazan:'جازان',Jazan:'جازان',Makkah:'مكة',Mecca:'مكة',
    Taif:'الطائف',Madinah:'المدينة المنورة',Medina:'المدينة المنورة',Dammam:'الدمام',Abha:'أبها'
  };
  function execLocalizedPlace(value){
    const raw=String(value||'').trim();
    if(!raw)return '';
    if(currentLang==='ar'){
      if(EXEC_AR_CITIES[raw])return EXEC_AR_CITIES[raw];
      let match=raw.match(/^(.+?)\s+branch$/i);
      if(match)return `فرع ${EXEC_AR_CITIES[match[1]]||match[1]}`;
      match=raw.match(/^(.+?)\s+(?:centre|center)$/i);
      if(match)return `مركز ${EXEC_AR_CITIES[match[1]]||match[1]}`;
      match=raw.match(/^(.+?)\s+headquarters$/i);
      if(match)return `المقر الرئيسي - ${EXEC_AR_CITIES[match[1]]||match[1]}`;
    }
    const translated=opsTr(raw);
    return translated&&translated!==raw?translated:raw;
  }
  function execDate(value){return value?saDate(value):'—'}
  function executiveLoadingPage(title=et('dashboard'),sub=et('dashboardSub'),message=et('loading')){
    return `${head((OPS_UI_OVERRIDES?.[currentLang]?.exec?.executiveEyebrow||'KSA · EXECUTIVE INTELLIGENCE'),title,sub,`<button class="btn light" data-exec-refresh>↻ ${et('refresh')}</button>`)}
      ${execPeriodTabs()}<div class="card empty">${message}</div>`;
  }
  function execTrendChart(trend){
    const rows=Array.isArray(trend?.rows)?trend.rows:[];
    if(!rows.length)return `<div class="card empty">${et('noData')}</div>`;
    const visible=rows.slice(-30);
    const max=Math.max(1,...visible.map(row=>Number(row.shipments||0)));
    const labelStep=visible.length>20?(opsIsRtl()?6:5):visible.length>12?(opsIsRtl()?4:3):visible.length>8?2:1;
    return `<div class="bar-chart" style="min-height:190px">${visible.map((row,index)=>{
      const value=Number(row.shipments||0),delivered=Number(row.delivered||0);
      const fullLabel=new Date(row.date+'T00:00:00').toLocaleDateString(
        opsLocaleTag(),opsIsRtl()?{calendar:'gregory',numberingSystem:currentLang==='ar'?'arab':'latn',month:'2-digit',day:'2-digit'}:{calendar:'gregory',month:'short',day:'numeric'}
      );
      const showLabel=index%labelStep===0||index===visible.length-1;
      const axisLabel=showLabel?fullLabel:'';
      return `<i style="height:${Math.max(5,100*value/max)}%" data-label="${safe(axisLabel)}" title="${safe(`${et('shipments')}: ${fmt(value)} · ${et('delivered')}: ${fmt(delivered)} · ${fullLabel}`)}"></i>`;
    }).join('')}</div>`;
  }
  function execStatusMarkup(rows){
    if(!Array.isArray(rows)||!rows.length)return `<div class="card empty">${et('noData')}</div>`;
    const total=Math.max(1,rows.reduce((n,row)=>n+Number(row.count||0),0));
    return rows.map(row=>{
      const percent=Math.round(Number(row.count||0)*100/total);
      return `<div class="summary-row"><span>${safe(opsTr(row.status||'Unknown'))}</span><b><bdi>${fmt(row.count)}</bdi> · <bdi>${fmt(percent)}%</bdi></b></div>`;
    }).join('');
  }
  function execBranchMarkup(rows){
    if(!Array.isArray(rows)||!rows.length)return `<div class="card empty">${et('noData')}</div>`;
    return `<div class="grid" style="gap:8px">${rows.map(row=>`<article class="card" style="padding:12px;box-shadow:none">
      <div class="shipment-top"><b>${safe(execLocalizedPlace(row.name||row.code||'—'))}</b><span class="ship-phone">${safe(execLocalizedPlace(row.city||''))}</span><span class="push"></span><span class="badge green">${fmt(row.delivery_rate||0)}%</span></div>
      <div class="record-meta" style="margin-top:8px">
        <span>${et('originated')}: <b>${fmt(row.originated)}</b></span>
        <span>${et('received')}: <b>${fmt(row.received)}</b></span>
        <span>${et('branchDelivered')}: <b>${fmt(row.delivered)}</b></span>
        ${row.invoiced!=null?`<span>${et('invoiced')}: <b>${execMoney(row.invoiced)}</b></span>`:''}
      </div>
    </article>`).join('')}</div>`;
  }
  function execCourierMarkup(payload){
    const rows=Array.isArray(payload?.rows)?payload.rows:[];
    if(!rows.length)return `<div class="card empty">${et('noData')}</div>`;
    return `<div class="grid" style="gap:8px">${rows.slice(0,8).map(row=>`<article class="card" style="padding:12px;box-shadow:none">
      <div class="shipment-top"><b>${safe(row.name||'—')}</b><span class="ship-phone">${safe(execLocalizedPlace(row.branch||''))}</span><span class="push"></span><span class="badge ${Number(row.success_rate)>=80?'green':''}">${fmt(row.success_rate)}%</span></div>
      <div class="record-meta" style="margin-top:8px">
        <span>${et('attempts')}: <b>${fmt(row.attempted_shipments)}</b></span>
        <span>${et('success')}: <b>${fmt(row.delivered_attempts)}</b></span>
        <span>${et('failed')}: <b>${fmt(row.failed_attempts)}</b></span>
      </div>
    </article>`).join('')}</div>`;
  }
  function execFleetMarkup(fleet){
    if(!fleet)return `<div class="card empty">${et('noData')}</div>`;
    return `<div class="grid kpis" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      ${kpi(et('vehicles'),fleet.total||0,et('fleetUtilization'),'▣')}
      ${kpi(et('available'),fleet.available||0,et('vehicles'),'✓','positive')}
      ${kpi(et('onRoute'),fleet.on_route||0,`${et('fleetUtilization')}: ${fmt(fleet.utilization_rate||0)}%`,'⇄')}
      ${kpi(et('maintenance'),fleet.maintenance||0,`${et('maintenanceDue')}: ${fmt(fleet.maintenance_due_30d||0)}`,'⚙',Number(fleet.maintenance||0)?'negative':'')}
    </div><div class="record-meta" style="margin-top:10px">
      <span>${et('docsExpiring')}: <b>${fmt(fleet.documents_expiring_30d||0)}</b></span>
      <span>${et('routes')}: <b>${fmt(fleet.routes_in_period||0)}</b></span>
    </div>`;
  }
  function execCampaignMarkup(payload){
    if(!payload)return `<div class="card empty">${et('noData')}</div>`;
    const top=Array.isArray(payload.top)?payload.top:[];
    return `<div class="grid kpis" style="grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:12px">
      ${kpi(et('campaigns'),payload.total||0,`${et('published')}: ${fmt(payload.published||0)}`,'◇')}
      ${kpi(et('campaignSent'),payload.sent||0,`${et('campaignDelivery')}: ${fmt(payload.delivery_success_rate||0)}%`,'✉','positive')}
      ${kpi(et('redemptions'),payload.redemptions||0,execMoney(payload.discount_total||0),'％')}
      ${kpi(et('failed'),payload.failed||0,et('campaignDelivery'),'⚠',Number(payload.failed||0)?'negative':'')}
    </div>${top.length?`<div class="grid" style="gap:8px">${top.slice(0,5).map(row=>`<article class="card" style="padding:11px;box-shadow:none"><div class="shipment-top"><b>${safe(row.name||row.code)}</b><span class="push"></span><span class="badge ${row.is_published?'green':''}">${safe(campaignStatusLabel(row.status))}</span></div><div class="record-meta"><span>${et('campaignSent')}: <b>${fmt(row.sent)}</b></span><span>${et('redemptions')}: <b>${fmt(row.redemptions)}</b></span></div></article>`).join('')}</div>`:''}`;
  }
  function execAlertsMarkup(alerts){
    const rows=[
      [et('failedOpen'),alerts?.failed_delivery_open||0,'proof'],
      [et('outstandingInvoices'),alerts?.outstanding_invoices||0,'shipments'],
      [et('maintenanceDue'),alerts?.maintenance_due_30d||0,'drivers'],
      [et('docsExpiring'),alerts?.vehicle_documents_expiring_30d||0,'drivers']
    ];
    return rows.map(([label,value,target])=>`<button type="button" class="summary-row" data-page="${target}" style="width:100%;border:0;background:transparent;text-align:inherit;cursor:pointer"><span>${safe(label)}</span><b class="${Number(value)>0?'negative':''}">${fmt(value)}</b></button>`).join('');
  }
  function execRecentMarkup(rows){
    if(!Array.isArray(rows)||!rows.length)return `<div class="card empty">${et('noData')}</div>`;
    return `<div class="grid" style="gap:8px">${rows.map(row=>`<button type="button" class="card" data-exec-track="${safe(row.awb||'')}" style="padding:11px;box-shadow:none;text-align:inherit;cursor:pointer">
      <div class="shipment-top"><b class="awb">${safe(row.awb||'—')}</b><span class="push"></span><span class="badge">${safe(opsTr(row.status||'—'))}</span></div>
      <div class="ship-route" style="margin-top:8px"><span>${safe(opsTr(row.origin||'—'))}</span><b>→</b><span>${safe(opsTr(row.destination||'—'))}</span></div>
    </button>`).join('')}</div>`;
  }
  function executiveDashboardMarkup(data){
    const k=data?.kpis||{},finance=data?.finance;
    const generated=data?.generated_at?execDate(data.generated_at):'—';
    return `${head((OPS_UI_OVERRIDES?.[currentLang]?.exec?.executiveEyebrow||'KSA · EXECUTIVE INTELLIGENCE'),et('dashboard'),et('dashboardSub'),`<button class="btn light" data-exec-refresh>↻ ${et('refresh')}</button>`)}
      ${execPeriodTabs()}
      <p class="kpi-note">${et('generated')}: ${safe(generated)}</p>
      <div class="grid kpis">
        ${kpi(et('shipments'),fmt(k.shipments||0),execGrowth(k.shipments_growth)||et('period'),'▤')}
        ${kpi(et('deliveryRate'),`${fmt(k.delivery_rate||0)}%`,`${fmt(k.delivered||0)} ${et('delivered')}`,'✓','positive')}
        ${kpi(et('activeRoutes'),fmt(k.active_routes||0),`${fmt(k.routes||0)} ${et('routes')}`,'⇄')}
        ${kpi(et('failedOpen'),fmt(k.failed_delivery_open||0),et('alerts'),'⚠',Number(k.failed_delivery_open||0)?'negative':'')}
      </div>
      ${finance?`<div class="section-title"><h2>${et('finance')}</h2></div><div class="grid kpis">
        ${kpi(et('invoiced'),execMoney(finance.invoiced),execGrowth(finance.invoiced_growth),'▧')}
        ${kpi(et('collected'),execMoney(finance.collected),execGrowth(finance.collected_growth),'✓','positive')}
        ${kpi(et('outstanding'),execMoney(finance.outstanding),`${fmt(finance.outstanding_invoice_count||0)} ${et('outstandingInvoices')}`,'◷',Number(finance.outstanding||0)?'negative':'')}
        ${kpi(et('collectionRate'),`${fmt(finance.collection_rate||0)}%`,`${et('discounts')}: ${execMoney(finance.discounts||0)}`,'％')}
      </div>`:''}
      <div class="grid dashboard-grid">
        <section class="card"><div class="section-title" style="margin-top:0"><h2>${et('trend')}</h2><span class="badge">${fmt(data?.trend?.days||0)}</span></div>${execTrendChart(data?.trend)}</section>
        <section class="card"><div class="section-title" style="margin-top:0"><h2>${et('status')}</h2></div>${execStatusMarkup(data?.status_distribution)}</section>
      </div>
      <div class="section-title"><h2>${et('branches')}</h2></div>${execBranchMarkup(data?.branches)}
      <div class="grid dashboard-grid" style="margin-top:16px">
        <section class="card"><div class="section-title" style="margin-top:0"><h2>${et('couriers')}</h2></div>${execCourierMarkup(data?.couriers)}</section>
        <section class="card"><div class="section-title" style="margin-top:0"><h2>${et('alerts')}</h2></div>${execAlertsMarkup(data?.alerts)}</section>
      </div>
      <div class="section-title"><h2>${et('fleet')}</h2></div><section class="card">${execFleetMarkup(data?.fleet)}</section>
      <div class="section-title"><h2>${et('campaigns')}</h2></div><section class="card">${execCampaignMarkup(data?.campaigns)}</section>
      <div class="section-title"><h2>${et('recent')}</h2></div>${execRecentMarkup(data?.recent_shipments)}`;
  }
  function executiveHomePage(){
    if(accessRole()==='courier')return liveHome();
    if(!hasPermission('stats.read'))return liveHome();
    const ready=state.executiveDashboard&&state.executiveDashboardPeriod===state.executivePeriod;
    if(!ready)return executiveLoadingPage();
    return executiveDashboardMarkup(state.executiveDashboard);
  }
  function reportFinanceMarkup(finance){
    if(!finance)return `<div class="card empty">${et('noData')}</div>`;
    const methods=Array.isArray(finance.payment_methods)?finance.payment_methods:[];
    return `<div class="grid kpis">
      ${kpi(et('invoiced'),execMoney(finance.invoiced),'▧','▧')}
      ${kpi(et('collected'),execMoney(finance.collected),`${fmt(finance.collection_rate||0)}%`,'✓','positive')}
      ${kpi(et('outstanding'),execMoney(finance.outstanding),`${fmt(finance.outstanding_invoice_count||0)} ${et('outstandingInvoices')}`,'◷',Number(finance.outstanding||0)?'negative':'')}
      ${kpi(et('discounts'),execMoney(finance.discounts||0),et('finance'),'％')}
    </div>${methods.length?`<div class="section-title"><h3>${et('paymentMethods')}</h3></div>${methods.map(row=>`<div class="summary-row"><span>${safe(execPaymentMethodLabel(row.method))}</span><b>${fmt(row.count)} · ${execMoney(row.amount)}</b></div>`).join('')}`:''}`;
  }
  function managementReportsMarkup(report){
    const opsData=report?.operations||{},k=opsData.kpis||{};
    return `${head((OPS_UI_OVERRIDES?.[currentLang]?.exec?.reportingEyebrow||'KSA · MANAGEMENT REPORTING'),et('reports'),et('reportsSub'),hasPermission('reports.read')?`<div class="ops-inline-actions"><button class="btn light" data-exec-export="pdf">▧ ${et('shipmentPdf')}</button><button class="btn light" data-exec-export="xlsx">▦ ${et('shipmentExcel')}</button><button class="btn primary" data-exec-refresh>↻ ${et('refresh')}</button></div>`:`<button class="btn primary" data-exec-refresh>↻ ${et('refresh')}</button>`)}
      ${execPeriodTabs()}
      <div class="grid kpis">
        ${kpi(et('shipments'),fmt(k.shipments||0),`${fmt(k.pieces||0)} ${et('pieces')}`,'▤')}
        ${kpi(et('deliveryRate'),`${fmt(k.delivery_rate||0)}%`,`${fmt(k.delivered||0)} ${et('delivered')}`,'✓','positive')}
        ${kpi(et('avgDelivery'),`${fmt(k.avg_delivery_hours||0)} ${et('hours')}`,et('operationalSummary'),'◷')}
        ${kpi(et('activeRoutes'),fmt(k.active_routes||0),`${fmt(k.routes||0)} ${et('routes')}`,'⇄')}
      </div>
      <div class="grid dashboard-grid">
        <section class="card"><div class="section-title" style="margin-top:0"><h2>${et('trend')}</h2></div>${execTrendChart(opsData.trend)}</section>
        <section class="card"><div class="section-title" style="margin-top:0"><h2>${et('status')}</h2></div>${execStatusMarkup(opsData.status_distribution)}</section>
      </div>
      <div class="section-title"><h2>${et('finance')}</h2></div><section class="card">${reportFinanceMarkup(report?.finance)}</section>
      <div class="section-title"><h2>${et('branches')}</h2></div>${execBranchMarkup(report?.branch_performance)}
      <div class="grid dashboard-grid" style="margin-top:16px">
        <section class="card"><div class="section-title" style="margin-top:0"><h2>${et('couriers')}</h2></div>${execCourierMarkup(report?.courier_performance)}</section>
        <section class="card"><div class="section-title" style="margin-top:0"><h2>${et('alerts')}</h2></div>${execAlertsMarkup(report?.alerts)}</section>
      </div>
      <div class="section-title"><h2>${et('fleet')}</h2></div><section class="card">${execFleetMarkup(report?.fleet)}</section>
      <div class="section-title"><h2>${et('campaigns')}</h2></div><section class="card">${execCampaignMarkup(report?.campaigns)}</section>
      <div class="section-title"><h2>${et('recent')}</h2></div>${execRecentMarkup(opsData.recent_shipments)}`;
  }
  function managementReportsPage(){
    if(!hasPermission('reports.read')){
      return executiveHomePage();
    }
    const ready=state.managementReport&&state.managementReportPeriod===state.executivePeriod;
    if(!ready)return executiveLoadingPage(et('reports'),et('reportsSub'),et('loadingReports'));
    return managementReportsMarkup(state.managementReport);
  }
  async function loadExecutiveDashboard(force=false){
    if(!user||!hasPermission('stats.read')||accessRole()==='courier')return;
    const period=state.executivePeriod||'30d';
    if(!force&&state.executiveDashboard&&state.executiveDashboardPeriod===period)return;
    if(state.executiveLoading)return;
    state.executiveLoading=true;state.executiveError=null;
    try{
      const data=await api(`/api/dashboard/executive?period=${encodeURIComponent(period)}`);
      state.executiveDashboard=data;state.executiveDashboardPeriod=period;
    }catch(error){
      state.executiveError=error;
      toast(opsTr(error.message));
    }finally{
      state.executiveLoading=false;
      if(page==='home'&&!state.auditOpen)window.render();
    }
  }
  async function loadManagementReport(force=false){
    if(!user||!hasPermission('reports.read'))return;
    const period=state.executivePeriod||'30d';
    if(!force&&state.managementReport&&state.managementReportPeriod===period)return;
    if(state.managementReportLoading)return;
    state.managementReportLoading=true;state.managementReportError=null;
    try{
      const data=await api(`/api/reports/management?period=${encodeURIComponent(period)}`);
      state.managementReport=data;state.managementReportPeriod=period;
    }catch(error){
      state.managementReportError=error;
      toast(opsTr(error.message));
    }finally{
      state.managementReportLoading=false;
      if(page==='analytics'&&!state.auditOpen)window.render();
    }
  }
  function bindExecutiveDashboardUI(){
    $$('.exec-period',app).forEach(button=>button.onclick=()=>{
      const period=button.dataset.execPeriod||'30d';
      if(state.executivePeriod===period)return;
      state.executivePeriod=period;
      state.executiveDashboard=null;state.executiveDashboardPeriod=null;
      state.managementReport=null;state.managementReportPeriod=null;
      window.render();
    });
    $$('[data-exec-refresh]',app).forEach(button=>button.onclick=()=>{
      if(page==='analytics')loadManagementReport(true);else loadExecutiveDashboard(true);
    });
    $$('[data-exec-export]',app).forEach(button=>button.onclick=()=>exportReport(button.dataset.execExport));
    $$('[data-exec-track]',app).forEach(button=>button.onclick=()=>{
      tracking=button.dataset.execTrack||'';
      if(!tracking)return;
      page='tracking';window.render();
    });
    if(page==='home'&&hasPermission('stats.read')&&accessRole()!=='courier'){
      if(state.executiveError&&!state.executiveLoading){
        const target=app.querySelector('.card.empty');
        if(target)target.innerHTML=`<div class="notice-error">${safe(opsTr(state.executiveError.message||'Could not load dashboard.'))}</div><button class="btn primary" data-exec-retry style="margin-top:10px">${et('refresh')}</button>`;
        app.querySelector('[data-exec-retry]')?.addEventListener('click',()=>loadExecutiveDashboard(true));
      }else loadExecutiveDashboard(false);
    }
    if(page==='analytics'&&hasPermission('reports.read')){
      if(state.managementReportError&&!state.managementReportLoading){
        const target=app.querySelector('.card.empty');
        if(target)target.innerHTML=`<div class="notice-error">${safe(opsTr(state.managementReportError.message||'Could not load reports.'))}</div><button class="btn primary" data-report-retry style="margin-top:10px">${et('refresh')}</button>`;
        app.querySelector('[data-report-retry]')?.addEventListener('click',()=>loadManagementReport(true));
      }else loadManagementReport(false);
    }
  }


  function bindOps(){
    if(!app)return;
    fixStaffLanguageShell();
    fixResidualOpsLanguage(app);
    installSearchAuditUI();
    bindExecutiveDashboardUI();
    bindAccessControlUI();
    $$('.shipment',app).forEach(card=>{const awb=$('.awb',card)?.textContent?.trim(),s=shipments.find(x=>x.awb===awb);if(!awb||!s)return;let row=$('.ship-bottom',card);if(!row){row=document.createElement('div');row.className='ship-bottom';card.appendChild(row)}
      const delivered=isDeliveredShipment(s);
      if(delivered){
        $('[data-reassign]',card)?.remove();
        $('[data-status]',card)?.remove();
        if(hasPermission('pod.read')&&!$('[data-pod-view]',row)){
          const proofButton=document.createElement('button');
          proofButton.className='btn accent small ops-view-pod';
          proofButton.dataset.podView=awb;
          proofButton.textContent=`✓ ${ct('viewPod')}`;
          row.appendChild(proofButton);
        }
      }
      if(!$('.ops-waybill',card)){const b=document.createElement('button');b.className='btn light small ops-waybill';b.textContent=`▤ ${opsTr('بوليصة الشحن')}`;b.onclick=()=>showWaybill(awb);row.appendChild(b)}if(!$('.ops-documents',card)){const d=document.createElement('button');d.className='btn light small ops-documents';d.textContent=`▦ ${dt('documents')}`;d.onclick=()=>openShipmentDocuments(awb);row.appendChild(d)}const meta=$('.record-meta',card);if(meta&&!$('.ops-pay-state',meta)){const p=document.createElement('span');p.className='ops-pay-state';const method=s.payment_method==='cod'?opsTr('الدفع عند الاستلام COD'):s.payment_method==='company'?opsTr('حساب الشركات المتعاقدة'):opsTr('يدفع المرسل');p.textContent=`${opsTr('حالة الدفع')}: ${method} · ${opsTr(s.payment_status||'غير مدفوع')}`;meta.appendChild(p)}if(hasPermission('shipments.payment')&&['sender','company'].includes(s.payment_method)&&(!['مدفوع'].includes(s.payment_status)||isCustomerBooking(s))&&!$('[data-payment-awb]',row)){const p=document.createElement('button');p.className='btn light small';p.dataset.paymentAwb=awb;p.textContent=`✓ ${pt('button')}`;row.appendChild(p)}if(isCustomerBooking(s)&&!$('.ops-customer-booking-badge',card)){const top=$('.shipment-top',card);if(top){const badge=document.createElement('span');badge.className='badge blue ops-customer-booking-badge';badge.textContent=opsTr('حجز عميل');top.insertBefore(badge,top.querySelector('.push')||null)}}if(s.customer_user_id&&meta&&!$('.ops-customer-owner',meta)){const owner=document.createElement('span');owner.className='ops-customer-owner';owner.innerHTML=`${safe(clt('account'))}: <b>${safe(s.customer_account_name||s.customer_account_username||('#'+s.customer_user_id))}</b>${s.customer_account_mobile?` · ${safe(s.customer_account_mobile)}`:''}`;meta.appendChild(owner)}if(hasPermission('shipments.edit')&&!s.customer_user_id&&!$('[data-link-customer]',row)){const link=document.createElement('button');link.className='btn light small';link.dataset.linkCustomer=awb;link.textContent=`♙ ${clt('link')}`;row.appendChild(link)}});
    ['landingTrackForm','publicTrackForm'].forEach(id=>{const f=$('#'+id);if(f&&!f.dataset.bound){f.dataset.bound='1';f.onsubmit=e=>{e.preventDefault();tracking=[...new Set(String(new FormData(f).get('awb')||'').split(/[\s,;]+/).map(value=>value.trim().toUpperCase()).filter(Boolean))].join(', ');if(!tracking)return;const hash='#track='+encodeURIComponent(tracking);history.replaceState(null,'',location.pathname+location.search+hash);f.dataset.autoTrackHash=hash;return searchPublic(tracking,$('#'+(id==='landingTrackForm'?'landingTrackResult':'publicTrackResult')))}}});
    $$('[data-route-scan]',app).forEach(b=>b.onclick=()=>promptRouteScan(b.dataset.routeScan));
    $$('[data-route-manifest]',app).forEach(b=>b.onclick=()=>printManifest(b.dataset.routeManifest));
    $$('[data-route-status]',app).forEach(b=>b.onclick=()=>routeStatus(b.dataset.routeStatus,b.dataset.statusValue));
    bindTransferControls(app);
    $$('[data-courier-refresh]',app).forEach(button=>button.onclick=async()=>{button.disabled=true;try{await refreshCourierTasks(true)}catch(error){toast(opsTr(error.message))}finally{if(button.isConnected)button.disabled=false}});
    $$('[data-delivery-start]',app).forEach(button=>button.onclick=()=>startDeliveryAttemptModal(button.dataset.deliveryStart));
    $$('[data-delivery-fail]',app).forEach(button=>button.onclick=()=>failDeliveryAttemptModal(button.dataset.deliveryFail));
    $$('[data-delivery-history]',app).forEach(button=>button.onclick=()=>deliveryAttemptHistoryModal(button.dataset.deliveryHistory));
    $$('[data-delivery-pod]',app).forEach(button=>button.onclick=()=>selectPodShipment(button.dataset.deliveryPod));
    $$('[data-pod-view]',app).forEach(button=>button.onclick=()=>openSavedPodModal(button.dataset.podView));
    $$('[data-pickup-action]',app).forEach(button=>button.onclick=()=>pickupActionModal(button.dataset.pickupNumber,button.dataset.pickupAction));
    $$('[data-payment-awb]',app).forEach(b=>b.onclick=()=>openPaymentLedger(b.dataset.paymentAwb));
    $$('[data-link-customer]',app).forEach(b=>b.onclick=()=>linkCustomerAccountModal(b.dataset.linkCustomer));
    $$('[data-fleet-add]',app).forEach(b=>b.onclick=()=>vehicleFleetModal());
    $$('[data-fleet-edit]',app).forEach(b=>b.onclick=()=>vehicleFleetModal(b.dataset.fleetEdit));
    $$('[data-fleet-view]',app).forEach(b=>b.onclick=()=>fleetDetailsModal(b.dataset.fleetView));
    $$('[data-fleet-maintenance]',app).forEach(b=>b.onclick=()=>fleetMaintenanceModal(b.dataset.fleetMaintenance));
    $$('[data-fleet-inspection]',app).forEach(b=>b.onclick=()=>fleetInspectionModal(b.dataset.fleetInspection));
    $$('[data-fleet-document]',app).forEach(b=>b.onclick=()=>fleetDocumentModal(b.dataset.fleetDocument));
    $$('[data-fleet-refresh]',app).forEach(b=>b.onclick=async()=>{b.disabled=true;try{await fleetRefresh(true)}catch(err){toast(opsTr(err.message))}finally{if(b.isConnected)b.disabled=false}});
    $$('[data-branch-manage]',app).forEach(button=>button.onclick=()=>branchManagementModal());
    const refresh=$('[data-route-refresh]',app);if(refresh)refresh.onclick=()=>{state.last=0;refreshOps(true)};
    $$('[data-driver-location]',app).forEach(b=>b.onclick=()=>{const d=drivers.find(x=>x.user_id===user?.id)||drivers[0];if(d)locationModal(d.id);else toast(opsTr('لا يوجد حساب سائق مرتبط بهذا المستخدم'))});
    const pf=$('#podForm');if(pf)bindPodForm(pf);
    const pricingForm=$('#pricingSettingsForm');if(pricingForm)pricingForm.onsubmit=async e=>{e.preventDefault();if(!requirePermission('pricing.manage'))return;const d=Object.fromEntries(new FormData(pricingForm));Object.keys(d).forEach(k=>d[k]=Number(d[k]));d.vat_rate/=100;d.insurance_rate/=100;try{state.pricing=await api('/api/pricing',{method:'PATCH',body:JSON.stringify(d)});toast(opsTr('تم حفظ إعدادات التسعير'));render()}catch(err){toast(opsTr(err.message))}};
    const quoteForm=$('#pricingQuoteForm');if(quoteForm){
      const grid=$('#pricingQuote3DGrid');
      const recalc=()=>{const d=new FormData(quoteForm),q=baseFeeQuote(d.get('weight'),1,0,false,'sender',d.get('pricing_size_code'),d.get('length_cm'),d.get('width_cm'),d.get('height_cm'));if(!quoteForm.elements.pricing_size_code.value&&q.size)quoteForm.elements.pricing_size_code.value=q.size.code;$('#pricingQuoteResult').innerHTML=quoteMarkup(q);if(grid){grid.innerHTML=pricing3DGrid(quoteForm.elements.pricing_size_code.value,true);bindPricing3DCards(grid,quoteForm,()=>recalc())}};
      ['length_cm','width_cm','height_cm'].forEach(name=>quoteForm.elements[name]?.addEventListener('input',()=>{quoteForm.elements.pricing_size_code.value='';recalc()}));
      quoteForm.oninput=recalc;bindPricing3DCards(grid,quoteForm,()=>recalc());recalc()
    }
    $$('[data-pricing-edit]',app).forEach(button=>button.onclick=()=>pricingSizeModal(Number(button.dataset.pricingEdit)));
    $('[data-pricing-add]',app)?.addEventListener('click',()=>pricingSizeModal());
    const clientSearch=$('#clientSearch');if(clientSearch&&!clientSearch.dataset.bound){clientSearch.dataset.bound='1';clientSearch.oninput=()=>{const q=clientSearch.value.trim().toLowerCase(),rows=state.clients.filter(c=>[c.name,c.code,c.mobile,c.commercial_registration,c.national_id].some(x=>String(x||'').toLowerCase().includes(q)));$('#clientsGrid').innerHTML=rows.map(clientCard).join('')||`<div class="card empty">${opsTr('لا توجد حسابات مطابقة')}</div>`;localizeNow($('#clientsGrid'));bindOps()}}
    $$('[data-client-view]',app).forEach(b=>b.onclick=()=>clientDetailsModal(b.dataset.clientView));
    $$('[data-client-edit]',app).forEach(b=>b.onclick=()=>clientFormModal(b.dataset.clientEdit));
    $$('[data-user-edit]',app).forEach(button=>button.onclick=()=>openUserAccount(Number(button.dataset.userEdit)));
    $$('[data-user-toggle]',app).forEach(button=>button.onclick=async()=>{await updateUserAccount(button.dataset.userToggle,{is_active:button.dataset.nextActive==='true'});state.accessOverview=null;if(page==='staff')loadAccessOverview(true)});
    $$('[data-user-revoke]',app).forEach(button=>button.onclick=async()=>{await updateUserAccount(button.dataset.userRevoke,{revoke_sessions:true});state.accessOverview=null;if(page==='staff')loadAccessOverview(true)});
    $$('[data-campaign-manage]',app).forEach(b=>b.onclick=()=>campaignModal('خصم',b.dataset.campaignManage));
    $$('[data-campaign-type]',app).forEach(b=>b.onclick=()=>campaignModal(b.dataset.campaignType));
    $$('[data-campaign-publish]',app).forEach(b=>b.onclick=()=>campaignPublish(b.dataset.campaignPublish,true));
    $$('[data-campaign-unpublish]',app).forEach(b=>b.onclick=()=>campaignPublish(b.dataset.campaignUnpublish,false));
    $$('[data-campaign-dispatch]',app).forEach(b=>b.onclick=()=>campaignDispatch(b.dataset.campaignDispatch));
    $$('[data-campaign-results]',app).forEach(b=>b.onclick=()=>campaignResultsModal(b.dataset.campaignResults));
    $$('.analytics-period',app).forEach(b=>b.onclick=()=>{state.analyticsPeriod=b.dataset.period;render()});
    $$('[data-tracking-home]',app).forEach(button=>button.onclick=trackingHome);
    $$('[data-track]',app).forEach(button=>button.onclick=()=>{tracking=button.dataset.track;const hash='#track='+encodeURIComponent(tracking);if(location.hash!==hash)location.hash=hash;else{page=user?'tracking':'landing';render();window.scrollTo(0,0)}});
    autoTrackFragment();
    const notice=$('.notice');if(notice&&!notice.dataset.opsBound){notice.dataset.opsBound='1';notice.onclick=async()=>{try{state.notifications=await api('/api/notifications');state.lastNotificationSignature=notificationSignature();updateNoticeBadge();openNotificationCenter()}catch(e){toast(opsTr(e.message))}}}updateNoticeBadge();$$('[data-open-notifications]',app).forEach(button=>button.onclick=openNotificationCenter);$$('[data-home-notification]',app).forEach(button=>button.onclick=()=>openNotificationTarget(button.dataset.awb,button.dataset.route,button.dataset.id));
    if(pricingForm&&!hasPermission('pricing.manage'))$$('input,button',pricingForm).forEach(field=>field.disabled=true);applyPermissionControls(app);localizeNow(app);syncReportExportButtons();
  }
  function pricingSizeModal(id=null){
    if(!requirePermission('pricing.manage'))return;
    const row=pricingRows(false).find(item=>Number(item.id)===Number(id))||{
      code:'',label_en:'',label_ar:'',length_cm:10,width_cm:10,height_cm:10,
      examples_en:'',examples_ar:'',base_fee:10,is_active:1,manual_only:0,
      sort_order:(pricingRows(false).length+1)*10
    };
    $('#modalRoot').innerHTML=`<div class="modal-backdrop" data-close><section class="modal ops-modal pricing-size-editor">
      <div class="modal-head"><div><div class="eyebrow">GHAZALA SMART PRICING</div><h2>${id?opsTr('تعديل حجم وتعرفة'):opsTr('إضافة حجم وتعرفة')}</h2></div><button class="icon-btn" data-close>×</button></div>
      <form id="pricingSizeForm" class="form-grid">
        <div class="field span-2 pricing-size-editor-preview">${pricing3DCard(row,row.code)}</div>
        <label class="field"><span>${opsTr('رمز الحجم')} *</span><input name="code" maxlength="20" required value="${safe(row.code)}"></label>
        <label class="field"><span>${opsTr('الاسم الإنجليزي')} *</span><input name="label_en" required value="${safe(row.label_en)}"></label>
        <label class="field"><span>${opsTr('الاسم العربي')}</span><input name="label_ar" value="${safe(row.label_ar)}"></label>
        <label class="field"><span>${opsTr('السعر الأساسي')}</span><input name="base_fee" type="number" min="0" step="0.01" required value="${safe(row.base_fee)}"></label>
        <label class="field"><span>${opsTr('الطول (سم)')}</span><input name="length_cm" type="number" min="0.1" step="0.1" required value="${safe(row.length_cm)}"></label>
        <label class="field"><span>${opsTr('العرض (سم)')}</span><input name="width_cm" type="number" min="0.1" step="0.1" required value="${safe(row.width_cm)}"></label>
        <label class="field"><span>${opsTr('الارتفاع (سم)')}</span><input name="height_cm" type="number" min="0.1" step="0.1" required value="${safe(row.height_cm)}"></label>
        <label class="field"><span>${opsTr('ترتيب العرض')}</span><input name="sort_order" type="number" step="1" value="${safe(row.sort_order)}"></label>
        <label class="field span-2"><span>${opsTr('أمثلة بالإنجليزية')}</span><textarea name="examples_en">${safe(row.examples_en)}</textarea></label>
        <label class="field span-2"><span>${opsTr('أمثلة بالعربية')}</span><textarea name="examples_ar">${safe(row.examples_ar)}</textarea></label>
        <label class="field check-field"><input name="is_active" type="checkbox" ${row.is_active!==0?'checked':''}><span>${opsTr('نشط')}</span></label>
        <label class="field check-field"><input name="manual_only" type="checkbox" ${row.manual_only?'checked':''}><span>${opsTr('اختيار يدوي فقط')}</span></label>
        <div class="field span-2 ops-form-actions"><button class="btn light" type="button" data-close>${opsTr('إلغاء')}</button><button class="btn primary">${opsTr('حفظ')}</button></div>
      </form>
    </section></div>`;
    wireModal();localizeNow($('#modalRoot'));
    const form=$('#pricingSizeForm');
    form.onsubmit=async event=>{
      event.preventDefault();
      const data=Object.fromEntries(new FormData(form));
      ['length_cm','width_cm','height_cm','base_fee','sort_order'].forEach(key=>data[key]=Number(data[key]||0));
      data.code=String(data.code||'').trim().toUpperCase();
      data.is_active=form.elements.is_active.checked;
      data.manual_only=form.elements.manual_only.checked;
      if(id)data.id=id;
      const button=form.querySelector('[type="submit"]');button.disabled=true;
      try{
        state.pricing=await api('/api/pricing',{method:'PATCH',body:JSON.stringify({sizes:[data]})});
        closeModal();toast(opsTr('تم حفظ حجم وتعرفة الشحن'));render();
      }catch(error){toast(opsTr(error.message))}
      finally{if(button?.isConnected)button.disabled=false}
    };
  }
  function pricingLive(){
    const p=state.pricing||{},sizes=pricingRows(false);
    const canManage=hasPermission('pricing.manage');
    return `${head(
      `KSA · ${opsTr('التسعير والعقود')}`,
      pricingUi('التسعير وأحجام الطرود','Pricing & Parcel Sizes'),
      opsTr('تعرفة موحدة تربط العميل وإنشاء الشحنة والفاتورة بنفس محرك التسعير'),
      canManage?`<button class="btn primary" type="button" data-pricing-add>＋ ${opsTr('إضافة حجم')}</button>`:''
    )}
    <section class="pricing-hero-3d">
      <div><span class="eyebrow">GHAZALA SMART PRICING</span><h2>${opsTr('اختر الحجم · احسب السعر · أنشئ الشحنة')}</h2><p>${opsTr('الأحجام والأسعار مستوردة من جدول غزالا وتدار مركزياً من هذه الصفحة.')}</p></div>
      <div class="pricing-hero-cubes" aria-hidden="true"><span></span><span></span><span></span></div>
    </section>
    <div class="grid dashboard-grid">
      <section class="card">
        <div class="section-title" style="margin-top:0"><h2>${opsTr('حاسبة سعر الشحن')}</h2></div>
        <form id="pricingQuoteForm" class="form-grid">
          <label class="field"><span>${opsTr('الطول (سم)')}</span><input name="length_cm" type="number" min="0" step="0.1" value="30"></label>
          <label class="field"><span>${opsTr('العرض (سم)')}</span><input name="width_cm" type="number" min="0" step="0.1" value="20"></label>
          <label class="field"><span>${opsTr('الارتفاع (سم)')}</span><input name="height_cm" type="number" min="0" step="0.1" value="15"></label>
          <label class="field"><span>${opsTr('الوزن الإجمالي (كجم)')}</span><input name="weight" type="number" min="0.5" step="0.1" value="1"></label>
          <input type="hidden" name="pricing_size_code" value="">
          <div class="field span-2"><div class="pricing-3d-grid compact customer-pricing-3d-grid management-pricing-outlet-grid" id="pricingQuote3DGrid">${pricing3DGrid('',true)}</div></div>
          <div class="field span-2" id="pricingQuoteResult"></div>
        </form>
      </section>
      <section class="card">
        <div class="section-title" style="margin-top:0"><h2>${opsTr('إعداد تعرفة النظام')}</h2>${canManage?'':`<span class="badge">${opsTr('قراءة فقط')}</span>`}</div>
        ${canManage?`<form id="pricingSettingsForm" class="form-grid">
          <label class="field"><span>${opsTr('تعرفة احتياطية بدون أبعاد')}</span><input name="base_fee" type="number" min="0" step="0.01" value="${safe(p.base_fee??65)}"></label>
          <label class="field"><span>${opsTr('الوزن المشمول (كجم)')}</span><input name="included_weight" type="number" min="0" step="0.1" value="${safe(p.included_weight??1)}"></label>
          <label class="field"><span>${opsTr('رسوم كل كجم إضافي')}</span><input name="extra_kg_fee" type="number" min="0" step="0.01" value="${safe(p.extra_kg_fee??2.5)}"></label>
          <label class="field"><span>${opsTr('ضريبة القيمة المضافة %')}</span><input name="vat_rate" type="number" min="0" max="100" step="0.1" value="${safe((p.vat_rate??.15)*100)}"></label>
          <label class="field"><span>${opsTr('رسوم الدفع عند الاستلام')}</span><input name="cod_fee" type="number" min="0" step="0.01" value="${safe(p.cod_fee??3.5)}"></label>
          <label class="field"><span>${opsTr('نسبة التأمين %')}</span><input name="insurance_rate" type="number" min="0" max="100" step="0.1" value="${safe((p.insurance_rate??.02)*100)}"></label>
          <label class="field"><span>${opsTr('أقل رسوم تأمين')}</span><input name="insurance_minimum" type="number" min="0" step="0.01" value="${safe(p.insurance_minimum??5)}"></label>
          <div class="field span-2"><button class="btn primary full">${opsTr('حفظ تعرفة النظام')}</button></div>
        </form>`:`<div class="record-meta" style="grid-template-columns:repeat(2,minmax(0,1fr))">
          <span>${opsTr('تعرفة احتياطية بدون أبعاد')}: <b>${fmt(p.base_fee??65)} ${opsTr('ر.س')}</b></span>
          <span>${opsTr('الوزن المشمول (كجم)')}: <b>${fmt(p.included_weight??1)}</b></span>
          <span>${opsTr('رسوم كل كجم إضافي')}: <b>${fmt(p.extra_kg_fee??2.5)} ${opsTr('ر.س')}</b></span>
          <span>${opsTr('ضريبة القيمة المضافة %')}: <b>${fmt((p.vat_rate??.15)*100)}%</b></span>
          <span>${opsTr('رسوم الدفع عند الاستلام')}: <b>${fmt(p.cod_fee??3.5)} ${opsTr('ر.س')}</b></span>
          <span>${opsTr('نسبة التأمين %')}: <b>${fmt((p.insurance_rate??.02)*100)}%</b></span>
          <span>${opsTr('أقل رسوم تأمين')}: <b>${fmt(p.insurance_minimum??5)} ${opsTr('ر.س')}</b></span>
        </div>`}
      </section>
    </div>
    <div class="section-title"><div><h2>${opsTr('كتالوج الأحجام والأسعار')}</h2><p>${opsTr('كل بطاقة تمثل حجماً تقريبياً وسعراً أساسياً للشحن.')}</p></div><span class="badge">${sizes.length}</span></div>
    <div class="pricing-admin-grid customer-pricing-3d-grid management-pricing-outlet-grid">
      ${sizes.map(row=>`<article class="pricing-admin-card pricing-admin-outlet-wrap ${row.is_active===0?'is-disabled':''}">
        ${pricing3DCard(row,'')}
        <div class="pricing-admin-meta"><span>${row.manual_only?opsTr('اختيار يدوي فقط'):opsTr('اقتراح تلقائي')}</span><span>${row.is_active!==0?opsTr('نشط'):opsTr('غير نشط')}</span></div>
        ${canManage?`<button class="btn light full" type="button" data-pricing-edit="${safe(row.id)}">${opsTr('تعديل الحجم والسعر')}</button>`:''}
      </article>`).join('')}
    </div>`;
  }
  window.createModal=createShipmentModal;
  window.linkCustomerAccountModal=linkCustomerAccountModal;
  window.home=executiveHomePage;
  window.dispatchPage=dispatchLive;
  window.driversPage=driversFleetPage;
  window.clientsPage=clientsLivePage;
  window.campaignsPage=campaignsLivePage;
  window.staffPage=staffLivePage;
  window.analyticsPage=managementReportsPage;
  window.trackingPage=trackingWithPublic;
  window.proofPage=proofLive;
  window.openDeliveryProof=function(awb){if(!requirePermission('pod.read'))return;page='proof';window.render();requestAnimationFrame(()=>{const select=$('#proofAwb');if(!select||![...select.options].some(option=>option.value===awb))return toast(opsTr('لم نعثر على الشحنة'));select.value=awb;select.dispatchEvent(new Event('change',{bubbles:true}));$('.ops-pod-card')?.scrollIntoView({behavior:'smooth',block:'start'})})};
  window.landingPage=landingWithTracker;
  window.pricingPage=pricingLive;
  function actionFailure(type,err){console.error(`Action ${type} failed`,err);if($('#routeLoading'))closeModal();toast(opsTr('تعذر فتح الإجراء. أعد تحميل الصفحة وحاول مرة أخرى.'))}
  window.action=function(type,button){if(!canAction(type))return toast(opsTr('ليست لديك صلاحية لهذا الإجراء'));try{const handlers={create:createShipmentModal,route:routeCreateModal,vehicle:vehicleFleetModal,branch:branchModal,client:clientFormModal,campaign:campaignModal,driver:driverModal,staff:()=>openUserAccount(),'reset-demo':resetDemo,export:()=>exportReport('pdf'),'export-pdf':()=>exportReport('pdf'),'export-xlsx':()=>exportReport('xlsx')};if(handlers[type]){const result=handlers[type]();return result?.catch?result.catch(err=>actionFailure(type,err)):result}if(type==='quote'){page='pricing';render();requestAnimationFrame(()=>$('#pricingQuoteForm input')?.focus());return}if(type==='contract'){if(button?.dataset.clientId)return clientDetailsModal(button.dataset.clientId);page='clients';render();return}if(type==='contact'){const phone=button?.dataset.phone;if(phone){location.href=`tel:${phone}`;return}return toast(opsTr('رقم التواصل غير متوفر'))}return baseAction(type)}catch(err){actionFailure(type,err)}};
  window.addEventListener('ghazala:languagechange',()=>{
    fixStaffLanguageShell();
    if(state.auditOpen){openAuditLogScreen();return}
    const modalOpen=!!document.querySelector('#modalRoot')?.children?.length;
    if(user&&accessRole()!=='customer'&&!modalOpen){
      window.render();
      return;
    }
    // Keep active forms/signatures intact when a modal is open.
    localizeNow(document.body);
    fixResidualOpsLanguage(document.body);
    if($('#documentFrame')&&state.documentPreview){
      const preview=state.documentPreview;
      if(preview.kind==='waybill')showWaybill(preview.id);else printManifest(preview.id);
    }
  });
  window.render=function(){state.auditOpen=false;syncOpsOwner();const fragment=trackingFragment();if(fragment&&(!user||page==='landing')){tracking=fragment.awb;if(user)page='tracking'}else if(fragment&&user&&page!=='tracking'&&page!=='business'){history.replaceState(null,'',location.pathname+location.search)}baseRender();bindOps();installSearchAuditUI();app.dataset.opsReady='1';if(user)refreshOps()};
  window.addEventListener('hashchange',()=>{const fragment=trackingFragment();if(fragment){page=user?'tracking':'landing';tracking=fragment.awb;render();window.scrollTo(0,0)}else if($('#customerTrackingView',app)){tracking='';page='landing';render()}});
  window.bindOps=bindOps;
  if(!state.notificationTimer){
    state.notificationTimer=setInterval(refreshManagementFeed,15000);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshManagementFeed()});
  }
  requestAnimationFrame(()=>{
    if(!app.dataset.opsReady)window.render();
    setTimeout(refreshManagementFeed,1200);
  });
})();
