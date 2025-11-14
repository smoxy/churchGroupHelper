"""
Biblical Text Selector Module
==============================

This module implements the smart selection algorithm for biblical texts
used in birthday messages. The algorithm considers:
- Age suitability (age_min, age_max)
- Gender preference (M, F, or any)
- Recent usage exclusion (last N used globally)
- Per-group monthly exclusion (avoid repetition in same group)
- Fallback logic if filters too restrictive

The selection process prioritizes variety and appropriateness.
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from database import Database

logger = logging.getLogger(__name__)


class BiblicalTextSelector:
    """
    Smart selector for biblical texts in birthday messages.
    
    Implements filtering algorithm with fallback logic to ensure
    a text is always available even with restrictive criteria.
    """
    
    def __init__(self, db: Database):
        """
        Initialize the selector with database connection.
        
        Args:
            db: Database instance for queries
        """
        self.db = db
    
    def _calculate_age(self, birth_date: str) -> Optional[int]:
        """
        Calculate age from birth_date string.
        
        Args:
            birth_date: Birth date in format 'MM/dd' or 'yyyy/MM/dd'
            
        Returns:
            Age in years or None if year not provided
        """
        parts = birth_date.split('/')
        
        # Check if full date with year (yyyy/MM/dd or MM/dd/yyyy)
        if len(parts) == 3:
            # Try yyyy/MM/dd format
            if len(parts[0]) == 4:
                year = int(parts[0])
            # Try MM/dd/yyyy format
            elif len(parts[2]) == 4:
                year = int(parts[2])
            else:
                return None
            
            current_year = datetime.now().year
            age = current_year - year
            
            # Adjust if birthday hasn't occurred yet this year
            month = int(parts[1] if len(parts[0]) == 4 else parts[0])
            day = int(parts[2] if len(parts[0]) == 4 else parts[1])
            today = datetime.now()
            
            if (today.month, today.day) < (month, day):
                age -= 1
            
            return age
        
        # No year provided, can't calculate age
        return None
    
    def _detect_gender(
        self,
        first_name: str,
        gender_override: Optional[str] = None
    ) -> Optional[str]:
        """
        Detect gender from name or use override.
        
        Args:
            first_name: First name of the person
            gender_override: Manual gender override ('M', 'F', or None)
            
        Returns:
            'M', 'F', or None if unknown
        """
        # Use override if provided
        if gender_override:
            return gender_override
        
        # Try gender-guesser library if available
        try:
            import gender_guesser.detector as gender
            detector = gender.Detector()
            result = detector.get_gender(first_name)
            
            # Map gender-guesser results to M/F
            if result in ['male', 'mostly_male']:
                return 'M'
            elif result in ['female', 'mostly_female']:
                return 'F'
            else:
                return None
        except ImportError:
            logger.warning("gender-guesser library not available, skipping gender detection")
            return None
    
    def _get_texts_used_in_last_month(
        self,
        group_id: int
    ) -> List[int]:
        """
        Get IDs of biblical texts used in the last month for this group.
        
        Queries birthday_messages table to find which texts were used
        recently in this specific group, enabling per-group monthly exclusion.
        
        Args:
            group_id: Telegram group ID
            
        Returns:
            List of biblical text IDs used in last 30 days
        """
        try:
            from database import BirthdayMessage
            
            # Get texts used in last 30 days for this group
            last_month = datetime.now() - timedelta(days=30)
            
            with self.db.get_session() as session:
                used_ids = session.query(BirthdayMessage.biblical_text_id)\
                    .filter(
                        BirthdayMessage.group_id == group_id,
                        BirthdayMessage.created_at >= last_month,
                        BirthdayMessage.biblical_text_id != None
                    ).distinct()\
                    .all()
            
            result = [row[0] for row in used_ids if row[0]]
            logger.debug(f"Texts used in last month for group {group_id}: {len(result)} texts")
            return result
        
        except Exception as e:
            logger.warning(f"Error getting texts used in last month: {e}")
            return []
    
    def select_text(
        self,
        group_id: int,
        birthday: Dict[str, Any],
        language: str = 'it',
        exclude_last_n: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Select the most appropriate biblical text for a birthday.
        
        Selection algorithm:
        1. Calculate age if birth year available
        2. Detect gender (override or auto-detect)
        3. Query texts with filters: group_id, language, age, gender
        4. Exclude last N used globally
        5. Exclude texts used in last month for this group
        6. If no results, relax filters progressively:
           - Remove gender filter
           - Remove age filter
           - Remove monthly exclusion
           - Use any available text
        
        Args:
            group_id: Telegram group ID
            birthday: Birthday dictionary with person's info
            language: Language preference for text
            exclude_last_n: Number of recently used texts to exclude
            
        Returns:
            Dictionary with selected biblical text or None if no texts available
        """
        logger.info(f"Selecting biblical text for birthday {birthday['id']} in group {group_id}")
        
        # Calculate age and detect gender
        age = self._calculate_age(birthday['birth_date'])
        gender = self._detect_gender(
            birthday['first_name'],
            birthday.get('gender_override')
        )
        
        logger.debug(f"Birthday {birthday['id']}: age={age}, gender={gender}")
        
        # Get texts used in last month for this group
        monthly_exclusions = self._get_texts_used_in_last_month(group_id)
        
        # Try with full filters
        texts = self.db.get_biblical_texts(
            group_id=group_id,
            language=language,
            age=age,
            gender=gender,
            exclude_last_n=exclude_last_n
        )
        
        # Filter out monthly exclusions
        texts = [t for t in texts if t['id'] not in monthly_exclusions]
        
        if texts:
            logger.info(f"Found {len(texts)} texts with full filters")
            return texts[0]
        
        # Fallback 1: Remove gender filter
        logger.debug("No texts with gender filter, trying without gender")
        texts = self.db.get_biblical_texts(
            group_id=group_id,
            language=language,
            age=age,
            gender=None,
            exclude_last_n=exclude_last_n
        )
        texts = [t for t in texts if t['id'] not in monthly_exclusions]
        
        if texts:
            logger.info(f"Found {len(texts)} texts without gender filter")
            return texts[0]
        
        # Fallback 2: Remove age filter
        logger.debug("No texts without gender, trying without age")
        texts = self.db.get_biblical_texts(
            group_id=group_id,
            language=language,
            age=None,
            gender=None,
            exclude_last_n=exclude_last_n
        )
        texts = [t for t in texts if t['id'] not in monthly_exclusions]
        
        if texts:
            logger.info(f"Found {len(texts)} texts without age/gender filters")
            return texts[0]
        
        # Fallback 3: Remove monthly exclusion
        logger.debug("No texts without age/gender, trying without monthly exclusion")
        texts = self.db.get_biblical_texts(
            group_id=group_id,
            language=language,
            age=None,
            gender=None,
            exclude_last_n=exclude_last_n
        )
        
        if texts:
            logger.info(f"Found {len(texts)} texts without monthly exclusion")
            return texts[0]
        
        # Fallback 4: Use any available text (no exclusions)
        logger.warning("No texts with any filters, using any available text")
        texts = self.db.get_biblical_texts(
            group_id=group_id,
            language=language,
            age=None,
            gender=None,
            exclude_last_n=0
        )
        
        if texts:
            logger.info(f"Found {len(texts)} texts without any filters")
            return texts[0]
        
        # No texts available at all
        logger.error(f"No biblical texts available for group {group_id}")
        logger.error(f"CRITICAL: Group {group_id} has no biblical texts configured!")
        logger.error(f"ACTION REQUIRED: Import biblical texts for this group using the admin interface.")
        logger.error(f"Birthday messages cannot be sent without biblical texts.")
        return None
    
    def mark_text_used(self, text_id: int) -> bool:
        """
        Mark a biblical text as used (updates last_used_at).
        
        Args:
            text_id: ID of the biblical text
            
        Returns:
            True if updated successfully, False otherwise
        """
        return self.db.update_biblical_text_last_used(text_id)


