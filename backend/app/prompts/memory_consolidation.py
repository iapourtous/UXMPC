"""
Memory Consolidation Prompts

Prompts for LLM-based memory consolidation
"""

CONSOLIDATION_PROMPT = """Tu es un expert en synthèse et consolidation de mémoire. Ta tâche est de fusionner intelligemment plusieurs mémoires similaires en une seule mémoire consolidée de haute qualité.

Voici {count} mémoires similaires à consolider :

{memories}

Instructions pour la consolidation :

1. **Fusion des informations redondantes** : Identifie et fusionne les informations répétées en gardant la version la plus complète et précise.

2. **Préservation des détails uniques** : TOUS les détails importants et uniques de chaque mémoire doivent être préservés. Ne perds aucune information significative.

3. **Identification des patterns** : Identifie les patterns récurrents, les préférences utilisateur, et les tendances qui émergent de ces mémoires.

4. **Structure claire** : Organise l'information de manière logique et structurée, en utilisant des sections si nécessaire.

5. **Contexte temporel** : Si les mémoires contiennent des informations temporelles, préserve la chronologie et note les évolutions.

6. **Synthèse intelligente** : Ne te contente pas de concaténer - crée une synthèse cohérente qui capture l'essence de toutes les mémoires.

Format de sortie souhaité :
- Commence par un résumé exécutif de 2-3 phrases
- Organise ensuite par thèmes ou catégories logiques
- Utilise des bullet points pour les listes d'éléments
- Maximum 500 mots au total

Résumé consolidé :"""

PREFERENCE_CONSOLIDATION_PROMPT = """Tu es un expert en analyse des préférences utilisateur. Consolide ces préférences en un profil cohérent.

Préférences à analyser :
{preferences}

Crée un profil consolidé qui :
1. Regroupe les préférences par catégorie
2. Identifie les préférences les plus fortes
3. Note les éventuelles contradictions
4. Extrait les patterns comportementaux

Profil consolidé :"""

TECHNICAL_CONSOLIDATION_PROMPT = """Tu es un expert technique. Consolide ces informations techniques en une documentation claire.

Informations techniques :
{technical_info}

Crée une documentation consolidée qui :
1. Organise par type (configurations, commandes, erreurs, solutions)
2. Préserve tous les détails techniques précis
3. Identifie les relations entre éléments
4. Structure pour faciliter la recherche future

Documentation consolidée :"""