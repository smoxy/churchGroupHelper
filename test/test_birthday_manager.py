"""
Unit Tests for Birthday Manager

Tests the birthday management functionality including:
- Date parsing
- CSV processing
- Database operations
"""

import unittest
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from birthday_manager import BirthdayManager
from database import Database


class TestBirthdayDateParsing(unittest.TestCase):
    """Test date parsing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = Database.get_instance('sqlite:///:memory:')
        self.manager = BirthdayManager(self.db)
    
    def test_parse_date_with_year(self):
        """Test parsing date with year (dd-MM-yyyy)."""
        result = self.manager._parse_birth_date('15-03-1990')
        self.assertEqual(result, '1990/03/15')
    
    def test_parse_date_without_year(self):
        """Test parsing date without year (dd-MM)."""
        result = self.manager._parse_birth_date('23-12')
        self.assertEqual(result, '12/23')
    
    def test_parse_date_single_digit_day(self):
        """Test parsing date with single digit day."""
        result = self.manager._parse_birth_date('5-12-1990')
        self.assertEqual(result, '1990/12/05')
    
    def test_parse_date_single_digit_month(self):
        """Test parsing date with single digit month."""
        result = self.manager._parse_birth_date('15-3-1990')
        self.assertEqual(result, '1990/03/15')
    
    def test_parse_date_invalid_format(self):
        """Test parsing invalid date format."""
        with self.assertRaises(ValueError):
            self.manager._parse_birth_date('1990-03-15')
    
    def test_parse_date_invalid_day(self):
        """Test parsing date with invalid day."""
        with self.assertRaises(ValueError):
            self.manager._parse_birth_date('32-12-1990')
    
    def test_parse_date_invalid_month(self):
        """Test parsing date with invalid month."""
        with self.assertRaises(ValueError):
            self.manager._parse_birth_date('15-13-1990')
    
    def test_parse_date_invalid_year(self):
        """Test parsing date with invalid year."""
        with self.assertRaises(ValueError):
            self.manager._parse_birth_date('15-03-1800')
    
    def test_parse_date_with_whitespace(self):
        """Test parsing date with whitespace."""
        result = self.manager._parse_birth_date('  15-03-1990  ')
        self.assertEqual(result, '1990/03/15')


class TestBirthdayDatabase(unittest.TestCase):
    """Test database operations for birthdays."""
    
    def setUp(self):
        """Set up test database."""
        self.db = Database.get_instance('sqlite:///:memory:')
        
        # Add test group
        self.db.add_authorized_group(
            group_id=-123456789,
            group_name='Test Group'
        )
    
    def test_add_birthday(self):
        """Test adding a birthday."""
        birthday = self.db.add_birthday(
            first_name='Mario',
            last_name='Rossi',
            birth_date='1990/03/15',
            group_ids=[-123456789],
            comment='Test user'
        )
        
        self.assertIsNotNone(birthday.id)
        self.assertEqual(birthday.first_name, 'Mario')
        self.assertEqual(birthday.last_name, 'Rossi')
        self.assertEqual(birthday.birth_date, '1990/03/15')
        self.assertEqual(birthday.group_ids, [-123456789])
    
    def test_get_all_birthdays(self):
        """Test retrieving all birthdays."""
        # Add test birthdays
        self.db.add_birthday('Mario', 'Rossi', '03/15', [-123456789])
        self.db.add_birthday('Anna', 'Bianchi', '1985/12/23', [-123456789])
        
        birthdays = self.db.get_all_birthdays()
        self.assertEqual(len(birthdays), 2)
    
    def test_get_birthdays_by_group(self):
        """Test retrieving birthdays for a specific group."""
        # Add birthday to test group
        self.db.add_birthday('Mario', 'Rossi', '03/15', [-123456789])
        
        # Add birthday to different group
        self.db.add_birthday('Anna', 'Bianchi', '12/23', [-987654321])
        
        birthdays = self.db.get_birthdays_by_group(-123456789)
        self.assertEqual(len(birthdays), 1)
        self.assertEqual(birthdays[0]['first_name'], 'Mario')
    
    def test_update_birthday_groups(self):
        """Test updating group IDs for a birthday."""
        birthday = self.db.add_birthday('Mario', 'Rossi', '03/15', [-123456789])
        
        # Update groups
        success = self.db.update_birthday_groups(birthday.id, [-123456789, -987654321])
        self.assertTrue(success)
        
        # Verify update
        birthdays = self.db.get_all_birthdays()
        self.assertEqual(len(birthdays[0]['group_ids']), 2)
    
    def test_delete_birthday(self):
        """Test deleting a birthday."""
        birthday = self.db.add_birthday('Mario', 'Rossi', '03/15', [-123456789])
        
        # Delete birthday
        success = self.db.delete_birthday(birthday.id)
        self.assertTrue(success)
        
        # Verify deletion
        birthdays = self.db.get_all_birthdays()
        self.assertEqual(len(birthdays), 0)
    
    def test_get_group_name_by_id(self):
        """Test retrieving group name."""
        name = self.db.get_group_name_by_id(-123456789)
        self.assertEqual(name, 'Test Group')
    
    def test_update_group_name(self):
        """Test updating group name."""
        success = self.db.update_group_name(-123456789, 'Updated Group')
        self.assertTrue(success)
        
        # Verify update
        name = self.db.get_group_name_by_id(-123456789)
        self.assertEqual(name, 'Updated Group')


class TestCSVProcessing(unittest.TestCase):
    """Test CSV processing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = Database.get_instance('sqlite:///:memory:')
        self.manager = BirthdayManager(self.db)
        
        # Add test group
        self.db.add_authorized_group(-123456789, 'Test Group')
    
    def test_process_valid_csv(self):
        """Test processing a valid CSV."""
        csv_content = """NOME,COGNOME,DATA DI NASCITA (dd-MM-yyyy),COMMENTO
Mario,Rossi,15-03-1990,Membro attivo
Anna,Bianchi,23-12,Visitatrice"""
        
        import asyncio
        result = asyncio.run(self.manager._process_csv(
            csv_content.encode('utf-8'),
            [-123456789]
        ))
        
        self.assertEqual(result['success_count'], 2)
        self.assertEqual(result['error_count'], 0)
    
    def test_process_csv_with_errors(self):
        """Test processing CSV with errors."""
        csv_content = """NOME,COGNOME,DATA DI NASCITA (dd-MM-yyyy),COMMENTO
Mario,Rossi,15-03-1990,Valid
,Bianchi,23-12,Missing first name
Anna,Verdi,invalid-date,Invalid date"""
        
        import asyncio
        result = asyncio.run(self.manager._process_csv(
            csv_content.encode('utf-8'),
            [-123456789]
        ))
        
        self.assertEqual(result['success_count'], 1)
        self.assertEqual(result['error_count'], 2)
    
    def test_process_csv_with_bom(self):
        """Test processing CSV with BOM."""
        csv_content = "\ufeffNOME,COGNOME,DATA DI NASCITA (dd-MM-yyyy),COMMENTO\nMario,Rossi,15-03-1990,Test"
        
        import asyncio
        result = asyncio.run(self.manager._process_csv(
            csv_content.encode('utf-8-sig'),
            [-123456789]
        ))
        
        self.assertEqual(result['success_count'], 1)


if __name__ == '__main__':
    unittest.main()
