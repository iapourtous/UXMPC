FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium with all dependencies
RUN pip install playwright && \
    playwright install chromium --with-deps

# Install Playwright browsers
RUN playwright install chromium

COPY . .

# Create script to install dynamic dependencies on startup
RUN echo '#!/bin/bash\n\
if [ -f "/app/dynamic_requirements.txt" ]; then\n\
    echo "Installing dynamic dependencies..."\n\
    pip install -r /app/dynamic_requirements.txt || echo "Warning: Some dependencies failed to install"\n\
fi\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]