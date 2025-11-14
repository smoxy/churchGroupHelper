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
from typing import List, Dict, Any, Optional

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser

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
        # Note: get_chat_llm now includes automatic fallback for temperature errors
        self.llm = get_chat_llm(
            provider=self.provider,
            temperature=0.7,  # Creative but not too random
            max_tokens=500  # Reasonable length for birthday messages
        )
        self._gender_detector = None
        self._gender_detector_unavailable = False
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
- Appropriati per l'età e per il genere (maschio/femmina) della persona, adeguando aggettivi e pronomi
- Integrare ogni testo biblico fornito citando riferimento e significato pastorale
- Spiegare con chiarezza le NOTE DEL DATABASE (campo "commento"): indicano chi è presente nel gruppo e chi può essere contattato per far arrivare gli auguri
- Dichiarare esplicitamente chi recapita gli auguri quando la nota lo specifica
- Brevi e concisi (massimo 200 parole)
- In italiano corretto e scorrevole
- Adatti per essere inviati in un gruppo Telegram

IMPORTANTE: Quando ci sono più persone, il messaggio è UNICO ma ogni persona riceve un testo biblico DEDICATO.
Devi integrare tutti i testi biblici nel messaggio in modo armonioso.""")
        
        human_template = """Genera un messaggio di auguri di compleanno per la comunità, usando le informazioni seguenti.

Informazioni sui festeggiati:
{people_info}

Note operative dal database (presenza nel gruppo e contatti: ripeti questi riferimenti nel messaggio):
{comments_info}

Testi biblici da integrare nel messaggio:
{biblical_texts}

Ricorda:
- Se ci sono più persone, crea UN SOLO messaggio che le citi tutte
- Ogni persona deve avere il SUO testo biblico dedicato
- Integra i testi in modo naturale nel messaggio
- Usa un tono appropriato per età e genere
- Se ci sono note/commenti, trasforma chiaramente l'informazione in "Nel gruppo c'è..." o "Per recapitare gli auguri rivolgersi a..."
- Mantieni il messaggio conciso ma significativo

Messaggio:"""

        human_message = HumanMessagePromptTemplate.from_template(human_template)
        return ChatPromptTemplate.from_messages([system_message, human_message])

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape Markdown V2 special characters for safe Telegram output."""
        if not text:
            return ''
        replacements = ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '!']
        for char in replacements:
            text = text.replace(char, f"\\{char}")
        return text

    def _build_contact_block(self, birthdays: List[Dict[str, Any]]) -> str:
        """Return formatted lines explaining who can deliver the wishes."""
        lines = []
        for b in birthdays:
            comment = (b.get('comment') or '').strip()
            if not comment:
                continue
            name = f"{b['first_name']} {b['last_name']}".strip()
            safe_name = self._escape_markdown(name)
            safe_comment = self._escape_markdown(comment)
            lines.append(f"• Per {safe_name} rivolgersi a: {safe_comment}")
        return "\n".join(lines)

    def _attach_contact_info(
        self,
        message: str,
        birthdays: List[Dict[str, Any]]
    ) -> str:
        """Append explicit contact information block when comments are present."""
        contact_block = self._build_contact_block(birthdays)
        if not contact_block:
            return message
        return (
            f"{message}\n\n📞 *Chi recapita gli auguri:*\n{contact_block}"
        )

    def _get_gender_detector(self):
        """Lazily load gender detector if available."""
        if self._gender_detector_unavailable:
            return None
        if self._gender_detector is not None:
            return self._gender_detector
        try:
            import gender_guesser.detector as gender
            self._gender_detector = gender.Detector()
            return self._gender_detector
        except ImportError:
            logger.debug("gender-guesser not installed; skipping automatic gender inference for birthday messages")
            self._gender_detector_unavailable = True
            return None

    def _detect_gender_code(self, birthday: Dict[str, Any]) -> Optional[str]:
        """Return 'M' or 'F' when gender can be inferred for a birthday entry."""
        explicit = birthday.get('gender') or birthday.get('gender_override')
        if isinstance(explicit, str):
            explicit_code = explicit.strip().upper()
            if explicit_code in {'M', 'F'}:
                return explicit_code
        first_name = birthday.get('first_name')
        if not first_name:
            return None
        detector = self._get_gender_detector()
        if not detector:
            return None
        result = detector.get_gender(first_name)
        if result in ['male', 'mostly_male']:
            return 'M'
        if result in ['female', 'mostly_female']:
            return 'F'
        return None

    def _describe_gender_label(self, birthday: Dict[str, Any]) -> Optional[str]:
        """Return Italian label for the detected gender."""
        code = self._detect_gender_code(birthday)
        if code == 'M':
            return 'maschio'
        if code == 'F':
            return 'femmina'
        return None
    
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
        lines = []
        for b in birthdays:
            name = f"{b['first_name']} {b['last_name']}".strip()
            descriptors = []
            if b.get('age'):
                descriptors.append(f"{b.get('age')} anni")
            gender_label = self._describe_gender_label(b)
            if gender_label:
                descriptors.append(f"genere: {gender_label}")
            if descriptors:
                lines.append(f"- {name} ({', '.join(descriptors)})")
            else:
                lines.append(f"- {name}")
        
        return "\n".join(lines)
    
    def _format_comments_info(
        self,
        birthdays: List[Dict[str, Any]]
    ) -> str:
        """
        Format comment information for the prompt.
        
        Args:
            birthdays: List of birthday dictionaries
            
        Returns:
            Formatted string with comments or empty string
        """
        comments = []
        for b in birthdays:
            comment = (b.get('comment') or '').strip()
            if not comment:
                continue
            name = f"{b['first_name']} {b['last_name']}"
            comments.append(
                f"- {name}: {comment}\n  (nel messaggio scrivi chi è nel gruppo o chi può consegnare gli auguri)"
            )
        
        if not comments:
            return "Nessuna nota specifica su presenza o contatti."
        
        return (
            "Elenco delle persone nel gruppo da menzionare come contatto per gli auguri:\n" +
            "\n".join(comments)
        )
    
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
        
        sections = []
        for text, birthday in zip(biblical_texts, birthdays):
            person_name = f"{birthday['first_name']} {birthday['last_name']}"
            version = text.get('version') or 'versione predefinita'

            section_lines = [
                f"Per {person_name}:",
                f"  Versetto {text['reference']} ({version})",
                f"  Testo: \"{text['text']}\"",
            ]

            meta_parts = []
            if text.get('theme'):
                meta_parts.append(f"tema {text['theme']}")
            if text.get('language'):
                meta_parts.append(f"lingua {text['language']}")
            if text.get('age_min') or text.get('age_max'):
                age_min = text.get('age_min')
                age_max = text.get('age_max')
                if age_min and age_max:
                    meta_parts.append(f"fascia {age_min}-{age_max} anni")
                elif age_min:
                    meta_parts.append(f"da {age_min}+ anni")
                else:
                    meta_parts.append(f"fino a {age_max} anni")
            if text.get('gender_preference'):
                pref = str(text['gender_preference'])
                if pref.upper() == 'M':
                    pref_label = 'maschile'
                elif pref.upper() == 'F':
                    pref_label = 'femminile'
                else:
                    pref_label = pref
                meta_parts.append(f"orientato a pubblico {pref_label}")
            if meta_parts:
                section_lines.append(f"  Metadati: {', '.join(meta_parts)}")

            sections.append("\n".join(section_lines))

        return "\n\n".join(sections)
    
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
        
        ai_candidate = None

        if use_ai:
            try:
                prompt = self._create_prompt_template()
                people_info = self._format_people_info(birthdays)
                comments_info = self._format_comments_info(birthdays)
                biblical_texts_info = self._format_biblical_texts(biblical_texts, birthdays)

                parser = StrOutputParser()
                chain = prompt | self.llm | parser
                ai_candidate = chain.invoke({
                    "people_info": people_info,
                    "comments_info": comments_info,
                    "biblical_texts": biblical_texts_info
                })
                if ai_candidate:
                    ai_candidate = ai_candidate.strip()
                    logger.info("AI candidate generated (%d chars)", len(ai_candidate))
            except Exception as exc:
                logger.error("Error generating AI message: %s", exc)

        used_static_template = False
        message_body = ai_candidate if ai_candidate else None

        if not message_body:
            message_body = self._generate_static_template(birthdays, biblical_texts)
            used_static_template = True

        if not message_body:
            return None

        final_message = self._attach_contact_info(message_body, birthdays)

        if not self._validate_message(final_message):
            if not used_static_template:
                logger.warning("AI message failed final validation; retrying with static template")
                fallback = self._generate_static_template(birthdays, biblical_texts)
                used_static_template = True
                if fallback:
                    final_message = self._attach_contact_info(fallback, birthdays)
            if not self._validate_message(final_message):
                logger.warning(
                    "Generated message still fails validation (%d chars); sending as-is",
                    len(final_message) if final_message else 0
                )

        return final_message
    
    def _validate_message(self, message: Optional[str]) -> bool:
        """
        Validate generated message for length and basic content.
        
        Args:
            message: Generated message string
            
        Returns:
            True if valid, False otherwise
        """
        if not message:
            logger.warning("Message empty or None")
            return False

        if len(message) < 40:
            logger.warning("Message too short (%d chars)", len(message))
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
