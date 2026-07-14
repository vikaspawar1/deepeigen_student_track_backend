"""
Views and API endpoints for course management, enrollment, and progress tracking.

This module handles course listings, detailed views, enrollment checks,
installment-based access control, video progress, and assignment submissions.
"""
import importlib.util
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.utils import timezone
from datetime import timedelta, datetime, date
from django.utils.timezone import now
from django.contrib.sites.shortcuts import get_current_site
from decimal import Decimal
from course.models import Course

# Initialize logger
logger = logging.getLogger("course.progress")

# Create your views here.
from .models import *
from django.http import HttpResponse, HttpResponseBadRequest, FileResponse, JsonResponse, HttpResponseForbidden
from utils.decorators import api_login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from dateutil.relativedelta import *

import razorpay
from paywix.payu import Payu
from accounts.models import Account
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from numpy import random
import importlib
import io
import os
import sys
import math
import json
import mimetypes


# reportlab for PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# razorpay object creation
razorpay_client  = razorpay.Client(
                        auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET_KEY)
                        )


# ============================================================
# HELPER FUNCTION: Check if user can purchase a course
# Added: 09 Feb 2025 - To prevent duplicate purchases
# ============================================================
def can_user_purchase_course(user, course):
    """!
    @brief Checks if a user is eligible to purchase a specific course.
    @details Prevents duplicate purchases if the user already has an active enrollment
             or a subscription that covers the course category.

    @param user (Account) The user attempting the purchase.
    @param course (Course) The course to be purchased.

    @return tuple (can_purchase: bool, reason: str, existing_enrollment: EnrolledUser)
    """
    from datetime import datetime
    
    if not user.is_authenticated:
        return True, "Anonymous user can purchase", None
    
    # Check for existing enrollment
    enrollment = EnrolledUser.objects.filter(
        user=user,
        course=course,
        enrolled=True
    ).first()
    
    if enrollment:
        # Check if enrollment is still valid (end_at > now)
        if enrollment.end_at and enrollment.end_at > timezone.now():
            return False, f"You are already enrolled in this course. Access expires on {enrollment.end_at.strftime('%Y-%m-%d')}. Please contact support if you believe this is an error.", enrollment
            
    # Check for active subscription that covers this course category
    from subscriptions.models import UserSubscription, PlanCategoryAccess
    active_subs = UserSubscription.objects.filter(user=user, is_active=True, end_date__gt=timezone.now())
    for sub in active_subs:
        # Restriction: Subscription only covers FEATURED courses
        if course.is_featured and PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type, category=course.category).exists():
            class SubEnrollment:
                def __init__(self, end_date):
                    self.end_at = end_date
            return False, f"You already have access to this course through your active subscription.", SubEnrollment(sub.end_date)
            
    if enrollment and enrollment.end_at and enrollment.end_at <= timezone.now():
        return True, f"Previous enrollment expired on {enrollment.end_at.strftime('%Y-%m-%d')}. User can repurchase.", enrollment
    
    return True, "User is not enrolled in this course", None




# ============================================================
# HELPER FUNCTION: Progressive Section Access Based on Installments
# ============================================================
def installment_Checker(enrolled_user, course):
    """!
    @brief Determines accessible course sections based on installment payment status.
    @details Implements progressive access logic:
             - 1 installment: 100% access.
             - 2 installments: 50% after 1st payment, 100% after 2nd.
             - 3 installments: 33% after 1st payment, 66% after 2nd, 100% after 3rd.

    @param enrolled_user (EnrolledUser) The user's enrollment record.
    @param course (Course) The course being accessed.

    @return QuerySet The set of sections the user is allowed to access.
    """
    def custom_round(value):
        """Round up for percentages (0.5 rounds up)"""
        return math.ceil(value)
    
    all_sections = course.section_set.all().order_by('id')
    total_count = all_sections.count()
    
    # Safety check: if course has no sections, return empty
    if total_count == 0:
        return course.section_set.none()
    
    if not enrolled_user:
        # No enrollment = no access
        return course.section_set.none()
    
    if enrolled_user.no_of_installments <= 1:
        # Full payment or single installment = full access
        return all_sections
    
    if enrolled_user.no_of_installments == 2:
        # 2 installment plan
        if enrolled_user.second_installments:
            # Both payments done = full access (100%)
            return all_sections
        elif enrolled_user.first_installments:
            # Only 1st payment done = 50% access
            allowed_count = custom_round(total_count * 50 / 100)
            return all_sections[:allowed_count]
        else:
            # No payment = no access
            return course.section_set.none()
    
    elif enrolled_user.no_of_installments == 3:
        # 3 installment plan
        if enrolled_user.first_installments and enrolled_user.second_installments and enrolled_user.third_installments:
            # All payments done = full access (100%)
            return all_sections
        elif enrolled_user.first_installments and enrolled_user.second_installments:
            # 1st & 2nd payments done = 66% access (2/3 of the course)
            allowed_count = custom_round(total_count * 66 / 100)
            return all_sections[:allowed_count]
        elif enrolled_user.first_installments:
            # Only 1st payment done = 33% access (1/3 of the course)
            allowed_count = custom_round(total_count * 33 / 100)
            return all_sections[:allowed_count]
        else:
            # No payment = no access
            return course.section_set.none()
    
    # Fallback: full access
    return all_sections




# ============================================================
# API ENDPOINT: Get Accessible Sections Based on Installments
# ============================================================
@permission_classes([IsAuthenticated])
@api_view(['GET'])
def get_accessible_sections(request, course_id):
    """!
    @brief API endpoint to retrieve sections accessible to the logged-in user.
    @details Factors in active enrollments, subscriptions, and installment payment status.

    @param request (Request) DRF Request object.
    @param course_id (int) ID of the target course.

    @return JsonResponse List of accessible sections and access metadata (200).
    """
    try:

        
        # Get course
        course = Course.objects.filter(id=course_id).first()
        if not course:
            return JsonResponse({
                "success": False,
                "message": "Course not found",
                "status": 404
            }, status=404)

        # CHANGE 11 JUNE 2026: Admin bypass - grant full access immediately
        if request.user.is_staff or request.user.is_superadmin:
            accessible_sections = course.section_set.all().order_by('id')
            sections_data = [{
                "id": section.id,
                "name": section.name,
                "title": section.title,
                "part_number": section.part_number,
                "estimated_time": section.estimated_time,
                "topics_covered": section.topics_covered,
            } for section in accessible_sections]

            return JsonResponse({
                "success": True,
                "status": 200,
                "data": {
                    "course_id": course_id,
                    "course_title": course.title,
                    "enrollment": {
                        "no_of_installments": 1,
                        "first_installments": True,
                        "second_installments": True,
                        "third_installments": True,
                        "enrolled_on": now.isoformat(),
                        "access_until": None,
                        "is_admin": True
                    },
                    "access": {
                        "total_sections": accessible_sections.count(),
                        "accessible_sections_count": accessible_sections.count(),
                        "access_percentage": 100,
                        "next_unlock_requirement": None,
                    },
                    "sections": sections_data,
                }
            }, status=200)
        
        # Check if user is enrolled
        now = timezone.now()
        enrollment = EnrolledUser.objects.filter(
            user=request.user,
            course=course,
            enrolled=True,
            end_at__gt=now
        ).first()
        
        user_subscription = None
        if not enrollment:
            from subscriptions.models import UserSubscription, PlanCategoryAccess
            active_subs = UserSubscription.objects.filter(user=request.user, is_active=True, end_date__gt=now)
            for sub in active_subs:
                # Restriction: Subscription only covers FEATURED courses
                if course.is_featured and PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type, category=course.category).exists():
                    user_subscription = sub
                    break

        if not enrollment and not user_subscription:
            return JsonResponse({
                "success": False,
                "message": "You are not enrolled in this course",
                "status": 403,
                "debug": {
                    "enrolled": False,
                    "check_details": "No active enrollment found or enrollment expired"
                }
            }, status=403)
        
        
        total_sections = course.section_set.all().count()
        
        if total_sections == 0:
            return JsonResponse({
                "success": False,
                "message": "Course has no sections available",
                "status": 400,
                "debug": {
                    "total_sections": 0,
                    "error": "Course is not properly set up with sections"
                }
            }, status=400)
        
        # Check if user is staff/superadmin (bypass installment checks)
        if request.user.is_staff or request.user.is_superadmin or user_subscription:
            accessible_sections = course.section_set.all().order_by('id')
            access_percentage = 100
            next_unlock = None
        else:
            # Get accessible sections based on installment status
            accessible_sections = installment_Checker(enrollment, course)
            
            # Calculate access percentage
            accessible_count = accessible_sections.count()
            access_percentage = int((accessible_count / total_sections * 100)) if total_sections > 0 else 0
            
            # Determine next unlock requirement
            next_unlock = None
            if enrollment.no_of_installments == 2:
                if not enrollment.first_installments:
                    next_unlock = "Make 1st payment to unlock 50% of course"
                elif not enrollment.second_installments:
                    next_unlock = "Complete 2nd installment to unlock full course"
            elif enrollment.no_of_installments == 3:
                if not enrollment.first_installments:
                    next_unlock = "Make 1st payment to unlock 33% of course"
                elif not enrollment.second_installments:
                    next_unlock = "Complete 2nd installment to unlock 66% of course"
                elif not enrollment.third_installments:
                    next_unlock = "Complete 3rd installment to unlock full course"
        
        # Serialize accessible sections
        sections_data = []
        for section in accessible_sections:
            sections_data.append({
                "id": section.id,
                "name": section.name,
                "title": section.title,
                "part_number": section.part_number,
                "estimated_time": section.estimated_time,
                "topics_covered": section.topics_covered,
            })
        
        return JsonResponse({
            "success": True,
            "status": 200,
            "data": {
                "course_id": course_id,
                "course_title": course.title,
                "enrollment": {
                    "no_of_installments": enrollment.no_of_installments if enrollment else 1,
                    "first_installments": enrollment.first_installments if enrollment else True,
                    "second_installments": enrollment.second_installments if enrollment else True,
                    "third_installments": enrollment.third_installments if enrollment else True,
                    "enrolled_on": (enrollment.created_at.isoformat() if enrollment else user_subscription.created_at.isoformat()) if (enrollment or user_subscription) else None,
                    "access_until": (enrollment.end_at.isoformat() if enrollment else user_subscription.end_date.isoformat()) if (enrollment or user_subscription) else None,
                },
                "access": {
                    "total_sections": course.section_set.all().count(),
                    "accessible_sections_count": accessible_sections.count(),
                    "access_percentage": access_percentage,
                    "next_unlock_requirement": next_unlock,
                },
                "sections": sections_data,
            }
        }, status=200)
    
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Error fetching sections: {str(e)}",
            "status": 500
        }, status=500)




#change code 24/01/2025  vikas
# @api_login_required
def courses(request):
    """!
    @brief API endpoint to list all available courses or filtered featured courses.
    @details Filtering logic:
             - Admins see all courses.
             - Non-admins see only featured courses.
             - If `featured=true` is passed, returns only featured courses.

    @param request (Request) DRF Request object.

    @return JsonResponse Serialized course listing (200).
    """
    featured = request.GET.get('featured')
    
    # Logic: 
    # 1. If featured='true' is passed, show featured only.
    # 2. If user is NOT an admin (staff or superadmin), show featured only.
    # 3. Otherwise (admin user), show all courses.
    
    is_admin = request.user.is_authenticated and (request.user.is_staff or request.user.is_superadmin)
    
    if featured == 'true' or not is_admin:
        courses_qs = Course.objects.filter(is_featured=True).order_by('-enrolled_users', 'id')
    else:
        courses_qs = Course.objects.all().order_by('-enrolled_users', 'id')


    courses = []
    for course in courses_qs:
        courses.append({
            "id": course.id,
            "title": course.title,
            "url_link_name": course.url_link_name,
            "category": course.category,
            "duration": course.duration,
            "level": course.level,
            "indian_fee": course.indian_fee,
            "foreign_fee": course.foreign_fee,
            "course_image": course.course_image.url if course.course_image else "",
            "assignments": course.assignments,
            "enrolled_users": course.enrolled_users,
        })

    data = {
        "success": True,
        "title": "Courses | Deep Eigen",
        "description": "Deep eigen offers Category-I (Cat-I) and Category-II courses...",
        "canonical_url": request.build_absolute_uri(request.path),
        "course_flag": True,
        "courses": courses
    }

    return JsonResponse(data, safe=False)






#change code 24/01/2025  vikas
def course_detail(request, id, course_url):
    """!
    @brief Returns detailed technical and marketing information about a specific course.

    @param request (Request) DRF Request object.
    @param id (int) Unique course database ID.
    @param course_url (str) Slug for the course URL.

    @return JsonResponse Detailed course metadata, including instructors and TAs (200).
    """
    now = datetime.now()
    course = get_object_or_404(Course, pk=id, url_link_name=course_url)

    enrolled_user_flg = False
    if request.user.is_authenticated:
        enrolled_user_flg = EnrolledUser.objects.filter(
            course_id=id,
            user_id=request.user.id,
            enrolled=True,
            end_at__gt=now
        ).exists()

        if not enrolled_user_flg:
            from subscriptions.models import UserSubscription, PlanCategoryAccess
            active_subs = UserSubscription.objects.filter(user=request.user, is_active=True, end_date__gt=now)
            for sub in active_subs:
                # Restriction: Subscription only covers FEATURED courses
                if course.is_featured and PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type, category=course.category).exists():
                    enrolled_user_flg = True
                    break

    sections_data = []
    for section in course.section_set.all().order_by('id'):
        sections_data.append({
            "id": section.id,
            "name": section.name,
            "title": section.title,
            "part_number": section.part_number,
            "estimated_time": section.estimated_time,
        })

    data = {
        "success": True,
        "course": {
            "id": course.id,
            "title": course.title,
            "meta_description": course.meta_description,
            "category": course.category,
            "duration": course.duration,
            "level": course.level,
            "course_type": course.course_type,
            "indian_fee": course.indian_fee,
            "foreign_fee": course.foreign_fee,
            "image": course.course_image.url if course.course_image else "",
            "entire_overview": course.entire_overview,
            "access_description": course.access_description,
            "refund_description": course.refund_description,
            "assignment_description": course.assignment_description,
        },
        "teaching_assistants": [
            {
                "id": ta.id,
                "name": f"{ta.first_name} {ta.last_name}",
                "email": ta.email,
                "role": ta.role,
                "profile_picture": ta.profile_picture.url if ta.profile_picture else ""
            } for ta in course.teaching_assistant.all()
        ],
        "instructors": [
            {
                "id": ins.id,
                "name": f"{ins.first_name} {ins.last_name}",
                "email": ins.email,
                "role": ins.role,
                "profile_picture": ins.profile_picture.url if ins.profile_picture else ""
            } for ins in course.instructor.all()
        ],
        "sections": sections_data,
        "enrolled_user_flg": enrolled_user_flg,
        "thumbnail_flag": True if course.id == 8 else False,
        "canonical_url": request.build_absolute_uri(request.path),
    }

    return JsonResponse(data, safe=False)





#change code 24/01/26 vikas
def Admin_course_Overview(admin, course):
    """!
    @brief Helper to determine accessible sections and enrollment status for course overview.

    @param admin (Account) The user object (handles staff, superadmin, and students).
    @param course (Course) The course being analyzed.

    @return tuple (sections: QuerySet, enrolled_user: Account|EnrolledUser|UserSubscription|None)
    """

    
    # Handle anonymous users
    if not admin.is_authenticated:
        return course.section_set.all().order_by('id'), None
    
    if admin.is_superadmin or admin.is_staff:
        sections = course.section_set.all().order_by('id')

        # admin user as enrolled_user (consistent handling)
        enrolled_user = admin

    else:
        enrolled_user = EnrolledUser.objects.filter(
            course_id=course.id,
            user=admin,
            enrolled=True,
            end_at__gt=datetime.now()
        ).first()

        if not enrolled_user:
            from subscriptions.models import UserSubscription, PlanCategoryAccess
            active_subs = UserSubscription.objects.filter(user=admin, is_active=True, end_date__gt=datetime.now())
            for sub in active_subs:
                # Restriction: Subscription only covers FEATURED courses
                if course.is_featured and PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type, category=course.category).exists():
                    enrolled_user = sub
                    break

        if hasattr(enrolled_user, 'no_of_installments'):
            sections = installment_Checker(enrolled_user, course)
        elif enrolled_user:
            sections = course.section_set.all().order_by('id')
        else:
            sections = []
    return sections, enrolled_user



# @api_login_required
def course_overview(request, id, course_url):
    """!
    @brief API endpoint providing a comprehensive visual map of course sections, modules, and videos.

    @param request (Request) DRF Request object.
    @param id (int) Course Database ID.
    @param course_url (str) Course URL slug.

    @return JsonResponse Full course structure with enrollment/payment metadata (200).
    """
    # Use the correct Course field name `url_link_name` (models.Course defines `url_link_name`).
    course = get_object_or_404(Course, pk=id, url_link_name=course_url)

    # CHANGED 24 FEB 2026: Return ALL sections, not just accessible ones
    # Access control is now handled on frontend based on /sections/accessible/ API
    all_sections = course.section_set.all().order_by('id')
    
    # Still get enrolled_user for response metadata
    enrolled_user = None
    if request.user.is_authenticated:
        if request.user.is_superadmin or request.user.is_staff:
            enrolled_user = request.user
        else:
            enrolled_user = EnrolledUser.objects.filter(
                course_id=course.id,
                user=request.user,
                enrolled=True,
                end_at__gt=datetime.now()
            ).first()

            if not enrolled_user:
                from subscriptions.models import UserSubscription, PlanCategoryAccess
                active_subs = UserSubscription.objects.filter(user=request.user, is_active=True, end_date__gt=datetime.now())
                for sub in active_subs:
                    # Restriction: Subscription only covers FEATURED courses
                    if course.is_featured and PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type, category=course.category).exists():
                        enrolled_user = sub
                        break

    sections_data = []
    for section in all_sections:
        # Get modules for this section
        modules = section.module_set.all().order_by('id')
        
        # Serialize modules with their videos
        modules_data = []
        for module in modules:
            # Get all videos for this module
            videos = module.video_set.all().order_by('id')
            
            videos_data = []
            for video in videos:
                videos_data.append({
                    "id": video.id,
                    "title": video.title,
                    "link": video.link,
                    "type": video.type,
                    "duration": video.duration,
                })
            
            modules_data.append({
                "id": module.id,
                "name": module.name,
                "title": module.title,
                "videos": videos_data,
            })
        
        sections_data.append({
            "id": section.id,
            "name": section.name,
            "title": section.title,
            "part_number": section.part_number,
            "estimated_time": section.estimated_time,
            "total_assignments": section.total_assignments,
            "modules": modules_data,
        })

    enrolled_user_data = None

    if enrolled_user:
        # enrolled_user can be Account OR EnrolledUser OR UserSubscription
        if hasattr(enrolled_user, "enrolled"):
            # Calculate installment amounts based on course fee and number of installments
            def calculate_installment_amounts(course, no_of_installments):
                """Calculate individual installment amounts"""
                # Determine base fee (use Indian fee as default)
                base_fee = course.indian_fee if course.indian_fee else 0
                
                if no_of_installments == 2:
                    first_amt = base_fee / 2
                    second_amt = base_fee / 2
                    return {
                        'first': first_amt,
                        'second': second_amt,
                        'third': 0
                    }
                elif no_of_installments == 3:
                    first_amt = base_fee / 3
                    second_amt = base_fee / 3
                    third_amt = base_fee / 3
                    return {
                        'first': first_amt,
                        'second': second_amt,
                        'third': third_amt
                    }
                else:
                    return {
                        'first': base_fee,
                        'second': 0,
                        'third': 0
                    }
            
            installment_amounts = calculate_installment_amounts(course, enrolled_user.no_of_installments)
            
            enrolled_user_data = {
                "id": enrolled_user.id,
                "enrolled": enrolled_user.enrolled,
                "end_at": enrolled_user.end_at.isoformat() if enrolled_user.end_at else None,
                "full_access_flag": enrolled_user.full_access_flag,
                "no_of_installments": enrolled_user.no_of_installments,
                "first_installments": enrolled_user.first_installments,
                "second_installments": enrolled_user.second_installments,
                "third_installments": enrolled_user.third_installments,
                "first_installment_amount": installment_amounts['first'],
                "second_installment_amount": installment_amounts['second'],
                "third_installment_amount": installment_amounts['third'],
            }
        elif hasattr(enrolled_user, "plan"):
            enrolled_user_data = {
                "id": request.user.id,
                "enrolled": True,
                "end_at": enrolled_user.end_date.isoformat() if enrolled_user.end_date else None,
                "full_access_flag": True,
                "no_of_installments": 1,
                "first_installments": True,
                "second_installments": True,
                "third_installments": True,
                "first_installment_amount": 0,
                "second_installment_amount": 0,
                "third_installment_amount": 0,
            }
        else:
            # admin / staff user
            enrolled_user_data = {
                "id": enrolled_user.id,
                "role": "admin",
                "is_staff": enrolled_user.is_staff,
                "is_superuser": enrolled_user.is_superadmin,
                "enrolled": True,
                "full_access_flag": True,
                "no_of_installments": 1,
                "first_installments": True,
                "second_installments": True,
                "third_installments": True,
            }

    data = {
        "success": True,
        "course": {
            "id": course.id,
            "title": course.title,
            "level": course.level,
            "category": course.category,
        },
        "sections": sections_data,
        "enrolled_user": enrolled_user_data,
        "title": f"{course.title} | Overview",
        "canonical_url": request.build_absolute_uri(request.path),
    }

    return JsonResponse(data)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_section(request, id, course_url, section_url):
    """!
    @brief API endpoint for viewing a specific course section and its constituent modules.

    @param request (Request) DRF Request object.
    @param id (int) Course ID.
    @param course_url (str) Course URL slug.
    @param section_url (str) Section URL slug.

    @return JsonResponse Section details, modules, and locking status (200).
    """
    course = get_object_or_404(Course, pk=id, url_link_name=course_url)

    sections, enrolled_user = Admin_course_Overview(request.user, course)

    section = get_object_or_404(
        Section,
        course_id=id,
        url_name=section_url
    )

    modules = section.module_set.all().order_by('id')

    url_last_parameter = request.path.split('/')[-1]
    section_lock_flag = False

    # Section lock logic
    if course.id in [6, 8, 12]:

        if request.user.is_superadmin or request.user.is_staff:
            section_lock_flag = False

        else:
            if section.part_number != 1:
                section_lock_flag = True
                previous_part = section.part_number - 1

                previous_section = Section.objects.get(
                    part_number=previous_part,
                    course_id=course.id
                )

                assignment_count = AssignmentEvaluation.objects.filter(
                    user=request.user,
                    section_id=previous_section.id,
                    submit_flag=True
                ).count()

                if assignment_count == previous_section.total_assignments:
                    section_lock_flag = False
                    section = Section.objects.get(
                        part_number=previous_part + 1,
                        course_id=course.id
                    )

    #Serialize sections
    sections_data = [{
        "id": sec.id,
        "name": sec.name,
        "title": sec.title,
        "part_number": sec.part_number
    } for sec in sections]

    # Serialize modules
    modules_data = [{
        "id": mod.id,
        "name": mod.name,
        "title": mod.title
    } for mod in modules]

    # Enrolled user normalization
    enrolled_user_data = None
    if enrolled_user:
        if hasattr(enrolled_user, "enrolled"):
            enrolled_user_data = {
                "id": enrolled_user.id,
                "enrolled": enrolled_user.enrolled,
                "end_at": enrolled_user.end_at.isoformat() if enrolled_user.end_at else None,
                "full_access_flag": enrolled_user.full_access_flag,
            }
        else:
            enrolled_user_data = {
                "id": enrolled_user.id,
                "role": "admin",
                "is_staff": enrolled_user.is_staff,
                "is_superuser": enrolled_user.is_superadmin,
                "enrolled": True,
                "full_access_flag": True,
                "no_of_installments": 1,
                "first_installments": True,
                "second_installments": True,
                "third_installments": True,
            }

    data = {
        "success": True,
        "course": {
            "id": course.id,
            "title": course.title,
            "level": course.level,
            "category": course.category,
        },
        "sections": sections_data,
        "current_section": {
            "id": section.id,
            "name": section.name,
            "title": section.title,
            "part_number": section.part_number,
        },
        "modules": modules_data,
        "url_last_parameter": url_last_parameter,
        "enrolled_user": enrolled_user_data,
        "section_lock_flag": section_lock_flag,
        "title": f"{course.title} | {section.name}",
        "canonical_url": request.build_absolute_uri(request.path),
    }

    return JsonResponse(data)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def optional_assignments(request, id, course_url):
    """!
    @brief API endpoint to retrieve optional and elective assignments for a course.

    @param request (Request) DRF Request object.
    @param id (int) Course Database ID.
    @param course_url (str) Course URL slug.

    @return JsonResponse Serialized list of optional assignments and enrollment metadata (200).
    """
    now = datetime.now()

    course = get_object_or_404(
        Course,
        pk=id,
        url_link_name=course_url,
        optional_assignment_flg=True
    )

    enrolled_user = EnrolledUser.objects.filter(
        course_id=course.id,
        user=request.user,
        enrolled=True,
        end_at__gt=now
    ).first()

    if not enrolled_user:
        from subscriptions.models import UserSubscription, PlanCategoryAccess
        active_subs = UserSubscription.objects.filter(user=request.user, is_active=True, end_date__gt=now)
        for sub in active_subs:
            if PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type, category=course.category).exists():
                enrolled_user = sub
                break

    optional_assignments_qs = Assignment.objects.filter(
        course_id=course.id,
        assignment_type="optional"
    ).order_by('id')

    if hasattr(enrolled_user, 'no_of_installments'):
        sections = installment_Checker(enrolled_user, course)
    elif enrolled_user:
        sections = course.section_set.all().order_by('id')
    else:
        sections = []

    # 🔹 Serialize sections
    sections_data = [{
        "id": section.id,
        "name": section.name,
        "title": section.title,
        "part_number": section.part_number
    } for section in sections]

    # 🔹 Serialize optional assignments - include section_url from module -> section relationship
    optional_assignments_data = [{
        "id": assignment.id,
        "name": assignment.name,
        "assignment_type": assignment.assignment_type,
        "module_id": assignment.module_id,
        "section_url": assignment.module.section.url_name if assignment.module and assignment.module.section else "section-1",
        "pdf": assignment.pdf.url if assignment.pdf else ""
    } for assignment in optional_assignments_qs]

    # 🔹 Serialize enrolled user
    enrolled_user_data = None
    if enrolled_user:
        if hasattr(enrolled_user, 'enrolled'):
            enrolled_user_data = {
                "id": enrolled_user.id,
                "enrolled": enrolled_user.enrolled,
                "end_at": enrolled_user.end_at.isoformat() if enrolled_user.end_at else None,
                "full_access_flag": enrolled_user.full_access_flag,
                "no_of_installments": enrolled_user.no_of_installments,
            }
        elif hasattr(enrolled_user, 'plan'):
            enrolled_user_data = {
                "id": request.user.id,
                "enrolled": True,
                "end_at": enrolled_user.end_date.isoformat() if enrolled_user.end_date else None,
                "full_access_flag": True,
                "no_of_installments": 1,
            }

    data = {
        "success": True,
        "course": {
            "id": course.id,
            "title": course.title,
            "category": course.category,
            "level": course.level,
        },
        "sections": sections_data,
        "enrolled_user": enrolled_user_data,
        "optional_assignments": optional_assignments_data,
        "title": f"{course.title} | Optional Assignments",
        "canonical_url": request.build_absolute_uri(request.path),
    }

    return JsonResponse(data)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_assignments(request, id, course_url):
    """!
    @brief API endpoint to retrieve all assignments (mandatory and optional) associated with a course.
    @details Includes submission status flags for the authenticated user.

    @param request (Request) DRF Request object.
    @param id (int) Course ID.
    @param course_url (str) Course slug.

    @return JsonResponse Serialized assignment data with submission states (200).
    """
    course = get_object_or_404(Course, pk=id, url_link_name=course_url)

    now = datetime.now()
    enrolled_user = EnrolledUser.objects.filter(
        course_id=course.id,
        user=request.user,
        enrolled=True,
        end_at__gt=now
    ).first()

    # Get all assignments for the course
    assignments_qs = Assignment.objects.filter(
        course_id=course.id
    ).order_by('id')

    # Serialize assignments - include section_url from module -> section relationship
    assignments_data = [{
        "id": assignment.id,
        "name": assignment.name,
        "assignment_type": assignment.assignment_type,
        "module_id": assignment.module_id,
        "section_url": assignment.module.section.url_name if assignment.module and assignment.module.section else "section-1",
        "pdf": assignment.pdf.url if assignment.pdf else ""
    } for assignment in assignments_qs]

    # Get user's submission status for each assignment
    submissions = AssignmentEvaluation.objects.filter(
        course=course,
        user=request.user,
        submit_flag=True
    ).values_list('assignment_id', flat=True)

    # Mark assignments with submission status
    submitted_ids = set(submissions)
    for assignment in assignments_data:
        assignment['submitted'] = assignment['id'] in submitted_ids

    # Serialize enrolled user
    enrolled_user_data = None
    if enrolled_user:
        enrolled_user_data = {
            "id": enrolled_user.id,
            "enrolled": enrolled_user.enrolled,
            "end_at": enrolled_user.end_at.isoformat() if enrolled_user.end_at else None,
            "full_access_flag": enrolled_user.full_access_flag,
            "no_of_installments": enrolled_user.no_of_installments,
        }

    data = {
        "success": True,
        "course": {
            "id": course.id,
            "title": course.title,
            "category": course.category,
            "level": course.level,
        },
        "enrolled_user": enrolled_user_data,
        "assignments": assignments_data,
        "title": f"{course.title} | Assignments",
        "canonical_url": request.build_absolute_uri(request.path),
    }

    return JsonResponse(data)




class Evaluation:
    """!
    @brief Engine for automated evaluation of coding assignments across different course categories.
    @details Dynamically imports and executes course-specific evaluation scripts from specialized directories 
             (ML_Scripts, CV_1_Scripts, etc.).
    """
    
    def call_function_from_module(self,module,func_name,*args,**kwargs):
        """!
        @brief Safely calls a specific function from a dynamically loaded Python module.

        @param module The loaded module object.
        @param func_name (str) Name of the function to invoke.
        @param args Positional arguments for the target function.
        @param kwargs Keyword arguments for the target function.

        @return Any The result of the function call, or None if the function is missing or not callable.
        """
        if hasattr(module, func_name):
            func = getattr(module, func_name)
            if callable(func):
                return func(*args, **kwargs)
            else:
                return None
        else:
            return None
    
    def ML_Evaluation(self):
        spec=importlib.util.find_spec("ML_Scripts."+self.assignment)
        if spec!=None:
            module=importlib.util.module_from_spec(spec)
            sys.modules["ML_Scripts."+self.assignment] = module
            spec.loader.exec_module(module)
            eval_function=self.call_function_from_module(module,'eval',self.assign_obj)
            score=eval_function
            return score
        else:
            return None
    
    def CV_1_Evaluation(self):
        spec=importlib.util.find_spec("CV_1_Scripts."+self.assignment)
        if spec!=None:
            module=importlib.util.module_from_spec(spec)
            sys.modules["CV_1_Scripts."+self.assignment] = module
            spec.loader.exec_module(module)
            eval_function=self.call_function_from_module(module,'eval',self.assign_obj)
            score=eval_function
            return score
        else:
            return None
    
    def RL_Evaluation(self):
        spec=importlib.util.find_spec("RL_Scripts."+self.assignment)
        if spec!=None:
            module=importlib.util.module_from_spec(spec)
            sys.modules["RL_Scripts."+self.assignment] = module
            spec.loader.exec_module(module)
            eval_function=self.call_function_from_module(module,'eval',self.assign_obj)
            score=eval_function
            return score
        else:
            return None
    
    def CV_2_Evaluation(self):
        spec=importlib.util.find_spec("CV_2_Scripts."+self.assignment)
        if spec!=None:
            module=importlib.util.module_from_spec(spec)
            sys.modules["CV_2_Scripts."+self.assignment] = module
            spec.loader.exec_module(module)
            eval_function=self.call_function_from_module(module,'eval',self.assign_obj)
            score=eval_function
            return score
        else:
            return None



def AutoEvaluation(course,assignment,file_url):
    """!
    @brief High-level entry point for triggering automated grading for a student submission.

    @param course (Course) The course object containing category info.
    @param assignment (str) Name/Identifier of the assignment.
    @param file_url (str) Path or URL to the submitted source file.

    @return float|None The resulting numeric score or None if evaluation failed.
    """
    current_dir = os.getcwd()
    parent_module_path=os.path.join(current_dir,"AutoEvaluation","Evaluation_Scripts")
    sys.path.append(parent_module_path)
    
    if course.id==2:
        eval=Evaluation(assignment,file_url)
        result=eval.ML_Evaluation()
        return result
    
    elif course.id==6:
        eval=Evaluation(assignment,file_url)
        result=eval.CV_1_Evaluation()
        return result
          
    elif course.id==8:
        eval=Evaluation(assignment,file_url)
        result=eval.RL_Evaluation()
        return result
        
    else:
        eval=Evaluation(assignment,file_url)
        result=eval.CV_2_Evaluation()
        return result
    
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def course_progress(request, id, course_url, section_url, assignment_id):
    """!
    @brief API endpoint for student assignment submission.
    @details Handles multi-part file uploads, updates progress metrics, and triggers TA email notifications.

    @param request (Request) DRF Request object containing 'submitted_file'.
    @param id (int) Course ID.
    @param course_url (str) Course slug.
    @param section_url (str) Section slug.
    @param assignment_id (int) ID of the target assignment.

    @return JsonResponse Status of the submission and metadata (200).
    """

    # if request.method != "POST":
    #     return JsonResponse({
    #         "success": False,
    #         "message": "Only POST method is allowed"
    #     }, status=405)

    # Validate course exists
    course = Course.objects.filter(id=id, url_link_name=course_url).first()
    if not course:
        return JsonResponse({
            "success": False,
            "message": f"Course not found with id={id} and url={course_url}"
        }, status=404)

    # Validate section exists
    section = Section.objects.filter(course=course, url_name=section_url).first()
    if not section:
        return JsonResponse({
            "success": False,
            "message": f"Section not found: '{section_url}' for course '{course_url}'. Please check the section URL."
        }, status=404)

    # Validate assignment exists
    assignment = Assignment.objects.filter(id=assignment_id, course=course).first()
    if not assignment:
        return JsonResponse({
            "success": False,
            "message": f"Assignment not found with id={assignment_id} for course '{course_url}'"
        }, status=404)

    # Check for direct enrollment
    enrolled_user = EnrolledUser.objects.filter(
        course=course,
        user=request.user,
        enrolled=True
    ).first()

    # Check for playlist access as fallback
    has_playlist_access = False
    if not enrolled_user:
        from customplaylist.models import CustomPlaylist
        playlist_query = CustomPlaylist.objects.filter(
            user=request.user,
            is_purchased=True,
            playlist_lectures__lecture__module__section__course=course
        )
        has_playlist_access = any(not p.is_expired for p in playlist_query)

    if not enrolled_user and not has_playlist_access and not (request.user.is_superadmin or request.user.is_staff):
        return JsonResponse({
            "success": False,
            "message": "You are not enrolled in this course or playlist"
        }, status=403)

    if 'submitted_file' not in request.FILES:
        return JsonResponse({
            "success": False,
            "message": "No file uploaded"
        }, status=400)

    submitted_file = request.FILES['submitted_file']

    # Save assignment submission
    assignment_evaluation = AssignmentEvaluation.objects.create(
        course=course,
        user=request.user,
        submitted_file=submitted_file,
        assignment=assignment,
        section=section,
        submit_flag=True
    )

    # Update overall progress (non-admin users)
    if not (request.user.is_superadmin or request.user.is_staff):
        total_videos = Video.objects.filter(module__section__course=course).count()
        completed_videos = UserVideoProgress.objects.filter(
            user=request.user,
            course=course,
            completed=True
        ).count()
        video_percent = (completed_videos / total_videos) * 100 if total_videos > 0 else 0.0

        total_assignments = course.assignments or 0
        submitted_assignments = AssignmentEvaluation.objects.filter(
            course=course,
            user=request.user,
            submit_flag=True
        ).count()
        assignment_percent = (submitted_assignments / total_assignments) * 100 if total_assignments > 0 else 0.0

        if total_videos > 0 and total_assignments > 0:
            percentage = round((video_percent + assignment_percent) / 2)
        elif total_videos > 0:
            percentage = round(video_percent)
        else:
            percentage = round(assignment_percent)

        overall_progress, _ = OverallProgress.objects.get_or_create(user=request.user, course=course)
        overall_progress.progress = Decimal(percentage)
        overall_progress.save()

    # Prepare TA emails
    ta_list = list(
        course.teaching_assistant.all().values_list('email', flat=True)
    )

    # Send email to TAs
    try:
        io_file = io.BytesIO(submitted_file.read())
        io_file.seek(0)

        mail_subject = f"New Assignment Submitted by {request.user.email}"
        message = f"""
        A new assignment has been submitted.

        Student: {request.user.email}
        Course: {course.title}
        Assignment: {assignment.name}
        """

        email = EmailMessage(
            subject=mail_subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=ta_list
        )

        email.attach(
            submitted_file.name,
            io_file.read(),
            submitted_file.content_type
        )
        email.send()

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": "Assignment saved but email failed",
            "error": str(e)
        }, status=500)

    return JsonResponse({
        "success": True,
        "message": "Assignment submitted successfully",
        "data": {
            "course_id": course.id,
            "section": section.name,
            "assignment": assignment.name,
            "submitted_by": request.user.email
        }
    })




#change code 24/01/26 vikas
@permission_classes([IsAuthenticated])
@api_view(['GET'])
def course_enrollment(request, id, course_url):
    """!
    @brief API endpoint to check a user's enrollment status and retrieve current course pricing.

    @param request (Request) DRF Request object.
    @param id (int) Course Database ID.
    @param course_url (str) Course slug.

    @return JsonResponse Enrollment flags, expiration details, and fee structure (200).
    """

    course = get_object_or_404(Course, pk=id, url_link_name=course_url)



    enrolled_user = EnrolledUser.objects.filter(
        course_id=id,
        user=request.user,
        enrolled=True
    ).first()

    # Country-based fee
    if request.user.country and request.user.country.lower() == "india":
        fee = course.indian_fee
    else:
        fee = course.foreign_fee

    tax = 0
    total_amount = fee + tax

    payment_method = PaymentMethod.objects.filter(pk=3).first()

    # ============================================================
    # ENROLLMENT DETAILS: Enhanced response with expiration info
    # Added: 09 Feb 2025
    # ============================================================
    enrollment_details = {
        "is_enrolled": True if enrolled_user else False,
        "end_at": enrolled_user.end_at.strftime('%Y-%m-%d') if enrolled_user and enrolled_user.end_at else None,
        "is_expired": enrolled_user.end_at < datetime.now() if enrolled_user and enrolled_user.end_at else False,
    }

    # Check if user can repurchase (only if expired)
    can_repurchase = True
    if enrolled_user and enrolled_user.end_at and enrolled_user.end_at > datetime.now():
        can_repurchase = False

    enrollment_details["can_repurchase"] = can_repurchase

    return JsonResponse({
        "success": True,
        "data": {
            "course": {
                "id": course.id,
                "title": course.title,
                "slug": course.url_link_name
            },
            "enrolled": True if enrolled_user else False,
            "enrollment_details": enrollment_details,
            "fee": float(fee),
            "tax": float(tax),
            "total": float(total_amount),
            "razorpay_enabled": payment_method.razorpay_flag if payment_method else False,
            "canonical_url": request.build_absolute_uri(request.path)
        }
    })
    


#change code 24/01/26 vikas
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order(request, id, course_url):
    """!
    @brief API endpoint to initiate a course purchase order and generate a Razorpay order ID.

    @param request (Request) DRF Request object with billing/installment info.
    @param id (int) Course ID.
    @param course_url (str) Course slug.

    @return JsonResponse Internal order ID and Razorpay order metadata (200).
    """



    required_fields = ['address', 'city', 'state', 'zipcode']
    missing_fields = [field for field in required_fields if not request.POST.get(field)]
    if missing_fields:
        return JsonResponse({"success": False, "error": f"Missing required fields: {', '.join(missing_fields)}"}, status=400)

    course = get_object_or_404(Course, pk=id, url_link_name=course_url)

   
    can_purchase, reason, existing_enrollment = can_user_purchase_course(request.user, course)
    if not can_purchase:
        return JsonResponse({
            "success": False,
            "error": reason,
            "enrollment_details": {
                "enrolled": True,
                "end_at": existing_enrollment.end_at.strftime('%Y-%m-%d') if existing_enrollment.end_at else None,
                "message": "You are already enrolled in this course. Contact support if you believe this is an error."
            }
        }, status=400)

    post_data = request.data if hasattr(request, 'data') else request.POST
    user_country = post_data.get('country', '').strip().lower()
    
    if user_country == 'india':
        total_amount = course.indian_fee or 0
    else:
        # foreign_fee should be in INR, no conversion needed
        total_amount = course.foreign_fee or 0

    installment_option = post_data.get('installment_options', 'pay_once')
    no_of_installments = 1
    if installment_option == "pay_twice":
        payment_amount = total_amount / 2
        no_of_installments = 2
    elif installment_option == "pay_thrice":
        payment_amount = total_amount / 3
        no_of_installments = 3
    else:
        payment_amount = total_amount

    payment_amount = round(float(payment_amount), 2)

    try:
        # Create order
        order = Order.objects.create(
            user=request.user,
            course=course,
            first_name=request.user.first_name,
            last_name=request.user.last_name,
            phone=getattr(request.user, "phone_number", "") or "",
            email=request.user.email,
            address=post_data.get('address'),
            country=request.user.country or '',
            state=post_data.get('state'),
            city=post_data.get('city'),
            zipcode=post_data.get('zipcode'),
            course_amount=total_amount,  
            tax=0,
            no_of_installments=no_of_installments,
            total_amount=payment_amount
        )
        
        order.order_number = f"{date.today().strftime('%Y%m%d')}{order.id}"
        order.save()
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Failed to create order: {str(e)}"}, status=500)

    razorpay_order = None
    if payment_amount > 0:
        try:
            razorpay_order = razorpay_client.order.create({
                "amount": int(payment_amount * 100),
                "currency": "INR",
                "payment_capture": 1
            })
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Razorpay error: {str(e)}"}, status=500)

    return JsonResponse({
        "success": True,
        "message": "Order created successfully",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "total_amount": payment_amount,
            "installment_option": installment_option
        },
        "course": {
            "id": course.id,
            "title": course.title
        },
        "razorpay": razorpay_order
    })


#change code 27/01/26 vikas
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cart_summary(request, id, course_url):
    """!
    @brief API endpoint to create a course order and generate PayU transaction hashes.

    @param request (Request) DRF Request object with billing details.
    @param id (int) Course Database ID.
    @param course_url (str) Course URL slug.

    @return JsonResponse Order reference and PayU configuration (200).
    """

    course = get_object_or_404(Course, pk=id, url_link_name=course_url)

  
    can_purchase, reason, existing_enrollment = can_user_purchase_course(request.user, course)
    if not can_purchase:
        return JsonResponse({
            "success": False,
            "error": reason,
            "enrollment_details": {
                "enrolled": True,
                "end_at": existing_enrollment.end_at.strftime('%Y-%m-%d') if existing_enrollment.end_at else None,
                "message": "You are already enrolled in this course. Contact support if you believe this is an error."
            }
        }, status=400)

    try:
        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST

        order = Order.objects.create(
            user=request.user,
            course=course,
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            phone=data.get('phone'),
            email=request.user.email,
            address=data.get('address'),
            country=data.get('country'),
            state=data.get('state'),
            city=data.get('city'),
            zipcode=data.get('zipcode'),
            course_amount=data.get('course_amount'),
            tax=data.get('tax'),
            total_amount=data.get('total_amount')
        )

        current_date = date.today().strftime("%Y%m%d")
        order.order_number = f"{current_date}{order.id}"
        order.save()

        payu_data = {}
        if float(order.total_amount) > 0:
            surl = f"https://{get_current_site(request)}/courses/{course.id}/{course.url_link_name}/payment_success/{order.order_number}"
            furl = f"https://{get_current_site(request)}/courses/payment_failed/{order.order_number}"

            payu = Payu(
                settings.MERCHANT_KEY,
                settings.MERCHANT_SALT,
                surl,
                furl,
                settings.PAYU_MODE
            )

            order_details = {
                "txnid": order.order_number,
                "amount": order.total_amount,
                "firstname": order.first_name,
                "lastname": order.last_name,
                "email": order.email,
                "phone": request.user.phone_number,
                "productinfo": course.title,
                "address": order.address,
                "city": order.city,
                "state": order.state,
                "country": order.country,
                "zipcode": order.zipcode,
                "udf1": "", "udf2": "", "udf3": "", "udf4": "", "udf5": ""
            }

            payu_data = payu.transaction(**order_details)

        # JSON RESPONSE
        return JsonResponse({
            "success": True,
            "message": "Order created successfully",
            "order": {
                "id": order.id,
                "order_number": order.order_number,
                "total_amount": order.total_amount
            },
            "course": {
                "id": course.id,
                "title": course.title
            },
            "payu": payu_data
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)




#change code 27/01/26 vikas6
def check_already_user(request_user, payment_id, course_id):
    """!
    @brief Helper to update installment status for an existing enrollment.
    @details Used when a user pays a subsequent installment for a course they are already active in.

    @param request_user (Account) The student user.
    @param payment_id (str) The new payment transaction ID.
    @param course_id (int) ID of the course.

    @return JsonResponse Update confirmation and the identified installment (second/third) (200).
    """
    try:
        already_enroll = EnrolledUser.objects.get(
            user=request_user,
            course_id=course_id,
            first_installments=True
        )

        response_data = {
            "status": "success",
            "course_id": course_id,
            "payment_id": payment_id,
            "updated_installment": None
        }

        if already_enroll.no_of_installments > 1:

            if already_enroll.no_of_installments == 2:
                if not already_enroll.second_installments:
                    already_enroll.second_installments = True
                    already_enroll.installment_id_2 = payment_id
                    already_enroll.save()
                    response_data["updated_installment"] = "second"

            elif already_enroll.no_of_installments == 3:
                if not already_enroll.second_installments:
                    already_enroll.second_installments = True
                    already_enroll.installment_id_2 = payment_id
                    already_enroll.save()
                    response_data["updated_installment"] = "second"

                elif already_enroll.second_installments and not already_enroll.third_installments:
                    already_enroll.third_installments = True
                    already_enroll.installment_id_3 = payment_id
                    already_enroll.save()
                    response_data["updated_installment"] = "third"

        return JsonResponse(response_data, status=200)

    except EnrolledUser.DoesNotExist:
        return JsonResponse(
            {
                "status": "error",
                "message": "User is not enrolled in this course"
            },
            status=404
        )



#change code 27/01/26 vikas
def calculate_financial_year(order_type):
    """!
    @brief Helper to calculate the current financial year and generate a unique sequential serial number for invoices.
    @details Serial numbers are prefixed based on whether the order is free or paid.

    @param order_type (str) Either "free" or "paid".

    @return JsonResponse Financial year metadata and the generated serial number (200).
    """
    current_date = now().date()

    if current_date.month < 4:
        start_date = datetime(current_date.year - 1, 4, 1).date()
        end_date = datetime(current_date.year, 3, 31).date()
    else:
        start_date = datetime(current_date.year, 4, 1).date()
        end_date = datetime(current_date.year + 1, 3, 31).date()

    last_users = Order.objects.filter(
        created_at__gte=start_date,
        created_at__lt=end_date + timedelta(days=1),
        is_ordered=True,
        total_amount__gte=1.0
    )

    current_user_string = current_date.strftime("%d%m%Y")

    prefix = "free_" if order_type == "free" else ""

    if last_users.count() == 0:
        enroll_count = 1
    else:
        enroll_count = last_users.count() + 1

    result_string = f"{prefix}{current_user_string}.{enroll_count}"

    return JsonResponse({
        "status": "success",
        "order_type": order_type,
        "financial_year": {
            "start_date": start_date,
            "end_date": end_date
        },
        "current_date": current_date,
        "total_orders_this_year": last_users.count(),
        "generated_order_code": result_string
    }, status=200)



#change code 27/01/26 vikas
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payment_done(request, id, course_url, order_id):
    """!
    @brief API endpoint to verify Razorpay payment signatures and finalize student enrollment.
    @details Handles both free and paid courses. For paid courses, verifies hashes and amount authenticity 
             via Razorpay API before spawning EnrolledUser and Invoice_Registrant records.

    @param request (Request) DRF Request with 'razorpay_payment_id', 'razorpay_order_id', and 'razorpay_signature'.
    @param id (int) Course Database ID.
    @param course_url (str) Course URL slug.
    @param order_id (str) Order number cross-reference.

    @return JsonResponse Final enrollment status, transaction info, and invoice number (200).
    """



    try:
        order = get_object_or_404(Order, order_number=order_id)
        course = get_object_or_404(Course, pk=id, url_link_name=course_url)

        if order.total_amount == 0:
            payment = Payment.objects.create(
                user=request.user,
                payment_id=f"order_{order.order_number}",
                payment_method="Free",
                amount_paid=0,
                status="Completed"
            )

            order.payment = payment
            order.is_ordered = True
            order.save()

            serial_no = calculate_financial_year("free")

            enrolled_user = EnrolledUser.objects.create(
                user=request.user,
                course=course,
                course_price=0,
                enrolled=True,
                payment=payment,
                order=order,
                end_at=datetime.now() + relativedelta(months=course.duration),
                no_of_installments=1
            )

            Invoice_Registrant.objects.create(
                name=enrolled_user,
                order=order,
                serial_no=serial_no
            )

            OverallProgress.objects.create(
                course_id=course.id,
                user=request.user,
                progress=0
            )

            request.user.courses_enrolled += 1
            request.user.save()

            course.enrolled_users += 1
            course.save()

            return JsonResponse({
                "success": True,
                "message": "Free course enrolled successfully",
                "order_number": order.order_number,
                "payment_method": "Free",
                "invoice_no": serial_no
            }, status=200)

        # ================= PAID COURSE =================
        payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        signature = request.POST.get('razorpay_signature')

        if not payment_id or not razorpay_order_id or not signature:
            return JsonResponse({
                "success": False,
                "message": "Missing Razorpay parameters"
            }, status=400)

        try:
            params_dict = {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            }
            razorpay_client.utility.verify_payment_signature(params_dict)
        except Exception as sig_error:
            return JsonResponse({
                "success": False,
                "message": "Payment signature verification failed",
                "error": str(sig_error)
            }, status=400)

        try:
            razorpay_amount = razorpay_client.payment.fetch(payment_id)["amount"] / 100
        except Exception as fetch_error:
            return JsonResponse({
                "success": False,
                "message": "Failed to fetch payment details",
                "error": str(fetch_error)
            }, status=400)

        if razorpay_amount > order.total_amount:
            return JsonResponse({
                "success": False,
                "message": "Invalid payment amount"
            }, status=400)

        payment = Payment.objects.create(
            user=request.user,
            payment_id=payment_id,
            payment_method="RazorPay",
            amount_paid=razorpay_amount,
            status="Completed"
        )

        order.payment = payment
        order.is_ordered = True
        order.save()

        # ===== Installment check =====
        already_user = EnrolledUser.objects.filter(
            user=request.user,
            course=id,
            first_installments=True
        )

        serial_no_response = calculate_financial_year("paid")
        # Extract serial_no from JsonResponse
        if hasattr(serial_no_response, 'content'):
            import json
            serial_no_data = json.loads(serial_no_response.content)
            serial_no = serial_no_data.get('generated_order_code', f"INV-{order.order_number}")
        else:
            serial_no = f"INV-{order.order_number}"

        if already_user.exists():
            # Update installment status for returning users
            already_enroll = already_user.first()
            if already_enroll and already_enroll.no_of_installments > 1:
                if already_enroll.no_of_installments == 2:
                    if not already_enroll.second_installments:
                        already_enroll.second_installments = True
                        already_enroll.installment_id_2 = payment_id
                        already_enroll.save()
                elif already_enroll.no_of_installments == 3:
                    if not already_enroll.second_installments:
                        already_enroll.second_installments = True
                        already_enroll.installment_id_2 = payment_id
                        already_enroll.save()
                    elif already_enroll.second_installments and not already_enroll.third_installments:
                        already_enroll.third_installments = True
                        already_enroll.installment_id_3 = payment_id
                        already_enroll.save()
            
            enrolled_user = already_user.first()

        else:
            # Use the number of installments stored in the order
            no_of_installments = getattr(order, 'no_of_installments', 1)

            course_price = (
                course.indian_fee if order.country.upper() in ["INDIA", "IN"]
                else course.foreign_fee
            )

            enrolled_user = EnrolledUser.objects.create(
                user=request.user,
                course=course,
                course_price=course_price,
                enrolled=True,
                payment=payment,
                order=order,
                end_at=datetime.now() + relativedelta(months=course.duration),
                no_of_installments=no_of_installments,
                first_installments=True
            )

            OverallProgress.objects.create(
                course_id=course.id,
                user=request.user,
                progress=0
            )

            request.user.courses_enrolled += 1
            request.user.save()

            course.enrolled_users += 1
            course.save()

        invoice_reg = Invoice_Registrant.objects.create(
            name=enrolled_user,
            order=order,
            serial_no=serial_no
        )

        # Generate and store professional PDF for first payment (match installment flow)
        try:
            from course.invoice_generator import generate_professional_invoice
            from django.core.files.base import ContentFile

            pdf_bytes = generate_professional_invoice(
                order=order,
                item=enrolled_user,
                payment=payment,
                installment_number=1,
                invoice_type='course'
            )

            pdf_filename = f"Invoice_{order.order_number}_{str(payment.payment_id)[:8]}.pdf"
            invoice_reg.invoice.save(pdf_filename, ContentFile(pdf_bytes), save=True)
        except Exception:
            pass

        # ✅ SEND EMAIL TO ADMIN FOR FIRST PAYMENT
        try:
            from django.template.loader import render_to_string
            from django.core.mail import EmailMessage
            from django.conf import settings

            mail_list = ['sunil.roat@deepeigen.com']
            
            # Determine installment text based on no_of_installments
            if enrolled_user.no_of_installments == 1:
                installment_text = "Full payment received (1 of 1)"
            elif enrolled_user.no_of_installments == 2:
                installment_text = "First installment paid (1 of 2)"
            else:
                installment_text = "First installment paid (1 of 3)"
            
            mail_subject = f"Invoice Generated - {course.title} - New User Enrollment"
            
            message = render_to_string('invoice/invoice_mail.html', {
                'title_heading': 'New User Enrollment',
                'top_heading': f"A new user has successfully enrolled in {course.title}.",
                'firstname': request.user.first_name,
                'lastname': request.user.last_name,
                'course': course.title,
                'orderid': payment_id,
                'installment_info': installment_text
            })
            
            email = EmailMessage(mail_subject, message, settings.EMAIL_HOST_USER, mail_list)
            email.content_subtype = "html"
            email.send()
            
        except Exception:
            # Don't fail payment if email fails
            pass

        return JsonResponse({
            "success": True,
            "message": "Payment successful",
            "order_number": order.order_number,
            "payment_id": payment_id,
            "amount_paid": razorpay_amount,
            "invoice_no": serial_no,
            "course": course.title
        }, status=200)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": "Payment verification failed",
            "error": str(e)
        }, status=400)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order_manually(request):
    """!
    @brief API endpoint for administrative manual enrollment of a user into a course.
    @details Bypasses standard Razorpay/PayU automated flows by allowing manual payment ID entry 
             and immediate enrollment record creation. Restricted to admin use in practice.

    @param request (Request) DRF Request containing 'user' (email), 'courseId', and 'payment_id'.

    @return JsonResponse Summary of the manual enrollment and generated invoice number (200).
    """

    # if request.method != "POST":
    #     return JsonResponse({
    #         "success": False,
    #         "message": "Only POST method allowed"
    #     }, status=405)

    try:
        course_amount = float(request.POST.get("course_amount", 0))
        order_number = request.POST.get("order_number")
        course_id = request.POST.get("courseId")
        user_email = request.POST.get("user")
        payment_id = request.POST.get("payment_id")
        installment_option = request.POST.get("installment_options", "1")

        # ===== Validate =====
        if not all([order_number, course_id, user_email, payment_id]):
            return JsonResponse({
                "success": False,
                "message": "Missing required fields"
            }, status=400)

        course = Course.objects.get(id=course_id)
        user = Account.objects.get(email=user_email)

        # ===== Installment count =====
        no_of_installments = int(installment_option) if installment_option in ["1", "2", "3"] else 1

        # ===== Order =====
        order, created = Order.objects.get_or_create(
            order_number=order_number,
            defaults={
                "user": user,
                "course": course,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone_number,
                "email": user.email,
                "address": request.POST.get("address"),
                "country": user.country,
                "state": request.POST.get("state"),
                "city": request.POST.get("city"),
                "zipcode": request.POST.get("zipcode"),
                "course_amount": course_amount,
                "tax": request.POST.get("tax", 0),
                "total_amount": course_amount,
                "is_ordered": False
            }
        )

        # ===== Payment =====
        if Payment.objects.filter(payment_id=payment_id).exists():
            return JsonResponse({
                "success": False,
                "message": "Payment ID already exists"
            }, status=409)

        payment_method = "Free" if course_amount == 0 else "RazorPay"

        payment = Payment.objects.create(
            user=user,
            payment_id=payment_id,
            payment_method=payment_method,
            amount_paid=course_amount,
            status="Completed"
        )

        order.payment = payment
        order.is_ordered = True
        order.save()

        # ===== Enrollment =====
        already_user = EnrolledUser.objects.filter(
            user=user,
            course=course,
            first_installments=True
        )

        serial_no = calculate_financial_year("free" if course_amount == 0 else "paid")

        if already_user.exists():
            check_already_user(user.id, payment_id, course_id)
            enrolled_user = already_user.first()
        else:
            enrolled_user = EnrolledUser.objects.create(
                user=user,
                course=course,
                course_price=course_amount,
                enrolled=True,
                payment=payment,
                order=order,
                end_at=now() + relativedelta(months=course.duration),
                no_of_installments=no_of_installments,
                first_installments=True
            )

            OverallProgress.objects.create(
                course_id=course.id,
                user=user,
                progress=0
            )

            user.courses_enrolled += 1
            user.save()

            course.enrolled_users += 1
            course.save()

        # ===== Invoice =====
        Invoice_Registrant.objects.create(
            name=enrolled_user,
            order=order,
            serial_no=serial_no
        )

        # Generate and store professional PDF for manual order enrollment
        try:
            from course.invoice_generator import generate_professional_invoice
            from django.core.files.base import ContentFile

            pdf_bytes = generate_professional_invoice(
                order=order,
                item=enrolled_user,
                payment=payment,
                installment_number=1,
                invoice_type='course'
            )

            pdf_filename = f"Invoice_{order.order_number}_{str(payment.payment_id)[:8]}.pdf"
            # Fetch the Invoice_Registrant we just created to attach PDF
            invoice_reg_obj = Invoice_Registrant.objects.filter(name=enrolled_user, order=order).first()
            if invoice_reg_obj:
                invoice_reg_obj.invoice.save(pdf_filename, ContentFile(pdf_bytes), save=True)
        except Exception:
            pass

        # ===== Success JSON =====
        return JsonResponse({
            "success": True,
            "message": "User enrolled successfully",
            "order_number": order.order_number,
            "payment_id": payment.payment_id,
            "payment_method": payment.payment_method,
            "amount_paid": payment.amount_paid,
            "installments": no_of_installments,
            "invoice_no": serial_no,
            "course": {
                "id": course.id,
                "title": course.title
            },
            "user": {
                "id": user.id,
                "email": user.email
            }
        }, status=200)

    except Account.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "User not found"
        }, status=404)

    except Course.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Course not found"
        }, status=404)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": "Internal server error",
            "error": str(e)
        }, status=500)



#change code 27/01/26
@api_view(['POST'])
@permission_classes([AllowAny])
def payment_success(request):
    """!
    @brief Callback endpoint for successful automated PayU payment processing.
    @details Processes the PayU server-to-server POST response, verifies order integrity, 
             and triggers student enrollment upon confirmation.

    @param request (Request) POST data payload from PayU.

    @return JsonResponse Enrollment confirmation and transaction summary (200).
    """

    # The @api_view(['POST']) decorator already handles method checking.
    # The id, course_url, order_id parameters should be extracted from request.data or request.POST
    # For PayU, data is usually in request.POST

    # Extract parameters from request.POST or request.data
    # Assuming these are passed as form data or query params in the callback URL
    # You might need to adjust how these are received based on PayU's callback structure
    id = request.POST.get('id') # Or from URL if still needed, but usually passed in POST data
    course_url = request.POST.get('course_url') # Or from URL
    order_id = request.POST.get('order_id') # Or from URL

    if not all([id, course_url, order_id]):
        return JsonResponse({
            "success": False,
            "error": "Missing required parameters: id, course_url, order_id"
        }, status=400)

    order = get_object_or_404(Order, order_number=order_id)
    course = get_object_or_404(Course, pk=id, url_link_name=course_url)

    try:
        # PayU sends form-data
        payu_data = {k: v[0] for k, v in dict(request.POST).items()}
        ordered_amount = "{:.2f}".format(order.total_amount)

        # ---------- PAID COURSE ----------
        if order.total_amount > 0 and ordered_amount == payu_data.get('amount'):

            user = Account.objects.get(email=payu_data.get('email'))

            payment = Payment.objects.create(
                user=user,
                payment_id=f"order_{order.order_number}",
                payment_method="payU",
                amount_paid=payu_data.get('amount'),
                status="Completed"
            )

            order.payment = payment
            order.is_ordered = True
            order.save()

            enrolled_user = EnrolledUser.objects.create(
                user=user,
                course=course,
                order=order,
                payment=payment,
                enrolled=True,
                course_price=payu_data.get('amount'),
                end_at=datetime.now() + relativedelta(months=course.duration)
            )

            OverallProgress.objects.create(
                course=course,
                user=user,
                progress=0
            )

            user.courses_enrolled += 1
            user.save()

            course.enrolled_users += 1
            course.save()

            return JsonResponse({
                "success": True,
                "message": "Payment successful and user enrolled",
                "order": {
                    "order_number": order.order_number,
                    "amount": payment.amount_paid,
                    "status": order.status
                },
                "course": {
                    "id": course.id,
                    "title": course.title
                },
                "user": {
                    "id": user.id,
                    "email": user.email
                }
            })

        # ---------- FREE COURSE ----------
        elif order.total_amount == 0:

            # For free courses, the user should be authenticated.
            # If this is a PayU callback for a free course, it's unusual.
            # Assuming request.user is available if the user was logged in when initiating the free order.
            # If not, you might need to get the user from the order or PayU data.
            if not request.user.is_authenticated:
                # Attempt to get user from order if not authenticated
                user = Account.objects.get(email=order.email)
            else:
                user = request.user

            payment = Payment.objects.create(
                user=user,
                payment_id=f"order_{order.order_number}",
                payment_method="Free",
                amount_paid=0,
                status="Completed"
            )

            order.payment = payment
            order.is_ordered = True
            order.save()

            enrolled_user = EnrolledUser.objects.create(
                user=user,
                course=course,
                order=order,
                payment=payment,
                enrolled=True,
                course_price=0,
                end_at=datetime.now() + relativedelta(months=course.duration)
            )

            OverallProgress.objects.create(
                course=course,
                user=user,
                progress=0
            )

            user.courses_enrolled += 1
            user.save()

            course.enrolled_users += 1
            course.save()

            return JsonResponse({
                "success": True,
                "message": "Free course enrolled successfully",
                "order": {
                    "order_number": order.order_number,
                    "amount": 0
                },
                "course": {
                    "id": course.id,
                    "title": course.title
                }
            })

        # ---------- AMOUNT MISMATCH ----------
        else:
            return JsonResponse({
                "success": False,
                "error": "Payment amount mismatch"
            }, status=400)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)







@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payment_failed(request, order_id):
    """!
    @brief API endpoint to handle and record transaction failures reported by payment gateways.

    @param request (Request) DRF Request object.
    @param order_id (str) Order number associated with the failed session.

    @return JsonResponse Negative acknowledgement for frontend UX handling (200).
    """

    try:
        order = get_object_or_404(Order, order_number=order_id)
        user = Account.objects.get(email=order.email)

        return JsonResponse({
            "success": False,
            "message": "Payment failed",
            "order": {
                "order_id": order.order_number,
                "total_amount": order.total_amount,
                "is_ordered": order.is_ordered
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": f"{user.first_name} {user.last_name}"
            }
        }, status=400)

    except Account.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "User associated with this order not found"
        }, status=404)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": "Internal server error",
            "error": str(e)
        }, status=500)



#change code 27/01/26 vikas
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manual_user_registration(request):
    """!
    @brief API endpoint for administrative manual user registration and course attribution.
    @details GET: Provides master data (courses, users, orders, enrollments) for management dashboards.
             POST: Handles specific manual registration registration logic for a single student.

    @param request (Request) DRF Request object.

    @return JsonResponse Master data for admin dashboard (GET) or registration result (POST) (200/201).
    """

    # Permission check
    if not (request.user.is_staff or request.user.is_superadmin):
        return JsonResponse({
            "success": False,
            "message": "You must be a staff member or super admin to access this API"
        }, status=403)

    if request.method == "GET":
        courses = Course.objects.all()
        users = Account.objects.filter(is_active=True)
        orders = Order.objects.all()
        payments = Payment.objects.all()
        enrolled_users = EnrolledUser.objects.all()

        return JsonResponse({
            "success": True,
            "data": {
                "courses": [
                    {
                        "id": course.id,
                        "title": course.title,
                        "indian_fee": course.indian_fee,
                        "foreign_fee": course.foreign_fee
                    } for course in courses
                ],
                "users": [
                    {
                        "id": user.id,
                        "email": user.email,
                        "full_name": f"{user.first_name} {user.last_name}",
                        "is_active": user.is_active
                    } for user in users
                ],
                "orders": [
                    {
                        "id": order.id,
                        "order_number": order.order_number,
                        "total_amount": order.total_amount,
                        "is_ordered": order.is_ordered
                    } for order in orders
                ],
                "payments": [
                    {
                        "id": payment.id,
                        "payment_id": payment.payment_id,
                        "method": payment.payment_method,
                        "amount_paid": payment.amount_paid,
                        "status": payment.status
                    } for payment in payments
                ],
                "enrolled_users": [
                    {
                        "id": enroll.id,
                        "user_id": enroll.user.id,
                        "course_id": enroll.course.id,
                        "no_of_installments": enroll.no_of_installments,
                        "first_installments": enroll.first_installments,
                        "second_installments": enroll.second_installments,
                        "third_installments": enroll.third_installments
                    } for enroll in enrolled_users
                ]
            }
        }, status=200)

    elif request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")

        if not username or not email:
            return JsonResponse({
                "success": False,
                "message": "username and email are required"
            }, status=400)

        return JsonResponse({
            "success": True,
            "message": f"User {username} registered successfully"
        }, status=201)

    return JsonResponse({
        "success": False,
        "message": "Method not allowed"
    }, status=405)


#change done 27/01/26 vikas
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_orders(request):
    """!
    @brief API endpoint to retrieve all course order records for administrative auditing.

    @param request (Request) DRF Request object.

    @return JsonResponse List of all raw order objects from the database (200).
    """
    orders = list(Order.objects.all().values())  
    return JsonResponse({'orders': orders})


# ============================================================
# Payment API Endpoint for Processing Installments
# POST /course/payment/
# Accepts: course_id, installment_number, amount, currency
# Returns: Payment session URL or success message
# Added: 10 Feb 2026
# ============================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payment_installment(request):
    """!
    @brief API endpoint to initiate a payment session for a specific course installment (2nd or 3rd).
    @details Recalculates the proportional amount based on the user's country-specific course fee 
             and the number of installments in their plan.

    @param request (Request) DRF Request containing 'course_id' and 'installment_number'.

    @return JsonResponse Razorpay session data tailored for the specific installment (200).
    """
    # Check authentication
    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "message": "Authentication required. Please log in.",
            "status": 401
        }, status=401)
    
    if request.method != 'POST':
        return JsonResponse({
            "success": False,
            "message": "Method not allowed. Use POST.",
            "status": 405
        }, status=405)

    try:
        import json
        data = json.loads(request.body)
        
        course_id = data.get('course_id')
        installment_number = data.get('installment_number')  # 1, 2 or 3
        amount = data.get('amount')
        
        # Validate required fields (but amount will be recalculated)
        if not all([course_id, installment_number]):
            return JsonResponse({
                "success": False,
                "message": "Missing required fields: course_id, installment_number",
                "status": 400
            }, status=400)
        
        # Get course
        course = Course.objects.filter(id=course_id).first()
        if not course:
            return JsonResponse({
                "success": False,
                "message": f"Course with ID {course_id} not found",
                "status": 404
            }, status=404)
        
        # Get enrollment
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
        
        # Check if enrollment is still active
        if enrollment.end_at and enrollment.end_at < timezone.now():
            return JsonResponse({
                "success": False,
                "message": "Your course enrollment has expired",
                "status": 403
            }, status=403)
        
        # Validate installment number
        if installment_number not in [1, 2, 3]:
            return JsonResponse({
                "success": False,
                "message": "Invalid installment number. Must be 1, 2 or 3",
                "status": 400
            }, status=400)
        
        # Check if installment is already paid
        if installment_number == 1 and enrollment.first_installments:
            return JsonResponse({
                "success": False,
                "message": "First installment already paid",
                "status": 400
            }, status=400)
        
        if installment_number == 2 and enrollment.second_installments:
            return JsonResponse({
                "success": False,
                "message": "Second installment already paid",
                "status": 400
            }, status=400)
        
        if installment_number == 3 and enrollment.third_installments:
            return JsonResponse({
                "success": False,
                "message": "Third installment already paid",
                "status": 400
            }, status=400)
        
        user_country = getattr(request.user, 'country', 'India') or 'India'
        is_india = user_country.lower() in ['india', 'in']
        
        base_fee = course.indian_fee if is_india else course.foreign_fee
        
        standard_installment = round(base_fee / enrollment.no_of_installments, 2)
        
        if installment_number < enrollment.no_of_installments:
            installment_amount = standard_installment
        else:
            installment_amount = base_fee - (standard_installment * (enrollment.no_of_installments - 1))
        
        currency = 'INR' if is_india else '$'
        
        currency = 'INR' if is_india else '$'
        
        original_order = enrollment.order if enrollment.order else None
        
        order = Order.objects.create(
            user=request.user,
            course=course,
            first_name=original_order.first_name if original_order else (request.user.first_name or 'User'),
            last_name=original_order.last_name if original_order else (request.user.last_name or 'Payment'),
            phone=original_order.phone if original_order else (getattr(request.user, 'phone_number', '') or '0000000000'),
            email=request.user.email,
            address=original_order.address if original_order else 'Installment Payment',
            country=original_order.country if original_order else user_country,
            state=original_order.state if original_order else 'Online',
            city=original_order.city if original_order else 'Online',
            zipcode=original_order.zipcode if original_order else '000000',
            course_amount=float(installment_amount),
            tax=0,
            total_amount=float(installment_amount),
            status='New'
        )
        
        order.order_number = f"{date.today().strftime('%Y%m%d')}{order.id}"
        order.save()
        
        if is_india:
            amount_in_smallest = int(float(installment_amount) * 100)
            razorpay_currency = 'INR'
        else:
            amount_in_smallest = int(float(installment_amount) * 100)
            razorpay_currency = 'USD'
        
        razorpay_order = razorpay_client.order.create({
            'amount': amount_in_smallest,
            'currency': razorpay_currency,
            'receipt': f'order_{order.id}_{installment_number}',
            'payment_capture': 1,
        })
        
        order.razorpay_order_id = razorpay_order['id']
        order.save()
        
        return JsonResponse({
            "success": True,
            "message": f"Payment session created for installment {installment_number}",
            "status": 200,
            "data": {
                "razorpay_order_id": razorpay_order['id'],
                "razorpay_key": settings.RAZORPAY_API_KEY,
                "amount": amount_in_smallest,
                "currency": razorpay_currency,
                "customer_name": request.user.first_name or request.user.username,
                "customer_email": request.user.email,
                "order_id": order.id,
                "course_id": course_id,
                "installment_number": installment_number,
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid JSON in request body",
            "status": 400
        }, status=400)
    
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"Error processing payment: {str(e)}",
            "status": 500
        }, status=500)


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from django.db import transaction
from course.models import Course, EnrolledUser, Payment, Order
import json
import hmac
import hashlib


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payment_verify(request):
    """!
    @brief API endpoint to verify a Razorpay installment payment (2nd or 3rd installment).
    @details Validates the HMAC signature, updates the Enrollment installment status, 
             generates a professional PDF invoice, and sends a notification email to the finance team.

    @param request (Request) DRF Request with 'payment_id', 'order_id', 'signature', and 'installment_number'.

    @return JsonResponse Verification result and verified transaction metadata (200).
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "message": "Authentication required. Please log in.",
            "status": 401
        }, status=401)

    if request.method != 'POST':
        return JsonResponse({"success": False}, status=405)

    try:
        import json
        import hmac
        import hashlib
        from django.conf import settings

        data = json.loads(request.body)

        payment_id = data.get('payment_id')
        razorpay_order_id = data.get('order_id')
        signature = data.get('signature')
        course_id = data.get('course_id')
        installment_number = int(data.get('installment_number'))
        amount = float(data.get('amount', 0))

        message = f"{razorpay_order_id}|{payment_id}"

        message = f"{razorpay_order_id}|{payment_id}"
        expected_signature = hmac.new(
            settings.RAZORPAY_API_SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        if signature != expected_signature:
            return JsonResponse({
                "success": False,
                "message": "Payment signature verification failed"
            }, status=401)

        course = Course.objects.filter(id=course_id).first()
        if not course:
            return JsonResponse({"success": False, "message": "Course not found"}, status=404)

        enrollment = EnrolledUser.objects.filter(
            user=request.user,
            course=course,
            enrolled=True
        ).first()

        if not enrollment:
            return JsonResponse({"success": False, "message": "Enrollment not found"}, status=404)

 
        if installment_number == 1 and enrollment.first_installments:
            return JsonResponse({"success": False, "message": "First installment already paid"}, status=400)

        if installment_number == 2 and enrollment.second_installments:
            return JsonResponse({"success": False, "message": "Second installment already paid"}, status=400)

        if installment_number == 3 and enrollment.third_installments:
            return JsonResponse({"success": False, "message": "Third installment already paid"}, status=400)

     
        payment = Payment.objects.create(
            user=request.user,
            payment_id=payment_id,
            payment_method='razorpay',
            amount_paid=amount,
            status='Completed'
        )


        if installment_number == 1:
            enrollment.payment = payment
            enrollment.first_installments = True

        elif installment_number == 2:
            enrollment.installment_id_2 = payment_id
            enrollment.second_installments = True

        elif installment_number == 3:
            enrollment.installment_id_3 = payment_id
            enrollment.third_installments = True

        else:
            return JsonResponse({"success": False, "message": "Invalid installment number"}, status=400)

        enrollment.save()

  
        installment_order = Order.objects.filter(
            razorpay_order_id=razorpay_order_id
        ).first()

        if installment_order:
            installment_order.payment = payment
            installment_order.status = 'Completed'
            installment_order.is_ordered = True
            installment_order.save()

            try:
                serial_no_response = calculate_financial_year("paid")
                serial_no = None
                if hasattr(serial_no_response, 'content'):
                    serial_no_data = json.loads(serial_no_response.content)
                    serial_no = serial_no_data.get('generated_order_code', f"INV-{installment_order.order_number}")
                else:
                    serial_no = f"INV-{installment_order.order_number}"

                from course.invoice_generator import generate_professional_invoice
                
                pdf_bytes = generate_professional_invoice(
                    order=installment_order,
                    item=enrollment,
                    payment=payment,
                    installment_number=installment_number,
                    invoice_type='course'
                )

                from django.core.files.base import ContentFile
                pdf_filename = f"Invoice_{installment_order.order_number}_{payment.payment_id[:8]}.pdf"

                invoice_registrant = Invoice_Registrant.objects.create(
                    name=enrollment,
                    order=installment_order,
                    serial_no=serial_no
                )
                invoice_registrant.invoice.save(pdf_filename, ContentFile(pdf_bytes), save=True)

                try:
                    from django.template.loader import render_to_string
                    from django.core.mail import EmailMessage
                    from django.conf import settings

                    mail_list = ['sunil.roat@deepeigen.com']
                    
                    if installment_number == 1:
                        installment_text = f"First installment paid (1 of {enrollment.no_of_installments})"
                    elif installment_number == 2:
                        installment_text = f"Second installment paid (2 of {enrollment.no_of_installments})"
                    else:
                        installment_text = f"Final installment paid ({enrollment.no_of_installments} of {enrollment.no_of_installments})"
                    
                    mail_subject = f"Invoice Generated - {enrollment.course.title} - Installment {installment_number}"
                    
                    message = render_to_string('invoice/invoice_mail.html', {
                        'title_heading': 'Installment Payment Received',
                        'top_heading': f"A user has successfully paid installment {installment_number} for {enrollment.course.title}.",
                        'firstname': request.user.first_name,
                        'lastname': request.user.last_name,
                        'course': enrollment.course.title,
                        'orderid': payment_id,
                        'installment_info': installment_text
                    })
                    
                    email = EmailMessage(mail_subject, message, settings.EMAIL_HOST_USER, mail_list)
                    email.content_subtype = "html"
                    email.send()
                    
                except Exception:
                    pass

            except Exception:
                pass

        original_order = enrollment.order
        return JsonResponse({
            "success": True,
            "message": f"Installment {installment_number} verified successfully.",
            "data": {
                "payment_id": payment_id,
                "installment_number": installment_number,
                "order_number": installment_order.order_number if installment_order else None,
                "original_order_number": original_order.order_number if original_order else None,
                "serial_no": serial_no if installment_order else None
            }
        }, status=200)

    except Exception as e:
        print(" PAYMENT VERIFY ERROR:", str(e))
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)




@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def download_assignment_pdf(request, id, course_url, assignment_id):
    """!
    @brief Secure API endpoint for serving course assignment PDF files with access control.
    @details Verifies active enrollment, subscription, or playlist access before streaming 
             the file. Sets specific headers to prevent browser caching and ensure file integrity.

    @param request (Request) DRF Request object.
    @param id (int) Course Database ID.
    @param course_url (str) Course URL slug.
    @param assignment_id (int) ID of the target assignment.

    @return FileResponse Serving the PDF binary stream (200) or JsonResponse for access denied (403).
    """
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "message": "Authentication required"},
            status=401
        )

    course = get_object_or_404(Course, pk=id, url_link_name=course_url)

    is_enrolled = EnrolledUser.objects.filter(user=request.user, course=course, enrolled=True).exists()
    has_playlist_access = False
    if not is_enrolled:
        from customplaylist.models import CustomPlaylist
        playlist_query = CustomPlaylist.objects.filter(
            user=request.user,
            is_purchased=True,
            playlist_lectures__lecture__module__section__course=course
        )
        has_playlist_access = any(not p.is_expired for p in playlist_query)

    if not is_enrolled and not has_playlist_access and not (request.user.is_superadmin or request.user.is_staff):
        return JsonResponse(
            {"success": False, "message": "Access denied. Enrollment required."},
            status=403
        )

    assignment = get_object_or_404(Assignment, id=assignment_id, course=course)

    if not assignment.pdf:
        return JsonResponse(
            {"success": False, "message": "No PDF file available"},
            status=404
        )

    try:
        pdf_path = assignment.pdf.path
    except Exception as e:
        return JsonResponse(
            {"success": False, "message": f"Error getting PDF path: {str(e)}"},
            status=500
        )

    if not pdf_path or not os.path.exists(pdf_path):
        return JsonResponse(
            {"success": False, "message": "PDF not found on server"},
            status=404
        )

    try:
        file_size = os.path.getsize(pdf_path)
        if file_size == 0:
            return JsonResponse(
                {"success": False, "message": "PDF file is empty"},
                status=400
            )

        pdf_file = open(pdf_path, 'rb')
        
        content_type, _ = mimetypes.guess_type(pdf_path)
        if not content_type:
            content_type = 'application/octet-stream'
            
        response = FileResponse(
            pdf_file,
            content_type=content_type
        )
        
        _, extension = os.path.splitext(pdf_path)
        if not extension:
            extension = '.pdf' # Fallback
            
        safe_filename = "".join(c for c in assignment.name if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_filename}{extension}"
        response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}'
        response['Content-Length'] = file_size
        
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response
        
    except IOError as e:
        return JsonResponse(
            {"success": False, "message": "Error reading PDF file"},
            status=500
        )



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_video_progress(request):
    """!
    @brief API endpoint to record or update student progress on a specific instructional video.
    @details Implements 'sticky' completion logic. If a video is marked completed, it remains 
             completed. Triggers a recalculation of the user's OverallProgress for the course.

    @param request (Request) POST containing 'video_id', 'course_id', and 'completed' (bool).

    @return JsonResponse Status of the progress update and calculated completion percentage (200).
    """
    global logger
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a POST request.',
            'status': 405
        }, status=405)

    try:
        import json
        data = json.loads(request.body)
        
        video_id = data.get('video_id')
        course_id = data.get('course_id')
        section_id = data.get('section_id')
        completed = data.get('completed', False)
        
        if not video_id or not course_id:
            return JsonResponse({
                'success': False,
                'message': 'video_id and course_id are required',
                'status': 400
            }, status=400)
        
        # Get the video, course, and section objects
        try:
            video = Video.objects.get(id=video_id)
            course = Course.objects.get(id=course_id)
            section = Section.objects.get(id=section_id) if section_id else Section.objects.first()
        except Video.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Video not found',
                'status': 404
            }, status=404)
        except Course.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Course not found',
                'status': 404
            }, status=404)
        
        # Check if progress already exists, update or create
        # CHANGE 11 JUNE 2026: 'Sticky' completion - once True, stay True
        progress = UserVideoProgress.objects.filter(user=request.user, video=video).first()
        
        if progress:
            new_completed = True if progress.completed else completed
            progress.course = course
            progress.section = section
            progress.completed = new_completed
            progress.save()
            created = False
        else:
            progress = UserVideoProgress.objects.create(
                user=request.user,
                video=video,
                course=course,
                section=section,
                completed=completed
            )
            created = True
        logger.info(f"[SAVE_PROGRESS] user={request.user.id} video={video.id} course={course.id} completed={completed} created={created}")

            # Update OverallProgress for video completion
        if completed:
                total_videos = Video.objects.filter(module__section__course=course).count()
                completed_videos = UserVideoProgress.objects.filter(user=request.user, course=course, completed=True).count()
                video_percent = (completed_videos / total_videos) * 100 if total_videos > 0 else 0

                total_assignments = course.assignments or 0
                submitted_assignments = AssignmentEvaluation.objects.filter(
                    course=course,
                    user=request.user,
                    submit_flag=True,
                ).count()
                assignment_percent = (submitted_assignments / total_assignments) * 100 if total_assignments > 0 else 0

                if total_videos > 0 and total_assignments > 0:
                    percentage = round((video_percent + assignment_percent) / 2)
                elif total_videos > 0:
                    percentage = round(video_percent)
                else:
                    percentage = round(assignment_percent)

                from decimal import Decimal
                overall_progress, _ = OverallProgress.objects.get_or_create(user=request.user, course=course)
                overall_progress.progress = Decimal(percentage)
                overall_progress.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Video progress saved successfully',
            'status': 200,
            'data': {
                'video_id': video.id,
                'video_title': video.title,
                'course_id': course.id,
                'course_title': course.title,
                'course_url': course.url_link_name,
                'section_id': section.id if section else None,
                'section_url': section.url_name if section else '',
                'completed': progress.completed,
            }
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
            'message': f'Error saving video progress: {str(e)}',
            'status': 500
        }, status=500)


# @login_required(login_url='login')
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_video_progress(request, course_id):
    """!
    @brief API endpoint to retrieve a student's comprehensive video completion progress for a course.

    @param request (Request) DRF Request object.
    @param course_id (int) ID of the course.

    @return JsonResponse List of completed videos and aggregate completion percentage (200).
    """
    global logger

    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed. Please send a GET request.',
            'status': 405
        }, status=405)

    try:
        course = Course.objects.get(id=course_id)
        
        total_videos = Video.objects.filter(module__section__course=course).count()
        logger.info(f"[GET_PROGRESS] course={course.id} total_videos={total_videos}")

        completed_qs = UserVideoProgress.objects.filter(
            user=request.user,
            course=course,
            completed=True
        ).select_related('video')

        completed_count = completed_qs.count()
        logger.info(f"[GET_PROGRESS] user={request.user.id} completed_count={completed_count}")

        if total_videos > 0:
            completion_percentage = round((completed_count / total_videos) * 100)
        else:
            completion_percentage = 0
        logger.info(f"[GET_PROGRESS] completion_percentage={completion_percentage}")

        completed_videos = [
            {
                'video_id': progress.video.id,
                'video_title': progress.video.title,
                'completed_at': progress.created_at.isoformat() if progress.created_at else None
            }
            for progress in completed_qs
        ]

        return JsonResponse({
            'success': True,
            'message': 'Video progress retrieved successfully',
            'status': 200,
            'data': {
                'course_id': course.id,
                'course_title': course.title,
                'total_videos': total_videos,
                'completed_count': completed_count,
                'completion_percentage': completion_percentage,
                'completed_videos': completed_videos,
            }
        }, status=200)

    except Course.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Course not found',
            'status': 404
        }, status=404)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error getting video progress',
            'status': 500
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def custom_plan_assignments(request, id, course_url):
    """!
    @brief API endpoint to calculate the pro-rated number of assignments accessible to a custom playlist user.
    @details Formula: allowed_count = ceil((selected_lectures / total_lectures) * total_assessments).
             Ensures users only access assessments corresponding to the specific portion of the course 
             they have purchased.

    @param request (Request) DRF Request with 'selected_lecture_ids'.
    @param id (int) Course Database ID.
    @param course_url (str) Course URL slug.

    @return JsonResponse Proportional assignment list and calculation audit log (200).
    """
    import math
    
    # if request.method != 'POST':
    #     return JsonResponse({
    #         'success': False,
    #         'message': 'Method not allowed. Please send a POST request.',
    #         'status': 405
    #     }, status=405)

    try:
        course = get_object_or_404(Course, pk=id, url_link_name=course_url)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON in request body',
                'status': 400
            }, status=400)
        
        selected_lecture_ids = data.get('selected_lecture_ids', [])
        
        if not isinstance(selected_lecture_ids, list):
            return JsonResponse({
                'success': False,
                'message': 'selected_lecture_ids must be an array',
                'status': 400
            }, status=400)
        
        total_lectures = Video.objects.filter(module__section__course=course).count()
        
        total_assessments = course.assignments if course.assignments else 0
        
        all_assessments = list(Assignment.objects.filter(course=course).order_by('id'))
        
        selected_count = len(selected_lecture_ids)
        
        if total_lectures > 0 and total_assessments > 0:
            allowed_count = math.ceil((selected_count / total_lectures) * total_assessments)
        else:
            allowed_count = 0
        
        allowed_count = min(allowed_count, len(all_assessments))
        
        allowed_assessments = all_assessments[:allowed_count]
        
        assessments_data = []
        for assignment in allowed_assessments:
            assessments_data.append({
                'id': assignment.id,
                'name': assignment.name,
                'assignment_type': assignment.assignment_type,
                'module_id': assignment.module_id,
                'section_url': assignment.module.section.url_name if assignment.module and assignment.module.section else "section-1",
                'pdf': assignment.pdf.url if assignment.pdf else ""
            })
        
        if request.user.is_authenticated:
            submissions = AssignmentEvaluation.objects.filter(
                course=course,
                user=request.user,
                submit_flag=True
            ).values_list('assignment_id', flat=True)
            
            submitted_ids = set(submissions)
            for assignment in assessments_data:
                assignment['submitted'] = assignment['id'] in submitted_ids
        
        return JsonResponse({
            'success': True,
            'status': 200,
            'data': {
                'total_lectures': total_lectures,
                'selected_lectures': selected_count,
                'total_assessments': total_assessments,
                'allowed_assessments': allowed_count,
                'calculation': {
                    'formula': 'ceil((selected_lectures / total_lectures) * total_assessments)',
                    'example': f'ceil(({selected_count} / {total_lectures}) * {total_assessments}) = {allowed_count}'
                },
                'assessments': assessments_data
            }
        }, status=200)
    
    except Exception:
        return JsonResponse({
            'success': False,
            'message': 'Error fetching custom plan assessments',
            'status': 500
        }, status=500)
