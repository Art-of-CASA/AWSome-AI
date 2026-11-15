# Politique de sécurité

Ne signalez jamais un identifiant, une clé ou un autre problème de sécurité dans une issue ou une pull request publique. Prévenez le propriétaire du dépôt en privé, et révoquez tout identifiant exposé sans attendre.

Le projet n'utilise aucune clé stockée : le site déployé s'authentifie avec le rôle IAM de son instance EC2, et le développement local avec des identifiants AWS temporaires, jamais versionnés. Ne placez aucun secret, identifiant de compte ou adresse IP dans le code, les issues, les commentaires ou la documentation.
