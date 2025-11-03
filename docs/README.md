# Документация проекта

Эта папка содержит автогенерируемую документацию проекта на основе Sphinx.

## Быстрый старт

### Способ 1: Использование скрипта (Рекомендуется)

**Из корневой папки проекта:**

Windows (PowerShell или CMD):
```bash
python generate_docs.py
```

Или используйте .bat файл:
```bash
generate_docs.bat
```

Linux/Mac:
```bash
python3 generate_docs.py
```

### Способ 2: Прямая генерация через Python

```bash
cd docs
python -m sphinx -b html . _build/html
```

### Способ 3: Через make.bat (Windows)

```bash
cd docs
.\make.bat html
```

**Важно:** В PowerShell обязательно используйте `.\` перед именем скрипта.

### Способ 4: Через Makefile (Linux/Mac)

```bash
cd docs
make html
```

## Установка зависимостей

Если Sphinx еще не установлен:

```bash
pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints
```

Или установите из requirements.txt:

```bash
pip install -r docs/requirements.txt
```

## Просмотр документации

После генерации откройте файл:
```
docs/_build/html/index.html
```

**Windows (PowerShell):**
```powershell
Start-Process "docs\_build\html\index.html"
```

**Windows (CMD):**
```cmd
start docs\_build\html\index.html
```

**Linux/Mac:**
```bash
xdg-open docs/_build/html/index.html
```

## Структура документации

- `index.rst` - главная страница
- `overview.rst` - обзор проекта
- `installation.rst` - установка и настройка
- `modules.rst` - описание модулей (автогенерация)
- `handlers.rst` - обработчики (автогенерация)
- `utils.rst` - утилиты (автогенерация)
- `payments.rst` - система платежей
- `examples.rst` - примеры использования

## Автогенерация

Документация автоматически генерируется из:

- **Docstrings** в коде Python (автоматически)
- **RST файлов** в папке `docs/`
- **Моделей данных** SQLAlchemy

## Обновление документации

После изменения кода:

1. Обновите docstrings в коде (если необходимо)
2. Перегенерируйте документацию:
   ```bash
   python generate_docs.py
   ```
3. Обновите страницу в браузере (F5)

## Решение проблем

### Ошибка "make.bat не найден"

В PowerShell используйте:
```powershell
cd docs
.\make.bat html
```

Или используйте Python напрямую:
```bash
python -m sphinx -b html . _build/html
```

### Ошибка "Sphinx не установлен"

Установите зависимости:
```bash
pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints
```

### Ошибка импорта модулей

Убедитесь, что вы находитесь в корневой папке проекта при запуске скрипта генерации.

## Настройка

Файл `conf.py` содержит все настройки:

- Тема оформления (sphinx_rtd_theme)
- Расширения Sphinx
- Настройки автодокументации
- Пути к модулям проекта
