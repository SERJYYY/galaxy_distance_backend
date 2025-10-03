from django.db import models
from django.contrib.auth.models import User


class Galaxy(models.Model):
    """Таблица галактик (услуг)."""
    name = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    image_url = models.URLField(null=True, blank=True, verbose_name="URL изображения")
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
        User,
        on_delete=models.PROTECT,
        related_name="created_requests",
        verbose_name="Создатель"
    )
    moderator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="moderated_requests",
        null=True,
        blank=True,
        verbose_name="Модератор"
    )

    telescope = models.CharField(max_length=255, verbose_name="Телескоп")

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
