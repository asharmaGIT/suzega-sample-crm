FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY generate_data.py .
COPY schema.sql .

# Use ENTRYPOINT so arguments can be passed
ENTRYPOINT ["python", "generate_data.py"]

# Default arguments (can be overridden)
CMD []
