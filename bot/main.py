"""
Главный файл Telegram-бота для записи к мастерам
"""
import logging
import sys
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from bot.config import BOT_TOKEN, LOG_LEVEL
from bot.database import init_db, get_db_session
from bot.handlers import common, master, client, invoice
from bot.utils.notifications import start_scheduler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL),
    handlers=[
        logging.FileHandler('bot/logs/bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже или обратитесь в поддержку."
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения об ошибке: {e}")


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Централизованный обработчик callback queries"""
    query = update.callback_query
    
    if query.data == "ignore":
        await query.answer()
        return
    
    if query.data == "start_menu":
        await common.start_command(update, context)
        return
    
    if query.data == "services_back":
        # Возврат к услугам
        master_id = context.user_data.get('selected_master_id')
        if master_id:
            await client.show_services(update, context, master_id)
        return
    
    if query.data == "calendar_back":
        # Возврат к календарю
        today = __import__('datetime').datetime.now()
        from bot.utils.calendar import get_month_keyboard
        keyboard = get_month_keyboard(today.year, today.month)
        service = context.user_data.get('selected_service')
        message = (
            f"📅 Выберите дату для услуги:\n\n"
            f"🛠 {service.name}\n"
            f"💰 {service.price} ₽\n"
            f"⏱ {service.duration_minutes} мин."
        )
        await query.edit_message_text(message, reply_markup=keyboard)
        return
    
    # Обработка callback для мастеров
    if query.data == "become_master":
        await master.become_master_callback(update, context)
    elif query.data == "master_services":
        await master.master_services_callback(update, context)
    elif query.data == "service_create":
        await master.service_create_start(update, context)
    elif query.data.startswith("service_edit_form_"):
        await master.service_edit_form_callback(update, context)
    elif query.data.startswith("service_edit_"):
        await master.service_edit_callback(update, context)
    elif query.data.startswith("service_toggle_hidden_"):
        await master.service_toggle_hidden(update, context)
    elif query.data.startswith("service_delete_"):
        await master.service_delete(update, context)
    elif query.data == "master_link":
        await master.master_link_callback(update, context)
    elif query.data == "master_appointments":
        await master.master_appointments_callback(update, context)
    elif query.data == "master_settings":
        await master.master_settings_callback(update, context)
    elif query.data == "schedule_settings":
        await master.schedule_settings_callback(update, context)
    elif query.data == "schedule_weekly":
        await master.schedule_weekly_callback(update, context)
    elif query.data == "schedule_calendar_month":
        await master.schedule_calendar_month_callback(update, context)
    elif query.data.startswith("schedule_month_"):
        await master.schedule_month_navigation(update, context)
    elif query.data.startswith("schedule_edit_month_"):
        await master.schedule_edit_month_callback(update, context)
    elif query.data.startswith("schedule_edit_date_"):
        await master.schedule_edit_date_callback(update, context)
    elif query.data.startswith("schedule_view_date_"):
        await master.schedule_view_date_callback(update, context)
    elif query.data.startswith("schedule_day_"):
        await master.schedule_day_callback(update, context)
    elif query.data.startswith("schedule_set_work_hours_"):
        await master.schedule_set_work_hours_start(update, context)
    elif query.data.startswith("schedule_remove_day_"):
        await master.schedule_remove_day(update, context)
    elif query.data.startswith("schedule_remove_slot_"):
        await master.schedule_remove_day(update, context)
    elif query.data.startswith("schedule_set_day_off_"):
        await master.schedule_set_day_off(update, context)
    elif query.data.startswith("schedule_remove_date_"):
        await master.schedule_remove_date(update, context)
    elif query.data.startswith("schedule_set_time_"):
        await master.schedule_set_time_start(update, context)
    elif query.data.startswith("create_invoice_"):
        await invoice.create_invoice_callback(update, context)
    elif query.data.startswith("payment_method_"):
        await invoice.payment_method_callback(update, context)
    elif query.data.startswith("complete_appointment_"):
        await master.complete_appointment_callback(update, context)
    elif query.data.startswith("pay_invoice_"):
        await invoice.pay_invoice_callback(update, context)
    elif query.data.startswith("check_payment_"):
        await invoice.check_payment_status_callback(update, context)
    
    # Обработка callback для клиентов
    elif query.data == "book_by_link":
        await client.book_by_link_start(update, context)
    elif query.data.startswith("service_select_"):
        await client.service_select_callback(update, context)
    elif query.data.startswith("date_"):
        await client.date_selected_callback(update, context)
    elif query.data.startswith("time_"):
        await client.time_selected_callback(update, context)
    elif query.data == "appointment_confirm":
        await client.appointment_confirm_callback(update, context)
    elif query.data.startswith("month_"):
        await client.month_navigation_callback(update, context)
    elif query.data == "feedback":
        await common.feedback_callback(update, context)
    elif query.data == "client_appointments" or query.data.startswith("client_appointments_page_"):
        await client.client_appointments_callback(update, context)
    elif query.data.startswith("cancel_appointment_"):
        await client.cancel_appointment_callback(update, context)
    elif query.data.startswith("leave_feedback_"):
        await client.leave_feedback_callback(update, context)
    elif query.data.startswith("rating_"):
        await client.rating_callback(update, context)
    elif query.data.startswith("skip_feedback_text_"):
        await client.skip_feedback_text_callback(update, context)
    elif query.data.startswith("view_reviews_"):
        await client.view_master_reviews_callback(update, context)
    elif query.data == "master_reviews" or query.data.startswith("master_reviews_page_"):
        await master.master_reviews_callback(update, context)
    elif query.data.startswith("master_link_from_appointment_"):
        await client.show_master_profile_from_appointment(update, context)
    elif query.data == "settings_notifications":
        await master.settings_notifications_callback(update, context)
    elif query.data.startswith("set_notif_"):
        await master.set_notification_hours(update, context)
    elif query.data.startswith("edit_service_name_"):
        await master.service_edit_name_start(update, context)
    elif query.data.startswith("edit_service_description_"):
        await master.service_edit_description_start(update, context)
    elif query.data.startswith("edit_service_price_"):
        await master.service_edit_price_start(update, context)
    elif query.data.startswith("edit_service_duration_"):
        await master.service_edit_duration_start(update, context)
    else:
        # Неизвестный callback
        await query.answer("Неизвестная команда")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Централизованный обработчик сообщений"""
    # Проверка на получение контакта (телефона)
    if update.message.contact and context.user_data.get('phone_requested'):
        await client.handle_phone_contact(update, context)
        return
    
    # Проверка на оставление отзыва
    if context.user_data.get('leaving_feedback'):
        await client.handle_feedback_text(update, context)
        return
    
    # Проверка на настройку расписания
    if context.user_data.get('setting_schedule'):
        schedule_data = context.user_data.get('schedule_data', {})
        
        if 'start_time' not in schedule_data:
            await master.handle_schedule_start_time(update, context)
        elif 'end_time' not in schedule_data:
            await master.handle_schedule_end_time(update, context)
        return
    
    # Проверка на настройку индивидуального расписания для даты
    if context.user_data.get('setting_schedule_date'):
        schedule_data = context.user_data.get('schedule_data', {})
        
        if 'start_time' not in schedule_data:
            await master.handle_schedule_date_start_time(update, context)
        elif 'end_time' not in schedule_data:
            await master.handle_schedule_date_end_time(update, context)
        return
    
    # Проверка на создание услуги
    if context.user_data.get('creating_service'):
        service_data = context.user_data.get('service_data', {})
        
        if 'name' not in service_data:
            await master.handle_service_name(update, context)
        elif 'description' not in service_data:
            await master.handle_service_description(update, context)
        elif 'price' not in service_data:
            await master.handle_service_price(update, context)
        else:
            await master.handle_service_duration(update, context)
        return
    
    # Проверка на редактирование услуги
    if context.user_data.get('editing_service'):
        edit_field = context.user_data.get('editing_field')
        service_id = context.user_data.get('editing_service_id')
        
        if edit_field == 'name':
            await master.handle_service_name_edit(update, context, service_id)
        elif edit_field == 'description':
            await master.handle_service_description_edit(update, context, service_id)
        elif edit_field == 'price':
            await master.handle_service_price_edit(update, context, service_id)
        elif edit_field == 'duration':
            await master.handle_service_duration_edit(update, context, service_id)
        return
    
    # Проверка на ожидание ссылки
    if context.user_data.get('waiting_for_link'):
        await client.handle_link_input(update, context)
        return
    
    # Проверка на обратную связь
    if context.user_data.get('waiting_for_feedback'):
        await common.handle_feedback(update, context)
        return


def main():
    """Главная функция запуска бота"""
    logger.info("Запуск Telegram-бота...")
    
    # Инициализация БД
    init_db()
    logger.info("База данных инициализирована")
    
    # Выполнение миграций
    try:
        from bot.migrations import run_all_migrations
        run_all_migrations()
        logger.info("Миграции выполнены")
    except Exception as e:
        logger.warning(f"Ошибка при выполнении миграций (можно игнорировать если база новая): {e}")
    
    # Инициализация платежной системы (Telegram Bot Payments / FreedomPay KG)
    try:
        from bot.utils.payments import init_payments
        init_payments()
        logger.info("Платежная система инициализирована")
    except Exception as e:
        logger.warning(f"Ошибка инициализации платежной системы: {e}")
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавление сессии БД в bot_data
    application.bot_data['db_session'] = get_db_session
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", common.start_command))
    application.add_handler(CommandHandler("help", common.help_command))
    
    # Регистрация обработчика callback queries
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Регистрация обработчика сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    # Обработчик контактов (для запроса телефона)
    application.add_handler(MessageHandler(filters.CONTACT, message_handler))
    
    # Регистрация обработчиков Telegram Bot Payments
    # Обработчик PreCheckoutQuery (для подтверждения оплаты перед оплатой)
    from telegram.ext import PreCheckoutQueryHandler
    application.add_handler(PreCheckoutQueryHandler(invoice.pre_checkout_query_handler))
    # Обработчик successful_payment (после успешной оплаты)
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, invoice.successful_payment_handler))
    
    # Логируем все входящие сообщения для отладки платежей
    async def log_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Логирование всех сообщений для отладки"""
        if update.message and update.message.successful_payment:
            logger.info(f"📥 Получено successful_payment: {update.message.successful_payment.invoice_payload}")
        elif update.pre_checkout_query:
            logger.info(f"📥 Получен PreCheckoutQuery: {update.pre_checkout_query.invoice_payload}")
    
    # Добавляем временный обработчик для логирования (можно удалить после отладки)
    application.add_handler(MessageHandler(filters.ALL, log_all_messages), group=100)
    
    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)
    
    # Запуск планировщика уведомлений
    try:
        from bot.utils.notifications import start_scheduler
        start_scheduler(application.bot, get_db_session)
    except Exception as e:
        logger.warning(f"Не удалось запустить планировщик уведомлений: {e}")
    
    # Запуск бота
    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

