@echo off
echo ====================================
echo    BeForward Parser Bot
echo ====================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo ОШИБКА: Виртуальное окружение не найдено!
    echo Сначала запустите install.bat
    echo.
    pause
    exit /b 1
)

echo Активация venv...
call venv\Scripts\activate.bat

echo Запуск бота...
echo.
python rus_bot.py

pause

