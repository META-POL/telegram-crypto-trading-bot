#!/usr/bin/env python3
"""
app.py의 XT 통합 기능 테스트
"""

import sys
import os

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
except Exception as e:
    print(f"⚠️ pyxt 라이브러리 로드 중 오류: {e}")
    PYXTLIB_AVAILABLE = False
    Spot = None
    Perp = None

# XTClient 클래스 (app.py에서 사용하는 것과 동일)
class XTClient:
    """현물·선물 통합 래퍼"""
    def __init__(self, api_key, api_secret):
        if not PYXTLIB_AVAILABLE:
            print("❌ pyxt 라이브러리가 설치되지 않아 XTClient를 사용할 수 없습니다.")
            return
            
        try:
            self.spot = Spot(
                host="https://sapi.xt.com",       # 현물 REST 엔드포인트
                access_key=api_key,
                secret_key=api_secret
            )
            self.futures = Perp(
                host="https://fapi.xt.com",       # USDT-M 선물 REST 엔드포인트
                access_key=api_key,
                secret_key=api_secret
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

# UnifiedFuturesTrader 클래스의 XT 부분만 테스트
class XTTester:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange = 'xt'
    
    def get_futures_balance(self):
        """선물 계좌 잔고 조회 (app.py와 동일한 로직)"""
        try:
            if self.exchange == 'xt':
                # pyxt 라이브러리를 사용한 XT 선물 잔고 조회
                if PYXTLIB_AVAILABLE:
                    try:
                        print(f"pyxt 라이브러리 사용 시도: API_KEY={self.api_key[:10]}...")
                        
                        # XTClient 클래스 생성 (xt.py에서 성공한 방식)
                        xt_client = XTClient(self.api_key, self.api_secret)
                        balance = xt_client.futures_balance()
                        
                        print(f"pyxt 라이브러리 선물 잔고 조회 성공: {balance}")
                        
                        if 'error' in balance:
                            print(f"pyxt 라이브러리 오류: {balance['error']}")
                            # 오류 발생 시 기존 방식으로 폴백
                        else:
                            return {
                                'status': 'success',
                                'balance': balance,
                                'message': 'XT 선물 잔고 조회 성공 (pyxt 라이브러리)'
                            }
                    except Exception as e:
                        print(f"pyxt 라이브러리 선물 잔고 조회 실패: {e}")
                        print(f"pyxt 라이브러리 사용 불가능, 기존 방식으로 폴백")
                else:
                    print("pyxt 라이브러리가 설치되지 않음, 기존 방식 사용")
                
                # 기존 방식 (pyxt 라이브러리 사용 불가능한 경우)
                return {
                    'status': 'error',
                    'balance': {},
                    'message': 'pyxt 라이브러리 사용 불가능'
                }
        except Exception as e:
            return {
                'status': 'error',
                'balance': {},
                'message': f'오류 발생: {str(e)}'
            }
    
    def get_spot_balance(self):
        """스팟 계좌 잔고 조회 (app.py와 동일한 로직)"""
        try:
            if self.exchange == 'xt':
                # pyxt 라이브러리를 사용한 XT 스팟 잔고 조회
                if PYXTLIB_AVAILABLE:
                    try:
                        print(f"pyxt 라이브러리 사용 시도: API_KEY={self.api_key[:10]}...")
                        
                        # XTClient 클래스 생성 (xt.py에서 성공한 방식)
                        xt_client = XTClient(self.api_key, self.api_secret)
                        balance = xt_client.spot_balance()
                        
                        print(f"pyxt 라이브러리 스팟 잔고 조회 성공: {balance}")
                        
                        if 'error' in balance:
                            print(f"pyxt 라이브러리 오류: {balance['error']}")
                            # 오류 발생 시 기존 방식으로 폴백
                        else:
                            return {
                                'status': 'success',
                                'balance': balance,
                                'message': 'XT 스팟 잔고 조회 성공 (pyxt 라이브러리)'
                            }
                    except Exception as e:
                        print(f"pyxt 라이브러리 스팟 잔고 조회 실패: {e}")
                        # pyxt 실패 시 기존 방식으로 폴백
                else:
                    print("pyxt 라이브러리가 설치되지 않음, 기존 방식 사용")
                
                # 기존 방식 (pyxt 라이브러리 사용 불가능한 경우)
                return {
                    'status': 'error',
                    'balance': {},
                    'message': 'pyxt 라이브러리 사용 불가능'
                }
        except Exception as e:
            return {
                'status': 'error',
                'balance': {},
                'message': f'오류 발생: {str(e)}'
            }

def main():
    print("🚀 app.py XT 통합 기능 테스트")
    print("=" * 50)
    
    # API 키 설정
    API_KEY = "69b28903-8bbf-4ca3-a46e-1cd46fd1a520"
    SECRET_KEY = "ff40182cc9c4159bed390866e9723ee3bdda9a07"
    
    print(f"🔑 API 키: {API_KEY[:10]}...")
    print(f"🔐 시크릿 키: {SECRET_KEY[:10]}...")
    print()
    
    # XTTester 생성
    tester = XTTester(API_KEY, SECRET_KEY)
    
    # 1. 선물 잔고 조회 테스트
    print("📊 선물 잔고 조회 테스트")
    print("-" * 30)
    futures_result = tester.get_futures_balance()
    print(f"결과: {futures_result}")
    print()
    
    # 2. 스팟 잔고 조회 테스트
    print("💰 스팟 잔고 조회 테스트")
    print("-" * 30)
    spot_result = tester.get_spot_balance()
    print(f"결과: {spot_result}")
    print()
    
    # 3. 결과 요약
    print("=" * 50)
    print("📋 최종 테스트 결과 요약")
    print("=" * 50)
    
    print(f"선물 잔고 조회: {'✅ 성공' if futures_result['status'] == 'success' else '❌ 실패'}")
    print(f"스팟 잔고 조회: {'✅ 성공' if spot_result['status'] == 'success' else '❌ 실패'}")
    
    if futures_result['status'] == 'success' and spot_result['status'] == 'success':
        print("\n🎉 모든 테스트 성공! app.py에서 XT 통합이 정상 작동합니다.")
    else:
        print("\n⚠️ 일부 테스트 실패. 문제를 확인해주세요.")

if __name__ == "__main__":
    main() 