# VoiceBox Bridge Studio - Project Memory

## Objective

A fully local, offline voice studio built on Jamie Pine's VoiceBox (MIT). It keeps VoiceBox's TTS, voice cloning, stories, captures, effects, and model management, and adds speech-to-speech (the Voice Changer) as a built-in feature that converts existing speech or video recordings into a workspace voice profile while preserving the source timing, pacing, emphasis, and emotional performance as closely as the conversion engine permits.

Long local and YouTube video conversions are a primary use case. There must be no cloud inference, paid API, subscription, or per-minute service dependency. A one-time local model download is acceptable only after the user approves its size and license.

## User constraints

- Run inference entirely on the user's computer.
- STS uses the same workspace voice profiles as TTS, read in-process from the database and sample files, never over a separate HTTP API.
- Keep all services bound to loopback unless the user explicitly requests otherwise.
- Optimize eventually for long files, resumable jobs, and batch processing.
- Use only voice profiles and source media the user owns or has permission to use.
- Never download a multi-gigabyte model or dependency set (including the backend's PyTorch/TTS stack) without first telling the user its approximate size and receiving approval.
- Credit VoiceBox as the MIT license requires: keep `LICENSE` (© Voicebox Contributors) and `NOTICE.md`, and the About page credit.

## Provenance

- VoiceBox source imported from https://github.com/jamiepine/voicebox at commit `8af7efe62fab8d33e2a5dfbedabaa45f68a5184f` (0.6.0) in one commit on 2026-10-30. Upstream's release-signing workflow, maintainer agent skills, and `.mcp.json` were not imported.
- The pre-merge standalone bridge is preserved on branch `backup/main-pre-voicebox-merge`.
- Product name "VoiceBox Bridge Studio", Tauri identifier `com.digitalgods.voiceboxbridge`, main binary `voicebox-bridge-studio`. The Rust auto-paste self-detection constants in `tauri/src-tauri/src/main.rs` must stay in sync with these.
- The logo is the user's own artwork, `branding/logo-source.png`. `scripts/make_app_icon.py` cuts out its white background (including enclosed pockets listed in `ENCLOSED_BACKGROUND_SEEDS` and the drop shadow) and writes the in-app logo, favicons, and `tauri/app-icon.png`; then `cd tauri && bunx tauri icon app-icon.png` and `launcher\build.bat` refresh the platform icons and the launcher exe.
- Protocol and file identifiers stay upstream-compatible: `X-Voicebox-Client-Id`, `VOICEBOX_*` env vars, `voicebox_speak` MCP tool, `.voicebox.zip` profile exports, and the `voicebox.db` filename.
- Auto-update is disabled (`UPDATE_FEED_CONFIGURED` in `tauri/src/platform/updater.ts`, empty `plugins.updater.endpoints`). Never point it at upstream's feed.

## Architecture

- `backend/`: VoiceBox's FastAPI backend (Python 3.12, `backend/venv`). Port 17493, loopback.
- `backend/sts/`: speech-to-speech package. `WorkspaceVoices` reads profiles/samples via the shared SQLAlchemy session (`backend.database.session.SessionLocal`, read at call time) and resolves sample WAVs in place with `config.resolve_storage_path`. `OpenVoiceEngine` runs `openvoice_worker.py` in the isolated `.envs/openvoice-v2` Python 3.10 environment as a subprocess with HF offline mode.
- `backend/routes/sts.py`: `/sts` router. A lazily built process-wide `STSRuntime` shares one conversion lock across audio, local-video, and YouTube jobs; `run_sts_startup()` runs from the app lifespan.
- STS data shares the workspace data dir with the voice library: `inputs/`, `outputs/`, `jobs/`, `audio_jobs/`, `video_inputs/`, `video_jobs/`, `youtube_cache/`, plus `models/openvoice-v2/`.
- **Single studio theme:** gold on black-brown everywhere; there is no light mode or Theme setting. The palette is the shared `:root, .dark` block in `app/src/index.css` (`<html class="dark">` is fixed in the three `index.html` files for `dark:` variants). Use the tokens plus `.brand-title` (page titles), `.brand-label` (section labels), `.gold-fill` (primary actions), and `.studio-backdrop`; placeholders use `--placeholder` on `--field`. Keep text at 4.5:1 or better; don't dim informational text below `text-muted-foreground/80`.
- When editing upstream components, change only the needed class strings; don't run the formatter over whole upstream files (they are not Biome-formatted, and reformatting them makes upstream merges painful).
- `/stories`, `/captures`, `/settings/generation`, `/settings/captures` are app pages that collide with API GET routes; `backend/app.py` serves the SPA for browser page loads of them (`SPA_PAGES_SHADOWED_BY_API`).
- `app/src/components/LaunchScreen/`: full-window title card shown once per browser tab on launch (emblem, gold "VoiceBox Bridge / Studio" wordmark, Press Enter to continue). Styles are the `.launch-screen*` rules in `app/src/index.css`; it stays dark in both themes.
- `app/src/components/VoiceChangerTab/` + `app/src/lib/api/sts.ts`: the Voice Changer UI at route `/voice-changer`.
- `VoiceBoxBridgeStudio.exe` (built by `launcher/build.bat` from `launcher/launcher.py`, ignored by git) is the everyday launcher: a small windowed tray app that runs `backend.main` from `backend/venv` inside a kill-on-close job object and offers to close the standalone VoiceBox if it holds the port. `start-app.bat` is the console equivalent. Both serve `web/dist` from the backend with `--data-dir data`.
- The pre-merge `VoiceBoxBridge.exe` was a frozen copy of the old bridge that started the installed VoiceBox; it was deleted. Never revive it.
- The user's voices came from the installed VoiceBox library and were imported byte-identical into `data/`; a verified backup zip is in `data/backups/`. Never delete either copy. `scripts/import_voicebox_data.py` copies an installed VoiceBox library (`%APPDATA%\sh.voicebox.app`) into the workspace, read-only on the source.

VoiceBox profiles are not RVC models: a cloned profile is metadata plus reference WAVs and transcripts; shared Qwen/Chatterbox/LuxTTS/TADA weights are engine-level models. Do not use Whisper -> text -> TTS for conversion; it loses timing, delivery, and emotion. Preset and designed profiles have no samples and cannot be used for STS yet; generating and caching a neutral reference through TTS is the planned approach.

## Engine choice

OpenVoice V2 (MIT) is the installed engine; see `docs/sts/engine-audit.md`. Seed-VC is GPL-3.0 and must not be combined with this MIT codebase without a deliberate licensing decision. RVC needs per-speaker trained weights and is not profile-compatible.

## Development principles

- Keep generated files and caches inside explicit project/data directories.
- Preserve clean intermediate WAV files for debugging and later remuxing.
- Use structured job manifests so long conversions can resume after interruption.
- Process speech segments independently and reconstruct them at original timestamps.
- Never claim conversion success until the completed audio file has been decoded or otherwise validated.
- Benchmark a short clip before processing hours of material.
- STS tests (`backend/tests/sts`) must run without torch or a GPU; the rest of the backend suite needs the full environment.
- Do not record host-identifying measurements in the repository.

## Current status (2026-10-30)

- Merge complete on branch `voicebox-merge`. STS tests pass (80) in a lightweight Python 3.12 env; frontend typecheck, Biome, and the production web build pass.
- A real GPU conversion through `/sts/audio/jobs` using imported workspace profiles completed with exact source duration and was fully decoded.
- The full backend is installed in `backend/venv` (`just setup-python`, CUDA torch). The merged app was launched through `VoiceBoxBridgeStudio.exe`: one server on 17493 served the UI, the 9 imported voices through both `/profiles` and `/sts/voices`, and a live STS job with exact duration.
- No TTS model weights are present: the user's Hugging Face cache had been cleared before the merge (only lock folders remained). They must be re-downloaded from the Models tab, with the user's approval of each size.
- The Tauri desktop build has not been compiled.
- Automatic continuation of interrupted jobs after a process exit remains future work.

See `README.md`, `NOTICE.md`, `docs/sts/api.md`, `docs/sts/engine-install.md`, `docs/sts/engine-audit.md`, and `docs/sts/validation.md`.
