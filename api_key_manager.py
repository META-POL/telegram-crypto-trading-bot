#!/usr/bin/env python3
"""
API 키 관리 시스템
사용자가 직접 API 키를 입력하고 저장/관리
"""

import sqlite3
import logging
from cryptography.fernet import Fernet
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIKeyManager:
    def __init__(self):
        self.db_path = 'user_apis.db'
        self.init_db()
        
        # Fernet 키 설정
        fernet_key = os.environ.get('FERNET_KEY')
        if fernet_key:
            self.cipher = Fernet(fernet_key.encode())
        else:
            # 테스트용 키 (실제 배포시에는 환경변수 사용)
            self.cipher = Fernet(b'your-32-byte-fernet-key-here-test-only')
    
    def init_db(self):
        """데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # API 키 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exchange TEXT NOT NULL,
                    trading_type TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    api_secret TEXT,
                    private_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, exchange, trading_type)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("API 키 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 오류: {e}")
    
    def encrypt_data(self, data):
        """데이터 암호화"""
        if not data:
            return None
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data):
        """데이터 복호화"""
        if not encrypted_data:
            return None
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def save_api_keys(self, user_id, exchange, trading_type, api_key, api_secret=None, private_key=None):
        """API 키 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 데이터 암호화
            encrypted_api_key = self.encrypt_data(api_key)
            encrypted_api_secret = self.encrypt_data(api_secret) if api_secret else None
            encrypted_private_key = self.encrypt_data(private_key) if private_key else None
            
            # 기존 키가 있는지 확인
            cursor.execute('''
                SELECT id FROM api_keys 
                WHERE user_id = ? AND exchange = ? AND trading_type = ?
            ''', (user_id, exchange, trading_type))
            
            existing = cursor.fetchone()
            
            if existing:
                # 기존 키 업데이트
                cursor.execute('''
                    UPDATE api_keys 
                    SET api_key = ?, api_secret = ?, private_key = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND exchange = ? AND trading_type = ?
                ''', (encrypted_api_key, encrypted_api_secret, encrypted_private_key, user_id, exchange, trading_type))
                message = f"{exchange.capitalize()} {trading_type} API 키가 업데이트되었습니다."
            else:
                # 새 키 저장
                cursor.execute('''
                    INSERT INTO api_keys (user_id, exchange, trading_type, api_key, api_secret, private_key)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, exchange, trading_type, encrypted_api_key, encrypted_api_secret, encrypted_private_key))
                message = f"{exchange.capitalize()} {trading_type} API 키가 저장되었습니다."
            
            conn.commit()
            conn.close()
            
            return {
                'status': 'success',
                'message': message
            }
            
        except Exception as e:
            logger.error(f"API 키 저장 오류: {e}")
            return {
                'status': 'error',
                'message': f'API 키 저장 실패: {str(e)}'
            }
    
    def get_api_keys(self, user_id, exchange, trading_type):
        """API 키 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT api_key, api_secret, private_key 
                FROM api_keys 
                WHERE user_id = ? AND exchange = ? AND trading_type = ?
            ''', (user_id, exchange, trading_type))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                api_key, api_secret, private_key = result
                return {
                    'status': 'success',
                    'api_key': self.decrypt_data(api_key),
                    'api_secret': self.decrypt_data(api_secret) if api_secret else None,
                    'private_key': self.decrypt_data(private_key) if private_key else None
                }
            else:
                return {
                    'status': 'error',
                    'message': f'{exchange.capitalize()} {trading_type} API 키가 설정되지 않았습니다.'
                }
                
        except Exception as e:
            logger.error(f"API 키 조회 오류: {e}")
            return {
                'status': 'error',
                'message': f'API 키 조회 실패: {str(e)}'
            }
    
    def delete_api_keys(self, user_id, exchange, trading_type):
        """API 키 삭제"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM api_keys 
                WHERE user_id = ? AND exchange = ? AND trading_type = ?
            ''', (user_id, exchange, trading_type))
            
            conn.commit()
            conn.close()
            
            return {
                'status': 'success',
                'message': f'{exchange.capitalize()} {trading_type} API 키가 삭제되었습니다.'
            }
            
        except Exception as e:
            logger.error(f"API 키 삭제 오류: {e}")
            return {
                'status': 'error',
                'message': f'API 키 삭제 실패: {str(e)}'
            }
    
    def list_user_apis(self, user_id):
        """사용자의 모든 API 키 목록 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT exchange, trading_type, created_at, updated_at 
                FROM api_keys 
                WHERE user_id = ?
                ORDER BY exchange, trading_type
            ''', (user_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            if results:
                api_list = []
                for row in results:
                    exchange, trading_type, created_at, updated_at = row
                    api_list.append({
                        'exchange': exchange,
                        'trading_type': trading_type,
                        'created_at': created_at,
                        'updated_at': updated_at
                    })
                
                return {
                    'status': 'success',
                    'apis': api_list
                }
            else:
                return {
                    'status': 'error',
                    'message': '설정된 API 키가 없습니다.'
                }
                
        except Exception as e:
            logger.error(f"API 목록 조회 오류: {e}")
            return {
                'status': 'error',
                'message': f'API 목록 조회 실패: {str(e)}'
            }
    
    def has_api_keys(self, user_id, exchange, trading_type):
        """API 키 존재 여부 확인"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM api_keys 
                WHERE user_id = ? AND exchange = ? AND trading_type = ?
            ''', (user_id, exchange, trading_type))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"API 키 존재 확인 오류: {e}")
            return False

# 전역 인스턴스
api_manager = APIKeyManager() 