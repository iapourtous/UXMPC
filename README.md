# UXMCP - Universal eXtensible Model Context Protocol Manager

<div align="center">

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-blue)](https://reactjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0+-green)](https://www.mongodb.com/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-orange)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-Dual%20MIT%2FCommercial-purple)](LICENSE)

</div>

UXMCP est une plateforme complète de gestion de services MCP (Model Context Protocol) qui permet de créer, déployer et gérer dynamiquement des services pour les agents IA. Avec son interface web intuitive et son agent créateur autonome, UXMCP révolutionne la façon de construire des outils pour l'IA.

> 🎓 **Gratuit pour usage personnel et recherche** | 💼 **Licence commerciale pour entreprises**

## 🌟 Fonctionnalités Principales

### 🤖 Agent Créateur Autonome
- **Création automatique de services** par simple description en langage naturel
- **Correction automatique des erreurs** - l'agent debug et corrige le code jusqu'à ce qu'il fonctionne
- **Installation automatique des dépendances** - détecte et installe les packages manquants
- **Génération de documentation** et schémas de sortie

### 🔧 Gestion Dynamique de Services
- **3 types de services MCP** :
  - **Tools** : Actions et calculs avec schémas de sortie structurés
  - **Resources** : Fournisseurs de contenu avec types MIME
  - **Prompts** : Templates dynamiques pour les LLMs
- **Activation/désactivation en temps réel** sans redémarrage
- **Routes HTTP dynamiques** ajoutées/retirées à la volée
- **Intégration MCP native** pour tous les services actifs

### 🤝 Système d'Agents IA
- **Création d'agents personnalisés** avec profils LLM configurables
- **Accès aux outils MCP** - les agents peuvent utiliser tous les services actifs
- **Routes dynamiques** - chaque agent a son endpoint HTTP unique
- **Support streaming** pour les réponses en temps réel

### 💬 Interface de Chat Intégrée
- **Chat avec différents profils LLM** (GPT-4, Claude, etc.)
- **Historique des conversations** persistant
- **Support du streaming** pour les réponses longues
- **Interface moderne** avec Ant Design

### 🧠 Meta Chat - Création Intelligente avec Questionnaire
- **Questionnaire de clarification intelligent** - Pose des questions pertinentes pour mieux comprendre vos besoins
- **Génération automatique d'instructions** - Plus besoin de spécifier comment présenter le résultat
- **Création HTML/CSS/JS interactive** - Génère toujours des pages web modernes et interactives
- **Analyse automatique des intentions** - Comprend ce que vous voulez créer
- **Sélection ou création d'agent** - Trouve l'agent parfait ou en crée un nouveau automatiquement
- **Aucune configuration requise** - Décrivez simplement ce que vous voulez !

### 📊 Système de Logs Centralisé
- **Logs structurés dans MongoDB** avec traçabilité complète
- **API de requête puissante** avec filtres et agrégations
- **Suivi d'exécution** par service et par execution_id
- **Niveaux de log** configurables (DEBUG, INFO, WARNING, ERROR)

### 🎨 Interface Web React
- **Design moderne** avec Ant Design 5
- **Navigation intuitive** entre services, agents, profils et logs
- **Éditeur de code** avec coloration syntaxique
- **Tests intégrés** pour valider les services

## 🚀 Installation Rapide

### Prérequis
- Docker et Docker Compose
- Ports disponibles : 8000 (API), 5173 (Frontend), 27018 (MongoDB)

### Installation

```bash
# 1. Cloner le repository
git clone https://github.com/iapourtous/UXMCP.git
cd UXMCP

# 2. Lancer avec Docker Compose
make up

# 3. Accéder à l'interface
open http://localhost:5173
```

### Premier test avec Meta Chat

1. Créez d'abord un profil LLM dans l'onglet **LLM Profiles** :
   - Cliquez sur "Create New Profile"
   - Choisissez le mode **JSON** (requis pour Meta Chat)
   - **Kimi K2** est recommandé pour les meilleurs résultats
2. Allez dans l'onglet **Meta Chat**
3. Tapez simplement : `"créer un jeu de snake"`
4. Sélectionnez votre profil LLM JSON
5. Répondez aux 3-5 questions de clarification
6. Admirez votre jeu Snake fonctionnel en quelques secondes !

Meta Chat s'occupe du reste - de la conception à la réalisation ! 🎮

## 📋 Guide d'Utilisation

### Création Automatique de Service par IA

1. Allez dans l'onglet "Services"
2. Cliquez sur "Create with AI"
3. Décrivez votre service en langage naturel :
   ```
   "Un service qui extrait le texte d'une page web avec BeautifulSoup"
   ```
4. L'agent va :
   - Générer le code Python
   - Installer les dépendances nécessaires
   - Tester et corriger jusqu'à ce que ça fonctionne
   - Activer le service automatiquement

### Création Manuelle d'un Service

#### Exemple : Service Tool (Calculatrice)
```python
def handler(**params):
    operation = params.get('operation', 'add')
    a = float(params.get('a', 0))
    b = float(params.get('b', 0))
    
    if operation == 'add':
        result = a + b
    elif operation == 'multiply':
        result = a * b
    elif operation == 'power':
        result = a ** b
    else:
        return {"error": f"Unknown operation: {operation}"}
    
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result
    }
```

#### Exemple : Service Resource (Documentation)
```python
def handler(**params):
    doc_id = params.get('id', 'default')
    
    content = f"""# Documentation for {doc_id}
    
This is a sample resource providing documentation.
Generated at: {datetime.datetime.utcnow().isoformat()}
"""
    
    return {
        "content": content,
        "mimeType": "text/markdown"
    }
```

#### Exemple : Service Prompt (Template)
```python
def handler(**params):
    language = params.get('language', 'Python')
    task = params.get('task', 'explain this code')
    
    template = f"""You are an expert {language} developer.

Task: {task}

Please provide a detailed response following best practices."""
    
    return {"template": template}
```

### Création d'un Agent IA

1. Créez un profil LLM dans "LLM Profiles"
2. Allez dans "Agents" et cliquez "Create New Agent"
3. Configurez l'agent :
   - **Name** : Nom unique de l'agent
   - **System Prompt** : Instructions pour l'agent
   - **LLM Profile** : Profil à utiliser
   - **Tools** : Services MCP accessibles

### Utilisation du Meta Chat

Le Meta Chat est votre assistant intelligent qui transforme vos idées en applications web interactives grâce à un processus guidé.

#### 🎯 Le nouveau flux avec questionnaire

1. **Décrivez votre idée** en langage naturel
   ```
   "Créer un jeu de snake"
   "Afficher un graphique de mes ventes"
   "Faire un calculateur scientifique"
   ```

2. **Répondez aux questions de clarification**
   - Le système vous pose 3-5 questions contextuelles
   - Questions sur le style visuel, les fonctionnalités, le niveau de complexité
   - Vous pouvez répondre ou utiliser les valeurs par défaut

3. **Génération automatique optimisée**
   - Votre requête est enrichie avec vos réponses
   - Les instructions de présentation HTML/CSS/JS sont générées automatiquement
   - L'agent approprié est sélectionné ou créé

4. **Résultat : Une page web interactive**
   - Application HTML/CSS/JavaScript complète
   - Design moderne et responsive
   - Prête à être utilisée ou sauvegardée comme démo

#### Exemples de créations possibles avec Meta Chat

##### 🎮 Jeux interactifs
- **Tetris moderne** - Avec effets visuels, système de score et niveaux progressifs
- **Snake classique** - Version responsive avec contrôles tactiles pour mobile
- **Space Invaders** - Avec sons rétro et animations fluides
- **Memory Cards** - Jeu de mémoire avec thèmes personnalisables
- **Puzzle 2048** - Avec animations smooth et sauvegarde de score
- **Raycasting 3D** - Moteur 3D basique pour créer des labyrinthes interactifs

##### 🧮 Outils et calculatrices
- **Calculatrice scientifique** - Design moderne avec fonctions avancées :
  - Trigonométrie complète (sin, cos, tan et inverses)
  - Fonctions hyperboliques et logarithmiques
  - Mode degrés/radians avec conversion
  - Historique des calculs et mémoire
- **Convertisseur d'unités** - Multi-catégories (longueur, poids, température)
- **Calculateur de prêt** - Avec graphiques d'amortissement
- **Chronomètre/Timer** - Avec alarmes et export des temps

##### 📊 Visualisations de données
- **Dashboards interactifs** - Graphiques temps réel avec Chart.js
- **Traceur de fonctions** - Visualisation mathématique interactive
- **Générateur de fractales** - Mandelbrot, Julia avec zoom infini
- **Visualiseur de tri** - Animations d'algorithmes de tri
- **Graphiques financiers** - Chandeliers japonais, indicateurs techniques

##### 🎨 Applications créatives
- **Éditeur de pixel art** - Avec palette de couleurs et export
- **Générateur de patterns** - Motifs géométriques paramétrables
- **Simulateur de particules** - Effets visuels avec physics engine
- **Piano virtuel** - Avec sons réalistes et enregistrement
- **Canvas de dessin** - Outils de dessin avec calques

##### 📚 Outils éducatifs
- **Quiz interactif** - Avec système de points et feedback
- **Flashcards** - Pour l'apprentissage avec répétition espacée
- **Simulateur de circuits** - Logique booléenne interactive
- **Tableau périodique** - Avec informations détaillées sur chaque élément
- **Carte du monde** - Interactive avec données géographiques

#### 📸 Sauvegarde et partage de vos créations

Après avoir créé quelque chose avec Meta Chat, vous pouvez :
1. **Sauvegarder comme démo** - Conserve votre création avec toutes les métadonnées
2. **Partager via URL unique** - Chaque démo a son endpoint : `/demos/nom-de-votre-demo`
3. **Réutiliser vos créations** - Les démos sont accessibles en permanence
4. **Voir toutes vos démos** - Via l'API : `GET /demos`

Les démos sauvegardent automatiquement :
- ✅ La requête originale et la requête enrichie après clarifications
- ✅ Les instructions de présentation générées automatiquement
- ✅ L'agent utilisé et ses détails de configuration
- ✅ Le code HTML/CSS/JS complet et fonctionnel
- ✅ Les réponses au questionnaire de clarification

#### Exemple d'utilisation simple

```bash
# 1. Première requête - Le système génère un questionnaire
curl -X POST http://localhost:8000/meta-chat/clarify \
  -H "Content-Type: application/json" \
  -d '{
    "message": "créer un jeu de memory avec des cartes",
    "llm_profile": "gpt-4"
  }'

# 2. Réponse avec vos préférences au questionnaire
curl -X POST http://localhost:8000/meta-chat/process-clarifications \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "xxx-xxx-xxx",
    "answers": {
      "difficulty": "Moyen",
      "theme": "Animaux",
      "style": "Moderne"
    }
  }'
```

### Utilisation des Services

#### Via HTTP
```bash
# Service GET
curl http://localhost:8000/api/calculator?operation=add&a=5&b=3

# Service POST
curl -X POST http://localhost:8000/api/web_extractor \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

#### Via MCP
Les services actifs sont exposés sur `http://localhost:8000/mcp` pour les clients MCP.

#### Via Agents
```bash
curl -X POST http://localhost:8000/agents/my-agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Calculate 5 + 3"}'
```

## 🏗️ Architecture

```
UXMCP/
├── backend/                  # API FastAPI
│   ├── app/
│   │   ├── api/             # Endpoints REST
│   │   │   ├── services.py  # CRUD services
│   │   │   ├── agents.py    # Gestion agents
│   │   │   ├── chat.py      # Interface chat
│   │   │   ├── logs.py      # API logs
│   │   │   └── llm.py       # Profils LLM
│   │   ├── core/            # Core système
│   │   │   ├── dynamic_router.py    # Routes dynamiques
│   │   │   ├── mcp_manager.py       # Intégration MCP
│   │   │   ├── agent_tools.py       # Outils pour agents
│   │   │   └── mongodb_logger.py    # Système de logs
│   │   ├── models/          # Modèles Pydantic
│   │   └── services/        # Logic métier
│   │       ├── agent_service.py     # Agent créateur
│   │       └── service_crud.py      # CRUD services
│   └── tests/               # Tests unitaires
├── frontend/                # Interface React
│   └── src/
│       ├── components/      # Composants UI
│       │   ├── ServiceList.jsx
│       │   ├── AgentList.jsx
│       │   ├── ChatInterface.jsx
│       │   └── LogViewer.jsx
│       ├── services/        # API client
│       └── hooks/           # React hooks
├── examples/                # Services d'exemple
└── docker-compose.yml       # Configuration Docker
```

## 🔧 Configuration

### Variables d'Environnement

Créez un fichier `.env` dans le dossier `backend` :

```env
# MongoDB
MONGODB_URL=mongodb://mongo:27017
DATABASE_NAME=uxmcp

# API
MCP_SERVER_URL=http://localhost:8000/mcp
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:5173"]

# Optionnel : Clés API pour les LLMs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Configuration des Profils LLM

Les profils LLM peuvent être configurés via l'interface ou l'API. Pour Meta Chat, utilisez **obligatoirement** le mode JSON :

```json
{
  "name": "kimi-k2",
  "provider": "kimi",
  "model": "kimi-k2",
  "api_key": "sk-...",
  "endpoint": "https://api.moonshot.cn/v1/chat/completions",
  "max_tokens": 8192,
  "temperature": 0.7,
  "mode": "json",  // REQUIS pour Meta Chat
  "active": true
}
```

> 💡 **Recommandation** : Kimi K2 offre les meilleurs résultats pour Meta Chat grâce à sa compréhension approfondie des instructions et sa capacité à générer du code complexe.

## 📚 API Reference

### Services
- `GET /services` - Liste tous les services
- `POST /services` - Créer un service
- `GET /services/{id}` - Détails d'un service
- `PUT /services/{id}` - Mettre à jour un service
- `DELETE /services/{id}` - Supprimer un service
- `POST /services/{id}/activate` - Activer un service
- `POST /services/{id}/deactivate` - Désactiver un service
- `POST /services/{id}/test` - Tester un service

### Agents
- `GET /agents` - Liste tous les agents
- `POST /agents` - Créer un agent
- `POST /agents/{name}/chat` - Discuter avec un agent
- `POST /agent/create-service` - Créer un service via IA

### Logs
- `GET /logs/latest` - Logs récents
- `GET /logs/services/{service_id}` - Logs d'un service
- `GET /logs/search` - Recherche dans les logs
- `GET /logs/stats` - Statistiques des logs

### Chat
- `GET /chat/profiles` - Profils disponibles
- `POST /chat/stream` - Chat avec streaming
- `GET /chat/history` - Historique des conversations

### Meta Chat
- `POST /meta-chat/clarify` - Générer un questionnaire de clarification
  - Body: `{"message": "votre idée", "llm_profile": "nom_profil"}`
  - Response: Questionnaire avec questions contextuelles
- `POST /meta-chat/process-clarifications` - Traiter les réponses et générer le résultat
  - Body: `{"session_id": "xxx", "answers": {"q1": "réponse1", ...}}`
  - Response: Page HTML/CSS/JS interactive complète
- `POST /meta-chat/query` - Ancien endpoint direct (déprécié)
  - Préférez utiliser le flux clarify → process-clarifications

### Demos
- `GET /demos` - Liste toutes les démos créées
- `GET /demos/{name}` - Accéder à une démo spécifique (ex: `/demos/snake-game`)
- `POST /demos` - Sauvegarder une création Meta Chat comme démo
- `DELETE /demos/{id}` - Supprimer une démo

## 🛠️ Commandes Make

```bash
make help          # Afficher l'aide
make up            # Démarrer tous les services
make down          # Arrêter tous les services
make logs          # Suivre les logs
make status        # Vérifier le statut
make test          # Lancer les tests
make build         # Construire les images Docker
make clean         # Nettoyer volumes et images

# Développement
make shell-api     # Shell dans le container API
make shell-mongo   # Shell MongoDB
make import-examples  # Importer les exemples
```

## 🧪 Tests

```bash
# Tous les tests
make test

# Tests spécifiques
docker-compose exec api pytest tests/unit/test_models.py -v

# Avec couverture
docker-compose exec api pytest --cov=app
```

## 📖 Guides Avancés

### Ajouter un Nouveau Type de Service

1. Étendre le modèle dans `models/service.py`
2. Mettre à jour `mcp_manager.py` pour l'enregistrement
3. Ajouter le support UI dans `ServiceForm.jsx`
4. Documenter dans `service_documentation.py`

### Créer un Provider LLM Personnalisé

1. Implémenter l'interface dans `services/llm_service.py`
2. Ajouter la configuration dans `models/llm.py`
3. Tester avec l'agent créateur

### Débugger un Service

1. Vérifier les logs : `make logs`
2. Consulter les logs MongoDB via l'API
3. Utiliser l'endpoint de test dans l'UI
4. Examiner `/debug/mcp/info` pour l'état MCP

## 🤝 Contribution

Les contributions sont les bienvenues ! 

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

### Guidelines
- Suivre les conventions Python (PEP 8)
- Ajouter des tests pour les nouvelles fonctionnalités
- Mettre à jour la documentation
- Utiliser des messages de commit descriptifs

## 🔗 Ressources

- [Model Context Protocol](https://modelcontextprotocol.io) - Spécification MCP
- [FastAPI](https://fastapi.tiangolo.com) - Framework API
- [FastMCP](https://github.com/jlowin/fastmcp) - Implémentation Python MCP
- [React](https://reactjs.org) - Framework UI
- [Ant Design](https://ant.design) - Composants UI
- [MongoDB](https://www.mongodb.com) - Base de données

## 📄 Licence

UXMCP est distribué sous une **double licence** :

### 🎓 Usage Personnel et Recherche - MIT License
- ✅ **GRATUIT** pour usage personnel
- ✅ **GRATUIT** pour la recherche académique
- ✅ **GRATUIT** pour l'éducation
- ✅ **GRATUIT** pour les projets open source

### 💼 Usage Commercial - Licence Commerciale
- 💰 **PAYANT** pour les entreprises
- 💰 **PAYANT** pour usage commercial
- 💰 **PAYANT** pour les produits/services générant des revenus
- 📧 Contactez-nous pour obtenir une licence commerciale

Pour plus de détails, consultez :
- [LICENSE](LICENSE) - Texte complet des licences
- [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md) - Détails de la licence commerciale

## 🙏 Remerciements

- L'équipe Anthropic pour le Model Context Protocol
- La communauté FastAPI pour l'excellent framework
- Tous les contributeurs du projet

---

<div align="center">
Made with ❤️ by the UXMCP Team

**Usage personnel/recherche : MIT License | Usage commercial : Licence requise**
</div>