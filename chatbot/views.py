from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ChatbotFAQ, ChatbotReminder, ChatbotConversation
from rest_framework.permissions import AllowAny
from django.db import close_old_connections, OperationalError
import json


def _auto_delete_old_conversations(user):
    """Delete conversations older than 24 hours for the given user."""
    close_old_connections()
    try:
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=24)
        ChatbotConversation.objects.filter(user=user, timestamp__lt=cutoff).delete()
    except Exception:
        close_old_connections()


def calculate_points_and_analytics(user):
    close_old_connections()
    from student_analytics.models import StudentAnalytics, StudentCourseAnalytics, DailyLearningActivity
    from student_analytics.utils import (
        build_student_overview_summary,
        get_started_course_assignment_analytics,
        compute_dels_preview,
        recalculate_user_streak,
    )
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

    current_streak = recalculate_user_streak(user)

    course_analytics_qs = StudentCourseAnalytics.objects.filter(user=user).select_related('course')
    lecture_completion_total = 0.0
    course_count = 0

    for c in course_analytics_qs:
        course_count += 1
        lecture_total = c.total_lectures or 0
        lecture_percent = round((c.completed_lectures / lecture_total) * 100, 1) if lecture_total else 0.0
        lecture_completion_total += lecture_percent

    avg_lecture_percent = round(lecture_completion_total / course_count, 1) if course_count else 0.0

    # Live DELS computation preview matching dashboard overview logic
    dels_result = compute_dels_preview(user)

    # Pass assignment_progress_percentage, assignment_average_performance, and dels_result
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
        dels_result=dels_result,
    )
    summary.update(started_course_assignment_analytics)
    summary['dels_tier'] = dels_result.get('tier', 'N/A')
    summary['dels_value'] = dels_result.get('dels', 0.0)
    summary['follow_through_rate'] = dels_result.get('ftr', 0.0)

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
        'dels_tier': dels_result.get('tier', 'N/A'),
        'follow_through_rate': dels_result.get('ftr', 0.0),
        'summary': summary,
    }


def _get_study_activity_today_yesterday(user):
    """
    Returns (active_today, active_yesterday) based on DailyLearningActivity,
    LectureActivity, and UserVideoProgress.
    """
    from student_analytics.models import DailyLearningActivity, LectureActivity
    from course.models import UserVideoProgress
    from django.utils import timezone
    from django.db.models import Q
    import datetime

    now = timezone.now()
    today = now.date()
    yesterday = (now - datetime.timedelta(days=1)).date()

    active_today = (
        DailyLearningActivity.objects.filter(Q(user=user) & Q(date=today) & (Q(study_time__gte=30) | Q(assignments_submitted__gt=0))).exists() or
        LectureActivity.objects.filter(user=user, is_completed=True, completed_at__date=today).exists() or
        UserVideoProgress.objects.filter(user=user, completed=True, created_at__date=today).exists()
    )

    active_yesterday = (
        DailyLearningActivity.objects.filter(Q(user=user) & Q(date=yesterday) & (Q(study_time__gte=30) | Q(assignments_submitted__gt=0))).exists() or
        LectureActivity.objects.filter(user=user, is_completed=True, completed_at__date=yesterday).exists() or
        UserVideoProgress.objects.filter(user=user, completed=True, created_at__date=yesterday).exists()
    )

    return active_today, active_yesterday


class ChatbotHomeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        close_old_connections()
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
            "performance": stats.get('summary', {}),
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
        close_old_connections()
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
                avg_lecture_pct = stats['avg_lecture_percent']
                asgn_prog = stats['assignment_progress_percentage']
                asgn_avg = stats['assignment_average_performance']
                dels_tier = stats['dels_tier']

                reply = f"Your Overall Performance:\n\n"
                reply += f"Overall Score (DELS): {points} / 1000 pts ({dels_tier} Tier)\n"
                reply += f"  • Lectures Completed: {lectures} ({avg_lecture_pct}% of course content)\n"
                reply += f"  • Assignments Submitted: {assignments}\n"
                reply += f"  • Assignment Progress: {asgn_prog}%\n"
                reply += f"  • Assignment Avg Score: {asgn_avg}%\n"
                reply += f"  • Learning Streak: {streak} days\n\n"

                from student_analytics.models import StudentCourseAnalytics
                course_analytics = StudentCourseAnalytics.objects.filter(user=user).select_related('course')
                if course_analytics.exists():
                    reply += "Course-wise Progress:\n"
                    for ca in course_analytics:
                        reply += f"  • {ca.course.title}: {ca.completion_percentage}% ({ca.course_status})\n"
                    reply += "\nStart watching lectures and submitting assignments to earn more points!"
                else:
                    reply += "\nStart watching lectures and submitting assignments to earn more points!"

            elif any(kw in message for kw in ["progress", "completion"]):
                stats = calculate_points_and_analytics(user)
                from student_analytics.models import StudentCourseAnalytics
                course_analytics = StudentCourseAnalytics.objects.filter(user=user).select_related('course')
                if course_analytics.exists():
                    reply = "Your Course Progress:\n"
                    for ca in course_analytics:
                        reply += f"  • {ca.course.title}: {ca.completion_percentage}% completed ({ca.course_status})\n"
                else:
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


    
from rest_framework.permissions import AllowAny

class ChatbotPublicHomeView(APIView):
    permission_classes = [AllowAny]

    
    def get(self, request):
        return Response({
            "suggested_questions": [
                "What courses do you offer?",
                "Subscription Plans",
                "How do I enroll?",
                "Do you offer free trials?",
                "Which plan is best for beginners?",
                "Do you offer installments?",
                "Refund Policy",
                "Do I get a certificate?",
                "How does DeepEigen work?",
                "Contact Support"
            ]
        })


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from course.models import Course
import re


class ChatbotPublicMessageView(APIView):
    permission_classes = [AllowAny]

    # FRONTEND_BASE_URL = "http://localhost:5173"  # change to your live domain later

    PLANS = {
        "basic": {
            "name": "Basic — Learn By Building",
            "price": "₹4999/year ($79/year)",
            "category": "CAT-II",
            "for": "Beginners, Software Engineers, Students wanting practical AI skills",
            "features": "Application-focused courses, end-to-end projects, assignments, certificate, community support, lifetime access"
        },
        "standard": {
            "name": "Standard — Build Strong AI Foundations",
            "price": "₹11999/year ($125.83/year)",
            "category": "CAT-IA & CAT-II",
            "for": "AI/ML Engineers, Professional Upskilling",
            "features": "Theoretical modules, math intuition, architecture deep dives, priority doubt support, mini research projects, early access"
        },
        "premium": {
            "name": "Premium — Research-Level AI Education",
            "price": "₹29999/year ($314.58/year)",
            "category": "CAT-IA + CAT-IB + CAT-II",
            "for": "Researchers, M.Tech/PhD students, AI Scientists, Advanced ML Engineers",
            "features": "Complete theory, research paper reading, paper implementation, advanced capstone projects, research mentorship, Certificate of Excellence"
        },
    }

    def course_url(self, course):
        return f"{self.FRONTEND_BASE_URL}/courses/{course.id}/{course.url_link_name}"

    def find_course(self, message):
        """Match a course by title words or category code appearing in the message."""
        best_match = None
        best_score = 0
        for c in Course.objects.all():
            title_words = re.findall(r'\w+', c.title.lower())
            score = sum(1 for w in title_words if len(w) > 3 and w in message)
            if c.category and c.category.lower() in message:
                score += 1
            if score > best_score:
                best_score = score
                best_match = c
        return best_match if best_score > 0 else None

    def format_course_details(self, c):
        return (
            f"{c.title}\n"
            f"Price: ₹{c.indian_fee} / ${c.foreign_fee}\n"
            f"Duration: {c.duration} Months | Level: {c.level} | Category: {c.category}\n"
            f"Videos: {c.total_videos} | Assignments: {c.assignments}\n"
            f"[View Course]({self.course_url(c)})"
        )

    def post(self, request):
        message = request.data.get("message", "").lower().strip()
        reply = "I'm not sure about that — try asking about our courses, pricing, subscription plans, or how to enroll!"

        # ---------- Greetings & small talk ----------
        if any(kw in message for kw in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]):
            reply = "Hello! 👋 I'm the DeepEigen assistant. Ask me about our courses, pricing, subscription plans, or how to get started!"



        elif any(kw in message for kw in ["how are you", "what's up", "whats up"]):
            reply = "I'm doing great! Ask me anything about our courses, pricing, or subscription plans."




        elif any(kw in message for kw in ["thank you", "thanks", "thx"]):
            reply = "You're welcome! Let me know if you have more questions about courses or pricing."




        elif any(kw in message for kw in ["bye", "goodbye", "see you"]):
            reply = "Goodbye! Come back anytime you have questions about our courses."




        # ---------- All courses ----------
        elif any(kw in message for kw in ["all courses", "course list", "what courses", "courses do you offer",
                                            "list of courses", "available courses", "show courses"]):
            courses = Course.objects.all()
            if courses.exists():
                reply = "Here are our current courses:\n\n"
                for c in courses:
                    reply += f"• {c.title} — ₹{c.indian_fee} | {c.duration} Months | {c.level}\n"
                reply += "\nAsk me about a specific course by name for full details and the link!"
            else:
                reply = "Course list is currently unavailable — please check our Courses page."





        # ---------- Featured courses ----------
        elif any(kw in message for kw in ["featured", "popular course", "best course", "top course", "recommended course"]):
            featured = Course.objects.filter(is_featured=True)
            if featured.exists():
                reply = "Our featured courses:\n\n"
                for c in featured:
                    reply += f"• {c.title} — ₹{c.indian_fee} | {c.duration} Months\n"
            else:
                reply = "Check our Courses page to see all available options — no featured courses are marked right now."





        # ---------- Free preview / demo videos ----------
        elif any(kw in message for kw in ["free video", "free preview", "demo video", "trial video", "sample lecture"]):
            with_free = Course.objects.exclude(free_videos_link="").exclude(free_videos_link__isnull=True)
            if with_free.exists():
                reply = "These courses have free preview videos:\n\n"
                for c in with_free:
                    reply += f"• {c.title}: {c.free_videos_link}\n"
            else:
                reply = "Free preview videos aren't listed right now — check individual course pages for previews."



        # ---------- Specific course lookup (details / price / duration / level / videos / assignments) ----------
        elif self.find_course(message) or any(kw in message for kw in [
            "price", "cost", "fee", "how much", "duration", "how long", "level", "difficulty",
            "how many videos", "how many lectures", "how many assignments", "syllabus", "curriculum", "about the course"
        ]):
            matched = self.find_course(message)
            if matched:
                reply = self.format_course_details(matched)
            else:
                reply = ("Which course are you asking about? Try naming it directly, e.g. "
                         "'price of Machine Learning course' or 'duration of Computer Vision course'.")





        # ---------- Enrolled users / social proof ----------
        elif any(kw in message for kw in ["how many students", "enrolled students", "how popular"]):
            matched = self.find_course(message)
            if matched:
                reply = f"{matched.title} currently has {matched.enrolled_users} enrolled students."
            else:
                total = sum(c.enrolled_users or 0 for c in Course.objects.all())
                reply = f"We have {total} total student enrollments across all our courses!"




        # ---------- Installments / EMI ----------
        elif any(kw in message for kw in ["installment", "emi", "pay in parts", "monthly payment", "installments"]):
            reply = ("Yes! Many of our courses support installment payments (up to 3 installments). "
                     "You'll see installment options at checkout when purchasing a course.")




        # ---------- Refund policy ----------
        elif any(kw in message for kw in ["refund", "cancel", "money back", "return policy"]):
            reply = ("Refund policies vary by course — please check the specific course page for its refund terms, "
                     "or contact support at /contactus for help with a refund request.")




        # ---------- Certificate ----------
        elif any(kw in message for kw in ["certificate", "certification", "certified"]):
            reply = "Yes, you receive a course completion certificate after finishing a course, and a Certificate of Excellence with our Premium plan."




        # ---------- Instructor info ----------
        elif any(kw in message for kw in ["instructor", "teacher", "who teaches", "faculty", "mentor"]):
            reply = "Our courses are taught by experienced instructors and supported by teaching assistants. Check a specific course page for instructor bios."




        # ---------- Subscription plans — general ----------
        elif any(kw in message for kw in ["subscription", "plan", "plans", "membership", "packages"]):
            reply = "We offer 3 subscription plans:\n\n"
            for key, p in self.PLANS.items():
                reply += f"• {p['name']} — {p['price']} ({p['category']})\n"
            reply += "\nAsk 'which plan for beginners', 'for ML engineers', or 'for researchers' for a recommendation!"



        # ---------- Plan recommendation by profile ----------
        elif any(kw in message for kw in ["beginner", "software engineer", "practical", "new to ai", "new to machine learning"]):
            p = self.PLANS["basic"]
            reply = f"{p['name']} ({p['price']}) fits you best — {p['for']}. Includes: {p['features']}."




        elif any(kw in message for kw in ["upskill", "professional", "ml engineer", "ai engineer", "working professional"]):
            p = self.PLANS["standard"]
            reply = f"{p['name']} ({p['price']}) fits you best — {p['for']}. Includes: {p['features']}."




        elif any(kw in message for kw in ["researcher", "phd", "m.tech", "scientist", "advanced", "research level"]):
            p = self.PLANS["premium"]
            reply = f"{p['name']} ({p['price']}) fits you best — {p['for']}. Includes: {p['features']}."



        elif any(kw in message for kw in ["difference between plans", "compare plans", "which plan is best", "plan comparison"]):
            reply = "Plan comparison:\n\n"
            for key, p in self.PLANS.items():
                reply += f"• {p['name']} ({p['price']}) — {p['category']}\nBest for: {p['for']}\n\n"




        # ---------- Enrollment / signup ----------
        elif any(kw in message for kw in ["enroll", "sign up", "signup", "register", "join", "how to start", "get started"]):
            reply = "Create a free account, browse our courses, and enroll in the one that fits you — no payment needed just to sign up!"



        elif any(kw in message for kw in ["trial", "free course", "free access", "demo"]):
            reply = "Some of our courses offer free preview lectures. Sign up and check the course page to see what's available."


# ---------- About platform ----------
        elif any(kw in message for kw in ["how does", "how it works", "about deepeigen", "what is deepeigen", "what do you teach", "who founded", "founder"]):
            reply = ("DeepEigen is an online learning platform founded in 2021, offering graduate-level courses "
                     "in AI, Machine Learning, Robotics, and Autonomous Driving. Unlike typical intro-level courses, "
                     "DeepEigen goes deeper into the theory and mathematics behind these fields, helping students "
                     "build the kind of in-depth knowledge usually only available through MS/PhD programs abroad. "
                     "The platform also offers mentorship, certificates, and some free courses.")

        # ---------- Contact / support ----------
        elif any(kw in message for kw in ["contact", "support", "help", "reach you", "customer service"]):
            reply = "Reach us anytime at /contactus — our team typically responds within 24 hours."

        # ---------- Fallback to DB FAQ ----------
        else:
            from .models import ChatbotFAQ
            faqs = ChatbotFAQ.objects.all()
            for faq in faqs:
                keywords = [k.strip().lower() for k in faq.keywords.split(',')] if faq.keywords else []
                if any(kw in message for kw in keywords):
                    reply = faq.answer
                    break

        return Response({"reply": reply})