from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AssignmentActivity,
    DailyLearningActivity,
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
from .utils import build_student_overview_summary


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
        # DON'T recalculate on every request - just read pre-calculated data
        analytics, _ = StudentAnalytics.objects.get_or_create(user=request.user)

        from course.models import AssignmentEvaluation

        assignments_submitted = AssignmentEvaluation.objects.filter(
            user=request.user,
            submit_flag=True,
        ).count()
        admin_reviewed_count = AssignmentEvaluation.objects.filter(
            user=request.user,
            submit_flag=True,
            score__gt=0,
        ).count()
        pending_review_count = max(0, assignments_submitted - admin_reviewed_count)

        # Recompute engagement from actual daily activity records so admin updates show immediately
        total_study_minutes = DailyLearningActivity.objects.filter(user=request.user).aggregate(
            total=Sum('study_time')
        )['total'] or 0.0
        analytics.total_study_minutes = total_study_minutes

        from django.db.models import Q
        streak_dates = list(
            DailyLearningActivity.objects.filter(
                Q(user=request.user) & (Q(study_time__gte=30) | Q(assignments_submitted__gt=0))
            ).order_by('date').values_list('date', flat=True)
        )
        current_streak = 0
        if streak_dates:
            from datetime import timedelta
            last_date = streak_dates[-1]
            current_streak = 1
            previous_date = last_date
            for date_entry in reversed(streak_dates[:-1]):
                if date_entry == previous_date - timedelta(days=1):
                    current_streak += 1
                    previous_date = date_entry
                else:
                    break
        analytics.current_learning_streak = current_streak
        analytics.save()

        # Use select_related to reduce queries
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
                'course_performance_score': round(c.course_performance_score, 0),
                'course_max_score': 1000,
                'purchase_date': c.purchase_date.isoformat() if c.purchase_date else None,
                'started_date': c.access_start_date.isoformat() if c.access_start_date else None,
                'expected_completion_date': c.expected_completion_date.isoformat() if c.expected_completion_date else None,
                'actual_completion_date': c.actual_completion_date.isoformat() if c.actual_completion_date else None,
                'lecture_completion_percent': lecture_percent,
                'modules': [],
            })

        # ── Calculate purchased vs subscribed courses ──────────────────────────
        from course.models import EnrolledUser, Course
        from subscriptions.models import UserSubscription, PlanCategoryAccess

        enrolled_course_ids = set(
            EnrolledUser.objects.filter(user=request.user, enrolled=True)
            .values_list('course_id', flat=True)
        )

        # Purchased: directly from EnrolledUser
        purchased_courses = len(enrolled_course_ids)
        purchased_courses_completed = StudentCourseAnalytics.objects.filter(
            user=request.user,
            course_id__in=enrolled_course_ids,
            course_status='Completed'
        ).count()

        # Subscribed: courses unlocked from active subscription plan
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

        # Subscribed courses with progress (started)
        subscribed_courses_started = StudentCourseAnalytics.objects.filter(
            user=request.user,
            course_id__in=subscribed_course_ids,
            course_status__in=['In Progress', 'Completed']
        ).count() if subscribed_course_ids else 0

        avg_lecture_percent = round(lecture_completion_total / course_count, 1) if course_count else 0.0

        summary = build_student_overview_summary(
            analytics,
            total_courses_purchased=analytics.total_courses_purchased,
            assignments_reviewed=admin_reviewed_count,
            assignments_pending=pending_review_count,
            assignments_submitted=assignments_submitted,
            total_lectures_completed=analytics.total_lectures_completed,
            total_modules_completed=analytics.total_modules_completed,
            lecture_completion_percent=avg_lecture_percent,
        )

        summary['purchased_courses'] = purchased_courses
        summary['purchased_courses_completed'] = purchased_courses_completed
        summary['subscribed_courses'] = subscribed_courses
        summary['subscribed_courses_completed'] = subscribed_courses_completed
        summary['subscribed_courses_started'] = subscribed_courses_started
        summary['subscription_info'] = subscription_info

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
            f"Performance Score: {int(summary['overall_performance_score'])}",
            f"Avg Assignment Score: {round(summary['assignment_average'], 1)}%",
            f"Courses Completed: {summary['completed_courses']}/{summary['total_courses_purchased']}",
            f"Lectures Completed: {summary['lectures_completed']}",
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
            summary['overall_performance_score'] > 850
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
        return Response({
            "current_streak": analytics.current_learning_streak,
            "longest_streak": analytics.longest_learning_streak,
        })


class HistoryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lectures = LectureActivity.objects.filter(user=request.user).order_by('-completed_at')[:20]
        return Response(LectureActivitySerializer(lectures, many=True).data)
