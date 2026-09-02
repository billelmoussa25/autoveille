"""Estimation a la demande : tu decris une voiture, on te dit ce qu'elle vaut.

Sert au bot Telegram et au formulaire de l'interface web. Utilise exactement
la meme reference que les alertes : le prix median des annonces saines deja
collectees pour le meme profil, la meme annee et le meme kilometrage.
"""

import re

from . import etat as etat_mod
from . import extraction
from . import profilage, scoring

AIDE = (
    "Envoie-moi une voiture, par exemple :\n"
    "  clio 4 2014 130000 4200\n"
    "  golf 6 2011 210000km 4900 € embrayage hs\n\n"
    "Modele, annee, kilometrage, prix. Ajoute la panne si le vehicule est HS."
)


def _profil_correspondant(texte, profils, annee=None):
    """Renvoie (profil, texte prive du nom du modele).

    Le nom est retire pour que le chiffre d'une "clio 4" ou d'une "golf 6" ne
    soit pas pris pour une donnee. Le motif le plus long gagne : "clio 4"
    l'emporte sur "clio".
    """
    t = texte.lower()
    profil = profilage.choisir(texte, profils, annee)
    if profil is None:
        return None, texte
    motifs = sorted((m.lower() for m in profil.get("motifs", []) if m.lower() in t),
                    key=len, reverse=True)
    return profil, t.replace(motifs[0], " ", 1) if motifs else (profil, t)


NOMBRE = re.compile(extraction.NOMBRE)


def _nombres(texte):
    """Extrait annee, kilometrage et prix d'une saisie libre."""
    t = texte.lower().replace("\u202f", " ")

    annee = None
    m = re.search(r"\b(19[89]\d|20[0-2]\d)\b", t)
    if m:
        annee = int(m.group(1))
        t = t[:m.start()] + " " + t[m.end():]

    km = None
    m = re.search(NOMBRE.pattern + r"(?=\s*(?:km|kms)\b)", t)
    if m:
        km = int(re.sub(r"[^\d]", "", m.group(0)))
        t = t[:m.start()] + " " + t[m.end():]

    prix = None
    m = re.search(NOMBRE.pattern + r"(?=\s*(?:€|eur|euros)\b)", t)
    if m:
        prix = int(re.sub(r"[^\d]", "", m.group(0)))
        t = t[:m.start()] + " " + t[m.end():]

    # Nombres restants : le plus grand est le kilometrage, l'autre le prix.
    restants = [int(re.sub(r"[^\d]", "", n)) for n in NOMBRE.findall(t)]
    restants = [n for n in restants if n > 50]
    restants.sort(reverse=True)
    for n in restants:
        if km is None and n >= 15000:
            km = n
        elif prix is None:
            prix = n
    return annee, km, prix


def estimer(saisie, conf):
    """Renvoie un dictionnaire de resultat, ou {'erreur': ...}."""
    profils = conf["profils"]
    general = conf["general"]
    reparation = conf.get("reparation", {})
    marge_min = conf.get("alertes_hs", {}).get("marge_minimum", 1200)
    seuil = conf.get("alertes_saines", {}).get("seuil_alerte", 0.12)

    annee_indice = re.search(r"\b(19[89]\d|20[0-2]\d)\b", saisie)
    profil, reste = _profil_correspondant(
        saisie, profils, int(annee_indice.group(1)) if annee_indice else None)
    if profil is None:
        return {"erreur": "Modele non reconnu. Il doit faire partie de tes "
                          "profils de recherche dans config.yml."}

    annee, km, prix = _nombres(reste)
    manquants = [nom for nom, valeur in
                 (("annee", annee), ("kilometrage", km), ("prix", prix))
                 if valeur is None]
    if manquants:
        return {"erreur": "Il me manque : " + ", ".join(manquants) + "."}

    etat, panne, cout_min, cout_max, drapeaux = etat_mod.analyser(
        saisie, None, reparation.get("pannes", {}))

    annonce = {"profil": profil["id"], "annee": annee, "km": km, "prix": prix,
               "carburant": None, "etat": etat, "panne": panne,
               "cout_min": cout_min, "cout_max": cout_max,
               "drapeaux": ";".join(drapeaux)}

    median, nb, ecart, marge = scoring.evaluer(annonce, general, reparation)

    return {"profil": profil, "annee": annee, "km": km, "prix": prix,
            "etat": etat, "panne": panne, "cout_min": cout_min,
            "cout_max": cout_max, "drapeaux": drapeaux, "median": median,
            "comparables": nb, "ecart": ecart, "marge": marge,
            "marge_minimum": marge_min, "seuil": seuil}


def en_texte(res):
    """Met le resultat en forme pour Telegram."""
    if "erreur" in res:
        return res["erreur"] + "\n\n" + AIDE

    euros = lambda v: f"{v:,}".replace(",", " ") + " €"
    lignes = [f"<b>{res['profil']['libelle']}</b>",
              f"{res['annee']} · {euros(res['km']).replace(' €', ' km')} · {euros(res['prix'])}"]

    if res["median"] is None:
        lignes.append(f"\nPas encore de reference fiable : seulement "
                      f"{res['comparables']} annonces comparables en base.")
        return "\n".join(lignes)

    if res["etat"] == "reparer":
        panne = (res["panne"] or "non precisee").replace("_", " ")
        lignes.append(f"\nPanne : {panne} (repa. {res['cout_min']}–{res['cout_max']} €)")
        lignes.append(f"Revente estimee : {euros(res['median'])}")
        if res["marge"] is not None:
            verdict = "à voir" if res["marge"] >= res["marge_minimum"] else "trop juste"
            lignes.append(f"<b>Marge ~{euros(res['marge'])}</b> — {verdict}")
    else:
        pourcent = round(res["ecart"] * 100)
        lignes.append(f"\nReference : {euros(res['median'])}")
        if pourcent == 0:
            lignes.append("<b>Au prix du marche</b>")
        elif pourcent > 0:
            verdict = ("ça vaut le coup d'œil" if res["ecart"] >= res["seuil"]
                       else "dans le marche")
            lignes.append(f"<b>{pourcent} % sous le marche</b> — {verdict}")
        else:
            lignes.append(f"<b>{abs(pourcent)} % au-dessus du marche</b>")

    lignes.append(f"<i>sur {res['comparables']} annonces comparables</i>")
    for d in res["drapeaux"]:
        lignes.append(f"⚠️ mention « {d.replace('_', ' ')} » reperee")
    return "\n".join(lignes)
