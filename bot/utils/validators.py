"""
Утилиты для валидации данных
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from bot.models import Appointment, MasterProfile
import logging

logger = logging.getLogger(__name__)


def check_appointment_overlap(
    db: Session,
    master_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: int = None
) -> bool:
    """
    Проверка пересечения записей
    
    Args:
        db: Сессия БД
        master_id: ID мастера
        start_time: Начало новой записи
        end_time: Конец новой записи
        exclude_appointment_id: ID записи для исключения (при редактировании)
    
    Returns:
        True если есть пересечение, False если нет
    """
    query = db.query(Appointment).filter(
        Appointment.master_id == master_id,
        Appointment.status != "cancelled",
        # Проверка пересечения: новая запись начинается раньше, чем заканчивается существующая
        # И новая запись заканчивается позже, чем начинается существующая
        Appointment.start_time < end_time,
        Appointment.end_time > start_time
    )
    
    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)
    
    overlapping = query.first()
    
    if overlapping:
        logger.warning(
            f"Обнаружено пересечение записи для мастера {master_id} "
            f"с {start_time} по {end_time}"
        )
    
    return overlapping is not None


def validate_time_slot(
    start_time: datetime,
    end_time: datetime,
    min_duration_minutes: int = 15,
    max_advance_days: int = 365
) -> tuple[bool, str]:
    """
    Валидация временного слота
    
    Returns:
        (is_valid, error_message)
    """
    now = datetime.utcnow()
    
    # Проверка что время в будущем
    if start_time <= now:
        return False, "Нельзя записаться на прошедшее время"
    
    # Проверка что не слишком далеко вперед
    max_date = now + timedelta(days=max_advance_days)
    if start_time > max_date:
        return False, f"Нельзя записаться более чем на {max_advance_days} дней вперед"
    
    # Проверка что end_time > start_time
    if end_time <= start_time:
        return False, "Время окончания должно быть позже времени начала"
    
    # Проверка минимальной длительности
    duration = (end_time - start_time).total_seconds() / 60
    if duration < min_duration_minutes:
        return False, f"Минимальная длительность записи - {min_duration_minutes} минут"
    
    return True, ""


def generate_unique_link(master_id: int, username: str = None) -> str:
    """
    Генерация уникальной ссылки для мастера
    
    Format: master_<id>_<random>
    """
    import secrets
    random_part = secrets.token_urlsafe(8)
    
    if username:
        base = username.lower().replace(" ", "_")
    else:
        base = f"master_{master_id}"
    
    return f"{base}_{random_part}"


def validate_price(price: float) -> tuple[bool, str]:
    """Валидация цены"""
    if price < 0:
        return False, "Цена не может быть отрицательной"
    if price > 1000000:
        return False, "Цена слишком высокая"
    return True, ""


def validate_duration(duration_minutes: int) -> tuple[bool, str]:
    """Валидация длительности"""
    if duration_minutes < 5:
        return False, "Минимальная длительность услуги - 5 минут"
    if duration_minutes > 1440:  # 24 часа
        return False, "Максимальная длительность услуги - 24 часа"
    return True, ""



