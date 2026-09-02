"""Collecteur : ramasse les annonces, les stocke, calcule les scores.

Il n'envoie aucune notification. C'est le role des deux alerteurs, qui
relisent la base chacun de leur cote. Un seul collecteur pour les deux, pour
ne pas doubler les requetes vers les sites.
"""

import time
import traceback

from . import db, scoring, zone
from .config import charger
from .sources import lacentrale, mails_leboncoin


def un_passage(conf):
    general = conf["general"]
    profils = conf["profils"]
    sources = conf.get("sources", {})
    reparation = conf.get("reparation", {})
    pannes = reparation.get("pannes", {})

    reglages_zone = conf.get("zone", {})
    departements = zone.resoudre(reglages_zone.get("departements"))
    garder_si_inconnu = reglages_zone.get("garder_si_inconnu", True)

    recoltees = []

    if sources.get("lacentrale", {}).get("actif"):
        pause = sources["lacentrale"].get("pause_secondes", 12)
        for profil in profils:
            try:
                recoltees += lacentrale.collecter(
                    profil, general, pause=pause, catalogue_pannes=pannes,
                    departements=departements, garder_si_inconnu=garder_si_inconnu)
            except Exception:
                print(f"[lacentrale] erreur sur le profil {profil['id']}")
                traceback.print_exc()

    # En dessous de ce prix, on bascule l'annonce dans la categorie "a reparer"
    # meme si aucune panne n'est annoncee : c'est le flux qui doit la traiter.
    plafond = conf.get("alertes_hs", {}).get("prix_coup_de_filet")

    if sources.get("mails_leboncoin", {}).get("actif"):
        try:
            recoltees += mails_leboncoin.collecter(
                profils, sources["mails_leboncoin"], catalogue_pannes=pannes,
                departements=departements, garder_si_inconnu=garder_si_inconnu)
        except Exception:
            print("[mails] erreur de collecte")
            traceback.print_exc()

    nouvelles = 0
    a_reparer = 0
    for annonce in recoltees:
        prix = annonce.get("prix") or 0
        if plafond and 0 < prix <= plafond and annonce.get("etat") != "reparer":
            annonce["etat"] = "reparer"
            annonce["panne"] = annonce.get("panne") or "indetermine"

        if not db.enregistrer(annonce):
            continue
        nouvelles += 1
        if annonce.get("etat") == "reparer":
            a_reparer += 1
        median, nb, ecart, marge = scoring.evaluer(annonce, general, reparation)
        db.maj_score(annonce["id"], median, nb, ecart, marge)

    zone_lisible = ", ".join(sorted(departements)) if departements else "France entiere"
    print(f"collecte terminee : {len(recoltees)} annonces dans la zone "
          f"[{zone_lisible}], {nouvelles} nouvelles dont {a_reparer} a reparer")


def main():
    db.init()
    while True:
        conf = charger()
        try:
            un_passage(conf)
        except Exception:
            traceback.print_exc()
        time.sleep(conf["general"].get("intervalle_minutes", 25) * 60)


if __name__ == "__main__":
    main()
