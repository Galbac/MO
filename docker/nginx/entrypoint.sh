#!/bin/sh
set -eu

render_config() {
    if [ "${ENABLE_SSL:-false}" = "true" ] && [ -f "${SSL_CERT_PATH}" ] && [ -f "${SSL_KEY_PATH}" ]; then
        envsubst '${NGINX_SERVER_NAME} ${SSL_CERT_PATH} ${SSL_KEY_PATH}' \
            < /etc/nginx/templates/default.https.conf.template \
            > /etc/nginx/conf.d/default.conf
    else
        envsubst '${NGINX_SERVER_NAME}' \
            < /etc/nginx/templates/default.http.conf.template \
            > /etc/nginx/conf.d/default.conf
    fi
}

reload_loop() {
    while :; do
        sleep "${NGINX_RELOAD_INTERVAL_SECONDS:-21600}"
        render_config
        nginx -s reload || true
    done
}

render_config
reload_loop &
exec nginx -g 'daemon off;'
