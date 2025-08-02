#!/usr/bin/env python3

import os
from datetime import datetime
from flask import Flask, jsonify

# Flask 앱 생성
app = Flask(__name__)

@app.route('/')
def health_check():
    try:
        return jsonify({
            "status": "healthy", 
            "message": "Simple Test Bot",
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/health')
def health():
    try:
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "message": "Simple health check"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        print(f"🚀 간단한 테스트 서버 시작: 포트 {port}")
        print(f"🌐 환경 변수 PORT: {os.environ.get('PORT', '기본값 5000')}")
        
        # Flask 서버 시작
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"❌ 서버 시작 오류: {e}")
        import traceback
        print(f"❌ 스택 트레이스: {traceback.format_exc()}") 