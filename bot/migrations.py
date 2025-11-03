"""
Миграции базы данных
"""
from sqlalchemy import text, inspect
from bot.database import engine, SessionLocal
import logging

logger = logging.getLogger(__name__)


def migrate_schedule_slots():
    """
    Добавление новых столбцов в таблицу schedule_slots
    """
    db = SessionLocal()
    try:
        # Проверяем, существуют ли уже столбцы
        inspector = inspect(engine)
        
        # Проверяем, существует ли таблица
        if 'schedule_slots' not in inspector.get_table_names():
            logger.info("Таблица schedule_slots не существует, пропускаем миграцию")
            db.commit()
            return
        
        columns = [col['name'] for col in inspector.get_columns('schedule_slots')]
        
        if 'specific_date' not in columns:
            logger.info("Добавление столбца specific_date в schedule_slots")
            db.execute(text("ALTER TABLE schedule_slots ADD COLUMN specific_date DATE"))
            db.commit()
        
        if 'is_day_off' not in columns:
            logger.info("Добавление столбца is_day_off в schedule_slots")
            db.execute(text("ALTER TABLE schedule_slots ADD COLUMN is_day_off BOOLEAN DEFAULT 0"))
            db.commit()
        
        logger.info("Миграция schedule_slots выполнена успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при миграции: {e}")
        db.rollback()
        # Не поднимаем исключение, чтобы бот мог продолжить работу
        logger.warning("Миграция пропущена, возможно таблица уже обновлена")
    finally:
        db.close()


def migrate_invoices():
    """
    Создание таблицы invoices если она не существует
    """
    from bot.models import Invoice
    
    db = SessionLocal()
    try:
        inspector = inspect(engine)
        
        # Проверяем, существует ли таблица
        if 'invoices' not in inspector.get_table_names():
            logger.info("Создание таблицы invoices")
            Invoice.__table__.create(bind=engine, checkfirst=True)
            db.commit()
            logger.info("Таблица invoices создана успешно")
        else:
            logger.info("Таблица invoices уже существует")
        
    except Exception as e:
        logger.error(f"Ошибка при миграции invoices: {e}")
        db.rollback()
        logger.warning("Миграция invoices пропущена")
    finally:
        db.close()


def run_all_migrations():
    """Запуск всех миграций"""
    migrate_schedule_slots()
    migrate_invoices()


if __name__ == "__main__":
    run_all_migrations()

