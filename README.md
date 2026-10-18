# Railway Desktop Pro

Private **Ubuntu 24.04 XFCE desktop** and **Chromium remote browser** templates for Railway. Ubuntu uses a pinned Accetto Ubuntu/noVNC image; Chromium uses a pinned Debian base and its maintained security repository with a small process supervisor compatible with Railway's own PID 1.

Each template has one service and a persistent `/config` home. It generates a unique strong web password, exposes one authenticated HTTP port through Railway HTTPS, and includes daily and weekly volume backup schedules in the template configuration.

## Start

The repository contains `ubuntu/` and `chromium/`. Select the corresponding Railway service Root Directory and use its Dockerfile, without an extra Start Command.

- HTTP target port and `PORT`: `3000`.
- Login: `CUSTOM_USER=admin` and the generated `PASSWORD` from Railway Variables. Minimum 16 characters.
- Resolution: `VNC_RESOLUTION=1440x900`, configurable between 800x600 and 2560x1440.
- Volume: `/config`, used as the unprivileged `headless` user's entire home.
- Open the generated HTTPS domain; the noVNC client connects automatically. It supports keyboard, pointer, remote resize and clipboard text.
- Files downloaded or saved to `/config/Downloads` can also be downloaded through the authenticated `/files/` URL.
- Chromium starts with an example page. Its profile, bookmarks and history live in `/config/.config/chromium`.

## Architecture and checks

The supervisor starts TigerVNC, XFCE, noVNC/websockify and nginx. Browser and desktop processes run as `headless` (UID 1001); the initialization/proxy process starts as root. `headless` can use sudo with the generated web password, useful for temporary administration.

Only nginx listens publicly. VNC, its WebSocket relay and the health server bind to loopback. The local VNC hop has no second password; all public desktop, WebSocket, static client and download requests are protected by nginx HTTP Basic authentication with a salted password hash. Do not expose extra VNC/TCP ports.

The anonymous `/healthz` route returns only readiness, and checks the actual X display, required child processes, XFCE session and internal VNC/WebSocket ports. It returns 503 when the desktop is not ready. A stopped required process ends the container so Railway can restart it. SIGTERM is forwarded to process groups to allow profiles to close before redeploy.

Chromium uses `--disable-dev-shm-usage` for the small container shared-memory filesystem, CPU rendering, and `--no-sandbox` because the container runtime does not provide its normal desktop sandbox prerequisites. This is a private, single-session workstation; do not share access with untrusted users. There is no public browser automation/debugging API.

## Persistence and limits

Only data under `/config` survives a restart or redeploy: files, downloads, desktop settings and browser profile. Applications installed in the container's system filesystem are ephemeral; add permanent packages in the Dockerfile. First startup copies only missing home folders from the image and does not overwrite an existing profile.

This is a desktop container, not a full VM or systemd server. Sessions are shared by clients using the same login. GPU, audio/video conferencing and independent multi-user sessions are not part of these templates. Allow about 1–2 GB RAM for ordinary use; browser tabs can require more. Normal Railway usage and backup billing apply.

Use the Railway volume backup controls to restore data; changing or deleting the volume discards its files. Review image updates and back up before upgrading. Immutable image digests keep a tested upstream version reproducible; package installation during the build still receives Ubuntu repository updates.

## Sources and license

- [Accetto Ubuntu/XFCE/noVNC source](https://github.com/accetto/ubuntu-vnc-xfce-g3)
- [TigerVNC](https://tigervnc.org/)
- [noVNC](https://github.com/novnc/noVNC)

Community packaging, not affiliated with Canonical, Google, Railway or Accetto. Upstream components retain their respective licenses; this repository's wrapper and documentation are MIT licensed.
