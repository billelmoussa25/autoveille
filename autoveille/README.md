# Veille annonces auto

Conteneur qui surveille les annonces de voitures, calcule si le prix est
anormalement bas par rapport au marché, et envoie une notification Telegram
avec le lien. Une interface web permet de reparcourir tout l'historique.

## Ce que ça fait

1. Toutes les 25 minutes, le collecteur récupère les annonces correspondant
   aux profils définis dans `config.yml`.
2. Chaque annonce est stockée, y compris les mauvaises : elles servent à
   construire le prix de référence.
3. Pour une annonce donnée, le programme prend toutes les annonces déjà vues
   du même profil, avec une année à ±2 ans et un kilométrage à ±30 000 km,
   et en calcule le prix médian.
4. Si l'annonce est au moins 12 % sous ce médian, tu reçois la notification.
5. L'interface web sur `http://localhost:8080` liste tout, filtrable par
   profil, avec la position de chaque annonce par rapport à son marché.

## Les véhicules à réparer

Une voiture HS n'est pas sous le marché parce que c'est une affaire, mais
parce qu'elle est cassée. Elle a donc son propre calcul.

Le collecteur repère les mentions de panne dans l'annonce (« embrayage HS »,
« joint de culasse », « ne démarre pas », « CT refusé »…) et leur associe une
fourchette de coût définie dans `config.yml`. La valeur de revente vient des
annonces saines déjà collectées pour le même profil, la même année et le même
kilométrage, moins une décote de 12 % parce qu'un véhicule remis en route se
vend un peu moins bien.

    marge = (prix médian des saines × 0,88) − prix demandé − coût de réparation haut

L'alerte part si la marge dépasse `marge_minimum` (1 200 € par défaut). Le
coût retenu est le haut de la fourchette : c'est celui qui compte au moment de
décider.

Trois mentions coupent la notification, parce qu'elles bloquent la revente :
véhicule gagé (opposition sur la carte grise), procédure VGE/VEI (véhicule
immobilisé administrativement tant qu'un expert n'a pas validé la réparation),
et absence de carte grise. Ces annonces restent visibles dans l'interface avec
leur avertissement, mais ne te réveillent pas la nuit.

Les vrais chiffres à mettre à jour sont les fourchettes de coût dans la
section `reparation.pannes`. Ce sont elles qui décident si l'affaire tient, et
les miennes sont des valeurs de départ génériques.

## Les deux sources

**La Centrale** — collecte directe des pages de résultats. Le module lit
`robots.txt` avant chaque requête et respecte une pause de 12 secondes. À
savoir : les conditions générales du site interdisent la collecte
automatisée, et rien ici ne contourne une protection anti-robot. Si le site
renvoie un code 403 ou 429, c'est qu'il bloque — espace les passages ou
désactive la source dans `config.yml`.

**Leboncoin** — par ses propres mails d'alerte, pas par le site. Tu crées tes
recherches sauvegardées sur leboncoin, tu actives l'alerte mail, et le
collecteur lit ta boîte en IMAP pour en extraire les annonces. C'est la seule
voie automatique propre : aucun accès au site, donc rien qui puisse être
bloqué, et ça ne casse pas quand leboncoin refait son interface.

**En complément, facultatif** — un script navigateur
(`navigateur/leboncoin-capture.user.js`) capture aussi les annonces que tu
croises en naviguant toi-même sur le site.

## Estimer une voiture à la demande

La base de prix accumulée est interrogeable, depuis Telegram ou depuis
`/estimer` dans l'interface web :

    clio 4 2014 130000 4200
    golf 2011 210000 2900 embrayage hs

Même référence que les alertes : le prix médian des annonces saines
comparables. Pratique quand tu es devant une annonce sur ton téléphone.

## La zone géographique

Dans `config.yml`, section `zone` :

```yaml
zone:
  departements: ["idf", "60", "27"]
  garder_si_inconnu: true
```

Tu peux mélanger librement des noms de région et des numéros de département.
Régions reconnues : `idf`, `hauts_de_france`, `grand_est`, `normandie`,
`bretagne`, `pays_de_la_loire`, `centre_val_de_loire`,
`bourgogne_franche_comte`, `nouvelle_aquitaine`, `occitanie`,
`auvergne_rhone_alpes`, `paca`, `corse`. Une liste vide ne filtre rien.

`garder_si_inconnu: true` conserve les annonces dont le code postal n'est pas
lisible. Ça fait un peu de bruit, mais ça évite de rater une affaire à cause
d'un vendeur qui n'a pas rempli sa localisation. Mets `false` si tu préfères
le silence.

L'interface web propose en plus un filtre par département, pour restreindre
l'affichage sans toucher à la collecte.

## Démarrage

Guide complet dans **INSTALL.md** (création du LXC Proxmox, Docker, bot
Telegram, alertes mail). En résumé :

```bash
cp .env.example .env      # puis remplir le jeton Telegram et les accès mail
docker compose up -d --build
docker compose logs -f collecteur
```

Pour le jeton Telegram : écris à @BotFather dans l'application, commande
`/newbot`, il te renvoie le jeton. Envoie ensuite un message à ton bot et
ouvre `https://api.telegram.org/bot<TON_JETON>/getUpdates` pour lire
l'identifiant de conversation.

## À ajuster avant que ça serve

- **`config.yml`** : les `prix_max` et `km_max` sont des valeurs par défaut,
  mets les tiennes. `code_postal` et `rayon_km` aussi.
- **`app/sources/lacentrale.py`** : le dictionnaire `SELECTEURS` en haut du
  fichier contient les sélecteurs CSS de la page de résultats. Ils sont à
  vérifier sur le code source réel de la page — c'est le seul bloc à
  maintenir dans le temps. Si les logs affichent « aucune carte trouvée »,
  c'est là qu'il faut regarder.
- **`reparation.pannes`** : remplace mes fourchettes par tes coûts réels.
- **Le seuil** : `seuil_alerte: 0.12` est un point de départ. Trop bas, tu es
  noyé ; trop haut, tu ne reçois plus rien.

## Deux réserves

Le premier mois, la base est trop maigre pour que le prix de référence soit
fiable. Le programme s'en protège avec `comparables_minimum: 8` : en dessous
de 8 annonces similaires, il stocke sans se prononcer. Laisse-le tourner
avant de faire confiance aux alertes.

Un prix nettement sous le marché cache souvent quelque chose : véhicule
accidenté, compteur trafiqué, annonce d'appât. Le score fait gagner du temps
de tri, il ne remplace pas la vérification (historique, contrôle technique,
essai).

## Structure

```
docker-compose.yml        quatre services : collecteur, deux alerteurs, web
config.yml                profils de recherche et seuils
app/collecteur.py         collecte, stockage, calcul des scores
app/alerteur.py           notifications, une instance par categorie
app/zone.py               filtrage par region et departement
app/etat.py               detection HS, panne, mentions bloquantes
app/scoring.py            prix médian et écart
app/notify.py             envoi Telegram
app/web.py                interface web
app/db.py                 stockage SQLite
app/sources/lacentrale.py        collecte La Centrale
app/sources/mails_leboncoin.py   lecture des alertes mail leboncoin
```
