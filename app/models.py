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
from datetime import datetime

Base = declarative_base()


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
    """
    __tablename__ = 'authorized_groups'

    group_id = Column(Integer, primary_key=True)
    group_name = Column(String, nullable=False)
    church_id = Column(Integer, ForeignKey('churches.id'), nullable=True)
    language = Column(String, default='it')
    message_limit = Column(Integer, default=500)
    time_limit = Column(Integer, default=30)  # Days to keep messages
    last_cleanup = Column(DateTime, nullable=True)

    # Relationships
    church = relationship('Church', back_populates='groups')
    users = relationship('User', back_populates='church_group')
    messages = relationship('Message', back_populates='group', cascade='all, delete-orphan')
    transcriptions = relationship('Transcription', back_populates='group')

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
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    telegram_message_id = Column(Integer, nullable=True)  # Telegram's message ID for creating links

    # Relationships
    group = relationship('AuthorizedGroup', back_populates='messages')

    def __repr__(self):
        return f"<Message(id={self.message_id}, group_id={self.group_id}, author='{self.author_name}')>"


class Transcription(Base):
    """
    Caches audio transcriptions to avoid re-processing the same audio files.
    Uses hash-based identification for duplicate detection.
    """
    __tablename__ = 'transcriptions'

    hash = Column(String, primary_key=True)
    transcription = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    group_id = Column(Integer, ForeignKey('authorized_groups.group_id'), nullable=True)

    # Relationships
    group = relationship('AuthorizedGroup', back_populates='transcriptions')

    def __repr__(self):
        return f"<Transcription(hash='{self.hash[:8]}...', group_id={self.group_id})>"
