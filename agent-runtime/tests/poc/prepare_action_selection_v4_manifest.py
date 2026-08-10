from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from tests.poc.contracts import build_action_poc_manifest, write_append_only_manifest


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an append-only action-selection-v4 PoC manifest.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repository_root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    try:
        output.relative_to(repository_root)
    except ValueError as exc:
        raise SystemExit("poc.manifest_output_outside_repository") from exc
    manifest = build_action_poc_manifest(
        repository_root=repository_root,
        run_id=args.run_id,
        created_at_utc=_utc_now(),
        authorization_reference=args.authorization_reference,
    )
    digest = write_append_only_manifest(manifest, path=output)
    print(f"run_id={manifest.run_id}")
    print(f"manifest={output}")
    print(f"sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
