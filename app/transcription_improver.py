"""Utility module for improving transcription quality using LangChain."""

import logging
import os
from textwrap import dedent
from typing import Dict, Optional

from iso639 import Language
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

# In-memory cache to avoid rebuilding the LangChain stack repeatedly
_IMPROVER_CACHE: Dict[str, "TranscriptionImprover"] = {}


class TranscriptionImprover:
    """Encapsulates the LangChain pipeline for improving transcription quality."""

    def __init__(self, api_key: str, model_name: str = "gpt-oss:20b") -> None:
        """
        Initialise the LangChain model stack for transcription improvement.
        
        Args:
            api_key: Ollama API key for authentication
            model_name: Model to use for improvement (default: gpt-oss:20b)
        """
        self._api_key = api_key
        self._model_name = model_name
        self._llm = ChatOllama(
            base_url="https://ollama.com",
            model=model_name,
            temperature=0.2,  # Lower temperature for more consistent formatting
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {api_key}"
                }
            }
        )
        self._chain = self._build_chain()
        logger.info(f"TranscriptionImprover initialized with model: {model_name}")

    @property
    def chain(self) -> Runnable[Dict[str, str], str]:
        """Expose the Runnable chain (primarily for testing/inspection)."""
        return self._chain

    def _build_chain(self) -> Runnable[Dict[str, str], str]:
        """Assemble the prompt, model and output parser."""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._system_prompt()),
                (
                    "human",
                    "Original transcription in {language_name}:\n\n{transcription}\n\n"
                    "Improve this transcription following all the specified rules."
                ),
            ]
        )

        return prompt | self._llm | StrOutputParser()

    def _system_prompt(self) -> str:
        """Prompt that defines all formatting and quality improvement rules."""
        return dedent(
            """
            You are an assistant specialized in improving the quality of audio transcriptions.
            Your task is to correct and enhance the transcribed text while maintaining EXACTLY
            the original meaning.

            FUNDAMENTAL RULES:
            1. **PRESERVE CONTENT**: Do not modify, add, or remove information
            2. **LANGUAGE**: The transcription is primarily in {language_name}, but may contain terms, phrases, or quotes in other languages
            3. **MEANING**: The improved text must have the exact same meaning as the original
            4. **MULTILINGUAL AWARENESS**: Do NOT translate or modify words/phrases that are intentionally in another language

            CORRECTIONS TO APPLY:

            PUNCTUATION:
            - Add periods (.) at the end of complete sentences
            - Use commas (,) to separate clauses and improve readability
            - Insert question marks (?) for questions
            - Use exclamation marks (!) where appropriate
            - Add colons (:) and semicolons (;) where necessary

            FORMATTING:
            - Remove excessive line breaks (more than two consecutive)
            - Replace unnecessary line breaks with spaces
            - Maintain logical paragraphs using a blank line (double line break)
            - Use CAPITALS for the beginning of sentences
            - Fix irregular spacing

            COHERENCE:
            - Verify that the text is coherent in the declared language ({language_name})
            - If you find parts in a different language (quotes, technical terms, proper nouns), KEEP THEM AS IS
            - Only modify text that is clearly nonsensical or incorrectly transcribed in {language_name}
            - Correct obvious typos or transcription errors in {language_name} words
            - Normalize numbers and dates to standard format

            MULTILINGUAL HANDLING:
            - The transcription is primarily in {language_name}
            - Some words, phrases, names, or quotes may legitimately be in other languages
            - DO NOT translate these foreign language segments
            - DO NOT modify proper nouns, even if they appear to be in another language
            - ONLY improve punctuation and formatting, not the actual words

            WHAT NOT TO DO:
            - DO NOT translate any text
            - DO NOT summarize or paraphrase
            - DO NOT add information that is not present
            - DO NOT remove repetitions if they are part of the original speech
            - DO NOT modify proper nouns, places, or technical terms
            - DO NOT add titles, headings, or notes
            - DO NOT change words that are intentionally in a different language

            OUTPUT:
            - Return ONLY the improved text
            - No introduction or explanation
            - No comments about the changes made
            - Just the clean, formatted text
            """
        ).strip()

    def improve(self, transcription: str, language: str = "it") -> str:
        """
        Improve the quality of a transcription.
        
        Args:
            transcription: The original transcription text to improve
            language: Language code of the transcription (default: "it")
            
        Returns:
            Improved transcription with better formatting and punctuation
        """
        if not transcription or not transcription.strip():
            logger.warning("Empty transcription provided for improvement")
            return transcription

        # Skip improvement for very short transcriptions (likely already good)
        if len(transcription.strip()) < 50:
            logger.info("Transcription too short, skipping improvement")
            return transcription

        # Convert language code to readable name
        language_name = self._get_language_name(language)

        logger.info(
            f"Improving transcription (length: {len(transcription)} chars, "
            f"language: {language} ({language_name}), model: {self._model_name})"
        )

        payload = {
            "transcription": transcription,
            "language_name": language_name,
        }

        try:
            improved = self._chain.invoke(payload)
            logger.info(
                f"Transcription improved successfully "
                f"(original: {len(transcription)} chars, "
                f"improved: {len(improved)} chars)"
            )
            return improved.strip()
        except Exception as e:
            logger.error(
                f"Failed to improve transcription with model {self._model_name}: {e}",
                exc_info=True
            )
            # Return original transcription if improvement fails
            logger.warning("Returning original transcription due to error")
            return transcription

    def _get_language_name(self, language: str) -> str:
        """
        Convert a language code to a human-readable language name.
        
        Args:
            language: ISO 639-1 language code (e.g., "it", "en", "es")
            
        Returns:
            Human-readable language name (e.g., "Italian", "English", "Spanish")
        """
        if not language:
            return "Italian"
        
        try:
            match = Language.match(language)
            if match and match.name:
                return match.name.capitalize()
        except Exception:
            logger.debug(f"Unable to resolve language name for '{language}'", exc_info=True)
        
        # Fallback to capitalized language code
        return language.capitalize()


def create_improver(api_key: str, model_name: Optional[str] = None) -> TranscriptionImprover:
    """
    Return a cached TranscriptionImprover instance for the provided API key and model.
    
    Args:
        api_key: Ollama API key
        model_name: Model to use (default: reads from TRANSCRIPTION_IMPROVER_MODEL env var
                   or falls back to "gpt-oss:20b")
                   
    Returns:
        Cached or new TranscriptionImprover instance
    """
    # Get model from env var if not provided
    if model_name is None:
        model_name = os.getenv('TRANSCRIPTION_IMPROVER_MODEL', 'gpt-oss:20b')
    
    cache_key = f"{api_key}:{model_name}"
    
    if cache_key not in _IMPROVER_CACHE:
        logger.info(f"Creating new TranscriptionImprover with model: {model_name}")
        _IMPROVER_CACHE[cache_key] = TranscriptionImprover(api_key, model_name)
    
    return _IMPROVER_CACHE[cache_key]
