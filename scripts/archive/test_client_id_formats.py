#!/usr/bin/env python3
"""
Test different Client ID formats to find the correct one
"""
import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

def test_format(client_id, client_secret, refresh_token, description):
    """Test a specific credential format"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Client ID: {client_id}")
    print(f"{'='*60}")
    
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
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("errorCode"):
                print(f"❌ Error: {data.get('errorCode')} - {data.get('description')}")
                return False
            else:
                print("✅ SUCCESS! This format works!")
                print(f"New Access Token: {data.get('accessToken', '')[:40]}...")
                print(f"New Refresh Token: {data.get('refreshToken', '')[:40]}...")
                return True
        else:
            print(f"❌ Failed: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def main():
    original_client_id = os.getenv("CTRADER_CLIENT_ID")
    client_secret = os.getenv("CTRADER_CLIENT_SECRET")
    refresh_token = os.getenv("CTRADER_REFRESH_TOKEN")
    
    print("🔍 Testing different Client ID formats...")
    print(f"Original: {original_client_id}")
    
    # Test 1: Original format
    test_format(
        original_client_id,
        client_secret,
        refresh_token,
        "Original format (as-is)"
    )
    
    # Test 2: Just the number before underscore
    if "_" in original_client_id:
        just_number = original_client_id.split("_")[0]
        test_format(
            just_number,
            client_secret,
            refresh_token,
            "Just the number part (before underscore)"
        )
    
    # Test 3: The part after underscore
    if "_" in original_client_id:
        after_underscore = original_client_id.split("_", 1)[1]
        test_format(
            after_underscore,
            client_secret,
            refresh_token,
            "Part after underscore"
        )
    
    print("\n" + "="*60)
    print("Testing complete!")
    print("="*60)


if __name__ == "__main__":
    main()
