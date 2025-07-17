# Prompt Centralization Status

## ✅ Prompts Centralisés (Completed)

### Meta Chat Service
- [x] `meta_chat/analyze_intent.txt` - Analyse des requêtes utilisateur
- [x] `meta_chat/find_suitable_agent.txt` - Sélection d'agent
- [x] `meta_chat/direct_response.txt` - Réponse directe
- [ ] `meta_chat/generate_html_response.txt` - Génération HTML (fichier créé mais pas encore utilisé dans le code)

### Agent Service  
- [x] `agent_service/generate_initial_service.txt` - Création initiale de service
- [x] `agent_service/api_section_template.txt` - Template pour configuration API
- [x] `agent_service/fix_service_error.txt` - Correction d'erreurs de test
- [x] `agent_service/generate_test_params.txt` - Génération de paramètres de test
- [x] `agent_service/fix_activation_error.txt` - Correction d'erreurs d'activation
- [x] `agent_service/evaluate_test_result.txt` - Évaluation des résultats de test
- [ ] `agent_service/fix_from_test.txt` - Correction basée sur les tests (à créer)

### Service Generator
- [x] `service_generator/generation_prompt.txt` - Prompt principal de génération

### Meta Agent
- [x] `meta_agent/analyze_requirements.txt` - Analyse des besoins d'agent

### Tool Analyzer
- [x] `tool_analyzer/identify_tools.txt` - Identification des outils requis
- [x] `tool_analyzer/match_services.txt` - Correspondance avec services existants
- [ ] `tool_analyzer/evaluate_compatibility.txt` - Évaluation de compatibilité (à créer)
- [ ] `tool_analyzer/generate_spec.txt` - Génération de spécifications (à créer)

### Agent Executor
- [x] `agent_executor/system_prompt_template.txt` - Template de prompt système

## ❌ Prompts Non Centralisés (À faire)

### Code à modifier pour utiliser les prompts centralisés:

1. **meta_chat_service.py**
   - [ ] Ligne ~402: HTML response generation prompt

2. **agent_service.py**  
   - [ ] Ligne ~781: Test parameter generation
   - [ ] Ligne ~850: Fix activation error
   - [ ] Ligne ~1152: Test result evaluation
   - [ ] Ligne ~1230: Fix based on test result

3. **service_generator.py**
   - [ ] Remplacer la constante GENERATION_PROMPT par le chargement du fichier

4. **meta_agent_service.py**
   - [ ] Ligne ~272: Agent requirements analysis

5. **tool_analyzer.py**
   - [ ] Ligne ~38: Required tools analysis
   - [ ] Ligne ~116: Service matching
   - [ ] Ligne ~184: Service compatibility evaluation
   - [ ] Ligne ~243: Tool specification generation

6. **agent_executor.py**
   - [ ] Lignes 196-267: Dynamic system prompt construction

## Structure des Prompts

```
backend/app/prompts/
├── meta_chat/
│   ├── analyze_intent.txt ✅
│   ├── find_suitable_agent.txt ✅
│   ├── direct_response.txt ✅
│   └── generate_html_response.txt ✅
├── agent_service/
│   ├── generate_initial_service.txt ✅
│   ├── api_section_template.txt ✅
│   ├── fix_service_error.txt ✅
│   ├── generate_test_params.txt ✅
│   ├── fix_activation_error.txt ✅
│   └── evaluate_test_result.txt ✅
├── service_generator/
│   └── generation_prompt.txt ✅
├── meta_agent/
│   └── analyze_requirements.txt ✅
├── tool_analyzer/
│   ├── identify_tools.txt ✅
│   └── match_services.txt ✅
├── agent_executor/
│   └── system_prompt_template.txt ✅
└── llm_profiles/
    └── (vide pour l'instant)
```

## Prochaines Étapes

1. Finir de modifier le code pour utiliser tous les prompts centralisés
2. Ajouter le système de feedback dans meta_chat
3. Créer un agent qui peut modifier les prompts basé sur le feedback
4. Implémenter le versioning des prompts
5. Ajouter des tests pour le système de prompts