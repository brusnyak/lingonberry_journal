#!/usr/bin/env python3
"""
Test if Client Secret should be used as Client ID
"""
import requests
from requests.auth import HTTPBasicAuth

# Maybe the "Secret" shown is actually the full Client ID?
CLIENT_ID_OPTION_1 = "14299_6GrwlOC8xpjw3wii01yK59g190srgNLugxrl8tLjS1yakA70ii"
CLIENT_SECRET_OPTION_1 = "03GGc3ehttopFBM159Ym6GkHuiE4e9hUgNMCa1eaM1JNYcPu6y"

# Or maybe they're swapped?
CLIENT_ID_OPTION_2 = "03GGc3ehttopFBM159Ym6GkHuiE4e9hUgNMCa1eaM1JNYcPu6y"
CLIENT_SECRET_OPTION_2 = "14299_6GrwlOC8xpjw3wii01yK59g190srgNLugxrl8tLjS1yakA70ii"

REFRESH_TOKEN = "9YBsB7pwWFIU19k6uryHJAadw3cLcb5Tl0_SJrMW048"

tests = [
    ("Normal (ID=14299..., Secret=03GGc...)", CLIENT_ID_OPTION_1, CLIENT_SECRET_OPTION_1),
    ("Swapped (ID=03GGc..., Secret=14299...)", CLIENT_ID_OPTION_2, CLIENT_SECRET_OPTION_2),
]

print("=" * 60)
print("Testing ID/Secret Combinations")
print("=" * 60)

for name, client_id, client_secret in tests:
    print(f"\n{name}")
    print(f"Client ID: {client_id[:40]}...")
    print(f"Client Secret: {client_secret[:40]}...")
    
    try:
        response = requests.post(
            "https://openapi.ctrader.com/apps/token",
            auth=HTTPBasicAuth(client_id, client_secret),
            params={
                "grant_type": "refresh_token",
                "refresh_token": REFRESH_TOKEN
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if not data.get("errorCode"):
                print("✅✅✅ SUCCESS!")
                print(f"Access Token: {data.get('accessToken', '')[:40]}...")
                break
            else:
                print(f"❌ {data.get('errorCode')}: {data.get('description')}")
        else:
            print(f"❌ HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ {e}")

print("\n" + "=" * 60)
