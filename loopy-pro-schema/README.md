# Loopy Pro Project File Schema Tools

Reverse-engineer and create Loopy Pro project files programmatically.

## Background

[Loopy Pro](https://loopypro.com/) is a professional live looper, clip launcher, sequencer and DAW for iOS/macOS by [A Tasty Pixel](https://atastypixel.com/). Its project file format is **not publicly documented**, so these tools help you reverse-engineer it.

### What We Know

| Property | Value |
|----------|-------|
| **Native format** | Apple document bundle (directory that appears as single file) |
| **Shared/exported as** | `.lpproj.zip` (zipped bundle for transfer) |
| **On-device location** | `On My iPad > Loopy Pro` or `On My iPhone > Loopy Pro` |
| **macOS inspection** | Right-click `.lpproj` -> "Show Package Contents" |
| **Bundle ID** | `com.atastypixel.loopy-pro` |
| **Config format** | XML metadata file(s) inside the bundle |
| **Audio format (default)** | AAC/M4A (compressed) |
| **Audio format (lossless)** | WAV or AIFF (when uncompressed setting enabled) |
| **Bundle contents** | Layout data, audio files, MIDI bindings, effect chains |
| **Related extensions** | `.lpsession` (Loopy HD sessions), `.lprecording` (recording bundles) |

### Key Insight

Loopy Pro projects are **NOT** single binary blobs. They are standard Apple document bundles - essentially directories containing:
1. **XML configuration file(s)** - layout, loop config, MIDI bindings, effect chains
2. **Audio files** - AAC/M4A (default compressed) or WAV/AIFF (uncompressed)
3. **Plugin state** - Audio Unit extension saved states

When shared online (Patchstorage, wiki, etc.), these bundles are simply zipped into `.lpproj.zip` files.

> **Warning**: Forum users report that manually altering the XML config file can corrupt the project. Proceed carefully when modifying.

## Step 1: Get a Sample Project File

Download a `.lpproj.zip` from any of these sources:

- **Patchstorage** (community templates): https://patchstorage.com/platform/loopy-pro/
- **Loopy Pro Wiki examples**: https://wiki.loopypro.com/Category:Example
- **Simple Looper Tutorials**: https://wiki.loopypro.com/Simple_Looper_Tutorial_Projects
- **Sample Projects 2.0**: https://wiki.loopypro.com/Sample_Projects_2.0
- **User-Created Templates**: https://wiki.loopypro.com/User-Created_Templates_and_Presets
- **Export from app**: In Loopy Pro, use the project manager to export/share a project
- **macOS**: Right-click any project in Finder -> "Show Package Contents" to browse directly

### On-device access (iOS)

On iOS, you can browse project bundles using third-party file browsers like **WaveBox** that support showing package contents (the iOS Files app does not expose this).

## Step 2: Dissect the File

```bash
# From a downloaded zip
python3 dissect_lpproj.py /path/to/your_project.lpproj.zip

# From a macOS bundle directory
python3 dissect_lpproj.py /path/to/your_project.lpproj

# From a Loopy HD session
python3 dissect_lpproj.py /path/to/session.lpsession
```

This will:
1. Extract and list the complete file tree
2. Identify every file's format (XML, plist, JSON, AAC/M4A, WAV, CAF, images, etc.)
3. Parse and display contents of all structured data files (XML, plist, JSON)
4. Generate a `_schema.json` describing the project structure
5. Generate a `_full_analysis.json` with complete parsed contents

### Example Output

```
============================================================
FILE TREE
============================================================
  config.xml              (12.4 KB)   <- XML project configuration
  clips/
    track_1.m4a           (245.3 KB)  <- AAC audio (default format)
    track_2.m4a           (189.7 KB)
  plugins/
    reverb_state.plist    (2.1 KB)    <- Audio Unit saved state

============================================================
FILE ANALYSIS
============================================================
--- config.xml ---
  Format: xml
  Root tag: project
  Child tags: [tempo, timeSignature, tracks, pages, midiBindings, ...]
```

*(Actual structure will be revealed when you run this on a real file)*

## Step 3: Create New Projects

### Clone & Modify (recommended, safest approach)

```bash
# Simple clone
python3 create_lpproj.py clone source.lpproj.zip new_project.lpproj.zip

# Clone with modifications
python3 create_lpproj.py clone source.lpproj.zip new.lpproj.zip --mods mods.json
```

Example `mods.json` (update paths/keys after running dissector):
```json
{
    "replace_files": {
        "project.lpproj/clips/track1.m4a": "<path_to_your_audio>"
    },
    "modify_plist": {
        "project.lpproj/plugin_state.plist": {
            "volume": 0.75
        }
    },
    "remove_files": ["project.lpproj/clips/unused_track.m4a"],
    "add_files": {
        "project.lpproj/clips/new_track.wav": "<will_be_bytes>"
    }
}
```

> **Note**: The exact file paths and key names above are **placeholders**.
> Run `dissect_lpproj.py` first to discover the actual paths and keys used in your project.

## Detected Formats

The dissector recognizes:

| Format | Detection |
|--------|-----------|
| Binary plist | `bplist` magic bytes |
| XML plist | `<?xml` + DOCTYPE plist |
| Generic XML | `<?xml` (non-plist) |
| JSON | Starts with `{` or `[` |
| AAC/M4A/MP4 | `ftyp` box at offset 4 |
| WAV | `RIFF`...`WAVE` |
| CAF | `caff` magic |
| AIFF | `FORM`...`AIFF` |
| MIDI | `MThd` magic |
| PNG | PNG magic bytes |
| JPEG | `\xff\xd8` magic |
| SQLite | `SQLite format 3` |
| NSKeyedArchiver | Binary plist with `$archiver` key |

## Requirements

- Python 3.7+
- No external dependencies (uses only stdlib: zipfile, plistlib, json, struct, xml.etree)

## Contributing

After you dissect your first real project file, please share your findings!
The Loopy Pro community would benefit greatly from documented file format information.
Consider posting your `_schema.json` output.
