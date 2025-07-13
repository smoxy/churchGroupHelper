from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, Float, Text, ForeignKey, PickleType
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    church_group_id = Column(Integer, ForeignKey('authorized_groups.group_id'), primary_key=True)
    name = Column(String)
    surname = Column(String, default='')
    username = Column(String, default='')
    alias = Column(String, default='')
    birthday = Column(Date)
    admin_of = Column(PickleType)

class Church(Base):
    __tablename__ = 'churches'
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_ids = Column(PickleType)
    city = Column(String)
    address = Column(String, default='')
    country = Column(String, default='it')
    latitude = Column(Float)
    longitude = Column(Float)
    language = Column(String, default='it')
    description = Column(Text, default='')
    groups = relationship('AuthorizedGroup', back_populates='church')

class AuthorizedGroup(Base):
    __tablename__ = 'authorized_groups'
    group_id = Column(Integer, primary_key=True)
    group_name = Column(String)
    church_id = Column(Integer, ForeignKey('churches.id'))
    language = Column(String, default='it')
    message_limit = Column(Integer, default=500)
    time_limit = Column(Integer, default=30)
    last_cleanup = Column(DateTime)
    church = relationship('Church', back_populates='groups')
    messages = relationship('Message', back_populates='group')

class AuthorizedUser(Base):
    __tablename__ = 'authorized_users'
    user_id = Column(Integer, primary_key=True)
    first_name = Column(String)
    language = Column(String, default='it')

class Transcription(Base):
    __tablename__ = 'transcriptions'
    hash = Column(String, primary_key=True)
    transcription = Column(Text)
    timestamp = Column(DateTime)
    group_id = Column(Integer, ForeignKey('authorized_groups.group_id'))

class Message(Base):
    __tablename__ = 'messages'
    message_id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('authorized_groups.group_id'))
    user_id = Column(Integer)
    author_name = Column(String)
    message_text = Column(Text)
    timestamp = Column(DateTime)
    group = relationship('AuthorizedGroup', back_populates='messages')
