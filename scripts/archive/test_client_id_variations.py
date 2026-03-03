#!/usr/bin/env python3
"""
Test different Client ID formats with the NEW credentials
"""
import requests
from requests.auth import HTTPBasicAuth

CLIENT_SECRET = "03GGc3ehttopFBM159Ym6GkHuiE4e9hUgNMCa1eaM1JNYcPu6y"
REFRESH_TOKEN = "9YBsB7pwWFIU19k6uryHJAadw3cLcb5Tl0_SJrMW048"

# Different Client ID formats to try
client_ids = [
    ("Full format", "14299_6GrwlOC8xpjw3wii01yK59g190srgNLugxrl8tLjS1yakA70ii"),
    ("Just number", "14299"),
    ("After underscore", "6GrwlOC8xpjw3wii01yK59g190srgNLugxrl8tLjS1yakA70ii"),
]

print("=" * 60)
print("Testing Different Client ID Formats")
print("=" * 60)

for name, client_id in client_ids:
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Client ID: {client_id}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            "https://openapi.ctrader.com/apps/token",
            auth=HTTPBasicAuth(client_id, CLIENT_SECRET),
            params={
                "grant_type": "refresh_token",
                "refresh_token": REFRESH_TOKEN
            },
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("errorCode"):
                print(f"❌ Error: {data.get('errorCode')} - {data.get('description')}")
            else:
                print("✅✅✅ SUCCESS! This format works!")
                print(f"New Access Token: {data.get('accessToken', '')[:40]}...")
                print(f"Expires In: {data.get('expiresIn')} seconds")
                break
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:100]}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

print("\n" + "=" * 60)
