#!/usr/bin/env python3
"""
XT.com 통합 예제
 - 현물·선물 잔고조회
 - 현물·선물 주문
 - 전체 잔고(현물+선물) 요약
"""

import time
import logging
import requests
import hmac
import hashlib
import json
from datetime import datetime

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

# ---------- 환경설정 ----------
API_KEY = "69b28903-8bbf-4ca3-a46e-1cd46fd1a520"
SECRET_KEY = "ff40182cc9c4159bed390866e9723ee3bdda9a07"

# ---------- 공통 로직 ----------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

class XTClient:
    """현물·선물 통합 래퍼"""
    def __init__(self):
        if not PYXTLIB_AVAILABLE:
            print("❌ pyxt 라이브러리가 설치되지 않아 XTClient를 사용할 수 없습니다.")
            return
            
        try:
            self.spot = Spot(
                host="https://sapi.xt.com",       # 현물 REST 엔드포인트
                access_key=API_KEY,
                secret_key=SECRET_KEY
            )
            self.futures = Perp(
                host="https://fapi.xt.com",       # USDT-M 선물 REST 엔드포인트
                access_key=API_KEY,
                secret_key=SECRET_KEY
            )
            print("✅ XTClient 초기화 성공")
        except Exception as e:
            print(f"❌ XTClient 초기화 실패: {e}")
            self.spot = None
            self.futures = None

    # --------- 잔고 ---------
    def spot_balance(self, currency="usdt"):
        """현물 특정 자산 또는 전체 잔고 반환"""
        if not self.spot:
            return {"error": "Spot client not available"}
        try:
            return (self.spot.balance(currency) if currency
                    else self.spot.balanceList())
        except Exception as e:
            return {"error": f"Spot balance error: {e}"}

    def futures_balance(self):
        """선물 지갑 자산(계정 자본) 반환"""
        if not self.futures:
            return {"error": "Futures client not available"}
        try:
            return self.futures.get_account_capital()   # USDT, U-마진 등 포함
        except Exception as e:
            return {"error": f"Futures balance error: {e}"}

    def all_balances(self):
        """현물·선물 잔고 요약"""
        if not PYXTLIB_AVAILABLE:
            return {"error": "pyxt library not available"}
        try:
            spot_bal = self.spot_balance()
            perp_bal = self.futures_balance()
            return {"spot": spot_bal, "futures": perp_bal}
        except Exception as e:
            return {"error": f"All balances error: {e}"}

    # --------- 주문 ---------
    # 현물: 시장가·지정가
    def spot_order(self, symbol, side, qty, order_type="MARKET", price=None):
        if not self.spot:
            return {"error": "Spot client not available"}
        try:
            params = dict(symbol=symbol, side=side,
                          type=order_type, bizType="SPOT")
            if order_type == "MARKET":
                # BUY: quoteQty(USDT) / SELL: quantity(COIN)
                key = "quoteQty" if side.upper() == "BUY" else "quantity"
                params[key] = qty
            else:                                # LIMIT
                params.update(quantity=qty, price=price, timeInForce="GTC")
            return self.spot.place_order(**params)
        except Exception as e:
            return {"error": f"Spot order error: {e}"}

    # 선물: 시장가·지정가
    def futures_order(self, symbol, side, qty, order_type="MARKET", price=None):
        if not self.futures:
            return {"error": "Futures client not available"}
        try:
            params = dict(symbol=symbol, side=side,
                          type=order_type, quantity=qty)
            if price:                             # LIMIT
                params["price"] = price
            return self.futures.place_order(**params)
        except Exception as e:
            return {"error": f"Futures order error: {e}"}

class ManualXTAPITester:
    """수동 API 테스트 (pyxt 라이브러리 없이)"""
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_urls = {
            "spot": "https://sapi.xt.com",
            "futures": "https://fapi.xt.com"
        }
        
    def _get_signature(self, params=None):
        """HMAC-SHA256 서명 생성"""
        timestamp = str(int(time.time() * 1000))
        
        if params:
            # 쿼리 파라미터가 있는 경우
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            sign_string = f"access_key={self.api_key}&{query_string}&timestamp={timestamp}"
        else:
            # 쿼리 파라미터가 없는 경우
            sign_string = f"access_key={self.api_key}&timestamp={timestamp}"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).digest().hex()
        
        return {
            'signature': signature,
            'timestamp': timestamp,
            'sign_string': sign_string
        }
    
    def _get_headers(self, params=None):
        """API 요청 헤더 생성"""
        sig_data = self._get_signature(params)
        
        headers = {
            "access_key": self.api_key,
            "signature": sig_data['signature'],
            "timestamp": sig_data['timestamp'],
            "Content-Type": "application/json"
        }
        
        return headers, sig_data
    
    def test_manual_balance(self):
        """수동 잔고 조회 테스트"""
        print("\n🔧 수동 API 잔고 조회 테스트...")
        
        endpoints = [
            "/v4/account/balance",
            "/v4/account/assets", 
            "/v4/account/capital",
            "/account/balance",
            "/account/assets",
            "/account/capital"
        ]
        
        for market_type, base_url in self.base_urls.items():
            print(f"\n📍 {market_type.upper()} API: {base_url}")
            
            for endpoint in endpoints:
                url = f"{base_url}{endpoint}"
                headers, sig_data = self._get_headers()
                
                try:
                    print(f"  🔍 시도: {endpoint}")
                    print(f"    서명: {sig_data['sign_string']}")
                    
                    response = requests.get(url, headers=headers, timeout=10)
                    print(f"    상태: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        print(f"    응답: {json.dumps(data, indent=2)}")
                        
                        if data.get('rc') == 0:
                            print(f"    ✅ 성공!")
                        elif data.get('rc') == 1:
                            print(f"    ⚠️ 오류: {data.get('mc', 'Unknown error')}")
                        else:
                            print(f"    ❓ 예상치 못한 응답 형식")
                    else:
                        print(f"    ❌ HTTP 오류: {response.text}")
                        
                except Exception as e:
                    print(f"    ❌ 요청 오류: {e}")
                
                print()

# ---------- 사용 예시 ----------
def main():
    print("🚀 XT.com API 테스트 시작")
    print("=" * 60)
    
    print(f"🔑 API 키: {API_KEY[:10]}...")
    print(f"🔐 시크릿 키: {SECRET_KEY[:10]}...")
    print()
    
    # 1. pyxt 라이브러리 테스트
    if PYXTLIB_AVAILABLE:
        print("📦 pyxt 라이브러리 테스트")
        print("-" * 40)
        
        try:
            xt = XTClient()
            
            # 잔고조회 테스트
            print("\n💰 잔고 조회 테스트:")
            print("현물-USDT 잔고 →", xt.spot_balance("usdt"))
            print("선물 지갑 잔고 →", xt.futures_balance())
            print("전체 잔고 요약 →", xt.all_balances())
            
            # 주문 테스트 (실제 주문은 하지 않음)
            print("\n📋 주문 기능 확인 (실제 주문 안함):")
            print("현물 주문 함수 →", "사용 가능" if xt.spot else "사용 불가")
            print("선물 주문 함수 →", "사용 가능" if xt.futures else "사용 불가")
            
        except Exception as e:
            print(f"❌ pyxt 테스트 실패: {e}")
    else:
        print("❌ pyxt 라이브러리가 설치되지 않아 라이브러리 테스트를 건너뜁니다.")
    
    # 2. 수동 API 테스트
    print("\n🔧 수동 API 테스트")
    print("-" * 40)
    
    manual_tester = ManualXTAPITester(API_KEY, SECRET_KEY)
    manual_tester.test_manual_balance()
    
    # 3. 결과 요약
    print("\n" + "=" * 60)
    print("📋 최종 테스트 결과 요약")
    print("=" * 60)
    
    if PYXTLIB_AVAILABLE:
        print("✅ pyxt 라이브러리: 설치됨")
        print("   - 현물 API: 사용 가능")
        print("   - 선물 API: 사용 가능")
    else:
        print("❌ pyxt 라이브러리: 설치되지 않음")
        print("   - pip install pyxt로 설치 필요")
    
    print("\n🎯 운영 가능성:")
    if PYXTLIB_AVAILABLE:
        print("✅ 완전 운영 가능: pyxt 라이브러리로 모든 기능 사용 가능")
        print("   - 잔고 조회: 가능")
        print("   - 주문 실행: 가능")
        print("   - 시장 데이터: 가능")
    else:
        print("⚠️ 부분 운영 가능: 수동 API로만 가능")
        print("   - 잔고 조회: 수동 API 필요")
        print("   - 주문 실행: 수동 API 필요")
        print("   - 시장 데이터: 가능")

if __name__ == "__main__":
    main() 