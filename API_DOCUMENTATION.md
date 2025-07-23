# Documentation API UXMCP

## Vue d'ensemble

UXMCP (Universal eXtensible MCP) est un gestionnaire de services MCP (Model Context Protocol) dynamique permettant de créer, stocker et activer des services à la volée via une interface web. L'API backend est construite avec FastAPI et offre une architecture RESTful complète avec support SSE (Server-Sent Events) pour les opérations temps réel.

## Architecture

### Stack Technique
- **Framework**: FastAPI (Python)
- **Base de données**: MongoDB (via Motor pour l'async)
- **MCP**: FastMCP 2.0
- **Authentification**: Aucune (prévu pour environnement local/développement)
- **CORS**: Activé pour toutes les origines (configurable en production)

### Composants Principaux
1. **Services MCP**: Gestion des tools, resources et prompts
2. **Agents IA**: Système d'agents avec configuration 7D
3. **AI Agent**: Agent autonome pour création automatique de services
4. **LLM Profiles**: Gestion des profils de modèles de langage
5. **Meta-Agent**: Création automatique d'agents et d'outils
6. **Meta-Chat**: Système de chat intelligent avec amélioration de requêtes
7. **Feedback System**: Collecte et analyse de feedbacks utilisateurs
8. **Demos System**: Hébergement de démos HTML/CSS/JS interactives
9. **Chat Interface**: Interface de chat intégrée
10. **Logging System**: Système de logs MongoDB intégré

## Endpoints API

### 🏠 Root & Health

#### GET /
Endpoint racine fournissant les liens vers les principales ressources.

**Response:**
```json
{
  "message": "UXMCP - Dynamic MCP Service Manager",
  "endpoints": {
    "services": "/services",
    "llm_profiles": "/llms",
    "documentation": "/docs",
    "mcp_server": "/mcp",
    "openapi": "/docs"
  }
}
```

#### GET /health
Vérification de l'état de santé du service.

**Response:**
```json
{
  "status": "healthy"
}
```

### 📦 Services MCP (/services)

#### POST /services/
Créer un nouveau service MCP.

**Request Body:**
```json
{
  "name": "string",
  "service_type": "tool|resource|prompt",
  "route": "/api/my-service",
  "method": "GET|POST|PUT|DELETE",
  "params": [
    {
      "name": "param1",
      "type": "string",
      "required": true,
      "description": "Description du paramètre"
    }
  ],
  "code": "def handler(**params):\n    return {'result': 'ok'}",
  "dependencies": ["requests", "numpy"],
  "input_schema": {},  // Optionnel: schéma JSON pour MCP
  "output_schema": {}, // Optionnel: schéma de sortie pour les tools
  "llm_profile": "profile-name", // Optionnel
  "description": "Description du service",
  "documentation": "Documentation détaillée",
  "mime_type": "text/plain", // Pour les resources
  "prompt_template": "Template {{arg}}", // Pour les prompts
  "prompt_args": [], // Arguments du prompt
  "active": false
}
```

**Response:** Service object avec ID généré

#### GET /services/
Lister tous les services.

**Query Parameters:**
- `skip`: int (default: 0)
- `limit`: int (default: 100)
- `active_only`: bool (default: false)

#### GET /services/summary
Obtenir une liste simplifiée des services pour l'analyse LLM.

**Response:**
```json
[
  {
    "id": "service-id",
    "name": "service-name",
    "description": "Description",
    "type": "tool",
    "route": "/api/service",
    "active": true
  }
]
```

#### GET /services/{service_id}
Obtenir un service spécifique.

#### PUT /services/{service_id}
Mettre à jour un service.

#### DELETE /services/{service_id}
Supprimer un service (doit être désactivé).

#### POST /services/{service_id}/activate
Activer un service et monter son endpoint.

#### POST /services/{service_id}/deactivate
Désactiver un service et démonter son endpoint.

#### POST /services/{service_id}/test
Tester un service avec son profil LLM.

#### POST /services/generate
Générer un service automatiquement via LLM.

**Request Body:**
```json
{
  "name": "service-name",
  "service_type": "tool",
  "route": "/api/generated",
  "method": "GET",
  "description": "Ce que doit faire le service",
  "llm_profile": "profile-name"
}
```

### 🤖 Agents (/agents)

#### POST /agents/
Créer un nouvel agent IA.

**Request Body:**
```json
{
  "name": "agent-name",
  "llm_profile": "profile-name",
  "mcp_services": ["service1", "service2"],
  "system_prompt": "You are a helpful assistant",
  "pre_prompt": "Always be polite",
  "endpoint": "/api/agent/my-agent",
  "input_schema": "text", // ou objet JSON schema
  "output_schema": "text", // ou objet JSON schema
  "description": "Agent description",
  "active": false,
  
  // Configuration avancée
  "temperature": 0.7,
  "max_tokens": 4096,
  "allow_parallel_tool_calls": true,
  "require_tool_use": false,
  "max_iterations": 5,
  
  // Configuration 7D
  "backstory": "15 years experience as...",
  "objectives": ["Help users", "Provide accurate info"],
  "constraints": ["Never share PII", "Be factual"],
  "memory_enabled": true,
  "memory_config": {
    "max_memories": 1000,
    "embedding_model": "all-MiniLM-L6-v2",
    "search_k": 5
  },
  "reasoning_strategy": "chain-of-thought",
  "reasoning_config": {},
  "personality_traits": {
    "tone": "professional",
    "verbosity": "balanced",
    "empathy": "moderate",
    "humor": "subtle"
  },
  "decision_policies": {
    "confidence_threshold": 0.8,
    "require_confirmation": [],
    "auto_correct_errors": true,
    "explain_decisions": false,
    "max_retries": 3
  }
}
```

#### GET /agents/
Lister tous les agents.

**Query Parameters:**
- `skip`: int (default: 0)
- `limit`: int (default: 100)
- `active_only`: bool (default: false)

#### GET /agents/{agent_id}
Obtenir un agent spécifique.

#### PUT /agents/{agent_id}
Mettre à jour un agent.

#### DELETE /agents/{agent_id}
Supprimer un agent (désactive automatiquement si actif).

#### POST /agents/{agent_id}/activate
Activer un agent et monter son endpoint.

#### POST /agents/{agent_id}/deactivate
Désactiver un agent et démonter son endpoint.

#### POST /agents/{agent_id}/execute
Exécuter un agent directement (pour tests).

**Request Body:**
```json
{
  "input": "text input" ou {"structured": "input"},
  "conversation_history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ],
  "execution_options": {
    "timeout": 30000
  }
}
```

#### GET /agents/{agent_id}/validate
Valider les dépendances d'un agent.

### 🧠 Profils LLM (/llms)

#### POST /llms/
Créer un profil LLM.

**Request Body:**
```json
{
  "name": "profile-name",
  "provider": "openai|anthropic|groq|ollama|openrouter",
  "model": "gpt-4o",
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1", // Optionnel
  "temperature": 0.7,
  "max_tokens": 4096,
  "active": true,
  "is_default": false,
  "headers": {} // Headers additionnels optionnels
}
```

#### GET /llms/
Lister tous les profils LLM.

#### GET /llms/{profile_id}
Obtenir un profil LLM spécifique.

#### PUT /llms/{profile_id}
Mettre à jour un profil LLM.

#### DELETE /llms/{profile_id}
Supprimer un profil LLM.

### 💬 Chat Interface (/api/chat)

#### POST /api/chat/
Envoyer un message au LLM sélectionné.

**Request Body:**
```json
{
  "llm_profile_id": "profile-id",
  "message": "User message",
  "conversation_history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "LLM response",
  "error": null,
  "detail": null,
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  },
  "model": "gpt-4o"
}
```

### 🛠️ Meta-Agent (/meta-agent)

#### POST /meta-agent/create
Créer un agent automatiquement avec SSE pour le suivi du progrès.

**Request Body:**
```json
{
  "requirement": {
    "purpose": "Je veux un agent qui...",
    "use_cases": ["Cas d'usage 1", "Cas d'usage 2"],
    "domain": "customer_service",
    "capabilities": ["capability1", "capability2"],
    "constraints": ["constraint1"],
    "output_format": "structured",
    "complexity": "simple|moderate|complex",
    "llm_profile": "profile-name"
  },
  "auto_activate": true,
  "create_missing_tools": true,
  "test_agent": true,
  "max_tools_to_create": 5
}
```

**Response:** Server-Sent Events stream avec mises à jour du progrès

#### POST /meta-agent/analyze
Analyser les besoins sans créer d'agent.

#### POST /meta-agent/suggest-tools
Suggérer des outils pour un objectif donné.

**Request Body:**
```json
{
  "purpose": "What you want to accomplish",
  "domain": "general",
  "llm_profile": "profile-name"
}
```

#### GET /meta-agent/templates
Obtenir des modèles d'agents prédéfinis.

### 📊 Logs (/logs)

#### GET /logs/app
Obtenir les logs de l'application.

**Query Parameters:**
- `level`: DEBUG|INFO|WARNING|ERROR
- `module`: string (filtre par module)
- `search`: string (recherche dans les messages)
- `start_time`: datetime
- `end_time`: datetime
- `limit`: int (default: 100, max: 1000)
- `skip`: int (default: 0)

#### GET /logs/services/{service_id}
Obtenir les logs d'un service spécifique.

#### GET /logs/services/{service_id}/latest
Obtenir les derniers logs d'un service.

#### GET /logs/execution/{execution_id}
Obtenir tous les logs d'une exécution spécifique.

#### DELETE /logs/services/{service_id}/old
Supprimer les anciens logs d'un service.

**Query Parameters:**
- `days`: int (default: 30, max: 365)

#### GET /logs/services/stats/{service_id}
Obtenir les statistiques de logs d'un service.

#### GET /logs/search
Rechercher dans tous les logs de services.

### 📚 Documentation (/docs)

#### GET /docs/
Générer la documentation Markdown de tous les services actifs.

**Response:** Plain text (Markdown)

### 🔧 Debug MCP (/debug)

#### GET /debug/mcp/config
Obtenir la configuration MCP pour les clients.

#### GET /debug/mcp/info
Obtenir les informations sur les capacités MCP disponibles.

**Response:**
```json
{
  "server_name": "UXMCP Dynamic Services",
  "capabilities": {
    "tools": 5,
    "resources": 3,
    "prompts": 2
  },
  "tools": [...],
  "resources": [...],
  "prompts": [...]
}
```

### 🧠 Agent Memory (/agents/{agent_id}/memory)

#### GET /agents/{agent_id}/memory
Récupérer les mémoires récentes d'un agent.

**Query Parameters:**
- `limit`: int (default: 50) - Nombre maximum de mémoires
- `content_type`: string - Filtrer par type (user_message, agent_response, preference, stored_knowledge)
- `user_id`: string - Filtrer par utilisateur

#### POST /agents/{agent_id}/memory/search
Rechercher dans les mémoires d'un agent avec recherche sémantique.

**Request Body:**
```json
{
  "query": "search query",
  "k": 5,
  "content_types": ["user_message", "agent_response"],
  "min_importance": 0.5,
  "date_from": "2025-01-01T00:00:00",
  "date_to": "2025-12-31T23:59:59"
}
```

#### GET /agents/{agent_id}/memory/summary
Obtenir un résumé statistique des mémoires de l'agent.

#### DELETE /agents/{agent_id}/memory
Effacer toutes les mémoires d'un agent.

**Query Parameters:**
- `user_id`: string - Effacer seulement pour un utilisateur spécifique

#### DELETE /agents/{agent_id}/memory/{memory_id}
Supprimer une mémoire spécifique.

#### POST /agents/{agent_id}/memory/save-conversation
Sauvegarder une conversation complète en mémoire.

**Request Body:**
```json
{
  "conversation": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "conversation_id": "optional-id",
  "user_id": "optional-user-id",
  "metadata": {}
}
```

#### GET /agents/{agent_id}/memory/stats
Obtenir des statistiques détaillées sur la mémoire de l'agent.

### 💬 Meta-Chat (/meta-chat)

#### POST /meta-chat/query
Traiter une requête via le système meta-chat.

**Request Body:**
```json
{
  "message": "User message",
  "llm_profile": "profile-name",
  "conversation_history": [],
  "prefer_direct_answer": false,
  "create_agent_if_needed": true
}
```

#### POST /meta-chat/enhance
Améliorer une requête utilisateur et des instructions pour de meilleurs résultats.

**Request Body:**
```json
{
  "query": "What is the weather like",
  "instructions": "Show as a nice table",
  "llm_profile": "profile-name"
}
```

**Response:**
```json
{
  "enhanced_query": "Get current weather conditions including temperature, humidity, wind speed, and forecast for the next 24 hours",
  "enhanced_instructions": "Present the weather data in a well-formatted HTML table with headers, alternating row colors, and weather icons",
  "suggested_sources": ["OpenWeatherMap API", "Weather.gov", "Local weather station data"],
  "query_type": "weather_information",
  "complexity": "simple"
}
```

### 📝 Feedback System (/feedback)

#### POST /feedback/
Créer un nouveau feedback.

**Request Body:**
```json
{
  "rating": "positive",  // ou "negative"
  "message": "Great response!",
  "agent_used": "agent-name",
  "query": "Original user query",
  "response": "Agent response",
  "metadata": {
    "response_time": 1.23,
    "sources_used": ["source1", "source2"]
  }
}
```

**Response:** Feedback object avec ID généré

#### GET /feedback/{feedback_id}
Obtenir un feedback spécifique.

**Response:**
```json
{
  "id": "feedback-id",
  "rating": "positive",
  "message": "Great response!",
  "agent_used": "agent-name",
  "created_at": "2025-01-01T00:00:00",
  "query": "Original user query",
  "response": "Agent response",
  "metadata": {}
}
```

#### GET /feedback/
Lister les feedbacks avec pagination et filtres.

**Query Parameters:**
- `page`: int (default: 1)
- `per_page`: int (default: 20, max: 100)
- `rating`: string (positive|negative)
- `agent_used`: string (nom de l'agent)
- `start_date`: datetime
- `end_date`: datetime

**Response:**
```json
{
  "feedbacks": [...],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "pages": 5
}
```

#### GET /feedback/stats/overview
Obtenir des statistiques globales sur les feedbacks.

**Response:**
```json
{
  "total_feedbacks": 1000,
  "positive_count": 750,
  "negative_count": 250,
  "positive_percentage": 75.0,
  "by_date": {
    "2025-01-01": {"positive": 10, "negative": 2},
    "2025-01-02": {"positive": 15, "negative": 3}
  },
  "most_used_agents": [
    {"agent": "agent1", "count": 150},
    {"agent": "agent2", "count": 100}
  ]
}
```

#### GET /feedback/stats/by-agent
Obtenir des statistiques de feedback par agent.

**Response:**
```json
{
  "agents": [
    {
      "agent": "agent-name",
      "total": 100,
      "positive": 80,
      "negative": 20,
      "positive_percentage": 80.0,
      "average_response_time": 1.5
    }
  ]
}
```

### 🎨 Demos (/demos)

#### POST /demos/
Créer une nouvelle démo HTML/CSS/JS interactive.

**Request Body:**
```json
{
  "name": "weather-dashboard",
  "title": "Weather Dashboard Demo",
  "description": "Interactive weather visualization",
  "html_content": "<!DOCTYPE html><html>...</html>",
  "tags": ["weather", "dashboard", "visualization"],
  "metadata": {
    "author": "John Doe",
    "version": "1.0"
  }
}
```

**Response:** Demo object avec ID généré

#### GET /demos/
Lister toutes les démos avec recherche optionnelle.

**Query Parameters:**
- `skip`: int (default: 0)
- `limit`: int (default: 20, max: 100)
- `search`: string (recherche dans nom, titre, description)

**Response:**
```json
{
  "demos": [
    {
      "id": "demo-id",
      "name": "weather-dashboard",
      "title": "Weather Dashboard Demo",
      "description": "Interactive weather visualization",
      "tags": ["weather", "dashboard"],
      "created_at": "2025-01-01T00:00:00",
      "updated_at": "2025-01-01T00:00:00",
      "metadata": {}
    }
  ],
  "total": 50,
  "page": 1,
  "per_page": 20
}
```

#### GET /demos/{name}
Servir le contenu HTML d'une démo par son nom.

**Response:** HTML content (text/html)

#### GET /demos/details/{demo_id}
Obtenir les détails complets d'une démo.

**Response:** Demo object complet avec html_content

#### PUT /demos/{demo_id}
Mettre à jour les métadonnées d'une démo.

**Request Body:**
```json
{
  "title": "Updated Title",
  "description": "Updated description",
  "tags": ["new", "tags"],
  "metadata": {}
}
```

#### DELETE /demos/{demo_id}
Supprimer une démo.

### 🤖 AI Agent (/agent)

#### POST /agent/create-service
Créer un service automatiquement via un agent autonome.

Ce endpoint utilise Server-Sent Events (SSE) pour transmettre le progrès en temps réel.

**Request Body:**
```json
{
  "name": "weather_service",
  "description": "Service that fetches weather data for any city",
  "service_type": "tool",
  "llm_profile": "gpt4-profile",
  // Optionnel pour API externes
  "api_documentation": "API docs here...",
  "api_base_url": "https://api.example.com",
  "api_key": "your-api-key",
  "api_headers": {"X-Custom": "value"}
}
```

**Response:** Server-Sent Events stream
```
data: {"step": "starting", "message": "Initializing agent..."}

data: {"step": "analyzing", "message": "Analyzing service requirements..."}

data: {"step": "generating", "message": "Generating service code..."}

data: {"step": "testing", "message": "Testing service...", "test_result": {...}}

data: {"step": "fixing", "message": "Fixing errors...", "error": "...", "attempt": 1}

data: {"step": "completed", "message": "Service created successfully", "service_id": "..."}
```

#### POST /agent/analyze
Analyser une description de service sans la créer.

**Request Body:**
```json
{
  "description": "I need a service that...",
  "service_type": "tool",
  "llm_profile": "profile-name"
}
```

**Response:**
```json
{
  "analysis": {
    "suggested_name": "my_service",
    "suggested_route": "/api/my-service",
    "method": "POST",
    "parameters": [...],
    "dependencies": ["requests"],
    "has_output_schema": true,
    "documentation_preview": "This service..."
  },
  "preview_code": "def handler(**params):\n    ...",
  "service_type": "tool"
}
```

#### GET /agent/status
Obtenir le statut du système agent.

**Response:**
```json
{
  "status": "active",
  "version": "1.0.0",
  "capabilities": [
    "create_service",
    "test_service",
    "debug_service",
    "auto_fix_errors"
  ]
}
```

#### GET /agent/tools
Obtenir la liste des outils disponibles pour l'agent.

**Response:**
```json
{
  "tools": [
    {
      "name": "create_service",
      "description": "Create a new service in UXMCP"
    },
    {
      "name": "test_service",
      "description": "Test a service with sample inputs"
    }
  ],
  "description": "Tools available to the agent for service creation and management"
}
```

#### GET /agent/documentation
Obtenir la documentation utilisée par l'agent comme contexte.

**Response:**
```json
{
  "documentation": {
    "service_guide": "Complete guide for creating UXMCP services...",
    "error_solutions": "Common errors and their solutions..."
  },
  "description": "Documentation used by the agent to understand UXMCP services"
}
```

## Patterns Architecturaux

### 1. **Système de Routage Dynamique**
- Les services et agents créent dynamiquement des endpoints FastAPI
- Montage/démontage à chaud sans redémarrage
- Gestion des collisions de routes

### 2. **Gestionnaire MCP (MCPManager)**
- Singleton gérant tous les services MCP
- Enregistrement dynamique des tools/resources/prompts
- Exécution sécurisée du code utilisateur

### 3. **Système de Logs MongoDB**
- Logs structurés avec timestamps et niveaux
- Logs par service et par exécution
- Rotation automatique des logs

### 4. **Architecture 7D des Agents**
1. **Backstory**: Identité et contexte
2. **Objectives**: Missions claires
3. **Constraints**: Limites et restrictions
4. **Memory**: Persistance du contexte
5. **Reasoning**: Stratégies de raisonnement
6. **Personality**: Style de communication
7. **Policies**: Règles de décision

### 5. **Meta-Agent System**
- Analyse automatique des besoins
- Création d'agents et d'outils à la volée
- Matching intelligent avec services existants
- Progress tracking via SSE

### 6. **Système de Mémoire Active pour Agents**
- **Mémoire persistante** : ChromaDB + MongoDB pour stockage long terme
- **Mémoire de travail** : Collection avec TTL pour mémoire court terme
- **Outils mémoire intégrés** : 3 outils MCP automatiquement injectés
  - `memory_search` : Recherche sémantique dans les souvenirs
  - `memory_store` : Sauvegarde explicite d'informations importantes
  - `memory_analyze` : Analyse des patterns et insights
- **Apprentissage continu** : Les agents apprennent de leurs interactions
- **Contexte intelligent** : Chargement automatique du contexte pertinent

### 7. **AI Agent System**
- **Agent autonome** : Création automatique de services via LLM
- **Auto-debugging** : Correction automatique des erreurs
- **Test itératif** : Test et amélioration continue jusqu'au succès
- **Support API externes** : Intégration facile avec APIs tierces
- **Documentation contextuelle** : L'agent comprend le système UXMCP

### 8. **Feedback System**
- **Collecte de feedback** : Rating positif/négatif avec contexte
- **Analytics intégrés** : Statistiques par agent et globales
- **Amélioration continue** : Les feedbacks guident l'optimisation

### 9. **Demos System**
- **HTML/CSS/JS interactif** : Démos complètes hébergées
- **Gestion par tags** : Organisation et recherche faciles
- **Versioning intégré** : Métadonnées de version
- **Serving direct** : Accès par nom d'URL simple

### 10. **Meta-Chat Enhancement**
- **Amélioration de requêtes** : Transformation de requêtes vagues en précises
- **Instructions optimisées** : Génération d'instructions HTML détaillées
- **Suggestion de sources** : Recommandations de sources de données
- **Classification intelligente** : Type et complexité de requête

## Sécurité

### Points d'Attention
- ⚠️ **Pas d'authentification** : Prévu pour développement local
- ⚠️ **CORS ouvert** : Accepte toutes les origines
- ⚠️ **Exécution de code** : Le code des services est exécuté dynamiquement
- ⚠️ **API Keys** : Stockées en clair dans MongoDB

### Recommandations Production
1. Implémenter l'authentification JWT/OAuth
2. Configurer CORS avec origines spécifiques
3. Sandboxer l'exécution du code utilisateur
4. Chiffrer les API keys sensibles
5. Limiter les rate limits
6. Valider strictement les inputs

## Exemples d'Utilisation

### Créer un Service Simple
```python
# POST /services/
{
  "name": "weather_service",
  "service_type": "tool",
  "route": "/api/weather",
  "method": "GET",
  "params": [{
    "name": "city",
    "type": "string",
    "required": true,
    "description": "City name"
  }],
  "code": """
def handler(city):
    # Simuler une réponse météo
    return {
        'city': city,
        'temperature': 22,
        'condition': 'sunny'
    }
""",
  "description": "Get weather for a city"
}
```

### Créer un Agent avec Outils
```python
# POST /agents/
{
  "name": "travel_assistant",
  "llm_profile": "gpt4-profile",
  "mcp_services": ["weather_service", "flight_search"],
  "system_prompt": "You are a helpful travel assistant.",
  "endpoint": "/api/agent/travel",
  "backstory": "20 years experience as a travel agent",
  "objectives": ["Help plan trips", "Find best deals"],
  "memory_enabled": true
}
```

### Utiliser le Meta-Agent
```python
# POST /meta-agent/create
{
  "requirement": {
    "purpose": "I need a customer support agent that can handle refunds and track orders",
    "use_cases": [
      "Process refund requests",
      "Check order status",
      "Update customer information"
    ],
    "domain": "e-commerce",
    "llm_profile": "gpt4-profile"
  },
  "auto_activate": true,
  "create_missing_tools": true
}
```

### Créer un Service via AI Agent
```python
# POST /agent/create-service
{
  "name": "stock_price_checker",
  "description": "Get real-time stock prices and market data for any ticker symbol",
  "service_type": "tool",
  "llm_profile": "gpt4-profile",
  "api_documentation": "Alpha Vantage API docs...",
  "api_base_url": "https://www.alphavantage.co/query",
  "api_key": "your-api-key"
}
```

### Collecter du Feedback
```python
# POST /feedback/
{
  "rating": "positive",
  "message": "The agent provided accurate weather information with great formatting",
  "agent_used": "weather-assistant",
  "query": "What's the weather in Paris?",
  "response": "Current weather in Paris: 18°C, partly cloudy...",
  "metadata": {
    "response_time": 0.85,
    "sources_used": ["OpenWeatherMap"]
  }
}
```

### Créer une Démo Interactive
```python
# POST /demos/
{
  "name": "interactive-chart",
  "title": "Real-time Data Visualization",
  "description": "Interactive chart showing live data updates",
  "html_content": "<!DOCTYPE html>
<html>
<head>
    <title>Interactive Chart</title>
    <script src='https://cdn.plot.ly/plotly-latest.min.js'></script>
</head>
<body>
    <div id='chart'></div>
    <script>
        // Interactive plotting code here
    </script>
</body>
</html>",
  "tags": ["visualization", "charts", "real-time"],
  "metadata": {
    "framework": "plotly.js",
    "data_source": "websocket"
  }
}
```

### Améliorer une Requête avec Meta-Chat
```python
# POST /meta-chat/enhance
{
  "query": "show me sales data",
  "instructions": "make it pretty",
  "llm_profile": "gpt4-profile"
}

# Response:
{
  "enhanced_query": "Retrieve sales data for the current quarter including revenue by product category, top-performing regions, and year-over-year growth comparison",
  "enhanced_instructions": "Create an interactive HTML dashboard with: 1) Bar chart for revenue by category with hover tooltips, 2) Geographic heat map for regional performance, 3) Line graph showing monthly trends with YoY comparison, 4) Summary cards with key metrics. Use a modern color scheme with blue/green gradients and ensure mobile responsiveness.",
  "suggested_sources": ["Internal sales database", "CRM system", "Analytics platform"],
  "query_type": "business_analytics",
  "complexity": "moderate"
}
```

## WebSocket & SSE

### Server-Sent Events (SSE)
Les endpoints `/meta-agent/create` et `/agent/create-service` utilisent SSE pour transmettre le progrès en temps réel :

```javascript
const eventSource = new EventSource('/meta-agent/create');
eventSource.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`Step: ${progress.step}, Message: ${progress.message}`);
};
```

## Codes d'Erreur

- **400**: Bad Request - Données invalides ou manquantes
- **404**: Not Found - Ressource non trouvée
- **409**: Conflict - Conflit (ex: service déjà actif)
- **500**: Internal Server Error - Erreur serveur

## Limites et Quotas

- **Logs**: Max 1000 par requête
- **Services**: Pas de limite définie
- **Agents**: Max 5 itérations par défaut
- **Meta-Agent**: Max 5 outils créés par défaut
- **Timeout**: Variable selon l'endpoint

## Monitoring

Le système inclut des métriques via les logs MongoDB :
- Nombre d'exécutions par service
- Taux d'erreur par niveau
- Temps de réponse (via logs)
- Utilisation des tokens (via usage stats)

## Évolutions Futures

1. **WebSocket** pour chat temps réel
2. **GraphQL** API alternative
3. **Webhooks** pour événements
4. **Batch Operations** pour services/agents
5. **API Versioning** (v1, v2, etc.)
6. **Rate Limiting** configurable
7. **Caching** avec Redis
8. **Métriques** Prometheus/Grafana