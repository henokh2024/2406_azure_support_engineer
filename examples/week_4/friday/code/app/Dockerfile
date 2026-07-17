FROM python:3.10-slim

WORKDIR /app

# Install dependencies directly to keep it simple and single-contained
RUN pip install --no-cache-dir fastapi uvicorn requests

# Copy the python script into the container
COPY demo_alerts_config.py .

# Expose the port the FastAPI app runs on
EXPOSE 8000

# Execute the application
CMD ["python", "demo_alerts_config.py"]
