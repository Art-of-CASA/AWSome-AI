# Installation du site sur l'instance (exécutée par Session Manager depuis .github/workflows/deploy.yml).
# La variable VERSION (version de contenu attendue, ex. profil-0123abcd4567) est ajoutée en tête par le workflow.
#
# 1. Télécharge le paquet et vérifie que son manifeste porte bien la version attendue.
# 2. Installe ses dépendances avant l'activation, puis conserve le cache du chercheur et les traces locales.
# 3. Redémarre le service, puis vérifie que le serveur répond ET que la page d'accueil s'exécute sans erreur.
# 4. En cas d'échec, remet l'installation précédente en place et sort en erreur (le workflow échoue).
# Limite : le venv est partagé. Le retour arrière restaure les fichiers, pas les dépendances déjà installées ;
# une mise à jour incompatible des bibliothèques peut donc exiger une restauration séparée du venv.
set -euo pipefail
: "${VERSION:?VERSION manquante}"
BUCKET="alphaforge-mvp-024848442163-us-east-1"
RACINE="${ALPHAFORGE_RACINE:-/opt/alphaforge}"
cd "$RACINE"
RACINE="$(pwd -P)"
if [ "$RACINE" = / ]; then echo "Racine d'installation invalide"; exit 1; fi
PY="$RACINE/venv/bin/python"

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
retour_arriere() {
  statut="$1"
  trap - ERR
  # Une panne du service ou de la copie de secours ne doit pas interrompre les autres étapes de restauration.
  set +e
  echo "Échec du déploiement : retour à l'installation précédente"
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
rm -rf app.new
mkdir app.new
unzip -q app.zip -d app.new
TROUVEE="$(python3 -c 'import json; print(json.load(open("app.new/version_manifest.json"))["version"])')"
if [ "$TROUVEE" != "$VERSION" ]; then
  echo "Version du paquet inattendue : $TROUVEE au lieu de $VERSION"; rm -rf app.new; exit 1
fi
if ! "$PY" -m pip install -r "$RACINE/app.new/requirements.txt"; then
  echo "Échec de l'installation des dépendances : fichiers de l'ancienne version conservés"
  echo "Le venv partagé peut nécessiter une restauration séparée de ses dépendances"
  exit 1
fi
conserver_donnees app app.new
rm -rf app.prev
trap 'retour_arriere $?' ERR
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
