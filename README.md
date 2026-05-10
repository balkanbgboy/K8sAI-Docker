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
k8sai() { docker run --rm -it --network host -v /root/.kube/config:/root/.kube/config:ro -v "$(pwd)/k8s:/k8s" --env-file /root/.env balkanbgboy/k8s-ai-agent:v1.0; }
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
  balkanbgboy/k8s-ai-agent:v1.0
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
docker build -t balkanbgboy/k8s-ai-agent:v1.0 .
k8sai
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | _(required)_ | Gemini API key |
| `KUBECONFIG` | `/root/.kube/config` | Path to kubeconfig inside the container |
| `K8S_OUTPUT_DIR` | `/k8s` | Where YAML manifests are written inside the container |
| `KUBECTL` | _(auto-discovered)_ | Override kubectl binary path |

## Security Notes
- `.env` is excluded from the Docker build context via `.dockerignore` — your API key is **never** baked into the published image.
- The container runs as `root` to keep `/root/.kube/config` readable. For multi-tenant or production use, switch back to a non-root user and remount the kubeconfig under that user's home.
- The published image at `balkanbgboy/k8s-ai-agent:v1.0` carries no credentials. Verify with:
  ```bash
  docker history --no-trunc balkanbgboy/k8s-ai-agent:v1.0 | grep -iE 'api|key|secret|token'
  ```

## Troubleshooting

**`kubectl failed: ... dial tcp [::1]:8080: connection refused`**
Container isn't seeing the kubeconfig. Confirm `/root/.kube/config` exists on the host and the `-v` mount in your run command is correct.

**`[Errno 2] No such file or directory: 'kubectl'`**
You're running an old image built before kubectl was added. Rebuild: `docker build -t balkanbgboy/k8s-ai-agent:v1.0 .`.

**`API key required for Gemini Developer API`**
`/root/.env` is missing or empty. Check `cat /root/.env` — it must contain `GOOGLE_API_KEY=...`.

**The agent loops asking the same question**
The chat history must be preserved across turns. If you forked the code, ensure `chat_history` is appended after each `agent_executor.invoke(...)` call.

## Contributors
- balkanbgboy
