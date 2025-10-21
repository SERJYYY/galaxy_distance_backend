from django.conf import settings
from minio import Minio
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework.response import Response


def get_minio_client():
    """Создаёт клиент MinIO с настройками из settings.py"""
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,          # например, "minio:9000"
        access_key=settings.MINIO_ACCESS_KEY,      # например, "minio"
        secret_key=settings.MINIO_SECRET_KEY,      # например, "minio123"
        secure=False
    )


def upload_image_to_minio(file: InMemoryUploadedFile, bucket: str, object_name: str):
    """Загружает файл в MinIO и возвращает публичный URL"""
    client = get_minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=file,
        length=file.size,
    )

    # Формируем URL по шаблону http://localhost:9000/{bucket}/{object_id}
    return f"http://localhost:9000/{bucket}/{object_name}"


def delete_image_from_minio(object_name: str):
    """Безопасно удаляет файл из MinIO"""
    client = get_minio_client()
    try:
        client.remove_object(settings.MINIO_BUCKET, object_name)
    except Exception:
        pass  # если файла нет — игнорируем


def handle_galaxy_image_upload(galaxy, image_file):
    """
    Полный цикл: удалить старое изображение → загрузить новое → сохранить имя.
    Имя файла = id галактики (например, '1.png').
    """
    BUCKET = settings.MINIO_BUCKET  # например, "images"

    # Удаляем старое изображение, если есть
    if galaxy.image_name:
        delete_image_from_minio(galaxy.image_name)

    # Формируем имя нового объекта: "{id}.png"
    object_name = f"{galaxy.id}.png"

    try:
        url = upload_image_to_minio(image_file, BUCKET, object_name)
    except Exception as e:
        return Response({"error": f"Ошибка загрузки: {str(e)}"}, status=500)

    # Сохраняем имя файла в БД
    galaxy.image_name = object_name
    galaxy.save(update_fields=['image_name'])

    return Response({"image_url": url}, status=201)
