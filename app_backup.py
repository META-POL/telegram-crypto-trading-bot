#!/usr/bin/env python3
"""
텔레그램 암호화폐 선물 거래 봇
완전 통합 버전 - 모든 기능이 하나의 파일에
"""

import os
import time
import hmac
import hashlib
import requests
import threading
import base64
import logging
from datetime import datetime
from flask import Flask, jsonify, request

# 라이브러리 import
try:
    from nacl.signing import SigningKey
except ImportError:
    SigningKey = None

try:
    import ccxt
except ImportError:
    ccxt = None

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

@app.route('/webhook', methods=['POST'])
def webhook():
    """텔레그램 웹훅 처리"""
    print("📨 웹훅 요청 수신")
    try:
        from telegram import Update
        from telegram.ext import ApplicationBuilder
        import asyncio
        
        # 텔레그램 봇 토큰
        token = "8356129181:AAF5bWX6z6HSAF2MeTtUIjx76jOW2i0Xj1I"
        
        # 봇 애플리케이션 생성
        telegram_app = ApplicationBuilder().token(token).build()
        
        # 요청 데이터 확인
        data = request.get_json()
        print(f"📨 받은 데이터: {data}")
        
        # 업데이트 처리
        update = Update.de_json(data, telegram_app.bot)
        
        # 콜백 쿼리 처리 (버튼 클릭)
        if update.callback_query:
            await handle_callback_query(update.callback_query, telegram_app)
            return jsonify({"status": "success"})
        
        # 명령어 처리
        if update.message and update.message.text:
            text = update.message.text
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            print(f"📨 사용자 {user_id}: {text}")
            
            async def send_response():
                try:
                    if text == '/start':
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        
                        # 메인 메뉴 버튼
                        keyboard = [
                            [InlineKeyboardButton("🔑 API 키 설정", callback_data="api_setup")],
                            [InlineKeyboardButton("💰 잔고 조회", callback_data="balance_menu")],
                            [InlineKeyboardButton("📈 거래쌍 조회", callback_data="symbols_menu")],
                            [InlineKeyboardButton("📊 포지션 관리", callback_data="position_menu")],
                            [InlineKeyboardButton("⚙️ 설정", callback_data="settings_menu")],
                            [InlineKeyboardButton("❓ 도움말", callback_data="help")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        response_text = (
                            "🤖 **암호화폐 선물 거래 봇**\n\n"
                            "버튼을 클릭하여 원하는 기능을 선택하세요!\n\n"
                            "**지원 거래소:**\n"
                            "• XT Exchange\n"
                            "• Backpack Exchange\n"
                            "• Hyperliquid\n"
                            "• Flipster\n\n"
                            "먼저 API 키를 설정해주세요!"
                        )
                        await telegram_app.bot.send_message(
                            chat_id=chat_id, 
                            text=response_text, 
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                        print(f"✅ 사용자 {user_id}에게 메인 메뉴 전송")
                        
                    elif text == '/test':
                        await telegram_app.bot.send_message(chat_id=chat_id, text="✅ 봇이 정상 작동 중입니다!")
                        print(f"✅ 테스트 응답 전송")
                        
                    elif text == '/ping':
                        await telegram_app.bot.send_message(chat_id=chat_id, text="🏓 Pong! 봇이 살아있습니다!")
                        print(f"✅ 핑 응답 전송")
                        
                    elif text.startswith('/balance'):
                        parts = text.split()
                        if len(parts) < 2:
                            await telegram_app.bot.send_message(chat_id=chat_id, text="❌ 사용법: /balance [거래소]")
                            return
                        
                        exchange = parts[1].lower()
                        api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                        api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                        
                        if not api_key or not api_secret:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ {exchange} API 키가 설정되지 않음")
                            return
                        
                        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                        result = trader.get_futures_balance()
                        
                        if result.get('status') == 'success':
                            balance_data = result.get('balance', {})
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"💰 {exchange} 잔고: {balance_data}")
                        else:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ 잔고 조회 실패: {result}")
                        
                    elif text.startswith('/symbols'):
                        parts = text.split()
                        if len(parts) < 2:
                            await telegram_app.bot.send_message(chat_id=chat_id, text="❌ 사용법: /symbols [거래소]")
                            return
                        
                        exchange = parts[1].lower()
                        api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                        api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                        
                        if not api_key or not api_secret:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ {exchange} API 키가 설정되지 않음")
                            return
                        
                        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                        result = trader.get_futures_symbols()
                        
                        if result.get('status') == 'success':
                            symbols_data = result.get('symbols', [])
                            symbols_text = f"📈 {exchange} 거래쌍 ({len(symbols_data)}개):\n"
                            for i, symbol in enumerate(symbols_data[:20], 1):
                                symbols_text += f"{i}. {symbol}\n"
                            if len(symbols_data) > 20:
                                symbols_text += f"... 및 {len(symbols_data) - 20}개 더"
                            await telegram_app.bot.send_message(chat_id=chat_id, text=symbols_text)
                        else:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ 거래쌍 조회 실패: {result}")
                        
                    elif text.startswith('/long'):
                        parts = text.split()
                        if len(parts) < 5:
                            await telegram_app.bot.send_message(chat_id=chat_id, text="❌ 사용법: /long [거래소] [심볼] [수량] [레버리지]")
                            return
                        
                        exchange = parts[1].lower()
                        symbol = parts[2].upper()
                        size = float(parts[3])
                        leverage = int(parts[4])
                        
                        api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                        api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                        
                        if not api_key or not api_secret:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ {exchange} API 키가 설정되지 않음")
                            return
                        
                        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                        result = trader.open_long_position(symbol, size, leverage)
                        
                        if result.get('status') == 'success':
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"✅ 롱 포지션 오픈 성공: {result}")
                        else:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ 롱 포지션 오픈 실패: {result}")
                        
                    elif text.startswith('/short'):
                        parts = text.split()
                        if len(parts) < 5:
                            await telegram_app.bot.send_message(chat_id=chat_id, text="❌ 사용법: /short [거래소] [심볼] [수량] [레버리지]")
                            return
                        
                        exchange = parts[1].lower()
                        symbol = parts[2].upper()
                        size = float(parts[3])
                        leverage = int(parts[4])
                        
                        api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                        api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                        
                        if not api_key or not api_secret:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ {exchange} API 키가 설정되지 않음")
                            return
                        
                        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                        result = trader.open_short_position(symbol, size, leverage)
                        
                        if result.get('status') == 'success':
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"✅ 숏 포지션 오픈 성공: {result}")
                        else:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ 숏 포지션 오픈 실패: {result}")
                        
                    elif text.startswith('/close'):
                        parts = text.split()
                        if len(parts) < 3:
                            await telegram_app.bot.send_message(chat_id=chat_id, text="❌ 사용법: /close [거래소] [심볼]")
                            return
                        
                        exchange = parts[1].lower()
                        symbol = parts[2].upper()
                        
                        api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                        api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                        
                        if not api_key or not api_secret:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ {exchange} API 키가 설정되지 않음")
                            return
                        
                        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                        result = trader.close_position(symbol)
                        
                        if result.get('status') == 'success':
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"✅ 포지션 종료 성공: {result}")
                        else:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ 포지션 종료 실패: {result}")
                        
                    elif text.startswith('/positions'):
                        parts = text.split()
                        if len(parts) < 2:
                            await telegram_app.bot.send_message(chat_id=chat_id, text="❌ 사용법: /positions [거래소]")
                            return
                        
                        exchange = parts[1].lower()
                        api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                        api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                        
                        if not api_key or not api_secret:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ {exchange} API 키가 설정되지 않음")
                            return
                        
                        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                        result = trader.get_positions()
                        
                        if result.get('status') == 'success':
                            positions_data = result.get('positions', {})
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"📊 {exchange} 포지션: {positions_data}")
                        else:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ 포지션 조회 실패: {result}")
                        
                    elif text.startswith('/leverage'):
                        parts = text.split()
                        if len(parts) < 4:
                            await telegram_app.bot.send_message(chat_id=chat_id, text="❌ 사용법: /leverage [거래소] [심볼] [레버리지]")
                            return
                        
                        exchange = parts[1].lower()
                        symbol = parts[2].upper()
                        leverage = int(parts[3])
                        
                        api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
                        api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
                        
                        if not api_key or not api_secret:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ {exchange} API 키가 설정되지 않음")
                            return
                        
                        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                        result = trader.set_leverage(symbol, leverage)
                        
                        if result.get('status') == 'success':
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"✅ 레버리지 설정 성공: {result}")
                        else:
                            await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ 레버리지 설정 실패: {result}")
                        
                    elif text.startswith('/setapi'):
                        parts = text.split()
                        if len(parts) < 4:
                            await telegram_app.bot.send_message(chat_id=chat_id, text="❌ 사용법: /setapi [거래소] [API_KEY] [SECRET_KEY]")
                            return
                        
                        exchange = parts[1].lower()
                        api_key = parts[2]
                        api_secret = parts[3]
                        
                        # 환경변수로 설정 (실제로는 데이터베이스에 저장해야 함)
                        os.environ[f'{exchange.upper()}_API_KEY'] = api_key
                        os.environ[f'{exchange.upper()}_API_SECRET'] = api_secret
                        
                        await telegram_app.bot.send_message(
                            chat_id=chat_id, 
                            text=f"✅ {exchange.upper()} API 키가 설정되었습니다!\n\n이제 해당 거래소의 기능을 사용할 수 있습니다."
                        )
                        print(f"✅ 사용자 {user_id}가 {exchange} API 키 설정")
                        
                    else:
                        await telegram_app.bot.send_message(chat_id=chat_id, text="❓ 알 수 없는 명령어입니다. /start를 입력해보세요.")
                        
                except Exception as e:
                    print(f"❌ 응답 전송 오류: {e}")
                    await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ 오류가 발생했습니다: {str(e)}")
            
            # 비동기 함수 실행
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_response())
                loop.close()
            except Exception as e:
                print(f"❌ 비동기 실행 오류: {e}")
        
        print("✅ 웹훅 처리 완료")
        return jsonify({"status": "success"})
        
    except Exception as e:
        print(f"❌ 웹훅 오류: {e}")
        import traceback
        print(f"❌ 웹훅 스택 트레이스: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

async def handle_callback_query(callback_query, telegram_app):
    """콜백 쿼리 처리 (버튼 클릭)"""
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        chat_id = callback_query.message.chat_id
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        print(f"🔘 사용자 {user_id}가 버튼 클릭: {data}")
        
        if data == "api_setup":
            # API 키 설정 메뉴
            keyboard = [
                [InlineKeyboardButton("XT Exchange", callback_data="api_xt")],
                [InlineKeyboardButton("Backpack Exchange", callback_data="api_backpack")],
                [InlineKeyboardButton("Hyperliquid", callback_data="api_hyperliquid")],
                [InlineKeyboardButton("Flipster", callback_data="api_flipster")],
                [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🔑 **API 키 설정**\n\n거래소를 선택하여 API 키를 설정하세요.\n\n**설정 방법:**\n1. 거래소에서 API 키 생성\n2. API Key와 Secret Key 복사\n3. 아래 버튼 클릭하여 입력",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        elif data.startswith("api_"):
            # 특정 거래소 API 설정
            exchange = data.replace("api_", "")
            exchange_names = {
                "xt": "XT Exchange",
                "backpack": "Backpack Exchange", 
                "hyperliquid": "Hyperliquid",
                "flipster": "Flipster"
            }
            
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=f"🔑 **{exchange_names[exchange]} API 설정**\n\n"
                     f"다음 형식으로 API 키를 입력하세요:\n\n"
                     f"`/setapi {exchange} YOUR_API_KEY YOUR_SECRET_KEY`\n\n"
                     f"예시:\n"
                     f"`/setapi {exchange} abc123def456 ghi789jkl012`\n\n"
                     f"⚠️ **주의:** API 키는 안전하게 저장됩니다.",
                parse_mode='Markdown'
            )
            
        elif data == "balance_menu":
            # 잔고 조회 메뉴
            keyboard = [
                [InlineKeyboardButton("XT Exchange", callback_data="balance_xt")],
                [InlineKeyboardButton("Backpack Exchange", callback_data="balance_backpack")],
                [InlineKeyboardButton("Hyperliquid", callback_data="balance_hyperliquid")],
                [InlineKeyboardButton("Flipster", callback_data="balance_flipster")],
                [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="💰 **잔고 조회**\n\n거래소를 선택하여 잔고를 조회하세요.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        elif data.startswith("balance_"):
            # 특정 거래소 잔고 조회
            exchange = data.replace("balance_", "")
            api_key = os.environ.get(f'{exchange.upper()}_API_KEY')
            api_secret = os.environ.get(f'{exchange.upper()}_API_SECRET')
            
            if not api_key or not api_secret:
                await telegram_app.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"❌ {exchange.upper()} API 키가 설정되지 않았습니다.\n\n먼저 API 키를 설정해주세요.",
                    parse_mode='Markdown'
                )
                return
            
            try:
                trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                result = trader.get_futures_balance()
                
                if result.get('status') == 'success':
                    balance_data = result.get('balance', {})
                    await telegram_app.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=f"💰 **{exchange.upper()} 잔고**\n\n```\n{balance_data}\n```",
                        parse_mode='Markdown'
                    )
                else:
                    await telegram_app.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=callback_query.message.message_id,
                        text=f"❌ 잔고 조회 실패: {result}",
                        parse_mode='Markdown'
                    )
            except Exception as e:
                await telegram_app.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=callback_query.message.message_id,
                    text=f"❌ 오류 발생: {str(e)}",
                    parse_mode='Markdown'
                )
                
        elif data == "main_menu":
            # 메인 메뉴로 돌아가기
            keyboard = [
                [InlineKeyboardButton("🔑 API 키 설정", callback_data="api_setup")],
                [InlineKeyboardButton("💰 잔고 조회", callback_data="balance_menu")],
                [InlineKeyboardButton("📈 거래쌍 조회", callback_data="symbols_menu")],
                [InlineKeyboardButton("📊 포지션 관리", callback_data="position_menu")],
                [InlineKeyboardButton("⚙️ 설정", callback_data="settings_menu")],
                [InlineKeyboardButton("❓ 도움말", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text="🤖 **암호화폐 선물 거래 봇**\n\n버튼을 클릭하여 원하는 기능을 선택하세요!",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        elif data == "help":
            # 도움말
            help_text = (
                "❓ **도움말**\n\n"
                "**사용 방법:**\n"
                "1. 🔑 API 키 설정 - 거래소 API 키 입력\n"
                "2. 💰 잔고 조회 - 계좌 잔고 확인\n"
                "3. 📈 거래쌍 조회 - 거래 가능한 심볼 확인\n"
                "4. 📊 포지션 관리 - 포지션 오픈/종료\n\n"
                "**지원 거래소:**\n"
                "• XT Exchange\n"
                "• Backpack Exchange\n"
                "• Hyperliquid\n"
                "• Flipster\n\n"
                "**명령어:**\n"
                "• `/setapi [거래소] [API_KEY] [SECRET_KEY]` - API 키 설정\n"
                "• `/balance [거래소]` - 잔고 조회\n"
                "• `/symbols [거래소]` - 거래쌍 조회"
            )
            
            keyboard = [[InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=help_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        # 콜백 쿼리 응답
        await callback_query.answer()
        
    except Exception as e:
        print(f"❌ 콜백 쿼리 처리 오류: {e}")
        await callback_query.answer("❌ 오류가 발생했습니다.")

@app.route('/setup-webhook')
def setup_webhook_route():
    """웹훅 설정 엔드포인트"""
    print("🔗 웹훅 설정 엔드포인트 호출")
    success = setup_webhook()
    if success:
        return jsonify({"status": "success", "message": "웹훅 설정 완료"})
    else:
        return jsonify({"status": "error", "message": "웹훅 설정 실패"}), 500

@app.route('/test-webhook')
def test_webhook():
    """웹훅 테스트 엔드포인트"""
    return jsonify({
        "status": "success", 
        "message": "웹훅 엔드포인트가 정상 작동 중입니다",
        "timestamp": datetime.now().isoformat()
    })



# 선물거래 클래스
class UnifiedFuturesTrader:
    def __init__(self, exchange, **kwargs):
        self.exchange = exchange.lower()
        self.is_trading = True
        self.total_profit = 0.0
        self.lock = threading.Lock()
        self.active_orders = {}  # 활성 주문 추적
        self.positions = {}  # 포지션 추적
        self.risk_settings = {
            'max_loss': 100,  # 최대 손실 한도 (USDT)
            'stop_loss_percent': 5,  # 손절매 비율 (%)
            'take_profit_percent': 10,  # 익절매 비율 (%)
            'max_position_size': 1000,  # 최대 포지션 크기 (USDT)
            'max_leverage': 10  # 최대 레버리지
        }
        
        if self.exchange == 'xt':
            self.api_key = kwargs.get('api_key')
            self.api_secret = kwargs.get('api_secret')
            self.base_url = "https://sapi.xt.com"
        elif self.exchange == 'backpack':
            self.api_key = kwargs.get('api_key')
            self.private_key = kwargs.get('private_key')
            self.base_url = "https://api.backpack.exchange/api/v1"
            if SigningKey:
                self.signing_key = SigningKey(base64.b64decode(self.private_key))
            else:
                raise ImportError("pynacl 패키지가 필요합니다.")
        elif self.exchange == 'hyperliquid':
            if ccxt is None:
                raise ImportError("ccxt 패키지가 필요합니다.")
            self.api_key = kwargs.get('api_key')
            self.api_secret = kwargs.get('api_secret')
            self.ccxt_client = ccxt.hyperliquid({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
            })
        elif self.exchange == 'flipster':
            if ccxt is None:
                raise ImportError("ccxt 패키지가 필요합니다.")
            self.api_key = kwargs.get('api_key')
            self.api_secret = kwargs.get('api_secret')
            self.ccxt_client = ccxt.flipster({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
            })
        else:
            raise ValueError('지원하지 않는 거래소입니다: xt, backpack, hyperliquid, flipster만 지원')

    def set_risk_settings(self, max_loss=None, stop_loss_percent=None, take_profit_percent=None, max_position_size=None, max_leverage=None):
        """리스크 설정 업데이트"""
        if max_loss is not None:
            self.risk_settings['max_loss'] = max_loss
        if stop_loss_percent is not None:
            self.risk_settings['stop_loss_percent'] = stop_loss_percent
        if take_profit_percent is not None:
            self.risk_settings['take_profit_percent'] = take_profit_percent
        if max_position_size is not None:
            self.risk_settings['max_position_size'] = max_position_size
        if max_leverage is not None:
            self.risk_settings['max_leverage'] = max_leverage

    def _get_headers_xt(self, params=None):
        """XT API 헤더 생성"""
        timestamp = str(int(time.time() * 1000))
        params = params or {}
        sign_str = '&'.join([f"{k}={params[k]}" for k in sorted(params)]) + f"&timestamp={timestamp}"
        signature = hmac.new(self.api_secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
        return {
            "XT-API-KEY": self.api_key,
            "XT-API-SIGN": signature,
            "XT-API-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

    def _get_headers_backpack(self, instruction, params=None):
        """Backpack API 헤더 생성"""
        timestamp = str(int(time.time() * 1000))
        window = "5000"
        params = params or {}
        param_str = '&'.join([f"{k}={params[k]}" for k in sorted(params)])
        sign_str = f"instruction={instruction}"
        if param_str:
            sign_str += f"&{param_str}"
        sign_str += f"&timestamp={timestamp}&window={window}"
        signature = self.signing_key.sign(sign_str.encode())
        signature_b64 = base64.b64encode(signature.signature).decode()
        return {
            "X-API-Key": self.api_key,
            "X-Signature": signature_b64,
            "X-Timestamp": timestamp,
            "X-Window": window,
            "Content-Type": "application/json"
        }

    def get_futures_balance(self):
        """선물 계좌 잔고 조회"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/api/v4/futures/account/balance"
                headers = self._get_headers_xt()
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'balance': data.get('result', {}),
                        'message': 'XT 선물 잔고 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 선물 잔고 조회 실패: {response.status_code}'
                    }
            
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/capital"
                headers = self._get_headers_backpack("queryCapital")
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'balance': data,
                        'message': 'Backpack 선물 잔고 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'Backpack 선물 잔고 조회 실패: {response.status_code}'
                    }
            
            elif self.exchange in ['hyperliquid', 'flipster']:
                balance = self.ccxt_client.fetch_balance()
                return {
                    'status': 'success',
                    'balance': balance,
                    'message': f'{self.exchange.capitalize()} 선물 잔고 조회 성공'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'선물 잔고 조회 오류: {str(e)}'
            }

    def get_futures_symbols(self):
        """선물 거래쌍 조회"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/api/v4/futures/contract/list"
                headers = self._get_headers_xt()
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    symbols = [item['symbol'] for item in data.get('result', [])]
                    return {
                        'status': 'success',
                        'symbols': symbols,
                        'message': f'XT 선물 거래쌍 {len(symbols)}개 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 선물 거래쌍 조회 실패: {response.status_code}'
                    }
            
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/markets"
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    symbols = [item['symbol'] for item in data if item.get('type') == 'FUTURE']
                    return {
                        'status': 'success',
                        'symbols': symbols,
                        'message': f'Backpack 선물 거래쌍 {len(symbols)}개 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'Backpack 선물 거래쌍 조회 실패: {response.status_code}'
                    }
            
            elif self.exchange in ['hyperliquid', 'flipster']:
                markets = self.ccxt_client.load_markets()
                futures_symbols = [symbol for symbol, market in markets.items() if market.get('type') == 'future']
                return {
                    'status': 'success',
                    'symbols': futures_symbols,
                    'message': f'{self.exchange.capitalize()} 선물 거래쌍 {len(futures_symbols)}개 조회 성공'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'선물 거래쌍 조회 오류: {str(e)}'
            }

    def open_long_position(self, symbol, size, leverage=1, stop_loss=None, take_profit=None):
        """롱 포지션 오픈"""
        try:
            if self.exchange == 'xt':
                return self._open_position_xt(symbol, 'buy', size, leverage, stop_loss, take_profit)
            elif self.exchange == 'backpack':
                return self._open_position_backpack(symbol, 'buy', size, leverage, stop_loss, take_profit)
            elif self.exchange in ['hyperliquid', 'flipster']:
                return self._open_position_ccxt(symbol, 'buy', size, leverage, stop_loss, take_profit)
        except Exception as e:
            return {
                'status': 'error',
                'message': f'롱 포지션 오픈 오류: {str(e)}'
            }

    def open_short_position(self, symbol, size, leverage=1, stop_loss=None, take_profit=None):
        """숏 포지션 오픈"""
        try:
            if self.exchange == 'xt':
                return self._open_position_xt(symbol, 'sell', size, leverage, stop_loss, take_profit)
            elif self.exchange == 'backpack':
                return self._open_position_backpack(symbol, 'sell', size, leverage, stop_loss, take_profit)
            elif self.exchange in ['hyperliquid', 'flipster']:
                return self._open_position_ccxt(symbol, 'sell', size, leverage, stop_loss, take_profit)
        except Exception as e:
            return {
                'status': 'error',
                'message': f'숏 포지션 오픈 오류: {str(e)}'
            }

    def close_position(self, symbol, position_id=None):
        """포지션 종료"""
        try:
            if self.exchange == 'xt':
                return self._close_position_xt(symbol, position_id)
            elif self.exchange == 'backpack':
                return self._close_position_backpack(symbol, position_id)
            elif self.exchange in ['hyperliquid', 'flipster']:
                return self._close_position_ccxt(symbol, position_id)
        except Exception as e:
            return {
                'status': 'error',
                'message': f'포지션 종료 오류: {str(e)}'
            }

    def get_positions(self):
        """현재 포지션 조회"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/api/v4/futures/position/list"
                headers = self._get_headers_xt()
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'positions': data.get('result', []),
                        'message': 'XT 포지션 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 포지션 조회 실패: {response.status_code}'
                    }
            
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/positions"
                headers = self._get_headers_backpack("queryPositions")
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'positions': data,
                        'message': 'Backpack 포지션 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'Backpack 포지션 조회 실패: {response.status_code}'
                    }
            
            elif self.exchange in ['hyperliquid', 'flipster']:
                positions = self.ccxt_client.fetch_positions()
                return {
                    'status': 'success',
                    'positions': positions,
                    'message': f'{self.exchange.capitalize()} 포지션 조회 성공'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'포지션 조회 오류: {str(e)}'
            }

    def set_leverage(self, symbol, leverage):
        """레버리지 설정"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/api/v4/futures/account/leverage"
                params = {
                    'symbol': symbol,
                    'leverage': leverage
                }
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    return {
                        'status': 'success',
                        'message': f'XT 레버리지 {leverage}배 설정 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 레버리지 설정 실패: {response.status_code}'
                    }
            
            elif self.exchange in ['hyperliquid', 'flipster']:
                self.ccxt_client.set_leverage(leverage, symbol)
                return {
                    'status': 'success',
                    'message': f'{self.exchange.capitalize()} 레버리지 {leverage}배 설정 성공'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'레버리지 설정 오류: {str(e)}'
            }

    def test_api_connection(self):
        """API 연결 테스트"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/api/v4/futures/account/balance"
                headers = self._get_headers_xt()
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    return {
                        'status': 'success',
                        'message': 'XT 선물 API 연결 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 선물 API 연결 실패: {response.status_code}'
                    }
            
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/capital"
                headers = self._get_headers_backpack("queryCapital")
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    return {
                        'status': 'success',
                        'message': 'Backpack 선물 API 연결 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'Backpack 선물 API 연결 실패: {response.status_code}'
                    }
            
            elif self.exchange in ['hyperliquid', 'flipster']:
                self.ccxt_client.fetch_balance()
                return {
                    'status': 'success',
                    'message': f'{self.exchange.capitalize()} 선물 API 연결 성공'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'API 연결 테스트 오류: {str(e)}'
            }

    def _open_position_xt(self, symbol, side, size, leverage, stop_loss, take_profit):
        """XT 선물 포지션 오픈"""
        url = f"{self.base_url}/api/v4/futures/order/place"
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'market',
            'size': size,
            'leverage': leverage
        }
        
        if stop_loss:
            params['stopLoss'] = stop_loss
        if take_profit:
            params['takeProfit'] = take_profit
            
        headers = self._get_headers_xt(params)
        response = requests.post(url, headers=headers, json=params)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'status': 'success',
                'order_id': data.get('result', {}).get('orderId'),
                'message': f'XT {side.upper()} 포지션 오픈 성공'
            }
        else:
            return {
                'status': 'error',
                'message': f'XT 포지션 오픈 실패: {response.status_code}'
            }

    def _open_position_backpack(self, symbol, side, size, leverage, stop_loss, take_profit):
        """Backpack 선물 포지션 오픈"""
        url = f"{self.base_url}/order"
        params = {
            'symbol': symbol,
            'side': side.upper(),
            'orderType': 'MARKET',
            'quantity': size,
            'leverage': leverage
        }
        
        headers = self._get_headers_backpack("order", params)
        response = requests.post(url, headers=headers, json=params)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'status': 'success',
                'order_id': data.get('orderId'),
                'message': f'Backpack {side.upper()} 포지션 오픈 성공'
            }
        else:
            return {
                'status': 'error',
                'message': f'Backpack 포지션 오픈 실패: {response.status_code}'
            }

    def _open_position_ccxt(self, symbol, side, size, leverage, stop_loss, take_profit):
        """CCXT 기반 거래소 선물 포지션 오픈"""
        try:
            # 레버리지 설정
            self.ccxt_client.set_leverage(leverage, symbol)
            
            # 시장가 주문
            order = self.ccxt_client.create_market_order(
                symbol=symbol,
                side=side,
                amount=size,
                params={
                    'leverage': leverage,
                    'stopLoss': stop_loss,
                    'takeProfit': take_profit
                }
            )
            
            return {
                'status': 'success',
                'order_id': order.get('id'),
                'message': f'{self.exchange.capitalize()} {side.upper()} 포지션 오픈 성공'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'{self.exchange.capitalize()} 포지션 오픈 실패: {str(e)}'
            }

    def _close_position_xt(self, symbol, position_id):
        """XT 포지션 종료"""
        url = f"{self.base_url}/api/v4/futures/position/close"
        params = {
            'symbol': symbol
        }
        if position_id:
            params['positionId'] = position_id
            
        headers = self._get_headers_xt(params)
        response = requests.post(url, headers=headers, json=params)
        
        if response.status_code == 200:
            return {
                'status': 'success',
                'message': 'XT 포지션 종료 성공'
            }
        else:
            return {
                'status': 'error',
                'message': f'XT 포지션 종료 실패: {response.status_code}'
            }

    def _close_position_backpack(self, symbol, position_id):
        """Backpack 포지션 종료"""
        url = f"{self.base_url}/position/close"
        params = {
            'symbol': symbol
        }
        if position_id:
            params['positionId'] = position_id
            
        headers = self._get_headers_backpack("closePosition", params)
        response = requests.post(url, headers=headers, json=params)
        
        if response.status_code == 200:
            return {
                'status': 'success',
                'message': 'Backpack 포지션 종료 성공'
            }
        else:
            return {
                'status': 'error',
                'message': f'Backpack 포지션 종료 실패: {response.status_code}'
            }

    def _close_position_ccxt(self, symbol, position_id):
        """CCXT 기반 거래소 포지션 종료"""
        try:
            # 모든 포지션 조회
            positions = self.ccxt_client.fetch_positions([symbol])
            
            for position in positions:
                if position.get('size', 0) != 0:  # 포지션이 있는 경우
                    # 반대 방향으로 시장가 주문하여 포지션 종료
                    close_side = 'sell' if position.get('side') == 'long' else 'buy'
                    order = self.ccxt_client.create_market_order(
                        symbol=symbol,
                        side=close_side,
                        amount=abs(position.get('size', 0))
                    )
                    
                    return {
                        'status': 'success',
                        'order_id': order.get('id'),
                        'message': f'{self.exchange.capitalize()} 포지션 종료 성공'
                    }
            
            return {
                'status': 'error',
                'message': f'{self.exchange.capitalize()}에서 종료할 포지션이 없습니다'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'{self.exchange.capitalize()} 포지션 종료 실패: {str(e)}'
            }

# 사용자별 거래자 저장
user_traders = {}

async def setup_webhook_async():
    """웹훅 설정 (비동기)"""
    try:
        from telegram.ext import ApplicationBuilder
        
        # 텔레그램 봇 토큰
        token = "8356129181:AAF5bWX6z6HSAF2MeTtUIjx76jOW2i0Xj1I"
        
        # 봇 애플리케이션 생성
        telegram_app = ApplicationBuilder().token(token).build()
        
        # Railway URL 가져오기 (여러 환경변수 시도)
        railway_url = None
        
        # 1. RAILWAY_STATIC_URL 시도
        railway_url = os.environ.get('RAILWAY_STATIC_URL')
        
        # 2. RAILWAY_PUBLIC_DOMAIN 시도
        if not railway_url:
            public_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
            if public_domain:
                railway_url = f"https://{public_domain}"
        
        # 3. PORT 환경변수로 Railway 감지 후 기본 URL 사용
        if not railway_url and os.environ.get('PORT'):
            railway_url = "https://telegram-crypto-trading-bot-production.up.railway.app"
        
        # 4. 최후 수단으로 하드코딩된 URL (Railway에서 실제 도메인으로 변경 필요)
        if not railway_url:
            # Railway 대시보드에서 실제 도메인을 확인하고 여기에 입력하세요
            railway_url = "https://telegram-crypto-trading-bot-production.up.railway.app"
        
        print(f"🔍 사용할 Railway URL: {railway_url}")
        
        webhook_url = f"{railway_url}/webhook"
        
        print(f"🔗 웹훅 URL 설정: {webhook_url}")
        
        # 웹훅 설정 (비동기)
        result = await telegram_app.bot.set_webhook(url=webhook_url)
        
        if result:
            print(f"✅ 웹훅 설정 성공: {webhook_url}")
            return True
        else:
            print("❌ 웹훅 설정 실패")
            return False
            
    except Exception as e:
        print(f"❌ 웹훅 설정 오류: {e}")
        return False

def setup_webhook():
    """웹훅 설정 (동기 래퍼)"""
    import asyncio
    try:
        # 새로운 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 비동기 함수 실행
        result = loop.run_until_complete(setup_webhook_async())
        
        # 루프 정리
        loop.close()
        
        return result
        
    except Exception as e:
        print(f"❌ 웹훅 설정 래퍼 오류: {e}")
        return False

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 서버 시작: 포트 {port}")
    
    # Flask 서버 시작
    print("🌐 Flask 서버 시작...")
    
    # 웹훅 설정 시도
    print("🔗 웹훅 설정 시도...")
    setup_webhook()
    
    # Flask 서버 시작
    app.run(host='0.0.0.0', port=port, debug=False) 