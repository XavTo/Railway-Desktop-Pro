FROM library/debian@sha256:7378260c0a098d27ac206225db5e7d92b8c7c84ea7afccc86eeb513756bbd392
ARG DEBIAN_FRONTEND=noninteractive
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d \
    && apt-get update && apt-get install -y --no-install-recommends xfce4 xfce4-terminal xfce4-notifyd tumbler tigervnc-standalone-server tigervnc-common novnc websockify nginx openssl python3 python3-venv python3-pip dbus-x11 x11-utils xauth procps sudo tini firefox-esr ca-certificates curl wget git jq unzip iproute2 iputils-ping dnsutils netcat-openbsd fonts-dejavu-core at-spi2-core desktop-base librsvg2-common \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1001 --create-home --home-dir /config --shell /bin/bash --groups sudo headless \
    && install -d /opt/desktop-seed /config /tmp/.X11-unix /tmp/.ICE-unix \
    && cp -a /etc/skel/. /opt/desktop-seed/ \
    && chmod 1777 /tmp/.X11-unix /tmp/.ICE-unix \
    && chmod 644 /etc/passwd /etc/group
COPY entrypoint.py /opt/railway-desktop.py
COPY runtime_checks.py configure_defaults.py /opt/
RUN python3 /opt/configure_defaults.py
ENV HOME=/config PORT=3000 VNC_RESOLUTION=1440x900 NOVNC_HOME=/usr/share/novnc LANG=C.UTF-8
WORKDIR /config
EXPOSE 3000
ENTRYPOINT ["/usr/bin/tini", "--", "python3", "/opt/railway-desktop.py"]
