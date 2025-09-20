from django.shortcuts import render

galaxies = [
    {
        "id": 1,
        "name": "M101",
        "magnitude": 7.86,
        "distance": 6.4,
        "image_url": "http://127.0.0.1:9000/test/m101_vertushka.jpg",
        "description": "M101 — это спиральная галактика в созвездии Большой Медведицы, известная своими яркими спиральными рукавами."
    },
    {
        "id": 2,
        "name": "NGC 3982",
        "magnitude": 12.0,
        "distance": 17.0,
        "image_url": "http://127.0.0.1:9000/test/NGC_3982.jpg",
        "description": "NGC 3982 — спиральная галактика с активными областями звездообразования в созвездии Большой Медведицы."
    },
    {
        "id": 3,
        "name": "NGC 4424",
        "magnitude": 11.1,
        "distance": 16.0,
        "image_url": "http://127.0.0.1:9000/test/NGC_4424.jpg",
        "description": "NGC 4424 — спиральная галактика с нарушенной структурой спиральных рукавов, находящаяся в созвездии Девы."
    },
    {
        "id": 4,
        "name": "NGC 4526",
        "magnitude": 10.2,
        "distance": 16.4,
        "image_url": "http://127.0.0.1:9000/test/NGC_4526.jpg",
        "description": "NGC 4526 — линзообразная галактика с заметной пылевой полосой, расположена в созвездии Девы."
    },
    {
        "id": 5,
        "name": "UGC 9391",
        "magnitude": 13.5,
        "distance": 20.1,
        "image_url": "http://127.0.0.1:9000/test/UGC_9391.jpg",
        "description": "UGC 9391 — спиральная галактика малой яркости, изучаемая для определения расстояния по сверхновым типа Ia."
    }
]

galaxy_requests = [
    {
        "id": 1,
        "galaxy_ids": [1, 3],
        "telescope": "Хаббл",
        "date": "15.09.2025"
    },
    {
        "id": 2,
        "galaxy_ids": [2, 4, 5],
        "telescope": "Джеймс Уэбб",
        "date": "20.09.2025"
    },
    {
        "id": 3,
        "galaxy_ids": [1, 2, 3, 4, 5],
        "telescope": "Очень Большой Телескоп",
        "date": "01.10.2025"
    }
]

def galaxies_list(request):
    query = request.GET.get('q', '').strip()
    filtered_galaxies = galaxies

    if query:
        filtered_galaxies = [
            galaxy for galaxy in galaxies
            if query.lower() in galaxy["name"].lower()
        ]

    first_request = next((r for r in galaxy_requests if r["id"] == 3), None)
    count = len([g for g in galaxies if g["id"] in first_request["galaxy_ids"]]) if first_request else 0

    return render(request, "distance_calculation/galaxies.html", {
        "galaxies": filtered_galaxies,
        "search_query": query,
        "count": count 
    })

def galaxy_detail(request, galaxy_id):
    galaxy = next((g for g in galaxies if g["id"] == galaxy_id), None)
    return render(request, "distance_calculation/galaxy_detail.html", {
        "galaxy": galaxy,
        "not_found": galaxy is None
    })

def galaxy_request(request, request_id):
    req = next((r for r in galaxy_requests if r["id"] == request_id), None)
    if req is None:
        return render(request, "distance_calculation/404.html", {"message": "Заявка не найдена"})
    else:
        selected_galaxies = [g for g in galaxies if g["id"] in req["galaxy_ids"]]
        count = len(selected_galaxies)  # Считаем количество галактик

        return render(request, "distance_calculation/galaxy_request.html", {
            "request_id": request_id,
            "galaxies": selected_galaxies,
            "telescope_name": req["telescope"],
            "date": req["date"],
            "count": count  # Передаём количество
        })