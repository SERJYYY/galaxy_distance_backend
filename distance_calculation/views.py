from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Galaxy, GalaxyRequest, GalaxiesInRequest
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.db import connection



# galaxies = [
#     {
#         "id": 1,
#         "name": "M101",
#         "magnitude": 7.86,
#         "distance": 6.4,
#         "image_url": "http://127.0.0.1:9000/test/m101_vertushka.jpg",
#         "description": "M101 — это спиральная галактика в созвездии Большой Медведицы, известная своими яркими спиральными рукавами."
#     },
#     {
#         "id": 2,
#         "name": "NGC 3982",
#         "magnitude": 12.0,
#         "distance": 17.0,
#         "image_url": "http://127.0.0.1:9000/test/NGC_3982.jpg",
#         "description": "NGC 3982 — спиральная галактика с активными областями звездообразования в созвездии Большой Медведицы."
#     },
#     {
#         "id": 3,
#         "name": "NGC 4424",
#         "magnitude": 11.1,
#         "distance": 16.0,
#         "image_url": "http://127.0.0.1:9000/test/NGC_4424.jpg",
#         "description": "NGC 4424 — спиральная галактика с нарушенной структурой спиральных рукавов, находящаяся в созвездии Девы."
#     },
#     {
#         "id": 4,
#         "name": "NGC 4526",
#         "magnitude": 10.2,
#         "distance": 16.4,
#         "image_url": "http://127.0.0.1:9000/test/NGC_4526.jpg",
#         "description": "NGC 4526 — линзообразная галактика с заметной пылевой полосой, расположена в созвездии Девы."
#     },
#     {
#         "id": 5,
#         "name": "UGC 9391",
#         "magnitude": 13.5,
#         "distance": 20.1,
#         "image_url": "http://127.0.0.1:9000/test/UGC_9391.jpg",
#         "description": "UGC 9391 — спиральная галактика малой яркости, изучаемая для определения расстояния по сверхновым типа Ia."
#     }
# ]

# galaxy_requests = [
#     {
#         "id": 1,
#         "galaxy_ids": [1, 3],
#         "telescope": "Хаббл",
#         "date": "15.09.2025"
#     },
#     {
#         "id": 2,
#         "galaxy_ids": [2, 4, 5],
#         "telescope": "Джеймс Уэбб",
#         "date": "20.09.2025"
#     },
#     {
#         "id": 3,
#         "galaxy_ids": [1, 2, 3, 4, 5],
#         "telescope": "Очень Большой Телескоп",
#         "date": "01.10.2025"
#     }
# ]



# ==============================
# [GET] Список галактик (услуг)
# ==============================
def galaxies_list(request):
    search_query = request.GET.get("search", "")  # получаем поисковый запрос
    
    galaxies = Galaxy.objects.filter(is_active=True)  # активные галактики
    
    if search_query:  # если есть запрос
        galaxies = galaxies.filter(name__icontains=search_query)

    # берём суперпользователя admin
    user = User.objects.get(username="admin")

    # ищем активную заявку со статусом "draft"
    current_request = GalaxyRequest.objects.filter(creator=user, status="draft").first()
    count = current_request.galaxies.count() if current_request else 0

    return render(request, "distance_calculation/galaxies.html", {
        "galaxies": galaxies,
        "count": count,
        "current_request": current_request,
        "search_query": search_query,  # чтобы в input подставлялось значение
    })

# ==============================
# [GET] Подробности галактики
# ==============================
def galaxy_detail(request, galaxy_id):
    galaxy = Galaxy.objects.get(id=galaxy_id)
    return render(request, "distance_calculation/galaxy_detail.html", {"galaxy": galaxy})


# ==============================
# [POST] Добавление галактики в заявку
# ==============================
def add_galaxy(request, galaxy_id):
    user = User.objects.get(username="admin")
    galaxy = Galaxy.objects.get(id=galaxy_id)

    # ищем черновик, если нет — создаём новый
    galaxy_request = GalaxyRequest.objects.filter(creator=user, status="draft").first()
    if not galaxy_request:
        galaxy_request = GalaxyRequest.objects.create(
            creator=user,
            status="draft",
            created_at=timezone.now(),
            telescope="Не указан"
        )

    # добавляем галактику в заявку
    GalaxiesInRequest.objects.create(
        galaxy_request=galaxy_request,
        galaxy=galaxy
    )

    return redirect("galaxies_list")


# ==============================
# [GET] Просмотр заявки
# ==============================
def galaxy_request(request, request_id):
    user = User.objects.get(username="admin")

    # получаем заявку пользователя
    galaxy_request = GalaxyRequest.objects.filter(id=request_id, creator=user).first()

    # если заявка не найдена или удалена — редирект на страницу услуг
    if not galaxy_request or galaxy_request.status == "deleted":
        return redirect("galaxies_list")

    galaxies_in_request = galaxy_request.galaxies.all()

    return render(request, "distance_calculation/galaxy_request.html", {
        "galaxy_request": galaxy_request,
        "galaxies_in_request": galaxies_in_request,
    })


# ==============================
# [POST] Удаление заявки
# ==============================
def delete_galaxy_request(request, request_id):
    user = User.objects.get(username="admin")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE galaxy_requests
            SET status = %s
            WHERE id = %s AND creator_id = %s
            """,
            ["deleted", request_id, user.id]
        )

    return redirect("galaxies_list")