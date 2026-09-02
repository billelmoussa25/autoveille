"""Stockage local des annonces. SQLite = une base de donnees contenue dans
un seul fichier, sans serveur a installer."""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "data/annonces.sqlite3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS annonces (
    id            TEXT PRIMARY KEY,   -- empreinte source + identifiant
    source        TEXT NOT NULL,
    profil        TEXT NOT NULL,
    titre         TEXT,
    prix          INTEGER,
    annee         INTEGER,
    km            INTEGER,
    carburant     TEXT,
    boite         TEXT,
    code_postal   TEXT,
    departement   TEXT,
    url           TEXT NOT NULL,
    photo         TEXT,
    vu_le         TEXT NOT NULL,      -- premiere fois qu'on la voit
    revu_le       TEXT NOT NULL,      -- derniere fois qu'on la voit
    prix_median   INTEGER,            -- reference calculee au moment du scoring
    comparables   INTEGER,
    ecart         REAL,               -- ex. 0.15 = 15 % sous le median
    notifiee      INTEGER NOT NULL DEFAULT 0,
    etat          TEXT DEFAULT 'sain',   -- 'sain' ou 'reparer'
    panne         TEXT,
    cout_min      INTEGER,
    cout_max      INTEGER,
    drapeaux      TEXT,                  -- mentions bloquantes, separees par ';'
    marge         INTEGER                -- marge estimee si etat = 'reparer'
);
CREATE INDEX IF NOT EXISTS idx_profil ON annonces(profil);
CREATE INDEX IF NOT EXISTS idx_ecart  ON annonces(ecart);
CREATE INDEX IF NOT EXISTS idx_etat   ON annonces(etat);
"""

# Colonnes ajoutees apres coup : appliquees aux bases deja existantes.
MIGRATIONS = [
    "ALTER TABLE annonces ADD COLUMN etat TEXT DEFAULT 'sain'",
    "ALTER TABLE annonces ADD COLUMN panne TEXT",
    "ALTER TABLE annonces ADD COLUMN cout_min INTEGER",
    "ALTER TABLE annonces ADD COLUMN cout_max INTEGER",
    "ALTER TABLE annonces ADD COLUMN drapeaux TEXT",
    "ALTER TABLE annonces ADD COLUMN marge INTEGER",
    "ALTER TABLE annonces ADD COLUMN departement TEXT",
]


def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with connexion() as cx:
        cx.executescript(SCHEMA)
        for requete in MIGRATIONS:
            try:
                cx.execute(requete)
            except sqlite3.OperationalError:
                pass  # colonne deja presente


@contextmanager
def connexion():
    cx = sqlite3.connect(DB_PATH, timeout=30)
    cx.row_factory = sqlite3.Row
    try:
        yield cx
        cx.commit()
    finally:
        cx.close()


def enregistrer(annonce):
    """Insere l'annonce, ou met a jour sa date de derniere vue si on la
    connait deja. Renvoie True si c'est une nouveaute."""
    with connexion() as cx:
        existe = cx.execute(
            "SELECT 1 FROM annonces WHERE id = ?", (annonce["id"],)
        ).fetchone()
        if existe:
            cx.execute(
                "UPDATE annonces SET revu_le = ?, prix = ? WHERE id = ?",
                (annonce["revu_le"], annonce.get("prix"), annonce["id"]),
            )
            return False
        colonnes = ", ".join(annonce.keys())
        marques = ", ".join("?" for _ in annonce)
        cx.execute(
            f"INSERT INTO annonces ({colonnes}) VALUES ({marques})",
            tuple(annonce.values()),
        )
        return True


def comparables(profil, annee, km, carburant=None,
                tolerance_annee=2, tolerance_km=30000):
    """Annonces deja vues du meme profil, d'annee et de kilometrage proches.

    Le carburant est pris en compte quand il est connu : un diesel et une
    essence du meme modele ne se negocient pas au meme prix."""
    if annee is None or km is None:
        return []
    requete = """
        SELECT prix FROM annonces
        WHERE profil = ? AND prix IS NOT NULL AND prix > 0
          AND etat = 'sain'
          AND annee BETWEEN ? AND ?
          AND km    BETWEEN ? AND ?
    """
    params = [profil, annee - tolerance_annee, annee + tolerance_annee,
              max(0, km - tolerance_km), km + tolerance_km]
    if carburant:
        requete += " AND carburant = ?"
        params.append(carburant)
    with connexion() as cx:
        lignes = cx.execute(requete, tuple(params)).fetchall()
    return [l["prix"] for l in lignes]


def maj_score(annonce_id, prix_median, nb_comparables, ecart, marge=None):
    with connexion() as cx:
        cx.execute(
            "UPDATE annonces SET prix_median = ?, comparables = ?, ecart = ?, "
            "marge = ? WHERE id = ?",
            (prix_median, nb_comparables, ecart, marge, annonce_id),
        )


def marquer_notifiee(annonce_id):
    with connexion() as cx:
        cx.execute("UPDATE annonces SET notifiee = 1 WHERE id = ?", (annonce_id,))


def a_notifier(etat, limite=25):
    """Annonces de l'etat demande, deja evaluees et jamais notifiees."""
    with connexion() as cx:
        return [dict(l) for l in cx.execute(
            """
            SELECT * FROM annonces
            WHERE notifiee = 0 AND etat = ?
              AND (ecart IS NOT NULL OR marge IS NOT NULL OR prix IS NOT NULL)
            ORDER BY vu_le DESC LIMIT ?
            """,
            (etat, limite),
        ).fetchall()]


def lister(profil=None, seulement_bonnes=False, etat=None, limite=300):
    conditions, params = [], []
    if profil:
        conditions.append("profil = ?")
        params.append(profil)
    if etat:
        conditions.append("etat = ?")
        params.append(etat)
    if seulement_bonnes:
        conditions.append(
            "(ecart IS NOT NULL AND ecart >= 0.10) OR (marge IS NOT NULL AND marge > 0)")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with connexion() as cx:
        return cx.execute(
            f"SELECT * FROM annonces {where} ORDER BY vu_le DESC LIMIT ?",
            (*params, limite),
        ).fetchall()
