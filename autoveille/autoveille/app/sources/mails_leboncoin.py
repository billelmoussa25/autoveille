"""Collecte leboncoin par ses propres mails d'alerte.

Principe : tu crees tes recherches sauvegardees directement sur leboncoin et
tu actives l'alerte mail. Ce module se connecte a ta boite en IMAP (le
protocole standard de lecture de courrier), lit les mails d'alerte non lus et
en extrait les annonces.

Aucun acces automatise au site : rien a contourner, et ca ne casse pas quand
leboncoin change son interface. C'est la seule voie automatique propre vers
leboncoin.
"""

import email
import hashlib
import imaplib
import os
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from .. import extraction
from .. import etat as etat_mod
from .. import profilage
from .. import zone as zone_mod

LIEN_ANNONCE = re.compile(r"https?://(?:www\.)?leboncoin\.fr/[^\s\"'<>]*?/(\d{6,})")

CARBURANTS = {
    "diesel":  ["dci", "hdi", "tdci", "tdi", "cdti", "diesel", "d-4d", "bluehdi"],
    "essence": ["tce", "vti", "tsi", "essence", "16v", "vvt-i", "sce", "thp", "fsi"],
}


def _carburant(titre):
    t = (titre or "").lower()
    for nom, motifs in CARBURANTS.items():
        if any(m in t for m in motifs):
            return nom
    return None


def _texte(partie):
    charset = partie.get_content_charset() or "utf-8"
    try:
        return partie.get_payload(decode=True).decode(charset, "replace")
    except Exception:
        return ""


def _corps_html(message):
    if message.is_multipart():
        for partie in message.walk():
            if partie.get_content_type() == "text/html":
                return _texte(partie)
        for partie in message.walk():
            if partie.get_content_type() == "text/plain":
                return _texte(partie)
        return ""
    return _texte(message)


def collecter(profils, reglages, catalogue_pannes=None,
              departements=None, garder_si_inconnu=True):
    hote = os.environ.get("IMAP_HOST")
    utilisateur = os.environ.get("IMAP_USER")
    motdepasse = os.environ.get("IMAP_PASSWORD")
    dossier = os.environ.get("IMAP_FOLDER", "INBOX")

    if not all([hote, utilisateur, motdepasse]):
        print("[mails] identifiants IMAP absents — source ignoree")
        return []

    try:
        boite = imaplib.IMAP4_SSL(hote)
        boite.login(utilisateur, motdepasse)
        boite.select(dossier)
    except Exception as e:
        print(f"[mails] connexion impossible : {e}")
        return []

    expediteur = reglages.get("expediteur", "leboncoin.fr")
    statut, donnees = boite.search(None, f'(UNSEEN FROM "{expediteur}")')
    if statut != "OK":
        boite.logout()
        return []

    identifiants = donnees[0].split()
    departements = departements or set()
    maintenant = datetime.now(timezone.utc).isoformat()
    annonces = []
    vues = set()

    for identifiant in identifiants:
        statut, brut = boite.fetch(identifiant, "(RFC822)")
        if statut != "OK":
            continue
        message = email.message_from_bytes(brut[0][1])
        soup = BeautifulSoup(_corps_html(message), "lxml")

        for lien in soup.find_all("a", href=True):
            m = LIEN_ANNONCE.search(lien["href"])
            if not m:
                continue
            reference = m.group(1)
            if reference in vues:
                continue
            vues.add(reference)

            url = m.group(0)
            bloc = lien.find_parent(["td", "tr", "div"]) or lien
            texte = bloc.get_text(" ", strip=True)
            titre = lien.get_text(" ", strip=True) or texte[:120]

            annee = extraction.annee(texte)

            profil = profilage.choisir(titre, profils, annee)
            if profil is None:
                continue

            prix = extraction.prix(texte)
            km = extraction.kilometrage(texte)
            code_postal = extraction.code_postal(texte, exclure=(prix, km, annee))

            if not zone_mod.dans_zone(code_postal, departements, garder_si_inconnu):
                continue

            etat, panne, cout_min, cout_max, drapeaux = etat_mod.analyser(
                titre, texte, catalogue_pannes)

            photo = None
            img = bloc.find("img")
            if img and img.get("src", "").startswith("http"):
                photo = img["src"]

            annonces.append({
                "id": "lbc_" + hashlib.sha1(reference.encode()).hexdigest()[:16],
                "source": "leboncoin",
                "profil": profil["id"],
                "titre": titre,
                "prix": prix,
                "annee": annee,
                "km": km,
                "carburant": _carburant(titre),
                "boite": None,
                "code_postal": code_postal,
                "departement": zone_mod.departement(code_postal),
                "url": url,
                "photo": photo,
                "vu_le": maintenant,
                "revu_le": maintenant,
                "etat": etat,
                "panne": panne,
                "cout_min": cout_min,
                "cout_max": cout_max,
                "drapeaux": ";".join(drapeaux),
            })

    boite.logout()
    print(f"[mails] {len(identifiants)} mail(s) lu(s), {len(annonces)} annonce(s) retenue(s)")
    return annonces
