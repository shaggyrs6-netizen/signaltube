# Security

SignalTube is a single-user, loopback-only desktop application. It is not designed to be exposed on a public network or used as a multi-user service. Processes running as your OS user share its trust boundary. Owner-only files are not encryption.

## Report privately

For a vulnerability, use this repository's **Security → Report a vulnerability** feature. Do not post credentials, exploit details involving private data, or private viewing history in a public issue. If private reporting is unavailable, open a minimal issue requesting a private contact route without including sensitive details.

If a Google API key is exposed, revoke it in Google Cloud immediately. A leaked local launch link/session token also needs deliberate local rotation after stopping the app. Never reset the quota ledger to compensate for a credential problem.

## What stays private

`var/` contains personal choices, imported history, cached metadata, the API key and local session credential. It is excluded from Git. Local logs may contain launch URLs. Do not upload it, even when asking for help.

Only explicitly requested YouTube refreshes call Google's API. Visiting YouTube links opens the external site under its own privacy rules. Installation fetches Python dependencies. Tests do not require a real Google key.

The current beta is the supported code line. There is no guaranteed response time or security certification.
