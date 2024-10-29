import logging
import os
import hashlib
from dotenv import load_dotenv

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
