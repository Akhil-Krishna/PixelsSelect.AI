"""
Test Kokoro TTS — runs entirely local, no server needed.
Run: python test_kokoro.py
"""
import time
import sys

print("=" * 50)
print("TEST: Kokoro TTS")
print("=" * 50)

try:
    from kokoro import KPipeline
    print("✅ Kokoro imported")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("   Run: pip install kokoro soundfile")
    sys.exit(1)

print("\nLoading pipeline (downloads ~300MB on first run)...")
t0 = time.perf_counter()
pipeline = KPipeline(lang_code='a')  # 'a' = American English
load_time = time.perf_counter() - t0
print(f"✅ Loaded in {load_time:.1f}s")

text = "Hello, welcome to the HireAI interview platform. Please introduce yourself."
print(f"\nGenerating: {text!r}")

t0 = time.perf_counter()
import soundfile as sf
import numpy as np

samples = []
for _, _, audio in pipeline(text, voice='af_heart', speed=1.0):
    samples.append(audio)

audio_out = np.concatenate(samples)
gen_time = time.perf_counter() - t0

sf.write("test_kokoro.wav", audio_out, 24000)
print(f"✅ Generated in {gen_time:.2f}s")
print(f"   Saved: test_kokoro.wav")
print(f"\nPlay with: afplay test_kokoro.wav")