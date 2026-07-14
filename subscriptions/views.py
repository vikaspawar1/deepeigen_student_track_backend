from django.http import HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.conf import settings
from datetime import date, timedelta
import json
import razorpay
import io
from types import SimpleNamespace

from .models import SubscriptionPlan, PlanCategoryAccess, UserSubscription, SubscriptionInvoice
from course.invoice_generator import generate_professional_invoice
from course.models import Order, Payment, Course, EnrolledUser
from course.views import calculate_financial_year
from accounts.models import Account
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status


razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET_KEY)
)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_subscription_plans(request):
    """!
    @brief Public API endpoint to retrieve all available subscription plans.
    @details Returns each plan's tier (Basic/Standard/Premium), duration, pricing in both 
             INR and USD, and the list of course categories it authorizes.

    @param request (Request) DRF Request object.

    @return Response Collection of structured subscription plan metadata (200).
    """

    plans = SubscriptionPlan.objects.all()

    data = []

    for plan in plans:

        categories = PlanCategoryAccess.objects.filter(
            plan_type=plan.plan_type
        ).values_list("category", flat=True)

        data.append({
            "id": plan.id,
            "plan_type": plan.plan_type,
            "duration": plan.duration_type,
            "duration_days": plan.duration_days,
            "indian_price": plan.indian_price,
            "foreign_price": plan.foreign_price,
            "categories": list(categories)
        })

    return Response({
        "success": True,
        "plans": data
    })



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def plan_details(request, plan_type, duration):
    """!
    @brief Fetches granular details for a specific subscription plan based on user region.
    @details Normalizes plan types and durations, applies regional pricing (INR/USD), 
             and provides a list of featured courses accessible under the plan.

    @param request (Request) Authenticated DRF Request.
    @param plan_type (str) Plan tier (e.g., 'BASIC').
    @param duration (str) Timeframe (e.g., 'Monthly').

    @return Response Specific plan metadata and currency-adjusted pricing (200).
    """

    user = request.user
    user_country = (getattr(user, 'country', '') or "").lower()
    is_india = user_country in ["india", "in"]

    # normalize plan_type
    plan_type = plan_type.upper()

    # map frontend duration to backend duration
    duration_map = {
        "Monthly": "MONTHLY",
        "Quarterly": "FOUR_MONTH",
        "Yearly": "YEARLY"
    }

    duration = duration_map.get(duration, duration)

    # get plan
    plan = SubscriptionPlan.objects.filter(
        plan_type=plan_type,
        duration_type=duration
    ).first()

    if not plan:
        return Response({
            "success": False,
            "message": "Plan not found"
        }, status=status.HTTP_404_NOT_FOUND)

    # get allowed categories for this plan
    categories = list(
        PlanCategoryAccess.objects.filter(
            plan_type=plan_type
        ).values_list("category", flat=True)
    )

    # get courses under those categories - Restriction: Featured Only
    courses = Course.objects.filter(category__in=categories, is_featured=True)

    plan_price = plan.indian_price if is_india else plan.foreign_price

    courses_data = [
        {
            "id": c.id,
            "title": c.title,
            "category": c.category,
            "price": c.indian_fee if is_india else c.foreign_fee
        }
        for c in courses
    ]

    # Deductions removed as per user request
    deduction = 0
    purchased_courses = []

    # calculate final price
    final_price = plan_price

    return Response({
        "success": True,
        "id": plan.id,
        "plan": plan_type,
        "duration": duration,
        "plan_price": plan_price,
        "categories": categories,
        "courses": courses_data,
        "already_purchased": purchased_courses,
        "deduction": deduction,
        "final_price": final_price,
        "currency": "INR" if is_india else "USD"
    })



@api_view(['GET'])
def check_course_access(request, course_id):
    """!
    @brief Hybrid access verification endpoint for a specific course.
    @details Simultaneously checks for direct course enrollment and active subscription-based 
             category authorization to determine final user access.

    @param request (Request) Request containing 'user_id' parameter.
    @param course_id (int) ID of the target course.

    @return Response Boolean access status (200).
    """
    user_id = request.GET.get("user_id")

    course = get_object_or_404(Course, id=course_id)

    # check purchased course
    enrolled = EnrolledUser.objects.filter(
        user_id=user_id,
        course=course,
        enrolled=True
    ).exists()

    if enrolled:
        return Response({"access": True})

    # check subscription
    subscription = UserSubscription.objects.filter(
        user_id=user_id,
        is_active=True,
        end_date__gte=timezone.now()
    ).first()

    if not subscription:
        return Response({"access": False})

    # Get allowed categories
    allowed_categories = PlanCategoryAccess.objects.filter(
        plan_type=subscription.plan.plan_type
    ).values_list("category", flat=True)

    if course.category in allowed_categories and course.is_featured:
        return Response({"access": True})

    return Response({"access": False})



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscription_place_order(request):
    """!
    @brief API endpoint to initiate a subscription purchase workflow.
    @details Handles both paid (Razorpay Order creation) and free/deduction-covered 
             plans. For free plans, it immediately activates the subscription and 
             triggers invoice generation.

    @param request (Request) DRF Request with 'plan_id'.

    @return Response Razorpay order data (200) or immediate activation status (200).
    """
    try:
        plan_id = request.data.get("plan_id")
        if not plan_id:
            return Response({"success": False, "error": "Plan ID required"}, status=status.HTTP_400_BAD_REQUEST)

        plan = get_object_or_404(SubscriptionPlan, id=plan_id)

        user_country = (getattr(request.user, 'country', '') or "").lower()
        is_india = user_country in ["india", "in"]

        if is_india:
            base_amount = plan.indian_price
        else:
            base_amount = plan.foreign_price

        # Deduction logic removed as per user request
        deduction = 0
        total_amount = base_amount

        order = Order.objects.create(
            user=request.user,
            subscription_plan=plan,
            first_name=getattr(request.user, 'first_name', ''),
            last_name=getattr(request.user, 'last_name', ''),
            phone=getattr(request.user, 'phone_number', ''),
            email=request.user.email,
            address="",
            country=request.user.country or '',
            state="",
            city="",
            zipcode="",
            course_amount=base_amount,
            tax=0,
            total_amount=total_amount
        )

        order.order_number = f"{date.today().strftime('%Y%m%d')}{order.id}"
        order.save()

        if total_amount > 0:
            # Razorpay order creation
            # Use INR for all transactions to avoid account support/limit issues with USD
            if is_india:
                rzp_amount = int(order.total_amount * 100)
            else:
                # Convert USD to INR equivalent (using 83 as a default conversion rate)
                rzp_amount = int(order.total_amount * 83 * 100)
            
            razorpay_order = razorpay_client.order.create({
                "amount": rzp_amount,
                "currency": "INR",
                "payment_capture": 1
            })

            return Response({
                "success": True,
                "order": {
                    "id": order.id,
                    "order_number": order.order_number,
                    "total_amount": order.total_amount,
                    "currency": "INR" if is_india else "USD"
                },
                "razorpay": razorpay_order
            })
        else:
            # Total amount is 0, activate immediately
            payment = Payment.objects.create(
                user=request.user,
                payment_id=f"FREE-{order.order_number}",
                payment_method="Free/Deduction",
                amount_paid=0,
                status="Completed"
            )
            order.payment = payment
            order.is_ordered = True
            order.save()

            # Activate Subscription
            end_date = timezone.now() + timedelta(days=plan.duration_days)
            sub = UserSubscription.objects.create(
                user=request.user,
                plan=plan,
                payment=payment,
                start_date=timezone.now(),
                end_date=end_date,
                is_active=True
            )

            serial_no_response = calculate_financial_year("paid")
            serial_no = None
            if hasattr(serial_no_response, 'content'):
                serial_no_data = json.loads(serial_no_response.content)
                serial_no = serial_no_data.get('generated_order_code', f"DE-SUB-{order.order_number}")
            else:
                serial_no = f"DE-SUB-{order.order_number}"

            from django.core.files.base import ContentFile
            
            # Calculate exactly how many courses are in the plan
            categories = PlanCategoryAccess.objects.filter(
                plan_type=plan.plan_type
            ).values_list("category", flat=True)
            total_courses = Course.objects.filter(category__in=categories).count()

            pdf_bytes = generate_professional_invoice(
                order=order,
                item=sub,
                payment=payment,
                invoice_type='subscription'
            )

            SubscriptionInvoice.objects.create(
                subscription=sub,
                payment=payment,
                serial_no=serial_no,
                invoice=ContentFile(pdf_bytes, name=f"INV_{serial_no}.pdf")
            )

            return Response({
                "success": True,
                "message": "Subscription activated successfully (Deductions applied)",
                "free": True
            })
    except Exception as e:
        print(f"ERROR in place_order: {str(e)}")
        return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscription_payment_done(request, order_id):
    """!
    @brief Verification callback for subscription fulfillment via Razorpay.
    @details Validates the cryptographic payment signature, finalizes the order, 
             initializes the UserSubscription record, and spawns the SubscriptionInvoice.

    @param request (Request) DRF Request with Razorpay signature and IDs.
    @param order_id (str) The internal order tracking number.

    @return Response Activation confirmation with plan metadata (200).
    """
    try:
        order = get_object_or_404(Order, order_number=order_id)
        
        payment_id = request.data.get('razorpay_payment_id')
        razorpay_order_id = request.data.get('razorpay_order_id')
        signature = request.data.get('razorpay_signature')

        if not all([payment_id, razorpay_order_id, signature]):
            return Response({"success": False, "error": "Missing payment verification fields"}, status=status.HTTP_400_BAD_REQUEST)

        params_dict = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        }

        # Verify Razorpay signature
        razorpay_client.utility.verify_payment_signature(params_dict)

        # Create Payment record
        payment = Payment.objects.create(
            user=request.user,
            payment_id=payment_id,
            payment_method="RazorPay",
            amount_paid=order.total_amount,
            status="Completed"
        )

        order.payment = payment
        order.is_ordered = True
        order.save()

        # Activate Subscription
        plan = order.subscription_plan
        end_date = timezone.now() + timedelta(days=plan.duration_days)

        sub = UserSubscription.objects.create(
            user=request.user,
            plan=plan,
            payment=payment,
            start_date=timezone.now(),
            end_date=end_date,
            is_active=True
        )

        # Generate Invoice
        serial_no_response = calculate_financial_year("paid")
        serial_no = None
        if hasattr(serial_no_response, 'content'):
            serial_no_data = json.loads(serial_no_response.content)
            serial_no = serial_no_data.get('generated_order_code', f"DE-SUB-{order.order_number}")
        else:
            serial_no = f"DE-SUB-{order.order_number}"

        from django.core.files.base import ContentFile
        
        # Calculate exactly how many courses are in the plan versus how many already purchased
        inv_categories = PlanCategoryAccess.objects.filter(
            plan_type=plan.plan_type
        ).values_list("category", flat=True)

        total_courses = Course.objects.filter(category__in=inv_categories).count()

        pdf_bytes = generate_professional_invoice(
            order=order,
            item=sub,
            payment=payment,
            invoice_type='subscription'
        )

        SubscriptionInvoice.objects.create(
            subscription=sub,
            payment=payment,
            serial_no=serial_no,
            invoice=ContentFile(pdf_bytes, name=f"INV_{serial_no}.pdf")
        )

        return Response({
            "success": True,
            "message": "Subscription activated",
            "plan": plan.plan_type,
            "duration": plan.duration_type
        })

    except Exception as e:
        return Response({
            "success": False,
            "error": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def invoice_list(request):
    """!
    @brief Retrieves the authenticated user's subscription purchase history.
    @details Provides a structured list of invoices, payment IDs, and validity windows 
             for display on the student dashboard.

    @param request (Request) DRF Request object.

    @return Response Collection of subscription transaction summaries (200).
    """
    invoices = SubscriptionInvoice.objects.filter(
        subscription__user=request.user,
        payment__status="Completed"
    ).select_related("subscription", "payment", "subscription__plan").order_by("-created_at")

    data = []

    user_country = (getattr(request.user, "country", "") or "").upper()
    is_indian = user_country in ["INDIA", "IN"]

    currency = "INR" if is_indian else "$"
    currency_code = "INR" if is_indian else "USD"

    for inv in invoices:
        data.append({
            "invoice_id": inv.id,
            "payment_id": inv.payment.payment_id,
            "course_id": None,  # Subscriptions aren't tied to a single course
            "date": inv.created_at.isoformat(),
            "created_at": inv.created_at.isoformat(),
            "end_at": inv.subscription.end_date.isoformat(),
            "amount_paid": float(inv.payment.amount_paid or 0),
            "status": "paid",
            "download_url": f"/subscriptions/invoice/{inv.payment.payment_id}/download/",
            "currency": currency,
            "currency_code": currency_code,
            "installment_number": 1,
            "no_of_installments": 1,
            "course": f"Premium Plan: {inv.subscription.plan.plan_type} ({inv.subscription.plan.duration_type})",
        })

    return Response({
        "success": True,
        "data": data
    })



import io
from django.http import HttpResponse, FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_invoice(request, payment_id):
    """!
    @brief Secure file serving endpoint for subscription PDF invoices.
    @details Favoring pre-generated files from the database; falls back to dynamic 
             PDF generation using the shared invoice utility if necessary.

    @param request (Request) DRF Request object.
    @param payment_id (str) Transaction ID to cross-reference the invoice.

    @return FileResponse Serving the invoice PDF stream (200).
    """
    invoice = SubscriptionInvoice.objects.filter(
        subscription__user=request.user,
        payment__payment_id=payment_id
    ).first()

    if not invoice:
        return Response({"success": False, "message": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)

    # If PDF already generated and saved into the DB, return it
    if invoice.invoice:
        try:
            return FileResponse(invoice.invoice.open('rb'), content_type="application/pdf")
        except:
            pass

    # Build PDF dynamically using professional generator
    plan = invoice.subscription.plan
    categories = PlanCategoryAccess.objects.filter(
        plan_type=plan.plan_type
    ).values_list("category", flat=True)

    total_courses = Course.objects.filter(category__in=categories).count()

    # We need the Order object to pass to the generator
    # We can try to find the order associated with this payment
    order = Order.objects.filter(payment=invoice.payment).first()
    if not order:
        # Fallback order-like object if Order record is missing for some reason
        order = SimpleNamespace(
            order_number=invoice.serial_no,
            first_name=request.user.first_name,
            last_name=request.user.last_name,
            email=request.user.email,
            city="",
            state="",
            country=request.user.country or "",
            zipcode="",
            user=request.user,
            total_amount=invoice.payment.amount_paid or 0
        )

    pdf_bytes = generate_professional_invoice(
        order=order, 
        item=invoice.subscription, 
        payment=invoice.payment, 
        invoice_type='subscription'
    )

    return HttpResponse(pdf_bytes, content_type="application/pdf")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def accessed_courses(request):
    """!
    @brief Calculates and returns the specific courses authorized by the user's active plan.
    @details Filters global courses by categories allowed in the current plan and 
             requires the course to be marked as 'featured'.

    @param request (Request) DRF Request object.

    @return Response List of course ID/Title mappings for Authorized UI display (200).
    """
    now = timezone.now()
    subscription = UserSubscription.objects.filter(
        user=request.user,
        is_active=True,
        end_date__gte=now
    ).select_related("plan").order_by("-start_date").first()

    if not subscription:
        return Response({
            "success": False,
            "message": "No active subscription found"
        }, status=status.HTTP_404_NOT_FOUND)

    # Get allowed categories for the plan
    categories = list(
        PlanCategoryAccess.objects.filter(
            plan_type=subscription.plan.plan_type
        ).values_list("category", flat=True)
    )

    # Get featured courses in those categories
    courses = Course.objects.filter(
        category__in=categories,
        is_featured=True
    )

    courses_data = [
        {
            "id": c.id,
            "title": c.title,
            "category": c.category,
        }
        for c in courses
    ]

    return Response({
        "success": True,
        "plan": subscription.plan.plan_type,
        "duration": subscription.plan.duration_type,
        "courses": courses_data
    })