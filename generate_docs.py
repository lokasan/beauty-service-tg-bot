#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для генерации HTML документации проекта
"""
import subprocess
import sys
import os

def main():
    """Генерация документации"""
    print("=" * 50)
    print("Генерация HTML документации")
    print("=" * 50)
    
    # Проверка установки Sphinx
    print("\n1. Проверка зависимостей...")
    try:
        import sphinx
        print("   ✓ Sphinx установлен")
    except ImportError:
        print("   ✗ Sphinx не установлен. Установка...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", 
                       "sphinx", "sphinx-rtd-theme", "sphinx-autodoc-typehints"])
    
    # Переход в папку docs
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    if not os.path.exists(docs_dir):
        print(f"   ✗ Папка {docs_dir} не найдена")
        return 1
    
    os.chdir(docs_dir)
    print(f"   ✓ Переход в папку: {docs_dir}")
    
    # Генерация документации
    print("\n2. Генерация HTML документации...")
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "html", ".", "_build/html"],
        capture_output=False
    )
    
    if result.returncode != 0:
        print("\n   ✗ Ошибка генерации документации")
        return 1
    
    # Определение пути к index.html
    index_path = os.path.join(os.getcwd(), "_build", "html", "index.html")
    index_path_abs = os.path.abspath(index_path)
    
    print("\n" + "=" * 50)
    print("Документация успешно сгенерирована!")
    print("=" * 50)
    print(f"\nФайл документации: {index_path_abs}")
    print("\nДля открытия в браузере:")
    
    # Попытка открыть в браузере
    if os.name == 'nt':  # Windows
        print(f'   start "{index_path_abs}"')
        try:
            os.startfile(index_path_abs)
            print("\n   ✓ Документация открыта в браузере")
        except Exception as e:
            print(f"   ⚠ Не удалось открыть автоматически: {e}")
    else:  # Linux/Mac
        print(f"   xdg-open {index_path_abs}")
        try:
            subprocess.run(["xdg-open", index_path_abs])
            print("\n   ✓ Документация открыта в браузере")
        except Exception as e:
            print(f"   ⚠ Не удалось открыть автоматически: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())


