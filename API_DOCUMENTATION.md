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
3. **LLM Profiles**: Gestion des profils de modèles de langage
4. **Meta-Agent**: Création automatique d'agents et d'outils
5. **Chat Interface**: Interface de chat intégrée
6. **Logging System**: Système de logs MongoDB intégré

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

## WebSocket & SSE

### Server-Sent Events (SSE)
Le endpoint `/meta-agent/create` utilise SSE pour transmettre le progrès en temps réel :

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