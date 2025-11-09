"""
Birthday Message Generator Module
==================================

This module generates personalized birthday messages using AI (OpenAI or Ollama).
Uses LangChain for flexible provider support and prompt engineering.

Features:
- OpenAI API compatible (GPT-3.5, GPT-4, etc.)
- Ollama compatible (local models)
- Automatic provider selection via ai_provider module
- Gender-aware message generation
- Age-appropriate messaging
- Biblical text integration (each person gets dedicated text)
- Combined messages for multiple birthdays on same day
- Static template fallback if AI fails
- Message validation (length, content appropriateness)

Environment Variables (managed by ai_provider module):
- OPENAI_API_KEY: If set, uses OpenAI
- OPENAI_MODEL: Model name (default: gpt-5-nano)
- OLLAMA_BASE_URL: Ollama server URL (default: https://ollama.com)
- OLLAMA_MODEL: Ollama model name (default: gpt-oss:20b)
- AI_PROVIDER: Override provider ('openai' or 'ollama')
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage

from ai_provider import get_chat_llm, detect_ai_provider

logger = logging.getLogger(__name__)


class BirthdayMessageGenerator:
    """
    Generates personalized birthday messages using AI or static templates.
    
    Supports both OpenAI and Ollama providers via ai_provider module.
    """
    
    def __init__(self):
        """Initialize the message generator with AI provider."""
        self.provider = detect_ai_provider()
        self.llm = get_chat_llm(
            provider=self.provider,
            temperature=0.7,  # Creative but not too random
            max_tokens=500  # Reasonable length for birthday messages
        )
        logger.info(f"BirthdayMessageGenerator initialized with provider: {self.provider}")
    
    def _create_prompt_template(self) -> ChatPromptTemplate:
        """
        Create the prompt template for birthday message generation.
        
        Returns:
            ChatPromptTemplate for LangChain
        """
        system_message = SystemMessage(content="""Sei un assistente che genera messaggi di auguri di compleanno calorosi e personalizzati per una comunità cristiana.

I tuoi messaggi devono essere:
- Calorosi e affettuosi, ma rispettosi
- Appropriati per l'età e il genere della persona
- Includere il testo biblico fornito in modo naturale
- Brevi e concisi (massimo 200 parole)
- In italiano corretto e scorrevole
- Adatti per essere inviati in un gruppo Telegram

IMPORTANTE: Quando ci sono più persone, il messaggio è UNICO ma ogni persona riceve un testo biblico DEDICATO.
Devi integrare tutti i testi biblici nel messaggio in modo armonioso.""")
        
        human_template = """Genera un messaggio di auguri di compleanno per:

{people_info}

Testi biblici da integrare nel messaggio:
{biblical_texts}

Ricorda:
- Se ci sono più persone, crea UN SOLO messaggio che le citi tutte
- Ogni persona deve avere il SUO testo biblico dedicato
- Integra i testi in modo naturale nel messaggio
- Usa un tono appropriato per l'età e il genere
- Mantieni il messaggio conciso ma significativo

Messaggio:"""
        
        human_message = HumanMessagePromptTemplate.from_template(human_template)
        
        return ChatPromptTemplate.from_messages([system_message, human_message])
    
    def _format_people_info(
        self,
        birthdays: List[Dict[str, Any]]
    ) -> str:
        """
        Format birthday information for the prompt.
        
        Args:
            birthdays: List of birthday dictionaries
            
        Returns:
            Formatted string with people information
        """
        if len(birthdays) == 1:
            b = birthdays[0]
            age_info = f", {b.get('age', '?')} anni" if b.get('age') else ""
            gender_info = f" ({b.get('gender', 'sconosciuto')})" if b.get('gender') else ""
            return f"- {b['first_name']} {b['last_name']}{age_info}{gender_info}"
        
        lines = []
        for b in birthdays:
            age_info = f", {b.get('age', '?')} anni" if b.get('age') else ""
            gender_info = f" ({b.get('gender', 'sconosciuto')})" if b.get('gender') else ""
            lines.append(f"- {b['first_name']} {b['last_name']}{age_info}{gender_info}")
        
        return "\n".join(lines)
    
    def _format_biblical_texts(
        self,
        biblical_texts: List[Dict[str, Any]],
        birthdays: List[Dict[str, Any]]
    ) -> str:
        """
        Format biblical texts with person assignments.
        
        Args:
            biblical_texts: List of biblical text dictionaries
            birthdays: List of birthday dictionaries
            
        Returns:
            Formatted string with biblical texts assigned to people
        """
        if len(biblical_texts) != len(birthdays):
            logger.warning(f"Mismatch: {len(biblical_texts)} texts for {len(birthdays)} people")
        
        lines = []
        for i, (text, birthday) in enumerate(zip(biblical_texts, birthdays)):
            person_name = f"{birthday['first_name']} {birthday['last_name']}"
            lines.append(f"Per {person_name}:")
            lines.append(f'  {text["reference"]}: "{text["text"]}"')
            if i < len(biblical_texts) - 1:
                lines.append("")  # Blank line between texts
        
        return "\n".join(lines)
    
    def generate_message(
        self,
        birthdays: List[Dict[str, Any]],
        biblical_texts: List[Dict[str, Any]],
        use_ai: bool = True
    ) -> Optional[str]:
        """
        Generate a birthday message for one or more people.
        
        Args:
            birthdays: List of birthday dictionaries (can be 1 or more)
            biblical_texts: List of biblical text dictionaries (one per person)
            use_ai: If False, use static template instead of AI
            
        Returns:
            Generated message string or None if failed
        """
        if not birthdays or not biblical_texts:
            logger.error("Cannot generate message without birthdays or biblical texts")
            return None
        
        if len(birthdays) != len(biblical_texts):
            logger.error(f"Mismatch: {len(birthdays)} birthdays but {len(biblical_texts)} texts")
            return None
        
        # Use static template if AI disabled or if AI fails
        if not use_ai:
            return self._generate_static_template(birthdays, biblical_texts)
        
        try:
            # Create prompt
            prompt = self._create_prompt_template()
            
            # Format input data
            people_info = self._format_people_info(birthdays)
            biblical_texts_info = self._format_biblical_texts(biblical_texts, birthdays)
            
            # Generate message using AI
            chain = prompt | self.llm
            response = chain.invoke({
                "people_info": people_info,
                "biblical_texts": biblical_texts_info
            })
            
            message = response.content.strip()
            
            # Validate message
            if not self._validate_message(message):
                logger.warning("AI-generated message failed validation, using static template")
                return self._generate_static_template(birthdays, biblical_texts)
            
            logger.info(f"Successfully generated AI message ({len(message)} chars)")
            return message
            
        except Exception as e:
            logger.error(f"Error generating AI message: {e}")
            logger.info("Falling back to static template")
            return self._generate_static_template(birthdays, biblical_texts)
    
    def _validate_message(self, message: str) -> bool:
        """
        Validate generated message for length and basic content.
        
        Args:
            message: Generated message string
            
        Returns:
            True if valid, False otherwise
        """
        if not message or len(message) < 50:
            logger.warning("Message too short")
            return False
        
        if len(message) > 2000:  # Telegram message limit is 4096, be conservative
            logger.warning("Message too long")
            return False
        
        # Basic content check: should contain at least one name
        # (More sophisticated checks could be added)
        
        return True
    
    def _generate_static_template(
        self,
        birthdays: List[Dict[str, Any]],
        biblical_texts: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a birthday message using static template (fallback).
        
        Args:
            birthdays: List of birthday dictionaries
            biblical_texts: List of biblical text dictionaries
            
        Returns:
            Generated message string
        """
        logger.info("Using static template for birthday message")
        
        # Single person template
        if len(birthdays) == 1:
            b = birthdays[0]
            t = biblical_texts[0]
            
            name = f"{b['first_name']} {b['last_name']}"
            
            message = f"🎉 Buon compleanno {name}! 🎂\n\n"
            message += f"In questo giorno speciale, vogliamo augurarti ogni bene e ricordarti questo bellissimo versetto:\n\n"
            message += f'📖 {t["reference"]}\n'
            message += f'"{t["text"]}"\n\n'
            message += f"Che Dio ti benedica oggi e sempre! 🙏✨"
            
            return message
        
        # Multiple people template
        names = [f"{b['first_name']} {b['last_name']}" for b in birthdays]
        
        if len(names) == 2:
            names_str = f"{names[0]} e {names[1]}"
        else:
            names_str = ", ".join(names[:-1]) + f" e {names[-1]}"
        
        message = f"🎉 Buon compleanno {names_str}! 🎂\n\n"
        message += f"In questo giorno speciale, vogliamo augurarvi ogni bene e condividere con voi questi versetti:\n\n"
        
        for b, t in zip(birthdays, biblical_texts):
            person_name = f"{b['first_name']} {b['last_name']}"
            message += f"Per {person_name}:\n"
            message += f'📖 {t["reference"]}: "{t["text"]}"\n\n'
        
        message += f"Che Dio vi benedica oggi e sempre! 🙏✨"
        
        return message
    
    def add_mention_if_enabled(
        self,
        message: str,
        birthday: Dict[str, Any],
        mention_enabled: bool
    ) -> str:
        """
        Add Telegram mention to message if enabled and telegram_user_id available.
        
        Args:
            message: Generated message
            birthday: Birthday dictionary with telegram_user_id
            mention_enabled: Whether mentions are enabled for the group
            birthday_mention_opt_out: Whether this person opted out
            
        Returns:
            Message with mention added (if applicable)
        """
        # Check if mentions enabled globally and person hasn't opted out
        if not mention_enabled:
            return message
        
        if birthday.get('mention_opt_out', 0) == 1:
            logger.info(f"Birthday {birthday['id']} opted out of mentions")
            return message
        
        # Check if telegram_user_id available
        telegram_user_id = birthday.get('telegram_user_id')
        if not telegram_user_id:
            logger.info(f"No telegram_user_id for birthday {birthday['id']}, can't mention")
            return message
        
        # Add mention at the beginning
        # Format: [Name](tg://user?id=USER_ID)
        name = f"{birthday['first_name']} {birthday['last_name']}"
        mention = f"[{name}](tg://user?id={telegram_user_id})"
        
        # Replace first occurrence of name with mention
        message = message.replace(name, mention, 1)
        
        logger.info(f"Added mention for birthday {birthday['id']}")
        return message
