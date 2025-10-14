"""Utility module responsible for AI-powered conversation summaries."""

import logging
import re
from datetime import datetime
from textwrap import dedent
from typing import Any, Dict, List, Tuple

from iso639 import Language
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

# Pre-compiled regular expressions to avoid recompilation on every run
_HEADER_PATTERN = re.compile(r'^#{1,6}\s+', flags=re.MULTILINE)
_BOLD_PATTERN = re.compile(r'\*\*(.+?)\*\*')
_ITALIC_PATTERN = re.compile(r'\*(.+?)\*')
_UNDERSCORE_BOLD_PATTERN = re.compile(r'__(.+?)__')
_UNDERSCORE_ITALIC_PATTERN = re.compile(r'_(.+?)_')
_BLOCKQUOTE_PATTERN = re.compile(r'^>\s+', flags=re.MULTILINE)
_HR_PATTERN = re.compile(r'^[-*_]{3,}$', flags=re.MULTILINE)
_MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\([^\)]+\)')

# In-memory cache to avoid rebuilding the LangChain stack repeatedly
_SUMMARIZER_CACHE: Dict[str, "ConversationSummarizer"] = {}


class ConversationSummarizer:
    """Encapsulates the LangChain summarisation pipeline for chat transcripts."""

    def __init__(self, api_key: str) -> None:
        """Initialise the LangChain model stack."""
        self._api_key = api_key
        self._llm = ChatOllama(
            base_url="https://ollama.com",
            model="gpt-oss:120b",
            temperature=0.3,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {api_key}"
                }
            }
        )
        self._chain = self._build_chain()

    @property
    def chain(self) -> Runnable[Dict[str, str], str]:
        """Expose the Runnable chain (primarily for testing/inspection)."""
        return self._chain

    def _build_chain(self) -> Runnable[Dict[str, str], str]:
        """Assemble the prompt, few-shot examples, model and output parser."""
        examples = [
            {
                "input": dedent(
                    """
                    Simone (ID: 265699760) at 23:45 [MSG_ID: 21526]:
                    Test

                    Simone (ID: 265699760) at 23:46 [MSG_ID: 21527]:
                    Test

                    Simone (ID: 265699760) at 23:47 [MSG_ID: 21528]:
                    Prova
                    """
                ).strip(),
                "output": (
                    '<a href="tg://user?id=265699760">Simone</a> ha inviato alcuni messaggi '
                    'di test tra le 23:45 e le 23:47.'
                ),
            },
            {
                "input": dedent(
                    """
                    Mario (ID: 123456) at 14:30 [MSG_ID: 100]:
                    Dobbiamo organizzare l'evento di domani

                    Luigi (ID: 789012) at 14:32 [MSG_ID: 101]:
                    Sì, propongo di trovarci alle 15:00

                    Mario (ID: 123456) at 14:35 [MSG_ID: 102]:
                    Perfetto, confermo

                    Luigi (ID: 789012) at 14:36 [MSG_ID: 103]:
                    [AUDIO TRASCRITTO]: Vi aspetto in piazza alle tre del pomeriggio
                    """
                ).strip(),
                "output": (
                    '<a href="tg://user?id=123456">Mario</a> e '
                    '<a href="tg://user?id=789012">Luigi</a> hanno organizzato un incontro '
                    'per domani. Luigi ha <a href="https://t.me/c/CHAT_ID/101">proposto di '
                    'trovarsi alle 15:00</a> e ha confermato tramite messaggio vocale '
                    "l'appuntamento in piazza."
                ),
            },
        ]

        example_prompt = ChatPromptTemplate.from_messages(
            [("human", "Conversation:\n{input}"), ("ai", "{output}")]
        )

        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=examples,
        )

        final_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(self._system_prompt()),
                SystemMessagePromptTemplate.from_template(self._developer_prompt()),
                few_shot_prompt,
                (
                    "human",
                    "Conversation transcript:\n{conversation}\n\n"
                    "Respond with a single HTML paragraph that follows every instruction.",
                ),
            ]
        )

        return final_prompt | self._llm | StrOutputParser()

    def _system_prompt(self) -> str:
        """Prompt that defines all formatting and behavioural constraints."""
        current_date = datetime.utcnow().date().isoformat()
        return dedent(
            f"""
            You are ChatGPT, a large language model trained by OpenAI.
            Knowledge cutoff: 2024-06
            Current date: {current_date}
            Reasoning: high
            # Valid channels: analysis, commentary, final. Channel must be included for every message.
            """
        ).strip()

    def _developer_prompt(self) -> str:
        """Developer instructions rendered in Harmony-friendly layout."""
        return dedent(
            """
            # Instructions
            You are a concise conversation summariser. Obey every rule below without exception.

            ## Language
            - Write the final response in {language_name}.

            ## Output Format
            - Produce a single coherent paragraph no longer than 200 words.
            - Allowed HTML tags: <b>, <i>, <a href="URL">text</a>.
            - Do not emit Markdown, lists, headings, blockquotes, or horizontal rules.
            - Keep explicit line breaks to a minimum; only use blank lines when strictly necessary.

            ## Linking
            - Mention participants as <a href="tg://user?id=USER_ID">Name</a>.
            - Reference important messages as <a href="https://t.me/c/{chat_id_for_link}/MSG_ID">"quoted text"</a>.
            - Replace USER_ID and MSG_ID with the numeric identifiers from the transcript.

            ## Content Rules
            1. Summaries of trivial chatter (tests, greetings) must stay within two sentences.
            2. Highlight key decisions, follow-ups, deadlines, and commitments.
            3. Note audio messages succinctly as "messaggio vocale" or "messaggi vocali".
            4. Maintain a neutral, factual tone.

            ## Harmony Compliance
            - Emit reasoning steps on the analysis channel when required, and place the polished answer on the final channel only.
            - Never fabricate information that is not present in the transcript.

            # Exemplars
            Conversation:
            Simone (ID: 265699760) at 23:45 [MSG_ID: 21526]:
            Test

            Simone (ID: 265699760) at 23:46 [MSG_ID: 21527]:
            Test

            Simone (ID: 265699760) at 23:47 [MSG_ID: 21528]:
            Prova

            Summary:
            <a href="tg://user?id=265699760">Simone</a> ha inviato alcuni messaggi di test tra le 23:45 e le 23:47.

            Conversation:
            Mario (ID: 123456) at 14:30 [MSG_ID: 100]:
            Dobbiamo organizzare l'evento di domani

            Luigi (ID: 789012) at 14:32 [MSG_ID: 101]:
            Sì, propongo di trovarci alle 15:00

            Mario (ID: 123456) at 14:35 [MSG_ID: 102]:
            Perfetto, confermo

            Luigi (ID: 789012) at 14:36 [MSG_ID: 103]:
            [AUDIO TRASCRITTO]: Vi aspetto in piazza alle tre del pomeriggio

            Summary:
            <a href="tg://user?id=123456">Mario</a> e <a href="tg://user?id=789012">Luigi</a> hanno organizzato un incontro per domani. Luigi ha <a href="https://t.me/c/CHAT_ID/101">proposto di trovarsi alle 15:00</a> e ha confermato tramite messaggio vocale l'appuntamento in piazza.
            """
        ).strip()

    def format_conversation(
        self, messages: List[Dict[str, Any]], chat_id: int
    ) -> Tuple[str, str]:
        """Normalise conversation records into a chronological narrative string."""
        chat_id_for_link = (
            str(chat_id)[4:]
            if str(chat_id).startswith("-100")
            else str(chat_id)
        )

        chunks: List[str] = []
        previous_user_id: Any = None

        for item in messages:
            user_id = item.get("user_id")
            author_name = item.get("author_name", "Utente")
            timestamp = item.get("timestamp")
            telegram_msg_id = item.get("telegram_message_id", "N/A")

            if item.get("is_audio"):
                transcription = item.get("transcription", "")
                if not transcription:
                    continue
                content = f"[AUDIO TRASCRITTO]: {transcription}"
            else:
                content = item.get("message_text")
                if not content:
                    continue

            time_str = (
                timestamp.strftime("%H:%M")
                if isinstance(timestamp, datetime)
                else str(timestamp)
            )

            if previous_user_id != user_id:
                chunks.append(
                    f"\n{author_name} (ID: {user_id}) at {time_str} "
                    f"[MSG_ID: {telegram_msg_id}]:\n{content}\n"
                )
                previous_user_id = user_id
            else:
                chunks.append(f"[MSG_ID: {telegram_msg_id}]: {content}\n")

        structured_text = "".join(chunks).replace("CHAT_ID", chat_id_for_link)
        return structured_text, chat_id_for_link

    def summarize(
        self, messages: List[Dict[str, Any]], chat_id: int, language: str | None = "it"
    ) -> str:
        """Generate an HTML summary for the supplied conversation."""
        conversation, chat_id_for_link = self.format_conversation(messages, chat_id)
        if not conversation.strip():
            logger.warning("Conversation preprocessing produced no content to summarise.")
            return ""

        language_name = _resolve_language_name(language)

        logger.info("Generating summary for %s messages", len(messages))
        logger.debug("Conversation payload length: %s chars", len(conversation))

        payload = {
            "conversation": conversation,
            "language_name": language_name,
            "chat_id_for_link": chat_id_for_link,
        }

        try:
            summary = self._chain.invoke(payload)
        except Exception:  # pragma: no cover - propagated to caller
            logger.error("LangChain pipeline failed", exc_info=True)
            raise

        summary = summary.replace("CHAT_ID", chat_id_for_link)
        summary = self._clean_markdown_artifacts(summary)

        logger.info("Summary generated with %s characters", len(summary))
        return summary.strip()

    def _clean_markdown_artifacts(self, text: str) -> str:
        """Remove Markdown remnants that occasionally slip through the LLM."""
        text = _HEADER_PATTERN.sub("", text)
        text = _BOLD_PATTERN.sub(r"<b>\1</b>", text)
        text = _ITALIC_PATTERN.sub(r"<i>\1</i>", text)
        text = _UNDERSCORE_BOLD_PATTERN.sub(r"<b>\1</b>", text)
        text = _UNDERSCORE_ITALIC_PATTERN.sub(r"<i>\1</i>", text)
        text = _BLOCKQUOTE_PATTERN.sub("", text)
        text = _HR_PATTERN.sub("", text)
        text = _MARKDOWN_LINK_PATTERN.sub(r"\1", text)
        return text


def _resolve_language_name(language: str | None) -> str:
    """Convert a language code or name to a human-readable language label."""
    if not language:
        return "Italian"

    try:
        match = Language.match(language)
        if match and match.name:
            return match.name.capitalize()
    except Exception:
        logger.debug("Unable to resolve language name for '%s'", language, exc_info=True)

    return str(language).capitalize()


def create_summarizer(api_key: str) -> ConversationSummarizer:
    """Return a cached ConversationSummarizer instance for the provided API key."""
    if api_key not in _SUMMARIZER_CACHE:
        _SUMMARIZER_CACHE[api_key] = ConversationSummarizer(api_key)
    return _SUMMARIZER_CACHE[api_key]
