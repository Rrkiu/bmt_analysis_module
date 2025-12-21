# 베이스 이미지를 Python 3.8이 기본인 이미지로 교체 (키 업데이트 코드 포함)
FROM nvidia/cuda:11.3.1-cudnn8-devel-ubuntu20.04

# 기본 패키지 및 Python 3.8 설치
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3.8 \
    python3.8-dev \
    python3-pip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 기본 설정
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1
RUN python3 -m pip install --upgrade pip

# 이후 과정 동일...
WORKDIR /workspace
COPY requirements.txt .
# PyTorch 1.10.0을 CUDA 11.3 버전에 맞춰 직접 설치
RUN pip install torch==1.10.0+cu113 torchvision==0.11.1+cu113 -f https://download.pytorch.org/whl/cu113/torch_stable.html
RUN pip install --no-cache-dir -r requirements.txt

# Dockerfile 내 수정 예시
RUN pip install --no-cache-dir tqdm pycocotools fastapi uvicorn python-multipart pyzmq