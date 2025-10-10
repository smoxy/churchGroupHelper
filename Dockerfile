# Use the official Python 3.12 slim image
FROM python:3.12

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        wget \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies
RUN pip install "python-telegram-bot[job-queue]==21.6" python-dotenv==1.0.1 python-iso639 geopy requests==2.32.3 ollama

# Install SQLAlchemy for ORM
RUN pip install sqlalchemy==2.0.36

# Copy the bot script into the container
COPY app /app

# Command to run the bot
CMD ["python", "bot.py"]
