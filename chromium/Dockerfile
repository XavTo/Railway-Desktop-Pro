FROM accetto/ubuntu-vnc-xfce-chromium-g3@sha256:3fc2aae6067aaaf94ffd0efcb57f8490f56f06d8a5c5756f607164d4a1e7f931
USER root
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nginx openssl dbus-x11 x11-utils \
    && rm -rf /var/lib/apt/lists/* \
    && cp -a /home/headless /opt/desktop-seed \
    && chmod 644 /etc/passwd /etc/group \
    && usermod -d /config headless \
    && rm -f /dockerstartup/.initial_sudo_password
COPY entrypoint.py /opt/railway-desktop.py
ENV HOME=/config PORT=3000 VNC_RESOLUTION=1440x900 DESKTOP_APP=chromium
WORKDIR /config
ENTRYPOINT ["python3", "/opt/railway-desktop.py"]
