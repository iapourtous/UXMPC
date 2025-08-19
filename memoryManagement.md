# 🧠 Système de Gestion de Mémoire UXMCP

## Vue d'Ensemble

Le système de mémoire UXMCP offre aux agents une capacité de mémorisation persistante et intelligente, permettant des interactions contextuelles et personnalisées. Il combine stockage traditionnel (MongoDB) avec recherche sémantique (Vector Store) pour une expérience similaire à la mémoire humaine.

## 🏗️ Architecture Générale

### Diagramme d'Architecture Système

```mermaid
graph TB
    subgraph "Frontend"
        UI[Interface Web]
        Chat[Chat avec Agents]
    end
    
    subgraph "API Layer"
        FastAPI[FastAPI Server]
        Memory_API[Memory API]
        Agent_API[Agent API]
    end
    
    subgraph "Services"
        MemService[Agent Memory Service]
        Executor[Agent Executor]
        Tools[Memory Tools MCP]
    end
    
    subgraph "Storage Layer"
        MongoDB[(MongoDB<br/>Stockage Persistant)]
        
        subgraph "Vector Stores"
            ChromaDB[(ChromaDB<br/>Production)]
            SimpleStore[Simple Store<br/>Fallback]
        end
    end
    
    subgraph "ML Models"
        E5[multilingual-e5-large<br/>Embeddings]
    end
    
    UI --> FastAPI
    Chat --> Agent_API
    Agent_API --> Executor
    Executor --> Tools
    Tools --> MemService
    FastAPI --> Memory_API
    Memory_API --> MemService
    MemService --> MongoDB
    MemService --> ChromaDB
    MemService --> SimpleStore
    MemService --> E5
    
    style ChromaDB fill:#2ecc71
    style MongoDB fill:#3498db
    style E5 fill:#e74c3c
```

### Configuration Duale

```mermaid
flowchart LR
    Start([Démarrage]) --> Check{USE_CHROMADB?}
    Check -->|True| TryChroma{ChromaDB<br/>disponible?}
    Check -->|False| Simple[Simple Store]
    TryChroma -->|Oui| Chroma[ChromaDB]
    TryChroma -->|Non| Simple
    Chroma --> Ready([Prêt])
    Simple --> Ready
    
    style Chroma fill:#2ecc71
    style Simple fill:#f39c12
```

## 🔄 Cycle de Vie de la Mémoire

### Flow Complet de Gestion

```mermaid
stateDiagram-v2
    [*] --> Creation: Nouveau Message
    Creation --> Embedding: Génération Vecteur
    Embedding --> Storage: Sauvegarde
    Storage --> Check: Vérifier Limite
    Check --> Active: OK
    Check --> Cleanup: Limite Dépassée
    Cleanup --> Active: Nettoyage Terminé
    Active --> Search: Requête
    Search --> Retrieved: Résultat
    Retrieved --> Updated: Mise à jour accès
    Updated --> Active
    Active --> [*]: Fin de session
    
    note right of Cleanup
        Supprime 10% des mémoires
        avec le score d'utilité
        le plus faible
    end note
    
    note left of Embedding
        Modèle: multilingual-e5-large
        Dimension: 1024
    end note
```

### Algorithme de Score d'Utilité

```mermaid
graph TD
    subgraph "Calcul du Score d'Utilité"
        Input[Mémoire] --> Importance[Importance<br/>40%]
        Input --> Usage[Usage<br/>30%]
        Input --> Recency[Récence<br/>20%]
        Input --> Age[Âge<br/>10%]
        
        Importance --> Score[Score Final]
        Usage --> Score
        Recency --> Score
        Age --> Score
    end
    
    Score --> Decision{Score > Seuil?}
    Decision -->|Oui| Keep[Conserver]
    Decision -->|Non| Delete[Supprimer]
    
    style Score fill:#3498db
    style Keep fill:#2ecc71
    style Delete fill:#e74c3c
```

### Formule de Calcul

```python
utility_score = (
    importance * 0.4 +      # Type de contenu (0.0-1.0)
    usage_score * 0.3 +     # Fréquence d'accès normalisée
    recency_score * 0.2 +   # Jours depuis dernier accès (décroissance 30j)
    (1 - age_score) * 0.1   # Pénalité d'âge (décroissance 90j)
)
```

## 📊 Types de Mémoire et Hiérarchie

### Classification des Mémoires

```mermaid
classDiagram
    class AgentMemory {
        +id: str
        +agent_id: str
        +content: str
        +content_type: str
        +importance: float
        +created_at: datetime
        +last_accessed: datetime
        +access_count: int
        +user_id: Optional[str]
        +conversation_id: Optional[str]
        +metadata: Dict
        +tags: List[str]
    }
    
    class ContentTypes {
        <<enumeration>>
        USER_MESSAGE: 0.7
        AGENT_RESPONSE: 0.5
        PREFERENCE: 0.9
        STORED_KNOWLEDGE: 0.8
        TOOL_CALL: 0.6
        OBSERVATION: 0.4
    }
    
    class VectorData {
        +embedding: List[float]
        +dimension: int
        +model: str
        +similarity_score: float
    }
    
    AgentMemory --> ContentTypes: type
    AgentMemory --> VectorData: vector
```

### Hiérarchie d'Importance

```mermaid
graph LR
    subgraph "Échelle d'Importance"
        P[Preference<br/>0.9] --> SK[Stored Knowledge<br/>0.8]
        SK --> UM[User Message<br/>0.7]
        UM --> TC[Tool Call<br/>0.6]
        TC --> AR[Agent Response<br/>0.5]
        AR --> O[Observation<br/>0.4]
    end
    
    style P fill:#e74c3c
    style SK fill:#e67e22
    style UM fill:#f39c12
    style TC fill:#3498db
    style AR fill:#2ecc71
    style O fill:#95a5a6
```

## 💬 Contexte de Conversation - La Mémoire Immédiate

### Architecture de la Mémoire Conversationnelle

```mermaid
graph TD
    subgraph "Types de Mémoire"
        subgraph "Mémoire Immédiate"
            Context[Contexte de Conversation<br/>Session Active]
            History[Historique Récent<br/>5-10 derniers messages]
        end
        
        subgraph "Mémoire Court Terme"
            Session[Mémoire de Session<br/>Durée de la session]
            Recent[Interactions Récentes<br/>Dernières heures]
        end
        
        subgraph "Mémoire Long Terme"
            Persistent[Mémoire Persistante<br/>MongoDB + ChromaDB]
            Knowledge[Base de Connaissances<br/>Permanent]
        end
    end
    
    Context --> Session
    Session --> Persistent
    History --> Recent
    Recent --> Knowledge
    
    style Context fill:#e74c3c
    style Session fill:#f39c12
    style Persistent fill:#2ecc71
```

### Flow du Contexte Conversationnel

```mermaid
sequenceDiagram
    participant User
    participant ChatInterface
    participant Agent
    participant ContextManager
    participant Memory
    
    User->>ChatInterface: Message 1
    ChatInterface->>ContextManager: Init Context
    ContextManager->>Agent: [Empty Context]
    Agent->>User: Response 1
    ContextManager->>ContextManager: Update Context
    
    User->>ChatInterface: Message 2
    ChatInterface->>ContextManager: Get Context
    ContextManager->>Agent: [Message 1 + Response 1]
    Agent->>User: Response 2 (contextualisée)
    ContextManager->>ContextManager: Update Context
    
    Note over ContextManager: Fenêtre glissante de N messages
    
    ContextManager->>Memory: Save Important Parts
    Memory->>Memory: Persist if relevant
```

### Gestion de la Fenêtre de Contexte

```mermaid
flowchart LR
    subgraph "Fenêtre de Contexte (Token Limit)"
        M1[Message 1]
        M2[Message 2]
        M3[Message 3]
        M4[Message 4]
        M5[Message 5]
        New[Nouveau Message]
    end
    
    New --> Push[Ajouter]
    Push --> Check{Limite Tokens?}
    Check -->|Non| Keep[Garder Tout]
    Check -->|Oui| Trim[Supprimer Ancien]
    Trim --> M1
    M1 --> Remove[X]
    
    style New fill:#3498db
    style M1 fill:#e74c3c,stroke-dasharray: 5 5
```

### Hiérarchie Temporelle de la Mémoire

```mermaid
graph LR
    subgraph "Échelle Temporelle"
        Immediate[0-5 min<br/>Contexte Actif]
        Short[5-60 min<br/>Session]
        Medium[1-24h<br/>Journée]
        Long[>24h<br/>Permanent]
    end
    
    Immediate -->|Consolidation| Short
    Short -->|Filtrage| Medium
    Medium -->|Sélection| Long
    
    style Immediate fill:#e74c3c
    style Short fill:#f39c12
    style Medium fill:#3498db
    style Long fill:#2ecc71
```

### Stratégies de Gestion du Contexte

```mermaid
classDiagram
    class ContextStrategy {
        <<interface>>
        +manage_context()
        +should_persist()
        +extract_important()
    }
    
    class SlidingWindow {
        +window_size: int
        +token_limit: int
        +trim_oldest()
    }
    
    class ImportanceBased {
        +importance_threshold: float
        +score_message()
        +keep_important()
    }
    
    class Summarization {
        +summary_interval: int
        +summarize_old()
        +inject_summary()
    }
    
    class Hybrid {
        +combine_strategies()
        +adaptive_management()
    }
    
    ContextStrategy <|-- SlidingWindow
    ContextStrategy <|-- ImportanceBased
    ContextStrategy <|-- Summarization
    ContextStrategy <|-- Hybrid
```

## 🤖 Intégration avec les Agents

### Outils MCP de Mémoire

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant MemoryTools
    participant MemoryService
    participant Storage
    
    User->>Agent: Question
    Agent->>MemoryTools: memory_search("contexte précédent")
    MemoryTools->>MemoryService: search_memories()
    MemoryService->>Storage: vector_search + mongodb_fetch
    Storage-->>MemoryService: memories
    MemoryService-->>MemoryTools: results
    MemoryTools-->>Agent: contexte
    
    Agent->>Agent: Traitement avec contexte
    Agent->>User: Réponse contextualisée
    
    Agent->>MemoryTools: memory_store(conversation)
    MemoryTools->>MemoryService: save_memory()
    MemoryService->>Storage: dual_save()
    
    Note over Agent,MemoryService: Extraction automatique des préférences
```

### Flow d'Exécution avec Contexte

```mermaid
flowchart TD
    Start([Début Exécution]) --> Load[Charger Contexte]
    Load --> Search[Recherche Sémantique]
    Search --> Filter[Filtrer par Score > 0.7]
    Filter --> Format[Formater Contexte]
    Format --> Inject[Injecter dans Prompt]
    Inject --> Execute[Exécuter Agent]
    Execute --> Save[Sauvegarder Conversation]
    Save --> Extract[Extraire Préférences]
    Extract --> Update[Mettre à jour Mémoire]
    Update --> End([Fin])
    
    style Load fill:#3498db
    style Search fill:#9b59b6
    style Execute fill:#2ecc71
    style Extract fill:#e74c3c
```

### Outils Disponibles

```mermaid
graph TD
    subgraph "Memory Tools MCP"
        Search[memory_search<br/>Recherche sémantique]
        Store[memory_store<br/>Stockage explicite]
        Analyze[memory_analyze<br/>Analyse patterns]
    end
    
    subgraph "Paramètres Search"
        S1[query: str]
        S2[k: int = 5]
        S3[filters: Dict]
    end
    
    subgraph "Paramètres Store"
        ST1[content: str]
        ST2[importance: float]
        ST3[tags: List]
    end
    
    subgraph "Types Analyse"
        A1[summary]
        A2[preferences]
        A3[topics]
        A4[frequency]
        A5[gaps]
    end
    
    Search --> S1
    Search --> S2
    Search --> S3
    
    Store --> ST1
    Store --> ST2
    Store --> ST3
    
    Analyze --> A1
    Analyze --> A2
    Analyze --> A3
    Analyze --> A4
    Analyze --> A5
```

## 🔍 Système d'Embeddings

### Pipeline de Vectorisation

```mermaid
flowchart LR
    Text[Texte Original] --> Prefix[Ajout Préfixe]
    Prefix --> Model[E5-Large]
    Model --> Vector[Vecteur 1024D]
    Vector --> Normalize[Normalisation]
    Normalize --> Store[(Stockage)]
    
    subgraph "Préfixes"
        P1[passage: pour stockage]
        P2[query: pour recherche]
    end
    
    Prefix --> P1
    Prefix --> P2
    
    style Model fill:#e74c3c
    style Vector fill:#3498db
```

### Recherche Sémantique

```mermaid
sequenceDiagram
    participant Query
    participant Embedder
    participant VectorStore
    participant MongoDB
    participant Results
    
    Query->>Embedder: "query: {text}"
    Embedder->>Embedder: Generate embedding
    Embedder->>VectorStore: similarity_search(vector, k=5)
    VectorStore->>VectorStore: Cosine similarity
    VectorStore-->>MongoDB: Get full documents
    MongoDB-->>Results: Enriched memories
    
    Note over VectorStore: Score threshold: 0.5
    Note over Results: Sorted by similarity
```

## 📡 API et Endpoints

### Endpoints Disponibles

```mermaid
graph TD
    subgraph "Memory API Endpoints"
        GET1[GET /agents/{id}/memory<br/>Liste mémoires]
        POST1[POST /agents/{id}/memory/search<br/>Recherche sémantique]
        DELETE1[DELETE /agents/{id}/memory<br/>Effacer tout]
        DELETE2[DELETE /agents/{id}/memory/{mem_id}<br/>Effacer une mémoire]
        GET2[GET /agents/{id}/memory/summary<br/>Résumé statistiques]
        POST2[POST /agents/{id}/memory/save-conversation<br/>Sauver conversation]
        GET3[GET /agents/{id}/memory/stats<br/>Statistiques détaillées]
        GET4[GET /system/memory-info<br/>Info système]
    end
    
    style GET1 fill:#2ecc71
    style POST1 fill:#3498db
    style DELETE1 fill:#e74c3c
    style DELETE2 fill:#e74c3c
    style GET2 fill:#2ecc71
    style POST2 fill:#3498db
    style GET3 fill:#2ecc71
    style GET4 fill:#2ecc71
```

### Flow de Requêtes

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant MemoryAPI
    participant Service
    participant DB
    
    Client->>FastAPI: HTTP Request
    FastAPI->>MemoryAPI: Route Handler
    MemoryAPI->>MemoryAPI: Validate Agent
    MemoryAPI->>Service: Business Logic
    Service->>DB: Data Operations
    DB-->>Service: Results
    Service-->>MemoryAPI: Processed Data
    MemoryAPI-->>FastAPI: Response
    FastAPI-->>Client: JSON Response
    
    Note over MemoryAPI: Error Handling
    Note over Service: Dual Storage
```

## ⚙️ Configuration et Personnalisation

### Configuration par Agent

```mermaid
classDiagram
    class MemoryConfig {
        +max_memories: int = 1000
        +embedding_model: str
        +search_k: int = 5
        +context_window: int = 10
        +auto_cleanup: bool = true
        +preference_extraction: bool = true
        +importance_threshold: float = 0.5
    }
    
    class Agent {
        +id: str
        +name: str
        +memory_enabled: bool
        +memory_config: MemoryConfig
    }
    
    Agent --> MemoryConfig: has
```

### Variables d'Environnement

```mermaid
graph LR
    subgraph "Configuration Système"
        ENV1[USE_CHROMADB<br/>true/false]
        ENV2[CHROMA_PERSIST_DIR<br/>/data/chroma]
        ENV3[EMBEDDING_MODEL<br/>multilingual-e5-large]
        ENV4[MONGODB_URL<br/>mongodb://...]
        ENV5[MAX_MEMORY_PER_AGENT<br/>1000]
    end
    
    ENV1 --> VS{Vector Store}
    VS -->|true| ChromaDB
    VS -->|false| Simple
    
    ENV2 --> ChromaDB
    ENV3 --> Embedder
    ENV4 --> MongoDB
    ENV5 --> Cleanup
    
    style ENV1 fill:#3498db
    style ENV2 fill:#2ecc71
    style ENV3 fill:#e74c3c
```

## 📈 Performance et Optimisation

### Stratégies d'Optimisation

```mermaid
graph TD
    subgraph "Optimisations"
        Lazy[Lazy Loading<br/>Chargement à la demande]
        Cache[Cache Results<br/>Mise en cache]
        Batch[Batch Processing<br/>Traitement par lot]
        Index[Indexation<br/>MongoDB + ChromaDB]
        Filter[Metadata Filters<br/>Réduction espace recherche]
    end
    
    subgraph "Résultats"
        R1[Latence réduite]
        R2[Mémoire optimisée]
        R3[Scalabilité]
    end
    
    Lazy --> R1
    Cache --> R1
    Batch --> R2
    Index --> R1
    Filter --> R3
    
    style Lazy fill:#3498db
    style Cache fill:#2ecc71
    style Batch fill:#e74c3c
```

### Métriques de Performance

| Métrique | ChromaDB | Simple Store | Objectif |
|----------|----------|--------------|----------|
| Recherche (ms) | 50-100 | 10-30 | < 200 |
| Stockage (ms) | 100-200 | 20-50 | < 300 |
| Mémoires max | 10,000+ | 1,000 | Configurable |
| Taille embedding | 1024 | 384 | - |
| Persistance | ✅ | ❌ | - |

## 🔒 Gestion des Erreurs

### Stratégie de Dégradation Gracieuse

```mermaid
flowchart TD
    Op[Opération Mémoire] --> Try{Tentative}
    Try -->|Succès| Success[Retour Normal]
    Try -->|Échec ChromaDB| Fallback[Simple Store]
    Try -->|Échec Embedding| Mock[Mock Embeddings]
    Try -->|Échec Total| Log[Log Error]
    
    Fallback --> Continue[Continuer Exécution]
    Mock --> Continue
    Log --> Continue
    
    Continue --> Result[Résultat Partiel]
    
    style Success fill:#2ecc71
    style Fallback fill:#f39c12
    style Mock fill:#e67e22
    style Log fill:#e74c3c
```

## 🚀 Utilisation Pratique

### Exemple de Configuration Agent

```python
agent_config = {
    "name": "Assistant Technique",
    "memory_enabled": True,
    "memory_config": {
        "max_memories": 2000,
        "embedding_model": "intfloat/multilingual-e5-large",
        "search_k": 10,
        "context_window": 15,
        "auto_cleanup": True,
        "preference_extraction": True,
        "importance_threshold": 0.6
    }
}
```

### Exemple d'Utilisation des Outils

```python
# Recherche de contexte
context = await memory_search(
    "Quelles sont les préférences de programmation de l'utilisateur?"
)

# Stockage explicite
await memory_store(
    content="L'utilisateur préfère Python et utilise FastAPI",
    importance=0.9,
    tags=["preference", "technologie", "python"]
)

# Analyse des patterns
analysis = await memory_analyze(
    analysis_type="preferences",
    time_range="last_week"
)
```

## 📊 Monitoring et Statistiques

### Dashboard de Mémoire

```mermaid
graph TD
    subgraph "Statistiques Agent"
        Total[Total Mémoires: 472]
        Conv[Conversations: 28]
        Pref[Préférences: 15]
        Avg[Importance Moy: 0.64]
        Usage[Utilisation: 47%]
    end
    
    subgraph "Distribution Types"
        UM[User Messages: 40%]
        AR[Agent Responses: 35%]
        PR[Preferences: 10%]
        SK[Stored Knowledge: 10%]
        OT[Others: 5%]
    end
    
    subgraph "Activité"
        Today[Aujourd'hui: 12]
        Week[Cette semaine: 67]
        Month[Ce mois: 234]
    end
```

## 🎯 Cas d'Usage

### 1. Assistant Personnel
- Mémorise les préférences utilisateur
- Rappelle les conversations précédentes
- Adapte ses réponses au contexte

### 2. Support Technique
- Conserve l'historique des problèmes
- Identifie les patterns récurrents
- Suggère des solutions basées sur l'historique

### 3. Agent de Recherche
- Accumule les connaissances au fil du temps
- Évite les recherches répétitives
- Construit une base de connaissances personnalisée

## 🔮 Évolutions Futures

- **Multi-Agent Memory Sharing**: Partage de mémoires entre agents
- **Memory Compression**: Compression intelligente des anciennes mémoires
- **Semantic Clustering**: Regroupement automatique par thèmes
- **Memory Templates**: Templates réutilisables pour types de mémoires
- **Advanced Analytics**: Analyses prédictives basées sur l'historique

---

> 📝 **Note**: Ce système de mémoire transforme les agents UXMCP en assistants véritablement contextuels et personnalisés, capables d'apprendre et d'évoluer avec chaque interaction.