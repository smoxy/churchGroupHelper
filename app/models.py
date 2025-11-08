"""
SQLAlchemy ORM Models for Church Group Helper Bot

This module defines all database models using SQLAlchemy ORM.
Each model represents a table in the database with proper relationships and constraints.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Date,
    ForeignKey, JSON, Table
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()

# Import Birthday in models export
__all__ = ['Base', 'User', 'Church', 'AuthorizedGroup', 'AuthorizedUser', 
           'Message', 'Transcription', 'Birthday', 'BiblicalText', 'BirthdayMessage']


class User(Base):
    """
    Represents a user in a church group.
    A user can belong to multiple church groups.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    church_group_id = Column(Integer, ForeignKey('authorized_groups.group_id'), primary_key=True)
    name = Column(String, nullable=False)
    surname = Column(String, default='')
    username = Column(String, default='')
    alias = Column(String, default='')
    birthday = Column(Date, nullable=True)
    admin_of = Column(JSON, nullable=True)  # List of group IDs the user is admin of

    # Relationships
    church_group = relationship('AuthorizedGroup', back_populates='users')

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', surname='{self.surname}', church_group_id={self.church_group_id})>"


class Church(Base):
    """
    Represents a physical church location with geographic information.
    Churches can have multiple admin users and associated groups.
    """
    __tablename__ = 'churches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_ids = Column(JSON, nullable=True)  # List of user IDs who are admins
    city = Column(String, nullable=False)
    address = Column(String, default='')
    country = Column(String, default='it')
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    language = Column(String, default='it')
    description = Column(Text, default='')

    # Relationships
    groups = relationship('AuthorizedGroup', back_populates='church')

    def __repr__(self):
        return f"<Church(id={self.id}, city='{self.city}', country='{self.country}')>"


class AuthorizedGroup(Base):
    """
    Represents a Telegram group authorized to use the bot.
    Contains settings for message limits, language preferences, and cleanup policies.
    Also manages birthday notification settings per group.
    """
    __tablename__ = 'authorized_groups'

    group_id = Column(Integer, primary_key=True)
    group_name = Column(String, nullable=False)
    church_id = Column(Integer, ForeignKey('churches.id'), nullable=True)
    language = Column(String, default='it')
    message_limit = Column(Integer, default=500)
    time_limit = Column(Integer, default=30)  # Days to keep messages
    last_cleanup = Column(DateTime, nullable=True)
    
    # Birthday notification settings
    timezone = Column(String, default='Europe/Rome')  # IANA timezone for this group
    birthday_send_time = Column(String, default='09:00')  # Time to send birthday messages (HH:MM format)
    birthday_mention_enabled = Column(Integer, default=0)  # 0=no mention, 1=mention if telegram_user_id present
    birthday_ai_enabled = Column(Integer, default=1)  # 0=static template, 1=AI-generated
    birthday_retry_days = Column(Integer, default=2)  # Days to retry failed birthday messages

    # Relationships
    church = relationship('Church', back_populates='groups')
    users = relationship('User', back_populates='church_group')
    messages = relationship('Message', back_populates='group', cascade='all, delete-orphan')
    transcriptions = relationship('Transcription', back_populates='group')
    biblical_texts = relationship('BiblicalText', back_populates='group', cascade='all, delete-orphan')
    birthday_messages = relationship('BirthdayMessage', back_populates='group', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<AuthorizedGroup(group_id={self.group_id}, name='{self.group_name}')>"


class AuthorizedUser(Base):
    """
    Represents a user authorized to use the bot in private chats.
    Stores user preferences like language.
    """
    __tablename__ = 'authorized_users'

    user_id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    language = Column(String, default='it')

    def __repr__(self):
        return f"<AuthorizedUser(user_id={self.user_id}, name='{self.first_name}')>"


class Message(Base):
    """
    Stores messages from authorized groups for summarization and history.
    Messages are subject to automatic cleanup based on group settings.
    """
    __tablename__ = 'messages'

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('authorized_groups.group_id'), nullable=False)
    user_id = Column(Integer, nullable=True)
    author_name = Column(String, nullable=False)
    message_text = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    telegram_message_id = Column(Integer, nullable=True)  # Telegram's message ID for creating links

    # Relationships
    group = relationship('AuthorizedGroup', back_populates='messages')

    def __repr__(self):
        return f"<Message(id={self.message_id}, group_id={self.group_id}, author='{self.author_name}')>"


class Transcription(Base):
    """
    Caches audio transcriptions to avoid re-processing the same audio files.
    Uses hash-based identification for duplicate detection.
    
    Privacy considerations:
    - Private chat transcriptions have no message_id (no user metadata stored)
    - Group transcriptions link to Message table via foreign key
    - User metadata (user_id, author_name, telegram_message_id) only in Message table
    """
    __tablename__ = 'transcriptions'

    hash = Column(String, primary_key=True)
    transcription = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    group_id = Column(Integer, ForeignKey('authorized_groups.group_id'), nullable=True)
    message_id = Column(Integer, ForeignKey('messages.message_id'), nullable=True)  # Link to Message for metadata

    # Relationships
    group = relationship('AuthorizedGroup', back_populates='transcriptions')
    message = relationship('Message', backref='transcription', foreign_keys=[message_id])

    def __repr__(self):
        return f"<Transcription(hash='{self.hash[:8]}...', group_id={self.group_id}, message_id={self.message_id})>"


class Birthday(Base):
    """
    Stores birthday information for users.
    Each user can have one birthday entry that can be announced in multiple groups.
    Can optionally be linked to a Telegram user ID for more advanced features.
    """
    __tablename__ = 'birthdays'

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False, default='')
    birth_date = Column(String, nullable=False)  # Format: 'MM/dd' or 'yyyy/MM/dd'
    comment = Column(String, nullable=True)
    group_ids = Column(JSON, nullable=False, default=list)  # List of group IDs where to announce birthday
    telegram_user_id = Column(Integer, nullable=True)  # Optional: Telegram user ID for mentions/links
    
    # Privacy and personalization settings
    gender_override = Column(String, nullable=True)  # 'M', 'F', or null for auto-detection
    mention_opt_out = Column(Integer, default=0)  # 0=allow mention (if telegram_user_id), 1=never mention
    age_display = Column(Integer, default=1)  # 0=never show age, 1=show age (user-level config)
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    birthday_messages = relationship('BirthdayMessage', back_populates='birthday', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Birthday(id={self.id}, name='{self.first_name} {self.last_name}', birth_date='{self.birth_date}', telegram_user_id={self.telegram_user_id})>"


class BiblicalText(Base):
    """
    Stores biblical texts used for birthday messages.
    Texts are associated with specific groups and can be filtered by age/gender suitability.
    Each group manages its own collection of biblical texts.
    """
    __tablename__ = 'biblical_texts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('authorized_groups.group_id'), nullable=False)
    reference = Column(String, nullable=False)  # e.g., "Giovanni 3:16", "Salmo 23:1"
    text = Column(Text, nullable=False)  # The biblical text content
    language = Column(String, default='it')  # Language of the text
    theme = Column(String, nullable=True)  # Optional theme (e.g., "speranza", "amore", "fede")
    
    # Suitability filters for smart selection
    age_min = Column(Integer, nullable=True)  # Minimum age suitability (null = any age)
    age_max = Column(Integer, nullable=True)  # Maximum age suitability (null = any age)
    gender_preference = Column(String, nullable=True)  # 'M', 'F', or null for any gender
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime, nullable=True)  # Track when last used globally (across all birthdays)
    
    # Relationships
    group = relationship('AuthorizedGroup', back_populates='biblical_texts')
    birthday_messages = relationship('BirthdayMessage', back_populates='biblical_text')

    def __repr__(self):
        return f"<BiblicalText(id={self.id}, group_id={self.group_id}, reference='{self.reference}')>"


class BirthdayMessage(Base):
    """
    Tracks birthday messages sent to groups.
    Used for idempotency (avoid duplicate sends) and retry logic.
    Stores metadata about when messages were sent and their delivery status.
    """
    __tablename__ = 'birthday_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    birthday_id = Column(Integer, ForeignKey('birthdays.id'), nullable=False)
    group_id = Column(Integer, ForeignKey('authorized_groups.group_id'), nullable=False)
    biblical_text_id = Column(Integer, ForeignKey('biblical_texts.id'), nullable=True)  # Which text was used
    
    # Message content and metadata
    generated_message = Column(Text, nullable=True)  # Full generated message (stored for logging/debugging)
    message_hash = Column(String, nullable=True)  # SHA256 hash for privacy (alternative to storing full text)
    
    # Delivery tracking
    sent_at = Column(DateTime, nullable=True)  # When successfully sent (null = not sent yet)
    telegram_message_id = Column(Integer, nullable=True)  # Telegram's message ID if sent successfully
    status = Column(String, default='pending')  # 'pending', 'sent', 'failed', 'retrying'
    retry_count = Column(Integer, default=0)  # Number of retry attempts
    error_message = Column(Text, nullable=True)  # Error details if failed
    
    # Birthday year tracking (for idempotency across years)
    birthday_year = Column(Integer, nullable=False)  # Year this birthday was celebrated (e.g., 2025)
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    birthday = relationship('Birthday', back_populates='birthday_messages')
    group = relationship('AuthorizedGroup', back_populates='birthday_messages')
    biblical_text = relationship('BiblicalText', back_populates='birthday_messages')

    def __repr__(self):
        return f"<BirthdayMessage(id={self.id}, birthday_id={self.birthday_id}, group_id={self.group_id}, status='{self.status}', year={self.birthday_year})>"
