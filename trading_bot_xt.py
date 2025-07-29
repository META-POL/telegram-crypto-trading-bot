import time
import hmac
import hashlib
import requests
import threading

class XTSpotTrader:
    BASE_URL = "https://sapi.xt.com"

    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_trading = True
        self.total_profit = 0.0
        self.active_orders = []
        self.lock = threading.Lock()

    def _get_headers(self, params=None):
        # XT.com API 인증 헤더 생성
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

    def get_balance(self):
        """잔고 조회"""
        url = f"{self.BASE_URL}/api/v4/balance/list"
        headers = self._get_headers()
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}

    def buy(self, symbol, price, quantity, repeat=1):
        """지정가 반복 매수"""
        return self._trade('buy', symbol, price, quantity, repeat)

    def sell(self, symbol, price, quantity, repeat=1):
        """지정가 반복 매도"""
        return self._trade('sell', symbol, price, quantity, repeat)

    def _trade(self, side, symbol, price, quantity, repeat):
        """지정가 반복 매수/매도 내부 함수"""
        results = []
        for i in range(repeat):
            if not self.is_trading:
                results.append({"status": "stopped"})
                break
            order_result = self._place_order(side, symbol, price, quantity)
            results.append(order_result)
            time.sleep(1)  # 반복 간격(초)
        return results

    def _place_order(self, side, symbol, price, quantity):
        """실제 주문 전송 (매수/매도)"""
        url = f"{self.BASE_URL}/api/v4/order"
        params = {
            "symbol": symbol,
            "side": side,
            "type": "limit",
            "price": str(price),
            "quantity": str(quantity)
        }
        headers = self._get_headers(params)
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

    def stop_trading(self):
        """매매 정지"""
        self.is_trading = False

    def get_profit(self):
        """누적 매매수익 조회"""
        return self.total_profit 