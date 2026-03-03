#!/usr/bin/env python3
"""
Refresh cTrader Access Token
Simple script to refresh your cTrader access token using the refresh token
"""
import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# cTrader credentials
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("CTRADER_REFRESH_TOKEN")

def refresh_token():
    """Refresh the access token"""
    print("\n" + "="*70)
    print("🔄 cTrader Token Refresh")
    print("="*70)
    
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("\n❌ Missing credentials in .env file")
        print("   Required: CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, CTRADER_REFRESH_TOKEN")
        return False
    
    print(f"\n✅ Credentials loaded")
    print(f"   Client ID: {CLIENT_ID[:20]}...")
    print(f"   Refresh Token: {REFRESH_TOKEN[:20]}...")
    
    print(f"\n🔄 Requesting new access token...")
    
    try:
        response = requests.post(
            "https://openapi.ctrader.com/apps/token",
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            data={
                "grant_type": "refresh_token",
                "refresh_token": REFRESH_TOKEN,
            },
            timeout=10
        )
        
        response.raise_for_status()
        data = response.json()
        
        print(f"\n📦 Response data: {data}")
        
        new_access_token = data.get("access_token") or data.get("accessToken")
        new_refresh_token = data.get("refresh_token") or data.get("refreshToken", REFRESH_TOKEN)
        
        print(f"\n✅ Token refreshed successfully!")
        print(f"\n📝 Update your .env file with these new values:")
        print(f"\n" + "-"*70)
        print(f"CTRADER_ACCESS_TOKEN={new_access_token}")
        if new_refresh_token != REFRESH_TOKEN:
            print(f"CTRADER_REFRESH_TOKEN={new_refresh_token}")
        print("-"*70)
        
        print(f"\n💡 Tip: Copy the lines above and update your .env file")
        print("="*70)
        
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if e.response:
            print(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = refresh_token()
    exit(0 if success else 1)
