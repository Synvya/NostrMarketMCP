# Synvya API Client Guide

This guide helps developers build clients for the Synvya API using the OpenAPI specification.

## 📋 Overview

The Synvya API provides secure access to a curated database of business information. The API is designed for AI agents to easily find businesses, products, and services and in the future place orders directly with these businesses. 

## 📖 OpenAPI Specification

The complete API specification is available in [`api-specification.yaml`](./api-specification.yaml).

### Using the Specification

You can use this OpenAPI specification to:

1. **Generate Client SDKs** in multiple programming languages
2. **Validate Requests/Responses** during development
3. **Generate Documentation** for your integration
4. **Mock the API** for testing purposes

## 🔐 Authentication

The API supports two authentication methods:

### Method 1: API Key (Recommended)
```http
GET /api/stats
X-API-Key: your_api_key_here
```

### Method 2: Bearer Token
```http
GET /api/stats
Authorization: Bearer your_bearer_token_here
```

## 📊 Rate Limiting

- **Default Limit**: 100 requests per minute per IP
- **Rate Limit Headers**: Check `X-Rate-Limit-Remaining` in responses
- **Rate Limit Exceeded**: Returns HTTP 429 with `Retry-After` header

## 🛠️ Client SDK Generation

### Using OpenAPI Generator

Install the OpenAPI Generator:
```bash
npm install @openapitools/openapi-generator-cli -g
```

Generate clients for different languages:

#### Python Client
```bash
openapi-generator-cli generate \
  -i docs/api-specification.yaml \
  -g python \
  -o ./clients/python \
  --package-name nostr_profiles_client
```

#### JavaScript/TypeScript Client
```bash
openapi-generator-cli generate \
  -i docs/api-specification.yaml \
  -g typescript-axios \
  -o ./clients/typescript
```

#### Java Client
```bash
openapi-generator-cli generate \
  -i docs/api-specification.yaml \
  -g java \
  -o ./clients/java \
  --package-name com.example.nostrprofiles
```

#### Go Client
```bash
openapi-generator-cli generate \
  -i docs/api-specification.yaml \
  -g go \
  -o ./clients/go
```

## 📝 Code Examples

### Python Example (using requests)

```python
import requests
import json

class SynvyaClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def search_profiles(self, query: str, limit: int = 10):
        """Search for products and services"""
        url = f"{self.base_url}/api/search"
        data = {"query": query, "limit": limit}
        
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def search_business_profiles(self, query: str = "", business_type: str = "", limit: int = 10):
        """Search for business by name or type"""
        url = f"{self.base_url}/api/search_by_business_type"
        data = {"query": query, "business_type": business_type, "limit": limit}
        
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def get_profile(self, pubkey: str):
        """Get businesss information by public key"""
        url = f"{self.base_url}/api/profile/{pubkey}"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_stats(self):
        """Get database statistics"""
        url = f"{self.base_url}/api/stats"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

# Usage example
client = SynvyaClient("http://localhost:8080", "your_api_key")

# Search for Bitcoin-related profiles
results = client.search_profiles("bitcoin", limit=5)
print(f"Found {results['count']} profiles")

# Search for restaurants
restaurants = client.search_business_profiles(business_type="restaurant", limit=10)
print(f"Found {restaurants['count']} restaurants")

# Get specific profile
profile = client.get_profile("57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991")
print(f"Profile: {profile['profile']['name']}")
```

### JavaScript/TypeScript Example

```typescript
interface NostrProfile {
  pubkey: string;
  name?: string;
  display_name?: string;
  about?: string;
  picture?: string;
  website?: string;
  business_type?: string;
  // ... other fields
}

interface SearchResponse {
  success: boolean;
  count: number;
  profiles: NostrProfile[];
  query?: string;
}

class SynvyaClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'X-API-Key': this.apiKey,
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const response = await fetch(url, { ...options, headers });
    
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
  }

  async searchProfiles(query: string, limit: number = 10): Promise<SearchResponse> {
    return this.request<SearchResponse>('/api/search', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    });
  }

  async searchBusinessProfiles(
    query: string = '',
    businessType: string = '',
    limit: number = 10
  ): Promise<SearchResponse> {
    return this.request<SearchResponse>('/api/search_by_business_type', {
      method: 'POST',
      body: JSON.stringify({
        query,
        business_type: businessType,
        limit,
      }),
    });
  }

  async getProfile(pubkey: string): Promise<{ success: boolean; profile: NostrProfile }> {
    return this.request<{ success: boolean; profile: NostrProfile }>(`/api/profile/${pubkey}`);
  }

  async getStats(): Promise<{ success: boolean; stats: any }> {
    return this.request<{ success: boolean; stats: any }>('/api/stats');
  }
}

// Usage example
const client = new SynvyaClient('http://localhost:8080', 'your_api_key');

// Search for profiles
client.searchProfiles('bitcoin', 5)
  .then(results => console.log(`Found ${results.count} profiles`))
  .catch(error => console.error('Search failed:', error));
```

### cURL Examples

#### Search Products and Services
```bash
curl -X POST "http://localhost:8080/api/search" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "bitcoin", "limit": 5}'
```

#### Search Business Profiles
```bash
curl -X POST "http://localhost:8080/api/search_by_business_type" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "coffee", "business_type": "restaurant", "limit": 10}'
```

#### Get Business Profile by Public Key
```bash
curl -X GET "http://localhost:8080/api/profile/57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991" \
  -H "X-API-Key: your_api_key"
```

#### Get Statistics
```bash
curl -X GET "http://localhost:8080/api/stats" \
  -H "X-API-Key: your_api_key"
```

## 🔍 Error Handling

The API uses standard HTTP status codes and returns structured error responses:

### Error Response Format
```json
{
  "error": "Error message",
  "details": "Additional error details",
  "code": "ERROR_CODE"
}
```

### Common HTTP Status Codes
- **200**: Success
- **400**: Bad Request (invalid input)
- **401**: Unauthorized (authentication required)
- **404**: Not Found (profile doesn't exist)
- **429**: Rate Limit Exceeded
- **500**: Internal Server Error

### Error Handling Example (Python)
```python
try:
    results = client.search_profiles("bitcoin")
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        print("Authentication failed - check your API key")
    elif e.response.status_code == 429:
        print("Rate limit exceeded - wait before retrying")
    elif e.response.status_code == 400:
        error_data = e.response.json()
        print(f"Bad request: {error_data.get('error')}")
    else:
        print(f"API error: {e}")
except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")
```

## 📊 Response Validation

### Profile Data Structure
```json
{
  "pubkey": "57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991",
  "name": "Alice",
  "display_name": "Alice Cooper",
  "about": "Bitcoin developer and coffee enthusiast",
  "picture": "https://example.com/avatar.jpg",
  "website": "https://alice.example.com",
  "nip05": "alice@example.com",
  "lud16": "alice@getalby.com",
  "business_type": "restaurant",
  "tags": [["L", "business.type"], ["l", "restaurant", "business.type"]],
  "created_at": 1699123456
}
```

### Search Response Structure
```json
{
  "success": true,
  "count": 5,
  "profiles": [/* array of Profile objects */],
  "query": "bitcoin"
}
```

## 🧪 Testing Your Client

### Mock Server
You can use the OpenAPI specification to create a mock server for testing:

```bash
# Using Prism (API mocking tool)
npm install -g @stoplight/prism-cli
prism mock docs/api-specification.yaml
```

### Unit Testing Example (Python)
```python
import unittest
from unittest.mock import patch, Mock
from your_client import SynvyaClient

class TestSynvyaClient(unittest.TestCase):
    def setUp(self):
        self.client = SynvyaClient("http://test.example.com", "test_key")
    
    @patch('requests.post')
    def test_search_profiles(self, mock_post):
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "count": 2,
            "profiles": [{"pubkey": "abc123", "name": "Test"}],
            "query": "test"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Test the method
        result = self.client.search_profiles("test", 10)
        
        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        mock_post.assert_called_once()
```

## 🎯 Best Practices

### 1. **Rate Limiting**
- Implement exponential backoff for 429 responses
- Cache results when appropriate
- Batch requests efficiently

### 2. **Error Handling**
- Always handle HTTP errors gracefully
- Log errors for debugging
- Provide user-friendly error messages

### 3. **Input Validation**
- Validate public keys (64-character hex strings)
- Limit query string lengths
- Sanitize user input

### 4. **Performance**
- Use connection pooling for multiple requests
- Implement request timeouts
- Consider pagination for large result sets

### 5. **Security**
- Store API keys securely (environment variables)
- Use HTTPS in production
- Validate SSL certificates

## 📚 Additional Resources

- [OpenAPI Specification](https://swagger.io/specification/)
- [OpenAPI Generator](https://openapi-generator.tech/)
- [Nostr Protocol Documentation](https://github.com/nostr-protocol/nips)
- [API Testing with Postman](https://learning.postman.com/docs/getting-started/introduction/)

## 🐛 Troubleshooting

### Common Issues

**Authentication Errors (401)**
- Verify your API key is correct
- Check the authentication method (API key vs Bearer token)
- Ensure the header name is exactly `X-API-Key`

**Rate Limiting (429)**
- Implement exponential backoff
- Check the `Retry-After` header
- Consider caching frequently accessed data

**Invalid Public Key Format (400)**
- Public keys must be 64-character hexadecimal strings
- Remove any prefixes like "npub" - use raw hex format
- Validate format before making requests

**Connection Issues**
- Verify the server URL and port
- Check firewall settings
- Ensure the server is running and accessible

For more help, check the server logs or contact API support. 