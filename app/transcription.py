import os
from datetime import datetime
import whisper
import torch
import logging
from utils import TMP_DIR, compute_file_hash, get_device
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
        self.model = None
        self.device = get_device()
        if self.device == 'cpu':
            logger.warning("CUDA not available. Using CPU for transcription.")
        else:
            logger.info("Using CUDA for transcription.")

    def load_model(self):
        if not self.model:
            self.model = whisper.load_model('turbo', device=self.device)
            logger.info("Whisper model loaded.")

    def valid_languages(self):
        return whisper.tokenizer.LANGUAGES.keys()

    def identify_language(self, file_path) -> tuple:
        '''
        Identify the language of the audio file
        :param file_path: path to the audio file
        :return: language code, dictionary of probabilities

        WARNING: This is not needed since it is already done in the whisper transcribe method
        use it only if you want to get the language code and probabilities
        '''
        logger.info(f"Identifying language of {file_path}")
        # load audio and pad/trim it to fit 30 seconds
        audio = whisper.load_audio(file_path)
        audio = whisper.pad_or_trim(audio)

        # make log-Mel spectrogram and move to the same device as the model
        mel = whisper.log_mel_spectrogram(audio, n_mels=128).to(self.model.device)
        logger.info(f"Mel shape")

        # detect the spoken language
        _, probs = self.model.detect_language(mel)
        logger.info(f"Detected languages: {probs}")
        # get the language with the highest probability
        language = max(probs, key=probs.get)
        logger.info(f"Identified language: {language}")
        return language, probs

    def transcribe_audio(self, file_path, language: str, group_id: int, user_id: int, author_name: str, timestamp, is_allowed: bool=False) -> tuple:
        # Compute hash
        audio_hash = compute_file_hash(file_path, language)

        # Check if transcription exists
        transcription = self.db.get_transcription(audio_hash)
        if transcription:
            logger.info("Transcription found in cache.")
            # Add the transcription as a message
            self.db.add_message(
                group_id=group_id,
                user_id=user_id,
                author_name=author_name,
                message_text=transcription,
                timestamp=timestamp
            )
            return transcription, True  # Cached
        elif not is_allowed:
            logger.info("Transcription not allowed.")
            return "", False

        # Transcribe audio
        self.load_model()
        try:
            result = self.model.transcribe(file_path, language=language)
            transcription = result['text'].strip()
            # Save transcription to DB
            self.db.save_transcription(audio_hash, transcription, group_id)
            # Add the transcription as a message
            self.db.add_message(
                group_id=group_id,
                user_id=user_id,
                author_name=author_name,
                message_text=transcription,
                timestamp=timestamp
            )
            return transcription, False  # Not cached
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            raise e
        finally:
            # Clear RAM memory
            del self.model
            self.model = None
            # Clear GPU memory
            if self.device == 'cuda':
                torch.cuda.empty_cache()
