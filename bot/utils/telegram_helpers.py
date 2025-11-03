"""
Вспомогательные функции для работы с Telegram API
"""
from telegram import Update
from telegram.error import BadRequest
import logging

logger = logging.getLogger(__name__)


async def safe_edit_message_text(query, text: str, reply_markup=None, parse_mode=None):
    """
    Безопасное редактирование сообщения с обработкой ошибок
    
    Args:
        query: CallbackQuery объект
        text: Текст сообщения
        reply_markup: Клавиатура (опционально)
        parse_mode: Режим парсинга (опционально)
    
    Returns:
        True если успешно, False если ошибка
    """
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except BadRequest as e:
        error_message = str(e).lower()
        
        # Сообщение не изменилось
        if "message is not modified" in error_message:
            logger.debug(f"Сообщение не изменилось: {e}")
            await query.answer()
            return True
        
        # Сообщение слишком длинное
        if "message is too long" in error_message:
            logger.warning(f"Сообщение слишком длинное: {len(text)} символов")
            # Обрезаем сообщение до 4096 символов
            max_length = 4096 - 50  # Оставляем запас
            truncated_text = text[:max_length] + "\n\n... (сообщение обрезано)"
            try:
                await query.edit_message_text(
                    text=truncated_text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return True
            except Exception as e2:
                logger.error(f"Ошибка при обрезке сообщения: {e2}")
                await query.answer("Ошибка: сообщение слишком длинное")
                return False
        
        # Другие ошибки BadRequest
        logger.warning(f"BadRequest при редактировании сообщения: {e}")
        await query.answer("Ошибка обновления сообщения")
        return False
    
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании сообщения: {e}")
        await query.answer("Произошла ошибка")
        return False



