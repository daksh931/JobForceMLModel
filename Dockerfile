# Use an official Python runtime as a base image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install gunicorn

# Expose the port Flask will run on
EXPOSE 7860

# Run the application
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]

