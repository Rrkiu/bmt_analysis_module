docker start -itd --gpus all \
    --shm-size=8gb \
    -p 8001:8000 \
    -p 8002:8002 \
    -v $(pwd):/workspace \
    -w /workspace/TrackNetV3 \
    --name tracknet_test \
    tracknet_inference:2512 