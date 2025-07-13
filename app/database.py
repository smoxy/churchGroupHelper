import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim

# Enable logging
logConf = logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Nominatim init
geolocator = Nominatim(user_agent="churchLocatorBot")

# TODO: Passare ad un ORM come SQLAlchemy
class Database:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_file='/data/bot.db'):
        self.connection = sqlite3.connect(db_file, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.create_tables()

    @classmethod
    def get_instance(cls, db_file='/data/bot.db'):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_file)
        return cls._instance

    def create_tables(self):
        cursor = self.connection.cursor()

        #TODO: make a batch operation that checks birtdhay of the same user_id that are not matching the same date
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER,
                church_group_id INTEGER,
                name TEXT,
                surname TEXT DEFAULT '',
                username TEXT DEFAULT '',
                alias TEXT DEFAULT '',
                birthday DATE,
                admin_of BLOB,
                PRIMARY KEY (id, church_group_id),
                FOREIGN KEY(church_group_id) REFERENCES authorized_groups(group_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS churches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_ids BLOB,
                city TEXT,
                address TEXT DEFAULT '',
                country TEXT DEFAULT 'it',
                latitude REAL,
                longitude REAL,
                language TEXT DEFAULT 'it',
                description TEXT DEFAULT ''
            )
        ''')

        #TODO: create function to associate a church to a group
        #TODO: make a batch operation that checks if a group that is associated to a church has a language that is different from the church language, if so, asks group admin to change the language
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS authorized_groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                church_id INTEGER,
                language TEXT DEFAULT 'it',
                message_limit INTEGER DEFAULT 500,
                time_limit INTEGER DEFAULT 30,
                last_cleanup DATETIME,
                FOREIGN KEY(church_id) REFERENCES churches(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS authorized_users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                language TEXT DEFAULT 'it',
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcriptions (
                hash TEXT PRIMARY KEY,
                transcription TEXT,
                timestamp DATETIME,
                group_id INTEGER,
                FOREIGN KEY(group_id) REFERENCES authorized_groups(group_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                author_name TEXT,
                message_text TEXT,
                timestamp DATETIME,
                FOREIGN KEY(group_id) REFERENCES authorized_groups(group_id)
            )
        ''')

        self.connection.commit()

    @contextmanager
    def get_cursor(self):
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error: {e}")
            raise e
        finally:
            cursor.close()

    # Methods for users
    def add_user(self, user_id: int, church_group_id: int, name: str, surname: str='', username: str='', alias: str='', birthday=None, admin_of=None):
        logger.info(f"Adding user '{name}' '{surname}' ({alias}) with birthday '{birthday}' to church group '{church_group_id}'")
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT OR IGNORE INTO users (id, name, surname, username, alias, birthday, church_group_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, name, surname, username, alias, birthday, church_group_id))
    
    def remove_user():
        pass

    # Methods for churches
    def add_church(self, city, address='', country='it', language='it', latitude=None, longitude=None, description=''):
        logger.info(f"Adding church '{city}' with address '{address}' in '{country}' ({latitude}, {longitude})")
        if description:
            logger.info(f"Description: {description}")
        if latitude is None or longitude is None:
            logger.warning("Missing coordinates")
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO churches (city, description, address, country, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (city, description, address, country, latitude, longitude))
    
    def add_church_admin(self, church_id, user_id):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT admin_ids FROM churches WHERE id = ?
            ''', (church_id,))
            result = cursor.fetchone()
            admin_ids = result['admin_ids'] if result else []
            admin_ids.append(user_id)
            cursor.execute('''
                UPDATE churches SET admin_ids = ? WHERE id = ?
            ''', (admin_ids, church_id))
    
    def remove_church_admin(self, church_id, user_id):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT admin_ids FROM churches WHERE id = ?
            ''', (church_id,))
            result = cursor.fetchone()
            admin_ids = result['admin_ids'] if result else []
            admin_ids.remove(user_id)
            cursor.execute('''
                UPDATE churches SET admin_ids = ? WHERE id = ?
            ''', (admin_ids, church_id))
    
    def get_church_admins(self, church_id):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT admin_ids FROM churches WHERE id = ?
            ''', (church_id,))
            result = cursor.fetchone()
            return result['admin_ids'] if result else []
    
    def update_church_language(self, church_id, language):
        with self.get_cursor() as cursor:
            cursor.execute('''
                UPDATE churches SET language = ? WHERE id = ?
            ''', (language, church_id))
    
    def get_church_language(self, church_id):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT language FROM churches WHERE id = ?', (church_id,))
            result = cursor.fetchone()
            return result['language'] if result else None
    
    def update_church_location(self, church_id, latitude=None, longitude=None):
        pass
        


    # Methods for authorized groups
    def add_authorized_group(self, group_id, group_name, language='it', message_limit=500, time_limit=30):
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT OR IGNORE INTO authorized_groups (group_id, group_name, language, message_limit, time_limit)
                VALUES (?, ?, ?, ?, ?)
            ''', (group_id, group_name, language, message_limit, time_limit))

    def remove_authorized_group(self, group_id):
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM authorized_groups WHERE group_id = ?', (group_id,))

    def get_group_settings(self, group_id):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT * FROM authorized_groups WHERE group_id = ?', (group_id,))
            return cursor.fetchone()
        
    def get_authorized_groups(self):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT group_id FROM authorized_groups')
            return [gid[0] for gid in cursor.fetchall()]

    def update_group_language(self, group_id, language):
        with self.get_cursor() as cursor:
            cursor.execute('''
                UPDATE authorized_groups SET language = ? WHERE group_id = ?
            ''', (language, group_id))

    def update_group_limits(self, group_id, message_limit=None, time_limit=None):
        with self.get_cursor() as cursor:
            if message_limit is not None:
                cursor.execute('''
                    UPDATE authorized_groups SET message_limit = ? WHERE group_id = ?
                ''', (message_limit, group_id))
            if time_limit is not None:
                cursor.execute('''
                    UPDATE authorized_groups SET time_limit = ? WHERE group_id = ?
                ''', (time_limit, group_id))

    # Methods for authorized users
    def add_authorized_user(self, user_id: int, first_name: str, language: str='it'):
        logger.info(f"Adding user '{first_name}'@'{user_id}' with language '{language}'")
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT OR IGNORE INTO authorized_users (user_id, first_name, language)
                VALUES (?, ?, ?)
            ''', (user_id, first_name, language))
            
    def update_user_language(self, user_id, first_name, language):
        logger.info(f"Setting language for user '{first_name}'@'{user_id}' to '{language}'")
        with self.get_cursor() as cursor:
            cursor.execute('''
                UPDATE authorized_users SET first_name = ?, language = ? WHERE user_id = ?
            ''', (first_name, language, user_id))

    def remove_authorized_user(self, user_id):
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM authorized_users WHERE user_id = ?', (user_id,))

    def get_authorized_users(self):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT * FROM authorized_users')
            return [uid[0] for uid in cursor.fetchall()]

    def get_user_language(self, user_id):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT language FROM authorized_users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result['language'] if result else 'it'

    # Methods for messages
    def add_message(self, group_id, user_id, author_name, message_text, timestamp):
        if group_id is None:
            return
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO messages (group_id, user_id, author_name, message_text, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (group_id, user_id, author_name, message_text, timestamp))

    def get_messages(self, group_id, limit=None, since_message_id=None):
        with self.get_cursor() as cursor:
            query = 'SELECT * FROM messages WHERE group_id = ?'
            params = [group_id]
            if since_message_id:
                query += ' AND message_id >= ?'
                params.append(since_message_id)
            query += ' ORDER BY timestamp ASC'
            if limit:
                query += ' LIMIT ?'
                params.append(limit)
            cursor.execute(query, params)
            return cursor.fetchall()

    def clean_null_group_messages(self):
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM messages WHERE group_id IS NULL')

    def clean_old_messages(self, group_id, all_messages: bool=False):
        settings = self.get_group_settings(group_id)
        if not settings:
            return
        message_limit = settings['message_limit']
        time_limit = settings['time_limit']

        if all_messages:
            with self.get_cursor() as cursor:
                cursor.execute('''
                    DELETE FROM messages WHERE group_id = ?
                ''', (group_id,))
        else:
            with self.get_cursor() as cursor:
                # Delete messages older than time_limit days
                time_threshold = datetime.now() - timedelta(days=time_limit)
                cursor.execute('''
                    DELETE FROM messages WHERE group_id = ? AND timestamp < ?
                ''', (group_id, time_threshold))

                # Keep only the last message_limit messages
                cursor.execute('''
                    SELECT message_id FROM messages WHERE group_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?
                ''', (group_id, message_limit, message_limit))
                rows = cursor.fetchall()
                if rows:
                    oldest_message_id_to_keep = rows[-1]['message_id']
                    cursor.execute('''
                        DELETE FROM messages WHERE group_id = ? AND message_id < ?
                    ''', (group_id, oldest_message_id_to_keep))

    # Methods for transcriptions
    def get_transcription(self, audio_hash):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT transcription FROM transcriptions WHERE hash = ?', (audio_hash,))
            result = cursor.fetchone()
            return result['transcription'] if result else None

    def save_transcription(self, audio_hash, transcription, group_id):
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO transcriptions (hash, transcription, timestamp, group_id)
                VALUES (?, ?, ?, ?)
            ''', (audio_hash, transcription, datetime.now(), group_id))
    
    def clean_old_transcriptions(self, days):
         with self.get_cursor() as cursor:
            # Delete messages older than time_limit days
            time_threshold = datetime.now() - timedelta(days=days)
            cursor.execute('''
                DELETE FROM transcriptions WHERE timestamp < ?
            ''', (time_threshold,))
