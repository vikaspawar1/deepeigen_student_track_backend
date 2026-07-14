"""
Professional Subscription Invoice PDF Generator using ReportLab
"""

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas


def generate_subscription_invoice(order, subscription, payment, total_courses=0):
    """!
    @brief (Legacy/Utility) Generates a professional PDF invoice for a subscription purchase.
    @details Branded with Deep Eigen headers, it includes billing details, payment summary, 
             and access period information. 
             @note This function is largely superseded by course.invoice_generator.generate_professional_invoice.

    @param order (Order) The order record containing user/billing info.
    @param subscription (UserSubscription) The active subscription instance.
    @param payment (Payment) The transaction record.
    @param total_courses (int) Count of courses accessible in this plan.

    @return bytes Raw PDF binary content.
    """

    buffer = BytesIO()

    # ---------------- Currency ----------------
    user_country = (getattr(order.user, 'country', '') or '').upper()
    is_indian = user_country in ['INDIA', 'IN']
    currency = 'INR' if is_indian else '$'

    # ---------------- Canvas Setup ----------------
    c = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    c.setTitle("SUBSCRIPTION INVOICE")

    page_width, page_height = A4
    margin = 25 * mm
    usable_width = page_width - (2 * margin)

    # ==================== BORDER ====================
    c.rect(15*mm, 15*mm, page_width - 30*mm, page_height - 30*mm)

    # ==================== HEADER ====================
    c.setFont("Helvetica-Bold", 24)
    c.setFillColorRGB(0.17, 0.31, 0.57)
    c.drawString(margin, page_height - 35*mm, "DEEP EIGEN")

    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(margin, page_height - 42*mm, "Professional Learning Platform")
    c.drawString(margin, page_height - 48*mm, "contact@deepeigen.com | www.deepeigen.com")

    # Invoice title
    c.setFont("Helvetica-Bold", 28)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawRightString(page_width - margin, page_height - 35*mm, "INVOICE")

    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0.9, 0.1, 0.1)
    invoice_number = f"{order.order_number}_{payment.payment_id[-6:]}"
    c.drawRightString(page_width - margin, page_height - 42*mm, invoice_number)

    # ==================== BILL TO ====================
    y_pos = page_height - 65*mm

    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.17, 0.31, 0.57)
    c.drawString(margin, y_pos, "BILL TO")

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.2, 0.2, 0.2)

    y_pos -= 5*mm
    c.drawString(margin, y_pos, f"{order.first_name} {order.last_name}")
    y_pos -= 4*mm
    c.drawString(margin, y_pos, order.email or "")
    y_pos -= 4*mm
    c.drawString(margin, y_pos, f"{order.city}, {order.state}, {order.country}")
    y_pos -= 4*mm
    c.drawString(margin, y_pos, f"PIN: {order.zipcode}")

    # ==================== INVOICE DETAILS (CENTER) ====================
    center_x = page_width / 2 - 15*mm

    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.17, 0.31, 0.57)
    c.drawString(center_x, page_height - 65*mm, "INVOICE DETAILS")

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.2, 0.2, 0.2)

    detail_y = page_height - 70*mm
    c.drawString(center_x, detail_y, f"Order #: {order.order_number}")

    invoice_date = payment.created_at if hasattr(payment, 'created_at') else datetime.now()
    detail_y -= 4*mm
    c.drawString(center_x, detail_y, f"Date: {invoice_date.strftime('%d %B %Y')}")

    # Add course count stats
    detail_y -= 4*mm
    c.drawString(center_x, detail_y, f"Total Courses in Plan: {total_courses}")

    # ==================== PAYMENT INFO (RIGHT) ====================
    right_x = page_width - 85*mm

    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.17, 0.31, 0.57)
    c.drawString(right_x, page_height - 65*mm, "PAYMENT INFO")

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.2, 0.2, 0.2)

    pay_y = page_height - 70*mm
    c.drawString(right_x, pay_y, f"Payment ID: {payment.payment_id}")
    pay_y -= 4*mm
    c.drawString(right_x, pay_y, "Status: Completed")

    # ==================== PAYMENT BADGE ====================
    badge_y = page_height - 95*mm

    c.setFillColorRGB(0.8, 0.95, 0.85)
    c.rect(margin, badge_y - 8*mm, usable_width, 10*mm, fill=1, stroke=1)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.2, 0.6, 0.2)
    c.drawString(margin + 5*mm, badge_y - 5*mm, "Payment Received Successfully")

    # ==================== TABLE ====================
    table_y = page_height - 110*mm

    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]

    plan_description = f"{subscription.plan.plan_type} ({subscription.plan.duration_type})"
    description_para = Paragraph(plan_description, normal_style)
    duration_para = Paragraph(f"{subscription.start_date.strftime('%d %b %Y')} to {subscription.end_date.strftime('%d %b %Y')}", normal_style)

    table_data = [
        ['#', 'Subscription Plan', 'Access Period', 'Amount'],
        ['1', description_para, duration_para, f'{currency} {order.total_amount:.2f}'],
    ]

    col_widths = [
        usable_width * 0.08,
        usable_width * 0.42,
        usable_width * 0.30,
        usable_width * 0.20
    ]

    table = Table(table_data, colWidths=col_widths)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4F8F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),

        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),

        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    table.wrapOn(c, usable_width, 0)
    table.drawOn(c, margin, table_y - 35*mm)

    # ==================== PAYMENT SUMMARY ====================
    summary_y = table_y - 55*mm

    summary_width = usable_width * 0.7

    c.setFillColorRGB(0.95, 0.95, 0.95)
    c.rect(margin, summary_y - 35*mm, summary_width, 40*mm, fill=1, stroke=1)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.17, 0.31, 0.57)
    c.drawString(margin + 5*mm, summary_y - 5*mm, "PAYMENT SUMMARY")

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)

    line_y = summary_y - 15*mm
    c.drawString(margin + 5*mm, line_y, "Subtotal:")
    c.drawRightString(margin + summary_width - 5*mm, line_y, f"{currency} {order.total_amount:.2f}")

    line_y -= 6*mm
    c.drawString(margin + 5*mm, line_y, "Tax:")
    c.drawRightString(margin + summary_width - 5*mm, line_y, f"{currency} 0.00")

    line_y -= 8*mm
    c.line(margin + 5*mm, line_y + 2*mm, margin + summary_width - 5*mm, line_y + 2*mm)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.17, 0.31, 0.57)
    c.drawString(margin + 5*mm, line_y - 3*mm, "Total Amount Paid:")
    c.drawRightString(margin + summary_width - 5*mm, line_y - 3*mm, f"{currency} {order.total_amount:.2f}")

    # ==================== FOOTER ====================
    footer_y = 30*mm

    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(margin, footer_y, page_width - margin, footer_y)

    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(page_width / 2, footer_y - 5*mm,
                        "Thank you for subscribing! You now have access to premium course materials.")
    c.drawCentredString(page_width / 2, footer_y - 9*mm,
                        "For queries, contact: support@deepeigen.com | Company PAN: AAICD5934H")
    c.drawCentredString(page_width / 2, footer_y - 13*mm,
                        "Computer generated invoice - signature not required.")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()
