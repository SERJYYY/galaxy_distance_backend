from rest_framework import generics, status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser
from .minio_utils import handle_galaxy_image_upload, delete_image_from_minio
from rest_framework.permissions import IsAuthenticated
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Galaxy, GalaxyRequest, GalaxiesInRequest
from .serializers import (
    GalaxySerializer, GalaxyCreateSerializer,
    GalaxyRequestSerializer, GalaxyRequestCreateSerializer,
    UserRegisterSerializer, UserSerializer, GalaxyRequestDetailSerializer, UserProfileSerializer
)


User = get_user_model()

# -----------------------
# GALAXY VIEWS
# -----------------------
class GalaxyListView(generics.ListAPIView):
    queryset = Galaxy.objects.all()
    serializer_class = GalaxySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

class GalaxyDetailView(generics.RetrieveAPIView):
    queryset = Galaxy.objects.all()
    serializer_class = GalaxySerializer
    permission_classes = [permissions.AllowAny]


class GalaxyCreateView(generics.CreateAPIView):
    queryset = Galaxy.objects.all()
    serializer_class = GalaxyCreateSerializer
    permission_classes = [permissions.IsAdminUser]


class AddGalaxyToDraftView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        galaxy_id = request.data.get('galaxy_id')
        galaxy = get_object_or_404(Galaxy, id=galaxy_id)

        # Проверяем, есть ли черновик у текущего пользователя
        draft_request = GalaxyRequest.objects.filter(
            creator=request.user,
            status=GalaxyRequest.Status.DRAFT
        ).first()

        # Если нет — создаём новую заявку
        if not draft_request:
            draft_request = GalaxyRequest.objects.create(
                creator=request.user,
                status=GalaxyRequest.Status.DRAFT,
                telescope=None
            )

        # Проверяем, не добавлена ли уже эта услуга в черновик
        if GalaxiesInRequest.objects.filter(
            galaxy_request=draft_request,
            galaxy=galaxy
        ).exists():
            return Response(
                {"detail": "Эта услуга уже есть в черновой заявке."},
                status=400
            )

        # Добавляем услугу в заявку
        GalaxiesInRequest.objects.create(
            galaxy_request=draft_request,
            galaxy=galaxy
        )

        return Response(
            {"status": "added", "draft_id": draft_request.id},
            status=201
        )
    


class GalaxyUpdateView(generics.GenericAPIView):
    queryset = Galaxy.objects.all()
    serializer_class = GalaxyCreateSerializer
    permission_classes = [permissions.IsAdminUser]

    def put(self, request):
        galaxy_id = request.data.get('id')  # Берём id из тела запроса
        galaxy = get_object_or_404(Galaxy, id=galaxy_id)
        serializer = self.get_serializer(galaxy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class GalaxyImageUploadView(APIView):
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        galaxy_id = request.data.get("id")
        image_file = request.FILES.get("image")

        if not galaxy_id or not image_file:
            return Response({"error": "Нужно передать 'id' и 'image'."}, status=400)

        galaxy = get_object_or_404(Galaxy, id=galaxy_id)
        return handle_galaxy_image_upload(galaxy, image_file)
    

class GalaxyDeleteView(APIView):
    """Мягкое удаление услуги (галактики)."""

    def delete(self, request):
        galaxy_id = request.data.get("id")
        if not galaxy_id:
            return Response({"error": "Не указан ID услуги"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            galaxy = Galaxy.objects.get(id=galaxy_id, is_active=True)
        except Galaxy.DoesNotExist:
            return Response({"error": "Услуга не найдена или уже удалена"}, status=status.HTTP_404_NOT_FOUND)

        # Мягкое удаление: деактивируем
        galaxy.is_active = False
        galaxy.save()

        # Удаляем изображение из MinIO (если есть)
        if galaxy.image_name:
            try:
                delete_image_from_minio(galaxy.image_name)
            except Exception as e:
                return Response({"error": f"Ошибка при удалении изображения: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"success": f"Услуга '{galaxy.name}' успешно деактивирована."}, status=status.HTTP_200_OK)

# -----------------------
# GALAXY REQUEST VIEWS
# -----------------------
class CartIconView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        draft = GalaxyRequest.objects.filter(creator=request.user, status='draft').first()
        if draft:
            count = draft.galaxies.count()
            return Response({'draft_id': draft.id, 'count': count})
        return Response({'draft_id': None, 'count': 0})


class GalaxyRequestListView(generics.ListAPIView):
    serializer_class = GalaxyRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Исключаем удаленные и черновики
        queryset = GalaxyRequest.objects.exclude(status__in=['deleted', 'draft'])

        # Фильтрация по диапазону дат формирования
        created_at = self.request.query_params.get('created_at')  # начало диапазона
        submitted_at = self.request.query_params.get('submitted_at')  # конец диапазона

        if created_at:
            dt_from = parse_datetime(created_at)
            if dt_from:
                queryset = queryset.filter(created_at__gte=dt_from)
        if submitted_at:
            dt_to = parse_datetime(submitted_at)
            if dt_to:
                queryset = queryset.filter(submitted_at__lte=dt_to)

        # Оставляем обычную сортировку по id (по умолчанию)
        return queryset
    

class GalaxyRequestDetailView(generics.RetrieveAPIView):
    queryset = GalaxyRequest.objects.all()
    serializer_class = GalaxyRequestDetailSerializer
    permission_classes = [IsAuthenticated]


class GalaxyRequestUpdateView(APIView):
    def put(self, request):
        request_id = request.data.get('id')
        new_telescope = request.data.get('telescope')
        
        if not request_id or new_telescope is None:
            return Response({'error': 'id and telescope are required'}, status=400)

        galaxy_request = get_object_or_404(GalaxyRequest, id=request_id)
        galaxy_request.telescope = new_telescope
        galaxy_request.save(update_fields=['telescope'])
        
        return Response({'status': 'telescope updated'})


class GalaxyRequestFormView(APIView):
    """
    Формирует черновую заявку текущего пользователя.
    Проверка обязательных полей: telescope и magnitude для всех услуг.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request):
        # Получаем черновую заявку текущего пользователя
        draft = GalaxyRequest.objects.filter(creator=request.user, status=GalaxyRequest.Status.DRAFT).first()
        if not draft:
            return Response({"error": "У вас нет черновой заявки для формирования."}, status=404)

        # Проверка обязательного поля telescope
        if not draft.telescope:
            return Response({"error": "Поле telescope обязательно для формирования заявки."}, status=400)

        # Проверка обязательного поля magnitude для каждой услуги
        missing_magnitude = []
        for item in draft.galaxies.all():  # related_name="galaxies"
            if item.magnitude is None:
                missing_magnitude.append(item.galaxy.name)
        if missing_magnitude:
            return Response(
                {"error": f"Отсутствует видимая звездная величина (magnitude) у услуг: {', '.join(missing_magnitude)}"},
                status=400
            )

        # Формирование заявки
        draft.status = GalaxyRequest.Status.SUBMITTED
        draft.submitted_at = timezone.now()
        draft.save(update_fields=["status", "submitted_at"])

        return Response({"status": "formed", "draft_id": draft.id})


class GalaxyRequestCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        if not request.user.is_staff:
            return Response({'error': 'Only staff can complete/reject'}, status=403)

        request_id = request.data.get('id')
        status_action = request.data.get('action')

        if status_action not in ['complete', 'rejected']:
            return Response({'error': 'Invalid action'}, status=400)

        galaxy_request = get_object_or_404(GalaxyRequest, id=request_id, status=GalaxyRequest.Status.SUBMITTED)

        # Назначаем модератора и дату завершения
        galaxy_request.moderator = request.user
        galaxy_request.completed_at = timezone.now()
        galaxy_request.status = GalaxyRequest.Status.COMPLETED if status_action == 'complete' else GalaxyRequest.Status.REJECTED
        galaxy_request.save(update_fields=['moderator', 'completed_at', 'status'])

        # Расчет расстояния для каждой услуги
        M = -19.3
        for item in galaxy_request.galaxies.all():
            if item.magnitude is not None:
                item.distance = 10 ** ((item.magnitude - M + 5) / 5) / 1000000
                item.save(update_fields=['distance'])

        return Response({
            'id': galaxy_request.id,
            'status': galaxy_request.status,
            'result': 'success'
        })


class GalaxyRequestDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        # Ищем текущую черновую заявку пользователя
        draft_request = GalaxyRequest.objects.filter(
            creator=request.user,
            status=GalaxyRequest.Status.DRAFT
        ).first()

        if not draft_request:
            return Response({'error': 'Нет активной черновой заявки'}, status=404)

        # Soft delete: меняем статус и проставляем дату формирования
        draft_request.status = GalaxyRequest.Status.DELETED
        draft_request.submitted_at = timezone.now()
        draft_request.save(update_fields=['status', 'submitted_at'])

        return Response({
            'id': draft_request.id,
            'status': 'deleted'
        }, status=200)


# -----------------------
# GALAXIS IN REQUEST VIEWS
# -----------------------
class RemoveGalaxyFromDraftView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        # Получаем id услуги из тела запроса
        galaxy_id = request.data.get('galaxy_id')
        if not galaxy_id:
            return Response({'error': 'Не указан galaxy_id'}, status=400)

        # Находим черновую заявку текущего пользователя
        draft_request = GalaxyRequest.objects.filter(
            creator=request.user, status=GalaxyRequest.Status.DRAFT
        ).first()

        if not draft_request:
            return Response({'error': 'Нет активной черновой заявки'}, status=404)

        # Находим связь заявка-услуга
        try:
            item = GalaxiesInRequest.objects.get(galaxy_request=draft_request, galaxy_id=galaxy_id)
        except GalaxiesInRequest.DoesNotExist:
            return Response({'error': 'Услуга не найдена в заявке'}, status=404)

        # Удаляем запись
        item.delete()
        return Response({'status': 'услуга удалена', 'galaxy_id': galaxy_id, 'request_id': draft_request.id})
    

class UpdateMagnitudeView(APIView):
    """PUT — изменение magnitude в текущей черновой заявке."""

    def put(self, request):
        user = request.user
        galaxy_id = request.data.get("galaxy_id")
        magnitude = request.data.get("magnitude")

        # Проверка входных данных
        if not galaxy_id or magnitude is None:
            return Response({"error": "Необходимо указать galaxy_id и magnitude."}, status=400)

        # Проверяем, есть ли у пользователя черновая заявка
        try:
            draft_request = GalaxyRequest.objects.get(
                creator=user,
                status=GalaxyRequest.Status.DRAFT
            )
        except GalaxyRequest.DoesNotExist:
            return Response({"error": "Нет активной черновой заявки."}, status=404)

        # Проверяем, что услуга есть в этой заявке
        try:
            item = GalaxiesInRequest.objects.get(
                galaxy_request=draft_request,
                galaxy_id=galaxy_id
            )
        except GalaxiesInRequest.DoesNotExist:
            return Response({"error": "Услуга не найдена в заявке."}, status=404)

        # Обновляем magnitude
        item.magnitude = magnitude
        item.save(update_fields=["magnitude"])

        return Response({
            "message": "Видимая звездная величина обновлена успешно.",
            "galaxy_id": galaxy_id,
            "new_magnitude": magnitude
        }, status=200)


# -----------------------
# USER VIEWS
# -----------------------
class UserRegisterView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]


# class UserProfileView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         data = {
#             "id": user.id,
#             "username": user.username,
#             "email": user.email,
#             "first_name": user.first_name,
#             "last_name": user.last_name,
#             "is_staff": user.is_staff,  # True — если админ
#             "is_superuser": user.is_superuser,
#         }
#         return Response(data)


class UserLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user:
            login(request, user)
            return Response({'status': 'logged_in'})
        return Response({'error': 'invalid_credentials'}, status=400)


class UserLogoutView(APIView):
    """POST — деавторизация (logout)"""

    def post(self, request):
        logout(request)
        return Response({"message": "Пользователь успешно деавторизован."}, status=status.HTTP_200_OK)
    

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Возвращает данные текущего пользователя"""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        """Обновляет данные текущего пользователя"""
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
