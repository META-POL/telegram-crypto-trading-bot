# 🤖 텔레그램 암호화폐 트레이딩 봇

암호화폐 거래소와 연동하여 실시간 시장 분석과 매매 신호를 제공하는 텔레그램 봇입니다.

## ✨ 주요 기능

- 🔐 **보안 인증**: 허용된 채널과 사용자만 접근 가능
- 📊 **실시간 시장 분석**: RSI, MACD, 이동평균선, 볼린저 밴드, 스토캐스틱 등
- 💰 **현재가 조회**: 실시간 가격 및 24시간 변동률
- 💵 **잔고 조회**: 거래소 계좌 잔고 확인
- 🎯 **매매 신호**: 기술적 지표 기반 매수/매도 신호
- 🖥️ **인터랙티브 메뉴**: 버튼 기반 사용자 인터페이스

## 🛠️ 설치 및 설정

### 1. 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`env_example.txt` 파일을 참고하여 `.env` 파일을 생성하세요:

```bash
cp env_example.txt .env
```

`.env` 파일에서 다음 정보를 설정하세요:

#### 텔레그램 봇 설정
1. **텔레그램 봇 토큰 생성**:
   - [@BotFather](https://t.me/botfather)에서 봇 생성
   - 받은 토큰을 `TELEGRAM_BOT_TOKEN`에 설정

2. **채널 ID 확인**:
   - 봇을 채널에 추가
   - 채널에서 메시지를 보낸 후 `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`에서 채널 ID 확인
   - `ALLOWED_CHANNEL_ID`에 설정

3. **사용자 ID 설정**:
   - 허용할 사용자들의 텔레그램 ID를 `ALLOWED_USER_IDS`에 쉼표로 구분하여 설정

#### 거래소 API 설정
1. **Binance API 키 생성**:
   - Binance 계정에서 API 키 생성
   - `EXCHANGE_API_KEY`와 `EXCHANGE_SECRET` 설정

## 🚀 실행 방법

```bash
python telegram_bot.py
```

## 📱 사용법

### 기본 명령어

- `/start` - 봇 시작 및 사용자 정보 확인
- `/help` - 도움말 및 사용법
- `/menu` - 인터랙티브 메뉴 열기

### 트레이딩 명령어

- `/price [심볼]` - 현재가 조회 (예: `/price BTC/USDT`)
- `/analysis [심볼]` - 기술적 분석 결과
- `/balance` - 계좌 잔고 조회
- `/signals [심볼]` - 매매 신호 분석

### 예시

```
/price BTC/USDT
/analysis ETH/USDT
/signals ADA/USDT
/balance
```

## 🔧 지원 거래소

- **Binance** (기본)
- **Upbit** (설정 변경 필요)

## 📊 기술적 지표

- **RSI (Relative Strength Index)**: 과매수/과매도 구간 판단
- **MACD**: 추세 전환 신호
- **이동평균선**: 20일, 50일 이동평균
- **볼린저 밴드**: 변동성 및 가격 범위
- **스토캐스틱**: 모멘텀 지표

## ⚠️ 주의사항

- 이 봇은 **투자 조언이 아닌 정보 제공** 목적입니다
- 실제 거래 전 충분한 검토가 필요합니다
- 손실에 대한 책임은 사용자에게 있습니다
- API 키는 안전하게 보관하세요

## 🔒 보안 기능

- 허용된 채널에서만 작동
- 허용된 사용자만 접근 가능
- 모든 거래 정보는 안전하게 암호화

## 📁 프로젝트 구조

```
NEW_BOT_project/
├── telegram_bot.py      # 메인 봇 파일
├── trading_bot.py       # 거래소 연동 및 분석
├── auth_manager.py      # 인증 관리
├── config.py           # 설정 관리
├── requirements.txt    # 필요한 패키지
├── env_example.txt     # 환경 변수 예시
└── README.md          # 프로젝트 설명
```

## 🐛 문제 해결

### 봇이 응답하지 않는 경우
1. 봇 토큰이 올바른지 확인
2. 봇이 채널에 추가되었는지 확인
3. 사용자 ID가 허용 목록에 있는지 확인

### 거래소 연결 오류
1. API 키와 시크릿이 올바른지 확인
2. API 권한이 적절히 설정되었는지 확인
3. 네트워크 연결 상태 확인

## 📞 지원

문제가 발생하거나 개선 사항이 있으시면 이슈를 등록해주세요.

---

**면책 조항**: 이 소프트웨어는 교육 및 정보 제공 목적으로만 제공됩니다. 실제 투자 결정은 신중히 하시기 바랍니다. 