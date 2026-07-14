from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from course.models import Assignment, AssignmentEvaluation
import logging

logger = logging.getLogger(__name__)  # Optional: for logging errors in production

     
        
# Assignment Api
def assignment_api(request):
    """!
    @brief Administrative API endpoint to retrieve a paginated list of all course assignments.
    @details Supports backend dashboard management by providing metadata including 
             assignment type, module association, and direct PDF access links.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated collection of assignment metadata (200).
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
        
        assignments = Assignment.objects.all().order_by('-created_date')
        
        # Paginate enrolled users
        paginator = Paginator(assignments, limit)
        
        try:
            assignment_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page out of range', 'total_pages': paginator.num_pages}, status=404)
        
        assignments_data = []
        
        for eu in assignment_page.object_list:
            assignments_data.append({
                'id': eu.id,
                'name': eu.name,
                'assignment_type': eu.assignment_type,
                'module': eu.module.title,
                'course_title': eu.course.title,
                'created_date': eu.created_date,
                'current_pdf': eu.pdf.url if eu.pdf else None,
            })
            
        # print("assignments_data:", json.dumps(assignments_data, indent=4, default=str))
        return JsonResponse({
            'assignments': assignments_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('unhandled error in assignment_api view')
        
        return JsonResponse({
            'error': 'Something went wrong. Please try again later'         
        }, status=400)
        
        
# Assignment Evaluation
def assignmentEvaluation_api(request):
    """!
    @brief Administrative API endpoint to audit student assignment submissions and scores.
    @details Aggregates student-specific performance data across all courses, providing 
             access to submitted files and automated evaluation flags.

    @param request (HttpRequest) DRF/Django Request with 'page' and 'limit' query params.

    @return JsonResponse Paginated list of student evaluation records (200).
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
        
        assignmentEvaluation = AssignmentEvaluation.objects.all().order_by('-created_at')
        
        # Paginate enrolled users
        paginator = Paginator(assignmentEvaluation, limit)
        
        try:
            assignmentEvaluation_page = paginator.page(page)
        except PageNotAnInteger:
            return JsonResponse({ 'error': 'Page is not an integer'}, status=400)
        except EmptyPage:
            return JsonResponse({'error': 'Page our of range', 'total_pages': paginator.num_pages}, status=404)
        
        assignmentEvaluation_data = []
        
        for eu in assignmentEvaluation_page.object_list:
            assignmentEvaluation_data.append({
                'id': eu.id,
                'user_id': eu.user.id,
                'user_name': eu.user.first_name,
                'user_email': eu.user.email,
                'course_title': eu.course.title,
                'section_name': eu.section.name,
                'assignment_name': eu.assignment.name,
                'score': eu.score,
                'submitted_file': eu.submitted_file.url if eu.submitted_file else None,
                'submit_flag': eu.submit_flag,
                'created_at': eu.created_at,
            })
            
        # print("assignmentsEvalu_data:", json.dumps(assignmentEvaluation_data, indent=4, default=str))
        return JsonResponse({
            'assignmentEvaluation': assignmentEvaluation_data,
            'total_pages': paginator.num_pages,
            'current_page': page
        }, status=200)
    except Exception as e:
        # Optional: log unexpected errors
        logger.exception('unhandled error in assignment_api view')
        
        return JsonResponse({
            'error': 'Something went wronge. Please try again later'         
        }, status=400)

      