"""
Birthday Admin Commands Module
===============================

Admin commands for managing the birthday notification system:
- /birthdaysettings - Configure group birthday notification settings
- /previewbirthday - Preview birthday message before sending
- /sendbirthday - Manually send birthday message for testing
- /birthdaystats - View statistics on sent birthday messages
- /importbiblicaltexts - Import biblical texts from CSV file
- /listbiblicaltexts - List biblical texts for a group
- /deletebiblicaltext - Delete a biblical text

All commands require admin privileges.
"""

import logging
import os
import csv
from typing import Optional
from io import StringIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from database import Database
from utils import is_admin
from biblical_text_selector import BiblicalTextSelector, import_biblical_texts_from_csv
from birthday_message_generator import BirthdayMessageGenerator
from birthday_scheduler import BirthdayScheduler

logger = logging.getLogger(__name__)

# Conversation states
STATE_SETTINGS_MENU = 1
STATE_SETTINGS_EDIT = 2
STATE_CSV_UPLOAD = 3


class BirthdayAdminCommands:
    """Handles all admin commands for birthday notification system."""
    
    def __init__(self, db: Database):
        """
        Initialize birthday admin commands handler.
        
        Args:
            db: Database instance
        """
        self.db = db
        self.text_selector = BiblicalTextSelector(db)
        self.message_generator = BirthdayMessageGenerator()
    
    async def birthday_settings_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Show birthday notification settings for the group.
        
        Command: /birthdaysettings
        """
        chat = update.effective_chat
        user = update.effective_user
        
        # Check if command is in a group
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text(
                "❌ Questo comando funziona solo nei gruppi."
            )
            return ConversationHandler.END
        
        # Check admin status
        if not await is_admin(update, context, user.id, chat.id):
            await update.message.reply_text(
                "❌ Solo gli amministratori possono usare questo comando."
            )
            return ConversationHandler.END
        
        # Get current settings
        settings = self.db.get_group_birthday_settings(chat.id)
        
        if not settings:
            await update.message.reply_text(
                "❌ Gruppo non trovato nel database."
            )
            return ConversationHandler.END
        
        # Format settings message
        message = f"🎂 <b>Impostazioni Compleanni</b>\n\n"
        message += f"Gruppo: {settings['group_name']}\n\n"
        message += f"🌍 <b>Timezone:</b> {settings['timezone']}\n"
        message += f"⏰ <b>Orario invio:</b> {settings['birthday_send_time']}\n"
        message += f"🔔 <b>Mention abilitati:</b> {'Sì' if settings['birthday_mention_enabled'] else 'No'}\n"
        message += f"🤖 <b>Messaggi AI:</b> {'Sì' if settings['birthday_ai_enabled'] else 'No (template statico)'}\n"
        message += f"🔄 <b>Giorni retry:</b> {settings['birthday_retry_days']}\n"
        
        # Create inline keyboard
        keyboard = [
            [InlineKeyboardButton("🌍 Modifica Timezone", callback_data='bday_set_timezone')],
            [InlineKeyboardButton("⏰ Modifica Orario", callback_data='bday_set_time')],
            [InlineKeyboardButton("🔔 Toggle Mention", callback_data='bday_toggle_mention')],
            [InlineKeyboardButton("🤖 Toggle AI", callback_data='bday_toggle_ai')],
            [InlineKeyboardButton("🔄 Modifica Retry", callback_data='bday_set_retry')],
            [InlineKeyboardButton("❌ Chiudi", callback_data='bday_close')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Store group_id in context for callbacks
        context.user_data['birthday_settings_group_id'] = chat.id
        
        return STATE_SETTINGS_MENU
    
    async def handle_settings_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle button presses in settings menu."""
        query = update.callback_query
        await query.answer()
        
        group_id = context.user_data.get('birthday_settings_group_id')
        if not group_id:
            await query.edit_message_text("❌ Sessione scaduta. Usa /birthdaysettings di nuovo.")
            return ConversationHandler.END
        
        action = query.data
        
        if action == 'bday_close':
            await query.edit_message_text("✅ Impostazioni chiuse.")
            return ConversationHandler.END
        
        elif action == 'bday_toggle_mention':
            settings = self.db.get_group_birthday_settings(group_id)
            new_value = 0 if settings['birthday_mention_enabled'] else 1
            self.db.update_group_birthday_settings(
                group_id=group_id,
                birthday_mention_enabled=new_value
            )
            await query.edit_message_text(
                f"✅ Mention {'abilitati' if new_value else 'disabilitati'}.\n\n"
                f"Usa /birthdaysettings per vedere le impostazioni aggiornate."
            )
            return ConversationHandler.END
        
        elif action == 'bday_toggle_ai':
            settings = self.db.get_group_birthday_settings(group_id)
            new_value = 0 if settings['birthday_ai_enabled'] else 1
            self.db.update_group_birthday_settings(
                group_id=group_id,
                birthday_ai_enabled=new_value
            )
            await query.edit_message_text(
                f"✅ Messaggi AI {'abilitati' if new_value else 'disabilitati (userò template statici)'}.\n\n"
                f"Usa /birthdaysettings per vedere le impostazioni aggiornate."
            )
            return ConversationHandler.END
        
        elif action == 'bday_set_timezone':
            await query.edit_message_text(
                "🌍 Invia il nuovo timezone in formato IANA (esempio: Europe/Rome, America/New_York).\n\n"
                "Lista completa: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\n\n"
                "Usa /cancel per annullare."
            )
            context.user_data['birthday_settings_action'] = 'timezone'
            return STATE_SETTINGS_EDIT
        
        elif action == 'bday_set_time':
            await query.edit_message_text(
                "⏰ Invia il nuovo orario di invio in formato HH:MM (esempio: 09:00, 14:30).\n\n"
                "Usa /cancel per annullare."
            )
            context.user_data['birthday_settings_action'] = 'time'
            return STATE_SETTINGS_EDIT
        
        elif action == 'bday_set_retry':
            await query.edit_message_text(
                "🔄 Invia il numero di giorni per i retry (esempio: 2, 3, 5).\n\n"
                "Usa /cancel per annullare."
            )
            context.user_data['birthday_settings_action'] = 'retry'
            return STATE_SETTINGS_EDIT
        
        return STATE_SETTINGS_MENU
    
    async def handle_settings_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle text input for settings changes."""
        group_id = context.user_data.get('birthday_settings_group_id')
        action = context.user_data.get('birthday_settings_action')
        
        if not group_id or not action:
            await update.message.reply_text("❌ Sessione scaduta.")
            return ConversationHandler.END
        
        text = update.message.text.strip()
        
        try:
            if action == 'timezone':
                # Validate timezone
                from zoneinfo import ZoneInfo
                ZoneInfo(text)  # This will raise an exception if invalid
                
                self.db.update_group_birthday_settings(
                    group_id=group_id,
                    timezone=text
                )
                await update.message.reply_text(
                    f"✅ Timezone aggiornato a: {text}\n\n"
                    f"Usa /birthdaysettings per vedere le impostazioni."
                )
            
            elif action == 'time':
                # Validate time format (HH:MM)
                import re
                if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', text):
                    await update.message.reply_text(
                        "❌ Formato non valido. Usa HH:MM (esempio: 09:00)"
                    )
                    return STATE_SETTINGS_EDIT
                
                self.db.update_group_birthday_settings(
                    group_id=group_id,
                    birthday_send_time=text
                )
                await update.message.reply_text(
                    f"✅ Orario invio aggiornato a: {text}\n\n"
                    f"Usa /birthdaysettings per vedere le impostazioni."
                )
            
            elif action == 'retry':
                # Validate number
                days = int(text)
                if days < 0 or days > 7:
                    await update.message.reply_text(
                        "❌ Numero non valido. Usa un numero tra 0 e 7."
                    )
                    return STATE_SETTINGS_EDIT
                
                self.db.update_group_birthday_settings(
                    group_id=group_id,
                    birthday_retry_days=days
                )
                await update.message.reply_text(
                    f"✅ Giorni retry aggiornati a: {days}\n\n"
                    f"Usa /birthdaysettings per vedere le impostazioni."
                )
            
            return ConversationHandler.END
        
        except Exception as e:
            await update.message.reply_text(
                f"❌ Errore: {str(e)}\n\nRiprova o usa /cancel per annullare."
            )
            return STATE_SETTINGS_EDIT
    
    async def cancel_settings(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel settings conversation."""
        await update.message.reply_text("❌ Operazione annullata.")
        return ConversationHandler.END
    
    async def preview_birthday_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Preview a birthday message for a specific person.
        
        Command: /previewbirthday <birthday_id>
        """
        chat = update.effective_chat
        user = update.effective_user
        
        # Check admin
        if not await is_admin(update, context, user.id, chat.id):
            await update.message.reply_text(
                "❌ Solo gli amministratori possono usare questo comando."
            )
            return
        
        # Parse birthday_id
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "❌ Uso: /previewbirthday <birthday_id>\n\n"
                "Usa /listbirthdays per vedere gli ID."
            )
            return
        
        try:
            birthday_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ ID compleanno non valido.")
            return
        
        # Get birthday
        birthday = self.db.get_birthday_by_id(birthday_id)
        if not birthday:
            await update.message.reply_text(f"❌ Compleanno {birthday_id} non trovato.")
            return
        
        # Check if birthday is in this group
        if chat.id not in birthday['group_ids']:
            await update.message.reply_text(
                f"❌ Il compleanno {birthday_id} non è configurato per questo gruppo."
            )
            return
        
        # Get settings
        settings = self.db.get_group_birthday_settings(chat.id)
        
        # Select biblical text
        biblical_text = self.text_selector.select_text(
            group_id=chat.id,
            birthday=birthday,
            language=settings.get('language', 'it')
        )
        
        if not biblical_text:
            await update.message.reply_text(
                "❌ Nessun testo biblico disponibile per questo gruppo.\n\n"
                "Usa /importbiblicaltexts per importare testi."
            )
            return
        
        # Generate message
        use_ai = settings.get('birthday_ai_enabled', 1) == 1
        message = self.message_generator.generate_message(
            birthdays=[birthday],
            biblical_texts=[biblical_text],
            use_ai=use_ai
        )
        
        if not message:
            await update.message.reply_text("❌ Errore nella generazione del messaggio.")
            return
        
        # Add mention if enabled
        mention_enabled = settings.get('birthday_mention_enabled', 0) == 1
        if mention_enabled:
            message = self.message_generator.add_mention_if_enabled(
                message=message,
                birthday=birthday,
                mention_enabled=mention_enabled
            )
        
        # Send preview
        preview_header = f"📝 <b>ANTEPRIMA MESSAGGIO COMPLEANNO</b>\n\n"
        preview_header += f"<i>Questo messaggio NON sarà inviato, è solo un'anteprima.</i>\n\n"
        preview_header += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(
            preview_header + message,
            parse_mode='HTML'
        )
    
    async def birthday_stats_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Show birthday message statistics.
        
        Command: /birthdaystats [days]
        """
        chat = update.effective_chat
        user = update.effective_user
        
        # Check if in group
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text(
                "❌ Questo comando funziona solo nei gruppi."
            )
            return
        
        # Check admin
        if not await is_admin(update, context, user.id, chat.id):
            await update.message.reply_text(
                "❌ Solo gli amministratori possono usare questo comando."
            )
            return
        
        # Parse days parameter
        days = 30
        if context.args and len(context.args) >= 1:
            try:
                days = int(context.args[0])
                if days < 1 or days > 365:
                    await update.message.reply_text("❌ Giorni devono essere tra 1 e 365.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Numero di giorni non valido.")
                return
        
        # Get statistics
        stats = self.db.get_birthday_messages_stats(group_id=chat.id, days=days)
        
        message = f"📊 <b>Statistiche Messaggi Compleanno</b>\n\n"
        message += f"Periodo: ultimi {days} giorni\n\n"
        message += f"📤 <b>Totale messaggi:</b> {stats['total']}\n"
        message += f"✅ <b>Inviati:</b> {stats['sent']}\n"
        message += f"❌ <b>Falliti:</b> {stats['failed']}\n"
        message += f"⏳ <b>In attesa:</b> {stats['pending']}\n\n"
        
        if stats['total'] > 0:
            message += f"📈 <b>Tasso di successo:</b> {stats['success_rate']:.1f}%\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def import_biblical_texts_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Import biblical texts from CSV file.
        
        Command: /importbiblicaltexts
        Then send CSV file as document.
        """
        chat = update.effective_chat
        user = update.effective_user
        
        # Check if in group
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text(
                "❌ Questo comando funziona solo nei gruppi."
            )
            return ConversationHandler.END
        
        # Check admin
        if not await is_admin(update, context, user.id, chat.id):
            await update.message.reply_text(
                "❌ Solo gli amministratori possono usare questo comando."
            )
            return ConversationHandler.END
        
        message = "📖 <b>Importa Testi Biblici</b>\n\n"
        message += "Invia un file CSV con i seguenti campi:\n\n"
        message += "<code>reference,text,theme,age_min,age_max,gender_preference</code>\n\n"
        message += "<b>Esempio:</b>\n"
        message += '<code>"Giovanni 3:16","Perché Dio ha tanto amato...","amore",,,</code>\n\n'
        message += "Usa /cancel per annullare."
        
        await update.message.reply_text(message, parse_mode='HTML')
        
        context.user_data['import_texts_group_id'] = chat.id
        
        return STATE_CSV_UPLOAD
    
    async def handle_csv_upload(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle CSV file upload for biblical texts."""
        group_id = context.user_data.get('import_texts_group_id')
        
        if not group_id:
            await update.message.reply_text("❌ Sessione scaduta.")
            return ConversationHandler.END
        
        # Get document
        document = update.message.document
        
        if not document or not document.file_name.endswith('.csv'):
            await update.message.reply_text(
                "❌ Per favore invia un file CSV.\n\nUsa /cancel per annullare."
            )
            return STATE_CSV_UPLOAD
        
        try:
            # Download file
            file = await context.bot.get_file(document.file_id)
            csv_content = await file.download_as_bytearray()
            csv_text = csv_content.decode('utf-8')
            
            # Parse and import
            count = 0
            reader = csv.DictReader(StringIO(csv_text))
            
            for row in reader:
                reference = row.get('reference', '').strip()
                text = row.get('text', '').strip()
                
                if not reference or not text:
                    continue
                
                theme = row.get('theme', '').strip() or None
                age_min = int(row['age_min']) if row.get('age_min', '').strip() else None
                age_max = int(row['age_max']) if row.get('age_max', '').strip() else None
                gender_pref = row.get('gender_preference', '').strip() or None
                
                text_id = self.db.add_biblical_text(
                    group_id=group_id,
                    reference=reference,
                    text=text,
                    language='it',
                    theme=theme,
                    age_min=age_min,
                    age_max=age_max,
                    gender_preference=gender_pref
                )
                
                if text_id:
                    count += 1
            
            await update.message.reply_text(
                f"✅ Importati {count} testi biblici con successo!"
            )
            
            return ConversationHandler.END
        
        except Exception as e:
            logger.error(f"Error importing CSV: {e}")
            await update.message.reply_text(
                f"❌ Errore nell'importazione: {str(e)}\n\nRiprova o usa /cancel."
            )
            return STATE_CSV_UPLOAD


def get_birthday_admin_conversation_handler(db: Database) -> ConversationHandler:
    """
    Create the conversation handler for birthday settings.
    
    Args:
        db: Database instance
        
    Returns:
        ConversationHandler for birthday settings
    """
    commands = BirthdayAdminCommands(db)
    
    return ConversationHandler(
        entry_points=[
            CommandHandler('birthdaysettings', commands.birthday_settings_command),
            CommandHandler('importbiblicaltexts', commands.import_biblical_texts_command)
        ],
        states={
            STATE_SETTINGS_MENU: [
                CallbackQueryHandler(commands.handle_settings_callback, pattern='^bday_')
            ],
            STATE_SETTINGS_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, commands.handle_settings_input),
                CommandHandler('cancel', commands.cancel_settings)
            ],
            STATE_CSV_UPLOAD: [
                MessageHandler(filters.Document.ALL, commands.handle_csv_upload),
                CommandHandler('cancel', commands.cancel_settings)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', commands.cancel_settings)
        ],
        per_message=False
    )


def register_birthday_admin_commands(application, db: Database) -> None:
    """
    Register all birthday admin command handlers.
    
    Args:
        application: Telegram Application instance
        db: Database instance
    """
    commands = BirthdayAdminCommands(db)
    
    # Conversation handler for settings and import
    application.add_handler(get_birthday_admin_conversation_handler(db))
    
    # Simple command handlers
    application.add_handler(CommandHandler('previewbirthday', commands.preview_birthday_command))
    application.add_handler(CommandHandler('birthdaystats', commands.birthday_stats_command))
    
    logger.info("Birthday admin commands registered")
