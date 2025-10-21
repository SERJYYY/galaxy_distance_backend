from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Galaxy, GalaxyRequest, GalaxiesInRequest
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.db import connection




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