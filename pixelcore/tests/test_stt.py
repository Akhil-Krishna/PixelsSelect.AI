"""
Test Groq Whisper STT.
Generates a silent audio file and sends it to Groq STT.
Run: python test_stt.py
"""
import asyncio
import io
import os
import sys
import wave
import struct
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")

print("=" * 50)
print("TEST: Groq Whisper STT")
print("=" * 50)

if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY not set in .env")
    sys.exit(1)

print(f"✅ GROQ_API_KEY found")
print(f"   STT Model: {GROQ_STT_MODEL}")


def make_test_wav() -> bytes:
    """Generate a short WAV file with a simple sine wave tone."""
    import math
    sample_rate = 16000
    duration = 2  # seconds
    frequency = 440  # Hz (A note)

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        samples = []
        for i in range(sample_rate * duration):
            val = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            samples.append(struct.pack('<h', val))
        wf.writeframes(b''.join(samples))
    return buf.getvalue()


async def test_stt():
    import httpx

    wav_bytes = make_test_wav()
    print(f"\nGenerated test WAV: {len(wav_bytes)} bytes")
    print("Sending to Groq STT...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": ("test.wav", wav_bytes, "audio/wav")},
                data={"model": GROQ_STT_MODEL, "language": "en"},
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("text", "").strip()
            print(f"✅ Groq STT responded")
            print(f"   Transcription: {text!r}")
            if not text:
                print("   (Empty transcription is normal for a sine tone — API is working)")
    except Exception as e:
        print(f"❌ Groq STT FAILED: {e}")


asyncio.run(test_stt())
print("\nSTT test done.")

