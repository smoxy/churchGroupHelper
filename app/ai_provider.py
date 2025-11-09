"""
AI Provider Manager Module
===========================

Centralized AI provider management for OpenAI and Ollama.
Provides automatic detection and initialization of the appropriate provider.

This module is used by:
- summarizer.py (conversation summaries)
- transcription_improver.py (transcription formatting)
- birthday_message_generator.py (birthday messages)

Environment Variables:
- OPENAI_API_KEY: If set, uses OpenAI
- OPENAI_MODEL: OpenAI model name (default: gpt-5-nano)
- OLLAMA_API_KEY: Ollama API key (for hosted service)
- OLLAMA_BASE_URL: Ollama server URL (default: https://ollama.com)
- OLLAMA_MODEL: Ollama model name (default: gpt-oss:20b)
- AI_PROVIDER: Override provider ('openai' or 'ollama')
- USE_DEFAULT_TEMPERATURE: If 'true', don't set custom temperature (use model default)

Auto-detection logic:
1. If AI_PROVIDER is set explicitly, use it
2. If OPENAI_API_KEY is set, use OpenAI
3. Otherwise, use Ollama (default)

Temperature handling:
- Some models (especially fine-tuned or specialized ones) only support default temperature
- Set USE_DEFAULT_TEMPERATURE=true to disable custom temperature values
- If a temperature error is detected at runtime, automatically retries without temperature
"""

import logging
import os
from typing import Literal, Optional
from functools import wraps

logger = logging.getLogger(__name__)

ProviderType = Literal['openai', 'ollama']

# Cache for models that don't support custom temperature
_MODELS_NO_CUSTOM_TEMP = set()


class LLMWithFallback:
    """
    Wrapper for LangChain LLM that handles temperature-related errors with fallback.
    
    Some models (like gpt-5-mini, gpt-5-nano) don't support custom temperature values.
    This wrapper detects such errors and automatically retries without temperature.
    """
    
    def __init__(self, llm, model_name: str):
        """
        Args:
            llm: The wrapped LangChain LLM instance
            model_name: Name of the model (for logging and caching)
        """
        self._llm = llm
        self._model_name = model_name
    
    def invoke(self, input, config=None):
        """Invoke with fallback for temperature errors."""
        try:
            return self._llm.invoke(input, config)
        except Exception as e:
            error_msg = str(e)
            # Check if it's a temperature-related error
            if 'temperature' in error_msg.lower() and 'does not support' in error_msg.lower():
                logger.warning(
                    f"Model {self._model_name} doesn't support custom temperature. "
                    f"Retrying with default temperature. Error: {error_msg}"
                )
                _MODELS_NO_CUSTOM_TEMP.add(self._model_name)
                
                # Recreate LLM without temperature
                provider = detect_ai_provider()
                new_llm = get_chat_llm(
                    provider=provider,
                    model_override=self._model_name,
                    use_default_temperature=True
                )
                # Unwrap if it's also a LLMWithFallback
                if isinstance(new_llm, LLMWithFallback):
                    return new_llm._llm.invoke(input, config)
                return new_llm.invoke(input, config)
            else:
                raise
    
    def batch(self, inputs, config=None, **kwargs):
        """Batch invoke with fallback for temperature errors."""
        try:
            return self._llm.batch(inputs, config, **kwargs)
        except Exception as e:
            error_msg = str(e)
            if 'temperature' in error_msg.lower() and 'does not support' in error_msg.lower():
                logger.warning(
                    f"Model {self._model_name} doesn't support custom temperature. "
                    f"Retrying batch with default temperature."
                )
                _MODELS_NO_CUSTOM_TEMP.add(self._model_name)
                
                provider = detect_ai_provider()
                new_llm = get_chat_llm(
                    provider=provider,
                    model_override=self._model_name,
                    use_default_temperature=True
                )
                # Unwrap if it's also a LLMWithFallback
                if isinstance(new_llm, LLMWithFallback):
                    return new_llm._llm.batch(inputs, config, **kwargs)
                return new_llm.batch(inputs, config, **kwargs)
            else:
                raise
    
    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped LLM."""
        return getattr(self._llm, name)


def detect_ai_provider() -> ProviderType:
    """
    Detect which AI provider to use based on environment variables.
    
    Returns:
        'openai' or 'ollama'
    """
    # Explicit override
    provider = os.getenv('AI_PROVIDER', '').lower()
    if provider in ['openai', 'ollama']:
        logger.info(f"Using explicit AI provider from AI_PROVIDER: {provider}")
        return provider
    
    # Auto-detect based on API key presence
    if os.getenv('OPENAI_API_KEY'):
        logger.info("Detected OPENAI_API_KEY, using OpenAI provider")
        return 'openai'
    
    # Default to Ollama
    logger.info("No OPENAI_API_KEY found, using Ollama provider (default)")
    return 'ollama'


def get_chat_llm(
    provider: ProviderType = None,
    temperature: float = 0.7,
    max_tokens: int = None,
    model_override: str = None,
    use_default_temperature: bool = False
):
    """
    Get a LangChain Chat LLM instance for the specified or detected provider.
    
    Args:
        provider: 'openai' or 'ollama' (auto-detect if None)
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Maximum tokens in response (None = use provider default)
        model_override: Override model name (None = use env var or default)
        use_default_temperature: If True, don't set temperature parameter (use model's default)
        
    Returns:
        LangChain ChatLLM instance (ChatOpenAI or ChatOllama) with automatic fallback handling
    """
    if provider is None:
        provider = detect_ai_provider()
    
    # Check if we should use default temperature from environment variable
    if os.getenv('USE_DEFAULT_TEMPERATURE', '').lower() == 'true':
        use_default_temperature = True
        logger.info("USE_DEFAULT_TEMPERATURE is set, will use model's default temperature")
    
    if provider == 'openai':
        from langchain_openai import ChatOpenAI
        
        model = model_override or os.getenv('OPENAI_MODEL', 'gpt-5-nano')
        
        # Check if this model is known to not support custom temperature
        if model in _MODELS_NO_CUSTOM_TEMP:
            logger.info(f"Model {model} previously detected as not supporting custom temperature, using default")
            use_default_temperature = True
        
        kwargs = {
            'model': model
        }
        
        # Only add temperature if not using default
        if not use_default_temperature:
            kwargs['temperature'] = temperature
        
        if max_tokens:
            kwargs['max_tokens'] = max_tokens
        
        temp_info = "default" if use_default_temperature else str(temperature)
        logger.info(f"Initializing ChatOpenAI with model: {model}, temperature: {temp_info}")
        llm = ChatOpenAI(**kwargs)
        
        # Wrap with fallback handler
        return LLMWithFallback(llm, model)
    
    else:  # ollama
        from langchain_ollama import ChatOllama
        
        base_url = os.getenv('OLLAMA_BASE_URL', 'https://ollama.com')
        model = model_override or os.getenv('OLLAMA_MODEL', 'gpt-oss:20b')
        api_key = os.getenv('OLLAMA_API_KEY')
        
        kwargs = {
            'model': model,
            'base_url': base_url,
            'temperature': temperature
        }
        
        # Add API key if available (for hosted Ollama service)
        if api_key:
            kwargs['client_kwargs'] = {
                'headers': {
                    'Authorization': f'Bearer {api_key}'
                }
            }
            logger.info(f"Initializing ChatOllama with model: {model} at {base_url} (authenticated)")
        else:
            logger.info(f"Initializing ChatOllama with model: {model} at {base_url} (no auth)")
        
        llm = ChatOllama(**kwargs)
        
        # Wrap with fallback handler
        return LLMWithFallback(llm, model)


def get_provider_info() -> dict:
    """
    Get information about the current AI provider configuration.
    
    Returns:
        Dictionary with provider details
    """
    provider = detect_ai_provider()
    
    if provider == 'openai':
        model = os.getenv('OPENAI_MODEL', 'gpt-5-nano')
        api_key_set = bool(os.getenv('OPENAI_API_KEY'))
        
        return {
            'provider': 'openai',
            'model': model,
            'authenticated': api_key_set,
            'base_url': 'https://api.openai.com/v1'
        }
    else:
        base_url = os.getenv('OLLAMA_BASE_URL', 'https://ollama.com')
        model = os.getenv('OLLAMA_MODEL', 'gpt-oss:20b')
        api_key_set = bool(os.getenv('OLLAMA_API_KEY'))
        
        return {
            'provider': 'ollama',
            'model': model,
            'authenticated': api_key_set,
            'base_url': base_url
        }
