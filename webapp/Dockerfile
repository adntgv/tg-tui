FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PTY support and SSH
RUN apt-get update && apt-get install -y \
    bash \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements first for better caching
COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules from parent directory
COPY database/ ./database/
COPY security/ ./security/
COPY ssh/ ./ssh/
COPY config.py ./config.py

# Copy webapp specific files
COPY webapp/ ./

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]