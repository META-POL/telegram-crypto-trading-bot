#!/usr/bin/env python3
"""
거래소별 API 지원 정보 및 대안 제공
"""

class ExchangeInfo:
    """거래소 정보 관리 클래스"""
    
    def __init__(self):
        self.exchange_data = {
            'xt': {
                'name': 'XT Exchange',
                'api_support': True,
                'spot_support': True,
                'futures_support': True,
                'api_requirements': ['API Key', 'API Secret'],
                'website': 'https://www.xt.com',
                'api_docs': 'https://doc.xt.com',
                'alternatives': ['binance', 'okx', 'bybit']
            },
            'backpack': {
                'name': 'Backpack',
                'api_support': True,
                'spot_support': True,
                'futures_support': True,
                'api_requirements': ['API Key', 'Private Key'],
                'website': 'https://backpack.exchange',
                'api_docs': 'https://docs.backpack.exchange',
                'alternatives': ['binance', 'okx', 'bybit']
            },
            'hyperliquid': {
                'name': 'Hyperliquid',
                'api_support': True,
                'spot_support': False,
                'futures_support': True,
                'api_requirements': ['API Key', 'API Secret'],
                'website': 'https://hyperliquid.xyz',
                'api_docs': 'https://hyperliquid.gitbook.io/hyperliquid',
                'alternatives': ['binance', 'okx', 'bybit']
            },
            'flipster': {
                'name': 'Flipster',
                'api_support': True,
                'spot_support': True,
                'futures_support': True,
                'api_requirements': ['API Key', 'API Secret'],
                'website': 'https://flipster.io',
                'api_docs': 'https://docs.flipster.io',
                'alternatives': ['binance', 'okx', 'bybit']
            },
            'binance': {
                'name': 'Binance',
                'api_support': True,
                'spot_support': True,
                'futures_support': True,
                'api_requirements': ['API Key', 'API Secret'],
                'website': 'https://www.binance.com',
                'api_docs': 'https://binance-docs.github.io/apidocs',
                'alternatives': ['okx', 'bybit', 'xt']
            },
            'okx': {
                'name': 'OKX',
                'api_support': True,
                'spot_support': True,
                'futures_support': True,
                'api_requirements': ['API Key', 'API Secret', 'Passphrase'],
                'website': 'https://www.okx.com',
                'api_docs': 'https://www.okx.com/docs-v5',
                'alternatives': ['binance', 'bybit', 'xt']
            },
            'bybit': {
                'name': 'Bybit',
                'api_support': True,
                'spot_support': True,
                'futures_support': True,
                'api_requirements': ['API Key', 'API Secret'],
                'website': 'https://www.bybit.com',
                'api_docs': 'https://bybit-exchange.github.io/docs',
                'alternatives': ['binance', 'okx', 'xt']
            }
        }
    
    def get_exchange_info(self, exchange):
        """거래소 정보 조회"""
        return self.exchange_data.get(exchange.lower(), None)
    
    def get_all_exchanges(self):
        """모든 거래소 목록 반환"""
        return list(self.exchange_data.keys())
    
    def get_supported_exchanges(self):
        """API를 지원하는 거래소 목록 반환"""
        return [ex for ex, info in self.exchange_data.items() if info['api_support']]
    
    def get_spot_exchanges(self):
        """현물 거래를 지원하는 거래소 목록 반환"""
        return [ex for ex, info in self.exchange_data.items() if info['spot_support']]
    
    def get_futures_exchanges(self):
        """선물 거래를 지원하는 거래소 목록 반환"""
        return [ex for ex, info in self.exchange_data.items() if info['futures_support']]
    
    def get_alternatives(self, exchange):
        """대체 거래소 목록 반환"""
        info = self.get_exchange_info(exchange)
        if info:
            return info.get('alternatives', [])
        return []
    
    def format_exchange_info(self, exchange):
        """거래소 정보를 포맷팅하여 반환"""
        info = self.get_exchange_info(exchange)
        if not info:
            return f"❌ {exchange.capitalize()} 거래소 정보를 찾을 수 없습니다."
        
        text = f"🏪 **{info['name']}**\n\n"
        
        # API 지원 여부
        if info['api_support']:
            text += "✅ **API 지원**: 예\n"
            text += f"🔑 **필요 API**: {', '.join(info['api_requirements'])}\n"
        else:
            text += "❌ **API 지원**: 아니오\n"
            text += "💡 **대안**: 웹 스크래핑 또는 수동 입력\n"
        
        # 거래 유형 지원
        text += f"📈 **현물 거래**: {'✅' if info['spot_support'] else '❌'}\n"
        text += f"📊 **선물 거래**: {'✅' if info['futures_support'] else '❌'}\n"
        
        # 링크
        text += f"🌐 **웹사이트**: {info['website']}\n"
        if info['api_support']:
            text += f"📚 **API 문서**: {info['api_docs']}\n"
        
        # 대체 거래소
        if info['alternatives']:
            alt_names = [self.exchange_data[alt]['name'] for alt in info['alternatives']]
            text += f"🔄 **대체 거래소**: {', '.join(alt_names)}\n"
        
        return text
    
    def get_no_api_solution(self, exchange):
        """API가 없는 거래소의 대안 제공"""
        info = self.get_exchange_info(exchange)
        if not info or info['api_support']:
            return None
        
        text = f"💡 **{info['name']} API 대안**\n\n"
        text += "이 거래소는 API를 제공하지 않습니다.\n\n"
        text += "**가능한 대안:**\n"
        text += "1. **웹 스크래핑**: 웹사이트에서 직접 데이터 수집\n"
        text += "2. **수동 입력**: 사용자가 직접 잔고 정보 입력\n"
        text += "3. **대체 거래소**: API를 제공하는 유사한 거래소 사용\n\n"
        
        if info['alternatives']:
            text += "**추천 대체 거래소:**\n"
            for alt in info['alternatives']:
                alt_info = self.exchange_data[alt]
                text += f"• **{alt_info['name']}**: {', '.join(alt_info['api_requirements'])}\n"
        
        return text

# 전역 인스턴스
exchange_info = ExchangeInfo() 