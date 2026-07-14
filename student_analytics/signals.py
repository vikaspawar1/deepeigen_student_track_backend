"""
signals.py – Student Analytics Signal Handlers
Tracks: video completions, course progress, assignment submissions/evaluations.
Does NOT modify any existing course models.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from course.models import UserVideoProgress, OverallProgress, AssignmentEvaluation, EnrolledUser
from .models import (
    StudentAnalytics, StudentCourseAnalytics, LectureActivity,
    AssignmentActivity, DailyLearningActivity
)


def get_or_create_analytics(user):
    analytics, _ = StudentAnalytics.objects.get_or_create(user=user)
    return analytics


def update_internship_eligibility(analytics):
    """
    Internship eligibility requires:
      - Performance score >= 900
      - Average assignment score >= 80
      - At least 1 course completed
    """
    if (
        analytics.overall_performance_score >= 900
        and analytics.average_assignment_score >= 80
        and analytics.total_courses_completed >= 1
    ):
        analytics.internship_eligible = True
    else:
        analytics.internship_eligible = False
    analytics.save()


def record_daily_learning_activity(user, is_lecture=False, is_assignment=False, study_minutes=0):
    from datetime import date
    daily, _ = DailyLearningActivity.objects.get_or_create(
        user=user, date=date.today()
    )
    daily.study_time += study_minutes
    if is_lecture:
        daily.lectures_completed += 1
    if is_assignment:
        daily.assignments_submitted += 1
    daily.save()


def _sync_course_analytics_to_global(analytics, course_analytics):
    """Recompute global totals from all per-course records."""
    from django.db.models import Sum, Avg, Count
    all_ca = StudentCourseAnalytics.objects.filter(user=analytics.user)
    analytics.total_lectures_completed = all_ca.aggregate(s=Sum('completed_lectures'))['s'] or 0
    analytics.total_assignments_completed = all_ca.aggregate(s=Sum('completed_assignments'))['s'] or 0
    analytics.total_modules_completed = all_ca.aggregate(s=Sum('completed_modules'))['s'] or 0
    analytics.total_courses_completed = all_ca.filter(course_status='Completed').count()
    analytics.total_courses_purchased = StudentCourseAnalytics.objects.filter(user=analytics.user).count()
    analytics.save()


# ─────────────────────────────────────────────
# 1. Video / Lecture Completion
# ─────────────────────────────────────────────
@receiver(post_save, sender=UserVideoProgress)
def track_video_completion(sender, instance, created, **kwargs):
    if not instance.completed:
        return

    activity, act_created = LectureActivity.objects.get_or_create(
        user=instance.user,
        course=instance.course,
        lecture=instance.video,
        defaults={'is_completed': True, 'completed_at': timezone.now()}
    )

    if act_created:
        analytics = get_or_create_analytics(instance.user)

        course_analytics, _ = StudentCourseAnalytics.objects.get_or_create(
            user=instance.user,
            course=instance.course
        )
        course_analytics.completed_lectures += 1
        course_analytics.course_performance_score += 2
        
        # Populate dates if missing
        if not course_analytics.purchase_date:
            enrolled = EnrolledUser.objects.filter(user=instance.user, course=instance.course, enrolled=True).first()
            access_start_date = None
            duration_months = getattr(instance.course, 'duration', 0) or 6
            if enrolled:
                access_start_date = enrolled.created_at
            else:
                from subscriptions.models import UserSubscription, PlanCategoryAccess
                active_subscriptions = UserSubscription.objects.filter(user=instance.user, is_active=True).order_by('start_date')
                for sub in active_subscriptions:
                    categories = PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type).values_list("category", flat=True)
                    if instance.course.category in categories and instance.course.is_featured:
                        access_start_date = sub.start_date
                        break
                        
            if access_start_date:
                from datetime import timedelta
                course_analytics.purchase_date = access_start_date
                course_analytics.access_start_date = access_start_date
                course_analytics.expected_course_duration = duration_months * 30
                course_analytics.expected_completion_date = access_start_date + timedelta(days=duration_months * 30)

        course_analytics.save()

        analytics.overall_performance_score += 2
        analytics.total_lectures_completed += 1
        analytics.total_courses_purchased = StudentCourseAnalytics.objects.filter(user=instance.user).count()
        update_internship_eligibility(analytics)
        
        # Track daily learning activity (Lecture +1)
        record_daily_learning_activity(instance.user, is_lecture=True, study_minutes=15)


# ─────────────────────────────────────────────
# 2. Course Completion (OverallProgress hits 100)
# ─────────────────────────────────────────────
@receiver(post_save, sender=OverallProgress)
def track_course_progress(sender, instance, **kwargs):
    course_analytics, _ = StudentCourseAnalytics.objects.get_or_create(
        user=instance.user,
        course=instance.course
    )
    course_analytics.completion_percentage = float(instance.progress)

    # Populate dates if missing
    if not course_analytics.purchase_date:
        enrolled = EnrolledUser.objects.filter(user=instance.user, course=instance.course, enrolled=True).first()
        access_start_date = None
        duration_months = getattr(instance.course, 'duration', 0) or 6
        if enrolled:
            access_start_date = enrolled.created_at
        else:
            from subscriptions.models import UserSubscription, PlanCategoryAccess
            active_subscriptions = UserSubscription.objects.filter(user=instance.user, is_active=True).order_by('start_date')
            for sub in active_subscriptions:
                categories = PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type).values_list("category", flat=True)
                if instance.course.category in categories and instance.course.is_featured:
                    access_start_date = sub.start_date
                    break
                    
        if access_start_date:
            from datetime import timedelta
            course_analytics.purchase_date = access_start_date
            course_analytics.access_start_date = access_start_date
            course_analytics.expected_course_duration = duration_months * 30
            course_analytics.expected_completion_date = access_start_date + timedelta(days=duration_months * 30)

    if float(instance.progress) >= 100 and course_analytics.course_status != 'Completed':
        course_analytics.course_status = 'Completed'
        course_analytics.actual_completion_date = timezone.now()
        course_analytics.course_performance_score += 150
        course_analytics.save()

        analytics = get_or_create_analytics(instance.user)
        analytics.overall_performance_score += 150
        analytics.total_courses_completed += 1
        analytics.total_courses_purchased = StudentCourseAnalytics.objects.filter(user=instance.user).count()
        update_internship_eligibility(analytics)
    elif float(instance.progress) > 0 and course_analytics.course_status == 'Not Started':
        course_analytics.course_status = 'In Progress'
        course_analytics.save()
    else:
        course_analytics.save()





# ─────────────────────────────────────────────
# 3. Assignment Evaluation (Admin reviews / grades)
# ─────────────────────────────────────────────
@receiver(post_save, sender=AssignmentEvaluation)
def track_assignment_evaluation(sender, instance, created, **kwargs):
    if not instance.submit_flag:
        return
        
    score_float = float(instance.score)

    # Track daily learning activity (Assignment +1)
    # Only track if this is a newly submitted/created evaluation (not just a score update)
    if created or instance.score == 0:
        record_daily_learning_activity(instance.user, is_assignment=True, study_minutes=30)


    # Determine early-submission bonus
    early_bonus = 0
    try:
        enrolled = EnrolledUser.objects.filter(
            user=instance.user,
            course=instance.course,
            enrolled=True
        ).order_by('created_at').first()

        access_start_date = None
        if enrolled:
            access_start_date = enrolled.created_at
        else:
            from subscriptions.models import UserSubscription, PlanCategoryAccess
            active_subscriptions = UserSubscription.objects.filter(
                user=instance.user, is_active=True
            ).order_by('start_date')
            
            for sub in active_subscriptions:
                categories = PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type).values_list("category", flat=True)
                if instance.course.category in categories and instance.course.is_featured:
                    access_start_date = sub.start_date
                    break

        if access_start_date:
            course_duration_months = getattr(instance.course, 'duration', 0) or 6
            course_duration_days = course_duration_months * 30
            days_elapsed = (instance.created_at - access_start_date).days if instance.created_at else 0
            # If submitted in first half of course duration, grant early bonus
            if days_elapsed < course_duration_days // 2:
                early_bonus = 20
            elif days_elapsed < (course_duration_days * 3) // 4:
                early_bonus = 10
    except Exception:
        early_bonus = 0

    # Score-based bonus
    score_bonus = 0
    if score_float >= 95:
        score_bonus = 60
    elif score_float >= 85:
        score_bonus = 50
    elif score_float >= 75:
        score_bonus = 40
    elif score_float >= 60:
        score_bonus = 30
    else:
        score_bonus = 10

    total_bonus = score_bonus + early_bonus

    # Update or create AssignmentActivity
    activity, act_created = AssignmentActivity.objects.get_or_create(
        user=instance.user,
        course=instance.course,
        assignment=instance.assignment,
        defaults={
            'marks': score_float,
            'status': 'Admin Reviewed',
            'assignment_submission_time': instance.created_at,
            'admin_review_time': timezone.now(),
        }
    )

    if not act_created:
        activity.marks = score_float
        activity.status = 'Admin Reviewed'
        activity.admin_review_time = timezone.now()
        if not activity.assignment_submission_time and instance.created_at:
            activity.assignment_submission_time = instance.created_at
        activity.save()

    analytics = get_or_create_analytics(instance.user)

    # Recalculate running average
    completed = analytics.total_assignments_completed
    if act_created:
        new_total = completed + 1
        analytics.average_assignment_score = (
            (analytics.average_assignment_score * completed) + score_float
        ) / new_total
        analytics.total_assignments_completed = new_total
        analytics.overall_performance_score += total_bonus
    else:
        # Re-average: treat as update (just add bonus if not already added)
        if completed > 0:
            analytics.average_assignment_score = (
                (analytics.average_assignment_score * completed) + score_float
            ) / (completed + 1)

    # Update course analytics
    course_analytics, _ = StudentCourseAnalytics.objects.get_or_create(
        user=instance.user,
        course=instance.course
    )
    if act_created:
        course_analytics.completed_assignments += 1
    course_analytics.assignment_average = analytics.average_assignment_score
    course_analytics.course_performance_score += total_bonus
    course_analytics.save()

    update_internship_eligibility(analytics)





# ─────────────────────────────────────────────
# 4. Enrollment – set purchase_date on course analytics
# ─────────────────────────────────────────────
@receiver(post_save, sender=EnrolledUser)
def track_enrollment(sender, instance, created, **kwargs):
    if created and instance.enrolled:
        course_analytics, _ = StudentCourseAnalytics.objects.get_or_create(
            user=instance.user,
            course=instance.course
        )
        if not course_analytics.purchase_date:
            course_analytics.purchase_date = instance.created_at
            course_analytics.access_start_date = instance.created_at
            if instance.course.duration:
                from datetime import timedelta
                course_analytics.expected_course_duration = instance.course.duration * 30
                course_analytics.expected_completion_date = (
                    instance.created_at + timedelta(days=instance.course.duration * 30)
                )
            course_analytics.save()

        analytics = get_or_create_analytics(instance.user)
        analytics.total_courses_purchased = StudentCourseAnalytics.objects.filter(
            user=instance.user
        ).count()
        analytics.save()





# ─────────────────────────────────────────────
# 5. Daily Learning Activity (Engagement & Consistency)
# ─────────────────────────────────────────────
@receiver(post_save, sender=DailyLearningActivity)
def track_daily_learning(sender, instance, created, **kwargs):
    """
    When daily learning activity is recorded, update engagement & consistency metrics.
    """
    from datetime import timedelta, date
    from django.db.models import Sum
    
    user = instance.user
    analytics = get_or_create_analytics(user)
    
    # ===== ENGAGEMENT: Total study minutes =====
    total_mins = DailyLearningActivity.objects.filter(
        user=user
    ).aggregate(total=Sum('study_time'))['total'] or 0.0
    analytics.total_study_minutes = total_mins
    
    # ===== CONSISTENCY: Calculate learning streak =====
    # Start from TODAY and go backwards until we find a gap
    from django.db.models import Q
    today = date.today()
    streak = 0
    check_date = today

    # Keep checking backwards while records exist
    while True:
        has_activity = DailyLearningActivity.objects.filter(
            Q(user=user, date=check_date) & (Q(study_time__gte=30) | Q(assignments_submitted__gt=0))
        ).exists()

        if has_activity:
            streak += 1
            check_date = check_date - timedelta(days=1)
        else:
            break

    # Longest streak can be derived from historical consecutive activity
    all_dates = list(
        DailyLearningActivity.objects.filter(
            Q(user=user) & (Q(study_time__gte=30) | Q(assignments_submitted__gt=0))
        )
        .values_list('date', flat=True)
        .order_by('date')
    )
    longest_streak = 0
    current_run = 0
    previous_date = None
    for entry_date in all_dates:
        if previous_date is None:
            current_run = 1
        elif entry_date == previous_date + timedelta(days=1):
            current_run += 1
        else:
            longest_streak = max(longest_streak, current_run)
            current_run = 1
        previous_date = entry_date
    longest_streak = max(longest_streak, current_run)

    analytics.current_learning_streak = streak
    analytics.longest_learning_streak = max(analytics.longest_learning_streak or 0, longest_streak)
    analytics.save()
    
    print(f"[Signal] Updated {user.email}: Study={total_mins}min, Streak={streak}d")


# ─────────────────────────────────────────────
# 6. Assignment Activity Updates (when admin directly edits marks)
# ─────────────────────────────────────────────
@receiver(post_save, sender=AssignmentActivity)
def track_assignment_activity_update(sender, instance, created, **kwargs):
    """
    When assignment activity is saved (including direct admin edits), recalculate assignment average.
    Light-weight update - only update average_assignment_score.
    """
    # Skip if no marks set
    if instance.marks <= 0:
        return
    
    analytics = get_or_create_analytics(instance.user)
    
    # Recalculate average and completed assignment totals from all graded assignments
    from django.db.models import Avg, Count, Q
    graded = AssignmentActivity.objects.filter(
        user=instance.user,
        marks__gt=0,
    ).filter(
        Q(status__iexact='Admin Reviewed') | Q(admin_review_time__isnull=False)
    ).aggregate(avg=Avg('marks'), count=Count('id'))
    
    if graded['count'] and graded['count'] > 0:
        analytics.average_assignment_score = graded['avg'] or 0.0
        analytics.total_assignments_completed = graded['count']
    else:
        analytics.average_assignment_score = 0.0
        analytics.total_assignments_completed = 0
    analytics.save()


# ─────────────────────────────────────────────
# 7. Subscription Purchase Tracker
# ─────────────────────────────────────────────
@receiver(post_save, sender='subscriptions.UserSubscription')
def track_subscription(sender, instance, created, **kwargs):
    """
    When a UserSubscription is created or activated, map the allowed featured courses
    to StudentCourseAnalytics so they appear in the user's dashboard.
    """
    if instance.is_active:
        analytics = get_or_create_analytics(instance.user)
        # Simply update the courses purchased count based on active tracking
        analytics.total_courses_purchased = StudentCourseAnalytics.objects.filter(user=instance.user).count()
        analytics.save()
