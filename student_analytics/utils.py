"""
utils.py – Sync utility for Student Analytics.

Scoring Rules:
  - Each lecture completed:           +2  pts
  - Course fully completed (100%):   +150 pts
  - Per assignment (score-based):
      ≥95  → +60 pts
      ≥85  → +50 pts
      ≥75  → +40 pts
      ≥60  → +30 pts
      <60  → +10 pts
  - Early submission bonus (vs course duration):
      Submitted in first 50% of course duration  → +20 pts extra
      Submitted in first 75% of course duration  → +10 pts extra

Purchase date / expected completion date are calculated here but NOT
sent to the frontend – they are internal to the scoring logic.
"""
from datetime import timedelta

from django.utils import timezone

from course.models import AssignmentEvaluation, EnrolledUser, OverallProgress, UserVideoProgress
from .models import AssignmentActivity, LectureActivity, StudentAnalytics, StudentCourseAnalytics


def _score_bonus(score_f: float) -> int:
    """Return performance-score bonus for a given assignment score (0-100)."""
    if score_f >= 95:
        return 60
    if score_f >= 85:
        return 50
    if score_f >= 75:
        return 40
    if score_f >= 60:
        return 30
    return 10




def _early_submission_bonus(submitted_at, enrolled_at, course_duration_months: int) -> int:
    """
    Calculate early-submission bonus.
    course_duration_months: integer months (e.g. 6).
    Returns 0 if dates are missing.
    """
    if not submitted_at or not enrolled_at:
        return 0
    course_duration_days = (course_duration_months or 6) * 30
    days_elapsed = max(0, (submitted_at - enrolled_at).days)
    if days_elapsed < course_duration_days // 2:
        return 20
    if days_elapsed < (course_duration_days * 3) // 4:
        return 10
    return 0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def build_student_overview_summary(
    analytics,
    *,
    total_courses_purchased,
    assignments_reviewed,
    assignments_pending,
    assignments_submitted,
    total_lectures_completed,
    total_modules_completed,
    lecture_completion_percent=None,
):
    # ── Assignment Performance: 0–500 pts ──────────────────────────────────
    assignment_average = float(getattr(analytics, 'average_assignment_score', 0.0) or 0.0)
    assignment_performance_points = round(
        min(500.0, max(0.0, (assignment_average / 100.0) * 500.0)), 1
    )

    # ── Lecture Completion: 0–350 pts ───────────────────────────────────────
    lecture_percent = float(lecture_completion_percent or 0.0)
    lecture_completion_points = round(min(350.0, max(0.0, lecture_percent / 100.0 * 350.0)), 1)

    # ── Consistency (Streak): 0–150 pts ────────────────────────────────────
    streak = int(getattr(analytics, 'current_learning_streak', 0) or 0)
    if streak >= 30:
        consistency_points = 150.0
    elif streak >= 20:
        consistency_points = 120.0
    elif streak >= 10:
        consistency_points = 75.0
    elif streak >= 5:
        consistency_points = 40.0
    else:
        consistency_points = round(max(0.0, streak * 8.0), 1)

    # ── Overall Score: sum clamped to 1000 ─────────────────────────────────
    overall_score = round(
        _clamp(
            assignment_performance_points + lecture_completion_points + consistency_points,
            0,
            1000,
        ),
        1,
    )

    # Keep overall_completion for display purposes (courses completed %)
    total_purchased = int(total_courses_purchased or 0)
    overall_completion = round(lecture_completion_percent, 1) if lecture_completion_percent is not None else 0.0

    return {
        'overall_completion': overall_completion,
        'overall_performance_score': round(overall_score, 0),
        'performance_points_earned': round(overall_score, 0),
        'performance_points_max': 1000,
        'assignment_average': round(assignment_average, 1),
        'completed_courses': int(getattr(analytics, 'total_courses_completed', 0) or 0),
        'total_courses_purchased': total_purchased,
        'study_time_minutes': int(getattr(analytics, 'total_study_minutes', 0) or 0),
        'study_hours': round((getattr(analytics, 'total_study_minutes', 0) or 0) / 60.0, 1),
        'consistency_score': round(consistency_points, 0),
        'completion_speed': 0,
        'internship_eligible': bool(getattr(analytics, 'internship_eligible', False)),
        'videos_completed': int(total_lectures_completed or 0),
        'assignments_submitted': int(assignments_submitted or 0),
        'assignments_reviewed': int(assignments_reviewed or 0),
        'assignments_pending_review': int(assignments_pending or 0),
        'lectures_completed': int(total_lectures_completed or 0),
        'lectures_completed_percent': round(lecture_percent, 1),
        'modules_completed': int(total_modules_completed or 0),
        'learning_streak': streak,
        'score_breakdown': {
            'assignment_performance': {
                'earned': round(assignment_performance_points, 0),
                'max': 500,
                'percent': round((assignment_performance_points / 500.0) * 100.0, 1),
            },
            'lecture_completion': {
                'earned': round(lecture_completion_points, 0),
                'max': 350,
                'percent': round((lecture_completion_points / 350.0) * 100.0, 1),
            },
            'consistency': {
                'earned': round(consistency_points, 0),
                'max': 150,
                'percent': round((consistency_points / 150.0) * 100.0, 1),
            },
            'overall': {
                'earned': round(overall_score, 0),
                'max': 1000,
                'percent': round((overall_score / 1000.0) * 100.0, 1),
            },
        },
    }









def sync_user_analytics(user):
    """
    Rebuild all analytics for `user` from raw course data.
    Safe to call repeatedly (idempotent).
    """
    analytics, _ = StudentAnalytics.objects.get_or_create(user=user)

    enrolled_qs = EnrolledUser.objects.filter(
        user=user, enrolled=True
    ).select_related('course').order_by('created_at')

    # Dictionary to hold unified course access info to avoid duplicates
    # course_id -> { 'course': Course object, 'purchase_date': datetime, 'duration_months': int }
    unified_course_access = {}

    for enroll in enrolled_qs:
        unified_course_access[enroll.course.id] = {
            'course': enroll.course,
            'purchase_date': enroll.created_at,
            'duration_months': getattr(enroll.course, 'duration', 0) or 6
        }

    # Integrate subscription plans
    from subscriptions.models import UserSubscription, PlanCategoryAccess
    from course.models import Course, UserVideoProgress, OverallProgress
    active_subscriptions = UserSubscription.objects.filter(
        user=user, is_active=True
    ).select_related('plan').order_by('start_date')

    for sub in active_subscriptions:
        categories = PlanCategoryAccess.objects.filter(
            plan_type=sub.plan.plan_type
        ).values_list("category", flat=True)
        sub_courses = Course.objects.filter(category__in=categories, is_featured=True)
        
        for c in sub_courses:
            if c.id not in unified_course_access:
                # Only include subscription courses if the user has started them
                has_progress = OverallProgress.objects.filter(user=user, course=c, progress__gt=0).exists()
                has_video = UserVideoProgress.objects.filter(user=user, course=c, completed=True).exists()
                
                if has_progress or has_video:
                    unified_course_access[c.id] = {
                        'course': c,
                        'purchase_date': sub.start_date,
                        'duration_months': getattr(c, 'duration', 0) or 6,
                        'source': 'subscription'
                    }

    analytics.total_courses_purchased = len(unified_course_access)

    total_score = 0.0
    total_lectures = 0
    total_modules = 0
    completed_courses = 0
    total_assignments_submitted = 0
    total_assignments_reviewed = 0
    total_assignments_pending = 0
    total_score_sum = 0.0

    for access_data in unified_course_access.values():
        course = access_data['course']
        course_analytics, _ = StudentCourseAnalytics.objects.get_or_create(
            user=user, course=course
        )
        course_score = 0.0

        course_duration_months = access_data['duration_months']
        course_duration_days = course_duration_months * 30
        purchase_date = access_data['purchase_date']
        expected_completion_date = purchase_date + timedelta(days=course_duration_days)

        if not course_analytics.purchase_date:
            course_analytics.purchase_date = purchase_date
            course_analytics.access_start_date = purchase_date
            course_analytics.expected_course_duration = course_duration_days
            course_analytics.expected_completion_date = expected_completion_date

        progress = OverallProgress.objects.filter(user=user, course=course).first()
        if progress:
            course_analytics.completion_percentage = float(progress.progress)
            if float(progress.progress) >= 100:
                if course_analytics.course_status != 'Completed':
                    course_analytics.course_status = 'Completed'
                    if not course_analytics.actual_completion_date:
                        course_analytics.actual_completion_date = timezone.now()

                    if course_analytics.actual_completion_date <= expected_completion_date:
                        days_early = (expected_completion_date - course_analytics.actual_completion_date).days
                        speed_bonus = min(50, days_early // 6)
                        course_score += speed_bonus

                course_score += 150
                completed_courses += 1
            elif float(progress.progress) > 0:
                course_analytics.course_status = 'In Progress'
                course_score += float(progress.progress) * 0.5
        else:
            course_analytics.completion_percentage = 0.0

        videos_done = UserVideoProgress.objects.filter(
            user=user, course=course, completed=True
        )
        lect_count = videos_done.count()

        from course.models import Video
        total_lectures_count = Video.objects.filter(module__section__course=course).count()
        course_analytics.total_lectures = total_lectures_count

        if course_analytics.course_status == 'Completed' and total_lectures_count > lect_count:
            # If course is marked completed, assume lecture completion is complete too.
            lect_count = total_lectures_count

        course_analytics.completed_lectures = lect_count
        course_score += lect_count * 2
        total_lectures += lect_count

        for vp in videos_done:
            LectureActivity.objects.get_or_create(
                user=user,
                course=course,
                lecture=vp.video,
                defaults={'is_completed': True, 'completed_at': timezone.now()}
            )

        evals = AssignmentEvaluation.objects.filter(
            user=user, course=course
        ).select_related('assignment').order_by('created_at')

        course_asgn_score_sum = 0.0
        course_asgn_reviewed = 0
        course_asgn_pending = 0

        for ev in evals:
            score_f = float(ev.score)
            submitted_at = ev.created_at

            if ev.submit_flag or submitted_at:
                is_submitted = True
            else:
                is_submitted = False

            is_reviewed = (score_f > 0)

            if is_reviewed:
                sb = _score_bonus(score_f)
                eb = _early_submission_bonus(submitted_at, purchase_date, course_duration_months)
                total_bonus = sb + eb
                course_score += total_bonus
                course_asgn_score_sum += score_f
                course_asgn_reviewed += 1
            elif is_submitted:
                course_score += 5
                course_asgn_pending += 1

            status_label = 'Admin Reviewed' if is_reviewed else ('Submitted' if is_submitted else 'Pending')
            acts = AssignmentActivity.objects.filter(
                user=user,
                course=course,
                assignment=ev.assignment,
            ).order_by('id')
            if acts.exists():
                act = acts.first()
                created = False
                if acts.count() > 1:
                    acts.exclude(id=act.id).delete()
            else:
                act = AssignmentActivity.objects.create(
                    user=user,
                    course=course,
                    assignment=ev.assignment,
                    marks=score_f,
                    status=status_label,
                    assignment_submission_time=submitted_at,
                    admin_review_time=timezone.now() if is_reviewed else None,
                )
                created = True

            if not created:
                act.marks = score_f
                act.status = status_label
                if not act.assignment_submission_time and submitted_at:
                    act.assignment_submission_time = submitted_at
                if is_reviewed and not act.admin_review_time:
                    act.admin_review_time = submitted_at
                act.save()

        course_asgn_submitted = course_asgn_reviewed + course_asgn_pending
        course_analytics.completed_assignments = course_asgn_submitted
        course_analytics.assignment_average = (
            course_asgn_score_sum / course_asgn_reviewed
            if course_asgn_reviewed > 0 else 0.0
        )
        course_analytics.course_performance_score = course_score
        course_analytics.save()

        total_score += course_score
        total_assignments_submitted += course_asgn_submitted
        total_assignments_reviewed += course_asgn_reviewed
        total_assignments_pending += course_asgn_pending
        total_score_sum += course_asgn_score_sum
        total_modules += course_analytics.completed_modules

    analytics.total_courses_completed = completed_courses
    analytics.total_lectures_completed = total_lectures
    analytics.total_assignments_completed = total_assignments_submitted
    analytics.average_assignment_score = (
        total_score_sum / total_assignments_reviewed
        if total_assignments_reviewed > 0 else 0.0
    )
    analytics.total_modules_completed = total_modules
    analytics.overall_performance_score = total_score

    analytics.internship_eligible = (
        analytics.overall_performance_score >= 900
        and analytics.average_assignment_score >= 80
        and analytics.total_courses_completed >= 1
    )
    analytics.save()

    analytics._assignments_reviewed = total_assignments_reviewed
    analytics._assignments_pending = total_assignments_pending
    analytics._assignments_submitted = total_assignments_submitted

    return analytics
