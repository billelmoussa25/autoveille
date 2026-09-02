"""Detection de l'etat d'un vehicule et estimation du cout de remise en route.

Deux categories :
  - "sain"     : vehicule roulant, annonce normale
  - "reparer"  : vehicule en panne, accidente ou refuse au controle technique

Pour un vehicule a reparer, on identifie la panne annoncee et on lui associe
une fourchette de cout. Ces fourchettes sont dans config.yml : ce sont des
valeurs de depart, a remplacer par tes propres couts.
"""

import re

# Mentions qui bloquent ou compliquent serieusement la revente.
# "gage" = le vehicule porte une opposition, la carte grise ne peut pas etre
# transferee tant qu'elle n'est pas levee.
# "VGE" / "VEI" = procedure vehicule gravement endommage ou economiquement
# irreparable : le vehicule est immobilise administrativement tant qu'un
# expert n'a pas valide la reparation.
DRAPEAUX = {
    "gage":            ["gagé", "gage", "opposition", "non gageable"],
    "procedure_vge":   ["vge", "vei", "véhicule gravement", "vehicule gravement",
                        "procédure", "procedure", "expertise bloquante"],
    "sans_papiers":    ["sans carte grise", "sans cg", "carte grise détruite",
                        "pas de carte grise", "hors circulation"],
    "pour_pieces":     ["pour pièces", "pour pieces", "pieces detachees",
                        "pièces détachées", "épave", "epave"],
}

# Signaux generaux qu'on a affaire a un vehicule non roulant / a reprendre.
SIGNAUX_HS = [
    "hs", "h.s", "hors service", "en panne", "ne démarre pas", "ne demarre pas",
    "demarre pas", "ne roule pas", "à réparer", "a reparer", "à restaurer",
    "accidenté", "accidente", "ct refusé", "ct refuse", "contre-visite",
    "sans ct", "non roulant", "immobilisé", "immobilise", "vice caché",
    "moteur cassé", "moteur casse", "bruit moteur", "fume",
    "en l'etat", "en letat", "vendue en l'etat", "vendu en l'etat",
    "a debattre pour reparation", "projet", "pour bricoleur", "mecano",
]


def _normaliser(texte):
    t = (texte or "").lower()
    t = t.replace("’", "'")
    return re.sub(r"\s+", " ", t)


def analyser(titre, description=None, catalogue_pannes=None):
    """Renvoie (etat, panne, cout_min, cout_max, drapeaux).

    etat    : "sain" ou "reparer"
    panne   : identifiant de la panne detectee, ou None
    drapeaux: liste des mentions bloquantes reperees
    """
    texte = _normaliser(f"{titre or ''} {description or ''}")
    catalogue_pannes = catalogue_pannes or {}

    drapeaux = [nom for nom, motifs in DRAPEAUX.items()
                if any(m in texte for m in motifs)]

    # Panne identifiee : on prend la premiere qui correspond, le catalogue
    # etant ordonne du plus grave au plus benin dans config.yml.
    panne = None
    cout_min = cout_max = None
    for identifiant, regles in catalogue_pannes.items():
        motifs = [m.lower() for m in regles.get("motifs", [])]
        if any(m in texte for m in motifs):
            panne = identifiant
            cout_min = regles.get("cout_min")
            cout_max = regles.get("cout_max")
            break

    est_hs = bool(panne) or bool(drapeaux) or any(
        re.search(rf"(?<![a-z]){re.escape(s)}(?![a-z])", texte) for s in SIGNAUX_HS
    )

    if not est_hs:
        return "sain", None, None, None, []

    # Panne non identifiee : on retombe sur la fourchette generique.
    if panne is None and "indetermine" in catalogue_pannes:
        panne = "indetermine"
        cout_min = catalogue_pannes["indetermine"].get("cout_min")
        cout_max = catalogue_pannes["indetermine"].get("cout_max")

    return "reparer", panne, cout_min, cout_max, drapeaux
