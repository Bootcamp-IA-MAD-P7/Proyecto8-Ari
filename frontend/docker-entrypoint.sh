#!/bin/sh
# Resolves the Nginx config template against env vars, then starts Nginx.
# Local defaults match compose (Block 3): API_UPSTREAM=http://api:8000,
# NGINX_PORT=80. Render (Block 4) overrides both without a rebuild.
set -eu

: "${API_UPSTREAM:=http://api:8000}"
: "${NGINX_PORT:=80}"
export API_UPSTREAM NGINX_PORT

# The explicit variable list is load-bearing: without it, envsubst would
# also try to substitute every other $-prefixed token in the template
# (Nginx's own $uri, $host, $remote_addr, ...), corrupting the config.
envsubst '${API_UPSTREAM} ${NGINX_PORT}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
