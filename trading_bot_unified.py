import time
import hmac
import hashlib
import requests
import threading
import base64
from datetime import datetime
try:
    from nacl.signing import SigningKey
except ImportError:
    SigningKey = None

# Hyperliquid용
try:
    import ccxt
except ImportError:
    ccxt = None

class UnifiedSpotTrader:
    def __init__(self, exchange, **kwargs):
        self.exchange = exchange.lower()
        self.is_trading = True
        self.total_profit = 0.0
        self.lock = threading.Lock()
        self.active_orders = {}  # 활성 주문 추적
        self.risk_settings = {
            'max_loss': 100,  # 최대 손실 한도 (USDT)
            'stop_loss_percent': 5,  # 손절매 비율 (%)
            'take_profit_percent': 10,  # 익절매 비율 (%)
            'max_position_size': 1000  # 최대 포지션 크기 (USDT)
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
                raise ImportError("pynacl 패키지가 필요합니다. requirements.txt에 pynacl==1.5.0 추가")
        elif self.exchange == 'hyperliquid':
            if ccxt is None:
                raise ImportError("ccxt 패키지가 필요합니다. requirements.txt에 ccxt==4.1.77 추가")
            self.api_key = kwargs.get('api_key')
            self.api_secret = kwargs.get('api_secret')
            self.ccxt_client = ccxt.hyperliquid({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
            })
        else:
            raise ValueError('지원하지 않는 거래소입니다: xt, backpack, hyperliquid만 지원')

    def set_risk_settings(self, max_loss=None, stop_loss_percent=None, take_profit_percent=None, max_position_size=None):
        """리스크 설정 업데이트"""
        if max_loss is not None:
            self.risk_settings['max_loss'] = max_loss
        if stop_loss_percent is not None:
            self.risk_settings['stop_loss_percent'] = stop_loss_percent
        if take_profit_percent is not None:
            self.risk_settings['take_profit_percent'] = take_profit_percent
        if max_position_size is not None:
            self.risk_settings['max_position_size'] = max_position_size

    def _get_headers_xt(self, params=None):
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

    def get_balance(self):
        if self.exchange == 'xt':
            url = f"{self.base_url}/api/v4/balance/list"
            headers = self._get_headers_xt()
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.text}
        elif self.exchange == 'backpack':
            url = f"{self.base_url}/capital/balances"
            headers = self._get_headers_backpack("balanceQuery")
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.text}
        elif self.exchange == 'hyperliquid':
            return self.ccxt_client.fetch_balance()
        else:
            return {"error": "지원하지 않는 거래소"}

    def get_current_price(self, symbol):
        """현재 가격 조회"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/api/v4/public/ticker/24hr"
                params = {"symbol": symbol}
                headers = self._get_headers_xt(params)
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return float(data.get('lastPrice', 0))
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/ticker/{symbol}"
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return float(data.get('lastPrice', 0))
            elif self.exchange == 'hyperliquid':
                ticker = self.ccxt_client.fetch_ticker(symbol)
                return ticker['last']
        except Exception as e:
            print(f"가격 조회 오류: {e}")
        return None

    def calculate_fee(self, amount, fee_rate=0.001):
        """수수료 계산 (기본 0.1%)"""
        return amount * fee_rate

    def buy(self, symbol, price, quantity, repeat=1, order_type='limit'):
        """매수 주문 (개선된 버전)"""
        if order_type == 'market':
            return self._market_buy(symbol, quantity, repeat)
        else:
            if self.exchange == 'xt':
                return self._trade_xt('buy', symbol, price, quantity, repeat)
            elif self.exchange == 'backpack':
                return self._trade_backpack('Bid', symbol, price, quantity, repeat)
            elif self.exchange == 'hyperliquid':
                results = []
                for _ in range(repeat):
                    order = self.ccxt_client.create_limit_buy_order(symbol, quantity, price)
                    results.append(order)
                return results

    def sell(self, symbol, price, quantity, repeat=1, order_type='limit'):
        """매도 주문 (개선된 버전)"""
        if order_type == 'market':
            return self._market_sell(symbol, quantity, repeat)
        else:
            if self.exchange == 'xt':
                return self._trade_xt('sell', symbol, price, quantity, repeat)
            elif self.exchange == 'backpack':
                return self._trade_backpack('Ask', symbol, price, quantity, repeat)
            elif self.exchange == 'hyperliquid':
                results = []
                for _ in range(repeat):
                    order = self.ccxt_client.create_limit_sell_order(symbol, quantity, price)
                    results.append(order)
                return results

    def _market_buy(self, symbol, quantity, repeat):
        """시장가 매수"""
        results = []
        for _ in range(repeat):
            if not self.is_trading:
                results.append({"status": "stopped"})
                break
            try:
                if self.exchange == 'xt':
                    result = self._place_market_order_xt('buy', symbol, quantity)
                elif self.exchange == 'backpack':
                    result = self._place_market_order_backpack('Bid', symbol, quantity)
                elif self.exchange == 'hyperliquid':
                    result = self.ccxt_client.create_market_buy_order(symbol, quantity)
                results.append(result)
                time.sleep(1)
            except Exception as e:
                results.append({"error": str(e)})
        return results

    def _market_sell(self, symbol, quantity, repeat):
        """시장가 매도"""
        results = []
        for _ in range(repeat):
            if not self.is_trading:
                results.append({"status": "stopped"})
                break
            try:
                if self.exchange == 'xt':
                    result = self._place_market_order_xt('sell', symbol, quantity)
                elif self.exchange == 'backpack':
                    result = self._place_market_order_backpack('Ask', symbol, quantity)
                elif self.exchange == 'hyperliquid':
                    result = self.ccxt_client.create_market_sell_order(symbol, quantity)
                results.append(result)
                time.sleep(1)
            except Exception as e:
                results.append({"error": str(e)})
        return results

    def volume_trading(self, symbol, price, quantity, repeat=1):
        """거래량 생성을 위한 자동 매수-매도"""
        results = []
        for i in range(repeat):
            if not self.is_trading:
                results.append({"status": "stopped"})
                break
            
            # 1. 매수 주문
            buy_result = self.buy(symbol, price, quantity, 1, 'market')
            if 'error' in str(buy_result):
                results.append({"error": f"매수 실패: {buy_result}"})
                continue
            
            # 2. 잠시 대기 (거래량 생성 효과)
            time.sleep(2)
            
            # 3. 매도 주문 (약간 낮은 가격으로)
            sell_price = price * 0.999  # 0.1% 낮은 가격으로 매도
            sell_result = self.sell(symbol, sell_price, quantity, 1, 'market')
            
            # 4. 결과 기록
            trade_info = {
                "round": i + 1,
                "buy_result": buy_result,
                "sell_result": sell_result,
                "volume_generated": quantity * 2,  # 매수+매도 = 2배 거래량
                "timestamp": datetime.now().isoformat()
            }
            results.append(trade_info)
            
            # 5. 다음 라운드 전 대기
            time.sleep(3)
        
        return results

    def stop_loss_order(self, symbol, buy_price, quantity, stop_loss_percent=None):
        """스탑로스 주문"""
        if stop_loss_percent is None:
            stop_loss_percent = self.risk_settings['stop_loss_percent']
        
        stop_loss_price = buy_price * (1 - stop_loss_percent / 100)
        return self.sell(symbol, stop_loss_price, quantity, 1, 'limit')

    def take_profit_order(self, symbol, buy_price, quantity, take_profit_percent=None):
        """익절매 주문"""
        if take_profit_percent is None:
            take_profit_percent = self.risk_settings['take_profit_percent']
        
        take_profit_price = buy_price * (1 + take_profit_percent / 100)
        return self.sell(symbol, take_profit_price, quantity, 1, 'limit')

    def get_order_status(self, order_id, symbol):
        """주문 상태 조회"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/api/v4/order"
                params = {"orderId": order_id}
                headers = self._get_headers_xt(params)
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order/{order_id}"
                headers = self._get_headers_backpack("orderQuery")
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
            elif self.exchange == 'hyperliquid':
                return self.ccxt_client.fetch_order(order_id, symbol)
        except Exception as e:
            return {"error": str(e)}
        return {"error": "주문 상태 조회 실패"}

    def cancel_order(self, order_id, symbol):
        """주문 취소"""
        try:
            if self.exchange == 'xt':
                url = f"{self.base_url}/api/v4/order"
                params = {"orderId": order_id}
                headers = self._get_headers_xt(params)
                response = requests.delete(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
            elif self.exchange == 'backpack':
                url = f"{self.base_url}/order/{order_id}"
                headers = self._get_headers_backpack("orderCancel")
                response = requests.delete(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
            elif self.exchange == 'hyperliquid':
                return self.ccxt_client.cancel_order(order_id, symbol)
        except Exception as e:
            return {"error": str(e)}
        return {"error": "주문 취소 실패"}

    def _trade_xt(self, side, symbol, price, quantity, repeat):
        results = []
        for i in range(repeat):
            if not self.is_trading:
                results.append({"status": "stopped"})
                break
            order_result = self._place_order_xt(side, symbol, price, quantity)
            results.append(order_result)
            time.sleep(1)
        return results

    def _place_order_xt(self, side, symbol, price, quantity):
        url = f"{self.base_url}/api/v4/order"
        params = {
            "symbol": symbol,
            "side": side,
            "type": "limit",
            "price": str(price),
            "quantity": str(quantity)
        }
        headers = self._get_headers_xt(params)
        response = requests.post(url, json=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            with self.lock:
                if side == 'sell':
                    self.total_profit += price * float(quantity) - self.calculate_fee(price * float(quantity))
                else:
                    self.total_profit -= price * float(quantity) + self.calculate_fee(price * float(quantity))
            return data
        else:
            return {"error": response.text}

    def _place_market_order_xt(self, side, symbol, quantity):
        url = f"{self.base_url}/api/v4/order"
        params = {
            "symbol": symbol,
            "side": side,
            "type": "market",
            "quantity": str(quantity)
        }
        headers = self._get_headers_xt(params)
        response = requests.post(url, json=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}

    def _trade_backpack(self, side, symbol, price, quantity, repeat):
        results = []
        for i in range(repeat):
            if not self.is_trading:
                results.append({"status": "stopped"})
                break
            order_result = self._place_order_backpack(side, symbol, price, quantity)
            results.append(order_result)
            time.sleep(1)
        return results

    def _place_order_backpack(self, side, symbol, price, quantity):
        url = f"{self.base_url}/order"
        params = {
            "symbol": symbol,
            "side": side,  # "Bid"=매수, "Ask"=매도
            "orderType": "Limit",
            "price": str(price),
            "quantity": str(quantity)
        }
        headers = self._get_headers_backpack("orderExecute", params)
        response = requests.post(url, json=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            with self.lock:
                if side == 'Ask':
                    self.total_profit += price * float(quantity) - self.calculate_fee(price * float(quantity))
                else:
                    self.total_profit -= price * float(quantity) + self.calculate_fee(price * float(quantity))
            return data
        else:
            return {"error": response.text}

    def _place_market_order_backpack(self, side, symbol, quantity):
        url = f"{self.base_url}/order"
        params = {
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "quantity": str(quantity)
        }
        headers = self._get_headers_backpack("orderExecute", params)
        response = requests.post(url, json=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}

    def stop_trading(self):
        self.is_trading = False

    def get_profit(self):
        return self.total_profit

    def get_risk_info(self):
        """리스크 정보 조회"""
        return {
            "current_profit": self.total_profit,
            "max_loss_limit": self.risk_settings['max_loss'],
            "stop_loss_percent": self.risk_settings['stop_loss_percent'],
            "take_profit_percent": self.risk_settings['take_profit_percent'],
            "max_position_size": self.risk_settings['max_position_size'],
            "risk_level": "HIGH" if abs(self.total_profit) > self.risk_settings['max_loss'] * 0.8 else "NORMAL"
        } 