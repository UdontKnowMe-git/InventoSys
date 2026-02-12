import os
import psycopg2
from dotenv import load_dotenv

# 1. Load the .env file
load_dotenv()

# 2. Get the URL
db_url = os.getenv("DATABASE_URL")

print("--- DIAGNOSTIC TEST ---")

if not db_url:
    print("❌ ERROR: Could not find DATABASE_URL in .env file.")
    print("   Make sure you have a file named '.env' (no name, just extension).")
else:
    print(f"✅ Found URL: {db_url[:20]}... (hidden)")

# 3. Attempt Connection
try:
    print("Attempting to connect to Neon PostgreSQL...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # 4. Run a simple query
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    
    print("\n🎉 SUCCESS! Connected to:")
    print(db_version[0])
    
    conn.close()
    
except Exception as e:
    print("\n❌ CONNECTION FAILED")
    print("Error Details:")
    print(str(e))
    
print("-----------------------")