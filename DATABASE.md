# Database Architecture - SQLAlchemy ORM

## Overview

This project uses **SQLAlchemy ORM** for database operations, providing a robust, maintainable, and scalable database layer.

## Key Features

### ✨ Modern ORM Implementation
- **Object-Relational Mapping**: Work with Python objects instead of raw SQL
- **Database Agnostic**: Easy migration to PostgreSQL, MySQL, or other databases
- **Type Safety**: Better type checking and validation
- **Relationships**: Proper foreign key relationships between models

### 🔒 Thread-Safe Operations
- Scoped sessions for concurrent request handling
- Connection pooling for better performance
- Proper transaction management with automatic rollback

### 📊 Clean Architecture
- **Singleton Pattern**: Single database instance across the application
- **Context Managers**: Safe session handling with automatic cleanup
- **Separation of Concerns**: Models separate from business logic

## Database Models

### User
Represents users in church groups.
```python
class User(Base):
    id: int (PK)
    church_group_id: int (PK, FK)
    name: str
    surname: str
    username: str
    alias: str
    birthday: date
    admin_of: list[int]  # JSON field
```

### Church
Represents physical church locations.
```python
class Church(Base):
    id: int (PK, auto)
    admin_ids: list[int]  # JSON field
    city: str
    address: str
    country: str
    latitude: float
    longitude: float
    language: str
    description: str
```

### AuthorizedGroup
Telegram groups authorized to use the bot.
```python
class AuthorizedGroup(Base):
    group_id: int (PK)
    group_name: str
    church_id: int (FK)
    language: str
    message_limit: int
    time_limit: int
    last_cleanup: datetime
```

### AuthorizedUser
Individual users authorized for private chats.
```python
class AuthorizedUser(Base):
    user_id: int (PK)
    first_name: str
    language: str
```

### Message
Messages from groups for summarization.
```python
class Message(Base):
    message_id: int (PK, auto)
    group_id: int (FK)
    user_id: int
    author_name: str
    message_text: str
    timestamp: datetime
```

### Transcription
Cached audio transcriptions.
```python
class Transcription(Base):
    hash: str (PK)
    transcription: str
    timestamp: datetime
    group_id: int (FK)
```

## Usage Examples

### Basic Operations

```python
from database import Database

# Get database instance (singleton)
db = Database.get_instance()

# Add an authorized group
db.add_authorized_group(
    group_id=12345,
    group_name="Church Youth Group",
    language="it",
    message_limit=500,
    time_limit=30
)

# Get group settings
settings = db.get_group_settings(12345)
print(f"Language: {settings['language']}")

# Add a message
db.add_message(
    group_id=12345,
    user_id=67890,
    author_name="John",
    message_text="Hello everyone!",
    timestamp=datetime.now()
)

# Get recent messages
messages = db.get_messages(group_id=12345, limit=10)
for msg in messages:
    print(f"{msg['author_name']}: {msg['message_text']}")
```

### Advanced Operations

```python
# Add a church with location
church_id = db.add_church(
    city="Rome",
    address="Via Example 123",
    country="it",
    latitude=41.9028,
    longitude=12.4964,
    language="it",
    description="Main church"
)

# Add church admins
db.add_church_admin(church_id.id, user_id=12345)
db.add_church_admin(church_id.id, user_id=67890)

# Get all admins
admins = db.get_church_admins(church_id.id)
print(f"Church admins: {admins}")

# Clean old messages based on group settings
deleted_count = db.clean_old_messages(group_id=12345)
print(f"Deleted {deleted_count} old messages")

# Clean old transcriptions
deleted_count = db.clean_old_transcriptions(days=7)
print(f"Deleted {deleted_count} old transcriptions")
```

### Direct Session Access (Advanced)

For complex queries, you can use sessions directly:

```python
with db.get_session() as session:
    from models import AuthorizedGroup, Message
    from sqlalchemy import func
    
    # Get message count per group
    results = session.query(
        AuthorizedGroup.group_name,
        func.count(Message.message_id).label('message_count')
    ).join(Message).group_by(AuthorizedGroup.group_id).all()
    
    for group_name, count in results:
        print(f"{group_name}: {count} messages")
```

## Database Configuration

### SQLite (Default)
```python
db = Database.get_instance('sqlite:////data/bot.db')
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

## Migration from Old Implementation

The new ORM implementation is **100% backward compatible** with the old SQLite implementation. No database migration is needed - the same schema is used.

See [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) for detailed migration information.

## Best Practices

### ✅ DO

```python
# Use context managers for session handling
with db.get_session() as session:
    user = session.query(User).filter_by(id=123).first()
    user.name = "New Name"
    # Automatic commit on success

# Use provided Database methods
db.add_authorized_user(user_id, first_name, language)

# Handle exceptions properly
try:
    db.add_message(...)
except Exception as e:
    logger.error(f"Failed to add message: {e}")
```

### ❌ DON'T

```python
# Don't create sessions manually
session = db.Session()  # NO!

# Don't forget to commit
session.add(user)
# Forgot session.commit()!  # NO!

# Don't use raw SQL queries
db.engine.execute("INSERT INTO ...")  # NO!
```

## Performance Considerations

### Connection Pooling
- SQLAlchemy manages connection pooling automatically
- Connections are reused across requests
- Better performance than creating new connections

### Query Optimization
- Use `.first()` instead of `.all()[0]` for single results
- Use `.exists()` for checking existence
- Limit query results with `.limit(n)`

### Bulk Operations
```python
# Efficient bulk insert
with db.get_session() as session:
    messages = [
        Message(group_id=123, user_id=i, author_name=f"User{i}", 
                message_text="Hello", timestamp=datetime.now())
        for i in range(100)
    ]
    session.bulk_save_objects(messages)
```

## Testing

### Unit Tests
```python
import unittest
from database import Database
from models import AuthorizedGroup

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite for tests
        self.db = Database('sqlite:///:memory:')
    
    def test_add_group(self):
        group = self.db.add_authorized_group(123, "Test Group")
        self.assertEqual(group.group_id, 123)
        
    def test_get_settings(self):
        self.db.add_authorized_group(123, "Test Group", language="en")
        settings = self.db.get_group_settings(123)
        self.assertEqual(settings['language'], 'en')
```

## Troubleshooting

### Database Locked (SQLite)
SQLite has limited concurrent write support. For high-traffic bots, consider PostgreSQL.

### JSON Column Updates
When modifying JSON columns, mark them as modified:
```python
from sqlalchemy.orm.attributes import flag_modified

church.admin_ids.append(new_admin)
flag_modified(church, 'admin_ids')
```

### Memory Leaks
Always use context managers to ensure sessions are closed:
```python
with db.get_session() as session:
    # Your code here
    pass  # Session automatically closed
```

## Future Enhancements

### Potential Additions
1. **Database Migrations**: Use Alembic for schema versioning
2. **Caching Layer**: Add Redis for frequently accessed data
3. **Read Replicas**: Separate read/write databases for scaling
4. **Audit Logging**: Track all database changes
5. **Soft Deletes**: Mark records as deleted instead of removing them

### Example: Adding Alembic Migrations
```bash
pip install alembic
alembic init migrations
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Resources

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/en/20/)
- [SQLAlchemy ORM Tutorial](https://docs.sqlalchemy.org/en/20/orm/tutorial.html)
- [SQLAlchemy Best Practices](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)

## Contributing

When adding new database features:

1. Define models in `models.py`
2. Add methods to `Database` class in `database.py`
3. Document with comprehensive docstrings
4. Add unit tests
5. Update this documentation

---

**Note**: This database layer is designed to be extensible and maintainable. Follow the established patterns when adding new features.
