# Quick Deploy

## ArgoCD (Recommended)
```bash
kubectl apply -f k8s/argocd-project.yaml
kubectl apply -f k8s/argocd-application.yaml
```

## Manual
```bash
kubectl apply -f k8s/manifests/
```

## Access
- App: `http://node-ip:30800`
- Docs: `http://node-ip:30800/docs`
- Health: `http://node-ip:30800/health`

## Check Status
```bash
kubectl get all -n video-montage
```