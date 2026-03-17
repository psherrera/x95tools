@echo off
echo ==========================================
echo   Iniciando YouTube Downloader...
echo ==========================================
echo.

:: Verificar si el entorno virtual existe
if not exist ".venv" (
    echo [ERROR] No se encontró el entorno virtual (.venv).
    echo Por favor, ejecuta primero 'instalar.bat'.
    pause
    exit /b
)

:: Iniciar el backend en segundo plano
echo [+] Levantando el servidor backend (Flask)...
start /b cmd /c ".venv\Scripts\activate && cd backend && python app.py"

:: Esperar un par de segundos para que el servidor inicie
timeout /t 3 /nobreak >nul

:: Abrir el frontend en el navegador
echo [+] Abriendo la interfaz en el navegador...
start frontend\index.html

echo.
echo [+] La aplicación está lista.
echo No cierres esta ventana mientras uses el programa (o ciérrala al terminar).
echo.
pause
