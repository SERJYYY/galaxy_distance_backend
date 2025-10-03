from django.urls import path
from . import views

urlpatterns = [
    path('galaxies/', views.galaxies_list, name='galaxies_list'),
    path('galaxy/<int:galaxy_id>/', views.galaxy_detail, name='galaxy_detail'),
    path('galaxy_request/<int:request_id>/', views.galaxy_request, name='galaxy_request'),
    path('add_galaxy/<int:galaxy_id>/', views.add_galaxy, name='add_galaxy'),
    path('delete_galaxy_request/<int:request_id>/', views.delete_galaxy_request, name='delete_galaxy_request'),
]