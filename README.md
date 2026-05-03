# Kubernetes AI Agent

A Python AI agent powered by Google Gemini that creates Kubernetes Deployments and Services via natural language.

## Prerequisites
- Docker
- A running Kubernetes cluster with `kubectl` configured
- A Google Gemini API key

## Run

```bash
docker run -it --env-file .env balkanbgboy/k8s-ai-agent:v1.0
```

Create a `.env` file with:
```
GOOGLE_API_KEY=your_key_here
```

## Usage

```
🤖 Kubernetes AI Agent Initialized

💡 What should I do? (or 'exit'): create a deployment named web-app with nginx image and 3 replicas

```

The agent supports:
- Creating Deployments: `create a deployment named <name> with <image> image and <n> replicas`
- Creating Services: `create a service for <name> on port <port>`

## Build Locally

```bash
git clone https://github.com/balkanbgboy/k8s-ai-agent
cd k8s-ai-agent
docker build -t k8s-ai-agent .
docker run -it --env-file .env k8s-ai-agent
```

## Contributors
- balkanbgboy
