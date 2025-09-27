FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PTY support and SSH
RUN apt-get update && apt-get install -y \
    bash \
    openssh-client \
    sshpass \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements from webapp directory
COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules from root directory
COPY database/ ./database/
COPY security/ ./security/
COPY ssh/ ./ssh/
COPY ui/ ./ui/
COPY config.py ./config.py

# Copy webapp specific files
COPY webapp/ ./

# Create data directory for database
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////app/data/ssh_connections.db

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]