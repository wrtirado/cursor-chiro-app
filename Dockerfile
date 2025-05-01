# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir ensures that pip doesn't store cache, reducing image size
# --upgrade pip ensures we have the latest pip version
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Define environment variables (if any)
# ENV MY_VARIABLE=my_value

# Command to run the application using Uvicorn
# Replace 'your_main_app_file' with the actual name of your main FastAPI file (e.g., main.py)
# Replace 'app' with the name of the FastAPI application instance in that file
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 