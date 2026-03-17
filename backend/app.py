from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)

# Directorio temporal para descargas
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/api/video-info', methods=['POST'])
def get_video_info():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'Se requiere una URL de YouTube'}), 400
    
    # Detectar FFmpeg (intentando ruta global y la específica de winget)
    import subprocess
    has_ffmpeg = False
    ffmpeg_paths = [
        'ffmpeg', # Global
        r'C:\Users\Pablo Herrera\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe'
    ]
    
    for path in ffmpeg_paths:
        try:
            subprocess.run([path, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            has_ffmpeg = True
            break
        except:
            continue

    attempts = [
        # Intento 1: Máxima compatibilidad (camuflaje completo)
        {
            'quiet': True, 'no_warnings': True, 'js_runtime': 'node', 'cachedir': False,
            'remote_components': 'ejs:github',
            'noplaylist': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'extractor_args': {'youtube': {'player_client': ['web', 'mweb', 'web_embedded', 'ios', 'android']}}
        },
        # Intento 2: Sin extractor_args específicos (más genérico)
        {
            'quiet': True, 'no_warnings': True, 'js_runtime': 'node', 'cachedir': False,
            'remote_components': 'ejs:github',
            'noplaylist': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        },
        # Intento 3: Básico
        { 'quiet': True, 'no_warnings': True, 'cachedir': False, 'noplaylist': True }
    ]

    info = None
    last_error = ""
    for opts in attempts:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info: break
        except Exception as e:
            last_error = str(e)
            continue

    if not info:
        return jsonify({'error': f'No se pudo obtener información tras varios intentos. Error: {last_error}'}), 500

    # Obtener formatos
    formats = []
    seen_res = set()
    
    # Si no hay ffmpeg, priorizamos los que ya tienen audio y video (progressive/merged)
    # Pero si la lista es corta, mostramos los m3u8 también que yt-dlp puede bajar solos a veces
    all_formats = info.get('formats', [])
    
    # Filtrar formatos útiles (con video)
    useful_formats = [f for f in all_formats if f.get('vcodec') != 'none']
    
    # Ordenar por calidad
    useful_formats.sort(key=lambda x: (x.get('height') or 0), reverse=True)

    for f in useful_formats:
        res = f.get('resolution') or f"{f.get('height')}p"
        ext = f.get('ext', 'mp4')
        has_audio = f.get('acodec') != 'none'
        
        # Si no tenemos ffmpeg y este formato NO tiene audio, marcamos aviso
        label_suffix = ""
        if not has_audio and not has_ffmpeg:
            label_suffix = " (Sin audio - Requiere FFmpeg)"
        elif not has_audio:
             label_suffix = " (Solo video)"

        # Solo añadir una entrada por resolución para no saturar
        if res not in seen_res:
            filesize = f.get('filesize') or f.get('filesize_approx')
            formats.append({
                'format_id': f.get('format_id'),
                'ext': ext,
                'resolution': res,
                'filesize': filesize,
                'label': f"{res} (.{ext}){label_suffix}"
            })
            seen_res.add(res)

    # Obtener el thumbnail de mayor resolución
    max_res_thumb = info.get('thumbnail')
    thumbnails = info.get('thumbnails', [])
    if thumbnails:
        max_res_thumb = sorted(thumbnails, key=lambda x: x.get('width', 0))[-1].get('url')

    return jsonify({
        'title': info.get('title'),
        'thumbnail': info.get('thumbnail'),
        'max_res_thumbnail': max_res_thumb,
        'duration': info.get('duration'),
        'uploader': info.get('uploader'),
        'description': info.get('description')[:200] + '...',
        'formats': formats,
        'has_ffmpeg': has_ffmpeg,
        'has_subtitles': bool(info.get('subtitles') or info.get('automatic_captions'))
    })

@app.route('/api/transcript', methods=['POST'])
def get_transcript():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'Se requiere una URL de YouTube'}), 400

    import tempfile
    import re

    # Opciones para solo descargar subtítulos
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['es', 'en'], # Priorizar español e inglés
            'outtmpl': os.path.join(tmpdir, 'sub.%(ext)s'),
            'quiet': True,
            'noplaylist': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Buscar el archivo de subtítulos generado
                sub_file = None
                for ext in ['es.vtt', 'es.srt', 'en.vtt', 'en.srt']:
                    path = os.path.join(tmpdir, f'sub.{ext}')
                    if os.path.exists(path):
                        sub_file = path
                        break
                
                if not sub_file:
                    for f in os.listdir(tmpdir):
                        if f.startswith('sub.'):
                            sub_file = os.path.join(tmpdir, f)
                            break

                if sub_file:
                    with open(sub_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    content = re.sub(r'WEBVTT.*?\n\n', '', content, flags=re.DOTALL)
                    content = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*?\n', '', content)
                    content = re.sub(r'^\d+\n', '', content, flags=re.MULTILINE)
                    content = re.sub(r'<[^>]*>', '', content)
                    lines = content.split('\n')
                    clean_lines = []
                    last_line = ""
                    for line in lines:
                        line = line.strip()
                        if line and line != last_line:
                            clean_lines.append(line)
                            last_line = line
                    
                    final_text = ' '.join(clean_lines)
                    return jsonify({'transcript': final_text})
                
                # Si no hay subs, forzamos el error para ir al fallback
                raise Exception("No subtitles found, switching to Whisper")

        except Exception as e:
            error_str = str(e)
            print(f"Subtitles failed: {error_str}. Attempting local transcription...")
            
            try:
                import whisper
                # 1. Descargar solo audio en baja calidad
                audio_opts = {
                    'format': 'm4a/bestaudio/worst',
                    'outtmpl': os.path.join(tmpdir, 'audio.%(ext)s'),
                    'quiet': True,
                    'noplaylist': True,
                }
                
                with yt_dlp.YoutubeDL(audio_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    audio_file = ydl.prepare_filename(info)
                
                # 2. Transcribir con Whisper (modelo base)
                model = whisper.load_model("base")
                result = model.transcribe(audio_file)
                
                return jsonify({
                    'transcript': result['text'].strip(),
                    'method': 'whisper'
                })
            except Exception as whisper_e:
                # Si esto también falla, limpiar el error de yt-dlp y devolverlo
                clean_error = re.sub(r'\u001b\[[0-9;]*m', '', error_str)
                return jsonify({'error': f'No se pudo obtener la transcripción (YouTube bloqueado y Whisper falló): {clean_error}'}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id', 'best')
    
    if not url:
        return jsonify({'error': 'Se requiere una URL de YouTube'}), 400
    
    # Generar un nombre de archivo único para evitar colisiones
    unique_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_FOLDER, f'%(title)s_{unique_id}.%(ext)s')
    
    ydl_opts = {
        'format': format_id,
        'outtmpl': output_template,
        'quiet': True,
        'js_runtime': 'node',
        'remote_components': 'ejs:github',
        'cachedir': False,
        'noplaylist': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'extractor_args': {'youtube': {'player_client': ['web', 'mweb', 'web_embedded', 'ios', 'android']}},
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if os.path.exists(filename):
                return send_file(filename, as_attachment=True)
            else:
                return jsonify({'error': 'Archivo no encontrado después de la descarga'}), 500
                
    except Exception as e:
        return jsonify({'error': f'Error en la descarga: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
