# Use a specific version of Python as a base image (e.g., Python 3.11)
FROM python:3.11-slim

# Set environment variables to avoid Python buffering output (useful for logging)
ENV PYTHONUNBUFFERED=1

# Install Poetry and dependencies for the installation process
RUN apt-get update && apt-get install -y curl build-essential

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH explicitly (ensure correct path to .local/bin)
ENV PATH="/root/.local/bin:$PATH"

# Verify Poetry installation
RUN which poetry && poetry --version  # Check if poetry is installed and verify its version

# Set the working directory in the container
WORKDIR /app

# Copy only the Poetry-related files first (to leverage Docker cache)
COPY pyproject.toml poetry.lock /app/

# Install the dependencies using Poetry
RUN poetry install --no-root --only main

# Copy the rest of your application code into the container
COPY . /app/

# Command to run the application using the shell form
CMD poetry run python broker.py
