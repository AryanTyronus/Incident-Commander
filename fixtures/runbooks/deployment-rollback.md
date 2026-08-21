# Deployment Rollback

## Overview

Procedure for rolling back a deployment when issues are detected.

## When to Rollback

- Error rate exceeds 5% after deployment
- Critical functionality is broken
- Performance degradation detected

## Rollback Steps

### Kubernetes
```bash
kubectl rollout undo deployment/<service-name>
```

### Docker Compose
```bash
docker-compose down
docker-compose -f docker-compose.previous.yml up -d
```

### Manual
1. Stop the current version
2. Deploy the previous version
3. Verify health checks pass
4. Monitor error rates

## Verification

After rollback:
- [ ] Health check returns 200
- [ ] Error rate returns to baseline
- [ ] No data corruption
- [ ] All dependent services healthy

## Post-Incident

After successful rollback:
1. Document what went wrong
2. Create ticket for fix
3. Schedule proper deployment window
