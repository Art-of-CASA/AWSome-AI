# Datathon 2026

An explainable, simulation-only investment-analysis prototype for the
PolyFinances Datathon 2026. It uses public financial data to demonstrate how
different fictional investor profiles could receive transparent, verifiable
decision support. It is not personalized financial advice and does not place
real trades.

## Security and collaboration

- This repository is private.
- Do not commit API keys, tokens, passwords, `.env` files, or AWS credential
  files. The included `.env.example` contains names only, never values.
- Runtime secrets are stored in AWS Secrets Manager. AWS Lambda receives only
  the permissions it needs to use its designated secret.
- Deployment uses GitHub Actions with OIDC-issued, short-lived AWS credentials;
  it does not use long-lived AWS access keys stored in GitHub.
- Open a pull request for changes and obtain a teammate review before merging
  to `main`.

## Local setup

1. Copy `.env.example` to `.env`.
2. Add only your own development credentials to `.env`.
3. Do not share or commit that file.

Implementation and deployment instructions will be added with the prototype.
