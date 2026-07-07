# Traefik Reverse Proxy

Shared Traefik v3 instance that terminates TLS for all apps on this droplet
and routes traffic to them over the external `traefik-public` Docker
network. It is deployed once per server, independently of any single app's
compose stack (see `docker-compose.prod.yml` at the repo root for how SigDoc
attaches to it via labels).

## First-time setup on a fresh server

1. Create the external network Traefik and the apps share:

   ```bash
   docker network create traefik-public
   ```

2. Create the ACME storage directory and file with restrictive permissions
   (Traefik refuses to start if `acme.json` is not `600`):

   ```bash
   mkdir -p ./letsencrypt
   touch ./letsencrypt/acme.json
   chmod 600 ./letsencrypt/acme.json
   ```

3. Create `.env` in this directory with your certificate contact email:

   ```bash
   cat > .env <<'EOF'
   # Email address used by Let's Encrypt for certificate issuance and expiry notices.
   LE_EMAIL=admin@example.com
   EOF
   # edit .env and set LE_EMAIL to a real address you control
   ```

   Note: an `.env.example` template could not be checked into the repo from
   this environment (sandbox denies writes to any `.env*` filename); the
   content above is exactly what such a template would contain.

4. Start Traefik:

   ```bash
   docker compose up -d
   ```

Traefik will pick up any container on `traefik-public` that has
`traefik.enable=true` labels and request a Let's Encrypt certificate for it
automatically via the `letsencrypt` cert resolver (HTTP-01 challenge on the
`web` entrypoint). Plain HTTP requests on port 80 are permanently redirected
to HTTPS on port 443.

No dashboard or API is exposed — this stack only does routing and TLS
termination.
