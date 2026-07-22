"""
signals.py — Signal handlers for student_analytics

Automatically syncs analytics tables when raw course data changes:
  - UserVideoProgress saved → LectureActivity + StudentCourseAnalytics updated
  - AssignmentEvaluation saved → AssignmentActivity + StudentCourseAnalytics updated
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='course.UserVideoProgress')
def on_video_progress_saved(sender, instance, created, **kwargs):
    """
    When a UserVideoProgress record is saved (video completed),
    create/update the corresponding LectureActivity and refresh
    the StudentCourseAnalytics lecture counts.
    """
    try:
        from .models import LectureActivity, StudentCourseAnalytics, StudentAnalytics
        from course.models import Video

        user = instance.user
        course = instance.course
        video = instance.video

        if not user or not course or not video:
            return

        # Create/update LectureActivity
        if instance.completed:
            la, la_created = LectureActivity.objects.get_or_create(
                user=user, course=course, lecture=video,
                defaults={
                    "is_completed": True,
                    "completed_at": timezone.now(),
                },
            )
            if not la_created and not la.is_completed:
                la.is_completed = True
                la.completed_at = timezone.now()
                la.save(update_fields=["is_completed", "completed_at"])

        # Update StudentCourseAnalytics lecture counts
        from course.models import UserVideoProgress as UVP
        completed_count = UVP.objects.filter(user=user, course=course, completed=True).count()
        total_count = Video.objects.filter(module__section__course=course).count()

        sca, _ = StudentCourseAnalytics.objects.get_or_create(user=user, course=course)
        sca.completed_lectures = completed_count
        sca.total_lectures = total_count
        sca.last_activity_at = timezone.now()

        # Update course status based on progress
        if completed_count > 0 and sca.course_status == "Not Started":
            sca.course_status = "In Progress"

        sca.save(update_fields=[
            "completed_lectures", "total_lectures", "last_activity_at", "course_status",
        ])

        # Update global StudentAnalytics lecture count
        total_lectures_all = sum(
            s.completed_lectures for s in StudentCourseAnalytics.objects.filter(user=user)
        )
        sa, _ = StudentAnalytics.objects.get_or_create(user=user)
        sa.total_lectures_completed = total_lectures_all
        sa.save(update_fields=["total_lectures_completed"])

        logger.info(
            f"[SIGNAL] on_video_progress_saved: user={user.id} course={course.id} "
            f"video={video.id} completed={instance.completed} lectures={completed_count}/{total_count}"
        )

    except Exception:
        logger.exception("[SIGNAL] on_video_progress_saved failed")


@receiver(post_save, sender='course.AssignmentEvaluation')
def on_assignment_evaluation_saved(sender, instance, created, **kwargs):
    """
    When an AssignmentEvaluation is saved (submission or review),
    create/update the AssignmentActivity and refresh
    the StudentCourseAnalytics assignment counts.
    """
    try:
        from .models import AssignmentActivity, StudentCourseAnalytics, StudentAnalytics
        from course.models import AssignmentEvaluation

        user = instance.user
        course = instance.course
        assignment = instance.assignment

        if not user or not course or not assignment:
            return

        score_f = float(instance.score or 0)
        is_submitted = bool(instance.submit_flag or instance.created_at)
        is_reviewed = score_f > 0

        status_label = (
            "Admin Reviewed" if is_reviewed
            else ("Submitted" if is_submitted else "Pending")
        )

        # Create or update AssignmentActivity
        aa, aa_created = AssignmentActivity.objects.get_or_create(
            user=user, course=course, assignment=assignment,
            defaults={
                "marks": score_f,
                "status": status_label,
                "assignment_submission_time": instance.created_at if is_submitted else None,
                "admin_review_time": timezone.now() if is_reviewed else None,
            },
        )
        if not aa_created:
            aa.marks = score_f
            aa.status = status_label
            if not aa.assignment_submission_time and is_submitted:
                aa.assignment_submission_time = instance.created_at
            if is_reviewed and not aa.admin_review_time:
                aa.admin_review_time = timezone.now()
            aa.save()

        # Update StudentCourseAnalytics assignment counts
        evals = AssignmentEvaluation.objects.filter(user=user, course=course)
        submitted_count = evals.filter(submit_flag=True).count()
        reviewed_count = evals.filter(submit_flag=True, score__gt=0).count()

        sca, _ = StudentCourseAnalytics.objects.get_or_create(user=user, course=course)
        sca.completed_assignments = submitted_count
        sca.last_activity_at = timezone.now()

        if submitted_count > 0 and reviewed_count > 0:
            from django.db.models import Sum
            total_score = float(
                evals.filter(submit_flag=True, score__gt=0)
                .aggregate(total=Sum("score"))["total"] or 0
            )
            sca.assignment_average = total_score / reviewed_count
        else:
            sca.assignment_average = 0.0

        # Update course status
        if submitted_count > 0 and sca.course_status == "Not Started":
            sca.course_status = "In Progress"

        sca.save(update_fields=[
            "completed_assignments", "assignment_average", "last_activity_at", "course_status",
        ])

        # Update global StudentAnalytics
        total_submitted_all = sum(
            s.completed_assignments for s in StudentCourseAnalytics.objects.filter(user=user)
        )
        sa, _ = StudentAnalytics.objects.get_or_create(user=user)
        sa.total_assignments_completed = total_submitted_all
        sa.save(update_fields=["total_assignments_completed"])

        logger.info(
            f"[SIGNAL] on_assignment_evaluation_saved: user={user.id} course={course.id} "
            f"assignment={assignment.id} submitted={is_submitted} reviewed={is_reviewed} score={score_f}"
        )

    except Exception:
        logger.exception("[SIGNAL] on_assignment_evaluation_saved failed")
