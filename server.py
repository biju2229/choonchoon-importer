"""
ChoonChoon Cloud Auto-Importer (24x7 Cloud Runner for Render / Koyeb)
Listens to @TejalShikshaVibhag and auto-posts to ChoonChoon via Supabase.
Handles full text + rich photo attachments with Storage & Base64 dual-fallback.
"""

import os
import sys
import re
import json
import time
import io
import base64
import asyncio
import datetime
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from PIL import Image

# --- Config ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 37197679))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "aea6a0e5a2d75a805c19f6401d3d78e1")
CHANNEL_USERNAME = os.environ.get("TELEGRAM_CHANNEL", "TejalShikshaVibhag")
SESSION_STRING = os.environ.get(
    "TELEGRAM_SESSION", 
    "1BVtsOHEBu3MjcBuWuNEcfspSiq5MUm6SMEDTH3aMqPn_QkMvAE3XPToGks-4Rc3fP1VffzV4uNBQOHQ7ruqQk71l-XYkWSADYt0yMbGFA6usqAt5Mv5yuiGTRPL69o_Ne04zRM3xxfzL8GYoAZ_xF_AhMoRUmINyqgSF8bJ60OhCFRRtgd_AKD08pIkAs5J64BeOVvTasqEzgzcHrTfeO95uUYFOFS5N69yyjCF289XqUWvAx74ZznHl4zH9eyuPSLKyFIsWdPtsBsC3PvyxLMRWiQIa2nWiLMd22myapEynqljBMHj-I6WhiZ1RbofoZFF_P_OFO0FlmJCCMoRfzlhhDlkExzg="
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://nhfxdmuzazvevfahebts.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_MAmK6J1fiwVVDbDeNhsJEw_LW8FVbeO")
TEJAL_USER_ID = os.environ.get("TARGET_USER_ID", "93ea8b89-a8e5-40ec-a579-514fb4d90520")

PORT = int(os.environ.get("PORT", 8080))
PROCESSED_IDS = set()

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

_cached_token = None
_token_expiry = 0

def get_supabase_auth_token() -> str:
    """Gets authenticated JWT for tejal@gmail.com so Supabase Storage allows uploads."""
    global _cached_token, _token_expiry
    now = time.time()
    if _cached_token and now < _token_expiry:
        return _cached_token

    try:
        url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
        payload = json.dumps({"email": "tejal@gmail.com", "password": "123456"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            _cached_token = data.get("access_token")
            _token_expiry = now + 3600  # valid for 1 hour
            return _cached_token
    except Exception as e:
        print(f"   [Auth Error]: {e}")
        return None

def upload_media_to_supabase(image_bytes: bytes) -> str:
    """Uploads image bytes to Supabase Storage 'choon_media'. If fails, falls back to direct Base64."""
    try:
        # Resize/compress image using Pillow
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Cap max dimension to 1280px for fast loading
        img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        compressed_bytes = buf.getvalue()

        # Try authenticated Supabase Storage upload
        token = get_supabase_auth_token()
        filename = f"images/post_{int(time.time())}_{int(time.time() * 1000) % 1000}.jpg"
        storage_url = f"{SUPABASE_URL}/storage/v1/object/choon_media/{filename}"

        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token or SUPABASE_ANON_KEY}",
            "Content-Type": "image/jpeg",
            "x-upsert": "true"
        }

        req = urllib.request.Request(storage_url, data=compressed_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status in (200, 201):
                    public_url = f"{SUPABASE_URL}/storage/v1/object/public/choon_media/{filename}"
                    print(f"   ✅ [Media Uploaded to Storage]: {public_url}")
                    return public_url
        except Exception as se:
            print(f"   ⚠️ Storage upload ({se}), falling back to direct Base64...")

        # Fallback to Base64 (ChoonChoon app renders Base64 natively!)
        b64_str = base64.b64encode(compressed_bytes).decode("utf-8")
        b64_url = f"data:image/jpeg;base64,{b64_str}"
        print(f"   ✅ [Media Encoded as Base64] (Size: {len(compressed_bytes) // 1024} KB)")
        return b64_url

    except Exception as e:
        print(f"   ❌ [Image Processing Error]: {e}")
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

def clean_telegram_text(raw_text: str) -> str:
    """Removes messy Telegram markdown stars (**), hashes, and cleans spacing."""
    if not raw_text:
        return ""
    # Strip asterisks (stars) used for bold/italic in Telegram
    text = re.sub(r'\*{1,}', '', raw_text)
    # Strip markdown formatting symbols
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'~{2,}', '', text)
    text = re.sub(r'`{1,}', '', text)
    # Clean multiple spaces on single line
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Clean multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

async def process_msg(client, message):
    if message.id in PROCESSED_IDS:
        return
    PROCESSED_IDS.add(message.id)

    raw_text = message.raw_text or message.text or message.message or ""
    text = clean_telegram_text(raw_text)
    photo_url = None

    print(f"\n📩 [New Update from @{CHANNEL_USERNAME}] (Msg ID: {message.id})")
    if text:
        preview = text[:80].replace("\n", " ")
        print(f"   Content: {preview}...")

    # Check for photo or document image
    is_photo = message.photo is not None
    is_doc_image = False
    if message.document and hasattr(message.document, "mime_type") and message.document.mime_type:
        if message.document.mime_type.startswith("image/"):
            is_doc_image = True

    if is_photo or is_doc_image:
        try:
            print("   📸 Detected photo attachment, downloading to memory...")
            img_bytes = await message.download_media(file=bytes)
            if img_bytes:
                photo_url = upload_media_to_supabase(img_bytes)
        except Exception as e:
            print(f"   Download error: {e}")

    ok = post_to_choonchoon(text, photo_url)
    if ok:
        print(f"   ✅ Successfully posted to ChoonChoon feed! (Has image: {bool(photo_url)})")

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

    # Catch up recent 3 messages
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
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()
    asyncio.run(start_importer())

if __name__ == "__main__":
    main()
