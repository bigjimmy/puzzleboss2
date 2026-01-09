FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    apache2 \
    php \
    php-yaml \
    php-curl \
    php-mbstring \
    libapache2-mod-php \
    default-libmysqlclient-dev \
    default-mysql-client \
    gcc \
    pkg-config \
    supervisor \
    libldap2-dev \
    libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

# Enable Apache modules
RUN a2enmod rewrite proxy proxy_http headers

# Set working directory
WORKDIR /app

# Upgrade pip to fix CVE-2025-8869 (affects pip <= 25.2)
RUN pip install --upgrade pip>=25.3

# Copy Python requirements and install
COPY requirements.txt .
# Suppress setuptools deprecation warnings during build (they're from the packages, not our code)
ENV PYTHONWARNINGS="ignore::DeprecationWarning"
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONWARNINGS=""

# Copy application code
COPY . .

# Create default puzzleboss.yaml from sample
# This will be used if no volume mount overrides it
RUN cp puzzleboss-SAMPLE.yaml puzzleboss.yaml

# Copy Apache configuration
COPY docker/apache-site.conf /etc/apache2/sites-available/000-default.conf

# Copy supervisor configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy entrypoint script
COPY docker/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create directory for prometheus metrics
RUN mkdir -p /dev/shm/puzzleboss_prometheus && chmod 777 /dev/shm/puzzleboss_prometheus

# Expose HTTP port
EXPOSE 80

# Use supervisor to run both Apache and Gunicorn
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
