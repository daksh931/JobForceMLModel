# Use an official Python runtime as a base image
FROM python:3.9

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the .env file (ensure it's not ignored by .gitignore)
COPY .env /app/.env

# Expose the port Flask will run on
EXPOSE 7860

# Run the application
CMD ["python", "app.py"]
