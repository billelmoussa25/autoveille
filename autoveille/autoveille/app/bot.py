"""Bot Telegram a l'ecoute : tu lui envoies une voiture, il te repond.

N'interroge que api.telegram.org. Aucune requete vers un site d'annonces.
"""

import os
import time
import traceback

import requests

from . import db
from .config import charger
from .estimation import AIDE, en_texte, estimer

API = "https://api.telegram.org/bot{token}/{methode}"


def _appeler(methode, **donnees):
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_TOKEN absent")
    r = requests.post(API.format(token=token, methode=methode),
                      json=donnees, timeout=70)
    return r.json()


def _repondre(conversation, texte):
    _appeler("sendMessage", chat_id=conversation, text=texte,
             parse_mode="HTML", disable_web_page_preview=True)


def _resume(conf):
    seuil = conf.get("alertes_saines", {}).get("seuil_alerte", 0.12)
    marge_min = conf.get("alertes_hs", {}).get("marge_minimum", 1200)
    toutes = db.lister(limite=5000)
    saines = [a for a in toutes if a["etat"] == "sain"]
    hs = [a for a in toutes if a["etat"] == "reparer"]
    bonnes = sum(1 for a in saines if (a["ecart"] or 0) >= seuil)
    marges = sum(1 for a in hs if (a["marge"] or 0) >= marge_min)
    return (f"<b>Base actuelle</b>\n"
            f"{len(saines)} annonces roulantes, dont {bonnes} sous le marche\n"
            f"{len(hs)} a reparer, dont {marges} avec une marge interessante")


def traiter(message, conf):
    conversation = message["chat"]["id"]
    texte = (message.get("text") or "").strip()
    if not texte:
        return

    if texte.startswith("/start") or texte.startswith("/aide") or texte.startswith("/help"):
        _repondre(conversation, AIDE)
        return
    if texte.startswith("/base") or texte.startswith("/resume"):
        _repondre(conversation, _resume(conf))
        return
    if texte.startswith("/"):
        _repondre(conversation, AIDE)
        return

    _repondre(conversation, en_texte(estimer(texte, conf)))


def main():
    db.init()
    print("bot demarre, en attente de messages")
    decalage = None
    while True:
        try:
            reponse = _appeler("getUpdates", offset=decalage, timeout=60)
            conf = charger()
            for maj in reponse.get("result", []):
                decalage = maj["update_id"] + 1
                message = maj.get("message") or maj.get("edited_message")
                if message:
                    try:
                        traiter(message, conf)
                    except Exception:
                        traceback.print_exc()
        except requests.RequestException:
            time.sleep(5)
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
