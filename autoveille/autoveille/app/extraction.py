"""Lecture des nombres dans un texte d'annonce.

Un seul endroit pour cette logique, parce qu'elle est piegeuse : dans
"Clio 4 1.5 dCi 4 100 € 2014 129 000 km", une regex trop permissive avale
l'annee au passage et sort un kilometrage de 2 014 129 000.

La regle : un nombre est soit ecrit d'un bloc (129000), soit decoupe en
groupes de trois exactement (129 000, 129.000). Rien d'autre ne se colle.
"""

import re

# Les \b sont indispensables : sans eux, la regex demarre au milieu de "2014"
# et reconstruit "014 129 000" a cheval sur l'annee et le kilometrage.
# Le \b initial est indispensable : sans lui, la regex demarre au milieu de
# "2014" et reconstruit "014 129 000" a cheval sur l'annee et le kilometrage.
# Pas de \b final, sinon "89000km" colle au suffixe et n'est plus reconnu.
NOMBRE = r"\b\d{1,3}(?:[ .\u00a0\u202f]\d{3})+|\b\d+"


def entier(texte):
    chiffres = re.sub(r"[^\d]", "", texte or "")
    return int(chiffres) if chiffres else None


def _avant(texte, suffixe):
    """Nombre place juste avant un suffixe donne (km, €...)."""
    m = re.search(rf"({NOMBRE})\s*(?:{suffixe})", texte, re.I)
    return entier(m.group(1)) if m else None


def annee(texte):
    m = re.search(r"\b(19[89]\d|20[0-2]\d)\b", texte or "")
    return int(m.group(1)) if m else None


def kilometrage(texte):
    return _avant(texte or "", r"km\b|kms\b")


def prix(texte):
    return _avant(texte or "", r"€|eur\b|euros\b")


def code_postal(texte, exclure=()):
    """Code postal a cinq chiffres, en ecartant les valeurs deja identifiees
    comme prix, kilometrage ou annee."""
    exclus = {str(v) for v in exclure if v is not None}
    for m in re.finditer(r"\b(\d{5})\b", texte or ""):
        if m.group(1) not in exclus:
            return m.group(1)
    return None
