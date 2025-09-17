# Kubernetes Manifests

## Structure
```
k8s/
├── manifests/
│   ├── namespace.yaml     # video-montage namespace
│   ├── deployment.yaml    # App deployment
│   └── service.yaml       # NodePort service (30800)
├── argocd-project.yaml    # ArgoCD project
└── argocd-application.yaml # ArgoCD app
```

## Deploy
```bash
# GitOps (recommended)
kubectl apply -f argocd-project.yaml
kubectl apply -f argocd-application.yaml

# Manual
kubectl apply -f manifests/
```

## Access
- **URL**: `http://node-ip:30800`
- **Docs**: `http://node-ip:30800/docs`
- **Health**: `http://node-ip:30800/health`
- **Namespace**: `video-montage`

## Image
- **Registry**: GitHub Container Registry
- **Image**: `ghcr.io/skorolevskiy/video-montage:main-*`
- **Auto-updated**: CI pipeline updates deployment with new tags

## Check Status
```bash
kubectl get all -n video-montage
kubectl logs -l app=video-montage -n video-montage
```

## Scale
```bash
kubectl scale deployment video-montage --replicas=3 -n video-montage
```

## Cleanup
```bash
kubectl delete -f manifests/
```