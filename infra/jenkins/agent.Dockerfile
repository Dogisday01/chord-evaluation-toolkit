FROM docker:cli@sha256:1a4c7cb63513f349bdad01fcc6e0f3f2f67d37b9da86f14dc0d4a0942eecda00 AS docker-cli
FROM jenkins/ssh-agent:jdk21@sha256:8298f5861edfb274bbb460f7d17a4ff14e8b73ac644b633fbe3671ad1264485f
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY agent-entrypoint.sh /usr/local/bin/chord-agent-entrypoint
RUN chmod 0755 /usr/local/bin/chord-agent-entrypoint
ENTRYPOINT ["/usr/local/bin/chord-agent-entrypoint"]
