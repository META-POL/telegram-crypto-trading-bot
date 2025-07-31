#!/usr/bin/env python3
"""
API 키 없이 테스트할 수 있는 모의 테스트 모드
"""

import time
import random
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockTrader:
    """모의 거래 클래스 - API 키 없이 테스트 가능"""
    
    def __init__(self, exchange, **kwargs):
        self.exchange = exchange.lower()
        self.is_test_mode = True
        self.mock_balance = {
            'USDT': 10000.0,
            'BTC': 0.5,
            'ETH': 5.0,
            'SOL': 100.0,
            'USDC': 5000.0
        }
        self.mock_positions = []
        self.mock_orders = []
        
        # 거래소별 더미 데이터
        self.exchange_data = {
            'xt': {
                'name': 'XT Exchange',
                'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT', 'DOT/USDT'],
                'fees': 0.001
            },
            'backpack': {
                'name': 'Backpack',
                'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
                'fees': 0.0005
            },
            'hyperliquid': {
                'name': 'Hyperliquid',
                'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'MATIC/USDT', 'AVAX/USDT'],
                'fees': 0.0002
            },
            'flipster': {
                'name': 'Flipster',
                'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'LINK/USDT', 'UNI/USDT'],
                'fees': 0.0008
            }
        }

    def get_balance(self):
        """모의 잔고 조회"""
        try:
            time.sleep(0.5)  # 실제 API 호출 시뮬레이션
            
            balance_text = f"💰 **{self.exchange_data[self.exchange]['name']} 잔고**\n\n"
            for currency, amount in self.mock_balance.items():
                if amount > 0:
                    balance_text += f"**{currency}**: {amount:,.4f}\n"
            
            balance_text += f"\n💡 **테스트 모드** - 실제 잔고가 아닙니다"
            
            return {
                'status': 'success',
                'balance': self.mock_balance,
                'message': balance_text
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'잔고 조회 오류: {str(e)}'
            }

    def get_all_symbols(self):
        """모의 거래쌍 조회"""
        try:
            time.sleep(0.3)
            symbols = self.exchange_data[self.exchange]['symbols']
            
            return {
                'status': 'success',
                'symbols': symbols,
                'message': f"{self.exchange_data[self.exchange]['name']} 거래쌍 {len(symbols)}개 조회 성공 (테스트 모드)"
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'거래쌍 조회 오류: {str(e)}'
            }

    def get_current_price(self, symbol):
        """모의 현재가 조회"""
        try:
            time.sleep(0.2)
            
            # 더미 가격 데이터
            base_prices = {
                'BTC': 45000 + random.uniform(-1000, 1000),
                'ETH': 3000 + random.uniform(-100, 100),
                'SOL': 100 + random.uniform(-10, 10),
                'ADA': 0.5 + random.uniform(-0.05, 0.05),
                'DOT': 7 + random.uniform(-0.5, 0.5),
                'MATIC': 0.8 + random.uniform(-0.1, 0.1),
                'AVAX': 25 + random.uniform(-2, 2),
                'LINK': 15 + random.uniform(-1, 1),
                'UNI': 8 + random.uniform(-0.5, 0.5)
            }
            
            base = symbol.split('/')[0]
            price = base_prices.get(base, 100 + random.uniform(-10, 10))
            
            return {
                'status': 'success',
                'price': price,
                'symbol': symbol,
                'message': f"{symbol} 현재가: ${price:,.4f} (테스트 모드)"
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'가격 조회 오류: {str(e)}'
            }

    def test_api_connection(self):
        """모의 API 연결 테스트"""
        try:
            time.sleep(0.5)
            
            return {
                'status': 'success',
                'message': f"{self.exchange_data[self.exchange]['name']} API 연결 성공 (테스트 모드)\n\n💡 실제 API 키가 필요하지 않습니다."
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'API 연결 테스트 오류: {str(e)}'
            }

class MockFuturesTrader:
    """모의 선물거래 클래스"""
    
    def __init__(self, exchange, **kwargs):
        self.exchange = exchange.lower()
        self.is_test_mode = True
        self.mock_futures_balance = {
            'USDT': 5000.0,
            'BTC': 0.1,
            'ETH': 1.0
        }
        self.mock_positions = []
        self.mock_leverage = 1
        
        self.exchange_data = {
            'xt': {
                'name': 'XT Exchange',
                'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
                'max_leverage': 10
            },
            'backpack': {
                'name': 'Backpack',
                'symbols': ['BTC/USDT', 'ETH/USDT'],
                'max_leverage': 5
            },
            'hyperliquid': {
                'name': 'Hyperliquid',
                'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
                'max_leverage': 20
            },
            'flipster': {
                'name': 'Flipster',
                'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
                'max_leverage': 15
            }
        }

    def get_futures_balance(self):
        """모의 선물 잔고 조회"""
        try:
            time.sleep(0.5)
            
            balance_text = f"📊 **{self.exchange_data[self.exchange]['name']} 선물 잔고**\n\n"
            for currency, amount in self.mock_futures_balance.items():
                if amount > 0:
                    balance_text += f"**{currency}**: {amount:,.4f}\n"
            
            balance_text += f"\n💡 **테스트 모드** - 실제 잔고가 아닙니다"
            
            return {
                'status': 'success',
                'balance': self.mock_futures_balance,
                'message': balance_text
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'선물 잔고 조회 오류: {str(e)}'
            }

    def get_futures_symbols(self):
        """모의 선물 거래쌍 조회"""
        try:
            time.sleep(0.3)
            symbols = self.exchange_data[self.exchange]['symbols']
            
            return {
                'status': 'success',
                'symbols': symbols,
                'message': f"{self.exchange_data[self.exchange]['name']} 선물 거래쌍 {len(symbols)}개 조회 성공 (테스트 모드)"
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'선물 거래쌍 조회 오류: {str(e)}'
            }

    def open_long_position(self, symbol, size, leverage=1, stop_loss=None, take_profit=None):
        """모의 롱 포지션 오픈"""
        try:
            time.sleep(1.0)
            
            position_id = f"pos_{int(time.time())}"
            position = {
                'id': position_id,
                'symbol': symbol,
                'side': 'long',
                'size': size,
                'leverage': leverage,
                'entry_price': 45000 + random.uniform(-1000, 1000),
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now().isoformat()
            }
            
            self.mock_positions.append(position)
            
            return {
                'status': 'success',
                'order_id': position_id,
                'message': f"📈 롱 포지션 오픈 성공 (테스트 모드)\n\n"
                          f"심볼: {symbol}\n"
                          f"크기: {size}\n"
                          f"레버리지: {leverage}배\n"
                          f"진입가: ${position['entry_price']:,.2f}"
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'롱 포지션 오픈 오류: {str(e)}'
            }

    def open_short_position(self, symbol, size, leverage=1, stop_loss=None, take_profit=None):
        """모의 숏 포지션 오픈"""
        try:
            time.sleep(1.0)
            
            position_id = f"pos_{int(time.time())}"
            position = {
                'id': position_id,
                'symbol': symbol,
                'side': 'short',
                'size': size,
                'leverage': leverage,
                'entry_price': 45000 + random.uniform(-1000, 1000),
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now().isoformat()
            }
            
            self.mock_positions.append(position)
            
            return {
                'status': 'success',
                'order_id': position_id,
                'message': f"📉 숏 포지션 오픈 성공 (테스트 모드)\n\n"
                          f"심볼: {symbol}\n"
                          f"크기: {size}\n"
                          f"레버리지: {leverage}배\n"
                          f"진입가: ${position['entry_price']:,.2f}"
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'숏 포지션 오픈 오류: {str(e)}'
            }

    def get_positions(self):
        """모의 포지션 조회"""
        try:
            time.sleep(0.5)
            
            if not self.mock_positions:
                return {
                    'status': 'success',
                    'positions': [],
                    'message': f"{self.exchange_data[self.exchange]['name']} - 현재 포지션이 없습니다 (테스트 모드)"
                }
            
            positions_text = f"📊 **{self.exchange_data[self.exchange]['name']} 포지션**\n\n"
            for pos in self.mock_positions:
                pnl = random.uniform(-500, 500)  # 모의 손익
                positions_text += f"**{pos['symbol']}** ({pos['side'].upper()})\n"
                positions_text += f"크기: {pos['size']} | 레버리지: {pos['leverage']}배\n"
                positions_text += f"진입가: ${pos['entry_price']:,.2f}\n"
                positions_text += f"손익: ${pnl:,.2f}\n\n"
            
            positions_text += "💡 **테스트 모드** - 실제 포지션이 아닙니다"
            
            return {
                'status': 'success',
                'positions': self.mock_positions,
                'message': positions_text
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'포지션 조회 오류: {str(e)}'
            }

    def set_leverage(self, symbol, leverage):
        """모의 레버리지 설정"""
        try:
            time.sleep(0.3)
            
            max_leverage = self.exchange_data[self.exchange]['max_leverage']
            if leverage > max_leverage:
                return {
                    'status': 'error',
                    'message': f'최대 레버리지는 {max_leverage}배입니다'
                }
            
            self.mock_leverage = leverage
            
            return {
                'status': 'success',
                'message': f"⚡ 레버리지 {leverage}배 설정 성공 (테스트 모드)\n\n"
                          f"거래소: {self.exchange_data[self.exchange]['name']}\n"
                          f"심볼: {symbol}"
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'레버리지 설정 오류: {str(e)}'
            }

    def test_api_connection(self):
        """모의 API 연결 테스트"""
        try:
            time.sleep(0.5)
            
            return {
                'status': 'success',
                'message': f"{self.exchange_data[self.exchange]['name']} 선물 API 연결 성공 (테스트 모드)\n\n💡 실제 API 키가 필요하지 않습니다."
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'API 연결 테스트 오류: {str(e)}'
            }

def create_mock_trader(exchange, trading_type='spot'):
    """모의 거래자 생성"""
    if trading_type == 'futures':
        return MockFuturesTrader(exchange)
    else:
        return MockTrader(exchange) 