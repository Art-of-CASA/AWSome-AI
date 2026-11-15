# Installation du site sur l'instance (exécutée par Session Manager depuis .github/workflows/deploy.yml).
# La variable VERSION (version de contenu attendue, ex. profil-0123abcd4567) est ajoutée en tête par le workflow.
#
# 1. Télécharge le paquet et vérifie que son manifeste porte bien la version attendue.
# 2. Installe ses dépendances avant l'activation, puis conserve le cache du chercheur et les traces locales.
# 3. Redémarre le service, puis vérifie que le serveur répond ET que la page d'accueil s'exécute sans erreur.
# 4. En cas d'échec, remet l'installation précédente en place et sort en erreur (le workflow échoue).
# Chaque publication prépare un venv distinct ; le retour arrière restaure aussi les dépendances.
set -euo pipefail
: "${VERSION:?VERSION manquante}"
BUCKET="alphaforge-mvp-024848442163-us-east-1"
RACINE="${ALPHAFORGE_RACINE:-/opt/alphaforge}"
cd "$RACINE"
RACINE="$(pwd -P)"
if [ "$RACINE" = / ]; then echo "Racine d'installation invalide"; exit 1; fi
PY="$RACINE/venv/bin/python"
exec 9>"$RACINE/deploiement.lock"
flock -n 9 || { echo "Un déploiement est déjà en cours"; exit 1; }

conserver_donnees() {
  # Copier le contenu, pas le dossier parent : une seconde publication ne crée pas traces/traces/.
  for dossier in cache traces; do
    if [ -d "$1/$dossier" ]; then
      mkdir -p "$2/$dossier"
      cp -a "$1/$dossier/." "$2/$dossier/" || return 1
    fi
  done
}

ANCIENNE_DEPLACEE=0
NOUVELLE_INSTALLEE=0
VENV_DEPLACE=0
VENV_ACTIVE=0
retour_arriere() {
  statut="$1"
  trap - ERR
  # Une panne du service ou de la copie de secours ne doit pas interrompre les autres étapes de restauration.
  set +e
  echo "Échec du déploiement : retour à l'installation précédente"
  if [ "$VENV_ACTIVE" = 1 ]; then unlink "$RACINE/venv"; fi
  if [ "$VENV_DEPLACE" = 1 ]; then mv "$RACINE/venv.prev" "$RACINE/venv"; fi
  if [ "$NOUVELLE_INSTALLEE" = 1 ] && [ -d app ]; then
    if [ "$ANCIENNE_DEPLACEE" = 1 ]; then
      conserver_donnees app app.prev || echo "Attention : copie des données locales incomplète"
    fi
    rm -rf app.echec
    mv app app.echec || echo "Impossible de conserver l'installation échouée"
  fi
  if [ "$ANCIENNE_DEPLACEE" = 1 ]; then
    if mv app.prev app; then
      systemctl restart alphaforge || echo "L'ancienne version est restaurée mais son redémarrage a échoué"
    else
      echo "Échec de la restauration des fichiers de l'ancienne version"
    fi
  else
    echo "Aucune installation précédente disponible"
  fi
  exit "$statut"
}

aws s3 cp "s3://$BUCKET/app/mvp_profil.zip" app.zip --only-show-errors
# Le vérificateur appartient à l'installateur de confiance, jamais au ZIP reçu.
python3 - "$VERSION" <<'VERIFIER'
import hashlib, json, sys, stat
from pathlib import PurePosixPath
from zipfile import ZipFile
with ZipFile("app.zip") as z:
    noms = z.namelist()
    if len(noms) != len(set(noms)):
        raise ValueError("Entrées répétées")
    for info in z.infolist():
        p = PurePosixPath(info.filename)
        if p.is_absolute() or ".." in p.parts or "\\" in info.filename or stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError("Chemin non autorisé")
    if sum(i.file_size for i in z.infolist()) > 50_000_000:
        raise ValueError("Paquet trop volumineux")
    def unique(paires):
        d = {}
        for k, v in paires:
            if k in d: raise ValueError("Clé répétée")
            d[k] = v
        return d
    m = json.loads(z.read("version_manifest.json"), object_pairs_hook=unique)
    fichiers = m["fichiers"]
    if not isinstance(fichiers, dict) or set(noms) != set(fichiers) | {"version_manifest.json"}:
        raise ValueError("Inventaire incorrect")
    for nom, attendu in fichiers.items():
        if hashlib.sha256(z.read(nom)).hexdigest() != attendu:
            raise ValueError("Empreinte incorrecte : " + nom)
    version = "profil-" + hashlib.sha256("\n".join(f"{n}:{h}" for n,h in fichiers.items()).encode()).hexdigest()[:12]
    if version != sys.argv[1] or m["version"] != version:
        raise ValueError("Version incorrecte")
VERIFIER
rm -rf app.new
mkdir app.new
unzip -q app.zip -d app.new
TROUVEE="$(python3 -c 'import json; print(json.load(open("app.new/version_manifest.json"))["version"])')"
if [ "$TROUVEE" != "$VERSION" ]; then
  echo "Version du paquet inattendue : $TROUVEE au lieu de $VERSION"; rm -rf app.new; exit 1
fi
mkdir -p "$RACINE/venvs"
NOUVEAU_VENV="$(mktemp -d "$RACINE/venvs/release.XXXXXXXX")"
# Garder l'interpréteur du service : le python3 système peut être une autre version.
"$PY" -m venv "$NOUVEAU_VENV"
if ! "$NOUVEAU_VENV/bin/python" -m pip install -r "$RACINE/app.new/requirements.txt"; then
  echo "Échec de l'installation des dépendances : fichiers de l'ancienne version conservés"
  exit 1
fi
conserver_donnees app app.new
rm -rf app.prev
rm -rf "$RACINE/venv.prev"
trap 'retour_arriere $?' ERR
if [ -e "$RACINE/venv" ]; then mv "$RACINE/venv" "$RACINE/venv.prev"; VENV_DEPLACE=1; fi
ln -s "$NOUVEAU_VENV" "$RACINE/venv"
VENV_ACTIVE=1
if [ -d app ]; then mv app app.prev; ANCIENNE_DEPLACEE=1; fi
mv app.new app
NOUVELLE_INSTALLEE=1
systemctl restart alphaforge

verifier() {
  for _ in $(seq 1 30); do
    curl -fs -o /dev/null http://localhost:8501/_stcore/health && break
    sleep 2
  done
  curl -fs -o /dev/null http://localhost:8501/_stcore/health || return 1
  # La page d'accueil doit s'exécuter sans exception (import manquant, erreur de syntaxe…). Aucun appel au modèle.
  (cd "$RACINE/app" && timeout 180 "$PY" - <<'FIN'
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py", default_timeout=120).run()
assert not at.exception, [str(e.value) for e in at.exception]
assert any(b.label.startswith("Charger") for b in at.button), "Accueil incomplet"
print("Page d'accueil OK")
FIN
  )
}

if verifier; then
  trap - ERR
  echo "Déployé : $VERSION"
else
  retour_arriere 1
fi
