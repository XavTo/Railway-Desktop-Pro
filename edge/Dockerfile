FROM debian@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f
ARG EDGE_VERSION=156.0.4314.42-1
ARG EDGE_SHA256=a8642f829e105fe7a4ac440548e6fa7eb726b49fff8ffc6a27f3d0fb25a5b405
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    xfce4 xfce4-terminal tigervnc-standalone-server novnc websockify curl \
    nginx openssl python3 dbus-x11 x11-utils xauth procps sudo ca-certificates \
    fonts-dejavu fonts-liberation xfonts-base \
    && curl -fsSL --retry 3 "https://packages.microsoft.com/repos/edge/pool/main/m/microsoft-edge-stable/microsoft-edge-stable_${EDGE_VERSION}_amd64.deb" -o /tmp/edge.deb \
    && echo "${EDGE_SHA256}  /tmp/edge.deb" | sha256sum -c - \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends /tmp/edge.deb \
    && rm /tmp/edge.deb && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1001 headless \
    && useradd -u 1001 -g 1001 -d /config -s /bin/bash headless \
    && echo 'headless ALL=(ALL:ALL) ALL' > /etc/sudoers.d/headless \
    && chmod 440 /etc/sudoers.d/headless \
    && cp -a /etc/skel /opt/desktop-seed
COPY entrypoint.py /opt/railway-desktop.py
ENV HOME=/config PORT=3000 VNC_RESOLUTION=1440x900 DESKTOP_APP=edge NOVNC_HOME=/usr/share/novnc
WORKDIR /config
EXPOSE 3000
ENTRYPOINT ["python3", "/opt/railway-desktop.py"]
