#!/usr/bin/env python3
"""
XT.com API 엔드포인트 찾기
"""

import requests

def test_xt_endpoints():
    """XT.com API 엔드포인트 테스트"""
    print("=== XT.com API 엔드포인트 테스트 ===")
    
    # 가능한 엔드포인트들
    endpoints = [
        "/api/v4/public/symbol",
        "/api/v4/public/symbol/list", 
        "/api/v4/public/symbols",
        "/api/v4/public/symbols/list",
        "/api/v4/public/markets",
        "/api/v4/public/markets/list",
        "/api/v4/public/ticker/24hr",
        "/api/v4/public/ticker",
        "/api/v4/public/exchangeInfo",
        "/api/v4/public/info"
    ]
    
    base_url = "https://sapi.xt.com"
    
    for endpoint in endpoints:
        url = base_url + endpoint
        print(f"\n테스트: {endpoint}")
        try:
            response = requests.get(url)
            print(f"상태코드: {response.status_code}")
            if response.status_code == 200:
                print(f"✅ 성공! 응답 길이: {len(response.text)}")
                print(f"응답 내용 (처음 200자): {response.text[:200]}")
                break
            else:
                print(f"❌ 실패: {response.text[:100]}")
        except Exception as e:
            print(f"❌ 오류: {e}")

if __name__ == "__main__":
    test_xt_endpoints() 