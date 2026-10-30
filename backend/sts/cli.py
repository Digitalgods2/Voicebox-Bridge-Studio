"""Command-line access to speech-to-speech: ``python -m backend.sts <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from .. import config
from .audio_effects import AudioEffectsError
from .conversion_service import ConversionService
from .openvoice_engine import OpenVoiceEngine, OpenVoiceError
from .settings import STSSettings
from .workspace_voices import VoiceWorkspaceError, WorkspaceVoices


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Speech-to-speech with workspace voice profiles")
    parser.add_argument("--data-dir", type=Path, help="Workspace data directory (database, profiles, STS jobs)")
    parser.add_argument(
        "--device",
        help="Inference device: 'cpu', 'cuda', or 'cuda:<index>' (default from STS_ENGINE_DEVICE, else cuda:0)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("profiles", help="List workspace voice profiles")
    commands.add_parser("engine-status", help="Check the isolated OpenVoice installation without loading its model")
    commands.add_parser(
        "engine-probe",
        help="Load the OpenVoice model (CUDA by default; pass --device cpu to run without a GPU) and report readiness",
    )
    samples = commands.add_parser("samples", help="List reference samples for a profile")
    samples.add_argument("profile_id")
    convert = commands.add_parser("convert", help="Convert one source recording to a workspace voice sample")
    convert.add_argument("source_audio", type=Path)
    convert.add_argument("profile_id")
    convert.add_argument("sample_id")
    convert.add_argument("--output", type=Path)
    convert.add_argument("--tau", type=float, default=0.3)
    convert.add_argument(
        "--pitch-semitones",
        type=float,
        default=0.0,
        help="Duration-preserving pitch correction from -6 to +6 semitones",
    )
    convert.add_argument(
        "--brightness-db",
        type=float,
        default=0.0,
        help="Tone-depth/high-shelf adjustment from -6 dB (deeper) to +6 dB (brighter)",
    )
    convert.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.data_dir:
            config.set_data_dir(args.data_dir)
        settings = STSSettings.from_env()
        if args.device:
            settings = replace(settings, engine_device=args.device)

        if args.command in {"engine-status", "engine-probe"}:
            engine = OpenVoiceEngine(device=settings.engine_device)
            _print(engine.status() if args.command == "engine-status" else engine.probe())
            return 0

        from .. import database

        database.init_db()
        voices = WorkspaceVoices(max_reference_bytes=settings.max_reference_bytes)
        if args.command == "profiles":
            _print(voices.profiles())
        elif args.command == "samples":
            _print(voices.samples(args.profile_id))
        elif args.command == "convert":
            conversions = ConversionService(settings.data_dir, voices, OpenVoiceEngine(device=settings.engine_device))
            _print(
                conversions.convert(
                    args.source_audio,
                    args.profile_id,
                    args.sample_id,
                    tau=args.tau,
                    pitch_semitones=args.pitch_semitones,
                    brightness_db=args.brightness_db,
                    overwrite=args.overwrite,
                    output_audio=args.output,
                )
            )
        return 0
    except (ValueError, LookupError, VoiceWorkspaceError, OpenVoiceError, AudioEffectsError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
