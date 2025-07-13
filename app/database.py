from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker

from models import Base, User, Church, AuthorizedGroup, AuthorizedUser, Transcription, Message
from geopy.geocoders import Nominatim

logConf = logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Nominatim init
geolocator = Nominatim(user_agent="churchLocatorBot")

class Database:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_file: str = '/data/bot.db'):
        self.engine = create_engine(
            f'sqlite:///{db_file}',
            connect_args={'check_same_thread': False},
            future=True
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    @classmethod
    def get_instance(cls, db_file: str = '/data/bot.db') -> "Database":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_file)
        return cls._instance

    @contextmanager
    def get_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Session rollback due to exception")
            raise
        finally:
            session.close()

    # Users
    def add_user(
        self,
        user_id: int,
        church_group_id: int,
        name: str,
        surname: str = '',
        username: str = '',
        alias: str = '',
        birthday=None,
        admin_of=None,
    ) -> None:
        logger.info(
            "Adding user '%s' '%s' (%s) with birthday '%s' to church group '%s'",
            name,
            surname,
            alias,
            birthday,
            church_group_id,
        )
        with self.get_session() as session:
            user = session.get(User, {"id": user_id, "church_group_id": church_group_id})
            if not user:
                user = User(
                    id=user_id,
                    church_group_id=church_group_id,
                    name=name,
                    surname=surname,
                    username=username,
                    alias=alias,
                    birthday=birthday,
                    admin_of=admin_of,
                )
                session.add(user)

    def add_church(
        self,
        city: str,
        address: str = '',
        country: str = 'it',
        language: str = 'it',
        latitude: float | None = None,
        longitude: float | None = None,
        description: str = '',
    ) -> None:
        logger.info(
            "Adding church '%s' with address '%s' in '%s' (%s, %s)",
            city,
            address,
            country,
            latitude,
            longitude,
        )
        with self.get_session() as session:
            church = Church(
                city=city,
                address=address,
                country=country,
                latitude=latitude,
                longitude=longitude,
                language=language,
                description=description,
            )
            session.add(church)

    def add_church_admin(self, church_id: int, user_id: int) -> None:
        with self.get_session() as session:
            church = session.get(Church, church_id)
            if church:
                admins = church.admin_ids or []
                if user_id not in admins:
                    admins.append(user_id)
                    church.admin_ids = admins

    def remove_church_admin(self, church_id: int, user_id: int) -> None:
        with self.get_session() as session:
            church = session.get(Church, church_id)
            if church and church.admin_ids:
                admins = church.admin_ids
                if user_id in admins:
                    admins.remove(user_id)
                    church.admin_ids = admins

    def get_church_admins(self, church_id: int):
        with self.get_session() as session:
            church = session.get(Church, church_id)
            return church.admin_ids if church else []

    def update_church_language(self, church_id: int, language: str) -> None:
        with self.get_session() as session:
            church = session.get(Church, church_id)
            if church:
                church.language = language

    def get_church_language(self, church_id: int):
        with self.get_session() as session:
            church = session.get(Church, church_id)
            return church.language if church else None

    # Authorized groups
    def add_authorized_group(
        self,
        group_id: int,
        group_name: str,
        language: str = 'it',
        message_limit: int = 500,
        time_limit: int = 30,
    ) -> None:
        with self.get_session() as session:
            if not session.get(AuthorizedGroup, group_id):
                ag = AuthorizedGroup(
                    group_id=group_id,
                    group_name=group_name,
                    language=language,
                    message_limit=message_limit,
                    time_limit=time_limit,
                )
                session.add(ag)

    def remove_authorized_group(self, group_id: int) -> None:
        with self.get_session() as session:
            ag = session.get(AuthorizedGroup, group_id)
            if ag:
                session.delete(ag)

    def get_group_settings(self, group_id: int):
        with self.get_session() as session:
            return session.get(AuthorizedGroup, group_id)

    def get_authorized_groups(self):
        with self.get_session() as session:
            return list(session.scalars(select(AuthorizedGroup.group_id)))

    def update_group_language(self, group_id: int, language: str) -> None:
        with self.get_session() as session:
            ag = session.get(AuthorizedGroup, group_id)
            if ag:
                ag.language = language

    def get_group_language(self, group_id: int):
        with self.get_session() as session:
            ag = session.get(AuthorizedGroup, group_id)
            return ag.language if ag else 'it'

    def update_group_limits(
        self,
        group_id: int,
        message_limit: int | None = None,
        time_limit: int | None = None,
    ) -> None:
        with self.get_session() as session:
            ag = session.get(AuthorizedGroup, group_id)
            if ag:
                if message_limit is not None:
                    ag.message_limit = message_limit
                if time_limit is not None:
                    ag.time_limit = time_limit

    # Authorized users
    def add_authorized_user(self, user_id: int, first_name: str, language: str = 'it') -> None:
        logger.info("Adding user '%s'@'%s' with language '%s'", first_name, user_id, language)
        with self.get_session() as session:
            if not session.get(AuthorizedUser, user_id):
                session.add(AuthorizedUser(user_id=user_id, first_name=first_name, language=language))

    def update_user_language(self, user_id: int, first_name: str, language: str) -> None:
        logger.info("Setting language for user '%s'@'%s' to '%s'", first_name, user_id, language)
        with self.get_session() as session:
            user = session.get(AuthorizedUser, user_id)
            if user:
                user.first_name = first_name
                user.language = language

    def remove_authorized_user(self, user_id: int) -> None:
        with self.get_session() as session:
            user = session.get(AuthorizedUser, user_id)
            if user:
                session.delete(user)

    def get_authorized_users(self):
        with self.get_session() as session:
            return list(session.scalars(select(AuthorizedUser.user_id)))

    def get_user_language(self, user_id: int):
        with self.get_session() as session:
            user = session.get(AuthorizedUser, user_id)
            return user.language if user else 'it'

    # Messages
    def add_message(
        self,
        group_id: int | None,
        user_id: int,
        author_name: str,
        message_text: str,
        timestamp,
    ) -> None:
        if group_id is None:
            return
        with self.get_session() as session:
            msg = Message(
                group_id=group_id,
                user_id=user_id,
                author_name=author_name,
                message_text=message_text,
                timestamp=timestamp,
            )
            session.add(msg)

    def get_messages(self, group_id: int, limit: int | None = None, since_message_id: int | None = None):
        with self.get_session() as session:
            stmt = select(Message).where(Message.group_id == group_id)
            if since_message_id:
                stmt = stmt.where(Message.message_id >= since_message_id)
            stmt = stmt.order_by(Message.timestamp.asc())
            if limit:
                stmt = stmt.limit(limit)
            return session.scalars(stmt).all()

    def clean_null_group_messages(self) -> None:
        with self.get_session() as session:
            session.execute(delete(Message).where(Message.group_id == None))

    def clean_old_messages(self, group_id: int, all_messages: bool = False) -> None:
        settings = self.get_group_settings(group_id)
        if not settings:
            return
        message_limit = settings.message_limit
        time_limit = settings.time_limit

        with self.get_session() as session:
            if all_messages:
                session.execute(delete(Message).where(Message.group_id == group_id))
                return

            time_threshold = datetime.now() - timedelta(days=time_limit)
            session.execute(
                delete(Message).where(
                    Message.group_id == group_id,
                    Message.timestamp < time_threshold,
                )
            )
            subquery = (
                select(Message.message_id)
                .where(Message.group_id == group_id)
                .order_by(Message.timestamp.desc())
                .limit(message_limit)
                .offset(message_limit)
            )
            rows = session.scalars(subquery).all()
            if rows:
                oldest_id = rows[-1]
                session.execute(
                    delete(Message).where(
                        Message.group_id == group_id,
                        Message.message_id < oldest_id,
                    )
                )

    # Transcriptions
    def get_transcription(self, audio_hash: str):
        with self.get_session() as session:
            tr = session.get(Transcription, audio_hash)
            return tr.transcription if tr else None

    def save_transcription(self, audio_hash: str, transcription: str, group_id: int) -> None:
        with self.get_session() as session:
            tr = Transcription(
                hash=audio_hash,
                transcription=transcription,
                timestamp=datetime.now(),
                group_id=group_id,
            )
            session.add(tr)

    def clean_old_transcriptions(self, days: int) -> None:
        with self.get_session() as session:
            time_threshold = datetime.now() - timedelta(days=days)
            session.execute(
                delete(Transcription).where(Transcription.timestamp < time_threshold)
            )
