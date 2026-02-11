from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Galaxy, GalaxyRequest, GalaxiesInRequest, CustomUser
from .minio_utils import settings
from django.conf import settings

User = get_user_model()


# -----------------------
# GALAXY SERIALIZERS
# -----------------------
class GalaxySerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Galaxy
        fields = ['id', 'name', 'description', 'image_name', 'is_active', 'image_url']

    def get_image_url(self, obj):
        if not obj.image_name:
            return None
        # Формируем URL по тому же шаблону, что в minio_utils.upload_image_to_minio
        return f"http://localhost:9000/{settings.MINIO_BUCKET}/{obj.image_name}"


class GalaxyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Galaxy
        fields = ['name', 'description', 'image_name']


# -----------------------
# GALAXY REQUEST SERIALIZERS
# -----------------------
class GalaxyRequestItemSerializer(serializers.ModelSerializer):
    galaxy = GalaxySerializer(read_only=True)

    class Meta:
        model = GalaxiesInRequest
        fields = ['id', 'galaxy']


class GalaxyRequestSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField(read_only=True)
    moderator = serializers.StringRelatedField(read_only=True)
    created_at = serializers.DateTimeField(format="%d.%m.%Y %H:%M", read_only=True)
    submitted_at = serializers.DateTimeField(format="%d.%m.%Y %H:%M", read_only=True)
    completed_at = serializers.DateTimeField(format="%d.%m.%Y %H:%M", read_only=True)

    class Meta:
        model = GalaxyRequest
        fields = [
            "id",
            "status",
            "creator",
            "moderator",
            "telescope",
            "created_at",
            "submitted_at",
            "completed_at",
        ]

class GalaxyRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GalaxyRequest
        fields = ['status']


class GalaxyInRequestSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='galaxy.name', read_only=True)
    image_name = serializers.CharField(source='galaxy.image_name', read_only=True)

    class Meta:
        model = GalaxiesInRequest
        fields = ['name', 'image_name']


class GalaxyRequestDetailSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField(read_only=True)
    moderator = serializers.StringRelatedField(read_only=True)
    items = GalaxyInRequestSerializer(source='galaxies', many=True, read_only=True)

    class Meta:
        model = GalaxyRequest
        fields = [
            'id', 'status', 'creator', 'moderator', 'telescope',
            'created_at', 'submitted_at', 'completed_at', 'items'
        ]


class GalaxyRequestListSerializer(serializers.ModelSerializer):
    creator = serializers.StringRelatedField(read_only=True)
    moderator = serializers.StringRelatedField(read_only=True)
    created_at = serializers.DateTimeField(format="%d.%m.%Y %H:%M", read_only=True)
    submitted_at = serializers.DateTimeField(format="%d.%m.%Y %H:%M", read_only=True)
    completed_at = serializers.DateTimeField(format="%d.%m.%Y %H:%M", read_only=True)
    calculated_galaxy_count = serializers.SerializerMethodField()

    class Meta:
        model = GalaxyRequest
        fields = [
            "id",
            "status",
            "creator",
            "moderator",
            "telescope",
            "created_at",
            "submitted_at",
            "completed_at",
            "calculated_galaxy_count",
        ]

    def get_calculated_galaxy_count(self, obj):
        # Считаем только услуги с заполненным distance
        return obj.galaxies.filter(distance__isnull=False).count()



# -----------------------
# USER SERIALIZERS
# -----------------------
class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email"),
            password=validated_data["password"]
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
        read_only_fields = ["id", "username"]

