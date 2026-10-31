FROM accetto/ubuntu-vnc-xfce-g3@sha256:de1b03759a37b78a62a0b4f25d1e29a54e7500bbc2101109b2430a5574e055b2
USER root
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nginx openssl dbus-x11 x11-utils xfce4-notifyd tumbler \
    && rm -rf /var/lib/apt/lists/* \
    && cp -a /home/headless /opt/desktop-seed \
    && chmod 644 /etc/passwd /etc/group \
    && usermod -d /config headless \
    && rm -f /dockerstartup/.initial_sudo_password
COPY entrypoint.py /opt/railway-desktop.py
COPY runtime_checks.py configure_defaults.py /opt/
RUN python3 /opt/configure_defaults.py
ENV HOME=/config PORT=3000 VNC_RESOLUTION=1440x900
WORKDIR /config
ENTRYPOINT ["python3", "/opt/railway-desktop.py"]
