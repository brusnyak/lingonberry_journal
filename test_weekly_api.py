#!/usr/bin/env python3
"""
Quick test script for weekly review API endpoints
Run this after starting the Flask app to verify everything works
"""

import requests
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000"

def get_monday(date=None):
    """Get Monday of the current week"""
    if date is None:
        date = datetime.now()
    day_of_week = date.weekday()
    monday = date - timedelta(days=day_of_week)
    return monday.strftime('%Y-%m-%d')

def test_trades_by_week():
    """Test GET /api/trades/week"""
    week_start = get_monday()
    print(f"\n📅 Testing trades for week starting {week_start}")
    
    # Test real trades
    response = requests.get(f"{BASE_URL}/api/trades/week", params={
        "account_id": 1,
        "week_start": week_start,
        "is_perfect": "false"
    })
    
    if response.status_code == 200:
        trades = response.json()
        print(f"✅ Real trades: {len(trades)} found")
        if trades:
            print(f"   First trade: {trades[0].get('symbol')} {trades[0].get('direction')}")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
    
    # Test perfect trades
    response = requests.get(f"{BASE_URL}/api/trades/week", params={
        "account_id": 1,
        "week_start": week_start,
        "is_perfect": "true"
    })
    
    if response.status_code == 200:
        trades = response.json()
        print(f"✅ Perfect trades: {len(trades)} found")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")

def test_week_stats():
    """Test GET /api/trades/week/stats"""
    week_start = get_monday()
    print(f"\n📊 Testing stats for week starting {week_start}")
    
    response = requests.get(f"{BASE_URL}/api/trades/week/stats", params={
        "account_id": 1,
        "week_start": week_start,
        "is_perfect": "false"
    })
    
    if response.status_code == 200:
        stats = response.json()
        print(f"✅ Stats loaded:")
        print(f"   Total trades: {stats.get('total_trades')}")
        print(f"   Win rate: {stats.get('win_rate')}%")
        print(f"   Net P&L: ${stats.get('net_pnl')}")
        print(f"   Profit factor: {stats.get('profit_factor')}")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")

def test_weekly_reflection():
    """Test POST /api/review/week"""
    week_start = get_monday()
    print(f"\n📝 Testing weekly reflection save")
    
    response = requests.post(f"{BASE_URL}/api/review/week", json={
        "account_id": 1,
        "week_start": week_start,
        "summary": "Test reflection from API test script",
        "key_wins": "Testing went well",
        "key_mistakes": "None",
        "next_week_focus": "Deploy to production"
    })
    
    if response.status_code == 200:
        print(f"✅ Reflection saved")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
    
    # Verify it was saved
    response = requests.get(f"{BASE_URL}/api/review/week", params={
        "account_id": 1,
        "week_start": week_start
    })
    
    if response.status_code == 200:
        review = response.json()
        print(f"✅ Reflection retrieved: {review.get('summary')[:50]}...")
    else:
        print(f"❌ Failed to retrieve: {response.status_code}")

def main():
    print("=" * 60)
    print("Weekly Review API Test Suite")
    print("=" * 60)
    print(f"Testing against: {BASE_URL}")
    print(f"Make sure the Flask app is running!")
    print("=" * 60)
    
    try:
        # Test if server is running
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print("❌ Server not responding. Start the Flask app first!")
            return
        
        print("✅ Server is running\n")
        
        # Run tests
        test_trades_by_week()
        test_week_stats()
        test_weekly_reflection()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure Flask app is running on port 5000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
