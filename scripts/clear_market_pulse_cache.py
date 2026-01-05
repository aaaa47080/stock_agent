import sqlite3
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import DB_PATH

def clear_market_pulse_cache():
    print(f"Opening database at: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if key exists first
        c.execute("SELECT count(*) FROM system_cache WHERE key = 'MARKET_PULSE'")
        count = c.fetchone()[0]
        
        if count > 0:
            print(f"Found 'MARKET_PULSE' cache. Deleting...")
            c.execute("DELETE FROM system_cache WHERE key = 'MARKET_PULSE'")
            conn.commit()
            print("✅ Market Pulse cache cleared successfully.")
        else:
            print("ℹ️ No Market Pulse cache found to delete.")
            
        conn.close()
    except Exception as e:
        print(f"❌ Error clearing cache: {e}")

if __name__ == "__main__":
    clear_market_pulse_cache()
