# Security Implementation Guide

## Overview

This document outlines the comprehensive security measures implemented for the Nostr Profiles API server, designed specifically for secure cloud deployment and OpenAI Custom GPT integration.

## Security Features Implemented

### 1. Authentication & Authorization

#### API Key Authentication
- **Header-based**: `X-API-Key: your_api_key`
- **Query parameter fallback**: `?api_key=your_api_key`
- **Constant-time comparison** to prevent timing attacks
- **Configurable**: Can be disabled for development, required for production

#### Bearer Token Authentication
- **Authorization header**: `Authorization: Bearer your_token`
- **JWT-compatible format** (though we use simple tokens)
- **Constant-time comparison** for security
- **Dual authentication**: Can be used alongside or instead of API keys

#### Production Validation
```python
if ENVIRONMENT == "production":
    if not API_KEY or len(API_KEY) < 32:
        raise ValueError("API_KEY must be set and at least 32 characters")
    if not BEARER_TOKEN or len(BEARER_TOKEN) < 32:
        raise ValueError("BEARER_TOKEN must be set and at least 32 characters")
```

### 2. Rate Limiting

#### Per-IP Rate Limiting
- **Default**: 100 requests per 60 seconds per IP
- **Configurable** via environment variables
- **In-memory tracking** with automatic cleanup
- **429 Too Many Requests** response with retry information

#### Endpoint-Specific Limits
- **Health check**: 10 requests per minute (lighter endpoint)
- **Stats endpoint**: 20 requests per minute (database read)
- **Refresh endpoint**: 2 requests per minute (expensive operation)

### 3. Input Validation & Sanitization

#### String Sanitization
- **HTML escaping** to prevent XSS attacks
- **Length validation** (configurable limits)
- **Type checking** for expected data types
- **Whitespace trimming** and normalization

#### Nostr Public Key Validation
- **64-character hex string** requirement
- **Regex validation**: `^[0-9a-fA-F]{64}$`
- **Case normalization** to lowercase
- **Input sanitization** before validation

#### Search Query Protection
- **SQL injection prevention**: Blocks dangerous patterns
- **Length limits**: Maximum 200 characters
- **Content filtering**: Removes potentially harmful characters
- **Validated patterns**: `['`, `"`, `;`, `--`, `/*`, `*/`, `xp_`, `sp_`]

### 4. CORS Configuration

#### OpenAI Custom GPT Compatibility
- **Primary origin**: `https://platform.openai.com`
- **Configurable additional origins** via environment
- **Credential support**: Allows authentication headers
- **Method restrictions**: Only GET, POST, OPTIONS
- **Header whitelist**: Authorization, Content-Type, X-API-Key

#### Production Configuration
```python
allowed_origins = ["https://platform.openai.com", "https://yourdomain.com"]
# Always includes OpenAI platform for Custom GPT compatibility
```

### 5. Security Headers

#### Comprehensive Security Headers
```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",           # Prevent MIME sniffing
    "X-Frame-Options": "DENY",                     # Prevent clickjacking
    "X-XSS-Protection": "1; mode=block",           # XSS protection
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",  # Force HTTPS
    "Content-Security-Policy": "default-src 'self'",  # Content restrictions
    "Referrer-Policy": "strict-origin-when-cross-origin",  # Referrer control
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()"  # Feature restrictions
}
```

### 6. Request Security Middleware

#### Suspicious Pattern Detection
- **URL path scanning** for common attack patterns
- **User agent validation** (minimum length requirements)
- **IP blocking capability** (manual and automatic)
- **Request logging** for security monitoring

#### Blocked Patterns
```python
suspicious_patterns = [
    "admin", "wp-admin", "phpmyadmin", "config", "env", "backup",
    "sql", "dump", "database", "passwd", "shadow", "etc",
    "../", "..\\", "%2e%2e", "script", "javascript", "vbscript"
]
```

### 7. Error Handling & Information Disclosure

#### Secure Error Responses
- **Generic error messages** in production
- **Detailed logging** server-side only
- **Status code standardization** (401, 403, 429, 500)
- **No sensitive information** in public error responses

#### Global Exception Handler
```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return Response(
        status_code=500,
        content=json.dumps({
            "success": False,
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
        }),
        media_type="application/json"
    )
```

### 8. Production Deployment Security

#### Environment Configuration
- **Secrets management** via AWS Secrets Manager
- **Environment-based behavior** (dev vs production)
- **Secure credential generation** using `secrets.token_urlsafe()`
- **Configuration validation** on startup

#### Container Security
- **Non-root user** execution in Docker
- **Minimal base image** (Python slim)
- **Multi-stage build** for smaller attack surface
- **Health checks** for monitoring

#### AWS Security
- **IAM roles** with minimal permissions
- **Security groups** with restricted access
- **ECS task isolation** 
- **CloudWatch logging** for audit trails
- **SSL/TLS termination** at load balancer

## Security Configuration

### Environment Variables

#### Required for Production
```env
API_KEY=your_32_plus_character_secure_key
BEARER_TOKEN=your_32_plus_character_secure_token
ALLOWED_ORIGINS=https://platform.openai.com,https://yourdomain.com
ENVIRONMENT=production
```

#### Optional Configuration
```env
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
DATABASE_PATH=/app/data/nostr_profiles.db
LOG_LEVEL=info
HOST=0.0.0.0
PORT=8080
```

### Generating Secure Credentials

```python
import secrets

# Generate secure credentials
api_key = secrets.token_urlsafe(32)      # 43 characters
bearer_token = secrets.token_urlsafe(32)  # 43 characters

print(f"API_KEY={api_key}")
print(f"BEARER_TOKEN={bearer_token}")
```

## Testing Security

### Authentication Testing
```bash
# Test without authentication (should fail in production)
curl https://yourdomain.com/api/search_profiles

# Test with API key
curl -H "X-API-Key: your_api_key" \
     -H "Content-Type: application/json" \
     -d '{"query": "bitcoin", "limit": 5}' \
     https://yourdomain.com/api/search_profiles

# Test with Bearer token
curl -H "Authorization: Bearer your_bearer_token" \
     -H "Content-Type: application/json" \
     -d '{"query": "bitcoin", "limit": 5}' \
     https://yourdomain.com/api/search_profiles
```

### Rate Limiting Testing
```bash
# Rapid requests to trigger rate limiting
for i in {1..105}; do
  curl -H "X-API-Key: your_api_key" https://yourdomain.com/health
done
# Should receive 429 status after 100 requests
```

### Input Validation Testing
```bash
# Test invalid pubkey format
curl -H "X-API-Key: your_api_key" \
     https://yourdomain.com/api/profile/invalid_pubkey

# Test SQL injection attempt
curl -H "X-API-Key: your_api_key" \
     -H "Content-Type: application/json" \
     -d '{"query": "test; DROP TABLE--", "limit": 5}' \
     https://yourdomain.com/api/search_profiles
```

## Security Monitoring

### Key Metrics to Monitor
1. **Authentication failures** per IP/time window
2. **Rate limit violations** and patterns
3. **Suspicious URL patterns** accessed
4. **Error rates** and types
5. **Response times** for anomaly detection

### Logging Examples
```
INFO: Authentication failed: Invalid API key
WARN: Rate limit exceeded for 192.168.1.100
WARN: Suspicious request from 192.168.1.100: /admin
ERROR: Input validation failed: Invalid characters in search query
```

### AWS CloudWatch Alarms
- **High error rate** (>10 4XX errors in 5 minutes)
- **Authentication failures** (>20 failures in 5 minutes)
- **Rate limit violations** (>50 violations in 5 minutes)
- **Health check failures**

## Security Best Practices

### Development
1. **Never commit credentials** to version control
2. **Use environment variables** for all configuration
3. **Test security features** regularly
4. **Keep dependencies updated**
5. **Use minimal Docker images**

### Production
1. **Rotate credentials** regularly (monthly)
2. **Monitor security logs** actively
3. **Use HTTPS everywhere** (TLS 1.2+)
4. **Implement backup strategies** for data
5. **Regular security audits**

### OpenAI Custom GPT Integration
1. **Whitelist only necessary origins**
2. **Use strong authentication** (both API key and Bearer token)
3. **Monitor usage patterns** for anomalies
4. **Implement usage quotas** if needed
5. **Document API usage** for users

## Compliance & Standards

### Security Standards
- **OWASP Top 10** mitigation
- **Input validation** best practices
- **Authentication** security standards
- **CORS** security guidelines
- **Container** security best practices

### Data Protection
- **No personal data storage** (public Nostr data only)
- **Audit logging** for access tracking
- **Secure data transmission** (HTTPS only)
- **Regular data cleanup** (optional)

## Incident Response

### Security Incident Types
1. **Authentication bypass** attempts
2. **DDoS or rate limit abuse**
3. **Injection attack** attempts
4. **Unauthorized data access**
5. **Service availability** issues

### Response Procedures
1. **Immediate**: Block suspicious IPs
2. **Short-term**: Rotate compromised credentials
3. **Medium-term**: Analyze logs and patch vulnerabilities
4. **Long-term**: Update security policies and monitoring

### Emergency Contacts
- **AWS Support**: For infrastructure issues
- **OpenAI Support**: For Custom GPT integration issues
- **Security Team**: For security incidents

This comprehensive security implementation provides multiple layers of protection suitable for production deployment while maintaining compatibility with OpenAI Custom GPTs. 