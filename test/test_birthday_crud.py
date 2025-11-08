"""
Unit Tests for Birthday CRUD Operations

Tests the new CRUD functionality including:
- Telegram user ID linking
- Birthday search
- Birthday update operations
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from database import Database


class TestBirthdayCRUD(unittest.TestCase):
    """Test CRUD operations for birthdays."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = Database.get_instance('sqlite:///:memory:')
        
        # Add test birthday
        self.birthday = self.db.add_birthday(
            first_name='Mario',
            last_name='Rossi',
            birth_date='03/15',
            group_ids=[1, 2],
            comment='Test user'
        )
    
    def test_get_birthday_by_id(self):
        """Test retrieving a birthday by ID."""
        birthday = self.db.get_birthday_by_id(self.birthday.id)
        
        self.assertIsNotNone(birthday)
        self.assertEqual(birthday['first_name'], 'Mario')
        self.assertEqual(birthday['last_name'], 'Rossi')
        self.assertEqual(birthday['birth_date'], '03/15')
    
    def test_get_birthday_by_id_not_found(self):
        """Test retrieving a non-existent birthday."""
        birthday = self.db.get_birthday_by_id(999)
        self.assertIsNone(birthday)
    
    def test_update_birthday_first_name(self):
        """Test updating first name."""
        success = self.db.update_birthday(self.birthday.id, first_name='Luigi')
        self.assertTrue(success)
        
        birthday = self.db.get_birthday_by_id(self.birthday.id)
        self.assertEqual(birthday['first_name'], 'Luigi')
    
    def test_update_birthday_last_name(self):
        """Test updating last name."""
        success = self.db.update_birthday(self.birthday.id, last_name='Verdi')
        self.assertTrue(success)
        
        birthday = self.db.get_birthday_by_id(self.birthday.id)
        self.assertEqual(birthday['last_name'], 'Verdi')
    
    def test_update_birthday_birth_date(self):
        """Test updating birth date."""
        success = self.db.update_birthday(self.birthday.id, birth_date='1990/12/25')
        self.assertTrue(success)
        
        birthday = self.db.get_birthday_by_id(self.birthday.id)
        self.assertEqual(birthday['birth_date'], '1990/12/25')
    
    def test_update_birthday_comment(self):
        """Test updating comment."""
        success = self.db.update_birthday(self.birthday.id, comment='Updated comment')
        self.assertTrue(success)
        
        birthday = self.db.get_birthday_by_id(self.birthday.id)
        self.assertEqual(birthday['comment'], 'Updated comment')
    
    def test_update_birthday_groups(self):
        """Test updating group IDs."""
        success = self.db.update_birthday(self.birthday.id, group_ids=[3, 4, 5])
        self.assertTrue(success)
        
        birthday = self.db.get_birthday_by_id(self.birthday.id)
        self.assertEqual(birthday['group_ids'], [3, 4, 5])
    
    def test_update_birthday_telegram_id(self):
        """Test updating Telegram user ID."""
        success = self.db.update_birthday_telegram_id(self.birthday.id, 123456789)
        self.assertTrue(success)
        
        birthday = self.db.get_birthday_by_id(self.birthday.id)
        self.assertEqual(birthday['telegram_user_id'], 123456789)
    
    def test_update_birthday_not_found(self):
        """Test updating a non-existent birthday."""
        success = self.db.update_birthday(999, first_name='Test')
        self.assertFalse(success)
    
    def test_search_birthdays_by_first_name(self):
        """Test searching birthdays by first name."""
        # Add more test data
        self.db.add_birthday('Anna', 'Bianchi', '12/23', [1])
        self.db.add_birthday('Mario', 'Verdi', '05/10', [2])
        
        results = self.db.search_birthdays(first_name='Mario')
        self.assertEqual(len(results), 2)  # Should find both Marios
    
    def test_search_birthdays_by_last_name(self):
        """Test searching birthdays by last name."""
        self.db.add_birthday('Anna', 'Rossi', '12/23', [1])
        
        results = self.db.search_birthdays(last_name='Rossi')
        self.assertEqual(len(results), 2)  # Should find both Rossis
    
    def test_search_birthdays_by_telegram_id(self):
        """Test searching birthdays by Telegram user ID."""
        # Update with Telegram ID
        self.db.update_birthday_telegram_id(self.birthday.id, 123456789)
        
        results = self.db.search_birthdays(telegram_user_id=123456789)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['telegram_user_id'], 123456789)
    
    def test_search_birthdays_partial_match(self):
        """Test searching with partial name match."""
        self.db.add_birthday('Maria', 'Rossi', '12/23', [1])
        
        results = self.db.search_birthdays(first_name='Mar')
        self.assertGreaterEqual(len(results), 2)  # Should find Mario and Maria
    
    def test_search_birthdays_case_insensitive(self):
        """Test that search is case-insensitive."""
        results = self.db.search_birthdays(first_name='mario')
        self.assertGreater(len(results), 0)
        
        results2 = self.db.search_birthdays(first_name='MARIO')
        self.assertEqual(len(results), len(results2))


class TestBirthdayWithTelegramID(unittest.TestCase):
    """Test birthday operations with Telegram user ID."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = Database.get_instance('sqlite:///:memory:')
    
    def test_add_birthday_with_telegram_id(self):
        """Test adding a birthday with Telegram user ID."""
        birthday = self.db.add_birthday(
            first_name='Mario',
            last_name='Rossi',
            birth_date='03/15',
            group_ids=[1, 2],
            telegram_user_id=123456789
        )
        
        self.assertEqual(birthday.telegram_user_id, 123456789)
        
        # Verify in database
        fetched = self.db.get_birthday_by_id(birthday.id)
        self.assertEqual(fetched['telegram_user_id'], 123456789)
    
    def test_get_all_birthdays_includes_telegram_id(self):
        """Test that get_all_birthdays includes telegram_user_id."""
        self.db.add_birthday(
            first_name='Mario',
            last_name='Rossi',
            birth_date='03/15',
            group_ids=[1],
            telegram_user_id=123456789
        )
        
        birthdays = self.db.get_all_birthdays()
        self.assertGreater(len(birthdays), 0)
        
        for birthday in birthdays:
            self.assertIn('telegram_user_id', birthday)
    
    def test_get_birthdays_by_group_includes_telegram_id(self):
        """Test that get_birthdays_by_group includes telegram_user_id."""
        self.db.add_birthday(
            first_name='Mario',
            last_name='Rossi',
            birth_date='03/15',
            group_ids=[1, 2],
            telegram_user_id=123456789
        )
        
        birthdays = self.db.get_birthdays_by_group(1)
        self.assertGreater(len(birthdays), 0)
        
        for birthday in birthdays:
            self.assertIn('telegram_user_id', birthday)
    
    def test_update_telegram_id_from_none(self):
        """Test updating telegram_user_id from None to a value."""
        birthday = self.db.add_birthday(
            first_name='Mario',
            last_name='Rossi',
            birth_date='03/15',
            group_ids=[1]
        )
        
        # Initially None
        fetched = self.db.get_birthday_by_id(birthday.id)
        self.assertIsNone(fetched['telegram_user_id'])
        
        # Update
        success = self.db.update_birthday_telegram_id(birthday.id, 987654321)
        self.assertTrue(success)
        
        # Verify
        fetched = self.db.get_birthday_by_id(birthday.id)
        self.assertEqual(fetched['telegram_user_id'], 987654321)
    
    def test_update_telegram_id_to_different_value(self):
        """Test changing telegram_user_id to a different value."""
        birthday = self.db.add_birthday(
            first_name='Mario',
            last_name='Rossi',
            birth_date='03/15',
            group_ids=[1],
            telegram_user_id=111111111
        )
        
        # Update to different value
        success = self.db.update_birthday_telegram_id(birthday.id, 222222222)
        self.assertTrue(success)
        
        # Verify
        fetched = self.db.get_birthday_by_id(birthday.id)
        self.assertEqual(fetched['telegram_user_id'], 222222222)


if __name__ == '__main__':
    unittest.main()
