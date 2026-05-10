# Kubernetes AI Agent

A Python AI agent powered by Google Gemini that creates Kubernetes Deployments and Services via natural language. The agent generates the YAML manifests, persists them to disk, and applies them to your cluster via `kubectl`.

## Features
- Natural-language deployment and service creation
- Namespace-aware: agent always asks for the target namespace and auto-creates it if it doesn't exist
- Manifests saved as YAML files on the host (auditable, reapplyable, committable)
- `kubectl` baked into the image — no client install required on the host
- Multi-stage Docker build (~734 MB)
- Conversation history maintained across turns

## Prerequisites
- Docker
- A running Kubernetes cluster you can administer (kubeadm, EKS, k3s, etc.)
- `/root/.kube/config` (or another readable kubeconfig) on the host
- A Google Gemini API key

## Setup on EC2 (one time)

**1. Make sure root has a working kubeconfig** (kubeadm example):
```bash
mkdir -p /root/.kube
cp /etc/kubernetes/admin.conf /root/.kube/config
chown root:root /root/.kube/config
kubectl get nodes   # should list your nodes
```

**2. Drop your Gemini key in `/root/.env`:**
```bash
echo 'GOOGLE_API_KEY=your_key_here' > /root/.env
chmod 600 /root/.env
```

**3. Add a `k8sai` shortcut to your shell** (so you don't retype the full `docker run` line every time):
```bash
cat >> /root/.bashrc << 'EOF'
k8sai() { docker run --rm -it --network host -v /root/.kube/config:/root/.kube/config:ro -v "$(pwd)/k8s:/k8s" --env-file /root/.env balkanbgboy/k8s-ai-agent:latest; }
EOF
source /root/.bashrc
```

## Run

From any directory on EC2:
```bash
k8sai
```

Manifests are written to `./k8s/` (relative to wherever you ran `k8sai`).

### Full command (what `k8sai` expands to)

```bash
docker run --rm -it --network host \
  -v /root/.kube/config:/root/.kube/config:ro \
  -v "$(pwd)/k8s:/k8s" \
  --env-file /root/.env \
  balkanbgboy/k8s-ai-agent:latest
```

| Flag | Why |
|---|---|
| `--network host` | Container reaches the cluster API server on the host network |
| `-v /root/.kube/config:/root/.kube/config:ro` | Cluster credentials |
| `-v "$(pwd)/k8s:/k8s"` | Manifests persist to the host's `./k8s/` folder |
| `--env-file /root/.env` | Loads `GOOGLE_API_KEY` at runtime (never baked into the image) |

## Usage

Before creating any deployment or service, the agent **always asks which namespace to use** — `default` or a different one. If you pick a different namespace, it asks for the name and creates it automatically before applying the workload.

### Default namespace
```
🤖 Kubernetes AI Agent Initialized

💡 What should I do? (or 'exit'): create a deployment named web-app with nginx image and 3 replicas
Agent: Should I deploy this to the 'default' namespace or a different one?

💡 default
Agent Output:
 Saved manifest: /k8s/web-app-deployment.yaml
 deployment.apps/web-app created
```

### Custom namespace (auto-created)
```
💡 create a service for web-app on port 80 type NodePort
Agent: Should I create this in the 'default' namespace or a different one?

💡 different
Agent: What is the name of the namespace?

💡 staging
Agent Output:
 Namespace manifest: /k8s/staging-namespace.yaml
 namespace/staging created
 Saved manifest: /k8s/web-app-svc-service.yaml
 service/web-app-svc created
```

The agent supports:
- **Deployments** — `create a deployment named <name> with <image> image and <n> replicas`
- **Services** — `create a service for <name> on port <port> type <ClusterIP|NodePort|LoadBalancer>`
- **Namespaces** — auto-created on demand whenever a non-default namespace is chosen

You can also volunteer the namespace upfront, e.g. `create a deployment named web-app with nginx in the staging namespace` — the agent will still confirm before applying.

After a successful run, the manifests sit in `./k8s/` and can be reapplied with plain `kubectl apply -f ./k8s/` (kubectl applies in alphabetical order, and namespace creation is idempotent, so the whole stack is safe to reapply).

## Build Locally

```bash
git clone https://github.com/balkanbgboy/k8s-ai-agent
cd k8s-ai-agent
docker build -t balkanbgboy/k8s-ai-agent:latest .
k8sai
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | _(required)_ | Gemini API key |
| `KUBECONFIG` | `/root/.kube/config` | Path to kubeconfig inside the container |
| `K8S_OUTPUT_DIR` | `/k8s` | Where YAML manifests are written inside the container |
| `KUBECTL` | _(auto-discovered)_ | Override kubectl binary path |

## CI/CD

The repo ships with three GitHub Actions workflows:

| Workflow | Triggers | What it does |
|---|---|---|
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Every push/PR to `master` | Lint with ruff, run unit tests, build the Docker image, scan with Trivy |
| [`.github/workflows/e2e.yml`](.github/workflows/e2e.yml) | Every PR + manual dispatch | Spin up a `kind` cluster, install dependencies, run pytest E2E tests against the cluster |
| [`.github/workflows/release.yml`](.github/workflows/release.yml) | Tag push matching `v*.*.*` | Build a multi-arch (amd64+arm64) image, push to Docker Hub with `vX.Y.Z`, `vX.Y`, and `latest` tags, and create a GitHub Release |

### When does the image get published to Docker Hub?

**Only when you push a git tag matching `v*.*.*`.** Pushing changes to `master` (including Dockerfile changes) only runs CI — it builds the image to verify the build works, but does **not** publish it. This is intentional: you decide when to cut a release.

| You do this | What happens |
|---|---|
| `git push origin master` (with Dockerfile/code changes) | CI runs: lint, tests, Docker build, Trivy scan. **No publish.** |
| `git push origin v1.2.3` (tag matching `v*.*.*`) | Release runs: multi-arch build, push to Docker Hub as `:v1.2.3` + `:v1.2` + `:latest`, create GitHub Release. |
| Open a PR to `master` | CI + E2E runs. **No publish.** |

So the typical workflow after changing the Dockerfile is:

```bash
git add Dockerfile
git commit -m "Bump kubectl to v1.37.0"
git push origin master            # CI verifies the build
git tag v1.1.1                    # cut a release
git push origin v1.1.1            # NOW the new image lands on Docker Hub
```

### One-time setup: Docker Hub secrets

The release workflow needs credentials to push to Docker Hub.

**1. Create an access token** (do **not** use your account password):
- Log into https://hub.docker.com → your avatar → **Account Settings** → **Personal access tokens** → **Generate new token**.
- Description: `github-actions-k8sai`. Permissions: **Read & Write**.
- Copy the token — Hub only shows it once.

**2. Add the secrets to GitHub:**
- Go to https://github.com/balkanbgboy/K8sAI-Docker/settings/secrets/actions
- Click **New repository secret** twice and add:
  - `DOCKERHUB_USERNAME` → `balkanbgboy`
  - `DOCKERHUB_TOKEN` → the token from step 1

### Cutting a release

```bash
git tag v1.1.0
git push origin v1.1.0
```

The release workflow runs, publishes `balkanbgboy/k8s-ai-agent:v1.1.0`, `:v1.1`, and `:latest` to Docker Hub, and creates a GitHub Release page with auto-generated notes.

### Running tests locally

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -m "not e2e"          # unit tests only
pytest -m e2e                # integration tests (need a real cluster on $KUBECONFIG)
```

## Security Notes
- `.env` is excluded from the Docker build context via `.dockerignore` — your API key is **never** baked into the published image.
- The container runs as `root` to keep `/root/.kube/config` readable. For multi-tenant or production use, switch back to a non-root user and remount the kubeconfig under that user's home.
- The published image at `balkanbgboy/k8s-ai-agent:latest` carries no credentials. Verify with:
  ```bash
  docker history --no-trunc balkanbgboy/k8s-ai-agent:latest | grep -iE 'api|key|secret|token'
  ```

## Troubleshooting

**`kubectl failed: ... dial tcp [::1]:8080: connection refused`**
Container isn't seeing the kubeconfig. Confirm `/root/.kube/config` exists on the host and the `-v` mount in your run command is correct.

**`[Errno 2] No such file or directory: 'kubectl'`**
You're running an old image built before kubectl was added. Rebuild: `docker build -t balkanbgboy/k8s-ai-agent:latest .`.

**`API key required for Gemini Developer API`**
`/root/.env` is missing or empty. Check `cat /root/.env` — it must contain `GOOGLE_API_KEY=...`.

**The agent loops asking the same question**
The chat history must be preserved across turns. If you forked the code, ensure `chat_history` is appended after each `agent_executor.invoke(...)` call.

## Contributors
- balkanbgboy
