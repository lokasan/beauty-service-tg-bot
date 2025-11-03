# Публикация документации на GitHub Pages

## Автоматическая публикация через GitHub Actions

Документация будет автоматически генерироваться и публиковаться при каждом push в ветки `main` или `master`.

## Настройка GitHub Pages

### Шаг 1: Включите GitHub Pages в настройках репозитория

1. Откройте ваш репозиторий на GitHub
2. Перейдите в **Settings** (Настройки)
3. В боковом меню найдите раздел **Pages**
4. В разделе **Source** выберите:
   - **Source**: `Deploy from a branch`
   - **Branch**: `gh-pages` (если используется старый метод)
   - ИЛИ **Source**: `GitHub Actions` (для нового метода через Actions)

### Шаг 2: Push изменений в репозиторий

```bash
git add .github/workflows/docs.yml
git add .gitignore
git add README.md
git commit -m "Add GitHub Pages deployment for documentation"
git push origin main
```

### Шаг 3: Проверьте статус деплоя

1. Откройте вкладку **Actions** в вашем репозитории
2. Найдите workflow "Build and Deploy Documentation"
3. Дождитесь завершения (обычно 2-3 минуты)

### Шаг 4: Доступ к документации

После успешного деплоя документация будет доступна по адресу:

```
https://ваш-username.github.io/master-session/
```

или

```
https://ваш-username.github.io/название-репозитория/
```

## Ручная публикация (альтернативный способ)

Если автоматическая публикация не работает, можно использовать ручной метод:

### Метод 1: Через ghp-import

```bash
# Установите ghp-import
pip install ghp-import

# Сгенерируйте документацию
python generate_docs.py

# Опубликуйте на GitHub Pages
ghp-import -n -p -f docs/_build/html
```

### Метод 2: Через отдельную ветку gh-pages

```bash
# Сгенерируйте документацию
python generate_docs.py

# Переключитесь на ветку gh-pages
git checkout --orphan gh-pages
git rm -rf .

# Скопируйте содержимое _build/html
cp -r docs/_build/html/* .

# Закоммитьте и запушьте
git add .
git commit -m "Deploy documentation"
git push origin gh-pages

# Вернитесь на основную ветку
git checkout main
```

## Обновление документации

Документация автоматически обновится при:

- Push изменений в папку `docs/`
- Push изменений в папку `bot/`
- Изменении файла `.github/workflows/docs.yml`

Также можно вручную запустить workflow:

1. Откройте вкладку **Actions**
2. Выберите workflow "Build and Deploy Documentation"
3. Нажмите **Run workflow**

## Решение проблем

### Документация не обновляется

1. Проверьте статус workflow в разделе **Actions**
2. Убедитесь, что GitHub Pages включен в настройках репозитория
3. Проверьте логи workflow на наличие ошибок

### Ошибки при генерации документации

1. Проверьте, что все зависимости установлены
2. Убедитесь, что путь к модулям в `conf.py` правильный
3. Проверьте логи в разделе **Actions**

### Ссылки не работают

1. Убедитесь, что файл `.nojekyll` существует в папке `docs/`
2. Проверьте, что все статические файлы включены в репозиторий

## Структура файлов

```
.github/
  workflows/
    docs.yml          # Workflow для автоматической публикации
docs/
  .nojekyll           # Отключает Jekyll для GitHub Pages
  conf.py             # Конфигурация Sphinx
  *.rst               # Исходные файлы документации
  _build/html/        # Сгенерированные HTML файлы (в .gitignore)
```

