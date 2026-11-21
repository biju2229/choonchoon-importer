"""
ChoonChoon Cloud Auto-Importer (24x7 Cloud Runner for Render / Koyeb)
Listens to @TejalShikshaVibhag and auto-posts to ChoonChoon via Supabase.
"""

import os
import sys
import json
import time
import asyncio
import datetime
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# --- Config ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 37197679))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "aea6a0e5a2d75a805c19f6401d3d78e1")
CHANNEL_USERNAME = os.environ.get("TELEGRAM_CHANNEL", "TejalShikshaVibhag")
SESSION_STRING = os.environ.get(
    "TELEGRAM_SESSION", 
    "1BVtsOHEBu6T8sbP3tx6EWaj_thzIpwk2vl70CSKZ0HAxe-xAMI40uSWxciX6lbhti7g0S-Sz0bzFatusJMFxl2uvSDo-ZsfZ2V7xYzhNvqMTCiEbsgOYv7vio4j4i0gRodambkkWCuuZi_om6F7HRGkAimowwp88biLPPnnrZ07qZwCu75cnYpMd4RPKxClqRMP8Pokxfsi1XlRni-tGLENXaif9g5L9vbiTHLMmNEtN-wzYohFsHEhdscXgNunskhwqGwcv85GhZxPz-CiD9wE9Afq0de9U-K1S3EtrT2v6ijr4OnHHnhi3qf5y-65MGVRJ1UsClkeK09E4VfUX_N4pHffEsJs="
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://nhfxdmuzazvevfahebts.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_MAmK6J1fiwVVDbDeNhsJEw_LW8FVbeO")
TEJAL_USER_ID = os.environ.get("TARGET_USER_ID", "93ea8b89-a8e5-40ec-a579-514fb4d90520")

PORT = int(os.environ.get("PORT", 8080))

PROCESSED_IDS = set()
TEMP_MEDIA_DIR = "temp_media"
os.makedirs(TEMP_MEDIA_DIR, exist_ok=True)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        res = {
            "status": "healthy",
            "service": "ChoonChoon Telegram Cloud Importer",
            "channel": f"@{CHANNEL_USERNAME}",
            "author": "तेजल शिक्षा विभाग, राजस्थान",
            "uptime_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        return

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"🌐 Health server listening on 0.0.0.0:{PORT}")
    server.serve_forever()

def upload_media_to_supabase(file_path: str) -> str:
    try:
        ext = os.path.splitext(file_path)[1].lower()
        content_type = "image/jpeg"
        if ext == ".png":
            content_type = "image/png"
        elif ext == ".webp":
            content_type = "image/webp"

        filename = f"tejal_{int(time.time())}_{os.path.basename(file_path)}"
        storage_url = f"{SUPABASE_URL}/storage/v1/object/choon_media/{filename}"

        with open(file_path, "rb") as f:
            data = f.read()

        req = urllib.request.Request(
            storage_url,
            data=data,
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Content-Type": content_type,
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                return f"{SUPABASE_URL}/storage/v1/object/public/choon_media/{filename}"
    except Exception as e:
        print(f"   [Media Upload Error]: {e}")
    return None

def post_to_choonchoon(text: str, photo_url: str = None) -> bool:
    if not text and not photo_url:
        return False

    payload = [{
        "author_id": TEJAL_USER_ID,
        "content": text.strip() if text else "📢 राजस्थान शिक्षा विभाग आदेश / सूचना",
        "district_id": "jaipur",
        "tehsil": "जयपुर",
        "media_type": "image" if photo_url else "text",
        "media_urls": [photo_url] if photo_url else [],
        "chokho_count": 0,
        "batal_count": 0,
        "rechoon_count": 0,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }]

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/choons",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"   [Choon Post Error]: {e}")
        return False

async def process_msg(client, message):
    if message.id in PROCESSED_IDS:
        return
    PROCESSED_IDS.add(message.id)

    text = message.text or message.message or ""
    photo_url = None

    print(f"\n📩 [New Update from @{CHANNEL_USERNAME}] (Msg ID: {message.id})")
    if text:
        preview = text[:80].replace("\n", " ")
        print(f"   Content: {preview}...")

    if message.photo or (message.media and isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument))):
        try:
            print("   Downloading image...")
            path = await message.download_media(file=TEMP_MEDIA_DIR)
            if path and os.path.exists(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    photo_url = upload_media_to_supabase(path)
                try:
                    os.remove(path)
                except Exception:
                    pass
        except Exception as e:
            print(f"   Download error: {e}")

    ok = post_to_choonchoon(text, photo_url)
    if ok:
        print("   ✅ Successfully posted to ChoonChoon feed!")

async def start_importer():
    print("=" * 65)
    print("🌾 ChoonChoon 24x7 Cloud Importer Started")
    print(f"📢 Source: @{CHANNEL_USERNAME}")
    print(f"👤 Target: तेजल शिक्षा विभाग, राजस्थान")
    print("=" * 65)

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    print("✅ Telethon StringSession Connected to MTProto Cloud!")

    channel = await client.get_entity(CHANNEL_USERNAME)
    print(f"📡 Channel Linked: {channel.title} (@{CHANNEL_USERNAME})")

    # Catch up recent
    print("🔍 Fetching latest 3 messages...")
    try:
        recent = await client.get_messages(channel, limit=3)
        for msg in reversed(recent):
            await process_msg(client, msg)
    except Exception as e:
        print(f"   Error fetching recent: {e}")

    print("\n🟢 Cloud Importer listening for real-time messages...")

    @client.on(events.NewMessage(chats=channel))
    async def handler(event):
        await process_msg(client, event.message)

    await client.run_until_disconnected()

def main():
    # Start HTTP server in background thread for Render/Koyeb health probes
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()

    # Start Telethon async loop
    asyncio.run(start_importer())

if __name__ == "__main__":
    main()
