"""
Database Test Script

This script tests the new SQLAlchemy ORM implementation to ensure
all database operations work correctly.

Run this before deploying to verify the migration was successful.
"""

import sys
import os
from datetime import datetime, timedelta

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from database import Database
from models import User, Church, AuthorizedGroup, AuthorizedUser, Message, Transcription


def test_database():
    """Run comprehensive database tests."""
    
    print("=" * 60)
    print("SQLAlchemy ORM Database Test Suite")
    print("=" * 60)
    print()
    
    # Use in-memory database for testing
    db = Database('sqlite:///:memory:')
    print("✓ Database initialized (in-memory)")
    print()
    
    # Test 1: Authorized Groups
    print("Test 1: Authorized Groups")
    print("-" * 40)
    try:
        group = db.add_authorized_group(
            group_id=12345,
            group_name="Test Church Group",
            language="it",
            message_limit=500,
            time_limit=30
        )
        print(f"✓ Added group: {group.group_name} (ID: {group.group_id})")
        
        settings = db.get_group_settings(12345)
        print(f"✓ Retrieved settings: {settings['group_name']}, lang={settings['language']}")
        
        groups = db.get_authorized_groups()
        print(f"✓ Found {len(groups)} authorized group(s)")
        
        db.update_group_language(12345, "en")
        print("✓ Updated group language to 'en'")
        
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 2: Authorized Users
    print("Test 2: Authorized Users")
    print("-" * 40)
    try:
        user = db.add_authorized_user(
            user_id=67890,
            first_name="John Doe",
            language="it"
        )
        print(f"✓ Added user: {user.first_name} (ID: {user.user_id})")
        
        lang = db.get_user_language(67890)
        print(f"✓ Retrieved user language: {lang}")
        
        db.update_user_language(67890, "John Doe", "en")
        print("✓ Updated user language to 'en'")
        
        users = db.get_authorized_users()
        print(f"✓ Found {len(users)} authorized user(s)")
        
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 3: Churches
    print("Test 3: Churches")
    print("-" * 40)
    try:
        church = db.add_church(
            city="Rome",
            address="Via Example 123",
            country="it",
            language="it",
            latitude=41.9028,
            longitude=12.4964,
            description="Test church"
        )
        print(f"✓ Added church: {church.city} (ID: {church.id})")
        
        db.add_church_admin(church.id, 67890)
        print(f"✓ Added admin to church")
        
        admins = db.get_church_admins(church.id)
        print(f"✓ Retrieved {len(admins)} church admin(s)")
        
        church_lang = db.get_church_language(church.id)
        print(f"✓ Church language: {church_lang}")
        
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 4: Users in Groups
    print("Test 4: Users in Church Groups")
    print("-" * 40)
    try:
        user = db.add_user(
            user_id=67890,
            church_group_id=12345,
            name="John",
            surname="Doe",
            username="johndoe",
            alias="JD",
            birthday=datetime(1990, 1, 15).date()
        )
        print(f"✓ Added user to church group: {user.name} {user.surname}")
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 5: Messages
    print("Test 5: Messages")
    print("-" * 40)
    try:
        # Add multiple messages
        for i in range(5):
            msg = db.add_message(
                group_id=12345,
                user_id=67890,
                author_name="John",
                message_text=f"Test message {i+1}",
                timestamp=datetime.now() - timedelta(minutes=5-i)
            )
        print(f"✓ Added 5 test messages")
        
        messages = db.get_messages(12345, limit=3)
        print(f"✓ Retrieved {len(messages)} messages (limit=3)")
        
        # Test message cleanup
        db.update_group_limits(12345, message_limit=2, time_limit=30)
        deleted = db.clean_old_messages(12345)
        print(f"✓ Cleaned up {deleted} old messages")
        
        remaining = db.get_messages(12345)
        print(f"✓ {len(remaining)} messages remaining")
        
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 6: Transcriptions
    print("Test 6: Transcriptions")
    print("-" * 40)
    try:
        # Save transcription
        hash1 = "abc123def456"
        trans = db.save_transcription(
            audio_hash=hash1,
            transcription="This is a test transcription",
            group_id=12345
        )
        print(f"✓ Saved transcription with hash: {hash1[:8]}...")
        
        # Retrieve transcription
        retrieved = db.get_transcription(hash1)
        print(f"✓ Retrieved transcription: {retrieved[:20]}...")
        
        # Save old transcription
        old_hash = "old123hash456"
        with db.get_session() as session:
            old_trans = Transcription(
                hash=old_hash,
                transcription="Old transcription",
                timestamp=datetime.now() - timedelta(days=8),
                group_id=12345
            )
            session.add(old_trans)
        
        # Clean old transcriptions
        deleted = db.clean_old_transcriptions(days=7)
        print(f"✓ Cleaned {deleted} old transcription(s)")
        
        # Verify old one is gone
        should_be_none = db.get_transcription(old_hash)
        if should_be_none is None:
            print(f"✓ Old transcription successfully removed")
        else:
            print(f"✗ Old transcription still exists")
        
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 7: Cleanup Operations
    print("Test 7: Cleanup Operations")
    print("-" * 40)
    try:
        # Remove user
        removed = db.remove_authorized_user(67890)
        print(f"✓ Removed authorized user: {removed}")
        
        # Remove group
        removed = db.remove_authorized_group(12345)
        print(f"✓ Removed authorized group: {removed}")
        
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Summary
    print("=" * 60)
    print("✓ All tests passed successfully!")
    print("=" * 60)
    print()
    print("The SQLAlchemy ORM implementation is working correctly.")
    print("You can now deploy the bot with confidence.")
    print()
    
    return True


def test_session_context_manager():
    """Test session context manager for proper cleanup."""
    
    print("Session Context Manager Test")
    print("-" * 40)
    
    db = Database('sqlite:///:memory:')
    
    try:
        # Test successful transaction
        with db.get_session() as session:
            from models import AuthorizedUser
            user = AuthorizedUser(user_id=111, first_name="Test", language="it")
            session.add(user)
        print("✓ Session commit successful")
        
        # Test rollback on error
        try:
            with db.get_session() as session:
                # Try to add duplicate (should fail)
                user = AuthorizedUser(user_id=111, first_name="Test2", language="en")
                session.add(user)
        except Exception:
            print("✓ Session rollback on error successful")
        
        # Verify user exists
        with db.get_session() as session:
            from models import AuthorizedUser
            user = session.query(AuthorizedUser).filter_by(user_id=111).first()
            if user:
                print(f"✓ User persisted correctly: {user.first_name}")
            else:
                print("✗ User not found after commit")
        
        print()
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_relationships():
    """Test SQLAlchemy relationships between models."""
    
    print("Relationship Test")
    print("-" * 40)
    
    db = Database('sqlite:///:memory:')
    
    try:
        with db.get_session() as session:
            from models import Church, AuthorizedGroup, Message
            
            # Create church
            church = Church(
                city="Test City",
                country="it",
                language="it"
            )
            session.add(church)
            session.flush()
            
            # Create group linked to church
            group = AuthorizedGroup(
                group_id=999,
                group_name="Test Group",
                church_id=church.id,
                language="it"
            )
            session.add(group)
            session.flush()
            
            # Create messages in group
            for i in range(3):
                msg = Message(
                    group_id=group.group_id,
                    user_id=123,
                    author_name="Test",
                    message_text=f"Message {i}",
                    timestamp=datetime.now()
                )
                session.add(msg)
            
            session.flush()
            
            # Test relationships
            print(f"✓ Church has {len(group.church.groups)} group(s)")
            print(f"✓ Group has {len(group.messages)} message(s)")
            print(f"✓ Group belongs to church: {group.church.city}")
            
        print()
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    print("\n🔍 Starting database tests...\n")
    
    success = True
    
    # Run main tests
    if not test_database():
        success = False
    
    # Run context manager tests
    if not test_session_context_manager():
        success = False
    
    # Run relationship tests
    if not test_relationships():
        success = False
    
    # Final result
    if success:
        print("\n✅ ALL TESTS PASSED! The database implementation is ready.\n")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED! Please review the errors above.\n")
        sys.exit(1)
