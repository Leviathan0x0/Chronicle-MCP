# Use a slim Python runtime base image
FROM python:3.11-slim

# Set workspace directory inside container
WORKDIR /app

# Copy requirement manifests and scripts
COPY requirements.txt .
COPY chat_server.py .
COPY chat_core.py .
COPY split_chats.py .
COPY README.md .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the server via standard I/O streams
ENTRYPOINT ["python", "chat_server.py"]