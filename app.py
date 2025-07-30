#!/usr/bin/env python3
"""
Railway 배포용 텔레그램 봇
완전히 새로운 구조로 asyncio 문제 해결
"""

import os
import logging
import threading
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from trading_bot_unified import UnifiedSpotTrader
from user_api_store import init_db

# Flask 앱 생성 (Railway 헬스체크용)
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy", "message": "Telegram Bot is running"})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "telegram-crypto-trading-bot"})

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 채널 ID
CHANNEL_ID = -1002751102244

# DB 초기화
init_db()
user_traders = {}

async def is_channel_member(bot, user_id, channel_id):
    """채널 멤버 확인"""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def get_main_menu_keyboard():
    """메인 메뉴 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("💰 잔고 조회", callback_data="balance"),
            InlineKeyboardButton("🔍 심볼 조회", callback_data="symbols")
        ],
        [
            InlineKeyboardButton("🔧 API 테스트", callback_data="test_api"),
            InlineKeyboardButton("❓ 도움말", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """봇 시작"""
    welcome_text = """
🤖 **암호화폐 트레이딩 봇**

원하는 기능을 선택하세요:
    """
    await update.message.reply_text(
        welcome_text, 
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """버튼 콜백 처리"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    bot = context.bot
    
    # 채널 멤버 체크
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await query.edit_message_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    
    if query.data == "balance":
        await query.edit_message_text(
            "💰 **잔고 조회**\n\n"
            "현재 Backpack 거래소만 지원됩니다.\n"
            "API 키를 설정하려면 관리자에게 문의하세요.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "symbols":
        try:
            # Backpack 심볼 조회 테스트
            trader = UnifiedSpotTrader(exchange='backpack', api_key='test', api_secret='test')
            symbols = trader.get_all_symbols()
            
            if isinstance(symbols, list) and len(symbols) > 0:
                symbols_text = "\n".join(symbols[:20])  # 최대 20개만 표시
                await query.edit_message_text(
                    f"🔍 **Backpack 거래쌍 목록**\n\n"
                    f"총 {len(symbols)}개 거래쌍\n\n"
                    f"```\n{symbols_text}\n```",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    f"❌ **심볼 조회 실패**\n\n"
                    f"오류: {str(symbols)}",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ **심볼 조회 오류**\n\n"
                f"오류: {str(e)}",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
    
    elif query.data == "test_api":
        await query.edit_message_text(
            "🔧 **API 테스트**\n\n"
            "현재 Backpack API 연결 테스트 중...",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
        
        try:
            trader = UnifiedSpotTrader(exchange='backpack', api_key='test', api_secret='test')
            result = trader.test_api_connection()
            
            if result.get('status') == 'success':
                await query.edit_message_text(
                    f"✅ **API 연결 성공!**\n\n"
                    f"{result.get('message')}",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    f"❌ **API 연결 실패**\n\n"
                    f"오류: {result.get('message')}",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )
        except Exception as e:
            await query.edit_message_text(
                f"❌ **API 테스트 오류**\n\n"
                f"오류: {str(e)}",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
    
    elif query.data == "help":
        help_text = """
❓ **도움말**

**지원 기능:**
- 💰 잔고 조회
- 🔍 심볼 조회  
- 🔧 API 테스트

**지원 거래소:**
- Backpack Exchange

**사용법:**
1. 메뉴에서 원하는 기능 선택
2. API 키 설정 (관리자 문의)
3. 거래소 선택 후 기능 사용

**주의사항:**
- 채널 멤버만 사용 가능
- API 키는 안전하게 암호화 저장
        """
        await query.edit_message_text(
            help_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    else:
        await query.edit_message_text(
            "🤖 **암호화폐 트레이딩 봇**\n\n원하는 기능을 선택하세요:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """잔고 조회 명령어"""
    await start(update, context)

async def symbols(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """심볼 조회 명령어"""
    await start(update, context)

async def test_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """API 테스트 명령어"""
    await start(update, context)

def run_telegram_bot():
    """텔레그램 봇 실행 함수"""
    # 환경 변수 확인
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN':
        print("❌ TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        print("Railway 대시보드에서 환경 변수를 설정하세요.")
        return
    
    print("🤖 텔레그램 봇 시작 중...")
    
    # 애플리케이션 빌드
    telegram_app = ApplicationBuilder().token(token).build()
    
    # 핸들러 등록
    telegram_app.add_handler(CommandHandler('start', start))
    telegram_app.add_handler(CommandHandler('balance', balance))
    telegram_app.add_handler(CommandHandler('symbols', symbols))
    telegram_app.add_handler(CommandHandler('testapi', test_api))
    telegram_app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ 텔레그램 봇이 성공적으로 시작되었습니다!")
    print("🔄 폴링 시작...")
    
    # 폴링 시작
    telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """메인 함수 - Flask와 텔레그램 봇을 함께 실행"""
    # 텔레그램 봇을 별도 스레드에서 실행
    bot_thread = threading.Thread(target=run_telegram_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Flask 서버 실행 (Railway 헬스체크용)
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Flask 서버 시작 중... 포트: {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    main() 