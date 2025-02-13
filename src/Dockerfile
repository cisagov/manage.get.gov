FROM python:3.10

# Python 3.11 introduces a bug in oic package, fyi - Oct 31, 2022

RUN apt-get update && apt-get install -y postgresql-client

# Install Chrome dependencies
RUN apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0
    # Additional dependencies for GTK
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    libx11-xcb1 \
    libxcb1 \
    libxss1 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    wget

# Add Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Install pa11y-ci globally
RUN npm install -g pa11y-ci

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pip install pipenv
RUN pipenv sync --system --dev
