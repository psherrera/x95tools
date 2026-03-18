from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
from flask_cors import CORS
import uuid
import requests
import gc
import torch
from urllib.parse import quote
from deep_translator import GoogleTranslator

# --- CONFIGURACIÓN DE RUTAS Y ENTORNO ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Raíz del proyecto
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Intentamos encontrar FFmpeg en el sistema o en la carpeta local
ffmpeg_extra_paths = [
    BASE_DIR,                                # Carpeta raíz del proyecto
    os.path.join(BASE_DIR, 'bin'),           # Carpeta bin local
    r'C:\Program Files\Red Giant\Trapcode Suite\Tools',
    r'C:\Program Files\SnapDownloader\resources\win',
]
current_path = os.environ.get("PATH", "")
nuevo_path = current_path
for p in ffmpeg_extra_paths:
    if os.path.exists(p) and p not in nuevo_path:
        nuevo_path = p + os.pathsep + nuevo_path

os.environ["PATH"] = nuevo_path
# --------------------------------------------------------

import json

app = Flask(__name__)
CORS(app)

# Directorio temporal para descargas (en la raíz)
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Caché de transcripciones (en la raíz)
CACHE_FILE = os.path.join(BASE_DIR, 'transcripts_cache.json')

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}")

# El modelo se cargará la primera vez que se necesite (Lazy Loading)
whisper_model = None

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        try:
            import whisper
            print("Cargando modelo Whisper en memoria (esto solo ocurre la primera vez)...")
            # Cambiamos a 'tiny' para que sea mucho más rápido en CPU y no se quede pensando
            whisper_model = whisper.load_model("tiny")
            print("Modelo Whisper (tiny) cargado correctamente.")
        except Exception as e:
            print(f"Error al cargar Whisper: {e}")
    return whisper_model

def translate_to_spanish(text):
    if not text:
        return ""
    try:
        translator = GoogleTranslator(source='auto', target='es')
        if len(text) > 4500:
            chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
            translated_chunks = [translator.translate(chunk) for chunk in chunks]
            return " ".join(translated_chunks)
        return translator.translate(text)
    except Exception as e:
        print(f"Error en traduccion: {e}")
        return text # Fallback al original

@app.route('/api/proxy-thumbnail')
def proxy_thumbnail():
    url = request.args.get('url')
    if not url:
        return "Falta URL", 400
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Referer': 'https://www.instagram.com/',
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        from flask import make_response
        response = make_response(resp.content)
        response.headers['Content-Type'] = resp.headers.get('Content-Type', 'image/jpeg')
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    except Exception as e:
        print(f"Proxy error: {e}")
        return str(e), 500

    
def get_ffmpeg_path():
    ffmpeg_paths = [
        r'C:\Program Files\Red Giant\Trapcode Suite\Tools\ffmpeg.exe',
        r'C:\Program Files\SnapDownloader\resources\win\ffmpeg.exe',
        'ffmpeg',  # Global PATH
        os.path.join(BASE_DIR, 'ffmpeg.exe'),
        os.path.join(BASE_DIR, 'bin', 'ffmpeg.exe'),
    ]
    import subprocess
    for p in ffmpeg_paths:
        try:
            subprocess.run([p, '-version'], capture_output=True, check=True)
            return p
        except:
            continue
    return None

@app.route('/api/video-info', methods=['POST'])
def get_video_info():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'Se requiere una URL'}), 400
    
    # Detectar FFmpeg
    ffmpeg_path = get_ffmpeg_path()
    has_ffmpeg = ffmpeg_path is not None

    is_youtube = 'youtube.com' in url or 'youtu.be' in url

    base_opts = {
        'quiet': True,
        'no_warnings': True,
        'cachedir': False,
        'noplaylist': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'cookiefile': os.path.join(BACKEND_DIR, 'cookies.txt') if os.path.exists(os.path.join(BACKEND_DIR, 'cookies.txt')) else None,
    }
    if has_ffmpeg:
        base_opts['ffmpeg_location'] = ffmpeg_path

    if is_youtube:
        attempts = [
            # Android client: obtiene formatos adaptativos completos (1080p, 4K)
            {**base_opts, 'extractor_args': {'youtube': {'player_client': ['android']}}},
            # iOS client: alternativa
            {**base_opts, 'extractor_args': {'youtube': {'player_client': ['ios']}}},
            # Web básico sin extractor args
            {**base_opts},
        ]
    else:
        attempts = [{**base_opts}]

    info = None
    last_error = ""
    for opts in attempts:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and info.get('formats'):
                    break
        except Exception as e:
            last_error = str(e)
            continue

    if not info:
        return jsonify({'error': f'No se pudo obtener información. Error: {last_error}'}), 500

    # Obtener formatos
    formats = []
    seen_res = set()
    
    all_formats = info.get('formats', [])
    
    # Filtrar formatos útiles (con video)
    useful_formats = [f for f in all_formats if f.get('vcodec') != 'none']
    
    # Ordenar por calidad
    useful_formats.sort(key=lambda x: (x.get('height') or 0), reverse=True)

    for f in useful_formats:
        res = f.get('resolution') or f"{f.get('height')}p"
        if res == "Nonep" or not f.get('height'):
             # Fallback for height-less formats
             res = f.get('format_note') or f.get('format_id') or "Calidad única"
             
        ext = f.get('ext', 'mp4')
        acodec = f.get('acodec')
        has_audio = acodec not in (None, 'none', 'n/a')
        
        # Especial para Instagram: si es mp4 y no se detecta audio, 
        # asumimos que es combinado (audio+video) ya que Instagram raramente sirve video solo.
        if "instagram.com" in url and ext == 'mp4' and not has_audio:
            has_audio = True
        
        # Etiqueta de aviso
        label_suffix = ""
        if not has_audio:
            if not has_ffmpeg:
                label_suffix = " (Sin audio - Requiere FFmpeg)"
            else:
                label_suffix = " (Solo video)"

        # Solo añadir una entrada por resolución para no saturar
        res_key = f"{res}_{ext}" # Usar resolución + extensión para evitar perder formatos válidos
        if res_key not in seen_res:
            filesize = f.get('filesize') or f.get('filesize_approx')
            formats.append({
                'format_id': f.get('format_id'),
                'ext': ext,
                'resolution': res,
                'filesize': filesize,
                'label': f"{res} (.{ext}){label_suffix}"
            })
            seen_res.add(res_key)

    # Si no hay formatos filtrados (ej. Instagram suele tener pocos), agregar el mejor directo
    if not formats and all_formats:
        f = all_formats[-1]
        formats.append({
            'format_id': f.get('format_id'),
            'ext': f.get('ext', 'mp4'),
            'resolution': f.get('resolution') or 'best',
            'filesize': f.get('filesize') or f.get('filesize_approx'),
            'label': f"Calidad estándar (.{f.get('ext', 'mp4')})"
        })

    # Obtener thumbnail con fallback desde la lista
    thumbnail = info.get('thumbnail')
    thumbnails = info.get('thumbnails', [])
    if thumbnails:
        sorted_thumbs = sorted(thumbnails, key=lambda x: x.get('width', 0), reverse=True)
        max_res_thumb = sorted_thumbs[0].get('url') if sorted_thumbs else thumbnail
        if not thumbnail and sorted_thumbs:
            thumbnail = sorted_thumbs[0].get('url')
    else:
        max_res_thumb = thumbnail

    # Para Instagram: intentar descargar miniatura y codificarla en base64
    is_instagram = 'instagram.com' in url
    if is_instagram and thumbnail:
        try:
            import base64
            headers_ig = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Referer': 'https://www.instagram.com/',
                'sec-fetch-mode': 'no-cors',
            }
            r = requests.get(thumbnail, headers=headers_ig, timeout=15)
            if r.status_code == 200 and len(r.content) > 100:
                img_b64 = base64.b64encode(r.content).decode('utf-8')
                mime = r.headers.get('Content-Type', 'image/jpeg').split(';')[0]
                thumbnail = f"data:{mime};base64,{img_b64}"
                max_res_thumb = thumbnail
            else:
                print(f"Proxy thumbnail failed: status {r.status_code}")
                thumbnail = None
                max_res_thumb = None
        except Exception as ex:
            print(f"Error descargando miniatura Instagram: {ex}")
            thumbnail = None
            max_res_thumb = None

    return jsonify({
        'title': info.get('title'),
        'thumbnail': thumbnail,
        'max_res_thumbnail': max_res_thumb,
        'duration': info.get('duration'),
        'uploader': info.get('uploader') or info.get('webpage_url_domain', 'Desconocido'),
        'description': (info.get('description') or 'Sin descripción')[:200] + '...',
        'formats': formats,
        'has_ffmpeg': has_ffmpeg,
        'has_subtitles': bool(info.get('subtitles') or info.get('automatic_captions'))
    })

@app.route('/api/transcript', methods=['POST'])
def get_transcript():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'Se requiere una URL'}), 400

    # 1. Verificar caché
    cache = load_cache()
    if url in cache:
        print(f"Caché encontrado para {url}")
        return jsonify({
            'transcript': cache[url],
            'method': 'cache'
        })

    import tempfile
    import re

    # Opciones para solo descargar subtítulos (YouTube)
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['es.*', 'en.*'], # Priorizar español e inglés (usando comodines para variantes)
            'outtmpl': os.path.join(tmpdir, 'sub.%(ext)s'),
            'quiet': True,
            'noplaylist': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'cookiefile': os.path.join(BACKEND_DIR, 'cookies.txt') if os.path.exists(os.path.join(BACKEND_DIR, 'cookies.txt')) else None,
        }
        fpath = get_ffmpeg_path()
        if fpath:
            ydl_opts['ffmpeg_location'] = fpath

        try:
            if 'youtube.com' in url or 'youtu.be' in url:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # Buscar el archivo de subtítulos generado
                    sub_file = None
                    is_english = False
                    
                    # Primero buscamos español
                    for f in os.listdir(tmpdir):
                        if f.startswith('sub.') and ('.es' in f or '.es-419' in f or '.es-ES' in f):
                            sub_file = os.path.join(tmpdir, f)
                            break
                    
                    # Si no hay español, buscamos inglés
                    if not sub_file:
                        for f in os.listdir(tmpdir):
                            if f.startswith('sub.') and ('.en' in f or '.en-US' in f or '.en-GB' in f):
                                sub_file = os.path.join(tmpdir, f)
                                is_english = True
                                break

                    # Si no encontramos con nombres específicos, buscamos cualquiera que empiece por sub.
                    if not sub_file:
                        for f in os.listdir(tmpdir):
                            if f.startswith('sub.'):
                                sub_file = os.path.join(tmpdir, f)
                                is_english = ('.en' in f)
                                break

                    if sub_file:
                        with open(sub_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Limpiar VTT/SRT
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
                        
                        # Traducción si es inglés
                        method_label = 'subtitles'
                        if is_english:
                            print("Traduciendo subtitulos de ingles a español...")
                            final_text = translate_to_spanish(final_text)
                            method_label = 'subtitles_translated'
                        
                        # Guardar en caché
                        cache[url] = final_text
                        save_cache(cache)
                        
                        return jsonify({
                            'transcript': final_text,
                            'method': method_label
                        })
            
            # Si no es YouTube o no tiene subs, forzamos el error para ir al fallback (Whisper)
            raise Exception("No direct subtitles found, switching to Whisper")

        except Exception as e:
            error_str = str(e)
            print(f"Subtitles failed or not applicable: {error_str}. Attempting local transcription...")
            
            try:
                model = get_whisper_model()
                if model is None:
                    raise Exception("Modelo Whisper no disponible")

                # 1. Descargar audio
                audio_opts = {
                    'format': 'bestaudio/best' if ('youtube.com' in url or 'youtu.be' in url) else 'best',
                    'outtmpl': os.path.join(tmpdir, 'audio.%(ext)s'),
                    'quiet': True,
                    'noplaylist': True,
                    'no_warnings': True,
                }
                fpath = get_ffmpeg_path()
                if fpath:
                    audio_opts['ffmpeg_location'] = fpath
                
                with yt_dlp.YoutubeDL(audio_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    audio_file = None
                    for f in os.listdir(tmpdir):
                        if f.startswith('audio.') and any(ext in f for ext in ['.m4a', '.mp3', '.mp4', '.webm']):
                            audio_file = os.path.join(tmpdir, f)
                            break
                    
                    if not audio_file:
                        for f in os.listdir(tmpdir):
                            if not f.endswith('.json'):
                                audio_file = os.path.join(tmpdir, f)
                                break
                    
                    if not audio_file or not os.path.exists(audio_file):
                        raise Exception("No se encontro el audio")
                
                # 2. Transcribir detectando idioma automáticamente
                import torch
                # Quitamos language='es' para que detecte el idioma real
                result = model.transcribe(audio_file, fp16=torch.cuda.is_available())
                detected_lang = result.get('language', 'unknown')
                print(f"Whisper detecto idioma: {detected_lang}")
                
                final_text = result['text'].strip()
                
                # Traducción si no es español
                if detected_lang != 'es':
                    print(f"Traduciendo Whisper de {detected_lang} a español...")
                    final_text = translate_to_spanish(final_text)
                
                # Guardar en caché
                cache[url] = final_text
                save_cache(cache)
                
                return jsonify({
                    'transcript': final_text,
                    'method': 'whisper'
                })
            except Exception as whisper_e:
                whisper_error_str = str(whisper_e)
                print(f"Whisper failed raw: {whisper_error_str}")
                return jsonify({'error': f'Error en transcripcion IA: {whisper_error_str}'}), 500
            finally:
                # Liberar memoria agresivamente
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id', 'best')
    
    if not url:
        return jsonify({'error': 'Se requiere una URL'}), 400
    
    # Generar un nombre de archivo único
    unique_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_FOLDER, f'%(title)s_{unique_id}.%(ext)s')
    
    ydl_opts = {
        'format': format_id,
        'outtmpl': output_template,
        'quiet': True,
        'noplaylist': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'cookiefile': os.path.join(BACKEND_DIR, 'cookies.txt') if os.path.exists(os.path.join(BACKEND_DIR, 'cookies.txt')) else None,
    }
    # Opciones extra solo para YouTube
    if 'youtube.com' in url or 'youtu.be' in url:
        ydl_opts.update({
            'js_runtime': 'node',
            'remote_components': 'ejs:github',
            'cachedir': False,
            'extractor_args': {'youtube': {'player_client': ['web', 'mweb', 'web_embedded', 'ios', 'android']}},
        })
    fpath = get_ffmpeg_path()
    if fpath:
        ydl_opts['ffmpeg_location'] = fpath
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url]) # Descargar directamente
            
            # Buscar el archivo que contenga el unique_id en la carpeta de descargas
            filename = None
            for f in os.listdir(DOWNLOAD_FOLDER):
                if unique_id in f:
                    filename = os.path.join(DOWNLOAD_FOLDER, f)
                    break
            
            if filename and os.path.exists(filename):
                return send_file(filename, as_attachment=True)
            else:
                return jsonify({'error': f'Archivo no encontrado tras descarga v2 (ID: {unique_id})'}), 500
                
    except Exception as e:
        return jsonify({'error': f'Error en la descarga: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
