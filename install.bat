@echo off
echo ====================================
echo    BeForward Parser Bot - Setup
echo ====================================
echo.

echo [1/4] Создание виртуального окружения...
python -m venv venv
if %errorlevel% neq 0 (
    echo ОШИБКА: Не удалось создать venv
    pause
    exit /b 1
)
echo OK
echo.

echo [2/4] Активация venv...
call venv\Scripts\activate.bat
echo OK
echo.

echo [3/4] Обновление pip...
python -m pip install --upgrade pip
echo OK
echo.

echo [4/4] Установка зависимостей...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ОШИБКА: Не удалось установить зависимости
    pause
    exit /b 1
)
echo OK
echo.

echo ====================================
echo    Установка завершена!
echo ====================================
echo.
echo Для запуска бота используйте: run.bat
echo Или вручную:
echo   1. venv\Scripts\activate
echo   2. python rus_bot.py
echo.
pause


