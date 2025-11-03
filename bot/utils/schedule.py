"""
Утилиты для работы с расписанием мастера
"""
from datetime import datetime, time, timedelta
from sqlalchemy.orm import Session
from bot.models import ScheduleSlot, Appointment, AppointmentStatus
from typing import List
import logging

logger = logging.getLogger(__name__)

DAYS_OF_WEEK = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


def is_time_in_schedule(
    db: Session,
    master_id: int,
    check_time: datetime
) -> bool:
    """
    Проверка, работает ли мастер в указанное время
    
    Args:
        db: Сессия БД
        master_id: ID мастера
        check_time: Время для проверки
    
    Returns:
        True если мастер работает в это время, False иначе
    """
    check_date = check_time.date()
    day_of_week = check_time.weekday()  # 0=Понедельник, 6=Воскресенье
    check_time_only = check_time.time()
    
    # Сначала проверяем индивидуальное расписание для конкретной даты
    specific_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == master_id,
        ScheduleSlot.specific_date == check_date
    ).all()
    
    # Если есть выходной день для этой даты
    for slot in specific_slots:
        if slot.is_day_off:
            return False
    
    # Если есть индивидуальное расписание для этой даты (не выходной)
    for slot in specific_slots:
        if not slot.is_day_off:
            slot_start = slot.start_time.time()
            slot_end = slot.end_time.time()
            if slot_start <= check_time_only < slot_end:
                return True
    
    # Если есть индивидуальное расписание, но время не попадает - возвращаем False
    if specific_slots:
        return False
    
    # Если нет индивидуального расписания, проверяем общее расписание по дням недели
    recurring_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == master_id,
        ScheduleSlot.is_recurring == True,
        ScheduleSlot.day_of_week == day_of_week
    ).all()
    
    for slot in recurring_slots:
        slot_start = slot.start_time.time()
        slot_end = slot.end_time.time()
        
        # Проверка что время попадает в рабочие часы
        if slot_start <= check_time_only < slot_end:
            return True
    
    # Если нет расписания, разрешаем запись в любое время (8:00-22:00 по умолчанию)
    if not recurring_slots:
        default_start = time(8, 0)
        default_end = time(22, 0)
        if default_start <= check_time_only < default_end:
            return True
    
    return False


def get_available_time_slots(
    db: Session,
    master_id: int,
    selected_date: datetime,
    service_duration_minutes: int,
    step_minutes: int = 30
) -> List[datetime]:
    """
    Получение списка доступных временных слотов для записи
    
    Args:
        db: Сессия БД
        master_id: ID мастера
        selected_date: Выбранная дата
        service_duration_minutes: Длительность услуги в минутах
        step_minutes: Шаг времени в минутах
    
    Returns:
        Список доступных временных слотов
    """
    check_date = selected_date.date()
    day_of_week = selected_date.weekday()
    
    # Получаем индивидуальное расписание для конкретной даты
    specific_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == master_id,
        ScheduleSlot.specific_date == check_date
    ).all()
    
    # Если есть выходной день для этой даты - нет доступных слотов
    for slot in specific_slots:
        if slot.is_day_off:
            return []
    
    # Если есть индивидуальное расписание для этой даты
    if specific_slots:
        schedule_slots = [s for s in specific_slots if not s.is_day_off]
    else:
        # Если нет индивидуального расписания, используем общее расписание по дням недели
        schedule_slots = db.query(ScheduleSlot).filter(
            ScheduleSlot.master_id == master_id,
            ScheduleSlot.is_recurring == True,
            ScheduleSlot.day_of_week == day_of_week
        ).all()
    
    # Получаем занятые записи на эту дату
    start_of_day = datetime.combine(check_date, time(0, 0))
    end_of_day = datetime.combine(check_date, time(23, 59, 59))
    
    booked_appointments = db.query(Appointment).filter(
        Appointment.master_id == master_id,
        Appointment.status != AppointmentStatus.CANCELLED,
        Appointment.start_time >= start_of_day,
        Appointment.start_time < end_of_day
    ).all()
    
    # Если нет расписания, используем значения по умолчанию
    if not schedule_slots:
        work_start = time(8, 0)
        work_end = time(22, 0)
    else:
        # Берем первый слот (можно расширить для нескольких слотов в день)
        slot = schedule_slots[0]
        work_start = slot.start_time.time()
        work_end = slot.end_time.time()
    
    # Генерируем доступные слоты
    available_slots = []
    current_time = datetime.combine(check_date, work_start)
    end_time = datetime.combine(check_date, work_end)
    
    while current_time < end_time:
        slot_end = current_time + timedelta(minutes=service_duration_minutes)
        
        # Проверяем, что слот не выходит за рабочие часы
        if slot_end > end_time:
            break
        
        # Проверяем, что слот не пересекается с существующими записями
        is_available = True
        for appointment in booked_appointments:
            if (current_time < appointment.end_time and slot_end > appointment.start_time):
                is_available = False
                break
        
        if is_available:
            # Проверяем, что время в будущем
            if current_time > datetime.utcnow():
                available_slots.append(current_time)
        
        current_time += timedelta(minutes=step_minutes)
    
    return available_slots

