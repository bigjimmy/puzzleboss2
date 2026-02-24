#!/bin/bash
# Cloud-init: Prometheus (with native ECS SD), Node Exporter, Loki, Grafana,
#             Apache (phpMyAdmin, legacy scripts, mailman archives)
# Template vars: loki_s3_bucket, aws_region, project_name, ecs_cluster,
#                rds_endpoint, rds_username, rds_password, legacy_web_bucket
set -euo pipefail
exec > /var/log/observability-init.log 2>&1
export DEBIAN_FRONTEND=noninteractive

echo "=== Observability stack init ==="

# Move SSH to non-standard port
sed -i 's/^#\?Port .*/Port 3748/' /etc/ssh/sshd_config
systemctl restart ssh

# System packages
apt-get update
apt-get install -y apt-transport-https software-properties-common wget curl unzip jq

# AWS CLI (for S3 sync of legacy web content)
if ! command -v aws &> /dev/null; then
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o /tmp/awscliv2.zip
    unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install
    rm -rf /tmp/aws /tmp/awscliv2.zip
fi

# --- Prometheus ---
PROM_VERSION="3.9.1"
useradd --no-create-home --shell /bin/false prometheus || true
mkdir -p /etc/prometheus /var/lib/prometheus
wget -q "https://github.com/prometheus/prometheus/releases/download/v$${PROM_VERSION}/prometheus-$${PROM_VERSION}.linux-arm64.tar.gz" -O /tmp/prometheus.tar.gz
tar xzf /tmp/prometheus.tar.gz -C /tmp
cp /tmp/prometheus-*/prometheus /tmp/prometheus-*/promtool /usr/local/bin/
chown prometheus:prometheus /usr/local/bin/prometheus /usr/local/bin/promtool
chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus

cat > /etc/prometheus/prometheus.yml <<PROMEOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s
scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
  - job_name: 'loki'
    static_configs:
      - targets: ['localhost:3100']
  # Flask REST API metrics (prometheus_flask_exporter) — port 5000
  # Uses ECS task ID for stable-but-unique instance labels so that:
  #   - Multiple tasks (scale-up) produce distinct series
  #   - Stale series from replaced tasks auto-expire (5min staleness)
  #   - Dashboard queries should use sum/rate by (job) to aggregate across tasks
  - job_name: 'puzzleboss_api'
    aws_sd_configs:
      - role: ecs
        region: ${aws_region}
        port: 5000
        refresh_interval: 30s
    relabel_configs:
      - source_labels: [__meta_ecs_service]
        regex: puzzleboss
        action: keep
      - source_labels: [__meta_ecs_ip_address]
        target_label: __address__
        replacement: $${1}:5000
      - source_labels: [__meta_ecs_service]
        target_label: service
      - source_labels: [__meta_ecs_cluster]
        target_label: cluster
      # Use short task ID (first 8 chars) for readable instance labels
      # e.g. "puzzleboss-a1b2c3d4" instead of "172.31.41.47:5000"
      - source_labels: [__meta_ecs_task_arn]
        regex: '.*/(.{8}).*'
        target_label: instance
        replacement: 'puzzleboss-$${1}:5000'
  # PHP hunt metrics (puzzles, solves, activity, botstats) — port 80
  # These are database-derived gauges identical across all instances,
  # so a fixed instance label is fine — if scaled to 2+, Prometheus
  # deduplicates targets and scrapes only one (no data loss).
  - job_name: 'puzzleboss_app'
    aws_sd_configs:
      - role: ecs
        region: ${aws_region}
        port: 80
        refresh_interval: 30s
    metrics_path: /pb/metrics.php
    relabel_configs:
      - source_labels: [__meta_ecs_service]
        regex: puzzleboss
        action: keep
      - source_labels: [__meta_ecs_service]
        target_label: service
      - source_labels: [__meta_ecs_cluster]
        target_label: cluster
    metric_relabel_configs:
      - target_label: instance
        replacement: puzzleboss:80
PROMEOF
chown prometheus:prometheus /etc/prometheus/prometheus.yml

cat > /etc/systemd/system/prometheus.service <<EOF
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target
[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \\
  --config.file=/etc/prometheus/prometheus.yml \\
  --storage.tsdb.path=/var/lib/prometheus \\
  --storage.tsdb.retention.time=30d \\
  --web.listen-address=:9090
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# --- Node Exporter ---
NODE_EXP_VERSION="1.7.0"
useradd --no-create-home --shell /bin/false node_exporter || true
wget -q "https://github.com/prometheus/node_exporter/releases/download/v$${NODE_EXP_VERSION}/node_exporter-$${NODE_EXP_VERSION}.linux-arm64.tar.gz" -O /tmp/node_exporter.tar.gz
tar xzf /tmp/node_exporter.tar.gz -C /tmp
cp /tmp/node_exporter-*/node_exporter /usr/local/bin/
chown node_exporter:node_exporter /usr/local/bin/node_exporter

cat > /etc/systemd/system/node_exporter.service <<EOF
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target
[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# --- Loki (S3 backend) ---
LOKI_VERSION="3.0.0"
useradd --no-create-home --shell /bin/false loki || true
mkdir -p /etc/loki /var/lib/loki
wget -q "https://github.com/grafana/loki/releases/download/v$${LOKI_VERSION}/loki-linux-arm64.zip" -O /tmp/loki.zip
unzip -o /tmp/loki.zip -d /usr/local/bin/
mv /usr/local/bin/loki-linux-arm64 /usr/local/bin/loki || true
chmod +x /usr/local/bin/loki
chown loki:loki /usr/local/bin/loki
chown -R loki:loki /etc/loki /var/lib/loki

cat > /etc/loki/loki.yml <<LOKIEOF
auth_enabled: false
server:
  http_listen_port: 3100
common:
  path_prefix: /var/lib/loki
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory
schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: s3
      schema: v13
      index:
        prefix: index_
        period: 24h
storage_config:
  tsdb_shipper:
    active_index_directory: /var/lib/loki/tsdb-index
    cache_location: /var/lib/loki/tsdb-cache
  aws:
    s3: s3://${aws_region}/${loki_s3_bucket}
    region: ${aws_region}
limits_config:
  retention_period: 90d
  discover_log_levels: false
compactor:
  working_directory: /var/lib/loki/compactor
  retention_enabled: true
  delete_request_store: s3
LOKIEOF
chown loki:loki /etc/loki/loki.yml

cat > /etc/systemd/system/loki.service <<EOF
[Unit]
Description=Loki
Wants=network-online.target
After=network-online.target
[Service]
User=loki
Group=loki
Type=simple
ExecStart=/usr/local/bin/loki -config.file=/etc/loki/loki.yml
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# --- Grafana ---
wget -q -O /usr/share/keyrings/grafana.key https://apt.grafana.com/gpg.key
echo "deb [signed-by=/usr/share/keyrings/grafana.key] https://apt.grafana.com stable main" > /etc/apt/sources.list.d/grafana.list
apt-get update && apt-get install -y grafana

# Serve under /metrics path (behind ALB), anonymous Viewer access
sed -i 's|;root_url = .*|root_url = %(protocol)s://%(domain)s/metrics/|' /etc/grafana/grafana.ini
sed -i 's|;serve_from_sub_path = .*|serve_from_sub_path = true|' /etc/grafana/grafana.ini
# Enable anonymous access — visitors get read-only Viewer role, admin actions still require login
sed -i '/^\[auth\.anonymous\]/,/^\[/ s/;enabled = false/enabled = true/' /etc/grafana/grafana.ini

# Use RDS MySQL for Grafana state (dashboards, users, etc.) instead of local SQLite.
# This preserves dashboards across instance rebuilds.
RDS_HOST=$(echo "${rds_endpoint}" | cut -d: -f1)
sed -i '/^\[database\]/,/^\[/ {
  s/;type = sqlite3/type = mysql/
  s/;host = .*/host = '"$${RDS_HOST}"':3306/
  s/;name = grafana/name = grafana/
  s/;user = root/user = ${rds_username}/
  s/;password =/password = ${rds_password}/
}' /etc/grafana/grafana.ini

# Datasources (Prometheus, Loki, CloudWatch) are stored in the RDS grafana database.
# No file-based provisioning — avoids conflicts with DB-stored datasource definitions.
# To add/edit datasources, use the Grafana UI (admin login) or update RDS directly.
mkdir -p /etc/grafana/provisioning/datasources
chown -R grafana:grafana /etc/grafana/provisioning

# Dashboard provisioning directory (import dashboards via UI or drop JSON files here)
mkdir -p /etc/grafana/provisioning/dashboards /var/lib/grafana/dashboards
cat > /etc/grafana/provisioning/dashboards/default.yml <<DBEOF
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: 'Puzzleboss'
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
DBEOF
chown -R grafana:grafana /var/lib/grafana/dashboards

# --- Apache + PHP + phpMyAdmin (serves legacy web content on port 80) ---
echo "phpmyadmin phpmyadmin/dbconfig-install boolean false" | debconf-set-selections
echo "phpmyadmin phpmyadmin/reconfigure-webserver multiselect apache2" | debconf-set-selections
apt-get install -y apache2 libapache2-mod-php php-mysql php-mbstring php-json php-curl phpmyadmin
a2enmod cgi

# Point phpMyAdmin at RDS (RDS_HOST extracted earlier in Grafana database config)
cat > /etc/phpmyadmin/conf.d/rds.php <<'PMAEOF'
<?php
$cfg['Servers'][1]['host'] = 'RDS_HOST_PLACEHOLDER';
$cfg['Servers'][1]['port'] = '3306';
$cfg['Servers'][1]['connect_type'] = 'tcp';
PMAEOF
sed -i "s|RDS_HOST_PLACEHOLDER|$${RDS_HOST}|" /etc/phpmyadmin/conf.d/rds.php

# Health check endpoint for ALB
mkdir -p /var/www/html
echo "OK" > /var/www/html/health

# Apache vhost: phpMyAdmin, scripts, mailman archives
cat > /etc/apache2/sites-available/legacy.conf <<'APEOF'
<VirtualHost *:80>
    ServerName localhost
    DocumentRoot /var/www/html

    Alias /phpmyadmin /usr/share/phpmyadmin
    <Directory /usr/share/phpmyadmin>
        Require all granted
    </Directory>

    Alias /scripts /var/www/scripts
    <Directory /var/www/scripts>
        Options Indexes FollowSymLinks ExecCGI
        AddHandler cgi-script .cgi .pl .py
        Require all granted
    </Directory>
    ScriptAlias /scripts/cgi-bin/ /var/www/scripts/cgi-bin/

    Alias /mailmanarchives /var/www/mailmanarchives
    <Directory /var/www/mailmanarchives>
        Options Indexes FollowSymLinks
        Require all granted
    </Directory>
</VirtualHost>
APEOF

a2dissite 000-default || true
a2ensite legacy
mkdir -p /var/www/scripts /var/www/mailmanarchives

# Download legacy content from S3 (uploaded from old EC2 instance)
aws s3 sync "s3://${legacy_web_bucket}/scripts/" /var/www/scripts/ --region "${aws_region}" || echo "WARN: scripts not yet uploaded to S3"
aws s3 sync "s3://${legacy_web_bucket}/mailmanarchives/" /var/www/mailmanarchives/ --region "${aws_region}" || echo "WARN: mailmanarchives not yet uploaded to S3"

# --- Start all services ---
systemctl daemon-reload
systemctl enable --now prometheus node_exporter loki grafana-server apache2

rm -rf /tmp/prometheus* /tmp/node_exporter* /tmp/loki*
echo "=== Observability init complete ==="
echo "Grafana: http://localhost:3000 (admin/admin) | Prometheus: :9090 | Loki: :3100"
echo "Apache: http://localhost:80 (phpMyAdmin, /scripts, /mailmanarchives)"
echo "Note: ECS logs reach Loki via Fluent Bit FireLens sidecars in each ECS task"
