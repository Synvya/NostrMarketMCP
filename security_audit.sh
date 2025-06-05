#!/bin/bash
# Security Audit Script for Nostr Profiles API

echo "🔒 Security Audit for Nostr Profiles API"
echo "========================================"

# Check for sensitive files
echo "🔍 Checking for sensitive files..."
if find . -name "*.pem" -o -name "*.key" -o -name "*.crt" | grep -q .; then
    echo "❌ CRITICAL: Certificate files found in repository!"
    find . -name "*.pem" -o -name "*.key" -o -name "*.crt"
    echo "   These should be removed and added to .gitignore"
else
    echo "✅ No certificate files found in repository"
fi

# Check for hardcoded secrets
echo ""
echo "🔍 Checking for potential hardcoded secrets..."
if grep -r -i "password\|secret\|key\|token" --include="*.py" . | grep -v "API_KEY\|BEARER_TOKEN\|example\|config" | grep -q .; then
    echo "⚠️  Potential hardcoded secrets found:"
    grep -r -i "password\|secret\|key\|token" --include="*.py" . | grep -v "API_KEY\|BEARER_TOKEN\|example\|config" | head -5
else
    echo "✅ No obvious hardcoded secrets found"
fi

# Check Python security
echo ""
echo "🔍 Checking Python dependencies for vulnerabilities..."
if command -v safety &> /dev/null; then
    safety check
else
    echo "⚠️  'safety' not installed. Install with: pip install safety"
    echo "   Then run: safety check"
fi

# Check for .env files
echo ""
echo "🔍 Checking for environment files..."
if find . -name ".env*" -not -name "*.example" | grep -q .; then
    echo "⚠️  Environment files found (should be in .gitignore):"
    find . -name ".env*" -not -name "*.example"
else
    echo "✅ No .env files found in repository"
fi

# Check permissions
echo ""
echo "🔍 Checking file permissions..."
if find . -type f -perm -002 | grep -q .; then
    echo "⚠️  World-writable files found:"
    find . -type f -perm -002
else
    echo "✅ No world-writable files found"
fi

# Check git history for secrets (basic check)
echo ""
echo "🔍 Basic git history check for secrets..."
if git log --oneline | head -20 | grep -i -E "password|secret|key|token|credential" | grep -q .; then
    echo "⚠️  Potential secrets found in recent git history"
    echo "   Consider using git-secrets or similar tools for deeper analysis"
else
    echo "✅ No obvious secrets in recent git history"
fi

# Security configuration check
echo ""
echo "🔍 Checking security configuration..."
if [ -f "simple_secure_server.py" ]; then
    echo "✅ Secure server implementation found"
    
    if grep -q "SECURITY_HEADERS" simple_secure_server.py; then
        echo "✅ Security headers configured"
    else
        echo "❌ Security headers not found"
    fi
    
    if grep -q "rate_limiter" simple_secure_server.py; then
        echo "✅ Rate limiting implemented"
    else
        echo "❌ Rate limiting not found"
    fi
    
    if grep -q "InputValidator" simple_secure_server.py; then
        echo "✅ Input validation implemented"
    else
        echo "❌ Input validation not found"
    fi
else
    echo "❌ Secure server implementation not found"
fi

# AWS security check
echo ""
echo "🔍 Checking AWS deployment security..."
if [ -f "AWS_DEPLOYMENT.md" ]; then
    echo "✅ AWS deployment guide found"
    
    if grep -q "Secrets Manager" AWS_DEPLOYMENT.md; then
        echo "✅ AWS Secrets Manager mentioned"
    else
        echo "❌ AWS Secrets Manager not mentioned"
    fi
    
    if grep -q "Security Group" AWS_DEPLOYMENT.md; then
        echo "✅ Security Groups mentioned"
    else
        echo "❌ Security Groups not mentioned"
    fi
else
    echo "❌ AWS deployment guide not found"
fi

echo ""
echo "🔒 Security Audit Complete"
echo "========================="
echo ""
echo "📋 Recommendations:"
echo "1. Run 'safety check' regularly to check for vulnerable dependencies"
echo "2. Use 'git-secrets' to prevent secrets from being committed"
echo "3. Regularly rotate API keys and tokens"
echo "4. Monitor CloudWatch logs for suspicious activity"
echo "5. Keep dependencies updated"
echo "6. Review and audit access logs regularly" 