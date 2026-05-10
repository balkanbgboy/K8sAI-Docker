# --- Build stage: compile any wheels that need a toolchain ---
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LO "https://dl.k8s.io/release/v1.36.0/bin/linux/amd64/kubectl" \
    && install -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage: clean slim image with only what we need at run time ---
FROM python:3.12-slim

COPY --from=builder /install /usr/local
COPY --from=builder /usr/local/bin/kubectl /usr/local/bin/kubectl

WORKDIR /app
COPY . .

ENV KUBECONFIG=/root/.kube/config

CMD ["python", "app.py"]
