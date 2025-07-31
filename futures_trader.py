#!/usr/bin/env python3
"""
선물거래 전용 클래스
XT, Backpack, Hyperliquid, Flipster 지원
"""

import time
import hmac
import hashlib
import requests
import threading
import base64
import logging
from datetime import datetime
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