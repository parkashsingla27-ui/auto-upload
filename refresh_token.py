"""
Refresh Token Generator for YouTube API
========================================
Run this script to generate a Google OAuth2 refresh token.

Steps:
  1. Go to https://console.cloud.google.com/apis/credentials
  2. Create an OAuth 2.0 Client ID (Desktop App)
  3. Download the JSON and save it as 'client_secret.json' in this folder
  4. Run: python refresh_token.py
  5. A browser window will open — sign in with your Google account
  6. Copy the refresh token printed in the terminal
  7. Send it to the Telegram bot:  /set token <paste_token_here>
"""

import json, os

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("❌ Missing package. Run:")
    print("   pip install google-auth-oauthlib")
    exit(1)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = "client_secret.json"

if not os.path.exists(CLIENT_SECRET_FILE):
    print(f"❌ '{CLIENT_SECRET_FILE}' not found!")
    print()
    print("How to get it:")
    print("  1. Go to https://console.cloud.google.com/apis/credentials")
    print("  2. Create OAuth 2.0 Client ID → Desktop App")
    print("  3. Download the JSON file")
    print(f"  4. Rename it to '{CLIENT_SECRET_FILE}' and place it in this folder")
    exit(1)

print("🔐 Opening browser for Google sign-in...")
print()

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
creds = flow.run_local_server(port=0)

refresh_token = creds.refresh_token

print("=" * 60)
print("✅ YOUR REFRESH TOKEN:")
print("=" * 60)
print()
print(refresh_token)
print()
print("=" * 60)
print()
print("📋 Now send this to the Telegram bot:")
print(f"   /set token {refresh_token}")
print()
print("⚠️  Keep this token secret! Do not share it publicly.")
