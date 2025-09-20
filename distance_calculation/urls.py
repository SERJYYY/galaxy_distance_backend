from django.urls import path
from . import views

urlpatterns = [
    path('galaxies/', views.galaxies_list, name='galaxies_list'),                     # → /
    path('galaxy/<int:galaxy_id>/', views.galaxy_detail, name='galaxy_detail'),
    path('galaxy_request/<int:request_id>/', views.galaxy_request, name='galaxy_request'),  
]