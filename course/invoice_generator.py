"""
Automated Invoice Generation System for Deep Eigen.

This module leverages the ReportLab library to programmatically generate 
professional PDF invoices for courses, subscriptions, and custom playlists.
It handles multi-tiered installment labeling, currency calculation based on 
user country, and dynamic amount-to-words conversion.
"""
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

def generate_professional_invoice(order, item, payment, installment_number=1, invoice_type='course'):
    """!
    @brief Generates a professional PDF invoice for a transaction using the ReportLab library.
    @details Handles complex layout balancing, multi-currency formatting, 
             amount-to-words conversion, and installment-specific data labeling.

    @param order (Order) The order object containing billing and shipping details.
    @param item (Union[EnrolledUser, UserSubscription, CustomPlaylist]) The specific entity being purchased.
    @param payment (Payment) The payment record containing the transaction ID and amount.
    @param installment_number (int) The current installment index (1, 2, or 3). Defaults to 1.
    @param invoice_type (str) Product classification: 'course', 'subscription', or 'playlist'. Defaults to 'course'.

    @return bytes The generated PDF binary content, or None if the user context is missing.
    """
    buffer = BytesIO()
    p = inflect.engine()

    user = getattr(item, 'user', None) or (order.user if order else None)
    if not user:
        return None

    # Use order country first, then user country, then profile
    profile = getattr(user, 'userprofile', None)
    
    country_val = (getattr(order, 'country', '') or getattr(user, 'country', '') or (profile.country if profile else '') or '').upper()
    is_indian = country_val in ['INDIA', 'IN']
    currency = 'Rs' if is_indian else '$'
    currency_label = 'Total INR' if is_indian else 'Total USD'

    state = getattr(order, 'state', '')
    if not state or state.lower() == 'online':
        state = (profile.state if profile else '') or ''
    
    country = country_val.capitalize()
    if country.upper() in ['INDIA', 'IN']: 
        country = 'India'
    elif not country:
        country = 'India' # Default fallback if nothing found

    zipcode = getattr(order, 'zipcode', '')
    if not zipcode or zipcode == '000000':
        if profile and hasattr(profile, 'postal_code') and profile.postal_code:
            zipcode = profile.postal_code
        elif profile and hasattr(profile, 'address_line_2') and profile.address_line_2:
            zipcode = profile.address_line_2
        else:
            zipcode = '462026' 

    if invoice_type == 'course':
        title = item.course.title if item.course else "Course Access"
     
        total_fee = Decimal(str(item.course_price or getattr(order, 'total_amount', 0) or 0)) 
        num_installments = item.no_of_installments or 1
        
        current_installment_amount = Decimal(str(payment.amount_paid or 0))

        from course.models import Payment as CoursePaymentModel
        
        paid_sum = 0
        if installment_number >= 1 and item.payment:
            paid_sum += float(item.payment.amount_paid or 0)
        
        if installment_number >= 2 and item.installment_id_2:
            p2 = CoursePaymentModel.objects.filter(payment_id=item.installment_id_2, status__iexact="Completed").first()
            if p2: paid_sum += float(p2.amount_paid or 0)
            
        if installment_number >= 3 and item.installment_id_3:
            p3 = CoursePaymentModel.objects.filter(payment_id=item.installment_id_3, status__iexact="Completed").first()
            if p3: paid_sum += float(p3.amount_paid or 0)
        
        total_paid = Decimal(str(round(paid_sum, 2)))
        
        # Installment label
        if num_installments == 1:
            installment_text = "Full Payment"
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(installment_number, 'th')
            installment_text = f"{installment_number}{suffix} Installment"

    elif invoice_type == 'subscription':
        # item is UserSubscription
        plan = item.plan
        title = f"Subscription: {plan.plan_type} ({plan.duration_type})"
        total_fee = Decimal(str(getattr(order, 'total_amount', 0) or (plan.indian_price if is_indian else plan.foreign_price)))
        current_installment_amount = total_fee
        total_paid = total_fee
        num_installments = 1
        installment_text = "Full Payment"

    elif invoice_type == 'playlist':
        # item is CustomPlaylist
        title = f"Custom Playlist: {item.title}"
        total_fee = Decimal(str(item.total_price or 0))
        current_installment_amount = total_fee
        total_paid = total_fee
        num_installments = 1
        installment_text = "Full Payment"
    
    else:
        title = "Access Purchase"
        total_fee = Decimal(str(payment.amount_paid or 0))
        current_installment_amount = total_fee
        total_paid = total_fee
        num_installments = 1
        installment_text = "Full Payment"

    remaining_amount = round(total_fee - total_paid, 2)
    if remaining_amount < 0.05: 
        remaining_amount = Decimal('0.00')

    # ---------------- 4. Amount in Words ----------------
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

    # ---------------- 5. Canvas Setup ----------------
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Invoice_{payment.payment_id}")

    page_width, page_height = A4
    margin = 20 * mm
    usable_width = page_width - (2 * margin)

    # Top-align Logo and "INVOICE"
    header_y = page_height - 25*mm

    from django.conf import settings
    logo_paths = [
        "/home/deepeigen/Desktop/1 APR DEEPEIGEN ALL CODE/frontend/src/assets/Logo/logo-black.png",
        os.path.join(settings.BASE_DIR, 'static', 'img', 'logo-black.png'),
    ]
    
    logo_path = None
    for lp in logo_paths:
        if os.path.exists(lp):
            logo_path = lp
            break

    if logo_path:
        logo_height = 12 * mm
        # Logo on the left
        c.drawImage(logo_path, margin, 
        header_y - (logo_height / 2),
        width=45*mm, 
        preserveAspectRatio=True, mask='auto')

    # Heading centered but at the same top level as logo
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.red)
    c.drawCentredString(page_width / 2, header_y, "INVOICE")
    c.setStrokeColor(colors.red)
    c.line(page_width / 2 - 12*mm, header_y - 2*mm, page_width / 2 + 12*mm, header_y - 2*mm)

    # ==================== INFO AREA - BALANCED COLUMNS ====================
    y_pos = header_y - 30*mm
    c.setFillColor(colors.black)
    
    # Column X-coordinates
    left_x_label = margin
    left_x_value = margin + 22*mm
    
    right_x_label = page_width - margin - 75*mm
    right_x_value = page_width - margin - 50*mm

    # Row 1: Name & Invoice #
    c.setFont("Helvetica", 10)
    c.drawString(left_x_label, y_pos, "To")
    c.setFont("Helvetica-Bold", 10)
    first_name = getattr(order, 'first_name', '') or user.first_name
    last_name = getattr(order, 'last_name', '') or user.last_name
    c.drawString(left_x_value, y_pos, f": {first_name} {last_name}")

    c.setFont("Helvetica-Bold", 10)
    invoice_no_prefix = "DE"
    year_suffix = payment.created_at.strftime('%y-%y') if hasattr(payment, 'created_at') and payment.created_at else '26-26'
    invoice_no = f"{invoice_no_prefix}/{year_suffix}/{payment.payment_id[-6:]}"
    c.drawString(right_x_label, y_pos, "#")
    c.drawString(right_x_value, y_pos, f": {invoice_no}")

    # Row 2: State & Date
    y_pos -= 6*mm
    c.setFont("Helvetica", 10)
    c.drawString(left_x_label, y_pos, "State")
    c.drawString(left_x_value, y_pos, f": {state}")

    c.setFont("Helvetica-Bold", 10)
    invoice_date = payment.created_at.strftime('%d/%m/%Y') if hasattr(payment, 'created_at') and payment.created_at else datetime.now().strftime('%d/%m/%Y')
    c.drawString(right_x_label, y_pos, "Date")
    c.drawString(right_x_value, y_pos, f": {invoice_date}")

    # Row 3: Country & Phone
    y_pos -= 6*mm
    c.setFont("Helvetica", 10)
    c.drawString(left_x_label, y_pos, "Country")
    c.drawString(left_x_value, y_pos, f": {country}")

    c.setFont("Helvetica-Bold", 10)
    phone_val = getattr(order, 'phone', '') or getattr(user, 'phone_number', '') or ''
    c.drawString(right_x_label, y_pos, "Phone")
    c.drawString(right_x_value, y_pos, f": {phone_val}")

    # Row 4: PIN & Email
    y_pos -= 6*mm
    c.setFont("Helvetica", 10)
    c.drawString(left_x_label, y_pos, "PIN")
    c.drawString(left_x_value, y_pos, f": {zipcode}")

    c.setFont("Helvetica-Bold", 10)
    email_val = getattr(order, 'email', '') or user.email
    c.drawString(right_x_label, y_pos, "Email")
    c.drawString(right_x_value, y_pos, f": {email_val}")

    # Row 5: Access Validity (NEW)
    y_pos -= 6*mm
    valid_until = "Lifetime"
    if invoice_type == 'course' and hasattr(item, 'end_at') and item.end_at:
        valid_until = item.end_at.strftime('%d/%m/%Y')
    elif invoice_type == 'subscription' and hasattr(item, 'end_date') and item.end_date:
        valid_until = item.end_date.strftime('%d/%m/%Y')
    elif invoice_type == 'playlist' and hasattr(item, 'created_at'):
        from dateutil.relativedelta import relativedelta
        valid_until = (item.created_at + relativedelta(months=item.duration)).strftime('%d/%m/%Y')

    c.setFont("Helvetica-Bold", 10)
    c.drawString(right_x_label, y_pos, "Access Until")
    c.drawString(right_x_value, y_pos, f": {valid_until}")



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

    description_para = Paragraph(title, course_title_style)

    data = [
        ['#', 'Description', 'Payment ID', currency_label],
        ['1', description_para, payment.payment_id, f'{currency} : {total_fee:.2f}'],
        ['2', 'Discount Offered', '', f'{currency} : 0.00'],
        ['', '', '', ''],
    ]

    if invoice_type == 'course':
        data.extend([
            ['3', 'No Of Installments', 'Installment', 'Amount'],
            ['', str(num_installments), installment_text, f'{currency}:{current_installment_amount:.2f}'],
        ])
    else:
        # For non-course types, we don't necessarily need the installments breakdown
        data.extend([
            ['3', 'Purchase Type', 'Details', 'Amount'],
            ['', invoice_type.capitalize(), installment_text, f'{currency}:{current_installment_amount:.2f}'],
        ])

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