#!/usr/bin/env python3
"""
간단한 API 테스트 - 실제 문제 해결용
"""

import requests
import json

def test_backpack_symbols():
    """Backpack 심볼 조회 테스트"""
    print("=== Backpack 심볼 조회 테스트 ===")
    
    try:
        url = "https://api.backpack.exchange/api/v1/markets"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 성공! 응답 타입: {type(data)}")
            
            if isinstance(data, list):
                print(f"총 심볼 수: {len(data)}")
                
                # SPOT 거래만 필터링
                spot_symbols = []
                for item in data:
                    if isinstance(item, dict):
                        symbol = item.get('symbol')
                        market_type = item.get('marketType', '')
                        if symbol and market_type == 'SPOT':
                            spot_symbols.append(symbol)
                
                print(f"SPOT 거래 심볼 수: {len(spot_symbols)}")
                print(f"첫 10개 SPOT 심볼: {spot_symbols[:10]}")
                
                return spot_symbols
            else:
                print(f"❌ 예상치 못한 응답 구조: {type(data)}")
                return None
        else:
            print(f"❌ API 오류: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return None

def test_hyperliquid_symbols():
    """Hyperliquid 심볼 조회 테스트"""
    print("\n=== Hyperliquid 심볼 조회 테스트 ===")
    
    try:
        url = "https://api.hyperliquid.xyz/info"
        payload = {"type": "meta"}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 성공! 응답 타입: {type(data)}")
            
            if isinstance(data, dict) and 'universe' in data:
                universe = data['universe']
                print(f"총 심볼 수: {len(universe)}")
                
                # 심볼 이름 추출
                symbols = []
                for item in universe:
                    if isinstance(item, dict):
                        name = item.get('name')
                        if name:
                            symbols.append(name)
                
                print(f"추출된 심볼 수: {len(symbols)}")
                print(f"첫 10개 심볼: {symbols[:10]}")
                
                return symbols
            else:
                print(f"❌ 예상치 못한 응답 구조")
                return None
        else:
            print(f"❌ API 오류: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return None

def main():
    print("🔧 간단한 API 테스트 시작")
    print("=" * 50)
    
    # Backpack 테스트
    backpack_symbols = test_backpack_symbols()
    
    # Hyperliquid 테스트
    hyperliquid_symbols = test_hyperliquid_symbols()
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약:")
    
    if backpack_symbols:
        print(f"✅ Backpack: {len(backpack_symbols)}개 심볼 조회 성공")
    else:
        print("❌ Backpack: 심볼 조회 실패")
    
    if hyperliquid_symbols:
        print(f"✅ Hyperliquid: {len(hyperliquid_symbols)}개 심볼 조회 성공")
    else:
        print("❌ Hyperliquid: 심볼 조회 실패")
    
    print("=" * 50)
    print("✅ 테스트 완료")

if __name__ == "__main__":
    main() 