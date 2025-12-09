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


def migrate_feedback():
    """
    Добавление поля master_id в таблицу feedback и изменение message на nullable
    """
    db = SessionLocal()
    try:
        inspector = inspect(engine)
        
        # Проверяем, существует ли таблица
        if 'feedback' not in inspector.get_table_names():
            logger.info("Таблица feedback не существует, пропускаем миграцию")
            db.commit()
            return
        
        columns = [col['name'] for col in inspector.get_columns('feedback')]
        
        # Проверяем, нужно ли добавить master_id
        needs_master_id = 'master_id' not in columns
        
        # Проверяем, существует ли временная таблица от предыдущей миграции
        # Если да, значит миграция была прервана, нужно её завершить
        table_names = inspector.get_table_names()
        has_temp_table = 'feedback_new' in table_names
        
        # В SQLite мы не можем проверить nullable напрямую
        # Поэтому пересоздаем таблицу, если нужно добавить master_id
        # или если таблица была создана до изменений модели (старые таблицы могли иметь NOT NULL для message)
        # Это безопасно, так как мы копируем все данные
        needs_migration = needs_master_id
        
        # Если временная таблица существует, значит миграция была прервана
        # Нужно сначала удалить её и пересоздать
        if has_temp_table:
            logger.info("Обнаружена временная таблица feedback_new от прерванной миграции, удаляем её")
            db.execute(text("DROP TABLE IF EXISTS feedback_new"))
            db.commit()
            needs_migration = True
        
        # Если master_id уже есть, но таблица может иметь NOT NULL для message,
        # проверяем, можем ли мы вставить NULL
        if not needs_migration:
            try:
                # Пробуем вставить тестовую запись с NULL в message
                # Если получим ошибку, значит нужно мигрировать
                db.execute(text("""
                    INSERT INTO feedback (user_id, appointment_id, master_id, message, rating, created_at)
                    VALUES (-1, -1, -1, NULL, 1, datetime('now'))
                """))
                # Если вставка прошла успешно, значит структура правильная
                db.execute(text("DELETE FROM feedback WHERE user_id = -1"))
                db.commit()
                logger.info("Таблица feedback уже имеет правильную структуру (message nullable)")
            except Exception as e:
                # Если ошибка, значит message имеет NOT NULL, нужно мигрировать
                logger.info(f"Обнаружено ограничение NOT NULL для message: {e}")
                db.rollback()
                needs_migration = True
        
        # Если нужно добавить master_id или таблица может иметь неправильную структуру,
        # всегда выполняем миграцию для гарантии правильной структуры
        # Это безопасно, так как мы копируем все данные
        if needs_migration:
            logger.info("Начало миграции feedback: добавление master_id и изменение message на nullable")
            
            # Создаем временную таблицу с правильной структурой
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS feedback_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    appointment_id INTEGER REFERENCES appointments(id),
                    master_id INTEGER REFERENCES master_profiles(id),
                    message TEXT,
                    rating INTEGER,
                    created_at DATETIME NOT NULL
                )
            """))
            
            # Копируем данные из старой таблицы
            if needs_master_id:
                # Если нужно добавить master_id, получаем его из appointments
                db.execute(text("""
                    INSERT INTO feedback_new (id, user_id, appointment_id, master_id, message, rating, created_at)
                    SELECT 
                        f.id,
                        f.user_id,
                        f.appointment_id,
                        a.master_id,
                        f.message,
                        f.rating,
                        f.created_at
                    FROM feedback f
                    LEFT JOIN appointments a ON f.appointment_id = a.id
                """))
            else:
                # Если master_id уже есть, просто копируем данные
                db.execute(text("""
                    INSERT INTO feedback_new (id, user_id, appointment_id, master_id, message, rating, created_at)
                    SELECT id, user_id, appointment_id, master_id, message, rating, created_at
                    FROM feedback
                """))
            
            # Удаляем старую таблицу
            db.execute(text("DROP TABLE feedback"))
            
            # Переименовываем новую таблицу
            db.execute(text("ALTER TABLE feedback_new RENAME TO feedback"))
            
            db.commit()
            logger.info("Миграция feedback выполнена успешно: добавлен master_id, message теперь nullable")
        else:
            logger.info("Таблица feedback уже имеет правильную структуру")
        
    except Exception as e:
        logger.error(f"Ошибка при миграции feedback: {e}")
        db.rollback()
        logger.warning("Миграция feedback пропущена")
    finally:
        db.close()


def run_all_migrations():
    """Запуск всех миграций"""
    migrate_schedule_slots()
    migrate_invoices()
    migrate_feedback()


if __name__ == "__main__":
    run_all_migrations()

