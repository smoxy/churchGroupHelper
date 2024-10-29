import os
import json
import torch
import logging
from telegram import ( Update, Bot )
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
import whisper

TMP_DIR = f'{os.sep}tmp{os.sep}cache'

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admins
ADMINS = [] # Add your amdin IDs here

# Whitelists
WHITELISTED_GROUPS = set()
WHITELISTED_USERS = set()

# Dictionary to store language settings for each group
group_languages = {}



def load_whitelist():
    global WHITELISTED_GROUPS, WHITELISTED_USERS
    try:
        with open('whitelist.json', 'r') as f:
            data = json.load(f)
            WHITELISTED_GROUPS = set(data.get('groups', []))
            WHITELISTED_USERS = set(data.get('users', []))
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        save_whitelist()



def save_whitelist():
    data = {
        'groups': list(WHITELISTED_GROUPS),
        'users': list(WHITELISTED_USERS),
    }
    with open('whitelist.json', 'w') as f:
        json.dump(data, f)



def is_allowed(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None

    # Allow admins
    if user_id in ADMINS:
        return True

    # Check if user or group is whitelisted
    if user_id in WHITELISTED_USERS:
        return True
    if chat_id in WHITELISTED_GROUPS:
        return True

    return False



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    await update.message.reply_text(
        "Ciao! Trascriverò le registrazioni audio inviate in questo gruppo. "
        "Usa /setlanguage <codice_lingua> per impostare la lingua di trascrizione."
    )

    

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    await update.message.reply_text(
        "Comandi disponibili:\n"
        "/setlanguage <codice_lingua> - Imposta la lingua di trascrizione\n"
        "/addgroup - Aggiunge il gruppo alla whitelist\n"
        "/removegroup - Rimuove il gruppo dalla whitelist"
    )



async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    if len(context.args) != 1:
        await update.message.reply_text('Uso: /setlanguage <codice_lingua>')
        return

    language_code = context.args[0]
    
    # Verify if the language code is valid
    valid_languages = whisper.tokenizer.LANGUAGES.keys()
    if language_code not in valid_languages:
        await update.message.reply_text(
            f'Codice lingua non valido. Lingue supportate: {", ".join(valid_languages)}'
        )
        return

    chat_id = update.effective_chat.id
    group_languages[chat_id] = language_code
    await update.message.reply_text(f'Lingua di trascrizione impostata su {language_code}')



async def transcribe_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    chat_id = update.effective_chat.id
    language = group_languages.get(chat_id, 'it')  # Default language is Italian

    # Get the audio file
    audio = update.message.voice or update.message.audio or update.message.video_note
    if not audio:
        logger.error("Does not contain audio source")
        return

    # Download the file
    file = await context.bot.get_file(audio.file_id)
    file_path = f'{TMP_DIR}{os.sep}{audio.file_unique_id}.ogg'
    await file.download_to_drive(file_path)

    # Check if CUDA is available
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cpu':
        logger.warning("CUDA non disponibile. Utilizzo della CPU per la trascrizione.")
        await update.message.reply_text("CUDA non disponibile. Contattare l'amministratore del bot.")
        return

    # Load the Whisper model with CUDA support
    model = whisper.load_model('turbo', device=device)

    # Transcribe the audio
    try:
        result = model.transcribe(file_path, language=language)
        text = result['text'].strip()
        await update.message.reply_text(f'Trascrizione:\n{text}')
    except Exception as e:
        logger.error(f'Errore durante la trascrizione: {e}')
        await update.message.reply_text('Spiacente, si è verificato un errore durante la trascrizione.')
    finally:
        # Delete the model and clear GPU memory
        del model # for now I want to keep the model
        if device == 'cuda':
            torch.cuda.empty_cache()
        # Clean up the downloaded file
        if os.path.exists(file_path):
            os.remove(file_path)



async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None

    if user_id not in ADMINS:
        await update.message.reply_text("Non sei autorizzato a utilizzare questo comando.")
        return

    # Check if the command is sent in a group
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Questo comando può essere utilizzato solo in un gruppo.")
        return

    if chat_id in WHITELISTED_GROUPS:
        await update.message.reply_text("Questo gruppo è già nella whitelist.")
        return

    WHITELISTED_GROUPS.add(chat_id)
    save_whitelist()
    await update.message.reply_text("Questo gruppo è stato aggiunto alla whitelist.")


    
async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    
    if user_id not in ADMINS:
        await update.message.reply_text("Non sei autorizzato a utilizzare questo comando.")
        return

    # Check if the command is sent in a group
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Questo comando può essere utilizzato solo in un gruppo.")
        return

    if chat_id not in WHITELISTED_GROUPS:
        await update.message.reply_text("Questo gruppo non è nella whitelist.")
        return

    WHITELISTED_GROUPS.remove(chat_id)
    save_whitelist()
    await update.message.reply_text("Questo gruppo è stato aggiunto alla whitelist.")



async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    logger.warning(f'L\'aggiornamento "{update}" ha causato l\'errore "{context.error}"')



def main():
    # Load the whitelist
    load_whitelist()

    # Get the bot token from the environment
    TOKEN = os.getenv('TOKEN')
    if not TOKEN:
        raise ValueError("Nessun token del bot Telegram fornito. Imposta la variabile d'ambiente TOKEN.")

    application = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('setlanguage', set_language))
    application.add_handler(CommandHandler('addgroup', add_group))
    application.add_handler(CommandHandler('removegroup', remove_group))
    # Message handler for audio recordings
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE, transcribe_audio))

    # Log all errors
    application.add_error_handler(error)

    # Start the bot
    application.run_polling()
    logger.info("Il bot ha iniziato a ricevere aggiornamenti.")



if __name__ == "__main__":
    import asyncio
    try:
        main()
    except KeyboardInterrupt:
        logger.info("[i] Gracefully exit")
        quit()
