# Security policy

Do not report suspected credentials, API keys, tokens, or other security
issues in a public issue or pull request. Contact the repository owner
privately and rotate any exposed credential immediately.

Secrets must be stored in AWS Secrets Manager for deployed environments and in
an untracked local `.env` file for development. Never put a secret in source
code, GitHub Actions YAML, issue text, pull-request comments, or documentation.
