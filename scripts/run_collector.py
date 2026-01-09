import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app.services.collector import collector
from dotenv import load_dotenv

# Load env variables (Just in case, though collector imports client which imports config which loads .env)
# But config.py loads .env from CWD usually.
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

if __name__ == "__main__":
    print("Running collector manually...")
    collector.update_stock_list()
    print("Done.")
