# Security Policy

## Reporting a Vulnerability

We take the security of this project seriously. If you discover a security vulnerability, please do not open a public issue or disclose exploit details publicly.

Report vulnerabilities through GitHub private vulnerability reporting for this repository:

1. Open https://github.com/mohitkumhar/450-dsa/security/advisories/new
2. Include the affected area, reproduction steps, expected impact, and any suggested fix.
3. Wait for a maintainer response before sharing details publicly.

If GitHub private vulnerability reporting is unavailable, open a public issue that asks for a secure contact method without including sensitive vulnerability details.

We will investigate valid reports and respond as quickly as possible.

## Vulnerability Categories

We categorize security reports by type and severity:

| Category | Examples |
|----------|---------|
| **Authentication** | Login bypass, session fixation, token theft |
| **Authorization** | Privilege escalation, IDOR, missing access checks |
| **Injection** | SQL/NoSQL injection, SSTI, command injection |
| **XSS** | Stored, reflected, or DOM-based cross-site scripting |
| **CSRF** | Missing CSRF tokens on state-changing endpoints |
| **Data Exposure** | Unmasked PII, verbose error messages, exposed configs |
| **Supply Chain** | Compromised dependencies, malicious packages |

## Severity Rating

| Severity | CVSS Range | Response SLA |
|----------|-----------|-------------|
| **Critical** | 9.0–10.0 | Patch within 24 hours |
| **High** | 7.0–8.9 | Patch within 72 hours |
| **Medium** | 4.0–6.9 | Patch in next release |
| **Low** | 0.1–3.9 | Tracked, addressed when possible |

## Responsible Disclosure Policy

We follow responsible disclosure:
1. You report the issue privately
2. We acknowledge within 48 hours
3. We work on a fix and notify you
4. We release the fix and credit you (if desired)
5. You may publish after 90 days or after fix is released
