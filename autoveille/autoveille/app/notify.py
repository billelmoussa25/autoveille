"""Envoi des alertes Telegram."""

import os

import requests

API = "https://api.telegram.org/bot{token}/sendMessage"


def _echapper(texte):
    return (texte or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


AVERTISSEMENTS = {
    "gage": "vehicule gage, carte grise non transferable en l'etat",
    "procedure_vge": "procedure VGE/VEI en cours, expertise obligatoire avant remise en route",
    "sans_papiers": "pas de carte grise annoncee",
    "pour_pieces": "annonce pour pieces, reimmatriculation a verifier",
}


def envoyer(annonce, prix_median, ecart, marge, libelle_profil,
            conversation=None):
    token = os.environ.get("TELEGRAM_TOKEN")
    conversation = conversation or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not conversation:
        print("[telegram] jeton ou identifiant de conversation absent")
        return False

    km = f"{annonce['km']:,} km".replace(",", " ") if annonce.get("km") else "km inconnu"
    annee = annonce.get("annee") or "annee inconnue"
    prix = f"{annonce['prix']:,} €".replace(",", " ")
    median = f"{prix_median:,} €".replace(",", " ") if prix_median else "inconnue"
    lieu = f" — {annonce['code_postal']}" if annonce.get("code_postal") else ""

    if annonce.get("etat") == "reparer":
        cout = ""
        if annonce.get("cout_min") and annonce.get("cout_max"):
            cout = f"{annonce['cout_min']}–{annonce['cout_max']} €"
        panne = (annonce.get("panne") or "panne non precisee").replace("_", " ")
        lignes = [
            f"🔧 <b>{_echapper(annonce.get('titre'))}</b>",
            f"{prix} — {annee} — {km}{lieu}",
            f"Panne annoncee : {panne}" + (f" (repa. {cout})" if cout else ""),
        ]
        if marge is not None:
            lignes.append(
                f"Revente estimee : {median} — <b>marge ~{marge:,} €</b>".replace(",", " "))
        else:
            lignes.append("<b>Prix tres bas</b> — marge non calculable, "
                          "pas encore assez de references")
        for drapeau in filter(None, (annonce.get("drapeaux") or "").split(";")):
            if drapeau in AVERTISSEMENTS:
                lignes.append(f"⚠️ {AVERTISSEMENTS[drapeau]}")
        lignes += [f"Source : {annonce['source']}", annonce["url"]]
        texte = "\n".join(lignes)
    else:
        texte = (
            f"<b>{_echapper(annonce.get('titre'))}</b>\n"
            f"{prix} — {annee} — {km}{lieu}\n"
            f"Reference du marche : {median} "
            f"(<b>{round(ecart * 100)} % en dessous</b>, {libelle_profil})\n"
            f"Source : {annonce['source']}\n"
            f"{annonce['url']}"
        )

    try:
        r = requests.post(
            API.format(token=token),
            json={
                "chat_id": conversation,
                "text": texte,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        return r.ok
    except requests.RequestException as e:
        print(f"[telegram] envoi echoue : {e}")
        return False
