#!/usr/bin/env python3
"""
Loopy Pro Project File Dissector
=================================

Loopy Pro (.lpproj.zip) files are ZIP archives containing a project bundle.
This script extracts and analyzes the internal structure to reverse-engineer
the schema.

Usage:
    python3 dissect_lpproj.py <path_to_file.lpproj.zip>
    python3 dissect_lpproj.py <path_to_file.lpproj>

If you have a .lpproj file that isn't a zip (it's a directory/bundle on macOS),
point this script at the directory and it will analyze it directly.

Where to get sample files:
    - Patchstorage: https://patchstorage.com/platform/loopy-pro/
    - Loopy Pro Wiki: https://wiki.loopypro.com/Category:Example
    - Simple Looper Tutorials: https://wiki.loopypro.com/Simple_Looper_Tutorial_Projects
    - Sample Projects 2.0: https://wiki.loopypro.com/Sample_Projects_2.0
    - In-app: Loopy Pro ships with built-in sample projects
    - On-device: ~/Documents/Loopy Pro/ (iOS Files app)
"""

import sys
import os
import json
import zipfile
import plistlib
import struct
import hashlib
from pathlib import Path
from collections import defaultdict


def analyze_binary_data(data: bytes, name: str) -> dict:
    """Analyze a binary blob and try to identify its format."""
    info = {
        "size_bytes": len(data),
        "md5": hashlib.md5(data).hexdigest()[:12],
    }

    if len(data) == 0:
        info["format"] = "empty"
        return info

    # Check magic bytes
    magic = data[:8]

    # Binary plist
    if data[:6] == b'bplist':
        info["format"] = "binary_plist"
        try:
            parsed = plistlib.loads(data)
            info["plist_type"] = type(parsed).__name__
            if isinstance(parsed, dict):
                info["top_level_keys"] = sorted(parsed.keys())
                info["content"] = summarize_plist(parsed)
            elif isinstance(parsed, list):
                info["list_length"] = len(parsed)
                if parsed:
                    info["first_item_type"] = type(parsed[0]).__name__
            else:
                info["value_preview"] = repr(parsed)[:200]
        except Exception as e:
            info["parse_error"] = str(e)
        return info

    # XML plist
    if data[:5] == b'<?xml' or b'<!DOCTYPE plist' in data[:200]:
        info["format"] = "xml_plist"
        try:
            parsed = plistlib.loads(data)
            info["plist_type"] = type(parsed).__name__
            if isinstance(parsed, dict):
                info["top_level_keys"] = sorted(parsed.keys())
                info["content"] = summarize_plist(parsed)
        except Exception as e:
            info["parse_error"] = str(e)
        return info

    # JSON
    if data[:1] in (b'{', b'['):
        try:
            parsed = json.loads(data)
            info["format"] = "json"
            info["json_type"] = type(parsed).__name__
            if isinstance(parsed, dict):
                info["top_level_keys"] = sorted(parsed.keys())
                info["content"] = summarize_json(parsed)
            elif isinstance(parsed, list):
                info["list_length"] = len(parsed)
            return info
        except json.JSONDecodeError:
            pass

    # ZIP
    if data[:2] == b'PK':
        info["format"] = "zip_archive"
        return info

    # WAV
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        info["format"] = "wav_audio"
        info.update(parse_wav_header(data))
        return info

    # CAF (Core Audio Format)
    if data[:4] == b'caff':
        info["format"] = "caf_audio"
        return info

    # AIFF
    if data[:4] == b'FORM' and data[8:12] in (b'AIFF', b'AIFC'):
        info["format"] = "aiff_audio"
        return info

    # MIDI
    if data[:4] == b'MThd':
        info["format"] = "midi"
        return info

    # PNG
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        info["format"] = "png_image"
        return info

    # JPEG
    if data[:2] == b'\xff\xd8':
        info["format"] = "jpeg_image"
        return info

    # SQLite
    if data[:16] == b'SQLite format 3\x00':
        info["format"] = "sqlite_database"
        return info

    # NSKeyedArchiver (often starts with bplist but check $archiver key)
    if info.get("format") == "binary_plist":
        content = info.get("content", {})
        if "$archiver" in info.get("top_level_keys", []):
            info["format"] = "nskeyedarchiver_plist"

    info["format"] = "unknown_binary"
    info["magic_hex"] = data[:16].hex()
    info["magic_ascii"] = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[:16])
    return info


def parse_wav_header(data: bytes) -> dict:
    """Parse basic WAV header info."""
    try:
        if len(data) < 44:
            return {}
        channels = struct.unpack_from('<H', data, 22)[0]
        sample_rate = struct.unpack_from('<I', data, 24)[0]
        bits_per_sample = struct.unpack_from('<H', data, 34)[0]
        data_size = struct.unpack_from('<I', data, 4)[0]
        duration = data_size / (sample_rate * channels * bits_per_sample / 8) if sample_rate else 0
        return {
            "channels": channels,
            "sample_rate": sample_rate,
            "bits_per_sample": bits_per_sample,
            "duration_seconds": round(duration, 2),
        }
    except Exception:
        return {}


def summarize_plist(obj, depth=0, max_depth=4) -> any:
    """Recursively summarize a plist object for readable output."""
    if depth > max_depth:
        return f"<truncated at depth {max_depth}>"

    if isinstance(obj, dict):
        result = {}
        for k, v in sorted(obj.items()):
            result[k] = summarize_plist(v, depth + 1, max_depth)
        return result
    elif isinstance(obj, list):
        if len(obj) == 0:
            return []
        if len(obj) <= 5:
            return [summarize_plist(item, depth + 1, max_depth) for item in obj]
        return [
            summarize_plist(obj[0], depth + 1, max_depth),
            f"... ({len(obj)} items total)",
            summarize_plist(obj[-1], depth + 1, max_depth),
        ]
    elif isinstance(obj, bytes):
        return f"<bytes: {len(obj)} bytes>"
    elif isinstance(obj, (int, float, bool, str)):
        s = repr(obj)
        return s if len(s) <= 200 else s[:200] + "..."
    else:
        return f"<{type(obj).__name__}>"


def summarize_json(obj, depth=0, max_depth=4) -> any:
    """Recursively summarize a JSON object for readable output."""
    if depth > max_depth:
        return f"<truncated at depth {max_depth}>"

    if isinstance(obj, dict):
        result = {}
        for k, v in sorted(obj.items()):
            result[k] = summarize_json(v, depth + 1, max_depth)
        return result
    elif isinstance(obj, list):
        if len(obj) == 0:
            return []
        if len(obj) <= 3:
            return [summarize_json(item, depth + 1, max_depth) for item in obj]
        return [
            summarize_json(obj[0], depth + 1, max_depth),
            f"... ({len(obj)} items total)",
            summarize_json(obj[-1], depth + 1, max_depth),
        ]
    elif isinstance(obj, str):
        return obj if len(obj) <= 200 else obj[:200] + "..."
    else:
        return obj


def dissect_zip(zip_path: str) -> dict:
    """Dissect a .lpproj.zip file."""
    result = {
        "source_file": os.path.basename(zip_path),
        "source_size_bytes": os.path.getsize(zip_path),
        "file_tree": [],
        "file_analysis": {},
        "summary": {},
    }

    extensions = defaultdict(int)
    formats = defaultdict(int)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            entry = {
                "path": info.filename,
                "compressed_size": info.compress_size,
                "uncompressed_size": info.file_size,
                "is_dir": info.is_dir(),
            }
            result["file_tree"].append(entry)

            if not info.is_dir() and info.file_size > 0:
                ext = Path(info.filename).suffix.lower()
                extensions[ext] += 1

                data = zf.read(info.filename)
                analysis = analyze_binary_data(data, info.filename)
                result["file_analysis"][info.filename] = analysis
                formats[analysis.get("format", "unknown")] += 1

    result["summary"] = {
        "total_files": sum(1 for f in result["file_tree"] if not f["is_dir"]),
        "total_dirs": sum(1 for f in result["file_tree"] if f["is_dir"]),
        "extensions": dict(extensions),
        "detected_formats": dict(formats),
        "total_uncompressed_bytes": sum(f["uncompressed_size"] for f in result["file_tree"]),
    }

    return result


def dissect_directory(dir_path: str) -> dict:
    """Dissect a .lpproj directory/bundle."""
    result = {
        "source_dir": os.path.basename(dir_path),
        "file_tree": [],
        "file_analysis": {},
        "summary": {},
    }

    extensions = defaultdict(int)
    formats = defaultdict(int)

    for root, dirs, files in os.walk(dir_path):
        for d in sorted(dirs):
            rel = os.path.relpath(os.path.join(root, d), dir_path)
            result["file_tree"].append({
                "path": rel + "/",
                "is_dir": True,
            })

        for f in sorted(files):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, dir_path)
            size = os.path.getsize(full)

            entry = {
                "path": rel,
                "size": size,
                "is_dir": False,
            }
            result["file_tree"].append(entry)

            ext = Path(f).suffix.lower()
            extensions[ext] += 1

            if size > 0 and size < 100_000_000:  # Skip files > 100MB
                with open(full, 'rb') as fh:
                    data = fh.read()
                analysis = analyze_binary_data(data, f)
                result["file_analysis"][rel] = analysis
                formats[analysis.get("format", "unknown")] += 1

    result["summary"] = {
        "total_files": sum(1 for f in result["file_tree"] if not f["is_dir"]),
        "total_dirs": sum(1 for f in result["file_tree"] if f["is_dir"]),
        "extensions": dict(extensions),
        "detected_formats": dict(formats),
    }

    return result


def print_tree(file_tree: list):
    """Print a tree view of the file structure."""
    print("\n" + "=" * 60)
    print("FILE TREE")
    print("=" * 60)
    for entry in file_tree:
        path = entry["path"]
        if entry["is_dir"]:
            print(f"  📁 {path}")
        else:
            size = entry.get("uncompressed_size") or entry.get("size", 0)
            if size > 1_000_000:
                size_str = f"{size / 1_000_000:.1f} MB"
            elif size > 1000:
                size_str = f"{size / 1000:.1f} KB"
            else:
                size_str = f"{size} B"
            print(f"  📄 {path}  ({size_str})")


def print_analysis(file_analysis: dict):
    """Print detailed analysis of each file."""
    print("\n" + "=" * 60)
    print("FILE ANALYSIS")
    print("=" * 60)

    for path, analysis in sorted(file_analysis.items()):
        print(f"\n--- {path} ---")
        fmt = analysis.get("format", "unknown")
        print(f"  Format: {fmt}")
        print(f"  Size: {analysis.get('size_bytes', 0)} bytes")

        if fmt in ("binary_plist", "xml_plist", "nskeyedarchiver_plist"):
            if "top_level_keys" in analysis:
                print(f"  Top-level keys: {analysis['top_level_keys']}")
            if "content" in analysis:
                print(f"  Content preview:")
                print(json.dumps(analysis["content"], indent=4, default=str)[:3000])

        elif fmt == "json":
            if "top_level_keys" in analysis:
                print(f"  Top-level keys: {analysis['top_level_keys']}")
            if "content" in analysis:
                print(f"  Content preview:")
                print(json.dumps(analysis["content"], indent=4, default=str)[:3000])

        elif fmt == "wav_audio":
            for k in ("channels", "sample_rate", "bits_per_sample", "duration_seconds"):
                if k in analysis:
                    print(f"  {k}: {analysis[k]}")

        elif fmt == "unknown_binary":
            print(f"  Magic (hex): {analysis.get('magic_hex', '')}")
            print(f"  Magic (ascii): {analysis.get('magic_ascii', '')}")


def extract_schema(file_analysis: dict) -> dict:
    """Extract a generalized schema from the analyzed files."""
    schema = {
        "description": "Loopy Pro Project File Schema (reverse-engineered)",
        "container_format": "zip",
        "file_extension": ".lpproj.zip",
        "structure": {},
    }

    for path, analysis in sorted(file_analysis.items()):
        fmt = analysis.get("format", "unknown")
        entry = {
            "format": fmt,
            "size_bytes": analysis.get("size_bytes", 0),
        }

        if fmt in ("binary_plist", "xml_plist", "json"):
            if "top_level_keys" in analysis:
                entry["keys"] = analysis["top_level_keys"]
            if "content" in analysis:
                entry["schema"] = infer_types(analysis["content"])

        elif fmt in ("wav_audio", "caf_audio", "aiff_audio"):
            for k in ("channels", "sample_rate", "bits_per_sample"):
                if k in analysis:
                    entry[k] = analysis[k]

        schema["structure"][path] = entry

    return schema


def infer_types(obj, depth=0, max_depth=3) -> any:
    """Infer types from a summarized object to create a schema."""
    if depth > max_depth:
        return "<...>"
    if isinstance(obj, dict):
        return {k: infer_types(v, depth + 1) for k, v in obj.items()}
    elif isinstance(obj, list):
        if not obj:
            return "Array<empty>"
        return [infer_types(obj[0], depth + 1)]
    elif isinstance(obj, bool):
        return "Boolean"
    elif isinstance(obj, int):
        return f"Integer (example: {obj})"
    elif isinstance(obj, float):
        return f"Float (example: {obj})"
    elif isinstance(obj, str):
        if obj.startswith("<bytes:"):
            return "Data (binary)"
        if obj.startswith("<truncated"):
            return "<nested object>"
        if len(obj) > 100:
            return f"String (example: {obj[:80]}...)"
        return f"String (example: {obj})"
    else:
        return str(type(obj).__name__)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: Please provide a path to a .lpproj.zip file or .lpproj directory")
        sys.exit(1)

    path = sys.argv[1]

    if not os.path.exists(path):
        print(f"Error: {path} does not exist")
        sys.exit(1)

    # Determine if it's a zip or directory
    if os.path.isdir(path):
        print(f"Analyzing directory: {path}")
        result = dissect_directory(path)
    elif zipfile.is_zipfile(path):
        print(f"Analyzing ZIP file: {path}")
        result = dissect_zip(path)
    else:
        # Maybe it's a renamed zip
        print(f"Warning: {path} is not a recognized format. Trying as zip...")
        try:
            result = dissect_zip(path)
        except zipfile.BadZipFile:
            print(f"Error: {path} is not a valid ZIP file or directory.")
            print("Loopy Pro project files (.lpproj.zip) are ZIP archives.")
            print("If you have a .lpproj that's a macOS bundle/package, it's a directory - point to it directly.")
            sys.exit(1)

    # Print results
    print_tree(result["file_tree"])

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(json.dumps(result["summary"], indent=2))

    print_analysis(result["file_analysis"])

    # Extract and print schema
    schema = extract_schema(result["file_analysis"])
    schema_path = os.path.splitext(os.path.splitext(path)[0])[0] + "_schema.json"
    # Use a default path if input is a dir
    if os.path.isdir(path):
        schema_path = path.rstrip('/') + "_schema.json"

    with open(schema_path, 'w') as f:
        json.dump(schema, f, indent=2, default=str)
    print(f"\n✅ Schema written to: {schema_path}")

    # Also write full analysis
    analysis_path = os.path.splitext(schema_path)[0] + "_full_analysis.json"
    with open(analysis_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"✅ Full analysis written to: {analysis_path}")


if __name__ == "__main__":
    main()
