#!/usr/bin/env python3
"""
텔레그램 봇 실행 파일
Railway 배포용
"""

import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from trading_bot_unified import UnifiedSpotTrader
from user_api_store import init_db, save_api, load_api

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 채널 ID
CHANNEL_ID = -1002751102244

# 대화 상태 정의
WAITING_API_KEY = 1
WAITING_API_SECRET = 2

init_db()  # DB 초기화
user_traders = {}
user_api_setup = {}  # 사용자별 API 설정 상태 저장

# 텔레그램 봇 함수들 (telegram_bot.py에서 복사)
async def is_channel_member(bot, user_id, channel_id):
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def get_main_menu_keyboard():
    """메인 메뉴 키보드 생성"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [
            InlineKeyboardButton("🏦 거래소 선택", callback_data="select_exchange"),
            InlineKeyboardButton("❓ 도움말", callback_data="help")
        ],
        [
            InlineKeyboardButton("🔑 API 등록", callback_data="set_api"),
            InlineKeyboardButton("💰 잔고 조회", callback_data="balance")
        ],
        [
            InlineKeyboardButton("📊 매매 신호", callback_data="signals"),
            InlineKeyboardButton("💵 수익 확인", callback_data="profit")
        ],
        [
            InlineKeyboardButton("📈 거래량 생성", callback_data="volume_trading"),
            InlineKeyboardButton("⚙️ 리스크 설정", callback_data="risk_settings")
        ],
        [
            InlineKeyboardButton("🔍 심볼 조회", callback_data="symbols"),
            InlineKeyboardButton("📊 시장 정보", callback_data="market_info")
        ],
        [
            InlineKeyboardButton("🔧 API 테스트", callback_data="test_api")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """봇 시작"""
    welcome_text = """
🤖 **통합 트레이딩 봇 (개선된 버전)**

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
    
    if query.data == "main_menu":
        await query.edit_message_text(
            "🤖 **통합 트레이딩 봇 (개선된 버전)**\n\n원하는 기능을 선택하세요:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "balance":
        trader = user_traders.get(user_id)
        if not trader:
            await query.edit_message_text(
                "❌ **거래소가 선택되지 않았습니다.**\n\n"
                "먼저 거래소를 선택하세요.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
            return
        
        await query.edit_message_text(
            "💰 **잔고 조회 중...**\n\n잠시만 기다려주세요.",
            parse_mode='Markdown'
        )
        
        result = trader.get_balance()
        
        if isinstance(result, dict) and 'error' in result:
            await query.edit_message_text(
                f"❌ **잔고 조회 실패**\n\n"
                f"오류: {result['error']}\n\n"
                f"**확인사항:**\n"
                f"1. API 키가 올바르게 등록되었는지 확인\n"
                f"2. API 권한이 잔고 조회를 허용하는지 확인\n"
                f"3. 네트워크 연결 상태 확인",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
        elif isinstance(result, dict) and len(result) > 0:
            balance_text = f"💰 **{trader.exchange.upper()} 잔고 정보**\n\n"
            for currency, balance in result.items():
                if isinstance(balance, dict) and 'available' in balance:
                    available = balance['available']
                    if available > 0:
                        balance_text += f"**{currency}**: `{available:.8f}`\n"
                elif isinstance(balance, (int, float)) and balance > 0:
                    balance_text += f"**{currency}**: `{balance:.8f}`\n"
            
            if balance_text == f"💰 **{trader.exchange.upper()} 잔고 정보**\n\n":
                balance_text += "보유 자산이 없습니다."
            
            await query.edit_message_text(
                balance_text,
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ **잔고 조회 실패**\n\n"
                f"예상치 못한 응답: {str(result)}",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )

    elif query.data == "symbols":
        trader = user_traders.get(user_id)
        if not trader:
            await query.edit_message_text(
                "❌ **거래소가 선택되지 않았습니다.**\n\n"
                "먼저 거래소를 선택하세요.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
            return
        
        await query.edit_message_text(
            "🔍 **심볼 조회 중...**\n\n"
            "거래쌍 목록을 가져오는 중입니다.",
            parse_mode='Markdown'
        )
        
        symbols = trader.get_all_symbols()
        
        if isinstance(symbols, dict) and 'error' in symbols:
            await query.edit_message_text(
                f"❌ **심볼 조회 실패**\n\n"
                f"오류: {symbols['error']}\n\n"
                f"**확인사항:**\n"
                f"1. API 키가 올바르게 등록되었는지 확인\n"
                f"2. 네트워크 연결 상태 확인\n"
                f"3. 거래소 서버 상태 확인",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
        elif isinstance(symbols, list) and len(symbols) > 0:
            # 심볼을 10개씩 그룹화
            symbol_groups = [symbols[i:i+10] for i in range(0, len(symbols), 10)]
            
            if len(symbol_groups) == 1:
                symbols_text = "\n".join(symbols[:20])  # 최대 20개만 표시
                await query.edit_message_text(
                    f"🔍 **{trader.exchange.upper()} 거래쌍 목록**\n\n"
                    f"총 {len(symbols)}개 거래쌍\n\n"
                    f"```\n{symbols_text}\n```\n\n"
                    f"전체 목록: `/symbols` 명령어 사용",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    f"🔍 **{trader.exchange.upper()} 거래쌍 목록**\n\n"
                    f"총 {len(symbols)}개 거래쌍\n\n"
                    f"페이지가 많아 `/symbols` 명령어로 전체 목록을 확인하세요.",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )
        else:
            await query.edit_message_text(
                f"❌ **심볼 조회 실패**\n\n"
                f"예상치 못한 응답: {str(symbols)}",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )

    elif query.data == "test_api":
        trader = user_traders.get(user_id)
        if not trader:
            await query.edit_message_text(
                "❌ **거래소가 선택되지 않았습니다.**\n\n"
                "먼저 거래소를 선택하세요.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
            return
        
        await query.edit_message_text(
            "🔧 **API 연결 테스트 중...**\n\n"
            "API 키와 연결 상태를 확인하고 있습니다.",
            parse_mode='Markdown'
        )
        
        result = trader.test_api_connection()
        
        if result.get('status') == 'success':
            await query.edit_message_text(
                f"✅ **API 연결 성공!**\n\n"
                f"{result.get('message')}\n\n"
                f"이제 잔고 조회와 심볼 조회가 정상적으로 작동할 것입니다.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                f"❌ **API 연결 실패**\n\n"
                f"오류: {result.get('message')}\n\n"
                f"**해결 방법:**\n"
                f"1. API 키를 다시 등록해보세요\n"
                f"2. API 권한 설정을 확인하세요\n"
                f"3. 네트워크 연결을 확인하세요",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )

    else:
        await query.edit_message_text(
            "🤖 **통합 트레이딩 봇 (개선된 버전)**\n\n원하는 기능을 선택하세요:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )

def main():
    # 환경 변수 확인
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN':
        print("❌ TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        print("Railway 대시보드에서 환경 변수를 설정하세요.")
        return
    
    print("🤖 텔레그램 봇 시작 중...")
    app = ApplicationBuilder().token(token).build()
    
    # 핸들러 등록
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ 텔레그램 봇이 성공적으로 시작되었습니다!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 