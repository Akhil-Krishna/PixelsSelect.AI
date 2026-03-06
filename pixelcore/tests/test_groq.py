"""
Test Groq LLM API connection.
Run: python test_groq.py
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

print("=" * 50)
print("TEST: Groq LLM")
print("=" * 50)

if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY not set in .env")
    sys.exit(1)

print(f"✅ GROQ_API_KEY found (starts with: {GROQ_API_KEY[:8]}...)")
print(f"   Model: {GROQ_MODEL}")

async def test_groq():
    import httpx

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say exactly: GROQ_TEST_OK"},
        ],
        "max_tokens": 20,
        "temperature": 0,
    }

    print("\nSending test message to Groq API...")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"].strip()
            print(f"✅ Groq responded: {reply!r}")
            print(f"   Tokens used: {data.get('usage', {})}")
    except Exception as e:
        print(f"❌ Groq API FAILED: {e}")

asyncio.run(test_groq())
print("\nGroq test done.")