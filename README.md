# Video Montage Application

FastAPI-based video processing application with automated CI/CD and Kubernetes deployment.

## Quick Start

### Local Development
```bash
pip install -r requirements.txt
python -m app.main
```
Access: http://localhost:8000

### Docker
```bash
docker-compose up --build
```

### Kubernetes
```bash
kubectl apply -f k8s/argocd-project.yaml
kubectl apply -f k8s/argocd-application.yaml
```
Access: http://node-ip:30800

## Features
- 🎬 Video processing and montage
- 🚀 FastAPI with interactive docs
- 🐳 Docker containerization
- ☸️ Kubernetes deployment
- 🔄 ArgoCD GitOps
- 📊 Health checks

## Project Structure
```
├── app/                    # Application code
├── k8s/                    # Kubernetes manifests
├── .github/workflows/      # CI/CD pipeline
├── docker-compose.yml      # Development setup
├── Dockerfile             # Container definition
└── requirements.txt       # Dependencies
```

## Deployment
See [DEPLOY.md](DEPLOY.md) for quick deployment instructions.
