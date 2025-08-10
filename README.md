# UXMCP - Universal eXtensible Model Context Protocol Manager

<div align="center">

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-blue)](https://reactjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0+-green)](https://www.mongodb.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Embedded-purple)](https://www.trychroma.com/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-orange)](https://modelcontextprotocol.io)

</div>

UXMCP est une plateforme complète de gestion de services MCP (Model Context Protocol) qui permet de créer, déployer et gérer dynamiquement des services pour les agents IA. Avec son interface web intuitive, ses agents intelligents et son système de création automatique, UXMCP révolutionne la façon de construire des outils pour l'IA.

## 🌟 Fonctionnalités Principales

### 🤖 Agents IA Intelligents
- **Configuration 7D avancée** : Backstory, Objectifs, Contraintes, Mémoire, Raisonnement, Personnalité, Politiques de décision
- **Chain of Thought Adaptatif** : Système de raisonnement multi-étapes inspiré d'Auto-CoT avec sélection automatique de stratégies
- **Mémoire persistante avec ChromaDB** : Les agents se souviennent des interactions passées
- **Accès à tous les outils MCP** : Utilisation dynamique de tous les services actifs
- **Chat agentique avancé** : Interface de conversation avec prévisualisation HTML intégrée
- **Sauvegarde de démos** : Transformation des réponses HTML en démos interactives

### 🛠️ Création Automatique de Services
- **Agent créateur autonome** : Création de services par description en langage naturel
- **Correction automatique** : L'agent débugue et corrige le code jusqu'à ce qu'il fonctionne
- **Gestion des dépendances** : Installation automatique des packages Python nécessaires
- **Tests intégrés** : Validation automatique avant activation

### 🔧 Services MCP Dynamiques
- **3 types de services** :
  - **Tools** : Actions et calculs avec schémas structurés
  - **Resources** : Fournisseurs de contenu avec types MIME
  - **Prompts** : Templates dynamiques pour les LLMs
- **Activation/désactivation à chaud** : Sans redémarrage du système
- **Routes HTTP dynamiques** : Endpoints créés automatiquement
- **Intégration MCP native** : Compatible avec tous les clients MCP

### 💾 Conversations Persistantes
- **Sauvegarde automatique** : Toutes les conversations sont enregistrées
- **Historique consultable** : Retrouvez facilement vos échanges passés
- **Multi-agents** : Utilisez différents agents dans la même conversation
- **Export en démo** : Transformez les réponses HTML en démos partageables

### 🎨 Système de Démos Interactives
- **Hébergement de démos HTML/CSS/JS** : Créez et partagez des démos web
- **Création depuis le chat** : Sauvegardez directement les réponses HTML des agents
- **Endpoints dynamiques** : Chaque démo a son URL unique
- **Gestion complète** : Listez, modifiez et supprimez vos démos

### 🧠 Meta-Agent Créateur
- **Création automatique d'agents** : Décrivez vos besoins, le meta-agent s'occupe du reste
- **Analyse des capacités** : Identifie les outils manquants
- **Création de services** : Génère automatiquement les services nécessaires
- **Configuration optimale** : Configure l'agent avec les meilleurs paramètres

### 🔗 Connexions MCP Externes
- **Intégration serveurs externes** : Connectez-vous à Context7, APIs personnalisées, autres serveurs MCP
- **Authentification multiple** : Support OAuth, API Key, Basic Auth
- **Cache intelligent** : Mise en cache des outils et ressources pour de meilleures performances
- **Outils transparents** : Les outils externes apparaissent naturellement dans les agents
- **Monitoring avancé** : Test de connectivité, ping automatique, retry intelligent
- **Transport multiple** : Support SSE, HTTP, et stdio pour maximum de compatibilité

### 📊 Système de Logs Avancé
- **Logs MongoDB structurés** : Traçabilité complète des exécutions
- **Filtrage puissant** : Par service, niveau, date, execution_id
- **API de requête** : Recherche et agrégation avancées
- **Interface web** : Visualisation en temps réel des logs

### 🎯 Gestion des Profils LLM
- **Multi-providers** : OpenAI, Anthropic, Google, et plus
- **Configuration flexible** : Température, tokens, mode de réponse
- **Sélection dynamique** : Changez de modèle à la volée
- **Support streaming** : Réponses en temps réel

## 🚀 Installation Rapide

### Prérequis
- Docker et Docker Compose
- Ports disponibles : 8000 (API), 5173 (Frontend), 27018 (MongoDB)
- 4GB de RAM minimum recommandé

### Installation

```bash
# 1. Cloner le repository
git clone https://github.com/yourusername/uxmcp.git
cd uxmcp

# 2. Lancer avec Docker Compose
make up

# 3. Accéder à l'interface
open http://localhost:5173
```

## 📋 Guide d'Utilisation

### 🎯 Création Automatique de Service par IA

1. Naviguez vers **Services** → **Create with AI**
2. Décrivez votre service en langage naturel :
   ```
   Un service qui analyse le sentiment d'un texte avec TextBlob
   ```
3. L'agent va automatiquement :
   - Générer le code Python approprié
   - Installer TextBlob et ses dépendances
   - Créer les tests et la documentation
   - Activer le service une fois fonctionnel

### 🤝 Utilisation du Chat Agentique

1. Allez dans **Agent Chat**
2. Sélectionnez un agent dans la liste
3. Commencez votre conversation
4. Fonctionnalités spéciales :
   - **Prévisualisation HTML** : Si l'agent génère du HTML, cliquez sur "Preview"
   - **Sauvegarde en démo** : Transformez les réponses HTML en démos permanentes
   - **Historique** : Retrouvez toutes vos conversations passées
   - **Multi-agents** : Changez d'agent sans perdre la conversation

### 🧠 Création d'Agent avec Meta-Agent

1. Naviguez vers **Agents** → **Create Meta Agent**
2. Décrivez votre besoin :
   ```
   J'ai besoin d'un agent expert en analyse de données qui peut 
   faire des graphiques et des statistiques
   ```
3. Le Meta-Agent va :
   - Analyser vos besoins
   - Identifier les outils nécessaires
   - Créer les services manquants
   - Configurer l'agent optimal

### 💡 Création Manuelle de Services

#### Service Tool (Analyse de sentiment)
```python
def handler(**params):
    from textblob import TextBlob
    
    text = params.get('text', '')
    if not text:
        return {"error": "No text provided"}
    
    blob = TextBlob(text)
    sentiment = blob.sentiment
    
    return {
        "text": text,
        "polarity": sentiment.polarity,
        "subjectivity": sentiment.subjectivity,
        "sentiment": "positive" if sentiment.polarity > 0 else "negative" if sentiment.polarity < 0 else "neutral"
    }
```

#### Service Resource (Données JSON)
```python
def handler(**params):
    import json
    
    data = {
        "users": [
            {"id": 1, "name": "Alice", "role": "admin"},
            {"id": 2, "name": "Bob", "role": "user"}
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return {
        "content": json.dumps(data, indent=2),
        "mimeType": "application/json"
    }
```

#### Service Prompt (Template personnalisé)
```python
def handler(**params):
    context = params.get('context', 'general')
    style = params.get('style', 'professional')
    
    template = f"""You are an AI assistant specialized in {context}.
Your communication style is {style}.

When responding:
1. Be clear and concise
2. Provide actionable insights
3. Support your answers with examples

How can I help you today?"""
    
    return {"template": template}
```

### 🎭 Configuration d'un Agent

1. **Créez un profil LLM** dans "LLM Profiles"
2. **Créez un nouvel agent** avec configuration 7D :
   - **Backstory** : Histoire et expertise de l'agent
   - **Objectives** : Buts et missions
   - **Constraints** : Limites et règles
   - **Memory** : Configuration de la mémoire
   - **Reasoning** : Approche de raisonnement
   - **Personality** : Traits de personnalité
   - **Decision Policies** : Règles de décision

### 🔗 Connexions MCP Externes

UXMCP peut se connecter à des serveurs MCP externes pour étendre les capacités des agents.

#### Connexion à Context7 (Documentation)

1. **Cloner et démarrer Context7** :
   ```bash
   git clone https://github.com/upstash/context7.git
   cd context7
   npm install && npm run build
   npm start -- --transport http --port 3001
   ```

2. **Créer la connexion dans UXMCP** :
   - Naviguez vers "MCP Connections"
   - Créez une nouvelle connexion :
     - **Nom** : Context7 Documentation Server
     - **URL** : `http://172.19.0.1:3001/mcp` (adresse Docker)
     - **Transport** : SSE
     - **Auth** : None

3. **Tester et synchroniser** :
   - Cliquez "Test Connection" (doit montrer 2 outils détectés)
   - Cliquez "Sync" pour mettre en cache les outils

4. **Assigner à un agent** :
   - Éditez un agent existant ou créez-en un nouveau
   - Dans "MCP Connections", sélectionnez votre connexion Context7
   - L'agent aura maintenant accès à `resolve-library-id` et `get-library-docs`

#### Exemple d'utilisation
```
Agent: Comment utiliser React hooks avec TypeScript ?

L'agent utilisera automatiquement :
1. resolve-library-id("react") → trouve l'ID Context7 de React
2. get-library-docs("/reactjs/react.dev", topic="hooks typescript") 
   → récupère la documentation officielle
```

### 🎨 Création de Démos

1. **Depuis le chat** : Cliquez sur "Save as Demo" sur une réponse HTML
2. **Via l'API** : POST vers `/demos/` avec le contenu HTML
3. **Gestion** : Section "Demos" pour voir et gérer toutes vos démos
4. **Partage** : Chaque démo a une URL unique accessible

## 🏗️ Architecture

```
UXMCP/
├── backend/                      # API FastAPI
│   ├── app/
│   │   ├── api/                 # Endpoints REST
│   │   │   ├── services.py      # CRUD services MCP
│   │   │   ├── agents.py        # Gestion des agents
│   │   │   ├── agent.py         # Agent créateur
│   │   │   ├── agent_memory.py  # API mémoire agents
│   │   │   ├── meta_agent.py    # Meta-agent créateur
│   │   │   ├── conversations.py # Gestion conversations
│   │   │   ├── demos.py         # Gestion démos
│   │   │   ├── chat.py          # Interface chat
│   │   │   ├── logs.py          # API logs
│   │   │   └── llms.py          # Profils LLM
│   │   ├── core/                # Core système
│   │   │   ├── dynamic_router.py     # Routes dynamiques
│   │   │   ├── mcp_manager.py        # Intégration MCP
│   │   │   ├── agent_router.py       # Routes agents
│   │   │   ├── agent_tools.py        # Outils pour agents
│   │   │   └── mongodb_logger.py     # Système de logs
│   │   ├── models/              # Modèles Pydantic
│   │   │   ├── service.py       # Modèles services
│   │   │   ├── agent.py         # Modèles agents
│   │   │   ├── mcp_connection.py # Modèles connexions MCP
│   │   │   ├── conversation.py  # Modèles conversations
│   │   │   └── demo.py          # Modèles démos
│   │   ├── services/            # Logique métier
│   │   │   ├── agent_service.py      # Agent créateur
│   │   │   ├── agent_executor.py     # Exécution agents
│   │   │   ├── cot_adaptive_engine.py # Moteur Chain of Thought adaptatif
│   │   │   ├── cot_complexity_analyzer.py # Analyseur de complexité Auto-CoT
│   │   │   ├── cot_demonstration_generator.py # Générateur de démonstrations
│   │   │   ├── meta_agent_service.py # Service meta-agent
│   │   │   ├── mcp_connection_service.py # CRUD connexions MCP
│   │   │   ├── mcp_client_service.py # Client MCP externe
│   │   │   └── conversation_crud.py  # CRUD conversations
│   │   └── prompts/             # Templates prompts
│   └── tests/                   # Tests unitaires
├── frontend/                    # Interface React
│   └── src/
│       ├── components/          # Composants UI
│       │   ├── ServiceListAntd.jsx    # Liste services
│       │   ├── AgentList.jsx          # Liste agents
│       │   ├── ChatWithAgents.jsx     # Chat agentique
│       │   ├── MetaAgentCreator.jsx   # Créateur meta-agent
│       │   ├── MCPConnectionList.jsx  # Liste connexions MCP
│       │   ├── DemoList.jsx           # Liste démos
│       │   └── LogsView.jsx           # Visualiseur logs
│       ├── services/            # API client
│       └── hooks/               # React hooks
├── examples/                    # Services d'exemple
├── docker-compose.yml           # Configuration Docker
└── Makefile                     # Commandes utiles
```

## 🔧 Configuration

### Variables d'Environnement

Créez un fichier `.env` dans le dossier `backend` :

```env
# MongoDB
MONGODB_URL=mongodb://mongo:27017
DATABASE_NAME=uxmcp

# ChromaDB
CHROMA_PERSIST_DIRECTORY=/app/chroma_data
CHROMA_COLLECTION_NAME=agent_memories

# API
MCP_SERVER_URL=http://localhost:8000/mcp
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:5173"]

# LLM API Keys (optionnel)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

### Configuration des Profils LLM

```json
{
  "name": "claude-3-opus",
  "provider": "anthropic",
  "model": "claude-3-opus-20240229",
  "api_key": "sk-ant-...",
  "endpoint": "https://api.anthropic.com/v1/messages",
  "max_tokens": 4096,
  "temperature": 0.7,
  "mode": "text",  // ou "json" pour réponses structurées
  "active": true
}
```

## 📚 API Reference

### Services MCP
- `GET /services` - Liste tous les services
- `POST /services` - Créer un service
- `GET /services/{id}` - Détails d'un service
- `PUT /services/{id}` - Mettre à jour
- `DELETE /services/{id}` - Supprimer
- `POST /services/{id}/activate` - Activer
- `POST /services/{id}/deactivate` - Désactiver
- `POST /services/{id}/test` - Tester

### Agents IA
- `GET /agents` - Liste tous les agents
- `POST /agents` - Créer un agent
- `GET /agents/{id}` - Détails agent
- `PUT /agents/{id}` - Mettre à jour
- `DELETE /agents/{id}` - Supprimer
- `POST /agents/{id}/activate` - Activer
- `POST /agents/{id}/execute` - Exécuter
- `GET /agents/{id}/validate` - Valider config

### Agent Memory
- `GET /agents/{id}/memory` - Liste mémoires
- `POST /agents/{id}/memory/search` - Recherche
- `DELETE /agents/{id}/memory/{memory_id}` - Supprimer
- `GET /agents/{id}/memory/summary` - Statistiques

### Conversations
- `GET /conversations` - Liste conversations
- `POST /conversations` - Créer conversation
- `GET /conversations/{id}` - Détails
- `PUT /conversations/{id}` - Mettre à jour
- `DELETE /conversations/{id}` - Supprimer
- `POST /conversations/{id}/messages` - Ajouter message
- `GET /conversations/summaries` - Résumés
- `GET /conversations/latest` - Dernière conversation

### Démos
- `GET /demos` - Liste démos
- `POST /demos` - Créer démo
- `GET /demos/{name}` - Voir démo
- `PUT /demos/{id}` - Mettre à jour
- `DELETE /demos/{id}` - Supprimer

### Meta-Agent
- `POST /meta-agent/create` - Créer agent automatiquement
- `POST /meta-agent/analyze` - Analyser besoins
- `POST /meta-agent/suggest-tools` - Suggérer outils

### AI Agent Créateur
- `POST /agent/create-service` - Créer service par IA (SSE)

### Logs
- `GET /logs/latest` - Logs récents
- `GET /logs/{collection}` - Logs par collection
- `GET /logs/app` - Logs application
- `GET /logs/services/{service_id}` - Logs service
- `GET /logs/search` - Recherche avancée

## 🛠️ Commandes Make

```bash
make help          # Afficher l'aide
make up            # Démarrer tous les services
make down          # Arrêter tous les services
make logs          # Suivre les logs
make status        # Vérifier le statut
make test          # Lancer les tests
make build         # Construire les images
make clean         # Nettoyer volumes et images

# Développement
make shell-api     # Shell dans container API
make shell-mongo   # Shell MongoDB
make import-examples  # Importer exemples
```

## 🧪 Tests

```bash
# Tous les tests
make test

# Tests spécifiques
docker-compose exec api pytest tests/unit/test_models.py -v

# Avec couverture
docker-compose exec api pytest --cov=app

# Tests d'intégration
docker-compose exec api pytest tests/integration/ -v
```

## 🎯 Cas d'Usage

### 1. Assistant de Développement
```python
# Créez un agent avec accès aux outils de code
agent_config = {
    "name": "dev-assistant",
    "backstory": "Expert Python avec 10 ans d'expérience",
    "objectives": ["Aider au développement", "Réviser le code", "Suggérer des améliorations"],
    "tools": ["code_analyzer", "test_runner", "documentation_generator"]
}
```

### 2. Analyseur de Données
```python
# Service pour analyse de CSV
def handler(**params):
    import pandas as pd
    import json
    
    csv_content = params.get('csv_content')
    df = pd.read_csv(io.StringIO(csv_content))
    
    analysis = {
        "shape": df.shape,
        "columns": df.columns.tolist(),
        "summary": df.describe().to_dict(),
        "missing_values": df.isnull().sum().to_dict()
    }
    
    return analysis
```

### 3. Générateur de Rapports
```python
# Agent avec mémoire pour suivi de projets
agent = {
    "name": "project-reporter",
    "memory": {"enabled": True, "max_memories": 1000},
    "personality": "Professionnel et synthétique",
    "decision_policies": ["Prioriser les faits", "Éviter les répétitions"]
}
```

## 📖 Guides Avancés

### Chain of Thought Adaptatif
Le système intègre un moteur de raisonnement Chain of Thought adaptatif inspiré d'Auto-CoT :
- **Analyse de complexité** : Classification automatique des problèmes (simple, arithmétique, logique, multi-étapes, créatif, analytique)
- **Stratégies diversifiées** : Sélection automatique parmi décomposition, raisonnement arrière, analogie, etc.
- **Itérations adaptatives** : Nombre d'itérations ajusté selon la complexité (3-15 max)
- **Convergence intelligente** : Détection automatique quand le raisonnement a atteint une solution satisfaisante
- **Support d'outils** : Intégration transparente des outils MCP dans le processus de raisonnement
- **Voir [adaptativeCOT.md](adaptativeCOT.md)** pour une documentation complète

### Optimisation des Agents
1. **Mémoire** : Activez ChromaDB pour les contextes longs
2. **Tools** : Limitez aux outils nécessaires pour la performance
3. **Prompts** : Utilisez des instructions claires et structurées
4. **Température** : Ajustez selon le besoin (0.3 pour précision, 0.8 pour créativité)
5. **Chain of Thought** : Activez le raisonnement adaptatif pour les tâches complexes

### Sécurité
1. **API Keys** : Stockez dans des variables d'environnement
2. **CORS** : Configurez les origines autorisées en production
3. **Validation** : Tous les inputs sont validés par Pydantic
4. **Sandboxing** : L'exécution de code est isolée

### Performance
1. **Cache** : Les services compilés sont mis en cache
2. **Async** : Toute l'API est asynchrone
3. **Indexes** : MongoDB indexes sur les champs fréquents
4. **Pagination** : Toutes les listes supportent la pagination

## 🤝 Contribution

Les contributions sont les bienvenues ! 

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

### Guidelines
- Suivre PEP 8 pour Python
- Tests requis pour nouvelles fonctionnalités
- Documentation des endpoints API
- Messages de commit descriptifs

## 🐛 Troubleshooting

### Problèmes Courants

**Services qui ne s'activent pas**
- Vérifiez les logs : `make logs`
- Testez le service : bouton "Test" dans l'UI
- Vérifiez les dépendances Python

**Agents sans réponse**
- Vérifiez le profil LLM est actif
- Vérifiez les clés API
- Consultez les logs de l'agent

**Erreurs MongoDB**
- Vérifiez que MongoDB est démarré : `make status`
- Vérifiez l'espace disque disponible

## 📄 License

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🔗 Ressources

- [Model Context Protocol](https://modelcontextprotocol.io) - Spécification MCP
- [FastAPI](https://fastapi.tiangolo.com) - Framework API
- [FastMCP](https://github.com/jlowin/fastmcp) - Implémentation Python MCP
- [React](https://reactjs.org) - Framework UI
- [Ant Design](https://ant.design) - Composants UI
- [MongoDB](https://www.mongodb.com) - Base de données
- [ChromaDB](https://www.trychroma.com) - Base vectorielle

## 🙏 Remerciements

- L'équipe Anthropic pour le Model Context Protocol
- La communauté FastAPI pour l'excellent framework
- Les contributeurs open source
- Tous les utilisateurs et testeurs du projet

---

<div align="center">
Made with ❤️ by the UXMCP Team
</div>