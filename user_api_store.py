import sqlite3
from cryptography.fernet import Fernet
import os

FERNET_KEY = os.environ.get('FERNET_KEY')
if not FERNET_KEY:
    # 최초 실행 시 키 생성 및 환경변수로 안내
    FERNET_KEY = Fernet.generate_key()
    print(f"환경변수 FERNET_KEY로 아래 값을 등록하세요:\n{FERNET_KEY.decode()}")
fernet = Fernet(FERNET_KEY)

DB_PATH = 'user_apis.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS apis
                 (user_id INTEGER, exchange TEXT, api_key TEXT, api_secret TEXT, PRIMARY KEY(user_id, exchange))''')
    conn.commit()
    conn.close()

def save_api(user_id, exchange, api_key, api_secret):
    enc_key = fernet.encrypt(api_key.encode()).decode()
    enc_secret = fernet.encrypt(api_secret.encode()).decode()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('REPLACE INTO apis VALUES (?, ?, ?, ?)', (user_id, exchange, enc_key, enc_secret))
    conn.commit()
    conn.close()

def load_api(user_id, exchange):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT api_key, api_secret FROM apis WHERE user_id=? AND exchange=?', (user_id, exchange))
    row = c.fetchone()
    conn.close()
    if row:
        api_key = fernet.decrypt(row[0].encode()).decode()
        api_secret = fernet.decrypt(row[1].encode()).decode()
        return api_key, api_secret
    return None 