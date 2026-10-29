# Contributing

Thanks for trying SignalTube. Small, clear reports are more useful than “it broke”.

## Report a bug

Use the bug report template and include your Linux/Omarchy version, browser, Python version, SignalTube release, steps and expected/actual behaviour. A synthetic example is ideal.

**Do not attach** API keys, private launch URLs, Takeout exports, database files, raw logs or screenshots containing private viewing history. See SECURITY.md for vulnerabilities and credential exposure.

## Suggest a change

Explain the problem you run into and the smallest useful improvement. The current boundaries are local-first operation, manual generation/refresh, a 100-unit daily cap, explicit user choices and Omarchy-compatible themes. Model integration, automatic polling and an app-menu installer are not part of this beta.

## Develop and test

```bash
uv sync --frozen
uv run --frozen pytest -q
```

Tests use synthetic data and fake API transports. The restart test starts short-lived loopback servers against temporary stores. Never add tests that use real API keys, paid services or another person's history.

Keep changes scoped. Include tests for state transitions, privacy or quota behaviour when relevant. Describe the visible behaviour and how it was checked. Do not commit `var/`, environment files or your local build artefacts. Run the suite before opening a pull request.

Contributions are accepted under the repository's MIT licence. Dependency licences remain their own.
