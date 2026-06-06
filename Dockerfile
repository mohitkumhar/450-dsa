# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Run the application using Gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1
