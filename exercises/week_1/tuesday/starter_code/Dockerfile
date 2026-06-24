FROM python:3.11-slim
WORKDIR /app

# Copy everything in the current directory (log_processor.py and logs.txt)
COPY . .

# Run the log processor script
CMD ["python", "log_processor.py"]
