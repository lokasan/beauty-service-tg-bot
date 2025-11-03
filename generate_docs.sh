#!/bin/bash
# Скрипт для генерации HTML документации

echo "Установка зависимостей для документации..."
pip install -q sphinx sphinx-rtd-theme sphinx-autodoc-typehints

echo ""
echo "Генерация документации..."
cd docs
python -m sphinx -b html . _build/html

echo ""
echo "Документация успешно сгенерирована!"
echo "Откройте файл docs/_build/html/index.html в браузере."
echo ""

