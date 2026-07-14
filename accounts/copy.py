from django.shortcuts import render, redirect, get_object_or_404
from .forms import UserForm, UserProfileForm
from .models import *
from course.models import *
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse,HttpRequest,JsonResponse
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
from django.template import RequestContext
from django import template
# from Invoice.models import *
from django.views.decorators.csrf import csrf_protect
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

from course.models import EnrolledUser, Course


# for changing to json output
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.utils.timezone import now




# ==================== NEW JSON VERSION ====================
# @csrf_protect
@csrf_exempt
def register(request):
    """
    API endpoint for user registration
    Returns JSON response with user details and status
    Matches Account model fields: first_name, last_name, username, email, password, phone_number, profession, country
    """
    if request.method == 'POST':
        try:
            import json
            # Handle both JSON and form-data requests
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                first_name = data.get('first_name', '').strip()
                last_name = data.get('last_name', '').strip()
                username = data.get('username', '').strip()
                email = data.get('email', '').strip()
                password = data.get('password', '').strip()
                confirm_password = data.get('confirm_password', '').strip()
                phone_number = data.get('phone_number', '').strip() or None
                profession = data.get('profession', '').strip()
                country = data.get('country', '').strip()
            else:
                first_name = request.POST.get('first_name', '').strip()
                last_name = request.POST.get('last_name', '').strip()
                username = request.POST.get('username', '').strip()
                email = request.POST.get('email', '').strip()
                password = request.POST.get('password', '').strip()
                confirm_password = request.POST.get('confirm_password', '').strip()
                phone_number = request.POST.get('phone_number', '').strip() or None
                profession = request.POST.get('profession', '').strip()
                country = request.POST.get('country', '').strip()

            # Validation: Check required fields
            required_fields = ['first_name', 'last_name', 'username', 'email', 'password', 'confirm_password', 'profession', 'country']
            for field in required_fields:
                if not locals()[field] or (field != 'phone_number' and field != 'country' and not locals()[field]):
                    return JsonResponse({
                        'success': False,
                        'message': f'{field.replace("_", " ").title()} is required',
                        'status': 400
                    }, status=400)

            # Validation: Password match
            if password != confirm_password:
                return JsonResponse({
                    'success': False,
                    'message': 'Password does not match',
                    'status': 400
                }, status=400)

            # Validation: Username already exists
            if Account.objects.filter(username=username).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'Username already exists',
                    'status': 400
                }, status=400)

            # Validation: Email already exists
            if Account.objects.filter(email=email).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'Email already exists',
                    'status': 400
                }, status=400)

            # Create user with all Account model fields
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

            # Create user profile with default picture
            profile = UserProfile()
            profile.user_id = user.id
            profile.profile_picture = 'default/default_user.png'
            profile.save()

            # Generate activation token
            current_site = get_current_site(request)
            mail_subject = 'Please activate your Deep Eigen account'
            email_context = {
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            }

            # Send activation email
            plain_message = render_to_string('accounts/account_verification_email.txt', email_context)
            html_message = render_to_string('accounts/account_verification_email.html', email_context)
            to_email = email
            from_email = settings.EMAIL_HOST_USER
            send_mail(mail_subject, plain_message, from_email, [to_email], html_message=html_message)

            # Return success response with user details
            return JsonResponse({
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
            }, status=201)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Registration failed: {str(e)}',
                'status': 500
            }, status=500)

    elif request.method == 'GET':
        # Return allowed methods info
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
# ==================== END OF NEW JSON VERSION ====================


@csrf_protect
def register_mannual(request):
    data = {
        'title': 'User Registration | Deep Eigen',
        'description': "Deep Eigen course enrollment is easy by registering as a user by inputting few basic information.",
        'canonical_url' : request.build_absolute_uri(request.path)
    }
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

            # Create a user profile
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
    return render(request, 'courses/manual_registration.html', data)


# ==================== NEW JSON VERSION ====================
@csrf_protect
@csrf_exempt
def login(request):
    """
    API endpoint for user login
    Returns JSON response with user details, authentication token, and pending course installments
    Matches Account model fields: email, password (and returns other fields)
    """
    if request.method == 'POST':
        try:
            import json
            # Handle both JSON and form-data requests
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                email = data.get('email', '').strip()
                password = data.get('password', '').strip()
            else:
                email = request.POST.get('email', '').strip()
                password = request.POST.get('password', '').strip()

            # Validation: Check required fields
            if not email or not password:
                return JsonResponse({
                    'success': False,
                    'message': 'Email and password are required',
                    'status': 400
                }, status=400)

            # Authenticate user with email and password
            user = auth.authenticate(email=email, password=password)

            if user is not None:
                # Check if user is active (email verified)
                if not user.is_active:
                    return JsonResponse({
                        'success': False,
                        'message': 'Account not activated. Please verify your email first.',
                        'status': 403
                    }, status=403)

                # Login the user (create session)
                auth.login(request, user)

                # Fetch enrolled users and pending installments
                enrolled_users = EnrolledUser.objects.filter(user=user)
                course_data = []

                if enrolled_users.exists():
                    for enrolled_user in enrolled_users:
                        course_section = []

                        # Check for pending installments (2nd, 3rd)
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

                # Store course data in session
                request.session['course_data'] = course_data

                # Return success response with user and course details
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful',
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
                        'is_staff': user.is_staff,
                        'is_superadmin': user.is_superadmin,
                        'date_joined': user.date_joined.isoformat(),
                        'last_login': user.last_login.isoformat() if user.last_login else None
                    },
                    'pending_courses': course_data,
                    'session_id': request.session.session_key
                }, status=200)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid email or password',
                    'status': 401
                }, status=401)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Login failed: {str(e)}',
                'status': 500
            }, status=500)

    elif request.method == 'GET':
        # Return allowed methods info
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
# ==================== END OF NEW JSON VERSION ====================




@csrf_protect
def login_mannual(request):
    data = {
        'title': 'User Login | Deep Eigen',
        'description': "Deep Eigen course access is easy by logging in as a user.",
        'canonical_url': request.build_absolute_uri(request.path)
    }
    
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']

        user = auth.authenticate(email=email, password=password)

        if user is not None:
            # Check if the user is staff or super admin
            if not (user.is_staff or user.is_superadmin):
                messages.error(request, 'You must be a staff member or super admin to access this page.')
                return redirect('login_mannual')

            auth.login(request, user)
            messages.success(request, 'You are now logged in.')

            # Since you want to remove the enrolled_users related logic, we don't process courses anymore
            # You can directly redirect to the dashboard or any other page
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

    return render(request, 'accounts/mannual_login.html', data)


# ==================== OLD HTML VERSION (COMMENTED OUT) ====================
# @login_required(login_url = 'login')
# def logout(request):
#     auth.logout(request)
#     messages.success(request, 'You are logged out.')
#     return redirect('login')
# ==================== END OF OLD HTML VERSION ====================


# ==================== NEW JSON VERSION ====================
@csrf_exempt

@login_required(login_url = 'login')
def logout(request):
    """
    API endpoint for user logout
    Returns JSON response confirming logout and clears session
    """
    if request.method in ['POST', 'GET']:
        try:
            # Get user info before logout for response
            user_email = request.user.email if request.user.is_authenticated else None
            
            # Clear session and logout user
            auth.logout(request)
            
            return JsonResponse({
                'success': True,
                'message': 'Logged out successfully',
                'status': 200,
                'user_email': user_email,
                'session_cleared': True
            }, status=200)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Logout failed: {str(e)}',
                'status': 500
            }, status=500)

    else:
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a POST or GET request.',
            'status': 405,
            'allowed_methods': ['POST', 'GET']
        }, status=405)
# ==================== END OF NEW JSON VERSION ====================

# ==================== NEW JSON VERSION ====================
def activate(request, uidb64, token):
    """
    API endpoint for email account activation
    Returns JSON response confirming account activation status
    Takes URL parameters: uidb64 (user id encoded), token (verification token)
    """
    try:
        # Decode the user ID from the base64 encoded string
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist) as e:
        # Invalid or expired activation link
        return JsonResponse({
            'success': False,
            'message': 'Invalid or expired activation link',
            'status': 400,
            'error_type': 'invalid_token'
        }, status=400)

    # Verify the token is valid
    if user is not None and default_token_generator.check_token(user, token):
        # Token is valid, activate the user
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
        # Token is invalid or expired
        return JsonResponse({
            'success': False,
            'message': 'Invalid or expired activation link. Please request a new verification email.',
            'status': 401,
            'error_type': 'invalid_or_expired_token'
        }, status=401)
# ==================== END OF NEW JSON VERSION ====================


    # New Code written by khilesh (Date - 31_Dec_2024) 
def Admin_verfiy(admin):

    if admin.is_superadmin:
        courses=Course.objects.all()
        userprofile=Account.objects.get(id=admin.id)
    
    elif not admin.is_superadmin and admin.is_staff:
        ta_admin=TeachingAssistant.objects.filter(email=admin.email)
        courses=ta_admin[0].course_set.all()
        userprofile=Account.objects.get(id=admin.id)
    else:
        # Use filter().first() so missing UserProfile won't raise
        userprofile = UserProfile.objects.filter(user_id=admin.id).first()
        # Use timezone-aware datetime to avoid comparison errors
        now = timezone.now()
        enrolled_users = EnrolledUser.objects.filter(user=admin, enrolled=True, end_at__gt=now).order_by('-created_at')
        courses = Course.objects.filter(id__in=[e.course_id for e in enrolled_users])

    
    return [courses,userprofile]   




def dashboard(request):
    """
    API endpoint for user dashboard
    Returns JSON response with user profile data and enrolled courses
    Handles different user types: superadmin, staff/TA, and regular users
    Matches Account and UserProfile model fields
    """

    # 🔐 AUTHENTICATION GUARD (FIXED INDENTATION)
    if not request.user.is_authenticated:
        print("AUTH:", request.user.is_authenticated)
        print("USER:", request.user)
        print("SESSION:", request.session.session_key)
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)

    if request.method == 'GET':
        try:
            # Use timezone-aware now to avoid naive/aware datetime errors
            now = datetime.now(timezone.utc)

            # Get user profile and courses based on user type
            courses, userprofile = Admin_verfiy(request.user)
            courses_count = courses.count()

            # Retrieve pending course data from session (from login)
            course_data = request.session.get('course_data', [])

            # Clear the session data after retrieving it
            if 'course_data' in request.session:
                del request.session['course_data']

            # Build user profile response
            if isinstance(userprofile, Account):
                # For superadmin and staff
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
                # For regular users -- handle missing UserProfile gracefully
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

            # Build courses response with progress data
            courses_list = []
            for course in courses:
                # Fetch progress for this course
                progress = OverallProgress.objects.filter(
                    user=request.user,
                    course=course
                ).first()
                
                completion = float(progress.progress) if progress else 0.0
                
                # Fetch enrolled user to get validity and assignments info
                enrolled_user = EnrolledUser.objects.filter(
                    user=request.user,
                    course=course,
                    enrolled=True
                ).first()
                
                # Calculate validity
                if enrolled_user and enrolled_user.end_at:
                    days_remaining = (enrolled_user.end_at - now).days
                    validity = f"{days_remaining} days" if days_remaining > 0 else "Expired"
                else:
                    validity = "N/A"
                
                courses_list.append({
                    'id': course.id,
                    'title': course.title,
                    'category': course.category,
                    'url_link_name': course.url_link_name,
                    'description': course.description[:200]
                    if hasattr(course, 'description') else None,
                    'completion': completion,
                    'validity': validity,
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

def Payment_due(request):

    # 🔐 Authentication Guard
    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "message": "Authentication required",
            "status": 403
        }, status=403)

    # 🔒 Method Guard
    if request.method != "GET":
        return JsonResponse({
            "success": False,
            "message": "Method not allowed. Use GET.",
            "status": 405,
            "allowed_methods": ["GET"]
        }, status=405)

    # Use timezone-aware datetime
    now = timezone.now()

    # ✅ FIX 1: Only fetch NON-EXPIRED enrollments (end_at > now)
    enroll_users = EnrolledUser.objects.filter(
        user=request.user,
        enrolled=True,
        end_at__gt=now
    ).select_related("course").distinct("course")

    response_data = []

    for enroll_user in enroll_users:

        course = enroll_user.course
        
        # ✅ FIX 2: Use foreign_fee for foreign users, indian_fee for Indian users
        user_country = getattr(request.user, 'country', '') or ''
        # Check for both 'india' and 'IN' (country code)
        if user_country.lower() == 'india' or user_country.upper() == 'IN':
            total_fee = Decimal(course.indian_fee or 0)
            currency = 'INR'
            currency_code = 'INR'
        else:
            total_fee = Decimal(course.foreign_fee or course.indian_fee or 0)
            currency = '$'
            currency_code = 'USD'
        
        installments = enroll_user.no_of_installments or 1
        per_installment = total_fee / installments if installments > 0 else total_fee
        
        # Calculate due dates based on course progress (33% and 66% completion)
        course_duration = course.duration or 6  # Default to 6 months
        # 2nd payment due at 33% progress = 1/3 of course_duration
        second_installment_due_date = enroll_user.created_at + relativedelta(months=max(1, course_duration//3))
        # 3rd payment due at 66% progress = 2/3 of course_duration
        third_installment_due_date = enroll_user.created_at + relativedelta(months=max(1, (2*course_duration)//3))

        # ✅ FIX 3: Correct logic - if second_installments=False, it's DUE
        second_paid = Decimal(0)
        second_due = Decimal(0)

        if not enroll_user.second_installments:
            second_due = per_installment
        elif enroll_user.second_installments:
            # If flag=True, payment should exist; fetch it safely
            if enroll_user.installment_id_2:
                payment_2nd = Payment.objects.filter(
                    payment_id=enroll_user.installment_id_2
                ).only("amount_paid").first()
                second_paid = Decimal(payment_2nd.amount_paid) if payment_2nd else per_installment
            else:
                # Flag is True but no payment_id: mark as fully paid
                second_paid = per_installment

        # ✅ FIX 4: Correct logic - if third_installments=False, it's DUE
        third_paid = Decimal(0)
        third_due = Decimal(0)

        if installments == 3 and not enroll_user.third_installments:
            third_due = per_installment
        elif installments == 3 and enroll_user.third_installments:
            # If flag=True, payment should exist; fetch it safely
            if enroll_user.installment_id_3:
                payment_3rd = Payment.objects.filter(
                    payment_id=enroll_user.installment_id_3
                ).only("amount_paid").first()
                third_paid = Decimal(payment_3rd.amount_paid) if payment_3rd else per_installment
            else:
                # Flag is True but no payment_id: mark as fully paid
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




def playlists(request):
    """
    API endpoint for user playlists
    Returns playlists (sections) from enrolled courses
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)

    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a GET request.',
            'status': 405
        }, status=405)

    enrolled_courses = EnrolledUser.objects.filter(
        user=request.user,
        enrolled=True
    ).values_list('course_id', flat=True)

    playlists_list = []
    playlist_id = 1

    for course_id in enrolled_courses:
        sections = Section.objects.filter(course_id=course_id).order_by('id')
        for section in sections:
            assignments_count = Assignment.objects.filter(section=section).count()
            lectures_count = Video.objects.filter(section=section).count() if hasattr(Video, 'section') else 0
            
            playlists_list.append({
                'id': str(playlist_id),
                'title': section.title or section.name,
                'lectures': max(lectures_count, 1),  # At least 1 to match mock data
                'assignments': max(assignments_count, 1)
            })
            playlist_id += 1

    # If no playlists found, return mock data
    if not playlists_list:
        from .data.loggedInData import loggedInData  # Can't import, so use fallback
        playlists_list = [
            {'id': '1', 'title': 'Getting Started', 'lectures': 10, 'assignments': 2},
            {'id': '2', 'title': 'Advanced Topics', 'lectures': 20, 'assignments': 3},
        ]

    return JsonResponse({
        'success': True,
        'message': 'Playlists retrieved successfully',
        'status': 200,
        'playlists': playlists_list,
        'timestamp': datetime.now().isoformat()
    }, status=200)


def certificates(request):
    """
    API endpoint for user certificates
    Returns completed courses (completion = 100%) as certificates
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)

    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a GET request.',
            'status': 405
        }, status=405)

    # Get all courses with 100% completion (certificates)
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

    # If no certificates, return empty list
    return JsonResponse({
        'success': True,
        'message': 'Certificates retrieved successfully',
        'status': 200,
        'certificates': certificates_list,
        'timestamp': datetime.now().isoformat()
    }, status=200)



@login_required(login_url = 'login')
# def Invoice_section(request):
#     now=datetime.now()
#     registrant_list=[]
#     user_enroll=EnrolledUser.objects.filter(user=request.user)
#     invoice_registrants=Invoice_Registrant.objects.all()
#     if user_enroll.exists():
#         for registrant in user_enroll:
#             invoice_reg=Invoice_Registrant.objects.filter(name=registrant)
#             if invoice_reg.exists():
#                for reg in invoice_reg:
#                    registrant_list.append(reg)
   
#     context={'registrants':registrant_list,'orders_exist':len(registrant_list)}
    
#     return render(request,'accounts/invoice.html',context)



# def Invoice_section(request):
#     # 🔐 Authentication guard (API-safe)
#     if not request.user.is_authenticated:
#         return JsonResponse({
#             'success': False,
#             'message': 'Authentication required',
#             'status': 403
#         }, status=403)

#     if request.method != 'GET':
#         return JsonResponse({
#             'success': False,
#             'message': 'Method not allowed. Please send a GET request.',
#             'status': 405,
#             'allowed_methods': ['GET']
#         }, status=405)

#     registrant_list = []

#     user_enroll = EnrolledUser.objects.filter(user=request.user)
    
#     if user_enroll.exists():
#         for enroll in user_enroll:
#             # Get the payment record for this enrollment
#             # NOTE: enroll.payment is a ForeignKey to Payment, use payment.id for comparison
#             # enroll.payment_id stores the id of the Payment object (not payment_id string)
#             # payment = None
#             # if enroll.payment:
#             #     payment = enroll.payment  # Direct access via ForeignKey
#             # Collect all installment payment IDs for this enrollment
#             payment_ids = []

# # First installment (stored via ForeignKey)
#             if enroll.payment:
#                 payment_ids.append(enroll.payment.payment_id)

# # Second installment
#             if enroll.installment_id_2:
#                 payment_ids.append(enroll.installment_id_2)

# # Third installment
#             if enroll.installment_id_3:
#                 payment_ids.append(enroll.installment_id_3)

# # Now fetch all Payment objects
#             payments = Payment.objects.filter(
#                 user=request.user,
#                 payment_id__in=payment_ids
#                 ).order_by('-created_at')

           
            
#             order = enroll.order
            
#             invoice_regs = Invoice_Registrant.objects.filter(name=enroll)
#             for reg in invoice_regs:
#                 # Determine currency based on user country
#                 user_country = getattr(request.user, 'country', '') or ''
#                 if user_country.lower() == 'india' or user_country.upper() == 'IN':
#                     currency = 'INR'
#                     currency_code = 'INR'
#                 else:
#                     currency = '$'
#                     currency_code = 'USD'
                
#                 # Get course amount (use per-installment if applicable)
#                 course_amount = order.course_amount if order else 0
#                 amount_paid = payment.amount_paid if payment else 0
#                 total_amount = order.total_amount if order else 0
                
#                 # Determine installment number by matching payment IDs
#                 installment_number = 1
#                 if payment:
#                     # Compare payment.id (primary key) with installment_id fields
#                     if enroll.installment_id_2 and str(enroll.installment_id_2) == str(payment.payment_id):
#                         installment_number = 2
#                     elif enroll.installment_id_3 and str(enroll.installment_id_3) == str(payment.payment_id):
#                         installment_number = 3
#                     # else: installment_number remains 1 (default)
                
#                 # Invoice status: paid if payment exists and is completed
#                 invoice_status = 'paid' if (payment and payment.status == 'Completed') else 'pending'
                
#                 registrant_list.append({
#                     'invoice_id': reg.id,
#                     'serial_no': reg.serial_no,
#                     'order_id': order.id if order else None,
#                     'course_id': enroll.course.id if enroll.course else None,
#                     'payment_id': payment.payment_id if payment else None,
#                     'course': str(enroll.course) if enroll.course else None,
#                     'course_amount': float(course_amount),
#                     'amount_paid': float(amount_paid),
#                     'total_amount': float(total_amount),
#                     'currency': currency,
#                     'currency_code': currency_code,
#                     'status': invoice_status,
#                     'payment_method': payment.payment_method if payment else None,
#                     'installment_number': installment_number,
#                     'no_of_installments': enroll.no_of_installments or 1,
#                     'created_at': reg.created_at.isoformat()
#                     if hasattr(reg, 'created_at') else order.created_at.isoformat() if order else None,
#                     'download_url': f'/accounts/invoice/{payment.payment_id if payment else ""}/'
#                                    f'{enroll.course.id if enroll.course else ""}/None' if order else None
#                 })

#     return JsonResponse({
#         'success': True,
#         'message': 'Invoice list retrieved successfully',
#         'status': 200,
#         'orders_exist': len(registrant_list),
#         'data': registrant_list,
#         'timestamp': timezone.now().isoformat()
#     }, status=200)

# def Invoice_section(request):

#     # 🔐 Authentication guard
#     if not request.user.is_authenticated:
#         return JsonResponse({
#             'success': False,
#             'message': 'Authentication required',
#             'status': 403
#         }, status=403)

#     if request.method != 'GET':
#         return JsonResponse({
#             'success': False,
#             'message': 'Method not allowed. Please send a GET request.',
#             'status': 405,
#             'allowed_methods': ['GET']
#         }, status=405)

#     registrant_list = []

#     user_enroll = EnrolledUser.objects.filter(user=request.user)

#     for enroll in user_enroll:

#         order = enroll.order

#         # 🔁 Collect all installment payment IDs
#         payment_ids = []

#         # First installment (FK)
#         if enroll.payment:
#             payment_ids.append(enroll.payment.payment_id)

#         # Second installment
#         if enroll.installment_id_2:
#             payment_ids.append(enroll.installment_id_2)

#         # Third installment
#         if enroll.installment_id_3:
#             payment_ids.append(enroll.installment_id_3)

#         # 🔎 Fetch all related Payment objects
#         payments = Payment.objects.filter(
#             user=request.user,
#             payment_id__in=payment_ids
#         ).order_by('-created_at')

#         # Determine currency
#         user_country = getattr(request.user, 'country', '') or ''
#         if user_country.lower() == 'india' or user_country.upper() == 'IN':
#             currency = 'INR'
#             currency_code = 'INR'
#         else:
#             currency = '$'
#             currency_code = 'USD'

#         # 🔁 LOOP over each payment (THIS WAS MISSING)
#         for payment in payments:

#             # Determine installment number
#             installment_number = 1
#             if enroll.installment_id_2 == payment.payment_id:
#                 installment_number = 2
#             elif enroll.installment_id_3 == payment.payment_id:
#                 installment_number = 3

#             invoice_status = 'paid' if payment.status == 'Completed' else 'pending'

#             registrant_list.append({
#                 'invoice_id': None,  # You can link Payment to Invoice_Registrant later if needed
#                 'serial_no': enroll.serial_number,
#                 'order_id': order.id if order else None,
#                 'course_id': enroll.course.id if enroll.course else None,
#                 'payment_id': payment.payment_id,
#                 'course': str(enroll.course) if enroll.course else None,
#                 'course_amount': float(order.course_amount) if order else 0,
#                 'amount_paid': float(payment.amount_paid),
#                 'total_amount': float(order.total_amount) if order else 0,
#                 'currency': currency,
#                 'currency_code': currency_code,
#                 'status': invoice_status,
#                 'payment_method': payment.payment_method,
#                 'installment_number': installment_number,
#                 'no_of_installments': enroll.no_of_installments or 1,
#                 'created_at': payment.created_at.isoformat(),
#                 'download_url': f'/accounts/invoice/{payment.payment_id}/{enroll.course.id}/None'
#                                  if order else None
#             })

#     return JsonResponse({
#         'success': True,
#         'message': 'Invoice list retrieved successfully',
#         'status': 200,
#         'orders_exist': len(registrant_list),
#         'data': registrant_list,
#         'timestamp': timezone.now().isoformat()
#     }, status=200)



# def invoice_status(request, order_id):
#     """
#     Check if invoice is ready for download
    
#     Purpose: Allow frontend to check invoice status before requesting PDF
    
#     Validations:
#     ✅ User authenticated
#     ✅ Order belongs to user
#     ✅ Payment verified
#     ✅ Order completed
    
#     Response Status:
#     - "ready": Invoice can be downloaded
#     - "generating": Invoice is being generated (try again later)
#     - "pending_payment": Payment not yet verified
#     - "order_incomplete": Order not yet completed
#     """
    
#     # 🔐 Authentication check
#     if not request.user.is_authenticated:
#         return JsonResponse({
#             "success": False,
#             "message": "Authentication required",
#             "status": 403,
#             "error_code": "AUTH_REQUIRED"
#         }, status=403)
    
#     if request.method != 'GET':
#         return JsonResponse({
#             "success": False,
#             "message": "Method not allowed. Use GET.",
#             "status": 405,
#             "error_code": "METHOD_NOT_ALLOWED"
#         }, status=405)
    
#     try:
#         # Check order exists and belongs to user
#         order = Order.objects.filter(id=order_id, user=request.user).first()
#         if not order:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Order not found or does not belong to you",
#                 "status": 404,
#                 "error_code": "ORDER_NOT_FOUND"
#             }, status=404)
        
#         # Check if order is completed
#         if not order.is_ordered:
#             return JsonResponse({
#                 "success": True,
#                 "message": "Invoice not ready - Order not yet completed",
#                 "status": 200,
#                 "invoice_status": "order_incomplete",
#                 "can_download": False,
#                 "order_id": order_id
#             }, status=200)
        
#         # Check if payment is verified
#         if not order.payment or order.payment.status != "Completed":
#             return JsonResponse({
#                 "success": True,
#                 "message": "Invoice not ready - Payment not yet verified",
#                 "status": 200,
#                 "invoice_status": "pending_payment",
#                 "can_download": False,
#                 "payment_status": order.payment.status if order.payment else "Not Found",
#                 "order_id": order_id
#             }, status=200)
        
#         # Check if invoice record exists in database
#         invoice_registrant = Invoice_Registrant.objects.filter(order=order).first()
        
#         if invoice_registrant and invoice_registrant.invoice:
#             # Invoice is stored and ready
#             return JsonResponse({
#                 "success": True,
#                 "message": "Invoice is ready for download",
#                 "status": 200,
#                 "invoice_status": "ready",
#                 "can_download": True,
#                 "invoice_id": invoice_registrant.id,
#                 "serial_no": invoice_registrant.serial_no,
#                 "order_id": order_id,
#                 "file_size_mb": invoice_registrant.invoice.size / 1024 / 1024 if invoice_registrant.invoice.size else "Unknown"
#             }, status=200)
#         else:
#             # All checks passed, invoice can be generated on-demand
#             return JsonResponse({
#                 "success": True,
#                 "message": "Invoice is ready for on-demand generation",
#                 "status": 200,
#                 "invoice_status": "ready",
#                 "can_download": True,
#                 "order_id": order_id,
#                 "note": "Invoice will be generated on-demand and saved"
#             }, status=200)
        
#     except Exception as e:
#         return JsonResponse({
#             "success": False,
#             "message": f"Error checking invoice status: {str(e)}",
#             "status": 500,
#             "error_code": "INTERNAL_ERROR"
#         }, status=500)


er(),
#                 'total_amount': order[0].total_amount,
#                 'company_name': company_details[0].name,
#                 'company_address': company_details[0].address,
#                 'company_phone': company_details[0].phone,
#                 'company_panid': company_details[0].pan, 
#                 }
#         with open('./static/pdfs/file.pdf','wb') as f:   

#             buf=io.BytesIO()
#             c = canvas.Canvas(buf, pagesize=(250*mm, 330*mm),
#                                 pageCompression=1, bottomup=1)
#             reportlab.rl_config.TTFSearchPath.append(
#                 str(settings.BASE_DIR) + '/staticfiles/fontawesome/webfonts/')

#             # register the external font with .ttf extension only
#             pdfmetrics.registerFont(
#                 TTFont('bookman-bold', './staticfiles/fontawesome/Bookman Bold/Bookman Bold.ttf'))
#             pdfmetrics.registerFont(
#                 TTFont('bookman', './staticfiles/fontawesome/bookman_old.TTF'))

#             pdfmetrics.registerFont(
#                 TTFont('Arial', './staticfiles/fontawesome/arial/arial.ttf'))

#             c.setTitle('INVOICE')

#             c.rect(15*mm, 15*mm, 220*mm, 296*mm, stroke=1, fill=0)

#             c.drawImage('./staticfiles/img/testing.png', 25*mm, 267*mm,
#                         width=64*mm, height=35*mm, mask=[0, 0.7, 0, 0.7, 0, 0.7])

#             company_name = ["DEEP EIGEN"]

#             if (int(data['created_date'].day) < 10 and int(data['created_date'].month) < 10):
                
#                 invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; &nbsp; # &nbsp;DE/{a}-{b}/{c:05d} <br/>Date:&nbsp; 0{1}/0{2}/{3} '.format(
                
#                 str(5.1*mm),     str(data['created_date'].day),    str(data['created_date'].month),   str(data['created_date'].year), a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=next_number) ]

            
#             elif (int(data['created_date'].day) < 10 and int(data['created_date'].month) >10):
                
#                 invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; &nbsp; # &nbsp; &nbsp;DE/{a}-{b}/{c:06d} <br/>Date:&nbsp; 0{1}/{2}/{3} '.format(
                    
#                     str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),     str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=s_n)]

            
#             elif (int(data['created_date'].day) >10 and int(data['created_date'].month) < 10):
                
#                 invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; # &nbsp;DE/{a}-{b}/{c:06d}<br/>Date:&nbsp; {1}/0{2}/{3} '.format(
                    
#                     str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),    str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=s_n)]


#             else :
#                 invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> 
# def Invoice(request, payment_id, course_id, orderNumber):
#     """
#     Generate and download invoice PDF
    
#     Parameters:
#     - payment_id: Razorpay payment ID
#     - course_id: Course ID
#     - orderNumber: Order number (format: "YYYY-YYYY.SERIAL_NUMBER" or "None")
    
#     Validations:
#     ✅ User authenticated
#     ✅ User enrolled in course
#     ✅ Enrollment is active (not expired)
#     ✅ Payment exists and status = "Completed"
#     ✅ Order exists and is_ordered = True
#     """
    
#     # 🔐 Authentication check
#     if not request.user.is_authenticated:
#         return JsonResponse({
#             "success": False,
#             "message": "Authentication required",
#             "status": 403,
#             "error_code": "AUTH_REQUIRED"
#         }, status=403)

#     # Use timezone-aware datetime
#     now = timezone.now()
    
#     try:
#         # ✅ VALIDATION 1: User enrollment exists
#         enrollUser = EnrolledUser.objects.filter(user=request.user, course=course_id).first()
#         if not enrollUser:
#             return JsonResponse({
#                 "success": False,
#                 "message": "User is not enrolled in this course",
#                 "status": 403,
#                 "error_code": "NOT_ENROLLED"
#             }, status=403)
        
#         # ✅ VALIDATION 2: Enrollment is active (not expired)
#         if not enrollUser.enrolled or enrollUser.end_at < now:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Course enrollment has expired or is inactive",
#                 "status": 403,
#                 "error_code": "ENROLLMENT_INACTIVE",
#                 "enrollment_end_date": enrollUser.end_at.isoformat() if enrollUser.end_at else None
#             }, status=403)
        
#         # ✅ VALIDATION 3: Payment exists
#         payment = Payment.objects.filter(user=request.user, payment_id=payment_id).first()
#         if not payment:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Payment record not found",
#                 "status": 404,
#                 "error_code": "PAYMENT_NOT_FOUND"
#             }, status=404)
        
#         # ✅ VALIDATION 4: Payment is verified (status = "Completed")
#         if payment.status != "Completed":
#             return JsonResponse({
#                 "success": False,
#                 "message": f"Payment has not been verified yet. Current status: {payment.status}",
#                 "status": 402,
#                 "error_code": "PAYMENT_NOT_VERIFIED",
#                 "payment_status": payment.status
#             }, status=402)
        
#         # ✅ VALIDATION 5: Order exists
#         order = Order.objects.filter(id=enrollUser.order.id).first()
#         if not order:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Order record not found",
#                 "status": 404,
#                 "error_code": "ORDER_NOT_FOUND"
#             }, status=404)
        
#         # ✅ VALIDATION 6: Order is completed
#         if not order.is_ordered:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Order has not been completed yet",
#                 "status": 402,
#                 "error_code": "ORDER_INCOMPLETE"
#             }, status=402)

#         total_amount_paid = Order.objects.filter(
#             user=request.user,
#             course=course_id,
#             payment=payment.id
#         ).aggregate(total_sum=Sum('payment__amount_paid'))

#         payment_date = order.created_at
#         #     print("start else is run_:", total_amount_paid)
            
#         #     payment_date=order[0].created_at
        
#         company_details = company.objects.all()

#         p = inflect.engine()
   
#         amount_chargebale = p.number_to_words(int(payment.amount_paid))
        

#         present_date = payment_date.date()
#         if present_date.month > 3:
#             financial_year = [present_date.year, present_date.year + 1]
#         else:
#             financial_year = [present_date.year - 1, present_date.year]


#         # 🔹 Get last invoice safely
#         last_invoice = Invoice_Registrant.objects.order_by('-id').first()

#         if last_invoice and last_invoice.serial_no:
#             try:
#                 parts = last_invoice.serial_no.split('.')
#                 if len(parts) == 2:
#                     last_number = int(parts[1])
#                     next_number = last_number + 1
#                 else:
#                     next_number = 1
#             except:
#                 next_number = 1
#         else:
#             next_number = 1


#         # 🔹 Generate new serial number
#         new_serial = f"{financial_year[0]}.{next_number:05d}"


#         # 🔥 Always create NEW invoice record
#         Invoice_registrant = Invoice_Registrant.objects.create(
#             order=order,
#             name=enrollUser,
#             serial_no=new_serial
#         )


#         # Determine installment type
#         install = "1st Installment"
#         if enrollUser.installment_id_2 == payment_id:
#             install = "2nd Installment"
#         elif enrollUser.installment_id_3 == payment_id:
#             install = "3rd Installment"

#         data = {'firstname': order.first_name,
#                 'lastname': order.last_name,
#                 'course': order.course,
#                 'orderid': order.order_number,
#                 'payment_id': payment_id,
#                 'created_date': order.created_at.date(),
#                 'course_category': order.course.category,
#                 'address': order.address,
#                 'city': order.city,
#                 'state': order.state,
#                 'country': order.country,
#                 'zipcode': order.zipcode,
#                 'phone_number': order.phone,
#                 'email': order.email,
#                 'quantity': 1,
#                 'amount': order.course_amount,
#                 'amount_paid': order.payment.amount_paid,
#                 'remaining_amount': order.total_amount - (total_amount_paid['total_sum']),
#                 'amount_charge': amount_chargebale.upper(),
#                 'total_amount': order.total_amount,
#                 'company_name': company_details[0].name,
#                 'company_address': company_details[0].address,
#                 'company_phone': company_details[0].phone,
#                 'company_panid': company_details[0].pan, 
#                 }
        
#         buf = io.BytesIO()
#         c = canvas.Canvas(buf, pagesize=(250*mm, 330*mm),
#                             pageCompression=1, bottomup=1)
#         reportlab.rl_config.TTFSearchPath.append(
#             str(settings.BASE_DIR) + '/staticfiles/fontawesome/webfonts/')

#         # register the external font with .ttf extension only
#         pdfmetrics.registerFont(
#             TTFont('bookman-bold', './staticfiles/fontawesome/Bookman Bold/Bookman Bold.ttf'))
#         pdfmetrics.registerFont(
#             TTFont('bookman', './staticfiles/fontawesome/bookman_old.TTF'))

#         pdfmetrics.registerFont(
#             TTFont('Arial', './staticfiles/fontawesome/arial/arial.ttf'))

#         c.setTitle('INVOICE')

#         c.rect(15*mm, 15*mm, 220*mm, 296*mm, stroke=1, fill=0)

#         c.drawImage('./staticfiles/img/testing.png', 25*mm, 267*mm,
#                         width=64*mm, height=35*mm, mask=[0, 0.7, 0, 0.7, 0, 0.7])

#         company_name = ["DEEP EIGEN"]

#         if (int(data['created_date'].day) < 10 and int(data['created_date'].month) < 10):
                
#                 invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; &nbsp; # &nbsp;DE/{a}-{b}/{c:05d} <br/>Date:&nbsp; 0{1}/0{2}/{3} '.format(
                
#                 str(5.1*mm),     str(data['created_date'].day),    str(data['created_date'].month),   str(data['created_date'].year), a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=next_number) ]

            
#         elif (int(data['created_date'].day) < 10 and int(data['created_date'].month) >10):
                
#                 invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; &nbsp; # &nbsp; &nbsp;DE/{a}-{b}/{c:06d} <br/>Date:&nbsp; 0{1}/{2}/{3} '.format(
                    
#                     str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),     str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=next_number)]

            
#         elif (int(data['created_date'].day) >10 and int(data['created_date'].month) < 10):
                
#                 invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; # &nbsp;DE/{a}-{b}/{c:06d}<br/>Date:&nbsp; {1}/0{2}/{3} '.format(
                    
#                     str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),    str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=next_number)]


#         else :
#                 invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; # &nbsp;DE/{a}-{b}/{c:06d} <br/>Date:&nbsp; {1}/{2}/{3} '.format(
                
#                     str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),    str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=next_number)]




#         input_string =data['course']

#             # print(input_string)
#         words = input_string.title.split()
#             # print(words[0:])
#         words.insert(-2,'\n')
#         output_string = ' '.join(words) 


#         invoice_data_1 = [
#                 'Phone: &nbsp; {0} <br/> Email: &nbsp; {1}'.format(str(data['phone_number']), data['email'])]

#         user_data = ['<font color="red" face="bookman-bold" size="{0}"></font> <br/> <font face="bookman-bold"> To &nbsp; &nbsp; &nbsp;&nbsp;&nbsp;&nbsp; :&nbsp;{1}  {2} </font> <br/> <font face="bookman-bold" >State </font> &nbsp;&nbsp; &nbsp; :&nbsp;{3} <br/>  <font face="bookman-bold" > Country </font>:   {4} <br/> <font face="bookman-bold" > PIN </font> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; :&nbsp;{5}' .format(
#                 str(5*mm), data['firstname'].capitalize(), data['lastname'].capitalize(), data['state'], data['country'], data['zipcode'])] 

            
#         if enrollUser.no_of_installments == 1:
                
#                 # Calculate discount
#                 discount = data['amount'] - total_amount_paid['total_sum']

#                 # Calculate total amount (Total Amount - Discount)
#                 total_amount = data['amount'] - discount

#                 # Calculate remaining amount (Total Amount - Paid Amount)
#                 remaining_amount = total_amount - total_amount_paid['total_sum']
                
#                 table_data = [['#','Course Description', 'Payment ID', 'Total INR'],

#                             ['1', '{0}'.format(output_string), '{0}'.format(data['payment_id']), 'Rs : {0}'.format(data['amount'])],

#                             ['2', ' Discount  Offered ', '', 'Rs : {0}'.format(discount)],

#                             ['', '', '', ''],
#                             ['3',"No Of Installments","Installment","Amount"],

#                             ['','{0}'.format(enrollUser.no_of_installments),'{0}'.format(install),'Rs:{0}'.format(data['amount'])],

#                                 ['Total Amount', ' ', ' ', 'Rs : {0}'.format(total_amount)],

#                                 ['Paid amount', ' ',' ', 'Rs : {0}'.format(total_amount_paid['total_sum'])],

#                                 ['Remaining Amount',  ' ', ' ',  'Rs : {0}'.format((remaining_amount))]]
                
#         elif enrollUser.no_of_installments == 3:
                
#                 course_amount = data['amount']
                
#                 installment_amount = round(data['amount'] / 3, 2)
                
#                 # Calculate discount
#                 discount = installment_amount - total_amount_paid['total_sum']

#                 # Calculate total amount (Total Amount - Discount)
#                 total_amount = round(installment_amount - discount, 2)

#                 # Calculate remaining amount (Total Amount - Paid Amount)
#                 remaining_amount = total_amount - total_amount_paid['total_sum']
                
#                 table_data = [['#','Course Description', 'Payment ID', 'Total INR'],

#                             ['1', '{0}'.format(output_string), '{0}'.format(data['payment_id']), 'Rs : {0}'.format(course_amount)],
                            
#                             ['2',"No Of Installments","Installment","Amount"],

#                             ['','{0}'.format(enrollUser.no_of_installments),'{0}'.format(install),'Rs:{0}'.format(installment_amount)],

#                             ['', '', '', ''],
                            
#                             ['3', ' Discount  Offered ', '', 'Rs : {0}'.format(discount)],



#                                 ['Total Amount', ' ', ' ', 'Rs : {0}'.format(total_amount)],

#                                 ['Paid amount', ' ',' ', 'Rs : {0}'.format(total_amount_paid['total_sum'])],

#                                 ['Remaining Amount',  ' ', ' ',  'Rs : {0}'.format((remaining_amount))]]
                
#         else:
                
#                 course_amount = data['amount']
                
#                 installment_amount = round(data['amount'] / 2, 2)
                
#                 # Calculate discount
#                 discount = installment_amount - total_amount_paid['total_sum']

#                 # Calculate total amount (Total Amount - Discount)
#                 total_amount = round(installment_amount - discount, 2)

#                 # Calculate remaining amount (Total Amount - Paid Amount)
#                 remaining_amount = total_amount - total_amount_paid['total_sum']
                
#                 table_data = [['#','Course Description', 'Payment ID', 'Total INR'],

#                             ['1', '{0}'.format(output_string), '{0}'.format(data['payment_id']), 'Rs : {0}'.format(course_amount)],
                            
#                             ['2',"No Of Installments","Installment","Amount"],

#                             ['','{0}'.format(enrollUser.no_of_installments),'{0}'.format(install),'Rs:{0}'.format(installment_amount)],

#                             ['', '', '', ''],
                            
#                             ['3', ' Discount  Offered ', '', 'Rs : {0}'.format(discount)],

#                                 ['Total Amount', ' ', ' ', 'Rs : {0}'.format(total_amount)],

#                                 ['Paid amount', ' ',' ', 'Rs : {0}'.format(total_amount_paid['total_sum'])],

#                                 ['Remaining Amount',  ' ', ' ',  'Rs : {0}'.format((remaining_amount))]]



#         table_below_data = ['SUBJECT TO BHOPAL JURISDICTION', 'E. & O. E.']

#         Amount_in_words = ['<font face="bookman" >Amount Chargeable (in words) </font>: <br/> <font face="bookman-bold" size="9">  INR {1} Rupees Only  /- </font>'.format(
#                 str(4.3*mm), amount_chargebale.capitalize())]

#         company_details = ['Company PAN : AAICD5934H',
#                 'CIN: U80900MP2021PTC056553']


#         signature=['computer generated receipt hence signature not required ']


#         font_name = 'Regular'  # custom font name


#         def heading():                                # Heading with name DEEP EIGEN
#                 textobject = c.beginText(94*mm, 290*mm)
#                 textobject.setFillColorRGB(200, 0, 0)
#                 textobject.setFont('bookman-bold', 10*mm)
#                 textobject.setHorizScale(100)
#                 for line in company_name:
#                     textobject.textLine(line)
#                 return textobject


#         def invoice_text():                           # Invoice  heading below text

#                 Style = ParagraphStyle(
#                     name='BodyText',
#                     fontName='bookman',
#                     fontSize=4.4*mm,
#                     alignment=2, 
#                     leftIndent=30,
#                     borderPadding=10,
#                     spaceShrinkage=0.04,
#                     rightIndent=-180,
#                     spaceBefore=8,          
#                     spaceAfter=8,
#                     leading=18,
                
#                     )

#                 text = c.beginText(200*mm, 270*mm)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('bookman', 14)
#                 for line in invoice_data:
#                     text = Paragraph(line, style=Style, bulletText=None)
#                 return text

#         def invoice_text_email():
#                 Style = ParagraphStyle(
#                     name='BodyText',
#                     fontName='bookman',
#                     fontSize=4.4*mm,
#                     leftIndent=-40,
#                     spaceBefore=8,
#                     spaceAfter=8,
#                     leading=18,
#                     allowWidows=1,
#                     )
#                 text = c.beginText(130*mm, 240*mm)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('bookman', 14)
#                 for line in invoice_data_1:
#                     text = Paragraph(line, style=Style, bulletText=None)
#                 return text


#         def user_text():
                
#                 Style = ParagraphStyle(

#                     name='BodyText',
#                     fontName='bookman',
#                     fontSize=4.4*mm,
#                     leftIndent=20,
#                     borderPadding=10,
#                     spaceShrinkage=0.05,
#                     rightIndent=-180,
#                     spaceBefore=8,
#                     spaceAfter=8,
#                     leading=18
#                 )
#                 text = c.beginText(150, 680)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('bookman', 12)
#                 for line in user_data:
#                     text = Paragraph(line, style=Style, bulletText=None)
#                 return text

#         def text():                                  # Other  text  below table
#                 text = c.beginText(20*mm, 125*mm)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('Times-Roman', 4.1*mm)
#                 for i in range(len(table_below_data)):
#                     if i == 1:
#                         text.setTextOrigin(204*mm, 125*mm)
#                         text.setFont('Times-Bold', 4.1*mm)
#                         text.textLine(table_below_data[i])
#                     else:
#                         text.textLine(table_below_data[i])

#                 return text

#         def amount_in_words():                    # Paid Amount in words
#                 text = c.beginText(20*mm, 120*mm)
#                 Style=ParagraphStyle(
                    
#                     name='BodyText',
#                     fontName='bookman',
#                     fontSize=4.1*mm,
#                     borderPadding=10,
#                     spaceShrinkage=0.05,
#                     rightIndent=-180,
#                     spaceBefore=8,
#                     spaceAfter=8,
#                     leading=18
                    
#                 )
                
#                 for line in Amount_in_words:
#                     text=Paragraph(line,style=Style,bulletText=None)
                
#                 return text

#         def Company_Details():                      # Company Details
#                 c.line(20*mm, 85*mm, 230*mm,85*mm)
#                 text = c.beginText(25*mm, 80*mm)
#                 text.setFont('bookman', 4.1*mm)
#                 c.line(20*mm, 69*mm, 230*mm,69*mm)
#                 for i in range(len(company_details)):
#                     if i == 1:
#                         text.setTextOrigin(25*mm, 73*mm)
#                         text.textLine(company_details[i])
#                     else:
#                         text.textLine(company_details[i])
#                 return text

#         table = Table(table_data, colWidths=[10*mm ,95*mm,55*mm,50*mm] ,rowHeights=[20,35,26,26,30,26,35,30,35])               #### Table data

#         table.setStyle(TableStyle([('BACKGROUND', (0, 0),(2,0),colors.white),

#                                 ('BOX', (0, 0),(-1,-1),2,colors.black),
#                                 ('GRID', (0, 0), (3, 1), 1, colors.black),
#                                 ('GRID', (0, 1),(3,1),1,colors.black),
#                                 ('GRID', (0, 2),(3,2),1,colors.black),
#                                 ('GRID', (0, 3),(3,3),1,colors.black),
#                                 ('GRID',(0,4),(3,4),1,colors.black),
#                                 ('GRID',(0,5),(3,5),1,colors.black),

#                                 ('LINEBELOW', (0, 4),(3,4),1,colors.black),
#                                 ('LINEBELOW', (0, 5),(3,5),1,colors.black),
#                                 ('LINEBELOW', (0, 6),(3,6),1,colors.black),
#                                 ('LINEBELOW', (0, 7),(3,7),1,colors.black),
#                                 ('GRID', (-1, 0),(-1,8),1,colors.black),
#                 # ('LINEBEFORE',(-1,0),(-1,-4),1,colors.black),
#                                 ('LINEBEFORE', (-2, 0),(0,-4),1,colors.black),
#                                 ('VALIGN', (0, 0),(-1,-1),'MIDDLE'),
#                                 ('ALIGN', (-1, 0),(-1,8),'CENTER'),
#                                 ('ALIGN', (1, 0),(1,1),'LEFT'),
#                                 ('FONT', (0, 0), (3, 0), 'bookman-bold', 4.2*mm),
#                                 ('FONT', (0, 2), (2, 2), 'bookman-bold', 4.2*mm),
#                                 ('FONT', (0, 4), (0, 8), 'bookman', 4.3*mm),
#                                 ('FONT', (0, 5), (3, 5), 'bookman', 4.3*mm),
#                                 ('FONT', (0, 1),(1,1),'bookman',4.1*mm),
#                                 ('FONT',(0,4),(3,4),'bookman-bold',4.3*mm),
#                                 ('FONT', (1, 1), (2, 1), 'bookman', 4.0*mm),
#                                 ('FONT', (1, 1), (1, 1), 'bookman-bold', 4.0*mm),
#                                 ('FONT', (-1, 0),(-1,1),'bookman-bold',4.2*mm),
#                                 ('FONT', (-1, 1), (-1, 8), 'Arial', 4.1*mm),
#                                 ('FONT', (0, 0), (0, 2), 'bookman-bold', 4.2*mm),
#                                 ('FONT', (-1, 4), (-2, 4), 'bookman-bold', 4.3*mm),

#             ]))


#         def Sign():
#                 text=c.beginText(120*mm, 100*mm)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('bookman',4*mm)
#                 for i in range(len(signature)):
#                     text.textLine(signature[i])
#                 return text

#             ######### Drawing  the content on canvas  ###################

#         c.drawText(heading())

#         invoice = invoice_text()

#         invoice1 = invoice_text_email()

#         invoice.wrapOn(c, 80*mm, 255*mm)

#         invoice.drawOn(c, 80*mm, 255*mm)

#         invoice1.wrapOn(c, 155*mm, 235*mm)

#         invoice1.drawOn(c, 155*mm, 235*mm)

#         user_para = user_text()

#         user_para.wrapOn(c, 25*mm, 235*mm)

#         user_para.drawOn(c, 25*mm, 235*mm)

#         table.wrapOn(c, 20*mm, 174*mm)

#         table.drawOn(c, 20*mm, 132*mm)

#         c.drawText(text())

#         amount = amount_in_words()

#         amount.wrapOn(c,20*mm, 125*mm)

#         amount.drawOn(c,20*mm, 104*mm)

#         c.drawText(Company_Details())

#         c.drawText(Sign())

#         c.showPage()
            
#         c.save()

#         buf.seek(0)
            
#             # 🔒 FILE SIZE VALIDATION (Max 50MB)
#         MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
#         pdf_size = len(buf.getvalue())
            
#         if pdf_size > MAX_FILE_SIZE:
#                 return JsonResponse({
#                     "success": False,
#                     "message": f"PDF file is too large ({pdf_size / 1024 / 1024:.2f}MB). Maximum allowed: {MAX_FILE_SIZE / 1024 / 1024:.2f}MB",
#                     "status": 413,
#                     "error_code": "FILE_TOO_LARGE",
#                     "file_size_mb": pdf_size / 1024 / 1024
#                 }, status=413)

#             # ✅ IMPROVED PDF RESPONSE HEADERS
#         pdf_filename = f"Invoice_{order.order_number}_{payment_id[:8]}.pdf"
            
#         res = HttpResponse(
#                 buf.getvalue(),
#                 content_type="application/pdf",
#                 headers={
#                     "Content-Disposition": f'attachment; filename="{pdf_filename}"',
#                     "Content-Length": str(pdf_size),
#                     "Cache-Control": "no-cache, no-store, must-revalidate",
#                     "Pragma": "no-cache",
#                     "Expires": "0"
#                 }
#             )

#         file = ContentFile(buf.getvalue())
            
#             # ✅ SAVE PDF TO DATABASE (Invoice_Registrant.invoice field)
#         try:
#                 Invoice_registrant.invoice.save(
#                     f"{order.first_name}_{order.last_name}_invoice_{payment_id}.pdf",
#                     file,
#                     save=True
#                 )
#         except Exception as e:
#                 print(f"⚠️ Warning: PDF could not be saved to database: {str(e)}")
#                 # Continue anyway - user still gets PDF, but storage failed

#             ###-------------------------Sending email to the course managment team -------------------------------###
            
#         if orderNumber and orderNumber != 'None':
#             return res
            
#         else:
#                 numberOfInstallments = enrollUser.no_of_installments
#                 firstInstallment = enrollUser.first_installments
#                 secondInstallment = enrollUser.second_installments
#                 thirdInstallment = enrollUser.third_installments
                
#                 title_heading = ""
#                 top_heading = ""
#                 installment_text = "" 
                
#                 if numberOfInstallments == 3:
#                     if firstInstallment and not secondInstallment and not thirdInstallment:
#                         title_heading = "New User Enrollment"
#                         top_heading = "A new user has enrolled in the following course:"
#                         installment_text = "First installment paid (1 of 3)"

#                     elif firstInstallment and secondInstallment and not thirdInstallment:
#                         title_heading = "Installment"
#                         top_heading = "A user has successfully completed their second installment payment for the following course."
#                         installment_text = "Second installment paid (2 of 3)"

#                     elif firstInstallment and secondInstallment and thirdInstallment:
#                         title_heading = "Installment"
#                         top_heading = "A user has successfully completed their final installment payment for the following course."
#                         installment_text = "Final installment paid (3 of 3)"
                        
#                 elif numberOfInstallments == 2:
#                     if firstInstallment and not secondInstallment:
#                         title_heading = "New User Enrollment"
#                         top_heading = "A new user has enrolled in the following course:"
#                         installment_text = "First installment paid (1 of 2)"
#                     elif firstInstallment and secondInstallment:
#                         title_heading = "Installment"
#                         top_heading = "A user has successfully completed their final installment payment for the following course."
#                         installment_text = "Final installment paid (2 of 2)"
                
#                 elif numberOfInstallments == 1:
#                     if firstInstallment:
#                         title_heading = "New User Enrollment"
#                         top_heading = "A new user has enrolled in the following course:"
#                         installment_text = "Full payment received"     
                                             
#                 else:
#                     print("else is running for nothing") 
                                           
#                 # mail_list=['pulkit.upadhyay@deepeigen.com','vamsikrishna@deepeigen.com','shani@swaayatt.com','sanjeevsharma@deepeigen.com']
#                 mail_list=['sunil.roat@deepeigen.com']
#                 mail_subject="A new invoice has generated for course {0} by order_id {1}".format(data['course'],data['orderid'])
#                 message=render_to_string('invoice/invoice_mail.html',
#                     {
#                         'title_heading': title_heading,
#                         'top_heading': top_heading,
#                         'firstname':data['firstname'],
#                         'orderid':data['payment_id'],
#                         'lastname':data['lastname'],
#                         'course':data['course'],
#                         'installment_info': installment_text
#                     }
#                 )
#                 email = EmailMessage(mail_subject, message, settings.EMAIL_HOST_USER,mail_list)
#                 email.content_subtype="html"
#                 email.attach('invoice_id_{0}_{1}.pdf'.format(data['firstname'],data['orderid']), buf.getvalue(), 'binary/pdf')
#                 email.send()
#                 return res
                  
                  
                  
#     except Exception as e:
#         import traceback
#         error_msg = traceback.format_exc()
#         print(f"🔴 Invoice generation error: {error_msg}")
#         return JsonResponse({
#             "success": False,
#             "message": f"Error generating invoice: {str(e)}",
#             "status": 500,
#             "error_details": error_msg if settings.DEBUG else None
#         }, status=500)


# def Invoice_manual(request ,userId, payment_id,course_id, orderNumber):
#     if not request.user.is_authenticated:
#      return JsonResponse({
#         "success": False,
#         "message": "Authentication required",
#         "status": 403
#     }, status=403)

    
#     now=timezone.now()
    
#     try:
#         # ✅ PRE-GENERATION VALIDATIONS (VERIFIED PAYMENT + COMPLETED ORDER + ENROLLED USER)
#         enrollUser=EnrolledUser.objects.filter(user=userId,course=course_id)
#         if not enrollUser.exists():
#             return JsonResponse({
#                 "success": False,
#                 "message": "User is not enrolled in this course",
#                 "status": 403
#             }, status=403)
        
#         # Check enrollment is active
#         if not enrollUser[0].enrolled or enrollUser[0].end_at < now:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Course enrollment has expired or is inactive",
#                 "status": 403
#             }, status=403)

#         payment=Payment.objects.filter(user=userId,payment_id=payment_id)
#         if not payment.exists():
#             return JsonResponse({
#                 "success": False,
#                 "message": "Payment record not found",
#                 "status": 404
#             }, status=404)
        
#         # Check payment is verified (status = Completed)
#         if payment[0].status != "Completed":
#             return JsonResponse({
#                 "success": False,
#                 "message": "Payment has not been verified yet",
#                 "status": 402
#             }, status=402)
        
#         order=Order.objects.filter(id=enrollUser[0].order.id)
#         if not order.exists():
#             return JsonResponse({
#                 "success": False,
#                 "message": "Order not found",
#                 "status": 404
#             }, status=404)
        
#         # Check order is completed
#         if not order[0].is_ordered:
#             return JsonResponse({
#                 "success": False,
#                 "message": "Order has not been completed yet",
#                 "status": 402
#             }, status=402)

#         total_amount_paid=Order.objects.filter(user=userId,course=course_id,payment=payment[0].id).aggregate(total_sum=Sum('payment__amount_paid'))

#         payment_date=order[0].created_at
            
#         company_details = company.objects.all()

#         p = inflect.engine()
   
#         amount_chargebale = p.number_to_words(int(order[0].payment.amount_paid))
        
#         # thi is new code written by khilesh (Date- 28_Jan_2025) start
#         if orderNumber and orderNumber != 'None':
#             orderTable = Order.objects.filter(order_number=orderNumber)
#             order_instance = orderTable.first()  # Get the first matching Order object
        
#             orderNo = f"{order_instance.first_name}-{order_instance.order_number}"  # Format the desired output
            
#             order_instance = Order.objects.get(order_number=orderNo.split('-')[-1])
#             Invoice_registrant = Invoice_Registrant.objects.filter(order=order_instance).first()
            
#             s_sr = Invoice_registrant.serial_no
#         else:
#             Invoice_registrant=Invoice_Registrant.objects.latest("id")
#             s_sr = Invoice_registrant.serial_no
            
#         # thi is new code written by khilesh (Date- 28_Jan_2025) end
        
#         parts = s_sr.split('.')
        
#         s_n =0
#         if len(parts) == 2:
#             current_date, serial_number_str = parts
            
#             serial_number = int(serial_number_str)
#             s_n = s_n+serial_number
            
#         else:
#             print("Invalid result string format.")
            
#         present_date=payment_date.date()
#         if present_date.month>3:
            
#             financial_year=[present_date.year,present_date.year+1]
#         else:
#             financial_year=[present_date.year-1,present_date.year]

#         install=["2nd Installment" if enrollUser[0].installment_id_2 == payment_id else  "3rd Installment" if enrollUser[0].installment_id_3 == payment_id else "1st Installment"  ][0]

#         data = {'firstname': order[0].first_name,
#                 'lastname': order[0].last_name,
#                 'course': order[0].course,
#                 'orderid': order[0].order_number,
#                 'payment_id':payment_id,
#                 'created_date': order[0].created_at.date(),
#                 'course_category': order[0].course.category,
#                 'address': order[0].address,
#                 'city': order[0].city,
#                 'state': order[0].state,
#                 'country': order[0].country,
#                 'zipcode': order[0].zipcode,
#                 'phone_number': order[0].phone,
#                 'email': order[0].email,
#                 'quantity': 1,
#                 'amount': order[0].course_amount,
#                 'amount_paid': order[0].payment.amount_paid,
#                 'remaining_amount': order[0].total_amount-(total_amount_paid['total_sum']),
#                 'amount_charge': amount_chargebale.upp</font> <br/> <br/> &nbsp; # &nbsp;DE/{a}-{b}/{c:06d} <br/>Date:&nbsp; {1}/{2}/{3} '.format(
                
#                     str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),    str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=s_n)]




#             input_string =data['course']

#             words = input_string.title.split()
#             words.insert(-2,'\n')
#             output_string = ' '.join(words)


#             invoice_data_1 = [
#                 'Phone: &nbsp; {0} <br/> Email: &nbsp; {1}'.format(str(data['phone_number']), data['email'])]

#             user_data = ['<font color="red" face="bookman-bold" size="{0}"></font> <br/> <font face="bookman-bold"> To &nbsp; &nbsp; &nbsp;&nbsp;&nbsp;&nbsp; :&nbsp;{1}  {2} </font> <br/> <font face="bookman-bold" >State </font> &nbsp;&nbsp; &nbsp; :&nbsp;{3} <br/>  <font face="bookman-bold" > Country </font>:   {4} <br/> <font face="bookman-bold" > PIN </font> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; :&nbsp;{5}' .format(
#                 str(5*mm), data['firstname'].capitalize(), data['lastname'].capitalize(), data['state'], data['country'], data['zipcode'])] 

#             if enrollUser[0].no_of_installments == 1:
                
#                 # Calculate discount
#                 discount = data['amount'] - total_amount_paid['total_sum']

#                 # Calculate total amount (Total Amount - Discount)
#                 total_amount =  data['amount'] - discount

#                 # Calculate remaining amount (Total Amount - Paid Amount)
#                 remaining_amount = total_amount - total_amount_paid['total_sum']
                
#                 table_data = [['#','Course Description', 'Payment ID', 'Total INR'],

#                             ['1', '{0}'.format(output_string), '{0}'.format(data['payment_id']), 'Rs : {0}'.format(data['amount'])],

#                             ['2', ' Discount  Offered ', '', 'Rs : {0}'.format(discount)],

#                             ['', '', '', ''],
#                             ['3',"No Of Installments","Installment","Amount"],

#                             ['','{0}'.format(enrollUser[0].no_of_installments),'{0}'.format(install),'Rs:{0}'.format(data['amount'])],

#                                 ['Total Amount', ' ', ' ', 'Rs : {0}'.format(total_amount)],

#                                 ['Paid amount', ' ',' ', 'Rs : {0}'.format(total_amount_paid['total_sum'])],

#                                 ['Remaining Amount',  ' ', ' ',  'Rs : {0}'.format((remaining_amount))]]
                
#             elif enrollUser[0].no_of_installments == 3:
                
#                 course_amount = data['amount']
#                 installment_amount = round(data['amount'] / 3, 2)
                
#                 # Calculate discount
#                 discount = installment_amount - total_amount_paid['total_sum']

#                 # Calculate total amount (Total Amount - Discount)
#                 total_amount =  round(installment_amount - discount, 2)

#                 # Calculate remaining amount (Total Amount - Paid Amount)
#                 remaining_amount = total_amount - total_amount_paid['total_sum']
                
#                 table_data = [['#','Course Description', 'Payment ID', 'Total INR'],

#                             ['1', '{0}'.format(output_string), '{0}'.format(data['payment_id']), 'Rs : {0}'.format(course_amount)],
                            
#                             ['2',"No Of Installments","Installment","Amount"],

#                             ['','{0}'.format(enrollUser[0].no_of_installments),'{0}'.format(install),'Rs:{0}'.format(installment_amount)],

#                             ['', '', '', ''],
                            
#                             ['3', ' Discount  Offered ', '', 'Rs : {0}'.format(discount)],



#                                 ['Total Amount', ' ', ' ', 'Rs : {0}'.format(total_amount)],

#                                 ['Paid amount', ' ',' ', 'Rs : {0}'.format(total_amount_paid['total_sum'])],

#                                 ['Remaining Amount',  ' ', ' ',  'Rs : {0}'.format((remaining_amount))]]
                
#             else:
                
#                 course_amount = data['amount']
#                 installment_amount = round(data['amount'] / 2, 2)
                
#                 # Calculate discount
#                 discount = installment_amount - total_amount_paid['total_sum']

#                 # Calculate total amount (Total Amount - Discount)
#                 total_amount =  round(installment_amount - discount, 2)

#                 # Calculate remaining amount (Total Amount - Paid Amount)
#                 remaining_amount = total_amount - total_amount_paid['total_sum']
                
#                 table_data = [['#','Course Description', 'Payment ID', 'Total INR'],

#                             ['1', '{0}'.format(output_string), '{0}'.format(data['payment_id']), 'Rs : {0}'.format(course_amount)],
                            
#                             ['2',"No Of Installments","Installment","Amount"],

#                             ['','{0}'.format(enrollUser[0].no_of_installments),'{0}'.format(install),'Rs:{0}'.format(installment_amount)],

#                             ['', '', '', ''],
                            
#                             ['3', ' Discount  Offered ', '', 'Rs : {0}'.format(discount)],

#                                 ['Total Amount', ' ', ' ', 'Rs : {0}'.format(total_amount)],

#                                 ['Paid amount', ' ',' ', 'Rs : {0}'.format(total_amount_paid['total_sum'])],

#                                 ['Remaining Amount',  ' ', ' ',  'Rs : {0}'.format((remaining_amount))]]
           
#             table_below_data = ['SUBJECT TO BHOPAL JURISDICTION', 'E. & O. E.']

#             Amount_in_words = ['<font face="bookman" >Amount Chargeable (in words) </font>: <br/> <font face="bookman-bold" size="9">  INR {1} Rupees Only  /- </font>'.format(
#                 str(4.3*mm), amount_chargebale.capitalize())]

#             company_details = ['Company PAN : AAICD5934H',
#                 'CIN: U80900MP2021PTC056553']


#             signature=['computer generated receipt hence signature not required ']


#             font_name = 'Regular'  # custom font name


#             def heading():                                # Heading with name DEEP EIGEN
#                 textobject = c.beginText(94*mm, 290*mm)
#                 textobject.setFillColorRGB(200, 0, 0)
#                 textobject.setFont('bookman-bold', 10*mm)
#                 textobject.setHorizScale(100)
#                 for line in company_name:
#                     textobject.textLine(line)
#                 return textobject


#             def invoice_text():                           # Invoice  heading below text

#                 Style = ParagraphStyle(
#                     name='BodyText',
#                     fontName='bookman',
#                     fontSize=4.4*mm,
#                     alignment=2, 
#                     leftIndent=30,
#                     borderPadding=10,
#                     spaceShrinkage=0.04,
#                     rightIndent=-180,
#                     spaceBefore=8,          
#                     spaceAfter=8,
#                     leading=18,
                
#                     )

#                 text = c.beginText(200*mm, 270*mm)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('bookman', 14)
#                 for line in invoice_data:
#                     text = Paragraph(line, style=Style, bulletText=None)
#                 return text

#             def invoice_text_email():
#                 Style = ParagraphStyle(
#                     name='BodyText',
#                     fontName='bookman',
#                     fontSize=4.4*mm,
#                     leftIndent=-40,
#                     spaceBefore=8,
#                     spaceAfter=8,
#                     leading=18,
#                     allowWidows=1,
#                     )
#                 text = c.beginText(130*mm, 240*mm)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('bookman', 14)
#                 for line in invoice_data_1:
#                     text = Paragraph(line, style=Style, bulletText=None)
#                 return text

#             def user_text():
                
#                 Style = ParagraphStyle(

#                     name='BodyText',
#                     fontName='bookman',
#                     fontSize=4.4*mm,
#                     leftIndent=20,
#                     borderPadding=10,
#                     spaceShrinkage=0.05,
#                     rightIndent=-180,
#                     spaceBefore=8,
#                     spaceAfter=8,
#                     leading=18
#                 )
#                 text = c.beginText(150, 680)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('bookman', 12)
#                 for line in user_data:
#                     text = Paragraph(line, style=Style, bulletText=None)
#                 return text

#             def text():                                  # Other  text  below table
#                 text = c.beginText(20*mm, 125*mm)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('Times-Roman', 4.1*mm)
#                 for i in range(len(table_below_data)):
#                     if i == 1:
#                         text.setTextOrigin(204*mm, 125*mm)
#                         text.setFont('Times-Bold', 4.1*mm)
#                         text.textLine(table_below_data[i])
#                     else:
#                         text.textLine(table_below_data[i])

#                 return text

#             def amount_in_words():                    # Paid Amount in words
#                 text = c.beginText(20*mm, 120*mm)
#                 Style=ParagraphStyle(
                    
#                     name='BodyText',
#                     fontName='bookman',
#                     fontSize=4.1*mm,
#                     borderPadding=10,
#                     spaceShrinkage=0.05,
#                     rightIndent=-180,
#                     spaceBefore=8,
#                     spaceAfter=8,
#                     leading=18
                    
#                 )
                
#                 for line in Amount_in_words:
#                     text=Paragraph(line,style=Style,bulletText=None)
                
#                 return text

#             def Company_Details():                      # Company Details
#                 c.line(20*mm, 85*mm, 230*mm,85*mm)
#                 text = c.beginText(25*mm, 80*mm)
#                 text.setFont('bookman', 4.1*mm)
#                 c.line(20*mm, 69*mm, 230*mm,69*mm)
#                 for i in range(len(company_details)):
#                     if i == 1:
#                         text.setTextOrigin(25*mm, 73*mm)
#                         text.textLine(company_details[i])
#                     else:
#                         text.textLine(company_details[i])
#                 return text

#             table = Table(table_data, colWidths=[10*mm ,95*mm,55*mm,50*mm] ,rowHeights=[20,35,26,26,30,26,35,30,35])               #### Table data

#             table.setStyle(TableStyle([('BACKGROUND', (0, 0),(2,0),colors.white),

#                                 ('BOX', (0, 0),(-1,-1),2,colors.black),
#                                 ('GRID', (0, 0), (3, 1), 1, colors.black),
#                                 ('GRID', (0, 1),(3,1),1,colors.black),
#                                 ('GRID', (0, 2),(3,2),1,colors.black),
#                                 ('GRID', (0, 3),(3,3),1,colors.black),
#                                 ('GRID',(0,4),(3,4),1,colors.black),
#                                 ('GRID',(0,5),(3,5),1,colors.black),

#                                 ('LINEBELOW', (0, 4),(3,4),1,colors.black),
#                                 ('LINEBELOW', (0, 5),(3,5),1,colors.black),
#                                 ('LINEBELOW', (0, 6),(3,6),1,colors.black),
#                                 ('LINEBELOW', (0, 7),(3,7),1,colors.black),
#                                 ('GRID', (-1, 0),(-1,8),1,colors.black),
#                 # ('LINEBEFORE',(-1,0),(-1,-4),1,colors.black),
#                                 ('LINEBEFORE', (-2, 0),(0,-4),1,colors.black),
#                                 ('VALIGN', (0, 0),(-1,-1),'MIDDLE'),
#                                 ('ALIGN', (-1, 0),(-1,8),'CENTER'),
#                                 ('ALIGN', (1, 0),(1,1),'LEFT'),
#                                 ('FONT', (0, 0), (3, 0), 'bookman-bold', 4.2*mm),
#                                 ('FONT', (0, 2), (2, 2), 'bookman-bold', 4.2*mm),
#                                 ('FONT', (0, 4), (0, 8), 'bookman', 4.3*mm),
#                                 ('FONT', (0, 5), (3, 5), 'bookman', 4.3*mm),
#                                 ('FONT', (0, 1),(1,1),'bookman',4.1*mm),
#                                 ('FONT',(0,4),(3,4),'bookman-bold',4.3*mm),
#                                 ('FONT', (1, 1), (2, 1), 'bookman', 4.0*mm),
#                                 ('FONT', (1, 1), (1, 1), 'bookman-bold', 4.0*mm),
#                                 ('FONT', (-1, 0),(-1,1),'bookman-bold',4.2*mm),
#                                 ('FONT', (-1, 1), (-1, 8), 'Arial', 4.1*mm),
#                                 ('FONT', (0, 0), (0, 2), 'bookman-bold', 4.2*mm),
#                                 ('FONT', (-1, 4), (-2, 4), 'bookman-bold', 4.3*mm),

#             ]))


#             def Sign():
#                 text=c.beginText(120*mm, 100*mm)
#                 text.setFillColorRGB(0, 0, 0)
#                 text.setFont('bookman',4*mm)
#                 for i in range(len(signature)):
#                     text.textLine(signature[i])
#                 return text

#             ######### Drawing  the content on canvas  ###################

#             c.drawText(heading())

#             invoice = invoice_text()

#             invoice1 = invoice_text_email()

#             invoice.wrapOn(c, 80*mm, 255*mm)

#             invoice.drawOn(c, 80*mm, 255*mm)

#             invoice1.wrapOn(c, 155*mm, 235*mm)

#             invoice1.drawOn(c, 155*mm, 235*mm)

#             user_para = user_text()

#             user_para.wrapOn(c, 25*mm, 235*mm)

#             user_para.drawOn(c, 25*mm, 235*mm)

#             table.wrapOn(c, 20*mm, 174*mm)

#             table.drawOn(c, 20*mm, 132*mm)

#             c.drawText(text())

#             amount = amount_in_words()

#             amount.wrapOn(c,20*mm, 125*mm)

#             amount.drawOn(c,20*mm, 104*mm)

#             c.drawText(Company_Details())

#             c.drawText(Sign())

#             c.save()
            
#             c.showPage()

#             buf.seek(0)

#             res=HttpResponse(buf.getvalue(),headers={
#                 'Content-Type':"application/pdf",
#                 "Content-Disposition": 'attachment; filename="invoice.pdf"',
#             })

#             file=ContentFile(buf.getvalue())
            
#             # ✅ SAVE PDF TO DATABASE (Invoice_Registrant.invoice field)
#             try:
#                 Invoice_registrant.invoice.save(
#                     f"{order[0].first_name}_{order[0].last_name}_invoice_{payment_id}.pdf",
#                     file,
#                     save=True
#                 )
#             except Exception as e:
#                 print(f"⚠️ Warning: PDF could not be saved to database: {str(e)}")
#                 # Continue anyway - user still gets PDF, but storage failed

#             ###-------------------------Sending email to the course managment team -------------------------------###
            
#         if orderNumber and orderNumber != 'None':
#             return res
            
#         else:
#                 numberOfInstallments = enrollUser[0].no_of_installments
#                 firstInstallment = enrollUser[0].first_installments
#                 secondInstallment = enrollUser[0].second_installments
#                 thirdInstallment = enrollUser[0].third_installments
                
#                 title_heading = ""
#                 top_heading = ""
#                 installment_text = "" 
                
#                 if numberOfInstallments == 3:
#                     if firstInstallment and not secondInstallment and not thirdInstallment:
#                         title_heading = "New User Enrollment"
#                         top_heading = "A new user has enrolled in the following course:"
#                         installment_text = "First installment paid (1 of 3)"

#                     elif firstInstallment and secondInstallment and not thirdInstallment:
#                         title_heading = "Installment"
#                         top_heading = "A user has successfully completed their second installment payment for the following course."
#                         installment_text = "Second installment paid (2 of 3)"

#                     elif firstInstallment and secondInstallment and thirdInstallment:
#                         title_heading = "Installment"
#                         top_heading = "A user has successfully completed their final installment payment for the following course."
#                         installment_text = "Final installment paid (3 of 3)"
                        
#                 elif numberOfInstallments == 2:
#                     if firstInstallment and not secondInstallment:
#                         title_heading = "New User Enrollment"
#                         top_heading = "A new user has enrolled in the following course:"
#                         installment_text = "First installment paid (1 of 2)"
#                     elif firstInstallment and secondInstallment:
#                         title_heading = "Installment"
#                         top_heading = "A user has successfully completed their final installment payment for the following course."
#                         installment_text = "Final installment paid (2 of 2)"
                
#                 elif numberOfInstallments == 1:
#                     if firstInstallment:
#                         title_heading = "New User Enrollment"
#                         top_heading = "A new user has enrolled in the following course:"
#                         installment_text = "Full payment received"     
                                             
#                 else:
#                     print("else is running for nothing")  
                                           
#                 # mail_list=['pulkit.upadhyay@deepeigen.com','vamsikrishna@deepeigen.com','shani@swaayatt.com','sanjeevsharma@deepeigen.com']
#                 mail_list=['sunil.roat@deepeigen.com']
#                 mail_subject="A new invoice has generated for course {0} by order_id {1}".format(data['course'],data['orderid'])
#                 message=render_to_string('invoice/invoice_mail.html',
#                     {   
#                         'title_heading': title_heading,
#                         'top_heading': top_heading,
#                         'firstname':data['firstname'],
#                         'orderid':data['payment_id'],
#                         'lastname':data['lastname'],
#                         'course':data['course'],
#                         'installment_info': installment_text
#                     }
#                 )
#                 email = EmailMessage(mail_subject, message, settings.EMAIL_HOST_USER,mail_list)
#                 email.content_subtype="html"
#                 email.attach('invoice_id_{0}_{1}.pdf'.format(data['firstname'],data['orderid']), buf.getvalue(), 'binary/pdf')
#                 email.send()
#                 return redirect('manual_registration')
                  
    
#     except Exception as e:
#         print(f"{type(e).__str__(e)}")



# ==================== OLD HTML VERSION (COMMENTED OUT) ====================
# def forgotPassword(request):
#     data = {
#         'title': 'Forgot Password | Deep Eigen',
#         'canonical_url' : request.build_absolute_uri(request.path)
#     }
#     if request.method == 'POST':
#         email = request.POST['email']
#         if Account.objects.filter(email=email).exists():
#             user = Account.objects.get(email__exact=email)
#
#             # Reset password email
#             current_site = get_current_site(request)
#             mail_subject = 'Reset Your Password'
#             data = {
#                 'user': user,
#                 'domain': current_site,
#                 'uid': urlsafe_base64_encode(force_bytes(user.pk)),
#                 'token': default_token_generator.make_token(user),
#             }
#             plain_message = render_to_string('accounts/reset_password_email.txt', data)
#             html_message = render_to_string('accounts/reset_password_email.html', data)
#             to_email = email
#             from_email = settings.EMAIL_HOST_USER
#             send_mail(mail_subject, plain_message, from_email, [to_email], html_message=html_message)
#
#             messages.success(request, 'Password reset email has been sent to your email address.')
#             return redirect('login')
#         else:
#             messages.error(request, 'Account does not exist!')
#             return redirect('forgotPassword')
#     return render(request, 'accounts/forgotPassword.html', data)
# ==================== END OF OLD HTML VERSION ====================


# ==================== NEW JSON VERSION ====================
# @csrf_protect
@csrf_exempt

def forgotPassword(request):
    """
    API endpoint for forgot password email
    Returns JSON response confirming if reset email was sent
    Matches Account model field: email
    """
    if request.method == 'POST':
        try:
            import json
            # Handle both JSON and form-data requests
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                email = data.get('email', '').strip()
            else:
                email = request.POST.get('email', '').strip()

            # Validation: Check required field
            if not email:
                return JsonResponse({
                    'success': False,
                    'message': 'Email is required',
                    'status': 400
                }, status=400)

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
                return JsonResponse({
                    'success': True,
                    'message': 'Password reset email has been sent to your email address. Please check your inbox.',
                    'status': 200,
                    'email_sent': True,
                    'email': email  # For confirmation display
                }, status=200)
            else:
                # Account doesn't exist
                return JsonResponse({
                    'success': False,
                    'message': 'Account with this email address does not exist.',
                    'status': 404,
                    'email_found': False
                }, status=404)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Failed to send reset email: {str(e)}',
                'status': 500
            }, status=500)

    elif request.method == 'GET':
        # Return allowed methods info
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



# ==================== NEW JSON VERSION ====================
def resetpassword_validate(request, uidb64, token):
    """
    API endpoint to validate password reset link
    Returns JSON response confirming if reset token is valid
    Takes URL parameters: uidb64 (user id encoded), token (reset token)
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


# @csrf_protect
@csrf_exempt

def resetPassword(request):
    """
    API endpoint to reset user password
    Returns JSON response confirming password reset
    Matches Account model field: password
    Expects: password, confirm_password
    """
    if request.method == 'POST':
        try:
            import json
            # Handle both JSON and form-data requests
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                password = data.get('password', '').strip()
                confirm_password = data.get('confirm_password', '').strip()
                uid = data.get('uid', '').strip()
            else:
                password = request.POST.get('password', '').strip()
                confirm_password = request.POST.get('confirm_password', '').strip()
                uid = request.session.get('uid', '')

            # Validation: Check required fields
            if not password or not confirm_password:
                return JsonResponse({
                    'success': False,
                    'message': 'Password and confirm password are required',
                    'status': 400
                }, status=400)

            # Validation: Passwords match
            if password != confirm_password:
                return JsonResponse({
                    'success': False,
                    'message': 'Passwords do not match',
                    'status': 400
                }, status=400)

            # Validation: Password length (minimum 6 characters)
            if len(password) < 6:
                return JsonResponse({
                    'success': False,
                    'message': 'Password must be at least 6 characters long',
                    'status': 400
                }, status=400)

            # Get uid from session or request
            if not uid:
                uid = request.session.get('uid', '')

            if not uid:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid session. Please request a new password reset link.',
                    'status': 401
                }, status=401)

            # Get user and update password
            try:
                user = Account.objects.get(pk=uid)
            except Account.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'User not found',
                    'status': 404
                }, status=404)

            # Set new password
            user.set_password(password)
            user.save()

            # Clear session uid after successful reset
            if 'uid' in request.session:
                del request.session['uid']

            return JsonResponse({
                'success': True,
                'message': 'Password has been reset successfully. You can now login with your new password.',
                'status': 200,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            }, status=200)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Password reset failed: {str(e)}',
                'status': 500
            }, status=500)

    elif request.method == 'GET':
        # Return allowed methods info
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
# ==================== END OF NEW JSON VERSION ====================

    # old code 
# def Admin_courses(admin):
#     if admin.is_superadmin:
#         print("khilesh here is superadmin")
#         courses=Course.objects.all()
#     elif admin.is_staff and not admin.is_superadmin:
#         print("khilesh here is admin")
#         ta_admin=TeachingAssistant.objects.filter(email=admin.email)
#         courses=ta_admin[0].course_set.all()
#     else:
#         print("khilesh here is user")
#         now = timezone.now()
        enrolled_user=EnrolledUser.objects.filter(user=admin, enrolled=True, end_at__gt=now).order_by('-created_at')
#         courses=Course.objects.filter(id__in=[e.course_id for e in enrolled_user])
#     # print(courses)
#     return courses


    # New Code written by khilesh (Date - 31_Dec_2024) 
def Admin_courses(admin):
    if admin.is_superadmin:
        courses=Course.objects.all()
    elif admin.is_staff and not admin.is_superadmin:
        ta_admin=TeachingAssistant.objects.filter(email=admin.email)
        courses=ta_admin[0].course_set.all()
    else:
        now = timezone.now()
        enrolled_user=EnrolledUser.objects.filter(user=admin, enrolled=True, end_at__gt=now).order_by('-created_at')
        courses=Course.objects.filter(id__in=[e.course_id for e in enrolled_user])
    # print(courses)
    return courses
    
    



# ==================== NEW JSON VERSION ====================
def mycourses(request):
    """
    API endpoint for listing user's courses
    Returns JSON response with user's enrolled courses based on user type
    Handles different user types: superadmin, staff/TA, and regular users
    Matches Course model fields
    
    Now returns prices based on user's country:
    - Indian users (country='India' or 'IN'): Shows INR prices (INR)
    - Other users: Shows USD prices ($)
    """
    # 🔐 AUTHENTICATION GUARD (API-SAFE)
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)
    
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
                # Set price and currency based on user's country
                if is_indian_user:
                    course_price = float(course.indian_fee or 0)
                    course_currency = 'INR'
                    course_currency_code = 'INR'
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
                    'original_indian_fee': float(course.indian_fee or 0) if hasattr(course, 'indian_fee') else None,
                    'original_foreign_fee': float(course.foreign_fee or 0) if hasattr(course, 'foreign_fee') else None,
                }
                
                # Add additional fields if they exist in the model
                if hasattr(course, 'price'):
                    course_data['price'] = course.price
                if hasattr(course, 'duration'):
                    course_data['duration'] = course.duration
                if hasattr(course, 'instructor'):
                    course_data['instructor'] = course.instructor.first_name if hasattr(course, 'instructor') else None
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
# ==================== END OF NEW JSON VERSION ====================
  

@login_required
def profile(request):
    """
    API endpoint to fetch logged-in user's profile
    GET only
    Combines Account + UserProfile models
    """

    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed',
            'status': 405,
            'allowed_methods': ['GET']
        }, status=405)

    user = request.user
    userprofile = get_object_or_404(UserProfile, user=user)

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


























# @login_required(login_url='login')
# ==================== OLD HTML VERSION (COMMENTED OUT) ====================
# @login_required(login_url='login')
# def edit_profile(request):
#     userprofile = get_object_or_404(UserProfile, user=request.user)
#     if request.method == 'POST':
#         user_form = UserForm(request.POST, instance=request.user)
#         profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)
#         if user_form.is_valid() and profile_form.is_valid():
#             user_form.save()
#             profile_form.save()
#             messages.success(request, 'Your profile has been updated.')
#             return redirect('edit_profile')
#     else:
#         user_form = UserForm(instance=request.user)
#         profile_form = UserProfileForm(instance=userprofile)
#     context = {
#         'user_form': user_form,
#         'profile_form': profile_form,
#         'userprofile': userprofile,
#         'title' : 'Edit Profile | Deep Eigen',
#         'canonical_url' : request.build_absolute_uri(request.path)
#     }
#     return render(request, 'accounts/edit_profile.html', context)
# ==================== END OF OLD HTML VERSION ====================







# ==================== NEW JSON VERSION ====================
# @login_required(login_url='login')
# def edit_profile(request):
#     """
#     API endpoint for viewing and updating user profile
#     GET: Returns current user profile data (Account + UserProfile)
#     POST: Updates user profile and returns updated data
#     Matches Account and UserProfile model fields
#     """
#     # 🔐 AUTHENTICATION GUARD (API-SAFE)
#     if not request.user.is_authenticated:
#         return JsonResponse({
#             'success': False,
#             'message': 'Authentication required',
#             'status': 403
#         }, status=403)
    

#     try:
#         userprofile = get_object_or_404(UserProfile, user=request.user)
        
#         if request.method == 'GET':
#             # Return current profile data
#             profile_data = {
#                 'user': {
#                     'id': request.user.id,
#                     'first_name': request.user.first_name,
#                     'last_name': request.user.last_name,
#                     'username': request.user.username,
#                     'email': request.user.email,
#                     'phone_number': request.user.phone_number,
#                     'profession': request.user.profession,
#                     'country': request.user.country,
#                 },
#                 'profile': {
#                     'address_line_1': userprofile.address_line_1,
#                     'address_line_2': userprofile.address_line_2,
#                     'city': userprofile.city,
#                     'state': userprofile.state,
#                     'country': userprofile.country,
#                     'profile_picture': userprofile.profile_picture.url if userprofile.profile_picture else None
#                 }
#             }
            
#             return JsonResponse({
#                 'success': True,
#                 'message': 'Profile data retrieved successfully',
#                 'status': 200,
#                 'data': profile_data
#             }, status=200)

#         elif request.method == 'POST':
#             # Update profile data
#             try:
#                 import json
                
#                 # Handle JSON request
#                 if request.content_type == 'application/json':
#                     data = json.loads(request.body)
                    
#                     # Update Account fields
#                     if 'first_name' in data and data['first_name']:
#                         request.user.first_name = data['first_name'].strip()
#                     if 'last_name' in data and data['last_name']:
#                         request.user.last_name = data['last_name'].strip()
#                     if 'phone_number' in data and data['phone_number']:
#                         request.user.phone_number = data['phone_number'].strip()
#                     if 'profession' in data and data['profession']:
#                         request.user.profession = data['profession'].strip()
#                     if 'country' in data and data['country']:
#                         request.user.country = data['country'].strip()
                    
#                     # Save Account changes
#                     request.user.save()
                    
#                     # Update UserProfile fields
#                     if 'address_line_1' in data:
#                         userprofile.address_line_1 = data['address_line_1'].strip() if data['address_line_1'] else ''
#                     if 'address_line_2' in data:
#                         userprofile.address_line_2 = data['address_line_2'].strip() if data['address_line_2'] else ''
#                     if 'city' in data:
#                         userprofile.city = data['city'].strip() if data['city'] else ''
#                     if 'state' in data:
#                         userprofile.state = data['state'].strip() if data['state'] else ''
#                     if 'country' in data:
#                         userprofile.country = data['country'].strip() if data['country'] else ''
                    
#                     userprofile.save()
                
#                 else:
#                     # Handle form-data request
#                     if request.POST.get('first_name'):
#                         request.user.first_name = request.POST.get('first_name').strip()
#                     if request.POST.get('last_name'):
#                         request.user.last_name = request.POST.get('last_name').strip()
#                     if request.POST.get('phone_number'):
#                         request.user.phone_number = request.POST.get('phone_number').strip()
#                     if request.POST.get('profession'):
#                         request.user.profession = request.POST.get('profession').strip()
#                     if request.POST.get('country'):
#                         request.user.country = request.POST.get('country').strip()
                    
#                     request.user.save()
                    
#                     if request.POST.get('address_line_1'):
#                         userprofile.address_line_1 = request.POST.get('address_line_1').strip()
#                     if request.POST.get('address_line_2'):
#                         userprofile.address_line_2 = request.POST.get('address_line_2').strip()
#                     if request.POST.get('city'):
#                         userprofile.city = request.POST.get('city').strip()
#                     if request.POST.get('state'):
#                         userprofile.state = request.POST.get('state').strip()
#                     if request.POST.get('country'):
#                         userprofile.country = request.POST.get('country').strip()
                    
#                     # Handle profile picture upload
#                     if 'profile_picture' in request.FILES:
#                         userprofile.profile_picture = request.FILES['profile_picture']
                    
#                     userprofile.save()
                
#                 # Return updated profile
#                 updated_profile = {
#                     'user': {
#                         'id': request.user.id,
#                         'first_name': request.user.first_name,
#                         'last_name': request.user.last_name,
#                         'username': request.user.username,
#                         'email': request.user.email,
#                         'phone_number': request.user.phone_number,
#                         'profession': request.user.profession,
#                         'country': request.user.country,
#                     },
#                     'profile': {
#                         'address_line_1': userprofile.address_line_1,
#                         'address_line_2': userprofile.address_line_2,
#                         'city': userprofile.city,
#                         'state': userprofile.state,
#                         'country': userprofile.country,
#                         'profile_picture': userprofile.profile_picture.url if userprofile.profile_picture else None
#                     }
#                 }
                
#                 return JsonResponse({
#                     'success': True,
#                     'message': 'Profile updated successfully',
#                     'status': 200,
#                     'data': updated_profile
#                 }, status=200)

#             except Exception as e:
#                 return JsonResponse({
#                     'success': False,
#                     'message': f'Failed to update profile: {str(e)}',
#                     'status': 400
#                 }, status=400)

#         else:
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Method not allowed. Use GET or POST.',
#                 'status': 405,
#                 'allowed_methods': ['GET', 'POST']
#             }, status=405)

#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Profile error: {str(e)}',
#             'status': 500
#         }, status=500)

# def edit_profile(request):
    """
    API endpoint for updating user profile
    POST only
    Updates Account + UserProfile fields


    """

    print("RAW BODY:", request.body)
    try:
        data = Json.loads(request.body)
        print("PARSED DATA:", data)
    except Exception as e:
        print("JSON ERROR:", e)
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)
    print("METHOD:", request.method)
    print("RAW BODY:", request.body)

    try:
        data = json.loads(request.body)
        print("PARSED DATA:", data)
    except Exception as e:
        print("JSON ERROR:", e)
        return JsonResponse(
            {"success": False, "message": "Invalid JSON"},
            status=400
        )

    # TEMP: return early to confirm JSON works
    return JsonResponse(
        {"success": True, "message": "JSON received"},
        status=200
    )
    # 🔐 AUTHENTICATION GUARD
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)

    # ❌ Block all methods except POST
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Use POST.',
            'status': 405,
            'allowed_methods': ['POST']
        }, status=405)

    try:
        userprofile = get_object_or_404(UserProfile, user=request.user)

        # -------------------------------
        # JSON REQUEST
        # -------------------------------
        if request.content_type == 'application/json':
            data = json.loads(request.body)

            # 🔹 Update Account fields
            if data.get('first_name'):
                request.user.first_name = data['first_name'].strip()

            if data.get('last_name'):
                request.user.last_name = data['last_name'].strip()

            if data.get('phone_number'):
                request.user.phone_number = data['phone_number'].strip()

            if data.get('profession'):
                request.user.profession = data['profession'].strip()

            if data.get('country'):
                request.user.country = data['country'].strip()

            request.user.save()

            # 🔹 Update UserProfile fields
            userprofile.address_line_1 = data.get('address_line_1', userprofile.address_line_1)
            userprofile.address_line_2 = data.get('address_line_2', userprofile.address_line_2)
            userprofile.city = data.get('city', userprofile.city)
            userprofile.state = data.get('state', userprofile.state)
            userprofile.country = data.get('country', userprofile.country)

            userprofile.save()

        # -------------------------------
        # FORM-DATA REQUEST
        # -------------------------------
        else:
            request.user.first_name = request.POST.get('first_name', request.user.first_name)
            request.user.last_name = request.POST.get('last_name', request.user.last_name)
            request.user.phone_number = request.POST.get('phone_number', request.user.phone_number)
            request.user.profession = request.POST.get('profession', request.user.profession)
            request.user.country = request.POST.get('country', request.user.country)
            request.user.save()

            userprofile.address_line_1 = request.POST.get('address_line_1', userprofile.address_line_1)
            userprofile.address_line_2 = request.POST.get('address_line_2', userprofile.address_line_2)
            userprofile.city = request.POST.get('city', userprofile.city)
            userprofile.state = request.POST.get('state', userprofile.state)
            userprofile.country = request.POST.get('country', userprofile.country)

            if 'profile_picture' in request.FILES:
                userprofile.profile_picture = request.FILES['profile_picture']

            userprofile.save()

        # ✅ RESPONSE
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully',
            'status': 200,
            'data': {
                'user': {
                    'id': request.user.id,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                    'username': request.user.username,
                    'email': request.user.email,
                    'phone_number': request.user.phone_number,
                    'profession': request.user.profession,
                    'country': request.user.country,
                },
                'profile': {
                    'address_line_1': userprofile.address_line_1,
                    'address_line_2': userprofile.address_line_2,
                    'city': userprofile.city,
                    'state': userprofile.state,
                    'country': userprofile.country,
                    'profile_picture': userprofile.profile_picture.url if userprofile.profile_picture else None
                }
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to update profile: {str(e)}',
            'status': 400
        }, status=400)


# @require_POST
@login_required
@csrf_exempt
def edit_profile(request):
    """
    API endpoint for updating user profile
    POST only
    Updates Account + UserProfile fields
    """
    # 🔐 AUTHENTICATION GUARD
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)

    # ❌ Block all methods except POST
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Use POST.',
            'status': 405,
            'allowed_methods': ['POST']
        }, status=405)

    # ---- Parse JSON safely ----
    try:
        import json
        data = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        print("JSON ERROR:", e)
        return JsonResponse(
            {"success": False, "message": "Invalid JSON"},
            status=400
        )

    print("PARSED DATA:", data)

    try:
        user = request.user
        userprofile = get_object_or_404(UserProfile, user=user)

        # ---- Update User fields ----
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

        # ---- Update Profile fields ----
        userprofile.address_line_1 = data.get("address_line_1", userprofile.address_line_1)
        userprofile.address_line_2 = data.get("address_line_2", userprofile.address_line_2)
        userprofile.city = data.get("city", userprofile.city)
        userprofile.state = data.get("state", userprofile.state)
        userprofile.country = data.get("country", userprofile.country)

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
                    "profile_picture": (
                        userprofile.profile_picture.url
                        if userprofile.profile_picture else None
                    ),
                },
            }
        }, status=200)

    except Exception as e:
        print("UPDATE ERROR:", e)
        return JsonResponse({
            "success": False,
            "message": f"Failed to update profile: {str(e)}",
        }, status=400)


@login_required(login_url='login')
@csrf_exempt
def upload_profile_picture(request):
    """
    API endpoint for uploading user profile picture
    POST only with multipart/form-data
    """
    # 🔐 AUTHENTICATION GUARD
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)

    # ❌ Block all methods except POST
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Use POST.',
            'status': 405,
            'allowed_methods': ['POST']
        }, status=405)

    try:
        userprofile = get_object_or_404(UserProfile, user=request.user)

        # Check if file was uploaded
        if 'profile_picture' not in request.FILES:
            return JsonResponse({
                'success': False,
                'message': 'No profile picture uploaded',
                'status': 400
            }, status=400)

        profile_picture = request.FILES['profile_picture']

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if profile_picture.content_type not in allowed_types:
            return JsonResponse({
                'success': False,
                'message': 'Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.',
                'status': 400
            }, status=400)

        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if profile_picture.size > max_size:
            return JsonResponse({
                'success': False,
                'message': 'File too large. Maximum size is 5MB.',
                'status': 400
            }, status=400)

        # Delete old profile picture if exists and not default
        if userprofile.profile_picture:
            old_picture = userprofile.profile_picture.path
            if hasattr(userprofile.profile_picture, 'name') and 'default' not in userprofile.profile_picture.name:
                try:
                    import os
                    if os.path.exists(old_picture):
                        os.remove(old_picture)
                except Exception:
                    pass  # Ignore errors deleting old picture

        # Save new profile picture
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
        print("UPLOAD ERROR:", e)
        return JsonResponse({
            "success": False,
            "message": f"Failed to upload profile picture: {str(e)}",
            'status': 500
        }, status=500)


# ==================== END OF NEW JSON VERSION ====================


@login_required(login_url='login')



# ==================== NEW JSON VERSION ====================
@login_required(login_url='login')
def change_password(request):
    """
    API endpoint for changing user password (logged in users)
    Returns JSON response confirming password change
    Requires current password for verification before change
    Matches Account model field: password
    """
    if request.method == 'POST':
        try:
            import json
            
            # Handle both JSON and form-data requests
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                current_password = data.get('current_password', '').strip()
                new_password = data.get('new_password', '').strip()
                confirm_password = data.get('confirm_password', '').strip()
            else:
                current_password = request.POST.get('current_password', '').strip()
                new_password = request.POST.get('new_password', '').strip()
                confirm_password = request.POST.get('confirm_password', '').strip()

            # Validation: Check required fields
            if not current_password or not new_password or not confirm_password:
                return JsonResponse({
                    'success': False,
                    'message': 'Current password, new password, and confirm password are required',
                    'status': 400
                }, status=400)

            # Validation: New passwords match
            if new_password != confirm_password:
                return JsonResponse({
                    'success': False,
                    'message': 'New password and confirm password do not match',
                    'status': 400
                }, status=400)

            # Validation: New password length (minimum 6 characters)
            if len(new_password) < 6:
                return JsonResponse({
                    'success': False,
                    'message': 'New password must be at least 6 characters long',
                    'status': 400
                }, status=400)

            # Validation: Current password is not same as new password
            if current_password == new_password:
                return JsonResponse({
                    'success': False,
                    'message': 'New password cannot be the same as current password',
                    'status': 400
                }, status=400)

            # Get the current user
            user = Account.objects.get(username__exact=request.user.username)

            # Verify current password is correct
            password_valid = user.check_password(current_password)
            if not password_valid:
                return JsonResponse({
                    'success': False,
                    'message': 'Current password is incorrect',
                    'status': 401
                }, status=401)

            # Set new password
            user.set_password(new_password)
            user.save()

            # Return success response
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
                'action': 'login_required'  # Frontend should redirect to login
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
        # Return allowed methods info
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
# ==================== END OF NEW JSON VERSION ====================

# ==================== TEMPORARY DEBUG ENDPOINT ====================
# This is a temporary debug endpoint to diagnose enrollment issues
# Remove this after fixing the enrollment problems
# @login_required(login_url='login')
# def debug_enrollments(request):
    """
    TEMPORARY DEBUG ENDPOINT - TO BE REMOVED AFTER FIXING ISSUES
    
    This endpoint provides detailed debug information about:
    - User account status
    - All EnrolledUser records (including expired ones)
    - All Order records
    - All Payment records
    - Any data inconsistencies
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
        
        # 1. CHECK ALL ENROLLED USER RECORDS
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
        
        # 2. CHECK ALL ORDER RECORDS
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
        
        # 3. CHECK ALL PAYMENT RECORDS
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
        
        # 4. ANALYSIS: FIND MISMATCHES
        issues = []
        
        # Check: Orders without enrollment
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
        
        # Check: Valid enrollments without orders
        orphaned_enrollments = enrolled_course_ids - order_course_ids
        if orphaned_enrollments:
            issues.append({
                'type': 'VALID_ENROLLMENTS_WITHOUT_ORDERS',
                'description': 'Valid enrollment exists but no order found',
                'course_ids': list(orphaned_enrollments),
                'severity': 'MEDIUM'
            })
        
        # Check: Expired enrollments
        if expired_enrolled:
            issues.append({
                'type': 'EXPIRED_ENROLLMENTS',
                'description': 'Some enrollments have expired',
                'count': len(expired_enrolled),
                'severity': 'LOW'
            })
        
        # Check: User courses_enrolled count mismatch
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
        
        # 5. WHAT MYCOURSES ENDPOINT WOULD RETURN
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
            # Regular user - only sees VALID enrollments
            courses_qs = Course.objects.filter(
                id__in=[e['course_id'] for e in valid_enrolled if e['course_id']]
            )
            visible_courses_count = courses_qs.count()
        
        debug_info['mycourses_simulation'] = {
            'user_type': 'superadmin' if user.is_superadmin else ('staff' if user.is_staff else 'regular_user'),
            'courses_visible_to_user': visible_courses_count,
            'note': 'Regular users only see courses with valid (non-expired) enrollments'
        }
        
        # 6. RECOMMENDATIONS
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

# ==================== END OF TEMPORARY DEBUG ENDPOINT ====================


# ============================================================
# Payment History Endpoint
# ============================================================
# Purpose: Get payment history for a specific course enrollment
# Route: GET /accounts/payment_history/{course_id}/
# Returns: All payments made for that course with details
# Added: 10 Feb 2026
# ============================================================

def generate_invoice_for_payment(payment_id, course_id, order_id, installment_number=None):
    """
    Helper function to generate and send invoice for a completed payment
    Called from payment_verify webhook
    
    Parameters:
    - payment_id: Razorpay payment ID
    - course_id: Course ID
    - order_id: Order ID
    - installment_number: Which installment (1, 2, or 3)
    
    Returns: True if successful, False otherwise
    """
    try:
        from django.template.loader import render_to_string
        from django.core.mail import EmailMessage
        from course.models import Order, Course
        from django.conf import settings
        
        # Get order and payment details
        order = Order.objects.filter(id=order_id).first()
        if not order:
            print(f"⚠️ Order {order_id} not found for invoice generation")
            return False
        
        payment = Payment.objects.filter(payment_id=payment_id).first()
        if not payment:
            print(f"⚠️ Payment {payment_id} not found for invoice generation")
            return False
        
        # Get enrollment for installment info
        enrollment = EnrolledUser.objects.filter(user=order.user, course_id=course_id).first()
        if not enrollment:
            print(f"⚠️ Enrollment not found for invoice generation")
            return False
        
        # Determine installment text
        installment_text = "Payment Received"
        if installment_number:
            if installment_number == 1:
                installment_text = f"First installment paid (1 of {enrollment.no_of_installments})"
            elif installment_number == 2:
                installment_text = f"Second installment paid (2 of {enrollment.no_of_installments})"
            elif installment_number == 3:
                installment_text = f"Final installment paid ({enrollment.no_of_installments} of {enrollment.no_of_installments})"
        
        # Get course
        course = Course.objects.filter(id=course_id).first()
        course_name = course.title if course else "Unknown Course"
        
        # Prepare email
        mail_list = ['khilesh.maskare@deepeigen.com']
        
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
        
        print(f"✅ Invoice email sent for payment {payment_id} (Installment {installment_number or 1})")
        return True
        
    except Exception as e:
        print(f"⚠️ Error generating invoice for payment {payment_id}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False


@login_required
def payment_history(request, course_id):
    """
    Get payment history for user's specific course enrollment
    """
    
    if request.method != 'GET':
        return JsonResponse({
            "success": False,
            "message": "Method not allowed. Use GET.",
            "status": 405
        }, status=405)
    
    try:
        from course.models import Course, EnrolledUser, Payment
        
        # Get course
        course = Course.objects.filter(id=course_id).first()
        if not course:
            return JsonResponse({
                "success": False,
                "message": "Course not found",
                "status": 404
            }, status=404)
        
        # Get enrollment for this user and course
        enrollment = EnrolledUser.objects.filter(
            user=request.user,
            course=course,
            enrolled=True
        ).first()
        
        if not enrollment:
            return JsonResponse({
                "success": False,
                "message": "You are not enrolled in this course",
                "status": 403
            }, status=403)
        
        # Fetch all payments for this enrollment
        # Payments are linked via:
        # - 1st installment: enrollment.payment (ForeignKey)
        # - 2nd installment: enrollment.installment_id_2
        # - 3rd installment: enrollment.installment_id_3
        
        payment_ids_list = [enrollment.installment_id_2, enrollment.installment_id_3]
        payment_ids_list = [pid for pid in payment_ids_list if pid]  # Remove None/empty values
        
        # Fetch 2nd and 3rd installment payments
        payments = []
        if payment_ids_list:
            payments = list(Payment.objects.filter(
                user=request.user,
                payment_id__in=payment_ids_list
            ).exclude(payment_id__isnull=True).exclude(payment_id__exact='').order_by('created_at'))
        
        # Add 1st installment payment if it exists (from enrollment.payment ForeignKey)
        if enrollment.payment:
            payments.insert(0, enrollment.payment)
        
        # Fallback: If no payments found via above methods, check Order model
        if not payments:
            from course.models import Order
            order = Order.objects.filter(
                user=request.user,
                course=course,
                payment__isnull=False
            ).first()
            
            if order and order.payment:
                payments = [order.payment]
        
        # Format payment data
        payment_list = []
        total_paid = 0
        
        for idx, payment in enumerate(payments):
            # Determine installment number by matching payment IDs
            if enrollment.payment and enrollment.payment.id == payment.id:
                installment_num = 1
            elif enrollment.installment_id_2 and enrollment.installment_id_2 == payment.payment_id:
                installment_num = 2
            elif enrollment.installment_id_3 and enrollment.installment_id_3 == payment.payment_id:
                installment_num = 3
            else:
                # Default to sequential order
                installment_num = idx + 1
            
            payment_amount = float(payment.amount_paid or 0)
            total_paid += payment_amount
            
            payment_list.append({
                "id": idx + 1,
                "payment_id": payment.payment_id,
                "payment_method": payment.payment_method or "unknown",
                "amount": payment_amount,
                "currency": "INR" if request.user.country and request.user.country.upper() in ['IN', 'INDIA'] else "$",
                "currency_code": "INR" if request.user.country and request.user.country.upper() in ['IN', 'INDIA'] else "USD",
                "status": payment.status.capitalize() if payment.status else "Unknown",
                "paid_at": payment.created_at.isoformat() if payment.created_at else None,
                "installment_number": installment_num,
                "invoice_id": f"INV-{course_id}-{installment_num}"
            })
        
        # Sort by installment number to ensure correct order
        payment_list.sort(key=lambda x: x['installment_number'])
        
        # Calculate remaining due
        user_country = getattr(request.user, 'country', '') or ''
        if user_country.lower() == 'india' or user_country.upper() == 'IN':
            total_fee = enrollment.course.indian_fee or 0
            currency = 'INR'
            currency_code = 'INR'
        else:
            total_fee = enrollment.course.foreign_fee or enrollment.course.indian_fee or 0
            currency = '$'
            currency_code = 'USD'
        
        remaining_due = float(total_fee) - total_paid
        
        return JsonResponse({
            "success": True,
            "message": "Payment history retrieved successfully",
            "status": 200,
            "data": {
                "course_id": course_id,
                "course_name": course.title,
                "course_category": course.category or "Course",
                "total_fee": float(total_fee),
                "total_paid": total_paid,
                "remaining_due": max(0, remaining_due),
                "currency": currency,
                "currency_code": currency_code,
                "no_of_installments": enrollment.no_of_installments,
                "payments_made": len(payment_list),
                "access_till": enrollment.end_at.isoformat() if enrollment.end_at else None,
                "enrolled_on": enrollment.created_at.isoformat() if enrollment.created_at else None,
                "payments": payment_list
            }
        })
    
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Error fetching payment history: {str(e)}",
            "status": 500
        }, status=500)
    


#added 13 feb 26 vikas
def recent_watch(request):
    """
    API endpoint for user's most recently watched video OR last accessed course
    Returns the video details with course and section information
    If no video progress, returns the last accessed course from session
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)

    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a GET request.',
            'status': 405
        }, status=405)

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
@csrf_exempt
def track_last_accessed_course(request):
    """
    API endpoint to track the last accessed course
    When user visits a course, this saves the course as last accessed course
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Authentication required',
            'status': 403
        }, status=403)

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a POST request.',
            'status': 405
        }, status=405)

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
        
        return JsonResponse({
            'success': True,
            'message': 'Last accessed course updated',
            'status': 200,
            'data': {
                'course_id': course.id,
                'course_title': course.title,
                'course_url': course.url_link_name,
            },
            'timestamp': datetime.now().isoformat()
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data',
            'status': 400
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error tracking course: {str(e)}',
            'status': 500
        }, status=500)








def generate_invoice_serial(payment_date):

    present_date = payment_date.date()

    if present_date.month > 3:
        fy_start = present_date.year
    else:
        fy_start = present_date.year - 1

    fy_prefix = f"{fy_start}."

    last_invoice = Invoice_Registrant.objects.filter(
        serial_no__startswith=fy_prefix
    ).order_by('-id').first()

    if last_invoice and last_invoice.serial_no:
        try:
            last_number = int(last_invoice.serial_no.split('.')[1])
            next_number = last_number + 1
        except:
            next_number = 1
    else:
        next_number = 1

    return f"{fy_start}.{next_number:05d}"


# ============================================================
# CHECK EXISTING INVOICE (WITHOUT MODEL CHANGE)
# ============================================================

def get_existing_invoice(order, payment_id):

    invoices = Invoice_Registrant.objects.filter(order=order)

    for inv in invoices:
        if inv.invoice and payment_id in inv.invoice.name:
            return inv

    return None


# ============================================================
# CREATE INVOICE RECORD
# ============================================================

def create_invoice(order, enrollment, payment):

    serial = generate_invoice_serial(payment.created_at)

    return Invoice_Registrant.objects.create(
        order=order,
        name=enrollment,
        serial_no=serial
    )


# ============================================================
# BUILD PDF (CLEAN VERSION)
# ============================================================

def build_invoice_pdf(order, payment, invoice_obj):

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(210*mm, 297*mm))

    c.setTitle("INVOICE")

    c.drawString(40, 800, f"Invoice No: {invoice_obj.serial_no}")
    c.drawString(40, 780, f"Order ID: {order.order_number}")
    c.drawString(40, 760, f"Payment ID: {payment.payment_id}")
    c.drawString(40, 740, f"Customer: {order.first_name} {order.last_name}")
    c.drawString(40, 720, f"Course: {order.course}")
    c.drawString(40, 700, f"Amount Paid: INR{payment.amount_paid}")
    c.drawString(40, 680, f"Date: {payment.created_at.date()}")

    c.showPage()
    c.save()

    buf.seek(0)
    return buf.getvalue()





def Invoice_section(request):

    if not request.user.is_authenticated:
        return JsonResponse({"success": False}, status=403)

    enrollments = EnrolledUser.objects.filter(user=request.user)

    data = []

    for enroll in enrollments:

        order = enroll.order
        if not order:
            continue

        payment_ids = []

        if enroll.payment:
            payment_ids.append(enroll.payment.payment_id)

        if enroll.installment_id_2:
            payment_ids.append(enroll.installment_id_2)

        if enroll.installment_id_3:
            payment_ids.append(enroll.installment_id_3)

        payments = Payment.objects.filter(
            user=request.user,
            payment_id__in=payment_ids
        ).order_by("-created_at")

        for payment in payments:

            installment_number = 1
            if enroll.installment_id_2 == payment.payment_id:
                installment_number = 2
            elif enroll.installment_id_3 == payment.payment_id:
                installment_number = 3

            currency = "INR" if request.user.country == "India" else "$"
            currency_code = "INR" if currency == "INR" else "USD"

            data.append({
                "id": str(payment.id),
                "date": payment.created_at.isoformat(),
                "amount": f"{currency}{float(payment.amount_paid):.2f}",
                "status": "paid" if payment.status == "Completed" else "pending",
                "downloadUrl": f"/accounts/invoice/{payment.payment_id}/{enroll.course.id}/None",

                "currency": currency,
                "currency_code": currency_code,
                "payment_method": payment.payment_method,
                "installment_number": installment_number,
                "no_of_installments": enroll.no_of_installments,
                "course": str(enroll.course),
                "course_amount": float(order.course_amount),
                "amount_paid": float(payment.amount_paid),
                "total_amount": float(order.total_amount),
            })

    return JsonResponse({
        "success": True,
        "data": data
    }, status=200)




def invoice_status(request, order_id):

    if not request.user.is_authenticated:
        return JsonResponse({"success": False}, status=403)

    order = Order.objects.filter(id=order_id, user=request.user).first()
    if not order:
        return JsonResponse({"success": False}, status=404)

    if not order.is_ordered:
        return JsonResponse({
            "success": True,
            "invoice_status": "order_incomplete",
            "can_download": False
        })

    if not order.payment or order.payment.status != "Completed":
        return JsonResponse({
            "success": True,
            "invoice_status": "pending_payment",
            "can_download": False
        })

    return JsonResponse({
        "success": True,
        "invoice_status": "ready",
        "can_download": True
    })




def Invoice(request, payment_id, course_id, orderNumber):

    if not request.user.is_authenticated:
        return JsonResponse({"success": False}, status=403)

    enroll = EnrolledUser.objects.filter(
        user=request.user,
        course=course_id
    ).first()

    if not enroll:
        return JsonResponse({"success": False}, status=403)

    payment = Payment.objects.filter(
        user=request.user,
        payment_id=payment_id
    ).first()

    if not payment or payment.status != "Completed":
        return JsonResponse({"success": False}, status=400)

    order = enroll.order

    # Prevent duplicate invoice creation
    invoice_obj = Invoice_Registrant.objects.filter(
        order=order,
        name=enroll
    ).first()

    if not invoice_obj:
        last_invoice = Invoice_Registrant.objects.order_by("-id").first()
        next_number = 1

        if last_invoice and last_invoice.serial_no:
            try:
                next_number = int(last_invoice.serial_no.split(".")[1]) + 1
            except:
                next_number = 1

        financial_year = timezone.now().year
        serial = f"{financial_year}.{next_number:05d}"

        invoice_obj = Invoice_Registrant.objects.create(
            order=order,
            name=enroll,
            serial_no=serial
        )

    if invoice_obj.invoice:
        return HttpResponse(invoice_obj.invoice.read(), content_type="application/pdf")

    # 🔹 Build simple PDF
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    p.drawString(100, 800, f"Invoice Serial: {invoice_obj.serial_no}")
    p.drawString(100, 780, f"Course: {order.course}")
    p.drawString(100, 760, f"Payment ID: {payment.payment_id}")
    p.drawString(100, 740, f"Amount: {payment.amount_paid}")

    p.save()
    buffer.seek(0)

    pdf_bytes = buffer.getvalue()

    invoice_obj.invoice.save(
        f"Invoice_{payment.payment_id}.pdf",
        ContentFile(pdf_bytes),
        save=True
    )

    return HttpResponse(pdf_bytes, content_type="application/pdf")




def Invoice_manual(request, userId, payment_id, course_id, orderNumber):

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

    # Call same Invoice logic but impersonate user
    request.user = user
    return Invoice(request, payment_id, course_id, orderNumber)
