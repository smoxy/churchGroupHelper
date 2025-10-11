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
        
        # Initialize transcription improver if API key is available
        self.improver = None
        if OLLAMA_API_KEY:
            try:
                self.improver = create_improver(OLLAMA_API_KEY, TRANSCRIPTION_IMPROVER_MODEL)
                logger.info(f"Transcription improver initialized with model: {TRANSCRIPTION_IMPROVER_MODEL}")
            except Exception as e:
                logger.warning(f"Failed to initialize transcription improver: {e}")
        else:
            logger.info("OLLAMA_API_KEY not set, transcription improvement disabled")

    async def _improve_with_streaming(self, transcription: str, language: str, telegram_context) -> str:
        """
        Improve transcription with streaming updates to Telegram message.
        
        Args:
            transcription: Original transcription text
            language: Language code
            telegram_context: Telegram context with update and message objects
            
        Returns:
            Complete improved transcription
        """
        from utils import TELEGRAM_MAX_MESSAGE_LENGTH
        import asyncio
        
        # Send initial "processing" message
        chat_id = telegram_context['update'].effective_chat.id
        processing_msg = await telegram_context['context'].bot.send_message(
            chat_id=chat_id,
            text="🔄 Miglioramento trascrizione in corso..."
        )
        
        accumulated_text = ""
        last_update_time = asyncio.get_event_loop().time()
        last_update_length = 0
        UPDATE_INTERVAL = 1.0  # Update every 1 second
        MIN_CHARS_FOR_UPDATE = 50  # Or when we have at least 50 new chars
        
        try:
            # Stream the improved transcription
            for chunk in self.improver.improve_stream(transcription, language):
                accumulated_text += chunk
                current_time = asyncio.get_event_loop().time()
                chars_since_update = len(accumulated_text) - last_update_length
                
                # Update message if enough time passed or enough new chars
                should_update = (
                    (current_time - last_update_time >= UPDATE_INTERVAL) or
                    (chars_since_update >= MIN_CHARS_FOR_UPDATE)
                )
                
                if should_update and accumulated_text.strip():
                    # Truncate if too long for single message
                    display_text = accumulated_text
                    if len(display_text) > TELEGRAM_MAX_MESSAGE_LENGTH - 100:
                        display_text = display_text[:TELEGRAM_MAX_MESSAGE_LENGTH - 100] + "..."
                    
                    try:
                        await telegram_context['context'].bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=processing_msg.message_id,
                            text=display_text
                        )
                        last_update_time = current_time
                        last_update_length = len(accumulated_text)
                    except Exception as e:
                        # Ignore edit errors (message not changed, etc.)
                        logger.debug(f"Could not edit message: {e}")
            
            # Final update with complete text
            if accumulated_text.strip():
                final_text = accumulated_text.strip()
                
                # If text is too long, send in multiple messages and delete the processing one
                if len(final_text) > TELEGRAM_MAX_MESSAGE_LENGTH:
                    from utils import split_message
                    chunks = split_message(final_text)
                    
                    # Delete processing message
                    try:
                        await telegram_context['context'].bot.delete_message(
                            chat_id=chat_id,
                            message_id=processing_msg.message_id
                        )
                    except:
                        pass
                    
                    # Send chunks
                    for chunk in chunks:
                        await telegram_context['context'].bot.send_message(
                            chat_id=chat_id,
                            text=chunk
                        )
                else:
                    # Update with final text
                    try:
                        await telegram_context['context'].bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=processing_msg.message_id,
                            text=final_text
                        )
                    except Exception as e:
                        logger.warning(f"Could not edit final message: {e}")
                
                return final_text
            else:
                # Empty result, delete processing message and return original
                try:
                    await telegram_context['context'].bot.delete_message(
                        chat_id=chat_id,
                        message_id=processing_msg.message_id
                    )
                except:
                    pass
                return transcription
                
        except Exception as e:
            logger.error(f"Error during streaming improvement: {e}", exc_info=True)
            # Delete processing message
            try:
                await telegram_context['context'].bot.delete_message(
                    chat_id=chat_id,
                    message_id=processing_msg.message_id
                )
            except:
                pass
            return transcription

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

    async def transcribe_audio(self, file_path, language: str, group_id: int, user_id: int, author_name: str, timestamp, telegram_message_id: int = None, is_allowed: bool=False, telegram_context=None) -> tuple:
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

        # Transcribe audio using external service with retry logic
        # The Whisper container unloads the model from VRAM after 2 minutes of inactivity
        # It needs time to reload the model when a new request arrives
        max_retries = 7
        retry_delay = 5  # seconds between retries
        url = f"{self.service_url}/asr"
        
        for attempt in range(1, max_retries + 1):
            try:
                
                logger.info(f"[Attempt {attempt}/{max_retries}] Sending transcription request to {url} for language '{language}'")
                
                with open(file_path, 'rb') as audio_file:
                    files = {'audio_file': audio_file}
                    params = {
                        'encode': 'true',
                        'task': 'transcribe',
                        'language': language,
                        'output': 'txt'
                    }
                    
                    start_time = time.time()
                    response = requests.post(url, files=files, params=params, timeout=300)
                    elapsed_time = time.time() - start_time
                    
                    logger.info(f"[Attempt {attempt}/{max_retries}] Response received in {elapsed_time:.2f}s - Status code: {response.status_code}")
                    
                    response.raise_for_status()
                    
                    # Il servizio restituisce il testo direttamente quando output=txt
                    transcription = response.text.strip()
                    
                    logger.info(f"[Attempt {attempt}/{max_retries}] Transcription successful - Length: {len(transcription)} characters")
                    
                    # Improve transcription quality if improver is available
                    if self.improver and transcription:
                        try:
                            # If telegram context is provided, use streaming to update message in real-time
                            if telegram_context:
                                logger.info("Improving transcription quality with streaming LangChain pipeline...")
                                logger.debug(f"Original transcription preview (first 200 chars): {transcription[:200]}")
                                
                                improved_transcription = await self._improve_with_streaming(
                                    transcription, language, telegram_context
                                )
                                
                                if improved_transcription and improved_transcription.strip():
                                    logger.info(
                                        f"Transcription improved with streaming: "
                                        f"Original length: {len(transcription)} chars, "
                                        f"Improved length: {len(improved_transcription)} chars"
                                    )
                                    transcription = improved_transcription
                                else:
                                    logger.warning("Streaming improvement returned empty result, keeping original")
                            else:
                                # Fallback to non-streaming if no telegram context
                                logger.info("Improving transcription quality with LangChain pipeline (no streaming)...")
                                logger.debug(f"Original transcription preview (first 200 chars): {transcription[:200]}")
                                
                                improved_transcription = self.improver.improve(transcription, language)
                                
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
