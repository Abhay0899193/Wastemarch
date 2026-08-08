#!/usr/bin/env python3
"""Stage 1 of the asset pipeline — concept art, reproducibly.

    python3 tools/pipeline/concept.py granary
    python3 tools/pipeline/concept.py granary --seeds 4
    python3 tools/pipeline/concept.py --list

Reads `prompts/style.md` plus `prompts/buildings/<id>.md`, joins them, runs
Z-Image Turbo, and writes the image next to a provenance record.

**Why the provenance record exists.** `CLAUDE.md` requires every generated asset
to record its model, prompt, seed and workflow hash. Two reasons, both real:

  * Reproducibility. An image you cannot regenerate is an image you cannot fix.
  * Provenance. If anyone ever asks how an asset in a shipped game was made,
    the answer is a file, not a memory.

The *workflow hash* covers the joined prompt and every generation parameter. If
it changes, the picture would change, so two images with the same hash and seed
are the same picture and two with different hashes are not comparable.

Only Apache-2.0 licensed models are permitted — see `CLAUDE.md`. This script
refuses to run anything else, because the blocked models happen to be sitting in
the same cache one flag away.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PROMPTS = HERE / "prompts"
OUT_ROOT = REPO / "assets-src" / "concept"
PROVENANCE = HERE / "provenance.json"

# The generator. Apache 2.0, and the 4-bit conversion of it that is actually
# cached on this machine. See docs/ENVIRONMENT.md.
#
# `mflux-generate-z-image-turbo` defaults to the full-precision upstream repo,
# which is NOT cached and which it will try to download — silently, for tens of
# minutes. Naming the model explicitly is not optional.
MODEL_REPO = "filipstrand/Z-Image-Turbo-mflux-4bit"
BASE_MODEL = "z-image-turbo"
BINARY = Path.home() / ".local/bin/mflux-generate-z-image-turbo"

# Licence gate. CLAUDE.md permits Z-Image Turbo, Qwen-Image-Edit-2509, Kokoro
# and Chatterbox, and hard-blocks Flux Kontext and XTTS-v2 as non-commercial.
# The Kontext weights ARE in this machine's model cache, for a different
# project. Never let a typo reach them.
ALLOWED_MODEL_SUBSTRINGS = ("z-image", "qwen-image-edit")
BLOCKED_MODEL_SUBSTRINGS = ("kontext", "xtts", "flux.1-dev", "flux.1-schnell")

DEFAULTS = {
    "steps": 8,          # Turbo. More is not better; it is just slower.
    "width": 1024,
    "height": 1024,
}


def model_is_permitted(repo: str) -> tuple[bool, str]:
    low = repo.lower()
    for bad in BLOCKED_MODEL_SUBSTRINGS:
        if bad in low:
            return False, f"'{bad}' is licence-blocked for commercial use (CLAUDE.md)"
    if not any(ok in low for ok in ALLOWED_MODEL_SUBSTRINGS):
        return False, "not on the permitted list in CLAUDE.md"
    return True, ""


def style_prompt() -> str:
    """The shared header, which is everything below the `---` line."""
    text = (PROMPTS / "style.md").read_text()
    _, _, body = text.partition("\n---\n")
    return " ".join(body.split())


def asset_prompt(asset_id: str) -> str:
    path = PROMPTS / "buildings" / f"{asset_id}.md"
    if not path.exists():
        sys.exit(f"No prompt file for '{asset_id}'. Expected {path}\n"
                 f"Known assets: {', '.join(known_assets()) or '(none yet)'}")
    text = path.read_text()
    _, _, body = text.partition("\n---\n")
    return " ".join((body or text).split())


def known_assets() -> list[str]:
    d = PROMPTS / "buildings"
    return sorted(p.stem for p in d.glob("*.md")) if d.exists() else []


def workflow_hash(prompt: str, params: dict) -> str:
    """One value covering everything that decides what the picture looks like.

    Deliberately excludes the seed: the point is to identify the *recipe*, so
    that several seeds of one recipe are recognisably siblings.
    """
    payload = json.dumps({"prompt": prompt, "model": MODEL_REPO, **params},
                         sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def record(entry: dict) -> None:
    existing = json.loads(PROVENANCE.read_text()) if PROVENANCE.exists() else []
    existing.append(entry)
    PROVENANCE.write_text(json.dumps(existing, indent=2) + "\n")


def generate(asset_id: str, seed: int, params: dict, prompt: str) -> Path:
    out_dir = OUT_ROOT / asset_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{asset_id}_{seed}.png"

    env = os.environ.copy()
    # The weights live in the sibling project's cache, which is 53 GB and is
    # deliberately not duplicated. Offline mode is what stops the hub from
    # hanging for twenty minutes trying to reach a repo that is already here.
    env.setdefault("HF_HOME", str(Path.home() / "mentoros-imagegen" / "hf-cache"))
    env["HF_HUB_DISABLE_XET"] = "1"
    env["HF_HUB_OFFLINE"] = "1"

    cmd = [
        str(BINARY),
        "--model", MODEL_REPO,
        "--base-model", BASE_MODEL,
        "--prompt", prompt,
        "--seed", str(seed),
        "--steps", str(params["steps"]),
        "--width", str(params["width"]),
        "--height", str(params["height"]),
        "--output", str(out),
    ]

    started = time.time()
    result = subprocess.run(cmd, env=env)
    took = time.time() - started

    if result.returncode != 0 or not out.exists():
        sys.exit(f"Generation failed for {asset_id} seed {seed}.")

    record({
        "asset": asset_id,
        "file": str(out.relative_to(REPO)),
        "model": MODEL_REPO,
        "base_model": BASE_MODEL,
        "seed": seed,
        "workflow_hash": workflow_hash(prompt, params),
        "prompt": prompt,
        "params": params,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "seconds": round(took, 1),
    })
    print(f"  {out.relative_to(REPO)}  ({took:.0f}s)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asset", nargs="?", help="asset id, e.g. granary")
    ap.add_argument("--seeds", type=int, default=1,
                    help="how many seeds to try (default 1)")
    ap.add_argument("--from-seed", type=int, default=1001)
    ap.add_argument("--steps", type=int, default=DEFAULTS["steps"])
    ap.add_argument("--list", action="store_true", help="list known assets and exit")
    args = ap.parse_args()

    if args.list or not args.asset:
        print("Assets with a prompt file:")
        for a in known_assets():
            print(f"  {a}")
        return 0

    ok, why = model_is_permitted(MODEL_REPO)
    if not ok:
        sys.exit(f"REFUSING: model '{MODEL_REPO}' — {why}")

    if not BINARY.exists():
        sys.exit(f"{BINARY} not found. See docs/ENVIRONMENT.md, 'Image generation'.")

    params = {**DEFAULTS, "steps": args.steps}
    prompt = f"{style_prompt()} {asset_prompt(args.asset)}"

    print(f"{args.asset}: {args.seeds} seed(s), recipe {workflow_hash(prompt, params)}")
    for i in range(args.seeds):
        generate(args.asset, args.from_seed + i, params, prompt)

    print(f"\nProvenance appended to {PROVENANCE.relative_to(REPO)}")
    print("Pick the best, then commit it. Rejects stay uncommitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
