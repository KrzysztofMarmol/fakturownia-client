# Security Policy

## Token handling

This client sends the Fakturownia API token **only** in the
`Authorization: Bearer` header — never in URLs, request bodies, log
messages or exception text. If you find any code path that violates this,
please treat it as a security issue.

## Reporting a vulnerability

Please report vulnerabilities privately via
[GitHub Security Advisories](https://github.com/KrzysztofMarmol/fakturownia-client/security/advisories/new).
Do not open public issues for security problems.

## Supported versions

Only the latest released version receives security fixes.
