from django.urls import path
from . import views
from .views import login_view, logout_view



urlpatterns = [
  # ---------------- GALAXY ----------------
    path('galaxies/', views.GalaxyListView.as_view(), name='galaxies-list'),  # GET список всех галактик
    path('galaxies/<int:pk>/', views.GalaxyDetailView.as_view(), name='galaxies-detail'),  # GET детали одной галактики
    path('galaxies/create/', views.GalaxyCreateView.as_view(), name='galaxies-create'),  # POST создание галактики (модератор)
    path('galaxies/<int:pk>/update/', views.GalaxyUpdateView.as_view(), name='galaxies-update'),  # PUT обновление галактики по ID
    path('galaxies/<int:pk>/upload-image/', views.GalaxyImageUploadView.as_view(), name='galaxies-upload-image'),  # POST загрузка изображения галактики
    path('galaxies/<int:pk>/delete/', views.GalaxyDeleteView.as_view(), name='galaxies-delete'),  # DELETE мягкое удаление галактики
    path('galaxies/<int:pk>/add-to-request/', views.AddGalaxyToDraftView.as_view(), name='galaxiesinrequest-add'), #POST добавление услуги в черновую заявку

    # ---------------- GALAXY REQUEST ----------------
    path('galaxy_requests/', views.GalaxyRequestListView.as_view(), name='galaxyrequests-list'),  # GET список всех заявок текущего пользователя
    path('galaxy_requests/<int:pk>/', views.GalaxyRequestDetailView.as_view(), name='galaxyrequests-detail'),  # GET детали одной заявки
    path('galaxy_requests/update/', views.GalaxyRequestUpdateView.as_view(), name='galaxyrequests-update'),  # PUT изменение поля telescope //кто вводит эти данные? 
    path('galaxy_requests/form/', views.GalaxyRequestFormView.as_view(), name='galaxyrequests-form'),  # PUT формирование черновой заявки
    path('galaxy_requests/<int:pk>/complete/', views.GalaxyRequestCompleteView.as_view(), name='galaxyrequests-complete'),  # PUT завершение или отклонение заявки модератором
    path('galaxy_requests/delete/', views.GalaxyRequestDeleteView.as_view(), name='galaxyrequests-delete'),  # DELETE мягкое удаление черновой заявки
    path('galaxy_requests/cart-icon/', views.CartIconView.as_view(), name='cart-icon'),  # GET количество услуг в черновой заявке

    # ---------------- GALAXIES IN REQUEST ----------------
    path('galaxy_requests/<int:pk>/remove-from-request/', views.RemoveGalaxyFromDraftView.as_view(), name='galaxiesinrequest-delete'),  # DELETE удаление услуги из текущей черновой заявки
    path('galaxy_requests/update-magnitude/', views.UpdateMagnitudeView.as_view(), name='galaxiesinrequest-update-magnitude'),  # PUT изменение magnitude услуги в черновой заявке

    # ---------------- USER ----------------
    path('users/register/', views.UserRegisterView.as_view(), name='user-register'),  # POST регистрация пользователя
    path('users/login/', login_view, name='user-login'),  # POST вход в систему (сессия + csrf)
    path('users/logout/', logout_view, name='user-logout'),  # POST выход из системы
    path('users/profile/', views.UserProfileView.as_view(), name='user-profile'),  # GET/PUT профиль текущего пользователя

]
