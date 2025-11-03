Установка и настройка
=====================

Требования
----------

* Python 3.8 или выше
* pip (менеджер пакетов Python)
* Telegram Bot Token от @BotFather
* Telegram Payment Provider Token для FreedomPay KG

Установка зависимостей
----------------------

Клонируйте репозиторий или скачайте проект, затем установите зависимости:

.. code-block:: bash

   pip install -r requirements.txt

Необходимые пакеты:

* ``python-telegram-bot==20.7`` - для работы с Telegram Bot API
* ``python-dotenv==1.0.0`` - для загрузки переменных окружения
* ``sqlalchemy==2.0.23`` - ORM для работы с базой данных
* ``apscheduler==3.10.4`` - для планирования уведомлений
* ``pytz==2023.3`` - для работы с часовыми поясами
* ``requests==2.31.0`` - для HTTP запросов

Настройка переменных окружения
-------------------------------

1. Скопируйте файл ``env.example`` в ``.env``:

   **Windows (CMD):**

   .. code-block:: bash

      copy env.example .env

   **Windows (PowerShell):**

   .. code-block:: powershell

      Copy-Item env.example .env

   **Linux/Mac:**

   .. code-block:: bash

      cp env.example .env

2. Откройте файл ``.env`` и заполните необходимые параметры:

.. code-block:: text

   BOT_TOKEN=your_bot_token_here
   TELEGRAM_PAYMENT_PROVIDER_TOKEN=your_provider_token_from_botfather
   FREEDOMPAY_ACCOUNT=545158
   FREEDOMPAY_IS_TEST=true
   DATABASE_URL=sqlite:///./bot.db
   TIMEZONE=UTC
   LOG_LEVEL=INFO

Получение токенов
-----------------

BOT_TOKEN
~~~~~~~~~

1. Откройте Telegram и найдите @BotFather
2. Отправьте команду ``/newbot``
3. Следуйте инструкциям для создания бота
4. Скопируйте полученный токен в ``BOT_TOKEN``

TELEGRAM_PAYMENT_PROVIDER_TOKEN
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. В @BotFather отправьте ``/mybots``
2. Выберите вашего бота
3. Перейдите в раздел "Payments"
4. Выберите FreedomPay KG
5. Получите тестовый токен провайдера
6. Скопируйте токен в ``TELEGRAM_PAYMENT_PROVIDER_TOKEN``

Запуск бота
-----------

Способ 1: Через run.py::

   python run.py

Способ 2: Через модуль Python::

   python -m bot.main

Способ 3: Напрямую::

   python bot/main.py

Первый запуск
-------------

При первом запуске:

1. Создается база данных ``bot.db`` (если не существует)
2. Выполняются миграции БД (если необходимо)
3. Инициализируется платежная система
4. Запускается планировщик уведомлений

Логи
----

Логи сохраняются в файл ``bot/logs/bot.log`` и выводятся в консоль.

Уровни логирования (LOG_LEVEL):

* ``DEBUG`` - подробная информация для отладки
* ``INFO`` - общая информация о работе бота
* ``WARNING`` - предупреждения
* ``ERROR`` - ошибки

Проверка работы
---------------

1. Найдите вашего бота в Telegram
2. Отправьте команду ``/start``
3. Если вы видите меню - бот работает правильно

Если возникли проблемы, проверьте:

* Правильность BOT_TOKEN
* Логи в файле ``bot/logs/bot.log``
* Установлены ли все зависимости

