FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python scripts
COPY convert_claude.py .
COPY convert_chatgpt.py .
COPY convert_grok.py .
COPY create_sql.py .

# Create output directory
RUN mkdir -p /app/output

# Set volume for input/output
VOLUME ["/data"]

# Default command shows help
CMD ["python", "create_sql.py", "--help"]
