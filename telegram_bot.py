import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("안녕하세요! 통합 트레이딩 봇입니다.\n/exchange [xt|backpack|hyperliquid]로 거래소를 선택하세요.\n먼저 /setapi로 본인 API를 등록하세요.")

async def setapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 3:
        await update.message.reply_text("사용법: /setapi [xt|backpack|hyperliquid] [API_KEY] [API_SECRET or PRIVATE_KEY]")
        return
    ex, key, secret = context.args[0].lower(), context.args[1], context.args[2]
    save_api(user_id, ex, key, secret)
    await update.message.reply_text(f"{ex.upper()} API 정보가 저장되었습니다!")

async def exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    if not context.args:
        await update.message.reply_text("사용법: /exchange [xt|backpack|hyperliquid]")
        return
    ex = context.args[0].lower()
    api_info = load_api(user_id, ex)
    if not api_info:
        await update.message.reply_text(f"먼저 /setapi {ex} [API_KEY] [API_SECRET] 으로 API를 등록하세요.")
        return
    if ex == 'xt':
        trader = UnifiedSpotTrader(exchange='xt', api_key=api_info[0], api_secret=api_info[1])
    elif ex == 'backpack':
        trader = UnifiedSpotTrader(exchange='backpack', api_key=api_info[0], private_key=api_info[1])
    elif ex == 'hyperliquid':
        trader = UnifiedSpotTrader(exchange='hyperliquid', api_key=api_info[0], api_secret=api_info[1])
    else:
        await update.message.reply_text("지원하지 않는 거래소입니다.")
        return
    user_traders[user_id] = trader
    await update.message.reply_text(f"{ex.upper()} 거래소로 설정되었습니다.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 /exchange 명령어로 거래소를 선택하세요.")
        return
    result = trader.get_balance()
    await update.message.reply_text(str(result))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 /exchange 명령어로 거래소를 선택하세요.")
        return
    if len(context.args) < 4:
        await update.message.reply_text("사용법: /buy [심볼] [가격] [수량] [횟수]")
        return
    symbol, price, qty, repeat = context.args[0], float(context.args[1]), float(context.args[2]), int(context.args[3])
    result = trader.buy(symbol, price, qty, repeat)
    await update.message.reply_text(str(result))

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if not trader:
        await update.message.reply_text("먼저 /exchange 명령어로 거래소를 선택하세요.")
        return
    if len(context.args) < 4:
        await update.message.reply_text("사용법: /sell [심볼] [가격] [수량] [횟수]")
        return
    symbol, price, qty, repeat = context.args[0], float(context.args[1]), float(context.args[2]), int(context.args[3])
    result = trader.sell(symbol, price, qty, repeat)
    await update.message.reply_text(str(result))

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if trader:
        trader.stop_trading()
        await update.message.reply_text("매매가 정지되었습니다.")
    else:
        await update.message.reply_text("먼저 /exchange 명령어로 거래소를 선택하세요.")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = context.bot
    if not await is_channel_member(bot, user_id, CHANNEL_ID):
        await update.message.reply_text("이 봇은 채널 멤버만 사용할 수 있습니다. 채널에 가입 후 다시 시도하세요.")
        return
    trader = user_traders.get(user_id)
    if trader:
        await update.message.reply_text(f"누적 수익: {trader.get_profit()} USDT")
    else:
        await update.message.reply_text("먼저 /exchange 명령어로 거래소를 선택하세요.")

def main():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('setapi', setapi))
    app.add_handler(CommandHandler('exchange', exchange))
    app.add_handler(CommandHandler('balance', balance))
    app.add_handler(CommandHandler('buy', buy))
    app.add_handler(CommandHandler('sell', sell))
    app.add_handler(CommandHandler('stop', stop))
    app.add_handler(CommandHandler('profit', profit))
    app.run_polling()

if __name__ == '__main__':
    main() 