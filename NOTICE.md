# Notices and credits

VoiceBox Bridge Studio is created and maintained by **DigitalGods**
(<https://github.com/Digitalgods2>), who is responsible for this app.

VoiceBox Bridge Studio is built on **VoiceBox** by Jamie Pine and the Voicebox
contributors: <https://github.com/jamiepine/voicebox>. VoiceBox's source was
imported from commit `8af7efe62fab8d33e2a5dfbedabaa45f68a5184f` (version 0.6.0)
and has since been modified: speech-to-speech was added as a built-in feature,
and the app was renamed, re-iconed, and disconnected from upstream's update feed.

VoiceBox is distributed under the MIT License, whose copyright and permission
notice must be kept in all copies or substantial portions of the software:

> MIT License
>
> Copyright (c) 2026 Voicebox Contributors
>
> The full text is in [`LICENSE`](LICENSE).

"VoiceBox" is used here only to credit and describe the upstream project. This
app is not affiliated with or endorsed by the VoiceBox project.

## Third-party components used by speech-to-speech

None of these are committed to this repository; they are installed locally.

| Component | License | Use |
| --- | --- | --- |
| [OpenVoice](https://github.com/myshell-ai/OpenVoice) source and V2 converter checkpoint | MIT | Voice conversion engine, run in an isolated environment |
| [PyTorch](https://pytorch.org/) | BSD-3-Clause | Inference runtime for the isolated engine |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | Downloads of authorized YouTube sources |
| [FFmpeg](https://ffmpeg.org/) / [Rubber Band](https://breakfastquay.com/rubberband/) | Depends on the installed build | Extraction, pitch correction, remuxing, validation |

FFmpeg and Rubber Band are used from the user's own installation; their license
obligations depend on that build and are not affected by this repository.

VoiceBox's own TTS engines and models (Qwen3-TTS, Chatterbox, LuxTTS, TADA,
Kokoro, OmniVoice, Whisper, and others) keep their upstream licenses; see the
Models tab and each model's model card before use.

## Licensing of this app's own additions

The MIT notice above covers the VoiceBox-derived code. The license for code
added in this repository (the speech-to-speech feature and other changes) is
chosen by this repository's owner. Until one is declared, add your own
copyright line to `LICENSE` when you decide to release these additions under
the same MIT terms.
