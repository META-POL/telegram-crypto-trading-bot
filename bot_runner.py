#!/usr/bin/env python3
"""
GitHub Actions용 봇 실행 스크립트
GitHub Actions에서 24/7 봇 운영을 위한 스크립트
"""

import os
import time
import signal
import sys
from telegram_bot import main as run_telegram_bot

def signal_handler(sig, frame):
    """시그널 핸들러 - 봇 종료 시 정리"""
    print("봇을 종료합니다...")
    sys.exit(0)

def main():
    """메인 실행 함수"""
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🤖 텔레그램 암호화폐 트레이딩 봇 시작...")
    print("GitHub Actions에서 실행 중...")
    
    # 환경 변수 확인
    required_env_vars = [
        'TELEGRAM_BOT_TOKEN',
        'ALLOWED_CHANNEL_ID', 
        'ALLOWED_USER_IDS',
        'EXCHANGE_API_KEY',
        'EXCHANGE_SECRET'
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ 누락된 환경 변수: {', '.join(missing_vars)}")
        print("GitHub Secrets에서 환경 변수를 설정해주세요.")
        return
    
    print("✅ 모든 환경 변수가 설정되었습니다.")
    
    try:
        # 봇 실행
        run_telegram_bot()
    except KeyboardInterrupt:
        print("봇이 중단되었습니다.")
    except Exception as e:
        print(f"봇 실행 중 오류 발생: {e}")
        # 오류 발생 시 5분 후 재시작
        print("5분 후 재시작합니다...")
        time.sleep(300)
        main()

if __name__ == "__main__":
    main() 