from types import SimpleNamespace

from django.test import SimpleTestCase

from .utils import build_student_overview_summary, build_assignment_analytics_summary


class StudentOverviewSummaryTests(SimpleTestCase):
    def test_builds_points_and_streak_metrics_from_student_analytics(self):
        analytics = SimpleNamespace(
            total_courses_completed=2,
            total_courses_purchased=4,
            total_study_minutes=180,
            current_learning_streak=5,
            average_assignment_score=88,
            overall_performance_score=748,
            internship_eligible=True,
            total_lectures_completed=32,
            total_modules_completed=6,
        )

        summary = build_student_overview_summary(
            analytics,
            total_courses_purchased=4,
            assignments_reviewed=3,
            assignments_pending=1,
            assignments_submitted=4,
            total_lectures_completed=32,
            total_modules_completed=6,
        )

        self.assertEqual(summary["overall_completion"], 50.0)
        self.assertEqual(summary["performance_points_earned"], 260)
        self.assertEqual(summary["performance_points_max"], 1000)
        self.assertEqual(summary["consistency_score"], 40)
        self.assertEqual(summary["study_time_minutes"], 180)
        self.assertEqual(summary["internship_eligible"], True)

    def test_builds_assignment_analytics_from_started_courses_only(self):
        summary = build_assignment_analytics_summary(
            total_assignments=48,
            submitted_assignments=42,
            reviewed_assignments=37,
            reviewed_marks_total=3525,
            started_courses_count=3,
            purchased_courses_count=4,
        )

        self.assertEqual(summary["total_assignments"], 48)
        self.assertEqual(summary["assignments_submitted"], 42)
        self.assertEqual(summary["assignments_reviewed"], 37)
        self.assertEqual(summary["assignments_pending_review"], 5)
        self.assertEqual(summary["assignment_progress_percentage"], 87.5)
        self.assertEqual(summary["assignment_average_performance"], 95.3)
        self.assertEqual(summary["started_courses"], 3)
        self.assertEqual(summary["purchased_courses"], 4)
