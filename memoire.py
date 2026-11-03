# memoire.py
# ----------
# Labo Agent cognitif, partie 2 : la mémoire (gérer le contexte).
# Une conversation de 8 tours avec l'agent de la partie 1, sous un budget artificiel de jetons.
#
# Lancer :
#   python memoire.py                        # budget 2000, résumé quand ça déborde
#   python memoire.py --budget 600           # budget plus petit pour voir le résumé se déclencher
#   python memoire.py --budget 600 --mode tronquer   # sans résumé : on oublie les vieux messages
#   python memoire.py --interactif           # taper soi-même les 8 messages

import argparse

import requests

from agent import (MAX_TOURS, MODELE, PROMPT_SYSTEME, URL_OLLAMA,
                   executer, lire_action, MOTIF_REPONSE)

PROMPT_SYSTEME_MEMOIRE = PROMPT_SYSTEME + """

Tu discutes avec la même personne pendant plusieurs tours.
Retiens ce qu'elle te dit (son prénom, son budget, ses achats).
Si une question ne demande aucun outil, réponds directement :
Pensée : je connais la réponse
Réponse : ..."""

# Les 8 messages de la conversation : l'information à retenir est donnée au tour 1
MESSAGES = [
    "Bonjour, je m'appelle Edan et mon budget est de 300 $. Retiens bien ces deux informations.",
    "Combien coûtent 2 casques ?",
    "Et combien coûte une webcam ?",
    "Si j'achète 2 casques et une webcam, combien je dépense au total ?",
    "Est-ce que ça entre dans mon budget ? Combien me resterait-il ?",
    "Combien coûtent 3 claviers et 2 souris ?",
    "Combien coûte une souris ?",
    "Pour finir : quel est mon prénom et quel est mon budget ?",
]


# --- Le budget de jetons ------------------------------------------------------------
def estimer_jetons(historique):
    """Estimation grossière : 1 jeton pour 4 caractères. Le prompt système n'est pas compté."""
    return sum(len(message["content"]) for message in historique[1:]) // 4


def afficher_budget(historique, budget, etiquette="Mémoire"):
    jetons = estimer_jetons(historique)
    barre = "█" * min(20, jetons * 20 // budget) + "░" * max(0, 20 - jetons * 20 // budget)
    print(f"[{etiquette} : {jetons} / {budget} jetons {barre}]\n")
    return jetons


# --- Les deux stratégies quand le budget déborde ---------------------------------------------
def appel_libre(prompt):
    """Appel au modèle sans le format ReAct (pour écrire le résumé)."""
    reponse = requests.post(URL_OLLAMA, json={
        "model": MODELE,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0},
    }, timeout=300)
    reponse.raise_for_status()
    return reponse.json()["message"]["content"].strip()


def resumer(historique):
    """Demande au modèle de résumer l'historique en 5 lignes et remplace l'historique par ce résumé."""
    conversation = "\n".join(f"{m['role']} : {m['content']}" for m in historique[1:])
    resume = appel_libre(
        "Résume la conversation ci-dessous en 5 lignes maximum, en français.\n"
        "Tu dois OBLIGATOIREMENT conserver : le prénom de l'utilisateur, son budget, "
        "les prix déjà trouvés et les totaux calculés.\n"
        "N'écris que le résumé, sans introduction.\n\n"
        f"Conversation :\n{conversation}"
    )
    print("📝 Résumé produit par le modèle :")
    print("   " + resume.replace("\n", "\n   ") + "\n")
    return [
        historique[0],                                   # on garde le prompt système
        {"role": "user", "content": f"Résumé de notre conversation jusqu'ici :\n{resume}"},
        {"role": "assistant", "content": "Pensée : je retiens ce résumé.\nRéponse : compris."},
    ]


def tronquer(historique, budget):
    """Sans résumé : on oublie les plus vieux messages jusqu'à repasser sous le budget."""
    oublies = 0
    while estimer_jetons(historique) > budget and len(historique) > 2:
        historique.pop(1)                                # le plus vieux après le prompt système
        oublies += 1
    print(f"✂️  {oublies} vieux messages oubliés pour repasser sous le budget.\n")
    return historique


# --- Un tour de conversation = la boucle ReAct de la partie 1, sur l'historique partagé -------
def appeler_modele_react(historique):
    reponse = requests.post(URL_OLLAMA, json={
        "model": MODELE,
        "messages": historique,
        "stream": False,
        "options": {"temperature": 0, "stop": ["Observation", "\nQuestion"]},
    }, timeout=300)
    reponse.raise_for_status()
    return reponse.json()["message"]["content"].strip()


def tour_de_conversation(historique, message):
    historique.append({"role": "user", "content": f"Question : {message}"})
    for _ in range(MAX_TOURS):
        texte = appeler_modele_react(historique)
        print(texte)
        historique.append({"role": "assistant", "content": texte})

        action = lire_action(texte)
        if action:
            observation = executer(*action)
            print(f"Observation : {observation}")
            historique.append({"role": "user", "content": f"Observation : {observation}"})
            continue
        if MOTIF_REPONSE.search(texte):
            return
        historique.append({"role": "user", "content":
            "Respecte le format : une ligne « Action : outil(\"argument\") » ou « Réponse : ... »."})
    print(f"⛔ Limite de {MAX_TOURS} tours atteinte.")


# --- La conversation ------------------------------------------------------------------------------
def conversation(budget, mode, interactif):
    historique = [{"role": "system", "content": PROMPT_SYSTEME_MEMOIRE}]
    print(f"Modèle : {MODELE} | Budget : {budget} jetons (1 jeton ≈ 4 caractères) | Mode : {mode}\n")

    for numero in range(1, len(MESSAGES) + 1):
        message = input(f"Vous (tour {numero}) : ") if interactif else MESSAGES[numero - 1]
        print(f"========== Tour {numero} ==========")
        print(f"Vous : {message}")
        tour_de_conversation(historique, message)

        jetons = afficher_budget(historique, budget)
        if jetons > budget:
            print(f"⚠️  Budget dépassé ({jetons} > {budget}).")
            if mode == "resume":
                historique = resumer(historique)
            else:
                historique = tronquer(historique, budget)
            afficher_budget(historique, budget, "Mémoire après")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent avec mémoire sous budget de jetons")
    parser.add_argument("--budget", type=int, default=2000)
    parser.add_argument("--mode", choices=["resume", "tronquer"], default="resume")
    parser.add_argument("--interactif", action="store_true")
    arguments = parser.parse_args()
    conversation(arguments.budget, arguments.mode, arguments.interactif)
