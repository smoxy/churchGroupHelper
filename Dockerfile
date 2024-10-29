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

# Install PyTorch 2.4.1 with CUDA 12.4 support
RUN pip install torch==2.4.1+cu124 torchaudio==2.4.1+cu124 --index-url https://download.pytorch.org/whl/cu124

# Install other Python dependencies
RUN pip install python-telegram-bot==21.6 python-dotenv==1.0.1 python-iso639
RUN pip install git+https://github.com/openai/whisper.git

# Copy the bot script into the container
COPY app /app

# Command to run the bot
CMD ["python", "bot.py"]
