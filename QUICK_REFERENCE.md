# SQLAlchemy ORM - Quick Reference

## Quick Start

```python
from database import Database

# Get database instance (singleton)
db = Database.get_instance()

# All operations use this instance
```

## Common Operations

### Authorized Groups

```python
# Add group
db.add_authorized_group(
    group_id=12345,
    group_name="My Church Group",
    language="it",
    message_limit=500,
    time_limit=30
)

# Get group settings
settings = db.get_group_settings(12345)
# Returns: {'group_id': 12345, 'group_name': '...', 'language': 'it', ...}

# Update language
db.update_group_language(12345, "en")

# Update limits
db.update_group_limits(12345, message_limit=1000, time_limit=60)

# Get all authorized groups
groups = db.get_authorized_groups()  # Returns list of group IDs

# Remove group
db.remove_authorized_group(12345)
```

### Authorized Users

```python
# Add user
db.add_authorized_user(
    user_id=67890,
    first_name="John",
    language="it"
)

# Get user language
lang = db.get_user_language(67890)  # Returns: 'it'

# Update user language
db.update_user_language(67890, "John", "en")

# Get all authorized users
users = db.get_authorized_users()  # Returns list of user IDs

# Remove user
db.remove_authorized_user(67890)
```

### Churches

```python
# Add church
church = db.add_church(
    city="Rome",
    address="Via Example 123",
    country="it",
    language="it",
    latitude=41.9028,
    longitude=12.4964,
    description="Main church location"
)

# Add admin to church
db.add_church_admin(church.id, user_id=67890)

# Get church admins
admins = db.get_church_admins(church.id)  # Returns list of admin IDs

# Remove admin
db.remove_church_admin(church.id, user_id=67890)

# Get/Update church language
lang = db.get_church_language(church.id)
db.update_church_language(church.id, "en")
```

### Users in Church Groups

```python
# Add user to church group
user = db.add_user(
    user_id=67890,
    church_group_id=12345,
    name="John",
    surname="Doe",
    username="johndoe",
    alias="JD",
    birthday=datetime(1990, 1, 15).date()
)

# Remove user from church group
db.remove_user(user_id=67890, church_group_id=12345)
```

### Messages

```python
from datetime import datetime

# Add message
db.add_message(
    group_id=12345,
    user_id=67890,
    author_name="John",
    message_text="Hello everyone!",
    timestamp=datetime.now()
)

# Get messages
messages = db.get_messages(
    group_id=12345,
    limit=10,  # Optional: limit number of messages
    since_message_id=100  # Optional: get messages from this ID onwards
)
# Returns list of dicts: [{'message_id': ..., 'author_name': ..., 'message_text': ..., ...}, ...]

# Clean old messages (based on group settings)
deleted_count = db.clean_old_messages(group_id=12345)

# Delete ALL messages from a group
deleted_count = db.clean_old_messages(group_id=12345, all_messages=True)

# Clean messages with null group_id
deleted_count = db.clean_null_group_messages()
```

### Transcriptions

```python
# Save transcription
db.save_transcription(
    audio_hash="abc123def456",
    transcription="This is the transcribed text",
    group_id=12345  # Optional
)

# Get transcription (from cache)
text = db.get_transcription("abc123def456")
# Returns: "This is the transcribed text" or None

# Clean old transcriptions
deleted_count = db.clean_old_transcriptions(days=7)
```

## Advanced Usage

### Direct Session Access

For complex queries:

```python
with db.get_session() as session:
    from models import AuthorizedGroup, Message
    from sqlalchemy import func
    
    # Complex query example
    results = session.query(
        AuthorizedGroup.group_name,
        func.count(Message.message_id).label('count')
    ).join(Message).group_by(AuthorizedGroup.group_id).all()
    
    for name, count in results:
        print(f"{name}: {count} messages")
    
    # Automatic commit on success, rollback on error
```

### Accessing Relationships

```python
with db.get_session() as session:
    from models import AuthorizedGroup
    
    # Get group with relationships
    group = session.query(AuthorizedGroup).filter_by(group_id=12345).first()
    
    # Access related church
    if group.church:
        print(f"Church: {group.church.city}")
    
    # Access related messages
    for msg in group.messages:
        print(f"{msg.author_name}: {msg.message_text}")
```

### Bulk Operations

```python
with db.get_session() as session:
    from models import Message
    from datetime import datetime
    
    # Bulk insert
    messages = [
        Message(
            group_id=12345,
            user_id=i,
            author_name=f"User{i}",
            message_text=f"Message {i}",
            timestamp=datetime.now()
        )
        for i in range(100)
    ]
    session.bulk_save_objects(messages)
```

## Database Configuration

### SQLite (Default)
```python
db = Database.get_instance('sqlite:////data/bot.db')
```

### In-Memory (Testing)
```python
db = Database('sqlite:///:memory:')
```

### PostgreSQL (Production)
```python
db = Database.get_instance(
    'postgresql://user:password@localhost:5432/churchbot'
)
```

### MySQL
```python
db = Database.get_instance(
    'mysql+pymysql://user:password@localhost/churchbot'
)
```

## Common Patterns

### Check if Entity Exists

```python
# Check if group exists
settings = db.get_group_settings(12345)
if settings:
    print("Group exists")
else:
    print("Group not found")

# Check if user is authorized
users = db.get_authorized_users()
if user_id in users:
    print("User is authorized")
```

### Safe Operations with Try-Except

```python
try:
    db.add_message(
        group_id=12345,
        user_id=67890,
        author_name="John",
        message_text="Hello",
        timestamp=datetime.now()
    )
except Exception as e:
    logger.error(f"Failed to add message: {e}")
    # Automatic rollback happens
```

### Conditional Updates

```python
# Update only if group exists
if db.get_group_settings(12345):
    db.update_group_language(12345, "en")
else:
    print("Group not found")
```

## Return Types

| Method | Returns |
|--------|---------|
| `add_authorized_group()` | `AuthorizedGroup` object |
| `add_authorized_user()` | `AuthorizedUser` object |
| `add_church()` | `Church` object |
| `add_user()` | `User` object |
| `add_message()` | `Message` object or `None` |
| `save_transcription()` | `Transcription` object |
| `get_group_settings()` | `dict` or `None` |
| `get_authorized_groups()` | `list[int]` |
| `get_authorized_users()` | `list[int]` |
| `get_messages()` | `list[dict]` |
| `get_transcription()` | `str` or `None` |
| `get_user_language()` | `str` (default: 'it') |
| `get_church_language()` | `str` or `None` |
| `get_church_admins()` | `list[int]` |
| `clean_*()` | `int` (count deleted) |
| `remove_*()` | `bool` (success) |
| `update_*()` | `bool` (success) |

## Models Quick Reference

### Import Models
```python
from models import User, Church, AuthorizedGroup, AuthorizedUser, Message, Transcription
```

### Model Attributes

**User**: `id`, `church_group_id`, `name`, `surname`, `username`, `alias`, `birthday`, `admin_of`

**Church**: `id`, `admin_ids`, `city`, `address`, `country`, `latitude`, `longitude`, `language`, `description`

**AuthorizedGroup**: `group_id`, `group_name`, `church_id`, `language`, `message_limit`, `time_limit`, `last_cleanup`

**AuthorizedUser**: `user_id`, `first_name`, `language`

**Message**: `message_id`, `group_id`, `user_id`, `author_name`, `message_text`, `timestamp`

**Transcription**: `hash`, `transcription`, `timestamp`, `group_id`

## Best Practices

✅ **Always use context managers**
```python
with db.get_session() as session:
    # operations here
```

✅ **Use provided Database methods**
```python
db.add_authorized_group(...)  # Good
# Don't write raw SQL
```

✅ **Handle exceptions properly**
```python
try:
    db.add_message(...)
except Exception as e:
    logger.error(f"Error: {e}")
```

✅ **Check for None returns**
```python
settings = db.get_group_settings(12345)
if settings:  # Check before using
    print(settings['language'])
```

❌ **Don't create sessions manually**
```python
session = db.Session()  # NO!
```

❌ **Don't forget to handle None**
```python
settings = db.get_group_settings(12345)
print(settings['language'])  # Can crash if settings is None!
```

## Debugging

### Enable SQL Logging

```python
# In database.py, change:
self.engine = create_engine(
    db_url,
    echo=True  # Shows all SQL queries
)
```

### Check Active Connections

```python
print(db.engine.pool.status())
```

### Manual Cleanup

```python
db.Session.remove()  # Close all sessions
db.engine.dispose()  # Close all connections
```

## Migration from Old Code

### Before (Old SQLite)
```python
cursor.execute('SELECT * FROM authorized_groups WHERE group_id = ?', (12345,))
result = cursor.fetchone()
language = result['language'] if result else 'it'
```

### After (SQLAlchemy ORM)
```python
settings = db.get_group_settings(12345)
language = settings['language'] if settings else 'it'
```

Much cleaner! ✨

---

## Need More Help?

- **Full Documentation**: [DATABASE.md](DATABASE.md)
- **Migration Guide**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **Setup Instructions**: [SETUP.md](SETUP.md)
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org/

---

**Happy Coding! 🚀**
