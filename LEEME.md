# YouTube Downloader Portable

Esta es una versión preparada para ser trasladada a cualquier computadora con Windows.

## Requisitos Previos

- **Python 3.10+**: Asegúrate de que esté instalado y que hayas marcado la opción "Add Python to PATH" durante la instalación.
- **FFmpeg (Recomendado)**: Necesario para unir audio y video en alta calidad (1080p+) y para la transcripción.
    - **Opción A**: Descarga `ffmpeg.exe` de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.7z), abre el ZIP y copia el archivo `ffmpeg.exe` (que está en la carpeta `bin`) a la carpeta raíz de este proyecto.
    - **Opción B**: Si ya lo tienes instalado en tu sistema, el programa lo detectará automáticamente.

## Cómo instalar en una PC nueva

1.  **Copia la carpeta** completa `app youtube` a la nueva PC.
2.  **Ejecuta `instalar.bat`**: Haz doble clic en este archivo. Se encargará de crear el entorno necesario e instalar las librerías automáticamente (necesita internet para este paso).
3.  **¡Listo!** Una vez termine, no necesitas volver a ejecutar el instalador en esa PC.

## Cómo ejecutar el programa

1.  Haz doble clic en **`iniciar_app.bat`**.
2.  Se abrirá una ventana negra (el servidor) y automáticamente tu navegador con la interfaz.
3.  **IMPORTANTE**: No cierres la ventana negra mientras usas el programa.

## Solución de problemas

- **Si no descarga en 1080p o falla el texto**: Asegúrate de tener `ffmpeg.exe` en la carpeta o instalado.
- **Error de "Python no encontrado"**: Reinstala Python 3.10 o superior y recuerda marcar la casilla de "Add Python to PATH".
- **Error de conexión**: Asegúrate de que no haya un firewall bloqueando el puerto 5000.
