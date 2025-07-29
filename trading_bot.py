import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from config import Config
import ta

logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, exchange_name='binance'):
        self.exchange_name = exchange_name
        self.exchange = None
        self.symbol = Config.DEFAULT_SYMBOL
        self.timeframe = Config.DEFAULT_TIMEFRAME
        
        # 거래소 초기화
        self._initialize_exchange()
    
    def _initialize_exchange(self):
        """거래소 초기화"""
        try:
            if self.exchange_name == 'binance':
                self.exchange = ccxt.binance({
                    'apiKey': Config.EXCHANGE_API_KEY,
                    'secret': Config.EXCHANGE_SECRET,
                    'sandbox': False,  # 실제 거래를 위해 False
                    'enableRateLimit': True
                })
            elif self.exchange_name == 'upbit':
                self.exchange = ccxt.upbit({
                    'apiKey': Config.EXCHANGE_API_KEY,
                    'secret': Config.EXCHANGE_SECRET,
                    'enableRateLimit': True
                })
            else:
                raise ValueError(f"Unsupported exchange: {self.exchange_name}")
            
            logger.info(f"Exchange {self.exchange_name} initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise
    
    def get_market_data(self, symbol=None, timeframe=None, limit=100):
        """시장 데이터 가져오기"""
        try:
            symbol = symbol or self.symbol
            timeframe = timeframe or self.timeframe
            
            # OHLCV 데이터 가져오기
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # DataFrame으로 변환
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return None
    
    def calculate_indicators(self, df):
        """기술적 지표 계산"""
        try:
            # 이동평균선
            df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
            df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
            
            # RSI
            df['rsi'] = ta.momentum.rsi(df['close'], window=14)
            
            # MACD
            macd = ta.trend.MACD(df['close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_histogram'] = macd.macd_diff()
            
            # 볼린저 밴드
            bb = ta.volatility.BollingerBands(df['close'])
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_middle'] = bb.bollinger_mavg()
            df['bb_lower'] = bb.bollinger_lband()
            
            # 스토캐스틱
            stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
            df['stoch_k'] = stoch.stoch()
            df['stoch_d'] = stoch.stoch_signal()
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def analyze_market(self, symbol=None):
        """시장 분석"""
        try:
            df = self.get_market_data(symbol)
            if df is None:
                return None
            
            df = self.calculate_indicators(df)
            
            # 최신 데이터
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            analysis = {
                'symbol': symbol or self.symbol,
                'current_price': latest['close'],
                'price_change': latest['close'] - prev['close'],
                'price_change_percent': ((latest['close'] - prev['close']) / prev['close']) * 100,
                'volume': latest['volume'],
                'indicators': {
                    'rsi': latest['rsi'],
                    'macd': latest['macd'],
                    'macd_signal': latest['macd_signal'],
                    'sma_20': latest['sma_20'],
                    'sma_50': latest['sma_50'],
                    'bb_upper': latest['bb_upper'],
                    'bb_lower': latest['bb_lower'],
                    'stoch_k': latest['stoch_k'],
                    'stoch_d': latest['stoch_d']
                },
                'signals': self._generate_signals(df)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
            return None
    
    def _generate_signals(self, df):
        """매매 신호 생성"""
        signals = []
        latest = df.iloc[-1]
        
        # RSI 과매수/과매도
        if latest['rsi'] > 70:
            signals.append("RSI 과매수 구간")
        elif latest['rsi'] < 30:
            signals.append("RSI 과매도 구간")
        
        # MACD 신호
        if latest['macd'] > latest['macd_signal']:
            signals.append("MACD 상승 신호")
        else:
            signals.append("MACD 하락 신호")
        
        # 이동평균선 크로스
        if latest['sma_20'] > latest['sma_50']:
            signals.append("단기 이평선이 장기 이평선 위")
        else:
            signals.append("단기 이평선이 장기 이평선 아래")
        
        # 볼린저 밴드
        if latest['close'] > latest['bb_upper']:
            signals.append("볼린저 밴드 상단 돌파")
        elif latest['close'] < latest['bb_lower']:
            signals.append("볼린저 밴드 하단 돌파")
        
        # 스토캐스틱
        if latest['stoch_k'] > 80:
            signals.append("스토캐스틱 과매수")
        elif latest['stoch_k'] < 20:
            signals.append("스토캐스틱 과매도")
        
        return signals
    
    def get_balance(self):
        """잔고 조회"""
        try:
            balance = self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return None
    
    def get_ticker(self, symbol=None):
        """현재가 조회"""
        try:
            symbol = symbol or self.symbol
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker: {e}")
            return None 