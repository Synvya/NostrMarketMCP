# Synvya API Client Guide

This guide helps developers build clients for the Synvya API using the OpenAPI specification.

## 📋 Overview

The Synvya API provides secure access to a curated database of business information. The API is designed for AI agents to easily find businesses, products, and services and in the future place orders directly with these businesses.

## 🛤️ Integration Strategies

The Synvya API supports two different integration approaches depending on your application's capabilities:

### Strategy 1: Simple Clients (No LLM) - Use `/api/chat`
**Best for:** Applications without built-in LLM capabilities that want natural language search

- ✅ **Easy Integration**: Single endpoint with natural language queries
- ✅ **Built-in AI**: Powered by OpenAI GPT models on the server side
- ✅ **No LLM Required**: No need to integrate your own language model
- ✅ **Automatic Function Selection**: AI automatically chooses the best search strategy
- ⚠️ **Less Control**: Limited customization of search logic and result processing

**Example Use Cases:**
- Simple web interfaces or mobile apps
- Chatbots without existing LLM integration
- Rapid prototyping and MVPs
- Applications focusing on user experience over search optimization

### Strategy 2: Advanced Clients (Have LLM) - Use Direct Endpoints
**Best for:** Applications with existing LLM capabilities that want fine-grained control

- ✅ **Full Control**: Direct access to specific search functions
- ✅ **Optimization**: Can optimize queries and combine multiple searches
- ✅ **Custom Logic**: Implement your own search strategies and result processing
- ✅ **Lower Latency**: Direct API calls without additional LLM processing
- ⚠️ **More Complex**: Requires LLM integration and function calling setup

**Available Endpoints:**
- `/api/search` - General profile search
- `/api/search_by_business_type` - Business-specific search with type filtering
- `/api/profile/{pubkey}` - Get specific profile by public key
- `/api/business_types` - List available business types
- `/api/stats` - Database statistics

**Example Use Cases:**
- Applications with existing OpenAI/Anthropic/other LLM integrations
- Advanced search interfaces with custom filtering
- Applications requiring specific result formatting or processing
- High-performance applications optimizing for speed and efficiency

## 📖 OpenAPI Specification

The complete API specification is available in [`api-specification.yaml`](./api-specification.yaml).

### Using the Specification

You can use this OpenAPI specification to:

1. **Generate Client SDKs** in multiple programming languages
2. **Validate Requests/Responses** during development
3. **Generate Documentation** for your integration
4. **Mock the API** for testing purposes

## 🤖 Strategy 1: Simple Clients - AI Chat API

### Overview
The `/api/chat` endpoint provides a complete natural language interface for applications without built-in LLM capabilities. The server handles all AI processing using OpenAI's GPT models.

### Why Use the Chat API?
- **No LLM Integration Required**: Skip the complexity of integrating language models
- **Natural Language Interface**: Users can ask questions in plain English
- **Automatic Optimization**: AI selects the best search strategy automatically
- **Streaming Support**: Real-time responses for better user experience
- **Context Awareness**: Maintains conversation history for follow-up queries

### Example Queries
```
"Find me restaurants in Seattle"
"Show me bitcoin developers"  
"I need a bookkeeper in Washington"
"What business types are available?"
"Get profile for pubkey abc123..."
```

### Request Format
```json
{
  "messages": [
    {"role": "user", "content": "Find me some restaurants"},
    {"role": "assistant", "content": "I found several restaurants..."},
    {"role": "user", "content": "What about coffee shops?"}
  ],
  "stream": true,
  "max_tokens": 1000,
  "temperature": 0.7
}
```

### Response Format (Streaming)
```
data: {"content": "I found "}
data: {"content": "several "}
data: {"content": "restaurants for you:\n\n"}
data: {"content": "1. **Acme Restaurant**\n"}
data: {"done": true}
```

### Response Format (Non-streaming)
```json
{
  "success": true,
  "message": {
    "role": "assistant", 
    "content": "I found several restaurants for you:\n\n1. **Acme Restaurant**..."
  },
  "stream": false
}
```

### JavaScript Example - Simple Client
```javascript
// Simple chat integration for applications without LLM
async function searchWithChat(userQuery) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'your_api_key_here'
    },
    body: JSON.stringify({
      messages: [
        { role: 'user', content: userQuery }
      ],
      stream: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.content) {
            console.log(data.content); // Stream content to UI
          } else if (data.done) {
            console.log('Search completed');
          }
        } catch (e) {
          // Skip malformed JSON
        }
      }
    }
  }
}

// Usage - no LLM knowledge required
searchWithChat("Find me some coffee shops in Seattle");
```

### Python Example - Simple Client
```python
import requests
import json

def simple_search(query, api_key):
    """Simple search using chat API - no LLM integration required"""
    response = requests.post(
        'https://api.synvya.com/api/chat',
        headers={
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        },
        json={
            'messages': [
                {'role': 'user', 'content': query}
            ],
            'stream': True
        },
        stream=True
    )

    for line in response.iter_lines():
        if line.startswith(b'data: '):
            try:
                data = json.loads(line[6:].decode())
                if 'content' in data:
                    print(data['content'], end='', flush=True)
                elif 'done' in data:
                    print('\nSearch completed')
                    break
            except json.JSONDecodeError:
                continue

# Usage - simple and straightforward
simple_search("Find me some restaurants", "your_api_key_here")
```

## 🔧 Strategy 2: Advanced Clients - Direct API Endpoints

### Overview
For applications that already have LLM capabilities and want fine-grained control over searches, use the direct API endpoints. This approach provides maximum flexibility and optimization opportunities.

### Why Use Direct Endpoints?
- **Full Control**: Choose exactly which search function to use
- **Performance**: Direct calls without additional LLM processing overhead  
- **Custom Logic**: Implement sophisticated search strategies
- **Result Processing**: Full control over how results are formatted and presented
- **Optimization**: Combine multiple searches and optimize for your specific use case

### Available Functions
- `search_profiles` - General profile search by keywords
- `search_business_profiles` - Business-specific search with type filtering
- `get_profile_by_pubkey` - Get specific profile by public key
- `get_business_types` - List available business types for filtering
- `get_stats` - Database statistics and metrics

### Python Example - Advanced Client with LLM Integration
```python
import requests
import json
import openai

class AdvancedSynvyaClient:
    def __init__(self, base_url: str, api_key: str, openai_api_key: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
        openai.api_key = openai_api_key

    def search_profiles(self, query: str, limit: int = 10):
        """Direct search for products and services"""
        url = f"{self.base_url}/api/search"
        data = {"query": query, "limit": limit}
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def search_business_profiles(self, query: str = "", business_type: str = "", limit: int = 10):
        """Direct search for businesses by name or type"""
        url = f"{self.base_url}/api/search_by_business_type"
        data = {"query": query, "business_type": business_type, "limit": limit}
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def get_profile(self, pubkey: str):
        """Get specific business profile by public key"""
        url = f"{self.base_url}/api/profile/{pubkey}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_business_types(self):
        """Get available business types"""
        url = f"{self.base_url}/api/business_types"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_stats(self):
        """Get database statistics"""
        url = f"{self.base_url}/api/stats"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def intelligent_search(self, user_query: str):
        """Use LLM to intelligently route to the best search strategy"""
        
        # Define available functions for LLM
        functions = [
            {
                "name": "search_profiles",
                "description": "Search for profiles by general keywords",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 10}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_business_profiles", 
                "description": "Search for businesses by name or type",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Business name query"},
                        "business_type": {"type": "string", "description": "Business type filter"},
                        "limit": {"type": "integer", "default": 10}
                    }
                }
            },
            {
                "name": "get_business_types",
                "description": "Get list of available business types",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

        # Use LLM to determine best search strategy
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that helps users search a business database. Use the available functions to find what the user needs."},
                {"role": "user", "content": user_query}
            ],
            functions=functions,
            function_call="auto"
        )

        # Execute the LLM's chosen function
        message = response.choices[0].message
        if message.get("function_call"):
            function_name = message["function_call"]["name"]
            function_args = json.loads(message["function_call"]["arguments"])
            
            if function_name == "search_profiles":
                results = self.search_profiles(**function_args)
            elif function_name == "search_business_profiles":
                results = self.search_business_profiles(**function_args)
            elif function_name == "get_business_types":
                results = self.get_business_types()
            
            # Use LLM to format the results nicely
            final_response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Format these search results in a helpful way for the user."},
                    {"role": "user", "content": f"Query: {user_query}\nResults: {json.dumps(results)}"}
                ]
            )
            
            return final_response.choices[0].message.content
        
        return "I couldn't determine how to search for that. Please try a more specific query."

# Usage example - advanced client with full control
client = AdvancedSynvyaClient("http://localhost:8080", "your_api_key", "your_openai_key")

# Direct API usage with full control
restaurants = client.search_business_profiles(business_type="restaurant", limit=5)
print(f"Found {restaurants['count']} restaurants")

# Or use LLM integration for intelligent routing
response = client.intelligent_search("Find me coffee shops in Seattle")
print(response)
```

### JavaScript Example - Advanced Client with LLM
```javascript
class AdvancedSynvyaClient {
  constructor(baseUrl, apiKey, openaiApiKey) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
    this.openaiApiKey = openaiApiKey;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'X-API-Key': this.apiKey,
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }
    return response.json();
  }

  async searchProfiles(query, limit = 10) {
    return this.request('/api/search', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    });
  }

  async searchBusinessProfiles(query = '', businessType = '', limit = 10) {
    return this.request('/api/search_by_business_type', {
      method: 'POST',
      body: JSON.stringify({
        query,
        business_type: businessType,
        limit,
      }),
    });
  }

  async getProfile(pubkey) {
    return this.request(`/api/profile/${pubkey}`);
  }

  async getBusinessTypes() {
    return this.request('/api/business_types');
  }

  async intelligentSearch(userQuery) {
    // Use your LLM integration to determine the best search strategy
    // This example shows the concept - implement with your preferred LLM
    
    const functions = [
      {
        name: 'searchProfiles',
        description: 'Search for profiles by general keywords',
        parameters: {
          type: 'object',
          properties: {
            query: { type: 'string', description: 'Search query' },
            limit: { type: 'integer', default: 10 }
          },
          required: ['query']
        }
      },
      // ... other function definitions
    ];

    // Your LLM integration logic here
    // Then execute the chosen function and format results
  }
}

// Usage - advanced client with full control
const client = new AdvancedSynvyaClient('http://localhost:8080', 'your_api_key', 'your_openai_key');

// Direct control over searches
const restaurants = await client.searchBusinessProfiles('', 'restaurant', 5);
console.log(`Found ${restaurants.count} restaurants`);

// Combined with your own LLM for intelligent routing  
const response = await client.intelligentSearch('Find me coffee shops in Seattle');
console.log(response);
```

## 🔐 Authentication

The API supports multiple authentication methods:

### Method 1: API Key (Recommended for All Endpoints)
```http
GET /api/stats
X-API-Key: your_api_key_here
```

### Method 2: Bearer Token
```http
GET /api/stats
Authorization: Bearer your_bearer_token_here
```

### Method 3: Chat Endpoint (API Key Only)
The `/api/chat` endpoint only requires your API key. The OpenAI integration is handled server-side.

```http
POST /api/chat
X-API-Key: your_api_key_here
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Find me some coffee shops"}
  ],
  "stream": true
}
```



## 📊 Rate Limiting

- **Default Limit**: 100 requests per minute per IP
- **Rate Limit Headers**: Check `X-Rate-Limit-Remaining` in responses
- **Rate Limit Exceeded**: Returns HTTP 429 with `Retry-After` header

**Note**: Chat endpoints may consume more rate limit due to potential multiple internal API calls.

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

## 📝 Quick Start Examples

### Strategy 1: Simple Client (No LLM) - Chat API

Perfect for applications that want natural language search without implementing their own LLM.

```python
# Simple Python client using chat API
import requests
import json

def search_businesses(query, api_key):
    """Simple business search using natural language"""
    response = requests.post(
        'https://api.synvya.com/api/chat',
        headers={'X-API-Key': api_key, 'Content-Type': 'application/json'},
        json={
            'messages': [{'role': 'user', 'content': query}],
            'stream': False  # Non-streaming for simplicity
        }
    )
    
    result = response.json()
    return result['message']['content']

# Usage - no LLM knowledge required
api_key = "your_api_key_here"
response = search_businesses("Find me coffee shops in Seattle", api_key)
print(response)
```

```javascript
// Simple JavaScript client using chat API
async function searchBusinesses(query, apiKey) {
  const response = await fetch('https://api.synvya.com/api/chat', {
    method: 'POST',
    headers: {
      'X-API-Key': apiKey,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      messages: [{ role: 'user', content: query }],
      stream: false
    })
  });
  
  const result = await response.json();
  return result.message.content;
}

// Usage - no LLM knowledge required
searchBusinesses("Find me restaurants near downtown", "your_api_key_here")
  .then(response => console.log(response));
```

### Strategy 2: Advanced Client (Have LLM) - Direct API Access

Perfect for applications with existing LLM capabilities that want full control over searches.

```python
# Advanced Python client using direct API endpoints
import requests
import json

class SynvyaDirectClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

    def search_profiles(self, query: str, limit: int = 10):
        """Direct search for products and services"""
        url = f"{self.base_url}/api/search"
        data = {"query": query, "limit": limit}
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def search_business_profiles(self, query: str = "", business_type: str = "", limit: int = 10):
        """Direct search for businesses by name or type"""
        url = f"{self.base_url}/api/search_by_business_type"
        data = {"query": query, "business_type": business_type, "limit": limit}
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def get_profile(self, pubkey: str):
        """Get specific business profile by public key"""
        url = f"{self.base_url}/api/profile/{pubkey}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_business_types(self):
        """Get available business types"""
        url = f"{self.base_url}/api/business_types"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_stats(self):
        """Get database statistics"""
        url = f"{self.base_url}/api/stats"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

# Usage example - direct control with your own LLM integration
client = SynvyaDirectClient("https://api.synvya.com", "your_api_key")

# Direct API calls for maximum control
restaurants = client.search_business_profiles(business_type="restaurant", limit=5)
print(f"Found {restaurants['count']} restaurants")

# Combine multiple searches for complex queries
business_types = client.get_business_types()
coffee_shops = client.search_business_profiles(query="coffee", business_type="restaurant")
# Your LLM can process and combine these results
```

```typescript
// Advanced TypeScript client using direct API endpoints
interface NostrProfile {
  pubkey: string;
  name?: string;
  display_name?: string;
  about?: string;
  picture?: string;
  website?: string;
  business_type?: string;
}

interface SearchResponse {
  success: boolean;
  count: number;
  profiles: NostrProfile[];
  query?: string;
}

class SynvyaDirectClient {
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

  async getBusinessTypes(): Promise<{ success: boolean; business_types: string[] }> {
    return this.request<{ success: boolean; business_types: string[] }>('/api/business_types');
  }

  async getStats(): Promise<{ success: boolean; stats: any }> {
    return this.request<{ success: boolean; stats: any }>('/api/stats');
  }
}

// Usage example - advanced control with your own LLM
const client = new SynvyaDirectClient('https://api.synvya.com', 'your_api_key');

// Direct API usage for maximum control
const restaurants = await client.searchBusinessProfiles('', 'restaurant', 5);
console.log(`Found ${restaurants.count} restaurants`);

// Your LLM can intelligently route and combine these API calls
const businessTypes = await client.getBusinessTypes();
// Use your LLM to determine best search strategy based on user query
```

### cURL Examples

#### Strategy 1: Simple Client - Chat API
```bash
# Natural language search using chat API
curl -X POST "https://api.synvya.com/api/chat" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Find me coffee shops in Seattle"}
    ],
    "stream": false
  }'
```

#### Strategy 2: Advanced Client - Direct API Endpoints

##### Search Products and Services
```bash
curl -X POST "https://api.synvya.com/api/search" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "bitcoin", "limit": 5}'
```

##### Search Business Profiles
```bash
curl -X POST "https://api.synvya.com/api/search_by_business_type" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "coffee", "business_type": "restaurant", "limit": 10}'
```

##### Get Business Profile by Public Key
```bash
curl -X GET "https://api.synvya.com/api/profile/57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991" \
  -H "X-API-Key: your_api_key"
```

##### Get Business Types
```bash
curl -X GET "https://api.synvya.com/api/business_types" \
  -H "X-API-Key: your_api_key"
```

##### Get Statistics
```bash
curl -X GET "https://api.synvya.com/api/stats" \
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

### Strategy Selection

#### Choose Chat API (Strategy 1) When:
- ✅ You don't have existing LLM integration
- ✅ You want rapid development and deployment
- ✅ Natural language interface is sufficient for your use case
- ✅ You prefer server-side AI processing
- ✅ You want to minimize complexity

#### Choose Direct API (Strategy 2) When:
- ✅ You already have LLM capabilities (OpenAI, Anthropic, etc.)
- ✅ You need fine-grained control over search logic
- ✅ You want to optimize for performance and latency
- ✅ You need custom result processing or formatting
- ✅ You want to combine multiple searches intelligently

### General Best Practices

#### 1. **Rate Limiting**
- Implement exponential backoff for 429 responses
- Cache results when appropriate
- **Chat API**: May consume more rate limit due to internal processing
- **Direct API**: More predictable rate limit consumption

#### 2. **Error Handling**
- Always handle HTTP errors gracefully
- Log errors for debugging
- Provide user-friendly error messages
- **Chat API**: Handle streaming errors and incomplete responses
- **Direct API**: Handle individual endpoint errors

#### 3. **Input Validation**
- **Chat API**: Validate message format and content length
- **Direct API**: Validate public keys (64-character hex strings), query lengths
- Sanitize user input in both cases

#### 4. **Performance**
- **Chat API**: Consider streaming for better perceived performance
- **Direct API**: Use connection pooling for multiple requests
- Implement request timeouts
- Consider pagination for large result sets

#### 5. **Security**
- Store API keys securely (environment variables)
- Use HTTPS in production
- Validate SSL certificates
- **Chat API**: Server handles OpenAI key management
- **Direct API**: You manage your own LLM keys if using one

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