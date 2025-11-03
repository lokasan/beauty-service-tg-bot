"""
Утилиты для работы с календарем
"""
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from calendar import monthrange
import pytz

# Месяцы на русском
MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def get_time_keyboard(
    selected_date: datetime,
    available_slots: list = None,
    step_minutes: int = 30
) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для выбора времени
    
    Args:
        selected_date: Выбранная дата
        available_slots: Список доступных временных слотов (если None - все время)
        step_minutes: Шаг времени в минутах (15, 30, 60)
    """
    buttons = []
    row = []
    
    if available_slots:
        # Используем только доступные слоты
        time_slots = []
        for slot in available_slots:
            time_str = slot.strftime("%H:%M")
            time_slots.append((slot, time_str))
    else:
        # Время с 8:00 до 22:00 (по умолчанию)
        start_hour = 8
        end_hour = 22
        current_time = datetime.combine(selected_date.date(), datetime.min.time().replace(hour=start_hour))
        
        time_slots = []
        while current_time.hour < end_hour or (current_time.hour == end_hour and current_time.minute == 0):
            time_str = current_time.strftime("%H:%M")
            time_slots.append((current_time, time_str))
            current_time += timedelta(minutes=step_minutes)
    
    # Группировка по строкам по 3 кнопки
    for i, (time_obj, time_str) in enumerate(time_slots):
        callback_data = f"time_{time_obj.hour:02d}_{time_obj.minute:02d}"
        row.append(InlineKeyboardButton(time_str, callback_data=callback_data))
        
        if len(row) == 3 or i == len(time_slots) - 1:
            buttons.append(row)
            row = []
    
    # Кнопка назад
    buttons.append([InlineKeyboardButton("◀️ Назад к календарю", callback_data="calendar_back")])
    
    return InlineKeyboardMarkup(buttons)


def get_month_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры календаря для выбора месяца
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
    
    # Дни месяца
    first_day, last_day = monthrange(year, month)
    # first_day: 0=Понедельник, 6=Воскресенье (в Python calendar)
    # Но нам нужно: 0=Понедельник
    first_weekday = (first_day + 1) % 7  # Преобразование
    
    current_row = []
    
    # Пустые клетки до первого дня
    for _ in range(first_weekday):
        current_row.append(InlineKeyboardButton(" ", callback_data="ignore"))
    
    # Дни месяца
    today = datetime.now().date()
    min_date = today
    max_date = today + timedelta(days=365)  # Можно записаться на год вперед
    
    for day in range(1, last_day + 1):
        date = datetime(year, month, day).date()
        callback_data = f"date_{year}_{month:02d}_{day:02d}"
        
        # Выделение сегодняшнего дня
        if date == today:
            display = f"[{day}]"
        elif date < min_date:
            display = " "
            callback_data = "ignore"
        else:
            display = str(day)
        
        current_row.append(InlineKeyboardButton(display, callback_data=callback_data))
        
        if len(current_row) == 7:
            buttons.append(current_row)
            current_row = []
    
    # Дополнить последнюю строку пустыми клетками
    if current_row:
        while len(current_row) < 7:
            current_row.append(InlineKeyboardButton(" ", callback_data="ignore"))
        buttons.append(current_row)
    
    # Навигация
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    
    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1
    
    nav_buttons = [
        InlineKeyboardButton("◀️", callback_data=f"month_{prev_year}_{prev_month:02d}"),
        InlineKeyboardButton("Назад", callback_data="services_back"),
        InlineKeyboardButton("▶️", callback_data=f"month_{next_year}_{next_month:02d}")
    ]
    buttons.append(nav_buttons)
    
    return InlineKeyboardMarkup(buttons)


def parse_date_from_callback(data: str) -> datetime:
    """Парсинг даты из callback_data"""
    parts = data.split("_")
    if len(parts) == 4 and parts[0] == "date":
        year, month, day = int(parts[1]), int(parts[2]), int(parts[3])
        return datetime(year, month, day)
    return None


def parse_time_from_callback(data: str) -> tuple[int, int]:
    """Парсинг времени из callback_data"""
    parts = data.split("_")
    if len(parts) == 3 and parts[0] == "time":
        hour, minute = int(parts[1]), int(parts[2])
        return hour, minute
    return None, None

