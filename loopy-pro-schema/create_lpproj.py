#!/usr/bin/env python3
"""
Loopy Pro Project File Creator
================================

Creates .lpproj.zip files that can be loaded into Loopy Pro.

IMPORTANT: Run dissect_lpproj.py on a real project file FIRST to get the
actual schema. Then update the schema constants in this file accordingly.

This file provides the scaffolding and will need to be updated once the
actual schema is known. The structure below is based on common iOS app
project bundle patterns and what we know about Loopy Pro.

Usage:
    # First, dissect a real file to get the schema:
    python3 dissect_lpproj.py /path/to/real_project.lpproj.zip

    # Then create a new project (update schema first!):
    python3 create_lpproj.py output_project.lpproj.zip

    # Or with a schema file from dissection:
    python3 create_lpproj.py output.lpproj.zip --schema real_project_schema.json
"""

import sys
import os
import json
import zipfile
import plistlib
import struct
import argparse
from pathlib import Path


def generate_wav(duration_seconds=1.0, sample_rate=44100, frequency=0, channels=1, bits=32):
    """
    Generate a WAV file in memory.

    Args:
        duration_seconds: Length of audio
        sample_rate: Sample rate (44100, 48000, etc.)
        frequency: Tone frequency in Hz. 0 = silence.
        channels: 1 = mono, 2 = stereo
        bits: Bits per sample (16, 24, 32)
    """
    import math
    num_samples = int(sample_rate * duration_seconds)
    bytes_per_sample = bits // 8
    block_align = channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    data_size = num_samples * block_align

    samples = bytearray()
    for i in range(num_samples):
        if frequency > 0:
            t = i / sample_rate
            value = math.sin(2 * math.pi * frequency * t)
            if bits == 16:
                sample = int(value * 32767)
                sample_bytes = struct.pack('<h', sample)
            elif bits == 24:
                sample = int(value * 8388607)
                sample_bytes = struct.pack('<i', sample)[:3]
            else:  # 32-bit float
                sample_bytes = struct.pack('<f', value)
        else:
            sample_bytes = b'\x00' * bytes_per_sample

        for _ in range(channels):
            samples.extend(sample_bytes)

    # Build WAV header
    fmt_code = 3 if bits == 32 else 1  # 3 = IEEE float, 1 = PCM
    header = struct.pack('<4sI4s', b'RIFF', 36 + data_size, b'WAVE')
    header += struct.pack('<4sIHHIIHH', b'fmt ', 16, fmt_code, channels,
                          sample_rate, byte_rate, block_align, bits)
    header += struct.pack('<4sI', b'data', data_size)

    return header + bytes(samples)


def generate_silence_caf(duration_seconds=1.0, sample_rate=44100, channels=1):
    """Generate a minimal CAF (Core Audio Format) file with silence."""
    # CAF is Apple's native format - Loopy Pro may prefer it
    # For now we generate WAV which is universally supported
    return generate_wav(duration_seconds, sample_rate, 0, channels)


class LoopyProProjectBuilder:
    """
    Builder for Loopy Pro project files.

    IMPORTANT: The internal structure below is a TEMPLATE based on common
    iOS app patterns. After running dissect_lpproj.py on a real file,
    update this class to match the actual schema.
    """

    def __init__(self, schema_path=None):
        self.schema = None
        if schema_path and os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                self.schema = json.load(f)
            print(f"Loaded schema from: {schema_path}")
        self.files = {}

    def from_schema(self, modifications=None):
        """
        Create a project using a loaded schema as the base.
        Apply modifications dict to override specific values.
        """
        if not self.schema:
            raise ValueError("No schema loaded. Run dissect_lpproj.py first.")

        # The schema tells us what files exist and their structure.
        # You would recreate each file based on the schema's structure info.
        print("Schema-based creation requires the full_analysis.json file")
        print("from dissect_lpproj.py, not just the schema.")
        print("See the reconstruct_from_analysis() method instead.")

    def reconstruct_from_analysis(self, analysis_path: str, modifications=None):
        """
        Reconstruct a project from a full analysis JSON.
        This is useful for creating variations of an existing project.

        The analysis JSON is produced by dissect_lpproj.py and contains
        the actual file contents (for structured data) and metadata
        (for binary/audio data).
        """
        with open(analysis_path, 'r') as f:
            analysis = json.load(f)

        # This requires the original file to copy binary data from.
        # For structured data (plist/json), we can reconstruct from the analysis.
        print("To create a modified copy, use clone_and_modify() with the original file.")

    def clone_and_modify(self, source_zip: str, output_zip: str, modifications: dict):
        """
        Clone an existing .lpproj.zip and apply modifications.

        This is the most reliable way to create new projects:
        1. Start from a known-good project
        2. Modify specific values (BPM, track names, etc.)
        3. Replace audio files
        4. Save as new zip

        Args:
            source_zip: Path to source .lpproj.zip
            output_zip: Path to write modified .lpproj.zip
            modifications: Dict of modifications to apply:
                {
                    "replace_files": {
                        "path/in/zip": b"new_data",
                    },
                    "modify_plist": {
                        "path/to/file.plist": {
                            "key.subkey": new_value,
                        },
                    },
                    "modify_json": {
                        "path/to/file.json": {
                            "key.subkey": new_value,
                        },
                    },
                    "remove_files": ["path/to/remove"],
                    "add_files": {
                        "path/in/zip": b"data",
                    },
                }
        """
        replace_files = modifications.get("replace_files", {})
        modify_plist = modifications.get("modify_plist", {})
        modify_json = modifications.get("modify_json", {})
        remove_files = set(modifications.get("remove_files", []))
        add_files = modifications.get("add_files", {})

        with zipfile.ZipFile(source_zip, 'r') as src, \
             zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as dst:

            for item in src.infolist():
                if item.filename in remove_files:
                    continue

                if item.filename in replace_files:
                    dst.writestr(item, replace_files[item.filename])
                    continue

                data = src.read(item.filename)

                # Modify plist files
                if item.filename in modify_plist:
                    try:
                        plist_data = plistlib.loads(data)
                        for key_path, value in modify_plist[item.filename].items():
                            set_nested(plist_data, key_path, value)
                        data = plistlib.dumps(plist_data)
                    except Exception as e:
                        print(f"Warning: Could not modify plist {item.filename}: {e}")

                # Modify JSON files
                if item.filename in modify_json:
                    try:
                        json_data = json.loads(data)
                        for key_path, value in modify_json[item.filename].items():
                            set_nested(json_data, key_path, value)
                        data = json.dumps(json_data).encode('utf-8')
                    except Exception as e:
                        print(f"Warning: Could not modify JSON {item.filename}: {e}")

                dst.writestr(item, data)

            # Add new files
            for path, file_data in add_files.items():
                dst.writestr(path, file_data)

        print(f"✅ Created modified project: {output_zip}")


def set_nested(obj: dict, key_path: str, value):
    """Set a nested value using dot-notation path."""
    keys = key_path.split('.')
    current = obj
    for key in keys[:-1]:
        if key.isdigit():
            current = current[int(key)]
        else:
            if key not in current:
                current[key] = {}
            current = current[key]
    final_key = keys[-1]
    if final_key.isdigit():
        current[int(final_key)] = value
    else:
        current[final_key] = value


def main():
    parser = argparse.ArgumentParser(
        description="Create or modify Loopy Pro project files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clone and modify an existing project:
  python3 create_lpproj.py clone source.lpproj.zip output.lpproj.zip

  # Clone with modifications from JSON:
  python3 create_lpproj.py clone source.lpproj.zip output.lpproj.zip --mods modifications.json

  # Generate a blank template (requires schema from dissect):
  python3 create_lpproj.py template output.lpproj.zip --schema project_schema.json
        """
    )

    subparsers = parser.add_subparsers(dest="command")

    # Clone command
    clone_parser = subparsers.add_parser("clone", help="Clone and modify a project")
    clone_parser.add_argument("source", help="Source .lpproj.zip file")
    clone_parser.add_argument("output", help="Output .lpproj.zip file")
    clone_parser.add_argument("--mods", help="JSON file with modifications")

    # Template command
    template_parser = subparsers.add_parser("template", help="Create from schema template")
    template_parser.add_argument("output", help="Output .lpproj.zip file")
    template_parser.add_argument("--schema", required=True, help="Schema JSON from dissect")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\n⚠️  IMPORTANT: Run dissect_lpproj.py on a real Loopy Pro project first!")
        print("   This will reveal the actual file format and schema.")
        print("\n   Step 1: Get a .lpproj.zip file from:")
        print("     - Patchstorage: https://patchstorage.com/platform/loopy-pro/")
        print("     - Loopy Pro Wiki: https://wiki.loopypro.com/Category:Example")
        print("     - Export from Loopy Pro app on iOS/macOS")
        print("\n   Step 2: python3 dissect_lpproj.py your_project.lpproj.zip")
        print("\n   Step 3: Use the schema to create new projects:")
        print("     python3 create_lpproj.py clone source.lpproj.zip new.lpproj.zip")
        return

    builder = LoopyProProjectBuilder(
        schema_path=getattr(args, 'schema', None)
    )

    if args.command == "clone":
        mods = {}
        if args.mods:
            with open(args.mods, 'r') as f:
                mods = json.load(f)
        builder.clone_and_modify(args.source, args.output, mods)

    elif args.command == "template":
        builder.from_schema()


if __name__ == "__main__":
    main()
