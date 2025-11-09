"""
Birthday Scheduler Module
=========================

This module manages the daily scheduler for birthday notifications.
Uses APScheduler (included in python-telegram-bot[job-queue]) to:
- Run daily checks at configured time per group (default 09:00)
- Handle timezone conversion per group
- Check for birthdays today
- Generate and send birthday messages
- Track sent messages for idempotency
- Implement retry logic for failed sends

The scheduler is timezone-aware and handles edge cases like:
- February 29 birthdays in non-leap years (celebrated on Feb 28)
- Multiple birthdays on the same day (combined message)
- Multiple groups with different timezones
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from telegram import Bot
from telegram.error import TelegramError

from database import Database
from biblical_text_selector import BiblicalTextSelector
from birthday_message_generator import BirthdayMessageGenerator
from utils import ADMINS

logger = logging.getLogger(__name__)


class BirthdayScheduler:
    """
    Manages daily birthday checks and message sending.
    
    Integrates with APScheduler (via python-telegram-bot job_queue)
    to schedule daily checks at configured times per group.
    """
    
    def __init__(self, db: Database, bot: Bot):
        """
        Initialize the birthday scheduler.
        
        Args:
            db: Database instance
            bot: Telegram Bot instance
        """
        self.db = db
        self.bot = bot
        self.text_selector = BiblicalTextSelector(db)
        self.message_generator = BirthdayMessageGenerator()
    
    async def _notify_admins_about_missing_config(
        self,
        group_id: int,
        birthday_name: str,
        issue_type: str = "biblical_texts"
    ) -> None:
        """
        Send private notification to admins who are members of the group.
        
        Args:
            group_id: The group where the issue occurred
            birthday_name: Name of the person whose birthday couldn't be sent properly
            issue_type: Type of configuration issue
        """
        logger.debug(f"[BIRTHDAY_SCHEDULER] Notifying admins about {issue_type} issue in group {group_id}")
        
        try:
            # Get group info for the notification
            try:
                chat = await self.bot.get_chat(group_id)
                group_name = chat.title if hasattr(chat, 'title') else f"Group {group_id}"
            except Exception as e:
                logger.warning(f"[BIRTHDAY_SCHEDULER] Could not get group name: {e}")
                group_name = f"Group {group_id}"
            
            # Check which admins are in this group
            notified_count = 0
            for admin_id in ADMINS:
                try:
                    # Check if admin is a member of the group
                    member = await self.bot.get_chat_member(group_id, admin_id)
                    
                    # Only notify if they're still a member (not kicked/left)
                    if member.status in ['creator', 'administrator', 'member']:
                        # Prepare notification message
                        if issue_type == "biblical_texts":
                            message = (
                                f"⚠️ *Configurazione Mancante - Testi Biblici*\n\n"
                                f"📍 Gruppo: _{group_name}_\n"
                                f"🎂 Compleanno: *{birthday_name}*\n\n"
                                f"❌ Il gruppo non ha testi biblici configurati!\n\n"
                                f"Ho inviato un messaggio di promemoria semplificato, "
                                f"ma per messaggi più completi e personalizzati è necessario:\n\n"
                                f"✅ *Azione Richiesta:*\n"
                                f"Importa i testi biblici per questo gruppo usando i comandi admin del bot.\n\n"
                                f"_Questo messaggio è stato inviato solo agli amministratori "
                                f"che sono membri di questo gruppo._"
                            )
                        else:
                            message = (
                                f"⚠️ *Errore Configurazione*\n\n"
                                f"📍 Gruppo: _{group_name}_\n"
                                f"🎂 Compleanno: *{birthday_name}*\n\n"
                                f"Si è verificato un problema di configurazione.\n"
                                f"Controlla le impostazioni del gruppo."
                            )
                        
                        # Send private message to admin
                        await self.bot.send_message(
                            chat_id=admin_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        notified_count += 1
                        logger.info(f"[BIRTHDAY_SCHEDULER] ✅ Notified admin {admin_id} about {issue_type} issue")
                    else:
                        logger.debug(f"[BIRTHDAY_SCHEDULER] Admin {admin_id} is not a member of group {group_id} (status: {member.status})")
                
                except TelegramError as e:
                    # Admin might not be in the group or have blocked the bot
                    logger.debug(f"[BIRTHDAY_SCHEDULER] Could not notify admin {admin_id}: {e}")
                except Exception as e:
                    logger.warning(f"[BIRTHDAY_SCHEDULER] Error checking admin {admin_id} membership: {e}")
            
            if notified_count > 0:
                logger.info(f"[BIRTHDAY_SCHEDULER] ✅ Notified {notified_count} admin(s) about {issue_type} issue in group {group_id}")
            else:
                logger.warning(f"[BIRTHDAY_SCHEDULER] ⚠️ No admins were notified (none are members of group {group_id} or bot is blocked)")
        
        except Exception as e:
            logger.error(f"[BIRTHDAY_SCHEDULER] Error in _notify_admins_about_missing_config: {e}", exc_info=True)
    
    def _generate_fallback_message(
        self,
        birthday: Dict[str, Any],
        use_ai: bool = True
    ) -> Optional[str]:
        """
        Generate a fallback birthday message when no biblical text is available.
        Uses AI if enabled to create an organic message that incorporates the comment field.
        
        Args:
            birthday: Birthday dictionary with person's info
            use_ai: Whether to use AI for generation
            
        Returns:
            Generated message string or None if failed
        """
        name = f"{birthday['first_name']} {birthday['last_name']}"
        comment = birthday.get('comment', '')
        
        if not use_ai:
            # Simple template fallback
            comment_part = f"\n\n💡 {comment}" if comment else ""
            message = f"🎉 Buon compleanno {name}! 🎂\n\n"
            message += f"Oggi festeggiamo il compleanno di {name}!\n"
            message += f"Ricordiamoci di fargli/farle gli auguri! 🎈{comment_part}"
            return message
        
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Create prompt for fallback message
            system_message = SystemMessage(content="""Sei un assistente che genera messaggi di promemoria per compleanni in una comunità cristiana.

Il tuo compito è creare un breve messaggio di promemoria caloroso che:
- Ricorda al gruppo di fare gli auguri alla persona
- Se presente una nota/commento, usala in modo ORGANICO per spiegare come raggiungere la persona con gli auguri
- Il commento spesso indica relazioni familiari o come contattare la persona (es. "nipote di Giovanni" o "tramite sua sorella Maria")
- NON fare note tecniche agli amministratori
- Mantieni un tono caloroso e positivo
- Massimo 150 parole
- In italiano""")
            
            human_content = f"""Genera un messaggio di promemoria per il compleanno di:
Nome: {name}"""
            
            if comment:
                human_content += f"\nNota importante da incorporare organicamente: {comment}"
                human_content += "\n\n(Usa questa nota per spiegare come il gruppo può fare gli auguri a questa persona, rendendolo naturale nel messaggio)"
            
            human_content += "\n\nMessaggio:"
            
            messages = [system_message, HumanMessage(content=human_content)]
            
            # Use the message generator's LLM
            response = self.message_generator.llm.invoke(messages)
            message = response.content.strip()
            
            # Validate message
            if message and 50 < len(message) < 1000:
                logger.info(f"[BIRTHDAY_SCHEDULER] Generated AI fallback message ({len(message)} chars)")
                return message
            else:
                logger.warning(f"[BIRTHDAY_SCHEDULER] AI fallback message validation failed (length: {len(message)})")
                return None
                
        except Exception as e:
            logger.error(f"[BIRTHDAY_SCHEDULER] Error generating AI fallback message: {e}", exc_info=True)
            return None
    
    def _parse_birth_date(self, birth_date: str) -> tuple[int, int]:
        """
        Parse birth_date string to get month and day.
        
        Args:
            birth_date: Birth date in format 'MM/dd' or 'yyyy/MM/dd'
            
        Returns:
            Tuple of (month, day)
        """
        parts = birth_date.split('/')
        
        if len(parts) == 2:
            # Format: MM/dd
            month, day = int(parts[0]), int(parts[1])
        elif len(parts) == 3:
            # Format: yyyy/MM/dd or MM/dd/yyyy
            if len(parts[0]) == 4:
                # yyyy/MM/dd
                month, day = int(parts[1]), int(parts[2])
            else:
                # MM/dd/yyyy
                month, day = int(parts[0]), int(parts[1])
        else:
            raise ValueError(f"Invalid birth_date format: {birth_date}")
        
        return month, day
    
    def _is_birthday_today(
        self,
        birth_date: str,
        timezone: str = 'Europe/Rome'
    ) -> bool:
        """
        Check if a birth date matches today in the given timezone.
        
        Handles February 29 edge case: in non-leap years, Feb 29 birthdays
        are celebrated on Feb 28 (as per user requirement).
        
        Args:
            birth_date: Birth date in format 'MM/dd' or 'yyyy/MM/dd'
            timezone: IANA timezone string
            
        Returns:
            True if birthday is today, False otherwise
        """
        try:
            month, day = self._parse_birth_date(birth_date)
        except Exception as e:
            logger.error(f"Error parsing birth_date {birth_date}: {e}")
            return False
        
        # Get today's date in the group's timezone
        tz = ZoneInfo(timezone)
        today = datetime.now(tz)
        today_month = today.month
        today_day = today.day
        
        # Direct match
        if month == today_month and day == today_day:
            return True
        
        # February 29 edge case
        if month == 2 and day == 29:
            # Check if today is Feb 28 in a non-leap year
            is_leap_year = (today.year % 4 == 0 and today.year % 100 != 0) or (today.year % 400 == 0)
            if not is_leap_year and today_month == 2 and today_day == 28:
                logger.info(f"Celebrating Feb 29 birthday on Feb 28 (non-leap year {today.year})")
                return True
        
        return False
    
    def get_birthdays_today(
        self,
        group_id: int,
        timezone: str = 'Europe/Rome'
    ) -> List[Dict[str, Any]]:
        """
        Get all birthdays for today in a specific group.
        
        Args:
            group_id: Telegram group ID
            timezone: IANA timezone string for the group
            
        Returns:
            List of birthday dictionaries
        """
        # Get all birthdays for this group
        all_birthdays = self.db.get_birthdays_by_group(group_id)
        
        # Filter for today's birthdays
        today_birthdays = [
            b for b in all_birthdays
            if self._is_birthday_today(b['birth_date'], timezone)
        ]
        
        logger.info(f"Found {len(today_birthdays)} birthdays today in group {group_id}")
        return today_birthdays
    
    async def check_and_send_birthdays(self, group_id: int) -> Dict[str, Any]:
        """
        Check for birthdays today and send messages if needed.
        
        This is the main function called by the scheduler.
        Implements idempotency to avoid duplicate sends.
        
        Args:
            group_id: Telegram group ID
            
        Returns:
            Dictionary with results: {
                'group_id': int,
                'birthdays_found': int,
                'messages_sent': int,
                'messages_skipped': int,
                'errors': List[str]
            }
        """
        logger.info(f"[BIRTHDAY_SCHEDULER] Checking birthdays for group {group_id}")
        logger.debug(f"[BIRTHDAY_SCHEDULER] Starting birthday check job for group {group_id}")
        
        # Get group settings
        settings = self.db.get_group_birthday_settings(group_id)
        if not settings:
            logger.error(f"[BIRTHDAY_SCHEDULER] Group {group_id} not found or has no settings")
            return {
                'group_id': group_id,
                'birthdays_found': 0,
                'messages_sent': 0,
                'messages_skipped': 0,
                'errors': ['Group not found']
            }
        
        logger.debug(f"[BIRTHDAY_SCHEDULER] Group {group_id} settings: timezone={settings['timezone']}, ai_enabled={settings.get('birthday_ai_enabled', 1)}")
        
        timezone = settings['timezone']
        current_year = datetime.now(ZoneInfo(timezone)).year
        
        logger.debug(f"[BIRTHDAY_SCHEDULER] Checking for birthdays on {datetime.now(ZoneInfo(timezone)).strftime('%Y-%m-%d')} (year: {current_year})")
        
        # Get birthdays for today
        birthdays = self.get_birthdays_today(group_id, timezone)
        
        logger.info(f"[BIRTHDAY_SCHEDULER] Found {len(birthdays)} birthdays today in group {group_id}")
        
        results = {
            'group_id': group_id,
            'birthdays_found': len(birthdays),
            'messages_sent': 0,
            'messages_skipped': 0,
            'errors': []
        }
        
        if not birthdays:
            logger.info(f"[BIRTHDAY_SCHEDULER] No birthdays today in group {group_id}")
            return results
        
        logger.info(f"[BIRTHDAY_SCHEDULER] Processing {len(birthdays)} birthdays for group {group_id}")
        
        # Check idempotency: have we already sent messages for these birthdays this year?
        for birthday in birthdays:
            logger.debug(f"[BIRTHDAY_SCHEDULER] Processing birthday: id={birthday['id']}, name={birthday['first_name']} {birthday['last_name']}, birth_date={birthday['birth_date']}")
            
            existing_msg = self.db.get_birthday_message(
                birthday_id=birthday['id'],
                group_id=group_id,
                birthday_year=current_year
            )
            
            if existing_msg and existing_msg['status'] == 'sent':
                logger.info(f"[BIRTHDAY_SCHEDULER] Birthday {birthday['id']} already sent to group {group_id} this year, skipping")
                results['messages_skipped'] += 1
                continue
            
            # Send birthday message
            try:
                logger.debug(f"[BIRTHDAY_SCHEDULER] Attempting to send birthday message for {birthday['first_name']} {birthday['last_name']}")
                success = await self._send_birthday_message(
                    birthday=birthday,
                    group_id=group_id,
                    settings=settings,
                    birthday_year=current_year
                )
                
                if success:
                    results['messages_sent'] += 1
                    logger.info(f"[BIRTHDAY_SCHEDULER] ✅ Successfully sent message for birthday {birthday['id']}")
                else:
                    error_msg = f"Failed to send for birthday {birthday['id']}"
                    results['errors'].append(error_msg)
                    logger.warning(f"[BIRTHDAY_SCHEDULER] ❌ {error_msg}")
            except Exception as e:
                error_msg = f"Error sending birthday {birthday['id']}: {str(e)}"
                logger.error(f"[BIRTHDAY_SCHEDULER] ❌ {error_msg}", exc_info=True)
                results['errors'].append(error_msg)
        
        logger.info(f"[BIRTHDAY_SCHEDULER] Completed birthday check for group {group_id}: sent={results['messages_sent']}, skipped={results['messages_skipped']}, errors={len(results['errors'])}")
        return results
    
    async def _send_birthday_message(
        self,
        birthday: Dict[str, Any],
        group_id: int,
        settings: Dict[str, Any],
        birthday_year: int
    ) -> bool:
        """
        Send a birthday message for one person.
        
        Full implementation with:
        - Biblical text selection
        - AI message generation (or static template)
        - Telegram sending with error handling
        - Database tracking
        
        Args:
            birthday: Birthday dictionary
            group_id: Telegram group ID
            settings: Group birthday settings
            birthday_year: Current year
            
        Returns:
            True if sent successfully, False otherwise
        """
        logger.info(f"[BIRTHDAY_SCHEDULER] Preparing birthday message for {birthday['first_name']} {birthday['last_name']} to group {group_id}")
        
        try:
            # Step 1: Select biblical text
            logger.debug(f"[BIRTHDAY_SCHEDULER] Step 1: Selecting biblical text for birthday {birthday['id']}")
            biblical_text = self.text_selector.select_text(
                group_id=group_id,
                birthday=birthday,
                language=settings.get('language', 'it')
            )
            
            if not biblical_text:
                # No biblical text available - send simple reminder message
                logger.warning(f"[BIRTHDAY_SCHEDULER] No biblical text available for group {group_id}, sending fallback message")
                logger.warning(f"[BIRTHDAY_SCHEDULER] ⚠️  CONFIGURATION WARNING: Group {group_id} has no biblical texts!")
                logger.warning(f"[BIRTHDAY_SCHEDULER] ⚠️  Sending simplified birthday reminder instead.")
                
                # Generate fallback message using AI if available
                name = f"{birthday['first_name']} {birthday['last_name']}"
                use_ai = settings.get('birthday_ai_enabled', 1) == 1
                
                logger.debug(f"[BIRTHDAY_SCHEDULER] Generating fallback message (AI enabled: {use_ai})")
                message = self._generate_fallback_message(
                    birthday=birthday,
                    use_ai=use_ai
                )
                
                if not message:
                    # Ultimate fallback if generation fails
                    logger.warning(f"[BIRTHDAY_SCHEDULER] Failed to generate fallback message, using basic template")
                    comment_info = f"\n\n💡 {birthday['comment']}" if birthday.get('comment') else ""
                    message = f"🎉 Buon compleanno {name}! 🎂\n\n"
                    message += f"Oggi festeggiamo il compleanno di {name}!\n"
                    message += f"Ricordiamoci di fargli/farle gli auguri! 🎈{comment_info}"
                
                # Create database record
                msg_id = self.db.create_birthday_message(
                    birthday_id=birthday['id'],
                    group_id=group_id,
                    birthday_year=birthday_year
                )
                
                if not msg_id:
                    logger.error(f"[BIRTHDAY_SCHEDULER] Failed to create birthday message record in database")
                    return False
                
                logger.debug(f"[BIRTHDAY_SCHEDULER] Created message record with ID: {msg_id}")
                
                # Send message to Telegram
                logger.debug(f"[BIRTHDAY_SCHEDULER] Sending fallback message to Telegram chat {group_id}")
                try:
                    sent_message = await self.bot.send_message(
                        chat_id=group_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    
                    logger.info(f"[BIRTHDAY_SCHEDULER] Fallback message sent successfully (telegram_msg_id: {sent_message.message_id})")
                    
                    # Mark as sent
                    self.db.update_birthday_message_sent(
                        message_id=msg_id,
                        telegram_message_id=sent_message.message_id
                    )
                    logger.debug(f"[BIRTHDAY_SCHEDULER] Marked message {msg_id} as sent in database")
                    
                    # Notify admins in private about missing configuration
                    logger.debug(f"[BIRTHDAY_SCHEDULER] Sending private notifications to admins")
                    await self._notify_admins_about_missing_config(
                        group_id=group_id,
                        birthday_name=name,
                        issue_type="biblical_texts"
                    )
                    
                    logger.info(f"[BIRTHDAY_SCHEDULER] ✅ Successfully sent fallback birthday message {msg_id} to group {group_id}")
                    return True
                    
                except TelegramError as e:
                    error_msg = f"Telegram error: {str(e)}"
                    logger.error(f"[BIRTHDAY_SCHEDULER] Failed to send fallback message: {error_msg}")
                    self.db.update_birthday_message_failed(msg_id, error_msg)
                    logger.debug(f"[BIRTHDAY_SCHEDULER] Marked message {msg_id} as failed in database")
                    return False
            
            logger.info(f"[BIRTHDAY_SCHEDULER] Selected biblical text: {biblical_text['reference']} (ID: {biblical_text['id']})")
            logger.debug(f"[BIRTHDAY_SCHEDULER] Biblical text content preview: {biblical_text.get('text', '')[:100]}...")
            
            # Step 2: Generate message using AI or static template
            use_ai = settings.get('birthday_ai_enabled', 1) == 1
            logger.debug(f"[BIRTHDAY_SCHEDULER] Step 2: Generating message (AI enabled: {use_ai})")
            
            message = self.message_generator.generate_message(
                birthdays=[birthday],
                biblical_texts=[biblical_text],
                use_ai=use_ai
            )
            
            if not message:
                error_msg = "Failed to generate birthday message"
                logger.error(f"[BIRTHDAY_SCHEDULER] {error_msg}")
                msg_id = self.db.create_birthday_message(
                    birthday_id=birthday['id'],
                    group_id=group_id,
                    birthday_year=birthday_year,
                    biblical_text_id=biblical_text['id']
                )
                if msg_id:
                    self.db.update_birthday_message_failed(msg_id, error_msg)
                return False
            
            logger.info(f"[BIRTHDAY_SCHEDULER] Generated message: {len(message)} characters")
            logger.debug(f"[BIRTHDAY_SCHEDULER] Message preview: {message[:150]}...")
            
            # Step 3: Add mention if enabled
            mention_enabled = settings.get('birthday_mention_enabled', 0) == 1
            logger.debug(f"[BIRTHDAY_SCHEDULER] Step 3: Adding mention (enabled: {mention_enabled})")
            if mention_enabled:
                message = self.message_generator.add_mention_if_enabled(
                    message=message,
                    birthday=birthday,
                    mention_enabled=mention_enabled
                )
                logger.debug(f"[BIRTHDAY_SCHEDULER] Message with mention: {len(message)} characters")
            
            # Step 4: Create database record BEFORE sending
            logger.debug(f"[BIRTHDAY_SCHEDULER] Step 4: Creating database record before sending")
            message_hash = hashlib.sha256(message.encode()).hexdigest()
            logger.debug(f"[BIRTHDAY_SCHEDULER] Message hash: {message_hash}")
            msg_id = self.db.create_birthday_message(
                birthday_id=birthday['id'],
                group_id=group_id,
                birthday_year=birthday_year,
                biblical_text_id=biblical_text['id'],
                generated_message=message,  # Store full message for debugging
                message_hash=message_hash
            )
            
            if not msg_id:
                logger.error(f"[BIRTHDAY_SCHEDULER] Failed to create birthday message record in database")
                return False
            
            logger.debug(f"[BIRTHDAY_SCHEDULER] Created message record with ID: {msg_id}")
            
            # Step 5: Send message to Telegram
            logger.debug(f"[BIRTHDAY_SCHEDULER] Step 5: Sending message to Telegram chat {group_id}")
            try:
                sent_message = await self.bot.send_message(
                    chat_id=group_id,
                    text=message,
                    parse_mode='Markdown'  # For mentions to work
                )
                
                logger.info(f"[BIRTHDAY_SCHEDULER] Message sent to Telegram successfully (telegram_msg_id: {sent_message.message_id})")
                
                # Mark as sent
                self.db.update_birthday_message_sent(
                    message_id=msg_id,
                    telegram_message_id=sent_message.message_id
                )
                logger.debug(f"[BIRTHDAY_SCHEDULER] Marked message {msg_id} as sent in database")
                
                # Mark biblical text as used
                self.text_selector.mark_text_used(biblical_text['id'])
                logger.debug(f"[BIRTHDAY_SCHEDULER] Marked biblical text {biblical_text['id']} as used")
                
                logger.info(f"[BIRTHDAY_SCHEDULER] ✅ Successfully sent birthday message {msg_id} to group {group_id}")
                return True
                
            except TelegramError as e:
                error_msg = f"Telegram error: {str(e)}"
                logger.error(f"[BIRTHDAY_SCHEDULER] Failed to send message to Telegram: {error_msg}")
                self.db.update_birthday_message_failed(msg_id, error_msg)
                logger.debug(f"[BIRTHDAY_SCHEDULER] Marked message {msg_id} as failed in database")
                return False
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"[BIRTHDAY_SCHEDULER] Error in _send_birthday_message: {error_msg}", exc_info=True)
            import traceback
            traceback.print_exc()
            return False
    
    async def retry_failed_messages(self) -> Dict[str, Any]:
        """
        Retry sending failed birthday messages within retry window.
        
        Checks all failed messages and attempts to resend them if:
        - They are within the retry window (default: 2 days)
        - Retry count hasn't exceeded the limit
        
        Returns:
            Dictionary with results: {
                'total_failed': int,
                'retried': int,
                'succeeded': int,
                'still_failed': int,
                'errors': List[str]
            }
        """
        logger.info("[BIRTHDAY_SCHEDULER] Checking for failed birthday messages to retry")
        
        # Get failed messages
        failed_messages = self.db.get_failed_birthday_messages(max_retry_days=2)
        
        results = {
            'total_failed': len(failed_messages),
            'retried': 0,
            'succeeded': 0,
            'still_failed': 0,
            'errors': []
        }
        
        logger.info(f"[BIRTHDAY_SCHEDULER] Found {len(failed_messages)} failed messages to potentially retry")
        
        for msg in failed_messages:
            logger.info(f"[BIRTHDAY_SCHEDULER] Retrying message {msg['id']} (attempt {msg['retry_count'] + 1}/3)")
            logger.debug(f"[BIRTHDAY_SCHEDULER] Failed message details: birthday_id={msg['birthday_id']}, group_id={msg['group_id']}, error='{msg.get('error_message', 'unknown')}'")
            
            # Check if message was already sent successfully this year (idempotency check)
            # This can happen if the message was sent by another process or manual intervention
            existing_msg = self.db.get_birthday_message(
                birthday_id=msg['birthday_id'],
                group_id=msg['group_id'],
                birthday_year=msg['birthday_year']
            )
            
            if existing_msg and existing_msg['status'] == 'sent' and existing_msg['id'] != msg['id']:
                logger.info(f"[BIRTHDAY_SCHEDULER] Birthday {msg['birthday_id']} already sent successfully this year (by message {existing_msg['id']}), skipping retry of message {msg['id']}")
                results['still_failed'] += 1  # Count as still failed, but won't retry
                continue
            
            # Don't skip configuration errors anymore - we now send fallback messages
            # So all errors are worth retrying
            
            # Get birthday and group settings
            birthday = self.db.get_birthday_by_id(msg['birthday_id'])
            if not birthday:
                logger.warning(f"[BIRTHDAY_SCHEDULER] Birthday {msg['birthday_id']} not found, skipping retry")
                results['still_failed'] += 1
                continue
            
            settings = self.db.get_group_birthday_settings(msg['group_id'])
            if not settings:
                logger.warning(f"[BIRTHDAY_SCHEDULER] Group {msg['group_id']} settings not found, skipping retry")
                results['still_failed'] += 1
                continue
            
            # Check retry limit (max 3 attempts)
            if msg['retry_count'] >= 3:
                logger.warning(f"[BIRTHDAY_SCHEDULER] Message {msg['id']} exceeded retry limit (3 attempts), giving up")
                results['still_failed'] += 1
                continue
            
            # Increment retry count in database
            self.db.increment_birthday_message_retry(msg['id'])
            results['retried'] += 1
            
            # Try to send again
            try:
                success = await self._send_birthday_message(
                    birthday=birthday,
                    group_id=msg['group_id'],
                    settings=settings,
                    birthday_year=msg['birthday_year']
                )
                
                if success:
                    results['succeeded'] += 1
                    logger.info(f"[BIRTHDAY_SCHEDULER] ✅ Successfully retried message {msg['id']}")
                else:
                    results['still_failed'] += 1
                    logger.warning(f"[BIRTHDAY_SCHEDULER] ❌ Retry failed for message {msg['id']}")
            except Exception as e:
                results['still_failed'] += 1
                logger.error(f"[BIRTHDAY_SCHEDULER] ❌ Exception during retry of message {msg['id']}: {str(e)}", exc_info=True)
        
        logger.info(f"[BIRTHDAY_SCHEDULER] Retry check completed: total={results['total_failed']}, retried={results['retried']}, succeeded={results['succeeded']}, still_failed={results['still_failed']}")
        return results


def setup_birthday_scheduler(
    application,
    db: Database
) -> None:
    """
    Setup birthday scheduler jobs for all groups.
    
    This function should be called during bot initialization.
    It creates daily jobs for each group at their configured send time.
    
    Args:
        application: Telegram Application instance (has bot and job_queue)
        db: Database instance
    """
    logger.info("[BIRTHDAY_SCHEDULER] Starting setup of birthday scheduler")
    
    job_queue = application.job_queue
    bot = application.bot
    
    # Get all groups
    groups = db.get_all_groups_info()
    logger.info(f"[BIRTHDAY_SCHEDULER] Found {len(groups)} groups in database")
    
    scheduler = BirthdayScheduler(db, bot)
    
    for group in groups:
        group_id = group['group_id']
        
        # Get group settings
        settings = db.get_group_birthday_settings(group_id)
        if not settings:
            logger.warning(f"[BIRTHDAY_SCHEDULER] No birthday settings for group {group_id}, skipping scheduler setup")
            continue
        
        # Parse send time (format: "HH:MM")
        try:
            hour, minute = map(int, settings['birthday_send_time'].split(':'))
        except Exception as e:
            logger.error(f"[BIRTHDAY_SCHEDULER] Invalid birthday_send_time for group {group_id}: {settings['birthday_send_time']}", exc_info=True)
            continue
        
        # Get timezone
        timezone = ZoneInfo(settings['timezone'])
        
        # Create async callback for this group
        async def birthday_check_callback(context, gid=group_id):
            """Async callback wrapper for birthday check"""
            logger.debug(f"[BIRTHDAY_SCHEDULER] Job triggered for group {gid}")
            try:
                result = await scheduler.check_and_send_birthdays(gid)
                logger.debug(f"[BIRTHDAY_SCHEDULER] Job completed for group {gid}: {result}")
            except Exception as e:
                logger.error(f"[BIRTHDAY_SCHEDULER] Job failed for group {gid}: {str(e)}", exc_info=True)
        
        # Create daily job
        job_queue.run_daily(
            callback=birthday_check_callback,
            time=datetime.now(timezone).replace(hour=hour, minute=minute, second=0, microsecond=0).timetz(),
            name=f"birthday_check_{group_id}"
        )
        
        logger.info(f"[BIRTHDAY_SCHEDULER] ✅ Scheduled daily birthday check for group {group_id} at {hour:02d}:{minute:02d} {settings['timezone']}")
    
    # Create async callback for retry job
    async def retry_failed_callback(context):
        """Async callback wrapper for retry failed messages"""
        logger.debug("[BIRTHDAY_SCHEDULER] Retry job triggered")
        try:
            result = await scheduler.retry_failed_messages()
            logger.debug(f"[BIRTHDAY_SCHEDULER] Retry job completed: {result}")
        except Exception as e:
            logger.error(f"[BIRTHDAY_SCHEDULER] Retry job failed: {str(e)}", exc_info=True)
    
    # Also schedule retry job (runs once per day at 10:00 Europe/Rome)
    rome_tz = ZoneInfo('Europe/Rome')
    job_queue.run_daily(
        callback=retry_failed_callback,
        time=datetime.now(rome_tz).replace(hour=10, minute=0, second=0, microsecond=0).timetz(),
        name="birthday_retry_failed"
    )
    
    
    logger.info("[BIRTHDAY_SCHEDULER] ✅ Birthday scheduler setup completed successfully")

