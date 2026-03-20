@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================
echo   Iniciando YouTube Downloader...
echo ==========================================
echo.

:: 1. Limpiar procesos previos en el puerto 5000
echo [+] Verificando si el servidor ya esta corriendo...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do (
    if NOT "%%a"=="" (
        echo [!] El puerto 5000 esta ocupado. Cerrando proceso %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
)

:: 2. Verificar si el entorno virtual existe
if not exist ".venv" (
    echo [ERROR] No se encontro el entorno virtual .venv
    echo Por favor, ejecuta primero instalar.bat
    pause
    exit /b
)

:: 3. Verificar si la carpeta se ha movido
findstr /C:"%CD%" ".venv\Scripts\activate.bat" >nul
if %errorlevel% neq 0 (
    echo [!] AVISO: La ubicacion de la carpeta ha cambiado.
    echo Si el servidor no arranca, borra la carpeta .venv y ejecuta instalar.bat
    echo.
)

:: 4. Iniciar el backend en una ventana aparte
echo [+] Levantando el servidor backend FastAPI (StreamVault Pro)...
echo [INFO] Se abrira una ventana negra que se cerrara automaticamente al terminar.
:: Usamos comillas dobles para manejar espacios en rutas y simplificamos el comando de activacion
start "Servidor Backend - StreamVault Pro" cmd /c "call .venv\Scripts\activate && python app-yt-pro\backend\main.py || (echo [ERROR] El servidor se detuvo inesperadamente && pause)"

:: 5. Esperar a que el servidor este listo (maximo 30 segundos)
echo [+] Esperando a que el servidor responda en el puerto 5000...
set "ready=0"
for /L %%i in (1,1,30) do (
    if !ready! equ 0 (
        netstat -an | findstr :5000 | findstr LISTENING >nul
        if !errorlevel! equ 0 (
            set "ready=1"
        ) else (
            <nul set /p=.
            timeout /t 1 /nobreak >nul
        )
    )
)
echo.

:: 6. Abrir el frontend si el servidor esta listo
if !ready! equ 1 (
    echo [+] Servidor listo. Abriendo la interfaz en el navegador...
    start "" "http://localhost:5000"
    echo.
    echo [+] Aplicacion iniciada con exito.
    echo [!] IMPORTANTE: No cierres la ventana negra del servidor mientras uses el programa.
) else (
    echo [ERROR] El servidor no inicio a tiempo o hubo un error.
    echo Revisa la ventana negra del servidor para mas detalles.
    pause
)

timeout /t 3 >nul
exit
