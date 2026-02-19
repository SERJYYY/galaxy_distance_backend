# backend/api/middleware/guest_session.py
import uuid
import time
from django.conf import settings
from django_redis import get_redis_connection

class GuestSessionMiddleware:
    """
    Middleware для управления гостевой сессией.
    Создаёт куку guest_session_id при первом посещении.
    Сессия хранится в Redis 20 минут.
    """
    
    COOKIE_NAME = "guest_session_id"
    SESSION_TTL = 20 * 60  # 20 минут в секундах
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.redis = get_redis_connection("default")
    
    def __call__(self, request):
        # Получаем или создаём guest_session_id
        guest_session_id = request.COOKIES.get(self.COOKIE_NAME)
        
        if not guest_session_id:
            # Создаём новую сессию
            guest_session_id = str(uuid.uuid4())
            self.redis.setex(
                f"guest_session:{guest_session_id}",
                self.SESSION_TTL,
                time.time()  # Время создания
            )
        else:
            # Проверяем и обновляем TTL существующей сессии
            session_key = f"guest_session:{guest_session_id}"
            if self.redis.exists(session_key):
                self.redis.expire(session_key, self.SESSION_TTL)
            else:
                # Сессия истекла — создаём новую
                guest_session_id = str(uuid.uuid4())
                self.redis.setex(
                    session_key,
                    self.SESSION_TTL,
                    time.time()
                )
        
        # Сохраняем в request для использования в views
        request.guest_session_id = guest_session_id
        
        response = self.get_response(request)
        
        # Устанавливаем куку
        response.set_cookie(
            self.COOKIE_NAME,
            guest_session_id,
            max_age=self.SESSION_TTL,
            httponly=True,
            samesite="Lax",
            secure=False,  # True для HTTPS
        )
        
        return response