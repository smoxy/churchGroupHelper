import os
from datetime import datetime
import logging
import requests
from utils import TMP_DIR, compute_file_hash, WHISPER_SERVICE_URL
from database import Database

# Enable logging
logConf = logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Transcriber:
    def __init__(self):
        self.db = Database.get_instance()
        self.service_url = WHISPER_SERVICE_URL
        logger.info(f"Whisper service URL: {self.service_url}")

    def valid_languages(self):
        # Lista delle lingue supportate da Whisper
        return [
            "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs",
            "ca", "cs", "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi",
            "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy",
            "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb",
            "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
            "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru",
            "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw",
            "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi",
            "yi", "yo", "yue", "zh"
        ]

    def identify_language(self, file_path) -> tuple:
        '''
        Identify the language of the audio file using the external service
        :param file_path: path to the audio file
        :return: language code, dictionary of probabilities

        WARNING: This is not needed since it is already done in the whisper transcribe method
        use it only if you want to get the language code and probabilities
        '''
        logger.info(f"Identifying language of {file_path}")
        
        try:
            # Prepare the request
            url = f"{self.service_url}/detect-language"
            
            with open(file_path, 'rb') as audio_file:
                files = {'audio_file': audio_file}
                params = {'encode': 'true'}
                
                response = requests.post(url, files=files, params=params, timeout=300)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Detected languages: {result}")
                
                # Il servizio restituisce un oggetto con la lingua e le probabilità
                # Formato atteso: {"detected_language": "it", "language_probability": 0.95}
                language = result.get('detected_language', 'en')
                probs = {language: result.get('language_probability', 1.0)}
                
                logger.info(f"Identified language: {language}")
                return language, probs
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during language detection: {e}")
            # Fallback to Italian if detection fails
            return 'it', {'it': 1.0}

    def transcribe_audio(self, file_path, language: str, group_id: int, user_id: int, author_name: str, timestamp, telegram_message_id: int = None, is_allowed: bool=False) -> tuple:
        # Compute hash
        audio_hash = compute_file_hash(file_path, language)

        # Check if transcription exists
        transcription = self.db.get_transcription(audio_hash)
        if transcription:
            logger.info("Transcription found in cache.")
            # Add the transcription as a message (only for groups - privacy)
            if group_id:
                message = self.db.add_message(
                    group_id=group_id,
                    user_id=user_id,
                    author_name=author_name,
                    message_text=transcription,
                    timestamp=timestamp,
                    telegram_message_id=telegram_message_id
                )
            return transcription, True  # Cached
        elif not is_allowed:
            logger.info("Transcription not allowed.")
            return "", False

        # Transcribe audio using external service
        try:
            url = f"{self.service_url}/asr"
            
            with open(file_path, 'rb') as audio_file:
                files = {'audio_file': audio_file}
                params = {
                    'encode': 'true',
                    'task': 'transcribe',
                    'language': language,
                    'output': 'txt'
                }
                
                logger.info(f"Sending transcription request to {url}")
                response = requests.post(url, files=files, params=params, timeout=300)
                response.raise_for_status()
                
                # Il servizio restituisce il testo direttamente quando output=txt
                transcription = response.text.strip()
                
                # Add the transcription as a message (only for groups - privacy)
                message_id = None
                if group_id:
                    message = self.db.add_message(
                        group_id=group_id,
                        user_id=user_id,
                        author_name=author_name,
                        message_text=transcription,
                        timestamp=timestamp,
                        telegram_message_id=telegram_message_id
                    )
                    # Get the message_id for foreign key reference
                    message_id = message.message_id if message else None
                
                # Save transcription to DB with message_id link (privacy: only for groups)
                self.db.save_transcription(
                    audio_hash=audio_hash,
                    transcription=transcription,
                    group_id=group_id,
                    message_id=message_id
                )
                
                return transcription, False  # Not cached
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during transcription: {e}")
            raise e
