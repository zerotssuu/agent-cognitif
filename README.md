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

## Partie 2 : la mémoire (gérer le contexte)

- [`memoire.py`](memoire.py) : conversation de 8 tours avec l'agent de la partie 1. Le budget de l'historique est estimé (1 jeton ≈ 4 caractères, prompt système non compté) et affiché à chaque tour. Au tour 1, l'utilisateur donne son prénom et son budget ; au tour 8, il les redemande.
- Budget de 2000 jetons ([transcription](transcription-partie2-budget2000.txt)) : rien ne déborde, les 8 tours n'atteignent que 615 jetons. Un budget de 600 n'aurait débordé qu'après le tour 8, trop tard pour vérifier la mémoire : le budget a donc été baissé à **300**.
- Budget de 300, **sans résumé** ([transcription](transcription-partie2-tronquer.txt)) : à chaque débordement, les plus vieux messages sont oubliés. Au tour 8, l'agent ne connaît plus ni le prénom ni le budget ; il tente même `chercherPrix("")`, puis redemande l'information.
- Budget de 300, **avec résumé** ([transcription](transcription-partie2.txt)) : au tour 5 (342 > 300), le modèle résume l'historique en 5 lignes, qui remplacent l'historique (prompt système conservé). La mémoire tombe à 85 jetons, et au tour 8 l'agent répond correctement : Edan, 300 $.

📑 **Que perd-on dans un résumé, et comment le choisir ?**

On perd le détail et la trace : la formulation exacte des messages, l'ordre des étapes, les Pensées et les appels d'outils intermédiaires, les nuances et le ton. Le résumé est aussi écrit par le modèle lui-même : il peut se tromper, arrondir ou oublier un fait, et cette erreur devient alors la seule « vérité » pour la suite de la conversation, sans retour possible au texte d'origine.

Pour bien le choisir, il faut décider à l'avance de ce qui doit survivre : les faits durables donnés par l'utilisateur (prénom, budget, contraintes), les résultats d'outils qui coûtent cher à refaire (prix trouvés, totaux calculés) et les décisions prises. Notre consigne nomme explicitement ces éléments (« Tu dois OBLIGATOIREMENT conserver : le prénom, le budget, les prix et les totaux »), c'est ce qui a permis à l'agent de répondre au tour 8. On peut aussi garder les derniers messages intacts et ne résumer que les plus anciens, ou ne pas résumer du tout les faits essentiels en les stockant à part, dans une mémoire structurée. À l'inverse, tronquer sans résumer est simple et gratuit, mais ce sont justement les informations du début, souvent les plus importantes, qui disparaissent en premier.
