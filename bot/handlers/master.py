"""
Обработчики для мастеров
"""
from sqlalchemy.orm import Session
from bot.models import User, UserRole, MasterProfile, Service, Appointment, AppointmentStatus
from bot.utils.forbidden_categories import validate_service_name
from bot.utils.validators import validate_price, validate_duration, generate_unique_link
from bot.utils.telegram_helpers import safe_edit_message_text
from bot.handlers.common import get_db_from_context
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, date
import logging
import secrets

logger = logging.getLogger(__name__)


async def become_master_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Стать мастером'"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user:
        await safe_edit_message_text(query, "Ошибка: пользователь не найден")
        return
    
    if user.role == UserRole.MASTER:
        await safe_edit_message_text(query, "Вы уже являетесь мастером!")
        return
    
    # Создание профиля мастера
    unique_link = generate_unique_link(user.id, user.username)
    
    master_profile = MasterProfile(
        user_id=user.id,
        unique_link=unique_link,
        business_name=user.full_name or f"Мастер {user.id}"
    )
    db.add(master_profile)
    
    user.role = UserRole.MASTER
    db.commit()
    
    keyboard = [
        [InlineKeyboardButton("📋 Добавить услугу", callback_data="service_create")],
        [InlineKeyboardButton("📅 Настроить расписание", callback_data="schedule_settings")],
        [InlineKeyboardButton("🔗 Моя ссылка", callback_data="master_link")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="start_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"✅ Вы стали мастером!\n\n"
        f"Ваша уникальная ссылка:\n"
        f"https://t.me/{context.bot.username}?start={unique_link}\n\n"
        f"Что дальше?\n"
        f"1. Добавьте услуги\n"
        f"2. Настройте расписание\n"
        f"3. Поделитесь ссылкой с клиентами"
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)
    logger.info(f"Пользователь {user_data.id} стал мастером")


async def master_services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр услуг мастера"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    services = db.query(Service).filter(
        Service.master_id == user.master_profile.id
    ).all()
    
    if not services:
        keyboard = [
            [InlineKeyboardButton("➕ Добавить услугу", callback_data="service_create")],
            [InlineKeyboardButton("◀️ Назад", callback_data="start_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message_text(
            query,
            "У вас пока нет услуг. Добавьте первую услугу!",
            reply_markup=reply_markup
        )
        return
    
    message = "📋 Ваши услуги:\n\n"
    buttons = []
    
    for service in services:
        status = "✅" if service.is_active and not service.is_hidden else "❌"
        message += (
            f"{status} {service.name}\n"
            f"💰 {service.price} ₽ | ⏱ {service.duration_minutes} мин.\n\n"
        )
        buttons.append([InlineKeyboardButton(
            f"{status} {service.name}",
            callback_data=f"service_edit_{service.id}"
        )])
    
    buttons.append([InlineKeyboardButton("➕ Добавить услугу", callback_data="service_create")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="start_menu")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def service_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания услуги"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['creating_service'] = True
    context.user_data['service_data'] = {}
    
    await safe_edit_message_text(
        query,
        "📝 Создание новой услуги\n\n"
        "Введите название услуги:"
    )


async def handle_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка названия услуги"""
    if not context.user_data.get('creating_service'):
        return
    
    service_name = update.message.text.strip()
    
    # Проверка на запрещенные категории
    is_valid, error_msg = validate_service_name(service_name)
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\n"
            "Пожалуйста, введите другое название:"
        )
        return
    
    context.user_data['service_data']['name'] = service_name
    
    await update.message.reply_text(
        f"Название: {service_name}\n\n"
        "Введите описание услуги (или отправьте '-' чтобы пропустить):"
    )


async def handle_service_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания услуги"""
    if not context.user_data.get('creating_service'):
        return
    
    description = update.message.text.strip()
    
    if description != '-':
        # Проверка на запрещенные категории
        is_valid, error_msg = validate_service_name(context.user_data['service_data']['name'], description)
        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "Пожалуйста, введите другое описание:"
            )
            return
    
    context.user_data['service_data']['description'] = description if description != '-' else None
    
    await update.message.reply_text(
        "Введите стоимость услуги в рублях (например: 1000):"
    )


async def handle_service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка цены услуги"""
    if not context.user_data.get('creating_service'):
        return
    
    try:
        price = float(update.message.text.strip())
        is_valid, error_msg = validate_price(price)
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "Введите корректную стоимость:"
            )
            return
        
        context.user_data['service_data']['price'] = price
        
        await update.message.reply_text(
            "Введите длительность услуги в минутах (например: 60):"
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат цены. Введите число (например: 1000):"
        )


async def handle_service_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка длительности услуги и создание"""
    if not context.user_data.get('creating_service'):
        return
    
    try:
        duration = int(update.message.text.strip())
        is_valid, error_msg = validate_duration(duration)
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "Введите корректную длительность:"
            )
            return
        
        db_func = context.bot_data.get('db_session')
        if callable(db_func):
            db = db_func()
        else:
            db = db_func
        
        user_data = update.effective_user
        
        user = db.query(User).filter(User.telegram_id == user_data.id).first()
        
        if not user or not user.master_profile:
            await update.message.reply_text("❌ Ошибка: профиль мастера не найден")
            context.user_data.pop('creating_service', None)
            return
        
        # Создание услуги
        service = Service(
            master_id=user.master_profile.id,
            name=context.user_data['service_data']['name'],
            description=context.user_data['service_data'].get('description'),
            price=context.user_data['service_data']['price'],
            duration_minutes=duration,
            is_active=True
        )
        
        db.add(service)
        db.commit()
        
        context.user_data.pop('creating_service', None)
        context.user_data.pop('service_data', None)
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои услуги", callback_data="master_services")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="start_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Услуга '{service.name}' успешно создана!",
            reply_markup=reply_markup
        )
        
        logger.info(f"Создана услуга {service.id} для мастера {user.master_profile.id}")
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Введите число минут (например: 60):"
        )


async def service_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    db = get_db_from_context(context)
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        await safe_edit_message_text(query, "Услуга не найдена")
        return
    
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"service_edit_form_{service_id}")],
        [
            InlineKeyboardButton(
                "👁 Скрыть" if not service.is_hidden else "👁 Показать",
                callback_data=f"service_toggle_hidden_{service_id}"
            )
        ],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"service_delete_{service_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="master_services")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status = "Активна" if service.is_active and not service.is_hidden else "Скрыта"
    
    message = (
        f"📋 {service.name}\n\n"
        f"💰 Цена: {service.price} ₽\n"
        f"⏱ Длительность: {service.duration_minutes} мин.\n"
        f"📝 Описание: {service.description or 'Нет описания'}\n"
        f"Статус: {status}"
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def service_edit_form_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Форма редактирования услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    db = get_db_from_context(context)
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        await safe_edit_message_text(query, "Услуга не найдена")
        return
    
    # Проверка владельца услуги
    user_data = update.effective_user
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile or user.master_profile.id != service.master_id:
        await safe_edit_message_text(query, "❌ У вас нет прав для редактирования этой услуги")
        return
    
    keyboard = [
        [InlineKeyboardButton("📝 Название", callback_data=f"edit_service_name_{service_id}")],
        [InlineKeyboardButton("📄 Описание", callback_data=f"edit_service_description_{service_id}")],
        [InlineKeyboardButton("💰 Цена", callback_data=f"edit_service_price_{service_id}")],
        [InlineKeyboardButton("⏱ Длительность", callback_data=f"edit_service_duration_{service_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"service_edit_{service_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"✏️ Редактирование услуги: {service.name}\n\n"
        f"Текущие данные:\n"
        f"📝 Название: {service.name}\n"
        f"📄 Описание: {service.description or 'Нет описания'}\n"
        f"💰 Цена: {service.price} ₽\n"
        f"⏱ Длительность: {service.duration_minutes} мин.\n\n"
        f"Выберите поле для редактирования:"
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


# Обработчики редактирования услуги

async def service_edit_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования названия услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    context.user_data['editing_service'] = True
    context.user_data['editing_field'] = 'name'
    context.user_data['editing_service_id'] = service_id
    
    await safe_edit_message_text(
        query,
        "📝 Редактирование названия услуги\n\n"
        "Введите новое название услуги:"
    )


async def service_edit_description_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования описания услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    context.user_data['editing_service'] = True
    context.user_data['editing_field'] = 'description'
    context.user_data['editing_service_id'] = service_id
    
    await safe_edit_message_text(
        query,
        "📄 Редактирование описания услуги\n\n"
        "Введите новое описание (или отправьте '-' чтобы удалить):"
    )


async def service_edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования цены услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    context.user_data['editing_service'] = True
    context.user_data['editing_field'] = 'price'
    context.user_data['editing_service_id'] = service_id
    
    await safe_edit_message_text(
        query,
        "💰 Редактирование цены услуги\n\n"
        "Введите новую стоимость в рублях (например: 1000):"
    )


async def service_edit_duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования длительности услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    context.user_data['editing_service'] = True
    context.user_data['editing_field'] = 'duration'
    context.user_data['editing_service_id'] = service_id
    
    await safe_edit_message_text(
        query,
        "⏱ Редактирование длительности услуги\n\n"
        "Введите новую длительность в минутах (например: 60):"
    )


async def handle_service_name_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, service_id: int):
    """Обработка редактирования названия услуги"""
    if not context.user_data.get('editing_service') or context.user_data.get('editing_field') != 'name':
        return
    
    service_name = update.message.text.strip()
    
    # Проверка на запрещенные категории
    is_valid, error_msg = validate_service_name(service_name)
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\n"
            "Пожалуйста, введите другое название:"
        )
        return
    
    db = get_db_from_context(context)
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        await update.message.reply_text("❌ Услуга не найдена")
        context.user_data.pop('editing_service', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_service_id', None)
        return
    
    # Проверка владельца
    user_data = update.effective_user
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile or user.master_profile.id != service.master_id:
        await update.message.reply_text("❌ У вас нет прав для редактирования этой услуги")
        context.user_data.pop('editing_service', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_service_id', None)
        return
    
    # Обновление услуги
    service.name = service_name
    db.commit()
    
    context.user_data.pop('editing_service', None)
    context.user_data.pop('editing_field', None)
    context.user_data.pop('editing_service_id', None)
    
    keyboard = [
        [InlineKeyboardButton("📋 Мои услуги", callback_data="master_services")],
        [InlineKeyboardButton(f"✏️ Редактировать {service.name}", callback_data=f"service_edit_form_{service_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Название услуги обновлено: {service_name}",
        reply_markup=reply_markup
    )
    
    logger.info(f"Обновлено название услуги {service_id}")


async def handle_service_description_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, service_id: int):
    """Обработка редактирования описания услуги"""
    if not context.user_data.get('editing_service') or context.user_data.get('editing_field') != 'description':
        return
    
    description = update.message.text.strip()
    
    db = get_db_from_context(context)
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        await update.message.reply_text("❌ Услуга не найдена")
        context.user_data.pop('editing_service', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_service_id', None)
        return
    
    # Проверка владельца
    user_data = update.effective_user
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile or user.master_profile.id != service.master_id:
        await update.message.reply_text("❌ У вас нет прав для редактирования этой услуги")
        context.user_data.pop('editing_service', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_service_id', None)
        return
    
    # Проверка на запрещенные категории
    if description != '-':
        is_valid, error_msg = validate_service_name(service.name, description)
        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "Пожалуйста, введите другое описание:"
            )
            return
    
    # Обновление услуги
    service.description = description if description != '-' else None
    db.commit()
    
    context.user_data.pop('editing_service', None)
    context.user_data.pop('editing_field', None)
    context.user_data.pop('editing_service_id', None)
    
    keyboard = [
        [InlineKeyboardButton("📋 Мои услуги", callback_data="master_services")],
        [InlineKeyboardButton(f"✏️ Редактировать {service.name}", callback_data=f"service_edit_form_{service_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Описание услуги обновлено",
        reply_markup=reply_markup
    )
    
    logger.info(f"Обновлено описание услуги {service_id}")


async def handle_service_price_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, service_id: int):
    """Обработка редактирования цены услуги"""
    if not context.user_data.get('editing_service') or context.user_data.get('editing_field') != 'price':
        return
    
    try:
        price = float(update.message.text.strip())
        is_valid, error_msg = validate_price(price)
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "Введите корректную стоимость:"
            )
            return
        
        db = get_db_from_context(context)
        service = db.query(Service).filter(Service.id == service_id).first()
        
        if not service:
            await update.message.reply_text("❌ Услуга не найдена")
            context.user_data.pop('editing_service', None)
            context.user_data.pop('editing_field', None)
            context.user_data.pop('editing_service_id', None)
            return
        
        # Проверка владельца
        user_data = update.effective_user
        user = db.query(User).filter(User.telegram_id == user_data.id).first()
        
        if not user or not user.master_profile or user.master_profile.id != service.master_id:
            await update.message.reply_text("❌ У вас нет прав для редактирования этой услуги")
            context.user_data.pop('editing_service', None)
            context.user_data.pop('editing_field', None)
            context.user_data.pop('editing_service_id', None)
            return
        
        # Обновление услуги
        service.price = price
        db.commit()
        
        context.user_data.pop('editing_service', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_service_id', None)
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои услуги", callback_data="master_services")],
            [InlineKeyboardButton(f"✏️ Редактировать {service.name}", callback_data=f"service_edit_form_{service_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Цена услуги обновлена: {price} ₽",
            reply_markup=reply_markup
        )
        
        logger.info(f"Обновлена цена услуги {service_id}")
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат цены. Введите число (например: 1000):"
        )


async def handle_service_duration_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, service_id: int):
    """Обработка редактирования длительности услуги"""
    if not context.user_data.get('editing_service') or context.user_data.get('editing_field') != 'duration':
        return
    
    try:
        duration = int(update.message.text.strip())
        is_valid, error_msg = validate_duration(duration)
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "Введите корректную длительность:"
            )
            return
        
        db = get_db_from_context(context)
        service = db.query(Service).filter(Service.id == service_id).first()
        
        if not service:
            await update.message.reply_text("❌ Услуга не найдена")
            context.user_data.pop('editing_service', None)
            context.user_data.pop('editing_field', None)
            context.user_data.pop('editing_service_id', None)
            return
        
        # Проверка владельца
        user_data = update.effective_user
        user = db.query(User).filter(User.telegram_id == user_data.id).first()
        
        if not user or not user.master_profile or user.master_profile.id != service.master_id:
            await update.message.reply_text("❌ У вас нет прав для редактирования этой услуги")
            context.user_data.pop('editing_service', None)
            context.user_data.pop('editing_field', None)
            context.user_data.pop('editing_service_id', None)
            return
        
        # Обновление услуги
        service.duration_minutes = duration
        db.commit()
        
        context.user_data.pop('editing_service', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_service_id', None)
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои услуги", callback_data="master_services")],
            [InlineKeyboardButton(f"✏️ Редактировать {service.name}", callback_data=f"service_edit_form_{service_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Длительность услуги обновлена: {duration} мин.",
            reply_markup=reply_markup
        )
        
        logger.info(f"Обновлена длительность услуги {service_id}")
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Введите число минут (например: 60):"
        )


async def service_toggle_hidden(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение видимости услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    db = get_db_from_context(context)
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        await safe_edit_message_text(query, "Услуга не найдена")
        return
    
    service.is_hidden = not service.is_hidden
    db.commit()
    
    await query.answer(f"Услуга {'скрыта' if service.is_hidden else 'показана'}")
    # Обновляем сообщение с новой информацией
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"service_edit_form_{service.id}")],
        [
            InlineKeyboardButton(
                "👁 Скрыть" if not service.is_hidden else "👁 Показать",
                callback_data=f"service_toggle_hidden_{service.id}"
            )
        ],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"service_delete_{service.id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="master_services")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status = "Активна" if service.is_active and not service.is_hidden else "Скрыта"
    
    message = (
        f"📋 {service.name}\n\n"
        f"💰 Цена: {service.price} ₽\n"
        f"⏱ Длительность: {service.duration_minutes} мин.\n"
        f"📝 Описание: {service.description or 'Нет описания'}\n"
        f"Статус: {status}"
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def service_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    db = get_db_from_context(context)
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        await safe_edit_message_text(query, "Услуга не найдена")
        return
    
    service_name = service.name
    db.delete(service)
    db.commit()
    
    keyboard = [
        [InlineKeyboardButton("📋 Мои услуги", callback_data="master_services")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message_text(
        query,
        f"✅ Услуга '{service_name}' удалена",
        reply_markup=reply_markup
    )
    
    logger.info(f"Услуга {service_id} удалена")


async def master_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ ссылки мастера"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    unique_link = user.master_profile.unique_link
    bot_username = context.bot.username
    full_link = f"https://t.me/{bot_username}?start={unique_link}"
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"🔗 Ваша уникальная ссылка для записи:\n\n"
        f"`{full_link}`\n\n"
        f"Отправьте эту ссылку клиентам, чтобы они могли записаться к вам.\n\n"
        f"Просто нажмите на ссылку, чтобы скопировать её."
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup, parse_mode='Markdown')


async def master_appointments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр записей мастера"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    # Показываем все записи: будущие и завершенные (для выставления чека)
    appointments = db.query(Appointment).filter(
        Appointment.master_id == user.master_profile.id
    ).order_by(Appointment.start_time.desc()).limit(30).all()
    
    if not appointments:
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="start_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message_text(
            query,
            "У вас пока нет будущих записей.",
            reply_markup=reply_markup
        )
        return
    
    message = "📅 Ваши записи:\n\n"
    buttons = []
    
    # Группируем записи по клиентам, чтобы исключить дубли кнопок
    clients_dict = {}  # client_id -> client_user
    
    for appointment in appointments:
        client = appointment.client
        service = appointment.service
        
        # Сохраняем клиента в словарь (если еще нет)
        if client.id not in clients_dict:
            clients_dict[client.id] = client
        
        status_emoji = {
            AppointmentStatus.PENDING: "⏳",
            AppointmentStatus.CONFIRMED: "✅",
            AppointmentStatus.CANCELLED: "❌",
            AppointmentStatus.COMPLETED: "✅"
        }.get(appointment.status, "📅")
        
        phone_text = f"\n   📱 {appointment.client_phone}" if appointment.client_phone else ""
        
        status_text = ""
        invoice_button = None
        complete_button = None
        
        if appointment.status == AppointmentStatus.COMPLETED:
            # Проверяем, есть ли чек для этой записи
            from bot.models import Invoice
            invoice = db.query(Invoice).filter(Invoice.appointment_id == appointment.id).first()
            if invoice:
                if invoice.payment_status.value == "succeeded":
                    status_text = " ✅ Оплачено"
                elif invoice.payment_status.value == "pending":
                    status_text = " 💳 Чек выставлен"
                else:
                    status_text = " 💳 Чек не оплачен"
            else:
                status_text = " 💳 Чек не выставлен"
                # Добавляем кнопку для выставления чека
                invoice_button = [InlineKeyboardButton(
                    f"💳 Выставить чек",
                    callback_data=f"create_invoice_{appointment.id}"
                )]
        elif appointment.status == AppointmentStatus.CONFIRMED:
            # Добавляем кнопку для завершения записи
            complete_button = [InlineKeyboardButton(
                f"✅ Завершить запись",
                callback_data=f"complete_appointment_{appointment.id}"
            )]
        
        message += (
            f"{status_emoji} {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"   {service.name}\n"
            f"   Клиент: {appointment.client_name or client.full_name}{phone_text}{status_text}\n\n"
        )
        
        # Добавляем кнопки, если нужно
        if invoice_button:
            buttons.append(invoice_button)
        if complete_button:
            buttons.append(complete_button)
    
    # Создаем кнопки для каждого уникального клиента
    for client_id, client_user in clients_dict.items():
        # Находим запись этого клиента для получения client_name
        client_appointment = next((a for a in appointments if a.client_id == client_id), None)
        client_name = (client_appointment.client_name if client_appointment and client_appointment.client_name else client_user.full_name)
        
        # Ссылка на личные сообщения клиента в Telegram
        # Используем username если есть, иначе tg://user?id={telegram_id}
        if client_user.username:
            client_link = f"https://t.me/{client_user.username}"
        else:
            # Если username нет, используем tg://user?id= для открытия чата
            client_link = f"tg://user?id={client_user.telegram_id}"
        
        buttons.append([InlineKeyboardButton(
            f"💬 Написать клиенту: {client_name}",
            url=client_link
        )])
    
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="start_menu")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def master_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки мастера"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    master_profile = user.master_profile
    
    keyboard = [
        [InlineKeyboardButton(
            f"🔔 Уведомления: за {master_profile.default_notification_hours} ч.",
            callback_data="settings_notifications"
        )],
        [InlineKeyboardButton("📅 Расписание работы", callback_data="schedule_settings")],
        [InlineKeyboardButton("◀️ Назад", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"⚙️ Настройки\n\n"
        f"🔔 Напоминание клиентам: за {master_profile.default_notification_hours} часов до записи\n\n"
        f"Выберите настройку:"
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def settings_notifications_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка времени уведомлений"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    keyboard = [
        [InlineKeyboardButton("1 час", callback_data="set_notif_1")],
        [InlineKeyboardButton("6 часов", callback_data="set_notif_6")],
        [InlineKeyboardButton("12 часов", callback_data="set_notif_12")],
        [InlineKeyboardButton("24 часа", callback_data="set_notif_24")],
        [InlineKeyboardButton("48 часов", callback_data="set_notif_48")],
        [InlineKeyboardButton("◀️ Назад", callback_data="master_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "🔔 Настройка уведомлений\n\n"
        "Выберите, за сколько часов до записи напоминать клиентам:"
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def set_notification_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка времени уведомлений"""
    query = update.callback_query
    await query.answer()
    
    hours = int(query.data.split("_")[-1])
    
    db = get_db_from_context(context)
    
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    user.master_profile.default_notification_hours = hours
    db.commit()
    
    keyboard = [
        [InlineKeyboardButton("◀️ Назад в настройки", callback_data="master_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message_text(
        query,
        f"✅ Время уведомлений установлено: {hours} часов до записи",
        reply_markup=reply_markup
    )
    
    logger.info(f"Мастер {user.id} установил время уведомлений: {hours} часов")


# Обработчики расписания мастера

async def schedule_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка расписания работы мастера - главное меню"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    master_profile = user.master_profile
    
    # Получаем текущее общее расписание
    from bot.models import ScheduleSlot
    schedule_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == master_profile.id,
        ScheduleSlot.is_recurring == True
    ).all()
    
    from bot.utils.schedule import DAYS_OF_WEEK
    
    scheduled_days = {}
    for slot in schedule_slots:
        if slot.day_of_week not in scheduled_days:
            scheduled_days[slot.day_of_week] = []
        scheduled_days[slot.day_of_week].append(slot)
    
    # Формируем информацию о расписании
    schedule_info = ""
    has_schedule = False
    for day_num in range(7):
        day_name = DAYS_OF_WEEK[day_num]
        if day_num in scheduled_days:
            has_schedule = True
            slots = scheduled_days[day_num]
            time_ranges = []
            for slot in slots:
                start_str = slot.start_time.strftime("%H:%M")
                end_str = slot.end_time.strftime("%H:%M")
                time_ranges.append(f"{start_str}-{end_str}")
            time_info = ", ".join(time_ranges)
            schedule_info += f"✅ {day_name}: {time_info}\n"
        else:
            schedule_info += f"❌ {day_name}: выходной\n"
    
    if not has_schedule:
        schedule_info = "Расписание не настроено. Используется по умолчанию (8:00-22:00)."
    
    keyboard = [
        [InlineKeyboardButton("📅 Общее расписание (дни недели)", callback_data="schedule_weekly")],
        [InlineKeyboardButton("📆 Календарь месяца", callback_data="schedule_calendar_month")]
    ]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="master_settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    today = datetime.now()
    message = (
        f"📅 Настройка расписания работы\n\n"
        f"Текущее общее расписание:\n{schedule_info}\n"
        f"Вы можете настроить:\n"
        f"• Общее расписание - рабочие дни недели\n"
        f"• Календарь месяца - индивидуальные дни с особым расписанием\n\n"
        f"Если день месяца не отредактирован, применяется общее расписание."
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def schedule_weekly_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка общего расписания по дням недели"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    master_profile = user.master_profile
    
    # Получаем текущее расписание
    from bot.models import ScheduleSlot
    schedule_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == master_profile.id,
        ScheduleSlot.is_recurring == True
    ).all()
    
    from bot.utils.schedule import DAYS_OF_WEEK
    
    keyboard = []
    scheduled_days = {}
    
    for slot in schedule_slots:
        if slot.day_of_week not in scheduled_days:
            scheduled_days[slot.day_of_week] = []
        scheduled_days[slot.day_of_week].append(slot)
    
    # Кнопки для каждого дня недели
    for day_num in range(7):
        day_name = DAYS_OF_WEEK[day_num]
        if day_num in scheduled_days:
            slots = scheduled_days[day_num]
            time_ranges = []
            for slot in slots:
                start_str = slot.start_time.strftime("%H:%M")
                end_str = slot.end_time.strftime("%H:%M")
                time_ranges.append(f"{start_str}-{end_str}")
            time_info = ", ".join(time_ranges)
            button_text = f"✅ {day_name} ({time_info})"
        else:
            button_text = f"❌ {day_name}"
        
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"schedule_day_{day_num}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="schedule_settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"📅 Общее расписание работы\n\n"
        f"Настройте рабочие дни недели. Это расписание будет применяться ко всем дням месяца,\n"
        f"кроме тех, для которых установлено индивидуальное расписание.\n\n"
        f"✅ - день настроен\n"
        f"❌ - день не настроен (выходной)\n\n"
        f"Выберите день для настройки:"
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def schedule_calendar_month_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ календаря месяца для настройки расписания"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    # Показываем текущий месяц
    today = datetime.now()
    from bot.utils.schedule_calendar import get_schedule_month_keyboard
    
    keyboard = get_schedule_month_keyboard(
        today.year,
        today.month,
        db,
        user.master_profile.id,
        mode="edit"
    )
    
    message = (
        f"📆 Календарь расписания\n\n"
        f"Выберите день для редактирования:\n"
        f"• ✓ - индивидуальное расписание\n"
        f"• ❌ - выходной\n"
        f"• Обычное число - применяется общее расписание"
    )
    
    await safe_edit_message_text(query, message, reply_markup=keyboard)


async def schedule_month_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Навигация по месяцам в календаре расписания"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    year = int(parts[2])
    month = int(parts[3])
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    from bot.utils.schedule_calendar import get_schedule_month_keyboard
    
    # Календарь всегда в режиме редактирования
    keyboard = get_schedule_month_keyboard(
        year,
        month,
        db,
        user.master_profile.id,
        mode="edit"
    )
    
    message = (
        f"📆 Календарь расписания\n\n"
        f"Выберите день для редактирования:\n"
        f"• ✓ - индивидуальное расписание\n"
        f"• ❌ - выходной\n"
        f"• Обычное число - применяется общее расписание"
    )
    
    await safe_edit_message_text(query, message, reply_markup=keyboard)


async def schedule_edit_month_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход в режим редактирования месяца"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    year = int(parts[3])
    month = int(parts[4])
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    context.user_data['schedule_calendar_mode'] = 'edit'
    
    from bot.utils.schedule_calendar import get_schedule_month_keyboard
    
    keyboard = get_schedule_month_keyboard(
        year,
        month,
        db,
        user.master_profile.id,
        mode="edit"
    )
    
    message = (
        f"📆 Редактирование расписания месяца\n\n"
        f"Выберите день для редактирования:\n"
        f"• ✓ - индивидуальное расписание\n"
        f"• ❌ - выходной\n"
        f"• Обычное число - применяется общее расписание"
    )
    
    await safe_edit_message_text(query, message, reply_markup=keyboard)


async def schedule_edit_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_date: date = None):
    """Редактирование расписания конкретной даты"""
    query = update.callback_query
    await query.answer()
    
    # Если дата не передана, парсим из callback_data
    if selected_date is None:
        parts = query.data.split("_")
        # Поддержка разных форматов: schedule_edit_date_, schedule_view_date_, schedule_set_day_off_, schedule_set_time_
        if "edit_date" in query.data or "view_date" in query.data:
            year = int(parts[3])
            month = int(parts[4])
            day = int(parts[5])
        elif "set_day_off" in query.data:
            year = int(parts[4])
            month = int(parts[5])
            day = int(parts[6])
        elif "set_time" in query.data:
            # Формат: schedule_set_time_{year}_{month:02d}_{day:02d}
            year = int(parts[3])
            month = int(parts[4])
            day = int(parts[5])
        elif "remove_date" in query.data:
            year = int(parts[3])
            month = int(parts[4])
            day = int(parts[5])
        else:
            # Пытаемся получить из контекста
            selected_date = context.user_data.get('schedule_date')
            if selected_date is None:
                await safe_edit_message_text(query, "❌ Ошибка: не удалось определить дату")
                return
        if selected_date is None:
            selected_date = date(year, month, day)
    
    # Извлекаем year, month, day из selected_date для использования в callback_data
    year = selected_date.year
    month = selected_date.month
    day = selected_date.day
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    from bot.models import ScheduleSlot
    
    # Получаем существующее расписание для этой даты
    existing_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == user.master_profile.id,
        ScheduleSlot.specific_date == selected_date
    ).all()
    
    keyboard = []
    
    if existing_slots:
        # Показываем текущее расписание
        for slot in existing_slots:
            if slot.is_day_off:
                keyboard.append([InlineKeyboardButton(
                    "❌ Выходной",
                    callback_data="ignore"
                )])
            else:
                start_str = slot.start_time.strftime("%H:%M")
                end_str = slot.end_time.strftime("%H:%M")
                keyboard.append([InlineKeyboardButton(
                    f"🕐 {start_str} - {end_str}",
                    callback_data=f"schedule_remove_date_{year}_{month:02d}_{day:02d}"
                )])
    
    keyboard.append([InlineKeyboardButton(
        "➕ Установить время работы",
        callback_data=f"schedule_set_time_{year}_{month:02d}_{day:02d}"
    )])
    keyboard.append([InlineKeyboardButton(
        "❌ Установить выходной",
        callback_data=f"schedule_set_day_off_{year}_{month:02d}_{day:02d}"
    )])
    keyboard.append([InlineKeyboardButton(
        "◀️ Назад к календарю",
        callback_data=f"schedule_month_{year}_{month:02d}"
    )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    from bot.utils.schedule_calendar import MONTHS_RU
    date_str = f"{day} {MONTHS_RU[month-1]} {year}"
    
    if existing_slots:
        message = f"📅 Редактирование расписания: {date_str}\n\n"
        for slot in existing_slots:
            if slot.is_day_off:
                message += "❌ Выходной\n"
            else:
                message += f"🕐 {slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}\n"
    else:
        message = (
            f"📅 Редактирование расписания: {date_str}\n\n"
            f"Для этой даты применяется общее расписание.\n"
            f"Вы можете установить индивидуальное расписание или выходной день."
        )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def schedule_view_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр расписания конкретной даты"""
    await schedule_edit_date_callback(update, context)


async def schedule_set_day_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка выходного дня"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    day = int(parts[6])
    
    selected_date = date(year, month, day)
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await query.answer("Ошибка: профиль мастера не найден")
        return
    
    from bot.models import ScheduleSlot
    
    # Удаляем существующие слоты для этой даты
    existing_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == user.master_profile.id,
        ScheduleSlot.specific_date == selected_date
    ).all()
    
    for slot in existing_slots:
        db.delete(slot)
    
    # Создаем слот выходного дня
    from datetime import datetime, time as dt_time
    start_time_dt = datetime.combine(selected_date, dt_time(0, 0))
    end_time_dt = datetime.combine(selected_date, dt_time(23, 59))
    
    slot = ScheduleSlot(
        master_id=user.master_profile.id,
        start_time=start_time_dt,
        end_time=end_time_dt,
        is_recurring=False,
        specific_date=selected_date,
        is_day_off=True
    )
    
    db.add(slot)
    db.commit()
    
    await query.answer("✅ Выходной день установлен")
    
    # Обновляем экран, передавая дату напрямую
    await schedule_edit_date_callback(update, context, selected_date=selected_date)


async def schedule_remove_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление индивидуального расписания для даты"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    year = int(parts[3])
    month = int(parts[4])
    day = int(parts[5])
    
    selected_date = date(year, month, day)
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await query.answer("Ошибка: профиль мастера не найден")
        return
    
    from bot.models import ScheduleSlot
    
    # Удаляем все слоты для этой даты
    existing_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == user.master_profile.id,
        ScheduleSlot.specific_date == selected_date
    ).all()
    
    for slot in existing_slots:
        db.delete(slot)
    
    db.commit()
    
    await query.answer("✅ Индивидуальное расписание удалено")
    
    # Обновляем экран, передавая дату напрямую
    await schedule_edit_date_callback(update, context, selected_date=selected_date)


async def schedule_set_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало установки времени работы для конкретной даты"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    # Формат: schedule_set_time_{year}_{month:02d}_{day:02d}
    # parts[0]=schedule, parts[1]=set, parts[2]=time, parts[3]=year, parts[4]=month, parts[5]=day
    year = int(parts[3])
    month = int(parts[4])
    day = int(parts[5])
    
    selected_date = date(year, month, day)
    
    context.user_data['setting_schedule_date'] = True
    context.user_data['schedule_date'] = selected_date
    context.user_data['schedule_data'] = {}
    
    from bot.utils.schedule_calendar import MONTHS_RU
    date_str = f"{day} {MONTHS_RU[month-1]} {year}"
    
    await safe_edit_message_text(
        query,
        f"📅 Установка времени работы: {date_str}\n\n"
        f"Введите время начала работы в формате ЧЧ:ММ (например: 09:00):"
    )


async def handle_schedule_date_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени начала работы для конкретной даты"""
    text = update.message.text.strip()
    
    try:
        time_parts = text.split(":")
        if len(time_parts) != 2:
            raise ValueError
        
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
        
        schedule_data = context.user_data.get('schedule_data', {})
        schedule_data['start_time'] = f"{hour:02d}:{minute:02d}"
        context.user_data['schedule_data'] = schedule_data
        
        await update.message.reply_text(
            f"✅ Время начала: {hour:02d}:{minute:02d}\n\n"
            f"Введите время окончания работы в формате ЧЧ:ММ (например: 18:00):"
        )
        
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ (например: 09:00):"
        )


async def handle_schedule_date_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени окончания работы для конкретной даты и сохранение"""
    text = update.message.text.strip()
    
    try:
        time_parts = text.split(":")
        if len(time_parts) != 2:
            raise ValueError
        
        end_hour = int(time_parts[0])
        end_minute = int(time_parts[1])
        
        if not (0 <= end_hour < 24 and 0 <= end_minute < 60):
            raise ValueError
        
        schedule_data = context.user_data.get('schedule_data', {})
        start_time_str = schedule_data.get('start_time')
        
        if not start_time_str:
            await update.message.reply_text("❌ Ошибка: потеряно время начала. Начните заново.")
            context.user_data.pop('setting_schedule_date', None)
            context.user_data.pop('schedule_date', None)
            context.user_data.pop('schedule_data', None)
            return
        
        start_parts = start_time_str.split(":")
        start_hour = int(start_parts[0])
        start_minute = int(start_parts[1])
        
        selected_date = context.user_data.get('schedule_date')
        
        from datetime import datetime, time as dt_time
        start_time_dt = datetime.combine(selected_date, dt_time(start_hour, start_minute))
        end_time_dt = datetime.combine(selected_date, dt_time(end_hour, end_minute))
        
        if end_time_dt <= start_time_dt:
            await update.message.reply_text(
                "❌ Время окончания должно быть позже времени начала. Введите корректное время:"
            )
            return
        
        db = get_db_from_context(context)
        user_data = update.effective_user
        
        user = db.query(User).filter(User.telegram_id == user_data.id).first()
        
        if not user or not user.master_profile:
            await update.message.reply_text("❌ Ошибка: профиль мастера не найден")
            context.user_data.pop('setting_schedule_date', None)
            context.user_data.pop('schedule_date', None)
            context.user_data.pop('schedule_data', None)
            return
        
        # Удаляем существующие слоты для этой даты
        from bot.models import ScheduleSlot
        existing_slots = db.query(ScheduleSlot).filter(
            ScheduleSlot.master_id == user.master_profile.id,
            ScheduleSlot.specific_date == selected_date
        ).all()
        
        for slot in existing_slots:
            db.delete(slot)
        
        # Создаем новый слот
        slot = ScheduleSlot(
            master_id=user.master_profile.id,
            start_time=start_time_dt,
            end_time=end_time_dt,
            is_recurring=False,
            specific_date=selected_date,
            is_day_off=False
        )
        
        db.add(slot)
        db.commit()
        
        context.user_data.pop('setting_schedule_date', None)
        context.user_data.pop('schedule_date', None)
        context.user_data.pop('schedule_data', None)
        
        keyboard = [
            [InlineKeyboardButton("📆 Календарь", callback_data=f"schedule_month_{selected_date.year}_{selected_date.month:02d}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="schedule_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        from bot.utils.schedule_calendar import MONTHS_RU
        date_str = f"{selected_date.day} {MONTHS_RU[selected_date.month-1]} {selected_date.year}"
        
        await update.message.reply_text(
            f"✅ Расписание для {date_str} сохранено:\n"
            f"🕐 {start_time_str} - {end_hour:02d}:{end_minute:02d}",
            reply_markup=reply_markup
        )
        
        logger.info(f"Мастер {user.id} установил индивидуальное расписание для {date_str}: {start_time_str}-{end_hour:02d}:{end_minute:02d}")
        
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ (например: 18:00):"
        )


async def schedule_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора дня недели для настройки"""
    query = update.callback_query
    await query.answer()
    
    day_num = int(query.data.split("_")[-1])
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or not user.master_profile:
        await safe_edit_message_text(query, "Ошибка: профиль мастера не найден")
        return
    
    from bot.utils.schedule import DAYS_OF_WEEK
    from bot.models import ScheduleSlot
    day_name = DAYS_OF_WEEK[day_num]
    
    # Проверяем, есть ли уже расписание для этого дня
    existing_slots = db.query(ScheduleSlot).filter(
        ScheduleSlot.master_id == user.master_profile.id,
        ScheduleSlot.is_recurring == True,
        ScheduleSlot.day_of_week == day_num
    ).all()
    
    keyboard = []
    
    if existing_slots:
        # Показываем текущее расписание
        for slot in existing_slots:
            start_str = slot.start_time.strftime("%H:%M")
            end_str = slot.end_time.strftime("%H:%M")
            keyboard.append([InlineKeyboardButton(
                f"🕐 {start_str} - {end_str}",
                callback_data=f"schedule_remove_slot_{slot.id}"
            )])
        keyboard.append([InlineKeyboardButton(
            "🗑 Удалить все слоты",
            callback_data=f"schedule_remove_day_{day_num}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "➕ Добавить рабочие часы",
        callback_data=f"schedule_set_work_hours_{day_num}"
    )])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="schedule_settings")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if existing_slots:
        message = (
            f"📅 {day_name}\n\n"
            f"Текущее расписание:\n"
        )
        for slot in existing_slots:
            message += f"🕐 {slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}\n"
    else:
        message = (
            f"📅 {day_name}\n\n"
            f"Расписание не настроено. Добавьте рабочие часы для этого дня."
        )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def schedule_set_work_hours_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало настройки рабочих часов"""
    query = update.callback_query
    await query.answer()
    
    day_num = int(query.data.split("_")[-1])
    
    context.user_data['setting_schedule'] = True
    context.user_data['schedule_day'] = day_num
    context.user_data['schedule_data'] = {}
    
    from bot.utils.schedule import DAYS_OF_WEEK
    day_name = DAYS_OF_WEEK[day_num]
    
    await safe_edit_message_text(
        query,
        f"📅 Настройка рабочего времени: {day_name}\n\n"
        f"Введите время начала работы в формате ЧЧ:ММ (например: 09:00):"
    )


async def schedule_remove_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление расписания для дня"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    if len(parts) == 4 and parts[0] == "schedule" and parts[1] == "remove" and parts[2] == "slot":
        slot_id = int(parts[3])
        
        db = get_db_from_context(context)
        from bot.models import ScheduleSlot
        slot = db.query(ScheduleSlot).filter(ScheduleSlot.id == slot_id).first()
        
        if slot:
            db.delete(slot)
            db.commit()
            await query.answer("Расписание удалено")
            # Обновляем экран
            await schedule_day_callback(update, context)
        else:
            await query.answer("Расписание не найдено")
    else:
        day_num = int(query.data.split("_")[-1])
        
        db = get_db_from_context(context)
        user_data = update.effective_user
        
        user = db.query(User).filter(User.telegram_id == user_data.id).first()
        
        if not user or not user.master_profile:
            await query.answer("Ошибка: профиль мастера не найден")
            return
        
        # Удаляем все слоты для этого дня
        from bot.models import ScheduleSlot
        slots = db.query(ScheduleSlot).filter(
            ScheduleSlot.master_id == user.master_profile.id,
            ScheduleSlot.is_recurring == True,
            ScheduleSlot.day_of_week == day_num
        ).all()
        
        for slot in slots:
            db.delete(slot)
        db.commit()
        
        await query.answer("Расписание для дня удалено")
        # Обновляем экран
        await schedule_day_callback(update, context)


async def handle_schedule_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени начала работы"""
    text = update.message.text.strip()
    
    try:
        # Парсим время в формате ЧЧ:ММ
        time_parts = text.split(":")
        if len(time_parts) != 2:
            raise ValueError
        
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
        
        schedule_data = context.user_data.get('schedule_data', {})
        schedule_data['start_time'] = f"{hour:02d}:{minute:02d}"
        context.user_data['schedule_data'] = schedule_data
        
        await update.message.reply_text(
            f"✅ Время начала: {hour:02d}:{minute:02d}\n\n"
            f"Введите время окончания работы в формате ЧЧ:ММ (например: 18:00):"
        )
        
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ (например: 09:00):"
        )


async def handle_schedule_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени окончания работы и сохранение расписания"""
    text = update.message.text.strip()
    
    try:
        # Парсим время в формате ЧЧ:ММ
        time_parts = text.split(":")
        if len(time_parts) != 2:
            raise ValueError
        
        end_hour = int(time_parts[0])
        end_minute = int(time_parts[1])
        
        if not (0 <= end_hour < 24 and 0 <= end_minute < 60):
            raise ValueError
        
        schedule_data = context.user_data.get('schedule_data', {})
        start_time_str = schedule_data.get('start_time')
        
        if not start_time_str:
            await update.message.reply_text("❌ Ошибка: потеряно время начала. Начните заново.")
            context.user_data.pop('setting_schedule', None)
            context.user_data.pop('schedule_day', None)
            context.user_data.pop('schedule_data', None)
            return
        
        # Парсим время начала
        start_parts = start_time_str.split(":")
        start_hour = int(start_parts[0])
        start_minute = int(start_parts[1])
        
        # Создаем datetime объекты для проверки
        from datetime import datetime, time as dt_time
        start_time_dt = datetime.combine(datetime.today().date(), dt_time(start_hour, start_minute))
        end_time_dt = datetime.combine(datetime.today().date(), dt_time(end_hour, end_minute))
        
        if end_time_dt <= start_time_dt:
            await update.message.reply_text(
                "❌ Время окончания должно быть позже времени начала. Введите корректное время:"
            )
            return
        
        # Сохраняем расписание
        db = get_db_from_context(context)
        user_data = update.effective_user
        
        user = db.query(User).filter(User.telegram_id == user_data.id).first()
        
        if not user or not user.master_profile:
            await update.message.reply_text("❌ Ошибка: профиль мастера не найден")
            context.user_data.pop('setting_schedule', None)
            context.user_data.pop('schedule_day', None)
            context.user_data.pop('schedule_data', None)
            return
        
        day_num = context.user_data.get('schedule_day')
        
        # Создаем слот расписания
        from bot.models import ScheduleSlot
        slot = ScheduleSlot(
            master_id=user.master_profile.id,
            start_time=start_time_dt,
            end_time=end_time_dt,
            is_recurring=True,
            day_of_week=day_num
        )
        
        db.add(slot)
        db.commit()
        
        context.user_data.pop('setting_schedule', None)
        context.user_data.pop('schedule_day', None)
        context.user_data.pop('schedule_data', None)
        
        keyboard = [
            [InlineKeyboardButton("📅 Расписание", callback_data="schedule_settings")],
            [InlineKeyboardButton("◀️ Назад", callback_data="master_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        from bot.utils.schedule import DAYS_OF_WEEK
        day_name = DAYS_OF_WEEK[day_num]
        
        await update.message.reply_text(
            f"✅ Расписание для {day_name} сохранено:\n"
            f"🕐 {start_time_str} - {end_hour:02d}:{end_minute:02d}",
            reply_markup=reply_markup
        )
        
        logger.info(f"Мастер {user.id} установил расписание для {day_name}: {start_time_str}-{end_hour:02d}:{end_minute:02d}")
        
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Неверный формат времени. Введите время в формате ЧЧ:ММ (например: 18:00):"
        )


async def complete_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение записи мастером"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    # Извлекаем ID записи
    appointment_id = int(query.data.split("_")[-1])
    
    # Получаем запись
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        await safe_edit_message_text(query, "Ошибка: запись не найдена")
        return
    
    # Проверяем, что пользователь - мастер этой записи
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    if not user or not user.master_profile or user.master_profile.id != appointment.master_id:
        await safe_edit_message_text(query, "Ошибка: у вас нет доступа к этой записи")
        return
    
    # Проверяем, что запись подтверждена
    if appointment.status != AppointmentStatus.CONFIRMED:
        await safe_edit_message_text(query, "Ошибка: запись не может быть завершена")
        return
    
    # Помечаем запись как завершенную
    appointment.status = AppointmentStatus.COMPLETED
    db.commit()
    
    # Уведомляем клиента
    try:
        client = appointment.client
        await context.bot.send_message(
            chat_id=client.telegram_id,
            text=f"✅ Услуга оказана!\n\n"
                 f"Услуга: {appointment.service.name}\n"
                 f"Дата: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n\n"
                 f"Мастер выставит чек для оплаты."
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления клиенту: {e}")
    
    # Обновляем сообщение для мастера
    await safe_edit_message_text(
        query,
        f"✅ Запись завершена!\n\n"
        f"Теперь вы можете выставить чек клиенту.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Выставить чек", callback_data=f"create_invoice_{appointment.id}")],
            [InlineKeyboardButton("◀️ Мои записи", callback_data="master_appointments")]
        ])
    )


