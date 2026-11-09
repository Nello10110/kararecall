# Docker images and updates

[🇫🇷 Français](../IMAGES-DOCKER.md) · [🇬🇧 English](docker-images.md)

Public Linux AMD64/ARM64 images:

- `ghcr.io/nello10110/kararecall-web:latest`
- `ghcr.io/nello10110/kararecall-worker:latest`

No GitHub account is needed to pull them. Images contain code, not private bookmarks, media or credentials.

## Existing Compose or Dockhand stack

For each KaraRecall service, remove the complete `build:` section, replace `image:` and replace `pull_policy: build` with `pull_policy: always`:

```yaml
services:
  recall:
    image: ghcr.io/nello10110/kararecall-web:latest
    pull_policy: always
  recall_worker:
    image: ghcr.io/nello10110/kararecall-worker:latest
    pull_policy: always
```

This is only an image-selection example. Retain your actual service names, environment, volumes, networks, reverse proxy and resource limits. Keep the existing storage volume and `.env`. Do not modify unrelated Karakeep services.

Remove any `command:` overrides that repeat the standard startup so each image can supply its default command. Images from version 0.6.1 also support the original `/app/web_server.py` and `/app/worker.py` paths.

In Dockhand, request new images and redeploy both KaraRecall services. With the example names:

```sh
docker compose config -q
docker compose pull recall recall_worker
docker compose up -d --no-deps recall recall_worker
```

The repository Compose uses names `web` and `worker`; substitute those when using it. Restarting alone does not fetch an image. `latest` does not change a running container automatically.

## Publication and pinning

CI runs Python, JavaScript, media, MCP and Compose checks. Successful pushes to `main` publish both architecture variants with `sha-FULL_COMMIT` tags. Only after both images build does CI promote the tested pair to `latest`, provided the commit is still the main head. The two registry promotions are sequential, not one atomic registry transaction. A shared commit tag pins a reproducible pair:

```dotenv
KARARECALL_IMAGE_TAG=sha-FULL_COMMIT
```

Use the exact published full SHA, not the placeholder. Update both services together and verify their reported versions. Keep a tested backup and previous tag for recovery.

## Local builds and custom UID/GID

```sh
docker compose -f compose.yaml -f deploy/compose.build.yaml up -d --build
```

The first Compose file defines the project root; the development override builds from that root. Published images use UID/GID 10001:10001. Custom `PUID`/`PGID` values apply to local builds only. Do not change ownership of unrelated NAS data. [Homelab configuration](homelab.md) · [Repository layout](repository.md).
