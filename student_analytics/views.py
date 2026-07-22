"""
views.py — Student Analytics API views (DELS edition, consolidated)

Everything the dashboard needs lives in this one file now:
  - the original overview/course/activity/leaderboard/performance/streak/history views
  - the new DELS endpoints from spec §5 (dels detail, dels breakdown,
    per-enrollment metrics, follow-through) — previously split across
    delsviews.py / dels_views.py, now merged in here.

All computation is imported from utils.py — no scoring logic lives here.
"""
from datetime import timedelta

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AssignmentActivity,
    DailyLearningActivity,
    DELSSnapshot,
    LectureActivity,
    StudentAnalytics,
    StudentCourseAnalytics,
)
from .serializers import (
    DailyLearningActivitySerializer,
    LectureActivitySerializer,
    StudentAnalyticsSerializer,
    StudentCourseAnalyticsSerializer,
)
from .utils import (
    build_student_overview_summary,
    compute_dels_preview,
    compute_follow_through,
    computeAQS,
    computeASR,
    computeATS,
    computeECI,
    computeMPA,
    computeOAB,
    computePALC,
    get_started_course_assignment_analytics,
    recalculate_user_streak,
    tier_for,
)


def _is_self_or_staff(request, user_id):
    if str(user_id).lower() == "me":
        return True
    try:
        return int(user_id) == request.user.id or request.user.is_staff
    except (ValueError, TypeError):
        return False


def _resolve_target_user(request, user_id):
    if str(user_id).lower() == "me":
        return request.user
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        uid = int(user_id)
        if uid == request.user.id:
            return request.user
        return get_object_or_404(User, id=uid)
    except (ValueError, TypeError):
        return request.user


# ─────────────────────────────────────────────────────────────────────────
# Existing dashboard views
# ─────────────────────────────────────────────────────────────────────────
class OverviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        analytics, _ = StudentAnalytics.objects.get_or_create(user=request.user)
        return Response(StudentAnalyticsSerializer(analytics).data)


class CourseAnalyticsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        try:
            ca = StudentCourseAnalytics.objects.get(user=request.user, course_id=course_id)
            return Response(StudentCourseAnalyticsSerializer(ca).data)
        except StudentCourseAnalytics.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class ActivityAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        activities = DailyLearningActivity.objects.filter(user=request.user).order_by('-date')[:30]
        return Response(DailyLearningActivitySerializer(activities, many=True).data)


class LeaderboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # overall_performance_score is the DELS value (0-1000), written
        # nightly by `python manage.py compute_dels` — ordering is unchanged.
        top = StudentAnalytics.objects.order_by('-overall_performance_score')[:10]
        return Response([
            {
                "rank": i + 1,
                "user_id": s.user.id,
                "name": f"{s.user.first_name} {s.user.last_name}",
                "score": s.overall_performance_score
            }
            for i, s in enumerate(top)
        ])


class PerformanceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        analytics, _ = StudentAnalytics.objects.get_or_create(user=request.user)
        recalculate_user_streak(request.user, analytics=analytics)

        # Ensure analytics tables are in sync with raw course data
        # (safety net for missed signals + first load after deployment)
        from .utils import sync_user_analytics
        analytics = sync_user_analytics(request.user)

        started_course_assignment_analytics = get_started_course_assignment_analytics(request.user)
        assignments_submitted = started_course_assignment_analytics['assignments_submitted']
        admin_reviewed_count = started_course_assignment_analytics['assignments_reviewed']
        pending_review_count = started_course_assignment_analytics['assignments_pending_review']

        total_study_minutes = DailyLearningActivity.objects.filter(user=request.user).aggregate(
            total=Sum('study_time')
        )['total'] or 0.0
        analytics.total_study_minutes = total_study_minutes
        analytics.save()

        course_analytics_qs = StudentCourseAnalytics.objects.filter(user=request.user).select_related('course')
        courses_data = []
        lecture_completion_total = 0.0
        course_count = 0

        for c in course_analytics_qs:
            course_count += 1
            lecture_total = c.total_lectures or 0
            lecture_percent = round((c.completed_lectures / lecture_total) * 100, 1) if lecture_total else 0.0
            lecture_completion_total += lecture_percent

            courses_data.append({
                'course_id': c.course.id,
                'course_title': c.course.title,
                'completion': c.completion_percentage,
                'course_status': c.course_status,
                'assignment_average': round(c.assignment_average, 1),
                'videos_completed': c.completed_lectures,
                'total_lectures': c.total_lectures or c.course.section_set.aggregate(total=Count('module__video'))['total'] or 0,
                'completed_assignments': c.completed_assignments,
                # course_performance_score is CCS*10 (0-1000), written by compute_dels
                'course_performance_score': round(c.course_performance_score, 0),
                'course_max_score': 1000,
                'purchase_date': c.purchase_date.isoformat() if c.purchase_date else None,
                'started_date': c.access_start_date.isoformat() if c.access_start_date else None,
                'expected_completion_date': c.expected_completion_date.isoformat() if c.expected_completion_date else None,
                'actual_completion_date': c.actual_completion_date.isoformat() if c.actual_completion_date else None,
                'lecture_completion_percent': lecture_percent,
                'modules': [],
            })

        # ── Purchased vs subscribed courses ─────────────────────────────
        from course.models import EnrolledUser, Course
        from subscriptions.models import UserSubscription, PlanCategoryAccess

        enrolled_course_ids = set(
            EnrolledUser.objects.filter(user=request.user, enrolled=True)
            .values_list('course_id', flat=True)
        )

        purchased_courses = len(enrolled_course_ids)
        purchased_courses_completed = StudentCourseAnalytics.objects.filter(
            user=request.user,
            course_id__in=enrolled_course_ids,
            course_status='Completed'
        ).count()

        active_sub = UserSubscription.objects.filter(
            user=request.user, is_active=True, end_date__gte=timezone.now()
        ).select_related('plan').order_by('-start_date').first()

        subscription_info = None
        subscribed_course_ids = set()
        if active_sub:
            sub_categories = list(
                PlanCategoryAccess.objects.filter(plan_type=active_sub.plan.plan_type)
                .values_list('category', flat=True)
            )
            sub_qs = Course.objects.filter(category__in=sub_categories, is_featured=True)
            subscribed_course_ids = set(sub_qs.values_list('id', flat=True)) - enrolled_course_ids
            subscription_info = {
                'plan': active_sub.plan.plan_type,
                'duration': active_sub.plan.duration_type,
                'start_date': active_sub.start_date.isoformat(),
                'end_date': active_sub.end_date.isoformat(),
            }

        subscribed_courses = len(subscribed_course_ids)
        subscribed_courses_completed = StudentCourseAnalytics.objects.filter(
            user=request.user,
            course_id__in=subscribed_course_ids,
            course_status='Completed'
        ).count() if subscribed_course_ids else 0

        subscribed_courses_started = StudentCourseAnalytics.objects.filter(
            user=request.user,
            course_id__in=subscribed_course_ids,
            course_status__in=['In Progress', 'Completed']
        ).count() if subscribed_course_ids else 0

        avg_lecture_percent = round(lecture_completion_total / course_count, 1) if course_count else 0.0

        # ── DELS: live preview for display (the nightly batch job owns the persisted value) ──
        dels_result = compute_dels_preview(request.user)

        summary = build_student_overview_summary(
            analytics,
            total_courses_purchased=analytics.total_courses_purchased,
            assignments_reviewed=admin_reviewed_count,
            assignments_pending=pending_review_count,
            assignments_submitted=assignments_submitted,
            total_lectures_completed=analytics.total_lectures_completed,
            total_modules_completed=analytics.total_modules_completed,
            lecture_completion_percent=avg_lecture_percent,
            total_assignments=started_course_assignment_analytics['total_assignments'],
            assignment_progress_percentage=started_course_assignment_analytics['assignment_progress_percentage'],
            assignment_average_performance=started_course_assignment_analytics['assignment_average_performance'],
            dels_result=dels_result,
        )
        summary.update(started_course_assignment_analytics)
        summary['assignment_average'] = started_course_assignment_analytics['assignment_average_performance']

        summary['purchased_courses'] = purchased_courses
        summary['purchased_courses_completed'] = purchased_courses_completed
        summary['subscribed_courses'] = subscribed_courses
        summary['subscribed_courses_completed'] = subscribed_courses_completed
        summary['subscribed_courses_started'] = subscribed_courses_started
        summary['subscription_info'] = subscription_info

        # DELS tier + FTR, surfaced alongside the legacy-shaped summary above
        summary['dels_tier'] = tier_for(summary['overall_performance_score'])
        summary['dels_value'] = summary['overall_performance_score']
        summary['follow_through_rate'] = dels_result['ftr']

        all_assignments = (
            AssignmentActivity.objects.filter(user=request.user)
            .select_related('assignment', 'course')
            .order_by('-id')
        )

        graded_assignments = []
        for a in all_assignments:
            is_reviewed = (a.marks > 0 and a.status == 'Admin Reviewed')
            effective_status = (
                a.status if is_reviewed else ('Submitted' if a.assignment_submission_time else 'Pending')
            )
            graded_assignments.append({
                'assignment_id': a.assignment.id,
                'assignment_name': a.assignment.name,
                'course_title': a.course.title,
                'score': round(a.marks, 1),
                'max_score': 100,
                'percentage': round((a.marks / 100.0) * 100.0, 1) if a.marks else 0.0,
                'performance_points': round((a.marks / 100.0) * 250.0, 1) if a.marks else 0.0,
                'download_time': a.assignment_download_time.isoformat() if a.assignment_download_time else None,
                'submitted_at': a.assignment_submission_time.isoformat() if a.assignment_submission_time else None,
                'admin_review_time': a.admin_review_time.isoformat() if a.admin_review_time else None,
                'status': effective_status,
                'feedback': a.feedback,
                'submitted_file': str(a.assignment.pdf) if a.assignment.pdf else None,
            })

        recent_activities = []
        for lecture in LectureActivity.objects.filter(user=request.user).order_by('-completed_at')[:5]:
            ts = lecture.completed_at or lecture.started_at
            recent_activities.append({
                'type': 'lecture',
                'title': f"Lecture completed: {lecture.lecture.title}",
                'course_title': lecture.course.title,
                'status': 'Completed',
                'timestamp': ts.isoformat() if ts else None,
            })

        for assignment in all_assignments[:5]:
            ts = assignment.assignment_submission_time or assignment.admin_review_time or assignment.assignment_download_time
            recent_activities.append({
                'type': 'assignment',
                'title': f"Assignment: {assignment.assignment.name}",
                'course_title': assignment.course.title,
                'score': assignment.marks if assignment.marks > 0 else None,
                'status': assignment.status,
                'timestamp': ts.isoformat() if ts else None,
            })

        for daily in DailyLearningActivity.objects.filter(user=request.user).order_by('-date')[:5]:
            recent_activities.append({
                'type': 'login',
                'title': 'Daily study activity logged',
                'course_title': None,
                'status': 'Active',
                'timestamp': daily.date.isoformat(),
            })

        recent_activities = sorted(
            recent_activities,
            key=lambda item: item.get('timestamp') or '',
            reverse=True,
        )[:10]

        total_students = StudentAnalytics.objects.count()
        rank = analytics.student_rank or 0
        percentile = round(max(0.0, min(100.0, 100.0 - (rank * 10.0))), 1) if total_students else 0.0

        insights = [
            f"Learning Score: {int(summary['overall_performance_score'])} ({dels_result['tier']})",
            f"Avg Assignment Score: {round(summary['assignment_average'], 1)}%",
            f"Courses Completed: {summary['completed_courses']}/{summary['total_courses_purchased']}",
            f"Lectures Completed: {summary['lectures_completed']}",
            f"Assignment Progress: {summary['assignment_progress_percentage']}%",
        ]
        if summary['assignment_average'] >= 80:
            insights.append('Excellent Assignment Performance')
        if summary['assignments_pending_review'] > 0:
            insights.append('Assignments Pending Review')
        if summary['consistency_score'] >= 80:
            insights.append('Consistency Improving')
        elif summary['consistency_score'] < 40:
            insights.append('Learning Streak Broken')
        if summary['overall_completion'] >= 90:
            insights.append('Course Nearly Completed')

        if (
            dels_result['tier'] in ('Strong', 'Elite')
            and summary['assignment_average'] > 80
            and summary['lectures_completed_percent'] > 90
            and summary['assignments_pending_review'] == 0
            and summary['consistency_score'] > 80
        ):
            insights.append('High Internship Potential')
        else:
            insights.append('Needs More Practice')

        return Response({
            'success': True,
            'analytics': {
                'summary': summary,
                'ranking': {
                    'rank': rank,
                    'total_students': total_students,
                    'percentile': percentile,
                },
                'courses': courses_data,
                'course_analytics': courses_data,
                'recent_activity': recent_activities,
                'activity_timeline': recent_activities,
                'graded_assignments': graded_assignments,
                'assignment_history': graded_assignments,
                'insights': insights,
            },
        })


class StreakAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        analytics, _ = StudentAnalytics.objects.get_or_create(user=request.user)
        current_streak = recalculate_user_streak(request.user)
        return Response({
            "current_streak": current_streak,
            "longest_streak": analytics.longest_learning_streak,
        })


class HistoryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lectures = LectureActivity.objects.filter(user=request.user).order_by('-completed_at')[:20]
        return Response(LectureActivitySerializer(lectures, many=True).data)


# ─────────────────────────────────────────────────────────────────────────
# DELS endpoints (spec §5) — additive reads for the new dashboard widgets
# ─────────────────────────────────────────────────────────────────────────
class DELSDetailAPIView(APIView):
    """GET /api/users/{id}/dels — current DELS, tier, 90-day trend, 'what changed' breakdown."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        if not _is_self_or_staff(request, user_id):
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        target_user = _resolve_target_user(request, user_id)
        dels_result = compute_dels_preview(target_user)
        since = timezone.now().date() - timedelta(days=90)
        trend = list(
            DELSSnapshot.objects.filter(user=target_user, date__gte=since)
            .order_by("date")
            .values("date", "dels_value", "tier")
        )

        return Response({
            "dels": dels_result["dels"],
            "tier": dels_result["tier"],
            "follow_through_rate": dels_result["ftr"],
            "trend": trend,
            "what_changed": dels_result["breakdown"],
        })


class DELSBreakdownAPIView(APIView):
    """GET /api/users/{id}/dels/breakdown — per-enrollment CCS + weight contribution."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        if not _is_self_or_staff(request, user_id):
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        target_user = _resolve_target_user(request, user_id)
        dels_result = compute_dels_preview(target_user)
        return Response(dels_result["breakdown"])


class EnrollmentMetricsAPIView(APIView):
    """GET /api/enrollments/{id}/metrics — PALC, ASR, ATS, AQS, ECI, MPA, OAB, LCR for one course card.
    The {id} in the URL is the *course_id*, not the StudentCourseAnalytics PK.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, enrollment_id):
        # enrollment_id here is actually the course_id passed by the frontend
        enrollment = StudentCourseAnalytics.objects.filter(
            course_id=enrollment_id,
            user=request.user,
        ).first()

        if enrollment is None:
            # Also allow staff to look up any user's enrollment
            if request.user.is_staff:
                enrollment = get_object_or_404(StudentCourseAnalytics, course_id=enrollment_id)
            else:
                return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        lcr = (
            round((enrollment.completed_lectures / enrollment.total_lectures) * 100, 1)
            if enrollment.total_lectures else 0.0
        )

        return Response({
            "course_id": enrollment.course_id,
            "PALC": computePALC(enrollment),
            "ASR": computeASR(enrollment),
            "ATS": computeATS(enrollment),
            "AQS": computeAQS(enrollment),
            "ECI": computeECI(enrollment),
            "MPA": computeMPA(enrollment),
            "OAB": computeOAB(enrollment),
            "LCR": lcr,
        })


class FollowThroughAPIView(APIView):
    """GET /api/users/{id}/follow-through — FTR + courses_started/completed/active counts."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        if not _is_self_or_staff(request, user_id):
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        target_user = _resolve_target_user(request, user_id)
        return Response(compute_follow_through(target_user.id))


class AvgMetricsAPIView(APIView):
    """GET /api/users/{id}/avg-metrics/ — averaged ASR, ATS, AQS, PALC, ECI across all enrollments.
    More efficient than calling /enrollments/{id}/metrics/ per course.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        if not _is_self_or_staff(request, user_id):
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        target_user = _resolve_target_user(request, user_id)
        enrollments = list(
            StudentCourseAnalytics.objects.filter(user=target_user)
        )

        if not enrollments:
            return Response({
                "ASR": 0, "ATS": 0, "AQS": 0, "PALC": 0, "ECI": 0,
                "enrollment_count": 0,
            })

        n = len(enrollments)
        asr_total = sum(computeASR(e) for e in enrollments)
        ats_total = sum(computeATS(e) for e in enrollments)
        aqs_total = sum(computeAQS(e) for e in enrollments)
        palc_total = sum(computePALC(e) for e in enrollments)
        eci_total = sum(computeECI(e) for e in enrollments)

        return Response({
            "ASR": round(asr_total / n, 1),
            "ATS": round(ats_total / n, 1),
            "AQS": round(aqs_total / n, 1),
            "PALC": round(palc_total / n, 1),
            "ECI": round(eci_total / n, 1),
            "enrollment_count": n,
        })