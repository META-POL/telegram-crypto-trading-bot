#!/usr/bin/env python3
"""
Railway 배포용 텔레그램 봇
완전히 새로운 구조로 asyncio 문제 해결
"""

import os
import logging
import threading
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from trading_bot_unified import UnifiedSpotTrader
from futures_trader import UnifiedFuturesTrader
from api_key_manager import api_manager
from exchange_info import exchange_info
from user_api_store import init_db

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask 앱 생성 (Railway 헬스체크용)
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({"status": "healthy", "message": "Telegram Bot is running"})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "telegram-crypto-trading-bot"})

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 채널 ID
CHANNEL_ID = -1002751102244

# DB 초기화
init_db()
user_traders = {}

async def is_channel_member(bot, user_id, channel_id):
    """채널 멤버 확인"""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def get_main_menu_keyboard():
    """메인 메뉴 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("💰 잔고 조회", callback_data="balance"),
            InlineKeyboardButton("🏪 거래소 선택", callback_data="select_exchange")
        ],
        [
            InlineKeyboardButton("🔑 API 키 관리", callback_data="manage_api"),
            InlineKeyboardButton("ℹ️ 거래소 정보", callback_data="exchange_info")
        ],
        [
            InlineKeyboardButton("❓ 도움말", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_exchange_selection_keyboard():
    """거래소 선택 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("XT Exchange", callback_data="exchange_xt"),
            InlineKeyboardButton("Backpack", callback_data="exchange_backpack")
        ],
        [
            InlineKeyboardButton("Hyperliquid", callback_data="exchange_hyperliquid"),
            InlineKeyboardButton("Flipster", callback_data="exchange_flipster")
        ],
        [
            InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_exchange_info_keyboard():
    """거래소 정보 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("XT Exchange", callback_data="info_xt"),
            InlineKeyboardButton("Backpack", callback_data="info_backpack")
        ],
        [
            InlineKeyboardButton("Hyperliquid", callback_data="info_hyperliquid"),
            InlineKeyboardButton("Flipster", callback_data="info_flipster")
        ],
        [
            InlineKeyboardButton("Binance", callback_data="info_binance"),
            InlineKeyboardButton("OKX", callback_data="info_okx")
        ],
        [
            InlineKeyboardButton("Bybit", callback_data="info_bybit")
        ],
        [
            InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_api_management_keyboard():
    """API 키 관리 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("➕ API 키 추가", callback_data="add_api"),
            InlineKeyboardButton("📋 API 키 목록", callback_data="list_api")
        ],
        [
            InlineKeyboardButton("🔍 API 키 확인", callback_data="check_api"),
            InlineKeyboardButton("🗑️ API 키 삭제", callback_data="delete_api")
        ],
        [
            InlineKeyboardButton("🔙 메인 메뉴", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_trading_type_keyboard():
    """거래 유형 선택 키보드 생성"""
    keyboard = [
        [
            InlineKeyboardButton("📈 현물 거래", callback_data="trading_spot"),
            InlineKeyboardButton("📊 선물 거래", callback_data="trading_futures")
        ],
        [
            InlineKeyboardButton("🔙 거래소 선택", callback_data="select_exchange")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """봇 시작"""
    welcome_text = """
🤖 **암호화폐 트레이딩 봇**

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
    
    if query.data == "balance":
        user_id = update.effective_user.id
        
        await query.edit_message_text(
            "💰 **잔고 조회 중...**\n\n"
            "모든 거래소의 잔고를 확인하고 있습니다.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
        
        try:
            balance_text = "💰 **전체 잔고 조회 결과**\n\n"
            total_balance = 0
            exchange_count = 0
            
            # 모든 거래소 확인
            exchanges = ['xt', 'backpack', 'hyperliquid', 'flipster']
            trading_types = ['spot', 'futures']
            
            for exchange in exchanges:
                exchange_name = exchange.capitalize()
                exchange_balance = 0
                exchange_has_api = False
                
                for trading_type in trading_types:
                    # API 키 존재 여부 확인
                    if api_manager.has_api_keys(user_id, exchange, trading_type):
                        exchange_has_api = True
                        
                        # API 키 가져오기
                        api_result = api_manager.get_api_keys(user_id, exchange, trading_type)
                        
                        if api_result['status'] == 'success':
                            try:
                                # 거래자 생성
                                if trading_type == 'spot':
                                    if exchange == 'backpack':
                                        # Backpack은 private_key 사용
                                        trader = UnifiedSpotTrader(
                                            exchange=exchange,
                                            api_key=api_result['api_key'],
                                            private_key=api_result['private_key']  # Backpack은 private_key 필드 사용
                                        )
                                    else:
                                        # 다른 거래소는 api_secret 사용
                                        trader = UnifiedSpotTrader(
                                            exchange=exchange,
                                            api_key=api_result['api_key'],
                                            api_secret=api_result['api_secret']
                                        )
                                    balance_result = trader.get_balance()
                                else:  # futures
                                    if exchange == 'backpack':
                                        # Backpack은 private_key 사용
                                        trader = UnifiedFuturesTrader(
                                            exchange=exchange,
                                            api_key=api_result['api_key'],
                                            private_key=api_result['private_key']  # Backpack은 private_key 필드 사용
                                        )
                                    else:
                                        # 다른 거래소는 api_secret 사용
                                        trader = UnifiedFuturesTrader(
                                            exchange=exchange,
                                            api_key=api_result['api_key'],
                                            api_secret=api_result['api_secret']
                                        )
                                    balance_result = trader.get_futures_balance()
                                
                                if balance_result.get('status') == 'success':
                                    balance_data = balance_result.get('balance', {})
                                    
                                    # 디버깅을 위한 로그 추가
                                    logger.info(f"잔고 데이터 - {exchange} {trading_type}: {balance_data}")
                                    
                                    # USDT 잔고 추출 (다양한 응답 구조 처리)
                                    usdt_balance = 0
                                    if isinstance(balance_data, dict):
                                        # 직접 USDT 키가 있는 경우
                                        if 'USDT' in balance_data:
                                            try:
                                                usdt_balance = float(balance_data['USDT'])
                                                logger.info(f"USDT 직접 키에서 추출: {usdt_balance}")
                                            except (ValueError, TypeError):
                                                usdt_balance = 0
                                        # total 객체 안에 USDT가 있는 경우
                                        elif 'total' in balance_data and isinstance(balance_data['total'], dict):
                                            if 'USDT' in balance_data['total']:
                                                try:
                                                    usdt_balance = float(balance_data['total']['USDT'])
                                                    logger.info(f"USDT total 객체에서 추출: {usdt_balance}")
                                                except (ValueError, TypeError):
                                                    usdt_balance = 0
                                        # free 객체 안에 USDT가 있는 경우
                                        elif 'free' in balance_data and isinstance(balance_data['free'], dict):
                                            if 'USDT' in balance_data['free']:
                                                try:
                                                    usdt_balance = float(balance_data['free']['USDT'])
                                                    logger.info(f"USDT free 객체에서 추출: {usdt_balance}")
                                                except (ValueError, TypeError):
                                                    usdt_balance = 0
                                        # available 객체 안에 USDT가 있는 경우 (Backpack)
                                        elif 'available' in balance_data and isinstance(balance_data['available'], dict):
                                            if 'USDT' in balance_data['available']:
                                                try:
                                                    usdt_balance = float(balance_data['available']['USDT'])
                                                    logger.info(f"USDT available 객체에서 추출: {usdt_balance}")
                                                except (ValueError, TypeError):
                                                    usdt_balance = 0
                                    
                                    exchange_balance += usdt_balance
                                    
                                    balance_text += f"🏪 **{exchange_name}** ({trading_type})\n"
                                    balance_text += f"💰 USDT: ${usdt_balance:,.2f}\n\n"
                                    
                            except Exception as e:
                                balance_text += f"🏪 **{exchange_name}** ({trading_type})\n"
                                balance_text += f"❌ 오류: {str(e)[:100]}...\n\n"
                                logger.error(f"잔고 조회 오류 - {exchange} {trading_type}: {str(e)}")
                                logger.error(f"전체 오류 상세: {str(e)}")
                
                if exchange_has_api:
                    total_balance += exchange_balance
                    exchange_count += 1
                    
                    balance_text += f"📊 **{exchange_name} 총 잔고**: ${exchange_balance:,.2f}\n"
                    balance_text += "─" * 30 + "\n\n"
                else:
                    balance_text += f"🏪 **{exchange_name}**\n"
                    balance_text += f"⚠️ API 키가 설정되지 않음\n"
                    balance_text += "─" * 30 + "\n\n"
            
            # 전체 요약
            balance_text += f"🎯 **전체 요약**\n"
            balance_text += f"📊 설정된 거래소: {exchange_count}개\n"
            balance_text += f"💰 총 잔고: ${total_balance:,.2f}\n\n"
            
            if exchange_count == 0:
                balance_text += "💡 API 키를 설정하려면 🔑 API 키 관리를 이용하세요."
            else:
                balance_text += "💡 모든 거래소의 잔고가 표시됩니다."
            
            await query.edit_message_text(
                balance_text,
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ **잔고 조회 오류**\n\n"
                f"오류: {str(e)}",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
    
    elif query.data == "select_exchange":
        await query.edit_message_text(
            "🏪 **거래소 선택**\n\n"
            "사용할 거래소를 선택하세요:",
            reply_markup=get_exchange_selection_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data.startswith("exchange_"):
        exchange = query.data.replace("exchange_", "")
        exchange_names = {
            "xt": "XT Exchange",
            "backpack": "Backpack",
            "hyperliquid": "Hyperliquid",
            "flipster": "Flipster"
        }
        exchange_name = exchange_names.get(exchange, exchange.upper())
        
        # 사용자 컨텍스트에 선택된 거래소 저장
        context.user_data['selected_exchange'] = exchange
        
        await query.edit_message_text(
            f"🏪 **{exchange_name} 선택됨**\n\n"
            f"현재 선택된 거래소: **{exchange_name}**\n\n"
            f"거래 유형을 선택하세요:",
            reply_markup=get_trading_type_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "trading_spot":
        exchange = context.user_data.get('selected_exchange', 'unknown')
        exchange_names = {
            "xt": "XT Exchange",
            "backpack": "Backpack",
            "hyperliquid": "Hyperliquid",
            "flipster": "Flipster"
        }
        exchange_name = exchange_names.get(exchange, exchange.upper())
        
        await query.edit_message_text(
            f"📈 **현물 거래 - {exchange_name}**\n\n"
            f"현재 선택된 거래소: **{exchange_name}**\n"
            f"거래 유형: **현물 거래**\n\n"
            f"**API 키 설정 필요:**\n"
            f"- API Key\n"
            f"- API Secret\n"
            f"- Private Key (Backpack의 경우)\n\n"
            f"관리자에게 문의하여 API 키를 설정하세요.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "trading_futures":
        exchange = context.user_data.get('selected_exchange', 'unknown')
        exchange_names = {
            "xt": "XT Exchange",
            "backpack": "Backpack",
            "hyperliquid": "Hyperliquid",
            "flipster": "Flipster"
        }
        exchange_name = exchange_names.get(exchange, exchange.upper())
        
        await query.edit_message_text(
            f"📊 **선물 거래 - {exchange_name}**\n\n"
            f"현재 선택된 거래소: **{exchange_name}**\n"
            f"거래 유형: **선물 거래**\n\n"
            f"**지원 기능:**\n"
            f"- 롱/숏 포지션 오픈\n"
            f"- 레버리지 설정 (최대 10배)\n"
            f"- 손절매/익절매 주문\n"
            f"- 포지션 관리\n\n"
            f"**API 키 설정 필요:**\n"
            f"- API Key\n"
            f"- API Secret\n"
            f"- Private Key (Backpack의 경우)\n\n"
            f"관리자에게 문의하여 API 키를 설정하세요.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    

    
    elif query.data == "manage_api":
        await query.edit_message_text(
            "🔑 **API 키 관리**\n\n"
            "API 키를 추가, 조회, 삭제할 수 있습니다.\n"
            "모든 API 키는 암호화되어 안전하게 저장됩니다.",
            reply_markup=get_api_management_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "add_api":
        await query.edit_message_text(
            "➕ **API 키 추가**\n\n"
            "API 키를 추가하려면 다음 형식으로 메시지를 보내세요:\n\n"
            "`/addapi [거래소] [거래유형] [API_KEY] [API_SECRET] [PRIVATE_KEY(선택)]`\n\n"
            "**예시:**\n"
            "`/addapi xt spot your_api_key your_api_secret`\n"
            "`/addapi backpack spot your_api_key your_private_key`\n\n"
            "**지원 거래소:** xt, backpack, hyperliquid, flipster\n"
            "**거래 유형:** spot, futures",
            reply_markup=get_api_management_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "list_api":
        user_id = update.effective_user.id
        result = api_manager.list_user_apis(user_id)
        
        if result['status'] == 'success':
            apis = result['apis']
            api_list_text = "📋 **설정된 API 키 목록**\n\n"
            
            for api in apis:
                exchange_name = api['exchange'].capitalize()
                trading_type = api['trading_type']
                created_at = api['created_at'][:10]  # 날짜만 표시
                api_list_text += f"🏪 **{exchange_name}** ({trading_type})\n"
                api_list_text += f"📅 설정일: {created_at}\n\n"
            
            api_list_text += "💡 API 키는 암호화되어 저장됩니다."
        else:
            api_list_text = f"❌ **API 키 목록 조회 실패**\n\n{result['message']}"
        
        await query.edit_message_text(
            api_list_text,
            reply_markup=get_api_management_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "check_api":
        await query.edit_message_text(
            "🔍 **API 키 확인**\n\n"
            "API 키를 확인하려면 다음 형식으로 메시지를 보내세요:\n\n"
            "`/checkapi [거래소] [거래유형]`\n\n"
            "**예시:**\n"
            "`/checkapi xt spot`\n"
            "`/checkapi backpack futures`\n\n"
            "**모든 API 키 확인:**\n"
            "`/checkapi all`\n\n"
            "💡 API 키는 보안상 마스킹 처리되어 표시됩니다.",
            reply_markup=get_api_management_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "delete_api":
        await query.edit_message_text(
            "🗑️ **API 키 삭제**\n\n"
            "API 키를 삭제하려면 다음 형식으로 메시지를 보내세요:\n\n"
            "`/deleteapi [거래소] [거래유형]`\n\n"
            "**예시:**\n"
            "`/deleteapi xt spot`\n"
            "`/deleteapi backpack futures`\n\n"
            "⚠️ 삭제된 API 키는 복구할 수 없습니다.",
            reply_markup=get_api_management_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "main_menu":
        await query.edit_message_text(
            "🤖 **암호화폐 트레이딩 봇**\n\n원하는 기능을 선택하세요:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "exchange_info":
        await query.edit_message_text(
            "ℹ️ **거래소 정보**\n\n"
            "아래에서 거래소를 선택하세요:",
            reply_markup=get_exchange_info_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data.startswith("info_"):
        exchange = query.data.replace("info_", "")
        info_text = exchange_info.format_exchange_info(exchange)
        await query.edit_message_text(
            info_text,
            reply_markup=get_exchange_info_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "help":
        help_text = """
❓ **도움말**

**지원 기능:**
- 💰 잔고 조회
- 🏪 거래소 선택
- 📈 현물 거래
- 📊 선물 거래
- 🔑 API 키 관리

**지원 거래소:**
- XT Exchange
- Backpack Exchange
- Hyperliquid
- Flipster

**거래 유형:**
- **현물 거래**: 실제 암호화폐 구매/판매
- **선물 거래**: 레버리지 거래, 롱/숏 포지션

**사용법:**
1. 거래소 선택
2. 거래 유형 선택 (현물/선물)
3. API 키 설정 (관리자 문의)
4. 거래하고 싶은 토큰 심볼을 직접 입력

**API 키 관리:**
- `/addapi` - API 키 추가
- `/checkapi` - API 키 확인
- `/deleteapi` - API 키 삭제
- 🔑 메뉴에서 API 키 관리
- 모든 API 키는 암호화 저장

**토큰 심볼 예시:**
- BTC (비트코인)
- ETH (이더리움)
- SOL (솔라나)
- USDC (USD 코인)

**API 키 필요사항:**
- XT: API Key, API Secret
- Backpack: API Key, Private Key
- Hyperliquid: API Key, API Secret
- Flipster: API Key, API Secret

**선물 거래 기능:**
- 레버리지 설정 (최대 10배)
- 롱/숏 포지션 오픈
- 손절매/익절매 주문
- 포지션 관리

**주의사항:**
- 채널 멤버만 사용 가능
- API 키는 안전하게 암호화 저장
- 각 거래소에서 지원하는 토큰만 거래 가능
- 선물 거래는 고위험 투자입니다
        """
        await query.edit_message_text(
            help_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    
    else:
        await query.edit_message_text(
            "🤖 **암호화폐 트레이딩 봇**\n\n원하는 기능을 선택하세요:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """잔고 조회 명령어"""
    await start(update, context)



async def add_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """API 키 추가 명령어"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    try:
        # /addapi [거래소] [거래유형] [API_KEY] [API_SECRET] [PRIVATE_KEY(선택)]
        parts = message_text.split()
        
        if len(parts) < 5:
            await update.message.reply_text(
                "❌ **잘못된 형식**\n\n"
                "올바른 형식: `/addapi [거래소] [거래유형] [API_KEY] [API_SECRET/PRIVATE_KEY]`\n\n"
                "**예시:**\n"
                "`/addapi xt spot your_api_key your_api_secret`\n"
                "`/addapi backpack spot your_api_key your_private_key`\n\n"
                "💡 **Backpack**: 4번째 파라미터는 Private Key\n"
                "💡 **다른 거래소**: 4번째 파라미터는 API Secret",
                parse_mode='Markdown'
            )
            return
        
        exchange = parts[1].lower()
        trading_type = parts[2].lower()
        api_key = parts[3]
        
        # Backpack의 경우 4번째 파라미터가 private_key
        if exchange == 'backpack':
            private_key = parts[4] if len(parts) > 4 else None
            api_secret = None
        else:
            # 다른 거래소는 4번째 파라미터가 api_secret
            api_secret = parts[4] if len(parts) > 4 else None
            private_key = parts[5] if len(parts) > 5 else None
        
        # 거래소 유효성 검사
        valid_exchanges = ['xt', 'backpack', 'hyperliquid', 'flipster']
        if exchange not in valid_exchanges:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래소**\n\n"
                f"지원 거래소: {', '.join(valid_exchanges)}"
            )
            return
        
        # 거래 유형 유효성 검사
        valid_types = ['spot', 'futures']
        if trading_type not in valid_types:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래 유형**\n\n"
                f"지원 유형: {', '.join(valid_types)}"
            )
            return
        
        # API 키 저장
        result = api_manager.save_api_keys(
            user_id, exchange, trading_type, api_key, api_secret, private_key
        )
        
        if result['status'] == 'success':
            await update.message.reply_text(
                f"✅ **API 키 저장 성공!**\n\n"
                f"{result['message']}\n\n"
                f"거래소: {exchange.capitalize()}\n"
                f"거래 유형: {trading_type}\n\n"
                f"💡 이제 실제 거래 기능을 사용할 수 있습니다."
            )
        else:
            await update.message.reply_text(
                f"❌ **API 키 저장 실패**\n\n"
                f"오류: {result['message']}"
            )
            
    except Exception as e:
        await update.message.reply_text(
            f"❌ **API 키 추가 오류**\n\n"
            f"오류: {str(e)}"
        )

async def delete_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """API 키 삭제 명령어"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    try:
        # /deleteapi [거래소] [거래유형]
        parts = message_text.split()
        
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ **잘못된 형식**\n\n"
                "올바른 형식: `/deleteapi [거래소] [거래유형]`\n\n"
                "**예시:**\n"
                "`/deleteapi xt spot`\n"
                "`/deleteapi backpack futures`",
                parse_mode='Markdown'
            )
            return
        
        exchange = parts[1].lower()
        trading_type = parts[2].lower()
        
        # 거래소 유효성 검사
        valid_exchanges = ['xt', 'backpack', 'hyperliquid', 'flipster']
        if exchange not in valid_exchanges:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래소**\n\n"
                f"지원 거래소: {', '.join(valid_exchanges)}"
            )
            return
        
        # 거래 유형 유효성 검사
        valid_types = ['spot', 'futures']
        if trading_type not in valid_types:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래 유형**\n\n"
                f"지원 유형: {', '.join(valid_types)}"
            )
            return
        
        # API 키 삭제
        result = api_manager.delete_api_keys(user_id, exchange, trading_type)
        
        if result['status'] == 'success':
            await update.message.reply_text(
                f"✅ **API 키 삭제 성공!**\n\n"
                f"{result['message']}\n\n"
                f"거래소: {exchange.capitalize()}\n"
                f"거래 유형: {trading_type}"
            )
        else:
            await update.message.reply_text(
                f"❌ **API 키 삭제 실패**\n\n"
                f"오류: {result['message']}"
            )
            
    except Exception as e:
        await update.message.reply_text(
            f"❌ **API 키 삭제 오류**\n\n"
            f"오류: {str(e)}"
        )

async def check_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """API 키 확인 명령어"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    try:
        # /checkapi [거래소] [거래유형]
        parts = message_text.split()
        
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ **잘못된 형식**\n\n"
                "올바른 형식: `/checkapi [거래소] [거래유형]`\n\n"
                "**예시:**\n"
                "`/checkapi xt spot`\n"
                "`/checkapi backpack futures`\n\n"
                "**또는 모든 API 키 확인:**\n"
                "`/checkapi all`",
                parse_mode='Markdown'
            )
            return
        
        exchange = parts[1].lower()
        trading_type = parts[2].lower()
        
        # 모든 API 키 확인
        if exchange == 'all':
            result = api_manager.list_user_apis(user_id)
            
            if result['status'] == 'success':
                apis = result['apis']
                api_list_text = "🔍 **설정된 API 키 목록**\n\n"
                
                for api in apis:
                    exchange_name = api['exchange'].capitalize()
                    trading_type = api['trading_type']
                    created_at = api['created_at'][:10]
                    updated_at = api['updated_at'][:10]
                    api_list_text += f"🏪 **{exchange_name}** ({trading_type})\n"
                    api_list_text += f"📅 설정일: {created_at}\n"
                    api_list_text += f"📝 수정일: {updated_at}\n\n"
                
                api_list_text += "💡 API 키는 보안상 마스킹 처리되어 표시됩니다."
                
                await update.message.reply_text(
                    api_list_text,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ **API 키 목록 조회 실패**\n\n"
                    f"오류: {result['message']}"
                )
            return
        
        # 거래소 유효성 검사
        valid_exchanges = ['xt', 'backpack', 'hyperliquid', 'flipster']
        if exchange not in valid_exchanges:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래소**\n\n"
                f"지원 거래소: {', '.join(valid_exchanges)}"
            )
            return
        
        # 거래 유형 유효성 검사
        valid_types = ['spot', 'futures']
        if trading_type not in valid_types:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래 유형**\n\n"
                f"지원 유형: {', '.join(valid_types)}"
            )
            return
        
        # API 키 조회
        result = api_manager.get_api_keys(user_id, exchange, trading_type)
        
        if result['status'] == 'success':
            api_key = result['api_key']
            api_secret = result['api_secret']
            private_key = result['private_key']
            
            # API 키 마스킹 처리
            masked_api_key = _mask_api_key(api_key)
            masked_api_secret = _mask_api_key(api_secret) if api_secret else None
            masked_private_key = _mask_api_key(private_key) if private_key else None
            
            check_text = f"🔍 **{exchange.capitalize()} {trading_type} API 키 확인**\n\n"
            check_text += f"🏪 **거래소**: {exchange.capitalize()}\n"
            check_text += f"📊 **거래 유형**: {trading_type}\n\n"
            check_text += f"🔑 **API Key**: `{masked_api_key}`\n"
            
            if masked_api_secret:
                check_text += f"🔐 **API Secret**: `{masked_api_secret}`\n"
            
            if masked_private_key:
                check_text += f"🔒 **Private Key**: `{masked_private_key}`\n"
            
            check_text += f"\n💡 **보안 정보**:\n"
            check_text += f"• API 키는 암호화되어 저장됩니다\n"
            check_text += f"• 실제 키는 마스킹 처리되어 표시됩니다\n"
            check_text += f"• 키의 앞 4자리와 뒤 4자리만 표시됩니다"
            
            await update.message.reply_text(
                check_text,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ **API 키 확인 실패**\n\n"
                f"오류: {result['message']}"
            )
            
    except Exception as e:
        await update.message.reply_text(
            f"❌ **API 키 확인 오류**\n\n"
            f"오류: {str(e)}"
        )

def _mask_api_key(api_key):
    """API 키 마스킹 처리"""
    if not api_key or len(api_key) < 8:
        return "****"
    
    return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"

def run_telegram_bot():
    """텔레그램 봇 실행 함수"""
    # 환경 변수 확인
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN':
        print("❌ TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        print("Railway 대시보드에서 환경 변수를 설정하세요.")
        return
    
    print("🤖 텔레그램 봇 시작 중...")
    
    # 애플리케이션 빌드
    telegram_app = ApplicationBuilder().token(token).build()
    
    # 핸들러 등록
    telegram_app.add_handler(CommandHandler('start', start))
    telegram_app.add_handler(CommandHandler('balance', balance))
    telegram_app.add_handler(CommandHandler('addapi', add_api))
    telegram_app.add_handler(CommandHandler('deleteapi', delete_api))
    telegram_app.add_handler(CommandHandler('checkapi', check_api))
    telegram_app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ 텔레그램 봇이 성공적으로 시작되었습니다!")
    print("🔄 폴링 시작...")
    
    try:
        # 폴링 시작
        telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ 텔레그램 봇 오류: {e}")

def run_flask_server():
    """Flask 서버 실행 함수"""
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Flask 서버 시작 중... 포트: {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def main():
    """메인 함수 - 텔레그램 봇을 메인 스레드에서 실행"""
    # Flask 서버를 별도 스레드에서 실행
    flask_thread = threading.Thread(target=run_flask_server)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 텔레그램 봇을 메인 스레드에서 실행
    run_telegram_bot()

if __name__ == '__main__':
    main() 