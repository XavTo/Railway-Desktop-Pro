FROM debian@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    chromium chromium-sandbox xfce4 xfce4-terminal tigervnc-standalone-server novnc websockify \
    nginx openssl python3 dbus-x11 x11-utils xauth procps sudo ca-certificates \
    fonts-dejavu fonts-liberation xfonts-base \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1001 headless \
    && useradd -u 1001 -g 1001 -d /config -s /bin/bash headless \
    && echo 'headless ALL=(ALL:ALL) ALL' > /etc/sudoers.d/headless \
    && chmod 440 /etc/sudoers.d/headless \
    && cp -a /etc/skel /opt/desktop-seed
COPY entrypoint.py /opt/railway-desktop.py
ENV HOME=/config PORT=3000 VNC_RESOLUTION=1440x900 DESKTOP_APP=chromium NOVNC_HOME=/usr/share/novnc
WORKDIR /config
ENTRYPOINT ["python3", "/opt/railway-desktop.py"]
