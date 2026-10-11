# Docker and local Jenkins

This setup runs the existing CLI and its tests in Linux containers. It needs Docker Desktop in Linux-container mode with a working WSL2 engine on Windows, or Docker Engine and Compose on Linux. Reserve approximately 6 GB for Docker and allow outbound GitHub, PyPI, and Docker Hub access. The existing GitHub Actions matrix still covers native Windows behavior.

## Build the application

From the repository root, run:

```powershell
docker build --target test -t chord-eval-test:local .
docker run --rm --network none chord-eval-test:local
docker build --target runtime --build-arg VCS_REF=$(git rev-parse HEAD) -t chord-eval:local .
docker run --rm --network none chord-eval:local --help
```

The test target installs the built wheel and development dependencies. The runtime target installs only the wheel and its pinned runtime dependencies; it runs as UID 10001. Source files, tests, examples, host virtual environments, and Jenkins secrets are absent from the runtime image. The base image is pinned by registry digest. Change pins deliberately and rerun the checks when updating them.

To run a calculation without relying on host bind mounts, explicitly copy input into a stopped container and copy reports out after it exits:

```powershell
New-Item -ItemType Directory -Force reports | Out-Null
docker create --name chord-local-example --network none chord-eval:local evaluate /tmp/examples/reference.lab /tmp/examples/prediction.lab --output /tmp/example.json --html /tmp/example.html
docker cp examples chord-local-example:/tmp/examples
docker start --attach chord-local-example
docker cp chord-local-example:/tmp/example.json reports/example.json
docker cp chord-local-example:/tmp/example.html reports/example.html
docker rm chord-local-example
```

Use a new container and output names for each run. Both root and major/minor scores in this ten-second example must equal 0.8. The application keeps its existing invalid-input and no-overwrite protections.

## Provision Jenkins

`infra/jenkins/compose.yaml` creates three services: an authenticated Jenkins LTS controller with zero executors, a dedicated SSH agent with two executors, and a separate privileged Docker-in-Docker builder. Two executors allow the dispatcher to wait while the worker runs. Docker traffic uses client TLS on the Compose bridge network; the daemon has no published host ports. The UI is published only at `127.0.0.1:8080`. The bridge allows outbound downloads. The controller has no Docker socket or Docker CLI.

This is a local trusted-code environment. The privileged builder and agent can execute project code and are not a sandbox for arbitrary pull requests. Run only branches you control. Jenkins uses CSRF protection and authenticated access; account signup and anonymous read are disabled. Agent SSH host-key verification uses the provisioned public host key.

Before starting, publish the infrastructure commit to the trusted branch. Prepare the following local files under `infra/jenkins/secrets/`, which is excluded from Git and both Docker build contexts:

| File | Content |
| --- | --- |
| `admin_password.txt` | Random administrator password, at least 24 characters |
| `agent_key` and `agent_key.pub` | Ed25519 SSH login private/public key pair, no passphrase |
| `agent_host_key` and `agent_host_key.pub` | Separate Ed25519 SSH server host private/public key pair, no passphrase |

On Windows use `infra/jenkins/bootstrap-secrets.ps1` to create them without printing credentials. It refuses to overwrite an existing setup. Keep the directory private to your Windows account. The admin username is `admin`; retrieve the password privately from `admin_password.txt` when signing in. Do not include these files, Jenkins home, TLS certificates, or Docker volumes in the submission archive.

```powershell
./infra/jenkins/bootstrap-secrets.ps1
Copy-Item infra/jenkins/.env.example infra/jenkins/.env
docker compose -f infra/jenkins/compose.yaml config --quiet
docker compose -f infra/jenkins/compose.yaml up --build -d
docker compose -f infra/jenkins/compose.yaml ps
```

Edit `.env` before starting if the repository or trusted pipeline branch differs. Defaults are the public project repository and `main`. The repository must be a public GitHub HTTPS URL; private repositories need a separate reviewed SCM credential configuration. Initialization reads local Docker secrets, configures authentication and the agent, and creates `chord-evaluation-worker` and `chord-evaluation-dispatcher` as Pipeline-from-SCM jobs. Pipeline definitions always come from the trusted control branch.

Open [local Jenkins](http://localhost:8080/) and wait until `docker-agent` is online. Check the builder from the agent:

```powershell
docker compose -f infra/jenkins/compose.yaml exec --user jenkins agent docker version
```

Build `chord-evaluation-dispatcher` once to initialize its Pipeline parameters, timer, and baseline. Its `TRACKED_BRANCH` defaults to the configured trusted branch. The selected tracking branch is retained for later timer runs and controller restarts. To switch branches, disable the timer in the job configuration, wait for the active dispatcher build and cancel any queued dispatcher builds, then use Build with Parameters with the new branch; that run reinstalls the timer. This prevents an already queued timer with old parameters from reverting the selection. Afterward the timer polls every minute while this computer, Docker, and Jenkins are running. No public webhook is needed.

## Each commit and each result

The dispatcher reads a durable branch-specific JSON state from `/var/jenkins-dispatcher` on the agent's named volume. Its first poll queues current HEAD as the baseline. Later polls enumerate every new commit in ancestry order and wait for one parameterized worker per SHA. Two pushes between polls therefore create separate worker runs. Failed worker results are recorded as processed so the fixing revision can run. A restart retains queued commits and results. An interrupted dispatcher may repeat a pending worker: delivery is at least once, and the SHA remains visible in its build.

Force pushes or diverged histories fail explicitly. Review the history and choose a new baseline deliberately; do not silently discard the state. To reset a branch, disable the dispatcher timer, stop or wait for its active build, and back up its state JSON in `/var/jenkins-dispatcher` under a different name through the agent. The next poll without the original state file initializes from current HEAD. Existing completed-build history remains in Jenkins and the backup. Each tracked branch has its own state file, with `/` encoded as `%`.

The worker validates `COMMIT_SHA` and `TRACKED_BRANCH`, fetches that branch from the configured repository, checks ancestry, and checks out the exact revision. An empty SHA builds current HEAD of the selected branch. Its stages are checkout, test-image build, Ruff plus pytest, runtime-image build, and runtime smoke checks. Runtime builds occur only after successful checks. Image tags contain the full SHA and Jenkins build number, and the OCI revision label identifies the commit.

Pytest JUnit XML and Ruff/pytest logs are copied from the test container even on failure and archived in Jenkins. Successful workers also archive image metadata, Docker version, checked SHA, JSON/HTML for the known-answer and real MIREX scenarios. Runtime checks verify non-root execution, both 0.8 metrics, input hashes, code provenance, a complete three-record real comparison, HTML output, invalid-input rejection, and no-overwrite behavior. Containers have no network access for these runs; `docker cp` transfers data/results across the remote builder boundary. Jobs remove only their own named containers.

## Evidence and persistence

Capture real builds rather than treating configuration as proof of execution. Retain the successful stage view, JUnit page, worker console and artifacts; then track a separate demonstration branch, push a deliberately incorrect calculation, capture the automatic failed worker with runtime stages skipped, fix it, and capture the next automatic successful worker. Push two commits before a polling interval and confirm separate SHA-labelled workers. Retain a repeat build and a Compose restart check.

```powershell
docker compose -f infra/jenkins/compose.yaml restart
docker compose -f infra/jenkins/compose.yaml ps
docker compose -f infra/jenkins/compose.yaml down
```

The named volumes preserve controller configuration/artifacts, the agent workspace, dispatcher state, Docker images, and client certificates across `restart` and `down`. Do not add `--volumes` unless deliberately deleting the entire local Jenkins setup. The init script reapplies the declared authentication, agent, and job SCM configuration on restart; environment changes require recreation with `up -d`.

`plugins.txt` pins the requested plugins and their required dependency closure resolved from the official update center. `jenkins-plugin-cli --latest=false` installs that list. Save an inventory from the running controller when collecting evidence, because detached plugins from the base image may also be present. Base image digests and plugin versions were selected on 11 October 2026.

References: [Jenkins Docker installation](https://www.jenkins.io/doc/book/installing/docker/), [Pipeline syntax](https://www.jenkins.io/doc/book/pipeline/syntax/), [official SSH agent image](https://github.com/jenkinsci/docker-ssh-agent), [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/), and [Docker copy command](https://docs.docker.com/reference/cli/docker/container/cp/).
