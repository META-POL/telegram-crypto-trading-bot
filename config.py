import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    # 텔레그램 봇 설정
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    ALLOWED_CHANNEL_ID = os.getenv('ALLOWED_CHANNEL_ID')  # 허용된 채널 ID
    ALLOWED_USER_IDS = os.getenv('ALLOWED_USER_IDS', '').split(',')  # 허용된 사용자 ID 목록
    
    # 거래소 설정
    EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY')
    EXCHANGE_SECRET = os.getenv('EXCHANGE_SECRET')
    EXCHANGE_PASSPHRASE = os.getenv('EXCHANGE_PASSPHRASE', '')  # 일부 거래소에서 필요
    
    # 거래 설정
    DEFAULT_SYMBOL = 'BTC/USDT'
    DEFAULT_TIMEFRAME = '1h'
    
    # 위험 관리 설정
    MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '0.1'))  # 최대 포지션 크기 (10%)
    STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '2.0'))  # 손절 비율
    TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '4.0'))  # 익절 비율 