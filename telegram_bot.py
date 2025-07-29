import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from trading_bot_unified import UnifiedSpotTrader
from user_api_store import init_db, save_api, load_api
import logging
import os

# 채널 ID (실제 운영 채널 ID로 교체)
CHANNEL_ID = -1002751102244

init_db()  # DB 초기화
user_traders = {}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def is_channel_member(bot, user_id, channel_id):
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def get_main_menu_keyboard():
    """메인 메뉴 키보드 생성"""
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
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_exchange_keyboard():
    """거래소 선택 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("XT.com", callback_data="exchange_xt"),
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
🤖 **통합 트레이딩 봇**

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
            "🤖 **통합 트레이딩 봇**\n\n원하는 기능을 선택하세요:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "select_exchange":
        await query.edit_message_text(
            "🏦 **거래소 선택**\n\n사용할 거래소를 선택하세요:",
            reply_markup=get_exchange_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data.startswith("exchange_"):
        exchange = query.data.split("_")[1]
        api_info = load_api(user_id, exchange)
        if not api_info:
            await query.edit_message_text(
                f"❌ **{exchange.upper()} API가 등록되지 않았습니다.**\n\n"
                f"먼저 `/setapi {exchange} [API_KEY] [API_SECRET]` 명령어로 API를 등록하세요.",
                parse_mode='Markdown'
            )
            return
        
        if exchange == 'xt':
            trader = UnifiedSpotTrader(exchange='xt', api_key=api_info[0], api_secret=api_info[1])
        elif exchange == 'backpack':
            trader = UnifiedSpotTrader(exchange='backpack', api_key=api_info[0], private_key=api_info[1])
        elif exchange == 'hyperliquid':
            trader = UnifiedSpotTrader(exchange='hyperliquid', api_key=api_info[0], api_secret=api_info[1])
        
        user_traders[user_id] = trader
        await query.edit_message_text(
            f"✅ **{exchange.upper()} 거래소로 설정되었습니다!**\n\n"
            f"이제 매매 기능을 사용할 수 있습니다.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "set_api":
        help_text = """
🔑 **API 등록 방법**

다음 명령어로 API를 등록하세요:

**XT.com:**
`/setapi xt [API_KEY] [API_SECRET]`

**Backpack:**
`/setapi backpack [API_KEY] [PRIVATE_KEY]`

**Hyperliquid:**
`/setapi hyperliquid [API_KEY] [API_SECRET]`

예시: `/setapi xt 5e917667-4856-4789-9d7b-1f55d2fa5f07 d48f7352c4a2e40a7f1a286f8319cba4ea33af4c`
        """
        await query.edit_message_text(
            help_text,
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
        
        result = trader.get_balance()
        await query.edit_message_text(
            f"💰 **잔고 정보**\n\n```\n{str(result)}\n```",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "profit":
        trader = user_traders.get(user_id)
        if not trader:
            await query.edit_message_text(
                "❌ **거래소가 선택되지 않았습니다.**\n\n"
                "먼저 거래소를 선택하세요.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
            return
        
        profit = trader.get_profit()
        await query.edit_message_text(
            f"💵 **누적 수익**\n\n`{profit} USDT`",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "signals":
        help_text = """
📊 **매매 신호 사용법**

다음 명령어로 매매를 실행하세요:

**매수:**
`/buy [심볼] [가격] [수량] [횟수]`

**매도:**
`/sell [심볼] [가격] [수량] [횟수]`

**매매 정지:**
`/stop`

예시: `/buy btc_usdt 30000 0.001 5`
        """
        await query.edit_message_text(
            help_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "help":
        help_text = """
❓ **도움말**

**1. API 등록**
먼저 `/setapi` 명령어로 본인 API를 등록하세요.

**2. 거래소 선택**
"거래소 선택" 버튼을 눌러 사용할 거래소를 선택하세요.

**3. 매매 실행**
- 잔고 조회: "잔고 조회" 버튼
- 매수: `/buy [심볼] [가격] [수량] [횟수]`
- 매도: `/sell [심볼] [가격] [수량] [횟수]`
- 매매 정지: `/stop`
- 수익 확인: "수익 확인" 버튼

**지원 거래소:** XT.com, Backpack, Hyperliquid
        """
        await query.edit_message_text(
            help_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )

async def setapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 3:
        await update.message.reply_text("사용법: /setapi [xt|backpack|hyperliquid] [API_KEY] [API_SECRET or PRIVATE_KEY]")
        return
    ex, key, secret = context.args[0].lower(), context.args[1], context.args[2]
    save_api(user_id, ex, key, secret)
    await update.message.reply_text(f"✅ {ex.upper()} API 정보가 저장되었습니다!")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 4:
        await update.message.reply_text("사용법: /buy [심볼] [가격] [수량] [횟수]")
        return
    symbol, price, qty, repeat = context.args[0], float(context.args[1]), float(context.args[2]), int(context.args[3])
    result = trader.buy(symbol, price, qty, repeat)
    await update.message.reply_text(f"✅ 매수 주문 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 4:
        await update.message.reply_text("사용법: /sell [심볼] [가격] [수량] [횟수]")
        return
    symbol, price, qty, repeat = context.args[0], float(context.args[1]), float(context.args[2]), int(context.args[3])
    result = trader.sell(symbol, price, qty, repeat)
    await update.message.reply_text(f"✅ 매도 주문 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if trader:
        trader.stop_trading()
        await update.message.reply_text("🛑 매매가 정지되었습니다.")
    else:
        await update.message.reply_text("먼저 거래소를 선택하세요.")

def main():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('setapi', setapi))
    app.add_handler(CommandHandler('buy', buy))
    app.add_handler(CommandHandler('sell', sell))
    app.add_handler(CommandHandler('stop', stop))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()

if __name__ == '__main__':
    main() 