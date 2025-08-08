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
1. **Services MCP**: Gestion des tools, resources et prompts internes
2. **Agents IA**: Système d'agents avec configuration 7D
3. **AI Agent**: Agent autonome pour création automatique de services
4. **LLM Profiles**: Gestion des profils de modèles de langage
5. **Meta-Agent**: Création automatique d'agents et d'outils
6. **MCP Client**: Connexions vers serveurs MCP externes (Context7, APIs externes)
7. **Workspace Management**: Gestion d'espaces de travail pour organiser les documents
8. **Document Management**: Upload, extraction et recherche sémantique de documents
9. **Demos System**: Hébergement de démos HTML/CSS/JS interactives
10. **Chat Interface**: Interface de chat intégrée
11. **Logging System**: Système de logs MongoDB intégré

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

#### POST /agents/{agent_id}/execute-stream
Exécuter un agent avec streaming SSE (Server-Sent Events) pour suivre le progrès en temps réel.

**Request Body:**
```json
{
  "input": "text input" ou {"structured": "input"},
  "conversation_history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ],
  "execution_options": {
    "timeout": 180000  // 3 minutes par défaut
  },
  "conversation_id": "existing-conversation-id",  // Optionnel
  "save_conversation": true  // Default: true
}
```

**Response:** Server-Sent Events stream avec mises à jour du progrès

**Format des événements SSE:**
```
data: {"step":"starting","message":"Starting execution of agent 'agent-name'","progress":0}

data: {"step":"validating","message":"Validating input","progress":10}

data: {"step":"preparing_tools","message":"Preparing MCP tools","progress":20}

data: {"step":"loading_memory","message":"Loading memory context","progress":30}

data: {"step":"calling_llm","message":"Calling LLM","progress":40,"iteration":1,"total_iterations":5}

data: {"step":"executing_tool","message":"Executing tool: weather_service","progress":60,"tool_call":{"name":"weather_service","args":{"city":"Paris"}}}

data: {"step":"processing_result","message":"Processing tool result","progress":80,"tool_result":{"temperature":18,"condition":"sunny"}}

data: {"step":"complete","message":"Execution completed","progress":100,"partial_output":"The weather in Paris is sunny with 18°C"}

data: [DONE]
```

**États possibles (ExecutionStep):**
- `starting`: Démarrage de l'exécution
- `validating`: Validation de l'entrée
- `preparing_tools`: Préparation des outils MCP
- `loading_memory`: Chargement du contexte mémoire (si activé)
- `calling_llm`: Appel au LLM
- `executing_tool`: Exécution d'un outil
- `processing_result`: Traitement du résultat
- `saving_memory`: Sauvegarde en mémoire (si activé)
- `complete`: Exécution terminée avec succès
- `error`: Erreur durant l'exécution
- `heartbeat`: Signal de maintien de connexion

**Exemple d'utilisation JavaScript:**
```javascript
const eventSource = new EventSource(`/api/agents/${agentId}/execute-stream`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    input: "What's the weather in Paris?",
    execution_options: { timeout: 180000 }
  })
});

eventSource.onmessage = (event) => {
  if (event.data === '[DONE]') {
    eventSource.close();
    return;
  }
  
  const progress = JSON.parse(event.data);
  console.log(`Step: ${progress.step} - ${progress.message} (${progress.progress}%)`);
  
  if (progress.step === 'complete') {
    console.log('Final output:', progress.partial_output);
  }
  
  if (progress.step === 'error') {
    console.error('Error:', progress.error_detail);
  }
};

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  eventSource.close();
};
```

**Avantages:**
- Pas de timeout pour les opérations longues
- Suivi en temps réel du progrès
- Visualisation des appels d'outils
- Résultats partiels disponibles
- Maintien de connexion automatique

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

### 🔗 Connexions MCP Externes (/mcp-connections)

Le système de connexions MCP permet d'intégrer des serveurs MCP externes et de rendre leurs outils disponibles aux agents. Cette fonctionnalité étend les capacités des agents en leur donnant accès à des services externes comme Context7, des APIs personnalisées, ou d'autres serveurs MCP.

#### POST /mcp-connections/
Créer une nouvelle connexion vers un serveur MCP externe.

**Request Body:**
```json
{
  "name": "Context7 Documentation Server",
  "description": "Up-to-date code documentation and examples from Context7",
  "server_url": "http://172.19.0.1:3001/mcp",
  "transport_type": "sse|http|stdio",
  "auth_type": "none|oauth|api_key|basic",
  "config": {
    "timeout": 30,
    "retry_attempts": 3,
    "description": "Provides up-to-date documentation for popular libraries",
    "api_key_header": "X-API-Key"  // Pour auth_type=api_key
  }
}
```

**Response:**
```json
{
  "id": "689276d852d1d4dc9cabc86f",
  "name": "Context7 Documentation Server",
  "description": "Up-to-date code documentation and examples from Context7",
  "server_url": "http://172.19.0.1:3001/mcp",
  "transport_type": "sse",
  "auth_type": "none",
  "status": "inactive",
  "config": {...},
  "created_at": "2025-08-05T21:25:44.543000",
  "updated_at": "2025-08-05T21:25:44.543000",
  "last_sync": null,
  "last_error": null,
  "last_ping": null,
  "ping_interval": 300,
  "retry_count": 0,
  "max_retries": 3
}
```

#### GET /mcp-connections/
Lister toutes les connexions MCP.

**Query Parameters:**
- `skip`: int (default: 0)
- `limit`: int (default: 100)

**Response:** Array des objets de connexion MCP

#### GET /mcp-connections/{connection_id}
Obtenir une connexion MCP spécifique.

**Response:** Objet connexion MCP ou 404 si non trouvée

#### PUT /mcp-connections/{connection_id}
Mettre à jour une connexion MCP existante.

**Request Body:** Même structure que POST (champs optionnels)

#### DELETE /mcp-connections/{connection_id}
Supprimer une connexion MCP et toutes ses données associées.

**Response:** 204 No Content ou 404 si non trouvée

#### POST /mcp-connections/{connection_id}/test
Tester la connectivité et les capacités d'un serveur MCP.

**Response:**
```json
{
  "success": true,
  "response_time": 0.083473,
  "server_info": {"name": "Context7 Documentation Server"},
  "tools_count": 2,
  "resources_count": 0,
  "prompts_count": 0,
  "error": null,
  "tested_at": "2025-08-05T21:39:30.483199"
}
```

#### POST /mcp-connections/{connection_id}/sync
Synchroniser et mettre en cache les outils, ressources et prompts du serveur MCP.

**Response:**
```json
{
  "message": "Server synchronized successfully",
  "tools_count": 2,
  "resources_count": 0,
  "prompts_count": 0,
  "cached_at": "2025-08-05T21:39:35.789179"
}
```

#### GET /mcp-connections/{connection_id}/tools
Obtenir les outils disponibles depuis une connexion MCP (depuis le cache).

**Response:**
```json
{
  "connection_id": "689276d852d1d4dc9cabc86f",
  "connection_name": "Context7 Documentation Server",
  "tools": [
    {
      "name": "resolve-library-id",
      "description": "Resolves a package/product name to a Context7-compatible library ID...",
      "inputSchema": {
        "type": "object",
        "properties": {
          "libraryName": {
            "type": "string",
            "description": "Library name to search for..."
          }
        },
        "required": ["libraryName"]
      }
    }
  ],
  "tools_count": 2
}
```

#### GET /mcp-connections/{connection_id}/resources
Obtenir les ressources disponibles depuis une connexion MCP.

#### GET /mcp-connections/{connection_id}/prompts
Obtenir les prompts disponibles depuis une connexion MCP.

#### POST /mcp-connections/{connection_id}/tools/{tool_name}/execute
Exécuter un outil spécifique depuis une connexion MCP externe.

**Request Body:**
```json
{
  "connection_id": "689276d852d1d4dc9cabc86f",
  "tool_name": "resolve-library-id",
  "parameters": {
    "libraryName": "react",
    "topic": "hooks typescript",
    "tokens": 15000
  }
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Documentation content here..."
      }
    ]
  },
  "execution_time": 1.234,
  "server_info": {"server_name": "Context7 Documentation Server"},
  "error": null
}
```

#### GET /mcp-connections/{connection_id}/auth
Obtenir le statut d'authentification d'une connexion.

**Response:**
```json
{
  "connection_id": "689276d852d1d4dc9cabc86f",
  "auth_type": "oauth",
  "has_auth": true,
  "is_valid": true,
  "expires_at": "2025-08-09T10:00:00.000Z",
  "scopes": ["read", "write"]
}
```

#### POST /mcp-connections/{connection_id}/auth/oauth
Démarrer un flow d'authentification OAuth.

**Request Body:**
```json
{
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "authorization_url": "https://example.com/oauth/authorize",
  "token_url": "https://example.com/oauth/token",
  "scopes": ["read", "write"],
  "redirect_uri": "http://localhost:8000/oauth/callback"
}
```

**Response:**
```json
{
  "authorization_url": "https://example.com/oauth/authorize?client_id=...&state=abc123",
  "state": "abc123"
}
```

#### POST /mcp-connections/{connection_id}/auth/callback
Traiter le callback OAuth après autorisation utilisateur.

**Request Body:**
```json
{
  "code": "authorization-code-from-oauth-provider",
  "state": "abc123"
}
```

**Response:**
```json
{
  "message": "OAuth authentication successful",
  "expires_at": "2025-08-09T10:00:00.000Z"
}
```

#### POST /mcp-connections/{connection_id}/auth/refresh
Actualiser un token d'accès expiré.

**Response:**
```json
{
  "message": "Token refreshed successfully",
  "expires_at": "2025-08-09T10:00:00.000Z"
}
```

#### POST /mcp-connections/{connection_id}/auth/api-key
Stocker une clé API pour l'authentification.

**Request Body:**
```json
{
  "api_key": "sk-abc123def456",
  "additional_data": {
    "key_name": "production-key",
    "permissions": "read-write"
  }
}
```

**Response:**
```json
{
  "message": "API key stored successfully"
}
```

#### DELETE /mcp-connections/{connection_id}/auth
Supprimer les informations d'authentification d'une connexion.

**Response:**
```json
{
  "message": "Authentication deleted successfully"
}
```

#### GET /mcp-connections/sessions/info
Obtenir des informations sur les sessions MCP actives.

**Response:**
```json
{
  "active_sessions": 3,
  "sessions": [
    {
      "connection_id": "689276d852d1d4dc9cabc86f",
      "connection_name": "Context7 Documentation Server",
      "status": "connected",
      "last_activity": "2025-08-08T10:00:00.000Z",
      "uptime_seconds": 1800
    }
  ],
  "total_connections": 5
}
```

#### POST /mcp-connections/sessions/cleanup
Nettoyer les sessions MCP inactives.

**Query Parameters:**
- `max_idle_minutes`: int (default: 30) - Durée max d'inactivité avant nettoyage

**Response:**
```json
{
  "message": "Cleaned up 2 inactive sessions"
}
```

#### Authentification MCP

Le système supporte plusieurs types d'authentification :

- **none**: Aucune authentification
- **oauth**: OAuth 2.0 avec tokens Bearer
- **api_key**: Clé API dans un header personnalisé
- **basic**: HTTP Basic Authentication

#### Intégration avec les Agents

Les outils MCP externes sont automatiquement disponibles aux agents qui ont des connexions MCP assignées. Dans la configuration d'un agent :

```json
{
  "name": "tech_doc_expert",
  "mcp_services": ["service1", "service2"],  // Services internes
  "mcp_connections": ["689276d852d1d4dc9cabc86f"], // Connexions externes
  "mcp_config": {
    "auto_sync": true,
    "cache_ttl": 300
  }
}
```

Les outils externes apparaissent avec le préfixe `mcp_{connection_id}_{tool_name}` lors de l'exécution pour éviter les conflits.

### 📁 Espaces de Travail (/api/workspaces)

Le système d'espaces de travail permet d'organiser et gérer les documents de manière structurée, avec des permissions par agent et des paramètres configurables.

#### POST /api/workspaces/
Créer un nouvel espace de travail.

**Request Body:**
```json
{
  "name": "projet-documentation",
  "description": "Espace de travail pour la documentation du projet",
  "owner_id": "user-123", // Optionnel
  "agent_ids": ["agent-456", "agent-789"], // Agents avec accès
  "is_public": false,
  "settings": {
    "max_file_size": 104857600, // 100MB en bytes
    "allowed_types": ["pdf", "docx", "markdown", "text"], // Types autorisés
    "auto_extract": true, // Extraction automatique de contenu
    "auto_embed": true, // Génération automatique d'embeddings
    "retention_days": 365 // Rétention des documents (null = illimité)
  },
  "metadata": {
    "project": "uxmcp-v2",
    "department": "engineering"
  }
}
```

**Response:**
```json
{
  "id": "workspace-123",
  "name": "projet-documentation",
  "description": "Espace de travail pour la documentation du projet",
  "owner_id": "user-123",
  "agent_ids": ["agent-456", "agent-789"],
  "is_public": false,
  "settings": {
    "max_file_size": 104857600,
    "allowed_types": ["pdf", "docx", "markdown", "text"],
    "auto_extract": true,
    "auto_embed": true,
    "retention_days": 365
  },
  "metadata": {
    "project": "uxmcp-v2",
    "department": "engineering"
  },
  "document_count": 0,
  "total_size": 0,
  "created_at": "2025-08-08T10:00:00.000Z",
  "updated_at": "2025-08-08T10:00:00.000Z"
}
```

#### GET /api/workspaces/
Lister tous les espaces de travail avec filtres optionnels.

**Query Parameters:**
- `skip`: int (default: 0) - Nombre d'éléments à ignorer
- `limit`: int (default: 100, max: 1000) - Nombre max de résultats
- `agent_id`: string - Filtrer par agent ayant accès
- `is_public`: bool - Filtrer par visibilité publique

**Response:** Array des objets workspace

#### GET /api/workspaces/{workspace_id}
Obtenir un espace de travail spécifique.

**Response:** Objet workspace complet ou 404 si non trouvé

#### GET /api/workspaces/by-name/{name}
Obtenir un espace de travail par son nom.

**Response:** Objet workspace ou 404 si non trouvé

#### PUT /api/workspaces/{workspace_id}
Mettre à jour un espace de travail existant.

**Request Body:**
```json
{
  "name": "nouveau-nom",
  "description": "Description mise à jour",
  "agent_ids": ["agent-456", "agent-789", "agent-new"],
  "is_public": true,
  "settings": {
    "max_file_size": 209715200, // 200MB
    "auto_extract": false
  },
  "metadata": {
    "status": "active",
    "last_review": "2025-08-08"
  }
}
```

**Response:** Objet workspace mis à jour

#### DELETE /api/workspaces/{workspace_id}
Supprimer un espace de travail et tous ses documents.

**Response:** 
```json
{
  "message": "Workspace deleted successfully"
}
```

#### POST /api/workspaces/{workspace_id}/agents/{agent_id}
Ajouter un agent à la liste d'accès de l'espace de travail.

**Response:**
```json
{
  "message": "Agent agent-123 added to workspace projet-documentation"
}
```

#### DELETE /api/workspaces/{workspace_id}/agents/{agent_id}
Retirer un agent de la liste d'accès de l'espace de travail.

**Response:**
```json
{
  "message": "Agent agent-123 removed from workspace projet-documentation"
}
```

#### GET /api/workspaces/{workspace_id}/stats
Obtenir des statistiques détaillées d'un espace de travail.

**Response:**
```json
{
  "workspace_id": "workspace-123",
  "document_count": 45,
  "total_size": 267845632, // Taille totale en bytes
  "document_types": {
    "pdf": 20,
    "docx": 15,
    "markdown": 8,
    "text": 2
  },
  "categories": {
    "documentation": 25,
    "code": 10,
    "data": 5,
    "report": 5
  },
  "recent_uploads": [
    {
      "document_id": "doc-456",
      "name": "guide-installation.pdf",
      "uploaded_at": "2025-08-07T15:30:00.000Z",
      "size": 2048576
    }
  ],
  "most_accessed": [
    {
      "document_id": "doc-123",
      "name": "api-reference.md",
      "access_count": 150,
      "last_accessed": "2025-08-08T09:45:00.000Z"
    }
  ],
  "agent_access": [
    {
      "agent_id": "agent-456",
      "agent_name": "Documentation Assistant",
      "access_count": 75
    }
  ]
}
```

### 📄 Gestion de Documents (/api/documents)

Le système de gestion de documents permet d'uploader, stocker, extraire et rechercher du contenu dans différents formats de fichiers avec support de la recherche sémantique.

#### POST /api/documents/
Créer un nouveau document avec upload de fichier optionnel.

**Request Body (multipart/form-data):**
```
name: "guide-utilisateur" (required)
type: "pdf" (required) - DocumentType enum
workspace_id: "workspace-123" (required)
description: "Guide d'utilisation complet" (optional)
category: "documentation" (optional) - DocumentCategory enum
tags: "guide,tutorial,pdf" (optional) - comma-separated tags
keywords: "docker,setup,installation" (optional) - comma-separated keywords
is_public: false (optional, default: false)
file: [binary file data] (optional)
```

**DocumentType enum:**
`pdf | text | markdown | html | json | csv | docx | xlsx | image | other`

**DocumentCategory enum:**
`documentation | code | data | report | presentation | reference | manual | other`

**Response:**
```json
{
  "id": "doc-456",
  "name": "guide-utilisateur",
  "type": "pdf",
  "description": "Guide d'utilisation complet",
  "workspace_id": "workspace-123",
  "category": "documentation",
  "tags": ["guide", "tutorial", "pdf"],
  "keywords": ["docker", "setup", "installation"],
  "content": "Contenu extrait automatiquement...", // Si extraction réussie
  "content_embedding": null, // Sera généré automatiquement
  "blob_id": "gridfs-blob-789", // ID GridFS pour le fichier original
  "file_size": 2048576,
  "mime_type": "application/pdf",
  "metadata": {},
  "access_count": 0,
  "last_accessed": null,
  "is_public": false,
  "chunk_ids": [], // IDs des chunks dans le vector store
  "created_at": "2025-08-08T10:00:00.000Z",
  "updated_at": "2025-08-08T10:00:00.000Z",
  "created_by": null,
  "updated_by": null
}
```

**Note:** Si une description est fournie lors de la création, un embedding sera automatiquement généré pour permettre la recherche sémantique.

#### GET /api/documents/
Lister les documents avec filtres optionnels.

**Query Parameters:**
- `skip`: int (default: 0) - Pagination
- `limit`: int (default: 100, max: 1000) - Limite de résultats
- `workspace_id`: string - Filtrer par espace de travail
- `category`: DocumentCategory - Filtrer par catégorie
- `tags`: string - Filtrer par tags (comma-separated)
- `keywords`: string - Filtrer par keywords (comma-separated)
- `type`: DocumentType - Filtrer par type de document

**Response:** Array des objets document

#### GET /api/documents/{document_id}
Obtenir un document spécifique.

**Response:** Objet document complet

#### GET /api/documents/{document_id}/download
Télécharger le fichier original d'un document.

**Response:** Streaming file download avec headers appropriés
```
Content-Type: application/pdf (ou mime type du fichier)
Content-Disposition: attachment; filename="guide-utilisateur.pdf"
```

#### GET /api/documents/{document_id}/content
Obtenir le contenu textuel extrait d'un document.

**Response:**
```json
{
  "content": "Contenu textuel extrait du document...",
  "message": "No content available" // Si pas d'extraction disponible
}
```

Si le contenu n'est pas encore extrait, l'endpoint tentera automatiquement l'extraction.

#### PUT /api/documents/{document_id}
Mettre à jour les métadonnées d'un document.

**Request Body:**
```json
{
  "name": "nouveau-nom",
  "description": "Nouvelle description",
  "category": "reference",
  "tags": ["updated", "reference", "important"],
  "keywords": ["api", "documentation", "guide"],
  "metadata": {
    "author": "John Doe",
    "version": "2.0"
  },
  "is_public": true
}
```

**Response:** Objet document mis à jour

**Note:** Si la description est modifiée, un nouvel embedding sera automatiquement généré pour améliorer la recherche sémantique.

#### DELETE /api/documents/{document_id}
Supprimer un document et son contenu de fichier.

**Response:**
```json
{
  "message": "Document deleted successfully"
}
```

#### POST /api/documents/search
Rechercher des documents avec support de recherche sémantique.

**Request Body:**
```json
{
  "query": "guide installation docker kubernetes",
  "workspace_ids": ["workspace-123", "workspace-456"], // Optionnel
  "categories": ["documentation", "manual"], // Optionnel
  "tags": ["docker", "k8s"], // Optionnel
  "keywords": ["kubernetes", "container", "deployment"], // Optionnel
  "types": ["pdf", "markdown"], // Optionnel
  "date_from": "2025-01-01T00:00:00.000Z", // Optionnel
  "date_to": "2025-12-31T23:59:59.000Z", // Optionnel
  "use_semantic": true, // Active la recherche sémantique
  "limit": 10 // Max 100
}
```

**Response:**
```json
[
  {
    "document": {
      "id": "doc-456",
      "name": "docker-installation-guide",
      "type": "pdf",
      "description": "Complete Docker installation guide",
      "workspace_id": "workspace-123",
      "category": "documentation",
      "tags": ["docker", "installation", "guide"],
      // ... autres propriétés du document
    },
    "score": 0.892, // Score de pertinence (0-1)
    "excerpt": "...Docker installation steps for Kubernetes...",
    "highlights": [
      "Docker installation on Ubuntu",
      "Kubernetes integration guide"
    ]
  }
]
```

#### POST /api/documents/{document_id}/extract
Forcer l'extraction et l'indexation du contenu d'un document.

**Response:**
```json
{
  "message": "Content extracted and indexed successfully",
  "content_length": 15420,
  "preview": "Docker is a platform that enables developers to..."
}
```

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


### 💬 Conversations (/conversations)

#### POST /conversations/
Créer une nouvelle conversation pour un agent.

**Request Body:**
```json
{
  "agent_id": "agent-123",
  "user_id": "user-456",  // Optionnel
  "title": "Weather Discussion",  // Optionnel, auto-généré si non fourni
  "messages": [],  // Liste initiale de messages (optionnel)
  "metadata": {},  // Optionnel
  "active": true  // Default: true
}
```

**Response:** Conversation object avec ID généré

#### GET /conversations/
Lister les conversations avec pagination.

**Query Parameters:**
- `skip`: int (default: 0)
- `limit`: int (default: 10, max: 100)
- `active_only`: bool (default: false) - Seulement les conversations actives
- `user_id`: string - Filtrer par utilisateur

**Response:**
```json
{
  "items": [
    {
      "_id": "conversation-id",
      "agent_id": "agent-123",
      "user_id": "user-456",
      "title": "Weather Discussion",
      "messages": [...],
      "metadata": {},
      "active": true,
      "last_activity": "2025-01-01T10:00:05",
      "created_at": "2025-01-01T10:00:00",
      "updated_at": "2025-01-01T10:00:05",
      "message_count": 2
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 10,
  "total_pages": 5
}
```

#### GET /conversations/summaries
Obtenir des résumés de conversations (version allégée pour listes).

**Query Parameters:**
- `agent_id`: string - Filtrer par agent
- `user_id`: string - Filtrer par utilisateur
- `limit`: int (default: 20, max: 50)

**Response:**
```json
[
  {
    "_id": "conversation-id",
    "agent_id": "agent-123",
    "title": "Weather Discussion",
    "message_count": 15,
    "last_activity": "2025-01-01T10:00:05",
    "created_at": "2025-01-01T10:00:00",
    "active": true
  }
]
```

#### GET /conversations/{conversation_id}
Obtenir une conversation spécifique avec tous ses messages.

**Response:**
```json
{
  "_id": "conversation-id",
  "agent_id": "agent-123",
  "user_id": "user-456",
  "title": "Weather Discussion",
  "messages": [
    {
      "role": "user",
      "content": "What's the weather?",
      "timestamp": "2025-01-01T10:00:00",
      "metadata": {},
      "tool_calls": null,
      "execution_id": null
    },
    {
      "role": "assistant",
      "content": "The weather is sunny...",
      "timestamp": "2025-01-01T10:00:05",
      "metadata": {"execution_id": "exec-123"},
      "tool_calls": [{"tool": "weather_api", "arguments": {"city": "Paris"}, "result": {...}}],
      "execution_id": "exec-123"
    }
  ],
  "metadata": {},
  "active": true,
  "last_activity": "2025-01-01T10:00:05",
  "created_at": "2025-01-01T10:00:00",
  "updated_at": "2025-01-01T10:00:05",
  "message_count": 2
}
```

#### PUT /conversations/{conversation_id}
Mettre à jour une conversation (titre, métadonnées, statut).

**Request Body:**
```json
{
  "title": "Updated Title",
  "metadata": {"tags": ["important"]},
  "active": false
}
```

#### DELETE /conversations/{conversation_id}
Supprimer une conversation et tous ses messages.

#### POST /conversations/{conversation_id}/messages
Ajouter un message à une conversation existante.

**Request Body:**
```json
{
  "role": "user",
  "content": "Follow-up question",
  "metadata": {},
  "tool_calls": null,
  "execution_id": null
}
```

#### POST /conversations/{conversation_id}/clear
Effacer tous les messages d'une conversation (mais garder la conversation).

#### GET /conversations/agent/{agent_id}
Obtenir toutes les conversations d'un agent avec pagination.

**Query Parameters:**
- `skip`: int (default: 0)
- `limit`: int (default: 10, max: 100)

**Response:** ConversationList (même format que GET /conversations/)

#### GET /conversations/agent/{agent_id}/latest
Obtenir la conversation la plus récente pour un agent.

**Query Parameters:**
- `user_id`: string - Pour obtenir la dernière conversation d'un utilisateur spécifique

**Response:** Conversation object ou 404 si aucune conversation n'existe

**Integration avec l'exécution d'agents:**

Les endpoints d'exécution d'agents (`/agents/{agent_id}/execute`) acceptent maintenant des paramètres supplémentaires pour la persistance:

```json
{
  "input": "User message",
  "conversation_id": "existing-conversation-id",  // Optionnel
  "save_conversation": true,  // Default: true
  "execution_options": {}  // Optionnel
}
```

**Response inclut maintenant:**
```json
{
  "success": true,
  "output": "Agent response",
  "conversation_id": "conversation-id-used",  // ID de la conversation utilisée/créée
  "execution_id": "exec-123",
  "tool_calls": [...],
  "iterations": 1,
  "usage": {}
}
```

### 🎨 Demos (/demos)

#### POST /demos/
Créer une nouvelle démo.

**Request Body:**
```json
{
  "name": "My Demo",
  "description": "Demo description",
  "html": "<html>...</html>",
  "metadata": {}
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

### 8. **Demos System**
- **HTML/CSS/JS interactif** : Démos complètes hébergées
- **Gestion par tags** : Organisation et recherche faciles
- **Versioning intégré** : Métadonnées de version
- **Serving direct** : Accès par nom d'URL simple

### 9. **Workspace & Document Management System**
- **Organisation hiérarchique** : Workspaces → Documents → Content
- **Extraction multi-format** : PDF, DOCX, XLSX, images, texte, etc.
- **Recherche sémantique** : Vector embeddings avec ChromaDB
- **Permissions granulaires** : Accès par agent et visibilité publique/privée
- **Métadonnées enrichies** : Tags, catégories, statistiques d'accès
- **Pipeline automatique** : Upload → Extraction → Indexation → Recherche

### 10. **External MCP Connections**
- **Connexions multi-protocoles** : SSE, HTTP, stdio pour serveurs MCP externes
- **Authentification complète** : OAuth, API keys, Basic auth
- **Cache intelligent** : Mise en cache des capacités et sessions
- **Session management** : Gestion automatique des connexions actives
- **Tool integration** : Outils externes disponibles pour tous les agents
- **Auto-discovery** : Synchronisation automatique des capacités serveur

## Sécurité

### Points d'Attention
- ⚠️ **Pas d'authentification** : Prévu pour développement local
- ⚠️ **CORS ouvert** : Accepte toutes les origines
- ⚠️ **Exécution de code** : Le code des services est exécuté dynamiquement
- ⚠️ **API Keys** : Stockées en clair dans MongoDB
- ⚠️ **Upload de fichiers** : Pas de validation anti-malware
- ⚠️ **Extraction de contenu** : Vulnérable aux fichiers malveillants
- ⚠️ **Connexions MCP externes** : Authentification stockée en base
- ⚠️ **Recherche sémantique** : Pas de filtrage du contenu sensible

### Recommandations Production
1. Implémenter l'authentification JWT/OAuth
2. Configurer CORS avec origines spécifiques
3. Sandboxer l'exécution du code utilisateur
4. Chiffrer les API keys sensibles
5. Limiter les rate limits
6. Valider strictement les inputs
7. Ajouter validation anti-malware pour uploads
8. Implémenter scan de sécurité pour contenu extrait
9. Chiffrer les credentials des connexions MCP
10. Filtrage du contenu sensible dans la recherche
11. Quotas de stockage par workspace
12. Audit trail pour accès aux documents

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


### Workflow Complet: Workspace + Documents + Agent

#### 1. Créer un Espace de Travail
```python
# POST /api/workspaces/
{
  "name": "knowledge-base",
  "description": "Base de connaissances technique",
  "agent_ids": ["doc-assistant-123"],
  "is_public": false,
  "settings": {
    "max_file_size": 52428800,  # 50MB
    "allowed_types": ["pdf", "docx", "markdown", "text"],
    "auto_extract": true,
    "auto_embed": true
  }
}
```

#### 2. Uploader des Documents
```bash
# Upload multiple documents
curl -X POST "http://localhost:8000/api/documents/" \
  -F "name=api-documentation" \
  -F "type=pdf" \
  -F "workspace_id=workspace-123" \
  -F "category=documentation" \
  -F "tags=api,reference,guide" \
  -F "file=@./docs/api-guide.pdf"

curl -X POST "http://localhost:8000/api/documents/" \
  -F "name=user-manual" \
  -F "type=docx" \
  -F "workspace_id=workspace-123" \
  -F "category=manual" \
  -F "tags=user,manual,guide" \
  -F "file=@./docs/user-manual.docx"
```

#### 3. Créer un Agent avec Accès aux Documents
```python
# POST /agents/
{
  "name": "documentation_assistant",
  "llm_profile": "gpt4-profile",
  "system_prompt": "You are a documentation assistant with access to technical documents. Help users find information and answer questions based on the available documentation.",
  "backstory": "Expert in technical documentation with access to comprehensive knowledge base",
  "objectives": [
    "Help users find relevant documentation",
    "Answer questions based on document content",
    "Provide accurate technical guidance"
  ],
  "memory_enabled": true,
  "workspace_access": ["workspace-123"], // Nouveau: accès workspace
  "endpoint": "/api/agent/docs-assistant"
}
```

#### 4. Rechercher dans les Documents
```python
# POST /api/documents/search
{
  "query": "authentication configuration setup",
  "workspace_ids": ["workspace-123"],
  "use_semantic": true,
  "limit": 5
}

# Response inclut les documents pertinents avec scores et excerpts
```

#### 5. Utiliser l'Agent avec Contexte Documentaire
```python
# L'agent peut maintenant accéder automatiquement aux documents
# POST /agents/documentation_assistant/execute
{
  "input": "How do I configure OAuth authentication?",
  "execution_options": {
    "use_document_context": true,  // Nouveau: utilise contexte docs
    "max_document_results": 3
  }
}

# L'agent recherchera automatiquement dans les documents 
# et utilisera le contenu pour répondre
```

### Connecter un Serveur MCP Externe
```python
# 1. Créer la connexion
# POST /mcp-connections/
{
  "name": "GitHub Integration",
  "description": "Access to GitHub repositories and issues",
  "server_url": "https://github-mcp-server.example.com/mcp",
  "transport_type": "sse",
  "auth_type": "oauth",
  "config": {
    "timeout": 30,
    "retry_attempts": 3
  }
}

# 2. Configurer l'authentification OAuth
# POST /mcp-connections/{connection_id}/auth/oauth
{
  "client_id": "github-client-id",
  "client_secret": "github-client-secret",
  "authorization_url": "https://github.com/login/oauth/authorize",
  "token_url": "https://github.com/login/oauth/access_token",
  "scopes": ["repo", "issues"]
}

# 3. Synchroniser les outils disponibles
# POST /mcp-connections/{connection_id}/sync

# 4. Utiliser les outils dans un agent
# POST /agents/
{
  "name": "github_assistant",
  "mcp_connections": ["github-connection-id"],
  "system_prompt": "You help manage GitHub repositories and issues"
}

# L'agent peut maintenant utiliser les outils GitHub
# comme create_issue, get_repository_info, etc.
```

## WebSocket & SSE

### Server-Sent Events (SSE)
Les endpoints suivants utilisent SSE pour transmettre le progrès en temps réel :
- `/meta-agent/create` : Création d'agents via meta-agent
- `/agent/create-service` : Création de services via AI agent
- `/agents/{agent_id}/execute-stream` : Exécution d'agents avec suivi du progrès

Exemple d'utilisation :

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
- **Documents**: Taille max configurable par workspace (50MB par défaut)
- **Workspaces**: Pas de limite sur le nombre
- **Recherche Documents**: Max 100 résultats par requête
- **Upload Files**: Support multipart jusqu'à la limite workspace
- **MCP Connections**: Max 30 secondes timeout par défaut
- **Vector Search**: Max 100 embeddings par recherche sémantique
- **Timeout**: Variable selon l'endpoint

## Monitoring

Le système inclut des métriques via les logs MongoDB :
- Nombre d'exécutions par service
- Taux d'erreur par niveau
- Temps de réponse (via logs)
- Utilisation des tokens (via usage stats)
- Statistiques d'usage par workspace
- Métrics de documents : uploads, téléchargements, recherches
- Performance des connexions MCP externes
- Taux de succès extraction de contenu
- Utilisation de l'espace de stockage (GridFS + Vector DB)

## Évolutions Futures

1. **WebSocket** pour chat temps réel
2. **GraphQL** API alternative
3. **Webhooks** pour événements
4. **Batch Operations** pour services/agents
5. **API Versioning** (v1, v2, etc.)
6. **Rate Limiting** configurable
7. **Caching** avec Redis
8. **Métriques** Prometheus/Grafana