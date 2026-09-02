// ==UserScript==
// @name         Autoveille — capture leboncoin
// @namespace    autoveille
// @version      1.0
// @description  Envoie a ton serveur Autoveille les annonces deja affichees a l'ecran. Aucune requete automatique vers leboncoin : le script ne lit que ce que ton navigateur a deja charge parce que TU as ouvert la page.
// @match        https://www.leboncoin.fr/recherche*
// @match        https://www.leboncoin.fr/c/voitures*
// @grant        GM_xmlhttpRequest
// @connect      *
// ==/UserScript==

(function () {
  "use strict";

  // ---- A REGLER -----------------------------------------------------------
  const SERVEUR = "http://192.168.1.50:8080";  // adresse de ton LXC
  const JETON = "";                             // doit correspondre a INGEST_TOKEN
  // -------------------------------------------------------------------------

  const dejaEnvoyees = new Set();

  const entier = (v) => {
    if (v === null || v === undefined) return null;
    const n = parseInt(String(v).replace(/[^\d]/g, ""), 10);
    return Number.isFinite(n) ? n : null;
  };

  // Leboncoin est une application Next.js : les annonces de la page sont
  // presentes en JSON dans la balise #__NEXT_DATA__. C'est bien plus stable
  // que de lire le HTML affiche, qui change a chaque refonte.
  function depuisNextData() {
    const balise = document.getElementById("__NEXT_DATA__");
    if (!balise) return null;
    let donnees;
    try {
      donnees = JSON.parse(balise.textContent);
    } catch (e) {
      return null;
    }

    // On cherche recursivement un tableau d'objets ressemblant a des annonces.
    const trouvees = [];
    const vues = new Set();
    (function explorer(noeud, profondeur) {
      if (!noeud || typeof noeud !== "object" || profondeur > 12) return;
      if (vues.has(noeud)) return;
      vues.add(noeud);
      if (Array.isArray(noeud)) {
        if (noeud.length && noeud[0] && typeof noeud[0] === "object" &&
            ("list_id" in noeud[0] || "subject" in noeud[0])) {
          trouvees.push(...noeud);
          return;
        }
        noeud.forEach((x) => explorer(x, profondeur + 1));
        return;
      }
      Object.values(noeud).forEach((x) => explorer(x, profondeur + 1));
    })(donnees, 0);

    if (!trouvees.length) return null;

    return trouvees.map((a) => {
      const attributs = {};
      (a.attributes || []).forEach((at) => { attributs[at.key] = at.value; });
      return {
        source: "leboncoin",
        url: a.url || (a.list_id ? `https://www.leboncoin.fr/ad/voitures/${a.list_id}` : null),
        titre: a.subject || null,
        description: (a.body || "").slice(0, 600),
        prix: Array.isArray(a.price) ? entier(a.price[0]) : entier(a.price),
        annee: entier(attributs.regdate),
        km: entier(attributs.mileage),
        carburant: attributs.fuel ? String(attributs.fuel) : null,
        boite: attributs.gearbox ? String(attributs.gearbox) : null,
        code_postal: a.location ? a.location.zipcode : null,
        photo: a.images && a.images.thumb_url ? a.images.thumb_url : null,
      };
    });
  }

  // Repli : lecture du HTML affiche. Moins fiable, a ajuster si la mise en
  // page change, mais ca depanne si la structure JSON evolue.
  function depuisHtml() {
    const liens = document.querySelectorAll('a[href*="/ad/voitures/"]');
    const annonces = [];
    liens.forEach((lien) => {
      const bloc = lien.closest("article") || lien;
      const texte = bloc.innerText || "";
      const prix = texte.match(/([\d\s\u202f]+)\s*€/);
      const km = texte.match(/([\d\s\u202f]+)\s*km/i);
      const annee = texte.match(/\b(19[89]\d|20[0-2]\d)\b/);
      const cp = texte.match(/\b(\d{5})\b/);
      const img = bloc.querySelector("img");
      annonces.push({
        source: "leboncoin",
        url: new URL(lien.getAttribute("href"), location.origin).href,
        titre: (bloc.querySelector("p, h2, h3") || lien).innerText.trim().slice(0, 200),
        description: texte.slice(0, 600),
        prix: prix ? entier(prix[1]) : null,
        km: km ? entier(km[1]) : null,
        annee: annee ? entier(annee[1]) : null,
        code_postal: cp ? cp[1] : null,
        photo: img ? img.src : null,
      });
    });
    return annonces;
  }

  function envoyer(annonces) {
    const nouvelles = annonces.filter((a) => a.url && !dejaEnvoyees.has(a.url));
    if (!nouvelles.length) return;
    nouvelles.forEach((a) => dejaEnvoyees.add(a.url));

    GM_xmlhttpRequest({
      method: "POST",
      url: SERVEUR + "/ingest",
      headers: { "Content-Type": "application/json", "X-Jeton": JETON },
      data: JSON.stringify(nouvelles),
      onload: (r) => {
        try {
          const res = JSON.parse(r.responseText);
          afficher(`${res.nouvelles} nouvelle(s) sur ${res.recues} envoyée(s)`);
        } catch (e) {
          afficher("réponse illisible du serveur");
        }
      },
      onerror: () => afficher("serveur injoignable"),
    });
  }

  let pastille;
  function afficher(message) {
    if (!pastille) {
      pastille = document.createElement("div");
      Object.assign(pastille.style, {
        position: "fixed", bottom: "16px", right: "16px", zIndex: 99999,
        background: "#16181C", color: "#fff", padding: "7px 13px",
        borderRadius: "3px", font: "400 13px/1.4 system-ui, sans-serif",
        boxShadow: "0 1px 4px rgba(0,0,0,.25)", pointerEvents: "none",
      });
      document.body.appendChild(pastille);
    }
    pastille.textContent = "Autoveille · " + message;
    pastille.style.opacity = "1";
    clearTimeout(pastille._t);
    pastille._t = setTimeout(() => { pastille.style.opacity = "0"; }, 4000);
  }

  function capturer() {
    const annonces = depuisNextData() || depuisHtml();
    if (annonces && annonces.length) envoyer(annonces);
  }

  // Capture au chargement, puis a chaque fois que tu scrolles ou changes de
  // page : le contenu est charge au fur et a mesure.
  setTimeout(capturer, 1500);
  new MutationObserver(() => {
    clearTimeout(window.__autoveilleT);
    window.__autoveilleT = setTimeout(capturer, 1200);
  }).observe(document.body, { childList: true, subtree: true });
})();
