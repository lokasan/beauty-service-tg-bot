"""
Обработчики для клиентов
"""
from sqlalchemy.orm import Session
from bot.models import User, UserRole, MasterProfile, Service, Appointment, AppointmentStatus, Feedback
from bot.utils.validators import check_appointment_overlap, validate_time_slot
from bot.utils.calendar import get_month_keyboard, get_time_keyboard, parse_date_from_callback, parse_time_from_callback
from bot.utils.notifications import schedule_notifications
from bot.utils.schedule import get_available_time_slots
from bot.utils.telegram_helpers import safe_edit_message_text
from bot.handlers.common import get_db_from_context
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


async def book_by_link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса записи по ссылке"""
    query = update.callback_query
    if query:
        await query.answer()
    
    message_text = (
        "📝 Запись по ссылке мастера\n\n"
        "Отправьте ссылку мастера или его уникальный код:"
    )
    
    if query:
        await query.edit_message_text(message_text)
    else:
        await update.message.reply_text(message_text)
    
    context.user_data['waiting_for_link'] = True


async def handle_master_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки мастера из команды /start"""
    if not context.args:
        return
    
    link_code = context.args[0]
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    # Получаем или создаем пользователя
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    if not user:
        from bot.handlers.common import get_or_create_user
        user = await get_or_create_user(db, user_data.id, user_data.username, user_data.full_name)
    
    # Поиск мастера по уникальной ссылке
    master_profile = db.query(MasterProfile).filter(
        MasterProfile.unique_link == link_code
    ).first()
    
    if not master_profile:
        await update.message.reply_text(
            "❌ Мастер не найден. Проверьте ссылку."
        )
        return
    
    # Проверка: мастер не может записаться к самому себе
    if user.master_profile and user.master_profile.id == master_profile.id:
        await update.message.reply_text(
            "❌ Вы не можете записаться к самому себе. Используйте ссылку другого мастера."
        )
        return
    
    # Проверяем активные услуги
    services = db.query(Service).filter(
        Service.master_id == master_profile.id,
        Service.is_active == True,
        Service.is_hidden == False
    ).all()
    
    if not services:
        await update.message.reply_text(
            "😔 У этого мастера пока нет доступных услуг."
        )
        return
    
    context.user_data['selected_master_id'] = master_profile.id
    context.user_data['master_link'] = link_code
    
    # Показываем услуги
    await show_services(update, context, master_profile.id)


async def handle_link_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенной ссылки"""
    if not context.user_data.get('waiting_for_link'):
        return
    
    link_input = update.message.text.strip()
    
    # Извлечение кода из ссылки или использование как есть
    if "?start=" in link_input:
        link_code = link_input.split("?start=")[-1]
    else:
        link_code = link_input
    
    db = get_db_from_context(context)
    
    master_profile = db.query(MasterProfile).filter(
        MasterProfile.unique_link == link_code
    ).first()
    
    if not master_profile:
        await update.message.reply_text(
            "❌ Мастер не найден. Проверьте ссылку и попробуйте снова:"
        )
        return
    
    # Проверка: мастер не может записаться к самому себе
    from bot.handlers.common import get_or_create_user
    user = await get_or_create_user(db, update.effective_user.id, update.effective_user.username, update.effective_user.full_name)
    if user.master_profile and user.master_profile.id == master_profile.id:
        await update.message.reply_text(
            "❌ Вы не можете записаться к самому себе. Используйте ссылку другого мастера."
        )
        context.user_data.pop('waiting_for_link', None)
        return
    
    context.user_data.pop('waiting_for_link', None)
    context.user_data['selected_master_id'] = master_profile.id
    context.user_data['master_link'] = link_code
    
    # Показываем услуги
    await show_services(update, context, master_profile.id)


async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE, master_id: int = None):
    """Показ услуг мастера"""
    db = get_db_from_context(context)
    
    if not master_id:
        master_id = context.user_data.get('selected_master_id')
    
    # Сохраняем master_id в контексте для возврата к услугам
    if master_id:
        context.user_data['selected_master_id'] = master_id
    
    if not master_id:
        await update.message.reply_text("Ошибка: мастер не выбран")
        return
    
    master_profile = db.query(MasterProfile).filter(MasterProfile.id == master_id).first()
    if not master_profile:
        await update.message.reply_text("Мастер не найден")
        return
    
    services = db.query(Service).filter(
        Service.master_id == master_id,
        Service.is_active is True,
        Service.is_hidden is False
    ).all()
    
    if not services:
        await update.message.reply_text("У этого мастера пока нет доступных услуг.")
        return
    
    # Рассчитываем средний рейтинг мастера
    from sqlalchemy import func
    avg_rating = db.query(func.avg(Feedback.rating)).select_from(Feedback).join(
        Appointment, Feedback.appointment_id == Appointment.id
    ).filter(
        Appointment.master_id == master_id,
        Feedback.rating.isnot(None)
    ).scalar()
    
    # Количество отзывов
    total_reviews = db.query(func.count(Feedback.id)).select_from(Feedback).join(
        Appointment, Feedback.appointment_id == Appointment.id
    ).filter(
        Appointment.master_id == master_id,
        Feedback.rating.isnot(None)
    ).scalar() or 0
    
    message = f"🛠 Услуги {master_profile.business_name or master_profile.user.full_name}:\n\n"
    
    if avg_rating:
        message += f"⭐ Средний рейтинг: {avg_rating:.1f}/5 ({'⭐' * round(avg_rating)})\n"
        message += f"📝 Отзывов: {total_reviews}\n\n"
    
    buttons = []
    for service in services:
        message += f"• {service.name}\n   💰 {service.price} ₽ | ⏱ {service.duration_minutes} мин.\n\n"
        buttons.append([InlineKeyboardButton(
            f"{service.name} - {service.price} ₽",
            callback_data=f"service_select_{service.id}"
        )])
    
    # Добавляем кнопку просмотра отзывов
    if total_reviews > 0:
        buttons.append([InlineKeyboardButton(
            f"⭐ Отзывы ({total_reviews})",
            callback_data=f"view_reviews_{master_id}"
        )])
    
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="start_menu")])
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)


async def service_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор услуги"""
    query = update.callback_query
    await query.answer()
    
    service_id = int(query.data.split("_")[-1])
    
    db = get_db_from_context(context)
    service = db.query(Service).filter(Service.id == service_id).first()
    
    if not service:
        await query.edit_message_text("Услуга не найдена")
        return
    
    context.user_data['selected_service_id'] = service_id
    context.user_data['selected_service'] = service
    
    # Показываем календарь
    today = datetime.now()
    keyboard = get_month_keyboard(today.year, today.month)
    
    message = (
        f"📅 Выберите дату для услуги:\n\n"
        f"🛠 {service.name}\n"
        f"💰 {service.price} ₽\n"
        f"⏱ {service.duration_minutes} мин."
    )
    
    await query.edit_message_text(message, reply_markup=keyboard)


async def date_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбранной даты"""
    query = update.callback_query
    await query.answer()
    
    selected_date = parse_date_from_callback(query.data)
    
    if not selected_date:
        await query.answer("Ошибка выбора даты")
        return
    
    context.user_data['selected_date'] = selected_date
    
    # Получаем доступные временные слоты с учетом расписания и занятости
    db = get_db_from_context(context)
    master_id = context.user_data.get('selected_master_id')
    service = context.user_data.get('selected_service')
    
    if not master_id or not service:
        await query.answer("Ошибка: потеряны данные. Начните заново.")
        return
    
    # Получаем доступные слоты
    available_slots = get_available_time_slots(
        db,
        master_id,
        selected_date,
        service.duration_minutes,
        step_minutes=30
    )
    
    if not available_slots:
        await query.answer(
            "❌ На эту дату нет доступного времени. Выберите другую дату.",
            show_alert=True
        )
        return
    
    # Показываем выбор времени
    keyboard = get_time_keyboard(selected_date, available_slots)
    
    message = (
        f"⏰ Выберите время:\n\n"
        f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
        f"🛠 Услуга: {service.name}\n\n"
        f"Доступно {len(available_slots)} временных слотов"
    )
    
    await query.edit_message_text(message, reply_markup=keyboard)


async def time_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбранного времени"""
    query = update.callback_query
    await query.answer()
    
    hour, minute = parse_time_from_callback(query.data)
    
    if hour is None or minute is None:
        await query.answer("Ошибка выбора времени")
        return
    
    selected_date = context.user_data.get('selected_date')
    service = context.user_data.get('selected_service')
    master_id = context.user_data.get('selected_master_id')
    
    if not all([selected_date, service, master_id]):
        await query.edit_message_text("Ошибка: потеряны данные. Начните заново.")
        return
    
    # Формируем время начала и конца
    start_time = datetime.combine(selected_date.date(), datetime.min.time().replace(hour=hour, minute=minute))
    end_time = start_time + timedelta(minutes=service.duration_minutes)
    
    # Валидация временного слота
    is_valid, error_msg = validate_time_slot(start_time, end_time)
    if not is_valid:
        await query.answer(f"❌ {error_msg}", show_alert=True)
        return
    
    # Проверка пересечений
    db = get_db_from_context(context)
    
    if check_appointment_overlap(db, master_id, start_time, end_time):
        await query.answer("❌ Это время уже занято. Выберите другое.", show_alert=True)
        return
    
    # Сохраняем выбранное время
    context.user_data['start_time'] = start_time
    context.user_data['end_time'] = end_time
    
    # Проверяем, запрашивали ли уже телефон
    if not context.user_data.get('phone_requested'):
        # Запрос номера телефона
        context.user_data['phone_requested'] = True
        contact_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        message = (
            f"📋 Подтверждение записи\n\n"
            f"🛠 Услуга: {service.name}\n"
            f"💰 Стоимость: {service.price} ₽\n"
            f"📅 Дата и время: {start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"⏱ Длительность: {service.duration_minutes} мин.\n\n"
            f"Пожалуйста, отправьте ваш номер телефона для связи:"
        )
        
        # Отправляем запрос телефона
        await safe_edit_message_text(query, message)
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Нажмите кнопку ниже, чтобы отправить номер телефона:",
                reply_markup=contact_keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка отправки запроса телефона: {e}")
            # Если не удалось отправить, просто показываем подтверждение без телефона
            context.user_data.pop('phone_requested', None)
            keyboard = [
                [
                    InlineKeyboardButton("✅ Подтвердить", callback_data="appointment_confirm"),
                    InlineKeyboardButton("❌ Отмена", callback_data="services_back")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await safe_edit_message_text(
                query,
                f"📋 Подтверждение записи\n\n"
                f"🛠 {service.name}\n"
                f"💰 {service.price} ₽\n"
                f"📅 {start_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"⏱ {service.duration_minutes} мин.\n\n"
                f"Подтвердите запись:",
                reply_markup=reply_markup
            )
        return
    
    # Подтверждение записи
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="appointment_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="services_back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"📋 Подтверждение записи\n\n"
        f"🛠 Услуга: {service.name}\n"
        f"💰 Стоимость: {service.price} ₽\n"
        f"📅 Дата и время: {start_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"⏱ Длительность: {service.duration_minutes} мин.\n\n"
        f"Подтвердите запись:"
    )
    
    await query.edit_message_text(message, reply_markup=reply_markup)


async def appointment_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение записи"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    service_id = context.user_data.get('selected_service_id')
    master_id = context.user_data.get('selected_master_id')
    start_time = context.user_data.get('start_time')
    end_time = context.user_data.get('end_time')
    
    if not all([service_id, master_id, start_time, end_time]):
        await query.edit_message_text("Ошибка: потеряны данные. Начните заново.")
        return
    
    # Получаем или создаем пользователя
    from bot.handlers.common import get_or_create_user
    user = await get_or_create_user(db, user_data.id, user_data.username, user_data.full_name)
    
    # Получаем профиль мастера
    master_profile = db.query(MasterProfile).filter(MasterProfile.id == master_id).first()
    
    # Проверка: мастер не может записаться к самому себе
    if user.master_profile and user.master_profile.id == master_id:
        await safe_edit_message_text(query, "❌ Вы не можете записаться к самому себе.")
        return
    
    # Повторная проверка пересечений
    if check_appointment_overlap(db, master_id, start_time, end_time):
        await query.edit_message_text(
            "❌ К сожалению, это время уже занято. Выберите другое время."
        )
        return
    
    # Получение телефона из контекста, если был отправлен
    client_phone = context.user_data.get('client_phone', None)
    
    # Создание записи
    appointment = Appointment(
        master_id=master_id,
        client_id=user.id,
        service_id=service_id,
        start_time=start_time,
        end_time=end_time,
        status=AppointmentStatus.CONFIRMED,
        client_name=user.full_name,
        client_phone=client_phone
    )
    
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    
    # Отправка уведомления о подтверждении сразу
    try:
        from bot.utils.notifications import send_confirmation_notification
        await send_confirmation_notification(context.bot, appointment)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о подтверждении: {e}")
    
    # Планирование напоминания
    reminder_hours = master_profile.default_notification_hours or 24
    schedule_notifications(db, appointment, reminder_hours)
    
    # Очистка данных
    context.user_data.pop('selected_service_id', None)
    context.user_data.pop('selected_service', None)
    context.user_data.pop('selected_master_id', None)
    context.user_data.pop('selected_date', None)
    context.user_data.pop('start_time', None)
    context.user_data.pop('end_time', None)
    context.user_data.pop('client_phone', None)
    context.user_data.pop('phone_requested', None)
    
    service = db.query(Service).filter(Service.id == service_id).first()
    
    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"✅ Запись успешно создана!\n\n"
        f"📅 Дата и время: {start_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"🛠 Услуга: {service.name}\n"
        f"💰 Стоимость: {service.price} ₽\n\n"
        f"Мы напомним вам о записи заранее."
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)
    
    logger.info(f"Создана запись {appointment.id} для клиента {user.id} к мастеру {master_id}")
    
    # Уведомление мастеру
    try:
        master_user = master_profile.user
        phone_text = f"\n📱 Телефон: {appointment.client_phone}" if appointment.client_phone else ""
        master_message = (
            f"📅 Новая запись!\n\n"
            f"Дата и время: {start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"Услуга: {service.name}\n"
            f"Клиент: {user.full_name}{phone_text}"
        )
        await context.bot.send_message(
            chat_id=master_user.telegram_id,
            text=master_message
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления мастеру: {e}")


async def handle_phone_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка получения номера телефона клиента"""
    if not update.message.contact:
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте ваш номер телефона через кнопку.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.pop('phone_requested', None)
        return
    
    # Сохраняем номер телефона
    phone = update.message.contact.phone_number
    context.user_data['client_phone'] = phone
    
    # Удаляем клавиатуру с кнопкой телефона
    await update.message.reply_text(
        "✅ Номер телефона получен!",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Показываем подтверждение записи
    service = context.user_data.get('selected_service')
    start_time = context.user_data.get('start_time')
    
    if not service or not start_time:
        await update.message.reply_text("❌ Ошибка: потеряны данные. Начните заново.")
        context.user_data.pop('phone_requested', None)
        context.user_data.pop('client_phone', None)
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="appointment_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="services_back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"📋 Подтверждение записи\n\n"
        f"🛠 Услуга: {service.name}\n"
        f"💰 Стоимость: {service.price} ₽\n"
        f"📅 Дата и время: {start_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"⏱ Длительность: {service.duration_minutes} мин.\n"
        f"📱 Телефон: {phone}\n\n"
        f"Подтвердите запись:"
    )
    
    await update.message.reply_text(message, reply_markup=reply_markup)


async def client_appointments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр записей клиента с пагинацией"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем номер страницы из callback_data: client_appointments_page_{page} или просто client_appointments
    page = 1
    if query.data.startswith("client_appointments_page_"):
        page = int(query.data.split('_')[-1])
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    # Получаем пользователя
    from bot.handlers.common import get_or_create_user
    user = await get_or_create_user(db, user_data.id, user_data.username, user_data.full_name)
    
    # Получаем все записи клиента: будущие и завершенные за последние 30 дней
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Сначала считаем общее количество записей
    from sqlalchemy import func
    total_appointments = db.query(func.count(Appointment.id)).filter(
        Appointment.client_id == user.id,
        Appointment.status != AppointmentStatus.CANCELLED,
        (
            (Appointment.start_time >= datetime.utcnow()) |  # Будущие записи
            (
                (Appointment.status == AppointmentStatus.COMPLETED) &  # Завершенные
                (Appointment.start_time >= thirty_days_ago)  # За последние 30 дней
            )
        )
    ).scalar() or 0
    
    if total_appointments == 0:
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="start_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message_text(
            query,
            "У вас пока нет записей.\n\n"
            "Здесь отображаются:\n"
            "• Будущие записи (для отмены)\n"
            "• Завершенные записи за последние 30 дней (для отзывов)",
            reply_markup=reply_markup
        )
        return
    
    # Пагинация: 5 записей на страницу
    per_page = 5
    total_pages = (total_appointments + per_page - 1) // per_page
    page = min(max(page, 1), total_pages)  # Ограничиваем страницу
    
    offset = (page - 1) * per_page
    
    # Получаем записи для текущей страницы
    appointments = db.query(Appointment).filter(
        Appointment.client_id == user.id,
        Appointment.status != AppointmentStatus.CANCELLED,
        (
            (Appointment.start_time >= datetime.utcnow()) |  # Будущие записи
            (
                (Appointment.status == AppointmentStatus.COMPLETED) &  # Завершенные
                (Appointment.start_time >= thirty_days_ago)  # За последние 30 дней
            )
        )
    ).order_by(Appointment.start_time.desc()).offset(offset).limit(per_page).all()
    
    # Проверяем, является ли пользователь мастером
    is_master = user.role == UserRole.MASTER if hasattr(user, 'role') else False
    
    if is_master:
        message = f"📝 Ваши записи как клиент:\n\n📄 Страница {page} из {total_pages}\n\n"
    else:
        message = f"📅 Ваши записи:\n\n📄 Страница {page} из {total_pages}\n\n"
    buttons = []
    
    # Группируем записи по мастерам, чтобы исключить дубли кнопок
    masters_dict = {}  # master_id -> master_profile
    
    for appointment in appointments:
        master_profile = appointment.master_profile
        service = appointment.service
        
        # Сохраняем мастера в словарь (если еще нет)
        if master_profile.id not in masters_dict:
            masters_dict[master_profile.id] = master_profile
        
        status_emoji = {
            AppointmentStatus.PENDING: "⏳",
            AppointmentStatus.CONFIRMED: "✅",
            AppointmentStatus.CANCELLED: "❌",
            AppointmentStatus.COMPLETED: "✔️"
        }.get(appointment.status, "📅")
        
        message += (
            f"{status_emoji} {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"   🛠 {service.name}\n"
            f"   👤 Мастер: {master_profile.business_name or master_profile.user.full_name}\n"
            f"   💰 {service.price} ₽\n"
        )
        
        # Добавляем кнопку отмены для подтвержденных и ожидающих записей
        if appointment.status in [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]:
            # Проверяем, можно ли отменить (не менее 2 часов до начала)
            time_until = appointment.start_time - datetime.utcnow()
            if time_until >= timedelta(hours=2):
                buttons.append([InlineKeyboardButton(
                    f"❌ Отменить: {appointment.start_time.strftime('%d.%m %H:%M')}",
                    callback_data=f"cancel_appointment_{appointment.id}"
                )])
        
        # Добавляем кнопку отзыва для завершенных записей
        if appointment.status == AppointmentStatus.COMPLETED:
            # Проверяем, есть ли уже отзыв
            existing_feedback = db.query(Feedback).filter(
                Feedback.appointment_id == appointment.id,
                Feedback.user_id == user.id
            ).first()
            
            if not existing_feedback:
                buttons.append([InlineKeyboardButton(
                    f"⭐ Оставить отзыв: {appointment.start_time.strftime('%d.%m %H:%M')}",
                    callback_data=f"leave_feedback_{appointment.id}"
                )])
        
        message += "\n"
    
    # Создаем кнопки для каждого уникального мастера
    for master_id, master_profile in masters_dict.items():
        master_user = master_profile.user
        master_name = master_profile.business_name or master_user.full_name
        
        # Ссылка на личные сообщения мастера в Telegram
        # Используем username если есть, иначе tg://user?id={telegram_id}
        if master_user.username:
            master_link = f"https://t.me/{master_user.username}"
        else:
            # Если username нет, используем tg://user?id= для открытия чата
            master_link = f"tg://user?id={master_user.telegram_id}"
        
        buttons.append([InlineKeyboardButton(
            f"💬 Написать мастеру: {master_name}",
            url=master_link
        )])
    
    # Кнопки пагинации
    nav_buttons = []
    
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"client_appointments_page_{page - 1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"client_appointments_page_{page + 1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="start_menu")])
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def show_master_profile_from_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль мастера из записи"""
    query = update.callback_query
    await query.answer()
    
    # Этот обработчик можно использовать для дополнительной функциональности
    # Пока просто перенаправляем на услуги мастера
    pass


async def cancel_appointment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена записи клиентом"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем appointment_id из callback_data: cancel_appointment_{id}
    appointment_id = int(query.data.split('_')[-1])
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    if not user:
        await safe_edit_message_text(query, "❌ Пользователь не найден")
        return
    
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        await safe_edit_message_text(query, "❌ Запись не найдена")
        return
    
    if appointment.client_id != user.id:
        await safe_edit_message_text(query, "❌ Это не ваша запись")
        return
    
    if appointment.status == AppointmentStatus.CANCELLED:
        await safe_edit_message_text(query, "❌ Запись уже отменена")
        return
    
    if appointment.status == AppointmentStatus.COMPLETED:
        await safe_edit_message_text(query, "❌ Нельзя отменить завершенную запись")
        return
    
    # Проверка: можно отменить только за определенное время до начала
    time_until = appointment.start_time - datetime.utcnow()
    
    if time_until < timedelta(hours=2):
        await query.answer(
            "❌ Запись можно отменить не менее чем за 2 часа до начала",
            show_alert=True
        )
        return
    
    # Отмена записи
    appointment.status = AppointmentStatus.CANCELLED
    db.commit()
    
    # Уведомление мастеру
    try:
        master_user = appointment.master_profile.user
        service = appointment.service
        await context.bot.send_message(
            chat_id=master_user.telegram_id,
            text=(
                f"⚠️ Запись отменена клиентом\n\n"
                f"Услуга: {service.name}\n"
                f"Дата: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"Клиент: {appointment.client_name or appointment.client.full_name}\n"
                f"Телефон: {appointment.client_phone or 'Не указан'}\n\n"
                f"Слот освобожден и доступен для записи."
            )
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления мастеру: {e}")
    
    # Показываем подтверждение отмены
    keyboard = [
        [InlineKeyboardButton("📅 Мои записи", callback_data="client_appointments")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message_text(
        query,
        "✅ Запись успешно отменена.\n\nСлот освобожден и доступен для записи.",
        reply_markup=reply_markup
    )
    
    logger.info(f"Запись {appointment_id} отменена клиентом {user.id}")


async def month_navigation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Навигация по месяцам"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    year = int(parts[1])
    month = int(parts[2])
    
    keyboard = get_month_keyboard(year, month)
    
    service = context.user_data.get('selected_service')
    if service:
        message = (
            f"📅 Выберите дату для услуги:\n\n"
            f"🛠 {service.name}\n"
            f"💰 {service.price} ₽\n"
            f"⏱ {service.duration_minutes} мин."
        )
    else:
        message = "📅 Выберите дату:"
    
    await query.edit_message_text(message, reply_markup=keyboard)


async def leave_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса оставления отзыва"""
    query = update.callback_query
    await query.answer()
    
    appointment_id = int(query.data.split('_')[-1])
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    if not user:
        await safe_edit_message_text(query, "❌ Пользователь не найден")
        return
    
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        await safe_edit_message_text(query, "❌ Запись не найдена")
        return
    
    if appointment.client_id != user.id:
        await safe_edit_message_text(query, "❌ Это не ваша запись")
        return
    
    if appointment.status != AppointmentStatus.COMPLETED:
        await safe_edit_message_text(query, "❌ Можно оставить отзыв только после завершения услуги")
        return
    
    # Проверка: уже есть отзыв?
    existing_feedback = db.query(Feedback).filter(
        Feedback.appointment_id == appointment_id,
        Feedback.user_id == user.id
    ).first()
    
    if existing_feedback:
        await safe_edit_message_text(query, "❌ Вы уже оставили отзыв на эту запись")
        return
    
    context.user_data['leaving_feedback'] = True
    context.user_data['feedback_appointment_id'] = appointment_id
    
    # Клавиатура с рейтингом
    keyboard = [
        [InlineKeyboardButton("⭐", callback_data=f"rating_{appointment_id}_1"),
         InlineKeyboardButton("⭐⭐", callback_data=f"rating_{appointment_id}_2"),
         InlineKeyboardButton("⭐⭐⭐", callback_data=f"rating_{appointment_id}_3"),
         InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rating_{appointment_id}_4"),
         InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rating_{appointment_id}_5")],
        [InlineKeyboardButton("◀️ Отмена", callback_data="client_appointments")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message_text(
        query,
        f"⭐ Оцените услугу (1-5 звезд):\n\n"
        f"Услуга: {appointment.service.name}\n"
        f"Мастер: {appointment.master_profile.business_name or appointment.master_profile.user.full_name}\n"
        f"Дата: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=reply_markup
    )


async def rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора рейтинга"""
    query = update.callback_query
    await query.answer()
    
    # callback_data: rating_{appointment_id}_{rating}
    parts = query.data.split('_')
    appointment_id = int(parts[1])
    rating = int(parts[2])
    
    if rating < 1 or rating > 5:
        await query.answer("❌ Неверный рейтинг", show_alert=True)
        return
    
    context.user_data['feedback_rating'] = rating
    context.user_data['feedback_appointment_id'] = appointment_id
    
    keyboard = [
        [InlineKeyboardButton("◀️ Пропустить текст", callback_data=f"skip_feedback_text_{appointment_id}")],
        [InlineKeyboardButton("◀️ Отмена", callback_data="client_appointments")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message_text(
        query,
        f"⭐ Рейтинг: {'⭐' * rating} ({rating}/5)\n\n"
        f"Напишите отзыв (или пропустите, если хотите оставить только оценку):",
        reply_markup=reply_markup
    )


async def skip_feedback_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск текста отзыва, сохранение только рейтинга"""
    query = update.callback_query
    await query.answer()
    
    appointment_id = int(query.data.split('_')[-1])
    
    rating = context.user_data.get('feedback_rating')
    if not rating:
        await safe_edit_message_text(query, "❌ Ошибка. Попробуйте снова.")
        return
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment or appointment.client_id != user.id:
        await safe_edit_message_text(query, "❌ Ошибка")
        return
    
    # Создание отзыва
    feedback = Feedback(
        user_id=user.id,
        appointment_id=appointment_id,
        master_id=appointment.master_id,
        rating=rating,
        message=None
    )
    db.add(feedback)
    db.commit()
    
    # Уведомление мастеру
    try:
        rating_stars = "⭐" * rating
        # Проверяем, является ли оставивший отзыв мастером
        is_master_client = user.role == UserRole.MASTER if hasattr(user, 'role') else False
        client_type = "👨‍💼 Мастер" if is_master_client else "👤 Клиент"
        
        await context.bot.send_message(
            chat_id=appointment.master_profile.user.telegram_id,
            text=(
                f"⭐ Новый отзыв!\n\n"
                f"Услуга: {appointment.service.name}\n"
                f"Рейтинг: {rating_stars} ({rating}/5)\n"
                f"Дата услуги: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"{client_type}: {appointment.client_name or user.full_name}"
            )
        )
    except Exception as e:
        logger.error(f"Ошибка отправки отзыва мастеру: {e}")
    
    # Очистка
    context.user_data.pop('leaving_feedback', None)
    context.user_data.pop('feedback_appointment_id', None)
    context.user_data.pop('feedback_rating', None)
    
    keyboard = [
        [InlineKeyboardButton("📅 Мои записи", callback_data="client_appointments")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message_text(
        query,
        f"✅ Спасибо за отзыв! Ваша оценка: {'⭐' * rating} ({rating}/5)",
        reply_markup=reply_markup
    )


async def handle_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста отзыва"""
    if not context.user_data.get('leaving_feedback'):
        return
    
    appointment_id = context.user_data.get('feedback_appointment_id')
    rating = context.user_data.get('feedback_rating')
    feedback_text = update.message.text.strip()
    
    if not appointment_id or not rating:
        await update.message.reply_text("❌ Ошибка. Попробуйте снова.")
        return
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment or appointment.client_id != user.id:
        await update.message.reply_text("❌ Ошибка")
        return
    
    # Создание отзыва
    feedback = Feedback(
        user_id=user.id,
        appointment_id=appointment_id,
        master_id=appointment.master_id,
        rating=rating,
        message=feedback_text
    )
    db.add(feedback)
    db.commit()
    
    # Уведомление мастеру
    try:
        rating_stars = "⭐" * rating
        # Проверяем, является ли оставивший отзыв мастером
        is_master_client = user.role == UserRole.MASTER if hasattr(user, 'role') else False
        client_type = "👨‍💼 Мастер" if is_master_client else "👤 Клиент"
        
        await context.bot.send_message(
            chat_id=appointment.master_profile.user.telegram_id,
            text=(
                f"⭐ Новый отзыв!\n\n"
                f"Услуга: {appointment.service.name}\n"
                f"Рейтинг: {rating_stars} ({rating}/5)\n"
                f"Отзыв: {feedback_text}\n"
                f"Дата услуги: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"{client_type}: {appointment.client_name or user.full_name}"
            )
        )
    except Exception as e:
        logger.error(f"Ошибка отправки отзыва мастеру: {e}")
    
    # Очистка
    context.user_data.pop('leaving_feedback', None)
    context.user_data.pop('feedback_appointment_id', None)
    context.user_data.pop('feedback_rating', None)
    
    keyboard = [
        [InlineKeyboardButton("📅 Мои записи", callback_data="client_appointments")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Спасибо за отзыв! Ваша оценка: {'⭐' * rating} ({rating}/5)",
        reply_markup=reply_markup
    )


async def view_master_reviews_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр отзывов мастера клиентом с пагинацией"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем master_id и page из callback_data: view_reviews_{master_id}_page_{page} или view_reviews_{master_id}
    parts = query.data.split('_')
    master_id = int(parts[2])  # view_reviews_{master_id}
    page = 1
    if len(parts) > 3 and parts[3] == 'page':
        page = int(parts[4])
    
    # Сохраняем master_id в контексте для возврата к услугам
    context.user_data['selected_master_id'] = master_id
    
    db = get_db_from_context(context)
    
    master_profile = db.query(MasterProfile).filter(MasterProfile.id == master_id).first()
    if not master_profile:
        await safe_edit_message_text(query, "❌ Мастер не найден")
        return
    
    # Получаем все отзывы мастера
    from sqlalchemy import func
    
    # Общее количество отзывов
    total_reviews = db.query(func.count(Feedback.id)).select_from(Feedback).join(
        Appointment, Feedback.appointment_id == Appointment.id
    ).filter(
        Appointment.master_id == master_id,
        Feedback.rating.isnot(None)
    ).scalar() or 0
    
    if total_reviews == 0:
        await safe_edit_message_text(
            query,
            f"📝 У мастера {master_profile.business_name or master_profile.user.full_name} пока нет отзывов."
        )
        return
    
    # Средний рейтинг
    avg_rating = db.query(func.avg(Feedback.rating)).select_from(Feedback).join(
        Appointment, Feedback.appointment_id == Appointment.id
    ).filter(
        Appointment.master_id == master_id,
        Feedback.rating.isnot(None)
    ).scalar()
    
    # Пагинация: 5 записей на страницу
    per_page = 5
    total_pages = (total_reviews + per_page - 1) // per_page
    page = min(max(page, 1), total_pages)  # Ограничиваем страницу
    
    offset = (page - 1) * per_page
    
    # Получаем отзывы для текущей страницы
    reviews = db.query(Feedback).select_from(Feedback).join(
        Appointment, Feedback.appointment_id == Appointment.id
    ).filter(
        Appointment.master_id == master_id,
        Feedback.rating.isnot(None)
    ).order_by(Feedback.created_at.desc()).offset(offset).limit(per_page).all()
    
    message = (
        f"⭐ Отзывы мастера: {master_profile.business_name or master_profile.user.full_name}\n\n"
        f"📊 Средний рейтинг: {avg_rating:.1f}/5 ({'⭐' * round(avg_rating)})\n"
        f"📝 Всего отзывов: {total_reviews}\n"
        f"📄 Страница {page} из {total_pages}\n\n"
    )
    
    for review in reviews:
        stars = "⭐" * review.rating if review.rating else "⭐"
        message += (
            f"{'⭐' * (review.rating or 0)} {review.rating or 0}/5\n"
        )
        if review.message:
            message += f"Отзыв: {review.message[:100]}{'...' if len(review.message) > 100 else ''}\n"
        message += f"Дата: {review.created_at.strftime('%d.%m.%Y')}\n\n"
    
    # Кнопки пагинации
    keyboard = []
    nav_buttons = []
    
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"view_reviews_{master_id}_page_{page - 1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"view_reviews_{master_id}_page_{page + 1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопка "Назад" возвращает к услугам мастера
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="services_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)

