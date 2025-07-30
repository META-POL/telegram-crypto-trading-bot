# Railway 배포 가이드

## 🚀 Railway 배포 설정

### 1. 환경 변수 설정

Railway 대시보드에서 다음 환경 변수들을 설정하세요:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
FERNET_KEY=your_fernet_key_here
```

### 2. Fernet 키 생성

Fernet 키를 생성하려면:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. 배포 확인

배포 후 다음 로그 메시지들을 확인하세요:
- `🤖 텔레그램 봇 시작 중...`
- `✅ 텔레그램 봇이 성공적으로 시작되었습니다!`
- `🔄 폴링 시작...`

### 4. 봇 테스트

텔레그램에서 다음 명령어들로 봇을 테스트하세요:
- `/start` - 봇 시작
- `/balance` - 잔고 조회
- `/symbols` - 심볼 조회
- `/testapi` - API 테스트

### 5. 문제 해결

#### 일반적인 문제들:

1. **환경 변수 누락**
   - TELEGRAM_BOT_TOKEN이 설정되었는지 확인
   - FERNET_KEY가 설정되었는지 확인

2. **배포 실패**
   - Railway 대시보드에서 로그 확인
   - 빌드 오류 메시지 확인

3. **봇 응답 없음**
   - 텔레그램 봇 토큰이 올바른지 확인
   - 채널 멤버십 확인

### 6. 현재 지원 기능

- ✅ **잔고 조회**: Backpack 거래소
- ✅ **심볼 조회**: Backpack 거래소
- ✅ **API 테스트**: Backpack 거래소
- ✅ **도움말**: 사용법 안내

### 7. 파일 구조

```
├── app.py              # 메인 봇 실행 파일
├── trading_bot_unified.py  # 거래소 API 통합
├── user_api_store.py   # API 키 저장
├── requirements.txt    # Python 패키지
├── Procfile           # Railway 실행 명령어
├── railway.json       # Railway 배포 설정
└── runtime.txt        # Python 버전
```

## 📝 참고사항

- Railway는 자동으로 HTTPS를 제공합니다
- 무료 플랜에서는 월 사용량 제한이 있습니다
- 로그는 Railway 대시보드에서 실시간으로 확인할 수 있습니다
- 현재 Backpack 거래소만 지원됩니다 