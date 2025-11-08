"""
Birthday Manager Module

Handles birthday data entry through Telegram bot conversation.
Allows admins to:
1. Select groups where birthdays should be announced
2. Upload CSV files with birthday data
3. Import birthdays into the database

Uses telegram-menu-builder for group selection interface.
"""

import logging
import csv
import io
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
from telegram_menu_builder import MenuBuilder

from database import Database
from utils import is_admin

# Enable logging
logger = logging.getLogger(__name__)

# Conversation states
STATE_SELECT_GROUPS = 1
STATE_UPLOAD_CSV = 2

# User data keys
KEY_SELECTED_GROUPS = 'birthday_selected_groups'


class BirthdayManager:
    """
    Manages birthday data entry process.
    """
    
    def __init__(self, db: Database):
        """
        Initialize birthday manager.
        
        Args:
            db: Database instance
        """
        self.db = db
    
    async def start_birthday_entry(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Start the birthday data entry process.
        Only admins can use this command in private chat.
        
        Returns:
            Next conversation state
        """
        user = update.effective_user
        chat = update.effective_chat
        
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
        context.user_data[KEY_SELECTED_GROUPS] = []
        
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
        await self._show_group_selection_menu(update, context, groups_info)
        
        return STATE_SELECT_GROUPS
    
    async def _update_group_names(
        self, 
        context: ContextTypes.DEFAULT_TYPE,
        groups_info: List[Dict]
    ):
        """
        Try to update group names from Telegram API.
        
        Args:
            context: Callback context
            groups_info: List of group information dictionaries
        """
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
    
    async def _show_group_selection_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        groups_info: List[Dict]
    ):
        """
        Display the group selection menu using inline keyboard.
        
        Args:
            update: Update object
            context: Callback context
            groups_info: List of group information dictionaries
        """
        selected_groups = context.user_data.get(KEY_SELECTED_GROUPS, [])
        
        # Build the menu
        keyboard = []
        
        # Show up to 5 groups at a time
        for group in groups_info[:5]:
            group_id = group['group_id']
            group_name = group['group_name'] or f"Group {group_id}"
            
            # Mark selected groups with checkmark
            if group_id in selected_groups:
                label = f"✅ {group_name}"
            else:
                label = f"⬜ {group_name}"
            
            keyboard.append([InlineKeyboardButton(
                label,
                callback_data=f"birthday_group_{group_id}"
            )])
        
        # Add "Done" button
        keyboard.append([InlineKeyboardButton(
            "✔️ Fatto - Continua",
            callback_data="birthday_done_selecting"
        )])
        
        # Add "Cancel" button
        keyboard.append([InlineKeyboardButton(
            "❌ Annulla",
            callback_data="birthday_cancel"
        )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            "🎂 *Gestione Compleanni*\n\n"
            "Seleziona i gruppi dove vuoi annunciare i compleanni.\n"
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
    
    async def handle_group_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle group selection/deselection callback.
        
        Returns:
            Next conversation state
        """
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Handle cancel
        if data == "birthday_cancel":
            await query.edit_message_text("❌ Operazione annullata.")
            return ConversationHandler.END
        
        # Handle done selecting
        if data == "birthday_done_selecting":
            selected_groups = context.user_data.get(KEY_SELECTED_GROUPS, [])
            
            if not selected_groups:
                await query.answer("⚠️ Seleziona almeno un gruppo!", show_alert=True)
                return STATE_SELECT_GROUPS
            
            # Move to CSV upload
            group_names = []
            for group_id in selected_groups:
                name = self.db.get_group_name_by_id(group_id)
                group_names.append(name or f"Group {group_id}")
            
            await query.edit_message_text(
                f"✅ Hai selezionato {len(selected_groups)} gruppo/i:\n" +
                "\n".join([f"• {name}" for name in group_names]) +
                "\n\n📄 *Carica il file CSV*\n\n"
                "Il file deve avere questo formato:\n"
                "`NOME,COGNOME,DATA DI NASCITA (dd-MM-yyyy),COMMENTO`\n\n"
                "Il cognome è opzionale: se sconosciuto, lascialo vuoto (es. `Elenuzza,,28-04,NO`).\n\n"
                "La DATA DI NASCITA può essere in formato:\n"
                "• `dd-MM` (solo giorno e mese)\n"
                "• `dd-MM-yyyy` (giorno, mese e anno)\n\n"
                "Esempi:\n"
                "`Mario,Rossi,15-03-1990,Membro attivo`\n"
                "`Anna,Bianchi,23-12,Visitatrice`\n\n"
                "Carica ora il file CSV.",
                parse_mode='Markdown'
            )
            
            return STATE_UPLOAD_CSV
        
        # Handle group toggle
        if data.startswith("birthday_group_"):
            group_id = int(data.replace("birthday_group_", ""))
            selected_groups = context.user_data.get(KEY_SELECTED_GROUPS, [])
            
            if group_id in selected_groups:
                selected_groups.remove(group_id)
            else:
                selected_groups.append(group_id)
            
            context.user_data[KEY_SELECTED_GROUPS] = selected_groups
            
            # Refresh the menu
            groups_info = self.db.get_all_groups_info()
            await self._show_group_selection_menu(update, context, groups_info)
            
            return STATE_SELECT_GROUPS
        
        return STATE_SELECT_GROUPS
    
    async def handle_csv_upload(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle CSV file upload and process birthday data.
        
        Returns:
            ConversationHandler.END
        """
        user = update.effective_user
        
        # Check if document is attached
        if not update.message.document:
            await update.message.reply_text(
                "⚠️ Per favore, carica un file CSV.\n"
                "Usa /birthday per ricominciare o /cancel per annullare."
            )
            return STATE_UPLOAD_CSV
        
        document = update.message.document
        
        # Check if it's a CSV file
        if not document.file_name.endswith('.csv'):
            await update.message.reply_text(
                "⚠️ Il file deve essere un CSV.\n"
                "Carica un file con estensione .csv"
            )
            return STATE_UPLOAD_CSV
        
        # Download the file
        try:
            file = await context.bot.get_file(document.file_id)
            file_bytes = await file.download_as_bytearray()
            
            # Process CSV
            selected_groups = context.user_data.get(KEY_SELECTED_GROUPS, [])
            result = await self._process_csv(file_bytes, selected_groups)
            
            # Send results
            await update.message.reply_text(
                result['message'],
                parse_mode='Markdown'
            )
            
            # Clean up user data
            context.user_data.pop(KEY_SELECTED_GROUPS, None)
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error processing CSV: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Errore durante l'elaborazione del file:\n{str(e)}\n\n"
                "Verifica il formato del CSV e riprova."
            )
            return STATE_UPLOAD_CSV
    
    async def _process_csv(
        self,
        file_bytes: bytearray,
        group_ids: List[int]
    ) -> Dict:
        """
        Process CSV file and import birthdays.
        
        Args:
            file_bytes: CSV file content
            group_ids: List of group IDs where to announce birthdays
            
        Returns:
            Dictionary with processing results
        """
        # Decode file (handle BOM if present). Some CSVs may contain an explicit
        # U+FEFF character followed by an UTF-8-sig BOM sequence (tests may do
        # this), so strip any leading BOM character after decoding.
        text = file_bytes.decode('utf-8-sig')
        if text and text[0] == '\ufeff':
            text = text.lstrip('\ufeff')

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(text))
        
        success_count = 0
        error_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is 1)
            try:
                # Extract fields
                first_name = row.get('NOME', '').strip()
                # 'COGNOME' is optional; if missing or unknown keep empty string
                last_name = row.get('COGNOME', '')
                if last_name is None:
                    last_name = ''
                last_name = last_name.strip()
                birth_date_raw = row.get('DATA DI NASCITA (dd-MM-yyyy)', '').strip()
                comment = row.get('COMMENTO', '').strip()
                
                # Validate required fields
                if not first_name:
                    raise ValueError("Nome mancante")

                # birth_date is mandatory, surname is optional
                if not birth_date_raw:
                    raise ValueError("Data di nascita mancante")
                
                # Parse and validate birth date
                birth_date = self._parse_birth_date(birth_date_raw)
                
                # Add to database
                self.db.add_birthday(
                    first_name=first_name,
                    last_name=last_name,
                    birth_date=birth_date,
                    group_ids=group_ids,
                    comment=comment
                )
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Riga {row_num}: {str(e)}")
                logger.warning(f"Error processing row {row_num}: {e}")
        
        # Build result message
        message = f"✅ *Importazione completata*\n\n"
        message += f"✔️ Importati con successo: *{success_count}*\n"
        
        if error_count > 0:
            message += f"❌ Errori: *{error_count}*\n\n"
            if errors:
                message += "*Dettagli errori:*\n"
                # Show first 10 errors
                for error in errors[:10]:
                    message += f"• {error}\n"
                if len(errors) > 10:
                    message += f"... e altri {len(errors) - 10} errori\n"
        
        return {
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors,
            'message': message
        }
    
    def _parse_birth_date(self, date_str: str) -> str:
        """
        Parse and validate birth date string.
        Accepts formats: 'dd-MM' or 'dd-MM-yyyy'
        Returns normalized format: 'MM/dd' or 'yyyy/MM/dd'
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Normalized date string
            
        Raises:
            ValueError: If date format is invalid
        """
        # Remove whitespace
        date_str = date_str.strip()
        
        # Try dd-MM-yyyy format
        match = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', date_str)
        if match:
            day, month, year = match.groups()
            day = int(day)
            month = int(month)
            year = int(year)
            
            # Validate
            if not (1 <= day <= 31):
                raise ValueError(f"Giorno non valido: {day}")
            if not (1 <= month <= 12):
                raise ValueError(f"Mese non valido: {month}")
            if not (1900 <= year <= 2100):
                raise ValueError(f"Anno non valido: {year}")
            
            # Return in yyyy/MM/dd format
            return f"{year}/{month:02d}/{day:02d}"
        
        # Try dd-MM format (without year)
        match = re.match(r'^(\d{1,2})-(\d{1,2})$', date_str)
        if match:
            day, month = match.groups()
            day = int(day)
            month = int(month)
            
            # Validate
            if not (1 <= day <= 31):
                raise ValueError(f"Giorno non valido: {day}")
            if not (1 <= month <= 12):
                raise ValueError(f"Mese non valido: {month}")
            
            # Return in MM/dd format
            return f"{month:02d}/{day:02d}"
        
        raise ValueError(f"Formato data non valido: '{date_str}'. Usa 'dd-MM' o 'dd-MM-yyyy'")
    
    async def cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Cancel the birthday entry process.
        
        Returns:
            ConversationHandler.END
        """
        context.user_data.pop(KEY_SELECTED_GROUPS, None)
        await update.message.reply_text("❌ Operazione annullata.")
        return ConversationHandler.END


def create_birthday_conversation_handler(db: Database) -> ConversationHandler:
    """
    Create the conversation handler for birthday management.
    
    Args:
        db: Database instance
        
    Returns:
        ConversationHandler for birthday management
    """
    manager = BirthdayManager(db)
    
    return ConversationHandler(
        entry_points=[
            CommandHandler('birthday', manager.start_birthday_entry)
        ],
        states={
            STATE_SELECT_GROUPS: [
                CallbackQueryHandler(manager.handle_group_selection)
            ],
            STATE_UPLOAD_CSV: [
                MessageHandler(
                    filters.Document.ALL,
                    manager.handle_csv_upload
                )
            ]
        },
        fallbacks=[
            CommandHandler('cancel', manager.cancel)
        ],
        name='birthday_entry',
        persistent=False
    )
