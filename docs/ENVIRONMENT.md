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

| Tool | Version | Where |
|---|---|---|
| **Java (Temurin JDK)** | `21.0.12` | `~/Library/Java/JavaVirtualMachines/jdk-21.0.12+8/Contents/Home` |
| **Android SDK** | platform-tools (adb 1.0.41), platform 34, build-tools 34.0.0 | `~/Android/sdk` |
| **Android debug keystore** | generated 8 Aug 2026 | `~/.android/debug.keystore` |

Both Java and the Android SDK live **inside your home folder**, installed without any
administrator involvement. See the setup section at the end for exactly how.

## Not installed

| Missing | Consequence | Plan |
|---|---|---|
| **Administrator access to this Mac** | No iPhone build of any kind is possible. | **Blocking the Phase 0 test.** See below. |
| **`gh`** (GitHub command-line tool) | None. The repository and remote already exist. | Not needed. |

### Android works today

A signed Android app was produced on 8 August 2026 and checked against the requirements in
the master plan:

| Requirement | Actual | |
|---|---|---|
| Minimum Android version 24 | `sdkVersion:'24'` | ✅ |
| 64-bit only, no 32-bit | `arm64-v8a` and nothing else | ✅ |
| Named and versioned correctly | `com.wastemarch.game`, `0.1.0` | ✅ |

These were read out of the finished app rather than assumed from the settings:

```bash
~/Android/sdk/build-tools/34.0.0/aapt2 dump badging Wastemarch.apk
```

**One problem found doing this, worth knowing about.** The app contained the Rust simulation
as a **zero-byte file** — the export reported success while quietly including nothing, because
the simulation had never been compiled for phone processors. The app would have started and
drawn the cube, and the simulation simply would not have been there.

The lesson is recorded: always check the *size* of what ends up inside the app, not just that
the name is present. The fix, in progress, is the Android NDK — the toolkit that compiles code
for phone processors.

### iOS — blocked on one admin password, and nothing else

**Investigated in full on 8 August 2026. This section is the conclusion; do not re-derive it.**

Xcode 26.3 is installed and the iOS SDK 26.2 is present. What is missing is Xcode's
*first-launch components*, which live in `/Library/Developer/PrivateFrameworks/` and can only
be installed by an administrator:

| Component | Present? | Needed for |
|---|---|---|
| iOS SDK 26.2, iPhoneOS platform | ✅ yes | compiling |
| `CoreDevice.framework` | ❌ **absent** | installing onto a physical iPhone |
| `CoreSimulator.framework` | ❌ **absent** | the iOS Simulator — **and `xcodebuild` itself** |

That last row is the one that decides everything. `xcodebuild` refuses to start at all without
`CoreSimulator`, even for a device-only build with signing switched off:

```
xcodebuild failed to load a required plug-in.
Ensure your system frameworks are up-to-date by running 'xcodebuild -runFirstLaunch'
```

**So there is no iOS build of any kind — device, simulator, or App Store upload — without
one administrator action.**

#### Do not buy the Developer Program hoping to avoid this

The £/$99-a-year programme with TestFlight looks like a way around needing admin on this Mac,
since TestFlight installs over the air. **It is not.** Uploading to TestFlight still requires
building an `.ipa` first, and building requires `xcodebuild`, which is exactly what is
blocked. The money would buy nothing until the admin step happens anyway.

#### The fix — one command, once

Whoever has administrator rights on this Mac runs:

```bash
sudo xcodebuild -runFirstLaunch
```

Equivalently, they open Xcode once and click through the "install additional components"
prompt. It takes a couple of minutes and never needs repeating.

**After that, a free Apple ID is enough.** Xcode → Settings → Accounts → + → sign in creates
a "Personal Team" that installs on your own devices. Those builds expire after seven days and
are simply reinstalled. The paid programme is a Phase 8 concern.

#### What is already proven to work without admin

Godot generated the complete iOS Xcode project, both device and simulator frameworks, MoltenVK
and the packed game data — all of it, no admin required. The export stopped only on missing
app icons, which is ordinary work rather than a permissions wall.

So the whole chain up to the point where Apple's tooling takes over is sound.

### Android needs no administrator at all

Every part of the Android toolchain installs inside your home folder. `$HOME` and
`~/.local/bin` are both writable; only `/usr/local/bin` is not, which is why Homebrew fails
and why the instructions below deliberately avoid it.

This makes Android the route that can make progress today. See the setup section at the end.

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

## Installing the Android toolchain — no administrator needed

**Do not use Homebrew for this.** Its `--cask` installers write to `/usr/local`, which is
root-owned on this Mac and will fail. Everything below installs into your home folder
instead, which needs no special permission.

The engineer can run all of this. It is written out so you can see what it does.

```bash
# 1. Java, unpacked into your home folder rather than installed system-wide.
mkdir -p ~/Library/Java/JavaVirtualMachines
cd ~/Downloads
curl -LO https://api.adoptium.net/v3/binary/latest/21/ga/mac/aarch64/jdk/hotspot/normal/eclipse
tar xzf eclipse -C ~/Library/Java/JavaVirtualMachines
export JAVA_HOME=~/Library/Java/JavaVirtualMachines/*/Contents/Home

# 2. The Android command-line tools, likewise.
mkdir -p ~/Android/sdk/cmdline-tools
cd ~/Downloads
curl -LO https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip
unzip -q commandlinetools-mac-11076708_latest.zip -d ~/Android/sdk/cmdline-tools
mv ~/Android/sdk/cmdline-tools/cmdline-tools ~/Android/sdk/cmdline-tools/latest

# 3. The pieces Godot actually needs.
export ANDROID_HOME=~/Android/sdk
~/Android/sdk/cmdline-tools/latest/bin/sdkmanager --sdk_root=$ANDROID_HOME \
  "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

Then in Godot: **Editor → Editor Settings → Export → Android**, set the SDK path to
`~/Android/sdk` and the Java path to the folder from step 1, and click the button that
generates a debug keystore.

A **keystore** is the file that signs your app so Android will accept it as genuinely yours.
The debug one is for testing on your own phone and nothing else.

Finally, on the phone: **Settings → About → tap "Build number" seven times**, then
**Developer options → USB debugging**. Plug it in and `~/Android/sdk/platform-tools/adb
devices` should list it.

### The emulated phone — a Pixel 6a with no Pixel 6a

An **emulator** is a complete Android phone running as a program on the Mac. Because this Mac
has an ARM processor and so do phones, the emulator runs the *real* phone build of our code,
not a translated version. That makes it trustworthy for anything about correctness, and
worthless for anything about speed. Installed 8 August 2026, no administrator needed:

```bash
export JAVA_HOME=~/Library/Java/JavaVirtualMachines/jdk-21.0.12+8/Contents/Home
~/Android/sdk/cmdline-tools/latest/bin/sdkmanager \
  "emulator" "system-images;android-34;default;arm64-v8a"     # about 1.6 GB

~/Android/sdk/cmdline-tools/latest/bin/avdmanager create avd \
  -n wastemarch_p6a -k "system-images;android-34;default;arm64-v8a" -d pixel_6a
```

Then edit `~/.android/avd/wastemarch_p6a.avd/config.ini` so it ends with these four lines —
the file may already contain older copies of them, and **duplicates must be deleted**, not
left below the originals:

```ini
hw.gpu.enabled=yes
hw.gpu.mode=host
hw.ramSize=4096
hw.initialOrientation=landscape
```

Start it with `~/Android/sdk/emulator/emulator -avd wastemarch_p6a -no-snapshot -no-boot-anim`.
`docs/TESTING.md` check 6 covers what to do next.

**Two things it cannot tell you.** Frame rate, because it borrows the Mac's graphics card. And
anything visual, because a screenshot of a 3D Godot app on the emulator comes back black —
that is a limitation of the emulator's screenshot tool, not a sign the game failed to draw.

## Image generation — installed, and not what the master plan expected

`MASTER_PLAN.md` assumes **ComfyUI**. ComfyUI is **not installed**, and as of 8 August 2026 it
has not been needed, because a better-suited tool for this particular Mac was already here.

**mflux** is a command-line image generator built on Apple's MLX, so it runs natively on this
machine's graphics hardware rather than through a translation layer. It was installed for the
sibling `mentoros` project and it has direct support for both of the models Wastemarch is
allowed to use.

| | |
|---|---|
| Binaries | `~/.local/bin/mflux-*` (installed as a `uv` tool) |
| Model weights | `~/mentoros-imagegen/hf-cache` — 53 GB, shared, **not duplicated** |
| Generator | Z-Image Turbo, 4-bit, `filipstrand/Z-Image-Turbo-mflux-4bit` |
| Measured | 16 seconds per step at 1024x1024; 8 steps is about **2 minutes** per image |
| Peak memory | **10.7 GB** of the machine's 24 GB |

Because it peaks at 10.7 GB, nothing else heavy may run at the same time — see the note about
never running a generator and a Blender render together.

Run it through the pipeline script rather than by hand, so provenance is recorded:

```bash
python3 tools/pipeline/concept.py --list
python3 tools/pipeline/concept.py keep --seeds 4
```

### Three things that will waste your time otherwise

**Name the model explicitly.** `mflux-generate-z-image-turbo` on its own defaults to the
full-size original of Z-Image Turbo, which is *not* in the cache. It then tries to download
about 16 GB — silently, with no progress shown, for twenty minutes. Always pass
`--model filipstrand/Z-Image-Turbo-mflux-4bit --base-model z-image-turbo`. The pipeline script
does this for you.

**Set the cache location and go offline.** `HF_HOME=~/mentoros-imagegen/hf-cache` and
`HF_HUB_OFFLINE=1`. Without the second one, the tool contacts Hugging Face to check for
updates even when everything it needs is already on disk, and that call can hang.

**Licence-blocked models are sitting in the same cache.** FLUX Kontext is there for the other
project, and `CLAUDE.md` forbids it here because its licence is non-commercial. One mistyped
flag would use it. `tools/pipeline/concept.py` therefore refuses to run any model that is not
on the permitted list, rather than trusting nobody will mistype.

### What is still open

`MASTER_PLAN.md` stage 3 generates textures conditioned on depth and normal maps baked from
the 3D model. mflux can do that conditioning for FLUX models but **not** for Z-Image or
Qwen-Image-Edit. So ComfyUI may still be needed when stage 3 is built. It is not needed now,
and installing it before it is needed would be work with no result.

---

### If you would rather fix Homebrew properly

One administrator command makes every future `brew install` work normally:

```bash
sudo chown -R $(whoami) /usr/local/bin
```

Not required for anything above.
