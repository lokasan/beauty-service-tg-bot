"""
Скрипт для ручного запуска миграций базы данных
"""
import logging
from bot.migrations import migrate_schedule_slots

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    print("Запуск миграции базы данных...")
    migrate_schedule_slots()
    print("Миграция завершена!")


