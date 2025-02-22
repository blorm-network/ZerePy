FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

# Verify Poetry installation
RUN poetry --version


# Set working directory
WORKDIR /app

# Copy Poetry files
COPY pyproject.toml poetry.lock /app/


# Install dependencies, including the 'server' extra
RUN poetry install --no-root --with=server



# Copy application code
COPY . /app/

# Expose port
EXPOSE 8000

# Set dstack simulator endpoint
ENV DSTACK_SIMULATOR_ENDPOINT="http://tappd:8090"

# Command to run the application using app.py
CMD ["poetry","run","python", "main.py", "--server"]