import yt_dlp
import sys

def test_url(url):
    print(f"Testing URL: {url}")
    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    if "tiktok.com" in url:
        ydl_opts['referer'] = 'https://www.tiktok.com/'
    elif "instagram.com" in url:
        ydl_opts['referer'] = 'https://www.instagram.com/'
    elif "facebook.com" in url:
        ydl_opts['referer'] = 'https://www.facebook.com/'
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f"SUCCESS: Found video '{info.get('title')}'")
    except Exception as e:
        print(f"FAILED: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_url(sys.argv[1])
    else:
        print("Usage: python test_download.py <url>")
