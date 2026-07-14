from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from discussion_forum.models import Question, Reply, SubReply
import logging
import json

logger = logging.getLogger(__name__)  # Optional: for logging errors in production

# Discussion Forum 
# Questions api
def questions_api(request):
    """!
    @brief Administrative API endpoint to retrieve a paginated list of discussion forum questions.
    @details Facilitates moderation by returning question details, approval status, 
             and associated course/section metadata.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated question collection (200).
    """
    try:
        # Get query parameters with defaults
        try:
            page = int(request.GET.get('page', 1))
            if page < 1:
                raise ValueError("Page number must be >= 1")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid page number'}, status=400)
        
        try:
            limit = int(request.GET.get('limit', 10))
            if limit < 1:
                raise ValueError("Limit must be >= 1")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid limit value'}, status=400)
        
        questions = Question.objects.all().order_by('-created_date')
        
        # Paginate enrolled users
        paginator = Paginator(questions, limit)
        
        try:
            questions_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page our of range', 'total_pages': paginator.num_pages}, status=404)
        
        questions_data = []
        
        for eu in questions_page.object_list:
            questions_data.append({
                'id': eu.id,
                'title': eu.title,
                'question': eu.question,
                'approval_flag': eu.approval_flag,
                'user_email': eu.user.email,
                'course_title': eu.course.title,
                'section_name': eu.section.name,
                'created_date': eu.created_date,
            })
            
        # print("questions_data:", json.dumps(questions_data, indent=4, default=str))
        return JsonResponse({
            'questions': questions_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('unhandled error in assignment_api view')
        
        return JsonResponse({
            'error': 'Something went wronge. Please try again later'         
        }, status=400)
        

# Replys api
def replys_api(request):
    """!
    @brief Administrative API endpoint to retrieve discussion forum replies.
    @details Supports auditing of student responses and email delivery status.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated collection of replies (200).
    """
    try:
        # Get query parameters with defaults
        try:
            page = int(request.GET.get('page', 1))
            if page < 1:
                raise ValueError("Page number must be >= 1")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid page number'}, status=400)
        
        try:
            limit = int(request.GET.get('limit', 10))
            if limit < 1:
                raise ValueError("Limit must be >= 1")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid limit value'}, status=400)
        
        replys = Reply.objects.all().order_by('-created_date')
        
        # Paginate enrolled users
        paginator = Paginator(replys, limit)
        
        try:
            replys_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page out of range', 'total_pages': paginator.num_pages}, status=404)
        
        replys_data = []
        
        for eu in replys_page.object_list:
            replys_data.append({
                'id': eu.id,
                'reply': eu.reply,
                'question_title': eu.question.title,
                'user_email': eu.user.email,
                'approval_flag': eu.approval_flag,
                'deliver_mail_flag': eu.deliver_mail_flag,
                'created_date': eu.created_date,
            })
            
        # print("questions_data:", json.dumps(replys_data, indent=4, default=str))
        return JsonResponse({
            'replys': replys_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('unhandled error in assignment_api view')
        
        return JsonResponse({
            'error': 'Something went wrong. Please try again later'         
        }, status=400)
        
        

# Sub Replys api
def subReplys_api(request):
    """!
    @brief Administrative API endpoint to retrieve discussion forum sub-replies.
    @details Extends audit capabilities to nested threaded conversations.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated collection of sub-replies (200).
    """
    try:
        # Get query parameters with defaults
        try:
            page = int(request.GET.get('page', 1))
            if page < 1:
                raise ValueError("Page number must be >= 1")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid page number'}, status=400)
        
        try:
            limit = int(request.GET.get('limit', 10))
            if limit < 1:
                raise ValueError("Limit must be >= 1")
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid limit value'}, status=400)
        
        subReplys = SubReply.objects.all().order_by('-created_date')
        
        # Paginate enrolled users
        paginator = Paginator(subReplys, limit)
        
        try:
            subReplys_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page out of range', 'total_pages': paginator.num_pages}, status=404)
        
        subReplys_data = []
        
        for eu in subReplys_page.object_list:
            subReplys_data.append({
                'id': eu.id,
                'sub_reply': eu.sub_reply,
                'reply': eu.reply.reply,
                'user_email': eu.user.email,
                'approval_flag': eu.approval_flag,
                'created_date': eu.created_date,
            })
            
        # print("questions_data:", json.dumps(subReplys_data, indent=4, default=str))
        return JsonResponse({
            'subReplys': subReplys_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('unhandled error in assignment_api view')
        
        return JsonResponse({
            'error': 'Something went wronge. Please try again later'         
        }, status=400)