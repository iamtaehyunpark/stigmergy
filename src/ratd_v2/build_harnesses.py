"""Generate the four frozen ET harness variants from shared sources.

The fair-fight rule requires the harness CORE (tool docs + behavioral
guidance) to be byte-identical across arms, with arm-specific text
limited to the arm's surface, activation model, and role. Building the
variants by concatenation makes that property structural, and makes the
pre-registration diff exactly the role/surface files.

    python3 -m src.ratd_v2.build_harnesses [--dir prompts/et]
"""
from __future__ import annotations

import argparse
from pathlib import Path

VARIANTS = {
    "harness_ratd.md": ["role_ratd.md", "core.md", "surface_circuit.md"],
    "harness_planner.md": ["role_planner.md", "core.md", "surface_planner.md"],
    "harness_worker.md": ["role_worker.md", "core.md"],
    "harness_stig.md": ["role_stig.md", "core.md", "surface_circuit.md",
                        "surface_stig.md"],
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="prompts/et")
    args = parser.parse_args(argv)
    base = Path(args.dir)
    src = base / "src"
    for out_name, parts in VARIANTS.items():
        text = "\n".join((src / p).read_text(encoding="utf-8").strip()
                         for p in parts) + "\n"
        (base / out_name).write_text(text, encoding="utf-8")
        print(f"wrote {base / out_name} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
