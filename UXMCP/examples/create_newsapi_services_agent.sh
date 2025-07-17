#!/bin/bash

# Configuration
API_URL="http://localhost:8000"
NEWSAPI_KEY="763084f248fe4cf5ba9f28a4a11d9e04"
LLM_PROFILE="ToolCreator"

echo "🤖 Creating NewsAPI Services with AI Agent for UXMCP"
echo "=================================================="

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "❌ jq is required but not installed. Please install jq first."
    exit 1
fi

# Function to create a service using the agent
create_service_with_agent() {
    local name=$1
    local type=$2
    local description=$3
    local api_doc=$4
    
    echo ""
    echo "🤖 Creating service with AI Agent: $name"
    echo "   Type: $type"
    echo "   Description: $description"
    
    # Create the service using the agent endpoint
    echo "   🔄 Agent is working..."
    
    # Create JSON payload
    AGENT_PAYLOAD=$(jq -n \
        --arg name "$name" \
        --arg type "$type" \
        --arg description "$description" \
        --arg llm_profile "$LLM_PROFILE" \
        --arg api_doc "$api_doc" \
        --arg api_base_url "https://newsapi.org/v2" \
        --arg api_key "$NEWSAPI_KEY" \
        '{
            name: $name,
            service_type: $type,
            description: $description,
            llm_profile: $llm_profile,
            api_documentation: $api_doc,
            api_base_url: $api_base_url,
            api_key: $api_key
        }')
    
    # Send request to agent and process SSE stream
    curl -N -s -X POST "$API_URL/agent/create-service" \
        -H "Content-Type: application/json" \
        -d "$AGENT_PAYLOAD" | while IFS= read -r line
    do
        # Skip empty lines
        if [ -z "$line" ]; then
            continue
        fi
        
        # Extract data from SSE format
        if [[ "$line" =~ ^data:\ (.+)$ ]]; then
            json_data="${BASH_REMATCH[1]}"
            
            # Parse the JSON data
            step=$(echo "$json_data" | jq -r '.step // ""')
            message=$(echo "$json_data" | jq -r '.message // ""')
            
            # Display progress based on step
            case "$step" in
                "analyzing")
                    echo "   🔍 $message"
                    ;;
                "generating")
                    echo "   ✨ $message"
                    ;;
                "creating")
                    echo "   📝 $message"
                    ;;
                "activating")
                    echo "   🚀 $message"
                    ;;
                "testing")
                    echo "   🧪 $message"
                    ;;
                "debugging")
                    echo "   🔧 $message"
                    ;;
                "fixed")
                    echo "   ✅ $message"
                    ;;
                "success")
                    echo "   🎉 $message"
                    service_id=$(echo "$json_data" | jq -r '.service_id // ""')
                    if [ -n "$service_id" ]; then
                        echo "   📍 Service ID: $service_id"
                    fi
                    ;;
                "error")
                    echo "   ❌ $message"
                    error=$(echo "$json_data" | jq -r '.error // ""')
                    if [ -n "$error" ]; then
                        echo "   Error details: $error"
                    fi
                    ;;
                "completed")
                    echo "   ✨ Agent finished!"
                    ;;
                *)
                    if [ -n "$message" ]; then
                        echo "   ℹ️  $message"
                    fi
                    ;;
            esac
        fi
    done
    
    echo "   ✅ Service creation process completed"
}

# Service 1: Top Headlines
create_service_with_agent \
    "news_top_headlines" \
    "tool" \
    "Get top headlines for a specific country with optional category filter. Route should be /api/news/headlines/{country} with GET method." \
    "NewsAPI Top Headlines Endpoint

Base URL: https://newsapi.org/v2
Endpoint: /top-headlines

Parameters:
- country: from route parameter (2-letter ISO code like us, fr, gb, de)
- category: optional query parameter (business, entertainment, general, health, science, sports, technology)
- pageSize: optional query parameter (default 10, max 100)
- apiKey: provided

Example: GET /top-headlines?country=us&category=technology&pageSize=10&apiKey=KEY

Response format:
{
  \"status\": \"ok\",
  \"totalResults\": 38,
  \"articles\": [
    {
      \"source\": {\"id\": \"cnn\", \"name\": \"CNN\"},
      \"author\": \"Author Name\",
      \"title\": \"Article Title\",
      \"description\": \"Article description\",
      \"url\": \"https://...\",
      \"urlToImage\": \"https://...\",
      \"publishedAt\": \"2024-01-13T10:00:00Z\",
      \"content\": \"Full content...\"
    }
  ]
}"

# Service 2: Search Everything
create_service_with_agent \
    "news_search" \
    "tool" \
    "Search news articles with filters. Route should be /api/news/search with POST method. Accept body with: query, language, date_from, date_to, sort_by, page_size" \
    "NewsAPI Everything Endpoint

Base URL: https://newsapi.org/v2
Endpoint: /everything

The handler should accept POST body with:
- query: search keywords (required)
- language: 2-letter code (optional, default 'en')
- date_from: ISO date string (optional)
- date_to: ISO date string (optional)
- sort_by: relevancy/popularity/publishedAt (optional, default 'publishedAt')
- page_size: number (optional, default 20, max 100)

Map body parameters to API parameters:
- q: from body.query (URL encode it)
- language: from body.language
- from: from body.date_from
- to: from body.date_to
- sortBy: from body.sort_by
- pageSize: from body.page_size
- apiKey: provided

Response has same format as top-headlines."

# Service 3: News by Source
create_service_with_agent \
    "news_by_source" \
    "tool" \
    "Get latest articles from a specific news source. Route should be /api/news/source/{source_id} with GET method." \
    "NewsAPI Top Headlines by Source

Base URL: https://newsapi.org/v2
Endpoint: /top-headlines

Parameters:
- sources: from route parameter source_id (e.g., 'bbc-news', 'cnn', 'techcrunch')
- pageSize: optional query parameter (default 20)
- apiKey: provided

Popular source IDs:
- bbc-news: BBC News
- cnn: CNN
- the-verge: The Verge
- techcrunch: TechCrunch
- wired: Wired
- bloomberg: Bloomberg
- reuters: Reuters

Example: GET /top-headlines?sources=bbc-news&apiKey=KEY"

# Service 4: Trending Topics
create_service_with_agent \
    "news_trending" \
    "tool" \
    "Get trending news about a topic from last 24 hours. Route should be /api/news/trending/{topic} with GET method." \
    "Get trending articles from last 24 hours sorted by popularity

Use /everything endpoint with:
- q: topic from route parameter (URL encode it)
- from: calculate using datetime.now() - timedelta(days=1), format as ISO string
- to: current time as ISO string
- sortBy: 'popularity'
- language: 'en' (or from optional query param)
- pageSize: 20 (or from optional query param)
- apiKey: provided

Calculate dates dynamically, don't hardcode them."

# Service 5: Daily Summary (Resource)
create_service_with_agent \
    "news_daily_summary" \
    "resource" \
    "Get a markdown summary of today's top news. Route should be /api/news/summary/today with GET method. Fetch headlines from multiple categories and format as markdown." \
    "This resource fetches headlines from multiple categories and formats as markdown.

Make multiple requests to /top-headlines with different categories:
- general (3 articles)
- technology (3 articles)
- business (3 articles)
- science (3 articles)

Use country='us' and pageSize=3 for each request.

Format the response as markdown:
# Daily News Summary

## General News
- **Title** (Source) - Description [Read more](url)

## Technology
...

Return with mimeType: 'text/markdown'"

echo ""
echo "✅ Done! The AI Agent has created all services."
echo ""
echo "🔍 You can check the services at:"
echo "  http://localhost:5173/services"
echo ""
echo "📡 API Examples:"
echo "  curl http://localhost:8000/api/news/headlines/us"
echo "  curl http://localhost:8000/api/news/headlines/fr?category=technology"
echo "  curl http://localhost:8000/api/news/source/bbc-news"
echo "  curl http://localhost:8000/api/news/trending/AI"
echo ""
echo "For search:"
echo "  curl -X POST http://localhost:8000/api/news/search \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": \"ChatGPT\", \"sort_by\": \"popularity\"}'"