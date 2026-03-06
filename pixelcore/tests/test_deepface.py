"""
Test DeepFace + OpenCV installation.
Run: python test_deepface.py
"""
import sys
import time

print("=" * 50)
print("TEST 1: numpy")
print("=" * 50)
try:
    import numpy as np
    print(f"✅ numpy {np.__version__}")
except ImportError as e:
    print(f"❌ numpy FAILED: {e}")
    sys.exit(1)

print()
print("=" * 50)
print("TEST 2: OpenCV")
print("=" * 50)
try:
    import cv2
    print(f"✅ OpenCV {cv2.__version__}")

    # Test face detector loads
    xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(xml)
    if cascade.empty():
        print("❌ Haar cascade failed to load")
    else:
        print("✅ Haar cascade loaded")
except ImportError as e:
    print(f"❌ OpenCV FAILED: {e}")

print()
print("=" * 50)
print("TEST 3: DeepFace import")
print("=" * 50)
try:
    from deepface import DeepFace
    print("✅ DeepFace imported successfully")
except ImportError as e:
    print(f"❌ DeepFace FAILED: {e}")
    sys.exit(1)

print()
print("=" * 50)
print("TEST 4: DeepFace analyze (synthetic image)")
print("=" * 50)
try:
    # Create a small synthetic test image (solid grey — won't detect a face
    # but tests that DeepFace runs without crashing)
    img = np.full((224, 224, 3), 128, dtype=np.uint8)

    print("Running DeepFace.analyze (enforce_detection=False)...")
    t0 = time.perf_counter()
    result = DeepFace.analyze(
        img_path=img,
        actions=["emotion"],
        enforce_detection=False,
        silent=True,
        detector_backend="opencv",
    )
    elapsed = time.perf_counter() - t0

    face_data = result[0] if isinstance(result, list) else result
    dominant = face_data.get("dominant_emotion", "unknown")
    print(f"✅ DeepFace.analyze completed in {elapsed:.2f}s")
    print(f"   Dominant emotion: {dominant}")
    print(f"   Emotions: {face_data.get('emotion', {})}")

except Exception as e:
    print(f"❌ DeepFace.analyze FAILED: {e}")

print()
print("All DeepFace tests done.")