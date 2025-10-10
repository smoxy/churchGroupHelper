import logging
import os
import hashlib
from dotenv import load_dotenv
from functools import wraps

# Load environment variables
load_dotenv()

# Enable logging
logConf = logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
TOKEN = os.getenv('TOKEN')

# Admin IDs
ADMINS = [int(admin) for admin in os.getenv('ADMINS').split(',')]

# Whisper service configuration
WHISPER_SERVICE_HOST = os.getenv('WHISPER_SERVICE_HOST', 'whisper')
WHISPER_SERVICE_PORT = os.getenv('WHISPER_SERVICE_PORT', '9000')
WHISPER_SERVICE_URI = os.getenv('WHISPER_SERVICE_URI', '')

# Construct base URL for Whisper service
if WHISPER_SERVICE_URI:
    WHISPER_SERVICE_URL = f"{WHISPER_SERVICE_URI.rstrip('/')}"
else:
    WHISPER_SERVICE_URL = f"http://{WHISPER_SERVICE_HOST}:{WHISPER_SERVICE_PORT}"

# Temporary directory
TMP_DIR = f'{os.sep}tmp{os.sep}cache'

# Ensure TMP_DIR exists
os.makedirs(TMP_DIR, exist_ok=True)

def compute_file_hash(file_path, lang: str='it'):
    """Compute SHA-256 hash of a file."""
    logger.info(f'Computing hash of {file_path} with language {lang}')
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        buf = f.read()
        salt = lang.encode()
        buf_salted = buf + salt
        hasher.update(buf_salted)
    return hasher.hexdigest()

def is_admin(user_id: int):
    """Check if a user is an admin."""
    return user_id in ADMINS

def get_device():
    """Get the device for torch."""
    import torch
    return 'cuda' if torch.cuda.is_available() else 'cpu'

def send_action(action):
    """Sends `action` while processing func command."""
    def decorator(func):
        @wraps(func)
        async def command_func(update, context, *args, **kwargs):
            await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return await func(update, context,  *args, **kwargs)
        return command_func
    
    return decorator