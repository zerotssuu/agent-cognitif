# 🤖 Agent cognitif : outils, mémoire, harnais

Labo de la série violette (Laboratoires Agents). Boucle d'agent écrite à la main, sans librairie d'agents.

**Modèle de langage** : `qwen2.5:3b` en local avec Ollama (aucune clé d'API, aucun coût).  
**Lancer** : `python agent.py "Combien coûtent 3 claviers et 2 souris ?"`

## Partie 1 : les outils (boucle ReAct)

- [`agent.py`](agent.py) : deux outils, `calculer(expression)` et `chercherPrix(produit)`, le prompt système au format imposé (Pensée / Action / Observation / Réponse) et la boucle limitée à 10 tours.
- [`prix.txt`](prix.txt) : une ligne par produit, `clavier;45`.
- [`transcription-partie1.txt`](transcription-partie1.txt) : l'agent décide seul d'appeler `chercherPrix` deux fois, puis `calculer`, avant de répondre 185 $.

Deux choix de conception :
- `calculer` n'utilise pas `eval()`, qui exécuterait n'importe quel code Python envoyé par le modèle. L'expression est analysée avec `ast`, et seuls les nombres et opérateurs arithmétiques sont acceptés.
- L'appel au modèle utilise `stop: ["Observation"]` : le modèle s'arrête avant d'inventer lui-même le résultat d'un outil. Seul le programme écrit les Observations.
