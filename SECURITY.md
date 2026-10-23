# Security Policy

## Supported versions

| Component | Supported |
|---|---|
| App | 1.5.x |
| Engine | 1.30.x |
| Repository tooling | current main |

## Reporting a vulnerability

Please use GitHub Private Vulnerability Reporting:

    Repository -> Security -> Report a vulnerability

Do not open a public Issue with exploit details, credentials, or user data.

## Never post

- API keys, access tokens, passwords
- .env or local configuration
- TLS private keys or certificates
- dgtf_memory/, session logs, user conversations
- Local model weights or private training data

## Scope

In scope:

- App and Engine source in this repository
- GitHub Actions workflows
- Repository configuration and release tooling
- Public Pages site

Out of scope:

- Local model weights downloaded separately
- Third-party model providers
- Vulnerabilities requiring physical access

## Response

- We aim to acknowledge reports within 7 days.
- We will validate, fix, and coordinate disclosure.
- Please do not publicly disclose before a fix is available.

## Safe harbor

Good-faith security research that respects privacy and avoids data destruction is welcome.
