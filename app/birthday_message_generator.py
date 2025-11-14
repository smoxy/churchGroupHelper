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
- Brevi e concisi (massimo 200 parole)
- In italiano corretto e scorrevole
- Adatti per essere inviati in un gruppo Telegram

IMPORTANTE: Quando ci sono più persone, il messaggio è UNICO ma ogni persona riceve un testo biblico DEDICATO.
Devi integrare tutti i testi biblici nel messaggio in modo armonioso.""")
        
        human_template = """Genera un messaggio di auguri di compleanno per la comunità, usando le informazioni seguenti.

Informazioni sui festeggiati:
{people_info}

Testi biblici da integrare nel messaggio:
{biblical_texts}

Ricorda:
- Se ci sono più persone, crea UN SOLO messaggio che le citi tutte
- Ogni persona deve avere il SUO testo biblico dedicato
- Integra i testi in modo naturale nel messaggio
- Usa un tono appropriato per età e genere
- Mantieni il messaggio conciso ma significativo
- Usa HTML per la formattazione: <b>bold</b>, <i>italic</i>, <u>underline</u>
- Per le interruzioni di riga usa SOLO newline normali (\\n), MAI <br/> o altri tag HTML per line break

Messaggio:"""

        human_message = HumanMessagePromptTemplate.from_template(human_template)
        return ChatPromptTemplate.from_messages([system_message, human_message])
    
    def _create_contact_enrichment_template(self) -> ChatPromptTemplate:
        """
        Create prompt template for adding contact delivery information.
        
        Returns:
            ChatPromptTemplate for contact info enrichment
        """
        system_message = SystemMessage(content="""Sei un assistente che arricchisce messaggi di auguri con informazioni su chi può recapitare gli auguri.

Il tuo compito è:
- Leggere il messaggio di auguri già generato
- Analizzare le note dal database sui contatti
- Aggiungere UN PARAGRAFO FINALE che spiega in modo narrativo e naturale chi potrà far arrivare gli auguri
- TRASFORMARE le note tecniche in frasi fluide e calde

IMPORTANTE:
- "SI" = la persona È presente nel gruppo Telegram, quindi leggerà direttamente gli auguri
- "NO - [chi c'è]" = la persona NON è nel gruppo, ma c'è qualcuno che farà arrivare gli auguri
- MAI copiare letteralmente il contenuto delle note
- Il paragrafo deve essere breve (1-2 frasi) e naturale
- Usa tono affettuoso e caloroso""")
        
        human_template = """Messaggio di auguri già generato:
{original_message}

Note sui contatti dal database:
{contacts_info}

Aggiungi un paragrafo finale (separato da riga vuota) che spieghi chi potrà recapitare gli auguri. 
Analizza la nota e trasformala in una frase narrativa naturale.

ESEMPI DI TRASFORMAZIONE:

1. Nota: "NO - c'è nonna Maria e fratello Luca"
   → "<i>[Nome] non è presente nel gruppo, ma la nonna Maria e suo fratello Luca potranno far arrivare tutto il nostro affetto! 💝</i>"

2. Nota: "NO- la mamma si"
   → "<i>[Nome] non è nel gruppo, ma la sua mamma riceverà i nostri auguri e glieli farà avere con tanto amore! 💝</i>"

3. Nota: "NO- c'è il padre" o "NO- c'è la moglie"
   → "<i>[Nome] non è presente nel gruppo, ma il padre/la moglie farà in modo che riceva tutti i nostri auguri! 💝</i>"

4. Nota: "NO- c'è tutta la famiglia"
   → "<i>[Nome] non è nel gruppo, ma la sua famiglia riceverà i nostri auguri e glieli farà avere! 💝</i>"

5. Nota: "SI" o "SI con la moglie"
   → "<i>Ci auguriamo che [Nome] possa leggere i nostri auguri direttamente qui nel gruppo! 🎉</i>"

6. Nota: "NO- il nonno Giovanni" (quando si usa il nome)
   → "<i>[Nome] non è presente nel gruppo, ma il nonno riceverà i nostri auguri e glieli farà avere con affetto! 💝</i>"

7. Nota: "NO- la zia Gabriella"
   → "<i>[Nome] non è nel gruppo, ma la zia riceverà i nostri auguri e glieli farà avere! 💝</i>"

REGOLE:
- Sostituisci sempre [Nome] con il nome vero della persona
- Se la nota menziona nomi specifici (es. "nonno Giovanni"), usa solo il ruolo generico ("il nonno") nella frase finale
- Mantieni il tono caloroso e affettuoso
- Una sola frase in corsivo con emoji finale
- Se ci sono più persone con note diverse, crea una frase per ognuna

Messaggio completo con paragrafo contatti:"""

        human_message = HumanMessagePromptTemplate.from_template(human_template)
        return ChatPromptTemplate.from_messages([system_message, human_message])

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters for safe Telegram HTML output."""
        if not text:
            return ''
        replacements = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }
        for char, escaped in replacements.items():
            text = text.replace(char, escaped)
        return text

    def _has_comments(self, birthdays: List[Dict[str, Any]]) -> bool:
        """Check if any birthday has a comment."""
        return any((b.get('comment') or '').strip() for b in birthdays)

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
        Format comment information for contact enrichment step.
        
        Args:
            birthdays: List of birthday dictionaries
            
        Returns:
            Formatted string with contact delivery notes
        """
        comments = []
        for b in birthdays:
            comment = (b.get('comment') or '').strip()
            if not comment:
                continue
            name = f"{b['first_name']} {b['last_name']}"
            comments.append(f"- {name}: {comment}")
        
        if not comments:
            return "Nessuna nota sui contatti."
        
        return "\n".join(comments)
    
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
                # Step 1: Generate main birthday message with biblical texts
                prompt = self._create_prompt_template()
                people_info = self._format_people_info(birthdays)
                biblical_texts_info = self._format_biblical_texts(biblical_texts, birthdays)

                parser = StrOutputParser()
                chain = prompt | self.llm | parser
                ai_candidate = chain.invoke({
                    "people_info": people_info,
                    "biblical_texts": biblical_texts_info
                })
                
                if ai_candidate:
                    ai_candidate = ai_candidate.strip()
                    logger.info("AI message generated (%d chars)", len(ai_candidate))
                    
                    # Step 2: Enrich with contact delivery information if comments exist
                    if self._has_comments(birthdays):
                        contacts_info = self._format_comments_info(birthdays)
                        contact_prompt = self._create_contact_enrichment_template()
                        contact_chain = contact_prompt | self.llm | parser
                        
                        enriched_message = contact_chain.invoke({
                            "original_message": ai_candidate,
                            "contacts_info": contacts_info
                        })
                        
                        if enriched_message:
                            ai_candidate = enriched_message.strip()
                            logger.info("AI message enriched with contact info (%d chars)", len(ai_candidate))
                        
            except Exception as exc:
                logger.error("Error generating AI message: %s", exc)

        used_static_template = False
        message_body = ai_candidate if ai_candidate else None

        if not message_body:
            message_body = self._generate_static_template(birthdays, biblical_texts)
            used_static_template = True

        if not message_body:
            return None

        final_message = message_body

        if not self._validate_message(final_message):
            if not used_static_template:
                logger.warning("AI message failed final validation; retrying with static template")
                fallback = self._generate_static_template(birthdays, biblical_texts)
                used_static_template = True
                if fallback:
                    final_message = fallback
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
            name_safe = self._escape_html(name)
            ref_safe = self._escape_html(t["reference"])
            text_safe = self._escape_html(t["text"])
            
            message = f"🎉 Buon compleanno <b>{name_safe}</b>! 🎂\n\n"
            message += f"In questo giorno speciale, vogliamo augurarti ogni bene e ricordarti questo bellissimo versetto:\n\n"
            message += f'📖 <i>{ref_safe}</i>\n'
            message += f'"{text_safe}"\n\n'
            message += f"Che Dio ti benedica oggi e sempre! 🙏✨"
            
            return message
        
        # Multiple people template
        names = [f"{b['first_name']} {b['last_name']}" for b in birthdays]
        names_safe = [self._escape_html(n) for n in names]
        
        if len(names_safe) == 2:
            names_str = f"{names_safe[0]} e {names_safe[1]}"
        else:
            names_str = ", ".join(names_safe[:-1]) + f" e {names_safe[-1]}"
        
        message = f"🎉 Buon compleanno <b>{names_str}</b>! 🎂\n\n"
        message += f"In questo giorno speciale, vogliamo augurarvi ogni bene e condividere con voi questi versetti:\n\n"
        
        for b, t in zip(birthdays, biblical_texts):
            person_name = f"{b['first_name']} {b['last_name']}"
            person_name_safe = self._escape_html(person_name)
            ref_safe = self._escape_html(t["reference"])
            text_safe = self._escape_html(t["text"])
            message += f"Per <b>{person_name_safe}</b>:\n"
            message += f'📖 <i>{ref_safe}</i>: "{text_safe}"\n\n'
        
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
