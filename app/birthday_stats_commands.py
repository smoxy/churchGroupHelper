"""
Birthday Statistics and Preview Commands
=========================================

This module provides commands for viewing:
- Upcoming birthdays
- Birthday message statistics (success/failure rates)
- Birthday preview/simulation for testing
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from database import Database
from utils import is_admin

logger = logging.getLogger(__name__)


class BirthdayStatsCommands:
    """Handles birthday statistics and preview commands."""
    
    def __init__(self, db: Database):
        """
        Initialize the stats commands handler.
        
        Args:
            db: Database instance
        """
        self.db = db
    
    async def upcoming_birthdays(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Show upcoming birthdays for the next 30 days.
        Usage: /upcomingbirthdays [days]
        
        Args:
            update: Update object
            context: Callback context
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Check if user is admin
        if not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo da amministratori."
            )
            return
        
        # Parse days parameter (default: 30)
        days = 30
        if context.args and len(context.args) == 1:
            try:
                days = int(context.args[0])
                if days < 1 or days > 365:
                    await update.message.reply_text("❌ Il numero di giorni deve essere tra 1 e 365.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Parametro non valido. Usa: /upcomingbirthdays [giorni]")
                return
        
        # Get all birthdays
        all_birthdays = self.db.get_all_birthdays()
        
        if not all_birthdays:
            await update.message.reply_text("📋 Non ci sono compleanni registrati.")
            return
        
        # Calculate upcoming birthdays
        today = datetime.now()
        upcoming = []
        
        for birthday in all_birthdays:
            birth_date = birthday['birth_date']
            
            # Parse birth_date (MM/dd or yyyy/MM/dd)
            parts = birth_date.split('/')
            if len(parts) == 2:
                month, day = int(parts[0]), int(parts[1])
            elif len(parts) == 3:
                if len(parts[0]) == 4:
                    month, day = int(parts[1]), int(parts[2])
                else:
                    month, day = int(parts[0]), int(parts[1])
            else:
                continue
            
            # Create birthday date for this year and next year
            try:
                this_year_birthday = datetime(today.year, month, day)
                next_year_birthday = datetime(today.year + 1, month, day)
            except ValueError:
                # Invalid date (e.g., Feb 29 in non-leap year)
                continue
            
            # Calculate days until birthday
            if this_year_birthday >= today:
                days_until = (this_year_birthday - today).days
                birthday_date = this_year_birthday
            else:
                days_until = (next_year_birthday - today).days
                birthday_date = next_year_birthday
            
            if days_until <= days:
                upcoming.append({
                    'birthday': birthday,
                    'days_until': days_until,
                    'date': birthday_date
                })
        
        # Sort by days until birthday
        upcoming.sort(key=lambda x: x['days_until'])
        
        if not upcoming:
            await update.message.reply_text(f"📅 Nessun compleanno nei prossimi {days} giorni.")
            return
        
        # Build message
        message = f"🎂 *Prossimi Compleanni* (prossimi {days} giorni)\n\n"
        
        for item in upcoming:
            b = item['birthday']
            days_until = item['days_until']
            birthday_date = item['date']
            
            full_name = f"{b['first_name']} {b['last_name']}".strip()
            date_str = birthday_date.strftime('%d/%m/%Y')
            
            if days_until == 0:
                days_text = "🎉 *OGGI!*"
            elif days_until == 1:
                days_text = "🎈 Domani"
            else:
                days_text = f"📅 Tra {days_until} giorni"
            
            groups_count = len(b.get('group_ids', []))
            telegram_info = " 👤" if b.get('telegram_user_id') else ""
            
            message += f"{days_text}\n"
            message += f"   *{full_name}*{telegram_info}\n"
            message += f"   📆 {date_str}\n"
            message += f"   📢 {groups_count} gruppo/i\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def birthday_stats(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Show birthday message statistics (success/failure rates).
        Usage: /birthdaystats [days]
        
        Args:
            update: Update object
            context: Callback context
        """
        user = update.effective_user
        
        # Check if user is admin
        if not is_admin(user.id):
            await update.message.reply_text(
                "⚠️ Questo comando può essere utilizzato solo da amministratori."
            )
            return
        
        # Parse days parameter (default: 30)
        days = 30
        if context.args and len(context.args) == 1:
            try:
                days = int(context.args[0])
                if days < 1 or days > 365:
                    await update.message.reply_text("❌ Il numero di giorni deve essere tra 1 e 365.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Parametro non valido. Usa: /birthdaystats [giorni]")
                return
        
        # Get statistics from database
        stats = self.db.get_birthday_messages_stats(days=days)
        
        # Build message
        message = f"📊 *Statistiche Messaggi di Compleanno* (ultimi {days} giorni)\n\n"
        
        message += f"📨 *Totale Messaggi:* {stats['total']}\n"
        message += f"✅ *Inviati:* {stats['sent']} ({stats['sent_percentage']:.1f}%)\n"
        message += f"❌ *Falliti:* {stats['failed']} ({stats['failed_percentage']:.1f}%)\n"
        message += f"🔄 *Retry Effettuati:* {stats['retries']}\n\n"
        
        if stats['failed'] > 0:
            message += "⚠️ *Errori Recenti:*\n"
            for error in stats.get('recent_errors', [])[:5]:
                message += f"   • {error.get('error_message', 'Unknown')[:50]}...\n"
            message += "\n"
        
        message += f"📅 *Periodo:* {stats['date_from']} - {stats['date_to']}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')


def register_birthday_stats_commands(application, db: Database) -> None:
    """
    Register birthday statistics and preview commands.
    
    Args:
        application: Telegram Application instance
        db: Database instance
    """
    stats_handler = BirthdayStatsCommands(db)
    
    # Register command handlers
    application.add_handler(CommandHandler('upcomingbirthdays', stats_handler.upcoming_birthdays))
    application.add_handler(CommandHandler('birthdaystats', stats_handler.birthday_stats))
    
    logger.info("Birthday statistics commands registered")
