from django.db import models
from accounts.models import Account
from course.models import Course, Section
from datetime import datetime
from django.core.mail import send_mail
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.conf import settings

# Create your models here.

class Question(models.Model):
    """!
    @brief Model representing a top-level student question in a forum section.
    @details Tracks question content, views, and approval status for quality control.
    """

    title = models.CharField(max_length=255)
    question = models.TextField()
    approval_flag = models.BooleanField(default=False)
    views = models.IntegerField(default=0)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    created_date = models.DateTimeField(default=datetime.now, blank=True)

    def __str__(self):
        return self.title

class Reply(models.Model):
    """!
    @brief Model representing a direct response to a forum Question.
    @details Contains logic to automate email notifications to the original poser 
             when a response is approved for delivery.
    """

    reply = models.TextField()
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    approval_flag = models.BooleanField(default=False)
    user = models.ForeignKey(Account, on_delete=models.CASCADE, default=2)
    created_date = models.DateTimeField(default=datetime.now, blank=True)
    deliver_mail_flag = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """!
        @brief Persists the reply and optionally triggers user notifications.
        @details Overrides the default save behavior to send HTML/Plaintext emails 
                 if the deliver_mail_flag is enabled.
        """
        if self.deliver_mail_flag:
            mail_subject = 'New Response to your Question'
            data = { 
                'user': self.user,
                'question': self.question,
                'course': self.question.course,
                'section': self.question.section,
                'reply': self.reply,
                }
            plain_message = render_to_string('discussion_forum/user_notification_email.txt', data)
            html_message = render_to_string('discussion_forum/user_notification_email.html', data)
            to_email = self.user.email
            from_email = settings.EMAIL_HOST_USER
            send_mail(mail_subject, plain_message, from_email, [to_email], html_message=html_message)
        super(Reply, self).save(*args, **kwargs)
    
    def get_approved_sub_replies(self):
        return self.subreply_set.filter(approval_flag=True).order_by('id')

    def __str__(self):
        return self.reply

class SubReply(models.Model):
    """!
    @brief Model representing a secondary response nested under a primary Reply.
    @details Supports deep threading in the discussion forum.
    """

    sub_reply = models.TextField()
    reply = models.ForeignKey(Reply, on_delete=models.CASCADE)
    approval_flag = models.BooleanField(default=False)
    user = models.ForeignKey(Account, on_delete=models.CASCADE, default=2)
    created_date = models.DateTimeField(default=datetime.now, blank=True)

    def __str__(self):
        return self.sub_reply
