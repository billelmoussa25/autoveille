"""Alerteur : relit la base et notifie ce qui n'a pas encore ete envoye.

Deux instances tournent en parallele, chacune sur sa categorie :
  MODE=saines  -> vehicules roulants sous le prix du marche
  MODE=hs      -> vehicules a reparer, et annonces tres bas prix

Chacune a son propre seuil et son propre canal Telegram. Tu peux en arreter
une sans toucher a l'autre.
"""

import os
import time
import traceback

from . import db, notify, scoring
from .config import charger

MODE = os.environ.get("MODE", "saines")
ETATS = {"saines": "sain", "hs": "reparer"}


BLOQUANTS = ("gage", "procedure_vge", "sans_papiers")


def _coup_de_filet(annonce, reglages):
    """Annonce tres bas prix : on la fait passer meme sans panne identifiee
    et meme sans assez de comparables pour calculer une marge.

    Les mentions qui bloquent la revente restent eliminatoires : un vehicule
    gage a 500 € n'est pas une affaire, c'est un probleme administratif."""
    plafond = reglages.get("prix_coup_de_filet")
    if not plafond:
        return False
    drapeaux = (annonce.get("drapeaux") or "").split(";")
    if any(d in BLOQUANTS for d in drapeaux if d):
        return False
    prix = annonce.get("prix") or 0
    return 0 < prix <= plafond


def un_passage(conf):
    etat = ETATS[MODE]
    reglages = conf.get(f"alertes_{MODE}", {})
    if not reglages.get("actif", True):
        return

    general = conf["general"]
    reparation = dict(conf.get("reparation", {}))
    reparation["actif"] = True
    reparation["marge_minimum"] = reglages.get("marge_minimum", 1200)
    general = dict(general)
    general["seuil_alerte"] = reglages.get("seuil_alerte", 0.12)
    general["prix_plancher"] = reglages.get("prix_plancher", 800)

    libelles = {p["id"]: p.get("libelle", p["id"]) for p in conf["profils"]}
    variable_chat = reglages.get("telegram_chat", "TELEGRAM_CHAT_ID")
    conversation = os.environ.get(variable_chat) or os.environ.get("TELEGRAM_CHAT_ID")

    envoyees = 0
    for annonce in db.a_notifier(etat):
        merite = scoring.merite_alerte(
            annonce, annonce.get("ecart"), annonce.get("marge"), general, reparation)
        if not merite and MODE == "hs":
            merite = _coup_de_filet(annonce, reglages)
        if not merite:
            db.marquer_notifiee(annonce["id"])   # evaluee, ecartee, on n'y revient pas
            continue

        if notify.envoyer(annonce, annonce.get("prix_median"), annonce.get("ecart"),
                          annonce.get("marge"), libelles.get(annonce["profil"], "?"),
                          conversation=conversation):
            db.marquer_notifiee(annonce["id"])
            envoyees += 1

    if envoyees:
        print(f"[{MODE}] {envoyees} alerte(s) envoyee(s)")


def main():
    if MODE not in ETATS:
        raise SystemExit(f"MODE inconnu : {MODE}. Valeurs acceptees : {list(ETATS)}")
    db.init()
    print(f"alerteur demarre en mode {MODE}")
    while True:
        conf = charger()
        try:
            un_passage(conf)
        except Exception:
            traceback.print_exc()
        time.sleep(conf.get(f"alertes_{MODE}", {}).get("intervalle_minutes", 5) * 60)


if __name__ == "__main__":
    main()
