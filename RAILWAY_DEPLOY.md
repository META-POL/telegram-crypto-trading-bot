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

배포 후 다음 URL로 헬스체크를 확인하세요:
- `https://your-app-name.railway.app/`
- `https://your-app-name.railway.app/health`

### 4. 로그 확인

Railway 대시보드에서 로그를 확인하여 오류를 진단하세요.

### 5. 문제 해결

#### 일반적인 문제들:

1. **환경 변수 누락**
   - TELEGRAM_BOT_TOKEN이 설정되었는지 확인
   - FERNET_KEY가 설정되었는지 확인

2. **포트 문제**
   - Railway는 자동으로 PORT 환경 변수를 설정
   - 코드에서 `os.environ.get('PORT', 5000)` 사용

3. **의존성 문제**
   - requirements.txt에 모든 필요한 패키지가 포함되어 있는지 확인

4. **헬스체크 실패**
   - Flask 앱이 정상적으로 시작되는지 확인
   - `/` 또는 `/health` 엔드포인트가 응답하는지 확인

### 6. 배포 후 테스트

1. 텔레그램에서 봇에게 `/start` 명령어 전송
2. 메뉴가 정상적으로 표시되는지 확인
3. API 등록 기능 테스트
4. 심볼 조회 및 잔고 조회 테스트

## 📝 참고사항

- Railway는 자동으로 HTTPS를 제공합니다
- 무료 플랜에서는 월 사용량 제한이 있습니다
- 로그는 Railway 대시보드에서 실시간으로 확인할 수 있습니다 