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
InlineKeyboardButton = None
InlineKeyboardMarkup = None
print("📝 모든 라이브러리는 필요시 로드됩니다")

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
            "• Hyperliquid\n\n"
            "먼저 API 키를 설정해주세요!"
        )

        await telegram_app.bot.send_message(
            chat_id=chat_id, 
            text=response_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except ImportError:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text="🤖 **암호화폐 선물 거래 봇**\n\n봇이 정상 작동 중입니다!",
            parse_mode='Markdown'
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
        "hyperliquid": "Hyperliquid"
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
    
    # 일반적인 거래 심볼들 (더 많은 심볼 추가)
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
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid",
        "flipster": "Flipster"
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
    direction_text = "📈 롱" if direction == "long" else "📉 숏"
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid",
        "flipster": "Flipster"
    }
    
    # 일반적인 선물 거래 심볼들
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
    direction_text = "📈 롱" if direction == "long" else "📉 숏"
    symbol_display = symbol.replace('_', '/')
    exchange_names = {
        "xt": "XT Exchange",
        "backpack": "Backpack Exchange",
        "hyperliquid": "Hyperliquid",
        "flipster": "Flipster"
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
        "hyperliquid": "Hyperliquid",
        "flipster": "Flipster"
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
        leverage = 1  # 기본값
        if len(parts) > 6:
            market_type = parts[6].lower()  # spot 또는 futures
    
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
        
        if market_type == 'spot':
            # 스팟 거래
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
        [InlineKeyboardButton("XT Exchange", callback_data="trade_exchange_xt")],
        [InlineKeyboardButton("Backpack Exchange", callback_data="trade_exchange_backpack")],
        [InlineKeyboardButton("Hyperliquid", callback_data="trade_exchange_hyperliquid")],
        [InlineKeyboardButton("Flipster", callback_data="trade_exchange_flipster")],
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
        "5. 🔄 거래하기 - 포지션 오픈\n"
        "6. 📊 시장 데이터 - 실시간 시장 정보\n\n"
        "**지원 거래소:**\n"
        "• XT Exchange (선물/스팟)\n"
        "• Backpack Exchange\n"
        "• Hyperliquid\n"
        "• Flipster\n\n"
        "**명령어:**\n"
        "• `/setapi [거래소] [API_KEY] [SECRET_KEY]` - API 키 설정\n"
        "• `/balance [거래소]` - 잔고 조회\n"
        "• `/symbols [거래소]` - 거래쌍 조회\n"
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
            # XT API 베이스 URL (공식 문서 기반)
            self.base_url = "https://sapi.xt.com"  # 공식 API
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
                url = f"{self.base_url}/v4/public/time"
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'message': 'XT API 연결 성공'
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
                    if SigningKey is None:
                        from nacl.signing import SigningKey
                    
                    if self.private_key:
                        self.signing_key = SigningKey(base64.b64decode(self.private_key))
                    
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
                except ImportError:
                    return {
                        'status': 'error',
                        'message': 'pynacl 패키지가 필요합니다'
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
        
        # XT API 서명 생성
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
        try:
            # pynacl 지연 로딩
            if SigningKey is None:
                from nacl.signing import SigningKey
            
            if self.signing_key is None and self.private_key:
                self.signing_key = SigningKey(base64.b64decode(self.private_key))
            
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
        except ImportError:
            raise ImportError("pynacl 패키지가 필요합니다")
        except Exception as e:
            raise Exception(f"Backpack 헤더 생성 오류: {str(e)}")

    def get_futures_balance(self):
        """선물 계좌 잔고 조회"""
        try:
            if self.exchange == 'xt':
                # XT 잔고 조회 - 공식 문서 기반 엔드포인트
                url = f"{self.base_url}/v4/account/balance"
                headers = self._get_headers_xt()
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'balance': data.get('result', {}),
                        'message': 'XT 잔고 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 잔고 조회 실패: {response.status_code}'
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

    def get_futures_symbols(self):
        """선물 거래쌍 조회"""
        try:
            if self.exchange == 'xt':
                # XT 거래쌍 조회 - 공식 문서 기반 엔드포인트
                url = f"{self.base_url}/v4/public/symbols"
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    # 실제 데이터에서 심볼 추출
                    symbols_data = data.get('result', [])
                    symbols = []
                    for symbol_info in symbols_data:
                        if isinstance(symbol_info, dict) and 'symbol' in symbol_info:
                            symbols.append(symbol_info['symbol'])
                    
                    return {
                        'status': 'success',
                        'symbols': symbols,
                        'message': f'XT 거래쌍 {len(symbols)}개 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 거래쌍 조회 실패: {response.status_code}'
                    }
            
            elif self.exchange == 'backpack':
                # Backpack Exchange 실제 지원 심볼들 (API 기반)
                # 실제 형식: BTC_USDC_PERP, ETH_USDC_PERP, SOL_USDC_PERP
                backpack_futures_symbols = [
                    'SOL_USDC_PERP',
                    'BTC_USDC_PERP',
                    'ETH_USDC_PERP',
                    'XRP_USDC_PERP',
                    'SUI_USDC_PERP',
                    'DOGE_USDC_PERP',
                    'JUP_USDC_PERP',
                    'TRUMP_USDC_PERP',
                    'WIF_USDC_PERP',
                    'BERA_USDC_PERP',
                    'LTC_USDC_PERP',
                    'ADA_USDC_PERP',
                    'LINK_USDC_PERP',
                    'IP_USDC_PERP',
                    'HYPE_USDC_PERP',
                    'BNB_USDC_PERP',
                    'AVAX_USDC_PERP',
                    'S_USDC_PERP',
                    'ONDO_USDC_PERP',
                    'KAITO_USDC_PERP',
                    'ARB_USDC_PERP',
                    'ENA_USDC_PERP',
                    'AAVE_USDC_PERP',
                    'DOT_USDC_PERP',
                    'FARTCOIN_USDC_PERP',
                    'NEAR_USDC_PERP',
                    'OP_USDC_PERP',
                    'PENGU_USDC_PERP',
                    'kPEPE_USDC_PERP',
                    'TAO_USDC_PERP',
                    'VIRTUAL_USDC_PERP',
                    'TIA_USDC_PERP',
                    'kBONK_USDC_PERP',
                    'FRAG_USDC_PERP',
                    'PUMP_USDC_PERP',
                    'SEI_USDC_PERP'
                ]
                
                return {
                    'status': 'success',
                    'symbols': backpack_futures_symbols,
                    'message': f'Backpack 선물 거래쌍 {len(backpack_futures_symbols)}개 조회 성공'
                }
            
            elif self.exchange == 'hyperliquid':
                try:
                    # Hyperliquid SDK 지연 로딩
                    from hyperliquid.info import Info
                    from hyperliquid.utils import constants
                    
                    if self.hyperliquid_info is None:
                        self.hyperliquid_info = Info(constants.MAINNET_API_URL, skip_ws=True)
                    
                    # 메타데이터 조회로 사용 가능한 심볼 가져오기
                    meta = self.hyperliquid_info.meta()
                    symbols = []
                    
                    if 'universe' in meta:
                        for asset in meta['universe']:
                            if 'name' in asset:
                                symbols.append(asset['name'])
                    
                    return {
                        'status': 'success',
                        'symbols': symbols,
                        'message': f'Hyperliquid 거래쌍 {len(symbols)}개 조회 성공'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Hyperliquid 거래쌍 조회 실패: {str(e)}'
                    }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'선물 거래쌍 조회 오류: {str(e)}'
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
                    return {
                        'status': 'success',
                        'order_id': data.get('result', {}).get('orderId'),
                        'message': 'XT 롱 포지션 오픈 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 롱 포지션 오픈 실패: {response.status_code}'
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
                    return {
                        'status': 'success',
                        'order_id': data.get('result', {}).get('orderId'),
                        'message': 'XT 숏 포지션 오픈 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 숏 포지션 오픈 실패: {response.status_code}'
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
                url = f"{self.base_url}/v4/order"
                params = {
                    'symbol': symbol,
                    'side': 'buy',
                    'type': order_type,
                    'quantity': size
                }
                
                # 지정가 주문의 경우 가격 추가
                if order_type == 'limit' and price:
                    params['price'] = price
                
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'order_id': data.get('result', {}).get('orderId'),
                        'message': 'XT 스팟 매수 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 스팟 매수 실패: {response.status_code}'
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
            
            elif self.exchange in ['hyperliquid', 'flipster']:
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
                    'quantity': size
                }
                
                # 지정가 주문의 경우 가격 추가
                if order_type == 'limit' and price:
                    params['price'] = price
                
                headers = self._get_headers_xt(params)
                response = requests.post(url, headers=headers, json=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'order_id': data.get('result', {}).get('orderId'),
                        'message': 'XT 스팟 매도 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 스팟 매도 실패: {response.status_code}'
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
                # XT 스팟 잔고 조회 - 공식 문서 기반 엔드포인트
                url = f"{self.base_url}/v4/account/balance"
                headers = self._get_headers_xt()
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'status': 'success',
                        'balance': data.get('result', {}),
                        'message': 'XT 스팟 잔고 조회 성공'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 스팟 잔고 조회 실패: {response.status_code}'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 스팟 잔고 조회 실패: {response.status_code}'
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

    def get_spot_symbols(self):
        """스팟 거래쌍 조회"""
        try:
            if self.exchange == 'xt':
                # XT 스팟 거래쌍 조회 - 공식 문서 기반 엔드포인트
                url = f"{self.spot_base_url}/v4/public/symbols"
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    # API 문서 링크 응답인지 확인
                    if 'result' in data and isinstance(data['result'], dict) and 'openapiDocs' in data['result']:
                        return {
                            'status': 'error',
                            'message': 'XT API 문서 링크 응답 - 실제 엔드포인트 확인 필요'
                        }
                    else:
                        # 실제 데이터에서 심볼 추출
                        symbols_data = data.get('result', [])
                        symbols = []
                        for symbol_data in symbols_data:
                            if isinstance(symbol_data, dict) and 'symbol' in symbol_data:
                                symbols.append(symbol_data['symbol'])
                        
                        return {
                            'status': 'success',
                            'symbols': symbols,
                            'message': f'XT 스팟 거래쌍 {len(symbols)}개 조회 성공'
                        }
                else:
                    return {
                        'status': 'error',
                        'message': f'XT 스팟 거래쌍 조회 실패: {response.status_code}'
                    }
            
            elif self.exchange == 'hyperliquid':
                try:
                    # Hyperliquid SDK 지연 로딩
                    from hyperliquid.info import Info
                    from hyperliquid.utils import constants
                    
                    if self.hyperliquid_info is None:
                        self.hyperliquid_info = Info(constants.MAINNET_API_URL, skip_ws=True)
                    
                    # 메타데이터 조회로 사용 가능한 심볼 가져오기
                    meta = self.hyperliquid_info.meta()
                    symbols = []
                    
                    if 'universe' in meta:
                        for asset in meta['universe']:
                            if 'name' in asset:
                                symbols.append(asset['name'])
                    
                    return {
                        'status': 'success',
                        'symbols': symbols,
                        'message': f'Hyperliquid 스팟 거래쌍 {len(symbols)}개 조회 성공'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': f'Hyperliquid 스팟 거래쌍 조회 실패: {str(e)}'
                    }
            
            else:
                return {
                    'status': 'error',
                    'message': f'{self.exchange.capitalize()}는 스팟 거래쌍 조회를 지원하지 않습니다.'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'스팟 거래쌍 조회 오류: {str(e)}'
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