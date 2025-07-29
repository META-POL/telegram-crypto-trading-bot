import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from trading_bot_unified import UnifiedSpotTrader
from user_api_store import init_db, save_api, load_api
import os

# 채널 ID (실제 운영 채널 ID로 교체)
CHANNEL_ID = -1002751102244

# 대화 상태 정의
WAITING_API_KEY = 1
WAITING_API_SECRET = 2

init_db()  # DB 초기화
user_traders = {}
user_api_setup = {}  # 사용자별 API 설정 상태 저장

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
        ],
        [
            InlineKeyboardButton("📈 거래량 생성", callback_data="volume_trading"),
            InlineKeyboardButton("⚙️ 리스크 설정", callback_data="risk_settings")
        ],
        [
            InlineKeyboardButton("🔍 심볼 조회", callback_data="symbols"),
            InlineKeyboardButton("📊 시장 정보", callback_data="market_info")
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

def get_api_setup_keyboard():
    """API 등록 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("XT.com API 등록", callback_data="setup_api_xt"),
            InlineKeyboardButton("Backpack API 등록", callback_data="setup_api_backpack")
        ],
        [
            InlineKeyboardButton("Hyperliquid API 등록", callback_data="setup_api_hyperliquid")
        ],
        [
            InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_trading_keyboard():
    """매매 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("📈 지정가 매수", callback_data="limit_buy"),
            InlineKeyboardButton("📉 지정가 매도", callback_data="limit_sell")
        ],
        [
            InlineKeyboardButton("⚡ 시장가 매수", callback_data="market_buy"),
            InlineKeyboardButton("⚡ 시장가 매도", callback_data="market_sell")
        ],
        [
            InlineKeyboardButton("🛑 스탑로스", callback_data="stop_loss"),
            InlineKeyboardButton("🎯 익절매", callback_data="take_profit")
        ],
        [
            InlineKeyboardButton("📊 거래량 생성", callback_data="volume_trading"),
            InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")
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
                f"먼저 API 등록 버튼에서 API를 등록하세요.",
                reply_markup=get_main_menu_keyboard(),
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
        await query.edit_message_text(
            "🔑 **API 등록**\n\n등록할 거래소를 선택하세요:",
            reply_markup=get_api_setup_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data.startswith("setup_api_"):
        exchange = query.data.split("_")[2]
        user_api_setup[user_id] = {"exchange": exchange, "step": "api_key"}
        
        if exchange == 'backpack':
            await query.edit_message_text(
                f"🔑 **{exchange.upper()} API 등록**\n\n"
                f"Backpack 공개키(API Key)를 입력하세요:",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                f"🔑 **{exchange.upper()} API 등록**\n\n"
                f"{exchange.upper()} API Key를 입력하세요:",
                parse_mode='Markdown'
            )
        return WAITING_API_KEY
    
    elif query.data == "signals":
        await query.edit_message_text(
            "📊 **매매 신호**\n\n매매 방식을 선택하세요:",
            reply_markup=get_trading_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "volume_trading":
        help_text = """
📈 **거래량 생성 사용법**

거래량 생성을 위한 자동 매수-매도 기능입니다.

**명령어:**
`/volume [심볼] [가격] [수량] [횟수]`

**예시:**
`/volume btc_usdt 30000 0.001 6`

**동작 방식:**
1. 지정가로 매수 주문
2. 2초 대기
3. 0.1% 낮은 가격으로 매도
4. 3초 대기 후 다음 라운드
5. 총 6회 반복

**주의:** 거래량 생성용이므로 수익을 목적으로 하지 않습니다.
        """
        await query.edit_message_text(
            help_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "risk_settings":
        help_text = """
⚙️ **리스크 설정 사용법**

**현재 리스크 설정 조회:**
`/risk`

**리스크 설정 변경:**
`/setrisk [최대손실] [손절비율] [익절비율] [최대포지션]`

**예시:**
`/setrisk 100 5 10 1000`

**설정 항목:**
- 최대손실: 최대 허용 손실 (USDT)
- 손절비율: 손절매 비율 (%)
- 익절비율: 익절매 비율 (%)
- 최대포지션: 최대 포지션 크기 (USDT)
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
        risk_info = trader.get_risk_info()
        await query.edit_message_text(
            f"💵 **수익 및 리스크 정보**\n\n"
            f"**누적 수익:** `{profit} USDT`\n"
            f"**리스크 레벨:** `{risk_info['risk_level']}`\n"
            f"**최대 손실 한도:** `{risk_info['max_loss_limit']} USDT`\n"
            f"**손절매 비율:** `{risk_info['stop_loss_percent']}%`\n"
            f"**익절매 비율:** `{risk_info['take_profit_percent']}%`",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "help":
        help_text = """
❓ **도움말 (개선된 버전)**

**1. API 등록**
"API 등록" 버튼을 눌러 거래소별로 API를 등록하세요.

**2. 거래소 선택**
"거래소 선택" 버튼을 눌러 사용할 거래소를 선택하세요.

**3. 매매 실행**
- **지정가 매수:** `/buy [심볼] [가격] [수량] [횟수]`
- **지정가 매도:** `/sell [심볼] [가격] [수량] [횟수]`
- **시장가 매수:** `/mbuy [심볼] [수량] [횟수]`
- **시장가 매도:** `/msell [심볼] [수량] [횟수]`
- **거래량 생성:** `/volume [심볼] [가격] [수량] [횟수]`
- **스탑로스:** `/sl [심볼] [매수가격] [수량] [손절비율]`
- **익절매:** `/tp [심볼] [매수가격] [수량] [익절비율]`
- **매매 정지:** `/stop`
- **주문 취소:** `/cancel [주문ID] [심볼]`
- **주문 상태:** `/status [주문ID] [심볼]`

**4. 리스크 관리**
- **리스크 설정 조회:** `/risk`
- **리스크 설정 변경:** `/setrisk [최대손실] [손절비율] [익절비율] [최대포지션]`

**5. 심볼 조회**
- **전체 심볼 조회:** `/symbols`
- **심볼 검색:** `/search [검색어]`
- **심볼 정보:** `/info [심볼]`

**지원 거래소:** XT.com, Backpack, Hyperliquid
        """
        await query.edit_message_text(
            help_text,
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
                "🔍 **심볼 조회**\n\n"
                "전체 심볼 목록을 가져오는 중...",
                parse_mode='Markdown'
            )
            
            symbols = trader.get_all_symbols()
            if isinstance(symbols, list) and len(symbols) > 0:
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
                    f"오류: {str(symbols)}",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='Markdown'
                )

        elif query.data == "market_info":
            help_text = """
📊 **시장 정보 사용법**

**현재 가격 조회:**
`/price [심볼]`

**심볼 검색:**
`/search [검색어]`

**예시:**
`/price ETH_USD`
`/search BTC`
`/search ETH`
            """
            await query.edit_message_text(
                help_text,
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )

async def handle_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """API Key 입력 처리"""
    user_id = update.effective_user.id
    api_key = update.message.text.strip()
    
    if user_id not in user_api_setup:
        await update.message.reply_text("❌ API 등록이 시작되지 않았습니다. 메인 메뉴에서 다시 시작하세요.")
        return ConversationHandler.END
    
    setup_info = user_api_setup[user_id]
    exchange = setup_info["exchange"]
    
    # API Key 저장
    user_api_setup[user_id]["api_key"] = api_key
    user_api_setup[user_id]["step"] = "api_secret"
    
    if exchange == 'backpack':
        await update.message.reply_text(
            f"✅ Backpack 공개키가 저장되었습니다.\n\n"
            f"이제 Backpack 비밀키(Private Key)를 입력하세요:"
        )
    else:
        await update.message.reply_text(
            f"✅ {exchange.upper()} API Key가 저장되었습니다.\n\n"
            f"이제 {exchange.upper()} API Secret을 입력하세요:"
        )
    
    return WAITING_API_SECRET

async def handle_api_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """API Secret 입력 처리"""
    user_id = update.effective_user.id
    api_secret = update.message.text.strip()
    
    if user_id not in user_api_setup:
        await update.message.reply_text("❌ API 등록이 시작되지 않았습니다. 메인 메뉴에서 다시 시작하세요.")
        return ConversationHandler.END
    
    setup_info = user_api_setup[user_id]
    exchange = setup_info["exchange"]
    api_key = setup_info["api_key"]
    
    # API 정보 저장
    save_api(user_id, exchange, api_key, api_secret)
    
    # 설정 정보 삭제
    del user_api_setup[user_id]
    
    await update.message.reply_text(
        f"✅ **{exchange.upper()} API 등록이 완료되었습니다!**\n\n"
        f"이제 거래소 선택에서 {exchange.upper()}를 사용할 수 있습니다.",
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """대화 취소"""
    user_id = update.effective_user.id
    if user_id in user_api_setup:
        del user_api_setup[user_id]
    
    await update.message.reply_text(
        "❌ API 등록이 취소되었습니다.",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

async def setapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 3:
        await update.message.reply_text("사용법: /setapi [xt|backpack|hyperliquid] [API_KEY] [API_SECRET]")
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
    result = trader.buy(symbol, price, qty, repeat, 'limit')
    await update.message.reply_text(f"✅ 지정가 매수 주문 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

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
    result = trader.sell(symbol, price, qty, repeat, 'limit')
    await update.message.reply_text(f"✅ 지정가 매도 주문 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def mbuy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """시장가 매수"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 3:
        await update.message.reply_text("사용법: /mbuy [심볼] [수량] [횟수]")
        return
    symbol, qty, repeat = context.args[0], float(context.args[1]), int(context.args[2])
    result = trader.buy(symbol, 0, qty, repeat, 'market')
    await update.message.reply_text(f"✅ 시장가 매수 주문 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def msell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """시장가 매도"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 3:
        await update.message.reply_text("사용법: /msell [심볼] [수량] [횟수]")
        return
    symbol, qty, repeat = context.args[0], float(context.args[1]), int(context.args[2])
    result = trader.sell(symbol, 0, qty, repeat, 'market')
    await update.message.reply_text(f"✅ 시장가 매도 주문 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """거래량 생성"""
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
        await update.message.reply_text("사용법: /volume [심볼] [가격] [수량] [횟수]")
        return
    symbol, price, qty, repeat = context.args[0], float(context.args[1]), float(context.args[2]), int(context.args[3])
    result = trader.volume_trading(symbol, price, qty, repeat)
    await update.message.reply_text(f"✅ 거래량 생성 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def stop_loss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """스탑로스 주문"""
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
        await update.message.reply_text("사용법: /sl [심볼] [매수가격] [수량] [손절비율]")
        return
    symbol, buy_price, qty, sl_percent = context.args[0], float(context.args[1]), float(context.args[2]), float(context.args[3])
    result = trader.stop_loss_order(symbol, buy_price, qty, sl_percent)
    await update.message.reply_text(f"✅ 스탑로스 주문 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def take_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """익절매 주문"""
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
        await update.message.reply_text("사용법: /tp [심볼] [매수가격] [수량] [익절비율]")
        return
    symbol, buy_price, qty, tp_percent = context.args[0], float(context.args[1]), float(context.args[2]), float(context.args[3])
    result = trader.take_profit_order(symbol, buy_price, qty, tp_percent)
    await update.message.reply_text(f"✅ 익절매 주문 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """리스크 설정 조회"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    risk_info = trader.get_risk_info()
    await update.message.reply_text(
        f"⚙️ **리스크 설정 정보**\n\n"
        f"**현재 수익:** `{risk_info['current_profit']} USDT`\n"
        f"**리스크 레벨:** `{risk_info['risk_level']}`\n"
        f"**최대 손실 한도:** `{risk_info['max_loss_limit']} USDT`\n"
        f"**손절매 비율:** `{risk_info['stop_loss_percent']}%`\n"
        f"**익절매 비율:** `{risk_info['take_profit_percent']}%`\n"
        f"**최대 포지션 크기:** `{risk_info['max_position_size']} USDT`",
        parse_mode='Markdown'
    )

async def setrisk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """리스크 설정 변경"""
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
        await update.message.reply_text("사용법: /setrisk [최대손실] [손절비율] [익절비율] [최대포지션]")
        return
    max_loss, sl_percent, tp_percent, max_position = float(context.args[0]), float(context.args[1]), float(context.args[2]), float(context.args[3])
    trader.set_risk_settings(max_loss, sl_percent, tp_percent, max_position)
    await update.message.reply_text(f"✅ 리스크 설정이 업데이트되었습니다!")

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """주문 취소"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("사용법: /cancel [주문ID] [심볼]")
        return
    order_id, symbol = context.args[0], context.args[1]
    result = trader.cancel_order(order_id, symbol)
    await update.message.reply_text(f"✅ 주문 취소 완료:\n```\n{str(result)}\n```", parse_mode='Markdown')

async def order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """주문 상태 조회"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("사용법: /status [주문ID] [심볼]")
        return
    order_id, symbol = context.args[0], context.args[1]
    result = trader.get_order_status(order_id, symbol)
    await update.message.reply_text(f"📊 주문 상태:\n```\n{str(result)}\n```", parse_mode='Markdown')

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

async def symbols(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """전체 심볼 목록 조회"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    
    symbols = trader.get_all_symbols()
    if isinstance(symbols, list) and len(symbols) > 0:
        # 심볼을 50개씩 그룹화하여 메시지 분할
        symbol_groups = [symbols[i:i+50] for i in range(0, len(symbols), 50)]
        
        for i, group in enumerate(symbol_groups):
            symbols_text = "\n".join(group)
            await update.message.reply_text(
                f"🔍 **{trader.exchange.upper()} 거래쌍 목록 ({i+1}/{len(symbol_groups)})**\n\n"
                f"```\n{symbols_text}\n```",
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(f"❌ 심볼 조회 실패: {str(symbols)}")

async def search_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """심볼 검색"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("사용법: /search [검색어]")
        return
    
    search_term = context.args[0].upper()
    symbols = trader.get_all_symbols()
    
    if isinstance(symbols, list):
        matched_symbols = [s for s in symbols if search_term in s.upper()]
        if matched_symbols:
            symbols_text = "\n".join(matched_symbols[:20])  # 최대 20개만 표시
            await update.message.reply_text(
                f"🔍 **'{search_term}' 검색 결과**\n\n"
                f"총 {len(matched_symbols)}개 발견\n\n"
                f"```\n{symbols_text}\n```",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ '{search_term}'에 해당하는 심볼을 찾을 수 없습니다.")
    else:
        await update.message.reply_text(f"❌ 심볼 조회 실패: {str(symbols)}")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 가격 조회"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("사용법: /price [심볼]")
        return
    
    symbol = context.args[0]
    current_price = trader.get_current_price(symbol)
    
    if current_price:
        await update.message.reply_text(
            f"💰 **{symbol} 현재 가격**\n\n"
            f"**가격:** `{current_price} USD`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"❌ {symbol} 가격 조회 실패")

async def symbol_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """심볼 상세 정보 조회"""
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 거래소를 선택하세요.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("사용법: /info [심볼]")
        return
    
    symbol = context.args[0]
    info = trader.get_symbol_info(symbol)
    
    if 'error' not in str(info):
        await update.message.reply_text(
            f"📊 **{symbol} 상세 정보**\n\n"
            f"```\n{str(info)}\n```",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"❌ {symbol} 정보 조회 실패: {str(info)}")

def main():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
    app = ApplicationBuilder().token(token).build()
    
    # 대화 핸들러 (API 등록용)
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^setup_api_")],
        states={
            WAITING_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_key)],
            WAITING_API_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_secret)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=True,  # 경고 메시지 해결
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('setapi', setapi))
    app.add_handler(CommandHandler('buy', buy))
    app.add_handler(CommandHandler('sell', sell))
    app.add_handler(CommandHandler('mbuy', mbuy))
    app.add_handler(CommandHandler('msell', msell))
    app.add_handler(CommandHandler('volume', volume))
    app.add_handler(CommandHandler('sl', stop_loss))
    app.add_handler(CommandHandler('tp', take_profit))
    app.add_handler(CommandHandler('risk', risk))
    app.add_handler(CommandHandler('setrisk', setrisk))
    app.add_handler(CommandHandler('cancel', cancel_order))
    app.add_handler(CommandHandler('status', order_status))
    app.add_handler(CommandHandler('stop', stop))
    app.add_handler(CommandHandler('symbols', symbols))
    app.add_handler(CommandHandler('search', search_symbol))
    app.add_handler(CommandHandler('price', price))
    app.add_handler(CommandHandler('info', symbol_info))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()

if __name__ == '__main__':
    main() 