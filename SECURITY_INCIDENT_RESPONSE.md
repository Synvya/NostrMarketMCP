# Security Incident Response: Exposed Private Key

## 🚨 Incident Summary
**Date**: Current  
**Type**: Private Key Exposure  
**Severity**: Medium (Self-signed certificate)  
**Status**: Active Response  

## 📋 What Happened
- Self-signed TLS certificate private key (`key.pem`) was committed to git repository
- Certificate files were accessible in repository history
- Files were used for local HTTPS development server

## ✅ Immediate Actions Taken
1. **Removed files** from current repository state
2. **Added comprehensive .gitignore** to prevent future exposure
3. **Updated deployment** to use AWS Certificate Manager instead

## 🔄 Required Remediation Actions

### 1. **Purge Git History** (CRITICAL)
Since the files were committed to git, they exist in repository history and need complete removal:

```bash
# WARNING: This will rewrite git history - coordinate with team first!

# Option A: Remove specific files from all history (RECOMMENDED)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch key.pem cert.pem' \
  --prune-empty --tag-name-filter cat -- --all

# Option B: Use git-filter-repo (if available - more efficient)
# git filter-repo --path key.pem --path cert.pem --invert-paths

# Force push to update remote (DESTRUCTIVE - warn collaborators)
git push origin --force --all
git push origin --force --tags

# Clean up local repository
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### 2. **Revoke/Replace Certificate**
Since this was a self-signed certificate:

```bash
# The old certificate is now invalid/untrusted anyway
# For production, use AWS Certificate Manager (already implemented)

# If you need local development certificates, generate new ones:
openssl req -x509 -newkey rsa:4096 -keyout new-key.pem -out new-cert.pem -days 365 -nodes \
  -subj "/C=US/ST=Local/L=Development/O=Local/CN=localhost"

# Add new certificates to .gitignore (already done)
echo "*.pem" >> .gitignore
```

### 3. **Rotate All Related Credentials**
Even though this was a self-signed cert, follow defense-in-depth:

```bash
# Generate new API credentials (already provided new ones)
python3 -c "
import secrets
print('NEW_API_KEY=' + secrets.token_urlsafe(32))
print('NEW_BEARER_TOKEN=' + secrets.token_urlsafe(32))
"

# Update all environments with new credentials
# Update AWS Secrets Manager with new values
```

### 4. **Verify Exposure Scope**
Check if the repository is public or if the exposed keys were used anywhere:

```bash
# Check git remotes
git remote -v

# Check if repo is public on GitHub/GitLab
# Review access logs if available
# Check if any services were using these certificates
```

## 🔍 Investigation Questions

### Certificate Usage Analysis
- **Where was this certificate used?** Local development only ✅
- **Was it a CA-issued certificate?** No, self-signed ✅
- **Any production systems using it?** No, production uses AWS ACM ✅
- **Repository visibility?** Check if public/private
- **Who had access?** Review collaborator list

### Timeline
1. **When was it committed?** `git log --follow key.pem`
2. **How long was it exposed?** From first commit to removal
3. **Any suspicious access?** Check repository access logs

## 🛡️ Prevention Measures

### 1. **Pre-commit Hooks**
```bash
# Install git-secrets to prevent future incidents
git secrets --install
git secrets --register-aws

# Add custom patterns
git secrets --add '*.pem'
git secrets --add '*.key'
git secrets --add 'BEGIN.*PRIVATE.*KEY'
```

### 2. **Repository Scanning**
```bash
# Add to security audit script
echo "Checking for certificate files..." >> security_audit.sh
echo "find . -name '*.pem' -o -name '*.key' -o -name '*.crt'" >> security_audit.sh
```

### 3. **Development Practices**
- **Never commit certificates** to version control
- **Use environment variables** for all credentials
- **Local certificates in separate directory** outside repo
- **Use docker volumes** for development certificates

## 📊 Risk Assessment

### Current Risk Level: 🟡 **MEDIUM → 🟢 LOW**

| Factor | Risk Level | Mitigation |
|--------|------------|------------|
| Certificate Type | Low | Self-signed, not CA-issued |
| Usage Scope | Low | Local development only |
| Repository Access | ? | **Need to verify public/private** |
| Production Impact | None | Uses AWS Certificate Manager |
| Data Exposure | Low | No sensitive data encrypted with this cert |

### If Repository is Public: 🔴 **HIGH RISK**
- Certificate is publicly accessible
- Could be used for man-in-the-middle attacks
- Immediate git history cleanup required

### If Repository is Private: 🟡 **MEDIUM RISK**  
- Limited exposure to collaborators
- Still requires cleanup for security hygiene
- Less urgent but should be addressed

## 🚀 Production Security Status

✅ **Production is SECURE**:
- Production deployment uses **AWS Certificate Manager**
- No exposed certificates in production configuration
- All secrets managed through **AWS Secrets Manager**
- Self-signed certificate was development-only

## 📋 Action Checklist

### Immediate (Next 24 hours)
- [ ] **Determine repository visibility** (public/private)
- [ ] **Review repository access logs** for suspicious activity
- [ ] **Generate new development certificates** if needed
- [ ] **Notify team members** about git history rewrite

### Short-term (Next week)
- [ ] **Purge git history** (coordinate with team)
- [ ] **Force push clean history** to all remotes
- [ ] **Install git-secrets** on all development machines
- [ ] **Update development documentation** with certificate best practices

### Long-term (Ongoing)
- [ ] **Regular security audits** using `./security_audit.sh`
- [ ] **Automated scanning** in CI/CD pipeline
- [ ] **Security training** for development team
- [ ] **Review and update** security procedures

## 🔄 Lessons Learned

1. **Certificate management** needs strict procedures
2. **Git pre-commit hooks** prevent accidental commits
3. **Regular security audits** catch issues early
4. **AWS managed services** (ACM) eliminate certificate management risks
5. **Development vs production** separation is critical

## 📞 Next Steps

1. **First Priority**: Determine if repository is public
2. **If Public**: Execute git history cleanup immediately
3. **If Private**: Plan coordinated cleanup with team
4. **Always**: Implement prevention measures

---

**Incident Handler**: Assistant  
**Review Date**: Current  
**Status**: Remediation in progress 