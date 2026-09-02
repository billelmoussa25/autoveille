"""Filtrage geographique par departement.

Le departement se lit sur les deux premiers chiffres du code postal, sauf
en Corse (2A/2B, codes 200xx a 206xx) et outre-mer (trois chiffres).
"""

REGIONS = {
    "idf":                    ["75", "77", "78", "91", "92", "93", "94", "95"],
    "hauts_de_france":        ["02", "59", "60", "62", "80"],
    "grand_est":              ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],
    "normandie":              ["14", "27", "50", "61", "76"],
    "bretagne":               ["22", "29", "35", "56"],
    "pays_de_la_loire":       ["44", "49", "53", "72", "85"],
    "centre_val_de_loire":    ["18", "28", "36", "37", "41", "45"],
    "bourgogne_franche_comte":["21", "25", "39", "58", "70", "71", "89", "90"],
    "nouvelle_aquitaine":     ["16", "17", "19", "23", "24", "33", "40", "47",
                               "64", "79", "86", "87"],
    "occitanie":              ["09", "11", "12", "30", "31", "32", "34", "46",
                               "48", "65", "66", "81", "82"],
    "auvergne_rhone_alpes":   ["01", "03", "07", "15", "26", "38", "42", "43",
                               "63", "69", "73", "74"],
    "paca":                   ["04", "05", "06", "13", "83", "84"],
    "corse":                  ["2A", "2B"],
}

# Codes region utilises dans les adresses de recherche de La Centrale.
# A verifier sur le site : ils changent rarement mais ils ne sont pas publics.
CODES_LACENTRALE = {
    "idf": "FR-IDF", "hauts_de_france": "FR-HDF", "grand_est": "FR-GES",
    "normandie": "FR-NOR", "bretagne": "FR-BRE", "pays_de_la_loire": "FR-PDL",
    "centre_val_de_loire": "FR-CVL", "bourgogne_franche_comte": "FR-BFC",
    "nouvelle_aquitaine": "FR-NAQ", "occitanie": "FR-OCC",
    "auvergne_rhone_alpes": "FR-ARA", "paca": "FR-PAC", "corse": "FR-COR",
}


def resoudre(entrees):
    """Transforme une liste melangeant regions et departements en ensemble
    de departements. ["idf", "60", "27"] -> {"75", ..., "95", "60", "27"}"""
    departements = set()
    for entree in entrees or []:
        cle = str(entree).strip().lower().replace("-", "_").replace(" ", "_")
        if cle in REGIONS:
            departements.update(REGIONS[cle])
        else:
            code = str(entree).strip().upper()
            if len(code) == 1:
                code = "0" + code
            departements.add(code)
    return departements


def departement(code_postal):
    """Departement correspondant a un code postal, ou None."""
    if not code_postal:
        return None
    cp = str(code_postal).strip()
    if not cp[:2].isdigit():
        return None
    if cp.startswith("20"):                       # Corse
        try:
            return "2A" if int(cp[:3]) <= 201 else "2B"
        except ValueError:
            return None
    if cp.startswith("97") or cp.startswith("98"):  # outre-mer
        return cp[:3]
    return cp[:2]


def dans_zone(code_postal, departements, garder_si_inconnu=True):
    """Vrai si l'annonce est dans la zone retenue. Une zone vide n'exclut
    personne. Un code postal absent est conserve par defaut : mieux vaut une
    annonce en trop qu'une bonne affaire ratee."""
    if not departements:
        return True
    dep = departement(code_postal)
    if dep is None:
        return garder_si_inconnu
    return dep in departements


def codes_regions(departements):
    """Codes region La Centrale couvrant les departements demandes."""
    codes = []
    for region, deps in REGIONS.items():
        if departements & set(deps):
            code = CODES_LACENTRALE.get(region)
            if code and code not in codes:
                codes.append(code)
    return codes
