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
❓ **암호화폐 트레이딩 봇 도움말**

## 🎯 **현재 사용 가능한 기능**

### ✅ **완전 구현된 기능**
- 💰 **잔고 조회**: `/balance` 또는 메뉴 버튼
- 🔑 **API 키 관리**: 추가, 확인, 삭제
- ℹ️ **거래소 정보**: API 지원 여부 확인
- 📈 **현물 거래**: 매수/매도 기능

### 🚧 **개발 중인 기능**
- 📊 **선물 거래**: 레버리지 거래 (준비 중)
- 🔍 **심볼 조회**: 거래 가능 코인 목록 (준비 중)

## 🏪 **지원 거래소**

| 거래소 | 현물 거래 | 선물 거래 | API 키 필요 |
|--------|-----------|-----------|-------------|
| XT Exchange | ✅ | ✅ | API Key + Secret |
| Backpack | ✅ | ✅ | API Key + Private Key |
| Hyperliquid | ❌ | ✅ | API Key + Secret |
| Flipster | ✅ | ✅ | API Key + Secret |

## 📋 **사용 가능한 명령어**

### 💰 **잔고 관련**
```
/balance - 모든 거래소 잔고 조회
```

### 🔑 **API 키 관리**
```
/addapi [거래소] [거래유형] [API_KEY] [API_SECRET/PRIVATE_KEY]
/checkapi [거래소] [거래유형] 또는 /checkapi all
/deleteapi [거래소] [거래유형]
```

### 📈 **현물 거래**
```
/spotbuy [거래소] [심볼] [수량] [가격(선택)] - 현물 매수
/spotsell [거래소] [심볼] [수량] [가격(선택)] - 현물 매도
```

### 📝 **명령어 예시**
```
/addapi backpack spot your_api_key your_private_key
/addapi xt futures your_api_key your_api_secret
/checkapi backpack spot
/balance
/spotbuy backpack BTC 0.001
/spotsell xt ETH 0.1 2100
```

## 🔧 **API 키 설정 방법**

### **Backpack 설정**
1. Backpack 웹사이트에서 API 키 생성
2. `/addapi backpack spot [API_KEY] [PRIVATE_KEY]`
3. `/addapi backpack futures [API_KEY] [PRIVATE_KEY]`

### **XT Exchange 설정**
1. XT 웹사이트에서 API 키 생성
2. `/addapi xt spot [API_KEY] [API_SECRET]`
3. `/addapi xt futures [API_KEY] [API_SECRET]`

### **다른 거래소 설정**
1. 각 거래소 웹사이트에서 API 키 생성
2. `/addapi [거래소] [거래유형] [API_KEY] [API_SECRET]`

## ⚠️ **중요 안내사항**

### **현재 상태**
- ✅ 잔고 조회 기능 완전 작동
- ✅ API 키 관리 기능 완전 작동
- ✅ 현물 거래 기능 완전 작동
- 🚧 선물 거래 기능은 개발 중 (준비 중)

### **보안**
- 모든 API 키는 암호화되어 저장
- 채널 멤버만 봇 사용 가능
- API 키는 서버에만 저장, 개발자도 접근 불가

### **사용 제한**
- ✅ 잔고 조회 및 현물 거래 가능
- 🚧 선물 거래는 추후 업데이트 예정
- 각 거래소별 API 지원 여부 확인 필요

## 🚀 **향후 업데이트 예정**

### **1단계 (현재)**
- ✅ 잔고 조회
- ✅ API 키 관리
- ✅ 현물 거래 (매수/매도)

### **2단계 (준비 중)**
- 🔍 심볼 조회
- 📊 선물 거래 (레버리지)

### **3단계 (계획)**
- 🎯 자동 거래 봇
- 📈 고급 차트 분석

## 📞 **지원 및 문의**
- 채널 멤버십 필요
- API 키 설정 문의는 관리자에게
- 버그 리포트는 개발자에게

**💡 현재는 잔고 조회, API 키 관리, 현물 거래가 가능합니다.**
**선물 거래는 개발 완료 후 업데이트됩니다.**
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
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        "💰 **잔고 조회 중...**\n\n"
        "모든 거래소의 잔고를 확인하고 있습니다.",
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
                                        private_key=api_result['private_key']
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
                                        private_key=api_result['private_key']
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
                balance_text += "⚠️ API 키가 설정되지 않음\n"
                balance_text += "─" * 30 + "\n\n"
        
        # 전체 요약
        balance_text += "🎯 **전체 요약**\n"
        balance_text += f"📊 설정된 거래소: {exchange_count}개\n"
        balance_text += f"💰 총 잔고: ${total_balance:,.2f}\n\n"
        balance_text += "💡 모든 거래소의 잔고가 표시됩니다."
        
        await update.message.reply_text(
            balance_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ **잔고 조회 오류**\n\n"
            f"오류: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )



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

async def spot_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현물 매수 명령어"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    try:
        # /spotbuy [거래소] [심볼] [수량] [가격(선택)]
        parts = message_text.split()
        
        if len(parts) < 4:
            await update.message.reply_text(
                "❌ **잘못된 형식**\n\n"
                "올바른 형식:\n"
                "`/spotbuy [거래소] [심볼] [수량] [가격(선택)]`\n\n"
                "**예시:**\n"
                "`/spotbuy backpack BTC 0.001` (시장가 매수)\n"
                "`/spotbuy xt ETH 0.1 2000` (지정가 매수)\n\n"
                "**지원 거래소:** xt, backpack, hyperliquid, flipster",
                parse_mode='Markdown'
            )
            return
        
        exchange = parts[1].lower()
        symbol = parts[2].upper()
        quantity = float(parts[3])
        
        # 가격 파싱 (쉼표 제거)
        price = None
        if len(parts) > 4:
            try:
                # 쉼표 제거 후 파싱
                price_str = parts[4].replace(',', '')
                price = float(price_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ **잘못된 가격 형식**\n\n"
                    "가격은 숫자로 입력하세요. (예: 3688.14 또는 3,688.14)"
                )
                return
        
        # Backpack 심볼 형식 변환
        if exchange == 'backpack':
            # ETH -> ETH-USDC, BTC -> BTC-USDC 등으로 변환
            if symbol in ['ETH', 'BTC', 'SOL', 'ADA', 'DOT', 'LINK', 'UNI', 'AVAX', 'MATIC', 'ATOM']:
                symbol = f"{symbol}-USDC"
            # 이미 USDC가 붙어있지 않은 경우 USDC 추가
            elif not symbol.endswith('USDC') and not symbol.endswith('USD'):
                symbol = f"{symbol}-USDC"
            # USD -> USDC 변환
            elif symbol.endswith('USD'):
                symbol = symbol.replace('USD', 'USDC')
        
        # 거래소 유효성 검사
        valid_exchanges = ['xt', 'backpack', 'hyperliquid', 'flipster']
        if exchange not in valid_exchanges:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래소**\n\n"
                f"지원 거래소: {', '.join(valid_exchanges)}"
            )
            return
        
        # API 키 확인
        if not api_manager.has_api_keys(user_id, exchange, 'spot'):
            await update.message.reply_text(
                f"❌ **API 키가 설정되지 않음**\n\n"
                f"{exchange.capitalize()} 현물 거래용 API 키를 먼저 설정하세요:\n"
                f"`/addapi {exchange} spot [API_KEY] [API_SECRET]`"
            )
            return
        
        # API 키 가져오기
        api_result = api_manager.get_api_keys(user_id, exchange, 'spot')
        if api_result['status'] != 'success':
            await update.message.reply_text(
                f"❌ **API 키 조회 실패**\n\n"
                f"오류: {api_result['message']}"
            )
            return
        
        # 거래자 생성
        if exchange == 'backpack':
            trader = UnifiedSpotTrader(
                exchange=exchange,
                api_key=api_result['api_key'],
                private_key=api_result['private_key']
            )
        else:
            trader = UnifiedSpotTrader(
                exchange=exchange,
                api_key=api_result['api_key'],
                api_secret=api_result['api_secret']
            )
        
        # 매수 주문 실행
        order_type = 'market' if price is None else 'limit'
        result = trader.buy(symbol, price or 0, quantity, 1, order_type)
        
        if isinstance(result, list) and len(result) > 0:
            order_result = result[0]
            if 'error' in str(order_result):
                await update.message.reply_text(
                    f"❌ **매수 주문 실패**\n\n"
                    f"🏪 거래소: {exchange.capitalize()}\n"
                    f"📈 심볼: {symbol}\n"
                    f"📊 수량: {quantity}\n"
                    f"💰 가격: {'시장가' if price is None else f'${price:,.2f}'}\n"
                    f"❌ 오류: {str(order_result)}"
                )
            else:
                await update.message.reply_text(
                    f"✅ **매수 주문 성공!**\n\n"
                    f"🏪 거래소: {exchange.capitalize()}\n"
                    f"📈 심볼: {symbol}\n"
                    f"📊 수량: {quantity}\n"
                    f"💰 가격: {'시장가' if price is None else f'${price:,.2f}'}\n"
                    f"🆔 주문 ID: {order_result.get('orderId', 'N/A')}"
                )
        else:
            await update.message.reply_text(
                f"❌ **매수 주문 실패**\n\n"
                f"오류: {str(result)}"
            )
        
    except ValueError:
        await update.message.reply_text(
            "❌ **잘못된 수량 또는 가격**\n\n"
            "수량과 가격은 숫자로 입력하세요."
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ **매수 주문 오류**\n\n"
            f"오류: {str(e)}"
        )

async def spot_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현물 매도 명령어"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    try:
        # /spotsell [거래소] [심볼] [수량] [가격(선택)]
        parts = message_text.split()
        
        if len(parts) < 4:
            await update.message.reply_text(
                "❌ **잘못된 형식**\n\n"
                "올바른 형식:\n"
                "`/spotsell [거래소] [심볼] [수량] [가격(선택)]`\n\n"
                "**예시:**\n"
                "`/spotsell backpack BTC 0.001` (시장가 매도)\n"
                "`/spotsell xt ETH 0.1 2100` (지정가 매도)\n\n"
                "**지원 거래소:** xt, backpack, hyperliquid, flipster",
                parse_mode='Markdown'
            )
            return

async def get_symbols(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """거래 가능한 심볼 조회 명령어"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    try:
        # /symbols [거래소]
        parts = message_text.split()
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ **잘못된 형식**\n\n"
                "올바른 형식: `/symbols [거래소]`\n\n"
                "**예시:**\n"
                "`/symbols backpack`\n"
                "`/symbols xt`\n\n"
                "**지원 거래소:** xt, backpack, hyperliquid, flipster",
                parse_mode='Markdown'
            )
            return
        
        exchange = parts[1].lower()
        
        # 거래소 유효성 검사
        valid_exchanges = ['xt', 'backpack', 'hyperliquid', 'flipster']
        if exchange not in valid_exchanges:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래소**\n\n"
                f"지원 거래소: {', '.join(valid_exchanges)}"
            )
            return
        
        # API 키 확인 (선택사항)
        has_api = api_manager.has_api_keys(user_id, exchange, 'spot')
        
        if has_api:
            # API 키가 있으면 실제 심볼 조회
            api_result = api_manager.get_api_keys(user_id, exchange, 'spot')
            if api_result['status'] == 'success':
                # 거래자 생성
                if exchange == 'backpack':
                    trader = UnifiedSpotTrader(
                        exchange=exchange,
                        api_key=api_result['api_key'],
                        private_key=api_result['private_key']
                    )
                else:
                    trader = UnifiedSpotTrader(
                        exchange=exchange,
                        api_key=api_result['api_key'],
                        api_secret=api_result['api_secret']
                    )
                
                # 심볼 조회
                symbols_result = trader.get_all_symbols()
                
                if isinstance(symbols_result, list) and len(symbols_result) > 0:
                    # 상위 20개만 표시
                    top_symbols = symbols_result[:20]
                    symbols_text = f"📊 **{exchange.capitalize()} 거래 가능 심볼** (상위 20개)\n\n"
                    
                    for i, symbol in enumerate(top_symbols, 1):
                        symbols_text += f"{i:2d}. {symbol}\n"
                    
                    if len(symbols_result) > 20:
                        symbols_text += f"\n... 및 {len(symbols_result) - 20}개 더"
                    
                    symbols_text += f"\n\n💡 총 {len(symbols_result)}개의 심볼이 거래 가능합니다."
                else:
                    symbols_text = f"❌ **심볼 조회 실패**\n\n"
                    symbols_text += f"오류: {str(symbols_result)}"
            else:
                symbols_text = f"❌ **API 키 조회 실패**\n\n"
                symbols_text += f"오류: {api_result['message']}"
        else:
            # API 키가 없으면 기본 심볼 목록 제공
            if exchange == 'backpack':
                symbols_text = f"📊 **{exchange.capitalize()} 주요 거래 심볼**\n\n"
                symbols_text += "💡 API 키를 설정하면 전체 심볼 목록을 확인할 수 있습니다.\n\n"
                symbols_text += "**주요 심볼:**\n"
                symbols_text += "• SOL-USDC\n"
                symbols_text += "• ETH-USDC\n"
                symbols_text += "• BTC-USDC\n"
                symbols_text += "• BONK-USDC\n"
                symbols_text += "• JUP-USDC\n"
                symbols_text += "• PYTH-USDC\n"
                symbols_text += "• ORCA-USDC\n"
                symbols_text += "• RAY-USDC\n\n"
                symbols_text += "**API 키 설정:**\n"
                symbols_text += f"`/addapi {exchange} spot [API_KEY] [API_SECRET]`"
            else:
                symbols_text = f"📊 **{exchange.capitalize()} 주요 거래 심볼**\n\n"
                symbols_text += "💡 API 키를 설정하면 전체 심볼 목록을 확인할 수 있습니다.\n\n"
                symbols_text += "**주요 심볼:**\n"
                symbols_text += "• BTC/USDT\n"
                symbols_text += "• ETH/USDT\n"
                symbols_text += "• SOL/USDT\n"
                symbols_text += "• ADA/USDT\n"
                symbols_text += "• DOT/USDT\n\n"
                symbols_text += "**API 키 설정:**\n"
                symbols_text += f"`/addapi {exchange} spot [API_KEY] [API_SECRET]`"
        
        await update.message.reply_text(
            symbols_text,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ **심볼 조회 오류**\n\n"
            f"오류: {str(e)}"
        )
        
        exchange = parts[1].lower()
        symbol = parts[2].upper()
        quantity = float(parts[3])
        
        # 가격 파싱 (쉼표 제거)
        price = None
        if len(parts) > 4:
            try:
                # 쉼표 제거 후 파싱
                price_str = parts[4].replace(',', '')
                price = float(price_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ **잘못된 가격 형식**\n\n"
                    "가격은 숫자로 입력하세요. (예: 3688.14 또는 3,688.14)"
                )
                return
        
        # Backpack 심볼 형식 변환
        if exchange == 'backpack':
            # ETH -> ETH-USDC, BTC -> BTC-USDC 등으로 변환
            if symbol in ['ETH', 'BTC', 'SOL', 'ADA', 'DOT', 'LINK', 'UNI', 'AVAX', 'MATIC', 'ATOM']:
                symbol = f"{symbol}-USDC"
            # 이미 USDC가 붙어있지 않은 경우 USDC 추가
            elif not symbol.endswith('USDC') and not symbol.endswith('USD'):
                symbol = f"{symbol}-USDC"
            # USD -> USDC 변환
            elif symbol.endswith('USD'):
                symbol = symbol.replace('USD', 'USDC')
        
        # 거래소 유효성 검사
        valid_exchanges = ['xt', 'backpack', 'hyperliquid', 'flipster']
        if exchange not in valid_exchanges:
            await update.message.reply_text(
                f"❌ **지원하지 않는 거래소**\n\n"
                f"지원 거래소: {', '.join(valid_exchanges)}"
            )
            return
        
        # API 키 확인
        if not api_manager.has_api_keys(user_id, exchange, 'spot'):
            await update.message.reply_text(
                f"❌ **API 키가 설정되지 않음**\n\n"
                f"{exchange.capitalize()} 현물 거래용 API 키를 먼저 설정하세요:\n"
                f"`/addapi {exchange} spot [API_KEY] [API_SECRET]`"
            )
            return
        
        # API 키 가져오기
        api_result = api_manager.get_api_keys(user_id, exchange, 'spot')
        if api_result['status'] != 'success':
            await update.message.reply_text(
                f"❌ **API 키 조회 실패**\n\n"
                f"오류: {api_result['message']}"
            )
            return
        
        # 거래자 생성
        if exchange == 'backpack':
            trader = UnifiedSpotTrader(
                exchange=exchange,
                api_key=api_result['api_key'],
                private_key=api_result['private_key']
            )
        else:
            trader = UnifiedSpotTrader(
                exchange=exchange,
                api_key=api_result['api_key'],
                api_secret=api_result['api_secret']
            )
        
        # 매도 주문 실행
        order_type = 'market' if price is None else 'limit'
        result = trader.sell(symbol, price or 0, quantity, 1, order_type)
        
        if isinstance(result, list) and len(result) > 0:
            order_result = result[0]
            if 'error' in str(order_result):
                await update.message.reply_text(
                    f"❌ **매도 주문 실패**\n\n"
                    f"🏪 거래소: {exchange.capitalize()}\n"
                    f"📈 심볼: {symbol}\n"
                    f"📊 수량: {quantity}\n"
                    f"💰 가격: {'시장가' if price is None else f'${price:,.2f}'}\n"
                    f"❌ 오류: {str(order_result)}"
                )
            else:
                await update.message.reply_text(
                    f"✅ **매도 주문 성공!**\n\n"
                    f"🏪 거래소: {exchange.capitalize()}\n"
                    f"📈 심볼: {symbol}\n"
                    f"📊 수량: {quantity}\n"
                    f"💰 가격: {'시장가' if price is None else f'${price:,.2f}'}\n"
                    f"🆔 주문 ID: {order_result.get('orderId', 'N/A')}"
                )
        else:
            await update.message.reply_text(
                f"❌ **매도 주문 실패**\n\n"
                f"오류: {str(result)}"
            )
        
    except ValueError:
        await update.message.reply_text(
            "❌ **잘못된 수량 또는 가격**\n\n"
            "수량과 가격은 숫자로 입력하세요."
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ **매도 주문 오류**\n\n"
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
    telegram_app.add_handler(CommandHandler('symbols', get_symbols))
    telegram_app.add_handler(CommandHandler('spotbuy', spot_buy))
    telegram_app.add_handler(CommandHandler('spotsell', spot_sell))
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