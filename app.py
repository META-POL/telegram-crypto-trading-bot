#!/usr/bin/env python3
"""
Railway 배포용 Flask 서버
텔레그램 봇은 나중에 추가 예정
"""

import os
from datetime import datetime
from flask import Flask, jsonify

# Flask 앱 생성
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({
        "status": "healthy", 
        "message": "Telegram Crypto Trading Bot is running!",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "message": "Health check endpoint",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/status')
def status():
    return jsonify({
        "status": "running",
        "service": "telegram-crypto-trading-bot",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test')
def test():
    return jsonify({
        "message": "Test endpoint working!",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Flask 서버 시작 중... 포트: {port}")
    print(f"🌐 서버 URL: http://0.0.0.0:{port}")
    print(f"🌐 헬스체크 URL: http://0.0.0.0:{port}/")
    print(f"🌐 상태 URL: http://0.0.0.0:{port}/status")
    print(f"🧪 테스트 URL: http://0.0.0.0:{port}/test")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False)
        print("✅ Flask 서버가 성공적으로 시작되었습니다!")
    except Exception as e:
        print(f"❌ Flask 서버 오류: {e}")
        print(f"❌ 오류 상세: {str(e)}")
        import traceback
        print(f"❌ 스택 트레이스: {traceback.format_exc()}") 