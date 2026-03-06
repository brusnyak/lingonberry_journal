#!/usr/bin/env python3
import os
import sqlite3

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "journal.db")
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Checking for indicator_data column...")
        cursor.execute("SELECT indicator_data FROM trades LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding indicator_data column...")
        cursor.execute("ALTER TABLE trades ADD COLUMN indicator_data TEXT")

    try:
        print("Checking for meta_data column...")
        cursor.execute("SELECT meta_data FROM trades LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding meta_data column...")
        cursor.execute("ALTER TABLE trades ADD COLUMN meta_data TEXT")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
