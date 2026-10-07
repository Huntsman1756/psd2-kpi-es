# Deploying the static site

The site is fully static: `uv run psd2-kpi-es site` renders `site/dist/`
(HTML + JSON + assets) from the published dataset. Any web server that
serves files can host it; the reference setup is nginx on a VPS.

## Server setup (once)

1. Point the subdomain DNS (`A`/`AAAA` record) at the VPS.
2. Create the web root, owned by the deploy user:
   `sudo mkdir -p /var/www/psd2-kpi-es && sudo chown <deploy-user> /var/www/psd2-kpi-es`
3. Install `deploy/nginx-psd2.conf` as
   `/etc/nginx/sites-available/psd2-kpi-es`, fix `server_name` and `root`,
   symlink it into `sites-enabled`, `nginx -t && systemctl reload nginx`.
4. HTTPS: `sudo certbot --nginx -d <domain>`.

## GitHub configuration (once)

Secrets (repo → Settings → Secrets and variables → Actions):

| name | value |
|---|---|
| `VPS_DEPLOY_KEY` | private SSH key of a deploy user allowed to write the web root |
| `VPS_HOST` | VPS hostname or IP |
| `VPS_DEPLOY_USER` | SSH user |

Variables:

| name | value |
|---|---|
| `VPS_WEB_ROOT` | e.g. `/var/www/psd2-kpi-es` |
| `VPS_SSH_PORT` | optional, defaults to 22 |

On the VPS, authorize the key's public half in the deploy user's
`~/.ssh/authorized_keys`. A dedicated keypair is recommended:
`ssh-keygen -t ed25519 -f psd2-deploy`.

## Running

`deploy-site.yml` runs monthly (day 6, after the data refresh) and on
`workflow_dispatch`. It ingests from live sources, builds the site, stores
`site/dist/` as a build artifact, and rsyncs it with `--delete` to the web
root. The ingest step fails the run on real ingestion errors;
`SOURCE_NOT_FOUND` is reported but tolerated (see `scripts/ingest_all.sh`).
