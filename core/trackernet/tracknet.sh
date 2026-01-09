docker run -d --gpus all \
    --shm-size=8gb \
    -p 8001:8000 \
    -p 8002:8002 \
    -v $(pwd):/workspace \
    -w /workspace/TrackNetV3 \
    --name tracknet_api \
    tracknet_inference:2512 \
    python3 inference_server.py