"""
Утилиты для календаря расписания мастера
"""
from datetime import datetime, date, timedelta
from calendar import monthrange
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.orm import Session
from bot.models import ScheduleSlot

MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def get_schedule_month_keyboard(
    year: int,
    month: int,
    db: Session,
    master_id: int,
    mode: str = "view"  # "view" или "edit"
) -> InlineKeyboardMarkup:
    """
    Создание календаря месяца для настройки расписания
    
    Args:
        year: Год
        month: Месяц (1-12)
        db: Сессия БД
        master_id: ID мастера
        mode: Режим отображения ("view" или "edit")
    
    Returns:
        InlineKeyboardMarkup с календарем
    """
    buttons = []
    
    # Строка с названием месяца и годом
    month_name = MONTHS_RU[month - 1]
    buttons.append([
        InlineKeyboardButton(f"{month_name} {year}", callback_data="ignore")
    ])
    
    # Заголовки дней недели
    weekdays = []
    for day in DAYS_RU:
        weekdays.append(InlineKeyboardButton(day, callback_data="ignore"))
    buttons.append(weekdays)
    
    # Получаем индивидуальные расписания для этого месяца
    start_date = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    
    specific_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == master_id,
        ScheduleSlot.specific_date >= start_date,
        ScheduleSlot.specific_date <= end_date
    ).all()
    
    schedule_dict = {}  # date -> (is_day_off, work_hours_str)
    for slot in specific_slots:
        slot_date = slot.specific_date
        if slot.is_day_off:
            schedule_dict[slot_date] = (True, "Выходной")
        else:
            start_str = slot.start_time.strftime("%H:%M")
            end_str = slot.end_time.strftime("%H:%M")
            schedule_dict[slot_date] = (False, f"{start_str}-{end_str}")
    
    # Дни месяца
    first_day, last_day_num = monthrange(year, month)
    first_weekday = (first_day + 1) % 7
    
    current_row = []
    today = datetime.now().date()
    
    for day in range(1, last_day_num + 1):
        day_date = date(year, month, day)
        
        # Формируем callback - всегда используем edit_date, так как редактирование доступно всегда
        callback_data = f"schedule_edit_date_{year}_{month:02d}_{day:02d}"
        
        # Получаем информацию о расписании для этого дня
        if day_date in schedule_dict:
            is_off, hours_info = schedule_dict[day_date]
            if is_off:
                display = f"❌{day}"  # Выходной
            else:
                display = f"✓{day}"  # Индивидуальное расписание
        else:
            display = str(day)  # Обычный день
        
        # Выделение сегодняшнего дня
        if day_date == today:
            display = f"[{display}]"
        
        # Неактивные дни в прошлом
        if day_date < today:
            display = " "
            callback_data = "ignore"
        
        current_row.append(InlineKeyboardButton(display, callback_data=callback_data))
        
        # Новая строка каждые 7 дней
        if len(current_row) == 7:
            buttons.append(current_row)
            current_row = []
    
    # Дополняем последнюю строку пустыми клетками
    if current_row:
        while len(current_row) < 7:
            current_row.append(InlineKeyboardButton(" ", callback_data="ignore"))
        buttons.append(current_row)
    
    # Навигация по месяцам
    nav_buttons = []
    
    # Предыдущий месяц
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    # Следующий месяц
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"schedule_month_{prev_year}_{prev_month:02d}"))
    nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"schedule_month_{next_year}_{next_month:02d}"))
    buttons.append(nav_buttons)
    
    # Кнопки управления
    control_buttons = []
    control_buttons.append(InlineKeyboardButton("📅 Общее расписание", callback_data="schedule_weekly"))
    control_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data="schedule_settings"))
    buttons.append(control_buttons)
    
    return InlineKeyboardMarkup(buttons)

