"""Authenticated shipment report generation. Files are built locally, in memory."""

from datetime import datetime, timedelta, timezone

from io import BytesIO

from pathlib import Path

import re

import json

import math

import sys

import threading

from xml.sax.saxutils import escape



ROOT = Path(__file__).parent

# Local report packages include Arabic/Urdu bidi and Hindi shaping dependencies.

# The Windows package supplies them here when the shared runtime lacks them;

# a normal deployment installs the same packages from requirements.txt.

LOCAL_DEPS = ROOT / "work" / "report-deps"

if LOCAL_DEPS.is_dir():

    sys.path.insert(0, str(LOCAL_DEPS))



LANGUAGES = ("ar", "en", "ur", "hi")

PERIODS = ("today", "7d", "30d", "90d", "365d", "all", "month", "quarter", "year")

MIME = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

LABELS = {

    "title": ("تقرير الشحنات", "Shipment report", "شپمنٹس کی رپورٹ", "शिपमेंट रिपोर्ट"),

    "brand": ("غزالا ترانسبورت", "Ghazala Transport", "غزالا ٹرانسپورٹ", "ग़ज़ाला ट्रांसपोर्ट"),

    "period": ("الفترة المحددة", "Selected period", "منتخب مدت", "चुनी हुई अवधि"),

    "today": ("اليوم", "Today", "آج", "आज"),

    "7d": ("آخر 7 أيام", "Last 7 days", "گزشتہ 7 دن", "पिछले 7 दिन"),

    "30d": ("آخر 30 يوماً", "Last 30 days", "گزشتہ 30 دن", "पिछले 30 दिन"),

    "90d": ("آخر 90 يوماً", "Last 90 days", "گزشتہ 90 دن", "पिछले 90 दिन"),

    "365d": ("آخر 365 يوماً", "Last 365 days", "گزشتہ 365 دن", "पिछले 365 दिन"),

    "all": ("كل الفترات", "All time", "تمام مدت", "सभी समय"),

    "month": ("هذا الشهر", "This month", "اس ماہ", "इस महीने"),

    "quarter": ("هذا الربع", "This quarter", "اس سہ ماہی", "इस तिमाही"),

    "year": ("هذا العام", "This year", "اس سال", "इस वर्ष"),

    "generated": ("وقت إعداد التقرير", "Generated at", "رپورٹ بننے کا وقت", "रिपोर्ट बनाने का समय"),

    "timezone": ("توقيت السعودية (UTC+03:00)", "KSA time (UTC+03:00)", "سعودی وقت (UTC+03:00)", "सऊदी समय (UTC+03:00)"),

    "shipments": ("الشحنات", "Shipments", "شپمنٹس", "शिपमेंट"),

    "rate": ("معدل التسليم", "Delivery rate", "ڈیلیوری کی شرح", "डिलीवरी दर"),

    "cod": ("مبالغ التحصيل المطلوبة", "Requested COD amounts", "مطلوبہ COD رقوم", "वसूली के लिए माँगी गई COD राशि"),

    "total_fee": ("قيمة رسوم الشحن المسجلة (شاملة الضريبة)", "Recorded shipment charges (incl. VAT)", "درج شدہ شپنگ چارجز (VAT سمیت)", "दर्ज शिपिंग शुल्क (VAT सहित)"),

    "awb": ("رقم البوليصة", "Waybill number", "وے بل نمبر", "वेबिल नंबर"),

    "status": ("الحالة", "Status", "حالت", "स्थिति"),

    "origin": ("من", "From", "کہاں سے", "कहाँ से"),

    "destination": ("إلى", "To", "کہاں تک", "कहाँ तक"),

    "sender_name": ("المرسل", "Sender", "بھیجنے والا", "भेजने वाला"),

    "sender_phone": ("جوال المرسل", "Sender mobile", "بھیجنے والے کا موبائل", "भेजने वाले का मोबाइल"),

    "recipient": ("المستلم", "Recipient", "وصول کنندہ", "प्राप्तकर्ता"),

    "phone": ("جوال المستلم", "Recipient mobile", "وصول کنندہ کا موبائل", "प्राप्तकर्ता का मोबाइल"),

    "driver_name": ("السائق", "Driver", "ڈرائیور", "ड्राइवर"),

    "driver_location": ("الموقع الحالي للسائق", "Driver current location", "ڈرائیور کی موجودہ جگہ", "ड्राइवर का वर्तमान स्थान"),

    "eta": ("وقت الوصول المتوقع", "Estimated arrival (ETA)", "متوقع آمد (ETA)", "अनुमानित आगमन (ETA)"),

    "created_at": ("تاريخ الإنشاء", "Created at", "بننے کا وقت", "बनाने का समय"),

    "details": ("تفاصيل الشحنات", "Shipment details", "شپمنٹس کی تفصیلات", "शिपमेंट विवरण"),

    "empty": ("لا توجد شحنات خلال الفترة المحددة", "No shipments in the selected period", "منتخب مدت میں کوئی شپمنٹ نہیں", "चुनी हुई अवधि में कोई शिपमेंट नहीं"),

    "currency": ("ر.س", "SAR", "ریال", "रियाल"),

    "page": ("صفحة", "Page", "صفحہ", "पृष्ठ"),

    "جدة": ("جدة", "Jeddah", "جدہ", "जेद्दा"),

    "جازان": ("جازان", "Jaazan", "جازان", "जाज़ान"),

    "تم إنشاء الشحنة": ("تم إنشاء الشحنة", "Shipment created", "شپمنٹ بن گئی", "शिपमेंट बनाया गया"),

    "قيد النقل": ("قيد النقل", "In transit", "راستے میں", "रास्ते में"),

    "جاهز للتسليم": ("جاهز للتسليم", "Ready for delivery", "ڈیلیوری کے لیے تیار", "डिलीवरी के लिए तैयार"),

    "قيد التوصيل": ("قيد التوصيل", "Out for delivery", "ڈیلیوری کے لیے روانہ", "डिलीवरी के लिए निकला"),

    "تم الاستلام": ("تم الاستلام", "Delivered", "ڈیلیور ہو گئی", "डिलीवर हो गया"),

    "تأخير": ("تأخير", "Delayed", "تاخیر", "देरी"),

    "اليوم": ("اليوم", "Today", "آج", "आज"),

    "غداً": ("غداً", "Tomorrow", "کل", "कल"),

    "مكتمل": ("مكتمل", "Complete", "مکمل", "पूरा"),

    "متأخر": ("متأخر", "Delayed", "تاخیر", "देरी"),

    "ساعات": ("ساعات", "hours", "گھنٹے", "घंटे"),

}

COLUMNS = ("awb", "status", "origin", "destination", "sender_name", "sender_phone", "recipient", "phone", "driver_name", "driver_location", "eta", "cod", "total_fee", "created_at")

# Excel must never infer phone numbers as numeric/scientific values.
PHONE_COLUMNS = {"sender_phone", "phone"}

KSA = timezone(timedelta(hours=3))

FONT_LOCK = threading.Lock()

CATALOG_FILE = ROOT / "assets" / "ui-translations.json"

UI_TRANSLATIONS = json.loads(CATALOG_FILE.read_text(encoding="utf-8")) if CATALOG_FILE.is_file() else {}

TRANSLATION_PATTERNS = {}

for language in LANGUAGES:

    phrases = UI_TRANSLATIONS.get(language, {})

    sources = sorted((key for key in phrases if re.search(r"[\u0600-\u06ff]", key)), key=len, reverse=True)

    TRANSLATION_PATTERNS[language] = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(key) for key in sources) + r")(?!\w)") if sources else None





def label(key, lang):

    return LABELS.get(key, (key,) * 4)[LANGUAGES.index(lang)]





def translated(value, lang):

    value = str(value or "")

    if value in LABELS:

        return label(value, lang)

    phrases = UI_TRANSLATIONS.get(lang, {})

    if value in phrases:

        return phrases[value]

    pattern = TRANSLATION_PATTERNS.get(lang)

    # A single pass also localizes parameterized ETA and system location text.

    return pattern.sub(lambda match: phrases[match.group(0)], value) if pattern else value





def parse_timestamp(value):

    try:

        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    except (TypeError, ValueError):

        raise ValueError("Invalid report date")

    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).astimezone(timezone.utc)





def report_options(query):

    fmt = query.get("format", [""])[0]

    lang = query.get("lang", ["en"])[0]

    period = query.get("period", ["month"])[0]

    if fmt not in MIME or lang not in LANGUAGES or period not in PERIODS:

        raise ValueError("Invalid report format, language or period")

    start = parse_timestamp(query.get("start", [""])[0])

    end = parse_timestamp(query.get("end", [""])[0])

    if start > end:

        raise ValueError("Report end must be after its start")

    return fmt, lang, period, start, end





def selected_rows(rows, start, end):

    result = []

    for row in rows:

        try:

            created = parse_timestamp(row.get("created_at"))

        except ValueError:

            continue

        if start <= created <= end:

            result.append(row)

    return result





def is_delivered_status(value):
    status = str(value or "").strip().casefold()
    return status in {"تم الاستلام", "تم التسليم", "delivered"}


def totals(rows):

    return {"shipments": len(rows), "rate": math.floor(100 * sum(is_delivered_status(r.get("status")) for r in rows) / len(rows) + .5) if rows else 0,

            "cod": round(sum(float(r.get("cod") or 0) for r in rows), 2),

            "total_fee": round(sum(float(r.get("total_fee") or 0) for r in rows), 2)}





def date_text(dt):

    return dt.astimezone(KSA).strftime("%Y-%m-%d %H:%M:%S")





def cell_value(row, key, lang):

    value = row.get(key)

    if key in ("cod", "total_fee"):

        return round(float(value or 0), 2)

    if key == "created_at" and value:

        try:

            return date_text(parse_timestamp(value))

        except ValueError:

            pass

    if key == "eta" and is_delivered_status(row.get("status")):

        return translated("مكتمل", lang)

    if key in ("status", "origin", "destination", "eta", "driver_location"):

        return translated(value, lang)

    # Names, addresses and contact records retain the spelling entered by staff.

    return str(value or "")





def excel_report(rows, lang, period, start, end):

    from openpyxl import Workbook

    from openpyxl.styles import Alignment, Font, PatternFill

    from openpyxl.utils import get_column_letter

    from openpyxl.worksheet.page import PageMargins

    wb = Workbook()

    ws = wb.active

    ws.title = label("shipments", lang)

    rtl = lang in ("ar", "ur")

    ws.sheet_view.rightToLeft = rtl

    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:N1")

    ws["A1"] = label("brand", lang) + " · " + label("title", lang)

    ws["A1"].font = Font(name="Arial", size=18, bold=True, color="0F1D30")

    ws.row_dimensions[1].height = 34

    for n, text in enumerate((label("period", lang) + ": " + label(period, lang),

                              date_text(start) + " — " + date_text(end) + " · " + label("timezone", lang),

                              label("generated", lang) + ": " + date_text(datetime.now(timezone.utc))), 2):

        ws.merge_cells(start_row=n, start_column=1, end_row=n, end_column=14)

        ws.cell(n, 1, text).font = Font(name="Arial", size=11, color="526176")

        ws.row_dimensions[n].height = 24

    stats = totals(rows)

    for index, key in enumerate(("shipments", "rate", "total_fee", "cod")):

        column = 1 + index * 3

        ws.merge_cells(start_row=6, start_column=column, end_row=6, end_column=column + 2)

        ws.merge_cells(start_row=7, start_column=column, end_row=7, end_column=column + 2)

        ws.cell(6, column, label(key, lang)).font = Font(name="Arial", bold=True, color="526176")

        cell = ws.cell(7, column, stats[key] / 100 if key == "rate" else stats[key])

        cell.font = Font(name="Arial", size=18, bold=True, color="0F1D30")

        cell.number_format = "0%" if key == "rate" else '#,##0.00 "' + label("currency", lang) + '"' if key in ("cod", "total_fee") else "0"

    ws.row_dimensions[7].height = 32

    header = 10

    for column, key in enumerate(COLUMNS, 1):

        cell = ws.cell(header, column, label(key, lang))

        cell.fill = PatternFill("solid", fgColor="0F1D30")

        cell.font = Font(name="Arial", bold=True, color="FFFFFF", size=11)

        cell.alignment = Alignment(horizontal="right" if rtl else "left", vertical="center", wrap_text=True)

    ws.row_dimensions[header].height = 42

    widths = (22, 24, 16, 16, 30, 23, 30, 23, 30, 40, 27, 22, 25, 24)

    for index, width in enumerate(widths, 1):

        ws.column_dimensions[get_column_letter(index)].width = width

    for rn, row in enumerate(rows, header + 1):

        wrapped_lines = 1

        for column, key in enumerate(COLUMNS, 1):

            value = cell_value(row, key, lang)

            # Preserve contact identifiers exactly as entered, including +, leading
            # zeros and long digit sequences. Excel must treat them as text.
            if key in PHONE_COLUMNS:
                value = str(value or "")

            cell = ws.cell(rn, column, value)

            if isinstance(value, str):

                # Explicit text avoids Excel interpreting customer data as formulas
                # or converting long phone numbers to scientific notation.

                cell.data_type = "s"

            cell.font = Font(name="Arial", size=11, color="0F1D30")

            cell.fill = PatternFill("solid", fgColor="F8F4F0" if rn % 2 else "FFFFFF")

            cell.alignment = Alignment(horizontal="right" if rtl else "left", vertical="top", wrap_text=True, readingOrder=2 if rtl else 1)

            if key in PHONE_COLUMNS:

                cell.number_format = "@"
                # quotePrefix is an additional Excel hint; it does not alter the
                # displayed value but prevents re-interpretation on open/save.
                try:
                    cell.quotePrefix = True
                except Exception:
                    pass

            elif key in ("cod", "total_fee"):

                cell.number_format = '#,##0.00 "' + label("currency", lang) + '"'

            # Wrapped addresses need enough height to stay readable in Excel.

            capacity = max(8, int(widths[column - 1] * .8))

            wrapped_lines = max(wrapped_lines, sum(max(1, (len(line) + capacity - 1) // capacity) for line in str(value).split("\n")))

        ws.row_dimensions[rn].height = min(409, max(42, wrapped_lines * 17 + 8))

    if not rows:

        ws.merge_cells("A11:N11")

        ws["A11"] = label("empty", lang)

        ws.row_dimensions[11].height = 30

    ws.freeze_panes = "C11"

    ws.auto_filter.ref = f"A10:N{10 + len(rows)}"

    ws.print_title_rows = "1:10"

    ws.print_options.horizontalCentered = True

    ws.page_setup.orientation = "landscape"

    ws.page_setup.paperSize = ws.PAPERSIZE_A3

    ws.page_setup.fitToWidth = 1

    ws.page_setup.fitToHeight = 0

    ws.sheet_properties.pageSetUpPr.fitToPage = True

    ws.page_margins = PageMargins(left=.3, right=.3, top=.4, bottom=.4)

    ws.print_area = f"A1:N{max(11, 10 + len(rows))}"

    wb.properties.title = label("title", lang)

    wb.properties.creator = "Ghazala Transport"

    output = BytesIO()

    wb.save(output)

    return output.getvalue()





def register_fonts():

    from reportlab.pdfbase import pdfmetrics

    from reportlab.pdfbase.ttfonts import TTFont

    with FONT_LOCK:

        for name, file in (("GhazalaLatin", "NotoSans-Regular.ttf"), ("GhazalaArabic", "NotoSansArabic-Regular.ttf"), ("GhazalaHindi", "GhazalaReportHindi-Regular.ttf")):

            if name not in pdfmetrics.getRegisteredFontNames():

                font_path = ROOT / "assets" / "fonts" / file

                if font_path.is_file():

                    pdfmetrics.registerFont(TTFont(name, str(font_path), shapable=name == "GhazalaHindi"))





def pdf_report(rows, lang, period, start, end):

    import arabic_reshaper

    from bidi.algorithm import get_display

    from reportlab.lib import colors

    from reportlab.lib.enums import TA_LEFT, TA_RIGHT

    from reportlab.lib.pagesizes import A4

    from reportlab.lib.styles import ParagraphStyle

    from reportlab.pdfbase import pdfmetrics

    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether, Image

    register_fonts()

    output = BytesIO()

    navy, muted, copper = colors.HexColor("#0F1D30"), colors.HexColor("#526176"), colors.HexColor("#89562F")

    width = A4[0] - 72

    rtl = lang in ("ar", "ur")



    def font_for(char, preferred):

        try:

            if ord(char) in pdfmetrics.getFont(preferred).face.charToGlyph:

                return preferred

            for name in ("GhazalaLatin", "GhazalaArabic", "GhazalaHindi"):

                if ord(char) in pdfmetrics.getFont(name).face.charToGlyph:

                    return name

        except Exception:

            pass

        return preferred



    def font_markup(text, preferred):

        runs, current, font = [], "", preferred

        for char in text:

            chosen = font_for(char, preferred)

            if current and chosen != font:

                runs.append(f'<font name="{font}">{escape(current)}</font>')

                current = ""

            current += char

            font = chosen

        if current:

            runs.append(f'<font name="{font}">{escape(current)}</font>')

        return "".join(runs)



    def paragraph(value, available=width, size=10, color=navy):

        text = str(value or "—")

        arabic = bool(re.search(r"[\u0600-\u08ff]", text))

        hindi = bool(re.search(r"[\u0900-\u097f]", text))

        font = "GhazalaHindi" if hindi else "GhazalaArabic" if arabic else "GhazalaLatin"

        if arabic:

            lines, current = [], ""

            for word in text.split():

                candidate = (current + " " + word).strip()

                visual = get_display(arabic_reshaper.reshape(candidate))

                try:

                    measured = sum(pdfmetrics.stringWidth(char, font_for(char, font), size) for char in visual)

                except Exception:

                    measured = len(visual) * size * 0.6

                if current and measured > available - 4:

                    lines.append(current)

                    current = word

                else:

                    current = candidate

            lines.append(current)

            text = "<br/>".join(font_markup(get_display(arabic_reshaper.reshape(line)), font) for line in lines)

        else:

            text = font_markup(text, font)

        style = ParagraphStyle("report", fontName=font, fontSize=size, leading=size * 1.65,

                               alignment=TA_RIGHT if arabic or rtl else TA_LEFT, textColor=color,

                               shaping=1 if hindi else 0, splitLongWords=True)

        return Paragraph(text, style)



    logo_path = ROOT / "static" / "ghazala-logo.png"

    if logo_path.is_file():

        logo_img = Image(str(logo_path))

        logo_scale = min(54 / logo_img.imageWidth, 54 / logo_img.imageHeight)

        logo_img.drawWidth = logo_img.imageWidth * logo_scale

        logo_img.drawHeight = logo_img.imageHeight * logo_scale

    else:

        logo_img = Paragraph("<b>Ghazala</b>", ParagraphStyle("logo", fontSize=16, textColor=navy))

    header = Table([[logo_img,

                     [paragraph(label("brand", lang), width - 76, 20), paragraph(label("title", lang), width - 76, 14, muted)]]], colWidths=[68, width - 68])

    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 1.5, copper), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))

    story = [header, Spacer(1, 14), paragraph(label("period", lang) + ": " + label(period, lang), size=12),

             paragraph(date_text(start) + " — " + date_text(end), size=9, color=muted),

             paragraph(label("timezone", lang) + " · " + label("generated", lang) + ": " + date_text(datetime.now(timezone.utc)), size=9, color=muted), Spacer(1, 14)]

    stats = totals(rows)

    keys = ("shipments", "rate", "total_fee", "cod")

    summary = Table([[paragraph(label(k, lang), width / 4 - 20, 9, muted) for k in keys],

                     [paragraph(str(stats[k]) + ("%" if k == "rate" else " " + label("currency", lang) if k in ("cod", "total_fee") else ""), width / 4 - 20, 15) for k in keys]], colWidths=[width / 4] * 4)

    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F4F0")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, -1), (-1, -1), 12)]))

    story.extend([summary, Spacer(1, 18), paragraph(label("details", lang), size=15), Spacer(1, 10)])

    if not rows:

        story.append(paragraph(label("empty", lang), size=12, color=muted))

    for row in rows:

        data = [[paragraph(row.get("awb", ""), width / 2 - 26, 12, copper),

                 paragraph(translated(row.get("status"), lang), width / 2 - 26, 11, copper)]]

        for left, right in (("origin", "destination"), ("sender_name", "recipient"), ("sender_phone", "phone"),

                            ("driver_name", "driver_location"), ("eta", "created_at"), ("cod", "total_fee")):

            pair = []

            for key in (left, right):

                value = cell_value(row, key, lang)

                if key in ("cod", "total_fee"):

                    value = f"{value:,.2f} " + label("currency", lang)

                pair.append([paragraph(label(key, lang), width / 2 - 26, 8, muted), paragraph(value, width / 2 - 26, 10)])

            data.append(pair[::-1] if rtl else pair)

        details = Table(data, colWidths=[width / 2] * 2, splitInRow=1, repeatRows=1)

        details.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F4F0")), ("BACKGROUND", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, 0), 10)]))

        story.extend([KeepTogether([details]), Spacer(1, 16)])



    def footer(canvas, doc):

        canvas.saveState()

        canvas.setStrokeColor(colors.HexColor("#E3DBD5"))

        canvas.line(36, 34, A4[0] - 36, 34)

        canvas.setFont("Helvetica", 8)

        canvas.setFillColor(muted)

        brand_footer = paragraph(label("brand", lang) + " · " + label("جدة", lang) + " / " + label("جازان", lang), width - 30, 8, muted)

        _, footer_height = brand_footer.wrap(width - 30, 30)

        brand_footer.drawOn(canvas, 36, 20)

        canvas.drawRightString(A4[0] - 36, 21, str(doc.page))

        canvas.restoreState()



    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=30, bottomMargin=48,

                                 title=label("title", lang), author="Ghazala Transport")

    document.build(story, onFirstPage=footer, onLaterPages=footer)

    return output.getvalue()





def generate_report(rows, fmt, lang, period, start, end):

    filtered = selected_rows(rows, start, end)

    return (pdf_report if fmt == "pdf" else excel_report)(filtered, lang, period, start, end)
