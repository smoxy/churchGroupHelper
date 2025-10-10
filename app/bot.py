import os
import logging
from telegram import Update, Bot
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from iso639 import Language
from database import Database
from transcription import Transcriber
from utils import TOKEN, is_admin, TMP_DIR, send_action, split_message
from datetime import datetime

# Enable logging
logConf = logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database.get_instance()
transcriber = Transcriber()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ciao! Trascriverò le registrazioni audio che mi invii. Puoi anche aggiungermi "
        "a un gruppo per trascrivere le registrazioni audio inviate nel gruppo.\n"
        "Usa /addgroup per autorizzare un gruppo.\n"
        "Usa /adduser per autorizzare un utente.\n"
        "Usa /removegroup per rimuovere un gruppo autorizzato.\n"
        "Usa /removeuser per rimuovere un utente autorizzato.\n"
        "Usa /setlanguage <codice_lingua> per impostare la lingua di trascrizione nel gruppo "
        "o usalo in chat privata con me per impostare la lingua di trascrizione dei messaggi che mi invierai.\n\n"
        "NOTA: questo bot non tiene in memoria i file audio trascritti, ma memorizza per un periodo limitato (7 giorni)"
        " le trascrizioni, senza legarle a un utente, così da non dover trascrivere nuovamente lo stesso file."
    )

def is_allowed(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    
    # Check if the user is an admin
    if user_id and is_admin(user_id):
        return True
    
    # Check if user or group is authorized
    if user_id in db.get_authorized_users():
        return True
    if chat_id in db.get_authorized_groups():
        return True
    
    return False
    

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    args = context.args

    if chat.type in ['group', 'supergroup']:
        # Group language
        if not is_admin(user.id):
            await update.message.reply_text("Solo gli amministratori possono impostare la lingua del gruppo.")
            return
        if len(args) != 1:
            await update.message.reply_text('Uso: /setlanguage <codice_lingua>')
            return
        language_code = args[0]
        # Verify if the language code is valid
        valid_languages = transcriber.valid_languages()
        if language_code not in valid_languages:
            await update.message.reply_text(
                f'Codice lingua non valido. Lingue supportate: {", ".join(valid_languages)}'
            )
            return
        db.update_group_language(chat.id, language_code)
        await update.message.reply_text(f'Lingua di trascrizione del gruppo impostata su {language_code}')
    else:
        if not is_allowed(update):
            await update.message.reply_text("Non sei autorizzato a utilizzare questo comando.")
            return
        # User language
        if len(args) != 1:
            await update.message.reply_text('Uso: /setlanguage <codice_lingua>')
            return
        language_code = args[0]
        # Verify if the language code is valid
        valid_languages = transcriber.valid_languages()
        if language_code not in valid_languages:
            await update.message.reply_text(
                f'Codice lingua non valido. Lingue supportate: {", ".join(valid_languages)}'
            )
            return
        db.update_user_language(user.id, user.first_name, language_code)
        await update.message.reply_text(f'La tua lingua di trascrizione è stata impostata su {language_code}')

@send_action(ChatAction.TYPING)
async def transcribe_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type in ['group', 'supergroup']:
        group_settings = db.get_group_settings(chat.id)
        if not group_settings:
            return
        language = group_settings['language']
        group_id = chat.id
    else:
        language = db.get_user_language(user.id)
        logger.info(f"User {user.first_name}@{user.id} language: {language}")
        if not language:
            return
        group_id = None  # No group_id in private chats

    # Get the audio file
    audio = update.message.voice or update.message.audio or update.message.video_note
    if not audio:
        logger.error("No audio source found")
        return

    # Download the file
    file = await context.bot.get_file(audio.file_id)
    file_path = f'{TMP_DIR}{os.sep}{audio.file_unique_id}.ogg'
    await file.download_to_drive(file_path)

    # Transcribe the audio
    try:
        transcription, cached = transcriber.transcribe_audio(
            file_path=file_path,
            language=language,
            group_id=group_id,
            user_id=user.id,
            author_name=user.first_name,
            timestamp=update.message.date,  # Use the date of the message
            is_allowed=is_allowed(update)
        )
        if not cached and not is_allowed(update):
            assert transcription==""
            await update.message.reply_text(f"{user.first_name} is not authorized to use this function.")
        else:
            # Split long transcriptions into multiple messages
            full_text = f'Trascrizione:\n{transcription}'
            message_chunks = split_message(full_text)
            
            # Send all chunks
            for i, chunk in enumerate(message_chunks):
                if i == 0:
                    # First message replies to the audio
                    await update.message.reply_text(chunk)
                else:
                    # Subsequent messages are sent to the chat
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        await update.message.reply_text('Spiacente, si è verificato un errore durante la trascrizione.')
    finally:
        db.clean_old_transcriptions(days=7)
        # Clean up the downloaded file
        if os.path.exists(file_path):
            os.remove(file_path)

async def message_collector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if chat.type in ['group', 'supergroup']:
        # Check if group is authorized
        group_settings = db.get_group_settings(chat.id)
        if not group_settings:
            return

        # Collect messages
        db.add_message(
            group_id=chat.id,
            user_id=user.id,
            author_name=user.first_name,
            message_text=message.text,
            timestamp=message.date,
            telegram_message_id=message.message_id
        )

        # Clean old messages
        db.clean_old_messages(chat.id)

@send_action(ChatAction.TYPING)
async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.message
    language = db.get_group_language(chat.id)

    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Questo comando può essere utilizzato solo nei gruppi.")
        return

    # Check if group is authorized
    group_settings = db.get_group_settings(chat.id)
    if not group_settings:
        return

    # This command must be used as a reply to a message
    if not message.reply_to_message:
        await update.message.reply_text(
            "Per favore, rispondi a un messaggio da cui iniziare il riassunto."
        )
        return

    # Get the telegram message ID of the replied message
    start_telegram_message_id = message.reply_to_message.message_id
    
    # Find the corresponding message in our database
    messages_to_summarize = []
    all_messages = db.get_messages(chat.id)
    
    # Find messages starting from the replied message
    start_collecting = False
    for msg in all_messages:
        if msg.get('telegram_message_id') == start_telegram_message_id:
            start_collecting = True
        if start_collecting:
            messages_to_summarize.append(msg)

    if not messages_to_summarize:
        await update.message.reply_text("Non ci sono messaggi da riassumere.")
        return

    # Build structured conversation with proper context
    structured_text = ""
    previous_user_id = None
    
    for msg in messages_to_summarize:
        user_id = msg['user_id']
        author_name = msg['author_name']
        timestamp = msg['timestamp']
        message_text = msg['message_text']
        telegram_msg_id = msg.get('telegram_message_id')
        
        # Format timestamp
        time_str = timestamp.strftime("%H:%M") if isinstance(timestamp, datetime) else str(timestamp)
        
        if previous_user_id != user_id:
            # New user speaking
            structured_text += f"\n{author_name} (ID: {user_id}) at {time_str}:\n{message_text}\n"
            previous_user_id = user_id
        else:
            # Same user continuing
            structured_text += f"{message_text}\n"

    language_name = Language.match(language).name.capitalize()
    
    # Build the prompt for the AI model with improved instructions
    prompt = (
        "You are an assistant tasked with summarizing a group discussion. The summary must:\n"
        f"- Be written in {language_name}, following a neutral and objective tone.\n"
        "- Include an organic, flowing narrative that captures the essence of the conversation.\n"
        "- Identify and highlight the most critical moments and decisions by quoting directly from participants.\n"
        "- The user ID and name for each message are provided in the format: 'Name (ID: USER_ID) at TIME'.\n\n"
        "To cite and highlight important contributions, use this format:\n"
        '<a href="tg://user?id=USER_ID">"Exact quote from the user\'s message"</a>\n\n'
        "Here is the conversation:\n\n"
        f"{structured_text}\n\n"
        "Only the most relevant parts should be quoted. Focus on meaningful contributions that drove "
        "the discussion forward, and make sure they are cited exactly as written. "
        "Provide a well-structured summary with clear sections if the conversation covers multiple topics."
    )

    # Use Ollama Cloud API to get the summary with streaming
    try:
        from ollama import Client
        
        client = Client(
            host="https://ollama.com",
            headers={'Authorization': 'Bearer ' + os.getenv('OLLAMA_API_KEY')}
        )

        messages_for_llm = [
            {
                'role': 'user',
                'content': prompt,
            },
        ]

        # Send initial "generating summary" message
        status_message = await update.message.reply_text(
            "🔄 Sto generando il riassunto...",
            parse_mode='HTML'
        )

        # Stream the response and collect it
        summary = ""
        for part in client.chat('gpt-oss:20b', messages=messages_for_llm, stream=True):
            summary += part['message']['content']

        # Delete the status message
        await status_message.delete()

        # Send the complete summary
        if summary:
            # Split long summaries into multiple messages if needed
            summary_chunks = split_message(summary)
            for i, chunk in enumerate(summary_chunks):
                if i == 0:
                    await update.message.reply_text(chunk, parse_mode='HTML')
                else:
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text=chunk,
                        parse_mode='HTML'
                    )
        else:
            await update.message.reply_text(
                "Non sono riuscito a generare un riassunto.",
                parse_mode='HTML'
            )

    except Exception as e:
        logger.error(f"Error with Ollama API: {e}")
        await update.message.reply_text(
            "Si è verificato un errore durante la generazione del riassunto.",
            parse_mode='HTML'
        )
        return

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not is_admin(user.id):
        await update.message.reply_text("Non sei autorizzato a utilizzare questo comando.")
        return

    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Questo comando può essere utilizzato solo in un gruppo.")
        return

    db.add_authorized_group(chat.id, chat.title)
    await update.message.reply_text("Questo gruppo è stato aggiunto alla lista autorizzata.")

async def remove_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not is_admin(user.id):
        await update.message.reply_text("Non sei autorizzato a utilizzare questo comando.")
        return

    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Questo comando può essere utilizzato solo in un gruppo.")
        return

    db.clean_old_messages(chat.id, all_messages=True)
    db.remove_authorized_group(chat.id)
    await update.message.reply_text("Questo gruppo è stato rimosso dalla lista autorizzata.")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    args = context.args
    user_to_authorize = update.message.reply_to_message.from_user

    if not is_admin(user.id):
        await update.message.reply_text("Non sei autorizzato a utilizzare questo comando.")
        return

    if user_to_authorize.id:
        first_name = user_to_authorize.first_name
        user_id = user_to_authorize.id
    elif len(args) < 2 or not args[0].isdigit():
        await update.message.reply_text('Uso: /adduser <user_id> <first_name>')
        return
    else:
        user_id = int(args[0])
        first_name = args[1]

    db.add_authorized_user(user_id, first_name)
    await update.message.reply_text(f'Utente {first_name}@{user_id} può usare il bot per le trascrizioni')

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    args = context.args
    user_to_deauthorize = update.message.reply_to_message.from_user

    if not is_admin(user.id):
        await update.message.reply_text("Non sei autorizzato a utilizzare questo comando.")
        return

    if user_to_deauthorize.id:
        user_id = user_to_deauthorize.id
    elif len(args) < 1 or not args[0].isdigit():
        await update.message.reply_text('Uso: /removeuser <user_id>')
        return
    else:
        user_id = int(args[0])

    db.remove_authorized_user(user_id)
    await update.message.reply_text(f'Utente {user_id} rimosso dalla lista autorizzata.')

async def set_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    args = context.args

    if not is_admin(user.id):
        await update.message.reply_text("Non sei autorizzato a utilizzare questo comando.")
        return

    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("Questo comando può essere utilizzato solo in un gruppo.")
        return

    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit():
        await update.message.reply_text('Uso: /setlimits <message_limit> <time_limit_in_days>')
        return

    message_limit = int(args[0])
    time_limit = int(args[1])

    db.update_group_limits(chat.id, message_limit=message_limit, time_limit=time_limit)
    await update.message.reply_text(f"Limiti aggiornati: {message_limit} messaggi, {time_limit} giorni")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    If sended in a private chat, asks for a group to manage (list of groups where the user is an admin or a member),
        then do as for the group settings.
    
    if sended in a group, show - in private - the settings of the group:
    - Language
    - Message limit
    - Time limit
    - Members -> show the list of users recorded in the group | if user_id not in churches(admin_ids) jump this step to -> call edit_user(user_id, church_group_id)
        - Change the user's language
        - Remove the user from the group - ADMIN ONLY
        - Change the user's surname
        - Change the user's alias
        - Change the user's birthday
    """
    pass

async def edit_user(update: Update, context: ContextTypes.DEFAULT_TYPE, church_group_id=None):
    """
    Edit the user's information:
    - Name          # only add update bottom - from the telegram user's name
    - Surname       # Sensible data (will be shown only the first letter in public chats)
    - Alias         # If present, will be shown instead of the name and surname. It is chosen by the user (or an admin, but only if asked by).
    - Birthday      # Sensitive data (will be shown only the day and month in public chats where it is enabled)
    - Group_IDs     # List of groups where will be shown the user's birthday (only for admins - an admin can see only the groups where they are admins)
    - Member_of     # Group where the user is an official church's member (only for admins) (change Member_of is done by the new church's group admin. If the user is already a member of another church, the admins of the old church will be notified and asked to confirm the change)
    
    Can be called by the user or an admin. Only the user or the admins can view the user's information.

    """
    pass

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('setlanguage', set_language))#TODO: move this function to group settings
    application.add_handler(CommandHandler('addgroup', add_group))
    application.add_handler(CommandHandler('removegroup', remove_group))
    application.add_handler(CommandHandler('setlimits', set_limits))
    application.add_handler(CommandHandler('summarize', summarize))
    application.add_handler(CommandHandler('adduser', add_user))        #TODO: remove this function - it's not in the purpose of the churchBot
    application.add_handler(CommandHandler('removeuser', remove_user))  #TODO: remove this function - it's not in the purpose of the churchBot
    application.add_handler(CommandHandler('settings', settings))

    # Message handlers
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE, transcribe_audio))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_collector))

    # Start the bot
    logger.info("Il bot ha iniziato a ricevere aggiornamenti.")
    application.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("[i] Gracefully exit")
        quit()
