# Deploy and Host Kali on Railway

Kali Pro Stack runs a private **Kali Linux Rolling XFCE desktop in your browser**, with a terminal, Firefox ESR and persistent personal files. Open the HTTPS address, sign in and use the desktop without installing a VNC client.

## About Hosting Kali

This is a real Kali Linux Rolling userspace built from the official distribution image. It includes XFCE, TigerVNC, noVNC and a password-protected reverse proxy. The browser communicates through HTTPS and WebSockets. Internal VNC and WebSocket listeners are bound to loopback, so there is no public raw VNC port.

A persistent Railway volume at `/config` stores the Linux user's home directory, downloads, desktop settings and Firefox profile. The runtime seeds a new profile once, preserves existing files on later starts, checks that the graphical session is ready and shuts down its child processes when Railway stops the service.

## Why choose this Kali template?

- **A complete desktop:** XFCE windows, a terminal, file manager and Firefox ESR.
- **A generated private login:** no shared public default password and no registration step.
- **Persistent personal data:** keep files, settings and browser profile under `/config`.
- **Container-aware startup:** no display manager, systemd or privileged container is required.
- **Useful readiness checks:** `/healthz` checks the display, session and required relay processes.
- **One application service:** no separate database, GPU or paid AI API key is required.

The Kali image includes Nmap, DNS tools and networking utilities. Tools that require hardware access, a custom kernel or extra host capabilities are outside this container workspace. Only use security tools on systems you are authorized to test.

## Common Use Cases

- Use a Kali desktop from a browser on another computer.
- Keep a personal Linux workspace with persistent project files.
- Run a terminal, Git and Python tools without installing them locally.
- Use an isolated Firefox profile for ordinary web tasks.
- Learn and troubleshoot Linux in an authenticated remote workspace.

## How do I access the desktop?

1. Deploy the template and wait for its healthcheck to pass.
2. Open the service's public Railway HTTPS domain.
3. Sign in with `CUSTOM_USER` (default `admin`) and the generated `PASSWORD` from Railway Variables.
4. Use the desktop and save personal files in your home directory. Download files through the protected `/files/` URL, which shows the home `Downloads` directory.

The web-login username is independent of the Linux user `headless`. The same generated password is configured for that Linux account; `sudo` asks for it when administrative access is needed.

## Frequently Asked Questions

### Is this a virtual machine?

It is a Kali Linux container with a graphical desktop. It shares the hosting platform's kernel. It does not provide a VM hypervisor, bootable ISO, full systemd host, direct USB access, GPU desktop or control of the host network.

### What survives a restart or redeploy?

Files under `/config` survive while you keep the volume. This includes the home directory and Firefox profile. System packages installed with `apt` and files elsewhere in the container are ephemeral across replacement deployments. Put reusable development tools and projects in your home directory, or extend the Dockerfile for permanent system-package changes. Persistence is not a backup: enable and verify Railway volume backups before storing important data.

### Do I need an API key?

No. The desktop and Firefox do not need an AI model or external API subscription. Railway hosting, storage and network usage are billed by Railway according to your plan and usage.

### Can I change the password or screen size?

Set `PASSWORD` and redeploy to update both the web login and Linux account password. Keep a strong password of at least 16 characters. Set `VNC_RESOLUTION`, for example `1440x900`; supported sizes range from `800x600` to `2560x1440`. Keep a single replica for this single-user persistent desktop.

### What if the browser shows a blank screen?

Wait for the service to become healthy, reload the page and check Railway runtime logs. The readiness endpoint verifies that the X display, XFCE session and private relays have started. WebSocket access must be allowed by your browser and network. Close unused heavy browser tabs if your workstation is short of memory.

## Dependencies for Kali Hosting

- Official Kali Linux Rolling container base, pinned by digest in the source Dockerfile.
- XFCE, TigerVNC, noVNC, Firefox ESR, Nginx and Python runtime supervision.
- One Railway service and a persistent `/config` volume.

This is a community template maintained by XavTo, not an official distribution-hosted service.

## Source

[Dockerfiles and runtime source](https://github.com/XavTo/Railway-Desktop-Pro/tree/debian-kali-2026-11-06/kali)
