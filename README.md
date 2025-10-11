# ChurchGroupHelper

## [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for Church Groups

This project aims to create a bot that serves as a multi-tool for church group chats, providing a range of practical features:

1. **Transcribe audio messages** for easy sharing and documentation of voice messages.
2. **Schedule messages** for future events or reminders. (TODO)
3. **Store important notes** or reminders, like messages or birthdays. (TODO)
4. **Summarize group conversations** from a specific message onward, useful for recapping discussions using Ollama Cloud API.
5. **Create and manage polls with a quorum** for voting on key decisions, especially valuable for church council meetings. (TODO)

The bot is designed for easy deployment using Docker Compose. **Now uses an external Whisper ASR service**, reducing resource requirements significantly (from 6GB RAM to ~512MB).

### Key Features

- ✅ **Automatic message splitting**: Long transcriptions are automatically split into multiple messages respecting Telegram's 4096 character limit
- ✅ **External Whisper service**: Uses [Whisper ASR Webservice](https://github.com/ahmetoner/whisper-asr-webservice) for efficient transcription
- ✅ **Smart text splitting**: Respects sentence boundaries when splitting long messages
- ✅ **Cache system**: Already transcribed audio files are retrieved from cache without re-transcription
- ✅ **AI-powered summaries**: Generate comprehensive summaries using **LangChain** for better prompt adherence
- ✅ **Smart citations**: Summaries include clickable user mentions and message links
- ✅ **Unified conversation view**: Messages and transcriptions are combined chronologically in summaries
- ✅ **Few-shot learning**: AI trained with examples for consistent HTML output format

See [EXTERNAL_WHISPER_SERVICE.md](EXTERNAL_WHISPER_SERVICE.md) for setup details and [LONG_MESSAGES_HANDLING.md](LONG_MESSAGES_HANDLING.md) for information about the message splitting feature.

---

## How To
To run the bot for the first time it needs an .env file with the following variables setted:
| VARIABLE       | Description    |
| -------------- | -------------- |
| WORK_DIR       | fullpath to projecr root dir |
| CONTAINER_NAME | The name that docker will use for the container |
| BOT_TOKEN      | Telegram bot token taked from BotFather |
| ADMINS         | IDs separated by a comma to declare which are the bot's admins |
| OLLAMA_API_KEY | Your Ollama Cloud API key for the summarization feature (get it from https://ollama.com) |

If you are using a Nvidia GPU remember to install the [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-container-toolkit)

## Bot commands
| Command                      | Description                  |
| ---------------------------- | ---------------------------- |
| /setlanguage _<lang>_        | Set the language inside a group or for the direct use. _lang_ has to be in ISO 639-1. |
| /addgroup                    | Add a particular group to the list of authorized one to use the AI models, since them are resource consuming tasks. This command is valid if sent inside the group, only bot admins can use it. |
| /removegroup                 | Remove a particular group from the list of authorized one. |
| /adduser _<user_id>_ _<first_name>_ | Allow the user to use the transcription in private. You can reply to a message and the bot will take the _user_id_ and the _first_name_ automatically. |
| /removeuser _<user_id>_     | Remove the user from the list of allowed one, denying the transcription feature. |
| /setlimits _<n_messages>_ _<days>_  | Set retaining limits of collected messages. The messages that are older will be permanently deleted. |
| /summarize                   | Reply to any message in the group to summarize the conversation from that message onwards. Includes both text messages and audio transcriptions. Uses LangChain with Ollama Cloud (`gpt-oss:120b`) for intelligent summaries and citations. |

---

## 📝 Conversation Summaries

The `/summarize` command generates intelligent summaries of group conversations using AI. Here's what makes it special:

### How it works

1. **Reply to any message** in the group with `/summarize`
2. The bot collects all **messages AND audio transcriptions** from that point onwards
3. Sends them to Ollama Cloud API (`gpt-oss:120b` model) orchestrated via LangChain
4. Generates a comprehensive summary with:
   - **Key discussion points** organized in a clear narrative
   - **Direct quotes** from important contributions
   - **Clickable user mentions** for easy reference
   - **Audio transcription context** (marked when relevant)

### 🔒 Privacy Design

The bot implements privacy-by-design principles:

- **Group transcriptions**: Linked to message metadata for summaries
- **Private transcriptions**: NO user metadata stored (fully private)
- **Data minimization**: User info (name, ID) stored ONLY in messages table
- **Foreign key architecture**: Transcriptions reference messages, not duplicate data
- **Retention policies**: Transcriptions cleaned up before messages (cache first)

### Example Usage

```
[User A sends a message about planning an event]
[User B responds with details]
[User C sends an audio message with additional ideas]
[User D sends text confirming]

Admin replies to User A's message with: /summarize

Bot generates:
"The group discussed planning the church event for next month. 
User A suggested organizing it, and User B provided logistical details.
User C shared additional ideas via audio message regarding venue options.
User D confirmed availability and commitment to help."
```

### Features

- ✨ **Unified conversation view**: Text and audio transcriptions merged chronologically
- 🎯 **Smart citations**: Important quotes linked to speakers with clickable message links
- 🌍 **Multilingual**: Summary generated in your group's configured language
- 🧠 **LangChain-powered**: Advanced prompt engineering with few-shot examples for consistent output
- 📏 **Concise output**: Strict 200-word limit, focusing only on key points
- 🔗 **Interactive links**: Click on user names or quoted messages to navigate directly

See [LANGCHAIN_REFACTORING.md](LANGCHAIN_REFACTORING.md) for technical details about the summarization system.
- ⚡ **Real-time streaming**: See the summary being generated live
- 📊 **Context preservation**: Maintains conversation flow and speaker attribution

### Setup

1. Add `OLLAMA_API_KEY` to your `.env` file (get it from https://ollama.com)
2. Run database migrations (in order):
   ```bash
   # Step 1: Add telegram_message_id to messages table
   python migrate_add_telegram_message_id.py ./data/bot.db
   
   # Step 2: Add message_id foreign key to transcriptions table
   python migrate_transcription_metadata.py ./data/bot.db
   ```
3. Restart the bot
4. Use `/summarize` in groups by replying to any message

**Note**: Existing transcriptions won't have message links, but new ones will work automatically.

---

## Libraries Used

- **Python**: 3.12
- **python-telegram-bot**: For handling Telegram interactions.
- **Whisper**: For audio transcription, supporting multilingual capabilities.
- **Ollama**: For AI-powered conversation summaries via Ollama Cloud API.
- **SQLAlchemy**: ORM for database management.
- **python-iso639**: To find the full name from the ISO 639-1 language setted.

## Supported Languages

Currently, the bot's interface is in Italian, but transcription supports all languages available through [Whisper](https://github.com/openai/whisper).

For summarization, the bot now leverages LangChain with Ollama Cloud's `gpt-oss:120b` model. The AI automatically writes the summary in the language configured for your group via `/setlanguage`, ensuring consistent, native-language recaps.

If you'd like to contribute translations or other enhancements, feel free to [reach out](mailto:churchBot@sf-paris.dev).

