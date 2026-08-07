# Environment — what is installed, where, and which version

**What this is.** This records the exact tools this project is built with on your Mac, the
exact versions, and the exact commands to run each one. Versions are pinned deliberately —
a different version of Godot or Blender can silently change how things build. If you ever
update one of these, update this file in the same sitting.

**Last verified:** 8 August 2026.

---

## The machine

| | |
|---|---|
| Model | Apple M4 Pro |
| Memory | 24 GB unified |
| Processor family | `arm64` (Apple Silicon) |
| Operating system | macOS (Darwin 25.0.0) |

24 GB is the number that shapes the whole art pipeline. See
[ASSET_PIPELINE.md](ASSET_PIPELINE.md) for what fits and what does not.

---

## Installed and verified

| Tool | Version | Where |
|---|---|---|
| **Godot** | `4.7.1.stable.official.a13da4feb` ✅ *matches target* | `/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot` |
| **Godot export templates** | `4.7.1.stable` — ✅ **complete**, all 35 files | `~/Library/Application Support/Godot/export_templates/4.7.1.stable/` |
| **Blender** | `5.2.0 LTS` (built 14 July 2026) | `/Users/singha7/Applications/Blender.app/Contents/MacOS/Blender` |
| **Rust** | `rustc 1.95.0` / `cargo 1.95.0` | `~/.cargo/bin/` |
| **Git** | `2.41.0` | `/usr/bin/git` |
| **Git LFS** | `3.7.1` | `~/.local/bin/git-lfs` — see the note below |
| **Xcode** | `26.3` (build 17C529) | `/Applications/Xcode.app` |
| **Python** | `3.14.1` | system |
| **Homebrew** | `6.0.13`, prefix `/usr/local` | `/usr/local/bin/brew` |

### Terms

- **Export templates** are pre-built copies of the Godot engine for each target platform.
  Without them Godot can edit the game but cannot produce an installable app.
- **Git LFS** ("Large File Storage") stores big binary files — 3D models, textures, audio —
  outside the normal history so the repository stays small and fast.
- **Homebrew** is a package installer for macOS.

---

## Not installed

| Missing | Consequence | Plan |
|---|---|---|
| **An Apple ID signed into Xcode** | Cannot build for iPhone at all. | **Blocking the Phase 0 test.** See below. |
| **Android SDK** | Cannot build an Android app at all. | Install when we are ready to put the game on an Android phone. Command below. |
| **Java runtime** | Required by the Android SDK. | Installed alongside it. |
| **`gh`** (GitHub command-line tool) | None. The repository and remote already exist. | Not needed. |

### iOS signing — the current blocker

Xcode 26.3 is installed but has **never been signed in**. There are no signing certificates,
no provisioning profiles, and no Apple ID configured:

```
$ security find-identity -v -p codesigning
     0 valid identities found
```

Godot therefore refuses to export for iPhone, with `App Store Team ID not specified`.

Apple will not let *anyone* install an app on *any* iPhone without an identity to sign it —
this is not a Godot limitation and there is no way around it.

**A free Apple ID is enough for now.** Signing in to Xcode with any Apple ID creates a
"Personal Team", which can install apps on your own devices. Those builds stop working after
seven days and have to be reinstalled, which is fine for development. The paid Developer
Program ($99/year) is only needed for TestFlight and the App Store, which is Phase 8.

To set it up: **Xcode → Settings → Accounts → + → Apple ID**, sign in. Then tell the
engineer, who will read the Team ID and put it into the export settings.

### Verified: the export chain itself works

To separate "the project cannot export" from "signing is not configured", a macOS build was
produced on 8 August 2026 with signing switched off. It built (a 177 MB app bundle), started,
and initialised the correct renderer:

```
Metal 4.0 - Forward Mobile - Using Device #0: Apple - Apple M4 Pro (Apple9)
```

So the project, the templates and the export pipeline are all sound. **The only thing
standing between here and an app on your iPhone is the Apple ID.**

Two things learned doing this, recorded so they do not cost time again:

- The macOS template contains **one universal binary**, not one per processor type. Asking
  the export for `arm64` fails with `Requested template binary "godot_macos_debug.arm64" not
  found`, which reads like a missing download but is not. The setting must say `universal`.
- An **exported** app ignores `--script`; it just runs the game. That option only works with
  the Godot editor binary.

---

## Two things that bit us, recorded so they do not bite again

### Homebrew cannot write to `/usr/local/bin`

`/usr/local/bin` on this Mac is owned by `root`, so `brew install` fails at the final step
where it creates the shortcut. Git LFS was therefore installed by downloading the official
release binary directly into `~/.local/bin`, which you own and which is already first on
your `PATH`. The download was checksum-verified against the published SHA-256.

**Consequence:** `git-lfs` will not update when you run `brew upgrade`. To update it, repeat
the download. It is a single self-contained file with no dependencies, so this is low-cost.

**If you would rather fix Homebrew properly**, run this once and future installs will work
normally:

```bash
sudo chown -R $(whoami) /usr/local/bin
```

### Blender is version 5.2, not 4.x

Most Blender scripting examples online are written for Blender 4.x, and several operations
were renamed or moved in 5.0. Every script in `tools/blender/` targets the **5.x** Python
interface. Copying a 4.x snippet without adapting it will fail.

---

## Commands

Set these once per terminal session:

```bash
export GODOT=/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot
export BLENDER=/Users/singha7/Applications/Blender.app/Contents/MacOS/Blender
```

### Open the game in the Godot editor

```bash
$GODOT --path game
```

### Import assets and check for errors, without opening a window

```bash
$GODOT --headless --path game --quit
```

**Headless** means "with no window and no graphics" — how a computer runs a task
unattended, and how our automated checks run.

### Run the simulation's tests

```bash
cd sim && cargo test --workspace
```

### Check that no decimal numbers have crept into the simulation

```bash
sh ci/no-floats.sh
```

Why this matters is explained in [ARCHITECTURE.md](ARCHITECTURE.md#the-important-idea-determinism).

### Build a 3D asset from its script, with no window

```bash
$BLENDER --background --factory-startup \
  --python tools/blender/build_asset.py -- --asset town_hall
```

`--factory-startup` means "ignore all my personal Blender settings and start clean." Without
it, a preference you changed months ago could quietly alter the output.

---

## Installing the Android toolchain, when we get there

Run these yourself, then tell the engineer it is done:

```bash
brew install --cask temurin                    # the Java runtime
brew install --cask android-commandlinetools   # the Android SDK
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0" \
           "cmdline-tools;latest" "ndk;23.2.8568313"
```

Then in Godot: **Editor → Editor Settings → Export → Android**, set the SDK path to
`/usr/local/share/android-commandlinetools`, and click the button to generate a debug
keystore. A **keystore** is the file that signs your app so Android will accept it as
genuinely yours. The debug one is for testing on your own phone only.

If Homebrew's permission problem above is still unfixed, these two `--cask` installs will
fail the same way. Run the `chown` command first.
