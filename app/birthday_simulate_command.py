"""
Birthday Simulation Command
============================

This module provides a command to simulate a birthday message for testing.
Uses telegram-menu-builder for interactive group and person selection.
"""

import logging
import random
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    ConversationHandler
)

from database import Database
from birthday_scheduler import BirthdayScheduler
from utils import is_admin

logger = logging.getLogger(__name__)

# Conversation states
STATE_SELECT_GROUP = 1
STATE_SELECT_PERSON = 2


class BirthdaySimulateCommand:
    """Handles birthday simulation for testing."""
    
    def __init__(self, db: Database):
        """
        Initialize the simulate command handler.
        
        Args:
            db: Database instance
        """
        self.db = db
    
    async def start_simulate(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Start birthday simulation flow.
        Usage: /simulatebirthday
        
        Returns:
            STATE_SELECT_GROUP
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Check if in private chat and user is admin
        if chat.type != 'private' or not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo da amministratori in chat privata."
            )
            return ConversationHandler.END
        
        # Get all groups
        groups = self.db.get_all_groups_info()
        
        if not groups:
            await update.message.reply_text(
                "❌ Nessun gruppo configurato nel database."
            )
            return ConversationHandler.END
        
        # Show group selection menu
        await self._show_group_selection(update, context, groups)
        return STATE_SELECT_GROUP
    
    async def _show_group_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        groups: list
    ):
        """
        Display group selection menu.
        
        Args:
            update: Update object
            context: Callback context
            groups: List of group info dictionaries
        """
        keyboard = []
        
        for group in groups[:10]:  # Limit to 10 groups
            group_id = group['group_id']
            group_name = group['group_name'] or f"Group {group_id}"
            
            keyboard.append([InlineKeyboardButton(
                f"📢 {group_name}",
                callback_data=f"sim_group_{group_id}"
            )])
        
        keyboard.append([InlineKeyboardButton(
            "❌ Annulla",
            callback_data="sim_cancel"
        )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "🎭 *Simulazione Compleanno*\n\n"
            "Seleziona il gruppo dove simulare l'invio del messaggio di compleanno:"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_group_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle group selection callback.
        
        Returns:
            STATE_SELECT_PERSON or ConversationHandler.END
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "sim_cancel":
            await query.edit_message_text("❌ Simulazione annullata.")
            return ConversationHandler.END
        
        # Extract group ID
        group_id = int(query.data.replace("sim_group_", ""))
        context.user_data['sim_group_id'] = group_id
        
        # Get birthdays for this group
        birthdays = self.db.get_birthdays_by_group(group_id)
        
        if not birthdays:
            await query.edit_message_text(
                f"❌ Nessun compleanno configurato per il gruppo selezionato."
            )
            return ConversationHandler.END
        
        # Show person selection menu (or random option)
        await self._show_person_selection(query, context, birthdays, group_id)
        return STATE_SELECT_PERSON
    
    async def _show_person_selection(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        birthdays: list,
        group_id: int
    ):
        """
        Display person selection menu.
        
        Args:
            query: Callback query
            context: Callback context
            birthdays: List of birthday dictionaries
            group_id: Group ID
        """
        keyboard = []
        
        # Add random option at the top
        keyboard.append([InlineKeyboardButton(
            "🎲 Persona Casuale",
            callback_data=f"sim_person_random"
        )])
        
        # Add specific people (limit to 8 to fit with random + cancel)
        for birthday in birthdays[:8]:
            full_name = f"{birthday['first_name']} {birthday['last_name']}".strip()
            keyboard.append([InlineKeyboardButton(
                f"🎂 {full_name}",
                callback_data=f"sim_person_{birthday['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton(
            "❌ Annulla",
            callback_data="sim_cancel"
        )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "🎭 *Simulazione Compleanno*\n\n"
            f"Gruppo selezionato: {group_id}\n"
            f"Compleanni disponibili: {len(birthdays)}\n\n"
            "Seleziona la persona per cui simulare il compleanno:"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_person_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle person selection and execute simulation.
        
        Returns:
            ConversationHandler.END
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "sim_cancel":
            await query.edit_message_text("❌ Simulazione annullata.")
            return ConversationHandler.END
        
        group_id = context.user_data.get('sim_group_id')
        if not group_id:
            await query.edit_message_text("❌ Errore: gruppo non trovato.")
            return ConversationHandler.END
        
        # Get birthdays for this group
        birthdays = self.db.get_birthdays_by_group(group_id)
        
        # Select person (random or specific)
        if query.data == "sim_person_random":
            birthday = random.choice(birthdays)
            selection_method = "casuale"
        else:
            birthday_id = int(query.data.replace("sim_person_", ""))
            birthday = self.db.get_birthday_by_id(birthday_id)
            selection_method = "specifica"
            
            if not birthday:
                await query.edit_message_text("❌ Errore: compleanno non trovato.")
                return ConversationHandler.END
        
        full_name = f"{birthday['first_name']} {birthday['last_name']}".strip()
        
        # Show confirmation message
        await query.edit_message_text(
            f"🎭 *Simulazione in corso...*\n\n"
            f"👤 Persona: *{full_name}*\n"
            f"📢 Gruppo ID: `{group_id}`\n"
            f"🎲 Selezione: {selection_method}\n\n"
            f"⏳ Sto generando e inviando il messaggio...",
            parse_mode='Markdown'
        )
        
        # Execute simulation (send actual birthday message)
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            
            # Get group settings
            settings = self.db.get_group_birthday_settings(group_id)
            if not settings:
                await query.edit_message_text(
                    f"❌ Errore: impostazioni gruppo non trovate.\n"
                    f"Configura il gruppo con /birthdaysettings prima di simulare."
                )
                return ConversationHandler.END
            
            # Create scheduler instance
            scheduler = BirthdayScheduler(self.db, context.bot)
            
            # Get current year
            timezone = settings['timezone']
            current_year = datetime.now(ZoneInfo(timezone)).year
            
            # Send birthday message
            success = await scheduler._send_birthday_message(
                birthday=birthday,
                group_id=group_id,
                settings=settings,
                birthday_year=current_year
            )
            
            if success:
                await query.edit_message_text(
                    f"✅ *Simulazione Completata!*\n\n"
                    f"👤 Persona: *{full_name}*\n"
                    f"📢 Gruppo ID: `{group_id}`\n"
                    f"📅 Data nascita: {birthday['birth_date']}\n\n"
                    f"🎉 Messaggio di compleanno inviato con successo al gruppo!",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    f"❌ *Simulazione Fallita*\n\n"
                    f"👤 Persona: *{full_name}*\n"
                    f"📢 Gruppo ID: `{group_id}`\n\n"
                    f"Il messaggio non è stato inviato. Controlla i log per maggiori dettagli.",
                    parse_mode='Markdown'
                )
        
        except Exception as e:
            logger.error(f"Error in birthday simulation: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ *Errore durante la simulazione*\n\n"
                f"Errore: `{str(e)}`",
                parse_mode='Markdown'
            )
        
        # Clean up
        context.user_data.pop('sim_group_id', None)
        return ConversationHandler.END
    
    async def cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel simulation."""
        context.user_data.pop('sim_group_id', None)
        await update.message.reply_text("❌ Simulazione annullata.")
        return ConversationHandler.END


def create_simulate_conversation_handler(db: Database) -> ConversationHandler:
    """
    Create the conversation handler for birthday simulation.
    
    Args:
        db: Database instance
        
    Returns:
        ConversationHandler for birthday simulation
    """
    simulator = BirthdaySimulateCommand(db)
    
    return ConversationHandler(
        entry_points=[
            CommandHandler('simulatebirthday', simulator.start_simulate)
        ],
        states={
            STATE_SELECT_GROUP: [
                CallbackQueryHandler(
                    simulator.handle_group_selection,
                    pattern='^sim_(group_|cancel)'
                )
            ],
            STATE_SELECT_PERSON: [
                CallbackQueryHandler(
                    simulator.handle_person_selection,
                    pattern='^sim_(person_|cancel)'
                )
            ]
        },
        fallbacks=[
            CommandHandler('cancel', simulator.cancel)
        ],
        name='birthday_simulation',
        persistent=False
    )
