# galaxy_distance/api/views.py
import uuid
import json
from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt

from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.authentication import BaseAuthentication

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.contrib.auth import authenticate

from django.db.models import Case, When, Value, IntegerField

import redis

from .models import Galaxy, GalaxyRequest, GalaxiesInRequest, CustomUser
from .serializers import (
    GalaxySerializer, GalaxyCreateSerializer,
    GalaxyRequestSerializer, GalaxyRequestDetailSerializer,
    UserRegisterSerializer, UserProfileSerializer
)
from .minio_utils import handle_galaxy_image_upload, delete_image_from_minio

# Redis client for sessions
SESSION_TTL_SECONDS = getattr(settings, "SESSION_TTL_SECONDS", 7 * 24 * 3600)  # 7 days default

redis_client = redis.StrictRedis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)

SESSION_REDIS_PREFIX = "session:"
session_storage = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)


# -------------------
# Session helpers (Redis-based)
# -------------------
class CsrfExemptSessionAuthentication(BaseAuthentication):
    """
    Кастомная аутентификация по session_id из cookie через Redis.
    """
    def authenticate(self, request):
        session_id = request.COOKIES.get("session_id")
        if not session_id:
            return None  # DRF понимает как "не аутентифицирован"

        user_username = session_storage.get(session_id)
        if not user_username:
            return None

        try:
            user = CustomUser.objects.get(username=user_username)
        except CustomUser.DoesNotExist:
            return None

        return (user, None)  # DRF требует кортеж (user, auth)


def _make_session_key(session_id: str) -> str:
    return f"{SESSION_REDIS_PREFIX}{session_id}"


def create_session_for_user(user):
    """
    Создаёт session_id, сохраняет в Redis (session:<id> -> user_id) и возвращает session_id.
    """
    session_id = uuid.uuid4().hex
    key = _make_session_key(session_id)
    try:
        redis_client.set(key, str(user.id), ex=SESSION_TTL_SECONDS)
    except Exception:
        # Если Redis недоступен — пробуем поднять исключение вверх
        raise
    return session_id


def delete_session(session_id: str):
    if not session_id:
        return
    key = _make_session_key(session_id)
    try:
        redis_client.delete(key)
    except Exception:
        # молча игнорируем ошибки удаления
        pass


def refresh_session_ttl(session_id: str):
    key = _make_session_key(session_id)
    try:
        redis_client.expire(key, SESSION_TTL_SECONDS)
    except Exception:
        pass


def get_user(request):
    """
    Возвращает экземпляр CustomUser или None.
    Берёт session_id из cookie и смотрит в Redis.
    """
    session_id = request.COOKIES.get("session_id")
    if not session_id:
        return None

    try:
        user_id = redis_client.get(_make_session_key(session_id))
    except Exception:
        return None

    if not user_id:
        return None

    try:
        user = CustomUser.objects.get(pk=int(user_id))
    except (CustomUser.DoesNotExist, ValueError):
        return None

    # продлеваем TTL
    refresh_session_ttl(session_id)
    return user


# ------------------- Permissions (Redis-session-aware) -------------------
class IsGuest(permissions.BasePermission):
    def has_permission(self, request, view):
        return get_user(request) is None


class IsAuthenticatedCustom(permissions.BasePermission):
    def has_permission(self, request, view):
        return get_user(request) is not None


class IsUser(permissions.BasePermission):
    def has_permission(self, request, view):
        user = get_user(request)
        return bool(user and not user.is_staff and not user.is_superuser)


class IsModerator(permissions.BasePermission):
    def has_permission(self, request, view):
        user = get_user(request)
        return bool(user and user.is_staff)


# helper to allow assigning permission classes on methods (like decorator in original)
def method_permission_classes(classes):
    def decorator(func):
        def decorated_func(self, *args, **kwargs):
            self.permission_classes = classes
            # call permission checks
            self.check_permissions(self.request)
            return func(self, *args, **kwargs)
        return decorated_func
    return decorator


User = CustomUser


# ------------------- Auth Views (Redis sessions) -------------------
@swagger_auto_schema(
    method='post',
    operation_description="Авторизация пользователя (по username и password). Возвращает Set-Cookie(session_id).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'username': openapi.Schema(type=openapi.TYPE_STRING, description='Имя пользователя'),
            'password': openapi.Schema(type=openapi.TYPE_STRING, description='Пароль'),
        },
        required=['username', 'password']
    ),
    responses={200: 'OK', 400: 'Ошибка авторизации'}
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def login_view(request):
    # Не используем request.user, т.к. аутентификация через Redis-сессии
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"status": "error", "message": "Необходимо указать username и password"}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"status": "error", "message": "Неверные учетные данные"}, status=400)

    # Создаём Redis-сессию
    try:
        session_id = create_session_for_user(user)
    except Exception as e:
        return Response({"status": "error", "message": f"Ошибка работы с сессиями: {str(e)}"}, status=500)

    # Получаем CSRF токен для клиента (если нужно)
    csrf_token = get_token(request)

    response = Response({
        "status": "ok",
        "message": f"Вход выполнен успешно для пользователя {user.username}",
        "csrftoken": csrf_token
    }, status=200)

    secure = not settings.DEBUG  # Secure cookie только когда не в DEBUG
    # Устанавливаем cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=secure,
        samesite='Lax',
        path='/'
    )

    return response


@swagger_auto_schema(
    method='post',
    operation_description="Выход пользователя из системы (удаление Redis-сессии и куки)",
    responses={200: 'Выход выполнен успешно'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
@csrf_exempt
def logout_view(request):
    session_id = request.COOKIES.get("session_id")
    if not session_id:
        return Response({"status": "error", "message": "Вы уже были деавторизованы"}, status=400)

    # Удаляем сессию
    delete_session(session_id)

    response = Response({"status": "ok", "message": "Вы вышли из системы"}, status=200)
    # Удаляем cookie
    response.delete_cookie('session_id', path='/')
    return response


class RedisSessionAuthentication(BaseAuthentication):
    """
    Аутентификация по session_id из cookie через Redis
    """
    def authenticate(self, request):
        session_id = request.COOKIES.get("session_id")
        if not session_id:
            return None  # DRF поймет, что аутентификация не прошла

        username = session_storage.get(session_id)
        if not username:
            return None

        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')

        return (user, None)

# ------------------- Galaxy Views -------------------
class GalaxyListView(APIView):
    @method_permission_classes((AllowAny,))
    def get(self, request):
        galaxies = Galaxy.objects.filter(is_active=True)
        serializer = GalaxySerializer(galaxies, many=True)
        return Response(serializer.data)


GalaxyListView.get = swagger_auto_schema(
    operation_description="Получить список всех активных услуг (галактик)",
    tags=["Galaxies"]
)(GalaxyListView.get)


class GalaxyDetailView(generics.RetrieveAPIView):
    queryset = Galaxy.objects.all()
    serializer_class = GalaxySerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_id="get_galaxy_detail",
        operation_description="Получить детальную информацию по одной галактике по ID",
        responses={
            200: openapi.Response(description="Детали галактики", schema=GalaxySerializer),
            404: openapi.Response(description="Галактика с указанным ID не найдена")
        },
        tags=["Galaxies"]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class GalaxyCreateView(APIView):
    permission_classes = [IsModerator]

    @swagger_auto_schema(
        operation_id="create_galaxy",
        operation_description="Создание новой галактики (услуги). Доступно только модераторам.",
        request_body=GalaxyCreateSerializer,
        responses={201: GalaxySerializer},
        tags=["Galaxies"]
    )
    def post(self, request):
        serializer = GalaxyCreateSerializer(data=request.data)
        if serializer.is_valid():
            galaxy = serializer.save()
            return Response(GalaxySerializer(galaxy).data, status=201)
        return Response(serializer.errors, status=400)

class GalaxyUpdateView(APIView):
    permission_classes = [IsModerator]

    @swagger_auto_schema(
        operation_id="update_galaxy",
        operation_description="Обновление информации о галактике по ID",
        request_body=GalaxyCreateSerializer,
        responses={200: GalaxySerializer},
        tags=["Galaxies"]
    )
    def put(self, request, pk):
        galaxy = get_object_or_404(Galaxy, id=pk)
        serializer = GalaxyCreateSerializer(galaxy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)


class GalaxyImageUploadView(APIView):
    permission_classes = [IsModerator]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_id="upload_galaxy_image",
        operation_description="Загрузка изображения для галактики по ID",
        manual_parameters=[
            openapi.Parameter(
                'image',
                openapi.IN_FORM,
                description='Файл изображения',
                type=openapi.TYPE_FILE,
                required=True
            )
        ],
        responses={200: openapi.Response(description="Успешная загрузка изображения")},
        tags=["Galaxies"]
    )
    def post(self, request, pk):
        image_file = request.FILES.get("image")
        if not image_file:
            return Response({"error": "Нужно передать 'image'."}, status=400)

        galaxy = get_object_or_404(Galaxy, id=pk)
        # предполагается, что handle_galaxy_image_upload возвращает Response
        return handle_galaxy_image_upload(galaxy, image_file)


class GalaxyDeleteView(APIView):
    permission_classes = [IsModerator]

    @swagger_auto_schema(
        operation_id="delete_galaxy",
        operation_description="Мягкое удаление галактики по ID (деактивация)",
        responses={200: openapi.Response(description="Галактика деактивирована")},
        tags=["Galaxies"]
    )
    def delete(self, request, pk):
        galaxy = get_object_or_404(Galaxy, id=pk, is_active=True)

        galaxy.is_active = False
        galaxy.save()

        if galaxy.image_name:
            try:
                delete_image_from_minio(galaxy.image_name)
            except Exception as e:
                return Response({"error": f"Ошибка при удалении изображения: {str(e)}"}, status=500)

        return Response({"success": f"Услуга '{galaxy.name}' успешно деактивирована."}, status=200)
    

class AddGalaxyToDraftView(APIView):
    """
    POST — Добавление услуги (галактики) в текущую черновую заявку пользователя.
    Если черновой заявки нет, создается новая.
    Доступен для обычного пользователя и модератора.
    """
    permission_classes = [IsUser | IsModerator]  # OR: пользователь или модератор

    @swagger_auto_schema(
        operation_id="add_galaxy_to_request",
        operation_description="Добавить услугу (галактику) в черновую заявку текущего пользователя. Если черновая заявка отсутствует, создается новая.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['galaxy_id'],
            properties={
                'galaxy_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID услуги (галактики)")
            }
        ),
        responses={
            200: openapi.Response(
                description="Услуга успешно добавлена",
                examples={"application/json": {"status": "услуга добавлена", "galaxy_id": 1, "request_id": 5}}
            ),
            400: "Не указан galaxy_id",
            404: "Галактика с таким ID не найдена"
        },
        tags=["Galaxies"]
    )
    def post(self, request):
        user = get_user(request)
        galaxy_id = request.data.get("galaxy_id")

        if not galaxy_id:
            return Response({"error": "Необходимо указать galaxy_id"}, status=400)

        galaxy = get_object_or_404(Galaxy, id=galaxy_id, is_active=True)

        # Получаем черновую заявку или создаем новую
        draft_request, created = GalaxyRequest.objects.get_or_create(
            creator=user,
            status=GalaxyRequest.Status.DRAFT
        )

        # Проверяем, что галактика еще не добавлена
        if GalaxiesInRequest.objects.filter(galaxy_request=draft_request, galaxy=galaxy).exists():
            return Response({"status": "услуга уже в черновой заявке", "galaxy_id": galaxy_id, "request_id": draft_request.id})

        # Добавляем галактику
        GalaxiesInRequest.objects.create(galaxy_request=draft_request, galaxy=galaxy)
        return Response({"status": "услуга добавлена", "galaxy_id": galaxy_id, "request_id": draft_request.id})


# ------------------- Galaxies In Request Views -------------------
class RemoveGalaxyFromDraftView(APIView):
    permission_classes = [IsAuthenticatedCustom]

    @swagger_auto_schema(
        operation_id="remove_galaxy_from_draft",
        operation_description="Удалить услугу (галактику) из текущей черновой заявки пользователя",
        manual_parameters=[
            openapi.Parameter(
                'galaxy_id', openapi.IN_QUERY, description="ID услуги (галактики) для удаления (или можно передать в теле запроса)", type=openapi.TYPE_INTEGER
            )
        ],
        responses={
            200: openapi.Response("Услуга успешно удалена", examples={"application/json": {"status": "услуга удалена", "galaxy_id": 1, "request_id": 5}}),
            400: "Не указан galaxy_id",
            404: "Нет активной черновой заявки или услуга не найдена"
        },
        tags=["GalaxyInRequest"]
    )
    def delete(self, request, galaxy_id=None):
        # allow galaxy_id via path param OR query/body
        galaxy_id = galaxy_id or request.query_params.get('galaxy_id') or request.data.get('galaxy_id')
        if not galaxy_id:
            return Response({'error': 'Не указан galaxy_id'}, status=400)

        try:
            galaxy_id = int(galaxy_id)
        except (TypeError, ValueError):
            return Response({'error': 'galaxy_id должен быть целым числом'}, status=400)

        user = get_user(request)
        draft_request = GalaxyRequest.objects.filter(creator=user, status=GalaxyRequest.Status.DRAFT).first()
        if not draft_request:
            return Response({'error': 'Нет активной черновой заявки'}, status=404)

        try:
            item = GalaxiesInRequest.objects.get(galaxy_request=draft_request, galaxy_id=galaxy_id)
        except GalaxiesInRequest.DoesNotExist:
            return Response({'error': 'Услуга не найдена в заявке'}, status=404)

        item.delete()
        return Response({'status': 'услуга удалена', 'galaxy_id': galaxy_id, 'request_id': draft_request.id})


class UpdateMagnitudeView(APIView):
    permission_classes = [IsAuthenticatedCustom]

    @swagger_auto_schema(
        operation_id="update_magnitude",
        operation_description="Обновить видимую звездную величину (magnitude) для услуги в черновой заявке",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['magnitude', 'galaxy_id'],
            properties={
                'magnitude': openapi.Schema(type=openapi.TYPE_NUMBER, description="Видимая звездная величина"),
                'galaxy_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID услуги")
            }
        ),
        responses={
            200: "Magnitude успешно обновлено",
            400: "Необходимо указать magnitude",
            404: "Нет активной черновой заявки или услуга не найдена"
        },
        tags=["GalaxyInRequest"]
    )
    def put(self, request, galaxy_id=None):
        # поддерживаем galaxy_id как path либо в теле/params
        galaxy_id = galaxy_id or request.data.get('galaxy_id') or request.query_params.get('galaxy_id')
        magnitude = request.data.get("magnitude")

        if magnitude is None:
            return Response({"error": "Необходимо указать magnitude."}, status=400)

        try:
            magnitude = float(magnitude)
        except (TypeError, ValueError):
            return Response({"error": "magnitude должен быть числом."}, status=400)

        if not galaxy_id:
            return Response({"error": "Не указан galaxy_id."}, status=400)

        try:
            galaxy_id = int(galaxy_id)
        except (TypeError, ValueError):
            return Response({"error": "galaxy_id должен быть целым числом"}, status=400)

        user = get_user(request)
        draft_request = GalaxyRequest.objects.filter(creator=user, status=GalaxyRequest.Status.DRAFT).first()
        if not draft_request:
            return Response({"error": "Нет активной черновой заявки."}, status=404)

        try:
            item = GalaxiesInRequest.objects.get(galaxy_request=draft_request, galaxy_id=galaxy_id)
        except GalaxiesInRequest.DoesNotExist:
            return Response({"error": "Услуга не найдена в заявке."}, status=404)

        item.magnitude = magnitude
        item.save(update_fields=["magnitude"])

        return Response({
            "message": "Видимая звездная величина обновлена успешно.",
            "galaxy_id": galaxy_id,
            "new_magnitude": magnitude
        }, status=200)


# ------------------- GalaxyRequest Views -------------------
class CartIconView(APIView):
    permission_classes = [IsUser]

    @swagger_auto_schema(
        operation_id="get_cart_icon",
        operation_description="Получить информацию о текущей черновой заявке пользователя (для отображения значка корзины).",
        responses={
            200: openapi.Response(
                description="Информация о черновой заявке",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'draft_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID черновой заявки'),
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Количество услуг в черновой заявке')
                    }
                )
            )
        },
        tags=["GalaxyRequests"]
    )
    def get(self, request):
        user = get_user(request)
        draft = GalaxyRequest.objects.filter(creator=user, status=GalaxyRequest.Status.DRAFT).first()
        count = draft.galaxies.count() if draft else 0
        return Response({'draft_id': draft.id if draft else None, 'count': count})


class GalaxyRequestListView(APIView):
    authentication_classes = [RedisSessionAuthentication]  # отключаем стандартную DRF аутентификацию
    permission_classes = [IsAuthenticatedCustom]

    @swagger_auto_schema(
        operation_description="Список заявок. Для обычного пользователя — только его заявки; для модератора — все заявки (кроме draft и deleted). Включает все галактики с magnitude и distance.",
        tags=["GalaxyRequests"]
    )
    def get(self, request):
        user = get_user(request)  # получаем пользователя через Redis
        if not user:
            return Response({"error": "User not authenticated"}, status=401)

        status_order = ["submitted", "completed", "rejected"]

        if user.is_staff or user.is_superuser:  # модератор
            queryset = GalaxyRequest.objects.exclude(status__in=["draft", "deleted"])
        else:  # обычный пользователь
            queryset = GalaxyRequest.objects.filter(creator=user).exclude(status__in=["draft", "deleted"])

        queryset = queryset.annotate(
            status_order=Case(
                *[When(status=s, then=Value(i)) for i, s in enumerate(status_order)],
                default=Value(len(status_order)),
                output_field=IntegerField(),
            )
        ).order_by("status_order", "submitted_at")

        # Формируем кастомный JSON
        data = []
        for req in queryset:
            galaxies_list = []
            for item in req.galaxies.all():
                galaxies_list.append({
                    "id": item.galaxy.id,
                    "name": item.galaxy.name,
                    "magnitude": item.magnitude,
                    "distance": item.distance
                })

            data.append({
                "id": req.id,
                "status": req.status,
                "creator": req.creator.username,
                "moderator": req.moderator.username if req.moderator else None,
                "telescope": req.telescope,
                "created_at": req.created_at,
                "submitted_at": req.submitted_at,
                "completed_at": req.completed_at,
                "galaxies": galaxies_list
            })

        return Response(data)


class GalaxyRequestDetailView(APIView):
    authentication_classes = [RedisSessionAuthentication]  # используем Redis-сессии
    permission_classes = [IsAuthenticatedCustom]

    @swagger_auto_schema(
        operation_description="Получить детали заявки. Пользователь видит только свои заявки (кроме draft и deleted). Модератор видит все заявки (кроме draft и deleted). Включает все галактики с magnitude и distance.",
        tags=["GalaxyRequests"]
    )
    def get(self, request, pk):
        user = get_user(request)
        if not user:
            return Response({"error": "User not authenticated"}, status=401)

        # Определяем фильтр по роли
        if user.is_staff or user.is_superuser:  # модератор
            galaxy_request = get_object_or_404(GalaxyRequest, pk=pk)
            if galaxy_request.status in ["draft", "deleted"]:
                return Response({"error": "Доступ к этой заявке запрещён"}, status=403)
        else:  # обычный пользователь
            galaxy_request = get_object_or_404(GalaxyRequest, pk=pk, creator=user)
            if galaxy_request.status in ["draft", "deleted"]:
                return Response({"error": "Доступ к этой заявке запрещён"}, status=403)

        # Формируем кастомный JSON
        galaxies_list = []
        for item in galaxy_request.galaxies.all():
            galaxies_list.append({
                "id": item.galaxy.id,
                "name": item.galaxy.name,
                "magnitude": item.magnitude,
                "distance": item.distance
            })

        data = {
            "id": galaxy_request.id,
            "status": galaxy_request.status,
            "creator": galaxy_request.creator.username,
            "moderator": galaxy_request.moderator.username if galaxy_request.moderator else None,
            "telescope": galaxy_request.telescope,
            "created_at": galaxy_request.created_at,
            "submitted_at": galaxy_request.submitted_at,
            "completed_at": galaxy_request.completed_at,
            "galaxies": galaxies_list
        }

        return Response(data)


class GalaxyRequestUpdateView(APIView):
    permission_classes = [IsUser]  

    @swagger_auto_schema(
        operation_description="Обновить поле telescope в текущей черновой заявке пользователя",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'telescope': openapi.Schema(type=openapi.TYPE_STRING)
            },
            required=['telescope']
        ),
        tags=["GalaxyRequests"]
    )
    def put(self, request):
        user = get_user(request)
        # Ищем черновую заявку текущего пользователя
        draft = GalaxyRequest.objects.filter(creator=user, status=GalaxyRequest.Status.DRAFT).first()
        if not draft:
            return Response({"error": "У пользователя нет активной черновой заявки"}, status=404)

        new_telescope = request.data.get('telescope')
        if not new_telescope:
            return Response({"error": "Поле telescope обязательно"}, status=400)

        draft.telescope = new_telescope
        draft.save(update_fields=['telescope'])
        return Response({"status": "telescope updated", "id": draft.id})


class GalaxyRequestFormView(APIView):
    permission_classes = [IsUser]

    @swagger_auto_schema(
        operation_description="Сформировать черновую заявку текущего пользователя. Проверка обязательных полей: telescope и magnitude для всех услуг.",
        tags=["GalaxyRequests"]
    )
    def put(self, request):
        user = get_user(request)
        draft = GalaxyRequest.objects.filter(creator=user, status=GalaxyRequest.Status.DRAFT).first()

        if not draft:
            return Response({"error": "У вас нет активной черновой заявки."}, status=404)

        if not draft.telescope:
            return Response({"error": "Поле telescope обязательно для формирования заявки."}, status=400)

        # Формируем список услуг с отсутствующим magnitude
        missing_magnitude = [
            f"{item.galaxy.name}({item.galaxy.id})" for item in draft.galaxies.all() if item.magnitude is None
        ]
        if missing_magnitude:
            return Response(
                {"error": f"Отсутствует magnitude у услуг: {', '.join(missing_magnitude)}"},
                status=400
            )

        # Формируем заявку
        draft.status = GalaxyRequest.Status.SUBMITTED
        draft.submitted_at = timezone.now()
        draft.save(update_fields=["status", "submitted_at"])
        return Response({"status": "formed", "id": draft.id})

        draft.status = GalaxyRequest.Status.SUBMITTED
        draft.submitted_at = timezone.now()
        draft.save(update_fields=["status", "submitted_at"])
        return Response({"status": "formed", "id": draft.id})

class GalaxyRequestCompleteView(APIView):
    permission_classes = [IsModerator]

    @swagger_auto_schema(operation_description="Завершить или отклонить заявку модератором. Доступно только для заявок со статусом 'submitted'.", request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'action': openapi.Schema(type=openapi.TYPE_STRING, enum=['complete', 'rejected'])
        },
        required=['action']
    ), tags=["GalaxyRequests"])
    def put(self, request, pk):
        galaxy_request = get_object_or_404(GalaxyRequest, pk=pk, status=GalaxyRequest.Status.SUBMITTED)
        action = request.data.get('action')
        if action not in ['complete', 'rejected']:
            return Response({"error": "Invalid action"}, status=400)

        galaxy_request.status = GalaxyRequest.Status.COMPLETED if action == 'complete' else GalaxyRequest.Status.REJECTED
        galaxy_request.moderator = get_user(request)
        galaxy_request.completed_at = timezone.now()
        galaxy_request.save(update_fields=['status', 'moderator', 'completed_at'])

        if galaxy_request.status == GalaxyRequest.Status.COMPLETED:
            # Расчет расстояния (Мпк)
            M = -19.3
            for item in galaxy_request.galaxies.all():
                if item.magnitude is not None:
                    # distance in Mpc
                    item.distance = 10 ** ((item.magnitude - M + 5) / 5) / 1_000_000
                    item.save(update_fields=['distance'])

        return Response({"id": galaxy_request.id, "status": galaxy_request.status, "result": "success"})


class GalaxyRequestDeleteView(APIView):
    permission_classes = [IsUser]

    @swagger_auto_schema(
        operation_description="Мягкое удаление черновой заявки текущего пользователя",
        tags=["GalaxyRequests"]
    )
    def delete(self, request):
        user = get_user(request)
        draft = GalaxyRequest.objects.filter(creator=user, status=GalaxyRequest.Status.DRAFT).first()

        if not draft:
            return Response({"error": "У вас нет активной черновой заявки."}, status=404)

        draft.status = GalaxyRequest.Status.DELETED
        draft.submitted_at = timezone.now()
        draft.save(update_fields=['status', 'submitted_at'])

        return Response({"id": draft.id, "status": "deleted"})

# ------------------- User Views -------------------
class UserRegisterView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [IsGuest]

    @swagger_auto_schema(
        operation_id="user_register",
        operation_description="Регистрация нового пользователя. Доступно только для гостей (неавторизованных).",
        request_body=UserRegisterSerializer,
        responses={
            201: openapi.Response(description="Пользователь успешно зарегистрирован", schema=UserRegisterSerializer),
            400: openapi.Response(description="Ошибка валидации данных")
        },
        tags=["Users"]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class UserLoginView(APIView):
    permission_classes = [IsGuest]

    @swagger_auto_schema(operation_description="Вход пользователя (создание сессии). Альтернатива /users/login/", request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'username': openapi.Schema(type=openapi.TYPE_STRING),
            'password': openapi.Schema(type=openapi.TYPE_STRING)
        },
        required=['username', 'password']
    ), tags=["Users"])
    def post(self, request):
        # Reuse login_view logic but inside class-based view
        username = request.data.get("username")
        password = request.data.get("password")
        if not username or not password:
            return Response({"error": "username and password required"}, status=400)

        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"error": "invalid_credentials"}, status=400)

        try:
            session_id = create_session_for_user(user)
        except Exception as e:
            return Response({"error": f"session error: {str(e)}"}, status=500)

        csrf = get_token(request)
        response = Response({"status": "logged_in", "csrftoken": csrf})
        secure = not settings.DEBUG
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=secure,
            samesite='Lax',
            path='/'
        )
        return response


class UserLogoutView(APIView):
    permission_classes = [IsAuthenticatedCustom]

    @swagger_auto_schema(operation_description="Выход пользователя (удаление сессии)", tags=["Users"])
    def post(self, request):
        session_id = request.COOKIES.get("session_id")
        delete_session(session_id)
        resp = Response({"status": "logged_out"})
        resp.delete_cookie('session_id', path='/')
        return resp


class UserProfileView(APIView):
    permission_classes = [IsAuthenticatedCustom]

    @swagger_auto_schema(operation_description="Получить профиль текущего пользователя", tags=["Users"])
    def get(self, request):
        user = get_user(request)
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)

    @swagger_auto_schema(operation_description="Изменить профиль текущего пользователя", request_body=UserProfileSerializer, tags=["Users"])
    def put(self, request):
        user = get_user(request)
        serializer = UserProfileSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
