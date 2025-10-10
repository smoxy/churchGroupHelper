# Church Group Helper Bot - Setup Instructions

## Quick Start

### Prerequisites
- Python 3.12+
- Docker & Docker Compose (for containerized deployment)
- Git

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd churchGroupHelper
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   
   # Install PyTorch with CUDA (if you have NVIDIA GPU)
   pip install torch==2.4.1+cu124 torchaudio==2.4.1+cu124 --index-url https://download.pytorch.org/whl/cu124
   
   # Or PyTorch CPU-only (if no GPU)
   pip install torch torchaudio
   
   # Install Whisper
   pip install git+https://github.com/openai/whisper.git
   ```

4. **Create environment file**:
   Create a `.env` file in the root directory:
   ```env
   TOKEN=your_telegram_bot_token_here
   ADMINS=123456789,987654321
   OPENAI_API_KEY=your_openai_key_here  # Optional, for summarization
   ```

5. **Run the bot**:
   ```bash
   python app/bot.py
   ```

### Docker Deployment (Recommended)

1. **Build and start services**:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

2. **View logs**:
   ```bash
   docker-compose logs -f
   ```

3. **Stop services**:
   ```bash
   docker-compose down
   ```

## Database Setup

The bot automatically creates the SQLite database at `/data/bot.db` on first run. No manual setup is required!

### Database Migration from Old Version

If you're upgrading from the old SQLite implementation:

1. **Your existing database is compatible!** No migration needed.
2. The new ORM uses the same schema as before.
3. Simply update the code and restart the bot.

For detailed migration information, see [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md).

## Architecture

### Project Structure
```
churchGroupHelper/
├── app/
│   ├── bot.py              # Main bot logic
│   ├── database.py         # SQLAlchemy ORM database layer
│   ├── models.py           # Database models
│   ├── transcription.py    # Audio transcription logic
│   ├── utils.py            # Utility functions
│   ├── church_menu.py      # Church management functions
│   └── database_old.py     # Backup of old implementation
├── compose.yaml            # Docker Compose configuration
├── Dockerfile              # Docker image definition
├── requirements.txt        # Python dependencies
├── MIGRATION_GUIDE.md      # Migration documentation
├── DATABASE.md             # Database architecture docs
└── README.md               # Project overview
```

### Technology Stack
- **Framework**: python-telegram-bot 21.6
- **ORM**: SQLAlchemy 2.0.36
- **Database**: SQLite (default) / PostgreSQL (production)
- **AI**: OpenAI Whisper (audio transcription)
- **Geocoding**: GeoPy + Nominatim

## Features

### Current Features
- ✅ Audio transcription (voice messages, audio files, video notes)
- ✅ Multi-language support
- ✅ Group message collection and management
- ✅ Transcription caching (avoid re-processing same audio)
- ✅ Authorized users and groups management
- ✅ Church location management with geocoding
- ✅ Automatic message cleanup based on group settings

### Planned Features
- 🚧 Message summarization with AI
- 🚧 Church member management
- 🚧 Birthday reminders
- 🚧 Event management
- 🚧 Multi-church support

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TOKEN` | Telegram bot token | Yes | - |
| `ADMINS` | Comma-separated admin user IDs | Yes | - |
| `OPENAI_API_KEY` | OpenAI API key for summarization | No | - |

### Bot Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/start` | Show welcome message | All |
| `/addgroup` | Authorize a group | Admin only |
| `/removegroup` | Remove group authorization | Admin only |
| `/adduser` | Authorize a user | Admin only |
| `/removeuser` | Remove user authorization | Admin only |
| `/setlanguage <code>` | Set transcription language | Group admin / User |
| `/setlimits <msg> <days>` | Set message limits | Admin only |
| `/summarize [n]` | Summarize last n messages | Authorized users |

### Supported Languages

The bot supports all languages available in OpenAI Whisper:
- Italian (it)
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- And 90+ more...

## Development

### Adding New Features

1. **Database Changes**:
   - Add models to `models.py`
   - Add methods to `database.py`
   - See [DATABASE.md](DATABASE.md) for examples

2. **Bot Commands**:
   - Add handler functions in `bot.py`
   - Register handlers in `main()`

3. **Testing**:
   ```bash
   # Run with test database
   python app/bot.py
   ```

### Database Operations

```python
from database import Database

db = Database.get_instance()

# Add authorized group
db.add_authorized_group(
    group_id=12345,
    group_name="My Group",
    language="it"
)

# Get messages
messages = db.get_messages(group_id=12345, limit=10)

# Clean old data
db.clean_old_messages(group_id=12345)
db.clean_old_transcriptions(days=7)
```

See [DATABASE.md](DATABASE.md) for comprehensive documentation.

## Troubleshooting

### Common Issues

#### "Module not found: sqlalchemy"
```bash
pip install sqlalchemy==2.0.36
```

#### "CUDA not available"
This is normal if you don't have an NVIDIA GPU. The bot will use CPU for transcription (slower but works).

#### "Database is locked"
SQLite limitation with concurrent writes. Consider PostgreSQL for production:
```python
db = Database.get_instance('postgresql://user:pass@localhost/dbname')
```

#### "Transcription taking too long"
- Ensure you have CUDA installed for GPU acceleration
- Use smaller audio files
- Consider using a more powerful server

### Logs

View logs for debugging:
```bash
# Docker
docker-compose logs -f

# Local
# Logs are printed to console
```

## Performance

### Resource Usage
- **Memory**: 2-4 GB (with Whisper model loaded)
- **GPU**: Recommended for fast transcription
- **Disk**: ~1 GB for Whisper model + database

### Optimization Tips
1. Enable GPU for Whisper (10-20x faster)
2. Use PostgreSQL for production (better concurrency)
3. Set appropriate message limits to reduce database size
4. Regular cleanup of old transcriptions

## Security

### Best Practices
1. **Never commit `.env` file** to version control
2. **Restrict admin access** to trusted users only
3. **Use strong database passwords** for PostgreSQL
4. **Regular backups** of `/data/bot.db`
5. **Update dependencies** regularly

### Data Privacy
- Audio files are not stored (deleted after transcription)
- Transcriptions are cached for 7 days (configurable)
- Messages are limited by group settings
- User data is minimal (only IDs and names)

## Deployment

### Docker (Recommended)

```yaml
# compose.yaml
version: '3.8'
services:
  bot:
    build: .
    volumes:
      - ./data:/data
    env_file:
      - .env
    restart: unless-stopped
```

### Systemd Service (Linux)

```ini
[Unit]
Description=Church Group Helper Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/churchbot
ExecStart=/opt/churchbot/venv/bin/python /opt/churchbot/app/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Backup and Restore

### Backup Database
```bash
# SQLite
cp /data/bot.db /backup/bot.db.$(date +%Y%m%d)

# Docker
docker cp churchbot:/data/bot.db ./backup/
```

### Restore Database
```bash
# SQLite
cp /backup/bot.db.20250101 /data/bot.db

# Docker
docker cp ./backup/bot.db churchbot:/data/bot.db
docker-compose restart
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

See [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for database migration
- Read [DATABASE.md](DATABASE.md) for database architecture

---

**Happy Bot Building! 🤖⛪**
