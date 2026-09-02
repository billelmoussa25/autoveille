"""Deux calculs distincts selon l'etat du vehicule.

Vehicule sain    : on cherche l'ecart au prix median du marche.
Vehicule a reparer : on cherche la marge estimee une fois remis en route.
Dans les deux cas la reference est la meme, le prix median des annonces
SAINES comparables deja collectees.
"""

import statistics

from . import db


def _reference(annonce, general):
    """Prix median des vehicules sains comparables, et taille de l'echantillon."""
    minimum = general.get("comparables_minimum", 8)

    prix_comparables = db.comparables(
        annonce["profil"], annonce.get("annee"), annonce.get("km"),
        carburant=annonce.get("carburant"),
    )
    # Echantillon trop maigre une fois filtre sur le carburant : on elargit.
    if len(prix_comparables) < minimum and annonce.get("carburant"):
        prix_comparables = db.comparables(
            annonce["profil"], annonce.get("annee"), annonce.get("km")
        )

    prix = annonce.get("prix")
    if annonce.get("etat") == "sain" and prix in prix_comparables:
        prix_comparables.remove(prix)      # ne pas se comparer a soi-meme

    if len(prix_comparables) < minimum:
        return None, len(prix_comparables)
    median = statistics.median(prix_comparables)
    return (int(median) if median > 0 else None), len(prix_comparables)


def evaluer(annonce, general, reparation=None):
    """Renvoie (prix_median, nb_comparables, ecart, marge).

    ecart concerne les vehicules sains, marge les vehicules a reparer :
    l'un des deux vaut toujours None.
    """
    prix = annonce.get("prix")
    if not prix or prix <= 0:
        return None, 0, None, None

    median, nb = _reference(annonce, general)
    if median is None:
        return None, nb, None, None

    if annonce.get("etat") != "reparer":
        return median, nb, round((median - prix) / median, 4), None

    # Vehicule a reparer : on retient le haut de la fourchette de cout, c'est
    # celui qui compte quand on decide d'y aller ou pas.
    cout = annonce.get("cout_max")
    if cout is None:
        return median, nb, None, None

    decote = (reparation or {}).get("decote_revente", 0.12)
    revente_estimee = median * (1 - decote)
    marge = int(revente_estimee - prix - cout)
    return median, nb, None, marge


def merite_alerte(annonce, ecart, marge, general, reparation=None):
    reparation = reparation or {}

    if annonce.get("etat") == "reparer":
        if not reparation.get("actif"):
            return False
        if marge is None:
            return False
        # Mentions qui bloquent la revente : on ne notifie pas, l'annonce
        # reste consultable dans l'interface avec son avertissement.
        drapeaux = (annonce.get("drapeaux") or "").split(";")
        if any(d in ("gage", "procedure_vge", "sans_papiers") for d in drapeaux if d):
            return False
        return marge >= reparation.get("marge_minimum", 1200)

    if ecart is None:
        return False
    if ecart < general.get("seuil_alerte", 0.12):
        return False
    if (annonce.get("prix") or 0) < general.get("prix_plancher", 800):
        return False
    return True
