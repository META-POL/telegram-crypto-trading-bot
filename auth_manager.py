from telegram import Update
from telegram.ext import ContextTypes
from config import Config
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self):
        self.allowed_channel_id = Config.ALLOWED_CHANNEL_ID
        self.allowed_user_ids = [int(uid.strip()) for uid in Config.ALLOWED_USER_IDS if uid.strip()]
    
    def is_user_authorized(self, user_id: int) -> bool:
        """사용자가 허용된 사용자인지 확인"""
        return user_id in self.allowed_user_ids
    
    def is_channel_authorized(self, chat_id: int) -> bool:
        """채팅이 허용된 채널인지 확인"""
        return str(chat_id) == self.allowed_channel_id
    
    def is_user_in_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """사용자가 허용된 채널에 있는지 확인"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            # 채널이 허용된 채널인지 확인
            if not self.is_channel_authorized(chat_id):
                logger.warning(f"Unauthorized channel access attempt: {chat_id}")
                return False
            
            # 사용자가 허용된 사용자인지 확인
            if not self.is_user_authorized(user_id):
                logger.warning(f"Unauthorized user access attempt: {user_id}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking user authorization: {e}")
            return False
    
    @staticmethod
    def require_auth(func):
        """인증이 필요한 함수를 위한 데코레이터"""
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            auth_manager = AuthManager()
            if not auth_manager.is_user_in_channel(update, context):
                await update.message.reply_text(
                    "⚠️ 접근 권한이 없습니다.\n"
                    "1. 허용된 채널에 입장했는지 확인하세요.\n"
                    "2. 관리자에게 사용자 ID를 등록 요청하세요."
                )
                return
            return await func(update, context, *args, **kwargs)
        return wrapper
    
    def get_user_info(self, update: Update) -> dict:
        """사용자 정보 반환"""
        user = update.effective_user
        return {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        } 