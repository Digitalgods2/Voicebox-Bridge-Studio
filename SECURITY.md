# Security and privacy

## Local-only data

Do not commit credentials, environment files, host paths, usernames, hardware
fingerprints, voice profile metadata, reference audio, source media, downloaded
video, generated output, job manifests, model weights, or runtime logs.

Runtime data belongs under the ignored `data/` workspace: the voice database,
profiles, generations, captures, and all speech-to-speech uploads, jobs, and
outputs. Python environments (`backend/venv/`, `.envs/`), third-party source
(`third_party/`), model caches, build output, and agent-specific files are
also ignored.

## Network boundary

The backend binds to loopback (`127.0.0.1`) by default, and the launcher never
changes that. Its API is unauthenticated. Do not expose it to a LAN or the
public internet without authentication, CSRF protection, rate limiting, and a
separate threat-model review.

Inference is local. The speech-to-speech engine runs with Hugging Face offline
mode forced on and verifies the converter checkpoint hash before loading it.
YouTube downloads happen only for URLs you submit with an explicit rights
confirmation.

## Updates

This app does not auto-update. Upstream VoiceBox's update feed and signing key
were disconnected so an upstream release can never replace this app. If you
publish your own releases, generate your own signing key, configure
`plugins.updater` in `tauri/src-tauri/tauri.conf.json`, and enable the check in
`tauri/src/platform/updater.ts`. Never commit the private signing key.

Voicebox Cloud backup/sync is off unless `VOICEBOX_CLOUD_ENABLED` is set; it
points at upstream's service and should stay off.

## Credential handling

The app does not require cloud inference credentials or API keys. Never add a
token to a URL, source file, test fixture, issue, log, or job manifest. If a
credential is committed accidentally, revoke it immediately and rewrite the
affected Git history before sharing the repository.

## Reporting

Report security concerns privately to the repository owner. Do not include real
credentials, personal media, host paths, or voice profile data in a GitHub issue.
Vulnerabilities in code inherited from VoiceBox may also affect upstream; report
those to the VoiceBox project as described in its own security policy.
