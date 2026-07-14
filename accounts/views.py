"""!
@file accounts/views.py
@brief Views module for account-related operations in the Deepeigen platform.

This module handles user registration, authentication (regular and manual),
account activation, profile management, and dashboard data retrieval.
It integrates with course enrollment and payment systems to provide a
unified student experience.
"""
from django.shortcuts import render, redirect, get_object_or_404
from .forms import UserForm, UserProfileForm
from .models import *
from course.models import *
from customplaylist.models import CustomPlaylist, Invoice as PlaylistInvoice
from subscriptions.models import UserSubscription, PlanCategoryAccess, SubscriptionInvoice
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse,HttpRequest,JsonResponse
from utils.decorators import api_login_required
from datetime import datetime, date,timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from django.db.models import Exists,Count
# Verification email
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
import requests
import json
from django.template import RequestContext
from django import template

from django.db import connection

#### Invoice as pdf 
from django.http import FileResponse

import inflect
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
import io
import reportlab
from django.conf import settings
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from deepeigen import *
from reportlab.lib.units import *
from django.core.files import File as DjangoFile
from django.core.files.base import ContentFile
from django.db.models import Q
from django.db.models import Sum

from course.models import EnrolledUser, Course, Payment, Order
from course.invoice_generator import generate_professional_invoice


# for changing to json output
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from types import SimpleNamespace
from decimal import Decimal
from django.utils.timezone import now
# from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from rest_framework import status
from .utils import get_tokens_for_user




@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """!
    @brief API endpoint for student registration.
    @details Validates input data, creates a new Account and UserProfile,
    and sends a verification email via AWS SES.

    @param request (Request) DRF Request object containing registration data:
        - first_name, last_name, username, email, password,
        - confirm_password, phone_number, profession, country.

    @return Response JSON indicating success (201) or failure (400/500).

    @note This function initiates the email-based account activation flow.
    """
    data = request.data
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    phone_number = data.get('phone_number', '').strip() or None
    profession = data.get('profession', '').strip()
    country = data.get('country', '').strip()

    required_fields = ['first_name', 'last_name', 'username', 'email', 'password', 'confirm_password', 'profession', 'country']
    for field in required_fields:
        val = data.get(field, '').strip()
        if not val:
            return Response({
                'success': False,
                'message': f'{field.replace("_", " ").title()} is required',
                'status': 400
            }, status=status.HTTP_400_BAD_REQUEST)

    if password != confirm_password:
        return Response({
            'success': False,
            'message': 'Password does not match',
            'status': 400
        }, status=status.HTTP_400_BAD_REQUEST)

    if Account.objects.filter(username=username).exists():
        return Response({
            'success': False,
            'message': 'Username already exists',   
            'status': 400
        }, status=status.HTTP_400_BAD_REQUEST)

    if Account.objects.filter(email=email).exists():
        return Response({
            'success': False,
            'message': 'Email already exists',
            'status': 400
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = Account.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password=password,
            phone_number=phone_number,
            profession=profession,
            country=country
        )
        user.save()

        profile = UserProfile()
        profile.user_id = user.id
        profile.profile_picture = 'default/default_user.png'
        profile.save()
        current_site = get_current_site(request)
        mail_subject = 'Please activate your Deep Eigen account'
        email_context = {
            'user': user,
            'domain': current_site,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
        }

        plain_message = render_to_string('accounts/account_verification_email.txt', email_context)
        html_message = render_to_string('accounts/account_verification_email.html', email_context)
        to_email = email
        from_email = settings.EMAIL_HOST_USER
        send_mail(mail_subject, plain_message, from_email, [to_email], html_message=html_message)

        return Response({
            'success': True,
            'message': 'Registration successful. Verification email sent to your email address.',
            'status': 201,
            'user': {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'profession': user.profession,
                'country': user.country,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat()
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            'success': False,
            'message': f'Registration failed: {str(e)}',
            'status': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['POST'])
def register_mannual(request):
    """
    Manual registration view for administrative or internal use.

    Allows creating and immediately activating a user without email verification.

    Args:
        request: HttpRequest object (typically from a form submission).

    Returns:
        HttpResponse: Redirects to registration page or renders the form.

    Side Effects:
        - Creates an active Account and UserProfile in the database.
    """
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
        phone_number = request.POST.get('phone_number')
        profession = request.POST['profession']
        country = request.POST['country']
        
        if password == confirm_password:
            if Account.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists')
                return redirect('manual_registration')
            elif Account.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists') 
                return redirect('manual_registration')
            else:
                user = Account.objects.create_user(first_name=first_name, last_name=last_name,
                                            username=username, email=email, password=password,
                                            phone_number=phone_number, profession=profession,
                                            country=country
                                            )
                user.is_active = True
                user.save()
        else:
            messages.error(request, 'Password do not match')
            return redirect('manual_registration')

        profile = UserProfile()
        profile.user_id = user.id
        profile.profile_picture = 'default/default_user.png'
        profile.save()

        # USER ACTIVATION
        # current_site = get_current_site(request)
        # mail_subject = 'Please activate your Deep Eigen account'
        # data = { 
        #     'user': user,
        #     'domain': current_site,
        #     'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        #     'token': default_token_generator.make_token(user),
        #     }
        # plain_message = render_to_string('accounts/account_verification_email.txt', data)
        # html_message = render_to_string('accounts/account_verification_email.html', data)
        # to_email = email
        # from_email = settings.EMAIL_HOST_USER
        # send_mail(mail_subject, plain_message, from_email, [to_email], html_message=html_message)

        messages.success(request, 'Registration Successfull')
        return redirect('manual_registration')
    return render(request, 'courses/manual_registration.html')


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """!
    @brief API endpoint for user authentication.
    @details Authenticates user credentials and checks for pending course installments
    to notify the student upon login.

    @param request (Request) DRF Request object containing 'email' and 'password'.

    @return Response JSON with access/refresh tokens, user details,
             and any pending payments (200) or error (401/403).
    """
    # try:
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '').strip()

    if not email or not password:
        return Response({
            'success': False,
            'message': 'Email and password are required',
            'status': 400
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(email=email, password=password)

    if user is not None:
        if not user.is_active:
            return Response({
                'success': False,
                'message': 'Account not activated. Please verify your email first.',
                'status': 403
            }, status=status.HTTP_403_FORBIDDEN)

        tokens = get_tokens_for_user(user)

        enrolled_users = EnrolledUser.objects.filter(user=user)
        course_data = []

        if enrolled_users.exists():
            for enrolled_user in enrolled_users:
                course_section = []

                if enrolled_user.no_of_installments > 1:
                    if enrolled_user.no_of_installments == 2:
                        if not enrolled_user.second_installments:
                            course_section.append({
                                'course_name': enrolled_user.course.title,
                                'course_price': round(enrolled_user.course_price/2, 2),
                                'course_id': enrolled_user.course.id,
                                'course_link': enrolled_user.course.url_link_name,
                                'installment': 'Second Installment'
                            })

                    elif enrolled_user.no_of_installments == 3:
                        if not enrolled_user.second_installments:
                            course_section.append({
                                'course_name': enrolled_user.course.title,
                                'course_price': round(enrolled_user.course_price/3, 2),
                                'course_id': enrolled_user.course.id,
                                'course_link': enrolled_user.course.url_link_name,
                                'installment': 'Second Installment'
                            })

                        elif enrolled_user.second_installments and not enrolled_user.third_installments:
                            course_section.append({
                                'course_name': enrolled_user.course.title,
                                'course_price': round(enrolled_user.course_price/3, 2),
                                'course_id': enrolled_user.course.id,
                                'course_link': enrolled_user.course.url_link_name,
                                'installment': 'Third Installment'
                            })

                course_data.extend(course_section)


        return Response({
            'success': True,
            'message': 'Login successful',
            'status': 200,
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'profession': user.profession,
                'country': user.country,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superadmin': user.is_superadmin,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None
            },
            'pending_courses': course_data
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'success': False,
            'message': 'Invalid email or password',
            'status': 401
        }, status=status.HTTP_401_UNAUTHORIZED)







def login_mannual(request):
    """
    Manual login view for staff or administrators.

    Args:
        request: HttpRequest object.

    Returns:
        HttpResponse: Dashboard redirect or rendered theme login page.
    """
    
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']

        user = auth.authenticate(email=email, password=password)

        if user is not None:
            if not (user.is_staff or user.is_superadmin):
                messages.error(request, 'You must be a staff member or super admin to access this page.')
                return redirect('login_mannual')

            auth.login(request, user)
            messages.success(request, 'You are now logged in.')

            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    nextPage = params['next']
                    return redirect(nextPage)
            except:
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid login credentials')
            return redirect('login_mannual')

    return render(request, 'accounts/mannual_login.html')





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """!
    @brief API endpoint to terminate a user session.

    @param request (Request) DRF Request object.

    @return Response JSON success message (200).
    """
   
    
    try:
            user_email = request.user.email if request.user.is_authenticated else None
            
            auth.logout(request)
            
            return Response({
                'success': True,
                'message': 'Logged out successfully',
                'status': 200,
                'user_email': user_email,
                'session_cleared': True
            }, status=status.HTTP_200_OK)

    except Exception as e:
            return Response({
                'success': False,
                'message': f'Logout failed: {str(e)}',
                'status': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['GET'])
@permission_classes([])
def activate(request, uidb64, token):
    """!
    @brief API endpoint for email verification and account activation.

    @param request (Request) HttpRequest object.
    @param uidb64 (str) Base64 encoded user primary key.
    @param token (str) Django password reset token used for verification.

    @return JsonResponse Activation status message and user data (200) or error (400/401).
    """
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist) as e:
        return JsonResponse({
            'success': False,
            'message': 'Invalid or expired activation link',
            'status': 400,
            'error_type': 'invalid_token'
        }, status=400)

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()

        return JsonResponse({
            'success': True,
            'message': 'Congratulations! Your account has been activated successfully.',
            'status': 200,
            'user': {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'profession': user.profession,
                'country': user.country,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat()
            }
        }, status=200)
    else:
        return JsonResponse({
            'success': False,
            'message': 'Invalid or expired activation link. Please request a new verification email.',
            'status': 401,
            'error_type': 'invalid_or_expired_token'
        }, status=401)





def Admin_verify(admin):
    """!
    @brief Helper function determining course accessibility based on user role.

    @param admin (Account) User object to verify permissions for.

    @return list A list containing [accessible_courses_queryset, user_profile_object].
    """

    if admin.is_superadmin:
        courses=Course.objects.all()
        userprofile=Account.objects.get(id=admin.id)
    
    elif not admin.is_superadmin and admin.is_staff:
        ta_admin=TeachingAssistant.objects.filter(email=admin.email)
        courses=ta_admin[0].course_set.all()
        userprofile=Account.objects.get(id=admin.id)
    else:
        userprofile = UserProfile.objects.filter(user_id=admin.id).first()
        now = timezone.now()
        
        enrolled_users = EnrolledUser.objects.filter(user=admin, enrolled=True, end_at__gt=now).order_by('-created_at')
        course_ids = [e.course_id for e in enrolled_users]
        
        active_subscriptions = UserSubscription.objects.filter(
            user=admin,
            is_active=True,
            end_date__gt=now
        ).select_related("plan")
        
        for sub in active_subscriptions:
            allowed_categories = PlanCategoryAccess.objects.filter(
                plan_type=sub.plan.plan_type
            ).values_list("category", flat=True)
            
            sub_courses = Course.objects.filter(category__in=allowed_categories, is_featured=True).values_list("id", flat=True)
            course_ids.extend(list(sub_courses))
            
        # Get unique courses
        courses = Course.objects.filter(id__in=list(set(course_ids)))

    
    return [courses,userprofile]





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """!
    @brief Main API endpoint for the student dashboard.
    @details Retrieves user profile data, subscription status, and details for all
    enrolled courses including progress and validity.

    @param request (Request) DRF Request object.

    @return JsonResponse Comprehensive dashboard data (200) or error (500).
    """



    if request.method == 'GET':
        try:
            now = datetime.now(timezone.utc)

            courses, userprofile = Admin_verify(request.user)
            courses_count = courses.count()

            course_data = request.session.get('course_data', [])

            if 'course_data' in request.session:
                del request.session['course_data']

            if isinstance(userprofile, Account):
                user_data = {
                    'id': userprofile.id,
                    'first_name': userprofile.first_name,
                    'last_name': userprofile.last_name,
                    'username': userprofile.username,
                    'email': userprofile.email,
                    'phone_number': userprofile.phone_number,
                    'profession': userprofile.profession,
                    'country': userprofile.country,
                    'is_active': userprofile.is_active,
                    'is_staff': userprofile.is_staff,
                    'is_superadmin': userprofile.is_superadmin,
                    'date_joined': userprofile.date_joined.isoformat(),
                    'user_type': 'superadmin' if userprofile.is_superadmin else 'staff'
                }
            else:
                user_data = {
                    'id': request.user.id,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                    'username': request.user.username,
                    'email': request.user.email,
                    'phone_number': request.user.phone_number,
                    'profession': request.user.profession,
                    'country': request.user.country,
                    'is_active': request.user.is_active,
                    'is_staff': request.user.is_staff,
                    'is_superadmin': request.user.is_superadmin,
                    'date_joined': request.user.date_joined.isoformat(),
                    'user_type': 'user',
                    'profile': {
                        'address_line_1': userprofile.address_line_1 if userprofile else '',
                        'address_line_2': userprofile.address_line_2 if userprofile else '',
                        'city': userprofile.city if userprofile else '',
                        'state': userprofile.state if userprofile else '',
                        'country': userprofile.country if userprofile else '',
                        'profile_picture': (
                            userprofile.profile_picture.url if (userprofile and userprofile.profile_picture) else None
                        )
                    }
                }

            courses_list = []
            
            from subscriptions.models import UserSubscription, PlanCategoryAccess
            active_subs = UserSubscription.objects.filter(user=request.user, is_active=True, end_date__gt=now)
            user_categories_subs = {}
            for sub in active_subs:
                cats = PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type).values_list('category', flat=True)
                for c in cats:
                    if c not in user_categories_subs or sub.end_date > user_categories_subs[c]:
                        user_categories_subs[c] = sub.end_date

            for course in courses:
                progress = OverallProgress.objects.filter(
                    user=request.user,
                    course=course
                ).first()
                
                completion = float(progress.progress) if progress else 0.0
                
                enrolled_user = EnrolledUser.objects.filter(
                    user=request.user,
                    course=course,
                    enrolled=True
                ).first()
                
                # Calculate validity
                if request.user.is_staff or request.user.is_superadmin:
                    validity = "Lifetime Access"
                elif enrolled_user and enrolled_user.end_at and enrolled_user.end_at > now:
                    days_remaining = (enrolled_user.end_at - now).days
                    validity = f"{days_remaining} days"
                elif course.category in user_categories_subs:
                    sub_end_date = user_categories_subs[course.category]
                    if sub_end_date > now:
                        days_remaining = (sub_end_date - now).days
                        validity = f"{days_remaining} days"
                else:
                    validity = "Expired"
                
                courses_list.append({
                    'id': course.id,
                    'title': course.title,
                    'category': course.category,
                    'url_link_name': course.url_link_name,
                    'description': course.description[:200]
                    if hasattr(course, 'description') else None,
                    'completion': completion,
                    'validity': validity,
                    'course_image': request.build_absolute_uri(course.course_image.url) if course.course_image else None,
                    'assignments': course.assignments if hasattr(course, 'assignments') else 0
                })

            return JsonResponse({
                'success': True,
                'message': 'Dashboard data retrieved successfully',
                'status': 200,
                'user': user_data,
                'courses': {
                    'total_count': courses_count,
                    'courses_list': courses_list
                },
                'pending_payments': course_data,
                'timestamp': now.isoformat()
            }, status=200)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Failed to retrieve dashboard data: {str(e)}',
                'status': 500
            }, status=500)

    elif request.method in ['POST', 'PUT', 'DELETE']:
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a GET request.',
            'status': 405,
            'allowed_methods': ['GET']
        }, status=405)

    else:
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed',
            'status': 405
        }, status=405)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def Payment_due(request):
    """!
    @brief API endpoint to retrieve payment due information for enrolled courses.
    @details Calculates remaining installments and their due dates based on the student's country.

    @param request (Request) DRF Request object.

    @return JsonResponse Payment due data (200).
    """
   
    if request.user.is_staff or request.user.is_superadmin:
        return JsonResponse({
            "success": True,
            "message": "Administrative accounts have no payment dues.",
            "status": 200,
            "data": [],
            "timestamp": timezone.now().isoformat()
        }, status=200)

    now = timezone.now()

    enroll_users = EnrolledUser.objects.filter(
        user=request.user,
        enrolled=True,
        end_at__gt=now
    ).select_related("course").distinct("course")

    response_data = []

    for enroll_user in enroll_users:

        course = enroll_user.course
        
        user_country = getattr(request.user, 'country', '') or ''
        if user_country.lower() == 'india' or user_country.upper() == 'IN':
            total_fee = Decimal(course.indian_fee or 0)
            currency = 'INR'
            currency_code = 'INR'
        else:
            total_fee = Decimal(course.foreign_fee or course.indian_fee or 0)
            currency = '$'
            currency_code = 'USD'
        
        installments = enroll_user.no_of_installments or 1
        per_installment = round(total_fee / installments, 2) if installments > 0 else total_fee
        
        course_duration = course.duration or 6  # Default to 6 months
        second_installment_due_date = enroll_user.created_at + relativedelta(months=max(1, course_duration//3))
        third_installment_due_date = enroll_user.created_at + relativedelta(months=max(1, (2*course_duration)//3))
        second_paid = Decimal(0)
        second_due = Decimal(0)

        if installments >= 2 and not enroll_user.second_installments:
            second_due = per_installment
        elif installments >= 2 and enroll_user.second_installments:
            if enroll_user.installment_id_2:
                payment_2nd = Payment.objects.filter(
                    payment_id=enroll_user.installment_id_2
                ).only("amount_paid").first()
                second_paid = Decimal(payment_2nd.amount_paid) if payment_2nd else per_installment
            else:
                second_paid = per_installment

        third_paid = Decimal(0)
        third_due = Decimal(0)

        if installments == 3 and not enroll_user.third_installments:
            third_due = per_installment
        elif installments == 3 and enroll_user.third_installments:
            if enroll_user.installment_id_3:
                payment_3rd = Payment.objects.filter(
                    payment_id=enroll_user.installment_id_3
                ).only("amount_paid").first()
                third_paid = Decimal(payment_3rd.amount_paid) if payment_3rd else per_installment
            else:
                third_paid = per_installment

        response_data.append({
            "course_id": course.id,
            "course_title": course.title,
            "no_of_installments": installments,
            "currency": currency,
            "currency_code": currency_code,
            "total_fee": float(total_fee),
            "per_installment": float(per_installment),
            "course_duration_months": course_duration,
            "end_at": enroll_user.end_at.isoformat() if enroll_user.end_at else None,
            "second_installment_paid": float(second_paid),
            "second_installment_due": float(second_due),
            "second_installment_due_date": second_installment_due_date.isoformat() if second_due > 0 else None,
            "third_installment_paid": float(third_paid),
            "third_installment_due": float(third_due),
            "third_installment_due_date": third_installment_due_date.isoformat() if third_due > 0 else None,
        })

    return JsonResponse({
        "success": True,
        "message": "Payment due data retrieved successfully",
        "status": 200,
        "data": response_data,
        "timestamp": now.isoformat()
    }, status=200)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def playlists(request):
    """!
    @brief API endpoint to retrieve the student's custom playlists.

    @param request (Request) DRF Request object.

    @return JsonResponse List of playlists with titles and lecture counts (200).
    """

    playlists_list = []
    # Note: Course sections are removed as per user requirement. 
    # Custom playlists are fetched via /customplaylist/my-playlists/ in the frontend.

    pass

    return JsonResponse({
        'success': True,
        'message': 'Playlists retrieved successfully',
        'status': 200,
        'playlists': playlists_list,
        'timestamp': datetime.now().isoformat()
    }, status=200)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def certificates(request):
    """!
    @brief API endpoint to retrieve earned certificates.
    @details A certificate is considered earned if the student has reached 100% completion in a course.

    @param request (Request) DRF Request object.

    @return JsonResponse List of certificate details (200).
    """

    completed_courses = OverallProgress.objects.filter(
        user=request.user,
        progress=100
    ).select_related('course')

    certificates_list = []
    for progress in completed_courses:
        course = progress.course
        certificates_list.append({
            'id': str(progress.id),
            'title': course.title,
            'completionDate': progress.created_at.strftime('%d %B %y'),
            'grade': '100%',
            'image': course.course_image.url if course.course_image else '',
        })

    return JsonResponse({
        'success': True,
        'message': 'Certificates retrieved successfully',
        'status': 200,
        'certificates': certificates_list,
        'timestamp': datetime.now().isoformat()
    }, status=200)



@api_view(['POST'])
@permission_classes([AllowAny])
def forgotPassword(request):
    """!
    @brief API endpoint to initiate the password reset process.
    @details Sends an email with a secure, one-time-use link via AWS SES.

    @param request (Request) DRF Request object containing 'email'.

    @return Response JSON confirming email delivery (200) or error (400/404/500).
    """
    # if request.method == 'POST':
    try:
        # data = request.data
        email = request.data.get('email', '').strip()

        # Validation: Check required field
        if not email:
            return Response({
                'success': False,
                'message': 'Email is required',
                'status': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if account with this email exists
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email__exact=email)

            # Generate password reset token
            current_site = get_current_site(request)
            mail_subject = 'Reset Your Password'
            email_context = {
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            }

            # Send password reset email
            plain_message = render_to_string('accounts/reset_password_email.txt', email_context)
            html_message = render_to_string('accounts/reset_password_email.html', email_context)
            to_email = email
            from_email = settings.EMAIL_HOST_USER
            send_mail(mail_subject, plain_message, from_email, [to_email], html_message=html_message)

            # Return success response
            return Response({
                'success': True,
                'message': 'Password reset email has been sent to your email address. Please check your inbox.',
                'status': 200,
                'email_sent': True,
                'email': email  # For confirmation display
            }, status=status.HTTP_200_OK)
        else:
            # Account doesn't exist
            return Response({
                'success': False,
                'message': 'Account with this email address does not exist.',
                'status': 404,
                'email_found': False
            }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            'success': False,
            'message': f'Failed to send reset email: {str(e)}',
            'status': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def resetpassword_validate(request, uidb64, token):
    """!
    @brief API endpoint to validate a password reset token.

    @param request (Request) HttpRequest object.
    @param uidb64 (str) Base64 encoded user primary key.
    @param token (str) Django password reset token.

    @return JsonResponse Validation status (200) or invalid link error (400/401).
    """
    try:
        # Decode the user ID from the base64 encoded string
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist) as e:
        # Invalid or expired reset link
        return JsonResponse({
            'success': False,
            'message': 'Invalid or expired password reset link',
            'status': 400,
            'error_type': 'invalid_link'
        }, status=400)

    # Verify the token is valid
    if user is not None and default_token_generator.check_token(user, token):
        # Token is valid, store in session for next step
        request.session['uid'] = uid
        
        return JsonResponse({
            'success': True,
            'message': 'Password reset link is valid. You can now reset your password.',
            'status': 200,
            'token_valid': True,
            'uid': uid,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        }, status=200)
    else:
        # Token is invalid or expired
        return JsonResponse({
            'success': False,
            'message': 'This password reset link has expired or is invalid. Please request a new one.',
            'status': 401,
            'error_type': 'expired_token'
        }, status=401)



@api_view(['POST'])
@permission_classes([AllowAny])
def resetPassword(request):
    """!
    @brief API endpoint to finalize the password reset.

    @param request (Request) DRF Request object containing 'password', 'confirm_password', and 'uid'.

    @return Response JSON success message (200) or validation error (400/401/404).
    """
    try:
        data = request.data
        password = data.get('password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        uid = data.get('uid', '').strip()

        # Validation: Check required fields
        if not password or not confirm_password:
            return Response({
                'success': False,
                'message': 'Password and confirm password are required',
                'status': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validation: Passwords match
        if password != confirm_password:
            return Response({
                'success': False,
                'message': 'Passwords do not match',
                'status': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validation: Password length (minimum 6 characters)
        if len(password) < 6:
            return Response({
                'success': False,
                'message': 'Password must be at least 6 characters long',
                'status': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get uid from session or request
        if not uid:
            uid = request.session.get('uid', '')

        if not uid:
            return Response({
                'success': False,
                'message': 'Invalid session. Please request a new password reset link.',
                'status': 401
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Get user and update password
        try:
            user = Account.objects.get(pk=uid)
        except Account.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found',
                'status': 404
            }, status=status.HTTP_404_NOT_FOUND)

        # Set new password
        user.set_password(password)
        user.save()

        # Clear session uid after successful reset
        if 'uid' in request.session:
            del request.session['uid']

        return Response({
            'success': True,
            'message': 'Password has been reset successfully. You can now login with your new password.',
            'status': 200,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'message': f'Password reset failed: {str(e)}',
            'status': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def Admin_courses(admin):
    """!
    @brief Helper function to get all courses accessible to a user.
    @details Logic handles Superadmins (global), Staff (assigned), and Students (enrolled/subscribed).

    @param admin (Account) User instance to check accessibility for.

    @return QuerySet A queryset of Course models.
    """
    if admin.is_superadmin:
        courses=Course.objects.all()
    elif admin.is_staff and not admin.is_superadmin:
        ta_admin=TeachingAssistant.objects.filter(email=admin.email)
        courses=ta_admin[0].course_set.all()
    else:
        now = timezone.now()
        
        # 1. Directly enrolled courses
        enrolled_user=EnrolledUser.objects.filter(user=admin, enrolled=True, end_at__gt=now).order_by('-created_at')
        course_ids = [e.course_id for e in enrolled_user]
        
        # 2. Courses from active subscriptions
        active_subscriptions = UserSubscription.objects.filter(
            user=admin,
            is_active=True,
            end_date__gt=now
        ).select_related("plan")
        
        for sub in active_subscriptions:
            allowed_categories = PlanCategoryAccess.objects.filter(
                plan_type=sub.plan.plan_type
            ).values_list("category", flat=True)
            
            sub_courses = Course.objects.filter(category__in=allowed_categories).values_list("id", flat=True)
            course_ids.extend(list(sub_courses))
            
        # Get unique courses
        courses = Course.objects.filter(id__in=list(set(course_ids)))
        
    return courses
    
    



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mycourses(request):
    """!
    @brief API endpoint to list all courses accessible to the authenticated student.
    @details Handles access via direct enrollment, subscriptions, and roles.
    Includes country-based pricing (INR/USD).

    @param request (Request) DRF Request object.

    @return JsonResponse List of courses with status, pricing, and metadata (200).
    """
    #  AUTHENTICATION GUARD (API-SAFE)

    
    if request.method == 'GET':
        try:
            # Use timezone-aware datetime to avoid comparison errors with end_at field
            now = timezone.now()
            
            # Get courses based on user type
            courses = Admin_courses(request.user)
            courses_count = courses.count()
            
            # Determine user country for currency selection
            user_country = getattr(request.user, 'country', '') or ''
            is_indian_user = user_country.lower() == 'india' or user_country.upper() == 'IN'
            
            # Build courses response with country-based pricing
            courses_list = []
            for course in courses:
                # Check if this course is accessed via subscription vs direct enrollment
                is_sub_course = False
                sub_at_hand = None
                
                # Check direct enrollment first
                is_enrolled = EnrolledUser.objects.filter(
                    user=request.user,
                    course=course,
                    enrolled=True,
                    end_at__gt=now
                ).exists()

                if not is_enrolled:
                    # Check active subscriptions for this category
                    active_sub = UserSubscription.objects.filter(
                        user=request.user,
                        is_active=True,
                        end_date__gt=now
                    ).select_related("plan").order_by('-end_date').first()
                    
                    if active_sub:
                        is_covered = PlanCategoryAccess.objects.filter(
                            plan_type=active_sub.plan.plan_type,
                            category=course.category
                        ).exists()
                        if is_covered:
                            is_sub_course = True
                            sub_at_hand = active_sub

                # Set price and currency based on user's country
                if is_indian_user:
                    if is_sub_course and sub_at_hand:
                        course_price = float(sub_at_hand.plan.indian_price or 0)
                    else:
                        course_price = float(course.indian_fee or 0)
                    course_currency = 'INR'
                    course_currency_code = 'INR'
                else:
                    if is_sub_course and sub_at_hand:
                        course_price = float(sub_at_hand.plan.foreign_price or 0)
                    else:
                        course_price = float(course.foreign_fee or course.indian_fee or 0)
                    course_currency = '$'
                    course_currency_code = 'USD'
                
                course_data = {
                    'id': course.id,
                    'title': course.title,
                    'category': course.category,
                    'url_link_name': course.url_link_name,
                    'description': course.description if hasattr(course, 'description') else None,
                    # Country-based pricing fields
                    'price': course_price,
                    'currency': course_currency,
                    'currency_code': course_currency_code,
                    'is_subscription': is_sub_course,
                    'original_indian_fee': float(course.indian_fee or 0) if hasattr(course, 'indian_fee') else None,
                    'original_foreign_fee': float(course.foreign_fee or 0) if hasattr(course, 'foreign_fee') else None,
                }
                
                # Add additional fields if they exist in the model
                # if hasattr(course, 'price'):
                #     course_data['price'] = course.price

                if hasattr(course, 'duration'):
                    course_data['duration'] = course.duration
                instructor = course.instructor.first()
                if instructor:
                    course_data['instructor'] = instructor.first_name
                else:
                    course_data['instructor'] = None
                if hasattr(course, 'created_at'):
                    course_data['created_at'] = course.created_at.isoformat()
                if hasattr(course, 'updated_at'):
                    course_data['updated_at'] = course.updated_at.isoformat()
                if hasattr(course, 'is_active'):
                    course_data['is_active'] = course.is_active
                if hasattr(course, 'thumbnail'):
                    course_data['thumbnail'] = course.thumbnail.url if course.thumbnail else None
                
                courses_list.append(course_data)
            
            # Determine user type
            user_type = 'user'
            if request.user.is_superadmin:
                user_type = 'superadmin'
            elif request.user.is_staff:
                user_type = 'staff'
            
            return JsonResponse({
                'success': True,
                'message': 'Courses retrieved successfully',
                'status': 200,
                'user_type': user_type,
                'user_country': user_country or 'Not set',
                'pricing_mode': 'INR' if is_indian_user else 'USD',
                'courses': {
                    'total_count': courses_count,
                    'courses_list': courses_list
                },
                'timestamp': datetime.now().isoformat()
            }, status=200)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Failed to retrieve courses: {str(e)}',
                'status': 500
            }, status=500)

    elif request.method in ['POST', 'PUT', 'DELETE']:
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a GET request.',
            'status': 405,
            'allowed_methods': ['GET']
        }, status=405)

    else:
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed',
            'status': 405
        }, status=405)
  

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    """!
    @brief API endpoint to retrieve the authenticated user's full profile.
    @details Merges Account (auth) and UserProfile (extended) data.

    @param request (Request) DRF Request object.

    @return JsonResponse Complete profile data object (200).
    """

    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed',
            'status': 405,
            'allowed_methods': ['GET']
        }, status=405)

    user = request.user
    
    # Safely get or create user profile to avoid 404 if it's missing
    userprofile, created = UserProfile.objects.get_or_create(user=user)
    
    if created:
        # Set default profile picture if just created
        userprofile.profile_picture = 'default/default_user.png'
        userprofile.save()

    profile_data = {
        # Account fields
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'name': f"{user.first_name} {user.last_name}",
        'username': user.username,
        'email': user.email,
        'phone': user.phone_number,
        'profession': user.profession,
        'country': user.country,
        'is_active': user.is_active,
        'created_at': user.date_joined.isoformat(),

        # UserProfile fields
        'address': {
            'address_line_1': userprofile.address_line_1,
            'address_line_2': userprofile.address_line_2,
            'city': userprofile.city,
            'state': userprofile.state,
            'country': userprofile.country,
            'postal_code': userprofile.postal_code,
        },
        'profile_picture': (
            userprofile.profile_picture.url
            if userprofile.profile_picture
            else None
        )
    }

    return JsonResponse({
        'success': True,
        'status': 200,
        'data': profile_data
    }, status=200)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def edit_profile(request):
    """!
    @brief API endpoint to update user profile information.
    @details Handles base Account fields and UserProfile address fields.

    @param request (Request) DRF Request object with JSON or Multipart data.

    @return JsonResponse Updated profile data (200) or error message (400).
    """

    try:
        import json
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse(
            {"success": False, "message": "Invalid JSON"},
            status=400
        )


    try:
        user = request.user
        userprofile, created = UserProfile.objects.get_or_create(user=user)

        if "first_name" in data:
            user.first_name = data["first_name"].strip()

        if "last_name" in data:
            user.last_name = data["last_name"].strip()

        if "phone_number" in data:
            user.phone_number = data["phone_number"].strip()

        if "profession" in data:
            user.profession = data["profession"].strip()

        if "country" in data:
            user.country = data["country"].strip()

        user.save()

        userprofile.address_line_1 = data.get("address_line_1", userprofile.address_line_1)
        userprofile.address_line_2 = data.get("address_line_2", userprofile.address_line_2)
        userprofile.city = data.get("city", userprofile.city)
        userprofile.state = data.get("state", userprofile.state)
        userprofile.country = data.get("country", userprofile.country)
        userprofile.postal_code = data.get("postal_code", userprofile.postal_code)

        userprofile.save()

        return JsonResponse({
            "success": True,
            "message": "Profile updated successfully",
            "data": {
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "profession": user.profession,
                    "country": user.country,
                },
                "profile": {
                    "address_line_1": userprofile.address_line_1,
                    "address_line_2": userprofile.address_line_2,
                    "city": userprofile.city,
                    "state": userprofile.state,
                    "country": userprofile.country,
                    "postal_code": userprofile.postal_code,
                    "profile_picture": (
                        userprofile.profile_picture.url
                        if userprofile.profile_picture else None
                    ),
                },
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Failed to update profile: {str(e)}",
        }, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """!
    @brief API endpoint to upload or update the user's profile picture.

    @param request (Request) DRF Request object containing 'profile_picture' in FILES.

    @return JsonResponse URL of the uploaded picture (200).
    @note Deletes the old profile picture from storage if it wasn't a default image.
    """

    try:
        userprofile, created = UserProfile.objects.get_or_create(user=request.user)

        if 'profile_picture' not in request.FILES:
            return JsonResponse({
                'success': False,
                'message': 'No profile picture uploaded',
                'status': 400
            }, status=400)

        profile_picture = request.FILES['profile_picture']

        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if profile_picture.content_type not in allowed_types:
            return JsonResponse({
                'success': False,
                'message': 'Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.',
                'status': 400
            }, status=400)

        max_size = 5 * 1024 * 1024  # 5MB
        if profile_picture.size > max_size:
            return JsonResponse({
                'success': False,
                'message': 'File too large. Maximum size is 5MB.',
                'status': 400
            }, status=400)

        if userprofile.profile_picture:
            old_picture = userprofile.profile_picture.path
            if hasattr(userprofile.profile_picture, 'name') and 'default' not in userprofile.profile_picture.name:
                try:
                    import os
                    if os.path.exists(old_picture):
                        os.remove(old_picture)
                except Exception:
                    pass  # Ignore errors deleting old picture

        userprofile.profile_picture = profile_picture
        userprofile.save()

        return JsonResponse({
            "success": True,
            "message": "Profile picture uploaded successfully",
            "status": 200,
            "data": {
                "profile_picture": userprofile.profile_picture.url if userprofile.profile_picture else None
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Failed to upload profile picture: {str(e)}",
            'status': 500
        }, status=500)







@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """!
    @brief API endpoint to change the authenticated user's password.
    @details Validates current password, new password complexity, and confirmation match.

    @param request (Request) DRF Request object containing 'current_password',
        'new_password', and 'confirm_password'.

    @return JsonResponse Success message (200) or validation error (400/401).
    @note Requires the user to log in again after a successful password change.
    """
    if request.method == 'POST':
        try:
            import json
            
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                current_password = data.get('current_password', '').strip()
                new_password = data.get('new_password', '').strip()
                confirm_password = data.get('confirm_password', '').strip()
            else:
                current_password = request.POST.get('current_password', '').strip()
                new_password = request.POST.get('new_password', '').strip()
                confirm_password = request.POST.get('confirm_password', '').strip()

            if not current_password or not new_password or not confirm_password:
                return JsonResponse({
                    'success': False,
                    'message': 'Current password, new password, and confirm password are required',
                    'status': 400
                }, status=400)

            if new_password != confirm_password:
                return JsonResponse({
                    'success': False,
                    'message': 'New password and confirm password do not match',
                    'status': 400
                }, status=400)

            if len(new_password) < 6:
                return JsonResponse({
                    'success': False,
                    'message': 'New password must be at least 6 characters long',
                    'status': 400
                }, status=400)

            if current_password == new_password:
                return JsonResponse({
                    'success': False,
                    'message': 'New password cannot be the same as current password',
                    'status': 400
                }, status=400)

            user = Account.objects.get(username__exact=request.user.username)

            password_valid = user.check_password(current_password)
            if not password_valid:
                return JsonResponse({
                    'success': False,
                    'message': 'Current password is incorrect',
                    'status': 401
                }, status=401)

            user.set_password(new_password)
            user.save()

            return JsonResponse({
                'success': True,
                'message': 'Password changed successfully. Please login again with your new password.',
                'status': 200,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'password_changed_at': datetime.now().isoformat()
                },
                'action': 'login_required' 
            }, status=200)

        except Account.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User not found',
                'status': 404
            }, status=404)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Failed to change password: {str(e)}',
                'status': 500
            }, status=500)

    elif request.method == 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a POST request.',
            'status': 405,
            'allowed_methods': ['POST']
        }, status=405)

    else:
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed',
            'status': 405
        }, status=405)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def enrollment_debug(request):
    """!
    @brief Detailed debug endpoint for user enrollment and payment state.
    @details Analyzes inconsistencies between Orders, Payments, and EnrolledUser records.

    @param request (Request) DRF Request object.

    @return JsonResponse Comprehensive diagnostic data (200).
    @note This is a temporary debug endpoint and should be restricted or removed in production.
    """
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a GET request.',
            'status': 405,
            'allowed_methods': ['GET']
        }, status=405)

    try:
        user = request.user
        now = timezone.now()
        
        debug_info = {
            'user_info': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superadmin': user.is_superadmin,
                'country': user.country,
                'courses_enrolled_count': getattr(user, 'courses_enrolled', 0),
            },
            'current_time': now.isoformat(),
            'timezone_info': {
                'using': 'django.utils.timezone.now',
                'is_aware': True
            },
            'analysis': {}
        }
        
        all_enrolled = EnrolledUser.objects.filter(user=user).order_by('-created_at')
        
        enrolled_data = []
        valid_enrolled = []
        expired_enrolled = []
        
        for enroll in all_enrolled:
            is_valid = enroll.enrolled and enroll.end_at > now
            
            enroll_info = {
                'id': enroll.id,
                'course_id': enroll.course.id if enroll.course else None,
                'course_title': str(enroll.course) if enroll.course else 'UNKNOWN',
                'enrolled': enroll.enrolled,
                'end_at': enroll.end_at.isoformat() if enroll.end_at else None,
                'is_valid_now': is_valid,
                'days_remaining': (enroll.end_at - now).days if enroll.end_at and is_valid else None,
                'no_of_installments': enroll.no_of_installments,
                'first_installments': enroll.first_installments,
                'second_installments': enroll.second_installments,
                'third_installments': enroll.third_installments,
                'created_at': enroll.created_at.isoformat() if enroll.created_at else None,
            }
            
            enrolled_data.append(enroll_info)
            
            if is_valid:
                valid_enrolled.append(enroll_info)
            else:
                expired_enrolled.append(enroll_info)
        
        debug_info['enrolled_users'] = {
            'total_count': all_enrolled.count(),
            'valid_count': len(valid_enrolled),
            'expired_or_invalid_count': len(expired_enrolled),
            'valid_enrollments': valid_enrolled,
            'expired_enrollments': expired_enrolled
        }
        
        orders = Order.objects.filter(user=user).order_by('-created_at')
        
        order_data = []
        completed_orders = []
        pending_orders = []
        
        for order in orders:
            order_info = {
                'id': order.id,
                'order_number': order.order_number,
                'course_id': order.course.id if order.course else None,
                'course_title': str(order.course) if order.course else 'UNKNOWN',
                'total_amount': order.total_amount,
                'is_ordered': order.is_ordered,
                'status': order.status,
                'created_at': order.created_at.isoformat() if order.created_at else None,
            }
            
            order_data.append(order_info)
            
            if order.is_ordered:
                completed_orders.append(order_info)
            else:
                pending_orders.append(order_info)
        
        debug_info['orders'] = {
            'total_count': orders.count(),
            'completed_count': len(completed_orders),
            'pending_count': len(pending_orders),
            'completed_orders': completed_orders,
            'pending_orders': pending_orders
        }
        
        payments = Payment.objects.filter(user=user).order_by('-created_at')
        
        payment_data = []
        completed_payments = []
        
        for payment in payments:
            payment_info = {
                'id': payment.id,
                'payment_id': payment.payment_id,
                'amount_paid': payment.amount_paid,
                'status': payment.status,
                'payment_method': payment.payment_method,
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
            }
            
            payment_data.append(payment_info)
            
            if payment.status == 'Completed':
                completed_payments.append(payment_info)
        
        debug_info['payments'] = {
            'total_count': payments.count(),
            'completed_count': len(completed_payments),
            'completed_payments': completed_payments
        }
        
        issues = []
        
        order_course_ids = set(o['course_id'] for o in completed_orders if o['course_id'])
        enrolled_course_ids = set(e['course_id'] for e in valid_enrolled if e['course_id'])
        
        missing_enrollments = order_course_ids - enrolled_course_ids
        if missing_enrollments:
            issues.append({
                'type': 'COMPLETED_ORDERS_WITHOUT_VALID_ENROLLMENT',
                'description': 'Orders exist but no valid enrollment record found',
                'course_ids': list(missing_enrollments),
                'severity': 'HIGH'
            })
        
        orphaned_enrollments = enrolled_course_ids - order_course_ids
        if orphaned_enrollments:
            issues.append({
                'type': 'VALID_ENROLLMENTS_WITHOUT_ORDERS',
                'description': 'Valid enrollment exists but no order found',
                'course_ids': list(orphaned_enrollments),
                'severity': 'MEDIUM'
            })
        
        if expired_enrolled:
            issues.append({
                'type': 'EXPIRED_ENROLLMENTS',
                'description': 'Some enrollments have expired',
                'count': len(expired_enrolled),
                'severity': 'LOW'
            })
        
        actual_count = len(valid_enrolled)
        stored_count = getattr(user, 'courses_enrolled', 0)
        if actual_count != stored_count:
            issues.append({
                'type': 'COUNT_MISMATCH',
                'description': 'User.courses_enrolled does not match actual valid enrollment count',
                'stored_count': stored_count,
                'actual_count': actual_count,
                'severity': 'LOW'
            })
        
        debug_info['analysis'] = {
            'issues_found': len(issues),
            'issues': issues,
            'summary': {
                'total_orders': orders.count(),
                'total_payments': payments.count(),
                'total_enrollments': all_enrolled.count(),
                'valid_enrollments': len(valid_enrolled),
                'user_stored_course_count': stored_count
            }
        }
        
        if user.is_superadmin:
            courses_qs = Course.objects.all()
            visible_courses_count = courses_qs.count()
        elif user.is_staff:
            ta_admin = TeachingAssistant.objects.filter(email=user.email)
            if ta_admin.exists():
                courses_qs = ta_admin[0].course_set.all()
                visible_courses_count = courses_qs.count()
            else:
                courses_qs = Course.objects.none()
                visible_courses_count = 0
        else:
            courses_qs = Course.objects.filter(
                id__in=[e['course_id'] for e in valid_enrolled if e['course_id']]
            )
            visible_courses_count = courses_qs.count()
        
        debug_info['mycourses_simulation'] = {
            'user_type': 'superadmin' if user.is_superadmin else ('staff' if user.is_staff else 'regular_user'),
            'courses_visible_to_user': visible_courses_count,
            'note': 'Regular users only see courses with valid (non-expired) enrollments'
        }
        
        recommendations = []
        
        if missing_enrollments:
            recommendations.append({
                'issue': 'Missing enrollment records',
                'action': 'Create EnrolledUser records for completed orders',
                'api': '/courses/place_order_mannualy/'
            })
        
        if orphaned_enrollments:
            recommendations.append({
                'issue': 'Orphaned enrollments',
                'action': 'Verify these enrollments are intentional or create orders',
            })
        
        if expired_enrolled:
            recommendations.append({
                'issue': 'Expired enrollments',
                'action': 'Extend end_at date if payments were completed',
            })
        
        debug_info['recommendations'] = recommendations
        
        return JsonResponse({
            'success': True,
            'message': 'Debug enrollment data retrieved successfully',
            'status': 200,
            'debug': debug_info,
            'note': 'This is a temporary debug endpoint. Remove after fixing issues.',
            'timestamp': now.isoformat()
        }, status=200)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Debug failed: {str(e)}',
            'status': 500,
            'error_type': type(e).__name__
        }, status=500)




def generate_invoice_for_payment(payment_id, course_id, order_id, installment_number=None):
    """!
    @brief Internal helper function to trigger invoice generation and email notification.

    @param payment_id (str) The unique transaction ID from Razorpay/PayU.
    @param course_id (int) ID of the course purchased.
    @param order_id (int) ID of the associated Order record.
    @param installment_number (int, optional) The installment sequence (1, 2, or 3).

    @return bool True if the notification email was sent successfully.
    """
    try:
        from django.template.loader import render_to_string
        from django.core.mail import EmailMessage
        from course.models import Order, Course
        from django.conf import settings
        
        order = Order.objects.filter(id=order_id).first()
        if not order:
            return False
        
        payment = Payment.objects.filter(payment_id=payment_id).first()
        if not payment:
            return False
        
        enrollment = EnrolledUser.objects.filter(user=order.user, course_id=course_id).first()
        if not enrollment:
            return False
        
        installment_text = "Payment Received"
        if installment_number:
            if installment_number == 1:
                installment_text = f"First installment paid (1 of {enrollment.no_of_installments})"
            elif installment_number == 2:
                installment_text = f"Second installment paid (2 of {enrollment.no_of_installments})"
            elif installment_number == 3:
                installment_text = f"Final installment paid ({enrollment.no_of_installments} of {enrollment.no_of_installments})"
        
        course = Course.objects.filter(id=course_id).first()
        course_name = course.title if course else "Unknown Course"
        
        mail_list = ['sunil.roat@deepeigen.com']
        
        title_heading = "Payment Received" if installment_number and installment_number > 1 else "New User Enrollment"
        top_heading = f"A user has successfully paid for {course_name}." if installment_number and installment_number > 1 else f"A new user has enrolled in {course_name}."
        
        mail_subject = f"Invoice Generated - {course_name} - Payment {installment_number or 1}"
        
        message = render_to_string('invoice/invoice_mail.html', {
            'title_heading': title_heading,
            'top_heading': top_heading,
            'firstname': order.first_name,
            'lastname': order.last_name,
            'course': course_name,
            'orderid': payment_id,
            'installment_info': installment_text
        })
        
        email = EmailMessage(mail_subject, message, settings.EMAIL_HOST_USER, mail_list)
        email.content_subtype = "html"
        email.send()
        
        return True
        
    except Exception:
        return False



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_history(request, course_id):
    """!
    @brief API endpoint to retrieve detailed payment history for a specific course or playlist.

    @param request (Request) DRF Request object.
    @param course_id (int) The ID of the course or playlist.

    @return JsonResponse Detailed payment records and invoice URLs (200).
    """
    is_playlist = request.query_params.get('is_playlist') == 'true'

    try:
        from course.models import Course, EnrolledUser, Payment
        from customplaylist.models import CustomPlaylist, Invoice as PlaylistInvoice

        if is_playlist:
            playlist = CustomPlaylist.objects.filter(id=course_id, user=request.user).first()
            if not playlist:
                return JsonResponse({"success": False, "message": "Playlist not found"}, status=404)

            user_country = (getattr(request.user, 'country', '') or '').upper()
            currency = "INR" if user_country in ["INDIA", "IN"] else "$"
            currency_code = "INR" if user_country in ["INDIA", "IN"] else "USD"
            total_fee = float(playlist.total_price)

            payment_list = []
            
            invoices = PlaylistInvoice.objects.filter(user=request.user, playlist=playlist).order_by('date')
            
            if invoices.exists():
                for idx, inv in enumerate(invoices):
                    payment_list.append({
                        "invoice_id": inv.id,
                        "order_id": playlist.order_id,
                        "payment_id": inv.payment_id,
                        "payment_method": "payment",
                        "currency": currency,
                        "currency_code": currency_code,
                        "status": "completed",
                        "installment_number": idx + 1,
                        "no_of_installments": invoices.count(),
                        "download_url": f"/accounts/invoice/playlist/{inv.payment_id}/{playlist.id}/",
                        "amount": float(inv.amount) / invoices.count() if invoices.count() > 0 else 0,
                        "paid_at": inv.date.isoformat() if inv.date else None
                    })
            elif playlist.is_purchased:
                payment_list.append({
                    "invoice_id": f"P-{playlist.id}",
                    "order_id": playlist.order_id,
                    "payment_id": playlist.payment_id or "N/A",
                    "payment_method": "payment",
                    "currency": currency,
                    "currency_code": currency_code,
                    "status": "completed",
                    "installment_number": 1,
                    "no_of_installments": 1,
                    "download_url": f"/accounts/invoice/playlist/{playlist.payment_id}/{playlist.id}/" if playlist.payment_id else "#",
                    "amount": total_fee,
                    "paid_at": playlist.created_at.isoformat() if playlist.created_at else None
                })

            return JsonResponse({
                "success": True,
                "data": {
                    "course_id": course_id,
                    "course_name": playlist.title,
                    "total_fee": total_fee,
                    "total_paid": total_fee if playlist.is_purchased else 0,
                    "remaining_due": 0 if playlist.is_purchased else total_fee,
                    "currency": currency,
                    "currency_code": currency_code,
                    "no_of_installments": max(1, invoices.count()),
                    "payments": payment_list,
                    "is_playlist": True
                }
            })

        course = Course.objects.filter(id=course_id).first()
        if not course:
            return JsonResponse({"success": False}, status=404)

        enrollment = EnrolledUser.objects.filter(
            user=request.user,
            course=course,
            enrolled=True
        ).first()

        if not enrollment:
            now = timezone.now()
            active_subscriptions = UserSubscription.objects.filter(
                user=request.user,
                is_active=True,
                end_date__gt=now
            ).select_related("plan")
            
            valid_sub = None
            for sub in active_subscriptions:
                is_covered = PlanCategoryAccess.objects.filter(
                    plan_type=sub.plan.plan_type,
                    category=course.category
                ).exists()
                if is_covered:
                    valid_sub = sub
                    break
            
            if not valid_sub:
                return JsonResponse({"success": False, "message": "No active enrollment or subscription found"}, status=200)

            user_country = (getattr(request.user, 'country', '') or '').upper()
            is_indian = user_country in ["INDIA", "IN"]
            currency = "INR" if is_indian else "$"
            currency_code = "INR" if is_indian else "USD"
            
            total_fee = valid_sub.plan.indian_price if is_indian else valid_sub.plan.foreign_price
            
            payment_list = []
            if valid_sub.payment:
                payment_list.append({
                    "invoice_id": 1,
                    "order_id": f"SUB-{valid_sub.id}",
                    "payment_id": valid_sub.payment.payment_id,
                    "payment_method": valid_sub.payment.payment_method or "razorpay",
                    "currency": currency,
                    "currency_code": currency_code,
                    "status": "completed",
                    "installment_number": 1,
                    "no_of_installments": 1,
                    "download_url": f"/subscriptions/invoice/{valid_sub.payment.payment_id}/download/",
                    "amount": float(valid_sub.payment.amount_paid or total_fee),
                    "paid_at": valid_sub.payment.created_at.isoformat() if valid_sub.payment.created_at else valid_sub.created_at.isoformat()
                })
            
            return JsonResponse({
                "success": True,
                "data": {
                    "course_id": course_id,
                    "course_name": f"{course.title} (Subscription: {valid_sub.plan.plan_type})",
                    "total_fee": float(total_fee),
                    "total_paid": float(valid_sub.payment.amount_paid or total_fee) if valid_sub.payment else 0,
                    "remaining_due": 0,
                    "currency": currency,
                    "currency_code": currency_code,
                    "no_of_installments": 1,
                    "payments": payment_list,
                    "is_subscription": True
                }
            })

        user_country = (getattr(request.user, 'country', '') or '').upper()
        payments = []

        if user_country in ["INDIA", "IN"]:
            currency = "INR"
            currency_code = "INR"
            total_fee = enrollment.course.indian_fee or 0
        else:
            currency = "$"
            currency_code = "USD"
            total_fee = enrollment.course.foreign_fee or enrollment.course.indian_fee or 0


        if enrollment.payment and enrollment.payment.status.capitalize() == "Completed":
            payments.append(enrollment.payment)

        if enrollment.installment_id_2:
            p2 = Payment.objects.filter(
                user=request.user,
                payment_id=enrollment.installment_id_2,
                status__iexact="Completed"
            ).first()
            if p2:
                payments.append(p2)

        if enrollment.installment_id_3:
            p3 = Payment.objects.filter(
                user=request.user,
                payment_id=enrollment.installment_id_3,
                status__iexact="Completed"
            ).first()
            if p3:
                payments.append(p3)

        payment_list = []
        total_paid = 0

        if payments:
            for idx, payment in enumerate(payments):
                if enrollment.payment and enrollment.payment.id == payment.id:
                    installment_num = 1
                elif enrollment.installment_id_2 == payment.payment_id:
                    installment_num = 2
                elif enrollment.installment_id_3 == payment.payment_id:
                    installment_num = 3
                else:
                    installment_num = idx + 1

                payment_amount = float(payment.amount_paid or 0)
                total_paid += payment_amount

                order = enrollment.order
                order_number = order.order_number if order else "None"
                order_id = order.id if order else None

                payment_list.append({
                    "invoice_id": idx + 1,
                    "order_id": order_id,
                    "payment_id": payment.payment_id,
                    "payment_method": payment.payment_method or "unknown",
                    "currency": currency,
                    "currency_code": currency_code,
                    "status": payment.status.lower() if payment.status else "pending",
                    "installment_number": installment_num,
                    "no_of_installments": enrollment.no_of_installments,
                    "download_url": f"/accounts/invoice/{payment.payment_id}/{course_id}/{order_number}/",
                    "amount": payment_amount,
                    "paid_at": payment.created_at.isoformat() if payment.created_at else None
                })
        elif enrollment.enrolled:
            payment_list.append({
                "invoice_id": 1,
                "order_id": enrollment.order.id if enrollment.order else None,
                "payment_id": enrollment.payment.payment_id if enrollment.payment else "Manual",
                "payment_method": "enrollment",
                "currency": currency,
                "currency_code": currency_code,
                "status": "completed",
                "installment_number": 1,
                "no_of_installments": enrollment.no_of_installments or 1,
                "download_url": f"/accounts/invoice/{enrollment.payment.payment_id}/{course_id}/{enrollment.order.order_number}/" if enrollment.payment and enrollment.order else "#",
                "amount": float(total_fee),
                "paid_at": enrollment.created_at.isoformat() if enrollment.created_at else None
            })
            total_paid = float(total_fee)

        payment_list.sort(key=lambda x: x["installment_number"])
        remaining_due = round(float(total_fee) - total_paid, 2)
        if remaining_due < 0.05:
            remaining_due = 0

        return JsonResponse({
            "success": True,
            "data": {
                "course_id": course_id,
                "course_name": course.title,
                "total_fee": float(total_fee),
                "total_paid": total_paid,
                "remaining_due": max(0, remaining_due),
                "currency": currency,
                "currency_code": currency_code,
                "no_of_installments": enrollment.no_of_installments,
                "payments": payment_list
            }
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)
    

#added 13 feb 26 vikas
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_watch(request):
    """!
    @brief API endpoint for user's most recently watched video OR last accessed course.
    @details Returns video details with course/section info, or fallbacks to session data.

    @param request (Request) DRF Request object.

    @return JsonResponse Recent watch data (200).
    """
    # if not request.user.is_authenticated:
    #     return JsonResponse({
    #         'success': False,
    #         'message': 'Authentication required',
    #         'status': 403
    #     }, status=403)

    # if request.method != 'GET':
    #     return JsonResponse({
    #         'success': False,
    #         'message': 'Method not allowed. Please send a GET request.',
    #         'status': 405
    #     }, status=405)

    recent_progress = UserVideoProgress.objects.filter(
        user=request.user
    ).select_related('video', 'course', 'section').order_by('-created_at').first()

    if recent_progress:
        video = recent_progress.video
        course = recent_progress.course
        section = recent_progress.section

        module = video.module if video else None
        module_name = module.title if module and hasattr(module, 'title') else module.name if module and hasattr(module, 'name') else ''

        recent_watch_data = {
            'id': recent_progress.id,
            'video_id': video.id if video else None,
            'video_title': video.title if video else '',
            'video_link': video.link if video else '',
            'video_duration': video.duration if video else '',
            'course_id': course.id if course else None,
            'course_title': course.title if course else '',
            'course_url': course.url_link_name if course else '',
            'section_id': section.id if section else None,
            'section_title': section.title if section else section.name if section else '',
            'section_url': section.url_name if section else '',
            'module_name': module_name,
            'completed': recent_progress.completed,
            'watched_at': recent_progress.created_at.isoformat() if recent_progress.created_at else None,
        }

        return JsonResponse({
            'success': True,
            'message': 'Recent watch data retrieved successfully',
            'status': 200,
            'recent_watch': recent_watch_data,
            'timestamp': datetime.now().isoformat()
        }, status=200)

    last_accessed_course_id = request.session.get('last_accessed_course_id')
    last_accessed_course_title = request.session.get('last_accessed_course_title')
    last_accessed_course_url = request.session.get('last_accessed_course_url')
    last_accessed_at = request.session.get('last_accessed_at')

    if last_accessed_course_id:
        recent_watch_data = {
            'id': None,
            'video_id': None,
            'video_title': None,
            'video_link': None,
            'video_duration': None,
            'course_id': last_accessed_course_id,
            'course_title': last_accessed_course_title,
            'course_url': last_accessed_course_url,
            'section_id': None,
            'section_title': None,
            'section_url': 'overview',
            'module_name': None,
            'completed': False,
            'watched_at': last_accessed_at,
        }

        return JsonResponse({
            'success': True,
            'message': 'Last accessed course retrieved from session',
            'status': 200,
            'recent_watch': recent_watch_data,
            'timestamp': datetime.now().isoformat()
        }, status=200)

    return JsonResponse({
        'success': True,
        'message': 'No recent watch history found',
        'status': 200,
        'recent_watch': None,
        'timestamp': datetime.now().isoformat()
    }, status=200)





#added 13 feb vikas
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_last_accessed_course(request):
    """!
    @brief API endpoint to track the last accessed course in the user's session.

    @param request (Request) DRF Request object containing 'course_id'.

    @return Response Success message (200).
    """
    # if not request.user.is_authenticated:
    #     return JsonResponse({
    #         'success': False,
    #         'message': 'Authentication required',
    #         'status': 403
    #     }, status=403)

    # if request.method != 'POST':
    #     return JsonResponse({
    #         'success': False,
    #         'message': 'Method not allowed. Please send a POST request.',
    #         'status': 405
    #     }, status=405)

    try:
        import json
        data = json.loads(request.body)
        
        course_id = data.get('course_id')
        
        if not course_id:
            return JsonResponse({
                'success': False,
                'message': 'course_id is required',
                'status': 400
            }, status=400)
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Course not found',
                'status': 404
            }, status=404)
        
        request.session['last_accessed_course_id'] = course_id
        request.session['last_accessed_course_title'] = course.title
        request.session['last_accessed_course_url'] = course.url_link_name
        request.session['last_accessed_at'] = datetime.now().isoformat()
        
        return Response({
            'success': True,
            'message': 'Last accessed course updated',
            'status': 200,
            'data': {
                'course_id': course.id,
                'course_title': course.title,
                'course_url': course.url_link_name,
            },
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error tracking course: {str(e)}',
            'status': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def Invoice_section(request):
    """!
    @brief API endpoint to retrieve all invoices (courses, playlists, subscriptions) for the user.

    @param request (Request) DRF Request object.

    @return JsonResponse List of all paid invoices (200).
    """

    enrollments = EnrolledUser.objects.filter(
        user=request.user,
        enrolled=True
    ).select_related("course", "payment")

    data = []

    user_country = (getattr(request.user, "country", "") or "").upper()
    is_indian = user_country in ["INDIA", "IN"]

    currency = "INR" if is_indian else "$"
    currency_code = "INR" if is_indian else "USD"

    for enroll in enrollments:

        payment_ids = []

        if enroll.payment:
            payment_ids.append(enroll.payment.payment_id)

        if enroll.installment_id_2:
            payment_ids.append(enroll.installment_id_2)

        if enroll.installment_id_3:
            payment_ids.append(enroll.installment_id_3)

        payments = Payment.objects.filter(
            payment_id__in=payment_ids,
            status="Completed"
        ).order_by("-created_at")

        for payment in payments:

            if enroll.payment and enroll.payment.payment_id == payment.payment_id:
                installment_number = 1
            elif enroll.installment_id_2 == payment.payment_id:
                installment_number = 2
            elif enroll.installment_id_3 == payment.payment_id:
                installment_number = 3
            else:
                installment_number = 1

            data.append({
                "invoice_id": payment.id,
                "payment_id": payment.payment_id,
                "order_id": enroll.order.razorpay_order_id if enroll.order else None, # Added for frontend status checks
                "course_id": enroll.course.id,
                "date": payment.created_at.isoformat(),
                "created_at": payment.created_at.isoformat(),
                "end_at": enroll.end_at.isoformat() if getattr(enroll, 'end_at', None) else None,
                "amount_paid": float(payment.amount_paid or 0),
                "status": "paid",
                "download_url": f"/accounts/invoice/{payment.payment_id}/{enroll.course.id}/None/",
                "currency": currency,
                "currency_code": currency_code,
                "installment_number": installment_number,
                "no_of_installments": enroll.no_of_installments,
                "course": enroll.course.title,
            })

    from customplaylist.models import CustomPlaylist, Invoice as PlaylistInvoice
    
    purchased_playlists = CustomPlaylist.objects.filter(
        user=request.user,
        is_purchased=True
    )
    
    for pl in purchased_playlists:
        if pl.payment_id:
            PlaylistInvoice.objects.get_or_create(
                playlist=pl,
                payment_id=pl.payment_id,
                defaults={
                    'user': request.user,
                    'playlist_name': pl.title,
                    'amount': pl.total_price,
                    'purchase_type': "Custom Playlist"
                }
            )

    # 2. Now fetch all invoice records for this user
    playlist_invoices = PlaylistInvoice.objects.filter(
        user=request.user
    ).select_related("playlist")

    for p_inv in playlist_invoices:
        data.append({
            "invoice_id": p_inv.id,
            "payment_id": p_inv.payment_id,
            "order_id": p_inv.playlist.order_id if p_inv.playlist else None,
            "playlist_id": p_inv.playlist.id if p_inv.playlist else None,
            "date": p_inv.date.isoformat(),
            "created_at": p_inv.date.isoformat(),
            "end_at": p_inv.playlist.end_date.isoformat() if p_inv.playlist else None,
            "amount_paid": float(p_inv.amount or 0),
            "status": "paid",
            "download_url": f"/accounts/invoice/playlist/{p_inv.payment_id}/{p_inv.playlist_id if hasattr(p_inv, 'playlist_id') else p_inv.playlist.id}/",
            "currency": currency,
            "currency_code": currency_code,
            "course": p_inv.playlist_name,
            "is_playlist": True
        })

    # - Add Subscription Invoices
    subscription_invoices = SubscriptionInvoice.objects.filter(
        subscription__user=request.user,
        payment__status="Completed"
    ).select_related("subscription", "payment", "subscription__plan")

    for s_inv in subscription_invoices:
        data.append({
            "invoice_id": s_inv.id,
            "payment_id": s_inv.payment.payment_id,
            "order_id": f"SUB-{s_inv.subscription.id}", # Subscriptions might not have a razorpay_order_id in Order model if it was a deduction, using unique string
            "subscription_id": s_inv.subscription.id,
            "date": s_inv.created_at.isoformat(),
            "created_at": s_inv.created_at.isoformat(),
            "end_at": s_inv.subscription.end_date.isoformat(),
            "amount_paid": float(s_inv.payment.amount_paid or 0),
            "status": "paid",
            "download_url": f"/subscriptions/invoice/{s_inv.payment.payment_id}/download/",
            "currency": currency,
            "currency_code": currency_code,
            "course": f"Subscription: {s_inv.subscription.plan.plan_type} ({s_inv.subscription.plan.duration_type})",
            "is_subscription": True
        })

    return JsonResponse({
        "success": True,
        "data": data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def invoice_status(request, order_id):
    """!
    @brief Check if an invoice is ready for download based on order/payment status.

    @param request (Request) DRF Request object.
    @param order_id (str) The external order ID (Razorpay/Sub/Playlist).

    @return JsonResponse Readiness status and download availability (200).
    """
    from customplaylist.models import CustomPlaylist
    
    # Check regular course orders first
    order = Order.objects.filter(razorpay_order_id=order_id).first()
    if order:
        is_completed = order.status == 'Completed'
        return JsonResponse({
            "success": True,
            "can_download": is_completed,
            "invoice_status": "completed" if is_completed else "pending_payment"
        })
    
    # Check custom playlist orders
    playlist = CustomPlaylist.objects.filter(order_id=order_id, user=request.user).first()
    if playlist:
        return JsonResponse({
            "success": True,
            "can_download": True,
            "invoice_status": "completed"
        })
    
    # Check subscription invoices
    if str(order_id).startswith("SUB-"):
        try:
            sub_id = int(order_id.replace("SUB-", ""))
            sub_exists = UserSubscription.objects.filter(id=sub_id, user=request.user, is_active=True).exists()
            if sub_exists:
                return JsonResponse({
                    "success": True,
                    "can_download": True,
                    "invoice_status": "completed"
                })
        except ValueError:
            pass

    return JsonResponse({
        "success": False,
        "can_download": False,
        "message": "Invoice not found or order not completed",
        "invoice_status": "not_found"
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def Invoice(request, payment_id, course_id, orderNumber):
    """!
    @brief API endpoint to generate or serve a cached PDF invoice for a course enrollment.

    @param request (Request) DRF Request object.
    @param payment_id (str) Transaction ID.
    @param course_id (int) Course ID.
    @param orderNumber (str) Unique order reference.

    @return HttpResponse PDF content or FileResponse for cached file.
    """

    # if not request.user.is_authenticated:
    #     return JsonResponse({"success": False}, status=403)

    # Get enrollment
    enrollment = EnrolledUser.objects.filter(
        user=request.user,
        course_id=course_id,
        enrolled=True
    ).first()

    if not enrollment:
        return JsonResponse({"success": False, "message": "Enrollment not found"}, status=404)

    # Get payment
    payment = Payment.objects.filter(
        user=request.user,
        payment_id=payment_id,
        status="Completed"
    ).first()

    if not payment:
        return JsonResponse({"success": False, "message": "Payment not found"}, status=404)

    # Detect installment number
    if enrollment.payment and enrollment.payment.payment_id == payment.payment_id:
        installment_number = 1
    elif enrollment.installment_id_2 == payment.payment_id:
        installment_number = 2
    elif enrollment.installment_id_3 == payment.payment_id:
        installment_number = 3
    else:
        installment_number = 1

  
    order = Order.objects.filter(
        payment__payment_id=payment_id,
        user=request.user
    ).first()
    
    if not order:
        order = enrollment.order

    from course.models import Invoice_Registrant
    invoice_reg = Invoice_Registrant.objects.filter(
        name=enrollment,
        order=order
    ).first()

    if invoice_reg and invoice_reg.invoice:
        try:
            return FileResponse(invoice_reg.invoice.open('rb'), content_type="application/pdf")
        except Exception:
            pass

    user_country = (getattr(request.user, "country", "") or "").upper()
    is_indian = user_country in ["INDIA", "IN"]

    pdf_content = generate_professional_invoice(order=order, item=enrollment, payment=payment, installment_number=installment_number, invoice_type='course')
    from django.core.files.base import ContentFile
    if not invoice_reg:
        invoice_reg = Invoice_Registrant.objects.create(name=enrollment, order=order)
    
    invoice_filename = f"Invoice_{order.order_number}_{payment.payment_id}.pdf"
    invoice_reg.invoice.save(invoice_filename, ContentFile(pdf_content), save=True)

    return HttpResponse(pdf_content, content_type="application/pdf")




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def playlist_invoice_view(request, payment_id, playlist_id):
    """!
    @brief Generate or retrieve professional PDF invoice for a custom playlist.

    @param request (Request) DRF Request object.
    @param payment_id (str) Transaction ID.
    @param playlist_id (int) Playlist ID.

    @return HttpResponse PDF content or FileResponse for cached file.
    """
    from customplaylist.models import CustomPlaylist, Invoice as PlaylistInvoice
    playlist = get_object_or_404(CustomPlaylist, id=playlist_id, user=request.user)
    
    p_invoice, created = PlaylistInvoice.objects.get_or_create(
        playlist=playlist,
        payment_id=payment_id,
        defaults={
            'user': request.user,
            'playlist_name': playlist.title,
            'amount': playlist.total_price,
            'purchase_type': "Custom Playlist"
        }
    )

    if p_invoice.invoice_file:
        try:
            return FileResponse(p_invoice.invoice_file.open('rb'), content_type="application/pdf")
        except Exception:
            pass

    try:
        payment = Payment.objects.filter(payment_id=payment_id).first()
        order = Order.objects.filter(payment=payment).first()

        pdf_content = generate_professional_invoice(
            order=order,
            item=playlist,
            payment=payment,
            invoice_type='playlist'
        )
        filename = f"Invoice_{playlist.id}_{payment_id[-6:]}.pdf"
        
        p_invoice.invoice_file.save(filename, ContentFile(pdf_content), save=True)
        
        return HttpResponse(pdf_content, content_type="application/pdf")

    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error generating invoice: {str(e)}"}, status=500)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
@staff_member_required
def Invoice_manual(request, userId, payment_id, course_id, orderNumber):
    """!
    @brief Administrative endpoint to generate invoices for other users.

    @param request (Request) DRF Request object.
    @param userId (str) ID of the target user.
    @param payment_id (str) Transaction ID.
    @param course_id (int) Course ID.
    @param orderNumber (str) Order reference.

    @return HttpResponse PDF content.
    """

    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"success": False}, status=403)

    from django.contrib.auth import get_user_model
    User = get_user_model()

    user = User.objects.filter(id=userId).first()
    if not user:
        return JsonResponse({"success": False}, status=404)

    enroll = EnrolledUser.objects.filter(
        user=user,
        course=course_id
    ).first()

    if not enroll:
        return JsonResponse({"success": False}, status=404)

    payment = Payment.objects.filter(
        user=user,
        payment_id=payment_id
    ).first()

    if not payment or payment.status != "Completed":
        return JsonResponse({"success": False}, status=400)

    request.user = user
    return Invoice(request, payment_id, course_id, orderNumber)
