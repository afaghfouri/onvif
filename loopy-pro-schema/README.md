# Loopy Pro Project File Schema Tools

Reverse-engineer and create Loopy Pro (`.lpproj.zip`) project files.

## Background

[Loopy Pro](https://loopypro.com/) is a professional live looper, clip launcher, sequencer and DAW for iOS/macOS by [A Tasty Pixel](https://atastypixel.com/). Its project file format is **not publicly documented**.

### What We Know

| Property | Value |
|----------|-------|
| File extension | `.lpproj.zip` (shared/exported) or `.lpproj` (on-device bundle) |
| Container format | ZIP archive |
| Bundle ID | `com.atastypixel.loopy-pro` |
| On-device location | `~/Documents/Loopy Pro/` (visible in iOS Files app) |
| Audio format | Likely WAV or CAF (Core Audio Format) |
| Config format | Likely binary plist or JSON (common iOS patterns) |

## Step 1: Get a Sample Project File

Download a `.lpproj.zip` from any of these sources:

- **Patchstorage** (community templates): https://patchstorage.com/platform/loopy-pro/
- **Loopy Pro Wiki examples**: https://wiki.loopypro.com/Category:Example
- **Simple Looper Tutorials**: https://wiki.loopypro.com/Simple_Looper_Tutorial_Projects
- **Sample Projects 2.0**: https://wiki.loopypro.com/Sample_Projects_2.0
- **User-Created Templates**: https://wiki.loopypro.com/User-Created_Templates_and_Presets
- **Export from app**: In Loopy Pro, use the project manager to export/share a project

## Step 2: Dissect the File

```bash
python3 dissect_lpproj.py /path/to/your_project.lpproj.zip
```

This will:
1. Extract and list the complete file tree
2. Identify the format of every file (plist, JSON, WAV, CAF, images, etc.)
3. Parse and display the contents of all structured data files
4. Generate a `_schema.json` describing the project structure
5. Generate a `_full_analysis.json` with complete parsed contents

### If you have an on-device `.lpproj` directory (macOS bundle):
```bash
python3 dissect_lpproj.py /path/to/your_project.lpproj
```

## Step 3: Create New Projects

### Clone & Modify (recommended)

The safest way to create valid project files:

```bash
# Simple clone
python3 create_lpproj.py clone source.lpproj.zip new_project.lpproj.zip

# Clone with modifications
python3 create_lpproj.py clone source.lpproj.zip new.lpproj.zip --mods mods.json
```

Example `mods.json`:
```json
{
    "replace_files": {
        "project.lpproj/clips/track1.wav": "<path_to_your_wav>"
    },
    "modify_plist": {
        "project.lpproj/state.plist": {
            "tempo": 120.0,
            "timeSignature.numerator": 4
        }
    },
    "modify_json": {
        "project.lpproj/config.json": {
            "name": "My New Project"
        }
    },
    "remove_files": ["project.lpproj/clips/unused_track.wav"],
    "add_files": {
        "project.lpproj/clips/new_track.wav": "<will_be_bytes>"
    }
}
```

> **Note**: The exact file paths and key names above are **placeholders**.
> Run `dissect_lpproj.py` first to discover the actual paths and keys.

## File Format Details

After running the dissector, update this section with the actual discovered schema.

### Expected Structure (to be confirmed)

```
your_project.lpproj.zip
└── [project_name].lpproj/       # Bundle directory
    ├── [config file]             # Project state/configuration (plist or JSON)
    ├── [audio files]/            # Loop/clip audio data (WAV or CAF)
    │   ├── track_1.[wav|caf]
    │   ├── track_2.[wav|caf]
    │   └── ...
    ├── [UI state]                # Widget/page layout configuration
    ├── [plugin state]/           # Audio Unit extension saved states
    └── [thumbnails]/             # Preview images (optional)
```

## Requirements

- Python 3.7+
- No external dependencies (uses only stdlib: zipfile, plistlib, json, struct)

## Contributing

After you dissect your first project file, please update this README with the
actual schema you discover! The Loopy Pro community will benefit from documented
file format information.
