@echo off
echo ==========================================
echo   Instalador Portátil - YouTube Downloader
echo ==========================================
echo.

:: Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no está instalado o no se encuentra en el PATH.
    echo Por favor, instala Python desde python.org antes de continuar.
    pause
    exit /b
)

:: Crear entorno virtual si no existe
if not exist ".venv" (
    echo [+] Creando entorno virtual (.venv)...
    python -m venv .venv
)

:: Activar entorno e instalar dependencias
echo [+] Instalando dependencias (esto puede tardar unos minutos)...
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [+] ¡Instalación completada con éxito!
echo Ahora puedes usar 'iniciar_app.bat' para abrir el programa.
echo.
pause
