"""
Модуль управления уведомлениями
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from bot.models import Appointment, Notification, NotificationType
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def send_notification(bot: Bot, chat_id: int, message: str):
    """Отправка уведомления пользователю"""
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        logger.info(f"Уведомление отправлено пользователю {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю {chat_id}: {e}")


async def send_confirmation_notification(bot: Bot, appointment: Appointment):
    """Отправка уведомления о подтверждении записи"""
    client = appointment.client
    service = appointment.service
    master = appointment.master_profile
    
    message = (
        f"✅ Ваша запись подтверждена!\n\n"
        f"📅 Дата и время: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"🛠 Услуга: {service.name}\n"
        f"💰 Стоимость: {service.price} ₽\n"
        f"⏱ Длительность: {service.duration_minutes} мин.\n"
        f"👤 Мастер: {master.business_name or master.user.full_name}\n\n"
        f"Мы напомним вам о записи заранее."
    )
    
    await send_notification(bot, client.telegram_id, message)


async def send_reminder_notification(bot: Bot, appointment: Appointment):
    """Отправка напоминания о записи"""
    client = appointment.client
    service = appointment.service
    
    message = (
        f"🔔 Напоминание о записи\n\n"
        f"📅 Дата и время: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"🛠 Услуга: {service.name}\n"
        f"⏱ Длительность: {service.duration_minutes} мин.\n\n"
        f"Не забудьте о встрече!"
    )
    
    await send_notification(bot, client.telegram_id, message)


async def send_cancellation_notification(bot: Bot, appointment: Appointment, cancelled_by: str = "master"):
    """Отправка уведомления об отмене записи"""
    client = appointment.client
    service = appointment.service
    
    if cancelled_by == "master":
        message = (
            f"❌ Ваша запись отменена мастером\n\n"
            f"📅 Дата: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"🛠 Услуга: {service.name}\n\n"
            f"Вы можете записаться на другое время."
        )
        await send_notification(bot, client.telegram_id, message)
    else:
        # Уведомление мастеру об отмене клиентом
        master_user = appointment.master_profile.user
        message = (
            f"❌ Клиент отменил запись\n\n"
            f"📅 Дата: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"🛠 Услуга: {service.name}\n"
            f"👤 Клиент: {appointment.client_name or client.full_name}\n"
        )
        await send_notification(bot, master_user.telegram_id, message)


def schedule_notifications(
    db: Session,
    appointment: Appointment,
    reminder_hours: int = 24
):
    """
    Планирование уведомлений для записи
    
    Args:
        db: Сессия БД
        appointment: Запись
        reminder_hours: За сколько часов напоминать
    """
    # Планирование напоминания (уведомление о подтверждении отправляется сразу)
    reminder_time = appointment.start_time - timedelta(hours=reminder_hours)
    if reminder_time > datetime.utcnow():
        reminder_notif = Notification(
            appointment_id=appointment.id,
            notification_type=NotificationType.REMINDER,
            scheduled_for=reminder_time,
            is_sent=False
        )
        db.add(reminder_notif)
        db.commit()
        logger.info(f"Напоминание запланировано для записи {appointment.id}")


async def process_pending_notifications(bot: Bot, db_func):
    """Обработка запланированных уведомлений"""
    from bot.database import get_db_session
    
    if callable(db_func):
        db = db_func()
    else:
        db = db_func
    
    try:
        now = datetime.utcnow()
        
        pending_notifications = db.query(Notification).filter(
            Notification.is_sent == False,
            Notification.scheduled_for <= now
        ).all()
        
        for notif in pending_notifications:
            appointment = notif.appointment
            
            if notif.notification_type == NotificationType.CONFIRMATION:
                await send_confirmation_notification(bot, appointment)
            elif notif.notification_type == NotificationType.REMINDER:
                await send_reminder_notification(bot, appointment)
            elif notif.notification_type == NotificationType.CANCELLATION:
                await send_cancellation_notification(bot, appointment)
            
            notif.is_sent = True
            notif.sent_at = now
        
        db.commit()
    except Exception as e:
        logger.error(f"Ошибка обработки уведомлений: {e}")
        db.rollback()
    finally:
        db.close()


def start_scheduler(bot: Bot, db_func):
    """Запуск планировщика уведомлений"""
    scheduler.add_job(
        process_pending_notifications,
        'interval',
        minutes=5,
        args=[bot, db_func],
        id='process_notifications',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Планировщик уведомлений запущен")

