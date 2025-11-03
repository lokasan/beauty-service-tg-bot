Утилиты (Utils)
===============

Вспомогательные модули для работы бота.

Календари
---------

.. automodule:: bot.utils.calendar
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: bot.utils.schedule_calendar
   :members:
   :undoc-members:
   :show-inheritance:

Расписание
----------

.. automodule:: bot.utils.schedule
   :members:
   :undoc-members:
   :show-inheritance:

Уведомления
-----------

.. automodule:: bot.utils.notifications
   :members:
   :undoc-members:
   :show-inheritance:

Валидация
---------

.. automodule:: bot.utils.validators
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: bot.utils.forbidden_categories
   :members:
   :undoc-members:
   :show-inheritance:

Вспомогательные функции
-----------------------

.. automodule:: bot.utils.telegram_helpers
   :members:
   :undoc-members:
   :show-inheritance:

Описание модулей
----------------

calendar.py
~~~~~~~~~~~

Функции для генерации календарей:

* ``get_calendar_keyboard()`` - генерация клавиатуры календаря для выбора даты
* ``get_time_keyboard()`` - генерация клавиатуры для выбора времени

schedule_calendar.py
~~~~~~~~~~~~~~~~~~~~

Календарь для настройки расписания мастера:

* ``get_schedule_month_keyboard()`` - генерация месячного календаря расписания
* Отображение индивидуальных расписаний и выходных дней

schedule.py
~~~~~~~~~~~

Логика работы с расписанием:

* ``is_time_in_schedule()`` - проверка, работает ли мастер в указанное время
* ``get_available_time_slots()`` - получение доступных временных слотов для записи

Учитывает:
- Еженедельное расписание
- Индивидуальные расписания для конкретных дней
- Выходные дни
- Занятые записи

notifications.py
~~~~~~~~~~~~~~~~

Система уведомлений:

* ``schedule_notifications()`` - планирование уведомлений для записи
* ``send_notification()`` - отправка уведомления пользователю
* ``process_pending_notifications()`` - обработка запланированных уведомлений

Типы уведомлений:
- Подтверждение записи (мгновенно)
- Напоминание (настраиваемое время)
- Отмена записи

validators.py
~~~~~~~~~~~~~

Функции валидации:

* ``validate_price()`` - проверка цены услуги
* ``validate_duration()`` - проверка длительности услуги
* ``check_appointment_overlap()`` - проверка пересечения записей
* ``generate_unique_link()`` - генерация уникальной ссылки мастера

forbidden_categories.py
~~~~~~~~~~~~~~~~~~~~~~~

Проверка запрещенных категорий услуг:

* ``check_forbidden_category()`` - проверка названия услуги на запрещенные категории
* Список запрещенных категорий по странам

telegram_helpers.py
~~~~~~~~~~~~~~~~~~~

Вспомогательные функции для работы с Telegram API:

* ``safe_edit_message_text()`` - безопасное редактирование сообщения с обработкой ошибок

Обрабатывает:
- "Message is not modified" ошибку
- "Message is too long" ошибку
- Другие ошибки Telegram API

