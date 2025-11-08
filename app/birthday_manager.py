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

from database import Database
from utils import is_admin

# Enable logging
logger = logging.getLogger(__name__)

# Conversation states
STATE_SELECT_GROUPS = 1
STATE_UPLOAD_CSV = 2
STATE_LIST_BIRTHDAYS = 3
STATE_EDIT_SELECT = 4
STATE_EDIT_FIELD = 5
STATE_LINK_SELECT = 6
STATE_LINK_FORWARD = 7

# User data keys
KEY_SELECTED_GROUPS = 'birthday_selected_groups'
KEY_CURRENT_PAGE = 'birthday_current_page'
KEY_SELECTED_BIRTHDAY_ID = 'birthday_selected_id'
KEY_EDIT_FIELD = 'birthday_edit_field'


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
        context.user_data.pop(KEY_CURRENT_PAGE, None)
        context.user_data.pop(KEY_SELECTED_BIRTHDAY_ID, None)
        context.user_data.pop(KEY_EDIT_FIELD, None)
        await update.message.reply_text("❌ Operazione annullata.")
        return ConversationHandler.END
    
    # ==================== CRUD Operations ====================
    
    async def list_birthdays(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        List all birthdays with pagination.
        
        Returns:
            ConversationHandler.END or STATE_LIST_BIRTHDAYS
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Check if in private chat and user is admin
        if chat.type != 'private' or not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo da amministratori in chat privata."
            )
            return ConversationHandler.END
        
        # Get all birthdays
        birthdays = self.db.get_all_birthdays()
        
        if not birthdays:
            await update.message.reply_text("📋 Non ci sono compleanni registrati.")
            return ConversationHandler.END
        
        # Initialize page
        page = context.user_data.get(KEY_CURRENT_PAGE, 0)
        
        # Show paginated list
        await self._show_birthdays_page(update, context, birthdays, page)
        
        return ConversationHandler.END
    
    async def _show_birthdays_page(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        birthdays: List[Dict],
        page: int = 0
    ):
        """
        Display a page of birthdays (10 per page).
        
        Args:
            update: Update object
            context: Callback context
            birthdays: List of birthday dictionaries
            page: Current page number
        """
        items_per_page = 10
        total_pages = (len(birthdays) + items_per_page - 1) // items_per_page
        
        # Ensure page is valid
        page = max(0, min(page, total_pages - 1))
        
        # Store birthdays list and current page in context for pagination
        context.user_data['birthday_list'] = birthdays
        context.user_data[KEY_CURRENT_PAGE] = page
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_birthdays = birthdays[start_idx:end_idx]
        
        # Build message
        message = f"📋 *Lista Compleanni* (Pagina {page + 1}/{total_pages})\n\n"
        
        for b in page_birthdays:
            full_name = f"{b['first_name']} {b['last_name']}".strip()
            telegram_info = f" 👤(ID: {b['telegram_user_id']})" if b.get('telegram_user_id') else ""
            groups_count = len(b.get('group_ids', []))
            
            message += f"🎂 *{full_name}*{telegram_info}\n"
            message += f"   📅 {b['birth_date']}\n"
            if b.get('comment'):
                message += f"   💬 {b['comment']}\n"
            message += f"   📢 {groups_count} gruppo/i\n"
            message += f"   🆔 ID: `{b['id']}`\n\n"
        
        message += "\nUsa /editbirthday <ID> per modificare\n"
        message += "Usa /deletebirthday <ID> per eliminare\n"
        message += "Usa /linkbirthday <ID> per associare ID Telegram"
        
        # Build keyboard for pagination
        keyboard = []
        nav_row = []
        
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Precedente", callback_data=f"bday_page_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Successivo ➡️", callback_data=f"bday_page_{page+1}"))
        
        if nav_row:
            keyboard.append(nav_row)
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        logger.debug(f"Showing birthdays page {page + 1}/{total_pages}, total birthdays: {len(birthdays)}")
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    
    async def handle_page_navigation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle pagination callback for birthday list.
        
        This is called when user clicks on Precedente/Successivo buttons.
        """
        query = update.callback_query
        await query.answer()
        
        # Extract page number from callback_data
        try:
            page = int(query.data.replace("bday_page_", ""))
        except ValueError:
            logger.error(f"Invalid page callback data: {query.data}")
            await query.edit_message_text("❌ Errore di paginazione.")
            return
        
        # Get stored birthday list
        birthdays = context.user_data.get('birthday_list', [])
        
        if not birthdays:
            logger.warning("Birthday list not found in context, fetching from DB")
            birthdays = self.db.get_all_birthdays()
        
        logger.debug(f"Page navigation: going to page {page + 1}, total birthdays: {len(birthdays)}")
        
        # Show the requested page
        await self._show_birthdays_page(update, context, birthdays, page)
    
    async def delete_birthday_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Delete a birthday entry (requires confirmation).
        Usage: /deletebirthday <ID>
        
        Returns:
            ConversationHandler.END
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Check if in private chat and user is admin
        if chat.type != 'private' or not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo da amministratori in chat privata."
            )
            return ConversationHandler.END
        
        # Parse birthday ID from command
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "❌ Utilizzo: /deletebirthday <ID>\n"
                "Usa /listbirthdays per vedere gli ID disponibili."
            )
            return ConversationHandler.END
        
        try:
            birthday_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ ID non valido. Deve essere un numero.")
            return ConversationHandler.END
        
        # Get birthday
        birthday = self.db.get_birthday_by_id(birthday_id)
        
        if not birthday:
            await update.message.reply_text(f"❌ Compleanno con ID {birthday_id} non trovato.")
            return ConversationHandler.END
        
        # Show confirmation
        full_name = f"{birthday['first_name']} {birthday['last_name']}".strip()
        keyboard = [
            [
                InlineKeyboardButton("✅ Conferma", callback_data=f"bday_delete_confirm_{birthday_id}"),
                InlineKeyboardButton("❌ Annulla", callback_data="bday_delete_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Sei sicuro di voler eliminare il compleanno di *{full_name}* ({birthday['birth_date']})?\n\n"
            f"Questa azione non può essere annullata.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END
    
    async def handle_delete_confirmation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle delete confirmation callback.
        
        Returns:
            ConversationHandler.END
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "bday_delete_cancel":
            await query.edit_message_text("❌ Eliminazione annullata.")
            return ConversationHandler.END
        
        # Extract birthday ID
        birthday_id = int(query.data.replace("bday_delete_confirm_", ""))
        
        # Delete birthday
        success = self.db.delete_birthday(birthday_id)
        
        if success:
            await query.edit_message_text(
                f"✅ Compleanno ID {birthday_id} eliminato con successo."
            )
        else:
            await query.edit_message_text(
                f"❌ Errore durante l'eliminazione del compleanno ID {birthday_id}."
            )
        
        return ConversationHandler.END
    
    async def edit_birthday_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Edit a birthday entry.
        Usage: /editbirthday <ID>
        
        Returns:
            STATE_EDIT_FIELD
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Check if in private chat and user is admin
        if chat.type != 'private' or not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo da amministratori in chat privata."
            )
            return ConversationHandler.END
        
        # Parse birthday ID from command
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "❌ Utilizzo: /editbirthday <ID>\n"
                "Usa /listbirthdays per vedere gli ID disponibili."
            )
            return ConversationHandler.END
        
        try:
            birthday_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ ID non valido. Deve essere un numero.")
            return ConversationHandler.END
        
        # Get birthday
        birthday = self.db.get_birthday_by_id(birthday_id)
        
        if not birthday:
            await update.message.reply_text(f"❌ Compleanno con ID {birthday_id} non trovato.")
            return ConversationHandler.END
        
        # Store birthday ID
        context.user_data[KEY_SELECTED_BIRTHDAY_ID] = birthday_id
        
        # Show edit menu
        await self._show_edit_menu(update, context, birthday)
        
        return STATE_EDIT_FIELD
    
    async def _show_edit_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        birthday: Dict
    ):
        """
        Display edit menu with inline keyboard.
        
        Args:
            update: Update object
            context: Callback context
            birthday: Birthday dictionary
        """
        full_name = f"{birthday['first_name']} {birthday['last_name']}".strip()
        telegram_info = f" 👤(ID: {birthday['telegram_user_id']})" if birthday.get('telegram_user_id') else " (non collegato)"
        
        message = (
            f"✏️ *Modifica Compleanno*\n\n"
            f"🎂 *Nome:* {full_name}{telegram_info}\n"
            f"📅 *Data:* {birthday['birth_date']}\n"
            f"💬 *Commento:* {birthday.get('comment') or 'Nessuno'}\n"
            f"📢 *Gruppi:* {len(birthday.get('group_ids', []))} gruppo/i\n\n"
            f"Seleziona il campo da modificare:"
        )
        
        keyboard = [
            [InlineKeyboardButton("👤 Nome", callback_data="bday_edit_first_name")],
            [InlineKeyboardButton("👥 Cognome", callback_data="bday_edit_last_name")],
            [InlineKeyboardButton("📅 Data", callback_data="bday_edit_birth_date")],
            [InlineKeyboardButton("💬 Commento", callback_data="bday_edit_comment")],
            [InlineKeyboardButton("📢 Gruppi", callback_data="bday_edit_groups")],
            [InlineKeyboardButton("❌ Annulla", callback_data="bday_edit_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    
    async def handle_edit_field_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle edit field selection callback.
        
        Returns:
            Next conversation state
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "bday_edit_cancel":
            context.user_data.pop(KEY_SELECTED_BIRTHDAY_ID, None)
            await query.edit_message_text("❌ Modifica annullata.")
            return ConversationHandler.END
        
        # Extract field name
        field = query.data.replace("bday_edit_", "")
        context.user_data[KEY_EDIT_FIELD] = field
        
        # Handle groups selection separately
        if field == "groups":
            birthday_id = context.user_data[KEY_SELECTED_BIRTHDAY_ID]
            birthday = self.db.get_birthday_by_id(birthday_id)
            context.user_data[KEY_SELECTED_GROUPS] = birthday.get('group_ids', [])
            
            groups_info = self.db.get_all_groups_info()
            await self._show_group_selection_menu_for_edit(query, context, groups_info)
            return STATE_EDIT_FIELD
        
        # Request new value
        field_names = {
            'first_name': 'nome',
            'last_name': 'cognome',
            'birth_date': 'data di nascita (formato dd-MM o dd-MM-yyyy)',
            'comment': 'commento'
        }
        
        await query.edit_message_text(
            f"✏️ Inserisci il nuovo valore per *{field_names.get(field, field)}*:",
            parse_mode='Markdown'
        )
        
        return STATE_EDIT_FIELD
    
    async def _show_group_selection_menu_for_edit(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        groups_info: List[Dict]
    ):
        """
        Display the group selection menu for editing.
        
        Args:
            query: Callback query
            context: Callback context
            groups_info: List of group information dictionaries
        """
        selected_groups = context.user_data.get(KEY_SELECTED_GROUPS, [])
        
        keyboard = []
        
        for group in groups_info[:5]:
            group_id = group['group_id']
            group_name = group['group_name'] or f"Group {group_id}"
            
            if group_id in selected_groups:
                label = f"✅ {group_name}"
            else:
                label = f"⬜ {group_name}"
            
            keyboard.append([InlineKeyboardButton(
                label,
                callback_data=f"bday_editgroup_{group_id}"
            )])
        
        keyboard.append([InlineKeyboardButton(
            "✔️ Conferma - Salva",
            callback_data="bday_editgroup_done"
        )])
        keyboard.append([InlineKeyboardButton(
            "❌ Annulla",
            callback_data="bday_edit_cancel"
        )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            "📢 *Seleziona i gruppi*\n\n"
            f"Gruppi selezionati: *{len(selected_groups)}*\n\n"
            "Clicca su un gruppo per selezionarlo/deselezionarlo.\n"
            "Quando hai finito, clicca su '✔️ Conferma - Salva'."
        )
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_edit_group_toggle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle group toggle in edit mode.
        
        Returns:
            STATE_EDIT_FIELD
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "bday_editgroup_done":
            # Save the new group IDs
            birthday_id = context.user_data[KEY_SELECTED_BIRTHDAY_ID]
            selected_groups = context.user_data.get(KEY_SELECTED_GROUPS, [])
            
            success = self.db.update_birthday(birthday_id, group_ids=selected_groups)
            
            if success:
                await query.edit_message_text(
                    f"✅ Gruppi aggiornati con successo! ({len(selected_groups)} gruppo/i)"
                )
            else:
                await query.edit_message_text("❌ Errore durante l'aggiornamento dei gruppi.")
            
            context.user_data.pop(KEY_SELECTED_BIRTHDAY_ID, None)
            context.user_data.pop(KEY_SELECTED_GROUPS, None)
            context.user_data.pop(KEY_EDIT_FIELD, None)
            return ConversationHandler.END
        
        # Toggle group
        group_id = int(query.data.replace("bday_editgroup_", ""))
        selected_groups = context.user_data.get(KEY_SELECTED_GROUPS, [])
        
        if group_id in selected_groups:
            selected_groups.remove(group_id)
        else:
            selected_groups.append(group_id)
        
        context.user_data[KEY_SELECTED_GROUPS] = selected_groups
        
        # Refresh menu
        groups_info = self.db.get_all_groups_info()
        await self._show_group_selection_menu_for_edit(query, context, groups_info)
        
        return STATE_EDIT_FIELD
    
    async def handle_edit_value(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle new value input for editing.
        
        Returns:
            ConversationHandler.END
        """
        new_value = update.message.text.strip()
        field = context.user_data.get(KEY_EDIT_FIELD)
        birthday_id = context.user_data.get(KEY_SELECTED_BIRTHDAY_ID)
        
        if not field or not birthday_id:
            await update.message.reply_text("❌ Errore: dati di sessione mancanti.")
            return ConversationHandler.END
        
        # Validate and update based on field
        try:
            if field == 'birth_date':
                # Parse and validate date
                new_value = self._parse_birth_date(new_value)
            
            # Update database
            kwargs = {field: new_value}
            success = self.db.update_birthday(birthday_id, **kwargs)
            
            if success:
                field_names = {
                    'first_name': 'Nome',
                    'last_name': 'Cognome',
                    'birth_date': 'Data di nascita',
                    'comment': 'Commento'
                }
                await update.message.reply_text(
                    f"✅ *{field_names.get(field, field)}* aggiornato con successo!",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Errore durante l'aggiornamento.")
            
        except ValueError as e:
            await update.message.reply_text(f"❌ Valore non valido: {str(e)}")
        
        # Clean up
        context.user_data.pop(KEY_SELECTED_BIRTHDAY_ID, None)
        context.user_data.pop(KEY_EDIT_FIELD, None)
        
        return ConversationHandler.END
    
    async def link_birthday_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Link a birthday to a Telegram user by forwarding a message.
        Usage: /linkbirthday <ID>
        
        Returns:
            STATE_LINK_FORWARD
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Check if in private chat and user is admin
        if chat.type != 'private' or not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo da amministratori in chat privata."
            )
            return ConversationHandler.END
        
        # Parse birthday ID from command
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "❌ Utilizzo: /linkbirthday <ID>\n"
                "Usa /listbirthdays per vedere gli ID disponibili."
            )
            return ConversationHandler.END
        
        try:
            birthday_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ ID non valido. Deve essere un numero.")
            return ConversationHandler.END
        
        # Get birthday
        birthday = self.db.get_birthday_by_id(birthday_id)
        
        if not birthday:
            await update.message.reply_text(f"❌ Compleanno con ID {birthday_id} non trovato.")
            return ConversationHandler.END
        
        # Store birthday ID
        context.user_data[KEY_SELECTED_BIRTHDAY_ID] = birthday_id
        
        full_name = f"{birthday['first_name']} {birthday['last_name']}".strip()
        
        await update.message.reply_text(
            f"🔗 *Collega Telegram ID*\n\n"
            f"Compleanno: *{full_name}* ({birthday['birth_date']})\n\n"
            f"Inoltra un messaggio dell'utente che vuoi collegare a questo compleanno.\n\n"
            f"Usa /cancel per annullare.",
            parse_mode='Markdown'
        )
        
        return STATE_LINK_FORWARD
    
    async def handle_link_forward(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle forwarded message to link Telegram user ID.
        
        Returns:
            ConversationHandler.END
        """
        birthday_id = context.user_data.get(KEY_SELECTED_BIRTHDAY_ID)
        
        if not birthday_id:
            await update.message.reply_text("❌ Errore: dati di sessione mancanti.")
            return ConversationHandler.END
        
        # Check if message is forwarded
        if not update.message.forward_from and not update.message.forward_sender_name:
            await update.message.reply_text(
                "⚠️ Devi inoltrare un messaggio dell'utente.\n"
                "Usa /cancel per annullare."
            )
            return STATE_LINK_FORWARD
        
        # Get user ID from forwarded message
        if update.message.forward_from:
            telegram_user_id = update.message.forward_from.id
            user_name = update.message.forward_from.first_name
            
            # Update birthday
            success = self.db.update_birthday_telegram_id(birthday_id, telegram_user_id)
            
            if success:
                birthday = self.db.get_birthday_by_id(birthday_id)
                full_name = f"{birthday['first_name']} {birthday['last_name']}".strip()
                
                await update.message.reply_text(
                    f"✅ *Collegamento riuscito!*\n\n"
                    f"Compleanno di *{full_name}* collegato a:\n"
                    f"👤 {user_name} (ID: `{telegram_user_id}`)",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Errore durante il collegamento.")
        else:
            await update.message.reply_text(
                "⚠️ Non è possibile recuperare l'ID utente.\n"
                "L'utente potrebbe aver nascosto il proprio account nelle impostazioni di privacy."
            )
        
        # Clean up
        context.user_data.pop(KEY_SELECTED_BIRTHDAY_ID, None)
        
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
            CommandHandler('birthday', manager.start_birthday_entry),
            CommandHandler('listbirthdays', manager.list_birthdays),
            CommandHandler('deletebirthday', manager.delete_birthday_command),
            CommandHandler('editbirthday', manager.edit_birthday_command),
            CommandHandler('linkbirthday', manager.link_birthday_command)
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
            ],
            STATE_EDIT_FIELD: [
                CallbackQueryHandler(
                    manager.handle_edit_field_selection,
                    pattern='^bday_edit_'
                ),
                CallbackQueryHandler(
                    manager.handle_edit_group_toggle,
                    pattern='^bday_editgroup_'
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manager.handle_edit_value
                )
            ],
            STATE_LINK_FORWARD: [
                MessageHandler(
                    filters.ALL,
                    manager.handle_link_forward
                )
            ]
        },
        fallbacks=[
            CommandHandler('cancel', manager.cancel),
            CallbackQueryHandler(
                manager.handle_delete_confirmation,
                pattern='^bday_delete_'
            ),
            CallbackQueryHandler(
                manager.handle_page_navigation,
                pattern='^bday_page_'
            )
        ],
        name='birthday_management',
        persistent=False
    )
