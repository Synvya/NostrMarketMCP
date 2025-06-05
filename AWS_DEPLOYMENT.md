# AWS ECS Deployment Guide

This guide provides step-by-step instructions for securely deploying the Nostr Profiles API to AWS ECS with production-ready security configurations.

## Prerequisites

1. AWS CLI installed and configured
2. Docker installed locally
3. AWS account with appropriate permissions
4. Domain name for HTTPS (recommended)

## Security Configuration

### 1. Generate Secure Credentials

First, generate secure API keys for production:

```bash
python3 -c "
import secrets
print('API_KEY=' + secrets.token_urlsafe(32))
print('BEARER_TOKEN=' + secrets.token_urlsafe(32))
"
```

Save these values securely - you'll need them for AWS Secrets Manager.

### 2. AWS Secrets Manager Setup

Store sensitive configuration in AWS Secrets Manager:

```bash
# Create secrets for API authentication
aws secretsmanager create-secret \
    --name "nostr-api/credentials" \
    --description "Nostr API authentication credentials" \
    --secret-string '{
        "API_KEY":"your_generated_api_key_here",
        "BEARER_TOKEN":"your_generated_bearer_token_here"
    }'
```

## Infrastructure Setup

### 1. Create ECS Cluster

```bash
# Create ECS cluster
aws ecs create-cluster \
    --cluster-name nostr-profiles-cluster \
    --capacity-providers FARGATE \
    --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1
```

### 2. Create VPC and Security Groups

```bash
# Create VPC (if you don't have one)
aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=nostr-api-vpc}]'

# Create security group for the API
aws ec2 create-security-group \
    --group-name nostr-api-sg \
    --description "Security group for Nostr API" \
    --vpc-id vpc-xxxxxxxx

# Allow HTTP traffic (you can restrict this further)
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxx \
    --protocol tcp \
    --port 8080 \
    --cidr 0.0.0.0/0
```

### 3. Create Application Load Balancer (ALB)

```bash
# Create ALB
aws elbv2 create-load-balancer \
    --name nostr-api-alb \
    --subnets subnet-xxxxxxxx subnet-yyyyyyyy \
    --security-groups sg-xxxxxxxx \
    --scheme internet-facing \
    --type application
```

### 4. Create ECR Repository

```bash
# Create ECR repository
aws ecr create-repository \
    --repository-name nostr-profiles-api \
    --image-scanning-configuration scanOnPush=true
```

## Docker Image Build and Push

### 1. Build and Tag Image

```bash
# Build the Docker image
docker build -t nostr-profiles-api .

# Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Tag image for ECR
docker tag nostr-profiles-api:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/nostr-profiles-api:latest

# Push to ECR
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/nostr-profiles-api:latest
```

## ECS Task Definition

Create `task-definition.json`:

```json
{
    "family": "nostr-profiles-api",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "512",
    "memory": "1024",
    "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
    "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole",
    "containerDefinitions": [
        {
            "name": "nostr-api",
            "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/nostr-profiles-api:latest",
            "portMappings": [
                {
                    "containerPort": 8080,
                    "protocol": "tcp"
                }
            ],
            "environment": [
                {
                    "name": "ENVIRONMENT",
                    "value": "production"
                },
                {
                    "name": "HOST",
                    "value": "0.0.0.0"
                },
                {
                    "name": "PORT",
                    "value": "8080"
                },
                {
                    "name": "ALLOWED_ORIGINS",
                    "value": "https://platform.openai.com,https://yourdomain.com"
                },
                {
                    "name": "RATE_LIMIT_REQUESTS",
                    "value": "100"
                },
                {
                    "name": "RATE_LIMIT_WINDOW",
                    "value": "60"
                },
                {
                    "name": "DATABASE_PATH",
                    "value": "/app/data/nostr_profiles.db"
                },
                {
                    "name": "LOG_LEVEL",
                    "value": "info"
                }
            ],
            "secrets": [
                {
                    "name": "API_KEY",
                    "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:nostr-api/credentials:API_KEY::"
                },
                {
                    "name": "BEARER_TOKEN",
                    "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:nostr-api/credentials:BEARER_TOKEN::"
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/nostr-profiles-api",
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "healthCheck": {
                "command": [
                    "CMD-SHELL",
                    "curl -f http://localhost:8080/health || exit 1"
                ],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60
            }
        }
    ]
}
```

Register the task definition:

```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

## Create ECS Service

```bash
# Create ECS service
aws ecs create-service \
    --cluster nostr-profiles-cluster \
    --service-name nostr-api-service \
    --task-definition nostr-profiles-api:1 \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxxx,subnet-yyyyyyyy],securityGroups=[sg-xxxxxxxx],assignPublicIp=ENABLED}" \
    --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/nostr-api-tg/1234567890123456,containerName=nostr-api,containerPort=8080
```

## SSL/TLS Configuration

### 1. Request SSL Certificate

```bash
# Request certificate from ACM
aws acm request-certificate \
    --domain-name yourdomain.com \
    --validation-method DNS \
    --subject-alternative-names api.yourdomain.com
```

### 2. Configure HTTPS Listener

```bash
# Add HTTPS listener to ALB
aws elbv2 create-listener \
    --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/nostr-api-alb/1234567890123456 \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012 \
    --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/nostr-api-tg/1234567890123456
```

## Monitoring and Logging

### 1. CloudWatch Log Group

```bash
# Create CloudWatch log group
aws logs create-log-group \
    --log-group-name /ecs/nostr-profiles-api \
    --retention-in-days 30
```

### 2. CloudWatch Alarms

```bash
# Create alarm for high error rate
aws cloudwatch put-metric-alarm \
    --alarm-name "NostrAPI-HighErrorRate" \
    --alarm-description "High error rate for Nostr API" \
    --metric-name 4XXError \
    --namespace AWS/ApplicationELB \
    --statistic Sum \
    --period 300 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2
```

## Security Best Practices

### 1. IAM Roles

Create minimal permission IAM roles:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:*:*:secret:nostr-api/*"
        }
    ]
}
```

### 2. Network Security

- Use private subnets for ECS tasks when possible
- Implement WAF rules for additional protection
- Enable VPC Flow Logs for network monitoring

### 3. Application Security

- Regularly rotate API keys in Secrets Manager
- Monitor API usage patterns
- Implement additional rate limiting based on usage
- Enable container image scanning in ECR

## OpenAI Custom GPT Configuration

Once deployed, configure your Custom GPT with:

1. **Server URL**: `https://yourdomain.com`
2. **Authentication**: API Key in header `X-API-Key: your_api_key`
3. **Schema**: Use the updated `openai_actions_schema.yaml` with your domain

## Testing the Deployment

```bash
# Test health endpoint
curl https://yourdomain.com/health

# Test authenticated endpoint
curl -H "X-API-Key: your_api_key" \
     -H "Content-Type: application/json" \
     -d '{"query": "bitcoin", "limit": 5}' \
     https://yourdomain.com/api/search_profiles
```

## Maintenance

### Updating the Application

1. Build and push new image to ECR
2. Update task definition with new image tag
3. Update ECS service to use new task definition

```bash
# Update service
aws ecs update-service \
    --cluster nostr-profiles-cluster \
    --service nostr-api-service \
    --task-definition nostr-profiles-api:2
```

### Scaling

```bash
# Scale service
aws ecs update-service \
    --cluster nostr-profiles-cluster \
    --service nostr-api-service \
    --desired-count 4
```

## Cost Optimization

- Use Fargate Spot instances for non-critical workloads
- Implement auto-scaling based on CPU/memory usage
- Use reserved capacity for predictable workloads
- Enable CloudWatch cost monitoring

## Troubleshooting

### Common Issues

1. **Task failing to start**: Check CloudWatch logs for error messages
2. **Health check failures**: Verify security group allows health check traffic
3. **High latency**: Consider increasing task resources or adding more replicas
4. **Authentication errors**: Verify Secrets Manager permissions and secret values

### Debugging Commands

```bash
# View service logs
aws logs tail /ecs/nostr-profiles-api --follow

# Check service status
aws ecs describe-services \
    --cluster nostr-profiles-cluster \
    --services nostr-api-service

# View task definition
aws ecs describe-task-definition \
    --task-definition nostr-profiles-api:1
``` 