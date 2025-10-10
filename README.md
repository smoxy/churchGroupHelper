# ChurchGroupHelper

## [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for Church Groups

This project aims to create a bot that serves as a multi-tool for church group chats, providing a range of practical features:

1. **Transcribe audio messages** for easy sharing and documentation of voice messages.
2. **Schedule messages** for future events or reminders. (TODO)
3. **Store important notes** or reminders, like messages or birthdays. (TODO)
4. **Summarize group conversations** from a specific message onward, useful for recapping discussions. (TODO)
5. **Create and manage polls with a quorum** for voting on key decisions, especially valuable for church council meetings. (TODO)

The bot is designed for easy deployment using Docker Compose. **Now uses an external Whisper ASR service**, reducing resource requirements significantly (from 6GB RAM to ~512MB).

### Key Features

- ✅ **Automatic message splitting**: Long transcriptions are automatically split into multiple messages respecting Telegram's 4096 character limit
- ✅ **External Whisper service**: Uses [Whisper ASR Webservice](https://github.com/ahmetoner/whisper-asr-webservice) for efficient transcription
- ✅ **Smart text splitting**: Respects sentence boundaries when splitting long messages
- ✅ **Cache system**: Already transcribed audio files are retrieved from cache without re-transcription

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
| /summarize _<n_messages>_    | Summarize the last _n_messages_, or reply to the message from which you would like the summary |

## Libraries Used

- **Python**: 3.12
- **python-telegram-bot**: For handling Telegram interactions.
- **Whisper**: For audio transcription, supporting multilingual capabilities.
- **PyTorch**: As a backend for Whisper and other potential machine learning tasks.
- **python-iso639**: To find the full name from the ISO 639-1 language setted.

## Supported Languages

Currently, the bot's interface is in Italian, but transcription supports all languages available through [Whisper](https://github.com/openai/whisper).

For summarization, which uses [Llama 3.2 3B](https://llamaimodel.com/3b/), eight languages are supported: English, German, French, Italian, Portuguese, Hindi, Spanish, and Thai.

If you’d like to contribute translations or other enhancements, feel free to [reach out](mailto:churchBot@sf-paris.dev).

