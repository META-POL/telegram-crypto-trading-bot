import logging
import sqlite3
import threading
import time
import base64
import json
import hmac
import hashlib
import requests
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask 앱 설정
app = Flask(__name__)

# 전역 변수
PYXTLIB_AVAILABLE = False
try:
    from pyxt import XTClient
    PYXTLIB_AVAILABLE = True
except ImportError:
    logger.warning("pyxt 라이브러리가 설치되지 않았습니다. 기본 HTTP 요청을 사용합니다.")

# SigningKey 전역 변수로 초기화
try:
    from nacl.signing import SigningKey
except ImportError:
    SigningKey = None
    logger.error("pynacl 패키지가 필요합니다. 설치: pip install pynacl")

class TelegramApp:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.bot = None
        self.app = Application.builder().token(bot_token).build()
        self.setup_handlers()

    def setup_handlers(self):
        """핸들러 설정"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("setapi", self.set_api))
        self.app.add_handler(CommandHandler("test", self.test_api))
        self.app.add_handler(CommandHandler("trade", self.handle_trade_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    async def start(self, update, context):
        """봇 시작 명령어"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        await show_main_menu(self, chat_id)

    async def set_api(self, update, context):
        """API 키 설정 명령어"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        args = context.args
        if len(args) < 3:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ 사용법: /setapi [거래소] [API_KEY] [SECRET_KEY]\n"
                     "예시: /setapi xt YOUR_API_KEY YOUR_SECRET_KEY\n"
                     "예시: /setapi backpack YOUR_API_KEY YOUR_PRIVATE_KEY",
                parse_mode='Markdown'
            )
            return
        exchange, api_key, api_secret = args[0].lower(), args[1], ' '.join(args[2:])
        try:
            save_user_api_keys(user_id, exchange, api_key, api_secret)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ {exchange.upper()} API 키가 설정되었습니다.\n"
                     f"연결 테스트: /test\n"
                     f"메인 메뉴로 돌아가기: /start",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"API 설정 오류: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ API 키 설정 실패: {str(e)}",
                parse_mode='Markdown'
            )

    async def test_api(self, update, context):
        """API 연결 테스트 명령어"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        user_keys = get_user_api_keys(user_id)
        if not user_keys:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ API 키가 설정되지 않았습니다. 먼저 /setapi 명령어로 설정하세요.",
                parse_mode='Markdown'
            )
            return
        text = "🔍 **API 연결 테스트 결과**\n\n"
        for exchange in ['xt', 'backpack']:
            if user_keys.get(f'{exchange}_api_key'):
                api_key = user_keys.get(f'{exchange}_api_key')
                api_secret = user_keys.get(f'{exchange}_api_secret') or user_keys.get(f'{exchange}_private_key')
                trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
                result = trader.test_api_connection()
                text += f"**{exchange.upper()}**: {result['message']}\n"
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')

    async def handle_callback(self, update, context):
        """콜백 쿼리 처리"""
        query = update.callback_query
        data = query.data
        chat_id = query.message.chat_id
        user_id = query.effective_user.id
        if data == "main_menu":
            await show_main_menu(self, chat_id)
        elif data == "api_management":
            await show_api_management_menu(self, chat_id, user_id, query)
        elif data.startswith("api_"):
            await handle_api_callback(self, chat_id, user_id, data, query)
        elif data.startswith("balance_"):
            await handle_balance_callback(self, chat_id, user_id, data, query)
        elif data.startswith("trade_") or data.startswith("order_type_") or data.startswith("leverage_") or data.startswith("futures_"):
            await handle_trade_callback(self, chat_id, user_id, data, query)
        elif data == "position_menu":
            await show_position_menu(self, chat_id, user_id, query)
        elif data == "position_list":
            await show_position_list_menu(self, chat_id, user_id, query)
        elif data == "position_close":
            await show_position_close_menu(self, chat_id, user_id, query)
        elif data.startswith("position_list_") or data.startswith("position_close_"):
            await handle_position_callback(self, chat_id, user_id, data, query)
        elif data == "settings_menu":
            await show_settings_menu(self, chat_id, user_id, query)
        elif data == "help":
            await show_help(self, chat_id, query)
        await query.answer()

    async def handle_text(self, update, context):
        """텍스트 메시지 처리"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        text = update.message.text
        if "quantity" in context.user_data:
            await handle_quantity_input(self, chat_id, user_id, text, context)
        elif "leverage" in context.user_data:
            await handle_leverage_input(self, chat_id, user_id, text, context)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔍 명령어를 입력하거나 메뉴를 사용하세요. /start로 메인 메뉴로 돌아갈 수 있습니다.",
                parse_mode='Markdown'
            )

class UnifiedFuturesTrader:
    def __init__(self, exchange, **kwargs):
        self.exchange = exchange.lower()
        self.is_trading = True
        self.total_profit = 0.0
        self.lock = threading.Lock()
        self.active_orders = {}
        self.positions = {}
        self.risk_settings = {
            'max_loss': 100,
            'stop_loss_percent': 5,
            'take_profit_percent': 10,
            'max_position_size': 1000,
            'max_leverage': 10
        }
        
        if self.exchange == 'xt':
            self.api_key = kwargs.get('api_key')
            self.api_secret = kwargs.get('api_secret')
            self.base_url = "https://fapi.xt.com"
            self.spot_base_url = "https://sapi.xt.com"
        elif self.exchange == 'backpack':
            self.api_key = kwargs.get('api_key')
            self.private_key = kwargs.get('private_key') or kwargs.get('api_secret')
            self.base_url = "https://api.backpack.exchange/api/v1"
            self.signing_key = None
        else:
            raise ValueError('지원하지 않는 거래소입니다: xt, backpack만 지원')

    def test_api_connection(self):
        """API 연결 테스트"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/v4/public/time"
                response = requests.get(url)
                if response.status_code == 200:
                    return {'status': 'success', 'message': 'XT API 연결 성공'}
                else:
                    return {'status': 'error', 'message': f'XT API 연결 실패: {response.status_code}'}
            elif self.exchange == 'backpack':
                try:
                    global SigningKey
                    if SigningKey is None:
                        from nacl.signing import SigningKey
                    if self.private_key:
                        self.signing_key = SigningKey(base64.b64decode(self.private_key))
                    url = "https://api.backpack.exchange/api/v1/account"
                    headers = self._get_headers_backpack("accountQuery")
                    response = requests.get(url, headers=headers)
                    logger.debug(f"Backpack API test response: {response.status_code} - {response.text}")
                    if response.status_code == 200:
                        return {'status': 'success', 'message': 'Backpack API 연결 성공'}
                    else:
                        return {'status': 'error', 'message': f'Backpack API 연결 실패: {response.status_code} - {response.text}'}
                except ImportError:
                    return {'status': 'error', 'message': 'pynacl 패키지가 필요합니다. pip install pynacl로 설치해주세요.'}
                except Exception as e:
                    return {'status': 'error', 'message': f'Backpack API 연결 테스트 오류: {str(e)}'}
        except Exception as e:
            return {'status': 'error', 'message': f'API 연결 테스트 오류: {str(e)}'}

    def _get_headers_backpack(self, instruction, params=None):
        from nacl.signing import SigningKey
        from nacl.encoding import RawEncoder
        import base64
        import time
        import json

        for attempt in range(3):
            if self.signing_key is None and self.private_key:
                try:
                    self.signing_key = SigningKey(base64.b64decode(self.private_key), encoder=RawEncoder)
                except Exception as e:
                    logger.error(f"Backpack signing key initialization failed: {e}")
                    raise ValueError(f"Invalid private key: {e}")

            timestamp = int(time.time() * 1000)
            window = 5000
            params = params or {}
            items = sorted(params.items(), key=lambda x: x[0])
            parts = []
            for k, v in items:
                if isinstance(v, (int, float)):
                    v = str(round(float(v), 8))
                parts.append(f"{k}={v}")

            sign_str = f"instruction={instruction}"
            if parts:
                sign_str += "&" + "&".join(parts)
            sign_str += f"&timestamp={timestamp}&window={window}"

            logger.debug(f"Backpack signature string (attempt {attempt + 1}): {sign_str}")
            logger.debug(f"Backpack request params: {params}")

            try:
                sig = self.signing_key.sign(sign_str.encode('utf-8')).signature
                signature_b64 = base64.b64encode(sig).decode('utf-8')
                headers = {
                    "X-API-Key": self.api_key,
                    "X-Signature": signature_b64,
                    "X-Timestamp": str(timestamp),
                    "X-Window": str(window),
                    "Content-Type": "application/json; charset=utf-8"
                }
                logger.debug(f"Backpack headers: {headers}")
                return headers
            except Exception as e:
                logger.error(f"Backpack signature creation failed (attempt {attempt + 1}): {e}")
                if attempt == 2:
                    raise ValueError(f"Signature creation error after 3 attempts: {e}")
                time.sleep(1)

    def _get_headers_xt(self, params=None):
        """XT API 헤더 생성"""
        timestamp = str(int(time.time() * 1000))
        params = params or {}
        sorted_params = sorted(params.items())
        query_string = '&'.join([f"{k}={str(v)}" for k, v in sorted_params])
        sign_string = f"access_key={self.api_key}&{query_string}&timestamp={timestamp}" if query_string else f"access_key={self.api_key}&timestamp={timestamp}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        headers = {
            "access_key": self.api_key,
            "signature": signature,
            "timestamp": timestamp,
            "Content-Type": "application/json"
        }
        logger.debug(f"XT sign string: {sign_string}")
        logger.debug(f"XT headers: {headers}")
        return headers

    def open_long_position(self, symbol, size, leverage=1, order_type='market', market_type='futures'):
        """롱 포지션 오픈"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/v4/order"
                params = {
                    'symbol': symbol,
                    'side': 'buy',
                    'type': order_type,
                    'quantity': str(size)
                }
                if market_type == 'futures' and leverage > 1:
                    params['leverage'] = leverage
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                if response.status_code == 200:
                    data = response.json()
                    order_id = data.get('orderId', 'unknown')
                    return {'status': 'success', 'order_id': order_id, 'message': 'XT 롱 포지션 오픈 성공'}
                else:
                    return {'status': 'error', 'message': f'XT 롱 포지션 오픈 실패: {response.status_code} - {response.text}'}
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order"
                backpack_order_type = 'Market' if order_type == 'market' else 'Limit'
                backpack_symbol = f"{symbol}_USDC_PERP" if market_type == 'futures' else f"{symbol}_USDC"
                body = {
                    "symbol": backpack_symbol,
                    "side": "Bid",
                    "orderType": backpack_order_type,
                    "quantity": str(round(float(size), 8))
                }
                if backpack_order_type == "Limit":
                    body["timeInForce"] = "GTC"
                if market_type == 'futures' and leverage > 1:
                    body['leverage'] = str(leverage)
                headers = self._get_headers_backpack("orderExecute", body)
                logger.debug(f"Backpack request body: {body}")
                response = requests.post(url, headers=headers, json=body)
                logger.debug(f"Backpack response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'order_id': data.get('orderId'), 'message': 'Backpack 롱 포지션 오픈 성공'}
                else:
                    return {'status': 'error', 'message': f'Backpack 롱 포지션 오픈 실패: {response.status_code} - {response.text}'}
        except Exception as e:
            logger.error(f"Long position error: {str(e)}")
            return {'status': 'error', 'message': f'롱 포지션 오픈 오류: {str(e)}'}

    def open_short_position(self, symbol, size, leverage=1, order_type='market', market_type='futures'):
        """숏 포지션 오픈"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/v4/order"
                params = {
                    'symbol': symbol,
                    'side': 'sell',
                    'type': order_type,
                    'quantity': str(size)
                }
                if market_type == 'futures' and leverage > 1:
                    params['leverage'] = leverage
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                if response.status_code == 200:
                    data = response.json()
                    order_id = data.get('orderId', 'unknown')
                    return {'status': 'success', 'order_id': order_id, 'message': 'XT 숏 포지션 오픈 성공'}
                else:
                    return {'status': 'error', 'message': f'XT 숏 포지션 오픈 실패: {response.status_code} - {response.text}'}
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order"
                backpack_order_type = 'Market' if order_type == 'market' else 'Limit'
                backpack_symbol = f"{symbol}_USDC_PERP" if market_type == 'futures' else f"{symbol}_USDC"
                body = {
                    "symbol": backpack_symbol,
                    "side": "Ask",
                    "orderType": backpack_order_type,
                    "quantity": str(round(float(size), 8))
                }
                if backpack_order_type == "Limit":
                    body["timeInForce"] = "GTC"
                if market_type == 'futures' and leverage > 1:
                    body['leverage'] = str(leverage)
                headers = self._get_headers_backpack("orderExecute", body)
                logger.debug(f"Backpack request body: {body}")
                response = requests.post(url, headers=headers, json=body)
                logger.debug(f"Backpack response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'order_id': data.get('orderId'), 'message': 'Backpack 숏 포지션 오픈 성공'}
                else:
                    return {'status': 'error', 'message': f'Backpack 숏 포지션 오픈 실패: {response.status_code} - {response.text}'}
        except Exception as e:
            logger.error(f"Short position error: {str(e)}")
            return {'status': 'error', 'message': f'숏 포지션 오픈 오류: {str(e)}'}

    def spot_buy(self, symbol, size, order_type='market', price=None):
        """스팟 매수"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/v4/order"
                params = {
                    'symbol': symbol,
                    'side': 'buy',
                    'type': order_type,
                    'quantity': str(size)
                }
                if order_type == 'limit' and price:
                    params['price'] = str(price)
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                if response.status_code == 200:
                    data = response.json()
                    order_id = data.get('orderId', 'unknown')
                    return {'status': 'success', 'order_id': order_id, 'message': 'XT 스팟 매수 성공'}
                else:
                    return {'status': 'error', 'message': f'XT 스팟 매수 실패: {response.status_code} - {response.text}'}
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order"
                backpack_order_type = 'Market' if order_type == 'market' else 'Limit'
                backpack_symbol = f"{symbol}_USDC"
                body = {
                    "symbol": backpack_symbol,
                    "side": "Bid",
                    "orderType": backpack_order_type,
                    "quantity": str(round(float(size), 8))
                }
                if order_type == 'limit' and price:
                    body["price"] = str(round(float(price), 8))
                    body["timeInForce"] = "GTC"
                headers = self._get_headers_backpack("orderExecute", body)
                logger.debug(f"Backpack spot buy request body: {body}")
                response = requests.post(url, headers=headers, json=body)
                logger.debug(f"Backpack spot buy response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'order_id': data.get('orderId'), 'message': 'Backpack 스팟 매수 성공'}
                else:
                    return {'status': 'error', 'message': f'Backpack 스팟 매수 실패: {response.status_code} - {response.text}'}
        except Exception as e:
            logger.error(f"Spot buy error: {str(e)}")
            return {'status': 'error', 'message': f'스팟 매수 오류: {str(e)}'}

    def spot_sell(self, symbol, size, order_type='market', price=None):
        """스팟 매도"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/v4/order"
                params = {
                    'symbol': symbol,
                    'side': 'sell',
                    'type': order_type,
                    'quantity': str(size)
                }
                if order_type == 'limit' and price:
                    params['price'] = str(price)
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                if response.status_code == 200:
                    data = response.json()
                    order_id = data.get('orderId', 'unknown')
                    return {'status': 'success', 'order_id': order_id, 'message': 'XT 스팟 매도 성공'}
                else:
                    return {'status': 'error', 'message': f'XT 스팟 매도 실패: {response.status_code} - {response.text}'}
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order"
                backpack_order_type = 'Market' if order_type == 'market' else 'Limit'
                backpack_symbol = f"{symbol}_USDC"
                body = {
                    "symbol": backpack_symbol,
                    "side": "Ask",
                    "orderType": backpack_order_type,
                    "quantity": str(round(float(size), 8))
                }
                if order_type == 'limit' and price:
                    body["price"] = str(round(float(price), 8))
                    body["timeInForce"] = "GTC"
                headers = self._get_headers_backpack("orderExecute", body)
                logger.debug(f"Backpack spot sell request body: {body}")
                response = requests.post(url, headers=headers, json=body)
                logger.debug(f"Backpack spot sell response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'order_id': data.get('orderId'), 'message': 'Backpack 스팟 매도 성공'}
                else:
                    return {'status': 'error', 'message': f'Backpack 스팟 매도 실패: {response.status_code} - {response.text}'}
        except Exception as e:
            logger.error(f"Spot sell error: {str(e)}")
            return {'status': 'error', 'message': f'스팟 매도 오류: {str(e)}'}

    def get_futures_balance(self):
        """선물 계좌 잔고 조회"""
        try:
            if self.exchange == 'xt':
                if PYXTLIB_AVAILABLE:
                    try:
                        xt_client = XTClient(self.api_key, self.api_secret)
                        if xt_client.futures is None:
                            raise Exception("XTClient futures client initialization failed")
                        balance_result = xt_client.get_futures_balance()
                        if balance_result.get('status') == 'success':
                            return {'status': 'success', 'balance': balance_result.get('balance'), 'message': 'XT 선물 잔고 조회 성공'}
                        else:
                            raise Exception(f"pyxt error: {balance_result.get('message')}")
                    except Exception as e:
                        logger.error(f"pyxt 라이브러리 선물 잔고 조회 실패: {e}")
                url = f"{self.base_url}/v4/account/futures/balance"
                headers = self._get_headers_xt()
                response = requests.get(url, headers=headers)
                logger.debug(f"XT futures balance response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    if data.get('rc') == 0:
                        return {'status': 'success', 'balance': data.get('result', {}), 'message': 'XT 선물 잔고 조회 성공'}
                    else:
                        return {'status': 'error', 'message': f'XT 선물 잔고 조회 실패: {data.get("mc", "Unknown error")}'}
                return {'status': 'error', 'message': f'XT 선물 잔고 조회 실패: {response.status_code} - {response.text}'}
            elif self.exchange == 'backpack':
                url = "https://api.backpack.exchange/api/v1/capital"
                headers = self._get_headers_backpack("balanceQuery")
                response = requests.get(url, headers=headers)
                logger.debug(f"Backpack futures balance response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'balance': data, 'message': 'Backpack 잔고 조회 성공'}
                else:
                    return {'status': 'error', 'message': f'Backpack 잔고 조회 실패: {response.status_code} - {response.text}'}
        except Exception as e:
            logger.error(f"Futures balance error: {str(e)}")
            return {'status': 'error', 'message': f'선물 잔고 조회 오류: {str(e)}'}

    def get_spot_balance(self):
        """스팟 계좌 잔고 조회"""
        try:
            if self.exchange == 'xt':
                if PYXTLIB_AVAILABLE:
                    try:
                        xt_client = XTClient(self.api_key, self.api_secret)
                        if xt_client.spot is None:
                            raise Exception("XTClient spot client initialization failed")
                        balance_result = xt_client.get_spot_balance()
                        if balance_result.get('status') == 'success':
                            return {'status': 'success', 'balance': balance_result.get('balance'), 'message': 'XT 스팟 잔고 조회 성공'}
                        else:
                            raise Exception(f"pyxt error: {balance_result.get('message')}")
                    except Exception as e:
                        logger.error(f"pyxt 라이브러리 스팟 잔고 조회 실패: {e}")
                url = f"{self.spot_base_url}/v4/account/spot/balance"
                headers = self._get_headers_xt()
                response = requests.get(url, headers=headers)
                logger.debug(f"XT spot balance response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    if data.get('rc') == 0:
                        return {'status': 'success', 'balance': data.get('result', {}), 'message': 'XT 스팟 잔고 조회 성공'}
                    else:
                        return {'status': 'error', 'message': f'XT 스팟 잔고 조회 실패: {data.get("mc", "Unknown error")}'}
                return {'status': 'error', 'message': f'XT 스팟 잔고 조회 실패: {response.status_code} - {response.text}'}
            elif self.exchange == 'backpack':
                url = "https://api.backpack.exchange/api/v1/capital"
                headers = self._get_headers_backpack("balanceQuery")
                response = requests.get(url, headers=headers)
                logger.debug(f"Backpack spot balance response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'balance': data, 'message': 'Backpack 스팟 잔고 조회 성공'}
                else:
                    return {'status': 'error', 'message': f'Backpack 스팟 잔고 조회 실패: {response.status_code} - {response.text}'}
        except Exception as e:
            logger.error(f"Spot balance error: {str(e)}")
            return {'status': 'error', 'message': f'스팟 잔고 조회 오류: {str(e)}'}

    def get_market_data(self, symbol, data_type='ticker'):
        """시장 데이터 조회"""
        try:
            if self.exchange == 'xt':
                if data_type == 'ticker':
                    url = f"{self.base_url}/v4/public/ticker/24hr"
                    if symbol:
                        url += f"?symbol={symbol}"
                    response = requests.get(url)
                elif data_type == 'depth':
                    url = f"{self.base_url}/v4/public/depth"
                    params = {'symbol': symbol, 'limit': 10}
                    response = requests.get(url, params=params)
                elif data_type == 'kline':
                    url = f"{self.base_url}/v4/public/kline"
                    params = {'symbol': symbol, 'interval': '1m', 'limit': 10}
                    response = requests.get(url, params=params)
                else:
                    return {'status': 'error', 'message': f'지원하지 않는 데이터 타입: {data_type}'}
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'data': data.get('result', {}), 'message': f'XT {data_type} 데이터 조회 성공'}
                else:
                    return {'status': 'error', 'message': f'XT {data_type} 데이터 조회 실패: {response.status_code}'}
            elif self.exchange == 'backpack':
                if data_type == 'ticker':
                    url = f"{self.base_url}/tickers"
                    if symbol:
                        url += f"?symbol={symbol}_USDC_PERP"
                    response = requests.get(url)
                elif data_type == 'depth':
                    url = f"{self.base_url}/depth"
                    params = {'symbol': f"{symbol}_USDC_PERP", 'limit': 10}
                    response = requests.get(url, params=params)
                elif data_type == 'kline':
                    url = f"{self.base_url}/klines"
                    params = {'symbol': f"{symbol}_USDC_PERP", 'interval': '1m', 'limit': 10}
                    response = requests.get(url, params=params)
                else:
                    return {'status': 'error', 'message': f'지원하지 않는 데이터 타입: {data_type}'}
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'data': data, 'message': f'Backpack {data_type} 데이터 조회 성공'}
                else:
                    return {'status': 'error', 'message': f'Backpack {data_type} 데이터 조회 실패: {response.status_code}'}
        except Exception as e:
            logger.error(f"Market data error: {str(e)}")
            return {'status': 'error', 'message': f'시장 데이터 조회 오류: {str(e)}'}

    def get_spot_market_data(self, symbol, data_type='ticker'):
        """스팟 시장 데이터 조회"""
        try:
            if self.exchange == 'xt':
                if data_type == 'ticker':
                    url = f"{self.spot_base_url}/v4/public/ticker/24hr"
                    if symbol:
                        url += f"?symbol={symbol}"
                    response = requests.get(url)
                elif data_type == 'depth':
                    url = f"{self.spot_base_url}/v4/public/depth"
                    params = {'symbol': symbol, 'limit': 10}
                    response = requests.get(url, params=params)
                elif data_type == 'kline':
                    url = f"{self.spot_base_url}/v4/public/kline"
                    params = {'symbol': symbol, 'interval': '1m', 'limit': 10}
                    response = requests.get(url, params=params)
                else:
                    return {'status': 'error', 'message': f'지원하지 않는 데이터 타입: {data_type}'}
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'data': data.get('result', {}), 'message': f'XT 스팟 {data_type} 데이터 조회 성공'}
                else:
                    return {'status': 'error', 'message': f'XT 스팟 {data_type} 데이터 조회 실패: {response.status_code}'}
            elif self.exchange == 'backpack':
                if data_type == 'ticker':
                    url = f"{self.base_url}/tickers"
                    if symbol:
                        url += f"?symbol={symbol}_USDC"
                    response = requests.get(url)
                elif data_type == 'depth':
                    url = f"{self.base_url}/depth"
                    params = {'symbol': f"{symbol}_USDC", 'limit': 10}
                    response = requests.get(url, params=params)
                elif data_type == 'kline':
                    url = f"{self.base_url}/klines"
                    params = {'symbol': f"{symbol}_USDC", 'interval': '1m', 'limit': 10}
                    response = requests.get(url, params=params)
                else:
                    return {'status': 'error', 'message': f'지원하지 않는 데이터 타입: {data_type}'}
                if response.status_code == 200:
                    data = response.json()
                    return {'status': 'success', 'data': data, 'message': f'Backpack 스팟 {data_type} 데이터 조회 성공'}
                else:
                    return {'status': 'error', 'message': f'Backpack 스팟 {data_type} 데이터 조회 실패: {response.status_code}'}
        except Exception as e:
            logger.error(f"Spot market data error: {str(e)}")
            return {'status': 'error', 'message': f'스팟 시장 데이터 조회 오류: {str(e)}'}

def init_database():
    """사용자 API 키 데이터베이스 초기화"""
    try:
        conn = sqlite3.connect('user_apis.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_api_keys (
                user_id INTEGER PRIMARY KEY,
                xt_api_key TEXT,
                xt_api_secret TEXT,
                backpack_api_key TEXT,
                backpack_private_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_leverage_settings (
                user_id INTEGER,
                exchange TEXT,
                symbol TEXT,
                direction TEXT,
                leverage INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, exchange, symbol, direction)
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

def save_user_api_keys(user_id, exchange, api_key, api_secret):
    """사용자 API 키 저장"""
    conn = sqlite3.connect('user_apis.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_api_keys (
            user_id, 
            xt_api_key, xt_api_secret, 
            backpack_api_key, backpack_private_key,
            updated_at
        )
        SELECT ?, 
               CASE WHEN ? = 'xt' THEN ? ELSE xt_api_key END,
               CASE WHEN ? = 'xt' THEN ? ELSE xt_api_secret END,
               CASE WHEN ? = 'backpack' THEN ? ELSE backpack_api_key END,
               CASE WHEN ? = 'backpack' THEN ? ELSE backpack_private_key END,
               CURRENT_TIMESTAMP
        FROM user_api_keys WHERE user_id = ? OR NOT EXISTS (SELECT 1 FROM user_api_keys WHERE user_id = ?)
    ''', (
        user_id,
        exchange, api_key, exchange, api_secret,
        exchange, api_key, exchange, api_secret,
        user_id, user_id
    ))
    conn.commit()
    conn.close()

def get_user_api_keys(user_id):
    """사용자 API 키 조회"""
    conn = sqlite3.connect('user_apis.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_api_keys WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'xt_api_key': row[1],
            'xt_api_secret': row[2],
            'backpack_api_key': row[3],
            'backpack_private_key': row[4]
        }
    return None

async def show_main_menu(telegram_app, chat_id):
    """메인 메뉴 표시"""
    try:
        keyboard = [
            [InlineKeyboardButton("🔑 API 키 관리", callback_data="api_management")],
            [InlineKeyboardButton("💰 잔고 조회", callback_data="balance_menu")],
            [InlineKeyboardButton("📊 포지션 관리", callback_data="position_menu")],
            [InlineKeyboardButton("🔄 거래하기", callback_data="trade_menu")],
            [InlineKeyboardButton("⚙️ 설정", callback_data="settings_menu")],
            [InlineKeyboardButton("❓ 도움말", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        response_text = (
            "🤖 **암호화폐 선물 거래 봇**\n\n"
            "버튼을 클릭하여 원하는 기능을 선택하세요!\n\n"
            "**지원 거래소:**\n"
            "• XT Exchange\n"
            "• Backpack Exchange\n\n"
            "먼저 API 키를 설정해주세요!"
        )
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=response_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Main menu error: {e}")

async def show_api_management_menu(telegram_app, chat_id, user_id, callback_query=None):
    """API 관리 메뉴 표시"""
    try:
        user_keys = get_user_api_keys(user_id)
        keyboard = [
            [InlineKeyboardButton(f"XT Exchange {'✅ 설정됨' if user_keys and user_keys.get('xt_api_key') else '❌ 미설정'}", callback_data="api_xt")],
            [InlineKeyboardButton(f"Backpack Exchange {'✅ 설정됨' if user_keys and user_keys.get('backpack_api_key') else '❌ 미설정'}", callback_data="api_backpack")],
            [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "🔑 **API 키 관리**\n\n각 거래소의 API 키 상태를 확인하고 설정할 수 있습니다."
        if callback_query:
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"API management menu error: {e}")

async def show_balance_menu(telegram_app, chat_id, user_id, callback_query=None):
    """잔고 조회 메뉴 표시"""
    try:
        keyboard = [
            [InlineKeyboardButton("XT Exchange", callback_data="balance_xt")],
            [InlineKeyboardButton("Backpack Exchange", callback_data="balance_backpack")],
            [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "💰 **잔고 조회**\n\n거래소를 선택하여 잔고를 조회하세요."
        if callback_query:
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Balance menu error: {e}")

async def show_trade_menu(telegram_app, chat_id, user_id, callback_query=None):
    """거래 메뉴 표시"""
    try:
        keyboard = [
            [InlineKeyboardButton("XT Exchange", callback_data="trade_exchange_xt")],
            [InlineKeyboardButton("Backpack Exchange", callback_data="trade_exchange_backpack")],
            [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "🔄 **거래하기**\n\n거래소를 선택하여 거래를 시작하세요."
        if callback_query:
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Trade menu error: {e}")

async def show_position_list_menu(telegram_app, chat_id, user_id, callback_query):
    """포지션 조회 메뉴 표시"""
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data="position_list_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data="position_list_backpack")],
        [InlineKeyboardButton("🔙 포지션 메뉴", callback_data="position_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text="📊 **포지션 조회**\n\n거래소를 선택하여 포지션을 조회하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_position_close_menu(telegram_app, chat_id, user_id, callback_query):
    """포지션 종료 메뉴 표시"""
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data="position_close_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data="position_close_backpack")],
        [InlineKeyboardButton("🔙 포지션 메뉴", callback_data="position_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text="❌ **포지션 종료**\n\n거래소를 선택하여 포지션을 종료하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_position_menu(telegram_app, chat_id, user_id, callback_query):
    """포지션 관리 메뉴 표시"""
    keyboard = [
        [InlineKeyboardButton("📊 포지션 조회", callback_data="position_list")],
        [InlineKeyboardButton("❌ 포지션 종료", callback_data="position_close")],
        [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text="📊 **포지션 관리**\n\n원하는 작업을 선택하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_settings_menu(telegram_app, chat_id, user_id, callback_query):
    """설정 메뉴 표시"""
    keyboard = [
        [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text="⚙️ **설정**\n\n현재 설정 기능은 준비 중입니다.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_help(telegram_app, chat_id, callback_query):
    """도움말 표시"""
    text = (
        "🤖 **암호화폐 선물 거래 봇 도움말**\n\n"
        "**주요 명령어:**\n"
        "• `/start`: 메인 메뉴 표시\n"
        "• `/setapi [거래소] [API_KEY] [SECRET_KEY]`: API 키 설정\n"
        "• `/test`: API 연결 테스트\n"
        "• `/trade [거래소] [심볼] [long/short/buy/sell] [주문타입] [수량] [레버리지/가격]`: 거래 실행\n\n"
        "**지원 거래소:**\n"
        "• XT Exchange\n"
        "• Backpack Exchange\n\n"
        "궁금한 점이 있으면 관리자에게 문의하세요!"
    )
    keyboard = [[InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_api_callback(telegram_app, chat_id, user_id, data, callback_query):
    """API 관련 콜백 처리"""
    try:
        exchange = data.replace("api_", "")
        exchange_names = {
            "xt": "XT Exchange",
            "backpack": "Backpack Exchange"
        }
        
        user_keys = get_user_api_keys(user_id)
        has_api_key = False
        if user_keys:
            if exchange == 'backpack':
                has_api_key = bool(user_keys.get('backpack_api_key') and user_keys.get('backpack_private_key'))
            else:
                has_api_key = bool(user_keys.get(f'{exchange}_api_key') and user_keys.get(f'{exchange}_api_secret'))
        
        if has_api_key:
            keyboard = [
                [InlineKeyboardButton("🔄 API 키 재설정", callback_data=f"api_reset_{exchange}")],
                [InlineKeyboardButton("✅ API 연결 테스트", callback_data=f"api_test_{exchange}")],
                [InlineKeyboardButton("🔙 API 관리", callback_data="api_management")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=f"🔑 **{exchange_names[exchange]} API 설정**\n\n"
                     f"✅ API 키가 이미 설정되어 있습니다.\n\n"
                     f"다음 중 선택하세요:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            setup_instructions = {
                "xt": (
                    f"🔑 **{exchange_names[exchange]} API 설정**\n\n"
                    f"다음 형식으로 API 키를 입력하세요:\n\n"
                    f"`/setapi {exchange} YOUR_API_KEY YOUR_SECRET_KEY`\n\n"
                    f"예시:\n"
                    f"`/setapi {exchange} abc123def456 ghi789jkl012`\n\n"
                    f"📋 **API 키 발급 방법:**\n"
                    f"1. XT Exchange 로그인\n"
                    f"2. API 관리 → 새 API 키 생성\n"
                    f"3. 거래 권한 활성화\n"
                    f"4. API 키와 시크릿 키 복사\n\n"
                    f"⚠️ **주의:** API 키는 안전하게 저장됩니다.\n\n"
                    f"🔙 API 관리로 돌아가려면 /start를 입력하세요."
                ),
                "backpack": (
                    f"🔑 **{exchange_names[exchange]} API 설정**\n\n"
                    f"다음 형식으로 API 키를 입력하세요:\n\n"
                    f"`/setapi {exchange} YOUR_API_KEY YOUR_PRIVATE_KEY`\n\n"
                    f"예시:\n"
                    f"`/setapi {exchange} abc123def456 ghi789jkl012`\n\n"
                    f"📋 **API 키 발급 방법:**\n"
                    f"1. Backpack Exchange 로그인\n"
                    f"2. 설정 → API 키 → 새 키 생성\n"
                    f"3. 거래 권한 활성화\n"
                    f"4. API 키와 개인키 복사\n\n"
                    f"⚠️ **주의:** API 키는 안전하게 저장됩니다.\n\n"
                    f"🔙 API 관리로 돌아가려면 /start를 입력하세요."
                )
            }
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=setup_instructions.get(exchange, f"🔑 **{exchange_names[exchange]} API 설정**\n\nAPI 키 설정 안내가 준비 중입니다."),
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"API callback error: {e}")

async def handle_balance_callback(telegram_app, chat_id, user_id, data, callback_query):
    """잔고 조회 콜백 처리"""
    exchange = data.replace("balance_", "")
    user_keys = get_user_api_keys(user_id)
    if not user_keys or not user_keys.get(f'{exchange}_api_key'):
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"❌ {exchange.upper()} API 키가 설정되지 않았습니다. 먼저 /setapi 명령어로 설정하세요.",
            parse_mode='Markdown'
        )
        return
    api_key = user_keys.get(f'{exchange}_api_key')
    api_secret = user_keys.get(f'{exchange}_api_secret') or user_keys.get(f'{exchange}_private_key')
    trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
    futures_result = trader.get_futures_balance()
    spot_result = trader.get_spot_balance()
    text = f"💰 **{exchange.upper()} 잔고 조회**\n\n"
    if futures_result.get('status') == 'success':
        text += f"**선물 잔고**: {futures_result.get('balance')}\n"
    else:
        text += f"**선물 잔고**: 조회 실패 - {futures_result.get('message')}\n"
    if spot_result.get('status') == 'success':
        text += f"**스팟 잔고**: {spot_result.get('balance')}\n"
    else:
        text += f"**스팟 잔고**: 조회 실패 - {spot_result.get('message')}\n"
    keyboard = [[InlineKeyboardButton("🔙 잔고 메뉴", callback_data="balance_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_trade_setup_menu(telegram_app, chat_id, user_id, trade_type, callback_query):
    """거래 설정 메뉴 표시"""
    keyboard = [
        [InlineKeyboardButton("선물 거래", callback_data=f"trade_type_{trade_type}_xt_futures"),
         InlineKeyboardButton("스팟 거래", callback_data=f"trade_type_{trade_type}_xt_spot")],
        [InlineKeyboardButton("선물 거래", callback_data=f"trade_type_{trade_type}_backpack_futures"),
         InlineKeyboardButton("스팟 거래", callback_data=f"trade_type_{trade_type}_backpack_spot")],
        [InlineKeyboardButton("🔙 거래 메뉴", callback_data="trade_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"🔄 **{trade_type.upper()} 거래 설정**\n\n거래소와 시장 유형을 선택하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_trade_type_menu(telegram_app, chat_id, user_id, trade_type, exchange, callback_query):
    """거래 유형 메뉴 표시"""
    keyboard = [
        [InlineKeyboardButton("선물 거래", callback_data=f"trade_type_{trade_type}_{exchange}_futures"),
         InlineKeyboardButton("스팟 거래", callback_data=f"trade_type_{trade_type}_{exchange}_spot")],
        [InlineKeyboardButton("🔙 거래 메뉴", callback_data="trade_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"🔄 **{trade_type.upper()} 거래 - {exchange.upper()}**\n\n시장 유형을 선택하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_futures_direction_menu(telegram_app, chat_id, user_id, exchange, callback_query):
    """선물 거래 방향 선택 메뉴"""
    keyboard = [
        [InlineKeyboardButton("롱 (Long)", callback_data=f"futures_direction_{exchange}_long"),
         InlineKeyboardButton("숏 (Short)", callback_data=f"futures_direction_{exchange}_short")],
        [InlineKeyboardButton("🔙 거래 메뉴", callback_data="trade_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"🔄 **선물 거래 - {exchange.upper()}**\n\n거래 방향을 선택하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_futures_symbol_menu(telegram_app, chat_id, user_id, exchange, direction, callback_query):
    """선물 거래 심볼 선택 메뉴"""
    symbols = ['BTC', 'ETH', 'XRP', 'SOL']
    keyboard = [
        [InlineKeyboardButton(symbol, callback_data=f"futures_symbol_{exchange}_{direction}_{symbol}")]
        for symbol in symbols
    ]
    keyboard.append([InlineKeyboardButton("🔙 방향 선택", callback_data=f"futures_direction_{exchange}_{direction}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"🔄 **선물 {direction.upper()} 거래 - {exchange.upper()}**\n\n심볼을 선택하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_symbol_selection_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, callback_query):
    """심볼 선택 메뉴"""
    symbols = ['BTC', 'ETH', 'XRP', 'SOL']
    keyboard = [
        [InlineKeyboardButton(symbol, callback_data=f"trade_symbol_{trade_type}_{exchange}_{market_type}_{symbol}")]
        for symbol in symbols
    ]
    keyboard.append([InlineKeyboardButton("🔙 시장 유형", callback_data=f"trade_type_{trade_type}_{exchange}_{market_type}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"🔄 **{trade_type.upper()} 거래 - {exchange.upper()} ({market_type.upper()})**\n\n심볼을 선택하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_order_type_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, callback_query):
    """주문 유형 선택 메뉴"""
    keyboard = [
        [InlineKeyboardButton("시장가 (Market)", callback_data=f"order_type_{trade_type}_{exchange}_{market_type}_{symbol}_market"),
         InlineKeyboardButton("지정가 (Limit)", callback_data=f"order_type_{trade_type}_{exchange}_{market_type}_{symbol}_limit")]
    ]
    keyboard.append([InlineKeyboardButton("🔙 심볼 선택", callback_data=f"trade_symbol_{trade_type}_{exchange}_{market_type}_{symbol}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"🔄 **{trade_type.upper()} 거래 - {exchange.upper()} ({market_type.upper()}) {symbol}**\n\n주문 유형을 선택하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_leverage_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, callback_query):
    """레버리지 선택 메뉴"""
    keyboard = [
        [InlineKeyboardButton(f"{lev}x", callback_data=f"leverage_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}_{lev}")]
        for lev in [1, 5, 10, 20]
    ]
    keyboard.append([InlineKeyboardButton("🔙 주문 유형", callback_data=f"order_type_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"🔄 **{trade_type.upper()} 거래 - {exchange.upper()} ({market_type.upper()}) {symbol} ({order_type.upper()})**\n\n레버리지를 선택하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_quantity_input(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, leverage=1, callback_query=None):
    """수량 입력 요청"""
    context.user_data['trade_info'] = {
        'trade_type': trade_type,
        'exchange': exchange,
        'market_type': market_type,
        'symbol': symbol,
        'order_type': order_type,
        'leverage': leverage
    }
    context.user_data['quantity'] = True
    text = (
        f"🔄 **{trade_type.upper()} 거래 - {exchange.upper()} ({market_type.upper()}) {symbol} ({order_type.upper()})**\n\n"
        f"레버리지: {leverage}x\n"
        f"수량을 입력하세요 (예: 0.001):"
    )
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=text,
            parse_mode='Markdown'
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='Markdown'
        )

async def show_futures_leverage_input(telegram_app, chat_id, user_id, exchange, direction, symbol, callback_query=None):
    """선물 거래 레버리지 입력 요청"""
    context.user_data['trade_info'] = {
        'trade_type': direction,
        'exchange': exchange,
        'market_type': 'futures',
        'symbol': symbol,
        'order_type': 'market'
    }
    context.user_data['leverage'] = True
    text = (
        f"🔄 **선물 {direction.upper()} 거래 - {exchange.upper()} {symbol}**\n\n"
        f"레버리지를 입력하세요 (예: 5):"
    )
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=text,
            parse_mode='Markdown'
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='Markdown'
        )

async def handle_quantity_input(telegram_app, chat_id, user_id, text, context):
    """수량 입력 처리"""
    try:
        size = float(text)
        if size <= 0:
            raise ValueError("수량은 0보다 커야 합니다.")
        trade_info = context.user_data.get('trade_info', {})
        trade_type = trade_info.get('trade_type')
        exchange = trade_info.get('exchange')
        market_type = trade_info.get('market_type')
        symbol = trade_info.get('symbol')
        order_type = trade_info.get('order_type')
        leverage = trade_info.get('leverage', 1)
        
        user_keys = get_user_api_keys(user_id)
        if not user_keys or not user_keys.get(f'{exchange}_api_key'):
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ {exchange.upper()} API 키가 설정되지 않았습니다. 먼저 /setapi 명령어로 설정하세요.",
                parse_mode='Markdown'
            )
            return
        
        api_key = user_keys.get(f'{exchange}_api_key')
        api_secret = user_keys.get(f'{exchange}_api_secret') or user_keys.get(f'{exchange}_private_key')
        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
        
        if market_type == 'spot':
            if trade_type == 'buy':
                result = trader.spot_buy(symbol, size, order_type)
            else:
                result = trader.spot_sell(symbol, size, order_type)
        else:
            if trade_type == 'long':
                result = trader.open_long_position(symbol, size, leverage, order_type, market_type)
            else:
                result = trader.open_short_position(symbol, size, leverage, order_type, market_type)
        
        if result.get('status') == 'success':
            success_message = (
                f"✅ **{trade_type.upper()} {'거래' if market_type == 'spot' else '포지션 오픈'} 성공**\n\n"
                f"거래소: {exchange.upper()}\n"
                f"심볼: {symbol}\n"
                f"수량: {size}\n"
                f"주문 유형: {order_type.upper()}\n"
                f"레버리지: {leverage}x\n"
                f"주문 ID: {result.get('order_id', 'N/A')}"
            )
            await telegram_app.bot.send_message(chat_id=chat_id, text=success_message, parse_mode='Markdown')
        else:
            error_msg = result.get('message', '알 수 없는 오류').replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[').replace(']', '\\]')
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **{'거래' if market_type == 'spot' else '포지션 오픈'} 실패**\n\n오류: {error_msg}",
                parse_mode='Markdown'
            )
        
        context.user_data.pop('quantity', None)
        context.user_data.pop('trade_info', None)
    except ValueError as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ 잘못된 수량 형식입니다: {str(e)}\n\n수량을 다시 입력하세요 (예: 0.001).",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Quantity input error: {e}")
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ 오류 발생: {str(e)}",
            parse_mode='Markdown'
        )

async def handle_leverage_input(telegram_app, chat_id, user_id, text, context):
    """레버리지 입력 처리"""
    try:
        leverage = int(text)
        if leverage <= 0:
            raise ValueError("레버리지는 0보다 커야 합니다.")
        trade_info = context.user_data.get('trade_info', {})
        trade_type = trade_info.get('trade_type')
        exchange = trade_info.get('exchange')
        market_type = trade_info.get('market_type')
        symbol = trade_info.get('symbol')
        order_type = trade_info.get('order_type')
        
        await show_quantity_input(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, leverage)
        context.user_data.pop('leverage', None)
    except ValueError as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ 잘못된 레버리지 형식입니다: {str(e)}\n\n레버리지를 다시 입력하세요 (예: 5).",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Leverage input error: {e}")
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ 오류 발생: {str(e)}",
            parse_mode='Markdown'
        )

async def handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query):
    """거래 콜백 처리"""
    logger.debug(f"Trade callback: {data}")
    try:
        if data == "trade_long":
            await show_trade_setup_menu(telegram_app, chat_id, user_id, "long", callback_query)
        elif data == "trade_short":
            await show_trade_setup_menu(telegram_app, chat_id, user_id, "short", callback_query)
        elif data.startswith("trade_long_") or data.startswith("trade_short_"):
            parts = data.split("_")
            trade_type = parts[1]
            exchange = parts[2]
            await show_trade_type_menu(telegram_app, chat_id, user_id, trade_type, exchange, callback_query)
        elif data.startswith("trade_type_"):
            parts = data.split("_")
            trade_type = parts[2]
            exchange = parts[3]
            market_type = parts[4]
            if market_type == "futures":
                await show_futures_direction_menu(telegram_app, chat_id, user_id, exchange, callback_query)
            else:
                await show_symbol_selection_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, callback_query)
        elif data.startswith("trade_symbol_"):
            parts = data.split("_")
            trade_type = parts[2]
            exchange = parts[3]
            market_type = parts[4]
            symbol = parts[5]
            await show_order_type_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, callback_query)
        elif data.startswith("order_type_"):
            parts = data.split("_")
            trade_type = parts[2]
            exchange = parts[3]
            market_type = parts[4]
            symbol = parts[5]
            order_type = parts[6]
            if market_type == "futures":
                await show_leverage_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, callback_query)
            else:
                await show_quantity_input(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, callback_query=callback_query)
        elif data.startswith("leverage_"):
            parts = data.split("_")
            trade_type = parts[1]
            exchange = parts[2]
            market_type = parts[3]
            symbol = parts[4]
            order_type = parts[5]
            leverage = parts[6]
            await show_quantity_input(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, leverage, callback_query)
        elif data.startswith("futures_direction_"):
            parts = data.split("_")
            exchange = parts[2]
            direction = parts[3]
            await show_futures_symbol_menu(telegram_app, chat_id, user_id, exchange, direction, callback_query)
        elif data.startswith("trade_exchange_"):
            parts = data.split("_")
            exchange = parts[2]
            await show_trade_type_menu(telegram_app, chat_id, user_id, "long", exchange, callback_query)
        elif data.startswith("futures_symbol_"):
            parts = data.split("_")
            exchange = parts[2]
            direction = parts[3]
            symbol = parts[4]
            await show_futures_leverage_input(telegram_app, chat_id, user_id, exchange, direction, symbol, callback_query)
    except Exception as e:
        logger.error(f"Trade callback error: {e}")
        await callback_query.answer("❌ 오류가 발생했습니다.")

async def handle_trade_command(telegram_app, chat_id, user_id, text):
    """거래 명령어 처리"""
    parts = text.split()
    if len(parts) < 5:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법:\n\n"
                 "**스팟 거래**: `/trade [거래소] [심볼] [매수/매도] [주문타입] [수량] [가격]`\n"
                 "예시: `/trade backpack BTC buy market 0.001`\n"
                 "예시: `/trade backpack BTC sell limit 0.001 50000`\n\n"
                 "**선물 거래**: `/trade [거래소] [심볼] [long/short] [주문타입] [수량] [레버리지]`\n"
                 "예시: `/trade backpack BTC long market 0.001 10`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    symbol = parts[2].upper()
    action = parts[3].lower()
    order_type = parts[4].lower()
    
    if action in ['buy', 'sell']:
        market_type = 'spot'
        direction = action
        size = float(parts[5])
        price = float(parts[6]) if order_type == 'limit' and len(parts) > 6 else None
        leverage = 1
    else:
        market_type = 'futures'
        direction = action
        size = float(parts[5])
        price = None
        if len(parts) < 7 or not parts[6].isdigit():
            await show_futures_leverage_input(telegram_app, chat_id, user_id, exchange, direction, symbol, callback_query=None)
            return
        leverage = int(parts[6])
    
    user_keys = get_user_api_keys(user_id)
    has_api_key = False
    if user_keys:
        if exchange == 'backpack':
            has_api_key = bool(user_keys.get('backpack_api_key') and user_keys.get('backpack_private_key'))
        else:
            has_api_key = bool(user_keys.get(f'{exchange}_api_key') and user_keys.get(f'{exchange}_api_secret'))
    
    if not has_api_key:
        exchange_names = {"xt": "XT Exchange", "backpack": "Backpack Exchange"}
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **{exchange_names.get(exchange, exchange.upper())} API 키가 설정되지 않았습니다.**\n\n"
                 f"먼저 API 키를 설정해주세요.\n\n"
                 f"🔑 API 관리로 이동하려면 /start를 입력하세요.",
            parse_mode='Markdown'
        )
        return
    
    try:
        api_key = user_keys.get(f'{exchange}_api_key')
        api_secret = user_keys.get(f'{exchange}_api_secret') or user_keys.get(f'{exchange}_private_key')
        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
        
        if market_type == 'spot':
            if direction == 'buy':
                result = trader.spot_buy(symbol, size, order_type, price)
            elif direction == 'sell':
                result = trader.spot_sell(symbol, size, order_type, price)
            else:
                await telegram_app.bot.send_message(
                    chat_id=chat_id,
                    text="❌ **잘못된 방향**\n\n스팟 거래에서는 'buy' 또는 'sell'이어야 합니다.",
                    parse_mode='Markdown'
                )
                return
        else:
            if direction == 'long':
                result = trader.open_long_position(symbol, size, leverage, order_type, market_type)
            elif direction == 'short':
                result = trader.open_short_position(symbol, size, leverage, order_type, market_type)
            else:
                await telegram_app.bot.send_message(
                    chat_id=chat_id,
                    text="❌ **잘못된 방향**\n\n선물 거래에서는 'long' 또는 'short'이어야 합니다.",
                    parse_mode='Markdown'
                )
                return
        
        if result.get('status') == 'success':
            if market_type == 'spot':
                success_message = f"✅ **{direction.upper()} 거래 성공**\n\n"
                success_message += f"거래소: {exchange.upper()}\n"
                success_message += f"심볼: {symbol}\n"
                success_message += f"수량: {size}\n"
                success_message += f"주문 ID: {result.get('order_id', 'N/A')}"
            else:
                success_message = f"✅ **{direction.upper()} 포지션 오픈 성공**\n\n"
                success_message += f"거래소: {exchange.upper()}\n"
                success_message += f"심볼: {symbol}\n"
                success_message += f"수량: {size}\n"
                success_message += f"레버리지: {leverage}배\n"
                success_message += f"주문 ID: {result.get('order_id', 'N/A')}"
            await telegram_app.bot.send_message(chat_id=chat_id, text=success_message, parse_mode='Markdown')
        else:
            error_msg = result.get('message', '알 수 없는 오류').replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[').replace(']', '\\]')
            error_message = f"❌ **{'거래' if market_type == 'spot' else '포지션 오픈'} 실패**\n\n오류: {error_msg}"
            await telegram_app.bot.send_message(chat_id=chat_id, text=error_message, parse_mode='Markdown')
    except Exception as e:
        await telegram_app.bot.send_message(chat_id=chat_id, text=f"❌ **오류 발생**\n\n{str(e)}", parse_mode='Markdown')

async def handle_position_callback(telegram_app, chat_id, user_id, data, callback_query):
    """포지션 관련 콜백 처리"""
    parts = data.split("_")
    action = parts[0]
    exchange = parts[2]
    text = f"📊 **{exchange.upper()} 포지션 {action.replace('position_', '')}**\n\n현재 구현 중입니다."
    keyboard = [[InlineKeyboardButton("🔙 포지션 메뉴", callback_data="position_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

# Flask 웹훅 엔드포인트
@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    telegram_app.app.process_update(update)
    return '', 200

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    init_database()
    telegram_app = TelegramApp("YOUR_BOT_TOKEN")  # 여기에