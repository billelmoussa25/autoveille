"""Collecte des annonces sur La Centrale.

A lire avant utilisation
------------------------
Les conditions generales du site interdisent la collecte automatisee. Ce
module reste volontairement minimal et poli : il lit robots.txt, s'annonce
avec un user-agent honnete (la ligne d'identification que tout client HTTP
envoie au serveur) et respecte une pause entre chaque requete. Il ne
contient et ne contiendra aucun contournement de protection anti-robot.

Les selecteurs CSS ci-dessous sont a verifier sur le code source reel de la
page : ils changent des que le site refait son interface. C'est le seul bloc
a maintenir dans le temps.
"""

import hashlib
import re
import time
import urllib.robotparser as robotparser
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .. import extraction
from .. import etat as etat_mod
from .. import profilage
from .. import zone as zone_mod

BASE = "https://www.lacentrale.fr"
UA = "autoveille/1.0 (veille personnelle, faible frequence)"

# ---------------------------------------------------------------------------
# BLOC A AJUSTER : selecteurs CSS de la page de resultats
# ---------------------------------------------------------------------------
SELECTEURS = {
    "carte":       "div[class*='searchCard']",
    "lien":        "a[href*='/auto-occasion-annonce-']",
    "titre":       "[class*='vehicleTitle'], h3",
    "prix":        "[class*='Price'], [class*='price']",
    "photo":       "img",
    "attributs":   "[class*='criteria'], [class*='Criteria']",
}
# ---------------------------------------------------------------------------


def _autorise(url, session):
    """Verifie robots.txt avant d'aller plus loin."""
    rp = robotparser.RobotFileParser()
    try:
        r = session.get(f"{BASE}/robots.txt", timeout=15)
        rp.parse(r.text.splitlines())
    except Exception:
        return False
    return rp.can_fetch(UA, url)


def _url_recherche(profil, departements):
    params = [f"makesModelsCommercialNames={profil['marque'].upper()}"]
    if profil.get("prix_max"):
        params.append(f"priceMax={profil['prix_max']}")
    if profil.get("km_max"):
        params.append(f"mileageMax={profil['km_max']}")
    if profil.get("annee_min"):
        params.append(f"yearMin={profil['annee_min']}")
    codes = zone_mod.codes_regions(departements)
    if codes:
        params.append("regions=" + ",".join(codes))
    return f"{BASE}/listing?{'&'.join(params)}"



CARBURANTS = {
    "diesel":  ["dci", "hdi", "tdci", "tdi", "cdti", "diesel", "d-4d", "blue hdi", "bluehdi"],
    "essence": ["tce", "vti", "tsi", "essence", "16v", "vvt-i", "sce", "thp", "fsi"],
}


def _carburant(titre):
    t = (titre or "").lower()
    for nom, motifs in CARBURANTS.items():
        if any(m in t for m in motifs):
            return nom
    return None

def collecter(profil, general, pause=12, catalogue_pannes=None,
              departements=None, garder_si_inconnu=True):
    """Renvoie une liste d'annonces normalisees pour un profil."""
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "fr-FR"})

    departements = departements or set()
    url = _url_recherche(profil, departements)
    if not _autorise(url, session):
        print(f"[lacentrale] robots.txt refuse {url} — profil ignore")
        return []

    time.sleep(pause)
    try:
        reponse = session.get(url, timeout=25)
    except requests.RequestException as e:
        print(f"[lacentrale] requete echouee : {e}")
        return []

    if reponse.status_code in (403, 429):
        print(f"[lacentrale] bloque (code {reponse.status_code}). "
              f"Espace davantage les passages ou desactive cette source.")
        return []
    if reponse.status_code != 200:
        print(f"[lacentrale] reponse inattendue : {reponse.status_code}")
        return []

    soup = BeautifulSoup(reponse.text, "lxml")
    cartes = soup.select(SELECTEURS["carte"])
    if not cartes:
        print("[lacentrale] aucune carte trouvee : les selecteurs CSS sont "
              "probablement obsoletes, a revoir dans SELECTEURS.")
        return []

    maintenant = datetime.now(timezone.utc).isoformat()
    annonces = []
    for carte in cartes:
        lien = carte.select_one(SELECTEURS["lien"])
        if not lien or not lien.get("href"):
            continue
        href = lien["href"]
        url_annonce = href if href.startswith("http") else BASE + href

        el_titre = carte.select_one(SELECTEURS["titre"])
        titre = el_titre.get_text(" ", strip=True) if el_titre else ""

        el_prix = carte.select_one(SELECTEURS["prix"])
        prix = extraction.prix(el_prix.get_text() if el_prix else "") \
            or extraction.entier(el_prix.get_text() if el_prix else None)

        texte_attributs = " ".join(
            e.get_text(" ", strip=True) for e in carte.select(SELECTEURS["attributs"])
        )
        contexte = f"{texte_attributs} {titre}"
        annee = extraction.annee(contexte)
        km = extraction.kilometrage(texte_attributs)
        code_postal = extraction.code_postal(texte_attributs,
                                             exclure=(prix, km, annee))
        if not zone_mod.dans_zone(code_postal, departements, garder_si_inconnu):
            continue

        if profilage.choisir(titre, [profil], annee) is None:
            continue

        el_photo = carte.select_one(SELECTEURS["photo"])
        photo = el_photo.get("src") or el_photo.get("data-src") if el_photo else None

        annonces.append({
            "id": "lc_" + hashlib.sha1(url_annonce.encode()).hexdigest()[:16],
            "source": "lacentrale",
            "profil": profil["id"],
            "titre": titre,
            "prix": prix,
            "annee": annee,
            "km": km,
            "carburant": _carburant(titre),
            "etat": etat,
            "panne": panne,
            "cout_min": cout_min,
            "cout_max": cout_max,
            "drapeaux": ";".join(drapeaux),
            "boite": None,
            "code_postal": code_postal,
            "departement": zone_mod.departement(code_postal),
            "url": url_annonce,
            "photo": photo,
            "vu_le": maintenant,
            "revu_le": maintenant,
        })
    return annonces
