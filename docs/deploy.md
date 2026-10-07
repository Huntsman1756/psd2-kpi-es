# Deploying the static site

The site is fully static: `uv run psd2-kpi-es site` renders `site/dist/`
(HTML + JSON + assets) from the published dataset. Any web server that
serves files can host it; the reference setup is nginx on a VPS.

## What goes live

`deploy-site.yml` **never ingests live sources**. New data reaches
production through the review path:

1. `refresh.yml` ingests from live sources and uploads the dataset as a
   workflow artifact — a *candidate*, reviewed before accepting.
2. The accepted dataset is attached to a GitHub release:
   `observations.parquet`, `sources.parquet`, `SHA256SUMS`
   (e.g. `gh release upload <tag> data/normalized/*.parquet dist/SHA256SUMS`).
3. `deploy-site.yml` downloads those assets from a release, verifies the
   SHA-256 checksums, builds the site and deploys it.

So the site always shows a reviewed dataset version, not "whatever the
fetchers found this morning". The workflow runs on `workflow_dispatch`
(optional `dataset_ref` input; empty = latest release carrying dataset
assets) and automatically when a release is published — a release without
dataset assets redeploys the site with the latest released dataset.

## Server setup (once)

1. Point the subdomain DNS (`A`/`AAAA` record) at the VPS.
2. Create a dedicated, unprivileged deploy user — no sudo, write access
   only to the web root:
   `sudo useradd -m -s /bin/bash psd2-deploy &&
    sudo mkdir -p /var/www/psd2-kpi-es &&
    sudo chown psd2-deploy /var/www/psd2-kpi-es`
3. Install `deploy/nginx-psd2.conf` as
   `/etc/nginx/sites-available/psd2-kpi-es`, fix `server_name` and `root`,
   symlink it into `sites-enabled`, `nginx -t && systemctl reload nginx`.
   nginx only needs read access to the web root.
4. HTTPS: `sudo certbot --nginx -d <domain>`.

## GitHub configuration (once)

Secrets (repo → Settings → Secrets and variables → Actions):

| name | value |
|---|---|
| `VPS_DEPLOY_KEY` | private SSH key of `psd2-deploy` (dedicated keypair: `ssh-keygen -t ed25519`) |
| `VPS_HOST` | VPS hostname or IP |
| `VPS_DEPLOY_USER` | `psd2-deploy` |
| `VPS_HOST_KEY` | the VPS host public key as a `known_hosts` line (`<host> <keytype> <base64>`) |

Variables:

| name | value |
|---|---|
| `VPS_WEB_ROOT` | e.g. `/var/www/psd2-kpi-es` |
| `VPS_SSH_PORT` | optional, defaults to 22 |
| `SITE_URL` | e.g. `https://psd2.example.com` — post-deploy smoke test |

The footer of every generated page shows the dataset release it was built
from, so the deployed site is always traceable to a reviewed dataset.

The workflow pins the host key (`StrictHostKeyChecking=yes`) rather than
trusting whatever it finds on first connect. Get the right line from the
VPS itself — `cat /etc/ssh/ssh_host_ed25519_key.pub`, prefixed with the
hostname — and verify the fingerprint against the provider console before
storing it. Do not seed it from an unverified `ssh-keyscan`.

Authorize the deploy key's public half in
`/home/psd2-deploy/.ssh/authorized_keys`.
