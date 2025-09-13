# Deploy Video Montage Application to Kubernetes

## Image Source
The deployment uses the Docker image built by GitHub Actions and published to GitHub Container Registry:
- **Image**: `ghcr.io/timur-riazantsev/video-montage:latest`
- **Registry**: GitHub Container Registry (ghcr.io)

## Quick Deploy
```bash
# Deploy all resources
kubectl apply -f k8s/

# Or deploy step by step
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

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