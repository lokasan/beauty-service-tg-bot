import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")
TIMEZONE = os.getenv("TIMEZONE", "UTC")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Настройки платежей через Telegram Bot Payments
# Токен провайдера получается от @BotFather в разделе Payments
# Для FreedomPay KG используется тестовый токен от BotFather
TELEGRAM_PAYMENT_PROVIDER_TOKEN = os.getenv("TELEGRAM_PAYMENT_PROVIDER_TOKEN")

# Настройки FreedomPay KG (для справки)
FREEDOMPAY_ACCOUNT = os.getenv("FREEDOMPAY_ACCOUNT", "545158")
FREEDOMPAY_IS_TEST = os.getenv("FREEDOMPAY_IS_TEST", "true").lower() == "true"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

