import os
import subprocess
import json
import logging
import uuid
import time
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VideoQuest API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths from system discovery
DEFAULT_FFMPEG_PATH = r"C:\ffmpeg-2026-02-18-git-52b676bb29-full_build\ffmpeg-2026-02-18-git-52b676bb29-full_build\bin\ffmpeg.exe"

def get_ffmpeg_path():
    if os.path.exists(DEFAULT_FFMPEG_PATH):
        return DEFAULT_FFMPEG_PATH
    import shutil
    path = shutil.which("ffmpeg")
    if path:
        return path
    return "ffmpeg" # Fallback to just "ffmpeg" and hope it's in PATH

FFMPEG_PATH = get_ffmpeg_path()
FFMPEG_DIR = os.path.dirname(FFMPEG_PATH) if os.path.isabs(FFMPEG_PATH) else None

TEMP_DIR = os.path.join(os.getcwd(), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

FRONTEND_DIR = os.path.abspath(os.path.join(os.getcwd(), "..", "frontend"))

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str
    extension: str

def cleanup_file(filepath: str):
    """Cleanup temporary files after download."""
    time.sleep(60) # Wait a bit to ensure transfer is complete
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Cleaned up {filepath}")
    except Exception as e:
        logger.error(f"Error cleaning up {filepath}: {e}")

class ProgressTracker:
    def __init__(self):
        self.clients: Dict[str, WebSocket] = {}

    async def register(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.clients[client_id] = websocket

    def unregister(self, client_id: str):
        if client_id in self.clients:
            del self.clients[client_id]

    async def send_progress(self, client_id: str, data: dict):
        if client_id in self.clients:
            try:
                await self.clients[client_id].send_json(data)
            except Exception:
                self.unregister(client_id)

progress_tracker = ProgressTracker()

def make_progress_hook(client_id: str, format_id: str, loop):
    def progress_hook(d):
        if d['status'] == 'downloading':
            # Robust percentage calculation
            percent = 0
            if d.get('total_bytes'):
                percent = (d.get('downloaded_bytes', 0) / d['total_bytes']) * 100
            elif d.get('total_bytes_estimate'):
                percent = (d.get('downloaded_bytes', 0) / d['total_bytes_estimate']) * 100
            else:
                # Fallback to parsing _percent_str and stripping ANSI codes
                import re
                p_str = d.get('_percent_str', '0%')
                # Remove ANSI escape codes
                p_str = re.sub(r'\x1b\[[0-9;]*m', '', p_str)
                p_str = p_str.replace('%', '').strip()
                try:
                    percent = float(p_str)
                except:
                    percent = 0
            
            asyncio.run_coroutine_threadsafe(
                progress_tracker.send_progress(client_id, {
                    "format_id": format_id,
                    "status": "downloading",
                    "progress": percent,
                    "speed": d.get('_speed_str', 'N/A'),
                    "eta": d.get('_eta_str', 'N/A')
                }), 
                loop
            )
        elif d['status'] == 'finished':
            asyncio.run_coroutine_threadsafe(
                progress_tracker.send_progress(client_id, {
                    "format_id": format_id,
                    "status": "ready",
                    "progress": 100
                }), 
                loop
            )
    return progress_hook

@app.websocket("/ws/progress/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await progress_tracker.register(client_id, websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        progress_tracker.unregister(client_id)

# Serve frontend
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.post("/api/info")
async def get_info(request: InfoRequest):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.google.com/',
        }
        
        # Site-specific headers for better success rates
        if "tiktok.com" in request.url:
            ydl_opts['referer'] = 'https://www.tiktok.com/'
        elif "instagram.com" in request.url:
            ydl_opts['referer'] = 'https://www.instagram.com/'
        elif "facebook.com" in request.url:
            ydl_opts['referer'] = 'https://www.facebook.com/'
            
        # Use cookies if available
        cookies_path = os.path.join(os.getcwd(), "cookies.txt")
        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
            logger.info("Using cookies in get_info")
            
        import yt_dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(request.url, download=False)
        
        if not data:
            raise HTTPException(status_code=400, detail="Could not fetch video information.")

        video_formats = []
        audio_formats = []
        seen_heights = set()
        
        target_heights = [360, 480, 720, 1080]
        
        # 1. Extract Video Formats
        formats = data.get("formats", [])
        
        # Filter for formats that have both video and audio (common for social media)
        # or separate video formats that we can merge.
        
        for target in target_heights:
            best_f = None
            min_diff = 9999
            
            for f in formats:
                height = f.get("height")
                if not height: continue
                
                diff = abs(height - target)
                if diff < 40 and diff < min_diff:
                    min_diff = diff
                    best_f = f
            
            if best_f and best_f.get("height") not in seen_heights:
                # Robust filesize detection for social media
                filesize = best_f.get("filesize") or best_f.get("filesize_approx") or best_f.get("filesize_expected")
                
                # Fallback calculation: (bitrate * duration) / 8
                if not filesize and best_f.get("tbr") and data.get("duration"):
                    filesize = (best_f["tbr"] * data["duration"] * 1024) / 8
                
                video_formats.append({
                    "id": best_f.get("format_id"),
                    "quality": f"{target}p",
                    "ext": best_f.get("ext"),
                    "height": best_f.get("height"),
                    "filesize": filesize
                })
                seen_heights.add(best_f.get("height"))

        # If no specific heights found or for social media (TikTok/Insta/FB),
        # pick the best available format
        if not video_formats:
            # First try formats with height
            all_v = [f for f in formats if f.get("height")]
            if not all_v:
                # Then try any format that isn't audio-only
                all_v = [f for f in formats if f.get("vcodec") != "none"]
            
            if all_v:
                # Pick the one with highest resolution or just the last one
                best_v = max(all_v, key=lambda x: x.get("height") or 0)
                filesize = best_v.get("filesize") or best_v.get("filesize_approx") or best_v.get("filesize_expected")
                
                # Fallback calculation: (bitrate * duration) / 8
                # We check tbr (total bitrate) or vbr (video bitrate)
                bitrate = best_v.get("tbr") or best_v.get("vbr")
                if not filesize and bitrate and data.get("duration"):
                    filesize = (bitrate * data["duration"] * 1024) / 8
                
                video_formats.append({
                    "id": best_v.get("format_id"),
                    "quality": f"{best_v.get('height') or 'Best'}p",
                    "ext": best_v.get("ext"),
                    "height": best_v.get("height"),
                    "filesize": filesize
                })
            elif formats:
                # Absolute fallback: just pick the last format
                best_v = formats[-1]
                filesize = best_v.get("filesize") or best_v.get("filesize_approx") or best_v.get("filesize_expected")
                
                # Fallback calculation
                bitrate = best_v.get("tbr") or best_v.get("vbr")
                if not filesize and bitrate and data.get("duration"):
                    filesize = (bitrate * data["duration"] * 1024) / 8
                
                video_formats.append({
                    "id": best_v.get("format_id"),
                    "quality": "Best Quality",
                    "ext": best_v.get("ext"),
                    "height": best_v.get("height"),
                    "filesize": filesize
                })

        # 2. Always Add Audio Option
        audio_formats.append({
            "id": "bestaudio",
            "quality": "High Quality Audio",
            "ext": "mp3",
            "filesize": None
        })

        return {
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "uploader": data.get("uploader"),
            "video_formats": video_formats,
            "audio_formats": audio_formats
        }

    except Exception as e:
        logger.exception("Error in /api/info")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{decorative_filename}")
async def download_video(
    decorative_filename: str,
    url: str, 
    format_id: str, 
    ext: str,
    client_id: str,
    background_tasks: BackgroundTasks
):
    download_id = str(uuid.uuid4())
    final_ext = "mp4" if ext != "mp3" else "mp3"
    output_filename = f"video_{download_id}"
    output_path = os.path.join(TEMP_DIR, output_filename)

    try:
        loop = asyncio.get_event_loop()
        import yt_dlp
        
        # Robust format selection: try requested + audio, fallback to best, or just requested
        if final_ext == "mp4":
            # For social media, often video and audio are already combined in 'best'
            format_spec = f"{format_id}+bestaudio/bestvideo+bestaudio/best"
        else:
            format_spec = "bestaudio/best"

        ydl_opts = {
            'format': format_spec,
            'outtmpl': f"{output_path}.%(ext)s",
            'ffmpeg_location': FFMPEG_DIR,
            'progress_hooks': [make_progress_hook(client_id, format_id, loop)],
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            # Add user-agent and referer to avoid blocks
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.google.com/',
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'geo_bypass': True,
        }

        # Site-specific headers for better success rates
        if "tiktok.com" in url:
            ydl_opts['referer'] = 'https://www.tiktok.com/'
        elif "instagram.com" in url:
            ydl_opts['referer'] = 'https://www.instagram.com/'
        elif "facebook.com" in url:
            ydl_opts['referer'] = 'https://www.facebook.com/'

        # Use cookies if available
        cookies_path = os.path.join(os.getcwd(), "cookies.txt")
        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
            logger.info("Using cookies.txt for download")

        if final_ext == "mp4":
            ydl_opts.update({
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                # Dictionary style for more reliable parameter application in newer yt-dlp
                'postprocessor_args': {
                    'ffmpeg': [
                        '-vcodec', 'libx264', 
                        '-acodec', 'aac', 
                        '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart'
                    ]
                },
            })
        elif final_ext == "mp3":
            ydl_opts.update({
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })

        def run_ydl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Send ready status via WebSocket - Server side work is done
            asyncio.run_coroutine_threadsafe(
                progress_tracker.send_progress(client_id, {
                    "format_id": format_id,
                    "status": "ready",
                    "progress": 100
                }), 
                loop
            )

        await asyncio.to_thread(run_ydl)

        # Find the actual file
        actual_file = None
        # Check for the expected extension first
        if os.path.exists(f"{output_path}.{final_ext}"):
            actual_file = f"{output_path}.{final_ext}"
        else:
            # Look for any file with the download_id
            for e in ["mp4", "mkv", "webm", "mp3", "m4a", "opus"]:
                check_path = f"{output_path}.{e}"
                if os.path.exists(check_path):
                    actual_file = check_path
                    break
        
        if not actual_file or not os.path.exists(actual_file):
            logger.error(f"File not found after download at {output_path}")
            raise HTTPException(status_code=500, detail="File extraction failed.")

        # MANDATORY RE-ENCODING PHASE
        # To ensure 100% compatibility with Windows Media Player, we force a re-encode to H.264
        # even if yt-dlp thought the format was already mp4.
        fixed_path = f"{output_path}_fixed.{final_ext}"
        logger.info(f"Mandatory Re-encoding/Remuxing {actual_file} to {fixed_path}")
        try:
            conv_cmd = [FFMPEG_PATH, "-y", "-i", actual_file]
            if final_ext == "mp4":
                # Strict H.264 encoding with broad compatibility settings
                conv_cmd += [
                    "-c:v", "libx264", 
                    "-preset", "veryfast", # Faster processing
                    "-crf", "23",          # Good balance of quality/size
                    "-c:a", "aac", 
                    "-b:a", "128k",        # Standard audio bitrate
                    "-pix_fmt", "yuv420p", # Essential for Windows/Mobile compatibility
                    "-movflags", "+faststart",
                    fixed_path
                ]
            else: # mp3
                conv_cmd += ["-ab", "192k", fixed_path]
            
            subprocess.run(conv_cmd, check=True)
            actual_file = fixed_path
        except Exception as e:
            logger.error(f"Mandatory conversion failed: {e}")
            # If re-encoding fails, we still have the original file as a fallback

        background_tasks.add_task(cleanup_file, actual_file)
        
        # Use the decorative filename from the URL path as the actual filename
        mimetype = "video/mp4" if final_ext == "mp4" else "audio/mpeg"
        
        return FileResponse(
            path=actual_file,
            filename=decorative_filename,
            media_type=mimetype
        )

    except Exception as e:
        logger.exception("Download error")
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
