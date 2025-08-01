#!/usr/bin/env python3
"""
텔레그램 암호화폐 선물 거래 봇
futures_trader.py 기반
"""

import os
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask 앱 생성
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({
        "status": "healthy", 
        "message": "Telegram Crypto Futures Trading Bot",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# 사용자별 거래자 저장
user_traders = {}

def run_telegram_bot():
    """텔레그램 봇 실행"""
    try:
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        print(f"🔍 토큰 확인: {token}")
        
        if not token:
            print("❌ TELEGRAM_BOT_TOKEN이 설정되지 않음")
            return
        
        print("🤖 텔레그램 봇 시작...")
        
        from telegram import Update
        from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
        
        # futures_trader import
        from futures_trader import UnifiedFuturesTrader
        
        telegram_app = ApplicationBuilder().token(token).build()
        
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """봇 시작"""
            user_id = update.effective_user.id
            await update.message.reply_text(
                "🤖 **암호화폐 선물 거래 봇**\n\n"
                "사용 가능한 명령어:\n"
                "/start - 봇 시작\n"
                "/balance [거래소] - 잔고 조회\n"
                "/long [거래소] [심볼] [수량] [레버리지] - 롱 포지션\n"
                "/short [거래소] [심볼] [수량] [레버리지] - 숏 포지션\n"
                "/close [거래소] [심볼] - 포지션 종료\n"
                "/positions [거래소] - 포지션 조회\n"
                "/setapi [거래소] [API_KEY] [API_SECRET] - API 설정\n\n"
                "지원 거래소: xt, backpack, hyperliquid, flipster",
                parse_mode='Markdown'
            )
        
        async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """잔고 조회"""
            try:
                parts = update.message.text.split()
                if len(parts) < 2:
                    await update.message.reply_text("❌ 사용법: /balance [거래소]")
                    return
                
                exchange = parts[1].lower()
                user_id = update.effective_user.id
                
                # API 키 확인 (간단한 구현)
                api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                
                if not api_key or not api_secret:
                    await update.message.reply_text(f"❌ {exchange} API 키가 설정되지 않음")
                    return
                
                # 거래자 생성
                trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                balance_result = trader.get_futures_balance()
                
                if balance_result.get('status') == 'success':
                    balance_data = balance_result.get('balance', {})
                    await update.message.reply_text(f"💰 {exchange} 잔고: {balance_data}")
                else:
                    await update.message.reply_text(f"❌ 잔고 조회 실패: {balance_result}")
                    
            except Exception as e:
                await update.message.reply_text(f"❌ 오류: {str(e)}")
        
        async def long_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """롱 포지션 오픈"""
            try:
                parts = update.message.text.split()
                if len(parts) < 5:
                    await update.message.reply_text("❌ 사용법: /long [거래소] [심볼] [수량] [레버리지]")
                    return
                
                exchange = parts[1].lower()
                symbol = parts[2].upper()
                size = float(parts[3])
                leverage = int(parts[4])
                
                api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                
                if not api_key or not api_secret:
                    await update.message.reply_text(f"❌ {exchange} API 키가 설정되지 않음")
                    return
                
                trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                result = trader.open_long_position(symbol, size, leverage)
                
                if result.get('status') == 'success':
                    await update.message.reply_text(f"✅ 롱 포지션 오픈 성공: {result}")
                else:
                    await update.message.reply_text(f"❌ 롱 포지션 오픈 실패: {result}")
                    
            except Exception as e:
                await update.message.reply_text(f"❌ 오류: {str(e)}")
        
        async def short_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """숏 포지션 오픈"""
            try:
                parts = update.message.text.split()
                if len(parts) < 5:
                    await update.message.reply_text("❌ 사용법: /short [거래소] [심볼] [수량] [레버리지]")
                    return
                
                exchange = parts[1].lower()
                symbol = parts[2].upper()
                size = float(parts[3])
                leverage = int(parts[4])
                
                api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                
                if not api_key or not api_secret:
                    await update.message.reply_text(f"❌ {exchange} API 키가 설정되지 않음")
                    return
                
                trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                result = trader.open_short_position(symbol, size, leverage)
                
                if result.get('status') == 'success':
                    await update.message.reply_text(f"✅ 숏 포지션 오픈 성공: {result}")
                else:
                    await update.message.reply_text(f"❌ 숏 포지션 오픈 실패: {result}")
                    
            except Exception as e:
                await update.message.reply_text(f"❌ 오류: {str(e)}")
        
        async def close_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """포지션 종료"""
            try:
                parts = update.message.text.split()
                if len(parts) < 3:
                    await update.message.reply_text("❌ 사용법: /close [거래소] [심볼]")
                    return
                
                exchange = parts[1].lower()
                symbol = parts[2].upper()
                
                api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                
                if not api_key or not api_secret:
                    await update.message.reply_text(f"❌ {exchange} API 키가 설정되지 않음")
                    return
                
                trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                result = trader.close_position(symbol)
                
                if result.get('status') == 'success':
                    await update.message.reply_text(f"✅ 포지션 종료 성공: {result}")
                else:
                    await update.message.reply_text(f"❌ 포지션 종료 실패: {result}")
                    
            except Exception as e:
                await update.message.reply_text(f"❌ 오류: {str(e)}")
        
        async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """포지션 조회"""
            try:
                parts = update.message.text.split()
                if len(parts) < 2:
                    await update.message.reply_text("❌ 사용법: /positions [거래소]")
                    return
                
                exchange = parts[1].lower()
                
                api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                
                if not api_key or not api_secret:
                    await update.message.reply_text(f"❌ {exchange} API 키가 설정되지 않음")
                    return
                
                trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                result = trader.get_positions()
                
                if result.get('status') == 'success':
                    positions_data = result.get('positions', {})
                    await update.message.reply_text(f"📊 {exchange} 포지션: {positions_data}")
                else:
                    await update.message.reply_text(f"❌ 포지션 조회 실패: {result}")
                    
            except Exception as e:
                await update.message.reply_text(f"❌ 오류: {str(e)}")
        
        # 핸들러 등록
        telegram_app.add_handler(CommandHandler('start', start))
        telegram_app.add_handler(CommandHandler('balance', balance))
        telegram_app.add_handler(CommandHandler('long', long_position))
        telegram_app.add_handler(CommandHandler('short', short_position))
        telegram_app.add_handler(CommandHandler('close', close_position))
        telegram_app.add_handler(CommandHandler('positions', positions))
        
        print("✅ 텔레그램 봇 핸들러 등록 완료")
        print("🔄 폴링 시작...")
        
        telegram_app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ 텔레그램 봇 오류: {e}")
        import traceback
        print(f"❌ 스택 트레이스: {traceback.format_exc()}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 서버 시작: 포트 {port}")
    
    # 텔레그램 봇 스레드 시작
    telegram_thread = threading.Thread(target=run_telegram_bot)
    telegram_thread.daemon = True
    telegram_thread.start()
    print("✅ 텔레그램 봇 스레드 시작됨")
    
    # Flask 서버 시작
    app.run(host='0.0.0.0', port=port, debug=False) 