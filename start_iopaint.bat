@echo off
echo ====================================
echo    IOPaint Server
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

echo Запуск IOPaint сервера с поддержкой RealESRGAN...
echo Порт: 8085
echo.
echo IOPaint будет доступен на http://localhost:8085
echo.
echo ВАЖНО: Не закрывайте это окно!
echo.

REM БЫСТРАЯ МОДЕЛЬ: MIGAN (в 2-3 раза быстрее LaMa)
iopaint start --model=migan --device=cpu --port=8085 --host=127.0.0.1 --enable-realesrgan --realesrgan-model=realesr-general-x4v3

REM Альтернатива (если есть GPU):
REM iopaint start --model=migan --device=cuda --port=8085 --host=127.0.0.1 --enable-realesrgan --realesrgan-model=realesr-general-x4v3

pause

