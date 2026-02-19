# backend/api/utils/viewed_galaxies.py
from django_redis import get_redis_connection
import time

redis = get_redis_connection("default")
MAX_VIEWED = 10  # Максимум 10 просмотренных в истории
RECENT_COUNT = 4  # Показывать 3 недавно просмотренных

def add_viewed_galaxy(guest_session_id: str, galaxy_id: int):
    """
    Добавляет галактику в список просмотренных для гостевой сессии.
    Хранит в Redis как sorted set (timestamp -> galaxy_id).
    """
    key = f"viewed_galaxies:{guest_session_id}"
    timestamp = time.time()
    
    # Добавляем в sorted set
    redis.zadd(key, {str(galaxy_id): timestamp})
    
    # Оставляем только последние MAX_VIEWED
    redis.zremrangebyrank(key, 0, -MAX_VIEWED - 1)
    
    # Устанавливаем TTL (20 минут)
    redis.expire(key, 20 * 60)

def get_recently_viewed_galaxies(guest_session_id: str, count: int = RECENT_COUNT):
    """
    Получает список ID недавно просмотренных галактик.
    Возвращает в порядке от новых к старым.
    """
    key = f"viewed_galaxies:{guest_session_id}"
    
    # Получаем последние count элементов (от новых к старым)
    galaxy_ids = redis.zrevrange(key, 0, count - 1)
    
    return [int(gid) for gid in galaxy_ids]