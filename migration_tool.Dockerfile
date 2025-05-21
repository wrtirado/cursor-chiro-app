FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the migration script
COPY migrate.py .

# Make the script executable (optional, depending on how you run it)
RUN chmod +x migrate.py

# Command to run migrations, e.g., apply all pending migrations.
# This can be overridden when running the container.
# Example: CMD ["python", "migrate.py", "up"]
# For now, let's set a default that can be easily overridden or just provide an entrypoint.
ENTRYPOINT ["python", "migrate.py"] 