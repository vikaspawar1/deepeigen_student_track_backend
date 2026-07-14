from django import template
from accounts.models import Account
from course.models import EnrolledUser, Course, Section, UserVideoProgress, OverallProgress, AssignmentEvaluation
from datetime import datetime, date
from django.core.exceptions import ObjectDoesNotExist
register = template.Library()

@register.simple_tag
def enrolled_user(course, user):
    now = datetime.now()
    return EnrolledUser.objects.filter(course_id=course.id, enrolled=True, user_id=user.id, end_at__gt=now).first()

@register.simple_tag
def assignment_submitted(assignment_id, user_id):
    try:
        return AssignmentEvaluation.objects.get(assignment_id=assignment_id, user_id=user_id)
    except AssignmentEvaluation.DoesNotExist:
        return None

@register.simple_tag
def user_overall_progress(course, user):
    try:
      admin_user=Account.objects.get(id=user.id)
      
      if admin_user.is_staff or admin_user.is_superadmin:
          progress=100
          return progress
      
      else:
        progress = OverallProgress.objects.filter(course_id=course.id, user_id=user.id).first().progress
        if progress > 99:
            return 100
        else:
            return progress
    
    except ObjectDoesNotExist:
       
        print("Account doesnt Exists !")

@register.simple_tag
def remaining_days(course_id, user_id):
    try:
    
       admin_user=Account.objects.get(id=user_id)

       if admin_user.is_staff or admin_user.is_superadmin:
           year,month,day=(datetime.today().year,datetime.today().month,datetime.today().day)
        #    print(year,month)
           end_at=datetime(year,month+3,day)
       else:
           end_at = EnrolledUser.objects.filter(course_id=course_id, user_id=user_id, enrolled=True).first().end_at
           

    except ObjectDoesNotExist:
    
        print("Account doesnt Exists !")
    
    return (end_at.date() - datetime.now().date()).days

@register.simple_tag
def already_reviewed(assignment_id, user_id):
    try:
        return AssignmentEvaluation.objects.filter(assignment_id=assignment_id, user_id=user_id).first()
    except AssignmentEvaluation.DoesNotExist:
        return None

@register.simple_tag
def unlock_next_part(course_id, section, user_id):
    if section.part_number == 1:
        return True
    else:
        section_part = section.part_number - 1
        section = Section.objects.get(part_number=section_part, course_id=course_id)
        assignment = AssignmentEvaluation.objects.filter(user_id=user_id, section_id=section.id, submit_flag=True)
        if assignment.count() == section.total_assignments:
            return False
        else:
            return True

@register.simple_tag
def user_detail(id):
    return Account.objects.get(pk=id)