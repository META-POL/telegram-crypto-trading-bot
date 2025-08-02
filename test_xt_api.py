import requests
import time
import hmac
import hashlib

def test_xt_api():
    """XT Exchange API 연결 테스트 (개선된 구현 테스트)"""
    
    # API 키 정보
    api_key = "e060cc97-84ad-4a62-aed8-198e5c85530a"
    api_secret = "421c0b02f715bfcdae119497135df83cf0bb8140"
    
    # XT API 베이스 URL (개선된 구현)
    base_url = "https://fapi.xt.com"  # 선물 API
    spot_base_url = "https://api.xt.com"  # 스팟 API
    
    def get_headers(params=None):
        """XT API 헤더 생성 (개선된 구현)"""
        timestamp = str(int(time.time() * 1000))
        params = params or {}
        
        # XT API 서명 생성
        sign_str = '&'.join([f"{k}={params[k]}" for k in sorted(params)]) + f"&timestamp={timestamp}"
        signature = hmac.new(api_secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
        
        return {
            "XT-API-KEY": api_key,
            "XT-API-SIGN": signature,
            "XT-API-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
    
    # 개선된 구현에서 사용하는 엔드포인트들
    test_endpoints = [
        # 선물 API 테스트 (개선된 구현)
        {
            'url': f"{base_url}/v1/public/time",
            'name': '선물 서버 시간 (개선된 구현)',
            'auth_required': False
        },
        {
            'url': f"{base_url}/v1/public/contracts",
            'name': '선물 계약 목록 (개선된 구현)',
            'auth_required': False
        },
        {
            'url': f"{base_url}/v1/account/balance",
            'name': '선물 잔고 조회 (개선된 구현)',
            'auth_required': True
        },
        {
            'url': f"{base_url}/v1/order",
            'name': '선물 주문 (개선된 구현)',
            'auth_required': True,
            'method': 'POST',
            'data': {
                'symbol': 'BTC_USDT',
                'side': 'buy',
                'type': 'market',
                'size': '0.001',
                'leverage': '1'
            }
        },
        
        # 스팟 API 테스트 (개선된 구현)
        {
            'url': f"{spot_base_url}/v4/public/time",
            'name': '스팟 서버 시간 (개선된 구현)',
            'auth_required': False
        },
        {
            'url': f"{spot_base_url}/v4/public/symbols",
            'name': '스팟 거래쌍 조회 (개선된 구현)',
            'auth_required': False
        },
        {
            'url': f"{spot_base_url}/v4/account/balance",
            'name': '스팟 잔고 조회 (개선된 구현)',
            'auth_required': True
        },
        {
            'url': f"{spot_base_url}/v4/order",
            'name': '스팟 주문 (개선된 구현)',
            'auth_required': True,
            'method': 'POST',
            'data': {
                'symbol': 'BTC_USDT',
                'side': 'buy',
                'type': 'market',
                'quantity': '0.001'
            }
        },
        
        # 기존 패턴들 (비교용)
        {
            'url': f"{base_url}/api/v4/futures/account/balance",
            'name': '기존 패턴 - 선물 잔고',
            'auth_required': True
        },
        {
            'url': f"{base_url}/api/v4/futures/contract/list",
            'name': '기존 패턴 - 계약 목록',
            'auth_required': False
        }
    ]
    
    print("=== XT Exchange API 연결 테스트 (개선된 구현) ===")
    print(f"테스트 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API 키: {api_key[:10]}...")
    print()
    
    successful_endpoints = []
    working_patterns = []
    
    for endpoint in test_endpoints:
        url = endpoint['url']
        name = endpoint['name']
        auth_required = endpoint['auth_required']
        method = endpoint.get('method', 'GET')
        data = endpoint.get('data')
        
        print(f"🔍 테스트: {name}")
        print(f"   URL: {url}")
        print(f"   메소드: {method}")
        print(f"   인증 필요: {'예' if auth_required else '아니오'}")
        if data:
            print(f"   데이터: {data}")
        
        try:
            if auth_required:
                headers = get_headers(data if data else {})
                if method == 'POST':
                    response = requests.post(url, headers=headers, json=data)
                else:
                    response = requests.get(url, headers=headers)
            else:
                if method == 'POST':
                    response = requests.post(url, json=data)
                else:
                    response = requests.get(url)
            
            print(f"   상태 코드: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # API 문서 링크 응답인지 확인
                if 'result' in data and isinstance(data['result'], dict) and 'openapiDocs' in data['result']:
                    print("   ⚠️ API 문서 링크 응답 (실제 데이터 아님)")
                else:
                    print("   ✅ 유효한 데이터 응답!")
                    successful_endpoints.append({
                        'name': name,
                        'url': url,
                        'data': data
                    })
                    
                    # 작동하는 패턴 기록
                    base_url_pattern = '/'.join(url.split('/')[:3])
                    if base_url_pattern not in working_patterns:
                        working_patterns.append(base_url_pattern)
                    
                    # 응답 데이터 일부 출력
                    if 'result' in data:
                        if isinstance(data['result'], list) and len(data['result']) > 0:
                            print(f"   📊 데이터 개수: {len(data['result'])}")
                            print(f"   📊 첫 번째 항목: {data['result'][0]}")
                        elif isinstance(data['result'], dict):
                            print(f"   📊 데이터 키: {list(data['result'].keys())}")
                    elif 'data' in data:
                        print(f"   📊 데이터 키: {list(data['data'].keys())}")
                    else:
                        print(f"   📊 응답 구조: {list(data.keys())}")
                        
            elif response.status_code == 401:
                print("   ❌ 401 - 인증 실패 (API 키 확인 필요)")
            elif response.status_code == 404:
                print("   ❌ 404 - 엔드포인트를 찾을 수 없음")
            elif response.status_code == 403:
                print("   ❌ 403 - 권한 없음")
            elif response.status_code == 503:
                print("   ❌ 503 - 서비스 없음")
            else:
                print(f"   ❌ 오류: {response.status_code}")
                print(f"   응답: {response.text[:200]}...")
                
        except Exception as e:
            print(f"   ❌ 예외 발생: {str(e)}")
        
        print()
    
    # 성공한 엔드포인트 요약
    print("=== 테스트 결과 요약 ===")
    print(f"총 테스트: {len(test_endpoints)}개")
    print(f"성공: {len(successful_endpoints)}개")
    print(f"실패: {len(test_endpoints) - len(successful_endpoints)}개")
    
    if successful_endpoints:
        print("\n✅ 성공한 엔드포인트:")
        for endpoint in successful_endpoints:
            print(f"   - {endpoint['name']}")
            print(f"     URL: {endpoint['url']}")
        
        print(f"\n🔧 작동하는 베이스 URL 패턴:")
        for pattern in working_patterns:
            print(f"   - {pattern}")
    else:
        print("\n❌ 모든 엔드포인트가 API 문서 링크만 반환합니다.")
        print("이는 다음 중 하나일 수 있습니다:")
        print("1. API 키가 유효하지 않음")
        print("2. API 키에 권한이 없음")
        print("3. 실제 엔드포인트가 다름")
        print("4. XT API가 현재 서비스 중이지 않음")
        print("\n💡 권장사항:")
        print("- XT 거래소 웹사이트에서 API 키 권한 확인")
        print("- API 키가 선물/스팟 거래 권한을 가지고 있는지 확인")
        print("- XT 공식 API 문서에서 최신 엔드포인트 확인")
    
    return successful_endpoints

if __name__ == "__main__":
    test_xt_api() 