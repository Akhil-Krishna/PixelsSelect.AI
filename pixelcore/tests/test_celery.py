"""
Test Celery worker is connected and processing tasks.
Run: python test_celery.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 50)
print("TEST: Celery Worker")
print("=" * 50)

CELERY_ENABLED = os.getenv("CELERY_ENABLED", "false").lower() == "true"
BROKER_URL = os.getenv("CELERY_BROKER_URL", "")

if not CELERY_ENABLED:
    print("⚠️  CELERY_ENABLED=false in .env")
    print("   Change it to true first, then re-run this test")
    sys.exit(0)

print(f"✅ CELERY_ENABLED=true")
print(f"   Broker: {BROKER_URL}")

try:
    from app.core.celery_app import celery_app

    print("\nPinging Celery worker...")
    # ping with 5 second timeout
    response = celery_app.control.ping(timeout=5)

    if response:
        for worker, reply in response[0].items():
            print(f"✅ Worker responded: {worker} → {reply}")
    else:
        print("❌ No workers responded")
        print("   Make sure the worker is running:")
        print("   celery -A app.core.celery_app worker --loglevel=info")

except Exception as e:
    print(f"❌ Celery test FAILED: {e}")

print("\nCelery test done.")