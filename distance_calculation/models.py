from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings


class Galaxy(models.Model):
    """Таблица галактик (услуг)."""
    name = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    image_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Имя файла в MinIO")
    is_active = models.BooleanField(default=True, verbose_name="Активна ли услуга")

    class Meta:
        db_table = "galaxies"
        verbose_name = "Галактика"
        verbose_name_plural = "Галактики"

    def __str__(self):
        return self.name


class GalaxyRequest(models.Model):
    """Таблица заявок."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        DELETED = "deleted", "Удалена"
        SUBMITTED = "submitted", "Сформирована"
        COMPLETED = "completed", "Завершена"
        REJECTED = "rejected", "Отклонена"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Статус"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата формирования")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершения")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_requests",
        verbose_name="Создатель"
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="moderated_requests",
        null=True,
        blank=True,
        verbose_name="Модератор"
    )

    telescope = models.CharField(max_length=255, verbose_name="Телескоп", null=True, blank=True)

    class Meta:
        db_table = "galaxy_requests"
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"

    def __str__(self):
        return f"Заявка #{self.id} ({self.get_status_display()})"


class GalaxiesInRequest(models.Model):
    """Таблица м-м: галактики в заявке."""
    galaxy_request = models.ForeignKey(GalaxyRequest, on_delete=models.PROTECT, related_name="galaxies")
    galaxy = models.ForeignKey(Galaxy, on_delete=models.PROTECT)
    magnitude = models.FloatField(verbose_name="Видимая звездная величина", blank=True, null=True)
    distance = models.FloatField(verbose_name="Расстояние (Мпк)", blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "galaxies_in_request"
        verbose_name = "Галактика в заявке"
        verbose_name_plural = "Галактики в заявке"

    def __str__(self):
        return f"{self.galaxy.name} в заявке #{self.galaxy_request.id}"



# Менеджер для кастомного пользователя
class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        """
        Создание обычного пользователя с username
        """
        if not username:
            raise ValueError('The Username must be set')
        
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        """
        Создание суперпользователя
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, password, **extra_fields)


# Кастомная модель пользователя
class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True, verbose_name="Имя пользователя")
    first_name = models.CharField(max_length=30, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=30, blank=True, verbose_name="Фамилия")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    is_staff = models.BooleanField(default=False, verbose_name="Менеджер (staff)")
    is_superuser = models.BooleanField(default=False, verbose_name="Администратор (superuser)")
    is_active = models.BooleanField(default=True, verbose_name="Активный пользователь")
    is_active = models.BooleanField(default=True, verbose_name="Активный пользователь")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    # важно — уникальные related_name
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='distance_calculation_users',  
        blank=True,
        help_text='Группы, к которым принадлежит пользователь.',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='distance_calculation_users_permissions',
        blank=True,
        help_text='Права пользователя.',
    )

    USERNAME_FIELD = 'username'  # основной идентификатор
    REQUIRED_FIELDS = []  # для создания суперпользователя через createsuperuser

    objects = CustomUserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username
