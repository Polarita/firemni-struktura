#!/bin/bash
set -euo pipefail
cd /home/zulip/deployments/current
module=zerver/lib/redis_utils.py
before=96183681492a8c5295fcc6588c47c4ecaaec478c12ca6f135677e2b9761a7203
after=addcc82d55a89680b0c9e3ccb50974d727753007a0e4cce20f5e1cdf751d7f42
if ! printf '%s  %s\n' "$after" "$module" | sha256sum -c --status; then
    printf '%s  %s\n' "$before" "$module" | sha256sum -c --status
    printf '%s  %s\n' "$after" /etc/polarita-zulip/redis_utils.py | sha256sum -c --status
    install -m 0644 /etc/polarita-zulip/redis_utils.py "$module"
fi
while [[ ! -s /run/secrets/pg-zulip || ! -s /run/secrets/zulip__secret_key ||
         ! -s /run/secrets/zulip__social_auth_oidc_secret || ! -f /etc/polarita-zulip/pripraveno ]]; do sleep 3; done
export SECRETS_postgres_password_FILE=/run/secrets/pg-zulip
export SETTING_EXTERNAL_HOST="$POLARITA_WEB:8444"
install -d -m 0700 -o zulip -g zulip /data/test-email
export SETTING_EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend SETTING_EMAIL_FILE_PATH=/data/test-email
export SETTING_SESSION_COOKIE_NAME=polzulipsid SETTING_CSRF_COOKIE_NAME=polzulipcsrf
export SETTING_ZULIP_ADMINISTRATOR=spravce@polarita.test
export SETTING_REMOTE_POSTGRES_HOST=10.239.33.12 SETTING_REMOTE_POSTGRES_SSLMODE=verify-full
install -d -m 0700 -o zulip -g zulip /home/zulip/.postgresql
install -m 0444 /etc/polarita-zulip/postgres.crt /home/zulip/.postgresql/root.crt
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export PGSSLROOTCERT=/etc/polarita-zulip/postgres.crt
export SETTING_REDIS_HOST=10.239.33.13 SETTING_MEMCACHED_LOCATION=10.239.32.17:11211
export SETTING_RABBITMQ_HOST=10.239.32.17 SETTING_RABBITMQ_USERNAME=zulip
export CONFIG_application_server__queue_workers_multiprocess=false CONFIG_application_server__nginx_worker_processes=1
export ZULIP_AUTH_BACKENDS=GenericOpenIdConnectBackend LOADBALANCER_IPS=10.239.31.10
export ZULIP_CUSTOM_SETTINGS="SOCIAL_AUTH_OIDC_ENABLED_IDPS = {'polarita': {'oidc_url': 'https://$POLARITA_WEB/identita/realms/polarita', 'display_name': 'Ředitelství Polarity', 'client_id': 'zulip', 'secret': get_secret('social_auth_oidc_secret'), 'auto_signup': False}}"
export AUTO_BACKUP_ENABLED=false TRUST_GATEWAY_IP=false
exec /sbin/entrypoint.sh app:run
