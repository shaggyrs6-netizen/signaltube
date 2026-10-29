# Your Google API key and free quota

Documentation checked 29 October 2026. Google can change labels/allocations; the actual limits in your own Console project are authoritative.

## How much usage do I get?

The YouTube Data API's standard no-charge allowance is quota-limited. Google's current default is **10,000 units per day shared by the ordinary endpoints**, with separate default buckets of **100 search calls/day** and **100 upload calls/day**. SignalTube does not use search or upload. Daily quotas reset at **midnight Pacific Time**, not your computer's local midnight. [Google's quota table](https://developers.google.com/youtube/data/determine_quota_cost)

SignalTube deliberately uses only **100 units/day**, with an independent persistent local guard. That is the app's safety budget, not Google's standard allowance. It calls `channels.list` (1 unit) when channel metadata is missing and `playlistItems.list` (1 unit per channel's recent-upload page). [Official method costs](https://developers.google.com/youtube/data/determine_quota_cost)

Examples for the current one-page collector:

| Tracked channels | Fully uncached refresh | Refresh with channel metadata cached |
|---|---:|---:|
| 3 | 6 units | 3 units |
| 10 | 20 units | 10 units |
| 13 | 26 units | 13 units |

The preview reserves `channel count + missing channel lookups` before sending anything. Errors/interruptions retain the reservation conservatively. Do not equate units with videos, dollars or a guaranteed number of refreshes. Shortlist builds, local choices and Takeout imports cost zero API units. Exceeding this app's cap blocks a batch; it does not buy more quota or enable billing. Other software sharing your Google project can use quota outside this local ledger. Use a dedicated project and check Console.

No Cloud hosting, Google Cloud free-credit trial, payment card or paid AI service is part of this setup. If your account's flow demands billing, stop and review the requirement rather than activating it just to continue. Quota verification is not a billing-account audit. Never create extra projects to evade Google's limits. Requests for additional quota are a separate Google process and are not part of SignalTube's setup. [Google's quota/audit guidance](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits)

## Create and restrict your key

1. Sign into [Google Cloud Console](https://console.cloud.google.com/). Create a dedicated project, for example **SignalTube**, and check it is selected.
2. Go to **APIs & Services → Library**, find **YouTube Data API v3**, and enable it. No Analytics/Reporting/AI API is needed.
3. Go to **Credentials → Create credentials → API key**. If shown a credential wizard, select YouTube Data API v3 and **Public data**. This app needs a standard API key, not OAuth consent, a service account or access to your private YouTube account.
4. Select **Restrict key**. Under **API restrictions**, restrict it to **YouTube Data API v3**, then save.
5. Application restrictions: the caller is the local Python server. Website/HTTP-referrer restrictions are inappropriate. A known stable **public outbound IP address** can be restricted under server/IP restrictions; do not enter `127.0.0.1` or a LAN address. VPNs, IPv6 and changing home IPs can affect matching. If you cannot maintain that restriction, a local trial can use no application restriction while retaining the API-only restriction—keep the key secret. [Google restriction guidance](https://docs.cloud.google.com/api-keys/docs/add-restrictions-api-keys)
6. Under **YouTube Data API v3 → Quotas & System Limits**, find **Queries per day**, not Search Queries per day. Lower its editable limit to **100** for this dedicated project and save. Confirm the saved value. If unavailable, SignalTube still enforces its own 100-unit cap; do not claim the Google-side cap was changed.
7. In SignalTube's folder, run `./run.sh key-add` and paste at the hidden terminal prompt. It stores the key in `var/secrets/youtube.key`, owner-only, without making any request. It refuses silent key replacement.
8. Open Watch next, check the estimated next-refresh cost and explicitly click **Refresh from YouTube**. This is the first step that calls the API.

## Compare usage

Console's **Queries per day** row shows the saved limit, current usage and percentage. Compare the same Pacific quota day with SignalTube's ledger. For example, 32 units under a 100-unit limit is 32%. SignalTube can reserve more than Google ultimately reports after a failed/interrupted batch; reporting delay or another app sharing the project may also explain differences. Do not delete the ledger to make them match.

## If something goes wrong

- Rejected key: check selected project, API enablement, API restriction and public-IP restriction. Never post the key or raw request headers in an issue.
- Daily cap/cooldown: wait until the shown eligible time; there is no automatic retry. Authentication/quota rejection can pause until the next Pacific quota day.
- Exposed key: revoke it in Google Console. Stop SignalTube, deliberately remove the revoked local key file, then run `key-add` for the replacement. Do not delete the quota database. Key rotation is not a quota reset.
- A Google key never belongs in browser URLs, Git, setup scripts or screenshots. The app's **local launch token** is another credential and should also remain private.

Further reference: [Google's getting-started guide](https://developers.google.com/youtube/data/getting-started), [API-key best practices](https://docs.cloud.google.com/docs/authentication/api-keys-best-practices).
