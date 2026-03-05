#!/usr/bin/env python3
"""
Quick test to verify webapp setup
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all imports work"""
    print("Testing imports...")
    try:
        from webapp import app
        from bot import journal_db
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_database():
    """Test database connection"""
    print("\nTesting database...")
    try:
        from bot import journal_db
        journal_db.init_db()
        accounts = journal_db.get_accounts()
        print(f"✅ Database connected - {len(accounts)} account(s) found")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_templates():
    """Test that required templates exist"""
    print("\nTesting templates...")
    templates = ['index.html', 'mini.html', 'analytics.html', 'weekly.html']
    missing = []
    
    for template in templates:
        path = f"webapp/templates/{template}"
        if os.path.exists(path):
            print(f"✅ {template} exists")
        else:
            print(f"❌ {template} missing")
            missing.append(template)
    
    return len(missing) == 0

def test_static_files():
    """Test that static files exist"""
    print("\nTesting static files...")
    files = [
        'webapp/static/css/style.css',
        'webapp/static/js/api.js',
        'webapp/static/js/charts.js'
    ]
    missing = []
    
    for file in files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
            missing.append(file)
    
    return len(missing) == 0

def main():
    print("=" * 50)
    print("Lingonberry Journal - Webapp Test")
    print("=" * 50)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Database", test_database()))
    results.append(("Templates", test_templates()))
    results.append(("Static Files", test_static_files()))
    
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 All tests passed! You can now run:")
        print("   make webapp")
        print("   Then open: http://localhost:5000")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
