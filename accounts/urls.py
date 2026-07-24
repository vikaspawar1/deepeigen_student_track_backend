"""
URL configuration for the accounts app.

Defines endpoints for authentication, registration, dashboard, profile management,
and account-specific functions like password resets and payment history.
"""
from django.urls import path
from accounts import views, auth_views


urlpatterns = [
    path('login/', views.login, name='login'),
    path('jwt-login/', auth_views.jwt_login, name='jwt_login'),
    path('refresh/', auth_views.jwt_refresh, name='refresh'),
    path('logout/', auth_views.jwt_logout, name='logout'),
    
    path('register/', views.register, name='register'),
    
    # login mannual made by khilesh (Date - 15_Jan_2025)
    path('register_mannual/', views.register_mannual, name='register_mannual'),
    path('login_mannual/', views.login_mannual, name='login_mannual'),
    
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('', views.dashboard, name='dashboard'),

    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('forgotPassword/', views.forgotPassword, name='forgotPassword'),
    path('resetpassword_validate/<uidb64>/<token>/', views.resetpassword_validate, name='resetpassword_validate'),
    path('resetPassword/', views.resetPassword, name='resetPassword'),

    path('mycourses/', views.mycourses, name='mycourses'),
    path('profile/', views.profile, name='profile'),   
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('upload_profile_picture/', views.upload_profile_picture, name='upload_profile_picture'),
    path('change_password/', views.change_password, name='change_password'),
   
    path('payment_due/',views.Payment_due,name="payment_due"),
    path('payment_history/<int:course_id>/', views.payment_history, name='payment_history'),  # API for payment history - added 10 Feb 2026
    path('invoice_manual/<str:userId>/<str:payment_id>/<int:course_id>/<str:orderNumber>', views.Invoice_manual,name="enroll_Invoice_manual" ),
    path('playlists/', views.playlists, name='playlists'),
    path('certificates/', views.certificates, name='certificates'),
    path('verify-certificate/', views.verify_certificate, name='verify_certificate'),

    path('invoice/', views.Invoice_section, name="Invoice_section"),


    
    path('invoice/status/<str:order_id>/', views.invoice_status, name="invoice_status"),

    path('invoice/<str:payment_id>/<int:course_id>/<str:orderNumber>/', views.Invoice, name="enroll_Invoice"),      
    
    path('invoice/playlist/<str:payment_id>/<int:playlist_id>/', views.playlist_invoice_view, name="playlist_invoice"),

    # on feb 14 #added new 13feb vikas
    path('recent-watch/', views.recent_watch, name='recent_watch'),
    
    # Track last accessed course - added 13 Feb 2026
    path('track-last-accessed-course/', views.track_last_accessed_course, name='track_last_accessed_course'),
    

    
]
