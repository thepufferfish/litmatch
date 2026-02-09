# Deployment Roadmap

**Target Environments:**
1. **Local development** — Developer's machine, Podman Compose + Vite dev server
2. **LAN server** — Mini PC on home/office network, full Podman Compose stack

**Container Runtime:** Podman (rootless, daemonless, Fedora-native). All `podman`
and `podman compose` commands are drop-in replacements for their Docker equivalents.

**Architecture:**

```
LAN clients --> Caddy (:80) --> FastAPI backend (:8000)
                    |                    |
                    |               PostgreSQL (:5432)
                    |
                    +--> Static frontend (built React SPA)
                    +--> Dagster UI (:3000) [optional]
```

## Phase A: Local Development Improvements — DONE

**Goal:** Clean up the existing Compose workflow so `podman compose up -d`
gives a developer a working backend with health checks and proper startup ordering.

### Work Items

| Step | Item | File(s) | Priority |
|------|------|---------|----------|
| A.1 | Add `/health` endpoint to backend | `backend/app/main.py` | HIGH |
| A.2 | Create `backend/entrypoint.sh` (runtime DB init) | `backend/entrypoint.sh` | HIGH |
| A.3 | Update backend Dockerfile (entrypoint, remove build-time DB init) | `backend/Dockerfile` | HIGH |
| A.4 | Add healthchecks to all services in compose.yaml | `compose.yaml` | HIGH |
| A.5 | Bind non-public ports to 127.0.0.1 | `compose.yaml` | MEDIUM |
| A.6 | Add `depends_on` with `condition: service_healthy` | `compose.yaml` | HIGH |
| A.7 | Change `restart: always` to `restart: unless-stopped` | `compose.yaml` | LOW |
| A.8 | Create `.env.example` with documented variables | `.env.example` | HIGH |
| A.9 | Update RUNBOOK.md with health check docs | `docs/RUNBOOK.md` | MEDIUM |
| A.10 | Update CLAUDE.md with new compose commands | `CLAUDE.md` | LOW |

### Key Implementation Details

**Backend health endpoint:**
```python
@app.get("/health")
def health_check(*, session: Session = Depends(get_session)):
    session.exec(text("SELECT 1"))
    return {"status": "ok"}
```

**Backend entrypoint.sh** (moves DB init from build-time to runtime):
```bash
#!/bin/sh
set -e
python -m backend.database
exec "$@"
```

**Compose healthchecks:**
```yaml
db:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
    interval: 10s
    timeout: 5s
    retries: 5

backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 15s
    timeout: 5s
    retries: 3
    start_period: 10s
  depends_on:
    db:
      condition: service_healthy
```

### Success Criteria
- [x] `podman compose up -d` starts db, backend, scrapyd with proper startup ordering
- [x] Backend waits for healthy database before starting
- [x] `curl http://localhost:8000/health` returns `{"status": "ok"}`
- [x] `podman compose ps` shows all services as "healthy"
- [x] Frontend dev server (`npm run dev`) connects to backend via Vite proxy
- [x] `.env.example` exists and documents every required/optional variable
- [x] No secrets in `.env.example`

## Phase B: LAN Server Deployment — NOT STARTED

**Depends on:** Phase A complete (**unblocked**)

**Goal:** Full application stack accessible from any device on the local network at
`http://litmatch.local`, with automatic startup, daily backups, and a simple update procedure.

### Work Items

| Step | Item | File(s) | Priority |
|------|------|---------|----------|
| B.1 | Create `Caddyfile` (reverse proxy + SPA serving) | `Caddyfile` | HIGH |
| B.2 | Create `Containerfile.caddy` (multi-stage: build frontend + Caddy) | `Containerfile.caddy` | HIGH |
| B.3 | Add `caddy` service to compose.yaml with `server` profile | `compose.yaml` | HIGH |
| B.4 | Update `CORS_ORIGINS` in `.env` for LAN hostname | `.env` | HIGH |
| B.5 | Create database backup script | `scripts/backup-db.sh` | HIGH |
| B.6 | Create systemd service file | Server: `/etc/systemd/system/litmatch.service` | HIGH |
| B.7 | Configure Avahi/mDNS for `litmatch.local` | Server config | MEDIUM |
| B.8 | Configure firewall (only port 80 exposed) | Server config | HIGH |
| B.9 | Set up backup cron job (daily, 30-day retention) | Server crontab | HIGH |
| B.10 | Document update/redeploy procedure | `docs/RUNBOOK.md` | MEDIUM |
| B.11 | Test from LAN client (browser, different machine) | Manual | HIGH |

### Key Implementation Details

**Caddyfile:**
```caddyfile
{
    auto_https off
}

:80 {
    handle_path /api/* {
        reverse_proxy backend:8000
    }

    handle_path /dagster/* {
        reverse_proxy dagster-webserver:3000
    }

    handle {
        root * /srv/frontend
        try_files {path} /index.html
        file_server
    }
}
```

- `handle_path` strips the path prefix before proxying, matching the Vite proxy behavior
- `try_files {path} /index.html` supports React Router client-side routing
- `auto_https off` because LAN-only, no public domain

**Containerfile.caddy** (multi-stage: builds frontend + serves via Caddy):
```dockerfile
FROM node:22-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY --from=frontend-build /app/dist /srv/frontend
COPY Caddyfile /etc/caddy/Caddyfile
```

**Current state:** All services (db, backend, frontend/Nginx, scrapyd, dagster-code, dagster-webserver, dagster-daemon) run in the main compose without profiles. Phase B will add Caddy as a `server` profile service.

**Compose profiles** (planned for Phase B):
```bash
# Local dev (current: all services, frontend via Nginx on port 8080)
podman compose up -d

# LAN server (full stack with Caddy on port 80)
podman compose --profile server up -d
```

**Podman rootless setup** (one-time, enables user-level containers that survive logout):
```bash
# Enable lingering so user containers persist after logout
loginctl enable-linger $USER

# Enable and start the user-level podman socket (needed by podman compose)
systemctl --user enable --now podman.socket
```

**systemd user service** (`~/.config/systemd/user/litmatch.service`):
```ini
[Unit]
Description=LitMatch Application Stack
Requires=podman.socket
After=podman.socket network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/framework/Projects/litmatch
ExecStart=/usr/bin/podman compose --profile server up -d --remove-orphans
ExecStop=/usr/bin/podman compose --profile server down
ExecReload=/usr/bin/podman compose --profile server up -d --build --remove-orphans
TimeoutStartSec=120

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable litmatch.service
systemctl --user start litmatch.service
```

> **Note:** Podman runs rootless by default on Fedora — no `sudo` needed for
> container operations. The user-level systemd service avoids running the
> application stack as root.

**mDNS setup** (Fedora):
```bash
sudo dnf install avahi nss-mdns
sudo systemctl enable --now avahi-daemon
sudo hostnamectl set-hostname litmatch
# Clients access: http://litmatch.local
```

**Firewall:**
```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```
Non-public ports (5432, 8000, 6800, 3000) are bound to `127.0.0.1` in compose.yaml — only Caddy's port 80 is exposed to the LAN.

**Database backup** (`scripts/backup-db.sh`):
```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/home/framework/backups/litmatch"
RETAIN_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/bookdb_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

podman compose -f /home/framework/Projects/litmatch/compose.yaml \
  exec -T db pg_dump -U bookuser bookdb | gzip > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
  echo "ERROR: Backup file is empty: $BACKUP_FILE" >&2
  exit 1
fi

echo "Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

find "$BACKUP_DIR" -name "bookdb_*.sql.gz" -mtime +${RETAIN_DAYS} -delete
echo "Pruned backups older than ${RETAIN_DAYS} days"
```

Cron (daily at 4:00 AM):
```
0 4 * * * /home/framework/Projects/litmatch/scripts/backup-db.sh >> /home/framework/backups/litmatch/backup.log 2>&1
```

### Update/Redeploy Procedure

```bash
cd /home/framework/Projects/litmatch
git pull origin dev
systemctl --user reload litmatch.service
# Or: podman compose --profile server up -d --build --remove-orphans
```

### Success Criteria
- [ ] `podman compose --profile server up -d` starts all services including Caddy
- [ ] `http://litmatch.local` serves the React SPA from any LAN device
- [ ] `/api/books/` requests are proxied to the backend correctly
- [ ] `/dagster/` requests are proxied to dagster-webserver
- [ ] SPA client-side routing works (direct URL access to `/books/123`)
- [ ] Login/register/logout work through the reverse proxy (cookies set correctly)
- [ ] Only port 80 is accessible from the LAN
- [ ] System auto-starts after reboot (`systemctl --user status litmatch`)
- [ ] Daily backup runs and produces valid `.sql.gz` files
- [ ] Backups older than 30 days are automatically pruned
- [ ] Update procedure: `git pull && systemctl --user reload litmatch` works

## Phase C: Dagster Compose Integration — DONE

**Note:** Dagster services were added directly to the main compose (no profile), not behind Caddy. Caddy integration deferred to Phase B (LAN server).

### Completed

| Step | Item | File(s) | Status |
|------|------|---------|--------|
| C.1 | Dagster services in compose.yaml (code, webserver, daemon) | `compose.yaml` | DONE |
| C.2 | Health checks on all Dagster services | `compose.yaml` | DONE |
| C.3 | Startup ordering (db → code → webserver/daemon) | `compose.yaml` | DONE |
| C.4 | Dagster storage persistent volume | `compose.yaml` | DONE |
| C.5 | RUNBOOK.md with Dagster operational docs | `docs/RUNBOOK.md` | DONE |
| C.6 | Dagster-daemon depends on backend (ensures DB schema init) | `compose.yaml` | DONE |

### Deferred to Phase B
| Step | Item | Notes |
|------|------|-------|
| C.7 | Add `/dagster/*` route to Caddyfile | Requires Phase B Caddy setup |
| C.8 | Weekly schedule | Event-driven via sensors instead |

### Success Criteria
- [x] `podman compose up --build -d` starts all services including Dagster
- [x] Dagster UI accessible at http://localhost:3000
- [ ] Dagster UI accessible at `http://litmatch.local/dagster/` (requires Phase B)
- [x] Sensors trigger pipeline execution automatically
- [x] Run history preserved after container restarts

## Environment Variables Reference

| Variable | Required | Default | Used By | Notes |
|----------|----------|---------|---------|-------|
| `POSTGRES_DB` | Yes | — | Compose | Database name |
| `POSTGRES_USER` | Yes | — | Compose | Database user |
| `POSTGRES_PASSWORD` | Yes | — | Compose | Database password |
| `DATABASE_URL` | Yes | — | Backend, Dagster | Full connection string |
| `SECRET_KEY` | Yes | — | Backend | JWT signing key (`openssl rand -hex 32`) |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Backend | For LAN: `http://litmatch.local` |
| `COOKIE_SECURE` | No | `true` | Backend | Set `false` for HTTP (no TLS) |
| `REFRESH_COOKIE_PATH` | No | `/auth/refresh` | Backend | Set `/api/auth/refresh` behind proxy |
| `PROXY_TOKEN` | Yes | — | Scrapyd | Rotating proxy service token |
| `SCRAPYD_URL` | No | `http://scrapyd:6800` | Dagster | Scrapyd container address |
| `RAW_DATA_DIR` | No | `/data/raw/raw` | Dagster | Scraper output path inside container |
| `DAGSTER_HOME` | No | `/opt/dagster/dagster_home` | Dagster | Dagster storage directory |

## Architecture Decisions

### ADR-004: Caddy as Reverse Proxy
**Decision:** Use Caddy for the reverse proxy and static file serving.
**Rationale:** Simple config (~20 lines), automatic HTTPS if ever needed, built-in static file serving eliminates a separate frontend container, good defaults (HTTP/2, compression, security headers).
**Alternatives considered:** Nginx (more complex config), Traefik (overkill for static compose).

### ADR-005: Compose Profiles
**Decision:** Use profiles to support both local dev and LAN server in a single compose file. Core services have no profile (always start). Caddy uses `server` profile. Dagster uses `dagster` profile.
**Rationale:** Single source of truth, explicit activation, no override file complexity.

### ADR-007: Podman over Docker
**Decision:** Use Podman as the container runtime instead of Docker.
**Rationale:** Podman is Fedora-native (pre-installed), runs rootless by default (no daemon, no root privileges), uses the same CLI and Compose file format as Docker, and supports user-level systemd services. OCI-compatible — same images, same registries, same Containerfiles.
**Migration notes:** `docker` CLI commands map 1:1 to `podman`. `docker compose` maps to `podman compose`. Dockerfiles are valid Containerfiles. No changes to `compose.yaml` syntax are required.

### ADR-006: No TLS for LAN Deployment
**Decision:** Serve over plain HTTP on port 80.
**Rationale:** No public domain, LAN-only, trusted network. `COOKIE_SECURE=false` required. Browsers show "Not Secure" indicator (acceptable for hobby project).
**Migration path:** Add a LAN CA or Caddy self-signed certs if needed later.

## Backup and Recovery

### Backup Strategy
- **Tool:** `pg_dump` via Podman, compressed with gzip
- **Frequency:** Daily at 4:00 AM via cron
- **Retention:** 30 days
- **Location:** `/home/framework/backups/litmatch/`
- **Naming:** `bookdb_YYYYMMDD_HHMMSS.sql.gz`

### Recovery Procedure
```bash
# Stop backend to prevent writes
podman compose stop backend

# Restore from backup
gunzip -c /home/framework/backups/litmatch/bookdb_YYYYMMDD_HHMMSS.sql.gz | \
  podman compose exec -T db psql -U bookuser bookdb

# Restart backend
podman compose start backend
```

### Disaster Recovery
1. Install Fedora (or any Linux with Podman) on replacement hardware
2. Clone the repository
3. Copy `.env` from backup or recreate from `.env.example`
4. `podman compose --profile server up -d`
5. Restore database from most recent backup
6. Re-run scraper to refresh data
