# ChoonChoon 24x7 Telegram Cloud Importer

Automated cloud worker that listens to `@TejalShikshaVibhag` and posts educational updates into ChoonChoon under **तेजल शिक्षा विभाग, राजस्थान**.

Runs 24x7 in the cloud without requiring your PC to be on.

## Render.com Setup (100% Free)
1. Go to [https://render.com](https://render.com) and Sign In with GitHub.
2. Click **New +** -> **Web Service**.
3. Select your repository `choonchoon-importer`.
4. Fill in:
   - **Name:** `choonchoon-tg-sync`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Instance Type:** `Free`
5. Click **Create Web Service**.

## Koyeb.com Setup (100% Free, Never Sleeps)
1. Go to [https://app.koyeb.com](https://app.koyeb.com) and Sign In.
2. Click **Create App** -> **GitHub**.
3. Select your repository `choonchoon-importer`.
4. Instance type: **Nano (Free)**.
5. Click **Deploy**.
