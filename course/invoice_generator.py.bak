import inflect
import os
from io import BytesIO
from datetime import datetime
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

def generate_professional_invoice(order, enrollment, payment, installment_number):
    """
    Generates an invoice matching the old format (Image 1)
    """
    buffer = BytesIO()
    p = inflect.engine()

    # ---------------- Currency ----------------
    user = enrollment.user
    user_country = (getattr(user, 'country', '') or '').upper()
    is_indian = user_country in ['INDIA', 'IN']
    currency = 'Rs' if is_indian else '$'
    currency_label = 'Total INR' if is_indian else 'Total USD'

    # ---------------- Address Fallback ----------------
    profile = getattr(user, 'userprofile', None)

    state = getattr(order, 'state', '') or (profile.state if profile else '') or ''
    country = getattr(order, 'country', '') or (profile.country if profile else '') or user.country or ''
    zipcode = getattr(order, 'zipcode', '') or (profile.address_line_2 if profile else '') or '000000'

    if not zipcode or zipcode == '000000':
        zipcode = getattr(order, 'zipcode', '') or '462026'

    # ---------------- Installment Logic ----------------
    total_fee = Decimal(str(enrollment.course_price or 0))
    num_installments = enrollment.no_of_installments or 1
    current_installment_amount = round(total_fee / num_installments, 2)

    if installment_number == 1:
        total_paid = current_installment_amount
        installment_text = "1st Installment"
    elif installment_number == 2:
        total_paid = round(current_installment_amount * 2, 2)
        installment_text = "2nd Installment"
    elif installment_number == 3:
        total_paid = total_fee
        installment_text = "3rd Installment"
    else:
        total_paid = current_installment_amount
        installment_text = f"{installment_number}th Installment"

    remaining_amount = total_fee - total_paid

    # Amount in words (handling paise/cents)
    def amount_to_words(amount, is_indian):
        whole_part = int(amount)
        decimal_part = int(round((amount - whole_part) * 100))

        words = p.number_to_words(whole_part).replace(",", "").capitalize()

        if is_indian:
            if decimal_part > 0:
                decimal_words = p.number_to_words(decimal_part).replace(",", "")
                return f"INR {words} Rupees and {decimal_words} Paise Only /-"
            return f"INR {words} Rupees Only /-"
        else:
            if decimal_part > 0:
                decimal_words = p.number_to_words(decimal_part).replace(",", "")
                return f"USD {words} Dollars and {decimal_words} Cents Only /-"
            return f"USD {words} Dollars Only /-"

    words_full = amount_to_words(total_paid, is_indian)

    # ---------------- Canvas Setup ----------------
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Invoice_{payment.payment_id}")

    page_width, page_height = A4
    margin = 20 * mm
    usable_width = page_width - (2 * margin)

    # ==================== HEADER ====================
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.red)
    c.drawCentredString(page_width / 2, page_height - 25*mm, "INVOICE")
    c.setStrokeColor(colors.red)
    c.line(page_width / 2 - 12*mm, page_height - 26*mm, page_width / 2 + 12*mm, page_height - 26*mm)

    from django.conf import settings
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo-black.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, margin, page_height - 40*mm, width=45*mm, preserveAspectRatio=True, mask='auto')

    # ==================== INFO AREA ====================
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    y_pos = page_height - 65*mm

    c.drawString(margin, y_pos, "To")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin + 20*mm, y_pos, f": {order.first_name} {order.last_name}")
    c.setFont("Helvetica", 10)
    y_pos -= 5*mm
    c.drawString(margin, y_pos, "State")
    c.drawString(margin + 20*mm, y_pos, f": {state}")
    y_pos -= 5*mm
    c.drawString(margin, y_pos, "Country")
    c.drawString(margin + 20*mm, y_pos, f": {country}")
    y_pos -= 5*mm
    c.drawString(margin, y_pos, "PIN")
    c.drawString(margin + 20*mm, y_pos, f": {zipcode}")

    # Right Column Info
    y_pos = page_height - 58*mm
    c.setFont("Helvetica-Bold", 10)
    invoice_no = f"DE/{payment.created_at.strftime('%y-%y') if hasattr(payment, 'created_at') and payment.created_at else '26-26'}/{payment.payment_id[-6:]}"
    c.drawRightString(page_width - margin - 35*mm, y_pos, "#")
    c.drawString(page_width - margin - 32*mm, y_pos, f" {invoice_no}")

    y_pos -= 5*mm
    invoice_date = payment.created_at.strftime('%d/%m/%Y') if hasattr(payment, 'created_at') and payment.created_at else datetime.now().strftime('%d/%m/%Y')
    c.drawRightString(page_width - margin - 35*mm, y_pos, "Date:")
    c.drawString(page_width - margin - 32*mm, y_pos, f" {invoice_date}")

    y_pos -= 10*mm
    c.drawRightString(page_width - margin - 75*mm, y_pos, "Phone:")
    c.drawString(page_width - margin - 72*mm, y_pos, f" {user.phone_number or ''}")

    y_pos -= 5*mm
    c.drawRightString(page_width - margin - 75*mm, y_pos, "Email:")
    c.drawString(page_width - margin - 72*mm, y_pos, f" {user.email}")

    # ==================== MAIN TABLE ====================
    y_pos -= 20*mm
    styles = getSampleStyleSheet()
    course_title_style = ParagraphStyle(
        'CourseTitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        alignment=0,
    )

    table_style = TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ])

    course_para = Paragraph(enrollment.course.title if enrollment.course else "Unknown Course", course_title_style)

    data = [
        ['#', 'Course Description', 'Payment ID', currency_label],
        ['1', course_para, payment.payment_id, f'{currency} : {total_fee:.2f}'],
        ['2', 'Discount Offered', '', f'{currency} : 0.00'],
        ['', '', '', ''],
        ['3', 'No Of Installments', 'Installment', 'Amount'],
        ['', str(enrollment.no_of_installments), installment_text, f'{currency}:{current_installment_amount:.2f}'],
    ]

    col_widths = [usable_width * 0.07, usable_width * 0.53, usable_width * 0.25, usable_width * 0.15]
    t = Table(data, colWidths=col_widths)
    t.setStyle(table_style)

    w, h = t.wrap(usable_width, page_height)
    t.drawOn(c, margin, y_pos - h)

    y_pos -= (h + 5*mm)

    # ==================== SUMMARY SECTION ====================
    summary_data = [
        ["Total Amount", f"{currency} : {total_fee:.2f}"],
        ["Paid amount", f"{currency} : {total_paid:.2f}"],
        ["Remaining Amount", f"{currency} : {remaining_amount:.2f}"]
    ]
    st = Table(summary_data, colWidths=[usable_width * 0.85, usable_width * 0.15])
    st.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    sw, sh = st.wrap(usable_width, page_height)
    st.drawOn(c, margin, y_pos - sh)

    y_pos -= (sh + 10*mm)

    # ==================== FOOTER ====================
    c.setFont("Helvetica", 10)
    c.drawString(margin, y_pos, "SUBJECT TO BHOPAL JURISDICTION")
    c.drawRightString(page_width - margin, y_pos, "E. & O. E.")

    y_pos -= 12*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y_pos, f"Amount Chargeable (in words) :")
    y_pos -= 5*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y_pos, words_full)

    y_pos -= 15*mm
    c.setFont("Helvetica", 9)
    c.drawRightString(page_width - margin, y_pos, "computer generated receipt hence signature not required")

    # Bottom lines
    y_pos -= 20*mm
    c.setStrokeColor(colors.red)
    c.line(margin, y_pos, page_width - margin, y_pos)
    y_pos -= 6*mm
    c.setFont("Helvetica", 10)
    c.drawString(margin + 5*mm, y_pos, "Company PAN : AAICD5934H")
    y_pos -= 6*mm
    c.drawString(margin + 5*mm, y_pos, "CIN : U80900MP2021PTC056553")
    y_pos -= 6*mm
    c.line(margin, y_pos, page_width - margin, y_pos)

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()