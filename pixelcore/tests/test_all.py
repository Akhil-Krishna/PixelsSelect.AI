"""
Run all service tests in sequence.
Run: python test_all.py
"""
import subprocess
import sys

tests = [
    ("PostgreSQL",  "test_db.py"),
    ("Redis",       "test_redis.py"),
    ("Groq LLM",    "test_groq.py"),
    ("Groq STT",    "test_stt.py"),
    ("DeepFace",    "test_deepface.py"),
]

results = []

for name, script in tests:
    print(f"\n{'='*50}")
    print(f"RUNNING: {name}")
    print(f"{'='*50}")
    result = subprocess.run([sys.executable, script])
    passed = result.returncode == 0
    results.append((name, passed))

print(f"\n{'='*50}")
print("SUMMARY")
print(f"{'='*50}")
for name, passed in results:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}  {name}")