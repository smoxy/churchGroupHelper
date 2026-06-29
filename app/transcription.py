import os
from datetime import datetime
import logging
import requests
import time
from utils import TMP_DIR, compute_file_hash, WHISPER_SERVICE_URL, OLLAMA_API_KEY, TRANSCRIPTION_IMPROVER_MODEL
from database import Database
from transcription_improver import create_improver

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
        
        # Initialize transcription improver (auto-detects OpenAI or Ollama)
        self.improver = None
        try:
            self.improver = create_improver(model_name=TRANSCRIPTION_IMPROVER_MODEL)
            logger.info(f"Transcription improver initialized (auto-detected provider)")
        except Exception as e:
            logger.warning(f"Failed to initialize transcription improver: {e}")
            logger.info("Transcription improvement will be disabled")

    def valid_languages(self):
        # The 25 European languages supported by nvidia/parakeet-tdt-0.6b-v3.
        return [
            "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr",
            "hr", "hu", "it", "lt", "lv", "mt", "nl", "pl", "pt", "ro",
            "ru", "sk", "sl", "sv", "uk",
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
                self.db.add_message(
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

        # Transcribe audio using external service with retry logic
        # The Parakeet ASR container unloads the model from VRAM after IDLE_TIMEOUT
        # (default 5 min) of inactivity. It needs time to reload the model on a new request.
        max_retries = 7
        retry_delay = 5  # seconds between retries
        url = f"{self.service_url}/transcribe"
        
        for attempt in range(1, max_retries + 1):
            try:
                
                logger.info(f"[Attempt {attempt}/{max_retries}] Sending transcription request to {url} for language '{language}'")
                
                with open(file_path, 'rb') as audio_file:
                    files = {'audio_file': audio_file}
                    # Parakeet v3 auto-detects the language; we still send it for
                    # logging/compatibility and reuse it later for the improver.
                    params = {'language': language}

                    start_time = time.time()
                    response = requests.post(url, files=files, params=params, timeout=300)
                    elapsed_time = time.time() - start_time

                    logger.info(f"[Attempt {attempt}/{max_retries}] Response received in {elapsed_time:.2f}s - Status code: {response.status_code}")

                    response.raise_for_status()

                    # The Parakeet service returns JSON: {"text": ..., "language": ..., "empty": bool}
                    data = response.json()
                    transcription = (data.get('text') or '').strip()
                    # Language auto-detected by the service from the transcribed text;
                    # use it for the improver so it matches the actually-spoken language
                    # (falls back to the requested language if detection was inconclusive).
                    detected_language = data.get('language') or language

                    logger.info(f"[Attempt {attempt}/{max_retries}] Transcription successful - Length: {len(transcription)} characters (detected language: {detected_language})")

                    # Improve transcription quality if improver is available
                    if self.improver and transcription:
                        try:
                            logger.info("Improving transcription quality with LangChain pipeline...")
                            logger.debug(f"Original transcription preview (first 200 chars): {transcription[:200]}")

                            improved_transcription = self.improver.improve(transcription, detected_language)
                            
                            logger.debug(f"Returned improved_transcription type: {type(improved_transcription)}")
                            logger.debug(f"Returned improved_transcription length: {len(improved_transcription) if improved_transcription else 0}")
                            
                            if improved_transcription and improved_transcription.strip():
                                logger.info(
                                    f"Transcription improved: "
                                    f"Original length: {len(transcription)} chars, "
                                    f"Improved length: {len(improved_transcription)} chars"
                                )
                                logger.debug(f"Improved transcription preview (first 200 chars): {improved_transcription[:200]}")
                                transcription = improved_transcription
                            else:
                                logger.warning(
                                    f"Improvement returned empty/invalid result "
                                    f"(type: {type(improved_transcription)}, "
                                    f"length: {len(improved_transcription) if improved_transcription else 0}), "
                                    f"keeping original"
                                )
                        except Exception as e:
                            logger.error(f"Failed to improve transcription: {e}", exc_info=True)
                            logger.info("Keeping original transcription due to improvement error")
                    
                    # Add the transcription as a message (only for groups - privacy)
                    message_id = None
                    if group_id:
                        message_id = self.db.add_message(
                            group_id=group_id,
                            user_id=user_id,
                            author_name=author_name,
                            message_text=transcription,
                            timestamp=timestamp,
                            telegram_message_id=telegram_message_id
                        )
                    
                    # Save transcription to DB with message_id link (privacy: only for groups)
                    self.db.save_transcription(
                        audio_hash=audio_hash,
                        transcription=transcription,
                        group_id=group_id,
                        message_id=message_id
                    )
                    
                    logger.info(f"Transcription saved successfully (audio_hash: {audio_hash})")
                    return transcription, False  # Not cached
                    
            except requests.exceptions.Timeout as e:
                logger.error(
                    f"[Attempt {attempt}/{max_retries}] Timeout error during transcription request: {str(e)}\n"
                    f"  - URL: {url}\n"
                    f"  - Language: {language}\n"
                    f"  - Timeout threshold: 300s\n"
                    f"  - Possible cause: Whisper service overloaded or model loading taking too long"
                )
                if attempt < max_retries:
                    logger.info(f"Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"All {max_retries} transcription attempts failed due to timeout")
                    raise
                    
            except requests.exceptions.ConnectionError as e:
                logger.error(
                    f"[Attempt {attempt}/{max_retries}] Connection error to Whisper service: {str(e)}\n"
                    f"  - URL: {url}\n"
                    f"  - Possible causes:\n"
                    f"    * Whisper service is not running\n"
                    f"    * Network connectivity issues\n"
                    f"    * Incorrect WHISPER_SERVICE_URL configuration"
                )
                if attempt < max_retries:
                    logger.info(f"Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"All {max_retries} transcription attempts failed due to connection error")
                    raise
                    
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else "Unknown"
                response_text = e.response.text[:500] if e.response else "No response body"
                
                logger.error(
                    f"[Attempt {attempt}/{max_retries}] HTTP error from Whisper service: {str(e)}\n"
                    f"  - URL: {url}\n"
                    f"  - Status Code: {status_code}\n"
                    f"  - Response: {response_text}\n"
                    f"  - Language requested: {language}\n"
                    f"  - Possible causes:\n"
                    f"    * Model still loading into VRAM (if status 503/504)\n"
                    f"    * Invalid audio format (if status 400)\n"
                    f"    * Service error (if status 500)"
                )
                
                # Retry only for 503/504 (service unavailable/timeout) - model might be loading
                if status_code in [503, 504] and attempt < max_retries:
                    logger.info(f"Service temporarily unavailable (model loading?). Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                elif attempt < max_retries:
                    logger.info(f"Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"All {max_retries} transcription attempts failed with HTTP error {status_code}")
                    raise
                    
            except requests.exceptions.RequestException as e:
                logger.error(
                    f"[Attempt {attempt}/{max_retries}] Unexpected request error during transcription: {str(e)}\n"
                    f"  - URL: {url}\n"
                    f"  - Language: {language}\n"
                    f"  - Error type: {type(e).__name__}"
                )
                if attempt < max_retries:
                    logger.info(f"Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"All {max_retries} transcription attempts failed with unexpected error")
                    raise
                    
            except Exception as e:
                logger.error(
                    f"[Attempt {attempt}/{max_retries}] Unexpected non-request error: {str(e)}\n"
                    f"  - Error type: {type(e).__name__}\n"
                    f"  - This is likely a code bug, not a service issue",
                    exc_info=True
                )
                # Don't retry on unexpected errors
                raise
