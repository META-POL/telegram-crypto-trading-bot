#!/usr/bin/env python3

"""
개선된 텔레그램 암호화폐 선물 거래 봇
사용자 친화적 인터페이스와 API 키 관리 기능 포함
"""

import os
import time
import hmac
import hashlib
import requests
import threading
import base64
import logging
import json
import sqlite3
import asyncio
from datetime import datetime
from flask import Flask, jsonify, request

# 라이브러리 import (지연 로딩으로 변경)
SigningKey = None
ccxt = None

# Telegram 라이브러리 import
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    print("✅ Telegram 라이브러리 로드 성공")
except ImportError as e:
    print(f"⚠️ Telegram 라이브러리 로드 실패: {e}")
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
except Exception as e:
    print(f"⚠️ Telegram 라이브러리 로드 중 오류: {e}")
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None

# pyxt 라이브러리 임포트 시도
try:
    from pyxt.spot import Spot          # 현물
    from pyxt.perp import Perp          # 선물
    PYXTLIB_AVAILABLE = True
    print("✅ pyxt 라이브러리 로드 성공")
except ImportError as e:
    print(f"⚠️ pyxt 라이브러리 로드 실패: {e}")
    print("pip install pyxt로 설치해주세요.")
    PYXTLIB_AVAILABLE = False
    Spot = None
    Perp = None
except Exception as e:
    print(f"⚠️ pyxt 라이브러리 로드 중 오류: {e}")
    PYXTLIB_AVAILABLE = False
    Spot = None
    Perp = None

print("📝 모든 라이브러리는 필요시 로드됩니다")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# XTClient 클래스 (수정된 버전)
class XTClient:
    """현물·선물 통합 래퍼"""
    def __init__(self, api_key, secret_key):
        try:
            if PYXTLIB_AVAILABLE:
                self.spot = Spot(
                    host="https://sapi.xt.com",
                    access_key=api_key,
                    secret_key=secret_key
                )
                self.futures = Perp(
                    host="https://fapi.xt.com",
                    access_key=api_key,
                    secret_key=secret_key
                )
                print(f"✅ XTClient 초기화 성공 - Spot: {type(self.spot)}, Futures: {type(self.futures)}")
            else:
                print("❌ pyxt 라이브러리를 사용할 수 없습니다.")
                self.spot = None
                self.futures = None
        except Exception as e:
            print(f"❌ XTClient 초기화 실패: {e}")
            self.spot = None
            self.futures = None

    def get_spot_balance(self, currency=None):
        """현물 잔고 조회"""
        try:
            if self.spot is None:
                raise Exception("Spot 클라이언트가 초기화되지 않았습니다.")
            
            if currency:
                result = self.spot.balance(currency)
                return {'status': 'success', 'balance': result}
            else:
                try:
                    result = self.spot.balances()
                    return {'status': 'success', 'balance': result}
                except AttributeError:
                    print("⚠️ Spot.balances() 없음, REST API로 직접 호출")
                    return self._fetch_all_spot_balances()
                    
        except Exception as e:
            print(f"❌ Spot balance error: {e}")
            return {'status': 'error', 'message': str(e)}

    def _fetch_all_spot_balances(self):
        """REST API 호출: /v4/balances"""
        try:
            import requests
            import hmac
            import hashlib
            import time
            
            timestamp = str(int(time.time() * 1000))
            path = "/v4/balances"
            header_string = (
                f"validate-algorithms=HmacSHA256"
                f"&validate-appkey={self.spot.access_key}"
                f"&validate-recvwindow=60000"
                f"&validate-timestamp={timestamp}"
            )
            message = f"{header_string}#GET#{path}"
            signature = hmac.new(
                self.spot.secret_key.encode(), message.encode(), hashlib.sha256
            ).hexdigest()
            headers = {
                "validate-algorithms": "HmacSHA256",
                "validate-appkey": self.spot.access_key,
                "validate-recvwindow": "60000",
                "validate-timestamp": timestamp,
                "validate-signature": signature,
                "Content-Type": "application/json"
            }
            response = requests.get(f"https://sapi.xt.com{path}", headers=headers)
            result = response.json()
            return {'status': 'success', 'balance': result}
            
        except Exception as e:
            print(f"❌ REST API spot balance error: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_futures_balance(self):
        """선물 잔고 조회"""
        try:
            if self.futures is None:
                raise Exception("Futures 클라이언트가 초기화되지 않았습니다.")
            
            code, data, err = self.futures.get_account_capital()
            if code == 200 and data.get("returnCode") == 0:
                return {'status': 'success', 'balance': data.get("result", [])}
            
            print(f"❌ 선물 잔고 조회 실패: {err or data}")
            return {'status': 'error', 'message': f"선물 잔고 조회 실패: {err or data}"}
            
        except Exception as e:
            print(f"❌ Futures balance error: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_all_balances(self):
        """통합 잔고 요약"""
        spot = self.get_spot_balance()
        futures = self.get_futures_balance()
        return {"spot": spot, "futures": futures}

    def place_spot_order(self, symbol, side, qty, order_type="MARKET", price=None):
        """현물 주문"""
        try:
            if self.spot is None:
                raise Exception("Spot 클라이언트가 초기화되지 않았습니다.")
            
            params = {"symbol": symbol, "side": side, "type": order_type, "bizType": "SPOT"}
            if order_type == "MARKET":
                key = "quoteQty" if side.upper() == "BUY" else "quantity"
                params[key] = qty
            else:
                params.update(quantity=qty, price=price, timeInForce="GTC")
            
            result = self.spot.place_order(**params)
            return {'status': 'success', 'order': result}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def place_futures_order(self, symbol, side, qty, order_type="MARKET", price=None):
        """선물 주문"""
        try:
            if self.futures is None:
                raise Exception("Futures 클라이언트가 초기화되지 않았습니다.")
            
            params = {"symbol": symbol, "side": side, "type": order_type, "quantity": qty}
            if price:
                params["price"] = price
            
            result = self.futures.place_order(**params)
            return {'status': 'success', 'order': result}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

# ---------- 메서드 확인 유틸리티 ----------
def check_available_methods(obj, name="Object"):
    """객체의 사용 가능한 메서드 확인"""
    methods = [method for method in dir(obj) 
               if callable(getattr(obj, method)) and not method.startswith('_')]
    print(f"\n=== {name} 사용 가능한 메서드 ===")
    for method in methods:
        print(f"- {method}")
    return methods

# Flask 앱 생성
try:
    app = Flask(__name__)
    print("✅ Flask 앱 생성 성공")
except Exception as e:
    print(f"❌ Flask 앱 생성 실패: {e}")
    raise

# 데이터베이스 초기화
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
                hyperliquid_api_key TEXT,
                hyperliquid_api_secret TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 레버리지 설정 테이블 추가
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
        print("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        print(f"⚠️ 데이터베이스 초기화 오류 (무시됨): {e}")

# 데이터베이스 초기화 실행
init_database()

def get_user_api_keys(user_id):
    """사용자 API 키 조회"""
    try:
        conn = sqlite3.connect('user_apis.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_api_keys WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'xt_api_key': result[1],
                'xt_api_secret': result[2],
                'backpack_api_key': result[3],
                'backpack_private_key': result[4],
                'hyperliquid_api_key': result[5],
                'hyperliquid_api_secret': result[6]
            }
        return None
    except Exception as e:
        print(f"⚠️ API 키 조회 오류: {e}")
        return None

def save_user_api_keys(user_id, exchange, api_key, api_secret):
    """사용자 API 키 저장"""
    try:
        conn = sqlite3.connect('user_apis.db')
        cursor = conn.cursor()
        
        # 사용자 존재 여부 확인
        cursor.execute('SELECT user_id FROM user_api_keys WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # 기존 사용자 업데이트
            if exchange == 'xt':
                cursor.execute('''
                    UPDATE user_api_keys 
                    SET xt_api_key = ?, xt_api_secret = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                ''', (api_key, api_secret, user_id))
            elif exchange == 'backpack':
                cursor.execute('''
                    UPDATE user_api_keys 
                    SET backpack_api_key = ?, backpack_private_key = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                ''', (api_key, api_secret, user_id))
            elif exchange == 'hyperliquid':
                cursor.execute('''
                    UPDATE user_api_keys 
                    SET hyperliquid_api_key = ?, hyperliquid_api_secret = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                ''', (api_key, api_secret, user_id))
            
        else:
            # 새 사용자 생성
            if exchange == 'xt':
                cursor.execute('''
                    INSERT INTO user_api_keys (user_id, xt_api_key, xt_api_secret)
                    VALUES (?, ?, ?)
                ''', (user_id, api_key, api_secret))
            elif exchange == 'backpack':
                cursor.execute('''
                    INSERT INTO user_api_keys (user_id, backpack_api_key, backpack_private_key)
                    VALUES (?, ?, ?)
                ''', (user_id, api_key, api_secret))
            elif exchange == 'hyperliquid':
                cursor.execute('''
                    INSERT INTO user_api_keys (user_id, hyperliquid_api_key, hyperliquid_api_secret)
                    VALUES (?, ?, ?)
                ''', (user_id, api_key, api_secret))
            
        
        conn.commit()
        conn.close()
        print(f"✅ API 키 저장 완료: {exchange} for user {user_id}")
    except Exception as e:
        print(f"⚠️ API 키 저장 오류: {e}")

def save_user_leverage_setting(user_id, exchange, symbol, direction, leverage):
    """사용자 레버리지 설정 저장"""
    try:
        conn = sqlite3.connect('user_apis.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_leverage_settings 
            (user_id, exchange, symbol, direction, leverage, updated_at) 
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, exchange, symbol, direction, leverage))
        
        conn.commit()
        conn.close()
        print(f"✅ 레버리지 설정 저장 완료: {exchange} {symbol} {direction} {leverage}x for user {user_id}")
    except Exception as e:
        print(f"⚠️ 레버리지 설정 저장 오류: {e}")

def get_user_leverage_setting(user_id, exchange, symbol, direction):
    """사용자 레버리지 설정 조회"""
    try:
        conn = sqlite3.connect('user_apis.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT leverage FROM user_leverage_settings 
            WHERE user_id = ? AND exchange = ? AND symbol = ? AND direction = ?
        ''', (user_id, exchange, symbol, direction))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        return 1  # 기본값
    except Exception as e:
        print(f"⚠️ 레버리지 설정 조회 오류: {e}")
        return 1  # 기본값

@app.route('/')
def health_check():
    try:
        return jsonify({
            "status": "healthy", 
            "message": "Enhanced Telegram Crypto Futures Trading Bot",
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/health')
def health():
    try:
        # 간단한 헬스체크 - 라이브러리 import 없이 작동
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "message": "Bot is running"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """텔레그램 웹훅 처리"""
    print("📨 웹훅 요청 수신")
    try:
        # 텔레그램 라이브러리 지연 로딩
        try:
            from telegram import Update
            from telegram.ext import ApplicationBuilder
            import asyncio
        except ImportError as e:
            print(f"❌ 텔레그램 라이브러리 로드 실패: {e}")
            return jsonify({"status": "error", "message": "텔레그램 라이브러리 로드 실패"}), 500
        
        # 텔레그램 봇 토큰 (강제로 새로운 토큰 사용)
        token = "8356129181:AAEVDzO9MrFe150TmviHFrt_B19hyBc-Xuo"
        print(f"🔍 사용 중인 봇 토큰: {token}")
        print(f"🔍 토큰 길이: {len(token)}")
        print(f"🔍 토큰 시작: {token[:20]}...")
        
        # 봇 애플리케이션 생성
        telegram_app = ApplicationBuilder().token(token).build()
        
        # 요청 데이터 확인
        data = request.get_json()
        print(f"📨 받은 데이터: {data}")
        
        # 업데이트 처리
        update = Update.de_json(data, telegram_app.bot)
        
        # 콜백 쿼리 처리 (버튼 클릭)
        if update.callback_query:
            # 비동기 함수 실행
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(handle_callback_query(update.callback_query, telegram_app))
                loop.close()
            except Exception as e:
                print(f"❌ 콜백 쿼리 처리 오류: {e}")
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
                        await show_main_menu(telegram_app, chat_id)
                        
                    elif text == '/test':
                        await telegram_app.bot.send_message(chat_id=chat_id, text="✅ 봇이 정상 작동 중입니다!")
                        
                    elif text == '/ping':
                        await telegram_app.bot.send_message(chat_id=chat_id, text="🏓 Pong! 봇이 살아있습니다!")
                        
                    elif text.startswith('/setapi'):
                        await handle_api_setup(telegram_app, chat_id, user_id, text)
                        
                    elif text.startswith('/balance'):
                        await handle_balance_command(telegram_app, chat_id, user_id, text)
                        
                    
                        
                    elif text.startswith('/positions'):
                        await handle_positions_command(telegram_app, chat_id, user_id, text)
                        
                    elif text.startswith('/trade'):
                        await handle_trade_command(telegram_app, chat_id, user_id, text)
                        
                    elif text.startswith('/leverage'):
                        await handle_leverage_command(telegram_app, chat_id, user_id, text)
                        
                    elif text.startswith('/close'):
                        await handle_close_command(telegram_app, chat_id, user_id, text)
                        
                    elif text == '/help':
                        await show_help(telegram_app, chat_id)
                        
                    elif text.startswith('/market'):
                        await handle_market_data_command(telegram_app, chat_id, user_id, text)
                        
                    elif text.startswith('/spotmarket'):
                        await handle_spot_market_data_command(telegram_app, chat_id, user_id, text)
                        
                    else:
                        await telegram_app.bot.send_message(
                            chat_id=chat_id, 
                            text="❓ 알 수 없는 명령어입니다. /start를 입력하여 메뉴를 확인하세요."
                        )
                        
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

async def show_main_menu(telegram_app, chat_id):
    """메인 메뉴 표시"""
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        print(f"🔍 메인 메뉴 표시 시작: chat_id={chat_id}")
        
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
            "• Backpack Exchange\n"
            "• Hyperliquid\n\n"
            "먼저 API 키를 설정해주세요!"
        )

        print(f"🔍 메인 메뉴 메시지 전송: {response_text[:50]}...")
        
        result = await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=response_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        print(f"🔍 메인 메뉴 전송 완료: message_id={result.message_id}")
        
    except ImportError:
        print(f"⚠️ 텔레그램 라이브러리 ImportError")
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text="🤖 **암호화폐 선물 거래 봇**\n\n봇이 정상 작동 중입니다!",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"❌ 메인 메뉴 표시 오류: {e}")
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ 메뉴 표시 중 오류가 발생했습니다: {str(e)}"
        )

async def handle_api_setup(telegram_app, chat_id, user_id, text):
    """API 설정 처리"""
    parts = text.split()
    if len(parts) < 4:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법: /setapi [거래소] [API_KEY] [SECRET_KEY]\n\n"
                 "예시:\n"
                 "`/setapi xt YOUR_API_KEY YOUR_SECRET_KEY`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    api_key = parts[2]
    api_secret = parts[3]
    
    # API 키 저장
    save_user_api_keys(user_id, exchange, api_key, api_secret)
    
    # API 연결 테스트
    try:
        if exchange == 'backpack':
            trader = UnifiedFuturesTrader(exchange, api_key=api_key, private_key=api_secret)
        else:
            trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
        test_result = trader.test_api_connection()
        
        if test_result.get('status') == 'success':
            await telegram_app.bot.send_message(
                chat_id=chat_id, 
                text=f"✅ **{exchange.upper()} API 키 설정 완료!**\n\n"
                     f"API 연결 테스트: ✅ 성공\n"
                     f"이제 {exchange.upper()}의 모든 기능을 사용할 수 있습니다.",
                parse_mode='Markdown'
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id, 
                text=f"⚠️ **{exchange.upper()} API 키 저장됨**\n\n"
                     f"API 연결 테스트: ❌ 실패\n"
                     f"오류: {test_result.get('message')}\n\n"
                     f"API 키를 다시 확인해주세요.",
                parse_mode='Markdown'
            )
    except Exception as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=f"⚠️ **{exchange.upper()} API 키 저장됨**\n\n"
                 f"API 연결 테스트 중 오류 발생: {str(e)}\n\n"
                 f"API 키를 다시 확인해주세요.",
            parse_mode='Markdown'
        )

async def handle_callback_query(callback_query, telegram_app):
    """콜백 쿼리 처리 (버튼 클릭)"""
    try:
        
        chat_id = callback_query.message.chat_id
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        print(f"🔘 사용자 {user_id}가 버튼 클릭: {data}")
        
        if data == "api_management":
            await show_api_management_menu(telegram_app, chat_id, user_id, callback_query)
            
        elif data == "balance_menu":
            await show_balance_menu(telegram_app, chat_id, user_id, callback_query)
            

            
        elif data == "position_menu":
            await show_position_menu(telegram_app, chat_id, user_id, callback_query)
            
        elif data == "trade_menu":
            await show_trade_menu(telegram_app, chat_id, user_id, callback_query)
            
        elif data == "settings_menu":
            await show_settings_menu(telegram_app, chat_id, user_id, callback_query)
            
        elif data == "help":
            await show_help(telegram_app, chat_id, callback_query)
            
        elif data == "main_menu":
            await show_main_menu(telegram_app, chat_id)
            
        elif data.startswith("api_"):
            await handle_api_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("balance_"):
            await handle_balance_callback(telegram_app, chat_id, user_id, data, callback_query)
            

            
        elif data.startswith("position_"):
            await handle_position_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("trade_"):
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("order_type_"):
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("leverage_"):
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("futures_direction_"):
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("trade_exchange_"):
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("futures_symbol_"):
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data in ["position_list", "position_close"]:
            await handle_position_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data in ["trade_long", "trade_short"]:
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
        
        # 콜백 쿼리 응답
        if callback_query:
            await callback_query.answer()
        
    except Exception as e:
        print(f"❌ 콜백 쿼리 처리 오류: {e}")
        if callback_query:
            await callback_query.answer("❌ 오류가 발생했습니다.")

async def handle_api_callback(telegram_app, chat_id, user_id, data, callback_query):
    """API 관련 콜백 처리"""
    
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        return
    
    exchange = data.replace("api_", "")
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange", 
        "hyperliquid": "Hyperliquid"
    }
    
    user_keys = get_user_api_keys(user_id)
    
    # API 키 존재 여부 확인 (더 정확한 체크)
    has_api_key = False
    if user_keys:
        if exchange == 'backpack':
            has_api_key = bool(user_keys.get('backpack_api_key') and user_keys.get('backpack_private_key'))
        else:
            has_api_key = bool(user_keys.get(f'{exchange}_api_key') and user_keys.get(f'{exchange}_api_secret'))
    
    if has_api_key:
        # API 키가 이미 설정된 경우
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
        # API 키가 설정되지 않은 경우 - 거래소별 맞춤 안내
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
            ),
            "hyperliquid": (
                f"🔑 **{exchange_names[exchange]} API 설정**\n\n"
                f"다음 형식으로 지갑 정보를 입력하세요:\n\n"
                f"`/setapi {exchange} YOUR_WALLET_ADDRESS YOUR_PRIVATE_KEY`\n\n"
                f"예시:\n"
                f"`/setapi {exchange} 0x1234...abcd 0x5678...efgh`\n\n"
                f"📋 **설정 방법:**\n"
                f"1. 지갑 주소와 개인키 준비\n"
                f"2. Hyperliquid에서 거래 권한 확인\n"
                f"3. 위 형식으로 입력\n\n"
                f"⚠️ **주의:** 개인키는 안전하게 저장됩니다.\n\n"
                f"🔙 API 관리로 돌아가려면 /start를 입력하세요."
            )
        }
        
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=setup_instructions.get(exchange, f"🔑 **{exchange_names[exchange]} API 설정**\n\nAPI 키 설정 안내가 준비 중입니다."),
            parse_mode='Markdown'
        )

async def handle_balance_callback(telegram_app, chat_id, user_id, data, callback_query):
    """잔고 조회 콜백 처리"""
    exchange = data.replace("balance_", "")
    user_keys = get_user_api_keys(user_id)
    
    # API 키 존재 여부 확인 (더 정확한 체크)
    has_api_key = False
    print(f"🔍 {exchange} API 키 체크 시작...")
    print(f"🔍 user_keys: {user_keys}")
    
    if user_keys:
        if exchange == 'backpack':
            backpack_api_key = user_keys.get('backpack_api_key')
            backpack_private_key = user_keys.get('backpack_private_key')
            has_api_key = bool(backpack_api_key and backpack_private_key)
            print(f"🔍 Backpack API 키: {backpack_api_key[:10] if backpack_api_key else 'None'}...")
            print(f"🔍 Backpack Private 키: {backpack_private_key[:10] if backpack_private_key else 'None'}...")
        else:
            api_key = user_keys.get(f'{exchange}_api_key')
            api_secret = user_keys.get(f'{exchange}_api_secret')
            has_api_key = bool(api_key and api_secret)
            print(f"🔍 {exchange} API 키: {api_key[:10] if api_key else 'None'}...")
            print(f"🔍 {exchange} API Secret: {api_secret[:10] if api_secret else 'None'}...")
    
    print(f"🔍 {exchange} API 키 존재 여부: {has_api_key}")
    
    if not has_api_key:
        exchange_names = {
            "xt": "XT Exchange",
            "backpack": "Backpack Exchange",
            "hyperliquid": "Hyperliquid"
        }
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
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
        
        # 선물 잔고 조회
        futures_result = trader.get_futures_balance()
        
        # 스팟 잔고 조회
        spot_result = trader.get_spot_balance()
        
        # 결과 조합
        formatted_balance = ""
        
        # 선물 잔고 처리
        if futures_result.get('status') == 'success':
            futures_data = futures_result.get('balance', {})
            
            if exchange == 'backpack':
                # Backpack 잔고 포맷팅
                if isinstance(futures_data, dict):
                    formatted_balance += "📊 **Backpack 잔고**\n\n"
                    
                    # 실제 Backpack 가격 가져오기
                    prices = trader._get_backpack_prices()
                    
                    # 주요 자산만 필터링 (0이 아닌 잔고만)
                    significant_assets = []
                    total_usd_value = 0
                    
                    for currency, balance_info in futures_data.items():
                        if isinstance(balance_info, dict):
                            available = float(balance_info.get('available', 0))
                            if available > 0:
                                # 실제 가격으로 USD 가치 계산
                                usd_value = 0
                                if currency == 'USDT' or currency == 'USDC':
                                    usd_value = available
                                elif currency in prices:
                                    usd_value = available * prices[currency]
                                else:
                                    # 가격 정보가 없는 경우 0으로 표시
                                    usd_value = 0
                                
                                significant_assets.append((currency, available, usd_value))
                                total_usd_value += usd_value
                    
                    # 잔고가 많은 순으로 정렬
                    significant_assets.sort(key=lambda x: x[2], reverse=True)
                    
                    if significant_assets:
                        for currency, available, usd_value in significant_assets:
                            if usd_value > 0:
                                formatted_balance += f"• **{currency}**: {available:,.8f} (${usd_value:,.2f})\n"
                            else:
                                formatted_balance += f"• **{currency}**: {available:,.8f}\n"
                        
                        formatted_balance += f"\n💰 **총 USD 가치**: ${total_usd_value:,.2f}"
                    else:
                        formatted_balance += "• 잔고가 없습니다.\n"
                else:
                    formatted_balance += f"📊 **선물 잔고**: {futures_data}\n\n"
            else:
                # XT 등 다른 거래소 처리
                if isinstance(futures_data, tuple) and len(futures_data) >= 2:
                    # pyxt 응답 형식: (status_code, data, None)
                    futures_info = futures_data[1]
                    if isinstance(futures_info, dict) and futures_info.get('result') == []:
                        formatted_balance += "📊 **선물 잔고**: 0 USDT (거래 없음)\n\n"
                    else:
                        formatted_balance += f"📊 **선물 잔고**: {futures_info}\n\n"
                else:
                    formatted_balance += f"📊 **선물 잔고**: {futures_data}\n\n"
        else:
            formatted_balance += f"📊 **선물 잔고**: 조회 실패 - {futures_result.get('message', '알 수 없는 오류')}\n\n"
        
        # 스팟 잔고 처리
        if spot_result.get('status') == 'success':
            spot_data = spot_result.get('balance', {})
            
            if isinstance(spot_data, dict):
                if 'totalUsdtAmount' in spot_data:
                    # 전체 잔고 응답 (balances() 메서드)
                    total_usdt = spot_data.get('totalUsdtAmount', '0')
                    formatted_balance += f"💰 **스팟 잔고**: {total_usdt} USDT\n"
                    
                    # 주요 자산만 표시
                    for asset in spot_data.get('assets', []):
                        currency = asset.get('currency', '').upper()
                        available = float(asset.get('availableAmount', 0))
                        if available > 0 and currency in ['USDT', 'USDC', 'BTC', 'ETH', 'SOL']:
                            formatted_balance += f"  - {currency}: {available}\n"
                elif 'availableAmount' in spot_data:
                    # 단일 통화 응답
                    available = float(spot_data.get('availableAmount', 0))
                    currency = spot_data.get('currency', 'USDT')
                    formatted_balance += f"💰 **스팟 잔고**: {available} {currency.upper()}\n"
                else:
                    formatted_balance += f"💰 **스팟 잔고**: {spot_data}\n"
            else:
                formatted_balance += f"💰 **스팟 잔고**: {spot_data}\n"
        else:
            formatted_balance += f"💰 **스팟 잔고**: 조회 실패 - {spot_result.get('message', '알 수 없는 오류')}\n"
        
        # InlineKeyboardButton이 사용 가능한지 확인
        if InlineKeyboardButton is None or InlineKeyboardMarkup is None:
            print("❌ InlineKeyboardButton 또는 InlineKeyboardMarkup이 사용할 수 없습니다.")
            reply_markup = None
        else:
            keyboard = [
                [InlineKeyboardButton("🔄 새로고침", callback_data=data)],
                [InlineKeyboardButton("🔙 잔고 메뉴", callback_data="balance_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"💰 **{exchange.upper()} 잔고**\n\n{formatted_balance}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ 잔고 조회 오류: {e}")
        print(f"❌ 오류 상세: {error_details}")
        
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"❌ **오류 발생**\n\n오류: {str(e)}\n\n관리자에게 문의해주세요.",
            parse_mode='Markdown'
        )



async def handle_position_callback(telegram_app, chat_id, user_id, data, callback_query):
    """포지션 관리 콜백 처리"""
    if data == "position_list":
        await show_position_list_menu(telegram_app, chat_id, user_id, callback_query)
    elif data == "position_close":
        await show_position_close_menu(telegram_app, chat_id, user_id, callback_query)

async def show_position_list_menu(telegram_app, chat_id, user_id, callback_query):
    """포지션 조회 메뉴 표시"""
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data="position_list_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data="position_list_backpack")],
        [InlineKeyboardButton("Hyperliquid", callback_data="position_list_hyperliquid")],
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
        [InlineKeyboardButton("Hyperliquid", callback_data="position_close_hyperliquid")],
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

async def handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query):
    """거래 콜백 처리"""
    print(f"🔘 거래 콜백 처리: {data}")
    
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        await callback_query.answer("❌ 오류가 발생했습니다.")
        return
    
    if data == "trade_long":
        await show_trade_setup_menu(telegram_app, chat_id, user_id, "long", callback_query)
    elif data == "trade_short":
        await show_trade_setup_menu(telegram_app, chat_id, user_id, "short", callback_query)
    elif data.startswith("trade_long_") or data.startswith("trade_short_"):
        # 거래소 선택 후 처리
        parts = data.split("_")
        trade_type = parts[1]  # long 또는 short
        exchange = parts[2]    # xt, backpack, hyperliquid
        await show_trade_type_menu(telegram_app, chat_id, user_id, trade_type, exchange, callback_query)
    elif data.startswith("trade_type_"):
        # 거래 타입 선택 후 처리 (스팟/선물)
        parts = data.split("_")
        trade_type = parts[2]  # long 또는 short
        exchange = parts[3]    # 거래소
        market_type = parts[4] # spot 또는 futures
        
        if market_type == "futures":
            # 선물 거래의 경우 롱/숏 선택 메뉴 표시
            await show_futures_direction_menu(telegram_app, chat_id, user_id, exchange, callback_query)
        else:
            # 스팟 거래의 경우 심볼 선택
            await show_symbol_selection_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, callback_query)
    elif data.startswith("trade_symbol_"):
        # 심볼 선택 후 처리
        parts = data.split("_")
        trade_type = parts[2]  # long 또는 short
        exchange = parts[3]    # 거래소
        market_type = parts[4] # spot 또는 futures
        symbol = parts[5]      # 심볼
        await show_order_type_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, callback_query)
    elif data.startswith("order_type_"):
        # 주문 타입 선택 후 처리
        print(f"🔘 주문 타입 콜백 처리: {data}")
        parts = data.split("_")
        trade_type = parts[2]  # long 또는 short
        exchange = parts[3]    # 거래소
        market_type = parts[4] # spot 또는 futures
        symbol = parts[5]      # 심볼
        order_type = parts[6]  # market 또는 limit
        
        print(f"🔘 파싱된 데이터: trade_type={trade_type}, exchange={exchange}, market_type={market_type}, symbol={symbol}, order_type={order_type}")
        
        if market_type == "futures":
            # 선물 거래의 경우 레버리지 선택
            print(f"🔘 선물 거래 - 레버리지 메뉴 표시")
            await show_leverage_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, callback_query)
        else:
            # 스팟 거래의 경우 바로 수량 입력
            print(f"🔘 스팟 거래 - 수량 입력 메뉴 표시")
            await show_quantity_input(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, callback_query=callback_query)
    elif data.startswith("leverage_"):
        # 레버리지 선택 후 처리 (선물 거래)
        parts = data.split("_")
        trade_type = parts[1]  # long 또는 short
        exchange = parts[2]    # 거래소
        market_type = parts[3] # futures
        symbol = parts[4]      # 심볼
        order_type = parts[5]  # market 또는 limit
        leverage = parts[6]    # 레버리지
        await show_quantity_input(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, leverage, callback_query)
    elif data.startswith("futures_direction_"):
        # 선물 거래 방향 선택 후 처리
        parts = data.split("_")
        exchange = parts[2]     # 거래소
        direction = parts[3]    # long 또는 short
        await show_futures_symbol_menu(telegram_app, chat_id, user_id, exchange, direction, callback_query)
    elif data.startswith("trade_exchange_"):
        # 거래소 선택 후 처리
        parts = data.split("_")
        exchange = parts[2]     # xt, backpack, hyperliquid
        await show_trade_type_menu(telegram_app, chat_id, user_id, "long", exchange, callback_query)
    elif data.startswith("futures_symbol_"):
        # 선물 거래 심볼 선택 후 처리
        parts = data.split("_")
        exchange = parts[2]     # 거래소
        direction = parts[3]    # long 또는 short
        symbol = parts[4]       # 심볼
        await show_futures_leverage_input(telegram_app, chat_id, user_id, exchange, direction, symbol, callback_query)

async def show_trade_setup_menu(telegram_app, chat_id, user_id, trade_type, callback_query):
    """거래 설정 메뉴 표시"""
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        await callback_query.answer("❌ 오류가 발생했습니다.")
        return
    
    trade_type_text = "📈 롱" if trade_type == "long" else "📉 숏"
    
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data=f"trade_{trade_type}_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data=f"trade_{trade_type}_backpack")],
        [InlineKeyboardButton("Hyperliquid", callback_data=f"trade_{trade_type}_hyperliquid")],
        [InlineKeyboardButton("🔙 거래 메뉴", callback_data="trade_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"{trade_type_text} **포지션 오픈**\n\n거래소를 선택하여 {trade_type_text.lower()} 포지션을 오픈하세요.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_trade_type_menu(telegram_app, chat_id, user_id, trade_type, exchange, callback_query):
    """거래 타입 선택 메뉴 (스팟/선물)"""
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        await callback_query.answer("❌ 오류가 발생했습니다.")
        return
    
    trade_type_text = "📈 롱" if trade_type == "long" else "📉 숏"
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid"
    }
    
    keyboard = [
        [InlineKeyboardButton("💱 스팟 거래", callback_data=f"trade_type_{trade_type}_{exchange}_spot")],
        [InlineKeyboardButton("📊 선물 거래", callback_data=f"trade_type_{trade_type}_{exchange}_futures")],
        [InlineKeyboardButton("🔙 거래소 선택", callback_data=f"trade_{trade_type}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"{trade_type_text} **거래 타입 선택**\n\n"
             f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
             f"거래 타입을 선택하세요:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_symbol_selection_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, callback_query):
    """심볼 선택 메뉴"""
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        await callback_query.answer("❌ 오류가 발생했습니다.")
        return
    
    if market_type == "spot":
        trade_type_text = "📈 매수" if trade_type == "long" else "📉 매도"
    else:
        trade_type_text = "📈 롱" if trade_type == "long" else "📉 숏"
    market_type_text = "💱 스팟" if market_type == "spot" else "📊 선물"
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid"
    }
    
    # XT Exchange인 경우 직접 입력 안내
    if exchange == "xt":
        keyboard = [
            [InlineKeyboardButton("📝 직접 입력", callback_data=f"trade_symbol_input_{trade_type}_{exchange}_{market_type}")],
            [InlineKeyboardButton("🔙 거래 타입 선택", callback_data=f"trade_{trade_type}_{exchange}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"{trade_type_text} **심볼 입력**\n\n"
                 f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
                 f"거래 타입: {market_type_text}\n\n"
                 f"XT Exchange는 거래 가능한 심볼이 많아서 직접 입력해주세요.\n\n"
                 f"**입력 형식**:\n"
                 f"**시장가**: `/trade {exchange} [심볼] {'buy' if trade_type == 'long' else 'sell'} market [수량]`\n"
                 f"**지정가**: `/trade {exchange} [심볼] {'buy' if trade_type == 'long' else 'sell'} limit [수량] [가격]`\n\n"
                 f"**예시**:\n"
                 f"`/trade xt BTCUSDT buy market 0.001`\n"
                 f"`/trade xt ETHUSDT buy limit 0.01 2000`\n"
                 f"`/trade xt CTSI sell market 100`\n\n"
                 f"**주의**: `market`을 정확히 입력해주세요 (martket 아님)",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # 다른 거래소들은 기존 심볼 목록 제공
    common_symbols = [
        ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
        ["ADA/USDT", "DOT/USDT", "LINK/USDT"],
        ["SOL/USDT", "MATIC/USDT", "AVAX/USDT"],
        ["XRP/USDT", "LTC/USDT", "BCH/USDT"],
        ["UNI/USDT", "ATOM/USDT", "FTM/USDT"],
        ["NEAR/USDT", "ALGO/USDT", "VET/USDT"],
        ["ICP/USDT", "FIL/USDT", "TRX/USDT"],
        ["ETC/USDT", "XLM/USDT", "HBAR/USDT"],
        ["MANA/USDT", "SAND/USDT", "AXS/USDT"],
        ["GALA/USDT", "CHZ/USDT", "ENJ/USDT"]
    ]
    
    keyboard = []
    for row in common_symbols:
        keyboard_row = []
        for symbol in row:
            keyboard_row.append(InlineKeyboardButton(
                symbol, 
                callback_data=f"trade_symbol_{trade_type}_{exchange}_{market_type}_{symbol.replace('/', '_')}"
            ))
        keyboard.append(keyboard_row)
    
    keyboard.append([InlineKeyboardButton("🔙 거래 타입 선택", callback_data=f"trade_{trade_type}_{exchange}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"{trade_type_text} **심볼 선택**\n\n"
             f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
             f"거래 타입: {market_type_text}\n\n"
             f"거래할 심볼을 선택하세요:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_futures_direction_menu(telegram_app, chat_id, user_id, exchange, callback_query):
    """선물 거래 방향 선택 메뉴 (롱/숏)"""
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        await callback_query.answer("❌ 오류가 발생했습니다.")
        return
    
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid"
    }
    
    keyboard = [
        [InlineKeyboardButton("📈 롱 포지션", callback_data=f"futures_direction_{exchange}_long")],
        [InlineKeyboardButton("📉 숏 포지션", callback_data=f"futures_direction_{exchange}_short")],
        [InlineKeyboardButton("🔙 거래 타입 선택", callback_data=f"trade_long_{exchange}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"📊 **선물 거래 방향 선택**\n\n"
             f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
             f"거래 타입: 📊 선물\n\n"
             f"거래 방향을 선택하세요:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_futures_symbol_menu(telegram_app, chat_id, user_id, exchange, direction, callback_query):
    """선물 거래 심볼 선택 메뉴"""
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        await callback_query.answer("❌ 오류가 발생했습니다.")
        return
    
    direction_text = "📈 롱" if direction == "long" else "📉 숏"
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid"
    }
    
    # XT Exchange인 경우 직접 입력 안내
    if exchange == "xt":
        keyboard = [
            [InlineKeyboardButton("📝 직접 입력", callback_data=f"futures_symbol_input_{exchange}_{direction}")],
            [InlineKeyboardButton("🔙 방향 선택", callback_data=f"futures_direction_{exchange}_{direction}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"{direction_text} **선물 심볼 입력**\n\n"
                 f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
                 f"거래 타입: 📊 선물\n\n"
                 f"XT Exchange는 거래 가능한 심볼이 많아서 직접 입력해주세요.\n\n"
                 f"**입력 형식**:\n"
                 f"`/trade {exchange} [심볼] {direction} [주문타입] [수량] futures`\n\n"
                 f"**예시**:\n"
                 f"`/trade xt BTCUSDT long market 0.001 futures`\n"
                 f"`/trade xt ETHUSDT short limit 0.01 2000 futures`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # 다른 거래소들은 기존 심볼 목록 제공
    futures_symbols = [
        ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
        ["ADA/USDT", "DOT/USDT", "LINK/USDT"],
        ["SOL/USDT", "MATIC/USDT", "AVAX/USDT"],
        ["XRP/USDT", "LTC/USDT", "BCH/USDT"],
        ["UNI/USDT", "ATOM/USDT", "FTM/USDT"]
    ]
    
    keyboard = []
    for row in futures_symbols:
        keyboard_row = []
        for symbol in row:
            keyboard_row.append(InlineKeyboardButton(
                symbol, 
                callback_data=f"futures_symbol_{exchange}_{direction}_{symbol.replace('/', '_')}"
            ))
        keyboard.append(keyboard_row)
    
    keyboard.append([InlineKeyboardButton("🔙 방향 선택", callback_data=f"futures_direction_{exchange}_{direction}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"{direction_text} **선물 심볼 선택**\n\n"
             f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
             f"거래 타입: 📊 선물\n\n"
             f"거래할 심볼을 선택하세요:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_futures_leverage_input(telegram_app, chat_id, user_id, exchange, direction, symbol, callback_query):
    """선물 거래 레버리지 입력 안내"""
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        await callback_query.answer("❌ 오류가 발생했습니다.")
        return
    
    direction_text = "📈 롱" if direction == "long" else "📉 숏"
    symbol_display = symbol.replace('_', '/')
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid"
    }
    
    keyboard = [
        [InlineKeyboardButton("🔙 심볼 선택", callback_data=f"futures_symbol_{exchange}_{direction}_{symbol}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"{direction_text} **레버리지 입력**\n\n"
             f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
             f"심볼: {symbol_display}\n"
             f"거래 타입: 📊 선물\n\n"
             f"다음 형식으로 레버리지를 입력하세요:\n\n"
             f"`/leverage {exchange} {symbol_display} {direction} [레버리지]`\n\n"
             f"예시:\n"
             f"`/leverage {exchange} {symbol_display} {direction} 10`",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_futures_quantity_input(telegram_app, chat_id, user_id, exchange, direction, symbol, leverage, callback_query):
    """선물 거래 수량 입력 안내"""
    direction_text = "📈 롱" if direction == "long" else "📉 숏"
    symbol_display = symbol.replace('_', '/')
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid"
    }
    
    keyboard = [
        [InlineKeyboardButton("🔙 레버리지 입력", callback_data=f"futures_symbol_{exchange}_{direction}_{symbol}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"{direction_text} **수량 입력**\n\n"
                 f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
                 f"심볼: {symbol_display}\n"
                 f"레버리지: {leverage}x\n"
                 f"거래 타입: 📊 선물\n\n"
                 f"다음 형식으로 수량을 입력하세요:\n\n"
                 f"`/trade {exchange} {symbol_display} {direction} market [수량]`\n\n"
                 f"예시:\n"
                 f"`/trade {exchange} {symbol_display} {direction} market 0.001`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"{direction_text} **수량 입력**\n\n"
                 f"거래소: {exchange_names.get(exchange, exchange.upper())}\n"
                 f"심볼: {symbol_display}\n"
                 f"레버리지: {leverage}x\n"
                 f"거래 타입: 📊 선물\n\n"
                 f"다음 형식으로 수량을 입력하세요:\n\n"
                 f"`/trade {exchange} {symbol_display} {direction} market [수량]`\n\n"
                 f"예시:\n"
                 f"`/trade {exchange} {symbol_display} {direction} market 0.001`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def show_order_type_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, callback_query):
    """주문 타입 선택 메뉴 (시장가/지정가)"""
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        await callback_query.answer("❌ 오류가 발생했습니다.")
        return
    
    if market_type == "spot":
        trade_type_text = "📈 매수" if trade_type == "long" else "📉 매도"
    else:
        trade_type_text = "📈 롱" if trade_type == "long" else "📉 숏"
    market_type_text = "💱 스팟" if market_type == "spot" else "📊 선물"
    symbol_display = symbol.replace('_', '/')
    
    keyboard = [
        [InlineKeyboardButton("⚡ 시장가", callback_data=f"order_type_{trade_type}_{exchange}_{market_type}_{symbol}_market")],
        [InlineKeyboardButton("📝 지정가", callback_data=f"order_type_{trade_type}_{exchange}_{market_type}_{symbol}_limit")],
        [InlineKeyboardButton("🔙 심볼 선택", callback_data=f"trade_type_{trade_type}_{exchange}_{market_type}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"{trade_type_text} **주문 타입 선택**\n\n"
             f"심볼: {symbol_display}\n"
             f"거래 타입: {market_type_text}\n\n"
             f"주문 타입을 선택하세요:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_leverage_menu(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, callback_query):
    """레버리지 선택 메뉴 (선물 거래용)"""
    if market_type == "spot":
        trade_type_text = "📈 매수" if trade_type == "long" else "📉 매도"
    else:
        trade_type_text = "📈 롱" if trade_type == "long" else "📉 숏"
    symbol_display = symbol.replace('_', '/')
    order_type_text = "⚡ 시장가" if order_type == "market" else "📝 지정가"
    
    # 일반적인 레버리지 옵션들
    leverage_options = [
        [InlineKeyboardButton("1x", callback_data=f"leverage_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}_1")],
        [InlineKeyboardButton("2x", callback_data=f"leverage_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}_2")],
        [InlineKeyboardButton("5x", callback_data=f"leverage_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}_5")],
        [InlineKeyboardButton("10x", callback_data=f"leverage_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}_10")],
        [InlineKeyboardButton("20x", callback_data=f"leverage_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}_20")],
        [InlineKeyboardButton("50x", callback_data=f"leverage_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}_50")],
        [InlineKeyboardButton("100x", callback_data=f"leverage_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}_100")],
        [InlineKeyboardButton("🔙 주문 타입 선택", callback_data=f"trade_symbol_{trade_type}_{exchange}_{market_type}_{symbol}")]
    ]
    reply_markup = InlineKeyboardMarkup(leverage_options)
    
    await telegram_app.bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        text=f"{trade_type_text} **레버리지 선택**\n\n"
             f"심볼: {symbol_display}\n"
             f"주문 타입: {order_type_text}\n\n"
             f"레버리지를 선택하세요:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_quantity_input(telegram_app, chat_id, user_id, trade_type, exchange, market_type, symbol, order_type, leverage=None, callback_query=None):
    """수량 입력 안내"""
    if market_type == "spot":
        trade_type_text = "📈 매수" if trade_type == "long" else "📉 매도"
    else:
        trade_type_text = "📈 롱" if trade_type == "long" else "📉 숏"
    market_type_text = "💱 스팟" if market_type == "spot" else "📊 선물"
    symbol_display = symbol.replace('_', '/')
    order_type_text = "⚡ 시장가" if order_type == "market" else "📝 지정가"
    
    if market_type == "futures" and leverage:
        leverage_text = f"\n레버리지: {leverage}x"
    else:
        leverage_text = ""
    
    # 거래 정보를 임시 저장 (실제로는 데이터베이스나 세션에 저장)
    trade_info = {
        'trade_type': trade_type,
        'exchange': exchange,
        'market_type': market_type,
        'symbol': symbol,
        'order_type': order_type,
        'leverage': leverage
    }
    
    # 실제 구현에서는 이 정보를 사용자별로 저장해야 함
    print(f"🔘 거래 정보 저장: {trade_info}")
    
    keyboard = [
        [InlineKeyboardButton("🔙 이전 단계", callback_data=f"order_type_{trade_type}_{exchange}_{market_type}_{symbol}_{order_type}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        # 스팟 거래와 선물 거래에 따른 명령어 형식 결정
        if market_type == 'spot':
            # 스팟 거래에서는 long -> buy, short -> sell로 변환
            spot_action = "buy" if trade_type == "long" else "sell"
            command_format = f"`/trade {exchange} {symbol_display} {spot_action} {order_type} [수량]"
            if order_type == 'limit':
                command_format += " [가격]"
            command_format += "`"
            
            example = f"`/trade {exchange} {symbol_display} {spot_action} {order_type} 0.001"
            if order_type == 'limit':
                example += " 50000"
            example += "`"
        else:
            command_format = f"`/trade {exchange} {symbol_display} {trade_type} {order_type} [수량] futures`"
            example = f"`/trade {exchange} {symbol_display} {trade_type} {order_type} 0.001 futures`"
        
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"{trade_type_text} **수량 입력**\n\n"
                 f"심볼: {symbol_display}\n"
                 f"거래 타입: {market_type_text}\n"
                 f"주문 타입: {order_type_text}{leverage_text}\n\n"
                 f"다음 형식으로 수량을 입력하세요:\n\n"
                 f"{'**스팟 거래**:' if market_type == 'spot' else '**선물 거래**:'}\n"
                 f"{command_format}\n\n"
                 f"예시:\n"
                 f"{example}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        # 스팟 거래와 선물 거래에 따른 명령어 형식 결정
        if market_type == 'spot':
            # 스팟 거래에서는 long -> buy, short -> sell로 변환
            spot_action = "buy" if trade_type == "long" else "sell"
            command_format = f"`/trade {exchange} {symbol_display} {spot_action} {order_type} [수량]"
            if order_type == 'limit':
                command_format += " [가격]"
            command_format += "`"
            
            example = f"`/trade {exchange} {symbol_display} {spot_action} {order_type} 0.001"
            if order_type == 'limit':
                example += " 50000"
            example += "`"
        else:
            command_format = f"`/trade {exchange} {symbol_display} {trade_type} {order_type} [수량] futures`"
            example = f"`/trade {exchange} {symbol_display} {trade_type} {order_type} 0.001 futures`"
        
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"{trade_type_text} **수량 입력**\n\n"
                 f"심볼: {symbol_display}\n"
                 f"거래 타입: {market_type_text}\n"
                 f"주문 타입: {order_type_text}{leverage_text}\n\n"
                 f"다음 형식으로 수량을 입력하세요:\n\n"
                 f"{'**스팟 거래**:' if market_type == 'spot' else '**선물 거래**:'}\n"
                 f"{command_format}\n\n"
                 f"예시:\n"
                 f"{example}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def handle_balance_command(telegram_app, chat_id, user_id, text):
    """잔고 조회 명령어 처리"""
    parts = text.split()
    if len(parts) < 2:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법: /balance [거래소]\n\n예시: `/balance xt`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    user_keys = get_user_api_keys(user_id)
    
    if not user_keys or not user_keys.get(f'{exchange}_api_key'):
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **{exchange.upper()} API 키가 설정되지 않았습니다.**\n\n"
                 f"먼저 API 키를 설정해주세요.\n\n"
                 f"🔑 API 관리로 이동하려면 /start를 입력하세요.",
            parse_mode='Markdown'
        )
        return
    
    try:
        api_key = user_keys.get(f'{exchange}_api_key')
        api_secret = user_keys.get(f'{exchange}_api_secret') or user_keys.get(f'{exchange}_private_key')
        
        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
        result = trader.get_futures_balance()
        
        if result.get('status') == 'success':
            balance_data = result.get('balance', {})
            
            # 잔고 데이터를 보기 좋게 포맷팅
            if isinstance(balance_data, dict):
                formatted_balance = ""
                total_balance = 0
                
                for currency, amount in balance_data.items():
                    if isinstance(amount, dict) and 'available' in amount:
                        available = float(amount.get('available', 0))
                        if available > 0:
                            formatted_balance += f"💰 **{currency}**: {available:,.8f}\n"
                            total_balance += 1
                    elif isinstance(amount, (int, float)) and float(amount) > 0:
                        formatted_balance += f"💰 **{currency}**: {float(amount):,.8f}\n"
                        total_balance += 1
                
                if not formatted_balance:
                    formatted_balance = "💡 사용 가능한 잔고가 없습니다."
                else:
                    formatted_balance = f"📊 **총 {total_balance}개 자산**\n\n{formatted_balance}"
            else:
                formatted_balance = f"📊 **잔고 정보**\n\n{str(balance_data)}"
            
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"💰 **{exchange.upper()} 잔고**\n\n{formatted_balance}",
                parse_mode='Markdown'
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **잔고 조회 실패**\n\n오류: {result.get('message', '알 수 없는 오류')}",
                parse_mode='Markdown'
            )
    except Exception as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
            parse_mode='Markdown'
        )



async def handle_positions_command(telegram_app, chat_id, user_id, text):
    """포지션 조회 명령어 처리"""
    parts = text.split()
    if len(parts) < 2:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법: /positions [거래소]\n\n예시: `/positions xt`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    user_keys = get_user_api_keys(user_id)
    
    # API 키 존재 여부 확인 (더 정확한 체크)
    has_api_key = False
    if user_keys:
        if exchange == 'backpack':
            has_api_key = bool(user_keys.get('backpack_api_key') and user_keys.get('backpack_private_key'))
        else:
            has_api_key = bool(user_keys.get(f'{exchange}_api_key') and user_keys.get(f'{exchange}_api_secret'))
    
    if not has_api_key:
        exchange_names = {
            "xt": "XT Exchange",
            "backpack": "Backpack Exchange",
            "hyperliquid": "Hyperliquid"
        }
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
        result = trader.get_positions()
        
        if result.get('status') == 'success':
            positions_data = result.get('positions', {})
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"📊 **{exchange.upper()} 포지션**\n\n```\n{positions_data}\n```",
                parse_mode='Markdown'
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **포지션 조회 실패**\n\n오류: {result.get('message', '알 수 없는 오류')}",
                parse_mode='Markdown'
            )
    except Exception as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
            parse_mode='Markdown'
        )

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
                 "**선물 거래**: `/trade [거래소] [심볼] [long/short] [주문타입] [수량] [거래타입]`\n"
                 "예시: `/trade backpack BTC long market 0.001 futures`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    symbol = parts[2].upper()
    action = parts[3].lower()  # buy/sell 또는 long/short
    order_type = parts[4].lower()  # market 또는 limit
    
    # 스팟 거래와 선물 거래 구분
    if action in ['buy', 'sell']:
        # 스팟 거래
        market_type = 'spot'
        direction = action  # buy/sell
        size = float(parts[5])
        price = None
        if order_type == 'limit' and len(parts) > 6:
            price = float(parts[6])
        leverage = 1
    else:
        # 선물 거래
        market_type = 'futures'
        direction = action  # long/short
        size = float(parts[5])
        price = None
        # 저장된 레버리지 설정 조회
        leverage = get_user_leverage_setting(user_id, exchange, symbol, direction)
        print(f"🔍 사용자 {user_id}의 레버리지 설정: {exchange} {symbol} {direction} = {leverage}x")
        if len(parts) > 6 and parts[6].lower() in ['spot', 'futures']:
            market_type = parts[6].lower()  # spot 또는 futures
    
    user_keys = get_user_api_keys(user_id)
    
    # API 키 존재 여부 확인 (더 정확한 체크)
    has_api_key = False
    if user_keys:
        if exchange == 'backpack':
            has_api_key = bool(user_keys.get('backpack_api_key') and user_keys.get('backpack_private_key'))
        else:
            has_api_key = bool(user_keys.get(f'{exchange}_api_key') and user_keys.get(f'{exchange}_api_secret'))
    
    if not has_api_key:
        exchange_names = {
            "xt": "XT Exchange",
            "backpack": "Backpack Exchange",
            "hyperliquid": "Hyperliquid"
        }
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
            # 스팟 거래
            try:
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
            except Exception as e:
                # 텔레그램 메시지 파싱 오류 방지를 위해 특수문자 처리
                error_msg = str(e).replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[').replace(']', '\\]')
                await telegram_app.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ **스팟 거래 오류**\n\n오류: {error_msg}\n\nAPI 키와 심볼을 확인해주세요.",
                    parse_mode='Markdown'
                )
                return
        else:
            # 선물 거래
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
            # 스팟 거래와 선물 거래에 따른 메시지 구분
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
            
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=success_message,
                parse_mode='Markdown'
            )
        else:
            # 스팟 거래와 선물 거래에 따른 실패 메시지 구분
            error_msg = result.get('message', '알 수 없는 오류')
            # 텔레그램 메시지 파싱 오류 방지를 위해 특수문자 처리
            error_msg = error_msg.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[').replace(']', '\\]')
            
            if market_type == 'spot':
                error_message = f"❌ **거래 실패**\n\n오류: {error_msg}"
            else:
                error_message = f"❌ **포지션 오픈 실패**\n\n오류: {error_msg}"
            
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=error_message,
                parse_mode='Markdown'
            )
    except Exception as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
            parse_mode='Markdown'
        )

async def handle_leverage_command(telegram_app, chat_id, user_id, text):
    """레버리지 설정 명령어 처리"""
    parts = text.split()
    if len(parts) < 5:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법: /leverage [거래소] [심볼] [방향] [레버리지]\n\n예시: `/leverage backpack BTC long 10`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    symbol = parts[2].upper()
    direction = parts[3].lower()
    leverage = int(parts[4])
    
    # 레버리지 설정을 데이터베이스에 저장
    save_user_leverage_setting(user_id, exchange, symbol, direction, leverage)
    
    # 레버리지 설정 완료 후 수량 입력 안내
    await show_futures_quantity_input(telegram_app, chat_id, user_id, exchange, direction, symbol, leverage, None)

async def handle_close_command(telegram_app, chat_id, user_id, text):
    """포지션 종료 명령어 처리"""
    parts = text.split()
    if len(parts) < 3:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법: /close [거래소] [심볼]\n\n예시: `/close xt BTCUSDT`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    symbol = parts[2].upper()
    
    user_keys = get_user_api_keys(user_id)
    
    if not user_keys or not user_keys.get(f'{exchange}_api_key'):
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **{exchange.upper()} API 키가 설정되지 않았습니다.**\n\n"
                 f"먼저 API 키를 설정해주세요.\n\n"
                 f"🔑 API 관리로 이동하려면 /start를 입력하세요.",
            parse_mode='Markdown'
        )
        return
    
    try:
        api_key = user_keys.get(f'{exchange}_api_key')
        api_secret = user_keys.get(f'{exchange}_api_secret') or user_keys.get(f'{exchange}_private_key')
        
        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
        result = trader.close_position(symbol)
        
        if result.get('status') == 'success':
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"✅ **포지션 종료 성공**\n\n"
                     f"거래소: {exchange.upper()}\n"
                     f"심볼: {symbol}\n"
                     f"주문 ID: {result.get('order_id', 'N/A')}",
                parse_mode='Markdown'
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **포지션 종료 실패**\n\n오류: {result.get('message', '알 수 없는 오류')}",
                parse_mode='Markdown'
            )
    except Exception as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
            parse_mode='Markdown'
        )

async def show_api_management_menu(telegram_app, chat_id, user_id, callback_query=None):
    """API 관리 메뉴 표시"""
    
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        return
    
    # 사용자 API 키 상태 확인
    user_keys = get_user_api_keys(user_id)
    
    keyboard = []
    exchanges = [
        ("xt", "XT Exchange"),
        ("backpack", "Backpack Exchange"),
        ("hyperliquid", "Hyperliquid")
    ]
    
    for exchange, name in exchanges:
        # API 키 존재 여부 확인 (더 정확한 체크)
        has_api_key = False
        if user_keys:
            if exchange == 'backpack':
                has_api_key = bool(user_keys.get('backpack_api_key') and user_keys.get('backpack_private_key'))
            else:
                has_api_key = bool(user_keys.get(f'{exchange}_api_key') and user_keys.get(f'{exchange}_api_secret'))
        
        if has_api_key:
            status = "✅ 설정됨"
        else:
            status = "❌ 미설정"
        
        keyboard.append([InlineKeyboardButton(f"{name} {status}", callback_data=f"api_{exchange}")])
    
    keyboard.extend([
        [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
    ])
    
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
            
async def show_balance_menu(telegram_app, chat_id, user_id, callback_query=None):
    """잔고 조회 메뉴 표시"""
    
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        return
    
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data="balance_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data="balance_backpack")],
        [InlineKeyboardButton("Hyperliquid", callback_data="balance_hyperliquid")],
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
            


async def show_position_menu(telegram_app, chat_id, user_id, callback_query=None):
    """포지션 관리 메뉴 표시"""
    
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 포지션 조회", callback_data="position_list")],
        [InlineKeyboardButton("❌ 포지션 종료", callback_data="position_close")],
        [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text="📊 **포지션 관리**\n\n포지션을 조회하고 관리할 수 있습니다.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text="📊 **포지션 관리**\n\n포지션을 조회하고 관리할 수 있습니다.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def show_trade_menu(telegram_app, chat_id, user_id, callback_query=None):
    """거래 메뉴 표시"""
    
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        return
    
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data="trade_exchange_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data="trade_exchange_backpack")],
        [InlineKeyboardButton("Hyperliquid", callback_data="trade_exchange_hyperliquid")],
        [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text="🔄 **거래하기**\n\n거래소를 선택하여 거래를 시작하세요.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text="🔄 **거래하기**\n\n거래소를 선택하여 거래를 시작하세요.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def show_settings_menu(telegram_app, chat_id, user_id, callback_query=None):
    """설정 메뉴 표시"""
    
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        return
    
    keyboard = [
        [InlineKeyboardButton("⚙️ 리스크 설정", callback_data="settings_risk")],
        [InlineKeyboardButton("🔔 알림 설정", callback_data="settings_notifications")],
        [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text="⚙️ **설정**\n\n봇의 설정을 관리할 수 있습니다.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text="⚙️ **설정**\n\n봇의 설정을 관리할 수 있습니다.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
            
async def show_help(telegram_app, chat_id, callback_query=None):
    """도움말 표시"""
    
    # Telegram 라이브러리 지연 로딩
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        print("❌ Telegram 라이브러리 import 실패")
        return
    
    help_text = (
        "❓ **도움말**\n\n"
        "**사용 방법:**\n"
        "1. 🔑 API 키 관리 - 거래소 API 키 설정\n"
        "2. 💰 잔고 조회 - 계좌 잔고 확인\n"
        "3. 📊 포지션 관리 - 포지션 조회/종료\n"
        "4. 🔄 거래하기 - 포지션 오픈\n"
        "5. 📊 시장 데이터 - 실시간 시장 정보\n\n"
        "**지원 거래소:**\n"
        "• XT Exchange (선물/스팟)\n"
        "• Backpack Exchange\n"
        "• Hyperliquid\n"

        "**명령어:**\n"
        "• `/setapi [거래소] [API_KEY] [SECRET_KEY]` - API 키 설정\n"
        "• `/balance [거래소]` - 잔고 조회\n"
        "• `/positions [거래소]` - 포지션 조회\n"
        "• `/trade [거래소] [심볼] [방향] [수량] [레버리지]` - 거래\n"
        "• `/close [거래소] [심볼]` - 포지션 종료\n"
        "• `/market [거래소] [심볼] [ticker/depth/kline]` - 선물 시장 데이터\n"
        "• `/spotmarket [거래소] [심볼] [ticker/depth/kline]` - 스팟 시장 데이터\n\n"
        "**시장 데이터 타입:**\n"
        "• `ticker`: 시장 가격 정보\n"
        "• `depth`: 호가창 데이터\n"
        "• `kline`: K라인 데이터"
    )
            
    keyboard = [[InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=help_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
# UnifiedFuturesTrader 클래스는 기존 app.py와 동일하게 유지
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
            # XT API 베이스 URL (pyxt 라이브러리 기반)
            self.base_url = "https://fapi.xt.com"  # 선물 API
            self.spot_base_url = "https://sapi.xt.com"  # 스팟 API
        elif self.exchange == 'backpack':
            self.api_key = kwargs.get('api_key')
            self.private_key = kwargs.get('private_key') or kwargs.get('api_secret')
            self.base_url = "https://api.backpack.exchange/api/v1"
            # 지연 로딩으로 변경
            self.signing_key = None
        elif self.exchange == 'hyperliquid':
            # Hyperliquid SDK가 설치되지 않은 경우 임시로 비활성화
            self.account_address = kwargs.get('api_key')  # 지갑 주소
            self.private_key = kwargs.get('api_secret')   # 개인키
            self.sdk_available = False  # SDK 미설치로 인해 비활성화

        else:
            raise ValueError('지원하지 않는 거래소입니다: xt, backpack, hyperliquid만 지원')

    def test_api_connection(self):
        """API 연결 테스트"""
        try:
            if self.exchange == 'xt':
                # XT API 연결 테스트 - 서버 시간 조회 (공개 엔드포인트)
                time_endpoints = [
                    "/v4/public/time"  # pyxt 라이브러리 엔드포인트
                ]
                
                for time_endpoint in time_endpoints:
                    url = f"{self.base_url}{time_endpoint}"
                    response = requests.get(url)
                    
                    print(f"XT API 연결 테스트 {time_endpoint}: {response.status_code}")  # 디버깅용
                    
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            'status': 'success',
                            'message': f'XT API 연결 성공 ({time_endpoint})'
                        }
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'message': 'XT API 연결 성공'
                    }
                else:
                    # API 키가 있는 경우 인증 테스트도 시도
                    if self.api_key and self.api_secret:
                        try:
                            # 인증이 필요한 엔드포인트로 테스트
                            test_url = f"{self.base_url}/v4/account/assets"
                            headers = self._get_headers_xt()
                            auth_response = requests.get(test_url, headers=headers)
                            
                            if auth_response.status_code == 200:
                                return {
                                    'status': 'success',
                                    'message': 'XT API 인증 성공'
                                }
                            else:
                                return {
                                    'status': 'error',
                                    'message': f'XT API 인증 실패: {auth_response.status_code} - {auth_response.text}'
                                }
                        except Exception as auth_e:
                            return {
                                'status': 'error',
                                'message': f'XT API 인증 테스트 오류: {str(auth_e)}'
                            }
                    else:
                        return {
                            'status': 'error',
                            'message': f'XT API 연결 실패: {response.status_code}'
                        }
            
            elif self.exchange == 'backpack':
                # Backpack Exchange API 연결 테스트 - 계좌 정보 조회
                try:
                    # pynacl 지연 로딩
                    global SigningKey
                    if SigningKey is None:
                        from nacl.signing import SigningKey
                    
                    if self.private_key:
                        self.signing_key = SigningKey(base64.b64decode(self.private_key))
                    
                    url = "https://api.backpack.exchange/api/v1/account"
                    headers = self._get_headers_backpack("accountQuery")
                    response = requests.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        return {
                            'status': 'success',
                            'message': 'Backpack API 연결 성공'
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'Backpack API 연결 실패: {response.status_code} - {response.text}'
                        }
                except ImportError:
                    return {
                        'status': 'error',
                        'message': 'pynacl 패키지가 필요합니다. pip install pynacl로 설치해주세요.'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Backpack API 연결 테스트 오류: {str(e)}'
                    }
            
            elif self.exchange == 'hyperliquid':
                return {
                    'status': 'error',
                    'message': 'Hyperliquid SDK가 설치되지 않았습니다. 패키지를 설치한 후 다시 시도해주세요.'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'API 연결 테스트 오류: {str(e)}'
            }

    def _get_headers_xt(self, params=None):
        """XT API 헤더 생성 (공식 문서 기반)"""
        timestamp = str(int(time.time() * 1000))
        params = params or {}
        
        # XT API 서명 생성 - 공식 문서 방식
        # 1. 파라미터를 알파벳 순으로 정렬
        sorted_params = sorted(params.items())
        
        # 2. 쿼리 스트링 생성 (값을 문자열로 변환)
        query_string = '&'.join([f"{k}={str(v)}" for k, v in sorted_params])
        
        # 3. 서명 문자열 생성 (pyxt 라이브러리 방식)
        if query_string:
            sign_string = f"access_key={self.api_key}&{query_string}&timestamp={timestamp}"
        else:
            sign_string = f"access_key={self.api_key}&timestamp={timestamp}"
        
        # 4. HMAC-SHA256 서명 생성
        signature = hmac.new(
            self.api_secret.encode('utf-8'), 
            sign_string.encode('utf-8'), 
            hashlib.sha256
        ).digest().hex()
        
        # 대안 서명 방식 (필요시 사용)
        # signature = base64.b64encode(hmac.new(
        #     self.api_secret.encode('utf-8'), 
        #     sign_string.encode('utf-8'), 
        #     hashlib.sha256
        # ).digest()).decode('utf-8')
        
        print(f"XT 서명 디버그: sign_string={sign_string}, signature={signature}")  # 디버깅용
        
        # pyxt 라이브러리 방식 헤더
        headers = {
            "access_key": self.api_key,
            "signature": signature,
            "timestamp": timestamp,
            "Content-Type": "application/json"
        }
        
        return headers

    def _get_headers_backpack(self, instruction, params=None):
        """Backpack API 헤더 생성 (ED25519 서명)"""
        try:
            # pynacl 지연 로딩
            global SigningKey
            if SigningKey is None:
                from nacl.signing import SigningKey
            
            if self.signing_key is None and self.private_key:
                try:
                    # 개인키를 base64 디코딩
                    private_key_bytes = base64.b64decode(self.private_key)
                    print(f"🔍 개인키 디코딩 성공, 길이: {len(private_key_bytes)}")
                    self.signing_key = SigningKey(private_key_bytes)
                except Exception as e:
                    print(f"⚠️ 개인키 디코딩 실패: {e}")
                    raise Exception(f"개인키 디코딩 오류: {str(e)}")
            
            # 타임스탬프를 정수로 생성하고 문자열로 변환
            timestamp = str(int(time.time() * 1000))
            window = "5000"
            
            print(f"🔍 현재 타임스탬프: {timestamp}")
            print(f"🔍 현재 시간: {datetime.now().isoformat()}")
            params = params or {}
            
            # Backpack API 공식 문서에 따른 서명 생성
            # 모든 파라미터를 딕셔너리에 넣고 알파벳 순서로 정렬
            
            # 서명용 파라미터 딕셔너리 생성
            sign_params = {}
            
            # instruction 추가
            sign_params['instruction'] = instruction
            
            # 주문 파라미터들을 문자열로 변환하여 추가
            for key, value in params.items():
                sign_params[key] = str(value)
            
            # timestamp와 window 추가
            sign_params['timestamp'] = timestamp
            sign_params['window'] = window
            
            # 모든 파라미터를 알파벳 순서로 정렬하여 서명 문자열 생성
            sorted_params = sorted(sign_params.items())
            sign_str = '&'.join([f"{key}={value}" for key, value in sorted_params])
            
            # 서명 문자열 디버깅
            print(f"🔍 서명용 파라미터: {sign_params}")
            print(f"🔍 정렬된 파라미터: {sorted_params}")
            print(f"🔍 최종 서명 문자열: {sign_str}")
            
            print(f"🔍 Backpack 서명 문자열: {sign_str}")
            
            # API 키와 개인키 디버깅 정보 출력
            print(f"🔍 Backpack API Key: {self.api_key[:20]}...")
            print(f"🔍 Backpack Private Key: {self.private_key[:20]}...")
            print(f"🔍 Backpack API Key 길이: {len(self.api_key)}")
            print(f"🔍 Backpack Private Key 길이: {len(self.private_key)}")
            print(f"🔍 서명할 메시지 길이: {len(sign_str)}")
            
            # ED25519 서명 생성
            message_bytes = sign_str.encode('utf-8')
            signature = self.signing_key.sign(message_bytes)
            signature_b64 = base64.b64encode(signature.signature).decode('utf-8')
            
            print(f"🔍 서명 길이: {len(signature.signature)}")
            print(f"🔍 Base64 서명 길이: {len(signature_b64)}")
            print(f"🔍 서명 시작: {signature_b64[:20]}...")
            
            headers = {
                "X-API-Key": self.api_key,
                "X-Signature": signature_b64,
                "X-Timestamp": timestamp,
                "X-Window": window,
                "Content-Type": "application/json"
            }
            
            # 헤더 디버깅 정보 출력
            print(f"🔍 X-API-Key: {headers['X-API-Key']}")
            print(f"🔍 X-Timestamp: {headers['X-Timestamp']}")
            print(f"🔍 X-Window: {headers['X-Window']}")
            print(f"🔍 X-Signature: {headers['X-Signature'][:20]}...")
            
            print(f"🔍 Backpack 헤더 생성 완료: {headers}")
            return headers
            
        except ImportError:
            raise ImportError("pynacl 패키지가 필요합니다. pip install pynacl로 설치해주세요.")
        except Exception as e:
            raise Exception(f"Backpack 헤더 생성 오류: {str(e)}")

    def _get_backpack_prices(self):
        """Backpack에서 실제 거래 가격 가져오기"""
        try:
            # Backpack 공개 API로 가격 정보 가져오기
            url = "https://api.backpack.exchange/api/v1/tickers"
            print(f"🔍 Backpack 가격 조회 URL: {url}")
            
            response = requests.get(url)
            print(f"🔍 Backpack 가격 조회 응답: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"🔍 Backpack 전체 티커 데이터 개수: {len(data)}")
                
                prices = {}
                
                # USDT 페어 가격 추출
                for ticker in data:
                    symbol = ticker.get('symbol', '')
                    last_price = ticker.get('last', '0')
                    
                    # USDT 페어에서 기본 자산 추출
                    if symbol.endswith('_USDT'):
                        base_asset = symbol.replace('_USDT', '')
                        try:
                            price = float(last_price)
                            prices[base_asset] = price
                            print(f"🔍 {base_asset}_USDT: ${price}")
                        except:
                            print(f"❌ {base_asset} 가격 변환 실패: {last_price}")
                
                print(f"🔍 Backpack 가격 데이터: {prices}")
                return prices
            else:
                print(f"❌ Backpack 가격 조회 실패: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            print(f"❌ Backpack 가격 조회 오류: {e}")
            return {}

    def get_futures_balance(self):
        """선물 계좌 잔고 조회"""
        try:
            if self.exchange == 'xt':
                # pyxt 라이브러리를 사용한 XT 선물 잔고 조회
                if PYXTLIB_AVAILABLE:
                    try:
                        print(f"pyxt 라이브러리 사용 시도: API_KEY={self.api_key[:10]}...")
                        
                        try:
                            # XTClient 클래스 생성 (xt.py에서 성공한 방식)
                            xt_client = XTClient(self.api_key, self.api_secret)
                            
                            # XTClient가 제대로 초기화되었는지 확인
                            if xt_client.futures is None:
                                print("XTClient 선물 클라이언트 초기화 실패")
                                raise Exception("XTClient futures client initialization failed")
                            
                            balance_result = xt_client.get_futures_balance()
                            print(f"pyxt 라이브러리 선물 잔고 조회 성공: {balance_result}")
                            
                            if balance_result.get('status') == 'success':
                                return {
                                    'status': 'success',
                                    'balance': balance_result.get('balance'),
                                    'message': 'XT 선물 잔고 조회 성공 (pyxt 라이브러리)'
                                }
                            else:
                                print(f"pyxt 라이브러리 오류: {balance_result.get('message')}")
                                raise Exception(f"pyxt error: {balance_result.get('message')}")
                        except Exception as e:
                            print(f"pyxt 라이브러리 선물 잔고 조회 실패: {e}")
                            # 기존 방식으로 폴백
                    except Exception as e:
                        print(f"pyxt 라이브러리 선물 잔고 조회 실패: {e}")
                        print(f"pyxt 라이브러리 사용 불가능, 기존 방식으로 폴백")
                else:
                    print("pyxt 라이브러리가 설치되지 않음, 기존 방식 사용")
                
                # 기존 방식 (pyxt 라이브러리 사용 불가능한 경우)
                base_urls = [
                    "https://fapi.xt.com",  # 선물 API
                    "https://api.xt.com",   # 기본 API
                    "https://sapi.xt.com"   # 스팟 API
                ]
                
                endpoints = [
                    "/v4/account/balance",  # v4 기본 엔드포인트
                    "/v4/account/assets",
                    "/v4/account/capital",
                    "/account/balance",  # v4 없이 시도
                    "/account/assets",
                    "/account/capital",
                    "/v4/balance",  # v4 balance
                    "/v4/assets",
                    "/balance",  # 기본 balance
                    "/assets",   # 기본 assets
                    "/v4/account/futures/balance",  # 선물 잔고
                    "/v4/account/futures/assets"  # 선물 자산
                ]
                
                for base_url in base_urls:
                    for endpoint in endpoints:
                        url = f"{base_url}{endpoint}"
                        headers = self._get_headers_xt()
                        response = requests.get(url, headers=headers)
                        
                        print(f"XT 선물 잔고 조회 시도 {base_url}{endpoint}: {response.status_code} - {response.text}")  # 디버깅용
                        
                        if response.status_code == 200:
                            data = response.json()
                            # API 문서 링크 응답 체크
                            if data.get('result', {}).get('openapiDocs'):
                                print(f"API 문서 링크 응답, 다른 엔드포인트 시도: {base_url}{endpoint}")
                                continue  # 다음 엔드포인트 시도
                            
                            # AUTH_001 오류 체크
                            if data.get('rc') == 1 and data.get('mc') == 'AUTH_001':
                                print(f"AUTH_001 오류 발생, pyxt 방식으로 재시도: {base_url}{endpoint}")
                                # pyxt 라이브러리 방식으로 재시도 (서명 재생성)
                                alt_timestamp = str(int(time.time() * 1000))
                                alt_sign_string = f"access_key={self.api_key}&timestamp={alt_timestamp}"
                                alt_signature = hmac.new(
                                    self.api_secret.encode('utf-8'), 
                                    alt_sign_string.encode('utf-8'), 
                                    hashlib.sha256
                                ).digest().hex()
                                
                                alt_headers = {
                                    "access_key": self.api_key,
                                    "signature": alt_signature,
                                    "timestamp": alt_timestamp,
                                    "Content-Type": "application/json"
                                }
                                alt_response = requests.get(url, headers=alt_headers)
                                if alt_response.status_code == 200:
                                    alt_data = alt_response.json()
                                    if alt_data.get('rc') == 0:  # 성공 응답
                                        return {
                                            'status': 'success',
                                            'balance': alt_data.get('result', {}),
                                            'message': f'XT 선물 잔고 조회 성공 ({base_url}{endpoint}) - pyxt 방식'
                                        }
                            elif data.get('rc') == 0:  # 정상 응답
                                return {
                                    'status': 'success',
                                    'balance': data.get('result', {}),
                                    'message': f'XT 선물 잔고 조회 성공 ({base_url}{endpoint})'
                                }
                
                # 모든 시도 실패 시
                return {
                    'status': 'error',
                    'balance': {},  # 빈 딕셔너리 반환
                    'message': f'XT 선물 잔고 조회 실패: pyxt 라이브러리와 모든 엔드포인트에서 실패. XT API 문서에서 실제 잔고 엔드포인트를 확인해야 합니다.'
                }
            
            elif self.exchange == 'backpack':
                # Backpack Exchange 잔고 조회 - API 문서 기반
                try:
                    print(f"🔍 Backpack 잔고 조회 시작...")
                    
                    # Backpack API 문서에 따른 잔고 조회
                    url = "https://api.backpack.exchange/api/v1/capital"
                    headers = self._get_headers_backpack("balanceQuery")
                    
                    print(f"🔍 Backpack API 호출: {url}")
                    print(f"🔍 Backpack 헤더: {headers}")
                    
                    response = requests.get(url, headers=headers)
                    print(f"🔍 Backpack 응답: {response.status_code} - {response.text}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        print(f"🔍 Backpack 잔고 데이터: {data}")
                        
                        return {
                            'status': 'success',
                            'balance': data,
                            'message': 'Backpack 잔고 조회 성공'
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'Backpack 잔고 조회 실패: {response.status_code} - {response.text}'
                        }
                        
                except Exception as e:
                    print(f"❌ Backpack 잔고 조회 오류: {e}")
                    return {
                        'status': 'error',
                        'message': f'Backpack 잔고 조회 오류: {str(e)}'
                    }
            
            elif self.exchange == 'hyperliquid':
                try:
                    # Hyperliquid SDK 지연 로딩
                    from hyperliquid.info import Info
                    from hyperliquid.utils import constants
                    
                    if self.hyperliquid_info is None:
                        self.hyperliquid_info = Info(constants.MAINNET_API_URL, skip_ws=True)
                    
                    # 사용자 상태 조회
                    user_state = self.hyperliquid_info.user_state(self.account_address)
                    
                    # 잔고 정보 추출
                    balance_data = {}
                    if 'assetPositions' in user_state:
                        for position in user_state['assetPositions']:
                            if 'position' in position and 'szi' in position['position']:
                                size = float(position['position']['szi'])
                                if size != 0:  # 0이 아닌 포지션만
                                    coin = position.get('coin', 'UNKNOWN')
                                    balance_data[coin] = {
                                        'available': size,
                                        'total': size
                                    }
                    
                    return {
                        'status': 'success',
                        'balance': balance_data,
                        'message': 'Hyperliquid 잔고 조회 성공'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Hyperliquid 잔고 조회 실패: {str(e)}'
                    }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'선물 잔고 조회 오류: {str(e)}'
            }



    def open_long_position(self, symbol, size, leverage=1, order_type='market', market_type='futures'):
        """롱 포지션 오픈"""
        try:
            if self.exchange == 'xt':
                # XT 주문 - 공식 문서 기반 엔드포인트
                url = f"{self.base_url}/v4/order"
                params = {
                    'symbol': symbol,
                    'side': 'buy',
                    'type': order_type,
                    'quantity': size
                }
                
                # 레버리지는 선물 거래에서만 설정
                if market_type == 'futures' and leverage > 1:
                    params['leverage'] = leverage
                
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"XT API 응답: {data}")  # 디버깅용 로그
                    
                    # 다양한 응답 구조 시도
                    order_id = 'unknown'
                    if isinstance(data, dict):
                        # 직접 orderId 확인
                        if 'orderId' in data:
                            order_id = data['orderId']
                        elif 'result' in data:
                            result = data['result']
                            if isinstance(result, dict):
                                if 'orderId' in result:
                                    order_id = result['orderId']
                                elif 'id' in result:
                                    order_id = result['id']
                            elif isinstance(result, str):
                                order_id = result
                        elif 'id' in data:
                            order_id = data['id']
                    
                    return {
                        'status': 'success',
                        'order_id': order_id,
                        'message': 'XT 롱 포지션 오픈 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 롱 포지션 오픈 실패: {response.status_code} - {response.text}'
                    }
            
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order"
                
                # Backpack Exchange API에 맞는 주문 타입 변환
                if order_type == 'market':
                    backpack_order_type = 'Market'
                elif order_type == 'limit':
                    backpack_order_type = 'Limit'
                else:
                    backpack_order_type = 'Market'  # 기본값
                
                # Backpack Exchange API 문서에 따른 올바른 파라미터 구조
                # 스팟 거래: BTC_USDC, 선물 거래: BTC_USDC_PERP
                backpack_symbol = symbol
                if market_type == 'spot':
                    # 스팟 거래: BTC -> BTC_USDC
                    if not symbol.endswith('_USDC'):
                        backpack_symbol = f"{symbol}_USDC"
                else:
                    # 선물 거래: BTC -> BTC_USDC_PERP
                    if not symbol.endswith('_PERP'):
                        backpack_symbol = f"{symbol}_USDC_PERP"
                
                params = {
                    'symbol': backpack_symbol,
                    'side': 'Bid',  # Backpack에서는 'Bid' (매수) 또는 'Ask' (매도)
                    'orderType': backpack_order_type,  # 'type' 대신 'orderType' 사용
                    'quantity': str(size)
                }
                
                # 레버리지는 선물 거래에서만 설정
                if market_type == 'futures' and leverage > 1:
                    params['leverage'] = str(leverage)
                    print(f"🔍 Backpack 롱 포지션 레버리지 설정: {leverage}x")
                else:
                    print(f"🔍 Backpack 롱 포지션 레버리지 미설정 (기본값 1x 사용)")
                
                headers = self._get_headers_backpack("orderExecute", params)  # instruction을 'orderExecute'로 변경
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'order_id': data.get('orderId'),
                        'message': 'Backpack 롱 포지션 오픈 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'Backpack 롱 포지션 오픈 실패: {response.status_code} - {response.text}'
                    }
            
            elif self.exchange == 'hyperliquid':
                try:
                    # Hyperliquid SDK 지연 로딩
                    from hyperliquid.exchange import Exchange
                    from hyperliquid.utils import constants
                    
                    if self.hyperliquid_exchange is None:
                        self.hyperliquid_exchange = Exchange(
                            self.account_address, 
                            self.private_key, 
                            constants.MAINNET_API_URL
                        )
                    
                    # 주문 실행
                    order = self.hyperliquid_exchange.order(
                        symbol=symbol,
                        side='B',  # B = Buy (롱)
                        size=size,
                        price=None if order_type == 'market' else price,
                        reduce_only=False
                    )
                    
                    return {
                        'status': 'success',
                        'order_id': order.get('hash', 'unknown'),
                        'message': 'Hyperliquid 롱 포지션 오픈 성공'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Hyperliquid 롱 포지션 오픈 실패: {str(e)}'
                    }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'롱 포지션 오픈 오류: {str(e)}'
            }

    def open_short_position(self, symbol, size, leverage=1, order_type='market', market_type='futures'):
        """숏 포지션 오픈"""
        try:
            if self.exchange == 'xt':
                # XT 주문 - 공식 문서 기반 엔드포인트
                url = f"{self.base_url}/v4/order"
                params = {
                    'symbol': symbol,
                    'side': 'sell',
                    'type': order_type,
                    'quantity': size
                }
                
                # 레버리지는 선물 거래에서만 설정
                if market_type == 'futures' and leverage > 1:
                    params['leverage'] = leverage
                
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"XT API 응답: {data}")  # 디버깅용 로그
                    
                    # 다양한 응답 구조 시도
                    order_id = 'unknown'
                    if isinstance(data, dict):
                        # 직접 orderId 확인
                        if 'orderId' in data:
                            order_id = data['orderId']
                        elif 'result' in data:
                            result = data['result']
                            if isinstance(result, dict):
                                if 'orderId' in result:
                                    order_id = result['orderId']
                                elif 'id' in result:
                                    order_id = result['id']
                            elif isinstance(result, str):
                                order_id = result
                        elif 'id' in data:
                            order_id = data['id']
                    
                    return {
                        'status': 'success',
                        'order_id': order_id,
                        'message': 'XT 숏 포지션 오픈 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 숏 포지션 오픈 실패: {response.status_code} - {response.text}'
                    }
            
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order"
                
                # Backpack Exchange API에 맞는 주문 타입 변환
                if order_type == 'market':
                    backpack_order_type = 'Market'
                elif order_type == 'limit':
                    backpack_order_type = 'Limit'
                else:
                    backpack_order_type = 'Market'  # 기본값
                
                # Backpack Exchange API 문서에 따른 올바른 파라미터 구조
                # 스팟 거래: BTC_USDC, 선물 거래: BTC_USDC_PERP
                backpack_symbol = symbol
                if market_type == 'spot':
                    # 스팟 거래: BTC -> BTC_USDC
                    if not symbol.endswith('_USDC'):
                        backpack_symbol = f"{symbol}_USDC"
                else:
                    # 선물 거래: BTC -> BTC_USDC_PERP
                    if not symbol.endswith('_PERP'):
                        backpack_symbol = f"{symbol}_USDC_PERP"
                
                params = {
                    'symbol': backpack_symbol,
                    'side': 'Ask',  # Backpack에서는 'Bid' (매수) 또는 'Ask' (매도)
                    'orderType': backpack_order_type,  # 'type' 대신 'orderType' 사용
                    'quantity': str(size)
                }
                
                # 레버리지는 선물 거래에서만 설정
                if market_type == 'futures' and leverage > 1:
                    params['leverage'] = str(leverage)
                
                headers = self._get_headers_backpack("orderExecute", params)  # instruction을 'orderExecute'로 변경
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'order_id': data.get('orderId'),
                        'message': 'Backpack 숏 포지션 오픈 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'Backpack 숏 포지션 오픈 실패: {response.status_code} - {response.text}'
                    }
            
            elif self.exchange == 'hyperliquid':
                try:
                    # Hyperliquid SDK 지연 로딩
                    from hyperliquid.exchange import Exchange
                    from hyperliquid.utils import constants
                    
                    if self.hyperliquid_exchange is None:
                        self.hyperliquid_exchange = Exchange(
                            self.account_address, 
                            self.private_key, 
                            constants.MAINNET_API_URL
                        )
                    
                    # 주문 실행
                    order = self.hyperliquid_exchange.order(
                        symbol=symbol,
                        side='A',  # A = Ask (숏)
                        size=size,
                        price=None if order_type == 'market' else price,
                        reduce_only=False
                    )
                    
                    return {
                        'status': 'success',
                        'order_id': order.get('hash', 'unknown'),
                        'message': 'Hyperliquid 숏 포지션 오픈 성공'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Hyperliquid 숏 포지션 오픈 실패: {str(e)}'
                    }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'숏 포지션 오픈 오류: {str(e)}'
            }

    def spot_buy(self, symbol, size, order_type='market', price=None):
        """스팟 매수"""
        try:
            if self.exchange == 'xt':
                # XT 스팟 매수 - 공식 문서 기반 엔드포인트
                # 대안 엔드포인트 시도
                url = f"{self.base_url}/v4/order"
                # 만약 실패하면 다른 엔드포인트 시도: f"{self.base_url}/v4/spot/order"
                params = {
                    'symbol': symbol,
                    'side': 'buy',
                    'type': order_type,
                    'quantity': str(size)  # 문자열로 변환
                }
                
                # 지정가 주문의 경우 가격 추가
                if order_type == 'limit' and price:
                    params['price'] = str(price)  # 문자열로 변환
                
                headers = self._get_headers_xt(params)
                print(f"XT API 요청: URL={url}, params={params}")  # 디버깅용
                print(f"XT API 헤더: {headers}")  # 디버깅용
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"XT API 응답: {data}")  # 디버깅용 로그
                    
                    # 인증 오류 확인
                    if isinstance(data, dict) and data.get('rc') == 1:
                        error_code = data.get('mc', 'UNKNOWN')
                        if error_code == 'AUTH_001':
                            return {
                                'status': 'error',
                                'message': f'XT API 인증 오류: API 키 또는 시크릿 키가 잘못되었습니다. (오류코드: {error_code})'
                            }
                        else:
                            return {
                                'status': 'error',
                                'message': f'XT API 오류: {error_code} - {data.get("ma", [])}'
                            }
                    
                    # 다양한 응답 구조 시도
                    order_id = 'unknown'
                    if isinstance(data, dict):
                        # 직접 orderId 확인
                        if 'orderId' in data:
                            order_id = data['orderId']
                        elif 'result' in data:
                            result = data['result']
                            if isinstance(result, dict):
                                if 'orderId' in result:
                                    order_id = result['orderId']
                                elif 'id' in result:
                                    order_id = result['id']
                            elif isinstance(result, str):
                                order_id = result
                        elif 'id' in data:
                            order_id = data['id']
                    
                    return {
                        'status': 'success',
                        'order_id': order_id,
                        'message': 'XT 스팟 매수 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 스팟 매수 실패: {response.status_code} - {response.text}'
                    }
            
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order"
                
                # Backpack Exchange API에 맞는 주문 타입 변환
                if order_type == 'market':
                    backpack_order_type = 'Market'
                elif order_type == 'limit':
                    backpack_order_type = 'Limit'
                else:
                    backpack_order_type = 'Market'  # 기본값
                
                # 스팟 거래 심볼 형식: BTC_USDC
                backpack_symbol = symbol
                if not symbol.endswith('_USDC'):
                    backpack_symbol = f"{symbol}_USDC"
                
                params = {
                    'symbol': backpack_symbol,
                    'side': 'Bid',  # 매수
                    'orderType': backpack_order_type,
                    'quantity': str(size)
                }
                
                # 지정가 주문의 경우 가격 추가
                if order_type == 'limit' and price:
                    params['price'] = str(price)
                
                headers = self._get_headers_backpack("orderExecute", params)
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'order_id': data.get('orderId'),
                        'message': 'Backpack 스팟 매수 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'Backpack 스팟 매수 실패: {response.status_code} - {response.text}'
                    }
            
            elif self.exchange == 'hyperliquid':
                order = self.ccxt_client.create_order(
                    symbol=symbol,
                    type=order_type,
                    side='buy',
                    amount=size,
                    price=price if order_type == 'limit' else None
                )
                return {
                    'status': 'success',
                    'order_id': order.get('id'),
                    'message': f'{self.exchange.capitalize()} 스팟 매수 성공'
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'스팟 매수 오류: {str(e)}'
            }

    def spot_sell(self, symbol, size, order_type='market', price=None):
        """스팟 매도"""
        try:
            if self.exchange == 'xt':
                # XT 스팟 매도 - 공식 문서 기반 엔드포인트
                url = f"{self.base_url}/v4/order"
                params = {
                    'symbol': symbol,
                    'side': 'sell',
                    'type': order_type,
                    'quantity': str(size)  # 문자열로 변환
                }
                
                # 지정가 주문의 경우 가격 추가
                if order_type == 'limit' and price:
                    params['price'] = str(price)  # 문자열로 변환
                
                headers = self._get_headers_xt(params)
                print(f"XT API 요청: URL={url}, params={params}")  # 디버깅용
                print(f"XT API 헤더: {headers}")  # 디버깅용
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"XT API 응답: {data}")  # 디버깅용 로그
                    
                    # 인증 오류 확인
                    if isinstance(data, dict) and data.get('rc') == 1:
                        error_code = data.get('mc', 'UNKNOWN')
                        if error_code == 'AUTH_001':
                            return {
                                'status': 'error',
                                'message': f'XT API 인증 오류: API 키 또는 시크릿 키가 잘못되었습니다. (오류코드: {error_code})'
                            }
                        else:
                            return {
                                'status': 'error',
                                'message': f'XT API 오류: {error_code} - {data.get("ma", [])}'
                            }
                    
                    # 다양한 응답 구조 시도
                    order_id = 'unknown'
                    if isinstance(data, dict):
                        # 직접 orderId 확인
                        if 'orderId' in data:
                            order_id = data['orderId']
                        elif 'result' in data:
                            result = data['result']
                            if isinstance(result, dict):
                                if 'orderId' in result:
                                    order_id = result['orderId']
                                elif 'id' in result:
                                    order_id = result['id']
                            elif isinstance(result, str):
                                order_id = result
                        elif 'id' in data:
                            order_id = data['id']
                    
                    return {
                        'status': 'success',
                        'order_id': order_id,
                        'message': 'XT 스팟 매도 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 스팟 매도 실패: {response.status_code} - {response.text}'
                    }
            
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order"
                
                # Backpack Exchange API에 맞는 주문 타입 변환
                if order_type == 'market':
                    backpack_order_type = 'Market'
                elif order_type == 'limit':
                    backpack_order_type = 'Limit'
                else:
                    backpack_order_type = 'Market'  # 기본값
                
                # 스팟 거래 심볼 형식: BTC_USDC
                backpack_symbol = symbol
                if not symbol.endswith('_USDC'):
                    backpack_symbol = f"{symbol}_USDC"
                
                params = {
                    'symbol': backpack_symbol,
                    'side': 'Ask',  # 매도
                    'orderType': backpack_order_type,
                    'quantity': str(size)
                }
                
                # 지정가 주문의 경우 가격 추가
                if order_type == 'limit' and price:
                    params['price'] = str(price)
                
                headers = self._get_headers_backpack("orderExecute", params)
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'order_id': data.get('orderId'),
                        'message': 'Backpack 스팟 매도 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'Backpack 스팟 매도 실패: {response.status_code} - {response.text}'
                    }
            
            elif self.exchange == 'hyperliquid':
                try:
                    # Hyperliquid SDK 지연 로딩
                    from hyperliquid.exchange import Exchange
                    from hyperliquid.utils import constants
                    
                    if self.hyperliquid_exchange is None:
                        self.hyperliquid_exchange = Exchange(
                            self.account_address, 
                            self.private_key, 
                            constants.MAINNET_API_URL
                        )
                    
                    # 스팟 매도 주문 (Hyperliquid는 주로 선물 거래를 지원)
                    order = self.hyperliquid_exchange.order(
                        symbol=symbol,
                        side='A',  # A = Ask (매도)
                        size=size,
                        price=None if order_type == 'market' else price,
                        reduce_only=False
                    )
                    
                    return {
                        'status': 'success',
                        'order_id': order.get('hash', 'unknown'),
                        'message': 'Hyperliquid 스팟 매도 성공'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Hyperliquid 스팟 매도 실패: {str(e)}'
                    }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'스팟 매도 오류: {str(e)}'
            }

    def get_spot_balance(self):
        """스팟 계좌 잔고 조회"""
        try:
            if self.exchange == 'xt':
                # pyxt 라이브러리를 사용한 XT 스팟 잔고 조회
                if PYXTLIB_AVAILABLE:
                    try:
                        print(f"pyxt 라이브러리 사용 시도: API_KEY={self.api_key[:10]}...")
                        
                        try:
                            print("🔍 스팟 잔고 조회 시작...")
                            # XTClient 클래스 생성 (xt.py에서 성공한 방식)
                            xt_client = XTClient(self.api_key, self.api_secret)
                            print(f"🔍 XTClient 생성 완료: {xt_client}")
                            
                            # XTClient가 제대로 초기화되었는지 확인
                            print(f"🔍 XTClient spot 속성: {xt_client.spot}")
                            if xt_client.spot is None:
                                print("❌ XTClient 스팟 클라이언트 초기화 실패")
                                raise Exception("XTClient spot client initialization failed")
                            
                            print("🔍 get_spot_balance() 메서드 호출 시작...")
                            balance_result = xt_client.get_spot_balance()
                            print(f"✅ pyxt 라이브러리 스팟 잔고 조회 성공: {balance_result}")
                            
                            if balance_result.get('status') == 'success':
                                return {
                                    'status': 'success',
                                    'balance': balance_result.get('balance'),
                                    'message': 'XT 스팟 잔고 조회 성공 (pyxt 라이브러리)'
                                }
                            else:
                                print(f"❌ pyxt 라이브러리 오류: {balance_result.get('message')}")
                                raise Exception(f"pyxt error: {balance_result.get('message')}")
                        except Exception as e:
                            print(f"❌ pyxt 라이브러리 스팟 잔고 조회 실패: {e}")
                            print(f"❌ 오류 타입: {type(e)}")
                            import traceback
                            print(f"❌ 오류 상세: {traceback.format_exc()}")
                            # 기존 방식으로 폴백
                    except Exception as e:
                        print(f"pyxt 라이브러리 스팟 잔고 조회 실패: {e}")
                        # pyxt 실패 시 기존 방식으로 폴백
                else:
                    print("pyxt 라이브러리가 설치되지 않음, 기존 방식 사용")
                
                # 기존 방식 (pyxt 라이브러리 사용 불가능한 경우)
                base_urls = [
                    "https://sapi.xt.com",  # 스팟 API
                    "https://api.xt.com",   # 기본 API
                    "https://fapi.xt.com"   # 선물 API
                ]
                
                endpoints = [
                    "/v4/account/balance",  # v4 기본 엔드포인트
                    "/v4/account/assets",
                    "/v4/account/capital",
                    "/account/balance",  # v4 없이 시도
                    "/account/assets",
                    "/account/capital",
                    "/v4/balance",  # v4 balance
                    "/v4/assets",
                    "/balance",  # 기본 balance
                    "/assets",   # 기본 assets
                    "/v4/account/spot/balance",  # 스팟 잔고
                    "/v4/account/spot/assets"  # 스팟 자산
                ]
                
                for base_url in base_urls:
                    for endpoint in endpoints:
                        url = f"{base_url}{endpoint}"
                        headers = self._get_headers_xt()
                        response = requests.get(url, headers=headers)
                        
                        print(f"XT 스팟 잔고 조회 시도 {base_url}{endpoint}: {response.status_code} - {response.text}")  # 디버깅용
                        
                        if response.status_code == 200:
                            data = response.json()
                            # API 문서 링크 응답 체크
                            if data.get('result', {}).get('openapiDocs'):
                                print(f"API 문서 링크 응답, 다른 엔드포인트 시도: {base_url}{endpoint}")
                                continue  # 다음 엔드포인트 시도
                            
                            # AUTH_001 오류 체크
                            if data.get('rc') == 1 and data.get('mc') == 'AUTH_001':
                                print(f"AUTH_001 오류 발생, pyxt 방식으로 재시도: {base_url}{endpoint}")
                                # pyxt 라이브러리 방식으로 재시도 (서명 재생성)
                                alt_timestamp = str(int(time.time() * 1000))
                                alt_sign_string = f"access_key={self.api_key}&timestamp={alt_timestamp}"
                                alt_signature = hmac.new(
                                    self.api_secret.encode('utf-8'), 
                                    alt_sign_string.encode('utf-8'), 
                                    hashlib.sha256
                                ).digest().hex()
                                
                                alt_headers = {
                                    "access_key": self.api_key,
                                    "signature": alt_signature,
                                    "timestamp": alt_timestamp,
                                    "Content-Type": "application/json"
                                }
                                alt_response = requests.get(url, headers=alt_headers)
                                if alt_response.status_code == 200:
                                    alt_data = alt_response.json()
                                    if alt_data.get('rc') == 0:  # 성공 응답
                                        return {
                                            'status': 'success',
                                            'balance': alt_data.get('result', {}),
                                            'message': f'XT 스팟 잔고 조회 성공 ({base_url}{endpoint}) - pyxt 방식'
                                        }
                            elif data.get('rc') == 0:  # 정상 응답
                                return {
                                    'status': 'success',
                                    'balance': data.get('result', {}),
                                    'message': f'XT 스팟 잔고 조회 성공 ({base_url}{endpoint})'
                                }
                
                # 모든 시도 실패 시
                return {
                    'status': 'error',
                    'balance': {},  # 빈 딕셔너리 반환
                    'message': f'XT 스팟 잔고 조회 실패: pyxt 라이브러리와 모든 엔드포인트에서 실패. XT API 문서에서 실제 잔고 엔드포인트를 확인해야 합니다.'
                }
            
            elif self.exchange == 'hyperliquid':
                try:
                    # Hyperliquid SDK 지연 로딩
                    from hyperliquid.info import Info
                    from hyperliquid.utils import constants
                    
                    if self.hyperliquid_info is None:
                        self.hyperliquid_info = Info(constants.MAINNET_API_URL, skip_ws=True)
                    
                    # 사용자 상태 조회
                    user_state = self.hyperliquid_info.user_state(self.account_address)
                    
                    # 스팟 잔고 정보 추출 (USDC 잔고 등)
                    balance_data = {}
                    if 'marginSummary' in user_state:
                        margin = user_state['marginSummary']
                        if 'accountValue' in margin:
                            balance_data['USDC'] = {
                                'available': float(margin['accountValue']),
                                'total': float(margin['accountValue'])
                            }
                    
                    return {
                        'status': 'success',
                        'balance': balance_data,
                        'message': 'Hyperliquid 스팟 잔고 조회 성공'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Hyperliquid 스팟 잔고 조회 실패: {str(e)}'
                    }
            
            else:
                return {
                    'status': 'error',
                    'message': f'{self.exchange.capitalize()}는 스팟 잔고 조회를 지원하지 않습니다.'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'스팟 잔고 조회 오류: {str(e)}'
            }



    def get_market_data(self, symbol, data_type='ticker'):
        """시장 데이터 조회"""
        try:
            if self.exchange == 'xt':
                if data_type == 'ticker':
                    # XT 시장 데이터 조회 - 공식 문서 기반
                    url = f"{self.base_url}/v4/public/ticker/24hr"
                    if symbol:
                        url += f"?symbol={symbol}"
                    response = requests.get(url)
                elif data_type == 'depth':
                    # XT 깊이 데이터 조회 - 공식 문서 기반
                    url = f"{self.base_url}/v4/public/depth"
                    params = {'symbol': symbol, 'limit': 10}
                    response = requests.get(url, params=params)
                elif data_type == 'kline':
                    # XT K라인 데이터 조회 - 공식 문서 기반
                    url = f"{self.base_url}/v4/public/kline"
                    params = {'symbol': symbol, 'interval': '1m', 'limit': 10}
                    response = requests.get(url, params=params)
                else:
                    return {
                        'status': 'error',
                        'message': f'지원하지 않는 데이터 타입: {data_type}'
                    }
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'data': data.get('result', {}),
                        'message': f'XT {data_type} 데이터 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT {data_type} 데이터 조회 실패: {response.status_code}'
                    }
            else:
                return {
                    'status': 'error',
                    'message': f'{self.exchange.capitalize()}는 시장 데이터 조회를 지원하지 않습니다.'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'시장 데이터 조회 오류: {str(e)}'
            }

    def get_spot_market_data(self, symbol, data_type='ticker'):
        """스팟 시장 데이터 조회"""
        try:
            if self.exchange == 'xt':
                if data_type == 'ticker':
                    # XT 스팟 시장 데이터 조회 - 공식 문서 기반
                    url = f"{self.base_url}/v4/public/ticker/24hr"
                    if symbol:
                        url += f"?symbol={symbol}"
                    response = requests.get(url)
                elif data_type == 'depth':
                    # XT 스팟 깊이 데이터 조회 - 공식 문서 기반
                    url = f"{self.base_url}/v4/public/depth"
                    params = {'symbol': symbol, 'limit': 10}
                    response = requests.get(url, params=params)
                elif data_type == 'kline':
                    # XT 스팟 K라인 데이터 조회 - 공식 문서 기반
                    url = f"{self.base_url}/v4/public/kline"
                    params = {'symbol': symbol, 'interval': '1m', 'limit': 10}
                    response = requests.get(url, params=params)
                else:
                    return {
                        'status': 'error',
                        'message': f'지원하지 않는 데이터 타입: {data_type}'
                    }
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'data': data.get('result', {}),
                        'message': f'XT 스팟 {data_type} 데이터 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 스팟 {data_type} 데이터 조회 실패: {response.status_code}'
                    }
            else:
                return {
                    'status': 'error',
                    'message': f'{self.exchange.capitalize()}는 스팟 시장 데이터 조회를 지원하지 않습니다.'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'스팟 시장 데이터 조회 오류: {str(e)}'
            }

async def handle_market_data_command(telegram_app, chat_id, user_id, text):
    """시장 데이터 조회 명령어 처리"""
    parts = text.split()
    if len(parts) < 3:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법:\n\n"
                 "`/market [거래소] [심볼] [데이터타입]`\n\n"
                 "**데이터 타입**:\n"
                 "- `ticker`: 시장 가격 정보\n"
                 "- `depth`: 호가창 데이터\n"
                 "- `kline`: K라인 데이터\n\n"
                 "**예시**:\n"
                 "`/market xt BTC_USDT ticker`\n"
                 "`/market xt BTC_USDT depth`\n"
                 "`/market xt BTC_USDT kline`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    symbol = parts[2].upper()
    data_type = parts[3].lower() if len(parts) > 3 else 'ticker'
    
    user_keys = get_user_api_keys(user_id)
    
    if not user_keys or not user_keys.get(f'{exchange}_api_key'):
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **{exchange.upper()} API 키가 설정되지 않았습니다.**\n\n"
                 f"먼저 API 키를 설정해주세요.\n\n"
                 f"🔑 API 관리로 이동하려면 /start를 입력하세요.",
            parse_mode='Markdown'
        )
        return
    
    try:
        api_key = user_keys.get(f'{exchange}_api_key')
        api_secret = user_keys.get(f'{exchange}_api_secret') or user_keys.get(f'{exchange}_private_key')
        
        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
        
        # 시장 데이터 조회
        result = trader.get_market_data(symbol, data_type)
        
        if result.get('status') == 'success':
            data = result.get('data', {})
            
            if data_type == 'ticker':
                # 티커 데이터 포맷팅
                if isinstance(data, list) and len(data) > 0:
                    ticker = data[0]
                    message = f"📊 **{symbol} 시장 데이터**\n\n"
                    message += f"거래소: {exchange.upper()}\n"
                    message += f"심볼: {symbol}\n"
                    message += f"최신가: {ticker.get('last', 'N/A')}\n"
                    message += f"24h 변동: {ticker.get('change24h', 'N/A')}\n"
                    message += f"거래량: {ticker.get('volume24h', 'N/A')}\n"
                    message += f"고가: {ticker.get('high24h', 'N/A')}\n"
                    message += f"저가: {ticker.get('low24h', 'N/A')}"
                else:
                    message = f"📊 **{symbol} 시장 데이터**\n\n데이터: {data}"
            elif data_type == 'depth':
                # 깊이 데이터 포맷팅
                message = f"📊 **{symbol} 호가창 데이터**\n\n"
                message += f"거래소: {exchange.upper()}\n"
                message += f"심볼: {symbol}\n\n"
                message += f"데이터: {data}"
            elif data_type == 'kline':
                # K라인 데이터 포맷팅
                message = f"📊 **{symbol} K라인 데이터**\n\n"
                message += f"거래소: {exchange.upper()}\n"
                message += f"심볼: {symbol}\n\n"
                message += f"데이터: {data}"
            else:
                message = f"📊 **{symbol} {data_type} 데이터**\n\n{data}"
            
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **시장 데이터 조회 실패**\n\n{result.get('message', '알 수 없는 오류')}",
                parse_mode='Markdown'
            )
    
    except Exception as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
            parse_mode='Markdown'
        )

async def handle_spot_market_data_command(telegram_app, chat_id, user_id, text):
    """스팟 시장 데이터 조회 명령어 처리"""
    parts = text.split()
    if len(parts) < 3:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법:\n\n"
                 "`/spotmarket [거래소] [심볼] [데이터타입]`\n\n"
                 "**데이터 타입**:\n"
                 "- `ticker`: 시장 가격 정보\n"
                 "- `depth`: 호가창 데이터\n"
                 "- `kline`: K라인 데이터\n\n"
                 "**예시**:\n"
                 "`/spotmarket xt BTC_USDT ticker`\n"
                 "`/spotmarket xt BTC_USDT depth`\n"
                 "`/spotmarket xt BTC_USDT kline`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    symbol = parts[2].upper()
    data_type = parts[3].lower() if len(parts) > 3 else 'ticker'
    
    user_keys = get_user_api_keys(user_id)
    
    if not user_keys or not user_keys.get(f'{exchange}_api_key'):
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=f"❌ **{exchange.upper()} API 키가 설정되지 않았습니다.**\n\n"
                 f"먼저 API 키를 설정해주세요.\n\n"
                 f"🔑 API 관리로 이동하려면 /start를 입력하세요.",
            parse_mode='Markdown'
        )
        return
    
    try:
        api_key = user_keys.get(f'{exchange}_api_key')
        api_secret = user_keys.get(f'{exchange}_api_secret') or user_keys.get(f'{exchange}_private_key')
        
        trader = UnifiedFuturesTrader(exchange, api_key=api_key, api_secret=api_secret)
        
        # 스팟 시장 데이터 조회
        result = trader.get_spot_market_data(symbol, data_type)
        
        if result.get('status') == 'success':
            data = result.get('data', {})
            
            if data_type == 'ticker':
                # 티커 데이터 포맷팅
                if isinstance(data, list) and len(data) > 0:
                    ticker = data[0]
                    message = f"📊 **{symbol} 스팟 시장 데이터**\n\n"
                    message += f"거래소: {exchange.upper()}\n"
                    message += f"심볼: {symbol}\n"
                    message += f"최신가: {ticker.get('last', 'N/A')}\n"
                    message += f"24h 변동: {ticker.get('change24h', 'N/A')}\n"
                    message += f"거래량: {ticker.get('volume24h', 'N/A')}\n"
                    message += f"고가: {ticker.get('high24h', 'N/A')}\n"
                    message += f"저가: {ticker.get('low24h', 'N/A')}"
                else:
                    message = f"📊 **{symbol} 스팟 시장 데이터**\n\n데이터: {data}"
            elif data_type == 'depth':
                # 깊이 데이터 포맷팅
                message = f"📊 **{symbol} 스팟 호가창 데이터**\n\n"
                message += f"거래소: {exchange.upper()}\n"
                message += f"심볼: {symbol}\n\n"
                message += f"데이터: {data}"
            elif data_type == 'kline':
                # K라인 데이터 포맷팅
                message = f"📊 **{symbol} 스팟 K라인 데이터**\n\n"
                message += f"거래소: {exchange.upper()}\n"
                message += f"심볼: {symbol}\n\n"
                message += f"데이터: {data}"
            else:
                message = f"📊 **{symbol} 스팟 {data_type} 데이터**\n\n{data}"
            
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **스팟 시장 데이터 조회 실패**\n\n{result.get('message', '알 수 없는 오류')}",
                parse_mode='Markdown'
            )
    
    except Exception as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
            parse_mode='Markdown'
        )

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        print(f"🚀 개선된 봇 서버 시작: 포트 {port}")
        print(f"🌐 환경 변수 PORT: {os.environ.get('PORT', '기본값 5000')}")
        print(f"📁 현재 작업 디렉토리: {os.getcwd()}")
        print(f"📋 파일 목록: {os.listdir('.')}")
        
        # Flask 서버 시작
        print("🌐 Flask 서버 시작 중...")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"❌ 서버 시작 오류: {e}")
        import traceback
        print(f"❌ 스택 트레이스: {traceback.format_exc()}") 