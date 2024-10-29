# ChurchGroupHelper

## [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for Church Groups

This project aims to create a bot that serves as a multi-tool for church group chats, providing a range of practical features:

1. **Transcribe audio messages** for easy sharing and documentation of voice messages.
2. **Schedule messages** for future events or reminders. (TODO)
3. **Store important notes** or reminders, like messages or birthdays. (TODO)
4. **Summarize group conversations** from a specific message onward, useful for recapping discussions. (TODO)
5. **Create and manage polls with a quorum** for voting on key decisions, especially valuable for church council meetings. (TODO)

The bot is designed for easy deployment using Docker Compose. It performs best on a system with a powerful CPU or an NVIDIA GPU (e.g., RTX A2000 6GB). My setup uses CUDA Version 12.6 and Nvidia Driver Version 560; however, feel free to modify the Dockerfile to fit your environment.

---

## How To
To run the bot for the first time it needs an .env file with the following variables setted:
| VARIABLE       | Description    |
| -------------- | -------------- |
| WORK_DIR       | fullpath to projecr root dir |
| CONTAINER_NAME | The name that docker will use for the container |
| BOT_TOKEN      | Telegram bot token taked from BotFather |

You have also to change the ADMINS list in bot.py inserting your admin telegram IDs.

If you are using a Nvidia GPU remember to install the [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-container-toolkit)

## Bot commands
| Command        | Description    |
| -------------- | -------------- |
| /setlanguage _<lang>_ | Set the language inside a group or for the direct use. _lang_ has to be in ISO 639-1. |
| /addgroup | Add a particular group to the list of authorized one to use the AI models, since them are resource consuming tasks. This command is valid if sent inside the group, only bot admins can use it. |
| /removegroup | Remove a particular group from the list of authorized one. |

## Libraries Used

- **Python**: 3.12
- **python-telegram-bot**: For handling Telegram interactions.
- **Whisper**: For audio transcription, supporting multilingual capabilities.
- **PyTorch**: As a backend for Whisper and other potential machine learning tasks.

## Supported Languages

Currently, the bot's interface is in Italian, but transcription supports all languages available through [Whisper](https://github.com/openai/whisper).

For summarization, which uses [Llama 3.2 3B](https://llamaimodel.com/3b/), eight languages are supported: English, German, French, Italian, Portuguese, Hindi, Spanish, and Thai.

If you’d like to contribute translations or other enhancements, feel free to [reach out](mailto:churchBot@sf-paris.dev).

