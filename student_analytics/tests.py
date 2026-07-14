from types import SimpleNamespace

from django.test import SimpleTestCase

from .utils import build_student_overview_summary


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
        self.assertEqual(summary["performance_points_earned"], 748)
        self.assertEqual(summary["performance_points_max"], 1000)
        self.assertEqual(summary["consistency_score"], 60)
        self.assertEqual(summary["study_time_minutes"], 180)
        self.assertEqual(summary["internship_eligible"], True)
