import json
import hmac
import hashlib
from decimal import Decimal
import razorpay
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import CustomPlaylist, PlaylistLecture
from course.models import Video, EnrolledUser, Course
from subscriptions.models import UserSubscription, PlanCategoryAccess
from django.utils import timezone

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET_KEY)
)


def get_lecture_pricing_and_ownership(user, lecture, duration, user_enrolled_courses=None, user_purchased_lectures=None):
    """!
    @brief Calculates the dynamic proportional price and verifies ownership for a single lecture.
    @details Implements logic to prevent double-charging by checking course-level enrollment 
             and individual playlist-level purchases.
    @note Price calculation: (Course Fee / Total Lectures) * (Selected Duration / Course Duration)

    @param user (Account) The user requesting the pricing.
    @param lecture (Video) The specific lecture to price.
    @param duration (int) Selected access duration in months.
    @param user_enrolled_courses (list) Pre-fetched list of owned course IDs for optimization.
    @param user_purchased_lectures (list) Pre-fetched list of owned lecture IDs for optimization.

    @return tuple (Decimal: price, bool: already_owned)
    """
    course = lecture.module.section.course
    
    # Ownership Check (Course level)
    if user_enrolled_courses is not None:
        is_course_owned = course.id in user_enrolled_courses
    else:
        is_course_owned = course.id in get_all_owned_course_ids(user)
        
    # Ownership Check (Individual lecture level)
    if user_purchased_lectures is not None:
        is_lecture_owned = lecture.id in user_purchased_lectures
    else:
        is_lecture_owned = PlaylistLecture.objects.filter(
            playlist__user=user, 
            playlist__is_purchased=True, 
            lecture=lecture
        ).exists()
        
    already_owned = bool(is_course_owned or is_lecture_owned)
    
    # Detect user country
    user_country = getattr(user, 'country', '') or ''
    is_indian = user_country.lower() == 'india' or user_country.upper() == 'IN'
    
    course_fee = Decimal(str(
        course.indian_fee if is_indian
        else (course.foreign_fee or course.indian_fee or 0)
    ))
    course_duration = Decimal(str(course.duration or 1))
    
    total_lectures = Video.objects.filter(module__section__course=course).count()
    
    if already_owned:
        lecture_price = Decimal('0.00')
    elif total_lectures > 0:
        # Formula: (Course Fee / Total Lectures) * (Selected Duration / Course Duration) * 1.01 (1% Premium Markup)
        base_lecture_price = course_fee / Decimal(total_lectures)
        lecture_price = base_lecture_price * (Decimal(duration) / course_duration) * Decimal('1.01')
    else:
        lecture_price = Decimal('0.00')
            
    return lecture_price, already_owned




def get_allowed_assignments(user, lecture_ids):
    """!
    @brief Calculates the proportional assignment quota accessible for a given set of lectures.
    @details Aggregates selected lectures by course and applies the ceiling formula to determine 
             authorized assessment access.
    @note Limit calculation: ceil((selected_count / total_lectures) * total_assessments)

    @param user (Account) The student user for submission verification.
    @param lecture_ids (list) Collection of target video IDs.

    @return list Structured assignment metadata including submission status.
    """
    import math
    from course.models import Assignment, Video, Course, AssignmentEvaluation
    
    selected_lectures = Video.objects.filter(id__in=lecture_ids).select_related('module__section__course')
    
    # Group lectures by course
    course_lecture_map = {}
    for lecture in selected_lectures:
        course_id = lecture.module.section.course_id
        if course_id not in course_lecture_map:
            course_lecture_map[course_id] = []
        course_lecture_map[course_id].append(lecture.id)
        
    allowed_assignments = []
    
    for course_id, selected_ids in course_lecture_map.items():
        course = Course.objects.get(id=course_id)
        total_lectures = Video.objects.filter(module__section__course_id=course_id).count()
        total_assessments = course.assignments if course.assignments else 0
        all_course_assignments = list(Assignment.objects.filter(course_id=course_id).order_by('id'))
        
        selected_count = len(selected_ids)
        
        if total_lectures > 0 and total_assessments > 0:
            allowed_count = math.ceil((selected_count / total_lectures) * total_assessments)
        else:
            allowed_count = 0
            
        allowed_count = min(allowed_count, len(all_course_assignments))
        course_subset = all_course_assignments[:allowed_count]
        
        for assignment in course_subset:
            # Check for existing submission
            is_submitted = AssignmentEvaluation.objects.filter(
                user=user, 
                assignment=assignment
            ).exists()

            allowed_assignments.append({
                'id': assignment.id,
                'name': assignment.name,
                'assignment_type': assignment.assignment_type,
                'module_id': assignment.module_id,
                'section_url': assignment.module.section.url_name if assignment.module and assignment.module.section else "section-1",
                'pdf': assignment.pdf.url if assignment.pdf else "",
                'course_title': course.title,
                'course_id': course.id,
                'course_url': course.url_link_name,
                'submitted': is_submitted
            })
            
    return allowed_assignments


def get_all_owned_course_ids(user):
    """!
    @brief Aggregates all course IDs authorized for a user via multiple access channels.
    @details Consolidates direct single-course enrollments and indirect subscription-based 
             category authorizations.

    @param user (Account) The target user.

    @return list Unified collection of accessible course primary keys.
    """
    owned_ids = set()
    
    # 1. Single course purchases
    enrolled_courses = EnrolledUser.objects.filter(
        user=user, enrolled=True
    ).values_list("course_id", flat=True)
    owned_ids.update(enrolled_courses)
    
    # 2. Subscription courses
    active_subs = UserSubscription.objects.filter(
        user=user, is_active=True, end_date__gte=timezone.now()
    )
    if active_subs.exists():
        plan_types = active_subs.values_list("plan__plan_type", flat=True)
        allowed_categories = PlanCategoryAccess.objects.filter(
            plan_type__in=plan_types
        ).values_list("category", flat=True)
        sub_course_ids = Course.objects.filter(
            category__in=allowed_categories
        ).values_list("id", flat=True)
        owned_ids.update(sub_course_ids)
        
    return list(owned_ids)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_custom_playlist(request):
    """!
    @brief API endpoint to initialize a new user-defined CustomPlaylist record.
    @details Performs real-time pricing calculations for the bundle, accounting for lecture 
             counts, access timeframe, and optional assignment access.

    @param request (Request) DRF Request with 'title', 'lecture_ids', and 'duration'.

    @return Response Collection metadata including calculated total_price and playlist_id (201).
    """
    try:
        data = request.data
        title = data.get('title')
        description = data.get('description', '')
        lecture_ids = data.get('lecture_ids', [])
        include_assignments = data.get('include_assignments', False)
        duration_val = data.get('duration', 1)
        
        # Convert duration to integer (months)
        try:
            if isinstance(duration_val, str):
                parts = duration_val.lower().split()
                val = int(parts[0])
                duration = val * 12 if 'year' in duration_val.lower() else val
            else:
                duration = int(duration_val)
        except (ValueError, IndexError):
            duration = 1

        if not title:
            return Response({'success': False, 'message': 'Title is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not lecture_ids:
            return Response({'success': False, 'message': 'At least one lecture must be selected.'}, status=status.HTTP_400_BAD_REQUEST)

        total_price = Decimal('0.00')
        lectures_details = []
        
        # Optimization: Get ownership info once
        user_enrolled_courses = get_all_owned_course_ids(request.user)
        
        valid_playlist_ids = [
            p.id for p in CustomPlaylist.objects.filter(user=request.user, is_purchased=True)
            if not p.is_expired
        ]
        user_purchased_lectures = PlaylistLecture.objects.filter(
            playlist_id__in=valid_playlist_ids
        ).values_list("lecture_id", flat=True)

        for l_id in lecture_ids:
            try:
                lecture = Video.objects.get(id=l_id)
                
                # Use helper for consistency
                lecture_price, already_owned = get_lecture_pricing_and_ownership(
                    request.user, lecture, duration, 
                    user_enrolled_courses, user_purchased_lectures
                )
                
                total_price += lecture_price
                lectures_details.append({
                    'lecture': lecture,
                    'price': lecture_price
                })
                
            except Video.DoesNotExist:
                continue

        if include_assignments:
            allowed_assignments = get_allowed_assignments(request.user, lecture_ids)
            total_price += Decimal('100.00') * len(allowed_assignments)  # assignment price is fixed, not per month

        # Create Playlist
        playlist = CustomPlaylist.objects.create(
            user=request.user,
            title=title,
            description=description,
            total_price=total_price.quantize(Decimal('0.01')),
            include_assignments=include_assignments,
            duration=duration
        )

        for item in lectures_details:
            PlaylistLecture.objects.create(playlist=playlist, lecture=item['lecture'])

        return Response({
            'success': True, 
            'message': 'Custom playlist created successfully', 
            'playlist_id': playlist.id,
            'total_price': float(playlist.total_price),
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
\



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview_custom_playlist(request):
    """!
    @brief API endpoint for pre-purchase financial audit and breakdown of a custom bundle.
    @details Provides student-facing transparency by listing per-lecture costs and 
             total pro-rated assignment accessibility.

    @param request (Request) DRF Request with 'lecture_ids' and 'duration'.

    @return Response Breakdown of costs and authorized metadata (200).
    """
    try:
        data = request.data
        lecture_ids = data.get('lecture_ids', [])
        duration_val = data.get('duration', 1)
        
        # Convert duration to integer (months)
        try:
            if isinstance(duration_val, str):
                parts = duration_val.lower().split()
                val = int(parts[0])
                duration = val * 12 if 'year' in duration_val.lower() else val
            else:
                duration = int(duration_val)
        except (ValueError, IndexError):
            duration = 1

        if not lecture_ids:
            return Response({
                'success': False,
                'message': 'No lectures selected.',
            }, status=status.HTTP_400_BAD_REQUEST)

        total_price = Decimal('0.00')
        breakdown = []

        # Optimization: Get ownership info once
        user_enrolled_courses = get_all_owned_course_ids(request.user)
        
        valid_playlist_ids = [
            p.id for p in CustomPlaylist.objects.filter(user=request.user, is_purchased=True)
            if not p.is_expired
        ]
        user_purchased_lectures = PlaylistLecture.objects.filter(
            playlist_id__in=valid_playlist_ids
        ).values_list("lecture_id", flat=True)

        include_assignments = data.get('include_assignments', False)

        for l_id in lecture_ids:
            try:
                lecture = Video.objects.get(id=l_id)
                
                # Use helper for consistency
                lecture_price, already_owned = get_lecture_pricing_and_ownership(
                    request.user, lecture, duration, 
                    user_enrolled_courses, user_purchased_lectures
                )

                total_price += lecture_price

                breakdown.append({
                    "id": lecture.id,
                    "title": lecture.title,
                    "course": lecture.module.section.course.title,
                    "price": float(lecture_price.quantize(Decimal('0.01')))
                })

            except Video.DoesNotExist:
                continue
        
        # Assignments base
        assignments_data = []
        if include_assignments:
            assignments_data = get_allowed_assignments(request.user, lecture_ids)
            total_price += Decimal('100.00') * len(assignments_data)  # assignment price is fixed, not per month

        return Response({
            "success": True,
            "total_price": float(total_price.quantize(Decimal('0.01'))),
            "breakdown": breakdown,
            "selected_duration": duration,
            "assignments_count": len(assignments_data),
            "assignments": assignments_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "message": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_playlist_payment(request, playlist_id):
    """!
    @brief API endpoint to finalize bundle price and spawn a Razorpay Order for a playlist.
    @details Recalculates the exact amount at the final step to ensure sync with dynamic 
             membership and duration changes.

    @param request (Request) DRF Request with current 'duration'.
    @param playlist_id (int) Target playlist database ID.

    @return Response Razorpay order initialization payload (200).
    """
    try:
        data = request.data
        duration_val = data.get('duration', '1 Month')
        
        # Convert duration to integer (months)
        try:
            if isinstance(duration_val, str):
                parts = duration_val.lower().split()
                val = int(parts[0])
                duration = val * 12 if 'year' in duration_val.lower() else val
            else:
                duration = int(duration_val)
        except (ValueError, IndexError):
            duration = 1
        
        playlist = get_object_or_404(CustomPlaylist, id=playlist_id, user=request.user)
        
        if playlist.is_purchased:
            return Response({'success': False, 'message': 'Playlist already purchased.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 🔹 Re-calculate Amount to ensure it's accurate at time of payment
        new_total_price = Decimal('0.00')
        
        # Optimization: Get ownership info once
        user_enrolled_courses = get_all_owned_course_ids(request.user)
        
        valid_playlist_ids = [
            p.id for p in CustomPlaylist.objects.filter(user=request.user, is_purchased=True)
            if not p.is_expired
        ]
        user_purchased_lectures = PlaylistLecture.objects.filter(
            playlist_id__in=valid_playlist_ids
        ).values_list("lecture_id", flat=True)

        for pl in playlist.playlist_lectures.all():
            lecture = pl.lecture
            
            # Use helper for consistency
            lecture_price, already_owned = get_lecture_pricing_and_ownership(
                request.user, lecture, duration, 
                user_enrolled_courses, user_purchased_lectures
            )
            
            new_total_price += lecture_price

        # Assignments base
        if playlist.include_assignments:
            # 100 per assignment per month (duration)
            l_ids = [pl.lecture.id for pl in playlist.playlist_lectures.all()]
            assignments_data = get_allowed_assignments(request.user, l_ids)
            new_total_price += Decimal('100.00') * len(assignments_data)  # assignment price is fixed, not per month
            
        total_amount = float(new_total_price.quantize(Decimal('0.01')))
        
        # Update playlist with potentially new total and duration
        playlist.total_price = new_total_price
        playlist.duration = duration
        playlist.save()
            
        # Detect user country for currency
        user_country = getattr(request.user, 'country', '') or ''
        is_indian = user_country.lower() == 'india' or user_country.upper() == 'IN'
        currency = 'INR' if is_indian else 'USD'
        
        # Razorpay amount in paise
        amount_in_paise = int(total_amount * 100)
        
        # 🔹 Create Razorpay Order
        razorpay_order = razorpay_client.order.create({
            'amount': amount_in_paise,
            'currency': currency,
            'receipt': f'cp_order_{playlist.id}',
            'payment_capture': 1
        })
        
        # Save order_id to playlist
        playlist.order_id = razorpay_order['id']
        from datetime import date
        playlist.order_number = f"{date.today().strftime('%Y%m%d')}{playlist.id}"
        playlist.status = 'pending'
        playlist.save()
        
        return Response({
            'success': True,
            'data': {
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_key': settings.RAZORPAY_API_KEY,
                'amount': amount_in_paise,
                'currency': currency,
                'customer_name': f"{request.user.first_name} {request.user.last_name}",
                'customer_email': request.user.email,
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_playlist_payment(request, playlist_id):
    """!
    @brief Secure verification endpoint for Custom Playlist fulfillment via Razorpay.
    @details Cryptographically validates signatures, updates enrollment flags, 
             creates administrative accounting records, and triggers professional invoice generation.

    @param request (Request) DRF Request with Razorpay verification bundle.
    @param playlist_id (int) ID of the purchased personalized bundle.

    @return Response Success acknowledgement and post-purchase confirmation (200).
    """
    try:
        data = request.data
        payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        signature = data.get('razorpay_signature')
        
        if not all([payment_id, razorpay_order_id, signature]):
             return Response({'success': False, 'message': 'Missing verification data'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 🔹 Verify Signature
        message = f"{razorpay_order_id}|{payment_id}"
        expected_signature = hmac.new(
            settings.RAZORPAY_API_SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected_signature:
            return Response({'success': False, 'message': 'Payment verification failed'}, status=status.HTTP_401_UNAUTHORIZED)
            
        playlist = get_object_or_404(CustomPlaylist, id=playlist_id, user=request.user)
        
        # 🔹 Mark as purchased
        playlist.is_purchased = True
        playlist.status = 'purchased'
        playlist.payment_id = payment_id
        playlist.save()
        
        # 🔹 Create Payment and Order Records for accounting
        from course.models import Payment, Order
        
        payment = Payment.objects.create(
            user=request.user,
            payment_id=payment_id,
            payment_method="Razorpay",
            amount_paid=float(playlist.total_price),
            status="Completed"
        )
        
        order = Order.objects.create(
            user=request.user,
            payment=payment,
            custom_playlist=playlist,
            order_number=playlist.order_number or f"{playlist.id}",
            first_name=request.user.first_name,
            last_name=request.user.last_name,
            email=request.user.email,
            phone=getattr(request.user, 'phone_number', ''),
            address="",
            country=getattr(request.user, 'country', ''),
            state="",
            city="",
            course_amount=float(playlist.total_price),
            tax=0.0,
            total_amount=float(playlist.total_price),
            razorpay_order_id=razorpay_order_id,
            status="Completed",
            is_ordered=True
        )
        
        # - Create Invoice Record and Generate PDF
        from .models import Invoice
        from course.invoice_generator import generate_professional_invoice
        from django.core.files.base import ContentFile

        p_invoice, created = Invoice.objects.get_or_create(
            playlist=playlist,
            payment_id=payment_id,
            defaults={
                'user': request.user,
                'playlist_name': playlist.title,
                'amount': playlist.total_price,
                'purchase_type': "Custom Playlist"
            }
        )

        try:
            pdf_content = generate_professional_invoice(
                order=order,
                item=playlist,
                payment=payment,
                invoice_type='playlist'
            )
            filename = f"Invoice_{playlist.id}_{payment_id[-6:]}.pdf"
            p_invoice.invoice_file.save(filename, ContentFile(pdf_content), save=True)
        except Exception as inv_err:
            print(f"Error generating playlist invoice: {inv_err}")
            # We don't fail the payment verification if invoice generation fails,
            # but we log it. It can be generated on-the-fly later.
        
        return Response({
            'success': True, 
            'message': 'Playlist purchased successfully.',
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_playlists(request):
    """!
    @brief API endpoint to retrieve all active, non-expired playlists for a student.
    @details Filters out legacy purchases past their validity window and calculates 
             live assignment access for each active bundle.

    @param request (Request) DRF Request object.

    @return Response Collection of playlist metadata and nested lecture/assignment lists (200).
    """
    try:
        playlists = CustomPlaylist.objects.filter(
            user=request.user,
            is_purchased=True
        ).order_by('-created_at')

        data = []

        for p in playlists:
            if p.is_expired:
                continue
            lectures = []
            for pl in p.playlist_lectures.all():
                lecture = pl.lecture
                lecture_item = {
                    'id': lecture.id,
                    'title': lecture.title,
                    'link': lecture.link,
                    'duration': lecture.duration,
                    'course': lecture.module.section.course.title,
                }
                lectures.append(lecture_item)

            # Proportional Assignments
            assignments = []
            if p.include_assignments:
                l_ids = [l.lecture_id for l in p.playlist_lectures.all()]
                assignments = get_allowed_assignments(request.user, l_ids)

            data.append({
                'id': p.id,
                'title': p.title,
                'description': p.description,
                'total_price': float(p.total_price),
                'include_assignments': p.include_assignments,
                'created_at': p.created_at.isoformat(),
                'lectures': lectures,
                'assignments': assignments,
                'assignments_count': len(assignments)
            })

        return Response({
            'success': True,
            'playlists': data,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_playlist_details(request, playlist_id):
    """!
    @brief API endpoint for deep inspection of a specific Custom Playlist.
    @details Provides lecture-by-lecture audit, duration tracking, and owner identification 
             for specialized frontend views.

    @param request (Request) DRF Request object.
    @param playlist_id (int) Target playlist database ID.

    @return Response Granular playlist object with nested content and pricing history (200).
    """
    try:
        playlist = get_object_or_404(CustomPlaylist, id=playlist_id, user=request.user)
        if playlist.is_expired:
            return Response({'success': False, 'message': 'This playlist has expired.'}, status=status.HTTP_403_FORBIDDEN)
        
        duration = playlist.duration or 1
        
        # Optimization: Get ownership info once
        user_enrolled_courses = get_all_owned_course_ids(request.user)
        
        valid_playlist_ids = [
            p.id for p in CustomPlaylist.objects.filter(user=request.user, is_purchased=True)
            if not p.is_expired
        ]
        user_purchased_lectures = PlaylistLecture.objects.filter(
            playlist_id__in=valid_playlist_ids
        ).values_list("lecture_id", flat=True)
        
        lectures = []
        for pl in playlist.playlist_lectures.all():
            lecture = pl.lecture
            
            # Use helper for consistency
            lecture_price, already_owned = get_lecture_pricing_and_ownership(
                request.user, lecture, duration, 
                user_enrolled_courses, user_purchased_lectures
            )
            
            lectures.append({
                'id': lecture.id,
                'title': lecture.title,
                'duration': lecture.duration,
                'videoUrl': lecture.link,
                'course': lecture.module.section.course.title,
                'course_id': lecture.module.section.course.id,
                'course_url': lecture.module.section.course.url_link_name,
                'section_url': lecture.module.section.url_name,
                'price': float(lecture_price.quantize(Decimal('0.01')))
            })

        # Proportional Assignments
        assignments = []
        if playlist.include_assignments:
            l_ids = [l.lecture_id for l in playlist.playlist_lectures.all()]
            assignments = get_allowed_assignments(request.user, l_ids)

        return Response({
            'success': True,
            'playlist': {
                'id': playlist.id,
                'title': playlist.title,
                'description': playlist.description,
                'total_price': float(playlist.total_price),
                'include_assignments': playlist.include_assignments,
                'duration': playlist.duration,
                'is_purchased': playlist.is_purchased,
                'created_at': playlist.created_at.isoformat(),
                'lectures': lectures,
                'assignments': assignments,
                'assignments_count': len(assignments)
            },
            'user': {
                'name': f"{request.user.first_name} {request.user.last_name}",
                'email': request.user.email,
            },
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)