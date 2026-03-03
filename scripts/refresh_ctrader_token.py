#!/usr/bin/env python3
"""
Refresh cTrader access token using refresh token
"""
import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("CTRADER_REFRESH_TOKEN")

def refresh_token():
    """Refresh the access token"""
    print("\n" + "="*70)
    print("🔄 Refreshing cTrader Access Token")
    print("="*70)
    
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("\n❌ Missing credentials in .env file")
        return False
    
    print(f"\n📝 Using credentials:")
    print(f"   Client ID: {CLIENT_ID[:20]}...")
    print(f"   Refresh Token: {REFRESH_TOKEN[:20]}...")
    
    # Token endpoint
    url = "https://openapi.ctrader.com/apps/token"
    
    # Request new token
    print(f"\n🔌 Requesting new token from: {url}")
    
    try:
        response = requests.post(
            url,
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            data={
                "grant_type": "refresh_token",
                "refresh_token": REFRESH_TOKEN,
            },
            timeout=10
        )
        
        response.raise_for_status()
        data = response.json()
        
        new_access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token", REFRESH_TOKEN)
        expires_in = data.get("expires_in", 0)
        
        print(f"\n✅ Token refreshed successfully!")
        print(f"   Expires in: {expires_in} seconds ({expires_in/86400:.1f} days)")
        
        print(f"\n📋 Update your .env file with these new values:")
        print(f"\nCTRADER_ACCESS_TOKEN={new_access_token}")
        print(f"CTRADER_REFRESH_TOKEN={new_refresh_token}")
        
        # Optionally update .env file automatically
        update = input("\n❓ Update .env file automatically? (y/n): ").strip().lower()
        
        if update == 'y':
            # Read current .env
            env_path = ".env"
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            # Update tokens
            with open(env_path, 'w') as f:
                for line in lines:
                    if line.startswith('CTRADER_ACCESS_TOKEN='):
                        f.write(f'CTRADER_ACCESS_TOKEN={new_access_token}\n')
                    elif line.startswith('CTRADER_REFRESH_TOKEN='):
                        f.write(f'CTRADER_REFRESH_TOKEN={new_refresh_token}\n')
                    else:
                        f.write(line)
            
            print(f"\n✅ .env file updated!")
        
        print("\n" + "="*70)
        print("✅ Complete!")
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
    import sys
    success = refresh_token()
    sys.exit(0 if success else 1)
