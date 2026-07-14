"""!
@brief URL configuration for the discussion_forum application.
@details Maps endpoint paths to forum views, including hierarchical threads (questions, replies, sub-replies).
"""
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.discussion_forum, name='discussion_forum'),
    path('<str:section_url>/', views.weekly_forum, name='weekly_forum'),
    path('<str:section_url>/create_post/', views.create_post, name="create_post"),
    path('<str:section_url>/search/', views.question_search, name="question_search"),
    path('<str:section_url>/<int:qid>/', views.individual_question, name="individual_question"),
    path('<str:section_url>/<int:qid>/create_reply/', views.create_reply, name="create_reply"),
    path('<str:section_url>/<int:qid>/<int:rid>/create_subreply/', views.create_subreply, name="create_subreply"),
]