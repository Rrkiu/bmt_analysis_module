import os
import cv2
import numpy as np
import torch
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import io
from PIL import Image

from model import TrackNet, InpaintNet
from utils.general import get_model, WIDTH, HEIGHT, to_img, to_img_format
from test import predict_location
import zmq
import threading

import time
from functools import wraps

def time_logger(name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            print(f"⏱️  [Model Server: {name}] {duration:.1f}ms")
            return result
        return wrapper
    return decorator

app = FastAPI(title="TrackNetV3 Inference Server")

# Global variables for models
tracknet = None
inpaintnet = None
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
seq_len = 8 # Default for TrackNetV3
bg_mode = ''

# Strategy A: Session-based buffer management on server side
from collections import deque
session_buffers = {}

def load_models(tracknet_path: str, inpaintnet_path: str = None):
    global tracknet, inpaintnet, seq_len, bg_mode
    
    print(f"Loading TrackNet from {tracknet_path}...")
    tracknet_ckpt = torch.load(tracknet_path, map_location=device)
    seq_len = tracknet_ckpt['param_dict']['seq_len']
    bg_mode = tracknet_ckpt['param_dict']['bg_mode']
    
    print(f"Model properties: seq_len={seq_len}, bg_mode={bg_mode}")
    
    tracknet = get_model('TrackNet', seq_len, bg_mode).to(device)
    tracknet.load_state_dict(tracknet_ckpt['model'])
    
    if device.type == 'cuda':
        tracknet = tracknet.half()
        print("TrackNet converted to FP16 (Half)")
    
    tracknet.eval()
    
    if inpaintnet_path and os.path.exists(inpaintnet_path):
        print(f"Loading InpaintNet from {inpaintnet_path}...")
        inpaintnet_ckpt = torch.load(inpaintnet_path, map_location=device)
        inpaintnet = get_model('InpaintNet').to(device)
        inpaintnet.load_state_dict(inpaintnet_ckpt['model'])
        
        if device.type == 'cuda':
            inpaintnet = inpaintnet.half()
            print("InpaintNet converted to FP16 (Half)")
            
        inpaintnet.eval()
    
    print("Models loaded successfully.")

@app.on_event("startup")
async def startup_event():
    # Attempt to load default models if they exist
    tracknet_path = "ckpts/TrackNet_best.pt"
    inpaintnet_path = "ckpts/InpaintNet_best.pt"
    if os.path.exists(tracknet_path):
        load_models(tracknet_path, inpaintnet_path)
    else:
        print(f"Warning: Default model path {tracknet_path} not found. Please load models via API or environment variables.")

class PredictionResponse(BaseModel):
    x: int
    y: int
    visibility: int

@app.post("/predict_frame", response_model=PredictionResponse)
@time_logger("Strategy A: Predict Single Frame")
async def predict_frame(
    session_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Strategy A: Receives only ONE frame, manages buffer internally.
    """
    if tracknet is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    # 1. Initialize or get session buffer
    if session_id not in session_buffers:
        session_buffers[session_id] = deque(maxlen=seq_len)
    
    buffer = session_buffers[session_id]

    # 2. Decode and preprocess the single frame
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image data")
    
    img_resized = cv2.resize(img, (WIDTH, HEIGHT))
    f = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    f = f.transpose(2, 0, 1) # (C, H, W)
    
    # 3. Add to session buffer
    buffer.append(f)

    # 4. Check if we have enough history to predict
    if len(buffer) < seq_len:
        return PredictionResponse(x=0, y=0, visibility=0)

    # 5. Prepare input sequence
    input_frames = list(buffer)
    
    if bg_mode == 'concat':
        # Use median of the current buffer as background
        median_frame = np.median(np.stack(input_frames), axis=0)
        input_frames.insert(0, median_frame)
    
    x_input = np.concatenate(input_frames, axis=0)
    x_input = torch.from_numpy(x_input).to(device)
    
    if device.type == 'cuda':
        x_input = x_input.half() / 255.0
    else:
        x_input = x_input.float() / 255.0
        
    x_input = x_input.unsqueeze(0) # (1, Channels, H, W)

    try:
        with torch.no_grad():
            y_pred = tracknet(x_input).detach().cpu()
        
        y_pred = (y_pred > 0.5).numpy()
        
        # We only care about the prediction of the LATEST frame (index seq_len - 1)
        heatmap = y_pred[0][seq_len - 1]
        bbox_pred = predict_location(to_img(heatmap))
        cx, cy = int(bbox_pred[0] + bbox_pred[2]/2), int(bbox_pred[1] + bbox_pred[3]/2)
        vis = 0 if cx == 0 and cy == 0 else 1
        
        return PredictionResponse(x=cx, y=cy, visibility=vis)
    except Exception as e:
        print(f"Inference error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict_sequence", response_model=List[PredictionResponse])
@time_logger("Full Inference Process")
async def predict_sequence(files: List[UploadFile] = File(...)):
    """
    Expects a sequence of frames (default 8).
    Returns coordinates for EACH frame in the sequence (usually we care about the last one).
    """
    if len(files) != seq_len:
        raise HTTPException(status_code=400, detail=f"Expected {seq_len} frames, got {len(files)}")

    frames = []
    for file in files:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
        
        # Resize to TrackNet input size
        img_resized = cv2.resize(img, (WIDTH, HEIGHT))
        frames.append(img_resized)

    # Prepare input tensor
    input_frames = []
    for frame in frames:
        f = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        f = f.transpose(2, 0, 1) # (C, H, W)
        input_frames.append(f)
    
    # Handle background mode
    if bg_mode == 'concat':
        # Use median of the sequence as a background fallback
        median_frame = np.median(np.stack(input_frames), axis=0)
        input_frames.insert(0, median_frame)
    elif bg_mode == 'subtract':
        # Not implemented here yet, but usually handled in dataset
        pass
    
    x_input = np.concatenate(input_frames, axis=0)
    x_input = torch.from_numpy(x_input).to(device)
    
    if device.type == 'cuda':
        x_input = x_input.half() / 255.0
    else:
        x_input = x_input.float() / 255.0
        
    x_input = x_input.unsqueeze(0) # Add batch dim: (1, Channels, H, W)

    try:
        with torch.no_grad():
            y_pred = tracknet(x_input).detach().cpu() # (1, L, H, W)
        
        # Process heatmap to coordinates
        y_pred = (y_pred > 0.5).numpy()
        
        results = []
        for f in range(seq_len):
            heatmap = y_pred[0][f]
            bbox_pred = predict_location(to_img(heatmap))
            cx, cy = int(bbox_pred[0] + bbox_pred[2]/2), int(bbox_pred[1] + bbox_pred[3]/2)
            vis = 0 if cx == 0 and cy == 0 else 1
            results.append(PredictionResponse(x=cx, y=cy, visibility=vis))

        return results
    except Exception as e:
        print(f"Error during inference: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "tracknet_loaded": tracknet is not None, "bg_mode": bg_mode, "seq_len": seq_len}

def zmq_server():
    """
    ZeroMQ Server for Strategy B: Ultra-low latency binary communication.
    """
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:8002")
    print("🚀 ZeroMQ Server started on port 8002")

    while True:
        try:
            # Receive metadata and frame
            message = socket.recv_multipart()
            session_id = message[0].decode('utf-8')
            frame_bytes = message[1]

            if tracknet is None:
                socket.send_json({"error": "Model not loaded"})
                continue

            # 1. Get session buffer
            if session_id not in session_buffers:
                session_buffers[session_id] = deque(maxlen=seq_len)
            buffer = session_buffers[session_id]

            # 2. Decode and preprocess
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                socket.send_json({"error": "Invalid image"})
                continue

            img_resized = cv2.resize(img, (WIDTH, HEIGHT))
            f = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
            f = f.transpose(2, 0, 1) # (C, H, W)
            
            # 3. Add to buffer
            buffer.append(f)

            if len(buffer) < seq_len:
                socket.send_json({"x": 0, "y": 0, "visibility": 0})
                continue

            # 4. Inference
            input_frames = list(buffer)
            if bg_mode == 'concat':
                median_frame = np.median(np.stack(input_frames), axis=0)
                input_frames.insert(0, median_frame)
            
            x_input = np.concatenate(input_frames, axis=0)
            x_input = torch.from_numpy(x_input).to(device)
            
            if device.type == 'cuda':
                x_input = x_input.half() / 255.0
            else:
                x_input = x_input.float() / 255.0
                
            x_input = x_input.unsqueeze(0)

            with torch.no_grad():
                y_pred = tracknet(x_input).detach().cpu().numpy()
            
            y_pred = (y_pred > 0.5)
            heatmap = y_pred[0][seq_len - 1]
            bbox_pred = predict_location(to_img(heatmap))
            cx, cy = int(bbox_pred[0] + bbox_pred[2]/2), int(bbox_pred[1] + bbox_pred[3]/2)
            vis = 0 if cx == 0 and cy == 0 else 1
            
            # 5. Fast JSON reply
            socket.send_json({"x": cx, "y": cy, "visibility": vis})

        except Exception as e:
            print(f"ZMQ Error: {e}")
            try:
                socket.send_json({"error": str(e)})
            except:
                pass

if __name__ == "__main__":
    # Start ZMQ server in a separate thread
    zmq_thread = threading.Thread(target=zmq_server, daemon=True)
    zmq_thread.start()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
