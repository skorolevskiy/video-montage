# Deploy Video Montage Application to Kubernetes

## Image Source
The deployment uses the Docker image built by GitHub Actions and published to GitHub Container Registry:
- **Image**: `ghcr.io/skorolevskiy/video-montage:latest`
- **Registry**: GitHub Container Registry (ghcr.io)
- **Auto-updated**: CI pipeline automatically updates deployment with new image tags

## Quick Deploy

### Manual Deployment
```bash
# Deploy all resources
kubectl apply -f k8s/

# Or deploy step by step
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### GitOps Deployment with ArgoCD (Recommended)
```bash
# Deploy ArgoCD project and application
kubectl apply -f k8s/argocd-project.yaml
kubectl apply -f k8s/argocd-application.yaml
```

See [ARGOCD.md](ARGOCD.md) for detailed ArgoCD setup and management instructions.

## CI/CD Integration

The GitHub Actions CI pipeline automatically:
1. **Builds** new Docker images on every push to main
2. **Tags** images with branch and commit SHA
3. **Updates** `deployment.yaml` with the new image tag
4. **Commits** the updated deployment back to the repository

### Automatic Updates with ArgoCD
When using ArgoCD:
1. CI pipeline updates the deployment manifest
2. ArgoCD detects the Git repository changes
3. ArgoCD automatically syncs the new image to Kubernetes
4. Zero-downtime deployment with automated rollout

This creates a complete GitOps workflow where code changes automatically trigger deployments.

## Access the Application
- **NodePort**: http://your-node-ip:30800
- **API Documentation**: http://your-node-ip:30800/docs
- **Health Check**: http://your-node-ip:30800/health

## Check Deployment Status
```bash
# Check pods
kubectl get pods -n video-montage

# Check service
kubectl get svc -n video-montage

# Check deployment
kubectl get deployment -n video-montage

# View logs
kubectl logs -l app=video-montage -n video-montage
```

## Scale the Application
```bash
# Scale to 3 replicas
kubectl scale deployment video-montage --replicas=3 -n video-montage
```

## Cleanup
```bash
# Delete all resources
kubectl delete -f k8s/
```

## GitOps Deployment with ArgoCD

For automated GitOps deployment, use ArgoCD instead of manual kubectl commands.

### Quick ArgoCD Setup
```bash
# Deploy ArgoCD project and application
kubectl apply -f k8s/argocd-project.yaml
kubectl apply -f k8s/argocd-application.yaml
```

See [ARGOCD.md](ARGOCD.md) for detailed ArgoCD setup and management instructions.

## Configuration Notes
- **Image**: Built from GitHub Actions and stored in GitHub Container Registry
- **Replicas**: 1 (can be scaled)
- **NodePort**: 30800 (accessible on all cluster nodes)
- **Namespace**: video-montage
- **Health Checks**: Simplified liveness and readiness probes on /health endpoint
- **No resource limits**: Allows flexible resource usage based on workload

## Building and Pushing New Images
To update the deployed image:
1. Push changes to the repository
2. Run the GitHub Actions workflow with "Push image to registry" enabled
3. Restart the deployment: `kubectl rollout restart deployment video-montage -n video-montage`