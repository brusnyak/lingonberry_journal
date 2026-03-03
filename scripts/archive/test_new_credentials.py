#!/usr/bin/env python3
"""
Test the NEW cTrader credentials directly
"""
import requests
from requests.auth import HTTPBasicAuth

# Your NEW credentials
CLIENT_ID = "14299_6GrwlOC8xpjw3wii01yK59g190srgNLugxrl8tLjS1yakA70ii"
CLIENT_SECRET = "03GGc3ehttopFBM159Ym6GkHuiE4e9hUgNMCa1eaM1JNYcPu6y"
ACCESS_TOKEN = "VyocCAB39CHzt_ckHfbjZTYNzisFklZ8yRfXS7o6qxw"
REFRESH_TOKEN = "9YBsB7pwWFIU19k6uryHJAadw3cLcb5Tl0_SJrMW048"
ACCOUNT_ID = "44798689"

print("=" * 60)
print("Testing NEW cTrader Credentials")
print("=" * 60)

print(f"\n📋 Credentials:")
print(f"   Client ID: {CLIENT_ID[:30]}...")
print(f"   Client Secret: {CLIENT_SECRET[:30]}...")
print(f"   Access Token: {ACCESS_TOKEN[:30]}...")
print(f"   Refresh Token: {REFRESH_TOKEN[:30]}...")
print(f"   Account ID: {ACCOUNT_ID}")

print("\n🔄 Testing token refresh...")

try:
    response = requests.post(
        "https://openapi.ctrader.com/apps/token",
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
        params={
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN
        },
        timeout=10
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        if data.get("errorCode"):
            print(f"\n❌ API Error: {data.get('errorCode')}")
            print(f"   Description: {data.get('description')}")
        else:
            print("\n✅✅✅ SUCCESS! Credentials are VALID! ✅✅✅")
            print(f"\n📝 Token info:")
            print(f"   New Access Token: {data.get('accessToken', '')[:40]}...")
            print(f"   New Refresh Token: {data.get('refreshToken', '')[:40]}...")
            print(f"   Expires In: {data.get('expiresIn')} seconds (~{data.get('expiresIn', 0) // 86400} days)")
            print(f"   Token Type: {data.get('tokenType')}")
            
            print("\n🎉 Your credentials work perfectly!")
            print("   You can now fetch market data from cTrader API")
    else:
        print(f"\n❌ Failed: {response.status_code}")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "=" * 60)
