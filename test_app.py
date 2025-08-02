#!/usr/bin/env python3
"""
Railway 배포 테스트용 간단한 Flask 앱
"""

import os
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({
        "status": "healthy", 
        "message": "Test Flask App for Railway",
        "timestamp": datetime.now().isoformat(),
        "port": os.environ.get('PORT', 'default'),
        "environment": os.environ.get('RAILWAY_ENVIRONMENT', 'unknown')
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/test')
def test():
    return jsonify({
        "message": "Test endpoint working!",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        print(f"🚀 테스트 서버 시작: 포트 {port}")
        print(f"🌐 환경 변수 PORT: {os.environ.get('PORT', '기본값 5000')}")
        print(f"📁 현재 작업 디렉토리: {os.getcwd()}")
        print(f"📋 파일 목록: {os.listdir('.')}")
        
        # Flask 서버 시작
        print("🌐 Flask 서버 시작 중...")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"❌ 서버 시작 오류: {e}")
        import traceback
        print(f"❌ 스택 트레이스: {traceback.format_exc()}") 