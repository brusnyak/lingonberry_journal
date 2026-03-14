#!/usr/bin/env python3
"""
Fully automated cTrader access token refresh script for cron jobs.
Updates .env file immediately without user intervention.
"""
import os
import requests
import sys
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# Use absolute path to find .env if run from cron
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("CTRADER_REFRESH_TOKEN")
ENV_PATH = os.path.join(BASE_DIR, ".env")

def automate_refresh():
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("❌ Error: Missing cTrader credentials in .env")
        return False

    url = "https://openapi.ctrader.com/apps/token"
    try:
        response = requests.post(
            url,
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            data={
                "grant_type": "refresh_token",
                "refresh_token": REFRESH_TOKEN,
            },
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        new_access = data.get("access_token")
        new_refresh = data.get("refresh_token", REFRESH_TOKEN)
        
        if not new_access:
            print("❌ Error: No access_token in cTrader response")
            return False

        # Read current .env
        with open(ENV_PATH, 'r') as f:
            lines = f.readlines()

        # Update lines
        updated_lines = []
        found_access = False
        found_refresh = False
        
        for line in lines:
            if line.startswith("CTRADER_ACCESS_TOKEN="):
                updated_lines.append(f"CTRADER_ACCESS_TOKEN={new_access}\n")
                found_access = True
            elif line.startswith("CTRADER_REFRESH_TOKEN="):
                updated_lines.append(f"CTRADER_REFRESH_TOKEN={new_refresh}\n")
                found_refresh = True
            else:
                updated_lines.append(line)
        
        # If keys weren't found, append them
        if not found_access: updated_lines.append(f"CTRADER_ACCESS_TOKEN={new_access}\n")
        if not found_refresh: updated_lines.append(f"CTRADER_REFRESH_TOKEN={new_refresh}\n")

        # Write back to .env
        with open(ENV_PATH, 'w') as f:
            f.writelines(updated_lines)

        print(f"✅ Automated Refresh Success: New access token saved to {ENV_PATH}")
        return True

    except Exception as e:
        print(f"❌ Automated Refresh Failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = automate_refresh()
    sys.exit(0 if success else 1)
