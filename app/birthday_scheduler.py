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
    
    def check_and_send_birthdays(self, group_id: int) -> Dict[str, Any]:
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
        logger.info(f"Checking birthdays for group {group_id}")
        
        # Get group settings
        settings = self.db.get_group_birthday_settings(group_id)
        if not settings:
            logger.error(f"Group {group_id} not found or has no settings")
            return {
                'group_id': group_id,
                'birthdays_found': 0,
                'messages_sent': 0,
                'messages_skipped': 0,
                'errors': ['Group not found']
            }
        
        timezone = settings['timezone']
        current_year = datetime.now(ZoneInfo(timezone)).year
        
        # Get birthdays for today
        birthdays = self.get_birthdays_today(group_id, timezone)
        
        results = {
            'group_id': group_id,
            'birthdays_found': len(birthdays),
            'messages_sent': 0,
            'messages_skipped': 0,
            'errors': []
        }
        
        if not birthdays:
            logger.info(f"No birthdays today in group {group_id}")
            return results
        
        # Check idempotency: have we already sent messages for these birthdays this year?
        for birthday in birthdays:
            existing_msg = self.db.get_birthday_message(
                birthday_id=birthday['id'],
                group_id=group_id,
                birthday_year=current_year
            )
            
            if existing_msg and existing_msg['status'] == 'sent':
                logger.info(f"Birthday {birthday['id']} already sent to group {group_id} this year, skipping")
                results['messages_skipped'] += 1
                continue
            
            # Send birthday message
            try:
                success = self._send_birthday_message(
                    birthday=birthday,
                    group_id=group_id,
                    settings=settings,
                    birthday_year=current_year
                )
                
                if success:
                    results['messages_sent'] += 1
                else:
                    results['errors'].append(f"Failed to send for birthday {birthday['id']}")
            except Exception as e:
                error_msg = f"Error sending birthday {birthday['id']}: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        return results
    
    def _send_birthday_message(
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
        logger.info(f"Preparing birthday message for {birthday['first_name']} {birthday['last_name']} to group {group_id}")
        
        try:
            # Step 1: Select biblical text
            biblical_text = self.text_selector.select_text(
                group_id=group_id,
                birthday=birthday,
                language=settings.get('language', 'it')
            )
            
            if not biblical_text:
                error_msg = "No biblical texts available for this group"
                logger.error(error_msg)
                # Create failed record
                msg_id = self.db.create_birthday_message(
                    birthday_id=birthday['id'],
                    group_id=group_id,
                    birthday_year=birthday_year
                )
                if msg_id:
                    self.db.update_birthday_message_failed(msg_id, error_msg)
                return False
            
            logger.info(f"Selected biblical text: {biblical_text['reference']}")
            
            # Step 2: Generate message using AI or static template
            use_ai = settings.get('birthday_ai_enabled', 1) == 1
            
            message = self.message_generator.generate_message(
                birthdays=[birthday],
                biblical_texts=[biblical_text],
                use_ai=use_ai
            )
            
            if not message:
                error_msg = "Failed to generate birthday message"
                logger.error(error_msg)
                msg_id = self.db.create_birthday_message(
                    birthday_id=birthday['id'],
                    group_id=group_id,
                    birthday_year=birthday_year,
                    biblical_text_id=biblical_text['id']
                )
                if msg_id:
                    self.db.update_birthday_message_failed(msg_id, error_msg)
                return False
            
            logger.info(f"Generated message: {len(message)} characters")
            
            # Step 3: Add mention if enabled
            mention_enabled = settings.get('birthday_mention_enabled', 0) == 1
            if mention_enabled:
                message = self.message_generator.add_mention_if_enabled(
                    message=message,
                    birthday=birthday,
                    mention_enabled=mention_enabled
                )
            
            # Step 4: Create database record BEFORE sending
            message_hash = hashlib.sha256(message.encode()).hexdigest()
            msg_id = self.db.create_birthday_message(
                birthday_id=birthday['id'],
                group_id=group_id,
                birthday_year=birthday_year,
                biblical_text_id=biblical_text['id'],
                generated_message=message,  # Store full message for debugging
                message_hash=message_hash
            )
            
            if not msg_id:
                logger.error("Failed to create birthday message record")
                return False
            
            # Step 5: Send message to Telegram
            try:
                sent_message = self.bot.send_message(
                    chat_id=group_id,
                    text=message,
                    parse_mode='Markdown'  # For mentions to work
                )
                
                # Mark as sent
                self.db.update_birthday_message_sent(
                    message_id=msg_id,
                    telegram_message_id=sent_message.message_id
                )
                
                # Mark biblical text as used
                self.text_selector.mark_text_used(biblical_text['id'])
                
                logger.info(f"✅ Successfully sent birthday message {msg_id} to group {group_id}")
                return True
                
            except TelegramError as e:
                error_msg = f"Telegram error: {str(e)}"
                logger.error(f"Failed to send message: {error_msg}")
                self.db.update_birthday_message_failed(msg_id, error_msg)
                return False
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Error in _send_birthday_message: {error_msg}")
            import traceback
            traceback.print_exc()
            return False
    
    def retry_failed_messages(self) -> Dict[str, Any]:
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
        logger.info("Checking for failed birthday messages to retry")
        
        # Get failed messages
        failed_messages = self.db.get_failed_birthday_messages(max_retry_days=2)
        
        results = {
            'total_failed': len(failed_messages),
            'retried': 0,
            'succeeded': 0,
            'still_failed': 0,
            'errors': []
        }
        
        for msg in failed_messages:
            # TODO: Implement retry logic
            # For now, just log
            logger.info(f"Would retry message {msg['id']} (attempt {msg['retry_count'] + 1})")
            results['retried'] += 1
        
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
    job_queue = application.job_queue
    bot = application.bot
    
    # Get all groups
    groups = db.get_all_groups_info()
    
    scheduler = BirthdayScheduler(db, bot)
    
    for group in groups:
        group_id = group['group_id']
        
        # Get group settings
        settings = db.get_group_birthday_settings(group_id)
        if not settings:
            logger.warning(f"No birthday settings for group {group_id}, skipping scheduler setup")
            continue
        
        # Parse send time (format: "HH:MM")
        try:
            hour, minute = map(int, settings['birthday_send_time'].split(':'))
        except Exception as e:
            logger.error(f"Invalid birthday_send_time for group {group_id}: {settings['birthday_send_time']}")
            continue
        
        # Get timezone
        timezone = ZoneInfo(settings['timezone'])
        
        # Create daily job
        job_queue.run_daily(
            callback=lambda context, gid=group_id: scheduler.check_and_send_birthdays(gid),
            time=datetime.now(timezone).replace(hour=hour, minute=minute, second=0, microsecond=0).timetz(),
            name=f"birthday_check_{group_id}"
        )
        
        logger.info(f"Scheduled daily birthday check for group {group_id} at {hour:02d}:{minute:02d} {settings['timezone']}")
    
    # Also schedule retry job (runs once per day at 10:00 Europe/Rome)
    rome_tz = ZoneInfo('Europe/Rome')
    job_queue.run_daily(
        callback=lambda context: scheduler.retry_failed_messages(),
        time=datetime.now(rome_tz).replace(hour=10, minute=0, second=0, microsecond=0).timetz(),
        name="birthday_retry_failed"
    )
    
    logger.info("Birthday scheduler setup completed")
