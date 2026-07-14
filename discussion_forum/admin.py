from django.contrib import admin
from .models import Question, Reply, SubReply
from course.admin import *
from course.models import *
# Register your models here.


from django.contrib import admin
from django.db.models import Q
from django.http import HttpRequest
from course.models import Module, Course, TeachingAssistant
from .models import Question  


class CourseFilter(admin.SimpleListFilter):
    title = ("Course ")

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "course_id"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        if not request.user.is_superadmin:
            ta=TeachingAssistant.objects.filter(email=request.user.email)
            ta_course=ta[0].course_set.all()
            q=[(str(course.id),(str(course.title))) for course in ta_course]
            
        else:
            admin_course=Course.objects.all()
            q=[(str(course.id),(str(course.title))) for course in admin_course]

        return q

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        
        if not request.user.is_superadmin:
            ta=TeachingAssistant.objects.filter(email=request.user.email)
            ta_course=ta[0].course_set.all()
            for course in ta_course:
                if self.value() == str(course.id):
                   if queryset.model==Module:
                     return queryset.filter(
                     section__course__id=course.id
                     )
                   
                   elif queryset.model==Video or queryset.model==Assignment:
                       return queryset.filter(
                           module__section__course__id=course.id
                       )
                   
                   else:
                       return queryset.filter(
                     course__id=course.id
                     )
                                     
        else:
            admin_course=Course.objects.all()

            for course in admin_course:
                if self.value() == str(course.id):
                   if queryset.model==Module:
                     return queryset.filter(
                     section__course__id=course.id
                     )
                   
                   elif queryset.model==Video or queryset.model==Assignment:
                       return queryset.filter(
                           module__section__course__id=course.id
                       )
                   
                   else:
                       return queryset.filter(
                     course__id=course.id
                     )
        
# ======================== Old code of QuestionAdmin (DATE - 14_Jan_2025) ===============================

# class QuestionAdmin(admin.ModelAdmin):
#     def get_queryset(self, request):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
#             if ta:
#                queryset = super().get_queryset(request)
#             else:
#                 queryset = super().get_queryset(request).filter(course__id__in=course_ids)
            
#         else:
#             queryset = super().get_queryset(request)
#         return queryset
    
#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
     
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)
   
#     list_display = ('id', 'title', 'user', 'approval_flag')
#     search_fields = ('user__email', 'title',)
#     ordering = ('-id',)
#     list_filter = [CourseFilter]


# ======================== New code of QuestionAdmin (DATE - 14_Jan_2025) ===============================

class QuestionAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        
        if not request.user.is_superadmin:  # Check if user is not a superuser
            ta = TeachingAssistant.objects.filter(email=request.user.email)  # Get TA by email
            if ta.exists():
                ta_courses = ta[0].course_set.all()  # Get courses assigned to this TA
                course_ids = [course.id for course in ta_courses]  # List of course IDs the TA has access to
                # Filter questions based on courses linked to the TA's modules
                queryset = queryset.filter(course__id__in=course_ids)
            else:
                queryset = queryset.none()  # No questions for a TA if they are not linked to any course
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superadmin:  # Check if user is not a superuser
            ta = TeachingAssistant.objects.filter(email=request.user.email)  # Get TA by email
            if ta.exists():
                ta_courses = ta[0].course_set.all()  # Get courses assigned to this TA
                course_ids = [course.id for course in ta_courses]  # List of course IDs the TA has access to
                if db_field.name == "course":
                    kwargs["queryset"] = Course.objects.filter(id__in=course_ids)  # Limit courses to those the TA can access
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    list_display = ('title', 'course', 'user', 'approval_flag')
    search_fields = ('title', 'user__email', 'course__title')
    ordering = ('-created_date',)
    list_filter = ['course']  # You can also filter by course in the admin panel



# ======================== Old code of ReplyAdmin (DATE - 14_Jan_2025) ===============================

# class ReplyAdmin(admin.ModelAdmin):
#     def get_queryset(self, request):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
            
#             if ta:
#                queryset = super().get_queryset(request)
#             else:
#                 queryset = super().get_queryset(request).filter(question__course__id__in=course_ids)
            
#         else:
#             queryset = super().get_queryset(request)
#         return queryset
    
#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
            
#             # if db_field.name=='question':
#             #     kwargs['queryset']=Question.objects.filter(Q(course__id__in=course_ids))
        
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)

#     list_display = ('id', 'question', 'user', 'approval_flag', 'deliver_mail_flag')
#     search_fields = ('user__email', 'question__title',)
#     ordering = ('-id',)
#     list_filter = ('question__course_id', 'question__section_id')


# ======================== New code of ReplyAdmin (DATE - 14_Jan_2025) ===============================

class ReplyAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        
        if not request.user.is_superadmin:  # Check if user is not a superuser
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            
            if ta.exists():
                ta_courses = ta[0].course_set.all()  # Get courses assigned to this TA
                course_ids = [course.id for course in ta_courses]  # List of course IDs the TA has access to
                
                # Filter replies based on courses linked to the TA's modules
                queryset = queryset.filter(question__course__id__in=course_ids)
            else:
                queryset = queryset.none()  # No replies for a TA if they are not linked to any course
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superadmin:  # Check if user is not a superuser
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            
            if ta.exists():
                ta_courses = ta[0].course_set.all()  # Get courses assigned to this TA
                course_ids = [course.id for course in ta_courses]  # List of course IDs the TA has access to
                
                if db_field.name == "question":  # Restrict choices for the 'question' field
                    kwargs["queryset"] = Question.objects.filter(course__id__in=course_ids)  # Filter questions by TA's course access
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Customize list_display to show related fields such as 'question', 'course', etc.
    def get_question(self, obj):
        return obj.question.title  # Assuming 'title' is the field of the Question model you want to show
    get_question.short_description = 'Question'  # Set the column title for 'Question'

    def get_course(self, obj):
        return obj.question.course.title  # Assuming 'title' is the field of the Course model you want to show
    get_course.short_description = 'Course'  # Set the column title for 'Course'

    list_display = ('get_question', 'get_course', 'user', 'approval_flag', 'deliver_mail_flag')
    search_fields = ('user__email', 'question__title',)
    ordering = ('-created_date',)
    list_filter = ('question__course_id', 'question__section_id')


# ======================== Old code of SubReplyAdmin (DATE - 14_Jan_2025) ===============================

# class SubReplyAdmin(admin.ModelAdmin):
#     def get_queryset(self, request):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
#             if ta:
#                queryset = super().get_queryset(request)
#             else:
#                 queryset = super().get_queryset(request).filter(reply__question__course__id__in=course_ids)
                  
                
#         else:
#             queryset = super().get_queryset(request)
#         return queryset
    
#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
            
#             # if db_field.name=='reply':
#             #     kwargs['queryset']=Reply.objects.filter(Q(question__course__id__in=course_ids))
        
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)

#     list_display = ('id', 'user', 'approval_flag')
#     search_fields = ('user__email',)
#     ordering = ('-id',)
#     list_filter = ('reply__question__course_id', 'reply__question__section_id')


# ======================== New code of SubReplyAdmin (DATE - 14_Jan_2025) ===============================

class SubReplyAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        
        if not request.user.is_superadmin:  # Check if user is not a superuser
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            
            if ta.exists():
                ta_courses = ta[0].course_set.all()  # Get courses assigned to this TA
                course_ids = [course.id for course in ta_courses]  # List of course IDs the TA has access to
                
                # Filter subreplies based on the course linked to the reply's question
                queryset = queryset.filter(reply__question__course__id__in=course_ids)
            else:
                queryset = queryset.none()  # No subreplies for a TA if they are not linked to any course
        return queryset
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superadmin:  # Check if user is not a superuser
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            
            if ta.exists():
                ta_courses = ta[0].course_set.all()  # Get courses assigned to this TA
                course_ids = [course.id for course in ta_courses]  # List of course IDs the TA has access to
                
                # Restrict the 'reply' field choices to only those replies linked to the TA's courses
                if db_field.name == "reply":
                    kwargs["queryset"] = Reply.objects.filter(question__course__id__in=course_ids)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Customize list_display to show related fields such as 'question', 'reply', etc.
    def get_question(self, obj):
        # Truncate the question title to 20 characters
        return obj.reply.question.title[:20] + '...' if len(obj.reply.question.title) > 20 else obj.reply.question.title
    get_question.short_description = 'Question'  # Set the column title for 'Question'

    def get_reply(self, obj):
        # Truncate the reply text to 20 characters
        return obj.reply.reply[:20] + '...' if len(obj.reply.reply) > 20 else obj.reply.reply
    get_reply.short_description = 'Reply'  # Set the column title for 'Reply'

    list_display = ('get_question', 'get_reply', 'user', 'approval_flag')
    search_fields = ('user__email', 'reply__question__title',)
    ordering = ('-created_date',)
    list_filter = ('reply__question__course_id', 'reply__question__section_id')



class PostAdminSite(admin.AdminSite):
    site_header = "Deep Eigen TA admin"
    site_title = "Deep Eigen TA Admin Portal"
    index_title = "Welcome to TA admin Panel"

# for Teaching Assistants
post_admin_site = PostAdminSite(name='post_admin')

# old code commented by khilesh
admin.site.register(Question, QuestionAdmin)
admin.site.register(Reply, ReplyAdmin)
admin.site.register(SubReply, SubReplyAdmin)

# for Teaching Assistants
post_admin_site.register(Question, QuestionAdmin)
post_admin_site.register(Reply, ReplyAdmin)
post_admin_site.register(SubReply, SubReplyAdmin)
post_admin_site.register(AssignmentEvaluation, AssignmentEvaluationAdmin)







###### Discussion forum without Restricted

# from django.contrib import admin
# from .models import Question, Reply, SubReply
# from course.admin import *

# # Register your models here.
# class QuestionAdmin(admin.ModelAdmin):

#     list_display = ('id', 'title', 'user', 'approval_flag')
#     search_fields = ('user__email', 'title',)
#     ordering = ('-id',)
#     list_filter = ('course_id',)

# class ReplyAdmin(admin.ModelAdmin):

#     list_display = ('id', 'question', 'user', 'approval_flag', 'deliver_mail_flag')
#     search_fields = ('user__email', 'question__title',)
#     ordering = ('-id',)
#     list_filter = ('question__course_id', 'question__section_id')

# class SubReplyAdmin(admin.ModelAdmin):

#     list_display = ('id', 'user', 'approval_flag')
#     search_fields = ('user__email',)
#     ordering = ('-id',)
#     list_filter = ('reply__question__course_id', 'reply__question__section_id')

# class PostAdminSite(admin.AdminSite):
#     site_header = "Deep Eigen TA admin"
#     site_title = "Deep Eigen TA Admin Portal"
#     index_title = "Welcome to TA admin Panel"

# # for Teaching Assistants
# post_admin_site = PostAdminSite(name='post_admin')

# admin.site.register(Question, QuestionAdmin)
# admin.site.register(Reply, ReplyAdmin)
# admin.site.register(SubReply, SubReplyAdmin)

# # for Teaching Assistants
# post_admin_site.register(Question, QuestionAdmin)
# post_admin_site.register(Reply, ReplyAdmin)
# post_admin_site.register(SubReply, SubReplyAdmin)
# post_admin_site.register(AssignmentEvaluation, AssignmentEvaluationAdmin)