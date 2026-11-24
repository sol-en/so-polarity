#!/usr/bin/env python3
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
creds_path = 'credentials.json'
token_path = 'token.json'

if not os.path.exists(creds_path):
    print(f"❌ Файл {creds_path} не знайдено!")
    sys.exit(1)

print("🔗 Відкриваємо вікно авторизації Google у браузері...")
flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
creds = flow.run_local_server(port=8080, open_browser=True)

with open(token_path, 'w') as f:
    f.write(creds.to_json())

print("✅ Успіх! Новий токен збережено в token.json.")
print("\nВаш новий рядок для Render (GMAIL_TOKEN_JSON):")
print(creds.to_json())
