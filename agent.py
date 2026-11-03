# agent.py
# --------
# Labo Agent cognitif, partie 1 : les outils et la boucle ReAct (penser, agir, observer).
# Aucune librairie d'agents : la boucle est à nous, comme la machine d'états était à nous.
#
# Lancer :  python agent.py "Combien coûtent 3 claviers et 2 souris ?"

import ast
import operator
import re
import sys

import requests

# --- Réglages -----------------------------------------------------------------
MODELE = "qwen2.5:3b"                         # modèle Ollama (essayer qwen2.5:7b si le format est mal suivi)
URL_OLLAMA = "http://localhost:11434/api/chat"
MAX_TOURS = 10                                # limite de sécurité de la boucle
FICHIER_PRIX = "prix.txt"


# --- Les outils -----------------------------------------------------------------
# calculer() n'utilise PAS eval() : eval exécuterait n'importe quel code Python
# envoyé par le modèle. On analyse l'expression et on n'accepte que l'arithmétique.
OPERATIONS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _evaluer(noeud):
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return noeud.value
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in OPERATIONS:
        return OPERATIONS[type(noeud.op)](_evaluer(noeud.left), _evaluer(noeud.right))
    if isinstance(noeud, ast.UnaryOp) and type(noeud.op) in OPERATIONS:
        return OPERATIONS[type(noeud.op)](_evaluer(noeud.operand))
    raise ValueError("expression non arithmétique")


def calculer(expression):
    """Évalue une expression arithmétique, par exemple « 3 * 45 + 2 * 25 »."""
    try:
        resultat = _evaluer(ast.parse(expression, mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError) as erreur:
        return f"Erreur : impossible de calculer « {expression} » ({erreur})"
    if isinstance(resultat, float) and resultat.is_integer():
        resultat = int(resultat)
    return str(resultat)


def chercherPrix(produit):
    """Lit le prix d'un produit dans prix.txt (une ligne par produit : clavier;45)."""
    cherche = produit.strip().lower()
    with open(FICHIER_PRIX, encoding="utf-8") as fichier:
        for ligne in fichier:
            if ";" not in ligne:
                continue
            nom, prix = ligne.strip().split(";", 1)
            if nom.strip().lower() == cherche:
                return prix.strip()
    return f"Erreur : produit « {produit} » introuvable"


OUTILS = {"calculer": calculer, "chercherPrix": chercherPrix}


# --- Le prompt système ----------------------------------------------------------
PROMPT_SYSTEME = """Tu es un agent qui répond aux questions sur les prix d'une boutique.
Tu ne connais AUCUN prix par cœur : tu dois utiliser tes outils.

Outils disponibles :
- chercherPrix(produit) : donne le prix unitaire d'un produit, en dollars. Exemple : chercherPrix("clavier")
- calculer(expression) : évalue une expression arithmétique. Exemple : calculer("3 * 45")

Format imposé. À chaque tour, écris UNE Pensée puis UNE Action, et arrête-toi :
Pensée : ce que tu dois faire maintenant
Action : nomOutil("argument")

Le système te répondra par :
Observation : le résultat de l'outil

Quand tu as tout ce qu'il faut, écris :
Pensée : j'ai la réponse
Réponse : la réponse finale, en une phrase

Règles :
- Une seule Action par tour, jamais deux.
- N'écris jamais toi-même de ligne « Observation » : attends celle du système.
- Utilise calculer pour tout calcul, même simple.

Exemple :
Question : Combien coûtent 3 claviers ?
Pensée : il me faut le prix du clavier.
Action : chercherPrix("clavier")
Observation : 45
Pensée : 3 claviers font 3 x 45.
Action : calculer("3 * 45")
Observation : 135
Pensée : j'ai la réponse
Réponse : trois claviers coûtent 135 $."""


# --- L'appel au modèle -----------------------------------------------------------
def appeler_modele(historique):
    reponse = requests.post(URL_OLLAMA, json={
        "model": MODELE,
        "messages": historique,
        "stream": False,
        # stop : le modèle s'arrête avant d'inventer sa propre Observation
        "options": {"temperature": 0, "stop": ["Observation", "\nQuestion"]},
    }, timeout=300)
    reponse.raise_for_status()
    return reponse.json()["message"]["content"].strip()


# --- La lecture de la réponse -----------------------------------------------------
MOTIF_ACTION = re.compile(r"Action\s*:\s*(\w+)\s*\((.*)\)")
MOTIF_REPONSE = re.compile(r"Réponse\s*:\s*(.+)", re.DOTALL)


def lire_action(texte):
    """Retourne (outil, argument) si le texte contient une Action, sinon None."""
    trouve = MOTIF_ACTION.search(texte)
    if not trouve:
        return None
    outil = trouve.group(1)
    argument = trouve.group(2).strip().strip("\"'«» ").strip()
    return outil, argument


def executer(outil, argument):
    if outil not in OUTILS:
        return f"Erreur : outil « {outil} » inconnu. Outils permis : {', '.join(OUTILS)}"
    return OUTILS[outil](argument)


# --- La boucle ReAct -------------------------------------------------------------------
def agent(question):
    historique = [
        {"role": "system", "content": PROMPT_SYSTEME},
        {"role": "user", "content": f"Question : {question}"},
    ]
    print(f"Question : {question}\n")

    for tour in range(1, MAX_TOURS + 1):
        texte = appeler_modele(historique)
        print(f"--- Tour {tour} ---")
        print(texte)
        historique.append({"role": "assistant", "content": texte})

        action = lire_action(texte)
        if action:                                   # 1. une Action : on exécute l'outil
            outil, argument = action
            observation = executer(outil, argument)
            print(f"Observation : {observation}\n")
            historique.append({"role": "user", "content": f"Observation : {observation}"})
            continue

        reponse = MOTIF_REPONSE.search(texte)
        if reponse:                                  # 2. une Réponse : c'est fini
            print(f"\n✅ Réponse finale : {reponse.group(1).strip()}")
            return reponse.group(1).strip()

        # 3. ni Action ni Réponse : on rappelle le format
        print("(format non respecté, rappel envoyé)\n")
        historique.append({"role": "user", "content":
            "Respecte le format : écris une ligne « Action : outil(\"argument\") » "
            "ou une ligne « Réponse : ... »."})

    print(f"\n⛔ Limite de {MAX_TOURS} tours atteinte sans réponse.")
    return None


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Combien coûtent 3 claviers et 2 souris ?"
    agent(question)
