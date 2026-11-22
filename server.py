"""
ChoonChoon Multi-Channel Cloud Auto-Importer (24x7 Cloud Runner for Render)
Supports multiple Telegram channels mapped to distinct ChoonChoon accounts:
1. @TejalShikshaVibhag -> तेजल शिक्षा विभाग, राजस्थान (tejal@gmail.com)
2. @EDUCATIONPORTAL1   -> एजुकेशन पोर्टल राजस्थान (educationportal@gmail.com)
3. @kalamacademysikar  -> कलाम एकेडमी सीकर (kalamacademysikar@gmail.com)

Features:
- Dual Engine: Real-time Event Listener + 45-second Active Polling Watchdog
- Auto-Join channels for live MTProto push updates
- Clean text formatting (removes markdown stars ****)
- Rich media processing (Supabase Storage + Base64 fallback)
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
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.tl.functions.channels import JoinChannelRequest
from PIL import Image

# --- Config ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 37197679))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "aea6a0e5a2d75a805c19f6401d3d78e1")
SESSION_STRING = os.environ.get(
    "TELEGRAM_SESSION", 
    "1BVtsOHEBu3MjcBuWuNEcfspSiq5MUm6SMEDTH3aMqPn_QkMvAE3XPToGks-4Rc3fP1VffzV4uNBQOHQ7ruqQk71l-XYkWSADYt0yMbGFA6usqAt5Mv5yuiGTRPL69o_Ne04zRM3xxfzL8GYoAZ_xF_AhMoRUmINyqgSF8bJ60OhCFRRtgd_AKD08pIkAs5J64BeOVvTasqEzgzcHrTfeO95uUYFOFS5N69yyjCF289XqUWvAx74ZznHl4zH9eyuPSLKyFIsWdPtsBsC3PvyxLMRWiQIa2nWiLMd22myapEynqljBMHj-I6WhiZ1RbofoZFF_P_OFO0FlmJCCMoRfzlhhDlkExzg="
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://nhfxdmuzazvevfahebts.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_MAmK6J1fiwVVDbDeNhsJEw_LW8FVbeO")
PORT = int(os.environ.get("PORT", 8080))

PROCESSED_IDS = set()
LAST_SEEN_MSG_IDS = {}
_global_client = None
_global_channels = []

# Channel to ChoonChoon User Mapping
CHANNELS_CONFIG = {
    "TejalShikshaVibhag": {
        "author_id": "93ea8b89-a8e5-40ec-a579-514fb4d90520",
        "email": "tejal@gmail.com",
        "username": "TejalShikshaVibhag",
        "display_name": "तेजल शिक्षा विभाग, राजस्थान",
        "avatar_url": "https://cdn5.telesco.pe/file/PzPzjSdZkJ54IVZAn_FrDAHXM5r0gzLkjL48d0HfnI11rRZCKghC7GyZH9uchCEb1YHjiKpl_WHtUrNhD2JGXh9JjGAVKwzSfkC8K7ZFOXwa-xCBioybE9uIBetrJny8nSP4od_Uo7Wqmg9V3cPkSOIqY13oin7PywIZgUi3q6SCgNJawYQwOBABgmNW_e1teF3x04EggEIsXtcf2c9YRb7Y0Kk8I7TvsEU7eg4MidgiLOgxeNP8MMFubXKFOa-Qz7p_OVXdXUpandV3QJipXCbVZ-X7df3VzGpjEGfgnwmNHLztw7mpu1isu2FC-R3k0cArtMBpO2tJD5I9OakCaA.jpg",
        "badge": "राजस्थान शिक्षा चौपाल",
        "bio": "🌟 सभी प्रतियोगी परीक्षाओं व राजस्थान शिक्षा विभाग री हर भर्ती, परीक्षा तिथि व ताजा आदेश री सबसे पहली जानकारी।",
        "district_id": "jaipur",
        "tehsil": "जयपुर"
    },
    "EDUCATIONPORTAL1": {
        "author_id": None,
        "email": "educationportal@gmail.com",
        "password": "123456",
        "username": "EducationPortal",
        "display_name": "एजुकेशन पोर्टल राजस्थान",
        "avatar_url": "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=400&auto=format&fit=crop&q=80",
        "badge": "शिक्षा व भर्ती मंच",
        "bio": "📚 राजस्थान की हर भर्ती परीक्षा, परिणाम, उत्तर कुंजी व प्रवेश पत्र री सबसूं सटीक व तेज जानकारी।",
        "district_id": "jaipur",
        "tehsil": "जयपुर"
    },
    "kalamacademysikar": {
        "author_id": None,
        "email": "kalamacademysikar@gmail.com",
        "password": "123456",
        "username": "kalamacademysikar",
        "display_name": "कलाम एकेडमी सीकर",
        "avatar_url": "https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=400&auto=format&fit=crop&q=80",
        "badge": "कलाम एकेडमी सीकर",
        "bio": "🎯 RAS, शिक्षक ग्रेड 1, 2, 3 (REET), सब-इंस्पेक्टर व राजस्थान री सभी प्रतियोगी परीक्षाओं री सर्वश्रेष्ठ तैयारी।",
        "district_id": "sikar",
        "tehsil": "सीकर"
    }
}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        res = {
            "status": "healthy",
            "service": "ChoonChoon Multi-Channel Telegram Cloud Importer",
            "channels": list(CHANNELS_CONFIG.keys()),
            "last_seen_ids": LAST_SEEN_MSG_IDS,
            "processed_count": len(PROCESSED_IDS),
            "uptime_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        return

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"🌐 Health server listening on 0.0.0.0:{PORT}")
    server.serve_forever()

_cached_tokens = {}

def get_supabase_auth_token(email: str = "tejal@gmail.com", password: str = "123456") -> str:
    global _cached_tokens
    now = time.time()
    if email in _cached_tokens and now < _cached_tokens[email]["expiry"]:
        return _cached_tokens[email]["token"]

    try:
        url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
        payload = json.dumps({"email": email, "password": password}).encode("utf-8")
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
            tok = data.get("access_token")
            if tok:
                _cached_tokens[email] = {"token": tok, "expiry": now + 3600}
                return tok
    except Exception as e:
        print(f"   [Auth Error for {email}]: {e}")
    return None

def ensure_user_account(cfg: dict) -> str:
    if cfg.get("author_id"):
        return cfg["author_id"]

    email = cfg.get("email")
    username = cfg.get("username")
    password = cfg.get("password", "123456")

    print(f"🔍 Checking Supabase account for @{username} ({email})...")

    # 1. Check public.users
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}&select=id",
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
        )
        with urllib.request.urlopen(req) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            if rows and len(rows) > 0 and rows[0].get("id"):
                cfg["author_id"] = rows[0]["id"]
                print(f"   ✅ Found user UID: {cfg['author_id']}")
                return cfg["author_id"]
    except Exception as e:
        pass

    # 2. Try signup
    try:
        signup_payload = {
            "email": email,
            "password": password,
            "data": {
                "display_name": cfg.get("display_name"),
                "username": username,
                "district_name": cfg.get("tehsil"),
                "home_district_id": cfg.get("district_id"),
                "badge_title": cfg.get("badge"),
                "avatar_url": cfg.get("avatar_url"),
                "bio": cfg.get("bio")
            }
        }
        req_signup = urllib.request.Request(
            f"{SUPABASE_URL}/auth/v1/signup",
            data=json.dumps(signup_payload).encode("utf-8"),
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_signup) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            uid = data.get("id") or data.get("user", {}).get("id")
            if uid:
                cfg["author_id"] = uid
                print(f"   ✅ Signed up new user UID: {uid}")
    except Exception:
        pass

    # 3. Try login to retrieve UID and token
    try:
        login_payload = {"email": email, "password": password}
        req_login = urllib.request.Request(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            data=json.dumps(login_payload).encode("utf-8"),
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_login) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            uid = data.get("user", {}).get("id")
            token = data.get("access_token")
            if uid:
                cfg["author_id"] = uid
                print(f"   ✅ Login SUCCESS! User UID: {uid}")

                profile_payload = {
                    "id": uid,
                    "email": email,
                    "username": username,
                    "display_name": cfg.get("display_name"),
                    "avatar_url": cfg.get("avatar_url"),
                    "badge_title": cfg.get("badge"),
                    "bio": cfg.get("bio"),
                    "home_district_id": cfg.get("district_id"),
                    "home_district_name": cfg.get("tehsil"),
                }
                req_profile = urllib.request.Request(
                    f"{SUPABASE_URL}/rest/v1/users",
                    data=json.dumps(profile_payload).encode("utf-8"),
                    headers={
                        "apikey": SUPABASE_ANON_KEY,
                        "Authorization": f"Bearer {token or SUPABASE_ANON_KEY}",
                        "Content-Type": "application/json",
                        "Prefer": "resolution=merge-duplicates"
                    }
                )
                try:
                    with urllib.request.urlopen(req_profile) as prof_resp:
                        print(f"   ✅ Profile upserted in public.users")
                except Exception:
                    pass
    except Exception as e:
        print(f"   Login note: {e}")

    return cfg.get("author_id")

def clean_telegram_text(raw_text: str) -> str:
    """Removes messy Telegram markdown stars (**), hashes, and cleans spacing."""
    if not raw_text:
        return ""
    text = re.sub(r'\*{1,}', '', raw_text)
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'~{2,}', '', text)
    text = re.sub(r'`{1,}', '', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def upload_media_to_supabase(image_bytes: bytes, email: str = "tejal@gmail.com") -> str:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        compressed_bytes = buf.getvalue()

        token = get_supabase_auth_token(email=email)
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

        b64_str = base64.b64encode(compressed_bytes).decode("utf-8")
        b64_url = f"data:image/jpeg;base64,{b64_str}"
        print(f"   ✅ [Media Encoded as Base64] (Size: {len(compressed_bytes) // 1024} KB)")
        return b64_url

    except Exception as e:
        print(f"   ❌ [Image Processing Error]: {e}")
        return None

def post_to_choonchoon(cfg: dict, text: str, photo_url: str = None) -> bool:
    author_id = cfg.get("author_id")
    if not author_id:
        print(f"   ❌ Missing author_id for {cfg.get('display_name')}, trying to resolve...")
        author_id = ensure_user_account(cfg)
        if not author_id:
            return False

    if not text and not photo_url:
        return False

    payload = [{
        "author_id": author_id,
        "content": text.strip() if text else f"📢 {cfg.get('display_name')} आदेश / सूचना",
        "district_id": cfg.get("district_id", "jaipur"),
        "tehsil": cfg.get("tehsil", "जयपुर"),
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

async def process_msg(client, channel_key: str, message):
    dedup_key = f"{channel_key}_{message.id}"
    if dedup_key in PROCESSED_IDS:
        return
    PROCESSED_IDS.add(dedup_key)

    cfg = CHANNELS_CONFIG.get(channel_key, {})
    raw_text = message.raw_text or message.text or message.message or ""
    text = clean_telegram_text(raw_text)
    photo_url = None

    print(f"\n📩 [New Update from @{channel_key}] -> Posting as '{cfg.get('display_name')}' (Msg ID: {message.id})")
    if text:
        preview = text[:80].replace("\n", " ")
        print(f"   Content: {preview}...")

    is_photo = message.photo is not None
    is_doc_image = False
    if message.document and hasattr(message.document, "mime_type") and message.document.mime_type:
        if message.document.mime_type.startswith("image/"):
            is_doc_image = True

    if is_photo or is_doc_image:
        try:
            print("   📸 Downloading photo attachment...")
            img_bytes = await message.download_media(file=bytes)
            if img_bytes:
                photo_url = upload_media_to_supabase(img_bytes, email=cfg.get("email", "tejal@gmail.com"))
        except Exception as e:
            print(f"   Download error: {e}")

    ok = post_to_choonchoon(cfg, text, photo_url)
    if ok:
        print(f"   ✅ Successfully posted to ChoonChoon feed! (Has image: {bool(photo_url)})")

async def check_channel_updates(client, active_channels):
    """Actively polls all channels for new messages every 45 seconds."""
    for c_key, channel_entity in active_channels:
        try:
            # Query the latest 5 messages
            messages = await client.get_messages(channel_entity, limit=5)
            if not messages:
                continue

            last_id = LAST_SEEN_MSG_IDS.get(c_key, 0)
            for msg in reversed(messages):
                if msg.id > last_id:
                    print(f"\n⚡ [Active Watchdog] Found new post on @{c_key} (ID: {msg.id})")
                    await process_msg(client, c_key, msg)
                    if msg.id > LAST_SEEN_MSG_IDS[c_key]:
                        LAST_SEEN_MSG_IDS[c_key] = msg.id

        except Exception as e:
            print(f"   Polling error on @{c_key}: {e}")

async def polling_watchdog(client, active_channels):
    """Continuous 45-second loop that guarantees all new posts are imported."""
    print("🚀 [Watchdog Loop] Started 45-second active polling thread.")
    while True:
        try:
            await asyncio.sleep(45)
            await check_channel_updates(client, active_channels)
        except Exception as e:
            print(f"Watchdog loop exception: {e}")

async def start_importer():
    global _global_client, _global_channels
    print("=" * 65)
    print("🌾 ChoonChoon Multi-Channel Cloud Importer Started")
    print("=" * 65)

    # 1. Ensure all mapped accounts exist in Supabase
    for c_key, c_cfg in CHANNELS_CONFIG.items():
        ensure_user_account(c_cfg)

    # 2. Connect Telegram MTProto Client
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    _global_client = client
    print("✅ Telethon StringSession Connected to MTProto Cloud!\n")

    # 3. Link each channel and catch up on latest updates
    active_channels = []
    for c_key, c_cfg in CHANNELS_CONFIG.items():
        try:
            channel_entity = await client.get_entity(c_key)
            active_channels.append((c_key, channel_entity))
            print(f"📡 Linked @{c_key} -> '{c_cfg.get('display_name')}' (UID: {c_cfg.get('author_id')})")

            # Try to join the channel so Telegram sends push events
            try:
                await client(JoinChannelRequest(channel_entity))
                print(f"   Subscribed to @{c_key} for push updates!")
            except Exception as je:
                pass

            # Fetch recent 2 messages
            try:
                recent = await client.get_messages(channel_entity, limit=2)
                if recent:
                    # Initialize last seen to oldest of the 2
                    LAST_SEEN_MSG_IDS[c_key] = recent[-1].id - 1
                    for msg in reversed(recent):
                        await process_msg(client, c_key, msg)
                        LAST_SEEN_MSG_IDS[c_key] = max(LAST_SEEN_MSG_IDS.get(c_key, 0), msg.id)
                else:
                    LAST_SEEN_MSG_IDS[c_key] = 0
            except Exception as e:
                print(f"   Catch-up error for @{c_key}: {e}")
                LAST_SEEN_MSG_IDS[c_key] = 0

        except Exception as e:
            print(f"⚠️ Could not link channel @{c_key}: {e}")

    _global_channels = active_channels
    print(f"\n🟢 Active channels ready: {[c[0] for c in active_channels]}")

    # 4. Attach event listeners for push events
    for c_key, channel_entity in active_channels:
        def make_handler(current_key):
            async def handler(event):
                await process_msg(client, current_key, event.message)
                if event.message and event.message.id > LAST_SEEN_MSG_IDS.get(current_key, 0):
                    LAST_SEEN_MSG_IDS[current_key] = event.message.id
            return handler

        client.add_event_handler(make_handler(c_key), events.NewMessage(chats=channel_entity))

    # 5. Start the active 45-second polling watchdog task (Guarantees delivery!)
    asyncio.create_task(polling_watchdog(client, active_channels))

    print("\n🟢 Multi-Channel Importer listening 24x7 with Active Polling Watchdog (Every 45s)...")
    await client.run_until_disconnected()

def main():
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()
    asyncio.run(start_importer())

if __name__ == "__main__":
    main()
