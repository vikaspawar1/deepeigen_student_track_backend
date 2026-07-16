"""
Django administrative interface configuration for the course application.

This module defines the admin classes for courses, sections, modules, videos, 
assignments, and enrollment management. It includes custom permissions for 
Teaching Assistants (TAs), complex multi-tiered installment payment filtering, 
and automated PDF invoice generation within the admin views.
"""
import io
import os
import re
import sys
import datetime
from decimal import Decimal
from typing import Any, Mapping
from collections.abc import Sequence

import inflect
import reportlab
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from django.contrib import admin, messages
from django.contrib.admin import site
from django.contrib.contenttypes.models import ContentType
from django.core.files import File as DjangoFile
from django.core.files.base import ContentFile
from django.db.models import Q, Sum
from django.forms import ModelForm, modelform_factory
from django import forms
from django.http import HttpResponse, FileResponse, HttpRequest
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMessage

from .models import *
from .widgets import CustomAdminWidget, ForeignKeyAddButtonWidget
from accounts.models import Account, company


class InstructorAdmin(admin.ModelAdmin):
    """
    Administrative interface for Instructor profiles.
    
    Restricts management permissions to superadmins only.
    """
    def profile(self, object):
        return format_html('<img src="{}" width="80" style="border-radius:50%;">'.format(object.profile_picture.url))
    
    def has_module_permission(self, request: HttpRequest):
        
        try:
            if request.user.is_superadmin:
                return True
            else:
                return False 

        except:

          return False
    
    def has_add_permission(self, request: HttpRequest) :
        if not request.user.is_superadmin:
            return False
        else:
          return super().has_add_permission(request)
    def has_delete_permission(self, request: HttpRequest, obj =None):
        if not request.user.is_superadmin:
            return False
        else:
          return super().has_add_permission(request)
    
    list_display = ('id', 'profile', 'first_name', 'email')
    search_fields = ('first_name', 'email')
    ordering = ('id',)

# Custom Form for TeachingAssistant
class TeachingAssistantForm(forms.ModelForm):
    # Display the courses as checkboxes, pre-selected based on the TA's registration
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label="Courses"
    )

    class Meta:
        model = TeachingAssistant
        fields = ['first_name', 'last_name', 'email', 'courses', 'socialaccount_link', 'role', 'profile_picture']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-select the courses the TA is already registered for
        if self.instance.pk:
            self.fields['courses'].initial = self.instance.course_set.all()


# TeachingAssistant Admin Configuration
class TeachingAssistantAdmin(admin.ModelAdmin):
    form = TeachingAssistantForm  # Use the custom form

    list_display = ('id', 'profile', 'first_name', 'last_name', 'email')
    search_fields = ('first_name', 'last_name', 'email')
    ordering = ('id',)

    def profile(self, obj):
        """Display profile picture in admin list."""
        return format_html('<img src="{}" width="80" style="border-radius:50%;">'.format(obj.profile_picture.url))

    # Permissions
    def has_module_permission(self, request):
        """Grant access to the module only for superadmins."""
        try:
            if request.user.is_superadmin:
                return True
            return False
        except Exception:
            return False

    def has_add_permission(self, request):
        """Restrict add permission to superadmins."""
        if not request.user.is_superadmin:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        """Restrict delete permission to superadmins."""
        if not request.user.is_superadmin:
            return False
        return super().has_delete_permission(request, obj)

    # Custom Save Logic
    def save_model(self, request, obj, form, add):
        """Custom save logic to handle user account and course assignments."""
        # Handle Account creation or update
        user_acc = Account.objects.filter(email=obj.email)
        if user_acc.exists():
            user_acc[0].save()
        else:
            acc = Account(
                first_name=obj.first_name,
                last_name=obj.last_name,
                username=obj.first_name + obj.last_name,
                email=obj.email,
                profession=obj.role,
                is_active=True,
                is_admin=True,
                is_staff=True
            )
            acc.set_password("ta@deepeigen")  # Set default password
            acc.save()

        # Save the TeachingAssistant object
        super().save_model(request, obj, form, add)
        
         # Handle ManyToMany relationship with Course
        if 'courses' in form.cleaned_data:
            obj.course_set.set(form.cleaned_data['courses'])  # Assign selected courses to the TA
        else:
            obj.course_set.clear()  # Clear all courses if none are selected


# class CourseAdmin(admin.ModelAdmin):
#     def course_image_picture(self, object):
#         return format_html('<img src="{}" width="80">'.format(object.course_image.url))
    
    
#     def get_queryset(self, request: HttpRequest) :
        
#         """Filter courses based on the user's role."""
#         qs = super().get_queryset(request)  # Get the base queryset
        
#         # If the user is a superadmin, return all courses
#         if request.user.is_superadmin:
#             return qs
        
#         # If the user is not a superadmin, filter courses for assigned TAs
#         try:
#             # Check if the user is a TA
#             ta = TeachingAssistant.objects.get(email=request.user.email)
#             # Return only courses assigned to the TA
#             return qs.filter(teaching_assistant=ta)
#         except TeachingAssistant.DoesNotExist:
#             # If the user is not a TA, return no courses
#             return qs.none()
    
#     def has_add_permission(self, request: HttpRequest) :
#         if not request.user.is_superadmin:
#           return False
        
#         else:
#             return True
    
#     def has_delete_permission(self, request: HttpRequest, obj=None):

#         if not request.user.is_superadmin:
#           return False
        
#         else:
#            return True
    
    
#     list_display = ('id', 'course_image_picture', 'title', 'category')
#     search_fields = ('title', 'category')
#     ordering = ('-id',)
#     list_display_links = ('title', 'id', 'course_image_picture')
#     class Meta:
#         # Add verbose name
#         verbose_name = 'Course'

# Course section is done in both pannel Admin and TA, now ta can able to see the all courses where he added, and admin can all (complition date - 13_Jan_2024 (By Khilesh))
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'course_image_picture', 'title', 'category')
    search_fields = ('title', 'category')
    ordering = ('-id',)
    list_display_links = ('title', 'id', 'course_image_picture')

    def course_image_picture(self, obj):
        """Display the course image in the admin."""
        if obj.course_image and hasattr(obj.course_image, 'url') and obj.course_image.name:
            return format_html('<img src="{}" width="80">'.format(obj.course_image.url))
        return format_html('<img src="{}" width="80">'.format('/static/admin/img/icon-no.svg'))

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """
        Customizes the field for teaching assistants in the course form.
        Shows only the TAs assigned to the course if editing an existing course.
        """
        if db_field.name == "teaching_assistant":  # Field name matches the ManyToMany relationship
            course_id = request.resolver_match.kwargs.get('object_id')
            if course_id:
                course = Course.objects.get(id=course_id)
                kwargs["queryset"] = TeachingAssistant.objects.filter(id__in=course.teaching_assistant.values('id'))  # Filter TAs based on the course
            else:
                kwargs["queryset"] = TeachingAssistant.objects.all()  # Show all TAs if no specific course
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_queryset(self, request):
        """Filter courses based on the user's role."""
        qs = super().get_queryset(request)  # Get the base queryset
        if request.user.is_superadmin:
            return qs
        try:
            ta = TeachingAssistant.objects.get(email=request.user.email)  # Get TA by user email
            return qs.filter(teaching_assistant=ta)  # Filter courses based on the assigned teaching assistant
        except TeachingAssistant.DoesNotExist:
            return qs.none()  # Return an empty queryset if TA doesn't exist



class CourseFilter(admin.SimpleListFilter):
    """
    Custom sidebar filter to allow administrators and TAs to filter objects by course.
    
    Automatically adjusts lookup options based on the user's assigned courses.
    """
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
        
# ======================== Old code of SectionAdmin (DATE - 13_Jan_2025) ===============================

# class SectionAdmin(admin.ModelAdmin):
#     def get_queryset(self, request: HttpRequest):

#         if not request.user.is_superadmin:
#             ta=TeachingAssistant.objects.filter(email=request.user.email)
#             ta_course=ta[0].course_set.all()
#             q=[]
#             for course in ta_course:
#                 q.append(course.id)
            
#             if ta:
#                 queryset=super().get_queryset(request)
#             else:    
#                 queryset=super().get_queryset(request).filter(Q(course__id__in=q))
                
        
#         else:
#             queryset=super().get_queryset(request)

            
#         return queryset
    
#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
            
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
#             if db_field.name=='course':
                
#                 kwargs['queryset']=Course.objects.filter(Q(id__in=course_ids))
            
        
     
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)
   
#     list_display = ('name', 'course',)
#     search_fields = ('name', 'title',)
#     ordering = ('-id',)
#     list_filter = [CourseFilter]


# ========================New code of SectionAdmin (DATE - 13_Jan_2025) ===============================

class SectionAdmin(admin.ModelAdmin):
    """
    Administrative interface for Course Sections.
    
    Filters available courses and existing sections based on TA assignments.
    """
    
    def get_queryset(self, request: HttpRequest):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                # Only show sections for courses the TA is registered in
                queryset = super().get_queryset(request).filter(course__id__in=course_ids)
            else:
                queryset = super().get_queryset(request).none()  # No access if no TA found
        else:
            queryset = super().get_queryset(request)
        return queryset
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                if db_field.name == 'course':
                    # Limit course choices based on the TA's courses
                    kwargs['queryset'] = Course.objects.filter(id__in=course_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    list_display = ('name', 'course',)
    search_fields = ('name', 'title',)
    ordering = ('-id',)
    list_filter = [CourseFilter]

# ======================== Old code of ModuleAdmin (DATE - 13_Jan_2025) ===============================

# class ModuleAdmin(admin.ModelAdmin):

#     def get_queryset(self, request: HttpRequest):
#          if not request.user.is_superadmin:
#             ta=TeachingAssistant.objects.filter(email=request.user.email)
#             ta_course=ta[0].course_set.all()
#             q=[]
#             for course in ta_course:
#                 q.append(course.id)
            
#             if ta:
#                 queryset=super().get_queryset(request)
#             else:
#                 queryset=super().get_queryset(request).filter(Q(section__course__id__in=q))
                    
                
#          else:
#              queryset=super().get_queryset(request)
        
             
#          return queryset
    
#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
            
#             # comment by khilesh (Date - 11_Dec_2024)
#             # if db_field.name=='section':
#             #     kwargs['queryset']=Section.objects.filter(Q(course__id__in=course_ids))
     
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)
    

#     list_display = ('title', 'section',)
#     search_fields = ('section__name',)
#     ordering = ('-id',)
#     list_filter = [CourseFilter]
#     save_as = True

# ======================== New code of ModuleAdmin (DATE - 13_Jan_2025) ===============================

class ModuleAdmin(admin.ModelAdmin):
    """
    Administrative interface for Course Modules.
    
    Ensures TAs only manage modules belonging to their assigned sections.
    """

    def get_queryset(self, request: HttpRequest):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                # Only show modules for sections of courses the TA is registered in
                queryset = super().get_queryset(request).filter(section__course__id__in=course_ids)
            else:
                queryset = super().get_queryset(request).none()  # No access if no TA found
        else:
            queryset = super().get_queryset(request)  # Superadmins see all modules
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                if db_field.name == 'section':
                    # Limit sections to only those in the TA's courses
                    kwargs['queryset'] = Section.objects.filter(course__id__in=course_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    list_display = ('title', 'section',)
    search_fields = ('section__name', 'title',)
    ordering = ('-id',)
    list_filter = [CourseFilter]
    save_as = True


# ======================== Old code of AssignmentAdmin (DATE - 13_Jan_2025) ===============================

# class AssignmentAdmin(admin.ModelAdmin):
    
#     def get_queryset(self, request):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
            
#             if ta:
#                 queryset = super().get_queryset(request)
#             else:
#                 queryset = super().get_queryset(request).filter(course__id__in=course_ids)
                
                
#         else:
#             queryset = super().get_queryset(request)
#         return queryset

#     # def get_form(self, request, obj=None, **kwargs):
#     #     kwargs['form'] = CouseModelForm
#     #     return super().get_form(request, obj=obj, **kwargs)

#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
            
#             # comment by khilesh (Date- 11_Dec_2024)
#             # if db_field.name=='course':
#             #     kwargs['queryset']=Course.objects.filter(Q(id__in=course_ids))
#             # elif db_field.name =='module':
#             #     kwargs['queryset']=Module.objects.filter(Q(section__course__id__in=course_ids))
        
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)

#     list_display = ('name', 'module', 'pdf')
#     search_fields = ('name',)
#     ordering = ('-id',)
#     list_filter = [CourseFilter]

# ======================== New code of AssignmentAdmin (DATE - 13_Jan_2025) ===============================

class AssignmentAdmin(admin.ModelAdmin):
    """
    Administrative interface for Assignments.
    
    Filters modules and visibility according to TA course assignments.
    """

    def get_queryset(self, request):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                # Only show assignments for modules in sections of courses the TA is registered in
                queryset = super().get_queryset(request).filter(module__section__course__id__in=course_ids)
            else:
                queryset = super().get_queryset(request).none()  # No access if no TA found
        else:
            queryset = super().get_queryset(request)  # Superadmins see all assignments
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                if db_field.name == 'module':
                    # Limit modules to only those in the TA's courses
                    kwargs['queryset'] = Module.objects.filter(section__course__id__in=course_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    list_display = ('name', 'module', 'pdf',)
    search_fields = ('name', 'module__title',)
    ordering = ('-id',)
    list_filter = [CourseFilter]


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    """
    Admin interface for managing Assessments per course.
    Admin can create assessments and later give scores to students via AssessmentActivity.
    """
    list_display = ('name', 'course', 'module', 'max_score', 'created_date')
    search_fields = ('name', 'course__title')
    list_filter = ('course',)
    ordering = ('course', 'id')



# ======================== Old code of VideoAdmin (DATE - 13_Jan_2025) ===============================

# class VideoAdmin(admin.ModelAdmin):

#     def get_queryset(self, request: HttpRequest):
#          if not request.user.is_superadmin:
#             ta=TeachingAssistant.objects.filter(email=request.user.email)
#             ta_course=ta[0].course_set.all()
#             q=[]
#             for course in ta_course:
#                 q.append(course.id)
            
#             if ta:
#                 queryset=super().get_queryset(request)
#             else:
#                 queryset=super().get_queryset(request).filter(Q(module__section__course__id__in=q))
                    

#          else:
#              queryset=super().get_queryset(request)

#          return queryset
    
#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         if not request.user.is_superadmin:
#             ta = TeachingAssistant.objects.filter(email=request.user.email)
#             ta_courses = ta[0].course_set.all()
#             course_ids = [course.id for course in ta_courses]
            
#             # comment by khilesh (Date - 11_Dec_2024)
#             # if db_field.name=='module':
#                 # kwargs['queryset']=Module.objects.filter(Q(section__course__id__in=course_ids))
     
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)

#     list_display = ('title', 'module', 'type', 'duration',)
#     search_fields = ('title',)
#     ordering = ('-module_id',)
#     list_filter = [CourseFilter]

# ======================== New code of VideoAdmin (DATE - 13_Jan_2025) ===============================

class VideoAdmin(admin.ModelAdmin):
    """
    Administrative interface for Course Videos.
    
    Restricts video content management based on TA roles and assignments.
    """

    def get_queryset(self, request: HttpRequest):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                # Only show videos for modules in sections of courses the TA is registered in
                queryset = super().get_queryset(request).filter(module__section__course__id__in=course_ids)
            else:
                queryset = super().get_queryset(request).none()  # No access if no TA found
        else:
            queryset = super().get_queryset(request)  # Superadmins see all videos
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                if db_field.name == 'module':
                    # Limit modules to only those in the TA's courses
                    kwargs['queryset'] = Module.objects.filter(section__course__id__in=course_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    list_display = ('title', 'module', 'type', 'duration',)
    search_fields = ('title', 'module__name',)
    ordering = ('-module_id',)
    list_filter = [CourseFilter]



# ======================== Old code of AssignmentEvaluationAdmin (DATE - 13_Jan_2025) ===============================

# class AssignmentEvaluationAdmin(admin.ModelAdmin):

#     def get_queryset(self, request: HttpRequest):

#         if not request.user.is_superadmin:
#             ta=TeachingAssistant.objects.filter(email=request.user.email)
#             ta_course=ta[0].course_set.all()
#             q=[]
#             for course in ta_course:
#                 q.append(course.id)
            
#             if ta:
#                 queryset=super().get_queryset(request)
#             else:
#                 queryset=super().get_queryset(request).filter(Q(course__id__in=q))
                
        
#         else:
#             queryset=super().get_queryset(request)

            
#         return queryset

#     def has_add_permission(self, request: HttpRequest) :
#         if not request.user.is_superadmin:
#           return False
#         else:
#           return super().has_add_permission(request) 
    
#     list_filter=[CourseFilter]
#     list_display = ('user', 'assignment', 'submitted_file', 'score', 'submit_flag', 'created_at')
#     search_fields = ('score', 'user__email')
#     ordering = ('-id',)
#     # list_filter = ('course_id',)
    

# ======================== New code of AssignmentEvaluationAdmin (DATE - 13_Jan_2025) ===============================

class AssignmentEvaluationAdmin(admin.ModelAdmin):
    """
    Administrative interface for student assignment submissions and evaluations.
    
    Provides TAs with access to submissions for their courses and 
    restricts addition of new evaluation entries.
    """

    def get_queryset(self, request: HttpRequest):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                # Only show evaluations for assignments in the TA's courses
                queryset = super().get_queryset(request).filter(assignment__module__section__course__id__in=course_ids)
            else:
                queryset = super().get_queryset(request).none()  # No access if no TA found
        else:
            queryset = super().get_queryset(request)  # Superadmins see all evaluations
        return queryset

    def has_add_permission(self, request: HttpRequest):
        # Prevent TAs from adding new evaluation entries
        if not request.user.is_superadmin:
            return False
        return super().has_add_permission(request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superadmin:
            ta = TeachingAssistant.objects.filter(email=request.user.email)
            if ta.exists():
                ta_courses = ta[0].course_set.all()
                course_ids = [course.id for course in ta_courses]
                if db_field.name == 'assignment':
                    # Limit assignments to those in the TA's courses
                    kwargs['queryset'] = Assignment.objects.filter(module__section__course__id__in=course_ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    list_filter = [CourseFilter]
    list_display = ('user', 'assignment', 'submitted_file', 'score', 'submit_flag', 'created_at')
    search_fields = ('score', 'user__email', 'assignment__name')
    ordering = ('-id',)



class ManualForm(ModelForm):
    """
    Form for manually enrolling users in courses with specific payment details.
    """
    class Meta:
        model=EnrolledUser
        fields=['order',"payment","user","course","course_price","enrolled","created_at","end_at"]
        
    
    def __init__(self, *args,**kwargs) :
        super(ManualForm,self).__init__(*args,**kwargs)
        self.fields['payment'].queryset=Payment.objects.order_by("-id")
        self.fields['order'].queryset=Order.objects.order_by("-id")
        self.fields['user'].queryset=Account.objects.order_by("-id")

class ChangeForm(ModelForm):
    """
    Form for updating existing enrollment records.
    """
    class Meta:
        model=EnrolledUser
        fields="__all__"

# class FreeForm(ModelForm):
#     class Meta:
#         model=EnrolledUser
#         fields=['order',"payment","user","course","course_price","enrolled","created_at","end_at"]
#         widgets={
#             'payment':CustomAdminWidget(rel=ContentType.objects.get_for_model(Payment),admin_site=site)
#         }
       
#         def __init__(self, *args,**kwargs) :
#             super(FreeForm,self).__init__(*args,**kwargs)
#             content_type=ContentType.objects.get_for_model(Payment)
#             self.fields['payment'].widget = CustomAdminWidget(
#                 rel=content_type,
#                 admin_site=site
#             )
#             self.fields['payment'].queryset=Payment.objects.filter(amount_paid__lte=0.0).order_by('-id')
#             self.fields['order'].queryset=Order.objects.filter(payment__amount_paid__lte=0.0).order_by("-id")
#             self.fields['user'].queryset=Account.objects.order_by("-id")
            
            

class EnrolledUserAdmin(admin.ModelAdmin):
    """
    Administrative interface for Enrolled Users.
    
    Manages custom forms for addition vs modification and handles 
    installment-based access flags.
    """

    def has_module_permission(self, request: HttpRequest) :
        try:
            
            if not request.user.is_superadmin:
                return False
            
            else:
              return True
        except:
            return True
    def filter_free_users(modeladmin, request, queryset):
     queryset = queryset.filter(user_type='free')
    # Perform your action here. For demonstration, we will just print the users.
     for user in queryset:
        print(user.username)

    def get_form(self, request, obj, **kwargs) :
        print(request.path,request.method)
        add_url="add"
        change_url="change"
        if add_url in request.path:
          kwargs['form']=ManualForm
        elif change_url in request.path:
            kwargs['form']=ChangeForm
        return super().get_form(request, obj, **kwargs)
    
    def save_model(self, request, obj, form, change) :
        obj.first_installments=True
        
        return super().save_model(request, obj, form, change)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # path('add_manual_user/', self.admin_site.admin_view(self.custom_manual_view), name='course_EnrolledUser_custom_view'),
            # path("add_free_user/",self.admin_site.admin_view(self.custom_free_view),name="course_enrolleduser_custom_freeview")
        ]
        return custom_urls + urls
   
    
    # def custom_manual_view(self, request):
        
    #     # Your custom view logic here
    #     if request.method == 'POST':
    #         form = ManualForm(request.POST)
    #         if form.is_valid():
    #             enroll_user=form.save(commit=False)
               
    #             enroll_user.first_installments=True
    #             form.save()
    #             self.message_user(request, "User created successfully.")
    #             return redirect('admin:course_enrolleduser_changelist')
    #     else:
    #         form = ManualForm()
    #         context = {
    #         'form': form,
    #         'opts': self.model._meta,
    #         'app_label': self.model._meta.app_label,
    #     }
       
    #     return render(request,"admin/custom_manual_add.html",context)

    # def custom_free_view(self,request):
        
    #     # print('form--'freeform)
    #     if request.method == 'POST':
    #         form = FreeForm(request.POST)
    #         if form.is_valid():
    #             enroll_user=form.save(commit=False)
               
    #             enroll_user.first_installments=True
    #             form.save()
    #             self.message_user(request, "Free User created successfully.")
    #             return redirect('admin:course_enrolleduser_changelist')
    #     else:
    #         form = FreeForm()
    #         context = {
    #         'form': form,
    #         'opts': self.model._meta,
    #         'app_label': self.model._meta.app_label,
    #     }
       
        return render(request,"admin/custom_free_add.html",context)
        
        
    
    # change_list_template = 'admin/course/enrolluser/change_list.html'    
    list_display = ('user', 'course','created_at','payment')
    search_fields = ('user__email','course__title')
    ordering = ('-id',)
    list_filter = ('course_id',)
    actions=[filter_free_users]
    
class OutlineAdmin(admin.ModelAdmin):
    """
    Administrative interface for Course Outlines.
    """

    def has_module_permission(self, request: HttpRequest) :
        try:
            if not request.user.is_superadmin:
                return False          
            
            else:
              return True
        
        except:
            return False

    list_display = ('title', 'course',)
    search_fields = ('title','course__title',)
    ordering = ('-id',)
    list_filter = ('course_id',)

class OrderAdmin(admin.ModelAdmin):
    """
    Administrative interface for Orders.
    """

    def has_module_permission(self, request: HttpRequest) :
        try:
            if not request.user.is_superadmin:
                return False          
            
            else:
              return True
        
        except:
            return True


    list_display = ('order_number', 'course', 'email', 'total_amount', 'is_ordered','payment','created_at')
    search_fields = ('order_number', 'email')
    ordering = ('-id',)
    list_filter = ('course_id',)

class PaymentAdmin(admin.ModelAdmin):
    """
    Administrative interface for Payments.
    """
    def has_module_permission(self, request: HttpRequest):
        try:
            if not request.user.is_superadmin:
                return False
            else:
              return super().has_module_permission(request)
        except:
            return True


    list_display = ('user', 'payment_id', 'payment_method', 'amount_paid', 'status')
    search_fields = ('user__email', 'payment_method','id','payment_id')
    ordering = ('-id',)

class PaymentMethodAdmin(admin.ModelAdmin):
     def has_module_permission(self, request: HttpRequest) :
        try:
            if not request.user.is_superadmin:
                return False
            
            else:
              return True
        except:
            return True
    

class OverallProgressAdmin(admin.ModelAdmin):
    """
    Administrative interface for Overall Progress tracking.
    """
    def has_module_permission(self, request: HttpRequest) :
        try:
            if not request.user.is_superadmin:
                return False
            
            else:
              return True
        except AttributeError:
            return True

    list_display = ('user', 'course', 'progress')
    search_fields = ('user__email', 'progress')
    ordering = ('-id',)

class Failed_AssignmentAdmin(admin.ModelAdmin):
    """
    Administrative interface for tracking failed assignment attempts.
    """

    def has_add_permission(self, request: HttpRequest):
        if request.user.is_superadmin:

           return super().has_add_permission(request)
        else:
            return False
    
    def has_delete_permission(self, request: HttpRequest, obj=None):
        if request.user.is_superadmin:
          return super().has_delete_permission(request, obj)
        else:
            return False
    
    def get_queryset(self, request: HttpRequest):

        if not request.user.is_superadmin:
            ta=TeachingAssistant.objects.filter(email=request.user.email)
            ta_course=ta[0].course_set.all()
            q=[]
            for course in ta_course:
                q.append(course.id)
            
            if ta:
                queryset=super().get_queryset(request)
            else:
                queryset=super().get_queryset(request).filter(Q(course__id__in=q))
                    
        else:
            queryset=super().get_queryset(request)

            
        return queryset
    list_display = ('user', 'assignment', 'submitted_file', 'score', 'created_at')
    search_fields = ('score', 'user__email')
    ordering = ('-id',)
    list_filter = [CourseFilter]

def calculate_financial_year(enroll_date, amount_paid):
    """
    Calculates the financial year serial number for an enrollment.

    Args:
        enroll_date (date): The date of enrollment.
        amount_paid (float): Amount paid for the enrollment.

    Returns:
        str: Serial number in current_user_string.count format.
    """
    current_date=enroll_date
    
    if current_date.month<4:
        
        current_financial_year=[datetime(current_date.year-1,4,1).date(),datetime(current_date.year,current_date.month,current_date.day)]
                            
    else:
        current_financial_year=[datetime(current_date.year,4,1).date(),datetime(current_date.year,current_date.month,current_date.day)]

    last_users=EnrolledUser.objects.filter(created_at__gte=current_financial_year[0],created_at__lte=current_financial_year[1]).order_by()
  
    current_user_string=current_date.strftime("%d%m%Y")

    if amount_paid == 0.0:
        result_string ="free_"
    else:
        result_string=""

    if last_users.count()==0:
        
        result_string+=f"{current_user_string}.{1}"                           
    
    else:
        enrollcount=last_users.count()+1
        result_string+=f"{current_user_string}.{enrollcount}"
    
    return result_string


def Invoice_add(id, payment_id, course_id):
    """
    Generates and saves a PDF invoice for a specific enrollment and payment.

    Side Effects:
        Saves a PDF file to the static/pdfs/ directory (local storage).
        Updates the Invoice_Registrant record with the serial number and PDF file.

    Args:
        id (int): EnrolledUser ID.
        payment_id (str): Payment ID from the gateway.
        course_id (int): Course ID.

    Returns:
        Invoice_Registrant or Exception: The created invoice record or an error.
    """
    
    # now=datetime.now()
    
    try:
     
        enrollUser=EnrolledUser.objects.filter(id=id,course=course_id)

        
        
        if  enrollUser[0].installment_id_2 == None and  enrollUser[0].installment_id_3 == None:
            
            payment=Payment.objects.filter(payment_id=payment_id)
        
            order=Order.objects.filter(id=enrollUser[0].order.id)

            invoice_reg=Invoice_Registrant(name=enrollUser[0],order=order[0])
           
            total_amount_paid=order.aggregate(total_sum=Sum('payment__amount_paid'))
            payment_date=order[0].created_at

            
        else:
            payment=Payment.objects.filter(payment_id=payment_id)
            
            order=Order.objects.filter(payment__in=payment,is_ordered=True)
            enroll_user=EnrolledUser.objects.get(id=id)
             
            invoice_reg=Invoice_Registrant(name=enroll_user,order=order[0])
           
            total_amount_paid=Order.objects.filter(user=enrollUser[0].user.id,course=course_id).aggregate(total_sum=Sum('payment__amount_paid'))
            
            payment_date=order[0].created_at
            
            
        

        
        # if payment_id == enrollUser[0].installment_id_2:
        #     total_amount_paid=Order.objects.filter(user=enrollUser[0].user.id,course=course_id).aggregate(total_sum=Sum('payment__amount_paid'))
        #     # print('2nd amount ',total_amount_paid)

        # elif payment_id == enrollUser[0].installment_id_3:
        #     total_amount_paid=Order.objects.filter(user=enrollUser[0].user.id,course=course_id).aggregate(total_sum=Sum('payment__amount_paid'))
        #     # print('3rd amount ',total_amount_paid)

        # else:
        #     total_amount_paid=Order.objects.filter(user=enrollUser[0].user.id,course=course_id,payment=payment[0].id).aggregate(total_sum=Sum('payment__amount_paid'))

        
        company_details = company.objects.all()

        p = inflect.engine()
   
        amount_chargebale = p.number_to_words(int(order[0].payment.amount_paid))
     
        s_sr = calculate_financial_year(payment_date,total_amount_paid['total_sum'])
        parts = s_sr.split('.')
        
        s_n =0
        if len(parts) == 2:
            current_date, serial_number_str = parts
            
            serial_number = int(serial_number_str)
            s_n = s_n+serial_number
            
        else:
            print("Invalid result string format.")
            
        
        present_date=payment_date
        
        if present_date.month>3:
            
            financial_year=[present_date.year,present_date.year+1]
        else:
            financial_year=[present_date.year-1,present_date.year]
        
            
        install=["2nd Installment" if enrollUser[0].installment_id_2 == payment_id else  "3rd Installment" if enrollUser[0].installment_id_3 == payment_id else "1st Installment"  ][0]
     
        
        invoice_reg.serial_no=s_sr
        invoice_reg.save()
        data = {'firstname': order[0].first_name,
                'lastname': order[0].last_name,
                'course': order[0].course,
                'orderid': order[0].order_number,
                'payment_id':payment_id,
                'created_date': order[0].created_at.date(),
                'course_category': order[0].course.category,
                'address': order[0].address,
                'city': order[0].city,
                'state': order[0].state,
                'country': order[0].country,
                'zipcode': order[0].zipcode,
                'phone_number': order[0].phone,
                'email': order[0].email,
                'quantity': 1,
                'amount': order[0].course_amount,
                'amount_paid': order[0].payment.amount_paid,
                'remaining_amount': order[0].total_amount-(total_amount_paid['total_sum']),
                'amount_charge': amount_chargebale.upper(),
                'total_amount': order[0].total_amount,
                'company_name': company_details[0].name,
                'company_address': company_details[0].address,
                'company_phone': company_details[0].phone,
                'company_panid': company_details[0].pan, 
                }
        with open('./static/pdfs/file.pdf','wb') as f:   

            buf=io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(250*mm, 330*mm),
                                pageCompression=1, bottomup=1)
            reportlab.rl_config.TTFSearchPath.append(
                str(settings.BASE_DIR) + '/staticfiles/fontawesome/webfonts/')

            # register the external font with .ttf extension only
            pdfmetrics.registerFont(
                TTFont('bookman-bold', './staticfiles/fontawesome/Bookman Bold/Bookman Bold.ttf'))
            pdfmetrics.registerFont(
                TTFont('bookman', './staticfiles/fontawesome/bookman_old.TTF'))

            pdfmetrics.registerFont(
                TTFont('Arial', './staticfiles/fontawesome/arial/arial.ttf'))

            c.setTitle('INVOICE')

            c.rect(15*mm, 15*mm, 220*mm, 296*mm, stroke=1, fill=0)

            c.drawImage('./staticfiles/img/testing.png', 25*mm, 267*mm,
                        width=64*mm, height=35*mm, mask=[0, 0.7, 0, 0.7, 0, 0.7])

            company_name = ["DEEP EIGEN"]

            if (int(data['created_date'].day) < 10 and int(data['created_date'].month) < 10):
                
                invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; &nbsp; # &nbsp;DE/{a}-{b}/{c:05d} <br/>Date:&nbsp; 0{1}/0{2}/{3} '.format(
                
                str(5.1*mm),     str(data['created_date'].day),    str(data['created_date'].month),   str(data['created_date'].year), a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=s_n) ]

            
            elif (int(data['created_date'].day) < 10 and int(data['created_date'].month) >10):
                
                invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; &nbsp; # &nbsp; &nbsp;DE/{a}-{b}/{c:06d} <br/>Date:&nbsp; 0{1}/{2}/{3} '.format(
                    
                    str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),     str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=s_n)]

            
            elif (int(data['created_date'].day) >10 and int(data['created_date'].month) < 10):
                
                invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; # &nbsp;DE/{a}-{b}/{c:06d}<br/>Date:&nbsp; {1}/0{2}/{3} '.format(
                    
                    str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),    str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=s_n)]


            else :
                invoice_data = ['<font color="red" face="bookman-bold" size="{0}"> <u>INVOICE </u> </font> <br/> <br/> &nbsp; # &nbsp;DE/{a}-{b}/{c:06d} <br/>Date:&nbsp; {1}/{2}/{3} '.format(
                
                    str(5.1*mm), str(data['created_date'].day), str(data['created_date'].month),    str(data['created_date'].year),  a=str(financial_year[0])[2:],  b=str(financial_year[1])[2:],  c=s_n)]




            input_string =data['course']

            words = input_string.title.split()
            words.insert(-2,'\n')
            output_string = ' '.join(words)


            invoice_data_1 = [
                'Phone: &nbsp; {0} <br/> Email: &nbsp; {1}'.format(str(data['phone_number']), data['email'])]

            user_data = ['<font color="red" face="bookman-bold" size="{0}"></font> <br/> <font face="bookman-bold"> To &nbsp; &nbsp; &nbsp;&nbsp;&nbsp;&nbsp; :&nbsp;{1}  {2} </font> <br/> <font face="bookman-bold" >State </font> &nbsp;&nbsp; &nbsp; :&nbsp;{3} <br/>  <font face="bookman-bold" > Country </font>:   {4} <br/> <font face="bookman-bold" > PIN </font> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; :&nbsp;{5}' .format(
                str(5*mm), data['firstname'].capitalize(), data['lastname'].capitalize(), data['state'], data['country'], data['zipcode'])] 

            table_data = [['#','Course Description', 'Payment ID', 'Total INR'],

                        ['1', '{0}'.format(output_string), '{0}'.format(
                            data['payment_id']), 'Rs : {0}'.format(data['amount'])],

                        ['2', ' Discount  Offered ', '', 'Rs : {a}'.format(a=str(0.0))],

                        ['', '', '', ''],
                        ['3',"No Of Installments","Installment","Amount"],

                        ['','{0}'.format(enrollUser[0].no_of_installments),'{0}'.format(install),'Rs:{0}'.format(data['amount_paid'])],

                            ['Total Amount', ' ', ' ', 'Rs : {0}'.format(
                            data['total_amount'])],

                            ['Paid amount', ' ',' ', 'Rs : {0}'.format(
                            total_amount_paid['total_sum'])],

                            ['Remaining Amount',  ' ', ' ',  'Rs : {0}'.format((data['remaining_amount']))]]

            table_below_data = ['SUBJECT TO BHOPAL JURISDICTION', 'E. & O. E.']

            Amount_in_words = ['<font face="bookman" >Amount Chargeable (in words) </font>: <br/> <font face="bookman-bold" size={0}>  INR {1} Rupees Only  /- </font>'.format(
                str(4.3*mm), amount_chargebale.capitalize())]

            company_details = ['Company PAN : AAICD5934H',
                'CIN: U80900MP2021PTC056553']


            signature=['computer generated receipt hence signature not required ']


            font_name = 'Regular'  # custom font name


            def heading():                                # Heading with name DEEP EIGEN
                textobject = c.beginText(94*mm, 290*mm)
                textobject.setFillColorRGB(200, 0, 0)
                textobject.setFont('bookman-bold', 10*mm)
                textobject.setHorizScale(100)
                for line in company_name:
                    textobject.textLine(line)
                return textobject


            def invoice_text():                           # Invoice  heading below text

                Style = ParagraphStyle(
                    name='BodyText',
                    fontName='bookman',
                    fontSize=4.4*mm,
                    alignment=2, 
                    leftIndent=30,
                    borderPadding=10,
                    spaceShrinkage=0.04,
                    rightIndent=-180,
                    spaceBefore=8,          
                    spaceAfter=8,
                    leading=18,
                
                    )

                text = c.beginText(200*mm, 270*mm)
                text.setFillColorRGB(0, 0, 0)
                text.setFont('bookman', 14)
                for line in invoice_data:
                    text = Paragraph(line, style=Style, bulletText=None)
                return text

            def invoice_text_email():
                Style = ParagraphStyle(
                    name='BodyText',
                    fontName='bookman',
                    fontSize=4.4*mm,
                    leftIndent=-40,
                    spaceBefore=8,
                    spaceAfter=8,
                    leading=18,
                    allowWidows=1,
                    )
                text = c.beginText(130*mm, 240*mm)
                text.setFillColorRGB(0, 0, 0)
                text.setFont('bookman', 14)
                for line in invoice_data_1:
                    text = Paragraph(line, style=Style, bulletText=None)
                return text


            def user_text():
                
                Style = ParagraphStyle(

                    name='BodyText',
                    fontName='bookman',
                    fontSize=4.4*mm,
                    leftIndent=20,
                    borderPadding=10,
                    spaceShrinkage=0.05,
                    rightIndent=-180,
                    spaceBefore=8,
                    spaceAfter=8,
                    leading=18
                )
                text = c.beginText(150, 680)
                text.setFillColorRGB(0, 0, 0)
                text.setFont('bookman', 12)
                for line in user_data:
                    text = Paragraph(line, style=Style, bulletText=None)
                return text

            def text():                                  # Other  text  below table
                text = c.beginText(20*mm, 125*mm)
                text.setFillColorRGB(0, 0, 0)
                text.setFont('Times-Roman', 4.1*mm)
                for i in range(len(table_below_data)):
                    if i == 1:
                        text.setTextOrigin(204*mm, 125*mm)
                        text.setFont('Times-Bold', 4.1*mm)
                        text.textLine(table_below_data[i])
                    else:
                        text.textLine(table_below_data[i])

                return text

            def amount_in_words():                    # Paid Amount in words
                text = c.beginText(20*mm, 120*mm)
                Style=ParagraphStyle(
                    
                    name='BodyText',
                    fontName='bookman',
                    fontSize=4.1*mm,
                    borderPadding=10,
                    spaceShrinkage=0.05,
                    rightIndent=-180,
                    spaceBefore=8,
                    spaceAfter=8,
                    leading=18
                    
                )
                
                for line in Amount_in_words:
                    text=Paragraph(line,style=Style,bulletText=None)
                
                return text

            def Company_Details():                      # Company Details
                c.line(20*mm, 85*mm, 230*mm,85*mm)
                text = c.beginText(25*mm, 80*mm)
                text.setFont('bookman', 4.1*mm)
                c.line(20*mm, 69*mm, 230*mm,69*mm)
                for i in range(len(company_details)):
                    if i == 1:
                        text.setTextOrigin(25*mm, 73*mm)
                        text.textLine(company_details[i])
                    else:
                        text.textLine(company_details[i])
                return text

            table = Table(table_data, colWidths=[10*mm ,95*mm,55*mm,50*mm] ,rowHeights=[20,35,26,26,30,26,35,30,35])               #### Table data

            table.setStyle(TableStyle([('BACKGROUND', (0, 0),(2,0),colors.white),

                                ('BOX', (0, 0),(-1,-1),2,colors.black),
                                ('GRID', (0, 0), (3, 1), 1, colors.black),
                                ('GRID', (0, 1),(3,1),1,colors.black),
                                ('GRID', (0, 2),(3,2),1,colors.black),
                                ('GRID', (0, 3),(3,3),1,colors.black),
                                ('GRID',(0,4),(3,4),1,colors.black),
                                ('GRID',(0,5),(3,5),1,colors.black),

                                ('LINEBELOW', (0, 4),(3,4),1,colors.black),
                                ('LINEBELOW', (0, 5),(3,5),1,colors.black),
                                ('LINEBELOW', (0, 6),(3,6),1,colors.black),
                                ('LINEBELOW', (0, 7),(3,7),1,colors.black),
                                ('GRID', (-1, 0),(-1,8),1,colors.black),
                # ('LINEBEFORE',(-1,0),(-1,-4),1,colors.black),
                                ('LINEBEFORE', (-2, 0),(0,-4),1,colors.black),
                                ('VALIGN', (0, 0),(-1,-1),'MIDDLE'),
                                ('ALIGN', (-1, 0),(-1,8),'CENTER'),
                                ('ALIGN', (1, 0),(1,1),'LEFT'),
                                ('FONT', (0, 0), (3, 0), 'bookman-bold', 4.2*mm),
                                ('FONT', (0, 2), (2, 2), 'bookman-bold', 4.2*mm),
                                ('FONT', (0, 4), (0, 8), 'bookman', 4.3*mm),
                                ('FONT', (0, 5), (3, 5), 'bookman', 4.3*mm),
                                ('FONT', (0, 1),(1,1),'bookman',4.1*mm),
                                ('FONT',(0,4),(3,4),'bookman-bold',4.3*mm),
                                ('FONT', (1, 1), (2, 1), 'bookman', 4.0*mm),
                                ('FONT', (1, 1), (1, 1), 'bookman-bold', 4.0*mm),
                                ('FONT', (-1, 0),(-1,1),'bookman-bold',4.2*mm),
                                ('FONT', (-1, 1), (-1, 8), 'Arial', 4.1*mm),
                                ('FONT', (0, 0), (0, 2), 'bookman-bold', 4.2*mm),
                                ('FONT', (-1, 4), (-2, 4), 'bookman-bold', 4.3*mm),

            ]))


            def Sign():
                text=c.beginText(120*mm, 100*mm)
                text.setFillColorRGB(0, 0, 0)
                text.setFont('bookman',4*mm)
                for i in range(len(signature)):
                    text.textLine(signature[i])
                return text

            ######### Drawing  the content on canvas  ###################

            c.drawText(heading())

            invoice = invoice_text()

            invoice1 = invoice_text_email()

            invoice.wrapOn(c, 80*mm, 255*mm)

            invoice.drawOn(c, 80*mm, 255*mm)

            invoice1.wrapOn(c, 155*mm, 235*mm)

            invoice1.drawOn(c, 155*mm, 235*mm)

            user_para = user_text()

            user_para.wrapOn(c, 25*mm, 235*mm)

            user_para.drawOn(c, 25*mm, 235*mm)

            table.wrapOn(c, 20*mm, 174*mm)

            table.drawOn(c, 20*mm, 132*mm)

            c.drawText(text())

            amount = amount_in_words()

            amount.wrapOn(c,20*mm, 125*mm)

            amount.drawOn(c,20*mm, 104*mm)

            c.drawText(Company_Details())

            c.drawText(Sign())

            c.save()
            

            c.showPage()

            buf.seek(0)

            res=HttpResponse(buf.getvalue(),headers={
                    'Content-Type':"application/pdf",
                    "Content-Disposition": 'attachment; filename="invoice.pdf"',
                })

            file=ContentFile(buf.getvalue())

            
             
            invoice_reg.invoice.save(f"{order[0].first_name}_invoice.pdf",file,save=True)

            ###-------------------------Sending email to the course Ta's-------------------------------###

            
            
            return invoice_reg
          
    except Exception as e:
        print(f"{type(e).__str__(e)}")
        return e
        


class InvoiceAdmin(admin.ModelAdmin):
    """
    Administrative interface for Invoice Registration.
    
    Includes functionality to batch generate invoices and 
    provides individual download buttons.
    """
    def has_module_permission(self, request: HttpRequest) :
        try:
            if not request.user.is_superadmin:
                return False
            
            else:
              return True
        except AttributeError:
            return True
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('add_invoice_reg/', self.admin_site.admin_view(self.custom_add_invoice_reg_view), name='course_invoice_registrant_custom_view'),
            
        ]
        return custom_urls + urls
    
    def custom_add_invoice_reg_view(self,request):
        
        enroll_users=EnrolledUser.objects.order_by("created_at").all()
      
        invoices=[]
        try:
            for user in enroll_users:
                
                invoice_reg=Invoice_add(user.id,user.payment.payment_id,user.course.id)
                invoices.append(invoice_reg)

                if user.installment_id_2 != None:
                    Invoice_reg=Invoice_add(user.id,user.installment_id_2,user.course.id)
                    invoices.append(Invoice_reg)
                if user.installment_id_3 != None:
                    Invoice_reg=Invoice_add(user.id,user.installment_id_3,user.course.id)
                    invoices.append(Invoice_reg)
            
            context={
                "users":invoices
            }
            return render(request,"admin/invoice_registrant.html",context)
        
        except Exception as e:
            print(f"{type(e).__str__(e)}")
            return f"{type(e).__str__(e)}"

    def download_invoice_button(self, obj):
        """Creates a download button for each invoice"""
        # Extract numeric part from order_number
        order_number = obj.order.order_number if obj.order else None
        numeric_order_number = re.search(r'\d+', order_number).group() if order_number else "Unknown"

        # Directly accessing the course title to get rid of "Lucky->"
        name = obj.name.course.title if obj.name and obj.name.course else "Unknown"
        course = Course.objects.filter(title=name).first()

        # Fetch order based on order_number
        order = Order.objects.filter(order_number__icontains=order_number).first()

        if order:
            # Extract payment ID and clean it
            payment_string = order.payment.payment_id if order.payment else "Unknown"
            payment_id = payment_string.split("->")[-1]  # Split and get the part after "Lucky->"

            # Get user_id from obj.name
            user_id = obj.name.user.id if obj.name and obj.name.user else "Unknown"
            
            if course and payment_id and course.id and numeric_order_number and user_id:
                # Generate the URL for the download invoice view
                url = reverse("enroll_Invoice_manual", args=[user_id, payment_id, course.id, numeric_order_number])
                return format_html('<a class="button" href="{}" target="_blank">📥 Download Invoice</a>', url)
        
        return "No Invoice Available"


    download_invoice_button.short_description = "Download Invoice"
        
    list_display=('name','serial_no',"order", "download_invoice_button")

    search_fields=('name__user__email',)

admin.site.register(Instructor, InstructorAdmin)
admin.site.register(TeachingAssistant, TeachingAssistantAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Section, SectionAdmin)
admin.site.register(Outline, OutlineAdmin)
admin.site.register(Module, ModuleAdmin)
admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(Video, VideoAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(EnrolledUser, EnrolledUserAdmin)
admin.site.register(AssignmentEvaluation, AssignmentEvaluationAdmin)
admin.site.register(PaymentMethod,PaymentMethodAdmin)
admin.site.register(OverallProgress, OverallProgressAdmin)
admin.site.register(Failed_Assignments,Failed_AssignmentAdmin)
admin.site.register(Invoice_Registrant, InvoiceAdmin)
# admin.site.register(UserInvoice,UserInvoiceAdmin)











###### Admin with previous changes 

# from django.contrib import admin
# from .models import *
# from accounts.models import Account
# from django.utils.html import format_html

# # Register your models here.
# class InstructorAdmin(admin.ModelAdmin):
#     def profile(self, object):
#         return format_html('<img src="{}" width="80" style="border-radius:50%;">'.format(object.profile_picture.url))

#     list_display = ('id', 'profile', 'first_name', 'email')
#     search_fields = ('first_name', 'email')
#     ordering = ('id',)

# class TeachingAssistantAdmin(admin.ModelAdmin):
#     def profile(self, object):
#         return format_html('<img src="{}" width="80" style="border-radius:50%;">'.format(object.profile_picture.url))

#     list_display = ('id', 'profile', 'first_name', 'email')
#     search_fields = ('first_name', 'email')
#     ordering = ('id',)

# class CourseAdmin(admin.ModelAdmin):
#     def course_image_picture(self, object):
#         return format_html('<img src="{}" width="80">'.format(object.course_image.url))

#     list_display = ('id', 'course_image_picture', 'title', 'category')
#     search_fields = ('title', 'category')
#     ordering = ('-id',)
#     list_display_links = ('title', 'id', 'course_image_picture')
#     class Meta:
#         # Add verbose name
#         verbose_name = 'Course'

# class SectionAdmin(admin.ModelAdmin):

#     list_display = ('name', 'course',)
#     search_fields = ('name', 'title',)
#     ordering = ('-id',)
#     list_filter = ('course_id',)

# class ModuleAdmin(admin.ModelAdmin):

#     list_display = ('title', 'section',)
#     search_fields = ('section__name',)
#     ordering = ('-id',)
#     list_filter = ('section__course_id',)
#     save_as = True

# class AssignmentAdmin(admin.ModelAdmin):

#     list_display = ('name', 'module', 'pdf')
#     search_fields = ('name',)
#     ordering = ('-id',)
#     list_filter = ('module__section__course_id',)

# class VideoAdmin(admin.ModelAdmin):

#     list_display = ('title', 'module', 'type', 'duration',)
#     search_fields = ('title',)
#     ordering = ('-module_id',)
#     list_filter = ('module__section__course_id',)

# class AssignmentEvaluationAdmin(admin.ModelAdmin):

#     list_display = ('user', 'assignment', 'submitted_file', 'score', 'submit_flag', 'created_at')
#     search_fields = ('score', 'user__email')
#     ordering = ('-id',)
#     list_filter = ('course_id',)

# class EnrolledUserAdmin(admin.ModelAdmin):

#     list_display = ('user', 'course','created_at','payment')
#     search_fields = ('user__email','course__title')
#     ordering = ('-id',)
#     list_filter = ('course_id',)

# class OutlineAdmin(admin.ModelAdmin):

#     list_display = ('title', 'course',)
#     search_fields = ('title','course__title',)
#     ordering = ('-id',)
#     list_filter = ('course_id',)

# class OrderAdmin(admin.ModelAdmin):

#     list_display = ('order_number', 'course', 'email', 'total_amount', 'is_ordered','payment','created_at')
#     search_fields = ('order_number', 'email')
#     ordering = ('-id',)
#     list_filter = ('course_id',)

# class PaymentAdmin(admin.ModelAdmin):

#     list_display = ('user', 'payment_id', 'payment_method', 'amount_paid', 'status')
#     search_fields = ('user__email', 'payment_method','id','payment_id')
#     ordering = ('-id',)

# class OverallProgressAdmin(admin.ModelAdmin):

#     list_display = ('user', 'course', 'progress')
#     search_fields = ('user__email', 'progress')
#     ordering = ('-id',)

# class Faild_AssignmentAdmin(admin.ModelAdmin):
#     list_display = ('user', 'assignment', 'submitted_file', 'score', 'created_at')
#     search_fields = ('score', 'user__email')
#     ordering = ('-id',)
#     list_filter = ('course_id',)


# admin.site.register(Instructor, InstructorAdmin)
# admin.site.register(TeachingAssistant, TeachingAssistantAdmin)
# admin.site.register(Course, CourseAdmin)
# admin.site.register(Section, SectionAdmin)
# admin.site.register(Outline, OutlineAdmin)
# admin.site.register(Module, ModuleAdmin)
# admin.site.register(Assignment, AssignmentAdmin)
# admin.site.register(Video, VideoAdmin)
# admin.site.register(Order, OrderAdmin)
# admin.site.register(Payment, PaymentAdmin)
# admin.site.register(EnrolledUser, EnrolledUserAdmin)
# admin.site.register(AssignmentEvaluation, AssignmentEvaluationAdmin)
# admin.site.register(PaymentMethod)
# admin.site.register(OverallProgress, OverallProgressAdmin)
# admin.site.register(Failed_Assignments,Faild_AssignmentAdmin)