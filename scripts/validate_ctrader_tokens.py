#!/usr/bin/env python3
"""
Validate cTrader API Tokens
Tests if your credentials are valid and can authenticate
"""
import os
import sys
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

def test_token_refresh():
    """Test if we can refresh the access token (validates all credentials)"""
    print("=" * 60)
    print("cTrader Token Validation")
    print("=" * 60)
    
    client_id = os.getenv("CTRADER_CLIENT_ID")
    client_secret = os.getenv("CTRADER_CLIENT_SECRET")
    refresh_token = os.getenv("CTRADER_REFRESH_TOKEN")
    access_token = os.getenv("CTRADER_ACCESS_TOKEN")
    
    print("\n📋 Checking credentials...")
    print(f"   Client ID: {client_id[:20] if client_id else 'MISSING'}...")
    print(f"   Client Secret: {client_secret[:20] if client_secret else 'MISSING'}...")
    print(f"   Access Token: {access_token[:20] if access_token else 'MISSING'}...")
    print(f"   Refresh Token: {refresh_token[:20] if refresh_token else 'MISSING'}...")
    
    if not all([client_id, client_secret, refresh_token]):
        print("\n❌ Missing required credentials!")
        print("\nPlease update your .env file with credentials from:")
        print("   https://openapi.ctrader.com/apps (Playground)")
        return False
    
    print("\n🔄 Testing token refresh endpoint...")
    print("   URL: https://openapi.ctrader.com/apps/token")
    
    try:
        response = requests.post(
            "https://openapi.ctrader.com/apps/token",
            auth=HTTPBasicAuth(client_id, client_secret),
            params={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            },
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("errorCode"):
                print(f"\n❌ API Error: {data.get('errorCode')}")
                print(f"   Description: {data.get('description')}")
                return False
            
            print("\n✅ Credentials are VALID!")
            print("\n📝 New tokens received:")
            print(f"   Access Token: {data.get('accessToken', '')[:30]}...")
            print(f"   Refresh Token: {data.get('refreshToken', '')[:30]}...")
            print(f"   Expires In: {data.get('expiresIn')} seconds (~{data.get('expiresIn', 0) // 86400} days)")
            
            print("\n💡 Update your .env file with these new tokens:")
            print(f"CTRADER_ACCESS_TOKEN={data.get('accessToken')}")
            print(f"CTRADER_REFRESH_TOKEN={data.get('refreshToken')}")
            
            return True
            
        elif response.status_code == 400:
            print("\n❌ Bad Request - Invalid credentials")
            print(f"   Response: {response.text}")
            print("\n💡 Your credentials may be:")
            print("   - Expired or revoked")
            print("   - From wrong environment (demo vs live)")
            print("   - Incorrectly copied")
            return False
            
        elif response.status_code == 401:
            print("\n❌ Unauthorized - Authentication failed")
            print("   Client ID or Client Secret is incorrect")
            return False
            
        else:
            print(f"\n❌ Unexpected response: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection Error - Cannot reach cTrader API")
        print("   Check your internet connection")
        return False
        
    except requests.exceptions.Timeout:
        print("\n❌ Timeout - cTrader API not responding")
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    result = test_token_refresh()
    
    print("\n" + "=" * 60)
    
    if result:
        print("✅ SUCCESS - Your credentials work!")
        print("=" * 60)
        print("\n📊 Next steps:")
        print("   1. Update .env with new tokens (shown above)")
        print("   2. Install Protobuf library: ./scripts/setup_ctrader.sh")
        print("   3. Test data fetching: python infra/ctrader_protobuf_client.py")
    else:
        print("❌ FAILED - Credentials are invalid")
        print("=" * 60)
        print("\n🔧 How to fix:")
        print("   1. Go to: https://openapi.ctrader.com/apps")
        print("   2. Click 'Playground' button")
        print("   3. Select scope (trading or accounts)")
        print("   4. Click 'Get token'")
        print("   5. Copy all 4 values:")
        print("      - Access Token")
        print("      - Refresh Token")
        print("      - Client ID")
        print("      - Client Secret")
        print("   6. Update your .env file")
        print("   7. Run this script again")


if __name__ == "__main__":
    main()
