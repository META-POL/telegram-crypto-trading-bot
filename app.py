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
            InlineKeyboardButton("🔧 API 테스트", callback_data="test_api")
        ],
        [
            InlineKeyboardButton("🏪 거래소 선택", callback_data="select_exchange"),
            InlineKeyboardButton("❓ 도움말", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_exchange_selection_keyboard():
    """거래소 선택 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("XT Exchange", callback_data="exchange_xt"),
            InlineKeyboardButton("Backpack", callback_data="exchange_backpack")
        ],
        [
            InlineKeyboardButton("Hyperliquid", callback_data="exchange_hyperliquid")
        ],
        [
            InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")
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
            "지원 거래소: XT, Backpack, Hyperliquid\n"
            "API 키를 설정하려면 관리자에게 문의하세요.\n\n"
            "**사용법:**\n"
            "거래하고 싶은 토큰 심볼을 직접 입력하세요.\n"
            "예: BTC, ETH, SOL 등",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "select_exchange":
        await query.edit_message_text(
            "🏪 **거래소 선택**\n\n"
            "사용할 거래소를 선택하세요:",
            reply_markup=get_exchange_selection_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data.startswith("exchange_"):
        exchange = query.data.replace("exchange_", "")
        exchange_names = {
            "xt": "XT Exchange",
            "backpack": "Backpack",
            "hyperliquid": "Hyperliquid"
        }
        exchange_name = exchange_names.get(exchange, exchange.upper())
        
        await query.edit_message_text(
            f"🏪 **{exchange_name} 선택됨**\n\n"
            f"현재 선택된 거래소: **{exchange_name}**\n\n"
            f"**API 키 설정 필요:**\n"
            f"- API Key\n"
            f"- API Secret\n"
            f"- Private Key (Backpack의 경우)\n\n"
            f"관리자에게 문의하여 API 키를 설정하세요.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "main_menu":
        await query.edit_message_text(
            "🤖 **암호화폐 트레이딩 봇**\n\n원하는 기능을 선택하세요:",
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
- 🔧 API 테스트
- 🏪 거래소 선택

**지원 거래소:**
- XT Exchange
- Backpack Exchange
- Hyperliquid

**사용법:**
1. 거래소 선택
2. API 키 설정 (관리자 문의)
3. 거래하고 싶은 토큰 심볼을 직접 입력

**토큰 심볼 예시:**
- BTC (비트코인)
- ETH (이더리움)
- SOL (솔라나)
- USDC (USD 코인)

**API 키 필요사항:**
- XT: API Key, API Secret
- Backpack: API Key, Private Key
- Hyperliquid: API Key, API Secret

**주의사항:**
- 채널 멤버만 사용 가능
- API 키는 안전하게 암호화 저장
- 각 거래소에서 지원하는 토큰만 거래 가능
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
    telegram_app.add_handler(CommandHandler('testapi', test_api))
    telegram_app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ 텔레그램 봇이 성공적으로 시작되었습니다!")
    print("🔄 폴링 시작...")
    
    try:
        # 폴링 시작
        telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ 텔레그램 봇 오류: {e}")

def run_flask_server():
    """Flask 서버 실행 함수"""
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Flask 서버 시작 중... 포트: {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def main():
    """메인 함수 - 텔레그램 봇을 메인 스레드에서 실행"""
    # Flask 서버를 별도 스레드에서 실행
    flask_thread = threading.Thread(target=run_flask_server)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 텔레그램 봇을 메인 스레드에서 실행
    run_telegram_bot()

if __name__ == '__main__':
    main() 