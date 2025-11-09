# ChurchGroupHelper

## [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for Church Groups

A comprehensive Telegram bot designed to serve as a multi-tool for church group chats, providing practical features for community management, communication, and administration.

## 🎯 Project Goals and Status

### ✅ Completed Features

1. **[Audio Transcription](#-audio-transcription)** - Transcribe audio messages in group chats and private conversations
   - Multi-language support via Whisper ASR
   - External service integration for resource efficiency
   - Smart caching system to avoid re-transcription
   - See [EXTERNAL_WHISPER_SERVICE.md](manuals/EXTERNAL_WHISPER_SERVICE.md) for details

2. **[Conversation Summarization](#-conversation-summaries)** - Intelligent AI-powered summaries of group discussions
   - LangChain-based summarization with Ollama Cloud
   - Unified view of text messages and audio transcriptions
   - Clickable citations and user mentions
   - See [SUMMARIZE_FEATURE.md](manuals/SUMMARIZE_FEATURE.md) and [LANGCHAIN_REFACTORING.md](manuals/LANGCHAIN_REFACTORING.md)

3. **[Transcription Enhancement](#-transcription-improvement)** - AI-powered punctuation and formatting correction
   - Automatic improvement of long audio transcriptions
   - Better readability with proper punctuation
   - See [TRANSCRIPTION_IMPROVEMENT.md](manuals/TRANSCRIPTION_IMPROVEMENT.md)

4. **[Birthday Notification System](#-birthday-notifications)** - Automated birthday celebrations with AI-generated messages
   - Full CRUD interface for birthday management
   - Automated daily checks with timezone-aware scheduling
   - AI-generated personalized messages (OpenAI or Ollama)
   - Smart biblical text selection (age/gender appropriate)
   - Retry logic for failed sends
   - Comprehensive admin commands
   - See [BIRTHDAY_NOTIFICATIONS.md](manuals/BIRTHDAY_NOTIFICATIONS.md) and [AI_PROVIDER_CONFIGURATION.md](manuals/AI_PROVIDER_CONFIGURATION.md)

### 🚧 In Development

5. **Multi-Provider AI Support** - Flexible AI provider selection
   - Auto-detection: OpenAI (if API key present) or Ollama (default)
   - Supports all major OpenAI models (GPT-3.5, GPT-4o, etc.)
   - Supports Ollama cloud and self-hosted
   - Per-feature model configuration
   - See [AI_PROVIDER_CONFIGURATION.md](manuals/AI_PROVIDER_CONFIGURATION.md)

### 📋 Planned Features

6. **Enhanced Member Database**
   - Permission system for birthday visibility
   - Member directory with photos
   - Role and ministry tracking
   - Attendance tracking

5. **Scheduled Messages** - Send messages to multiple chats simultaneously at scheduled times
   - **Requirements:**
     - Message scheduling interface (command or inline keyboard)
     - Multi-chat selection system
     - Time zone management
     - Message queue system
     - Persistent storage for scheduled messages
     - Admin-only access controls
   - **Use Cases:**
     - Announcements for church events
     - Weekly reminders across multiple groups
     - Coordinated communication to different communities

6. **ACMS Integration** - Member scraping and management from ACMS website
   - **Requirements:**
     - ACMS website authentication (credential-less, privacy-first)
     - Scraper for member data (name, surname, birthday)
     - Sync mechanism with local database
     - "Dummy" flag for non-official members
     - Soft-delete for removed members (mark as inactive)
     - **IMPORTANT: Requires permissions from SDA and UICCA (for Italy)**
   - **Privacy Considerations:**
     - No credential storage (temporary session only)
     - Local-only data storage
     - User consent management
     - GDPR compliance for EU members
   - **Technical Approach:**
     - Separate microservice architecture (recommended)
     - API-based communication with main bot
     - Scheduled sync jobs
     - Conflict resolution for data updates

7. **Advanced Polling System** - Democratic decision-making with quorum support
   - **Requirements:**
     - Poll creation with customizable options
     - Quorum setting (minimum participation threshold)
     - Vote tracking (who voted, what they voted)
     - Time-based expiration
     - Auto-close on absolute majority (50% + 1)
     - Vote reminders before expiration
     - Results visualization
     - Admin controls (close poll, extend time)
   - **Use Cases:**
     - Church council decisions
     - Event planning votes
     - Budget approvals
     - Community consensus building
   - **Technical Features:**
     - Vote immutability (no revoting)
     - Anonymous vs. transparent voting modes
     - Result export for record-keeping
     - Integration with message scheduling for reminders

## 🚀 Quick Start

The bot is designed for easy deployment using Docker Compose. **Now uses an external Whisper ASR service**, reducing resource requirements significantly (from 6GB RAM to ~512MB).

## 🔑 Key Features

### 🎤 Audio Transcription
- **Automatic message splitting**: Long transcriptions are automatically split into multiple messages respecting Telegram's 4096 character limit
- **External Whisper service**: Uses [Whisper ASR Webservice](https://github.com/ahmetoner/whisper-asr-webservice) for efficient transcription
- **Smart text splitting**: Respects sentence boundaries when splitting long messages
- **Cache system**: Already transcribed audio files are retrieved from cache without re-transcription
- **Multi-language support**: Supports all languages available through Whisper
- **Authorization system**: Per-user and per-group access control

### 📝 Conversation Summaries
- **AI-powered summaries**: Generate comprehensive summaries using **LangChain** with Ollama Cloud (`gpt-oss:120b`)
- **Smart citations**: Summaries include clickable user mentions and message links
- **Unified conversation view**: Messages and transcriptions are combined chronologically in summaries
- **Few-shot learning**: AI trained with examples for consistent HTML output format
- **Multilingual output**: Summaries generated in the group's configured language
- **Real-time streaming**: See the summary being generated live

### ✨ Transcription Improvement
- **AI-powered enhancement**: Automatic punctuation and formatting correction for long audio transcriptions using LangChain
- **Better readability**: Transforms raw transcriptions into properly formatted text
- **Smart processing**: Only improves transcriptions longer than 300 characters
- **Language-aware**: Respects the configured language for each group

See detailed documentation:
- [EXTERNAL_WHISPER_SERVICE.md](manuals/EXTERNAL_WHISPER_SERVICE.md) - Whisper setup and configuration
- [SUMMARIZE_FEATURE.md](manuals/SUMMARIZE_FEATURE.md) - Summary feature details
- [LANGCHAIN_REFACTORING.md](manuals/LANGCHAIN_REFACTORING.md) - Technical architecture
- [TRANSCRIPTION_IMPROVEMENT.md](manuals/TRANSCRIPTION_IMPROVEMENT.md) - AI enhancement system

---

## How To
To run the bot for the first time it needs an .env file with the following variables setted:
| VARIABLE       | Description    |
| -------------- | -------------- |
| WORK_DIR       | fullpath to projecr root dir |
| CONTAINER_NAME | The name that docker will use for the container |
| BOT_TOKEN      | Telegram bot token taked from BotFather |
| ADMINS         | IDs separated by a comma to declare which are the bot's admins |
| OPENAI_API_KEY | (Optional) Your OpenAI API key - if set, uses OpenAI instead of Ollama |
| OPENAI_MODEL   | (Optional) OpenAI model to use. Default: `gpt-5-nano`. Options: `gpt-4o-mini`, `gpt-4o`, etc. |
| OLLAMA_API_KEY | Your Ollama Cloud API key for AI features (get it from https://ollama.com) |
| OLLAMA_BASE_URL | (Optional) Ollama server URL. Default: `https://ollama.com`. For local: `http://localhost:11434` |
| OLLAMA_MODEL   | (Optional) Ollama model to use. Default: `gpt-oss:20b` |
| AI_PROVIDER    | (Optional) Force specific provider: `openai` or `ollama`. Auto-detects if not set. |
| TRANSCRIPTION_IMPROVER_MODEL | (Optional) Model override for transcription improvement |

**AI Provider Priority**: If `OPENAI_API_KEY` is set, uses OpenAI. Otherwise uses Ollama. See [AI_PROVIDER_CONFIGURATION.md](manuals/AI_PROVIDER_CONFIGURATION.md) for details.

If you are using a Nvidia GPU remember to install the [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-container-toolkit)

## Bot commands
| Command                      | Description                  |
| ---------------------------- | ---------------------------- |
| /setlanguage _<lang>_        | Set the language inside a group or for the direct use. _lang_ has to be in ISO 639-1. |
| /addgroup                    | Add a particular group to the list of authorized one to use the AI models. Only bot admins can use it. |
| /removegroup                 | Remove a particular group from the list of authorized one. |
| /adduser _<user_id>_ _<first_name>_ | Allow the user to use the transcription in private. Reply to a message for auto-fill. |
| /removeuser _<user_id>_     | Remove the user from the list of allowed one. |
| /setlimits _<n_messages>_ _<days>_  | Set retaining limits of collected messages. Older messages will be deleted. |
| /summarize                   | Reply to any message to summarize the conversation from that point. Uses AI (OpenAI or Ollama). |
| /birthday                    | Add a new birthday to the database (interactive conversation). |
| /listbirthdays              | List all birthdays with pagination (10 per page). |
| /editbirthday _<id>_        | Edit birthday details (interactive field selection). |
| /deletebirthday _<id>_      | Delete a birthday with confirmation. |
| /linkbirthday _<id>_        | Link a birthday to a Telegram user (forward their message). |
| /birthdaysettings           | Configure birthday notification settings for the group (admin only). |
| /importbiblicaltexts        | Import biblical texts from CSV file (admin only). |
| /previewbirthday _<id>_     | Preview AI-generated birthday message before sending (admin only). |
| /sendbirthday _<id>_        | Manually send birthday message to groups (admin only). |
| /birthdaystats              | View birthday message statistics (admin only). |

---

## 🗺️ Roadmap & Next Steps

### ✅ Recently Completed (November 2025)

1. **Birthday Notification System** - Fully implemented!
   - ✅ Daily birthday check job with timezone awareness
   - ✅ AI-generated personalized messages (OpenAI/Ollama support)
   - ✅ Smart biblical text selection (age/gender appropriate)
   - ✅ Retry logic for failed sends (2-day window)
   - ✅ Full CRUD interface with pagination
   - ✅ Admin commands for configuration
   - ✅ Comprehensive tracking and statistics

2. **Multi-Provider AI Support** - OpenAI + Ollama!
   - ✅ Auto-detection based on API keys
   - ✅ Support for all OpenAI models (GPT-3.5, GPT-4o, etc.)
   - ✅ Support for Ollama cloud and self-hosted
   - ✅ Unified API via LangChain
   - ✅ Per-feature model configuration

### Immediate Priorities (Q1 2026)

1. **Testing & Documentation**
   - [ ] Unit tests for birthday notification system
   - [ ] Integration tests for AI providers
   - [ ] User manual for birthday features
   - [ ] Admin guide for biblical text management

2. **Message Scheduling Foundation**
   - [ ] Design message queue database schema
   - [ ] Implement scheduling interface
   - [ ] Create multi-chat delivery system
   - [ ] Add time zone management
   - [ ] Build message preview and editing

### Medium-term Goals (Q2-Q3 2026)

3. **ACMS Integration Microservice**
   - [ ] Research ACMS website authentication flow
   - [ ] Request permissions from SDA and UICCA
   - [ ] Design microservice architecture
   - [ ] Implement secure scraper (no credential retention)
   - [ ] Create sync mechanism with main database
   - [ ] Add conflict resolution for data updates
   - [ ] Implement privacy controls and consent management

4. **Advanced Polling System**
   - [ ] Design poll database schema with vote tracking
   - [ ] Implement poll creation interface
   - [ ] Add quorum calculation and validation
   - [ ] Create time-based expiration system
   - [ ] Build vote reminder scheduler
   - [ ] Implement absolute majority auto-close
   - [ ] Add results visualization and export

### Long-term Vision

- **Multi-church support**: Manage multiple church communities from one bot instance
- **Mobile app integration**: Companion app for better member management
- **Event management**: Full calendar integration for church events
- **Donation tracking**: Transparent financial reporting (privacy-first)
- **Volunteer scheduling**: Coordinate service rotations and assignments

---

## 🔒 Privacy & Security

The bot implements **privacy-by-design** principles:

- **Group transcriptions**: Linked to message metadata for summaries only
- **Private transcriptions**: NO user metadata stored (fully private)
- **Data minimization**: User info stored ONLY where necessary
- **Foreign key architecture**: Avoids data duplication
- **Retention policies**: Configurable message retention with automatic cleanup
- **No credential storage**: Authentication sessions are never persisted (ACMS integration)
- **GDPR compliance**: User consent management and data portability

---

## 📖 Detailed Feature Documentation

### 📝 Conversation Summaries

The `/summarize` command generates intelligent summaries of group conversations using AI.

**How it works:**
1. Reply to any message with `/summarize`
2. Bot collects all messages and transcriptions from that point onwards
3. Sends to Ollama Cloud API (`gpt-oss:120b`) via LangChain
4. Generates comprehensive summary with citations and links

**See:** [SUMMARIZE_FEATURE.md](manuals/SUMMARIZE_FEATURE.md) | [LANGCHAIN_REFACTORING.md](manuals/LANGCHAIN_REFACTORING.md)

### 🎤 Audio Transcription

Transcribe voice messages in groups and private chats with multi-language support.

**Features:**
- External Whisper ASR service integration
- Smart caching to avoid re-transcription
- Automatic message splitting for long transcriptions
- Authorization system for users and groups

**See:** [EXTERNAL_WHISPER_SERVICE.md](manuals/EXTERNAL_WHISPER_SERVICE.md)

### ✨ Transcription Improvement

AI-powered enhancement of raw transcriptions with proper punctuation and formatting.

**Features:**
- Automatic processing for transcriptions > 300 characters
- Language-aware formatting
- LangChain-based improvement pipeline

**See:** [TRANSCRIPTION_IMPROVEMENT.md](manuals/TRANSCRIPTION_IMPROVEMENT.md)

---

## 🛠️ Technology Stack

### Core Technologies
- **Python**: 3.12
- **python-telegram-bot**: Telegram Bot API wrapper for handling interactions
- **SQLAlchemy**: ORM for database management with relationship support
- **LangChain**: Framework for AI/LLM applications and prompt engineering

### AI & Machine Learning
- **Whisper ASR**: Multi-language audio transcription via [Whisper ASR Webservice](https://github.com/ahmetoner/whisper-asr-webservice)
- **Ollama Cloud**: AI-powered features (summaries, transcription improvement)
  - Summary model: `gpt-oss:120b`
  - Transcription improvement model: `gpt-oss:20b` (configurable)

### Supporting Libraries
- **python-iso639**: Language code handling (ISO 639-1 standard)
- **geopy**: Geographic location services for church addresses
- **Docker & Docker Compose**: Containerized deployment

---

## 🌍 Supported Languages

- **Bot Interface**: Currently Italian (contributions welcome for translations)
- **Transcription**: All languages supported by [Whisper](https://github.com/openai/whisper) (100+ languages)
- **Summaries**: Generated in the group's configured language (via `/setlanguage`)
- **AI Enhancement**: Language-aware formatting and punctuation

---

## 🤝 Contributing

Contributions are welcome! Areas where help is especially appreciated:

- **Translations**: Help translate the bot interface to other languages
- **Feature Development**: Pick up any planned feature from the roadmap
- **Testing**: Test the bot in different scenarios and report issues
- **Documentation**: Improve guides and add examples

Feel free to [reach out](mailto:churchBot@sf-paris.dev) or open an issue/PR on GitHub.

---

## 📚 Documentation Index

### Setup & Configuration
- [SETUP.md](manuals/SETUP.md) - Complete setup guide
- [SETUP_VELOCE.md](manuals/SETUP_VELOCE.md) - Quick setup guide (Italian)
- [EXTERNAL_WHISPER_SERVICE.md](manuals/EXTERNAL_WHISPER_SERVICE.md) - Whisper service configuration

### Features
- [SUMMARIZE_FEATURE.md](manuals/SUMMARIZE_FEATURE.md) - Conversation summarization
- [TRANSCRIPTION_IMPROVEMENT.md](manuals/TRANSCRIPTION_IMPROVEMENT.md) - AI transcription enhancement

### Architecture & Development
- [DATABASE.md](manuals/DATABASE.md) - Database schema and design
- [README_ORM.md](manuals/README_ORM.md) - ORM implementation details
- [LANGCHAIN_REFACTORING.md](manuals/LANGCHAIN_REFACTORING.md) - LangChain integration architecture
- [LANGCHAIN_SETUP.md](manuals/LANGCHAIN_SETUP.md) - LangChain setup guide

### Migration & Changelogs
- [MIGRATION_GUIDE.md](manuals/MIGRATION_GUIDE.md) - Database migration guide
- [MIGRATION_SUMMARY.md](manuals/MIGRATION_SUMMARY.md) - Migration overview
- [OLLAMA_INTEGRATION_CHANGELOG.md](manuals/OLLAMA_INTEGRATION_CHANGELOG.md) - Ollama integration changes
- [TRANSCRIPTION_IMPROVEMENT_CHANGELOG.md](manuals/TRANSCRIPTION_IMPROVEMENT_CHANGELOG.md) - Enhancement feature changes

### Quick Reference
- [QUICK_REFERENCE.md](manuals/QUICK_REFERENCE.md) - Command and feature reference
- [RIEPILOGO_IMPLEMENTAZIONE.md](manuals/RIEPILOGO_IMPLEMENTAZIONE.md) - Implementation summary (Italian)
- [RIEPILOGO_MODIFICHE.md](manuals/RIEPILOGO_MODIFICHE.md) - Changes summary (Italian)

---

## 📄 License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

---

## 📬 Contact

For questions, suggestions, or contributions, contact: [churchBot@sf-paris.dev](mailto:churchBot@sf-paris.dev)

---

**Made with ❤️ for church communities**

