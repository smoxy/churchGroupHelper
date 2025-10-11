# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Ensure stdout/stderr are unbuffered for better logging in containers
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

# Copy requirement specification and install Python dependencies
COPY requirements.txt ./

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the bot script into the container
COPY app /app

# Command to run the bot
CMD ["python", "bot.py"]
