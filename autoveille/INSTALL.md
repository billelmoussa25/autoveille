# Installation pas à pas

## 1. Le conteneur LXC

### Dimensionnement

| Ressource | Valeur | Pourquoi |
|---|---|---|
| vCPU | 2 | 1 suffirait à l'exécution, mais la construction de l'image Docker est bien plus rapide à 2 |
| RAM | 2 Go | ~250 Mo réellement utilisés par les 4 processus. Le reste sert au cache disque et à la construction de l'image |
| Disque | 12 Go | images Docker ~400 Mo, système ~1,5 Go. La base grossit lentement : compte quelques dizaines de Mo par an |
| Swap | 512 Mo | filet de sécurité, ne servira pas |
| Template | Debian 12 | |

Tu peux descendre à 1 vCPU / 1 Go une fois que ça tourne. En dessous, la
construction de l'image risque de se faire tuer par manque de mémoire.

### Création depuis le nœud Proxmox

```bash
pct create 120 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname autoveille \
  --cores 2 --memory 2048 --swap 512 \
  --rootfs local-lvm:12 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1,keyctl=1 \
  --onboot 1 \
  --start 1
```

Remplace `120` par un identifiant libre, `local-lvm` par ton stockage, et le
nom du template par celui que tu as (`pveam available | grep debian-12` pour
la liste, `pveam download local <nom>` pour le récupérer).

`nesting=1` autorise l'imbrication de conteneurs, `keyctl=1` donne accès au
trousseau du noyau. Sans ces deux options, le démon Docker refuse de démarrer
dans un LXC non privilégié. C'est l'erreur la plus fréquente sur cette étape.

Si tu passes par l'interface web plutôt que la ligne de commande : onglet
**Options → Features**, coche *Nesting* et *keyctl*.

### Cas particulier : stockage ZFS

Si le disque du conteneur est sur ZFS, Docker ne peut pas utiliser son pilote
`overlay2` habituel. Ajoute dans `/etc/pve/lxc/120.conf` sur le nœud :

```
features: nesting=1,keyctl=1,fuse=1
```

Puis, dans le conteneur, installe `fuse-overlayfs` et déclare-le à Docker :

```bash
apt install -y fuse-overlayfs
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{ "storage-driver": "fuse-overlayfs" }
EOF
```

Sur du LVM ou de l'ext4 classique, rien à faire.

## 2. Docker dans le conteneur

Entre dedans depuis le nœud : `pct enter 120`

```bash
apt update && apt install -y ca-certificates curl gnupg git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Vérifie que ça tourne avant d'aller plus loin :

```bash
docker run --rm hello-world
```

Si cette commande échoue, le problème est dans les features du LXC, pas dans
le projet. Reprends l'étape 1.

## 3. Le projet

```bash
mkdir -p /opt/autoveille && cd /opt/autoveille
# décompresse l'archive ici, ou clone ton dépôt
cp .env.example .env
```

## 4. Le bot Telegram

1. Dans l'application Telegram, écris à **@BotFather**, commande `/newbot`.
   Donne un nom et un identifiant se terminant par `bot`. Il te renvoie un
   jeton du type `8123456789:AAH...`.
2. Envoie n'importe quel message à ton nouveau bot — sans ça il ne peut pas
   t'écrire.
3. Récupère ton identifiant de conversation en ouvrant dans un navigateur :
   `https://api.telegram.org/bot<TON_JETON>/getUpdates`
   Cherche `"chat":{"id":123456789` dans la réponse.

Si tu veux séparer les deux flux, crée deux groupes Telegram, ajoute le bot
dans chacun, et relance `getUpdates` : les identifiants de groupe sont
négatifs, du type `-1001234567890`.

Remplis `.env` :

```
TELEGRAM_TOKEN=8123456789:AAH...
TELEGRAM_CHAT_ID_SAINES=123456789
TELEGRAM_CHAT_ID_HS=123456789
```

Les deux peuvent pointer au même endroit si tu préfères tout recevoir
ensemble.

## 5. Les alertes leboncoin

C'est la voie automatique vers leboncoin, et la seule qui soit propre : le
programme ne touche jamais au site, il lit les mails que leboncoin t'envoie.

**Côté site**, une fois par recherche :

1. Fais ta recherche sur leboncoin avec tes critères.
2. Enregistre-la et active l'alerte par mail en fréquence **immédiate**.

**Côté conteneur**, il faut un accès en lecture à la boîte. Avec Gmail, un mot
de passe normal est refusé : active la validation en deux étapes sur le
compte, puis génère un **mot de passe d'application** de 16 caractères dans
les paramètres de sécurité Google. C'est cette chaîne qui va dans `.env`.

```
IMAP_HOST=imap.gmail.com
IMAP_USER=ton.adresse@gmail.com
IMAP_PASSWORD=xxxxxxxxxxxxxxxx
IMAP_FOLDER=INBOX
```

Utilise une adresse dédiée. Le programme marque les mails comme lus au
passage, ce qui salit vite une boîte personnelle.

### En complément : le script navigateur (facultatif)

Les mails ne contiennent que les nouvelles annonces. Si tu veux aussi capturer
ce que tu vois en naviguant, un script utilisateur le fait — sur ta propre
session, sans aucune requête automatique.

1. Renseigne `INGEST_TOKEN` dans `.env` (invente une chaîne).
2. Installe **Tampermonkey** (Chrome, Firefox, Edge) ou **Userscripts** (Safari
   iOS).
3. Ouvre `navigateur/leboncoin-capture.user.js` et règle les deux lignes du
   haut : `SERVEUR` avec l'adresse de ton LXC, `JETON` avec la même chaîne que
   `INGEST_TOKEN` dans `.env`.
4. Colle le script dans une nouvelle entrée Tampermonkey, enregistre.
5. Fais ta recherche sur leboncoin comme d'habitude et scrolle. Une pastille
   noire en bas à droite te confirme ce qui part vers le serveur.

Le script lit en priorité le bloc JSON `__NEXT_DATA__` que leboncoin embarque
dans ses pages : c'est bien plus stable que de lire la mise en page. Il a un
repli sur le HTML affiché si cette structure change.

Purement optionnel : les alertes mail tournent sans toi, le script n'ajoute
que ce que tu croises en naviguant.

## 6. La configuration

Ouvre `config.yml` et règle au minimum :

- `zone.departements` — ta zone de recherche
- les `prix_max` et `km_max` de chaque profil
- `reparation.pannes` — tes coûts réels de remise en route
- `alertes_saines.seuil_alerte` et `alertes_hs.marge_minimum`

## 7. Premier lancement

```bash
cd /opt/autoveille
docker compose up -d --build
docker compose logs -f collecteur
```

La construction prend 2 à 3 minutes la première fois. Tu dois voir apparaître
une ligne du type :

```
collecte terminee : 0 annonces dans la zone [27, 60, 75, ...], 0 nouvelles
```

L'interface est sur `http://<ip-du-lxc>:8080`.

## 8. Faire fonctionner La Centrale

C'est l'étape qui demande du travail manuel, et elle est inévitable : les
sélecteurs CSS que j'ai mis sont des suppositions.

Si les logs affichent `aucune carte trouvee : les selecteurs CSS sont
probablement obsoletes` :

1. Ouvre une page de résultats La Centrale dans ton navigateur.
2. Clic droit sur une annonce → Inspecter.
3. Relève le nom de la classe du bloc qui entoure une annonce entière, celui
   du titre, celui du prix.
4. Reporte-les dans le dictionnaire `SELECTEURS`, en haut de
   `app/sources/lacentrale.py`.
5. `docker compose up -d --build collecteur`

Si tu vois plutôt `bloque (code 403)`, le site refuse les requêtes. Augmente
`sources.lacentrale.pause_secondes`, allonge `general.intervalle_minutes`, ou
mets cette source à `actif: false` et travaille uniquement sur les alertes
mail leboncoin. Ne cherche pas à contourner : c'est ce qui transforme un outil
de veille en problème.

## 9. Vérifier que les alertes partent

Les alerteurs ne diront rien tant que la base n'a pas assez de références —
c'est voulu. Pour tester le canal Telegram tout de suite :

```bash
docker compose exec alertes-hs python -c "
from app.notify import envoyer
import os
envoyer({'titre':'Test','prix':2000,'annee':2014,'km':130000,'url':'https://exemple.fr',
         'source':'test','etat':'reparer','panne':'embrayage','cout_min':450,
         'cout_max':1100,'drapeaux':'','code_postal':'95100'},
        5500, None, 1500, 'Test',
        conversation=os.environ.get('TELEGRAM_CHAT_ID_HS'))
"
```

Tu dois recevoir le message dans les secondes qui suivent.

## 10. Entretien

**Sauvegarde.** Tout l'historique est dans le volume Docker `data`. C'est lui
qui a de la valeur : les prix accumulés ne se reconstituent pas.

```bash
docker run --rm -v autoveille_data:/data -v /root:/sauvegarde alpine \
  tar czf /sauvegarde/autoveille-$(date +%F).tar.gz -C /data .
```

Ajoute une sauvegarde Proxmox du LXC en plus, ça couvre tout.

**Logs.** `docker compose logs --tail 50 collecteur` pour le dernier passage,
`docker compose logs -f alertes-hs` pour suivre les notifications.

**Modifier la configuration.** `config.yml` est relu à chaque passage, pas
besoin de reconstruire. Un `docker compose restart` suffit pour appliquer
immédiatement. Seul un changement de code demande `--build`.

## Repères de dépannage

| Symptôme | Piste |
|---|---|
| `docker run hello-world` échoue | features `nesting` et `keyctl` absentes du LXC |
| Docker démarre mais les images ne se construisent pas, stockage ZFS | passer sur `fuse-overlayfs`, étape 1 |
| `aucune carte trouvee` | sélecteurs CSS à corriger, étape 8 |
| `bloque (code 403)` | ralentir ou désactiver la source |
| `identifiants IMAP absents` | `.env` incomplet, ou `env_file` non pris en compte : `docker compose config` pour vérifier |
| Le script navigateur affiche « serveur injoignable » | mauvaise adresse dans `SERVEUR`, ou le LXC n'est pas joignable depuis ton poste |
| Le script renvoie 403 | `JETON` du script différent de `INGEST_TOKEN` dans `.env` |
| Aucune alerte après plusieurs jours | normal si peu d'annonces : `comparables_minimum: 8` bloque le calcul tant que la base est trop maigre. L'interface web te montre l'état réel |
