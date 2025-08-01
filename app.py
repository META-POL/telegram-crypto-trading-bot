#!/usr/bin/env python3
"""
Railway 배포용 텔레그램 봇 + Flask 서버
"""

import os
import threading
import logging
from datetime import datetime
from flask import Flask, jsonify

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

def run_telegram_bot():
    """텔레그램 봇 실행 함수"""
    try:
        # 환경 변수 확인
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        print(f"🔍 환경 변수 확인: TELEGRAM_BOT_TOKEN = {token}")
        
        if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN':
            print("❌ TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
            print("Railway 대시보드에서 환경 변수를 설정하세요.")
            print("토큰: 8356129181:AAF5bWX6z6HSAF2MeTtUIjx76jOW2i0Xj1I")
            return
        
        print("🤖 텔레그램 봇 시작 중...")
        print(f"🔑 토큰: {token[:10]}...{token[-10:]}")
        
        # 텔레그램 봇 라이브러리 import (오류 발생 시 Flask 서버는 계속 작동)
        try:
            print("📦 텔레그램 봇 라이브러리 import 중...")
            from telegram import Update
            from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
            print("✅ 텔레그램 봇 라이브러리 import 성공")
        except ImportError as e:
            print(f"❌ 텔레그램 봇 라이브러리 import 실패: {e}")
            print("💡 Flask 서버는 계속 작동합니다.")
            return
        
        # 애플리케이션 빌드
        print("🔧 텔레그램 애플리케이션 빌드 중...")
        telegram_app = ApplicationBuilder().token(token).build()
        print("✅ 텔레그램 애플리케이션 빌드 성공")
        
        # 기본 핸들러만 등록 (나머지는 나중에 추가)
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("�� 암호화폐 트레이딩 봇이 시작되었습니다!")
        
        telegram_app.add_handler(CommandHandler('start', start))
        print("✅ 핸들러 등록 완료")
        
        print("✅ 텔레그램 봇이 성공적으로 시작되었습니다!")
        print("🔄 폴링 시작...")
        
        # 폴링 시작
        telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ 텔레그램 봇 오류: {e}")
        print(f"❌ 오류 상세: {str(e)}")
        print("💡 Flask 서버는 계속 작동합니다.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Flask 서버 시작 중... 포트: {port}")
    print(f"🌐 서버 URL: http://0.0.0.0:{port}")
    print(f"🌐 헬스체크 URL: http://0.0.0.0:{port}/")
    print(f"🌐 상태 URL: http://0.0.0.0:{port}/status")
    print(f"🧪 테스트 URL: http://0.0.0.0:{port}/test")
    
    # 텔레그램 봇을 별도 스레드에서 실행
    try:
        telegram_thread = threading.Thread(target=run_telegram_bot)
        telegram_thread.daemon = True
        telegram_thread.start()
        print("✅ 텔레그램 봇 스레드 시작됨")
    except Exception as e:
        print(f"❌ 텔레그램 봇 스레드 시작 실패: {e}")
        print("💡 Flask 서버는 계속 작동합니다.")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False)
        print("✅ Flask 서버가 성공적으로 시작되었습니다!")
    except Exception as e:
        print(f"❌ Flask 서버 오류: {e}")
        print(f"❌ 오류 상세: {str(e)}")
        import traceback
        print(f"❌ 스택 트레이스: {traceback.format_exc()}") 