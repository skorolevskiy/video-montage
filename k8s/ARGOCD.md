# ArgoCD Deployment for Video Montage Application

This directory contains simplified ArgoCD manifests for GitOps deployment of the Video Montage application.

## Files

- `argocd-project.yaml` - Minimal ArgoCD AppProject for basic organization
- `argocd-application.yaml` - Simplified ArgoCD Application for automated deployment

## Prerequisites

1. **ArgoCD installed** in your Kubernetes cluster
2. **Access to the repository** from ArgoCD (public repository)
3. **ArgoCD CLI** (optional, for command-line management)

## Quick Deploy

### 1. Deploy ArgoCD Project
```bash
kubectl apply -f k8s/argocd-project.yaml
```

### 2. Deploy ArgoCD Application
```bash
kubectl apply -f k8s/argocd-application.yaml
```

### 3. Verify Deployment
```bash
# Check ArgoCD application status
kubectl get applications -n argocd

# Check if the application is synced
kubectl describe application video-montage -n argocd
```

## ArgoCD Features Configured

### Automated Sync
- **Prune**: Automatically removes resources not defined in Git
- **Self Heal**: Automatically corrects drift from desired state
- **Create Namespace**: Automatically creates the target namespace

### Simplified Configuration
- **Minimal project**: Basic source and destination restrictions
- **Essential sync policy**: Core automated sync features only
- **Default security**: Uses ArgoCD's built-in security model

## Access ArgoCD UI

### Port Forward (for testing)
```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```
Then access: https://localhost:8080

### Get Admin Password
```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

## Managing the Application

### Using ArgoCD UI
1. Access the ArgoCD web interface
2. Find the `video-montage` application
3. Click on it to see the resource tree
4. Use Sync, Refresh, or other actions as needed

### Using ArgoCD CLI
```bash
# Login to ArgoCD
argocd login <argocd-server-ip>

# Get application status
argocd app get video-montage

# Sync application
argocd app sync video-montage

# View application logs
argocd app logs video-montage
```

### Using kubectl
```bash
# Get application status
kubectl get application video-montage -n argocd -o yaml

# Force sync
kubectl patch application video-montage -n argocd --type merge -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}'
```

## Customization

### Change Git Repository
Edit `argocd-application.yaml`:
```yaml
spec:
  source:
    repoURL: https://github.com/your-org/your-repo.git
```

### Change Target Cluster
Edit `argocd-application.yaml`:
```yaml
spec:
  destination:
    server: https://your-cluster-api-server
```

### Disable Auto Sync
Edit `argocd-application.yaml`:
```yaml
spec:
  syncPolicy:
    # Remove or comment out the automated section
    # automated:
    #   prune: true
    #   selfHeal: true
```

### Add Helm Support
If you want to use Helm charts instead of plain YAML:
```yaml
spec:
  source:
    repoURL: https://github.com/skorolevskiy/video-montage.git
    targetRevision: main
    path: helm/video-montage
    helm:
      valueFiles:
        - values.yaml
```

## Security Considerations

The ArgoCD project includes:
- **Source repository restrictions** - Only allows the video-montage repository
- **Destination restrictions** - Only allows deployment to video-montage namespace
- **Resource restrictions** - Limits what Kubernetes resources can be managed
- **RBAC roles** - Admin and developer roles with appropriate permissions

## Troubleshooting

### Application Stuck in Syncing
```bash
# Check application events
kubectl describe application video-montage -n argocd

# Check ArgoCD application controller logs
kubectl logs -l app.kubernetes.io/name=argocd-application-controller -n argocd
```

### Sync Failures
```bash
# View detailed sync status
argocd app get video-montage --show-operation

# Check resource status
kubectl get all -n video-montage
```

### Repository Access Issues
```bash
# Check ArgoCD repo-server logs
kubectl logs -l app.kubernetes.io/name=argocd-repo-server -n argocd
```

## Monitoring

Monitor your application through:
- **ArgoCD UI**: Real-time status and resource tree
- **Kubernetes Dashboard**: Standard Kubernetes resource monitoring
- **Application Logs**: `kubectl logs -l app=video-montage -n video-montage`
- **ArgoCD Notifications**: Configure Slack/email notifications for sync events