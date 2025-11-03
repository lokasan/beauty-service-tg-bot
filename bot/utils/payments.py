"""
Утилиты для работы с платежами через Telegram Bot Payments (FreedomPay KG)
"""
import logging
from typing import Optional, Dict, List
from telegram import LabeledPrice

logger = logging.getLogger(__name__)

from bot.config import TELEGRAM_PAYMENT_PROVIDER_TOKEN


def init_payments():
    """Инициализация платежной системы"""
    if TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        logger.info("Telegram Bot Payments (FreedomPay KG) инициализирована")
    else:
        logger.warning("Telegram Bot Payments не настроена: отсутствует TELEGRAM_PAYMENT_PROVIDER_TOKEN")


def create_payment(
    amount: float,
    description: str,
    return_url: str,
    invoice_id: int,
    payment_method: str = "card"
) -> Optional[Dict]:
    """
    Создание платежа через Telegram Bot Payments (FreedomPay KG)
    
    Args:
        amount: Сумма платежа
        description: Описание платежа
        return_url: URL для возврата после оплаты (не используется для Telegram Payments)
        invoice_id: ID чека в базе данных
        payment_method: Метод оплаты ("card" или "sbp") - не используется, Telegram выбирает сам
    
    Returns:
        Словарь с payment_id (invoice_id) и payment_url (None, т.к. используется sendInvoice)
    """
    try:
        if not TELEGRAM_PAYMENT_PROVIDER_TOKEN:
            logger.error("Telegram Bot Payments не настроена")
            return None
        
        # Telegram Bot Payments работает через sendInvoice
        # Возвращаем invoice_id для использования в sendInvoice
        logger.info(f"Подготовка платежа через Telegram Bot Payments для чека {invoice_id}")
        
        return {
            "payment_id": str(invoice_id),
            "payment_url": None,  # Не используется для Telegram Payments
            "status": "pending",
            "redsys_url": None,
            "html_form": None
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания платежа через Telegram Bot Payments: {e}")
        return None


def check_payment_status(payment_id: str) -> Optional[str]:
    """
    Проверка статуса платежа в Telegram Bot Payments
    
    Args:
        payment_id: ID платежа (invoice_id или pre_checkout_query_id)
    
    Returns:
        Статус платежа или None при ошибке
    """
    try:
        # Telegram Bot Payments отправляет уведомления через PreCheckoutQuery
        # Статус проверяется через обработчик pre_checkout_query
        logger.debug(f"Проверка статуса платежа {payment_id} через Telegram Bot Payments")
        return "pending"
        
    except Exception as e:
        logger.error(f"Ошибка проверки статуса платежа {payment_id}: {e}")
        return None


def verify_payment_notification(data: dict, signature: str = None) -> bool:
    """
    Проверка уведомления от Telegram Bot Payments
    
    Args:
        data: Данные уведомления
        signature: Подпись (если требуется)
    
    Returns:
        True если уведомление валидно
    """
    try:
        # Telegram Bot Payments проверяется автоматически через Bot API
        # Все уведомления от Telegram считаются валидными
        required_fields = ["invoice_payload"]
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"Отсутствует обязательное поле {field} в уведомлении")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка проверки уведомления: {e}")
        return False
