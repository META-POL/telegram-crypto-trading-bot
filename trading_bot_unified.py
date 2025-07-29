import time
import hmac
import hashlib
import requests
import threading
import base64
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

    def buy(self, symbol, price, quantity, repeat=1):
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

    def sell(self, symbol, price, quantity, repeat=1):
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
                    self.total_profit += price * float(quantity)
                else:
                    self.total_profit -= price * float(quantity)
            return data
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
                    self.total_profit += price * float(quantity)
                else:
                    self.total_profit -= price * float(quantity)
            return data
        else:
            return {"error": response.text}

    def stop_trading(self):
        self.is_trading = False

    def get_profit(self):
        return self.total_profit 