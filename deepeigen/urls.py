# """deepeigen URL Configuration

# The `urlpatterns` list routes URLs to views. For more information please see:
#     https://docs.djangoproject.com/en/3.2/topics/http/urls/
# Examples:
# Function views
#     1. Add an import:  from my_app import views
#     2. Add a URL to urlpatterns:  path('', views.home, name='home')
# Class-based views
#     1. Add an import:  from other_app.views import Home
#     2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
# Including another URLconf
#     1. Import the include() function: from django.urls import include, path
#     2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
# """
# from django.contrib import admin
# from django.urls import path, include
# from django.views.generic import RedirectView
# from . import views
# from django.conf.urls.static import static
# from django.conf import settings
# from discussion_forum.admin import post_admin_site

# # path('', include('discussion_forum.urls')),
# urlpatterns = [
#     path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
#     path('adminsecurelogin/', admin.site.urls),
#     path('admin-ta/', post_admin_site.urls),
#     path('', views.home, name='home'),
#     path('careers/', views.careers, name='careers'),
#     path('robots.txt/', views.robots_seo, name='robots_seo'),
#     path('sitemap/', views.html_sitemap, name='html_sitemap'),
#     path('sitemap.xml/', views.xml_sitemap, name='xml_sitemap'),
    
#     # =================================================================
#     # SPA FIX: API routes now at /api/accounts/*
#     # Why: Frontend handles /accounts/* routing, calls /api/accounts/* for data
#     # =================================================================
#     path('api/accounts/', include('accounts.urls')),
    
#     # Catch-all for SPA routes - MUST BE LAST
#     path('accounts/<path:path>', views.home, name='spa_accounts'),
#     path('accounts/', views.home, name='spa_accounts_root'),
#     path('faqs/', views.faqs, name='faqs'),
#     path('faqs/', views.faqs, name='faqs'),
#     path('terms/', views.terms, name='terms'),
#     path('privacypolicy/', views.privacypolicy, name='privacypolicy'),
#     path('privacypolicygdpr/', views.privacypolicygdpr, name='privacypolicygdpr'),
#     path('team/', include('teams.urls')),
#     path('maintenance/', views.maintenance, name='maintenance'),
#     path('contact/', include('contact.urls')),
#     path('courses/', include('course.urls')),
#     path('courses/<int:id>/<str:course_url>/discussionforum/', include('discussion_forum.urls')),
#     path('dashboard/', include('dashboard.urls')),
# ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""deepeigen URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views
from django.conf.urls.static import static
from django.conf import settings
from discussion_forum.admin import post_admin_site

"""
Deep Eigen Project URL Configuration.

The `urlpatterns` list routes URLs to views. This routing configuration 
handles project-wide routing, including admin, static pages (home, faqs), 
and includes application-specific routings for accounts, courses, dashboard, etc.
"""
urlpatterns = [
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path('adminsecurelogin/', admin.site.urls),
    path('admin-ta/', post_admin_site.urls),
    path('', views.home, name='home'),
    path('careers/', views.careers, name='careers'),
    path('robots.txt/', views.robots_seo, name='robots_seo'),
    path('sitemap/', views.html_sitemap, name='html_sitemap'),
    path('sitemap.xml/', views.xml_sitemap, name='xml_sitemap'),
    path('accounts/', include('accounts.urls')),
    path('faqs/', views.faqs, name='faqs'),
    path('faqs/', views.faqs, name='faqs'),
    path('terms/', views.terms, name='terms'),
    path('privacypolicy/', views.privacypolicy, name='privacypolicy'),
    path('privacypolicygdpr/', views.privacypolicygdpr, name='privacypolicygdpr'),
    path('team/', include('teams.urls')),
    path('maintenance/', views.maintenance, name='maintenance'),
    path('contact/', include('contact.urls')),
    path('courses/', include('course.urls')),
    path('courses/<int:id>/<str:course_url>/discussionforum/', include('discussion_forum.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('customplaylist/', include('customplaylist.urls')),
    path('subscriptions/', include('subscriptions.urls')),
    path('student-analytics/', include('student_analytics.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
