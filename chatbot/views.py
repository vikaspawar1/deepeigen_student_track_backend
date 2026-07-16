from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ChatbotFAQ, ChatbotReminder, ChatbotConversation
import json


def _auto_delete_old_conversations(user):
    """Delete conversations older than 24 hours for the given user."""
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=24)
    ChatbotConversation.objects.filter(user=user, timestamp__lt=cutoff).delete()


def calculate_points_and_analytics(user):
    from student_analytics.models import StudentAnalytics, StudentCourseAnalytics, DailyLearningActivity
    from student_analytics.utils import build_student_overview_summary, get_started_course_assignment_analytics
    from django.db.models import Sum, Q

    analytics, _ = StudentAnalytics.objects.get_or_create(user=user)

    started_course_assignment_analytics = get_started_course_assignment_analytics(user)
    assignments_submitted = started_course_assignment_analytics['assignments_submitted']
    admin_reviewed_count = started_course_assignment_analytics['assignments_reviewed']
    pending_review_count = started_course_assignment_analytics['assignments_pending_review']

    total_study_minutes = DailyLearningActivity.objects.filter(user=user).aggregate(
        total=Sum('study_time')
    )['total'] or 0.0
    analytics.total_study_minutes = total_study_minutes

    streak_dates = list(
        DailyLearningActivity.objects.filter(
            Q(user=user) & (Q(study_time__gte=30) | Q(assignments_submitted__gt=0))
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

    course_analytics_qs = StudentCourseAnalytics.objects.filter(user=user).select_related('course')
    lecture_completion_total = 0.0
    course_count = 0

    for c in course_analytics_qs:
        course_count += 1
        lecture_total = c.total_lectures or 0
        lecture_percent = round((c.completed_lectures / lecture_total) * 100, 1) if lecture_total else 0.0
        lecture_completion_total += lecture_percent

    avg_lecture_percent = round(lecture_completion_total / course_count, 1) if course_count else 0.0

    # Pass assignment_progress_percentage and assignment_average_performance
    # so the score matches the dashboard exactly.
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
    )

    # Use live analytics summary data here so chatbot matches the dashboard's current overall score.
    points = int(summary.get('overall_performance_score', 0))

    return {
        'points': points,
        'lectures': summary.get('lectures_completed', 0),
        'assignments': summary.get('assignments_submitted', 0),
        'streak': summary.get('learning_streak', 0),
        'avg_lecture_percent': avg_lecture_percent,
        'assignment_progress_percentage': started_course_assignment_analytics['assignment_progress_percentage'],
        'assignment_average_performance': started_course_assignment_analytics['assignment_average_performance'],
    }


def _get_study_activity_today_yesterday(user):
    """
    Returns (active_today, active_yesterday) based on DailyLearningActivity
    which is the same source the dashboard streak uses (30 min study OR assignment submitted).
    """
    from student_analytics.models import DailyLearningActivity
    from django.utils import timezone
    from django.db.models import Q

    now = timezone.now()
    today = now.date()
    yesterday = (now - __import__('datetime').timedelta(days=1)).date()

    active_today = DailyLearningActivity.objects.filter(
        Q(user=user) & Q(date=today) & (Q(study_time__gte=30) | Q(assignments_submitted__gt=0))
    ).exists()

    active_yesterday = DailyLearningActivity.objects.filter(
        Q(user=user) & Q(date=yesterday) & (Q(study_time__gte=30) | Q(assignments_submitted__gt=0))
    ).exists()

    return active_today, active_yesterday


class ChatbotHomeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        from course.models import EnrolledUser, UserVideoProgress
        from django.utils import timezone

        # Auto-delete conversations older than 24 hours
        _auto_delete_old_conversations(user)

        now = timezone.now()

        # Build real reminders list
        reminders = []

        # 1. Payment reminder — check for unpaid installments
        enrollments = EnrolledUser.objects.filter(user=user, enrolled=True, end_at__gt=now)
        for enrollment in enrollments:
            if enrollment.no_of_installments > 1:
                if not enrollment.second_installments:
                    reminders.append({
                        "id": "pay-2",
                        "type": "payment",
                        "link": "/accounts/billings_invoices",
                        "message": f"Payment Reminder: Your installment for '{enrollment.course.title}' is pending. Click here to go to Billing & Invoices and complete your payment to avoid losing access."
                    })
                    break
                elif enrollment.no_of_installments == 3 and not enrollment.third_installments:
                    reminders.append({
                        "id": "pay-3",
                        "type": "payment",
                        "link": "/accounts/billings_invoices",
                        "message": f"Final Payment Reminder: Your last installment for '{enrollment.course.title}' is pending. Click here to complete it and retain full access."
                    })
                    break

        # 2. Study streak reminder — use DailyLearningActivity (same source as dashboard streak)
        active_today, active_yesterday = _get_study_activity_today_yesterday(user)

        # Get last watched video for redirect link
        last_video = UserVideoProgress.objects.filter(user=user).order_by('-created_at').first()
        lecture_link = "/dashboard"
        if last_video:
            lecture_link = f"/course-view/{last_video.course.id}/{last_video.course.url_link_name}"

        if active_today:
            streak_msg = "Great work today! You've completed today's learning activity and earned your daily point. Keep this streak going — consistency is the key to mastery!"
            streak_link = lecture_link
        elif active_yesterday and not active_today:
            streak_msg = "Streak Alert! You were active yesterday but haven't completed today's learning yet. Your streak is about to break! Click here to continue and earn today's point."
            streak_link = lecture_link
        else:
            streak_msg = "Daily Learning Reminder: You haven't been active recently. Study for 30+ minutes or submit an assignment every day to earn points, maintain your streak, and stay on track!"
            streak_link = lecture_link

        reminders.append({
            "id": "streak",
            "type": "streak",
            "link": streak_link,
            "message": streak_msg
        })

        # Calculate exact current points using the same logic as the dashboard
        stats = calculate_points_and_analytics(user)
        points = stats['points']

        response_data = {
            "student_name": user.first_name or user.username,
            "points": points,
            "performance": {},
            "reminders": reminders,
            "suggested_questions": [
                "My Courses",
                "Show my progress",
                "Overall Score",
                "Assignments",
                "Payment",
                "Invoices",
                "Study Reminder",
                "Contact Support"
            ]
        }
        return Response(response_data)


class ChatbotRemindersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reminders = ChatbotReminder.objects.all()
        data = [
            {"id": r.id, "title": r.title, "message": r.message, "type": r.reminder_type}
            for r in reminders
        ]
        if not data:
            data = [
                {"id": "a1", "title": "Pending Assignment", "message": "You have 2 pending assignments.", "type": "pending_assignment"},
                {"id": "a2", "title": "Study Reminder", "message": "You haven't studied for 5 days.", "type": "inactive_days"},
            ]
        return Response(data)


class ChatbotFAQsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        faqs = ChatbotFAQ.objects.all()
        data = [{"id": faq.id, "question": faq.question, "answer": faq.answer} for faq in faqs]
        return Response(data)


class ChatbotMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        message = request.data.get("message", "").lower().strip()

        # Auto-delete conversations older than 24 hours on every interaction
        _auto_delete_old_conversations(user)

        reply = "I'm sorry, I didn't understand that. You can ask about: My Courses, Progress, Overall Score, Assignments, Payment, Invoices, Study Reminder, or Contact Support."

        # Keyword matching logic imports
        from course.models import EnrolledUser, OverallProgress, AssignmentEvaluation, UserVideoProgress
        from subscriptions.models import UserSubscription
        from django.utils import timezone
        from datetime import timedelta

        # Small talk and greetings
        handled = False
        if any(kw in message for kw in ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening"]):
            reply = f"Hello {user.first_name or user.username}! 👋 I'm your study assistant. Ask me about your courses, progress, payments, assignments, or study reminders."
            handled = True
        elif any(kw in message for kw in ["how are you", "how r you", "how are u", "how are things", "how is it going", "what's up", "whats up"]):
            reply = "I'm doing great, thanks for asking! 😊 I'm here to help you stay on track with your courses, progress, assignments, payments, and study reminders."
            handled = True
        elif any(kw in message for kw in ["thank you", "thanks", "thx", "appreciate it"]):
            reply = "You're welcome! If you have any questions about your courses, progress, assignments, or payments, just ask."
            handled = True
        elif any(kw in message for kw in ["bye", "goodbye", "see you", "talk later", "later"]):
            reply = "Goodbye! If you need help again, just send me a message and I'll be here to support your learning."
            handled = True

        if not handled:
            if any(kw in message for kw in ["my courses", "my course", "course", "purchased", "access"]):
                enrolled = EnrolledUser.objects.filter(user=user, enrolled=True)
                subs = UserSubscription.objects.filter(user=user, is_active=True)
                courses = [e.course.title for e in enrolled]
                sub_plans = [s.plan.plan_type for s in subs]

                if courses or sub_plans:
                    reply = "Your Enrolled Courses & Plans:\n"
                    if courses:
                        for c in courses:
                            reply += f"  • {c}\n"
                    if sub_plans:
                        reply += "\nActive Subscriptions:\n"
                        for p in sub_plans:
                            reply += f"  • {p} Plan\n"
                    reply += "\nGo to your Dashboard to continue learning!"
                else:
                    reply = "You haven't purchased any courses yet. Visit our Courses page to explore available courses."

            elif any(kw in message for kw in ["overall score", "overall", "score", "performance"]):
                stats = calculate_points_and_analytics(user)
                points = stats['points']
                lectures = stats['lectures']
                assignments = stats['assignments']
                streak = stats['streak']
                avg_lecture_pct = stats['assignment_progress_percentage']
                asgn_avg = stats['assignment_average_performance']

                reply = f"Your Overall Performance:\n\n"
                reply += f"Total Points: {points} / 1000 pts\n"
                reply += f"  • Lectures Completed: {lectures} ({stats['avg_lecture_percent']}% of course content)\n"
                reply += f"  • Assignments Submitted: {assignments}\n"
                reply += f"  • Assignment Progress: {avg_lecture_pct}%\n"
                reply += f"  • Assignment Avg Score: {asgn_avg}%\n"
                reply += f"  • Learning Streak: {streak} days\n\n"
                progresses = OverallProgress.objects.filter(user=user)
                if progresses.exists():
                    reply += "Course-wise Progress:\n"
                    for p in progresses:
                        reply += f"  • {p.course.title}: {p.progress}%\n"
                    reply += "\nStart watching lectures and submitting assignments to earn more points!"
                else:
                    reply += "\nStart watching lectures and submitting assignments to earn more points!"

            elif any(kw in message for kw in ["progress", "completion"]):
                progresses = OverallProgress.objects.filter(user=user)
                if progresses.exists():
                    reply = "Your Course Progress:\n"
                    for p in progresses:
                        reply += f"  • {p.course.title}: {p.progress}% completed\n"
                else:
                    reply = "No progress data yet. Start watching lectures to track your progress!"

            elif any(kw in message for kw in ["assignment", "assignments", "submit"]):
                evals = AssignmentEvaluation.objects.filter(user=user).order_by('-created_at')
                if evals.exists():
                    total = evals.count()
                    reply = f"Your Assignments ({total} total):\n"
                    for e in evals:
                        status = "Submitted" if e.submit_flag else "Pending"
                        reply += f"  • {e.assignment.name} — {status}\n"
                else:
                    reply = "You don't have any assignment submissions yet."

            elif any(kw in message for kw in ["payment", "billing", "due", "payment reminder"]):
                now = timezone.now()
                enrollments = EnrolledUser.objects.filter(user=user, enrolled=True, end_at__gt=now)
                pending_list = []
                for enrollment in enrollments:
                    if enrollment.no_of_installments > 1:
                        if not enrollment.second_installments:
                            pending_list.append(f"  • {enrollment.course.title} — 2nd Installment pending")
                        elif enrollment.no_of_installments == 3 and not enrollment.third_installments:
                            pending_list.append(f"  • {enrollment.course.title} — 3rd Installment pending")
                if pending_list:
                    reply = "Pending Payments:\n" + "\n".join(pending_list)
                    reply += "\n\nPlease visit Billing & Invoices to complete your payment."
                else:
                    reply = "All payments are up to date. You have no pending installments."

            elif "invoice" in message:
                reply = "Your invoices are available in the Billing & Invoices section of your dashboard.\n\nYou can view and download all your purchase invoices from there.\n\n Go to: Dashboard → Billing & Invoices"

            elif any(kw in message for kw in ["study reminder", "study", "streak", "reminder"]):
                active_today, active_yesterday = _get_study_activity_today_yesterday(user)
                if active_today:
                    reply = "You're on fire! You've already completed today's learning activity and earned your daily point.\n\nKeep this daily habit going — consistency is what separates successful students from the rest!\n\n Daily Goal: Study 30+ minutes or submit an assignment"
                elif active_yesterday:
                    reply = "Streak Alert! You were active yesterday but haven't completed today's learning yet.\n\nYour streak will break if you don't study or submit an assignment today!\n\n Go to your Dashboard and continue from where you left off.\n\n Reward: Every active day = streak point earned!"
                else:
                    reply = "Daily Learning Reminder\n\nYou haven't been active recently. Here's why consistency matters:\n\n• Daily study (30+ min) = streak points\n• More practice = better assignment scores\n• Consistency = course completion\n\n Head to your Dashboard and attend today's lecture or submit an assignment to get back on track!"

            elif any(kw in message for kw in ["contact", "support", "help"]):
                reply = "Need Help? We're here for you!\n\nYou can reach our support team through:\n\n•  Contact Page: /contactus\n•  Email us directly from the Contact form\n•  Our team typically responds within 24 hours\n\nVisit the Contact Us page from the navigation bar or click 'Contact Support' above."

            elif any(kw in message for kw in ["settings", "profile", "password"]):
                reply = "Account Settings\n\nYou can manage your account from the following pages:\n\n  •  Profile — Update your name, photo, bio\n  •  Password — Change your password\n  • Email Preferences — Notification settings\n\n Go to: Dashboard → Account → Settings"

            else:
                faqs = ChatbotFAQ.objects.all()
                for faq in faqs:
                    keywords = [k.strip().lower() for k in faq.keywords.split(',')] if faq.keywords else []
                    if any(kw in message for kw in keywords):
                        reply = faq.answer
                        break
        ChatbotConversation.objects.create(
            user=user,
            message=message,
            reply=reply
        )

        return Response({"reply": reply})

class ChatbotHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Auto-delete conversations older than 24 hours
        _auto_delete_old_conversations(request.user)

        # Fetch last 50 messages for the user (within last 24 hours after cleanup)
        conversations = ChatbotConversation.objects.filter(user=request.user).order_by('-timestamp')[:50]
        data = []
        for conv in reversed(conversations):
            data.append({"sender": "user", "text": conv.message, "timestamp": conv.timestamp})
            data.append({"sender": "bot", "text": conv.reply, "timestamp": conv.timestamp})
        return Response(data)
