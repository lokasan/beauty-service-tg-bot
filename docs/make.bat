@echo off

REM Command file for Sphinx documentation

set SPHINXBUILD=sphinx-build
set SOURCEDIR=.
set BUILDDIR=_build

if "%1" == "" goto help

REM Проверка через Python модуль (более надежно)
python -m sphinx --help >nul 2>nul
if errorlevel 1 (
	echo.
	echo.Ошибка: Sphinx не установлен или не найден.
	echo.
	echo.Установите Sphinx:
	echo.  pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints
	echo.
	echo.Или используйте Python напрямую:
	echo.  python -m sphinx -b html . _build/html
	echo.
	exit /b 1
)

REM Использование Python модуля для генерации
if "%1" == "html" (
	python -m sphinx -b html %SOURCEDIR% %BUILDDIR%/html %SPHINXOPTS%
	goto end
)

REM Для других команд используем стандартный sphinx-build
%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
goto end

:help
python -m sphinx -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%

:end
