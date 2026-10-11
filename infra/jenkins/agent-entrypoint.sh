#!/bin/sh
set -eu
install -m 0600 /run/secrets/agent_host_key /etc/ssh/ssh_host_ed25519_key
install -m 0644 /run/secrets/agent_host_public_key /etc/ssh/ssh_host_ed25519_key.pub
mkdir -p /home/jenkins/.ssh /var/jenkins-dispatcher
install -m 0600 /run/secrets/agent_public_key /home/jenkins/.ssh/authorized_keys
chown -R jenkins:jenkins /home/jenkins/.ssh /var/jenkins-dispatcher
chmod 0700 /home/jenkins/.ssh /var/jenkins-dispatcher
# SSH sessions do not inherit the container environment automatically.
for name in DOCKER_HOST DOCKER_TLS_VERIFY DOCKER_CERT_PATH TRUSTED_REPO_URL TRUSTED_BRANCH; do
    value=$(printenv "$name")
    case "$value" in *'"'*|*'\\'*|*' '*|*'
'*) echo "Invalid agent environment: $name" >&2; exit 1;; esac
    printf '%s=%s\n' "$name" "$value" >> /etc/environment
done
# Only the provisioned, verified host key is offered to the controller.
exec /usr/sbin/sshd -D -e -h /etc/ssh/ssh_host_ed25519_key
