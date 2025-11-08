"""
Database Module with SQLAlchemy ORM

This module provides database connection management, session handling,
and high-level database operations using SQLAlchemy ORM.

Best practices implemented:
- Singleton pattern for database instance
- Session management with context managers
- Thread-safe operations
- Proper error handling and logging
- Separation of concerns (models vs. operations)
"""

import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import create_engine, func, and_, or_
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.pool import StaticPool

from models import (
    Base, User, Church, AuthorizedGroup, AuthorizedUser,
    Message, Transcription, Birthday
)

# Enable logging
logger = logging.getLogger(__name__)


class Database:
    """
    Singleton database manager using SQLAlchemy ORM.
    
    Provides thread-safe database operations with proper session management.
    All database operations should go through this class.
    """
    
    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_url: str = 'sqlite:////data/bot.db'):
        """
        Initialize database connection and create tables.
        
        Args:
            db_url: SQLAlchemy database URL (default: SQLite at /data/bot.db)
        """
        # Create engine with appropriate settings
        if db_url.startswith('sqlite'):
            # SQLite-specific settings
            self.engine = create_engine(
                db_url,
                connect_args={'check_same_thread': False},
                poolclass=StaticPool,
                echo=False  # Set to True for SQL query logging
            )
        else:
            # For other databases (PostgreSQL, MySQL, etc.)
            self.engine = create_engine(
                db_url,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,   # Recycle connections after 1 hour
                echo=False
            )
        
        # Create session factory
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)
        
        # Create all tables
        self._create_tables()

    @classmethod
    def get_instance(cls, db_url: str = 'sqlite:////data/bot.db') -> 'Database':
        """
        Get or create the singleton database instance.
        
        Args:
            db_url: SQLAlchemy database URL
            
        Returns:
            Database instance
        """
        with cls._lock:
            # Special-case: if caller requests an in-memory SQLite DB, return a
            # fresh Database instance every time. In-memory SQLite DBs are bound
            # to the connection and cannot be shared across instances.
            if db_url == 'sqlite:///:memory:':
                return cls(db_url)

            # Otherwise, if an instance doesn't exist, or the requested DB URL
            # differs from the existing instance, create/replace the singleton.
            if cls._instance is None:
                cls._instance = cls(db_url)
            else:
                try:
                    existing_url = str(cls._instance.engine.url)
                except Exception:
                    existing_url = None
                if db_url and existing_url != db_url:
                    # Replace the singleton with a new instance for the requested DB
                    cls._instance = cls(db_url)
        return cls._instance

    def _create_tables(self):
        """Create all database tables if they don't exist."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created/verified successfully")

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions.
        
        Usage:
            with db.get_session() as session:
                # perform database operations
                session.add(obj)
        
        Yields:
            SQLAlchemy session
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            session.close()

    # ==================== User Operations ====================
    
    def add_user(
        self, 
        user_id: int, 
        church_group_id: int, 
        name: str, 
        surname: str = '', 
        username: str = '', 
        alias: str = '', 
        birthday: Optional[datetime] = None, 
        admin_of: Optional[List[int]] = None
    ) -> User:
        """
        Add a user to a church group.
        
        Args:
            user_id: Telegram user ID
            church_group_id: Church group ID the user belongs to
            name: User's first name
            surname: User's surname (optional)
            username: Telegram username (optional)
            alias: User's alias/nickname (optional)
            birthday: User's birthday (optional)
            admin_of: List of group IDs the user is admin of (optional)
            
        Returns:
            Created User object
        """
        logger.info(
            f"Adding user '{name}' '{surname}' ({alias}) with birthday '{birthday}' "
            f"to church group '{church_group_id}'"
        )
        
        with self.get_session() as session:
            user = session.query(User).filter_by(
                id=user_id, 
                church_group_id=church_group_id
            ).first()
            
            if user:
                # Update existing user
                user.name = name
                user.surname = surname
                user.username = username
                user.alias = alias
                user.birthday = birthday
                user.admin_of = admin_of
            else:
                # Create new user
                user = User(
                    id=user_id,
                    church_group_id=church_group_id,
                    name=name,
                    surname=surname,
                    username=username,
                    alias=alias,
                    birthday=birthday,
                    admin_of=admin_of
                )
                session.add(user)
            
            session.flush()
            return user

    def remove_user(self, user_id: int, church_group_id: int) -> bool:
        """
        Remove a user from a church group.
        
        Args:
            user_id: Telegram user ID
            church_group_id: Church group ID
            
        Returns:
            True if user was removed, False if not found
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(
                id=user_id, 
                church_group_id=church_group_id
            ).first()
            
            if user:
                session.delete(user)
                logger.info(f"Removed user {user_id} from group {church_group_id}")
                return True
            return False

    # ==================== Church Operations ====================
    
    def add_church(
        self, 
        city: str, 
        address: str = '', 
        country: str = 'it', 
        language: str = 'it', 
        latitude: Optional[float] = None, 
        longitude: Optional[float] = None, 
        description: str = ''
    ) -> Church:
        """
        Add a new church location.
        
        Args:
            city: City name
            address: Street address
            country: Country code (default: 'it')
            language: Language code (default: 'it')
            latitude: Geographic latitude
            longitude: Geographic longitude
            description: Church description
            
        Returns:
            Created Church object
        """
        logger.info(
            f"Adding church '{city}' with address '{address}' "
            f"in '{country}' ({latitude}, {longitude})"
        )
        if description:
            logger.info(f"Description: {description}")
        if latitude is None or longitude is None:
            logger.warning("Missing coordinates")
        
        with self.get_session() as session:
            church = Church(
                city=city,
                address=address,
                country=country,
                language=language,
                latitude=latitude,
                longitude=longitude,
                description=description,
                admin_ids=[]
            )
            session.add(church)
            session.flush()
            return church

    def add_church_admin(self, church_id: int, user_id: int) -> bool:
        """
        Add an admin to a church.
        
        Args:
            church_id: Church ID
            user_id: User ID to add as admin
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            church = session.query(Church).filter_by(id=church_id).first()
            if not church:
                logger.warning(f"Church {church_id} not found")
                return False
            
            if church.admin_ids is None:
                church.admin_ids = []
            
            if user_id not in church.admin_ids:
                church.admin_ids.append(user_id)
                # Mark the field as modified for JSON column
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(church, 'admin_ids')
                logger.info(f"Added user {user_id} as admin of church {church_id}")
            
            return True

    def remove_church_admin(self, church_id: int, user_id: int) -> bool:
        """
        Remove an admin from a church.
        
        Args:
            church_id: Church ID
            user_id: User ID to remove from admins
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            church = session.query(Church).filter_by(id=church_id).first()
            if not church or not church.admin_ids:
                return False
            
            if user_id in church.admin_ids:
                church.admin_ids.remove(user_id)
                # Mark the field as modified for JSON column
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(church, 'admin_ids')
                logger.info(f"Removed user {user_id} as admin from church {church_id}")
            
            return True

    def get_church_admins(self, church_id: int) -> List[int]:
        """
        Get list of admin user IDs for a church.
        
        Args:
            church_id: Church ID
            
        Returns:
            List of admin user IDs
        """
        with self.get_session() as session:
            church = session.query(Church).filter_by(id=church_id).first()
            return church.admin_ids if church and church.admin_ids else []

    def update_church_language(self, church_id: int, language: str) -> bool:
        """
        Update the language of a church.
        
        Args:
            church_id: Church ID
            language: New language code
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            church = session.query(Church).filter_by(id=church_id).first()
            if church:
                church.language = language
                return True
            return False

    def get_church_language(self, church_id: int) -> Optional[str]:
        """
        Get the language of a church.
        
        Args:
            church_id: Church ID
            
        Returns:
            Language code or None
        """
        with self.get_session() as session:
            church = session.query(Church).filter_by(id=church_id).first()
            return church.language if church else None

    # ==================== Authorized Group Operations ====================
    
    def add_authorized_group(
        self, 
        group_id: int, 
        group_name: str, 
        language: str = 'it', 
        message_limit: int = 500, 
        time_limit: int = 30
    ) -> AuthorizedGroup:
        """
        Add an authorized Telegram group.
        
        Args:
            group_id: Telegram group ID
            group_name: Group name
            language: Language code (default: 'it')
            message_limit: Maximum messages to keep (default: 500)
            time_limit: Days to keep messages (default: 30)
            
        Returns:
            Created or existing AuthorizedGroup object
        """
        with self.get_session() as session:
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            
            if group:
                # Update existing group
                group.group_name = group_name
                group.language = language
                group.message_limit = message_limit
                group.time_limit = time_limit
            else:
                # Create new group
                group = AuthorizedGroup(
                    group_id=group_id,
                    group_name=group_name,
                    language=language,
                    message_limit=message_limit,
                    time_limit=time_limit
                )
                session.add(group)
            
            session.flush()
            return group

    def remove_authorized_group(self, group_id: int) -> bool:
        """
        Remove an authorized group.
        
        Args:
            group_id: Telegram group ID
            
        Returns:
            True if group was removed
        """
        with self.get_session() as session:
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            if group:
                session.delete(group)
                logger.info(f"Removed authorized group {group_id}")
                return True
            return False

    def get_group_settings(self, group_id: int) -> Optional[Dict[str, Any]]:
        """
        Get settings for an authorized group.
        
        Args:
            group_id: Telegram group ID
            
        Returns:
            Dictionary with group settings or None
        """
        with self.get_session() as session:
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            if group:
                return {
                    'group_id': group.group_id,
                    'group_name': group.group_name,
                    'church_id': group.church_id,
                    'language': group.language,
                    'message_limit': group.message_limit,
                    'time_limit': group.time_limit,
                    'last_cleanup': group.last_cleanup
                }
            return None

    def get_authorized_groups(self) -> List[int]:
        """
        Get list of all authorized group IDs.
        
        Returns:
            List of group IDs
        """
        with self.get_session() as session:
            groups = session.query(AuthorizedGroup.group_id).all()
            return [g[0] for g in groups]

    def update_group_language(self, group_id: int, language: str) -> bool:
        """
        Update the language of a group.
        
        Args:
            group_id: Telegram group ID
            language: New language code
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            if group:
                group.language = language
                logger.info(f"Updated language for group {group_id} to {language}")
                return True
            return False

    def update_group_limits(
        self, 
        group_id: int, 
        message_limit: Optional[int] = None, 
        time_limit: Optional[int] = None
    ) -> bool:
        """
        Update message and time limits for a group.
        
        Args:
            group_id: Telegram group ID
            message_limit: New message limit (optional)
            time_limit: New time limit in days (optional)
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            if not group:
                return False
            
            if message_limit is not None:
                group.message_limit = message_limit
            if time_limit is not None:
                group.time_limit = time_limit
            
            logger.info(
                f"Updated limits for group {group_id}: "
                f"message_limit={message_limit}, time_limit={time_limit}"
            )
            return True

    def get_group_language(self, group_id: int) -> Optional[str]:
        """
        Get the language of a group.
        
        Args:
            group_id: Telegram group ID
            
        Returns:
            Language code or None
        """
        with self.get_session() as session:
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            return group.language if group else None

    # ==================== Authorized User Operations ====================
    
    def add_authorized_user(
        self, 
        user_id: int, 
        first_name: str, 
        language: str = 'it'
    ) -> AuthorizedUser:
        """
        Add an authorized user for private chats.
        
        Args:
            user_id: Telegram user ID
            first_name: User's first name
            language: Language code (default: 'it')
            
        Returns:
            Created or existing AuthorizedUser object
        """
        logger.info(f"Adding authorized user '{first_name}'@'{user_id}' with language '{language}'")
        
        with self.get_session() as session:
            user = session.query(AuthorizedUser).filter_by(user_id=user_id).first()
            
            if user:
                # Update existing user
                user.first_name = first_name
                user.language = language
            else:
                # Create new user
                user = AuthorizedUser(
                    user_id=user_id,
                    first_name=first_name,
                    language=language
                )
                session.add(user)
            
            session.flush()
            return user

    def update_user_language(self, user_id: int, first_name: str, language: str) -> bool:
        """
        Update language for an authorized user.
        
        Args:
            user_id: Telegram user ID
            first_name: User's first name
            language: New language code
            
        Returns:
            True if successful
        """
        logger.info(f"Setting language for user '{first_name}'@'{user_id}' to '{language}'")
        
        with self.get_session() as session:
            user = session.query(AuthorizedUser).filter_by(user_id=user_id).first()
            if user:
                user.first_name = first_name
                user.language = language
                return True
            else:
                # Create user if doesn't exist
                self.add_authorized_user(user_id, first_name, language)
                return True

    def remove_authorized_user(self, user_id: int) -> bool:
        """
        Remove an authorized user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user was removed
        """
        with self.get_session() as session:
            user = session.query(AuthorizedUser).filter_by(user_id=user_id).first()
            if user:
                session.delete(user)
                logger.info(f"Removed authorized user {user_id}")
                return True
            return False

    def get_authorized_users(self) -> List[int]:
        """
        Get list of all authorized user IDs.
        
        Returns:
            List of user IDs
        """
        with self.get_session() as session:
            users = session.query(AuthorizedUser.user_id).all()
            return [u[0] for u in users]

    def get_user_language(self, user_id: int) -> str:
        """
        Get the language preference for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Language code (default: 'it')
        """
        with self.get_session() as session:
            user = session.query(AuthorizedUser).filter_by(user_id=user_id).first()
            return user.language if user else 'it'

    # ==================== Message Operations ====================
    
    def add_message(
        self, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        author_name: str, 
        message_text: Optional[str], 
        timestamp: datetime,
        telegram_message_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Add a message to the database.
        
        Args:
            group_id: Telegram group ID (None for private chats)
            user_id: Telegram user ID
            author_name: Author's name
            message_text: Message content
            timestamp: Message timestamp
            telegram_message_id: Telegram's message ID for creating links
            
        Returns:
            Message ID or None if group_id is None
        """
        if group_id is None:
            return None
        
        with self.get_session() as session:
            message = Message(
                group_id=group_id,
                user_id=user_id,
                author_name=author_name,
                message_text=message_text,
                timestamp=timestamp,
                telegram_message_id=telegram_message_id
            )
            session.add(message)
            session.flush()
            return message.message_id

    def get_messages(
        self, 
        group_id: int, 
        limit: Optional[int] = None, 
        since_message_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get messages from a group.
        
        Args:
            group_id: Telegram group ID
            limit: Maximum number of messages to return
            since_message_id: Get messages starting from this ID
            
        Returns:
            List of message dictionaries
        """
        with self.get_session() as session:
            query = session.query(Message).filter_by(group_id=group_id)
            
            if since_message_id:
                query = query.filter(Message.message_id >= since_message_id)
            
            query = query.order_by(Message.timestamp.asc())
            
            if limit:
                query = query.limit(limit)
            
            messages = query.all()
            
            return [
                {
                    'message_id': msg.message_id,
                    'group_id': msg.group_id,
                    'user_id': msg.user_id,
                    'author_name': msg.author_name,
                    'message_text': msg.message_text,
                    'timestamp': msg.timestamp,
                    'telegram_message_id': msg.telegram_message_id
                }
                for msg in messages
            ]

    def clean_null_group_messages(self) -> int:
        """
        Remove messages with null group_id.
        
        Returns:
            Number of messages deleted
        """
        with self.get_session() as session:
            count = session.query(Message).filter(Message.group_id.is_(None)).delete()
            logger.info(f"Cleaned {count} messages with null group_id")
            return count

    def clean_old_messages(self, group_id: int, all_messages: bool = False) -> int:
        """
        Clean old messages from a group based on group settings.
        
        Args:
            group_id: Telegram group ID
            all_messages: If True, delete all messages from the group
            
        Returns:
            Number of messages deleted
        """
        settings = self.get_group_settings(group_id)
        if not settings:
            return 0
        
        message_limit = settings['message_limit']
        time_limit = settings['time_limit']
        
        with self.get_session() as session:
            if all_messages:
                count = session.query(Message).filter_by(group_id=group_id).delete()
                logger.info(f"Deleted all {count} messages from group {group_id}")
                return count
            
            deleted = 0
            
            # Delete messages older than time_limit days
            time_threshold = datetime.now() - timedelta(days=time_limit)
            count = session.query(Message).filter(
                and_(
                    Message.group_id == group_id,
                    Message.timestamp < time_threshold
                )
            ).delete()
            deleted += count
            
            # Keep only the last message_limit messages
            # Get the message_id of the oldest message to keep
            subquery = session.query(Message.message_id).filter_by(
                group_id=group_id
            ).order_by(Message.timestamp.desc()).limit(message_limit).subquery()
            
            # Delete messages not in the subquery
            count = session.query(Message).filter(
                and_(
                    Message.group_id == group_id,
                    ~Message.message_id.in_(subquery)
                )
            ).delete(synchronize_session=False)
            deleted += count
            
            if deleted > 0:
                logger.info(f"Cleaned {deleted} old messages from group {group_id}")
            
            # Update last cleanup time
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            if group:
                group.last_cleanup = datetime.now()
            
            return deleted

    # ==================== Transcription Operations ====================
    
    def get_transcription(self, audio_hash: str) -> Optional[str]:
        """
        Get a cached transcription by audio hash.
        
        Args:
            audio_hash: Hash of the audio file
            
        Returns:
            Transcription text or None
        """
        with self.get_session() as session:
            transcription = session.query(Transcription).filter_by(hash=audio_hash).first()
            return transcription.transcription if transcription else None

    def get_transcriptions(
        self, 
        group_id: int, 
        since_telegram_message_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get transcriptions from a group for summarization with metadata from Message table.
        
        Privacy: Only returns transcriptions that have an associated message (group messages).
        Private chat transcriptions are excluded (no message_id).
        
        Args:
            group_id: Telegram group ID
            since_telegram_message_id: Get transcriptions starting from this message ID
            
        Returns:
            List of transcription dictionaries with metadata from linked messages
        """
        with self.get_session() as session:
            # JOIN Transcription with Message to get user metadata
            query = session.query(Transcription, Message).join(
                Message, 
                Transcription.message_id == Message.message_id
            ).filter(
                Transcription.group_id == group_id,
                Transcription.message_id.isnot(None)  # Only group transcriptions
            )
            
            if since_telegram_message_id:
                query = query.filter(Message.telegram_message_id >= since_telegram_message_id)
            
            query = query.order_by(Message.timestamp.asc())
            results = query.all()
            
            return [
                {
                    'user_id': msg.user_id,
                    'author_name': msg.author_name,
                    'transcription': trans.transcription,
                    'timestamp': msg.timestamp,
                    'telegram_message_id': msg.telegram_message_id,
                    'is_audio': True  # Flag to identify transcriptions
                }
                for trans, msg in results
            ]

    def save_transcription(
        self, 
        audio_hash: str, 
        transcription: str, 
        group_id: Optional[int],
        message_id: Optional[int] = None
    ) -> Transcription:
        """
        Save a transcription to the cache.
        
        Privacy: Only group transcriptions have message_id (linking to Message table).
        Private chat transcriptions have no user metadata stored.
        
        Args:
            audio_hash: Hash of the audio file
            transcription: Transcription text
            group_id: Telegram group ID (None for private chats)
            message_id: Foreign key to messages table (None for private chats)
            
        Returns:
            Created Transcription object
        """
        with self.get_session() as session:
            trans = Transcription(
                hash=audio_hash,
                transcription=transcription,
                timestamp=datetime.now(),
                group_id=group_id,
                message_id=message_id
            )
            session.add(trans)
            session.flush()
            return trans

    def clean_old_transcriptions(self, days: int) -> int:
        """
        Remove transcriptions older than specified days.
        
        Args:
            days: Number of days to keep transcriptions
            
        Returns:
            Number of transcriptions deleted
        """
        with self.get_session() as session:
            time_threshold = datetime.now() - timedelta(days=days)
            count = session.query(Transcription).filter(
                Transcription.timestamp < time_threshold
            ).delete()
            
            if count > 0:
                logger.info(f"Cleaned {count} old transcriptions")
            
            return count

    # ==================== Birthday Operations ====================
    
    def add_birthday(
        self,
        first_name: str,
        last_name: str,
        birth_date: str,
        group_ids: List[int],
        comment: str = '',
        telegram_user_id: Optional[int] = None
    ) -> Birthday:
        """
        Add a birthday entry to the database.
        
        Args:
            first_name: Person's first name
            last_name: Person's last name
            birth_date: Birth date in format 'MM/dd' or 'yyyy/MM/dd'
            group_ids: List of group IDs where to announce birthday
            comment: Optional comment
            telegram_user_id: Optional Telegram user ID for mentions/links
            
        Returns:
            Created Birthday object
        """
        from types import SimpleNamespace

        with self.get_session() as session:
            birthday = Birthday(
                first_name=first_name,
                last_name=last_name,
                birth_date=birth_date,
                comment=comment,
                group_ids=group_ids,
                telegram_user_id=telegram_user_id
            )
            session.add(birthday)
            session.flush()
            # Copy fields into a simple detached object so callers can access
            # attributes after the session is closed without causing
            # DetachedInstanceError.
            b_obj = SimpleNamespace(
                id=birthday.id,
                first_name=birthday.first_name,
                last_name=birthday.last_name,
                birth_date=birthday.birth_date,
                comment=birthday.comment,
                group_ids=birthday.group_ids,
                telegram_user_id=birthday.telegram_user_id,
            )
            logger.info(f"Added birthday for {first_name} {last_name} ({birth_date})")
            return b_obj
    
    def get_all_birthdays(self) -> List[Dict[str, Any]]:
        """
        Get all birthdays from the database.
        
        Returns:
            List of birthday dictionaries
        """
        with self.get_session() as session:
            birthdays = session.query(Birthday).all()
            return [
                {
                    'id': b.id,
                    'first_name': b.first_name,
                    'last_name': b.last_name,
                    'birth_date': b.birth_date,
                    'comment': b.comment,
                    'group_ids': b.group_ids,
                    'telegram_user_id': b.telegram_user_id,
                    'created_at': b.created_at,
                    'updated_at': b.updated_at
                }
                for b in birthdays
            ]
    
    def get_birthdays_by_group(self, group_id: int) -> List[Dict[str, Any]]:
        """
        Get all birthdays that should be announced in a specific group.
        
        Args:
            group_id: Telegram group ID
            
        Returns:
            List of birthday dictionaries
        """
        with self.get_session() as session:
            birthdays = session.query(Birthday).all()
            result = []
            for b in birthdays:
                if b.group_ids and group_id in b.group_ids:
                    result.append({
                        'id': b.id,
                        'first_name': b.first_name,
                        'last_name': b.last_name,
                        'birth_date': b.birth_date,
                        'comment': b.comment,
                        'group_ids': b.group_ids,
                        'telegram_user_id': b.telegram_user_id
                    })
            return result
    
    def update_birthday_groups(self, birthday_id: int, group_ids: List[int]) -> bool:
        """
        Update the group IDs for a birthday.
        
        Args:
            birthday_id: Birthday ID
            group_ids: New list of group IDs
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            birthday = session.query(Birthday).filter_by(id=birthday_id).first()
            if birthday:
                birthday.group_ids = group_ids
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(birthday, 'group_ids')
                logger.info(f"Updated group IDs for birthday {birthday_id}")
                return True
            return False
    
    def delete_birthday(self, birthday_id: int) -> bool:
        """
        Delete a birthday entry.
        
        Args:
            birthday_id: Birthday ID
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            birthday = session.query(Birthday).filter_by(id=birthday_id).first()
            if birthday:
                session.delete(birthday)
                logger.info(f"Deleted birthday {birthday_id}")
                return True
            return False
    
    def get_birthday_by_id(self, birthday_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific birthday by its ID.
        
        Args:
            birthday_id: Birthday ID
            
        Returns:
            Birthday dictionary or None if not found
        """
        with self.get_session() as session:
            birthday = session.query(Birthday).filter_by(id=birthday_id).first()
            if birthday:
                return {
                    'id': birthday.id,
                    'first_name': birthday.first_name,
                    'last_name': birthday.last_name,
                    'birth_date': birthday.birth_date,
                    'comment': birthday.comment,
                    'group_ids': birthday.group_ids,
                    'telegram_user_id': birthday.telegram_user_id,
                    'created_at': birthday.created_at,
                    'updated_at': birthday.updated_at
                }
            return None
    
    def update_birthday(
        self, 
        birthday_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        birth_date: Optional[str] = None,
        comment: Optional[str] = None,
        group_ids: Optional[List[int]] = None,
        telegram_user_id: Optional[int] = None
    ) -> bool:
        """
        Update a birthday entry. Only provided fields will be updated.
        
        Args:
            birthday_id: Birthday ID
            first_name: New first name (optional)
            last_name: New last name (optional)
            birth_date: New birth date (optional)
            comment: New comment (optional)
            group_ids: New list of group IDs (optional)
            telegram_user_id: New Telegram user ID (optional)
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            birthday = session.query(Birthday).filter_by(id=birthday_id).first()
            if not birthday:
                return False
            
            if first_name is not None:
                birthday.first_name = first_name
            if last_name is not None:
                birthday.last_name = last_name
            if birth_date is not None:
                birthday.birth_date = birth_date
            if comment is not None:
                birthday.comment = comment
            if group_ids is not None:
                birthday.group_ids = group_ids
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(birthday, 'group_ids')
            if telegram_user_id is not None:
                birthday.telegram_user_id = telegram_user_id
            
            from datetime import timezone
            birthday.updated_at = datetime.now(timezone.utc)
            logger.info(f"Updated birthday {birthday_id}")
            return True
    
    def update_birthday_telegram_id(self, birthday_id: int, telegram_user_id: int) -> bool:
        """
        Update the Telegram user ID for a birthday entry.
        
        Args:
            birthday_id: Birthday ID
            telegram_user_id: Telegram user ID
            
        Returns:
            True if successful
        """
        return self.update_birthday(birthday_id, telegram_user_id=telegram_user_id)
    
    def search_birthdays(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        telegram_user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for birthdays by name or Telegram user ID.
        
        Args:
            first_name: First name to search (partial match, case-insensitive)
            last_name: Last name to search (partial match, case-insensitive)
            telegram_user_id: Telegram user ID to search
            
        Returns:
            List of matching birthday dictionaries
        """
        with self.get_session() as session:
            query = session.query(Birthday)
            
            if first_name:
                query = query.filter(Birthday.first_name.ilike(f'%{first_name}%'))
            if last_name:
                query = query.filter(Birthday.last_name.ilike(f'%{last_name}%'))
            if telegram_user_id:
                query = query.filter(Birthday.telegram_user_id == telegram_user_id)
            
            birthdays = query.all()
            return [
                {
                    'id': b.id,
                    'first_name': b.first_name,
                    'last_name': b.last_name,
                    'birth_date': b.birth_date,
                    'comment': b.comment,
                    'group_ids': b.group_ids,
                    'telegram_user_id': b.telegram_user_id,
                    'created_at': b.created_at,
                    'updated_at': b.updated_at
                }
                for b in birthdays
            ]
    
    def get_group_name_by_id(self, group_id: int) -> Optional[str]:
        """
        Get the name of a group by its ID.
        
        Args:
            group_id: Telegram group ID
            
        Returns:
            Group name or None if not found
        """
        with self.get_session() as session:
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            return group.group_name if group else None
    
    def update_group_name(self, group_id: int, group_name: str) -> bool:
        """
        Update the name of a group.
        
        Args:
            group_id: Telegram group ID
            group_name: New group name
            
        Returns:
            True if successful
        """
        with self.get_session() as session:
            group = session.query(AuthorizedGroup).filter_by(group_id=group_id).first()
            if group:
                group.group_name = group_name
                logger.info(f"Updated name for group {group_id} to {group_name}")
                return True
            return False
    
    def get_all_groups_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all authorized groups.
        
        Returns:
            List of dictionaries with group_id and group_name
        """
        with self.get_session() as session:
            groups = session.query(AuthorizedGroup).all()
            return [
                {
                    'group_id': g.group_id,
                    'group_name': g.group_name
                }
                for g in groups
            ]

    # ==================== Utility Methods ====================
    
    def close(self):
        """Close database connection and cleanup resources."""
        self.Session.remove()
        self.engine.dispose()
        logger.info("Database connection closed")
