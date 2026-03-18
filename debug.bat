@echo on
setlocal enabledelayedexpansion
cd /d %~dp0

echo ==========================================
echo   DEBUG: Iniciando YouTube Downloader...
echo ==========================================

:: 1. Limpiar procesos previos en el puerto 5000
echo [+] Verificando si el servidor ya está corriendo...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do (
    if NOT "%%a"=="" (
        echo [!] El puerto 5000 está ocupado. Cerrando proceso %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
)

:: 2. Verificar si el entorno virtual existe
if not exist ".venv" (
    echo [ERROR] No se encontró el entorno virtual (.venv).
    echo Por favor, ejecuta primero 'instalar.bat'.
    pause
    exit /b
)

:: 3. Verificar si la carpeta se ha movido
findstr /C:"%CD%" ".venv\Scripts\activate.bat" >nul
if %errorlevel% neq 0 (
    echo [!] AVISO: La ubicación de la carpeta ha cambiado.
)

:: 4. Iniciar el backend (sin START para ver errores aquí mismo si falla)
echo [+] Levantando el servidor backend (Flask)...
call .venv\Scripts\activate
python backend\app.py
pause
