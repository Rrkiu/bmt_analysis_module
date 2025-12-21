import requests
import cv2
import numpy as np

def test_api():
    url = "http://localhost:8001/predict_sequence"
    # Create 8 dummy frames
    files = []
    for i in range(8):
        img = np.zeros((288, 512, 3), dtype=np.uint8)
        _, img_encoded = cv2.imencode('.jpg', img)
        files.append(('files', (f'frame_{i}.jpg', img_encoded.tobytes(), 'image/jpeg')))
    
    try:
        print(f"Connecting to {url}...")
        response = requests.post(url, files=files, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
