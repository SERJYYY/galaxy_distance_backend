from django.urls import path
from . import views

urlpatterns = [
    # -----------------------
    # GALAXIES
    # -----------------------
    path('galaxies/', views.GalaxyListView.as_view(), name='galaxy-list'),  # GET все галактики
    path('galaxies/create/', views.GalaxyCreateView.as_view(), name='galaxy-create'),  # POST создать галактику
    path('galaxies/add-to-draft/', views.AddGalaxyToDraftView.as_view(), name='galaxy-add-to-draft'),  # POST добавить галактику в черновик заявки
    path('galaxies/<int:pk>/', views.GalaxyDetailView.as_view(), name='galaxy-detail'),  #GET одна галактика
    path('galaxies/update/', views.GalaxyUpdateView.as_view(), name='galaxy-update'),  #PUT изменение полей галактики
    path('galaxies/upload-image/', views.GalaxyImageUploadView.as_view(), name='galaxy-upload-image'),  #POST добавление изображения через minio
    path('galaxies/delete/', views.GalaxyDeleteView.as_view(), name='galaxy-delete'),  # DELETE удаление услуги (вместе с изображением из minio)

    # -----------------------
    # GALAXY REQUESTS
    # -----------------------
    path('galaxy_requests/cart-icon/', views.CartIconView.as_view(), name='cart-icon'),  # GET количество услуг в черновой заявке
    path('galaxy_requests/', views.GalaxyRequestListView.as_view(), name='galaxyrequest-list'),  # GET список заявок
    path('galaxy_requests/<int:pk>/', views.GalaxyRequestDetailView.as_view(), name='galaxyrequest-detail'),  # GET одна заявка
    path('galaxy_requests/update/', views.GalaxyRequestUpdateView.as_view(), name='galaxyrequest-update'),  # PUT изменить поля заявки
    path('galaxy_requests/form/', views.GalaxyRequestFormView.as_view(), name='galaxyrequest-form'),  # PUT сформировать заявку
    path('galaxy_requests/complete/', views.GalaxyRequestCompleteView.as_view(), name='galaxyrequest-complete'),  # PUT завершить/отклонить модератором
    path('galaxy_requests/delete/', views.GalaxyRequestDeleteView.as_view(), name='galaxyrequest-delete'),  # DELETE удаление активной заявки


    # -----------------------
    # GALAXIS IN REQUEST VIEWS
    # -----------------------
    path('galaxy_requests/remove-from-draft/', views.RemoveGalaxyFromDraftView.as_view(), name='galaxy-remove-from-draft'), # DELETE удаление услуги из заявки
    path('galaxy_requests/update-magnitude/', views.UpdateMagnitudeView.as_view(), name='update-magnitude'),  # PUT изменение видимой звездной величины у услуги в заявке
    
    # -----------------------
    # USERS
    # -----------------------
    path('users/register/', views.UserRegisterView.as_view(), name='user-register'),  # POST регистрация
    path('users/profile/', views.UserProfileView.as_view(), name='user-profile'),  # GET/PUT профиль текущего пользователя
    path('users/login/', views.UserLoginView.as_view(), name='user-login'),  # POST аутентификация
    path('users/logout/', views.UserLogoutView.as_view(), name='user-logout'),  # POST деавторизация
]
