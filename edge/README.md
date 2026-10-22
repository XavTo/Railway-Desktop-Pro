# Microsoft Edge on Railway

A private Microsoft Edge desktop in your browser, with generated password authentication and a persistent browser profile. Uses the official Microsoft stable Linux package, pinned by version and SHA-256, on a pinned Debian base.

## Features

- Full Edge GUI over HTTPS and noVNC; no local desktop client required.
- Password protection on the desktop, WebSocket and download directory.
- Persistent `/config`: Edge profile, bookmarks, extensions, browsing history and downloads.
- `/files/` provides an authenticated download listing for `/config/Downloads`.
- Separate desktop user; VNC and WebSocket backends bind to loopback only.
- Health checks verify X11, XFCE and all required processes. Supervision exits on a failed child process and handles Railway shutdown signals.
- Single replica, a Railway volume, restart on failure and a 30-second drain period.

## First connection

Deploy, open the generated HTTPS domain, and use `CUSTOM_USER` (default `admin`) with the generated `PASSWORD` from Railway variables. A password of at least 16 characters is required. The OS user is `headless`; sudo uses the same generated password.

Change `VNC_RESOLUTION` to a value between `800x600` and `2560x1440`. Defaults to `1440x900`. `TZ` defaults to `Europe/Paris`. Mount the volume at `/config`; do not scale this profile across replicas. Enable Railway volume backups after deployment.

## Browser isolation

Railway containers cannot provide the normal Chromium OS sandbox, so the desktop launches Edge with `--no-sandbox`. This is a private single-user workstation: do not expose it without authentication, share it with untrusted users, or attach sensitive cloud credentials. Browser updates require a new pinned image deployment. This project is independent of Microsoft and Railway.

## Local use

Build with Docker, provide a strong `PASSWORD`, publish port 3000 behind HTTPS and persist `/config` in a volume. The browser has no public remote-debugging port.
