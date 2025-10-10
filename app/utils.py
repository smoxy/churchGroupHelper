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

# Telegram constraints
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

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

def split_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list:
    """
    Split a long text into chunks that fit Telegram's message size limit.
    Tries to split at sentence boundaries when possible.
    
    :param text: The text to split
    :param max_length: Maximum length per message (default: 4096 for Telegram)
    :return: List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Try to split at sentence boundaries (. ! ? followed by space or newline)
    sentences = []
    current_sentence = ""
    
    for char in text:
        current_sentence += char
        if char in '.!?\n' and len(current_sentence) > 1:
            sentences.append(current_sentence)
            current_sentence = ""
    
    # Add any remaining text as a sentence
    if current_sentence:
        sentences.append(current_sentence)
    
    # Group sentences into chunks
    for sentence in sentences:
        # If a single sentence is longer than max_length, we need to split it
        if len(sentence) > max_length:
            # Split long sentence by words
            words = sentence.split()
            temp_chunk = ""
            for word in words:
                if len(temp_chunk) + len(word) + 1 <= max_length:
                    temp_chunk += word + " "
                else:
                    if temp_chunk:
                        chunks.append(temp_chunk.strip())
                    temp_chunk = word + " "
            if temp_chunk:
                if current_chunk and len(current_chunk) + len(temp_chunk) <= max_length:
                    current_chunk += temp_chunk
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = temp_chunk
        else:
            # Check if adding this sentence exceeds the limit
            if len(current_chunk) + len(sentence) <= max_length:
                current_chunk += sentence
            else:
                # Save current chunk and start a new one
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def send_action(action):
    """Sends `action` while processing func command."""
    def decorator(func):
        @wraps(func)
        async def command_func(update, context, *args, **kwargs):
            await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return await func(update, context,  *args, **kwargs)
        return command_func
    
    return decorator