"""Utility module for improving transcription quality using LangChain."""

import logging
import os
from datetime import datetime
from textwrap import dedent
from typing import Dict, Optional

from iso639 import Language
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate
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
        system_prompt = self._system_prompt()
        developer_prompt = self._developer_prompt()

        logger.debug(f"System prompt length: {len(system_prompt)} chars")
        logger.debug(f"System prompt preview (first 300 chars): {system_prompt[:300]}")

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(system_prompt),
                SystemMessagePromptTemplate.from_template(developer_prompt),
                (
                    "human",
                    "Original transcription in {language_name}:\n\n{transcription}\n\n"
                    "Improve this transcription following all the specified rules."
                ),
            ]
        )

        return prompt | self._llm | StrOutputParser()

    def _system_prompt(self) -> str:
        """Baseline Harmony system message with model metadata."""
        current_date = datetime.utcnow().date().isoformat()
        return dedent(
            f"""
            You are ChatGPT, a large language model trained by OpenAI.
            Knowledge cutoff: 2024-06
            Current date: {current_date}
            Reasoning: medium
            # Valid channels: analysis, commentary, final. Channel must be included for every message.
            """
        ).strip()

    def _developer_prompt(self) -> str:
        """Detailed instructions for the transcription improver."""
        return dedent(
            """
            # Instructions
            You improve audio transcriptions while preserving every piece of information from the source text.

            ## Preservation Rules
            - Maintain the original meaning exactly; never add, delete, or reinterpret facts.
            - Respect multilingual content: keep foreign words, quotes, and proper nouns unchanged.
            - Do not translate content from or into {language_name}.

            ## Corrections To Apply
            - Fix punctuation: sentence endings, commas, question marks, exclamations, colons, and semicolons.
            - Normalize spacing and eliminate excessive line breaks (more than two in a row).
            - Start sentences with capital letters and ensure consistent casing.
            - Organize paragraphs using a single blank line between logical sections only when needed.
            - Correct obvious typos in {language_name}, including numbers and dates, without altering intent.

            ## Format Requirements
            - Output plain text only; no commentary, metadata, or explanations.
            - Return the improved transcription exactly, with no leading or trailing whitespace beyond a single newline if appropriate.

            ## Harmony Compliance
            - Use the analysis channel solely for reasoning steps when necessary, and deliver the polished transcription on the final channel.
            - Decline to comply if the task violates these rules.
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
            logger.debug(f"Invoking LangChain with payload: language_name={language_name}, text_length={len(transcription)}")
            improved = self._chain.invoke(payload)
            
            # Log raw response for debugging
            logger.debug(f"Raw improved response type: {type(improved)}")
            logger.debug(f"Raw improved response length: {len(improved) if improved else 0}")
            if improved:
                logger.debug(f"First 200 chars of improved: {improved[:200]}")
            else:
                logger.warning("Model returned empty or None response!")
            
            # Check if improvement is valid
            if not improved or not improved.strip():
                logger.error(
                    f"Model {self._model_name} returned empty response. "
                    f"This might indicate a prompt issue or model failure. "
                    f"Keeping original transcription."
                )
                return transcription
            
            improved_stripped = improved.strip()
            logger.info(
                f"Transcription improved successfully "
                f"(original: {len(transcription)} chars, "
                f"improved: {len(improved_stripped)} chars)"
            )
            return improved_stripped
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
