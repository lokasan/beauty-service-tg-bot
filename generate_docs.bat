@echo off
REM Скрипт для генерации HTML документации

echo Установка зависимостей для документации...
pip install -q sphinx sphinx-rtd-theme sphinx-autodoc-typehints

if errorlevel 1 (
    echo Ошибка установки зависимостей
    pause
    exit /b 1
)

echo.
echo Генерация документации...
cd docs
python -m sphinx -b html . _build/html

if errorlevel 1 (
    echo Ошибка генерации документации
    cd ..
    pause
    exit /b 1
)

cd ..
echo.
echo ========================================
echo Документация успешно сгенерирована!
echo ========================================
echo.
echo Откройте файл: docs\_build\html\index.html
echo.
echo Для открытия в браузере выполните:
echo start docs\_build\html\index.html
echo.
pause

