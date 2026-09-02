"""Interface web : tableau de suivi des annonces collectees."""

import hashlib
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from . import db, etat as etat_mod, profilage, scoring, zone
from .estimation import estimer
from .config import charger

app = Flask(__name__)


@app.template_filter("euros")
def euros(valeur):
    if valeur is None:
        return "—"
    return f"{valeur:,}".replace(",", " ") + " €"


@app.template_filter("kilometres")
def kilometres(valeur):
    if valeur is None:
        return "—"
    return f"{valeur:,}".replace(",", " ") + " km"


@app.route("/ingest", methods=["POST"])
def ingest():
    """Recoit les annonces lues par le navigateur de l'utilisateur.

    Aucune requete n'est emise vers un site d'annonces : c'est le navigateur
    de l'utilisateur, sur sa propre session, qui envoie ce qu'il a deja
    affiche a l'ecran.
    """
    jeton_attendu = os.environ.get("INGEST_TOKEN")
    if jeton_attendu and request.headers.get("X-Jeton") != jeton_attendu:
        return jsonify({"erreur": "jeton invalide"}), 403

    db.init()
    conf = charger()
    general, profils = conf["general"], conf["profils"]
    reparation = conf.get("reparation", {})
    pannes = reparation.get("pannes", {})
    reglages_zone = conf.get("zone", {})
    departements = zone.resoudre(reglages_zone.get("departements"))
    garder = reglages_zone.get("garder_si_inconnu", True)
    plafond = conf.get("alertes_hs", {}).get("prix_coup_de_filet")

    recues = request.get_json(silent=True) or []
    maintenant = datetime.now(timezone.utc).isoformat()
    nouvelles = hors_zone = hors_profil = 0

    for brute in recues:
        titre = (brute.get("titre") or "").strip()
        url = (brute.get("url") or "").strip()
        if not titre or not url:
            continue

        profil = profilage.choisir(titre, profils, brute.get("annee"))
        if profil is None:
            hors_profil += 1
            continue

        code_postal = brute.get("code_postal")
        if not zone.dans_zone(code_postal, departements, garder):
            hors_zone += 1
            continue

        etat, panne, cout_min, cout_max, drapeaux = etat_mod.analyser(
            titre, brute.get("description"), pannes)

        prix = brute.get("prix")
        if plafond and prix and 0 < prix <= plafond and etat != "reparer":
            etat, panne = "reparer", panne or "indetermine"

        annonce = {
            "id": "nav_" + hashlib.sha1(url.encode()).hexdigest()[:16],
            "source": brute.get("source") or "navigateur",
            "profil": profil["id"], "titre": titre, "prix": prix,
            "annee": brute.get("annee"), "km": brute.get("km"),
            "carburant": brute.get("carburant"), "boite": brute.get("boite"),
            "code_postal": code_postal,
            "departement": zone.departement(code_postal),
            "url": url, "photo": brute.get("photo"),
            "vu_le": maintenant, "revu_le": maintenant,
            "etat": etat, "panne": panne, "cout_min": cout_min,
            "cout_max": cout_max, "drapeaux": ";".join(drapeaux),
        }
        if not db.enregistrer(annonce):
            continue
        nouvelles += 1
        median, nb, ecart, marge = scoring.evaluer(annonce, general, reparation)
        db.maj_score(annonce["id"], median, nb, ecart, marge)

    return jsonify({"recues": len(recues), "nouvelles": nouvelles,
                    "hors_zone": hors_zone, "hors_profil": hors_profil})


@app.route("/estimer")
def page_estimer():
    db.init()
    conf = charger()
    saisie = (request.args.get("q") or "").strip()
    resultat = estimer(saisie, conf) if saisie else None
    return render_template("estimer.html", saisie=saisie, resultat=resultat,
                           profils=conf["profils"])


@app.route("/")
def index():
    db.init()
    conf = charger()
    profils = conf["profils"]
    seuil = conf["general"].get("seuil_alerte", 0.12)
    marge_min = conf.get("reparation", {}).get("marge_minimum", 1200)

    profil_actif = request.args.get("profil") or None
    bonnes_seulement = request.args.get("bonnes") == "1"
    etat_actif = request.args.get("etat") or None
    dep_actif = request.args.get("dep") or None

    annonces = db.lister(profil=profil_actif, seulement_bonnes=bonnes_seulement,
                         etat=etat_actif)
    if dep_actif:
        annonces = [a for a in annonces if a["departement"] == dep_actif]
    departements = sorted(zone.resoudre(conf.get("zone", {}).get("departements")))
    nb_bonnes = sum(1 for a in annonces if (a["ecart"] or 0) >= seuil)
    nb_marge = sum(1 for a in annonces
                   if a["etat"] == "reparer" and (a["marge"] or 0) >= marge_min)

    return render_template(
        "index.html",
        annonces=annonces,
        profils=profils,
        profil_actif=profil_actif,
        bonnes_seulement=bonnes_seulement,
        seuil=seuil,
        marge_min=marge_min,
        nb_bonnes=nb_bonnes,
        nb_marge=nb_marge,
        etat_actif=etat_actif,
        dep_actif=dep_actif,
        departements=departements,
        libelles={p["id"]: p.get("libelle", p["id"]) for p in profils},
    )
