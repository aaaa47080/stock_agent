# Kubernetes Storage Stability Runbook

This runbook defines the minimum storage controls to avoid pod evictions caused by `ephemeral-storage` pressure.

## 1. Apply namespace baseline

```bash
kubectl apply -f deploy/k8s/storage-baseline.yaml -n <your-namespace>
```

This applies:
- `LimitRange` for default container requests/limits
- `ResourceQuota` for namespace-level caps

## 2. Patch deployment resources

```bash
kubectl apply -f deploy/k8s/deployment-storage-patch.yaml -n <your-namespace>
```

Important:
- Replace `metadata.name` and container `name` with your real deployment/container names if different.
- Review `emptyDir.sizeLimit` and match to your workload.

## 3. Validate runtime usage

```bash
kubectl top pod -n <your-namespace>
kubectl describe pod <pod-name> -n <your-namespace> | rg -n "ephemeral-storage|Evicted|DiskPressure"
```

## 4. Post-deploy smoke check

```bash
API_URL=https://yourdomain.com bash scripts/post_deploy_smoke.sh
```

## 5. Ongoing dependency hygiene

```bash
bash scripts/refresh_lock_and_audit.sh
```

If `requirements.lock.txt` changes, commit and deploy with the updated lockfile.
