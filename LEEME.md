# YouTube Downloader Portable

Esta es una versión preparada para ser trasladada a cualquier computadora con Windows.

## Requisitos Previos

- **Python 3.10+**: Asegúrate de que esté instalado y que hayas marcado la opción "Add Python to PATH" durante la instalación.
- **FFmpeg (Opcional pero recomendado)**: Para descargar videos en alta resolución (1080p+), coloca el archivo `ffmpeg.exe` en la carpeta raíz de este proyecto.

## Cómo instalar en una PC nueva

1.  **Copia la carpeta** completa `app youtube` a la nueva PC.
2.  **Ejecuta `instalar.bat`**: Haz doble clic en este archivo. Se encargará de crear el entorno necesario e instalar las librerías automáticamente (necesita internet para este paso).
3.  **¡Listo!** Una vez termine, no necesitas volver a ejecutar el instalador en esa PC.

## Cómo ejecutar el programa

1.  Haz doble clic en **`iniciar_app.bat`**.
2.  Se abrirá una ventana negra (el servidor) y automáticamente tu navegador con la aplicación.
3.  Cuando termines de usarlo, puedes cerrar el navegador y la ventana negra.

## Solución de problemas

- **Si no descarga en 1080p**: Asegúrate de tener `ffmpeg.exe` en la carpeta o instalado en el sistema.
- **Error de "Python no encontrado"**: Reinstala Python y recuerda marcar la casilla de "Add Python to PATH".
