# 🤖 개선된 텔레그램 암호화폐 선물 거래 봇

사용자 친화적인 클릭 기반 인터페이스와 안전한 API 키 관리 기능을 제공하는 텔레그램 암호화폐 선물 거래 봇입니다.

## ✨ 주요 기능

### 🔑 안전한 API 키 관리
- **사용자별 데이터베이스 저장**: 각 사용자의 API 키를 안전하게 SQLite 데이터베이스에 저장
- **API 연결 테스트**: 설정한 API 키의 유효성을 즉시 확인
- **다중 거래소 지원**: XT, Backpack, Hyperliquid, Flipster 거래소 지원

### 🎯 사용자 친화적 인터페이스
- **클릭 기반 메뉴**: 텍스트 입력 대신 버튼 클릭으로 모든 기능 사용
- **직관적인 네비게이션**: 메인 메뉴 → 서브 메뉴 → 기능 실행의 단계별 구조
- **실시간 상태 표시**: API 키 설정 상태, 잔고, 포지션 등을 실시간으로 확인

### 💰 거래 기능
- **잔고 조회**: 각 거래소별 실시간 잔고 확인
- **거래쌍 조회**: 거래 가능한 선물 심볼 목록 확인
- **포지션 관리**: 롱/숏 포지션 오픈 및 종료
- **포지션 조회**: 현재 보유 포지션 상태 확인

## 🚀 시작하기

### 1. 봇 시작
```
/start
```

### 2. API 키 설정
1. **API 키 관리** 버튼 클릭
2. 원하는 거래소 선택
3. 다음 형식으로 API 키 입력:
   ```
   /setapi [거래소] [API_KEY] [SECRET_KEY]
   ```
   예시: `/setapi xt YOUR_API_KEY YOUR_SECRET_KEY`

### 3. 기능 사용
- **💰 잔고 조회**: 거래소 선택 후 잔고 확인
- **📈 거래쌍 조회**: 거래 가능한 심볼 목록 확인
- **📊 포지션 관리**: 포지션 조회 및 종료
- **🔄 거래하기**: 롱/숏 포지션 오픈

## 📋 지원 명령어

### 기본 명령어
- `/start` - 메인 메뉴 표시
- `/help` - 도움말 표시
- `/test` - 봇 연결 테스트
- `/ping` - 봇 상태 확인

### API 관리
- `/setapi [거래소] [API_KEY] [SECRET_KEY]` - API 키 설정

### 거래 기능
- `/balance [거래소]` - 잔고 조회
- `/positions [거래소]` - 포지션 조회
- `/trade [거래소] [심볼] [방향] [수량] [레버리지]` - 포지션 오픈
- `/close [거래소] [심볼]` - 포지션 종료

## 🏦 지원 거래소

| 거래소 | API 키 타입 | 특별 요구사항 |
|--------|-------------|---------------|
| **XT Exchange** | API Key + Secret | 선물 거래 권한 필요 |
| **Backpack Exchange** | API Key + Private Key | Ed25519 서명 필요 |
| **Hyperliquid** | API Key + Secret | CCXT 라이브러리 사용 |
| **Flipster** | API Key + Secret | CCXT 라이브러리 사용 |

## 🔧 설치 및 설정

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
# 텔레그램 봇 토큰 (app.py에서 직접 설정 가능)
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. 서버 실행
```bash
python app.py
```

### 4. 웹훅 설정
```
https://your-domain.com/setup-webhook
```

## 📊 데이터베이스 구조

### user_api_keys 테이블
```sql
CREATE TABLE user_api_keys (
    user_id INTEGER PRIMARY KEY,
    xt_api_key TEXT,
    xt_api_secret TEXT,
    backpack_api_key TEXT,
    backpack_private_key TEXT,
    hyperliquid_api_key TEXT,
    hyperliquid_api_secret TEXT,
    flipster_api_key TEXT,
    flipster_api_secret TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🛡️ 보안 기능

- **사용자별 API 키 분리**: 각 사용자의 API 키를 개별적으로 저장
- **데이터베이스 암호화**: SQLite 데이터베이스에 안전하게 저장
- **API 키 검증**: 설정 시 즉시 API 연결 테스트 수행
- **오류 처리**: 모든 API 호출에 대한 안전한 오류 처리

## 🎨 사용자 인터페이스

### 메인 메뉴
```
🤖 암호화폐 선물 거래 봇

버튼을 클릭하여 원하는 기능을 선택하세요!

지원 거래소:
• XT Exchange
• Backpack Exchange
• Hyperliquid
• Flipster

먼저 API 키를 설정해주세요!

[🔑 API 키 관리] [💰 잔고 조회]
[📊 포지션 관리] [🔄 거래하기]
[⚙️ 설정] [❓ 도움말]
```

### API 관리 메뉴
```
🔑 API 키 관리

각 거래소의 API 키 상태를 확인하고 설정할 수 있습니다.

[XT Exchange ✅ 설정됨]
[Backpack Exchange ❌ 미설정]
[Hyperliquid ❌ 미설정]
[Flipster ❌ 미설정]
[🔙 메인 메뉴]
```

## 🔄 업데이트 내역

### v2.0 (현재 버전)
- ✅ 사용자 친화적 클릭 기반 인터페이스 추가
- ✅ 안전한 API 키 데이터베이스 관리
- ✅ 실시간 API 연결 테스트
- ✅ 개선된 오류 처리 및 사용자 피드백
- ✅ 다중 거래소 지원 확장

### v1.0 (이전 버전)
- ✅ 기본 텍스트 명령어 지원
- ✅ 4개 거래소 지원
- ✅ 기본 거래 기능

## 📞 지원

문제가 발생하거나 기능 요청이 있으시면 이슈를 등록해주세요.

## ⚠️ 주의사항

- **API 키 보안**: API 키는 절대 타인과 공유하지 마세요
- **거래 위험**: 암호화폐 선물 거래는 높은 위험을 수반합니다
- **테스트 환경**: 실제 거래 전에 테스트넷에서 충분히 테스트하세요
- **자금 관리**: 투자 가능한 자금만 사용하고 리스크를 관리하세요

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. # Railway 배포 트리거 - Sat Aug  2 11:08:19 KST 2025
