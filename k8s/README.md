# Deploy Video Montage Application to Kubernetes

## Quick Deploy
```bash
# Deploy all resources
kubectl apply -f k8s/

# Or deploy step by step
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
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
- **Replicas**: 2 (can be scaled)
- **NodePort**: 30800 (accessible on all cluster nodes)
- **Resource Limits**: 2Gi memory, 1 CPU core
- **Temp Storage**: 5Gi ephemeral volume for video processing
- **Health Checks**: Liveness and readiness probes on /health endpoint