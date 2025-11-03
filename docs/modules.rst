Модули проекта
==============

Основные модули
---------------

.. note::
   Модуль ``bot.main`` исключен из автогенерации из-за зависимости от инициализации логирования при импорте.
   Описание модуля предоставлено вручную ниже.

.. automodule:: bot.config
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: bot.database
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: bot.models
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: bot.migrations
   :members:
   :undoc-members:
   :show-inheritance:

Подробное описание модулей
--------------------------

bot.main
~~~~~~~~

Главный модуль бота. Содержит:

* Функцию ``main()`` - точка входа приложения
* Регистрацию всех обработчиков команд и callback queries
* Инициализацию базы данных и миграций
* Настройку планировщика уведомлений
* Обработчик ошибок

bot.config
~~~~~~~~~~

Модуль конфигурации. Содержит настройки:

* ``BOT_TOKEN`` - токен Telegram бота
* ``TELEGRAM_PAYMENT_PROVIDER_TOKEN`` - токен провайдера платежей
* ``DATABASE_URL`` - URL подключения к БД
* ``TIMEZONE`` - часовой пояс
* ``LOG_LEVEL`` - уровень логирования

Все настройки загружаются из переменных окружения (файл ``.env``).

bot.database
~~~~~~~~~~~~

Модуль работы с базой данных:

* ``init_db()`` - инициализация БД и создание таблиц
* ``get_db_session()`` - получение сессии БД для использования в handlers

bot.models
~~~~~~~~~~

SQLAlchemy модели данных:

* ``User`` - пользователи бота (мастера и клиенты)
* ``MasterProfile`` - профили мастеров
* ``Service`` - услуги мастеров
* ``ScheduleSlot`` - слоты расписания
* ``Appointment`` - записи клиентов
* ``Invoice`` - чеки на оплату
* ``Notification`` - запланированные уведомления
* ``Feedback`` - отзывы пользователей

bot.migrations
~~~~~~~~~~~~~~

Модуль для выполнения миграций БД:

* ``migrate_schedule_slots()`` - добавление полей в таблицу расписания
* ``migrate_invoices()`` - создание таблицы чеков
* ``run_all_migrations()`` - выполнение всех миграций

Миграции выполняются автоматически при запуске бота.

