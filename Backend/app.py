import os
import re
import json
import logging
from pathlib import Path
from urllib.parse import urlparse, quote
from flask import Flask, request, jsonify, send_file, after_this_request, send_from_directory, Response
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='')

# Configuration
BASE_DIR = Path(__file__).parent
DOWNLOAD_FOLDER = BASE_DIR / 'downloads'
DOWNLOAD_FOLDER.mkdir(exist_ok=True)
SUPPORTED_PLATFORMS = {
    'youtube.com': 'YouTube',
    'youtu.be': 'YouTube',
    'instagram.com': 'Instagram',
    'facebook.com': 'Facebook',
    'fb.watch': 'Facebook',
    'twitter.com': 'Twitter',
    'x.com': 'Twitter',
    'tiktok.com': 'TikTok',
    'vm.tiktok.com': 'TikTok',
    'vimeo.com': 'Vimeo',
    'terabox.com': 'Terabox'
}

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

# --- TYPO FIX: Corrected SUPPORTED_PLATFORS to SUPPORTED_PLATFORMS ---
def get_platform(url):
    """Identify the platform from URL"""
    try:
        domain = urlparse(url).netloc.lower()
        return next(
            (name for domain_part, name in SUPPORTED_PLATFORMS.items() 
             if domain_part in domain),
            None
        )
    except Exception as e:
        logger.error(f"URL parsing error: {e}")
        return None

def get_format_string(format_type, quality):
    """Generate reliable format selection string with fallbacks"""
    
    if format_type == 'mp3':
        return 'bestaudio/best'
    
    format_type = format_type if format_type in ['mp4', 'webm'] else 'mp4'

    if quality == 'best':
        return f'bestvideo[ext={format_type}]+bestaudio[ext=m4a]/bestvideo[ext={format_type}]+bestaudio/best'
    
    try:
        height = int(quality)
        return (
            f'bestvideo[height<={height}][ext={format_type}]+bestaudio/best[height<={height}]/best'
        )
    except ValueError:
        return f'bestvideo[ext={format_type}]+bestaudio/best'

@app.route('/')
def serve_index():
    """Serve the frontend index.html"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory(app.static_folder, path)

@app.route('/api/info', methods=['POST'])
def video_info():
    """Get video information with comprehensive format checking"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400

        platform = get_platform(url)
        if not platform:
            return jsonify({'error': 'Platform not supported'}), 400

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android'],
                    'skip': ['dash', 'hls']
                },
                'instagram': {
                    'force_generic_extractor': True
                }
            },
            'compat_opts': [
                'no-youtube-unavailable-videos',
                'no-youtube-channel-redirect'
            ],
            'allow_multiple_video_streams': True,
            'allow_multiple_audio_streams': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            if 'formats' in info:
                formats = [
                    {
                        'id': f.get('format_id'),
                        'ext': f.get('ext'),
                        'height': f.get('height'),
                        'width': f.get('width'),
                        'fps': f.get('fps'),
                        'vcodec': f.get('vcodec'),
                        'acodec': f.get('acodec'),
                        'filesize': round((f.get('filesize') or 0) / (1024 * 1024), 2) if f.get('filesize') is not None else None,
                        'quality': f.get('format_note') or f"{f.get('height', '?')}p",
                        'url': f.get('url')
                    }
                    for f in info['formats']
                    if (f.get('height') or f.get('acodec') != 'none') and f.get('protocol') not in ['m3u8_native', 'm3u8', 'dash']
                ]
                formats.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)

            thumbnails = info.get('thumbnails', [])
            best_thumbnail = info.get('thumbnail')
            
            # --- INSTAGRAM THUMBNAIL FIX: Manual fallback logic ---
            if platform == 'Instagram':
                 if info.get('url') and (info['url'].endswith('.jpg') or info['url'].endswith('.png') or info['url'].endswith('.mp4')):
                    best_thumbnail = info['url']
                 elif info.get('webpage_url'):
                    best_thumbnail = info['webpage_url']
            
            if thumbnails:
                best_thumbnail = max(
                    (t for t in thumbnails if t.get('url')),
                    key=lambda x: x.get('width', 0) * x.get('height', 0),
                    default={'url': best_thumbnail}
                )['url']

            return jsonify({
                'success': True,
                'platform': platform,
                'info': {
                    'id': info.get('id'),
                    'title': info.get('title', 'Untitled'),
                    'thumbnail': best_thumbnail,
                    'duration': info.get('duration'),
                    'uploader': info.get('uploader'),
                    'formats': formats,
                    'webpage_url': info.get('webpage_url'),
                    'is_live': info.get('is_live', False)
                }
            })

    except Exception as e:
        logger.error(f"Info endpoint error: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to get video info',
            'message': str(e),
            'possible_reasons': [
                'Video is private or restricted',
                'Geoblocked in your region',
                'Requires login (especially common for Instagram/Twitter)',
                'Format not available'
            ]
        }), 500

@app.route('/api/download-progress')
def download_progress():
    """SSE endpoint for robust download progress"""
    url = request.args.get('url')
    format_type = request.args.get('format', 'mp4')
    quality = request.args.get('quality', 'best')
    
    def generate():
        platform = get_platform(url)
        if not platform:
            yield "data: " + json.dumps({
                'status': 'error',
                'message': 'Platform not supported'
            }) + "\n\n"
            return

        # --- FILENAME FIX: Use title only for a clean name ---
        OUTPUT_TEMPLATE = str(DOWNLOAD_FOLDER / '%(title)s.%(ext)s')

        attempts = [{'format': get_format_string(format_type, quality)}]

        progress_data = {
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'status': 'starting',
            'attempt': 0
        }

        success = False

        for i, config in enumerate(attempts):
            progress_data['attempt'] = i + 1
            
            ydl_opts = {
                'outtmpl': OUTPUT_TEMPLATE,
                'quiet': True,
                'no_warnings': True,
                'logger': logger,
                'retries': 3,
                'fragment_retries': 3,
                'skip_unavailable_fragments': True,
                'postprocessor_args': {
                    'ffmpeg': ['-hide_banner', '-loglevel', 'error']
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web', 'android'],
                        'skip': ['dash', 'hls']
                    },
                    'instagram': {'download_preference': 'native'}
                },
                'compat_opts': ['no-youtube-unavailable-videos'],
                # Embed thumbnail for better file management and playback compatibility
                'writethumbnail': True,
                'embedthumbnail': True,
                **config
            }

            if format_type == 'mp3':
                preferred_quality = quality if quality != 'best' else '192' 

                ydl_opts.update({
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': preferred_quality,
                    }],
                    'extractaudio': True,
                    'keepvideo': False,
                    'format': 'bestaudio/best', 
                })
            else:
                ydl_opts.update({
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': format_type,
                    }],
                    'merge_output_format': format_type,
                })

            def progress_hook(d):
                if d['status'] == 'downloading':
                    progress_data.update({
                        'status': 'downloading',
                        'downloaded_bytes': d.get('downloaded_bytes', 0),
                        'total_bytes': d.get('total_bytes', 0),
                        'percent': d.get('_percent_str', '0%'),
                        'speed': d.get('_speed_str', 'N/A'),
                        'eta': d.get('_eta_str', 'N/A')
                    })
                elif d['status'] == 'finished':
                    progress_data.update({
                        'status': 'processing',
                        'percent': '100%',
                        'info': 'Finalizing media file...'
                    })
                
                yield f"data: {json.dumps(progress_data)}\n\n"
                
            ydl_opts['progress_hooks'] = [lambda d: next(progress_hook(d))] 

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    ydl.download([url])
                    
                    yield f"data: {json.dumps({'status': 'finished'})}\n\n"
                    success = True
                    break
            except DownloadError as e:
                logger.warning(f"Attempt {i+1} failed: {e}")
                yield "data: " + json.dumps({
                    'status': 'error',
                    'message': f"Download failed (Attempt {i+1}). Reason: {str(e)}"
                }) + "\n\n"
                continue
            except Exception as e:
                logger.error(f"Unexpected error in attempt {i+1}: {e}")
                yield "data: " + json.dumps({
                    'status': 'error',
                    'message': f"Unexpected error (Attempt {i+1}): {str(e)}"
                }) + "\n\n"
                continue

        if not success:
            error_msg = "Failed to initiate download after all attempts. Content may be restricted or unavailable."
            logger.error(error_msg)
            yield "data: " + json.dumps({
                'status': 'error',
                'message': error_msg,
                'suggestions': [
                    'Try again later',
                    'The content may have restrictions',
                    'Try a different format/quality combination'
                ]
            }) + "\n\n"
        
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/download', methods=['POST'])
def download():
    """Robust download endpoint with comprehensive error handling"""
    temp_file = None
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        format_type = data.get('format', 'mp4')
        quality = data.get('quality', 'best')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400

        platform = get_platform(url)
        if not platform:
            return jsonify({'error': 'Platform not supported'}), 400

        # --- FILENAME FIX: Use title only for a clean name ---
        OUTPUT_TEMPLATE = str(DOWNLOAD_FOLDER / '%(title)s.%(ext)s')

        ydl_opts = {
            'format': get_format_string(format_type, quality),
            'outtmpl': OUTPUT_TEMPLATE,
            'quiet': True,
            'no_warnings': True,
            'logger': logger,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android'],
                    'skip': ['dash', 'hls']
                },
                'instagram': {
                    'download_preference': 'native'
                }
            },
            'compat_opts': ['no-youtube-unavailable-videos'],
            'postprocessor_args': {
                'ffmpeg': ['-hide_banner', '-loglevel', 'error']
            },
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'writethumbnail': True,
            'embedthumbnail': True,
        }

        if format_type == 'mp3':
            preferred_quality = quality if quality != 'best' else '192' 

            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': preferred_quality,
                }],
                'extractaudio': True,
                'keepvideo': False
            })
        else:
            ydl_opts.update({
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': format_type,
                }],
                'merge_output_format': format_type,
            })

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # --- FILE PATH SEARCH LOGIC ---
            file_title_part = sanitize_filename(info.get('title', 'Untitled'))
            
            if format_type == 'mp3':
                 final_ext = '.mp3'
            else:
                 final_ext = f'.{format_type}'

            # Search for the final file based on title and extension
            matching_files = list(DOWNLOAD_FOLDER.glob(f"{file_title_part}*{final_ext}"))
            
            if matching_files:
                temp_file = str(max(matching_files, key=os.path.getmtime))
            else:
                temp_file = ydl.prepare_filename(info)
                
            if not os.path.exists(temp_file):
                raise FileNotFoundError(f"Download failed: final file was not created or found.")

            final_download_name = sanitize_filename(os.path.basename(temp_file))

            @after_this_request
            def cleanup(response):
                try:
                    if temp_file and os.path.exists(temp_file):
                        # Attempt to delete temporary files created by --writethumbnail
                        Path(temp_file).with_suffix('.webp').unlink(missing_ok=True)
                        Path(temp_file).with_suffix('.jpg').unlink(missing_ok=True)
                        Path(temp_file).with_suffix('.png').unlink(missing_ok=True)

                        os.remove(temp_file)
                        logger.info(f"Cleaned up file: {temp_file}")
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
                return response

            mime_type = f"{'audio' if format_type == 'mp3' else 'video'}/{'mpeg' if format_type == 'mp3' else format_type}"

            response = send_file(
                temp_file,
                as_attachment=True,
                mimetype=mime_type
            )
            
            # --- FILENAME FIX: Manual Content-Disposition header ---
            encoded_filename = quote(final_download_name)
            response.headers["Content-Disposition"] = f"attachment; filename={encoded_filename}"
            
            return response

    except DownloadError as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        return jsonify({
            'error': 'Download failed. This is likely due to platform restrictions, login requirements (Instagram/Twitter), or a failed stream merge.',
            'details': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({
            'error': 'An unexpected error occurred during download',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    # Dynamically get port from environment for local testing
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
    @app.route("/")
def index():
    return app.send_static_file("index.html")
