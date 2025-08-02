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
from datetime import datetime
from flask import Flask, jsonify, request

# 라이브러리 import
try:
    from nacl.signing import SigningKey
    print("✅ pynacl 라이브러리 로드 성공")
except ImportError:
    SigningKey = None
    print("⚠️ pynacl 라이브러리 로드 실패 (선택적 기능)")

try:
    import ccxt
    print("✅ ccxt 라이브러리 로드 성공")
except ImportError:
    ccxt = None
    print("⚠️ ccxt 라이브러리 로드 실패 (선택적 기능)")

# 텔레그램 라이브러리 import
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    print("✅ telegram 라이브러리 로드 성공")
except ImportError:
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    print("⚠️ telegram 라이브러리 로드 실패")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                flipster_api_key TEXT,
                flipster_api_secret TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                'hyperliquid_api_secret': result[6],
                'flipster_api_key': result[7],
                'flipster_api_secret': result[8]
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
            elif exchange == 'flipster':
                cursor.execute('''
                    UPDATE user_api_keys 
                    SET flipster_api_key = ?, flipster_api_secret = ?, updated_at = CURRENT_TIMESTAMP 
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
            elif exchange == 'flipster':
                cursor.execute('''
                    INSERT INTO user_api_keys (user_id, flipster_api_key, flipster_api_secret)
                    VALUES (?, ?, ?)
                ''', (user_id, api_key, api_secret))
        
        conn.commit()
        conn.close()
        print(f"✅ API 키 저장 완료: {exchange} for user {user_id}")
    except Exception as e:
        print(f"⚠️ API 키 저장 오류: {e}")

@app.route('/')
def health_check():
    return jsonify({
        "status": "healthy", 
        "message": "Enhanced Telegram Crypto Futures Trading Bot",
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
                        
                    elif text.startswith('/symbols'):
                        await handle_symbols_command(telegram_app, chat_id, user_id, text)
                        
                    elif text.startswith('/positions'):
                        await handle_positions_command(telegram_app, chat_id, user_id, text)
                        
                    elif text.startswith('/trade'):
                        await handle_trade_command(telegram_app, chat_id, user_id, text)
                        
                    elif text.startswith('/close'):
                        await handle_close_command(telegram_app, chat_id, user_id, text)
                        
                    elif text == '/help':
                        await show_help(telegram_app, chat_id)
                        
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
    
    keyboard = [
        [InlineKeyboardButton("🔑 API 키 관리", callback_data="api_management")],
        [InlineKeyboardButton("💰 잔고 조회", callback_data="balance_menu")],
        [InlineKeyboardButton("📈 거래쌍 조회", callback_data="symbols_menu")],
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
            
        elif data == "symbols_menu":
            await show_symbols_menu(telegram_app, chat_id, user_id, callback_query)
            
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
            
        elif data.startswith("symbols_"):
            await handle_symbols_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("position_"):
            await handle_position_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data.startswith("trade_"):
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data in ["position_list", "position_close"]:
            await handle_position_callback(telegram_app, chat_id, user_id, data, callback_query)
            
        elif data in ["trade_long", "trade_short"]:
            await handle_trade_callback(telegram_app, chat_id, user_id, data, callback_query)
        
        # 콜백 쿼리 응답
        await callback_query.answer()
        
    except Exception as e:
        print(f"❌ 콜백 쿼리 처리 오류: {e}")
        await callback_query.answer("❌ 오류가 발생했습니다.")

async def handle_api_callback(telegram_app, chat_id, user_id, data, callback_query):
    """API 관련 콜백 처리"""
    exchange = data.replace("api_", "")
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange", 
        "hyperliquid": "Hyperliquid",
        "flipster": "Flipster"
    }
    
    user_keys = get_user_api_keys(user_id)
    
    if user_keys and user_keys.get(f'{exchange}_api_key'):
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
        # API 키가 설정되지 않은 경우
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"🔑 **{exchange_names[exchange]} API 설정**\n\n"
                 f"다음 형식으로 API 키를 입력하세요:\n\n"
                 f"`/setapi {exchange} YOUR_API_KEY YOUR_SECRET_KEY`\n\n"
                 f"예시:\n"
                 f"`/setapi {exchange} abc123def456 ghi789jkl012`\n\n"
                 f"⚠️ **주의:** API 키는 안전하게 저장됩니다.\n\n"
                 f"🔙 API 관리로 돌아가려면 /start를 입력하세요.",
            parse_mode='Markdown'
        )

async def handle_balance_callback(telegram_app, chat_id, user_id, data, callback_query):
    """잔고 조회 콜백 처리"""
    exchange = data.replace("balance_", "")
    user_keys = get_user_api_keys(user_id)
    
    if not user_keys or not user_keys.get(f'{exchange}_api_key'):
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
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
                for currency, amount in balance_data.items():
                    if isinstance(amount, dict) and 'available' in amount:
                        available = amount.get('available', 0)
                        if float(available) > 0:
                            formatted_balance += f"💰 {currency}: {available}\n"
                    elif isinstance(amount, (int, float)) and float(amount) > 0:
                        formatted_balance += f"💰 {currency}: {amount}\n"
                
                if not formatted_balance:
                    formatted_balance = "사용 가능한 잔고가 없습니다."
                else:
                    formatted_balance = str(balance_data)
            
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
        else:
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=f"❌ **잔고 조회 실패**\n\n오류: {result.get('message', '알 수 없는 오류')}",
                parse_mode='Markdown'
            )
    except Exception as e:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
            parse_mode='Markdown'
        )

async def handle_symbols_callback(telegram_app, chat_id, user_id, data, callback_query):
    """거래쌍 조회 콜백 처리"""
    exchange = data.replace("symbols_", "")
    user_keys = get_user_api_keys(user_id)
    
    if not user_keys or not user_keys.get(f'{exchange}_api_key'):
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
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
        result = trader.get_futures_symbols()
        
        if result.get('status') == 'success':
            symbols_data = result.get('symbols', [])
            
            # 심볼 목록을 보기 좋게 포맷팅 (최대 20개만 표시)
            symbols_text = f"📈 **{exchange.upper()} 거래쌍** ({len(symbols_data)}개)\n\n"
            for i, symbol in enumerate(symbols_data[:20], 1):
                symbols_text += f"{i}. {symbol}\n"
            
            if len(symbols_data) > 20:
                symbols_text += f"\n... 및 {len(symbols_data) - 20}개 더"
            
            keyboard = [
                [InlineKeyboardButton("🔄 새로고침", callback_data=data)],
                [InlineKeyboardButton("🔙 거래쌍 메뉴", callback_data="symbols_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=symbols_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await telegram_app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback_query.message.message_id,
                text=f"❌ **거래쌍 조회 실패**\n\n오류: {result.get('message', '알 수 없는 오류')}",
                parse_mode='Markdown'
            )
    except Exception as e:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
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
        [InlineKeyboardButton("Flipster", callback_data="position_list_flipster")],
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
        [InlineKeyboardButton("Flipster", callback_data="position_close_flipster")],
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
    if data == "trade_long":
        await show_trade_setup_menu(telegram_app, chat_id, user_id, "long", callback_query)
    elif data == "trade_short":
        await show_trade_setup_menu(telegram_app, chat_id, user_id, "short", callback_query)

async def show_trade_setup_menu(telegram_app, chat_id, user_id, trade_type, callback_query):
    """거래 설정 메뉴 표시"""
    trade_type_text = "📈 롱" if trade_type == "long" else "📉 숏"
    
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data=f"trade_{trade_type}_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data=f"trade_{trade_type}_backpack")],
        [InlineKeyboardButton("Hyperliquid", callback_data=f"trade_{trade_type}_hyperliquid")],
        [InlineKeyboardButton("Flipster", callback_data=f"trade_{trade_type}_flipster")],
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
                for currency, amount in balance_data.items():
                    if isinstance(amount, dict) and 'available' in amount:
                        available = amount.get('available', 0)
                        if float(available) > 0:
                            formatted_balance += f"💰 {currency}: {available}\n"
                    elif isinstance(amount, (int, float)) and float(amount) > 0:
                        formatted_balance += f"💰 {currency}: {amount}\n"
                
                if not formatted_balance:
                    formatted_balance = "사용 가능한 잔고가 없습니다."
                else:
                    formatted_balance = str(balance_data)
            
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

async def handle_symbols_command(telegram_app, chat_id, user_id, text):
    """거래쌍 조회 명령어 처리"""
    parts = text.split()
    if len(parts) < 2:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법: /symbols [거래소]\n\n예시: `/symbols xt`",
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
        result = trader.get_futures_symbols()
        
        if result.get('status') == 'success':
            symbols_data = result.get('symbols', [])
            
            # 심볼 목록을 보기 좋게 포맷팅 (최대 20개만 표시)
            symbols_text = f"📈 **{exchange.upper()} 거래쌍** ({len(symbols_data)}개)\n\n"
            for i, symbol in enumerate(symbols_data[:20], 1):
                symbols_text += f"{i}. {symbol}\n"
            
            if len(symbols_data) > 20:
                symbols_text += f"\n... 및 {len(symbols_data) - 20}개 더"
            
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=symbols_text,
                parse_mode='Markdown'
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **거래쌍 조회 실패**\n\n오류: {result.get('message', '알 수 없는 오류')}",
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
    if len(parts) < 6:
        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text="❌ 사용법: /trade [거래소] [심볼] [방향] [수량] [레버리지]\n\n"
                 "예시: `/trade xt BTCUSDT long 0.001 10`",
            parse_mode='Markdown'
        )
        return
    
    exchange = parts[1].lower()
    symbol = parts[2].upper()
    direction = parts[3].lower()
    size = float(parts[4])
    leverage = int(parts[5])
    
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
        
        if direction == 'long':
            result = trader.open_long_position(symbol, size, leverage)
        elif direction == 'short':
            result = trader.open_short_position(symbol, size, leverage)
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text="❌ **잘못된 방향**\n\n방향은 'long' 또는 'short'이어야 합니다.",
                parse_mode='Markdown'
            )
            return
        
        if result.get('status') == 'success':
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"✅ **{direction.upper()} 포지션 오픈 성공**\n\n"
                     f"거래소: {exchange.upper()}\n"
                     f"심볼: {symbol}\n"
                     f"수량: {size}\n"
                     f"레버리지: {leverage}배\n"
                     f"주문 ID: {result.get('order_id', 'N/A')}",
                parse_mode='Markdown'
            )
        else:
            await telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **포지션 오픈 실패**\n\n오류: {result.get('message', '알 수 없는 오류')}",
                parse_mode='Markdown'
            )
    except Exception as e:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **오류 발생**\n\n{str(e)}",
            parse_mode='Markdown'
        )

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
    
    # 사용자 API 키 상태 확인
    user_keys = get_user_api_keys(user_id)
    
    keyboard = []
    exchanges = [
        ("xt", "XT Exchange"),
        ("backpack", "Backpack Exchange"),
        ("hyperliquid", "Hyperliquid"),
        ("flipster", "Flipster")
    ]
    
    for exchange, name in exchanges:
        if user_keys and user_keys.get(f'{exchange}_api_key'):
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
    
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data="balance_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data="balance_backpack")],
        [InlineKeyboardButton("Hyperliquid", callback_data="balance_hyperliquid")],
        [InlineKeyboardButton("Flipster", callback_data="balance_flipster")],
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
            
async def show_symbols_menu(telegram_app, chat_id, user_id, callback_query=None):
    """거래쌍 조회 메뉴 표시"""
    
    keyboard = [
        [InlineKeyboardButton("XT Exchange", callback_data="symbols_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data="symbols_backpack")],
        [InlineKeyboardButton("Hyperliquid", callback_data="symbols_hyperliquid")],
        [InlineKeyboardButton("Flipster", callback_data="symbols_flipster")],
        [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text="📈 **거래쌍 조회**\n\n거래소를 선택하여 거래 가능한 심볼을 조회하세요.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text="📈 **거래쌍 조회**\n\n거래소를 선택하여 거래 가능한 심볼을 조회하세요.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def show_position_menu(telegram_app, chat_id, user_id, callback_query=None):
    """포지션 관리 메뉴 표시"""
    
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
    
    keyboard = [
        [InlineKeyboardButton("📈 롱 포지션", callback_data="trade_long")],
        [InlineKeyboardButton("📉 숏 포지션", callback_data="trade_short")],
        [InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if callback_query:
        await telegram_app.bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text="🔄 **거래하기**\n\n포지션을 오픈할 수 있습니다.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text="🔄 **거래하기**\n\n포지션을 오픈할 수 있습니다.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def show_settings_menu(telegram_app, chat_id, user_id, callback_query=None):
    """설정 메뉴 표시"""
    
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
    help_text = (
        "❓ **도움말**\n\n"
        "**사용 방법:**\n"
        "1. 🔑 API 키 관리 - 거래소 API 키 설정\n"
        "2. 💰 잔고 조회 - 계좌 잔고 확인\n"
        "3. 📈 거래쌍 조회 - 거래 가능한 심볼 확인\n"
        "4. 📊 포지션 관리 - 포지션 조회/종료\n"
        "5. 🔄 거래하기 - 포지션 오픈\n\n"
        "**지원 거래소:**\n"
        "• XT Exchange\n"
        "• Backpack Exchange\n"
        "• Hyperliquid\n"
        "• Flipster\n\n"
        "**명령어:**\n"
        "• `/setapi [거래소] [API_KEY] [SECRET_KEY]` - API 키 설정\n"
        "• `/balance [거래소]` - 잔고 조회\n"
        "• `/symbols [거래소]` - 거래쌍 조회\n"
        "• `/positions [거래소]` - 포지션 조회\n"
        "• `/trade [거래소] [심볼] [방향] [수량] [레버리지]` - 거래\n"
        "• `/close [거래소] [심볼]` - 포지션 종료"
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
            self.base_url = "https://sapi.xt.com"
        elif self.exchange == 'backpack':
            self.api_key = kwargs.get('api_key')
            self.private_key = kwargs.get('private_key') or kwargs.get('api_secret')
            self.base_url = "https://api.backpack.exchange/api/v1"
            if SigningKey and self.private_key:
                self.signing_key = SigningKey(base64.b64decode(self.private_key))
            else:
                raise ImportError("pynacl 패키지가 필요하거나 private_key가 설정되지 않았습니다.")
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
                # Backpack Exchange API 연결 테스트 - 계좌 정보 조회
                url = f"{self.base_url}/account"
                headers = self._get_headers_backpack("accountQuery")
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
                # Backpack Exchange 잔고 조회 - /capital 엔드포인트 사용
                url = f"{self.base_url}/capital"
                headers = self._get_headers_backpack("balanceQuery")
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