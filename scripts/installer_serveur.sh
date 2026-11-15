# Installation du site sur l'instance (exécutée par Session Manager depuis .github/workflows/deploy.yml).
# La variable VERSION (version de contenu attendue, ex. profil-0123abcd4567) est ajoutée en tête par le workflow.
#
# 1. Télécharge le paquet et vérifie que son manifeste porte bien la version attendue.
# 2. L'installe dans un dossier NEUF (aucun ancien fichier ne reste mélangé), en conservant le cache du chercheur.
# 3. Redémarre le service, puis vérifie que le serveur répond ET que la page d'accueil s'exécute sans erreur.
# 4. En cas d'échec, remet l'installation précédente en place et sort en erreur (le workflow échoue).
set -euo pipefail
: "${VERSION:?VERSION manquante}"
BUCKET="alphaforge-mvp-024848442163-us-east-1"
RACINE=/opt/alphaforge
PY="$RACINE/venv/bin/python"
cd "$RACINE"

aws s3 cp "s3://$BUCKET/app/mvp_profil.zip" app.zip --only-show-errors
rm -rf app.new && mkdir app.new && unzip -q app.zip -d app.new
TROUVEE="$(python3 -c 'import json; print(json.load(open("app.new/version_manifest.json"))["version"])')"
if [ "$TROUVEE" != "$VERSION" ]; then
  echo "Version du paquet inattendue : $TROUVEE au lieu de $VERSION"; rm -rf app.new; exit 1
fi
if [ -d app/cache ]; then cp -a app/cache app.new/cache; fi
rm -rf app.prev
if [ -d app ]; then mv app app.prev; fi
mv app.new app
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
  echo "Déployé : $VERSION"
else
  echo "Échec de la vérification : retour à l'installation précédente"
  if [ -d app.prev ]; then
    rm -rf app.echec && mv app app.echec && mv app.prev app
    systemctl restart alphaforge
  fi
  exit 1
fi
