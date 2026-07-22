# SigDoc Backup Script

`backup.sh` takes a daily snapshot of both stateful services in the SigDoc
stack:

- **Postgres**: `pg_dump` of the `sigdoc` database, gzip-compressed, written
  to `/opt/docker/backups/sigdoc/pg_<date>.sql.gz`.
- **MinIO**: mirrors the `templates` and `documents` buckets into
  `/opt/docker/backups/sigdoc/minio/` using a disposable `minio/mc`
  container attached to the app's Docker network (no extra dependencies
  needed on the host).

It also rotates Postgres dumps older than 7 days. MinIO mirrors are
incremental (`mc mirror --overwrite` only transfers changed/new objects), so
no separate rotation is applied there.

Credentials are read directly from `/opt/docker/apps/sigdoc/.env` on the
droplet — the script must run on the same host as the SigDoc stack.

## Cron setup

Install for the `devrafaseros` user (`crontab -e`):

```cron
30 3 * * * /opt/docker/apps/sigdoc/infra/backup/backup.sh >> /opt/docker/backups/sigdoc/backup.log 2>&1
```

This runs daily at 03:30 server time, after typical low-traffic hours.

## Restore

**Postgres:**

```bash
gunzip -c /opt/docker/backups/sigdoc/pg_2026-07-06.sql.gz \
  | docker exec -i sigdoc-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

**MinIO** (mirror the local backup back into the running buckets):

```bash
SIGDOC_NETWORK=$(docker network ls --format '{{.Name}}' | grep sigdoc-network | head -1)

docker run --rm \
  --network "$SIGDOC_NETWORK" \
  -v /opt/docker/backups/sigdoc/minio:/backup \
  --entrypoint /bin/sh \
  minio/mc:RELEASE.2025-08-13T08-35-41Z \
  -c "
    mc alias set sigdoc http://minio:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD';
    mc mirror --overwrite /backup/templates sigdoc/templates;
    mc mirror --overwrite /backup/documents sigdoc/documents;
  "
```

## Off-droplet copy (recommended)

`/opt/docker/backups/sigdoc` lives on the same droplet as the data it backs
up — a disk failure or accidental `rm -rf` takes out both. Copy backups
off-box regularly, for example:

- Enable **DigitalOcean Droplet Backups** (weekly snapshots of the whole
  disk), and/or
- Sync `/opt/docker/backups/sigdoc` to a **DigitalOcean Spaces** bucket with
  `rclone` or `s3cmd` (Spaces is S3-compatible) on the same cron schedule,
  right after `backup.sh` finishes.

Either option is enough to survive a total loss of the droplet, which is
exactly what happened to the previous Contabo VPS.

## Downloadable bundle (`backup-bundle.sh` + `fetch-backup.sh`)

`backup.sh` keeps rolling backups **on the droplet**. When you want a single
portable copy on your own machine — for cold storage, or to measure how much
data you would pay to store off-site — use the bundle scripts instead.

**On the droplet**, `backup-bundle.sh` writes ONE self-contained archive to
`/opt/docker/backups/sigdoc/bundles/sigdoc-backup_<timestamp>.tar.gz`
containing the Postgres dump, both MinIO buckets, and a `MANIFEST.txt`. It
keeps the newest 5 bundles and prints a size breakdown, e.g.:

```
================= SigDoc backup bundle =================
 Postgres dump   : 12M
 MinIO templates : 340M (128 objects)
 MinIO documents : 2.1G (4530 objects)
 -------------------------------------------------------
 Bundle (.tar.gz): 2.3G
========================================================
```

That bundle size is the number to weigh against a paid target — e.g.
DigitalOcean Spaces is ~US$5/mo for 250 GB (S3-compatible).

**From your machine**, `fetch-backup.sh` downloads the newest bundle over SSH:

```bash
# Download the newest existing bundle:
SIGDOC_SSH=deploy@your-droplet ./infra/backup/fetch-backup.sh

# Or generate a fresh one on the droplet first, then download it:
SIGDOC_SSH=deploy@your-droplet ./infra/backup/fetch-backup.sh --run
```

It saves into `./sigdoc-backups/` (override with `SIGDOC_BACKUP_DIR`). The ssh
user needs docker access on the droplet only when using `--run`.

### Restore from a bundle

```bash
tar -xzf sigdoc-backup_<timestamp>.tar.gz          # -> postgres/ minio/ MANIFEST.txt

# Postgres:
gunzip -c postgres/pg_<timestamp>.sql.gz \
  | docker exec -i sigdoc-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# MinIO: same as the "Restore" section above, pointing at the extracted
# minio/templates and minio/documents directories.
```
