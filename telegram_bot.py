import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from auth_manager import AuthManager
from trading_bot import TradingBot
from config import Config
import asyncio

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramTradingBot:
    def __init__(self):
        self.auth_manager = AuthManager()
        self.trading_bot = TradingBot()
        self.application = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """봇 시작 명령어"""
        user_info = self.auth_manager.get_user_info(update)
        
        welcome_message = f"""
🤖 **암호화폐 트레이딩 봇**에 오신 것을 환영합니다!

👤 **사용자 정보:**
- ID: `{user_info['id']}`
- 이름: {user_info['first_name']} {user_info.get('last_name', '')}
- 사용자명: @{user_info.get('username', 'N/A')}

📊 **사용 가능한 명령어:**
/start - 봇 시작
/help - 도움말
/price [심볼] - 현재가 조회
/analysis [심볼] - 시장 분석
/balance - 잔고 조회
/signals [심볼] - 매매 신호
/menu - 메인 메뉴

💡 **예시:**
- `/price BTC/USDT`
- `/analysis ETH/USDT`
- `/signals ADA/USDT`
        """
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    @AuthManager.require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """도움말 명령어"""
        help_text = """
📚 **트레이딩 봇 사용법**

🔍 **기본 명령어:**
• `/price [심볼]` - 현재가 및 24시간 변동률 조회
• `/analysis [심볼]` - 기술적 분석 결과 조회
• `/balance` - 계좌 잔고 조회
• `/signals [심볼]` - 매매 신호 분석

📈 **분석 지표:**
• RSI (상대강도지수)
• MACD (이동평균수렴확산)
• 이동평균선 (20일, 50일)
• 볼린저 밴드
• 스토캐스틱

⚠️ **주의사항:**
• 이 봇은 투자 조언이 아닌 정보 제공 목적입니다
• 실제 거래 전 충분한 검토가 필요합니다
• 손실에 대한 책임은 사용자에게 있습니다

🔧 **지원 거래소:** Binance, Upbit
        """
        
        await update.message.reply_text(help_text)
    
    @AuthManager.require_auth
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """현재가 조회 명령어"""
        try:
            # 명령어에서 심볼 추출
            args = context.args
            symbol = args[0] if args else Config.DEFAULT_SYMBOL
            
            # 현재가 조회
            ticker = self.trading_bot.get_ticker(symbol)
            if not ticker:
                await update.message.reply_text(f"❌ {symbol} 현재가 조회에 실패했습니다.")
                return
            
            # 메시지 포맷팅
            price_message = f"""
💰 **{symbol} 현재가 정보**

📊 **가격 정보:**
• 현재가: ${ticker['last']:,.2f}
• 24시간 변동: {ticker['percentage']:+.2f}%
• 24시간 변동금액: ${ticker['change']:+,.2f}

📈 **거래량 정보:**
• 24시간 거래량: {ticker['baseVolume']:,.2f} {symbol.split('/')[0]}
• 24시간 거래대금: ${ticker['quoteVolume']:,.2f}

📊 **가격 범위:**
• 최고가: ${ticker['high']:,.2f}
• 최저가: ${ticker['low']:,.2f}
• 시가: ${ticker['open']:,.2f}

🕐 **업데이트 시간:** {ticker['datetime']}
            """
            
            await update.message.reply_text(price_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in price command: {e}")
            await update.message.reply_text("❌ 현재가 조회 중 오류가 발생했습니다.")
    
    @AuthManager.require_auth
    async def analysis_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시장 분석 명령어"""
        try:
            # 명령어에서 심볼 추출
            args = context.args
            symbol = args[0] if args else Config.DEFAULT_SYMBOL
            
            # 분석 시작 메시지
            await update.message.reply_text(f"🔍 {symbol} 시장 분석 중...")
            
            # 시장 분석 수행
            analysis = self.trading_bot.analyze_market(symbol)
            if not analysis:
                await update.message.reply_text(f"❌ {symbol} 분석에 실패했습니다.")
                return
            
            # 분석 결과 포맷팅
            analysis_message = f"""
📊 **{symbol} 기술적 분석 결과**

💰 **가격 정보:**
• 현재가: ${analysis['current_price']:,.2f}
• 변동률: {analysis['price_change_percent']:+.2f}%
• 거래량: {analysis['volume']:,.2f}

📈 **기술적 지표:**

**RSI (14):** {analysis['indicators']['rsi']:.2f}
• {'🔴 과매수' if analysis['indicators']['rsi'] > 70 else '🟢 과매도' if analysis['indicators']['rsi'] < 30 else '🟡 중립'}

**MACD:**
• MACD: {analysis['indicators']['macd']:.4f}
• Signal: {analysis['indicators']['macd_signal']:.4f}
• {'🟢 상승신호' if analysis['indicators']['macd'] > analysis['indicators']['macd_signal'] else '🔴 하락신호'}

**이동평균선:**
• 20일: ${analysis['indicators']['sma_20']:,.2f}
• 50일: ${analysis['indicators']['sma_50']:,.2f}
• {'🟢 단기>장기' if analysis['indicators']['sma_20'] > analysis['indicators']['sma_50'] else '🔴 단기<장기'}

**볼린저 밴드:**
• 상단: ${analysis['indicators']['bb_upper']:,.2f}
• 하단: ${analysis['indicators']['bb_lower']:,.2f}

**스토캐스틱:**
• %K: {analysis['indicators']['stoch_k']:.2f}
• %D: {analysis['indicators']['stoch_d']:.2f}

🎯 **매매 신호:**
{chr(10).join([f"• {signal}" for signal in analysis['signals']])}
            """
            
            await update.message.reply_text(analysis_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in analysis command: {e}")
            await update.message.reply_text("❌ 시장 분석 중 오류가 발생했습니다.")
    
    @AuthManager.require_auth
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """잔고 조회 명령어"""
        try:
            await update.message.reply_text("💰 잔고 조회 중...")
            
            balance = self.trading_bot.get_balance()
            if not balance:
                await update.message.reply_text("❌ 잔고 조회에 실패했습니다.")
                return
            
            # 잔고 정보 포맷팅
            balance_message = "💰 **계좌 잔고**\n\n"
            
            # USDT 잔고
            if 'USDT' in balance['total'] and balance['total']['USDT'] > 0:
                balance_message += f"💵 **USDT:** {balance['total']['USDT']:,.2f}\n"
            
            # 주요 암호화폐 잔고
            major_coins = ['BTC', 'ETH', 'BNB', 'ADA', 'DOT', 'LINK', 'LTC', 'XRP']
            for coin in major_coins:
                if coin in balance['total'] and balance['total'][coin] > 0:
                    balance_message += f"🪙 **{coin}:** {balance['total'][coin]:,.6f}\n"
            
            # 기타 코인들 (잔고가 있는 것만)
            other_coins = []
            for coin, amount in balance['total'].items():
                if amount > 0 and coin not in ['USDT'] + major_coins:
                    other_coins.append(f"🪙 **{coin}:** {amount:,.6f}")
            
            if other_coins:
                balance_message += "\n**기타 코인:**\n" + "\n".join(other_coins[:10])  # 최대 10개만 표시
            
            await update.message.reply_text(balance_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in balance command: {e}")
            await update.message.reply_text("❌ 잔고 조회 중 오류가 발생했습니다.")
    
    @AuthManager.require_auth
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """매매 신호 명령어"""
        try:
            # 명령어에서 심볼 추출
            args = context.args
            symbol = args[0] if args else Config.DEFAULT_SYMBOL
            
            await update.message.reply_text(f"🎯 {symbol} 매매 신호 분석 중...")
            
            # 시장 분석 수행
            analysis = self.trading_bot.analyze_market(symbol)
            if not analysis:
                await update.message.reply_text(f"❌ {symbol} 신호 분석에 실패했습니다.")
                return
            
            # 신호 분석
            signals = analysis['signals']
            current_price = analysis['current_price']
            
            # 매수/매도 신호 판단
            buy_signals = []
            sell_signals = []
            neutral_signals = []
            
            for signal in signals:
                if any(keyword in signal for keyword in ['과매도', '상승', '위']):
                    buy_signals.append(signal)
                elif any(keyword in signal for keyword in ['과매수', '하락', '아래']):
                    sell_signals.append(signal)
                else:
                    neutral_signals.append(signal)
            
            # 신호 메시지 생성
            signals_message = f"""
🎯 **{symbol} 매매 신호 분석**

💰 **현재가:** ${current_price:,.2f}

📊 **신호 요약:**
• 매수 신호: {len(buy_signals)}개
• 매도 신호: {len(sell_signals)}개
• 중립 신호: {len(neutral_signals)}개

{'🟢 **매수 신호:**' if buy_signals else ''}
{chr(10).join([f"• {signal}" for signal in buy_signals]) if buy_signals else ''}

{'🔴 **매도 신호:**' if sell_signals else ''}
{chr(10).join([f"• {signal}" for signal in sell_signals]) if sell_signals else ''}

{'🟡 **중립 신호:**' if neutral_signals else ''}
{chr(10).join([f"• {signal}" for signal in neutral_signals]) if neutral_signals else ''}

💡 **종합 의견:**
"""
            
            # 종합 의견 추가
            if len(buy_signals) > len(sell_signals):
                signals_message += "🟢 **매수 우세** - 기술적 지표상 매수 신호가 더 많습니다."
            elif len(sell_signals) > len(buy_signals):
                signals_message += "🔴 **매도 우세** - 기술적 지표상 매도 신호가 더 많습니다."
            else:
                signals_message += "🟡 **중립** - 매수/매도 신호가 균형을 이루고 있습니다."
            
            signals_message += "\n\n⚠️ **주의:** 이는 참고용이며, 실제 투자 결정은 신중히 하시기 바랍니다."
            
            await update.message.reply_text(signals_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in signals command: {e}")
            await update.message.reply_text("❌ 매매 신호 분석 중 오류가 발생했습니다.")
    
    @AuthManager.require_auth
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """메인 메뉴 명령어"""
        keyboard = [
            [
                InlineKeyboardButton("💰 현재가 조회", callback_data="price"),
                InlineKeyboardButton("📊 시장 분석", callback_data="analysis")
            ],
            [
                InlineKeyboardButton("💵 잔고 조회", callback_data="balance"),
                InlineKeyboardButton("🎯 매매 신호", callback_data="signals")
            ],
            [
                InlineKeyboardButton("❓ 도움말", callback_data="help"),
                InlineKeyboardButton("🔄 새로고침", callback_data="refresh")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🤖 **트레이딩 봇 메인 메뉴**\n\n원하는 기능을 선택하세요:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """버튼 콜백 처리"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "price":
            await self.price_command(update, context)
        elif query.data == "analysis":
            await self.analysis_command(update, context)
        elif query.data == "balance":
            await self.balance_command(update, context)
        elif query.data == "signals":
            await self.signals_command(update, context)
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "refresh":
            await query.edit_message_text("🔄 새로고침 완료!")
    
    def run(self):
        """봇 실행"""
        # 애플리케이션 생성
        self.application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # 명령어 핸들러 등록
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("price", self.price_command))
        self.application.add_handler(CommandHandler("analysis", self.analysis_command))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        self.application.add_handler(CommandHandler("signals", self.signals_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        
        # 버튼 콜백 핸들러
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # 에러 핸들러
        self.application.add_error_handler(self.error_handler)
        
        # 봇 시작
        logger.info("Starting Telegram Trading Bot...")
        self.application.run_polling()
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """에러 핸들러"""
        logger.error(f"Exception while handling an update: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

if __name__ == "__main__":
    bot = TelegramTradingBot()
    bot.run() 