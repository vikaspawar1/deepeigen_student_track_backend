"""
utils.py — Student Analytics business logic (DELS edition, consolidated)

This is the single home for every piece of logic the app needs:

  1. DELS scoring engine   — pure, stateless functions implementing every
                              formula in DELS-Developer-Implementation-Spec.md §3
                              (previously duplicated across dels_scoring.py /
                              Delsscoring.py — now lives here only).
  2. Summary builders      — map the DELS breakdown into the response shape
                              the frontend already expects.
  3. sync_user_analytics   — reconciles COUNTS and DATES from raw course-app
                              data. Does NOT touch overall_performance_score
                              or course_performance_score — those are DELS
                              values, written by `python manage.py compute_dels`.

views.py imports from here. Nothing here imports from views.py or urls.py.
"""
import math
from datetime import timedelta, date

from django.db.models import Sum, Avg, Q, Count
from django.utils import timezone

from course.models import Assignment, AssignmentEvaluation, EnrolledUser, OverallProgress, UserVideoProgress
from .models import (
    AssignmentActivity, LectureActivity, StudentAnalytics, StudentCourseAnalytics, DELSSnapshot,
)

# ─────────────────────────────────────────────────────────────────────────
# Constants (spec §3 / §6)
# ─────────────────────────────────────────────────────────────────────────
DEFAULT_SUGGESTED_LECTURES_PER_WEEK = 3
RW_LAMBDA = math.log(10) / 90.0   # 90 days inactive -> 10% weight retained
EMA_BETA = 0.20
INACTIVITY_DECAY = 0.005
COLD_START_DELS = 0.0


CCS_WEIGHTS = {"PALC": 0.15, "ASR": 0.15, "ATS": 0.10, "AQS": 0.35, "ECI": 0.10, "MPA": 0.15}

TIER_BANDS = [
    (0, 299, "At Risk"),
    (300, 499, "Developing"),
    (500, 699, "Proficient"),
    (700, 849, "Strong"),
    (850, 1000, "Elite"),
]


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def tier_for(dels_value):
    for lo, hi, label in TIER_BANDS:
        if lo <= dels_value <= hi:
            return label
    return "At Risk"


def _is_self_paced(enrollment):
    """Subscription/Playlist access = self-paced; Single Purchase = fixed-deadline."""
    return enrollment.access_source == "subscription"


def _days_since(dt):
    if not dt:
        return 0
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_default_timezone())
    return max(0, (now - dt).days)


def _course_duration_days(enrollment):
    return enrollment.expected_course_duration or ((getattr(enrollment.course, "duration", 0) or 6) * 30)


def _mandatory_activities_due_so_far(enrollment, assignment_activities=None):
    now = timezone.now()
    due_so_far = []
    if assignment_activities is None:
        activities = AssignmentActivity.objects.filter(user=enrollment.user, course=enrollment.course).select_related("assignment")
    else:
        activities = [act for act in assignment_activities if act.course_id == enrollment.course_id]

    for act in activities:
        if not getattr(act.assignment, "is_mandatory", True):
            continue
        due_date = getattr(act.assignment, "due_date", None)
        if due_date and due_date > now:
            continue  # not due yet — excluded from the denominator
        due_so_far.append(act)
    return due_so_far


# ─────────────────────────────────────────────────────────────────────────
# 1. Pace-Adjusted Lecture Score
# ─────────────────────────────────────────────────────────────────────────
def computePALC(enrollment):
    lectures_total = enrollment.total_lectures or 0
    if lectures_total == 0:
        return 0.0

    days_since_enrollment = _days_since(enrollment.access_start_date or enrollment.purchase_date)

    if _is_self_paced(enrollment):
        suggested = getattr(enrollment.course, "suggested_lectures_per_week", None) or DEFAULT_SUGGESTED_LECTURES_PER_WEEK
        weeks_elapsed = days_since_enrollment / 7.0
        expected_lectures_by_now = weeks_elapsed * suggested
    else:
        total_course_days = _course_duration_days(enrollment)
        expected_lectures_by_now = (
            (days_since_enrollment / total_course_days) * lectures_total if total_course_days else lectures_total
        )

    # 1. Raw Completion Ratio (80% Weight): Actual lectures completed / Total course lectures
    raw_completion_pct = (enrollment.completed_lectures / lectures_total) * 100.0

    # 2. Pace Score Ratio (20% Weight): Are lectures completed on/ahead of schedule for elapsed time?
    pace_ratio = (enrollment.completed_lectures / max(expected_lectures_by_now, 1.0)) * 100.0
    pace_score_pct = _clamp(pace_ratio, 0.0, 100.0)

    # Blended PALC Score: 80% Actual Completion + 20% Pace Adherence
    palc = 0.80 * raw_completion_pct + 0.20 * pace_score_pct
    return round(_clamp(palc, 0.0, 100.0), 2)


# ─────────────────────────────────────────────────────────────────────────
# 2. Assignment Submission Rate
# ─────────────────────────────────────────────────────────────────────────
def computeASR(enrollment, assignment_activities=None):
    due_so_far = _mandatory_activities_due_so_far(enrollment, assignment_activities)
    if not due_so_far:
        return 0.0
    submitted = sum(1 for a in due_so_far if a.assignment_submission_time)
    if submitted == 0:
        return 0.0
    return round(_clamp((submitted / len(due_so_far)) * 100.0, 0, 100), 2)


# ─────────────────────────────────────────────────────────────────────────
# 3. Assignment Timeliness Score
# ─────────────────────────────────────────────────────────────────────────
def computeATS(enrollment, assignment_activities=None):
    due_so_far = _mandatory_activities_due_so_far(enrollment, assignment_activities)
    if not due_so_far:
        return 0.0

    submitted = sum(1 for a in due_so_far if a.assignment_submission_time)
    if submitted == 0:
        return 0.0

    scores = []
    for act in due_so_far:
        due_date = getattr(act.assignment, "due_date", None)
        submitted_at = act.assignment_submission_time
        if not submitted_at:
            scores.append(0.0)
            continue
        if not due_date:
            scores.append(90.0)  # no explicit due date tracked yet — treat as on-time
            continue
        days_late = (submitted_at - due_date).days
        if days_late <= -2:
            scores.append(100.0)
        elif days_late <= 0:
            scores.append(90.0)
        else:
            scores.append(max(0.0, 90.0 - 15.0 * days_late))
    return round(sum(scores) / len(scores), 2)


# ─────────────────────────────────────────────────────────────────────────
# 4. Assignment Quality Score (graded submissions only)
# ─────────────────────────────────────────────────────────────────────────
def computeAQS(enrollment, assignment_activities=None):
    if assignment_activities is None:
        avg = AssignmentActivity.objects.filter(
            user=enrollment.user, course=enrollment.course, marks__gt=0
        ).filter(Q(status__iexact="Admin Reviewed") | Q(admin_review_time__isnull=False)).aggregate(avg=Avg("marks"))["avg"]
        return round(avg, 2) if avg else 0.0
    else:
        valid_marks = [
            act.marks for act in assignment_activities
            if act.course_id == enrollment.course_id
            and act.marks > 0
            and (
                (act.status and act.status.lower() == "admin reviewed")
                or act.admin_review_time is not None
            )
        ]
        if not valid_marks:
            return 0.0
        avg = sum(valid_marks) / len(valid_marks)
        return round(avg, 2)


# ─────────────────────────────────────────────────────────────────────────
# 5. Engagement Consistency Index
# ─────────────────────────────────────────────────────────────────────────
def computeECI(enrollment, lecture_activities=None, assignment_activities=None):
    start = enrollment.access_start_date or enrollment.purchase_date
    if not start:
        return 0.0

    days_elapsed = _days_since(start)
    if not _is_self_paced(enrollment):
        days_elapsed = min(days_elapsed, _course_duration_days(enrollment))
    days_elapsed = max(days_elapsed, 1)

    if lecture_activities is None:
        lecture_dates = set(
            LectureActivity.objects.filter(user=enrollment.user, course=enrollment.course, completed_at__isnull=False)
            .values_list("completed_at__date", flat=True)
        )
    else:
        lecture_dates = set()
        for act in lecture_activities:
            if act.course_id == enrollment.course_id and act.completed_at:
                dt = act.completed_at
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_default_timezone())
                lecture_dates.add(timezone.localdate(dt))

    if assignment_activities is None:
        assignment_dates = set(
            AssignmentActivity.objects.filter(
                user=enrollment.user, course=enrollment.course, assignment_submission_time__isnull=False
            ).values_list("assignment_submission_time__date", flat=True)
        )
    else:
        assignment_dates = set()
        for act in assignment_activities:
            if act.course_id == enrollment.course_id and act.assignment_submission_time:
                dt = act.assignment_submission_time
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_default_timezone())
                assignment_dates.add(timezone.localdate(dt))

    active_days = len(lecture_dates | assignment_dates)
    return round(_clamp((active_days / days_elapsed) * 100.0, 0, 100), 2)


# ─────────────────────────────────────────────────────────────────────────
# 6. Module Pace Adherence — fixed-deadline courses only, None if self-paced
# ─────────────────────────────────────────────────────────────────────────
def computeMPA(enrollment):
    if _is_self_paced(enrollment):
        return None  # weight redistributed in computeCCS

    total_course_days = _course_duration_days(enrollment)
    total_modules = enrollment.total_modules or 0
    if total_modules == 0 or total_course_days == 0:
        return 100.0

    days_since_enrollment = _days_since(enrollment.access_start_date or enrollment.purchase_date)
    expected_module = math.ceil((days_since_enrollment / total_course_days) * total_modules)
    modules_behind = max(0, expected_module - (enrollment.completed_modules or 0))
    return round(_clamp(100.0 - 20.0 * modules_behind, 0, 100), 2)


# ─────────────────────────────────────────────────────────────────────────
# 7. Optional Assignment Bonus
# ─────────────────────────────────────────────────────────────────────────
def computeOAB(enrollment, assignment_activities=None):
    if assignment_activities is None:
        graded = AssignmentActivity.objects.filter(
            user=enrollment.user, course=enrollment.course, marks__gt=0
        ).select_related("assignment").exclude(status="Pending")
    else:
        graded = [
            act for act in assignment_activities
            if act.course_id == enrollment.course_id
            and act.marks > 0
            and act.status != "Pending"
        ]
    optional_completed = sum(1 for a in graded if not getattr(a.assignment, "is_mandatory", True))
    return round(min(15.0, optional_completed * 3.0), 2)


# ─────────────────────────────────────────────────────────────────────────
# 8. Course Composite Score
# ─────────────────────────────────────────────────────────────────────────
def computeCCS(enrollment, assignment_activities=None, lecture_activities=None):
    metrics = {
        "PALC": computePALC(enrollment),
        "ASR": computeASR(enrollment, assignment_activities),
        "ATS": computeATS(enrollment, assignment_activities),
        "AQS": computeAQS(enrollment, assignment_activities),
        "ECI": computeECI(enrollment, lecture_activities, assignment_activities),
        "MPA": computeMPA(enrollment),
    }
    oab = computeOAB(enrollment, assignment_activities)

    if metrics["MPA"] is None:
        # self-paced: redistribute MPA's 0.15 weight proportionally across the other 5
        remaining = {k: w for k, w in CCS_WEIGHTS.items() if k != "MPA"}
        total_weight = sum(remaining.values())
        ccs = sum((w / total_weight) * metrics[k] for k, w in remaining.items())
    else:
        ccs = sum(CCS_WEIGHTS[k] * metrics[k] for k in CCS_WEIGHTS)

    ccs = _clamp(ccs + oab, 0, 100)
    metrics["OAB"] = oab
    return round(ccs, 2), metrics


# ─────────────────────────────────────────────────────────────────────────
# 9. Engagement Depth Weight (internal only)
# ─────────────────────────────────────────────────────────────────────────
def computeEDW(enrollment, lecture_activities=None, assignment_activities=None):
    lectures_total = enrollment.total_lectures or 0
    if lecture_activities is None:
        lectures_started = LectureActivity.objects.filter(user=enrollment.user, course=enrollment.course).count()
    else:
        lectures_started = sum(1 for act in lecture_activities if act.course_id == enrollment.course_id)

    lecture_start_ratio = (lectures_started / lectures_total) if lectures_total else 0.0

    expected_minutes = max((enrollment.completed_lectures or 0) * 15.0, 1.0)  # matches signals.py's 15 min/lecture
    actual_minutes = enrollment.study_minutes or 0.0
    time_spent_ratio = min(actual_minutes / expected_minutes, 1.0)

    total_modules = enrollment.total_modules or 0
    module_entry_ratio = ((enrollment.completed_modules or 0) / total_modules) if total_modules else 0.0

    total_assignments = enrollment.total_assignments or 0
    if assignment_activities is None:
        assignments_attempted = AssignmentActivity.objects.filter(user=enrollment.user, course=enrollment.course).count()
    else:
        assignments_attempted = sum(1 for act in assignment_activities if act.course_id == enrollment.course_id)

    assignment_attempt_ratio = (assignments_attempted / total_assignments) if total_assignments else 0.0

    edw = (
        0.30 * lecture_start_ratio
        + 0.30 * time_spent_ratio
        + 0.20 * module_entry_ratio
        + 0.20 * assignment_attempt_ratio
    )
    return round(_clamp(edw, 0, 1), 4)


# ─────────────────────────────────────────────────────────────────────────
# 10. Recency Weight
# ─────────────────────────────────────────────────────────────────────────
def computeRW(enrollment):
    days_since_last_activity = _days_since(enrollment.last_activity_at)
    return round(math.exp(-RW_LAMBDA * days_since_last_activity), 4)


# ─────────────────────────────────────────────────────────────────────────
# 11. Status Multiplier
# ─────────────────────────────────────────────────────────────────────────
def computeSM(enrollment, palc=None):
    if enrollment.course_status == "Completed":
        on_time = True
        if enrollment.actual_completion_date and enrollment.expected_completion_date:
            on_time = enrollment.actual_completion_date <= enrollment.expected_completion_date
        if on_time:
            return 1.15
        return 1.05 if _is_self_paced(enrollment) else 1.15

    days_since_last_activity = _days_since(enrollment.last_activity_at)
    if days_since_last_activity >= 30:
        return 0.70  # abandoned

    if not _is_self_paced(enrollment):
        days_since_enrollment = _days_since(enrollment.access_start_date or enrollment.purchase_date)
        if days_since_enrollment > _course_duration_days(enrollment):
            return 0.60  # expired, incomplete

    palc = computePALC(enrollment) if palc is None else palc
    return 1.00 if palc >= 90 else 0.90


# ─────────────────────────────────────────────────────────────────────────
# Follow-Through Ratio
# ─────────────────────────────────────────────────────────────────────────
def compute_follow_through(user_id):
    enrollments = list(StudentCourseAnalytics.objects.filter(user_id=user_id).select_related("course", "user"))
    courses_started = sum(1 for e in enrollments if e.course_status != "Not Started")
    courses_completed = sum(1 for e in enrollments if e.course_status == "Completed")
    courses_active_on_pace = sum(
        1 for e in enrollments if e.course_status == "In Progress" and computePALC(e) >= 90
    )
    ftr = ((courses_completed + courses_active_on_pace) / courses_started) if courses_started else 0.0
    return {
        "courses_started": courses_started,
        "courses_completed": courses_completed,
        "courses_active_on_pace": courses_active_on_pace,
        "ftr": round(ftr, 4),
    }


# ─────────────────────────────────────────────────────────────────────────
# 12. Deep Eigen Learning Score — the roll-up across all enrollments
# ─────────────────────────────────────────────────────────────────────────
def computeDELS(user_id):
    enrollments = list(StudentCourseAnalytics.objects.filter(user_id=user_id).select_related("course", "user"))

    # Pre-fetch all activity records exactly once
    assignment_activities = list(
        AssignmentActivity.objects.filter(user_id=user_id).select_related("assignment")
    )
    lecture_activities = list(
        LectureActivity.objects.filter(user_id=user_id)
    )

    enrollment_breakdown = []
    enrollments_to_persist = []
    weighted_sum, weight_sum = 0.0, 0.0

    for e in enrollments:
        ccs, metrics = computeCCS(e, assignment_activities=assignment_activities, lecture_activities=lecture_activities)
        edw = computeEDW(e, lecture_activities=lecture_activities, assignment_activities=assignment_activities)
        rw = computeRW(e)
        sm = computeSM(e, palc=metrics["PALC"])
        w_i = edw * rw * sm

        e.dels_contribution_weight = round(w_i, 4)
        enrollments_to_persist.append(e)

        weighted_sum += ccs * w_i
        weight_sum += w_i

        enrollment_breakdown.append({
            "course_id": e.course_id,
            "course_title": getattr(e.course, "title", ""),
            "CCS": ccs, "EDW": edw, "RW": rw, "SM": sm, "W": round(w_i, 4),
            **metrics,
        })

    dels_base = (weighted_sum / weight_sum) * 10.0 if weight_sum > 0 else 0.0

    # Inline follow-through calculation to reuse pre-fetched enrollments
    courses_started = sum(1 for e in enrollments if e.course_status != "Not Started")
    courses_completed = sum(1 for e in enrollments if e.course_status == "Completed")
    courses_active_on_pace = sum(
        1 for e in enrollments if e.course_status == "In Progress" and computePALC(e) >= 90
    )
    ftr = ((courses_completed + courses_active_on_pace) / courses_started) if courses_started else 0.0
    ca = _clamp((ftr - 0.5) * 100.0, -40.0, 40.0) if courses_started else 0.0
    dels_raw = dels_base + ca

    yesterday = timezone.now().date() - timedelta(days=1)
    prior_snapshot = (
        DELSSnapshot.objects.filter(user_id=user_id, date=yesterday).first()
        or DELSSnapshot.objects.filter(user_id=user_id).order_by("-date").first()
    )
    dels_yesterday = prior_snapshot.dels_value if prior_snapshot else dels_raw

    dels_today = EMA_BETA * dels_raw + (1 - EMA_BETA) * dels_yesterday

    had_activity_today = any(
        e.last_activity_at and e.last_activity_at.date() == timezone.now().date() for e in enrollments
    )
    if not had_activity_today and enrollments:
        most_recent_gap = min(_days_since(e.last_activity_at) for e in enrollments)
        if most_recent_gap > 7:
            dels_today *= (1 - INACTIVITY_DECAY)

    dels_today = round(_clamp(dels_today, 0, 1000), 2)
    tier = tier_for(dels_today)

    return {
        "dels": dels_today,
        "tier": tier,
        "ftr": ftr,
        "breakdown": {
            "enrollments": enrollment_breakdown,
            "ca": round(ca, 2),
            "dels_base": round(dels_base, 2),
            "delta_vs_yesterday": round(dels_today - dels_yesterday, 2),
        },
        "_enrollments_to_persist": enrollments_to_persist,
    }


def compute_dels_preview(user):
    """On-demand DELS computation for display — does NOT persist a DELSSnapshot
    (that's compute_dels's job, to keep the EMA smoothing correct at one write/day)."""
    return computeDELS(user.id)


def run_compute_dels_job():
    """
    Nightly/Scheduled Batch Job (DELS Spec §6):
    1. Reconciles raw data via sync_user_analytics for all active users with course activity.
    2. Computes DELS and creates/updates a daily DELSSnapshot for today.
    3. Updates StudentAnalytics.overall_performance_score and StudentCourseAnalytics.course_performance_score.
    4. Updates student rankings across the platform.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    today = timezone.now().date()

    # Filter to users with enrolled courses or progress records
    active_user_ids = set(EnrolledUser.objects.filter(enrolled=True).values_list("user_id", flat=True))
    active_user_ids.update(OverallProgress.objects.filter(progress__gt=0).values_list("user_id", flat=True))
    active_user_ids.update(StudentCourseAnalytics.objects.values_list("user_id", flat=True))

    active_users = User.objects.filter(id__in=active_user_ids, is_active=True)
    for user in active_users:
        try:
            sync_user_analytics(user)
            dels_res = computeDELS(user.id)

            DELSSnapshot.objects.update_or_create(
                user=user,
                date=today,
                defaults={
                    "dels_value": dels_res["dels"],
                    "tier": dels_res["tier"],
                    "breakdown_json": dels_res["breakdown"],
                },
            )

            sa, _ = StudentAnalytics.objects.get_or_create(user=user)
            sa.overall_performance_score = dels_res["dels"]
            sa.save(update_fields=["overall_performance_score"])

            eb_map = {item["course_id"]: item["CCS"] for item in dels_res["breakdown"]["enrollments"]}
            for e in dels_res.get("_enrollments_to_persist", []):
                if e.course_id in eb_map:
                    e.course_performance_score = round(eb_map[e.course_id] * 10.0, 1)
                e.save(update_fields=["dels_contribution_weight", "course_performance_score"])
        except Exception:
            continue

    all_analytics = list(StudentAnalytics.objects.order_by("-overall_performance_score"))
    for rank, sa in enumerate(all_analytics, start=1):
        sa.student_rank = rank
        sa.save(update_fields=["student_rank"])



# ─────────────────────────────────────────────────────────────────────────
# Legacy-shaped summary builders (keep the existing frontend contract intact)
# ─────────────────────────────────────────────────────────────────────────
def build_assignment_analytics_summary(
    *,
    total_assignments,
    submitted_assignments,
    reviewed_assignments,
    reviewed_marks_total,
    started_courses_count,
    purchased_courses_count,
):
    total_assignments = int(total_assignments or 0)
    submitted_assignments = int(submitted_assignments or 0)
    reviewed_assignments = int(reviewed_assignments or 0)
    reviewed_marks_total = float(reviewed_marks_total or 0.0)

    pending_review_assignments = max(0, submitted_assignments - reviewed_assignments)
    assignment_progress_percentage = round(
        (submitted_assignments / total_assignments) * 100.0, 1
    ) if total_assignments else 0.0
    assignment_average_performance = round(
        (reviewed_marks_total / (reviewed_assignments * 100.0)) * 100.0, 1
    ) if reviewed_assignments else 0.0

    return {
        "total_assignments": total_assignments,
        "assignments_submitted": submitted_assignments,
        "assignments_reviewed": reviewed_assignments,
        "assignments_pending_review": pending_review_assignments,
        "assignment_progress_percentage": assignment_progress_percentage,
        "assignment_average_performance": assignment_average_performance,
        "started_courses": int(started_courses_count or 0),
        "purchased_courses": int(purchased_courses_count or 0),
    }


def _legacy_breakdown_from_dels(dels_result: dict) -> dict:
    """
    Maps the new CCS sub-metrics (0-100 scale, per enrollment) into the old
    3-bucket shape (assignment_performance/lecture_completion/consistency,
    each with earned/max/percent) so the existing frontend keeps working
    unchanged. `overall` is the real DELS value (0-1000).
    """
    enrollments = dels_result["breakdown"]["enrollments"]
    n = len(enrollments) or 1

    avg_aqs = sum(e["AQS"] for e in enrollments) / n if enrollments else 0.0
    avg_asr = sum(e["ASR"] for e in enrollments) / n if enrollments else 0.0
    avg_ats = sum(e["ATS"] for e in enrollments) / n if enrollments else 0.0
    avg_palc = sum(e["PALC"] for e in enrollments) / n if enrollments else 0.0
    avg_eci = sum(e["ECI"] for e in enrollments) / n if enrollments else 0.0

    assignment_pct = (avg_aqs * 0.6 + avg_asr * 0.2 + avg_ats * 0.2)
    assignment_points = round(min(500.0, assignment_pct / 100.0 * 500.0), 1)

    lecture_points = round(min(350.0, avg_palc / 100.0 * 350.0), 1)
    consistency_points = round(min(150.0, avg_eci / 100.0 * 150.0), 1)

    overall = dels_result["dels"]

    return {
        "assignment_performance": {"earned": assignment_points, "max": 500, "percent": round(assignment_pct, 1)},
        "lecture_completion": {"earned": lecture_points, "max": 350, "percent": round(avg_palc, 1)},
        "consistency": {"earned": consistency_points, "max": 150, "percent": round(avg_eci, 1)},
        "overall": {"earned": round(overall, 0), "max": 1000, "percent": round(overall / 10.0, 1)},
    }


def compute_streak_consistency_points(streak: int) -> float:
    """
    Calculates consistency points (Max 150 pts) based on 7-day milestone stages:
    - 0 days streak: 0 pts (broken streak)
    - 1-6 days streak: 2 pts per day (Day 1: 2, Day 2: 4 ... Day 6: 12)
    - 7-13 days streak (Stage 1 - 7 Days): 20 pts base + 4 pts/day for days 8-13 (Day 7: 20 pts, Day 13: 44 pts)
    - 14-20 days streak (Stage 2 - 14 Days): 50 pts base + 5 pts/day for days 15-20 (Day 14: 50 pts, Day 20: 80 pts)
    - 21-27 days streak (Stage 3 - 21 Days): 85 pts base + 5 pts/day for days 22-27 (Day 21: 85 pts, Day 27: 115 pts)
    - 28-34 days streak (Stage 4 - 28 Days): 120 pts base + 5 pts/day for days 29-34 (Day 28: 120 pts, Day 34: 145 pts)
    - 35+ days streak (Stage 5 - 35 Days): 150 pts (Max points)
    """
    if streak <= 0:
        return 0.0
    elif streak < 7:
        return round(float(streak * 2), 1)
    elif streak < 14:
        return round(20.0 + (streak - 7) * 4.0, 1)
    elif streak < 21:
        return round(50.0 + (streak - 14) * 5.0, 1)
    elif streak < 28:
        return round(85.0 + (streak - 21) * 5.0, 1)
    elif streak < 35:
        return round(120.0 + (streak - 28) * 5.0, 1)
    else:
        return 150.0


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
    total_assignments=None,
    assignment_progress_percentage=None,
    assignment_average_performance=None,
    dels_result=None,
):
    assignment_average = float(getattr(analytics, "average_assignment_score", 0.0) or 0.0)
    overall_score = float(getattr(analytics, "overall_performance_score", 0.0) or 0.0)

    if dels_result is not None:
        breakdown = _legacy_breakdown_from_dels(dels_result)
        overall_score = dels_result["dels"]
    else:
        breakdown = {
            "assignment_performance": {"earned": round(min(500, overall_score * 0.5), 1), "max": 500, "percent": round(overall_score / 10.0, 1)},
            "lecture_completion": {"earned": round(min(350, overall_score * 0.35), 1), "max": 350, "percent": round(overall_score / 10.0, 1)},
            "consistency": {"earned": round(min(150, overall_score * 0.15), 1), "max": 150, "percent": round(overall_score / 10.0, 1)},
            "overall": {"earned": round(overall_score, 0), "max": 1000, "percent": round(overall_score / 10.0, 1)},
        }

    total_purchased = int(total_courses_purchased or 0)
    completed_courses = int(getattr(analytics, "total_courses_completed", 0) or 0)
    if lecture_completion_percent is not None:
        overall_completion = round(lecture_completion_percent, 1)
    elif total_purchased:
        overall_completion = round((completed_courses / total_purchased) * 100.0, 1)
    else:
        overall_completion = 0.0

    streak = int(getattr(analytics, "current_learning_streak", 0) or 0)
    consistency_pts = compute_streak_consistency_points(streak)

    breakdown["consistency"] = {
        "earned": consistency_pts,
        "max": 150,
        "percent": round((consistency_pts / 150.0) * 100.0, 1),
    }

    # Overall score equals the exact sum of the 3 breakdown categories
    overall_score = round(
        breakdown["assignment_performance"]["earned"]
        + breakdown["lecture_completion"]["earned"]
        + breakdown["consistency"]["earned"],
        0
    )

    breakdown["overall"] = {
        "earned": overall_score,
        "max": 1000,
        "percent": round(overall_score / 10.0, 1),
    }

    return {
        "overall_completion": overall_completion,
        "overall_performance_score": overall_score,
        "performance_points_earned": overall_score,
        "performance_points_max": 1000,
        "assignment_average": round(assignment_average, 1),
        "completed_courses": completed_courses,
        "total_courses_purchased": total_purchased,
        "study_time_minutes": int(getattr(analytics, "total_study_minutes", 0) or 0),
        "study_hours": round((getattr(analytics, "total_study_minutes", 0) or 0) / 60.0, 1),
        "consistency_score": breakdown["consistency"]["earned"],
        "completion_speed": 0,
        "internship_eligible": bool(getattr(analytics, "internship_eligible", False)),
        "videos_completed": int(total_lectures_completed or 0),
        "assignments_submitted": int(assignments_submitted or 0),
        "assignments_reviewed": int(assignments_reviewed or 0),
        "assignments_pending_review": int(assignments_pending or 0),
        "lectures_completed": int(total_lectures_completed or 0),
        "lectures_completed_percent": round(lecture_completion_percent or 0.0, 1),
        "modules_completed": int(total_modules_completed or 0),
        "learning_streak": streak,
        "score_breakdown": breakdown,
    }


def get_started_course_assignment_analytics(user):
    """Aggregate assignment counts and marks across all started courses only. Pure data aggregation, not scoring."""
    started_course_ids = set(
        StudentCourseAnalytics.objects.filter(
            user=user, course_status__in=["In Progress", "Completed"],
        ).values_list("course_id", flat=True)
    )

    enrolled_course_ids = set(
        EnrolledUser.objects.filter(user=user, enrolled=True).values_list("course_id", flat=True)
    )

    if enrolled_course_ids:
        started_from_activity = set(
            AssignmentEvaluation.objects.filter(
                user=user, course_id__in=enrolled_course_ids, submit_flag=True,
            ).values_list("course_id", flat=True)
        )
        started_from_activity |= set(
            OverallProgress.objects.filter(
                user=user, course_id__in=enrolled_course_ids, progress__gt=0,
            ).values_list("course_id", flat=True)
        )
        started_course_ids |= started_from_activity

    started_course_ids = sorted(started_course_ids)

    total_assignments = Assignment.objects.filter(course_id__in=started_course_ids).count() if started_course_ids else 0

    submitted_evals = AssignmentEvaluation.objects.filter(
        user=user, course_id__in=started_course_ids, submit_flag=True,
    )
    submitted_assignments = submitted_evals.count() if started_course_ids else 0

    reviewed_evals = submitted_evals.filter(score__gt=0)
    reviewed_assignments = reviewed_evals.count() if started_course_ids else 0
    reviewed_marks_total = float(reviewed_evals.aggregate(total=Sum("score"))["total"] or 0.0)

    return build_assignment_analytics_summary(
        total_assignments=total_assignments,
        submitted_assignments=submitted_assignments,
        reviewed_assignments=reviewed_assignments,
        reviewed_marks_total=reviewed_marks_total,
        started_courses_count=len(started_course_ids),
        purchased_courses_count=len(enrolled_course_ids),
    )


def recalculate_user_streak(user, analytics=None):
    """
    Recalculates current and longest learning streak for `user`.
    A streak is active ONLY if there is activity today OR yesterday.
    If the last activity date is before yesterday, current_learning_streak is 0 (broken).
    """
    from .models import StudentAnalytics, DailyLearningActivity, LectureActivity, AssignmentActivity
    from course.models import UserVideoProgress
    from django.utils import timezone
    from datetime import timedelta

    if analytics is None:
        analytics, _ = StudentAnalytics.objects.get_or_create(user=user)

    active_dates = set()

    # 1. DailyLearningActivity (study_time >= 30 or assignments_submitted > 0)
    for d in DailyLearningActivity.objects.filter(user=user):
        if (d.study_time and d.study_time >= 30) or (d.assignments_submitted and d.assignments_submitted > 0):
            active_dates.add(d.date)

    # 2. LectureActivity (completed lectures)
    for la in LectureActivity.objects.filter(user=user, is_completed=True):
        if la.completed_at:
            active_dates.add(la.completed_at.date())

    # 3. UserVideoProgress (completed videos)
    for uv in UserVideoProgress.objects.filter(user=user, completed=True):
        if uv.created_at:
            active_dates.add(uv.created_at.date())

    # 4. AssignmentActivity (submitted assignments)
    for aa in AssignmentActivity.objects.filter(user=user):
        if aa.assignment_submission_time:
            active_dates.add(aa.assignment_submission_time.date())

    sorted_dates = sorted(active_dates)
    current_streak = 0

    if sorted_dates:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        last_active = sorted_dates[-1]

        # Streak is ONLY active if last activity was today or yesterday
        if last_active >= yesterday:
            current_streak = 1
            prev_date = last_active
            for d in reversed(sorted_dates[:-1]):
                if d == prev_date - timedelta(days=1):
                    current_streak += 1
                    prev_date = d
                elif d == prev_date:
                    continue
                else:
                    break

    analytics.current_learning_streak = current_streak
    analytics.longest_learning_streak = max(analytics.longest_learning_streak or 0, current_streak)
    analytics.save(update_fields=['current_learning_streak', 'longest_learning_streak'])

    return current_streak


def sync_user_analytics(user):
    """
    Rebuild COUNTS and DATES for `user` from raw course data. Safe to call
    repeatedly (idempotent). Does NOT compute overall_performance_score or
    course_performance_score — those are DELS values, written by
    `python manage.py compute_dels`.
    """
    analytics, _ = StudentAnalytics.objects.get_or_create(user=user)
    recalculate_user_streak(user)

    enrolled_qs = EnrolledUser.objects.filter(user=user, enrolled=True).select_related("course").order_by("created_at")

    unified_course_access = {}
    for enroll in enrolled_qs:
        unified_course_access[enroll.course.id] = {
            "course": enroll.course,
            "purchase_date": enroll.created_at,
            "duration_months": getattr(enroll.course, "duration", 0) or 6,
            "access_source": "purchase",
        }

    from subscriptions.models import UserSubscription, PlanCategoryAccess
    from course.models import Course, Video

    active_subscriptions = UserSubscription.objects.filter(user=user, is_active=True).select_related("plan").order_by("start_date")
    for sub in active_subscriptions:
        categories = PlanCategoryAccess.objects.filter(plan_type=sub.plan.plan_type).values_list("category", flat=True)
        sub_courses = Course.objects.filter(category__in=categories, is_featured=True)

        for c in sub_courses:
            if c.id not in unified_course_access:
                has_progress = OverallProgress.objects.filter(user=user, course=c, progress__gt=0).exists()
                has_video = UserVideoProgress.objects.filter(user=user, course=c, completed=True).exists()
                if has_progress or has_video:
                    unified_course_access[c.id] = {
                        "course": c,
                        "purchase_date": sub.start_date,
                        "duration_months": getattr(c, "duration", 0) or 6,
                        "access_source": "subscription",
                    }

    analytics.total_courses_purchased = len(unified_course_access)

    total_lectures = 0
    total_modules = 0
    completed_courses = 0
    total_assignments_submitted = 0
    total_assignments_reviewed = 0
    total_assignments_pending = 0
    total_score_sum = 0.0  # for average_assignment_score only, not for scoring

    for access_data in unified_course_access.values():
        course = access_data["course"]
        course_analytics, _ = StudentCourseAnalytics.objects.get_or_create(user=user, course=course)

        course_duration_months = access_data["duration_months"]
        course_duration_days = course_duration_months * 30
        purchase_date = access_data["purchase_date"]
        expected_completion_date = purchase_date + timedelta(days=course_duration_days)

        if not course_analytics.purchase_date:
            course_analytics.purchase_date = purchase_date
            course_analytics.access_start_date = purchase_date
            course_analytics.expected_course_duration = course_duration_days
            course_analytics.expected_completion_date = expected_completion_date

        course_analytics.access_source = access_data["access_source"]

        progress = OverallProgress.objects.filter(user=user, course=course).first()
        if progress:
            course_analytics.completion_percentage = float(progress.progress)
            if float(progress.progress) >= 100:
                if course_analytics.course_status != "Completed":
                    course_analytics.course_status = "Completed"
                    course_analytics.dels_status = "completed"
                    if not course_analytics.actual_completion_date:
                        course_analytics.actual_completion_date = timezone.now()
                completed_courses += 1
            elif float(progress.progress) > 0:
                course_analytics.course_status = "In Progress"
        else:
            course_analytics.completion_percentage = 0.0

        videos_done = UserVideoProgress.objects.filter(user=user, course=course, completed=True)
        lect_count = videos_done.count()

        total_lectures_count = Video.objects.filter(module__section__course=course).count()
        course_analytics.total_lectures = total_lectures_count

        if course_analytics.course_status == "Completed" and total_lectures_count > lect_count:
            lect_count = total_lectures_count

        course_analytics.completed_lectures = lect_count
        total_lectures += lect_count

        for vp in videos_done:
            LectureActivity.objects.get_or_create(
                user=user, course=course, lecture=vp.video,
                defaults={"is_completed": True, "completed_at": timezone.now()},
            )

        evals = AssignmentEvaluation.objects.filter(user=user, course=course).select_related("assignment").order_by("created_at")

        course_asgn_score_sum = 0.0
        course_asgn_reviewed = 0
        course_asgn_pending = 0

        for ev in evals:
            score_f = float(ev.score)
            submitted_at = ev.created_at
            is_submitted = bool(ev.submit_flag or submitted_at)
            is_reviewed = score_f > 0

            if is_reviewed:
                course_asgn_score_sum += score_f
                course_asgn_reviewed += 1
            elif is_submitted:
                course_asgn_pending += 1

            status_label = "Admin Reviewed" if is_reviewed else ("Submitted" if is_submitted else "Pending")
            acts = AssignmentActivity.objects.filter(user=user, course=course, assignment=ev.assignment).order_by("id")
            if acts.exists():
                act = acts.first()
                created = False
                if acts.count() > 1:
                    acts.exclude(id=act.id).delete()
            else:
                act = AssignmentActivity.objects.create(
                    user=user, course=course, assignment=ev.assignment,
                    marks=score_f, status=status_label,
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
            course_asgn_score_sum / course_asgn_reviewed if course_asgn_reviewed > 0 else 0.0
        )
        course_analytics.save()

        total_assignments_submitted += course_asgn_submitted
        total_assignments_reviewed += course_asgn_reviewed
        total_assignments_pending += course_asgn_pending
        total_score_sum += course_asgn_score_sum
        total_modules += course_analytics.completed_modules

    analytics.total_courses_completed = completed_courses
    analytics.total_lectures_completed = total_lectures
    analytics.total_assignments_completed = total_assignments_submitted
    analytics.average_assignment_score = (
        total_score_sum / total_assignments_reviewed if total_assignments_reviewed > 0 else 0.0
    )
    analytics.total_modules_completed = total_modules
    # NOTE: overall_performance_score / internship_eligible are intentionally
    # NOT set here — `compute_dels` owns them.
    analytics.save()

    analytics._assignments_reviewed = total_assignments_reviewed
    analytics._assignments_pending = total_assignments_pending
    analytics._assignments_submitted = total_assignments_submitted

    return analytics