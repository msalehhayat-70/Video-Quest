# VideoQuest · Professional Media Extraction

> High-performance, professional-grade media downloader engineered for speed, reliability, and universal compatibility.

---

## ✦ Key Features

| Feature | Description |
|---|---|
| **Universal Compatibility** | Supports TikTok, Instagram, Facebook, and more |
| **Strict Codec Management** | Auto re-encodes downloads into **H.264 / AAC** for 100% playback compatibility |
| **Dual-Phase Progress** | Real-time WebSocket tracking (server-side) + Fetch-based transfer tracking (client-side) |
| **Metadata Intelligence** | Bitrate-based fallback logic to estimate file sizes when platforms hide them |
| **Premium Dark UI** | Sleek, high-contrast interface designed for focus and ease of use |

---

## ⚙ How It Works — The Technical Journey

### 1 · The Request *(Frontend)*

- **User Action** — Paste a URL from TikTok, Instagram, Facebook, or YouTube into the Command Center
- **Processing** — The frontend cleans the URL and fires a `POST` request to `/api/info`
- **Visuals** — A sleek loader appears while the backend probes the remote server

---

### 2 · Information Extraction *(Backend)*

- **Communication** — Uses **`yt-dlp`** to interface with each platform's internal API
- **Stealth & Success**
  - *Custom Headers* — Dynamically injects site-specific `Referer` and `User-Agent` headers to mimic a real browser
  - *Cookie Handling* — Uses a local `cookies.txt` to bypass login barriers when required
- **Parsing** — Receives all available formats from the remote server, then filters by preferred quality (360p, 720p, etc.)

---

### 3 · Extraction Strategy

| Platform | Strategy |
|---|---|
| **Facebook / Instagram** | Calculates missing file sizes from bitrate metadata |
| **YouTube** | Selects best separate video + audio streams for high-quality merging |

---

### 4 · Download & Re-encode Phase

```
Platform Server  →  Backend Storage  →  FFmpeg Re-encode  →  Client Browser
```

- **Fetch** — Streams the raw file from the platform to temporary server storage
- **Mandatory Re-encoding** — TikTok and others use HEVC codecs unsupported on Windows
  - `FFmpeg` performs a **forced H.264 / AAC re-encode**, reconstructing the video frame-by-frame
- **Fast-Start** — Applies `+faststart` flag, moving metadata to the file header for instant playback

---

### 5 · Final Save *(Client-side)*

- **Direct Stream** — File is streamed from the FastAPI backend to browser memory via the `fetch()` API
- **UI Sync** — Real-time `Saving… %` progress reflects actual bits arriving on your machine
- **Finality** — Browser triggers a local save once the full file is received → status updates to **Downloaded**

---

## 🛠 Tech Stack

**Backend**
- Python 3
- FastAPI
- Uvicorn
- yt-dlp
- FFmpeg

**Frontend**
- HTML5
- Vanilla CSS
- Vanilla JS (ES6+)
- Lucide Icons

---

## 🔧 Tool Deep-Dive

### yt-dlp — *The Extraction Engine*

`yt-dlp` is a feature-rich, actively maintained fork of `youtube-dl`. VideoQuest uses it to:

- **Probe platforms** — Fetches all available format metadata (resolution, codec, bitrate, file size) from TikTok, Instagram, Facebook, YouTube, and 1000+ other sites without downloading anything
- **Inject stealth headers** — Dynamically passes custom `Referer` and `User-Agent` headers per platform to mimic a real browser session and avoid bot detection
- **Handle authentication** — Reads a local `cookies.txt` to access login-gated content (e.g., private Instagram posts)
- **Filter formats** — Selects the right stream(s) based on user-chosen quality (360p / 720p / best), then hands the raw URL off to the download pipeline

```bash
# Example: extract info without downloading
yt-dlp --dump-json --no-download <URL>
```

---

### FFmpeg — *The Re-encode Engine*

`FFmpeg` is the industry-standard multimedia processing framework. VideoQuest uses it to:

- **Re-encode HEVC → H.264** — Platforms like TikTok serve video in HEVC (H.265), which Windows and most browsers don't natively support. FFmpeg reconstructs every frame into H.264, guaranteeing universal playback
- **Re-encode audio → AAC** — Normalizes audio streams to AAC for consistent compatibility across all devices
- **Apply Fast-Start** — Moves the `moov` atom (metadata) to the beginning of the MP4 file using the `+faststart` flag, so videos open instantly without buffering the entire file first
- **Stream processing** — Processes video as a stream, keeping memory usage low even for large files

```bash
# Example: what VideoQuest runs under the hood
ffmpeg -i input.mp4 -c:v libx264 -c:a aac -movflags +faststart output.mp4
```

---

## 🚀 Setup & Installation

**Step 1 — Install FFmpeg**

Ensure FFmpeg is installed and added to your system `PATH`.

**Step 2 — Backend Setup**

```bash
cd backend
pip install fastapi uvicorn yt-dlp
python -m uvicorn main:app --reload
```

**Step 3 — Frontend**

Open `index.html` via the local server:

```
http://localhost:8000

