"""``anatomy-build``: fetch sources, build the bundle, or validate without writing."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pipeline.build import BuildError, build
from pipeline.config import BuildConfig
from pipeline.fetch import fetch_all
from pipeline.wikidata import fetch_wikidata


def _config(args: argparse.Namespace) -> BuildConfig:
    cfg = BuildConfig.from_yaml(Path(args.config)) if args.config else BuildConfig()
    for key in ("fma_file", "uberon_file", "exercises_file", "bodyparts3d_dir", "wikidata_file"):
        value = getattr(args, key, None)
        if value:
            setattr(cfg, key, Path(value))
    for key in ("content_dir", "mapping_dir", "bundle_dir", "cache_dir"):
        value = getattr(args, key, None)
        if value:
            setattr(cfg, key, Path(value))
    if getattr(args, "skip_meshes", False):
        cfg.skip_meshes = True
    return cfg


def _add_source_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", help="YAML file overriding BuildConfig fields")
    p.add_argument("--fma-file", help="local FMA OWL/TTL file instead of data/raw/fma/fma.owl")
    p.add_argument("--uberon-file")
    p.add_argument("--exercises-file")
    p.add_argument("--bodyparts3d-dir")
    p.add_argument("--wikidata-file")
    p.add_argument("--content-dir")
    p.add_argument("--mapping-dir")
    p.add_argument("--bundle-dir")
    p.add_argument("--cache-dir")
    p.add_argument("--skip-meshes", action="store_true", help="skip OBJ->GLB conversion")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="anatomy-build")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download raw sources into data/raw")
    f.add_argument("--config")
    f.add_argument("--fma", action="store_true")
    f.add_argument("--uberon", action="store_true")
    f.add_argument("--exercises", action="store_true")
    f.add_argument("--bp3d", action="store_true")
    f.add_argument("--wikidata", action="store_true")
    f.add_argument("--all", action="store_true")

    b = sub.add_parser("build", help="build data/bundle from data/raw + content + mapping")
    _add_source_args(b)

    v = sub.add_parser("validate", help="run the build checks without writing the bundle")
    _add_source_args(v)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    cfg = _config(args)

    if args.cmd == "fetch":
        every = args.all
        fetch_all(
            cfg,
            fma=every or args.fma,
            uberon=every or args.uberon,
            exercises=every or args.exercises,
            bp3d=every or args.bp3d,
        )
        if every or args.wikidata:
            fetch_wikidata(cfg.sources.wikidata_sparql, cfg.cache_dir / "wikidata_by_fma.json")
        return 0

    if args.cmd == "validate":
        cfg.skip_meshes = True
    try:
        report = build(cfg, write=args.cmd == "build")
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(report.to_json())
    if report.errors:
        print(f"\n{len(report.errors)} error(s); bundle not written", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
