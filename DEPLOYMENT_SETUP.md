# 🚀 Production Deployment Setup Guide

This guide walks you through setting up the complete production deployment pipeline with:
1. ✅ Master-only deployments with protection rules
2. ✅ Feature flags for controlled rollouts
3. ✅ Environment protection with manual approval
4. ✅ Monitoring gates with auto-rollback

## Prerequisites

- GitHub repository with admin access
- Docker registry access (GitHub Container Registry)
- Production infrastructure (staging + production environments)

## 1. GitHub Environment Configuration

### Create Staging Environment
1. Go to **Settings** → **Environments** in your GitHub repository
2. Click **New Environment**
3. Name: `staging`
4. Configure protection rules:
   - ✅ **Required reviewers**: None (auto-deploy to staging)
   - ✅ **Wait timer**: 0 minutes
   - ✅ **Deployment branches**: Restrict to `master` only

### Create Production Environment
1. Click **New Environment**
2. Name: `production`
3. Configure protection rules:
   - ✅ **Required reviewers**: 1-2 reviewers (1 for solo development, 2+ for teams)
   - ✅ **Wait timer**: 5 minutes (review period)
   - ✅ **Deployment branches**: Restrict to `master` only
   - ✅ **Add reviewers**: Add yourself (for solo development) or senior developers/tech leads

### Set Environment Secrets
For both `staging` and `production` environments, add these secrets based on your actual configuration:

```bash
# Database & Cache (update with your actual production values)
DATABASE_URL=postgresql://postgres:your-prod-password@your-prod-db-host:5432/csfrace_prod
REDIS_URL=redis://your-prod-redis-host:6379/0

# OAuth Configuration (create production OAuth apps)
OAUTH_GOOGLE_CLIENT_ID=your-production-google-client-id
OAUTH_GOOGLE_CLIENT_SECRET=your-production-google-client-secret
OAUTH_GITHUB_CLIENT_ID=your-production-github-client-id
OAUTH_GITHUB_CLIENT_SECRET=your-production-github-client-secret

# Application Security (generate new secret key for production)
SECRET_KEY=your-production-secret-key-different-from-dev
```

### Set Environment Variables
Configure these variables per environment:

**Staging:**
```bash
ENVIRONMENT=staging
LOG_LEVEL=DEBUG
CACHE_TTL=300
RATE_LIMIT_REQUESTS=1000
FEATURE_FLAG_NEW_WORDPRESS_PARSER=true
FEATURE_FLAG_ENHANCED_IMAGE_PROCESSING=true
```

**Production:**
```bash
ENVIRONMENT=production
LOG_LEVEL=INFO
CACHE_TTL=3600
RATE_LIMIT_REQUESTS=10000
FEATURE_FLAG_NEW_WORDPRESS_PARSER=false
FEATURE_FLAG_ENHANCED_IMAGE_PROCESSING=false
```

## 2. Repository Secrets

Add these repository-level secrets in **Settings** → **Secrets and variables** → **Actions**:

```bash
CODECOV_TOKEN=<your codecov token from codecov.io>
```

**Note**: `GITHUB_TOKEN` is automatically provided by GitHub for all workflows - no manual setup needed.

## 3. Branch Protection Rules

Configure branch protection for `master`:

1. Go to **Settings** → **Branches**
2. Add rule for `master` branch:
   - ✅ **Require a pull request before merging**
   - ✅ **Require approvals**: 1 approval
   - ✅ **Dismiss stale PR approvals when new commits are pushed**
   - ✅ **Require status checks to pass before merging**
   - ✅ **Require branches to be up to date before merging**
   - ✅ **Include administrators**

## 4. Feature Flags Configuration

The feature flags system is already configured in `config/feature_flags.json`.

### How to use feature flags:

```python
from src.core.feature_flags import feature_enabled

# Simple conditional logic
if feature_enabled("new_wordpress_parser"):
    return new_parser.parse(content)
else:
    return legacy_parser.parse(content)

# With user context
if feature_enabled("enhanced_image_processing", user_id="user123"):
    return enhanced_processor.process(image)
```

### Override via environment variables:
```bash
# Force enable a feature
export FEATURE_FLAG_NEW_WORDPRESS_PARSER=true

# Force disable a feature
export FEATURE_FLAG_ENHANCED_IMAGE_PROCESSING=false
```

## 5. Deployment Workflow Usage

### Automatic Staging Deployment (Push to Master)
```bash
git checkout master
git pull origin master
git merge feature/my-feature
git push origin master
```
→ Triggers automatic staging deployment after CI passes

### Manual Production Deployment
1. Go to **Actions** → **Production Deployment Pipeline**
2. Click **Run workflow**
3. Select:
   - **Environment**: `production`
   - **Force deploy**: `false` (respect quality gates)
4. Click **Run workflow**
5. Wait for reviewers to approve (configured in environment protection)
6. Deployment proceeds automatically after approval

### Quality Gates

Before any deployment, these gates must pass:
- ✅ **Coverage**: >85% test coverage
- ✅ **Security**: No high/critical vulnerabilities
- ✅ **Linting**: Code formatting and style checks
- ✅ **Type Checking**: MyPy validation

## 6. Monitoring & Auto-Rollback

### Automatic Monitoring
After successful deployment, the system automatically monitors:
- 🏥 **Health checks**: Service availability and response times
- 📊 **Error rates**: 5-minute error rate monitoring
- 💾 **Resource usage**: Memory, CPU, and disk monitoring
- 🧪 **Application health**: Core functionality testing

### Auto-Rollback Triggers
Automatic rollback occurs when:
- ❌ Health endpoint returns non-200 status
- ❌ Error rate exceeds threshold (1% for production, 5% for staging)
- ❌ Response time exceeds limits (2s for production, 5s for staging)
- ❌ Core functionality tests fail

### Manual Rollback
```bash
# Via GitHub Actions
gh workflow run deploy.yml -f environment=production -f force_deploy=false

# Or trigger rollback directly
gh workflow run monitoring-gates.yml -f environment=production -f rollback_enabled=true
```

## 7. Notification Setup

### GitHub Native Notifications
GitHub provides built-in notifications for deployment events:

1. **Email Notifications**: Automatically sent to commit authors and repository watchers
2. **GitHub UI**: Deployment status visible in Actions tab and commit status
3. **Pull Request Integration**: Deployment status shown in PR checks
4. **Repository Insights**: Deployment history and metrics in Insights → Deployments

### Optional External Notifications
If you want additional notifications, you can configure:
- 📧 **Email notifications** via GitHub Actions email step
- 📱 **Teams webhooks** for Microsoft Teams integration
- 🎮 **Discord webhooks** for Discord server notifications
- 📟 **PagerDuty alerts** for critical production issues

**Note**: For solo development, GitHub's native notifications are typically sufficient.

## 8. Testing the Setup

### Test Staging Deployment
1. Create a small feature branch
2. Make a minor change to trigger deployment
3. Merge to master
4. Verify automatic staging deployment
5. Check monitoring runs successfully

### Test Production Deployment
1. Run production deployment workflow manually
2. Verify approval workflow triggers
3. Have a reviewer approve deployment
4. Monitor deployment and health checks
5. Verify monitoring gates complete successfully

### Test Auto-Rollback (Optional)
1. Deploy a version that will fail health checks
2. Verify automatic rollback triggers
3. Confirm service is restored to previous version
4. Check notifications are sent

## 9. Maintenance & Monitoring

### Regular Tasks
- 📊 Review deployment metrics weekly
- 🔍 Update feature flag rollout percentages
- 📈 Monitor error rates and performance trends
- 🛡️ Review security scan results
- 📝 Update deployment documentation

### Troubleshooting Common Issues

**Deployment fails quality gates:**
- Check test coverage reports
- Review security scan results
- Verify code formatting passes

**Environment protection not working:**
- Verify reviewers are added to environment
- Check branch restrictions are configured
- Confirm required approvals are set

**Auto-rollback not triggering:**
- Check health endpoint is responding correctly
- Review error thresholds for environment
- Verify monitoring gates workflow is enabled

**Feature flags not working:**
- Check `config/feature_flags.json` syntax
- Verify environment variables are set correctly
- Confirm feature flag initialization in code

## 10. Next Steps

Once setup is complete:
1. 🚀 **Gradual Rollouts**: Use feature flags to gradually enable new features
2. 📊 **Metrics**: Integrate with your monitoring stack (Prometheus, DataDog, etc.)
3. 🔄 **CI/CD Optimization**: Fine-tune quality gates and thresholds
4. 📈 **Scale**: Add more environments (demo, QA) as needed
5. 🛡️ **Security**: Implement additional security scanning and compliance checks

---

**🎉 Your production-ready deployment pipeline is now complete!**

This setup provides enterprise-grade deployment safety with intelligent CI, quality gates, manual approvals, and automatic rollback capabilities.