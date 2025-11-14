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
import io
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
from biblical_text_selector import BiblicalTextSelector
from birthday_message_generator import BirthdayMessageGenerator
from birthday_scheduler import BirthdayScheduler

logger = logging.getLogger(__name__)

BIBLICAL_TEXTS_DEFAULT_VERSION = os.getenv('BIBLICAL_TEXTS_DEFAULT_VERSION', 'CEI2008')

# Conversation states for birthdaysettings
STATE_SETTINGS_MENU = 1
STATE_SETTINGS_EDIT = 2
STATE_SELECT_GROUP_FOR_SETTINGS = 10

# Conversation states for importbiblicaltexts
STATE_SELECT_GROUPS_FOR_TEXTS = 20
STATE_UPLOAD_TEXTS_CSV = 21

# Conversation states for previewbirthday
STATE_SELECT_GROUP_FOR_PREVIEW = 30
STATE_SELECT_BIRTHDAY_FOR_PREVIEW = 31


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
        Works in both group and private chat:
        - If in private: show group selection menu
        - If in group: show settings directly
        """
        chat = update.effective_chat
        user = update.effective_user
        
        # If in private chat, show group selection
        if chat.type == 'private':
            if not is_admin(user.id):
                await update.message.reply_text(
                    "❌ Non sei autorizzato a utilizzare questo comando."
                )
                return ConversationHandler.END
            
            # Get all authorized groups
            groups_info = self.db.get_all_groups_info()
            
            if not groups_info:
                await update.message.reply_text(
                    "⚠️ Non ci sono gruppi autorizzati nel database."
                )
                return ConversationHandler.END
            
            # Show group selection menu
            keyboard = []
            for group in groups_info[:10]:  # Show up to 10 groups
                group_id = group['group_id']
                group_name = group['group_name'] or f"Gruppo {group_id}"
                
                keyboard.append([InlineKeyboardButton(
                    f"📋 {group_name}",
                    callback_data=f"bday_settings_group_{group_id}"
                )])
            
            keyboard.append([InlineKeyboardButton(
                "❌ Annulla",
                callback_data="bday_settings_cancel"
            )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎂 *Impostazioni Compleanni*\n\n"
                "Seleziona il gruppo di cui vuoi visualizzare/modificare le impostazioni.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return STATE_SELECT_GROUP_FOR_SETTINGS
        
        # If in group, show settings directly
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text(
                "❌ Questo comando funziona nei gruppi o in chat privata."
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
        
        # Store group_id in context for callbacks
        context.user_data['birthday_settings_group_id'] = chat.id
        
        return await self._show_settings_menu(update, context, settings)
    
    async def _show_settings_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        settings: dict
    ) -> int:
        """
        Display the settings menu for a group.
        
        Args:
            update: Update object
            context: Callback context
            settings: Group birthday settings
            
        Returns:
            STATE_SETTINGS_MENU
        """
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
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        
        return STATE_SETTINGS_MENU
    
    async def handle_settings_group_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle group selection callback for settings in private chat.
        
        Returns:
            STATE_SETTINGS_MENU or ConversationHandler.END
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "bday_settings_cancel":
            await query.edit_message_text("❌ Operazione annullata.")
            return ConversationHandler.END
        
        if query.data.startswith("bday_settings_group_"):
            group_id = int(query.data.replace("bday_settings_group_", ""))
            
            # Get settings for this group
            settings = self.db.get_group_birthday_settings(group_id)
            
            if not settings:
                await query.edit_message_text("❌ Impostazioni non trovate per questo gruppo.")
                return ConversationHandler.END
            
            # Store group_id in context for callbacks
            context.user_data['birthday_settings_group_id'] = group_id
            
            # Show settings menu
            return await self._show_settings_menu(query.update, context, settings)
        
        return STATE_SELECT_GROUP_FOR_SETTINGS
    
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
    ) -> int:
        """
        Start the birthday preview process.
        
        Command: /previewbirthday
        Only works in private chat. Guides user through:
        1. Group selection
        2. Birthday selection
        3. Preview generation and display
        """
        chat = update.effective_chat
        user = update.effective_user
        
        # Check if in private chat
        if chat.type != 'private':
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo in chat privata con il bot."
            )
            return ConversationHandler.END
        
        # Check if user is admin
        if not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Non sei autorizzato a utilizzare questo comando."
            )
            return ConversationHandler.END
        
        # Get all authorized groups
        groups_info = self.db.get_all_groups_info()
        
        if not groups_info:
            await update.message.reply_text(
                "⚠️ Non ci sono gruppi autorizzati nel database."
            )
            return ConversationHandler.END
        
        # Try to update group names from Telegram API
        await self._update_group_names(context, groups_info)
        
        # Show group selection menu
        keyboard = []
        for group in groups_info[:10]:
            group_id = group['group_id']
            group_name = group['group_name'] or f"Gruppo {group_id}"
            
            keyboard.append([InlineKeyboardButton(
                f"📋 {group_name}",
                callback_data=f"preview_group_{group_id}"
            )])
        
        keyboard.append([InlineKeyboardButton(
            "❌ Annulla",
            callback_data="preview_cancel"
        )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📝 *Anteprima Messaggio Compleanno*\n\n"
            "Seleziona il gruppo per il quale vuoi vedere un'anteprima del messaggio.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return STATE_SELECT_GROUP_FOR_PREVIEW
    
    async def handle_preview_group_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle group selection for preview."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "preview_cancel":
            await query.edit_message_text("❌ Operazione annullata.")
            return ConversationHandler.END
        
        if query.data.startswith("preview_group_"):
            group_id = int(query.data.replace("preview_group_", ""))
            
            # Store group_id in context
            context.user_data['preview_group_id'] = group_id
            
            # Get birthdays for this group with pagination
            birthdays = self.db.get_birthdays_by_group(group_id)
            
            if not birthdays:
                await query.edit_message_text(
                    "❌ Nessun compleanno trovato per questo gruppo."
                )
                return ConversationHandler.END
            
            # Store birthdays and reset page
            context.user_data['preview_birthdays'] = birthdays
            context.user_data['preview_birthday_page'] = 0
            
            # Show birthdays menu
            return await self._show_preview_birthdays_menu(query, context)
        
        return STATE_SELECT_GROUP_FOR_PREVIEW
    
    async def _show_preview_birthdays_menu(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Display birthday selection menu for preview."""
        birthdays = context.user_data.get('preview_birthdays', [])
        page = context.user_data.get('preview_birthday_page', 0)
        
        items_per_page = 10
        start = page * items_per_page
        end = start + items_per_page
        current_birthdays = birthdays[start:end]
        
        keyboard = []
        for birthday in current_birthdays:
            label = f"{birthday['first_name']} {birthday['last_name'] or ''} ({birthday['birth_date']})"
            keyboard.append([InlineKeyboardButton(
                label,
                callback_data=f"preview_birthday_{birthday['id']}"
            )])
        
        # Add pagination buttons
        pagination_row = []
        if page > 0:
            pagination_row.append(InlineKeyboardButton("◀️ Precedente", callback_data="preview_prev_page"))
        
        pagination_row.append(InlineKeyboardButton(
            f"Pagina {page + 1}/{(len(birthdays) - 1) // items_per_page + 1}",
            callback_data="preview_page_info"
        ))
        
        if end < len(birthdays):
            pagination_row.append(InlineKeyboardButton("Successiva ▶️", callback_data="preview_next_page"))
        
        if pagination_row:
            keyboard.append(pagination_row)
        
        keyboard.append([InlineKeyboardButton("❌ Annulla", callback_data="preview_cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 *Seleziona il compleanno*\n\n"
            f"Mostrando {len(current_birthdays)} di {len(birthdays)} compleanni.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return STATE_SELECT_BIRTHDAY_FOR_PREVIEW
    
    async def handle_preview_pagination(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle pagination for birthday selection."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "preview_cancel":
            await query.edit_message_text("❌ Operazione annullata.")
            context.user_data.pop('preview_group_id', None)
            context.user_data.pop('preview_birthdays', None)
            context.user_data.pop('preview_birthday_page', None)
            return ConversationHandler.END
        
        if query.data == "preview_page_info":
            await query.answer("ℹ️ Usa i pulsanti per navigare", show_alert=False)
            return STATE_SELECT_BIRTHDAY_FOR_PREVIEW
        
        birthdays = context.user_data.get('preview_birthdays', [])
        page = context.user_data.get('preview_birthday_page', 0)
        items_per_page = 10
        max_page = (len(birthdays) - 1) // items_per_page
        
        if query.data == "preview_prev_page":
            if page > 0:
                context.user_data['preview_birthday_page'] = page - 1
        elif query.data == "preview_next_page":
            if page < max_page:
                context.user_data['preview_birthday_page'] = page + 1
        
        return await self._show_preview_birthdays_menu(query, context)
    
    async def handle_preview_birthday_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle birthday selection and generate preview."""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("preview_birthday_"):
            birthday_id = int(query.data.replace("preview_birthday_", ""))
            group_id = context.user_data.get('preview_group_id')
            
            # Get birthday
            birthday = self.db.get_birthday_by_id(birthday_id)
            if not birthday:
                await query.edit_message_text("❌ Compleanno non trovato.")
                return ConversationHandler.END
            
            # Check if birthday is in this group
            if group_id not in birthday['group_ids']:
                await query.edit_message_text(
                    "❌ Il compleanno non è configurato per questo gruppo."
                )
                return ConversationHandler.END
            
            # Get settings
            settings = self.db.get_group_birthday_settings(group_id)
            
            # Select biblical text
            biblical_text = self.text_selector.select_text(
                group_id=group_id,
                birthday=birthday,
                language=settings.get('language', 'it')
            )
            
            if not biblical_text:
                await query.edit_message_text(
                    "❌ Nessun testo biblico disponibile per questo gruppo.\n\n"
                    "Usa /importbiblicaltexts per importare testi."
                )
                return ConversationHandler.END
            
            # Generate message
            use_ai = settings.get('birthday_ai_enabled', 1) == 1
            message = self.message_generator.generate_message(
                birthdays=[birthday],
                biblical_texts=[biblical_text],
                use_ai=use_ai
            )
            
            if not message:
                await query.edit_message_text("❌ Errore nella generazione del messaggio.")
                return ConversationHandler.END
            
            # Add mention if enabled
            mention_enabled = settings.get('birthday_mention_enabled', 0) == 1
            if mention_enabled:
                message = self.message_generator.add_mention_if_enabled(
                    message=message,
                    birthday=birthday,
                    mention_enabled=mention_enabled
                )
            
            # Send preview in private chat only
            preview_header = f"📝 <b>ANTEPRIMA MESSAGGIO COMPLEANNO</b>\n\n"
            preview_header += f"<i>Questo messaggio NON sarà inviato, è solo un'anteprima.</i>\n\n"
            preview_header += f"━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Edit the current message to show preview
            await query.edit_message_text(
                preview_header + message,
                parse_mode='HTML'
            )
            
            # Clean up
            context.user_data.pop('preview_group_id', None)
            context.user_data.pop('preview_birthdays', None)
            context.user_data.pop('preview_birthday_page', None)
            
            return ConversationHandler.END
        
        return STATE_SELECT_BIRTHDAY_FOR_PREVIEW
    
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
        Start the biblical texts import process.
        
        Command: /importbiblicaltexts
        Only works in private chat. Guides user through:
        1. Group selection
        2. CSV file upload
        3. Processing and results
        """
        chat = update.effective_chat
        user = update.effective_user
        
        # Check if in private chat
        if chat.type != 'private':
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo in chat privata con il bot."
            )
            return ConversationHandler.END
        
        # Check if user is admin
        if not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Non sei autorizzato a utilizzare questo comando."
            )
            return ConversationHandler.END
        
        # Initialize selected groups
        context.user_data['biblical_texts_selected_groups'] = []
        
        # Get all authorized groups
        groups_info = self.db.get_all_groups_info()
        
        if not groups_info:
            await update.message.reply_text(
                "⚠️ Non ci sono gruppi autorizzati nel database.\n"
                "Aggiungi prima dei gruppi con /addgroup"
            )
            return ConversationHandler.END
        
        # Try to update group names from Telegram API
        await self._update_group_names(context, groups_info)
        
        # Show group selection menu
        await self._show_biblical_texts_group_selection_menu(update, context, groups_info)
        
        return STATE_SELECT_GROUPS_FOR_TEXTS
    
    async def _update_group_names(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        groups_info: list
    ):
        """Try to update group names from Telegram API."""
        for group in groups_info:
            group_id = group['group_id']
            try:
                chat = await context.bot.get_chat(group_id)
                if chat.title:
                    self.db.update_group_name(group_id, chat.title)
                    group['group_name'] = chat.title
                    logger.info(f"Updated group name for {group_id}: {chat.title}")
            except Exception as e:
                logger.warning(f"Could not fetch group name for {group_id}: {e}")
    
    async def _show_biblical_texts_group_selection_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        groups_info: list
    ):
        """Display the group selection menu for biblical texts import."""
        selected_groups = context.user_data.get('biblical_texts_selected_groups', [])
        
        # Build the menu
        keyboard = []
        
        # Show up to 5 groups at a time
        for group in groups_info[:5]:
            group_id = group['group_id']
            group_name = group['group_name'] or f"Gruppo {group_id}"
            
            # Mark selected groups with checkmark
            if group_id in selected_groups:
                label = f"✅ {group_name}"
            else:
                label = f"⬜ {group_name}"
            
            keyboard.append([InlineKeyboardButton(
                label,
                callback_data=f"biblical_texts_group_{group_id}"
            )])
        
        # Add "Done" button
        keyboard.append([InlineKeyboardButton(
            "✔️ Fatto - Continua",
            callback_data="biblical_texts_done_selecting"
        )])
        
        # Add "Cancel" button
        keyboard.append([InlineKeyboardButton(
            "❌ Annulla",
            callback_data="biblical_texts_cancel"
        )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            "📖 *Importa Testi Biblici*\n\n"
            "Seleziona i gruppi dove vuoi aggiungere i testi biblici.\n"
            "Puoi selezionare più gruppi.\n\n"
            f"Gruppi selezionati: *{len(selected_groups)}*\n\n"
            "Clicca su un gruppo per selezionarlo/deselezionarlo.\n"
            "Quando hai finito, clicca su '✔️ Fatto - Continua'."
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def handle_biblical_texts_group_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle group selection/deselection callback for biblical texts."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Handle cancel
        if data == "biblical_texts_cancel":
            await query.edit_message_text("❌ Operazione annullata.")
            return ConversationHandler.END
        
        # Handle done selecting
        if data == "biblical_texts_done_selecting":
            selected_groups = context.user_data.get('biblical_texts_selected_groups', [])
            
            if not selected_groups:
                await query.answer("⚠️ Seleziona almeno un gruppo!", show_alert=True)
                return STATE_SELECT_GROUPS_FOR_TEXTS
            
            # Move to CSV upload
            group_names = []
            for group_id in selected_groups:
                name = self.db.get_group_name_by_id(group_id)
                group_names.append(name or f"Gruppo {group_id}")
            
            await query.edit_message_text(
                f"✅ Hai selezionato {len(selected_groups)} gruppo/i:\n" +
                "\n".join([f"• {name}" for name in group_names]) +
                "\n\n📖 *Importa Testi Biblici*\n\n"
                "Invia un file CSV con i seguenti campi:\n\n"
                "`reference,text,version,theme,age_min,age_max,gender_preference`\n\n"
                "*Esempio:*\n"
                "`Giovanni 3:16,Perché Dio ha tanto amato il mondo...,amore,,,`\n\n"
                "I campi `theme`, `age_min`, `age_max`, `gender_preference` sono opzionali.\n\n"
                "La colonna `version` è facoltativa (usa il valore di default configurato).\n\n"
                "Carica ora il file CSV.",
                parse_mode='Markdown'
            )
            
            return STATE_UPLOAD_TEXTS_CSV
        
        # Handle group toggle
        if data.startswith("biblical_texts_group_"):
            group_id = int(data.replace("biblical_texts_group_", ""))
            selected_groups = context.user_data.get('biblical_texts_selected_groups', [])
            
            if group_id in selected_groups:
                selected_groups.remove(group_id)
            else:
                selected_groups.append(group_id)
            
            context.user_data['biblical_texts_selected_groups'] = selected_groups
            
            # Refresh the menu
            groups_info = self.db.get_all_groups_info()
            await self._show_biblical_texts_group_selection_menu(update, context, groups_info)
            
            return STATE_SELECT_GROUPS_FOR_TEXTS
        
        return STATE_SELECT_GROUPS_FOR_TEXTS
    
    async def handle_biblical_texts_csv_upload(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle CSV file upload and process biblical texts."""
        # Check if document is attached
        if not update.message.document:
            await update.message.reply_text(
                "⚠️ Per favore, carica un file CSV.\n"
                "Usa /importbiblicaltexts per ricominciare o /cancel per annullare."
            )
            return STATE_UPLOAD_TEXTS_CSV
        
        document = update.message.document
        
        # Check if it's a CSV file
        if not document.file_name.endswith('.csv'):
            await update.message.reply_text(
                "⚠️ Il file deve essere un CSV.\n"
                "Carica un file con estensione .csv"
            )
            return STATE_UPLOAD_TEXTS_CSV
        
        # Download the file
        try:
            file = await context.bot.get_file(document.file_id)
            file_bytes = await file.download_as_bytearray()
            
            # Process CSV
            selected_groups = context.user_data.get('biblical_texts_selected_groups', [])
            result = await self._process_biblical_texts_csv(file_bytes, selected_groups)
            
            # Send results
            await update.message.reply_text(
                result['message'],
                parse_mode='Markdown'
            )
            
            # Clean up user data
            context.user_data.pop('biblical_texts_selected_groups', None)
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error processing biblical texts CSV: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Errore durante l'elaborazione del file:\n{str(e)}\n\n"
                "Verifica il formato del CSV e riprova."
            )
            return STATE_UPLOAD_TEXTS_CSV
    
    async def _process_biblical_texts_csv(
        self,
        file_bytes: bytearray,
        group_ids: list
    ) -> dict:
        """Process CSV file and import biblical texts."""
        # Decode file
        text = file_bytes.decode('utf-8-sig')
        if text and text[0] == '\ufeff':
            text = text.lstrip('\ufeff')

        csv_reader = csv.DictReader(io.StringIO(text))

        valid_rows = []
        parsing_errors = []

        for row_num, row in enumerate(csv_reader, start=2):
            reference = row.get('reference', '').strip()
            text_content = row.get('text', '').strip()
            version = row.get('version', '').strip() or BIBLICAL_TEXTS_DEFAULT_VERSION
            language = row.get('language', '').strip() or 'it'
            theme = row.get('theme', '').strip() or None
            gender_pref = row.get('gender_preference', '').strip() or None

            if not reference or not text_content:
                msg = f"Riga {row_num}: riferimento o testo mancante"
                parsing_errors.append(msg)
                logger.warning(msg)
                continue

            try:
                age_min = int(row['age_min']) if row.get('age_min', '').strip() else None
            except ValueError:
                msg = f"Riga {row_num}: age_min non valido ({row.get('age_min')})"
                parsing_errors.append(msg)
                logger.warning(msg)
                continue

            try:
                age_max = int(row['age_max']) if row.get('age_max', '').strip() else None
            except ValueError:
                msg = f"Riga {row_num}: age_max non valido ({row.get('age_max')})"
                parsing_errors.append(msg)
                logger.warning(msg)
                continue

            valid_rows.append({
                'row_num': row_num,
                'reference': reference,
                'text': text_content,
                'language': language,
                'version': version,
                'theme': theme,
                'age_min': age_min,
                'age_max': age_max,
                'gender_preference': gender_pref
            })

        if not valid_rows:
            message = "❌ Nessun testo valido trovato nel CSV."
            if parsing_errors:
                message += "\n" + "\n".join(parsing_errors[:5])
                if len(parsing_errors) > 5:
                    message += f"\n... e altri {len(parsing_errors) - 5} messaggi"
            return {
                'message': message,
                'errors': parsing_errors,
                'group_stats': {},
                'deleted': {}
            }

        deletion_summary = {}
        for group_id in group_ids:
            deleted = self.db.delete_biblical_texts_for_group(group_id)
            deletion_summary[group_id] = deleted

        group_stats = {
            group_id: {'imported': 0, 'duplicates': 0, 'failed': 0}
            for group_id in group_ids
        }
        insert_errors = []

        for row in valid_rows:
            for group_id in group_ids:
                if self.db.biblical_text_exists(
                    group_id,
                    reference=row['reference'],
                    version=row['version']
                ):
                    group_stats[group_id]['duplicates'] += 1
                    continue

                text_id = self.db.add_biblical_text(
                    group_id=group_id,
                    reference=row['reference'],
                    text=row['text'],
                    language=row['language'],
                    version=row['version'],
                    theme=row['theme'],
                    age_min=row['age_min'],
                    age_max=row['age_max'],
                    gender_preference=row['gender_preference']
                )

                if text_id:
                    group_stats[group_id]['imported'] += 1
                else:
                    group_stats[group_id]['failed'] += 1
                    insert_errors.append(
                        f"Gruppo {group_id}, riga {row['row_num']}: errore salvataggio"
                    )

        message = "✅ *Importazione completata*\n\n"
        message += f"Gruppi aggiornati: {len(group_ids)}\n"

        for group_id in group_ids:
            stats = group_stats[group_id]
            deleted = deletion_summary.get(group_id, 0)
            message += (
                f"• Gruppo {group_id}: rimossi {deleted} testi precedenti, "
                f"{stats['imported']} nuovi, {stats['duplicates']} duplicati"
            )
            if stats['failed']:
                message += f", {stats['failed']} salvataggi falliti"
            message += "\n"

        combined_errors = parsing_errors + insert_errors
        if combined_errors:
            message += "\n⚠️ *Avvisi durante l'importazione:*\n"
            for note in combined_errors[:5]:
                message += f"• {note}\n"
            if len(combined_errors) > 5:
                message += f"... e altri {len(combined_errors) - 5} messaggi\n"

        return {
            'message': message,
            'errors': combined_errors,
            'group_stats': group_stats,
            'deleted': deletion_summary
        }
    
    async def cancel_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel current operation."""
        context.user_data.pop('biblical_texts_selected_groups', None)
        context.user_data.pop('birthday_settings_group_id', None)
        context.user_data.pop('birthday_settings_action', None)
        await update.message.reply_text("❌ Operazione annullata.")
        return ConversationHandler.END


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
            CommandHandler('birthdaysettings', commands.birthday_settings_command)
        ],
        states={
            STATE_SELECT_GROUP_FOR_SETTINGS: [
                CallbackQueryHandler(commands.handle_settings_group_selection)
            ],
            STATE_SETTINGS_MENU: [
                CallbackQueryHandler(commands.handle_settings_callback, pattern='^bday_')
            ],
            STATE_SETTINGS_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, commands.handle_settings_input),
                CommandHandler('cancel', commands.cancel_command)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', commands.cancel_command)
        ],
        per_message=False
    )


def get_import_biblical_texts_conversation_handler(db: Database) -> ConversationHandler:
    """
    Create the conversation handler for importing biblical texts.
    
    Args:
        db: Database instance
        
    Returns:
        ConversationHandler for biblical texts import
    """
    commands = BirthdayAdminCommands(db)
    
    return ConversationHandler(
        entry_points=[
            CommandHandler('importbiblicaltexts', commands.import_biblical_texts_command)
        ],
        states={
            STATE_SELECT_GROUPS_FOR_TEXTS: [
                CallbackQueryHandler(commands.handle_biblical_texts_group_selection)
            ],
            STATE_UPLOAD_TEXTS_CSV: [
                MessageHandler(filters.Document.ALL, commands.handle_biblical_texts_csv_upload),
                CommandHandler('cancel', commands.cancel_command)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', commands.cancel_command)
        ],
        per_message=False
    )


def get_preview_birthday_conversation_handler(db: Database) -> ConversationHandler:
    """
    Create the conversation handler for previewing birthday messages.
    
    Args:
        db: Database instance
        
    Returns:
        ConversationHandler for birthday preview
    """
    commands = BirthdayAdminCommands(db)
    
    return ConversationHandler(
        entry_points=[
            CommandHandler('previewbirthday', commands.preview_birthday_command)
        ],
        states={
            STATE_SELECT_GROUP_FOR_PREVIEW: [
                CallbackQueryHandler(commands.handle_preview_group_selection)
            ],
            STATE_SELECT_BIRTHDAY_FOR_PREVIEW: [
                CallbackQueryHandler(commands.handle_preview_pagination, pattern='^preview_(prev|next)_page$|^preview_page_info$|^preview_cancel$'),
                CallbackQueryHandler(commands.handle_preview_birthday_selection, pattern='^preview_birthday_')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', commands.cancel_command)
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
    
    # Conversation handlers for settings, import, and preview
    application.add_handler(get_birthday_admin_conversation_handler(db))
    application.add_handler(get_import_biblical_texts_conversation_handler(db))
    application.add_handler(get_preview_birthday_conversation_handler(db))
    
    # Simple command handlers
    application.add_handler(CommandHandler('birthdaystats', commands.birthday_stats_command))
    
    logger.info("Birthday admin commands registered")
