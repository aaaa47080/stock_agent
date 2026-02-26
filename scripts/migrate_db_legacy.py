import os
import sys
import json
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not found.")
        return

    print("Connecting to Database...")
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        # 1. Ensure Source Table Exists
        cursor.execute("SELECT to_regclass('public.codebook_v4')")
        if not cursor.fetchone()[0]:
            print("⚠️ Source table codebook_v4 does not exist. Nothing to migrate.")
            return

        # 2. Ensure Target Table Exists (Fresh Start)
        cursor.execute("DROP TABLE IF EXISTS agent_codebook")
        conn.commit()
        
        cursor.execute("""
        CREATE TABLE agent_codebook (
            id TEXT PRIMARY KEY,
            data JSONB NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );
        """)
        conn.commit()
        
        # 3. Migrate Data
        cursor.execute("SELECT id, data, is_active FROM codebook_v4")
        rows = cursor.fetchall()
        print(f"Found {len(rows)} entries in codebook_v4.")
        
        migrated_count = 0
        for row in rows:
            entry_id = row['id']
            data = row['data']
            is_active = row['is_active']
            
            # Transform: symbols -> topics
            if "symbols" in data and "topics" not in data:
                data["topics"] = data.pop("symbols")
            
            # Insert into new table
            cursor.execute(
                "INSERT INTO agent_codebook (id, data, is_active) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, is_active = EXCLUDED.is_active",
                (entry_id, json.dumps(data), is_active)
            )
            migrated_count += 1
                
        conn.commit()
        print(f"✅ Successfully migrated {migrated_count} entries to 'agent_codebook'.")
        conn.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate_db()
