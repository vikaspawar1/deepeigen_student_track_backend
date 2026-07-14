from django.contrib import admin
from django.urls import path, include
from .views import discussionforum
from .views import assignment
from .views import enrolledUsers
from .views import users
from .views import invoice
from .views import overallProgress

from .views.graphs import enrolledUser, totalIncome, pendingsOrders, salesToday, newOrder, registeredUsers, mostSellingCourses, FiveYearCourseSalesSummary, overallShellWorldWide, monthlyShellWorldWide

urlpatterns = [
    path('users/', users.users_api, name='users-api'),
    path('enrolledUsers/', enrolledUsers.enrolledUsers_api, name='enrolledUsers_api'),
    path('assignment_api/', assignment.assignment_api, name='assignment_api'),
    path('assignmentEvaluation_api/', assignment.assignmentEvaluation_api, name='assignmentEvaluation_api'),
    path('invoiceRegistrant_api/', invoice.invoiceRegistrant_api, name='invoiceRegistrant_api'),
    path('overallProgress_api/', overallProgress.overallProgress_api, name='overallProgress_api'),
    
    path('questions_api/', discussionforum.questions_api, name='questions_api'),
    path('replys_api/', discussionforum.replys_api, name='replys_api'),
    path('subReplys_api/', discussionforum.subReplys_api, name='subReplys_api'),
    
    path('graph_enrolledUsers_api/', enrolledUser.graph_enrolledUsers_api, name='graph_enrolledUser_api' ),
    path('graph_total_income_api/', totalIncome.graph_total_income_api, name='graph_total_income_api'),
    path('graph_new_order_api/', newOrder.graph_new_order_api, name='graph_new_order_api'),
    path('graph_sales_today_api/', salesToday.graph_sales_today_api, name='graph_sales_today_api'),
    path('graph_pending_orders_api/', pendingsOrders.graph_pending_orders_api, name='graph_pending_orders_api'),
    
    path('graph_registeredUser_api/', registeredUsers.graph_registeredUser_api, name='graph_registeredUser_api'),
    path('most_selling_courses_api/', mostSellingCourses.most_selling_courses_api, name='most_selling_courses_api'),
    path('five_year_sales_summary_api/', FiveYearCourseSalesSummary.five_year_sales_summary_api, name='five_year_sales_summary_api'),
    path('overall_shell_world_wide_api/', overallShellWorldWide.overall_shell_world_wide_api, name='overall_shell_world_wide_api'),
    path('monthly_shell_world_wide_api/', monthlyShellWorldWide.monthly_shell_world_wide_api, name='monthly_shell_world_wide_api'),
]  