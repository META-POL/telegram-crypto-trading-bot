#!/usr/bin/env python3
"""
API 디버깅 테스트 스크립트
패키지 설치 없이 API 응답을 확인할 수 있습니다.
"""

import requests
import time
import hmac
import hashlib
import base64
import json

def test_xt_api():
    """XT.com API 테스트"""
    print("=== XT.com API 테스트 ===")
    
    # 공개 API 테스트 (인증 불필요)
    try:
        # 심볼 조회 - 수정된 엔드포인트
        urls = [
            "https://sapi.xt.com/api/v4/public/symbol/list",
            "https://sapi.xt.com/api/v4/public/symbols"
        ]
        
        for i, url in enumerate(urls, 1):
            print(f"\nXT 심볼 조회 (시도 {i}) - URL: {url}")
            response = requests.get(url)
            print(f"상태코드: {response.status_code}")
            print(f"응답 내용 (처음 300자): {response.text[:300]}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"응답 타입: {type(data)}")
                if isinstance(data, dict):
                    print(f"응답 키들: {list(data.keys())}")
                    if 'result' in data:
                        print(f"result 타입: {type(data['result'])}")
                        if isinstance(data['result'], list):
                            print(f"result 길이: {len(data['result'])}")
                            if len(data['result']) > 0:
                                print(f"첫 번째 항목: {data['result'][0]}")
                elif isinstance(data, list):
                    print(f"리스트 길이: {len(data)}")
                    if len(data) > 0:
                        print(f"첫 번째 항목: {data[0]}")
                break
        
    except Exception as e:
        print(f"XT API 테스트 오류: {e}")

def test_backpack_api():
    """Backpack API 테스트"""
    print("\n=== Backpack API 테스트 ===")
    
    try:
        # 심볼 조회
        url = "https://api.backpack.exchange/api/v1/markets"
        response = requests.get(url)
        print(f"Backpack 심볼 조회 - 상태코드: {response.status_code}")
        print(f"응답 내용 (처음 300자): {response.text[:300]}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"응답 타입: {type(data)}")
            if isinstance(data, list):
                print(f"리스트 길이: {len(data)}")
                if len(data) > 0:
                    print(f"첫 번째 항목: {data[0]}")
                    # SPOT 거래 필터링 테스트
                    spot_symbols = []
                    for item in data:
                        if isinstance(item, dict):
                            symbol = item.get('symbol')
                            market_type = item.get('marketType', '')
                            if symbol and market_type == 'SPOT':
                                spot_symbols.append(symbol)
                    print(f"SPOT 거래 심볼 수: {len(spot_symbols)}")
                    if len(spot_symbols) > 0:
                        print(f"첫 번째 SPOT 심볼: {spot_symbols[0]}")
        
    except Exception as e:
        print(f"Backpack API 테스트 오류: {e}")

def test_hyperliquid_api():
    """Hyperliquid API 테스트"""
    print("\n=== Hyperliquid API 테스트 ===")
    
    try:
        # 수정된 API 호출
        url = "https://api.hyperliquid.xyz/info"
        payload = {"type": "meta"}
        response = requests.post(url, json=payload)
        print(f"Hyperliquid API 테스트 - 상태코드: {response.status_code}")
        print(f"응답 내용 (처음 300자): {response.text[:300]}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"응답 타입: {type(data)}")
            if isinstance(data, dict):
                print(f"응답 키들: {list(data.keys())}")
                if 'universe' in data:
                    universe = data['universe']
                    print(f"universe 타입: {type(universe)}")
                    if isinstance(universe, list):
                        print(f"universe 길이: {len(universe)}")
                        if len(universe) > 0:
                            print(f"첫 번째 항목: {universe[0]}")
        
    except Exception as e:
        print(f"Hyperliquid API 테스트 오류: {e}")

def main():
    print("🔧 API 디버깅 테스트 시작")
    print("=" * 50)
    
    test_xt_api()
    test_backpack_api()
    test_hyperliquid_api()
    
    print("\n" + "=" * 50)
    print("✅ API 디버깅 테스트 완료")

if __name__ == "__main__":
    main() 