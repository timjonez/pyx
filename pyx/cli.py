"""CLI for pyx transpiler."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyx.transpiler import transpile


def transpile_file(input_path: Path, output_path: Path | None = None) -> str:
    """Transpile a single .pyx file to .py."""
    source = input_path.read_text(encoding="utf-8")
    result = transpile(source)

    if output_path is None:
        if input_path.suffix == ".pyx":
            output_path = input_path.with_suffix(".py")
        else:
            output_path = input_path.parent / (input_path.name + ".py")

    output_path.write_text(result, encoding="utf-8")
    return str(output_path)


def transpile_directory(input_dir: Path, output_dir: Path | None = None) -> list[str]:
    """Recursively transpile all .pyx files in a directory."""
    if output_dir is None:
        output_dir = input_dir

    transpiled: list[str] = []
    for pyx_file in input_dir.rglob("*.pyx"):
        rel = pyx_file.relative_to(input_dir)
        out = output_dir / rel.with_suffix(".py")
        out.parent.mkdir(parents=True, exist_ok=True)
        transpile_file(pyx_file, out)
        transpiled.append(str(out))

    return transpiled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transpile .pyx files to .py")
    parser.add_argument("paths", nargs="+", help="Files or directories to transpile")
    parser.add_argument("-o", "--out", help="Output file or directory")
    parser.add_argument("-w", "--watch", action="store_true", help="Watch for changes")

    args = parser.parse_args(argv)

    for path_str in args.paths:
        path = Path(path_str)
        if not path.exists():
            print(f"Error: {path} does not exist", file=sys.stderr)
            return 1

        out = Path(args.out) if args.out else None

        if path.is_file():
            if path.suffix != ".pyx":
                print(f"Warning: {path} is not a .pyx file", file=sys.stderr)
                continue
            result = transpile_file(path, out)
            print(f"Transpiled: {path} -> {result}")
        else:
            results = transpile_directory(path, out)
            for r in results:
                print(f"Transpiled: {r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
