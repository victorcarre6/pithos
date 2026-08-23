FROM node:22-bookworm-slim

ARG PI_VERSION=0.84.2

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl git python3 python3-pip python3-venv \
    && npm install --global "@earendil-works/pi-coding-agent@${PI_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENV HOME=/tmp/home
ENV PI_OFFLINE=1
ENV PI_CODING_AGENT_DIR=/tmp/pi-config

COPY entrypoint.sh /usr/local/bin/pithos-entrypoint
RUN chmod 0555 /usr/local/bin/pithos-entrypoint

ENTRYPOINT ["/usr/local/bin/pithos-entrypoint"]
