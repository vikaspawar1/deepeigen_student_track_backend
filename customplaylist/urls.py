from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.create_custom_playlist, name='create_custom_playlist'),
    path('preview/', views.preview_custom_playlist, name='preview_custom_playlist'),
    path('initiate_payment/<int:playlist_id>/', views.initiate_playlist_payment, name='initiate_playlist_payment'),
    path('verify_payment/<int:playlist_id>/', views.verify_playlist_payment, name='verify_playlist_payment'),
    path('my-playlists/', views.user_playlists, name='user_playlists'),
    path('details/<int:playlist_id>/', views.get_playlist_details, name='get_playlist_details'),
]
