#!/bin/bash
# Frontend 개발 서버 실행 스크립트

# nvm 로드
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Node.js 20 사용
nvm use 20

# 개발 서버 실행
npm run dev
