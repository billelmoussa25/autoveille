"""Choix du profil de recherche correspondant a une annonce.

Regle unique, utilisee partout : le motif le plus long gagne, pour que
"clio 4" l'emporte sur "clio". A motif egal, l'annee departage : une voiture
de 2014 va dans le profil dont la plage d'annees la contient.
"""


def choisir(titre, profils, annee=None):
    t = (titre or "").lower()
    candidats = []

    for profil in profils:
        correspondance = max(
            (len(m) for m in profil.get("motifs", []) if m.lower() in t),
            default=0,
        )
        if not correspondance:
            continue
        moteurs = profil.get("motifs_moteur")
        if moteurs and not any(m.lower() in t for m in moteurs):
            continue

        # Bonus si l'annee tombe dans la plage du profil : c'est ce qui
        # separe une Clio 3 d'une Clio 4 quand le titre dit juste "Clio".
        dans_plage = 0
        if annee is not None:
            mini = profil.get("annee_min")
            maxi = profil.get("annee_max")
            if (mini is None or annee >= mini) and (maxi is None or annee <= maxi):
                dans_plage = 1
            else:
                dans_plage = -1

        candidats.append((correspondance, dans_plage, profil))

    if not candidats:
        return None
    candidats.sort(key=lambda c: (-c[0], -c[1]))
    meilleur = candidats[0]
    # Motif generique et annee hors plage pour tout le monde : on ne devine pas.
    if meilleur[1] == -1:
        return None
    return meilleur[2]
