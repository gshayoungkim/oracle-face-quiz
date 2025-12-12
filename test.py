# test.py
import os
from dotenv import load_dotenv

# .env 로드
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

print("URL:", url)
print("KEY prefix:", None if key is None else key[:10])
