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
import json

try:
    from groq import Groq
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY")) if os.environ.get("GROQ_API_KEY") else None
except ImportError:
    groq_client = None

# --- CONFIGURACIÓN DE RUTAS Y ENTORNO ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
IS_RENDER = os.environ.get('RENDER') is not None

# Intentamos encontrar FFmpeg
ffmpeg_extra_paths = [
    BASE_DIR,
    os.path.join(BASE_DIR, 'bin'),
    r'C:\Program Files\Red Giant\Trapcode Suite\Tools',
    r'C:\Program Files\SnapDownloader\resources\win',
]
current_path = os.environ.get("PATH", "")
nuevo_path = current_path
for p in ffmpeg_extra_paths:
    if os.path.exists(p) and p not in nuevo_path:
        nuevo_path = p + os.pathsep + nuevo_path

os.environ["PATH"] = nuevo_path

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

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

# --- UNIFIED ROBUST OPTIONS (COOKIES & CLIENTS) ---
import random
import base64
import tempfile

def get_robust_opts(target_url, extra={}):
    """Genera opciones unificadas para yt-dlp con soporte para cookies locales y de entorno."""
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1'
    ]
    
    cookie_path = os.path.join(BACKEND_DIR, 'cookies.txt')
    opts = {
        'quiet': True,
        'no_warnings': True,
        'cachedir': False,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'user_agent': random.choice(USER_AGENTS),
        **extra
    }

    # Auto-detección de FFmpeg
    fpath = get_ffmpeg_path()
    if fpath:
        opts['ffmpeg_location'] = fpath

    # Soporte para cookies vía Variable de Entorno (Prioridad)
    cookie_b64 = os.environ.get('COOKIES_B64')
    if cookie_b64:
        try:
            cookie_data = base64.b64decode(cookie_b64).decode()
            temp_cookie = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            temp_cookie.write(cookie_data)
            temp_cookie.close()
            opts['cookiefile'] = temp_cookie.name
            print(f"DEBUG: Cargando cookies desde variable [COOKIES_B64] (Temp: {temp_cookie.name})")
        except Exception as e:
            print(f"DEBUG: Error cargando COOKIES_B64: {e}")
    
    # Si no hay COOKIES_B64, intentamos con cookiesfrombrowser (Local) o cookies.txt
    if 'cookiefile' not in opts:
        if not IS_RENDER:
            # En local priorizamos navegadores instalados
            opts['cookiesfrombrowser'] = 'chrome'
            print("DEBUG: Usando cookies del navegador (Local/Chrome)")
        elif os.path.exists(cookie_path):
            print(f"DEBUG: Cargando cookies locales desde {cookie_path}")
            opts['cookiefile'] = cookie_path
    
    # Estrategia de clientes para YouTube (Priorizamos móviles)
    if 'youtube.com' in target_url or 'youtu.be' in target_url:
        opts['extractor_args'] = {'youtube': {'player_client': ['ios', 'android', 'web']}}
        opts['user_agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1'
    
    return opts

@app.route('/api/health/cookies', methods=['GET'])
def health_check():
    """Endpoint para el monitor de estado del frontend."""
    cookie_path = os.path.join(BACKEND_DIR, 'cookies.txt')
    has_b64 = os.environ.get('COOKIES_B64') is not None
    has_file = os.path.exists(cookie_path)
    
    if IS_RENDER and not has_b64 and not has_file:
         return jsonify({'status': 'error', 'message': 'No cookies found in Render'}), 200
    return jsonify({'status': 'ok'}), 200

whisper_model = None

def get_whisper_model():
    global whisper_model
    if IS_RENDER:
        print("INFO: IA Whisper local desactivada en Render para prevenir cuelgues (Poca RAM).")
        return None
    if whisper_model is None:
        try:
            import whisper
            print("Cargando modelo Whisper en memoria...")
            whisper_model = whisper.load_model("tiny")
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
        return text

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
        return str(e), 500

def get_ffmpeg_path():
    ffmpeg_paths = [
        r'C:\Program Files\Red Giant\Trapcode Suite\Tools\ffmpeg.exe',
        r'C:\Program Files\SnapDownloader\resources\win\ffmpeg.exe',
        'ffmpeg',
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
    
    # Intentos de extracción con opciones unificadas
    try:
        opts = get_robust_opts(url)
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Usamos download=False para solo obtener info
            info = ydl.extract_info(url, download=False)
            last_error = ""
    except Exception as e:
        info = None
        last_error = str(e)

    if not info:
        msg = f"No se pudo obtener información. Error: {last_error}"
        if "confirm you're not a bot" in last_error or "403" in last_error:
            msg += "\n\n[TIP] YouTube detectó actividad sospechosa. Prueba:\n1. Cerrar Chrome/Edge si están abiertos.\n2. Asegúrate de tener sesión iniciada en YouTube en tu navegador.\n3. Intenta de nuevo en unos segundos."
        return jsonify({'error': msg}), 500

    has_ffmpeg = get_ffmpeg_path() is not None


    formats = []
    seen_res = set()
    all_formats = info.get('formats', [])
    useful_formats = [f for f in all_formats if f.get('vcodec') != 'none']
    useful_formats.sort(key=lambda x: (x.get('height') or 0), reverse=True)

    for f in useful_formats:
        res = f.get('resolution') or f"{f.get('height')}p"
        if res == "Nonep" or not f.get('height'):
             res = f.get('format_note') or f.get('format_id') or "Calidad única"
        ext = f.get('ext', 'mp4')
        acodec = f.get('acodec')
        has_audio = acodec not in (None, 'none', 'n/a')
        if "instagram.com" in url and ext == 'mp4' and not has_audio:
            has_audio = True
        
        label_suffix = ""
        if not has_audio:
            label_suffix = " (Sin audio - Requiere FFmpeg)" if not has_ffmpeg else " (Solo video)"

        res_key = f"{res}_{ext}"
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

    thumbnail = info.get('thumbnail')
    thumbnails = info.get('thumbnails', [])
    if thumbnails:
        sorted_thumbs = sorted(thumbnails, key=lambda x: x.get('width', 0), reverse=True)
        max_res_thumb = sorted_thumbs[0].get('url') if sorted_thumbs else thumbnail
        if not thumbnail and sorted_thumbs:
            thumbnail = sorted_thumbs[0].get('url')
    else:
        max_res_thumb = thumbnail

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

    cache = load_cache()
    if url in cache:
        return jsonify({'transcript': cache[url], 'method': 'cache'})

    import tempfile
    import re

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            if 'youtube.com' in url or 'youtu.be' in url:
                ydl_opts_subs = get_robust_opts(url, {
                    'skip_download': True,
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['es.*', 'en.*'],
                    'outtmpl': os.path.join(tmpdir, 'sub.%(ext)s'),
                })
                with yt_dlp.YoutubeDL(ydl_opts_subs) as ydl:
                    ydl.extract_info(url, download=True)
                    sub_file = None
                    is_english = False
                    for f in os.listdir(tmpdir):
                        if f.startswith('sub.') and ('.es' in f or '.es-419' in f or '.es-ES' in f):
                            sub_file = os.path.join(tmpdir, f)
                            break
                    if not sub_file:
                        for f in os.listdir(tmpdir):
                            if f.startswith('sub.') and ('.en' in f or '.en-US' in f or '.en-GB' in f):
                                sub_file = os.path.join(tmpdir, f)
                                is_english = True
                                break
                    if sub_file:
                        with open(sub_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        content = re.sub(r'WEBVTT.*?\n\n', '', content, flags=re.DOTALL)
                        content = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*?\n', '', content)
                        content = re.sub(r'^\d+\n', '', content, flags=re.MULTILINE)
                        content = re.sub(r'<[^>]*>', '', content)
                        final_text = ' '.join([line.strip() for line in content.split('\n') if line.strip()])
                        if is_english: final_text = translate_to_spanish(final_text)
                        cache[url] = final_text
                        save_cache(cache)
                        return jsonify({'transcript': final_text, 'method': 'subtitles'})

            # 2. Descargar audio con bitrate bajo (64k) para optimizar el limite de 25MB de Groq
            audio_opts = get_robust_opts(url, {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(tmpdir, 'audio.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '64', 
                }]
            })
            with yt_dlp.YoutubeDL(audio_opts) as ydl:
                ydl.download([url])
                audio_file = None
                for f in os.listdir(tmpdir):
                    if f.startswith('audio.'):
                        audio_file = os.path.join(tmpdir, f)
                        break
                if not audio_file: raise Exception("No se pudo descargar el audio")

            # 3. Transcribir con Groq API (Prioridad)
            if groq_client:
                file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
                if file_size_mb < 25:
                    try:
                        print(f"Usando Groq API ({file_size_mb:.1f}MB)...")
                        with open(audio_file, "rb") as f:
                            transcription = groq_client.audio.transcriptions.create(
                                file=(audio_file, f.read()),
                                model="whisper-large-v3",
                                response_format="text",
                                language="es"
                            )
                        if os.path.exists(audio_file): os.remove(audio_file) # Cleanup inmediata
                        cache[url] = transcription
                        save_cache(cache)
                        return jsonify({'transcript': transcription, 'method': 'groq_whisper_v3'})
                    except Exception as e:
                        print(f"Groq API Error: {e}")
                else:
                    print(f"Audio demasiado grande para Groq ({file_size_mb:.1f}MB).")

            # 4. Fallback: IA Local (Whisper)
            model = get_whisper_model()
            if not model: raise Exception("IA Local no disponible (Limite RAM). Configura GROQ_API_KEY")
            
            result = model.transcribe(audio_file)
            text = result['text'].strip()
            if result.get('language') != 'es': text = translate_to_spanish(text)
            if os.path.exists(audio_file): os.remove(audio_file) # Cleanup
            
            cache[url] = text
            save_cache(cache)
            return jsonify({'transcript': text, 'method': 'whisper_local'})

        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            gc.collect()
            if torch.cuda.is_available(): torch.cuda.empty_cache()

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id', 'best')
    unique_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_FOLDER, f'%(title)s_{unique_id}.%(ext)s')
    
    ydl_opts = get_robust_opts(url, {
        'format': format_id,
        'outtmpl': output_template,
    })
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            filename = None
            for f in os.listdir(DOWNLOAD_FOLDER):
                if unique_id in f:
                    filename = os.path.join(DOWNLOAD_FOLDER, f)
                    break
            if filename: return send_file(filename, as_attachment=True)
            return jsonify({'error': 'Archivo no generado'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
