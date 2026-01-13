
import sys
import os
import psycopg2

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

db_url = os.getenv("SUPABASE_URL") # This might be the REST URL, we need connection string?
db_key = os.getenv("SUPABASE_KEY")

# WARNING: 'supabase-py' client uses REST API which can't run DDL easily unless using RPC.
# We need direct Postgres connection to run DDL.
# Checking if we have a connection string in env.
# Usually SUPABASE_DB_URL is needed for direct postgres connection like: postgresql://postgres:[password]@db...

# Let's check environment variables, or try to use user provided info.
# The user env mostly has URL/KEY for REST.
# If I don't have direct DB access string, I can't restart schema easily via script unless I use a SQL client tool or RPC.

# Let's check .env content first? No, I shouldn't disclose secrets.
# But I can check if 'DATABASE_URL' exists.

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment. Cannot execute DDL.")
    print("Please add DATABASE_URL='postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres' to .env")
    # Try to construct it if user hasn't set it but we have partial info?
    # Actually, for Supabase, user usually knows.
    # If I can't connect, I will ask user.
else:
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Drop Tables
        print("Dropping tables (daily_technical_indicators, daily_candles)...")
        cur.execute("DROP TABLE IF EXISTS daily_technical_indicators CASCADE;")
        cur.execute("DROP TABLE IF EXISTS daily_candles CASCADE;")
        # Note: stocks table is master table, maybe keep it? Or drop to cleanly recreate refs?
        # User said "drop existing table and recreate". 
        # Schema file creates stocks first. If we change schema logic for stocks (we didn't), we can keep it.
        # But 'daily_candles' references 'stocks'. If we drop daily_candles, stocks is fine.
        # So we only drop the modified tables.
        
        # Read schema.sql
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'db', 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            
        # Execute Schema
        print("Applying new schema...")
        cur.execute(schema_sql)
        
        print("Schema reset successful.")
        conn.close()
        
    except Exception as e:
        print(f"Error resetting schema: {e}")
