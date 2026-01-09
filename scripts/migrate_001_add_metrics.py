import psycopg2
import os
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

# Supabase provides a connection string or we construct it.
# Check if DATABASE_URL exists, otherwise construct from generic envs if possible or ask user.
# Usually Supabase provides a transaction pooling URL or session URL. 
# For now, let's try to parse the default Postgres connection string if USER hasn't provided one explicitly, 
# but usually .env from "supabase status" contains "DB_URL" or similar? 
# "supabase status" typically gives: 'DB URL: postgresql://postgres:postgres@localhost:54322/postgres'
# We might need to ask the user or guess. 
# LOCAL Supabase usually is: postgresql://postgres:postgres@127.0.0.1:54322/postgres
# Let's try to look for DB_URL or construct it. The user has `.env` with SUPABASE_URL/KEY, but not necessarily DB connection string.

# However, for Local Supabase, the default password is often 'postgres' or 'your-super-secret-and-long-postgres-password' or similar. 
# Wait, "supabase start" asks for a password or generates one? 
# Usually "supabase start" runs on localhost:54322 with user 'postgres' and password 'postgres' (by default for some versions) or requires config.

# Let's try the standard local supabase port.
DB_HOST = "127.0.0.1"
DB_PORT = "54322"
DB_NAME = "postgres"
DB_USER = "postgres"
# If this fails, we might need to ask the user for the DB URI.
DB_PASS = "postgres" 

def run_migration():
    print("Connecting to Local Supabase DB...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Adding columns to daily_candles...")
        
        # Add change_rate
        try:
            cur.execute("ALTER TABLE daily_candles ADD COLUMN IF NOT EXISTS change_rate NUMERIC;")
            print("- Added change_rate")
        except Exception as e:
            print(f"- change_rate error: {e}")

        # Add market_cap
        try:
            cur.execute("ALTER TABLE daily_candles ADD COLUMN IF NOT EXISTS market_cap BIGINT;")
            print("- Added market_cap")
        except Exception as e:
            print(f"- market_cap error: {e}")
            
        cur.close()
        conn.close()
        print("Migration completed.")
        
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Please ensure Supabase is running and credentials are correct (Default: localhost:54322, postgres/postgres).")

if __name__ == "__main__":
    run_migration()
