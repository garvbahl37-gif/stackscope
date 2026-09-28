"""StackScope pipeline CLI.

    stackscope run              # everything, end to end (idempotent; downloads are cached)
    stackscope run --from core  # resume from a stage
    stackscope run --only analytics
    stackscope stages           # list stages

Stages: ingest -> external -> silver -> core -> weights -> marts -> analytics -> quality -> insights -> reports
The quality stage is a gate: any failing "blocker" check aborts the run before insights/reports.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable

from . import settings


def _ingest():
    from .ingest.kaggle import download_all
    download_all()


def _external():
    from .ingest.external import fetch_all
    fetch_all()


def _silver():
    from .harmonize.silver import build_silver
    counts = build_silver()
    print(f"  [silver] {counts['respondents']:,} respondents, {counts['tech_usage']:,} technology rows")


def _core():
    from .warehouse.build import build_core
    build_core()


def _with_connection(fn: Callable) -> Callable:
    def runner():
        from .warehouse.build import connect
        con = connect()
        try:
            fn(con)
        finally:
            con.close()
    return runner


def _weights(con):
    from .analytics.weighting import write_weights
    diag = write_weights(con)
    print(f"  [weights] raked {len(diag)} waves; design effect {diag.design_effect.min():.2f}-{diag.design_effect.max():.2f}")


def _marts():
    from .warehouse.build import build_marts
    build_marts()


def _analytics(con):
    from .analytics import (
        ai_drivers,
        compensation,
        forecast,
        landscape,
        network,
        salary_model,
        segments,
        trends,
    )
    for name, module in [("trends", trends), ("landscape", landscape), ("forecast", forecast),
                         ("skill premium", compensation), ("salary model", salary_model), ("segments", segments),
                         ("network", network), ("ai drivers", ai_drivers)]:
        t0 = time.time()
        result = module.train(con) if module is salary_model else module.run(con)
        summary = {k: v for k, v in result.items() if not isinstance(v, (list, dict))} if isinstance(result, dict) else result
        print(f"  [analytics] {name:<14} {time.time() - t0:5.1f}s  {summary}")


def _quality(con):
    from .quality.checks import run
    result = run(con)
    print(f"  [quality] {result}")
    if result["blocking_failures"]:
        raise SystemExit(f"Quality gate failed: {result['blocking_failures']}")


def _insights(con):
    from .analytics.insights import run
    print(f"  [insights] {run(con)}")


def _reports():
    from .reporting import build_all
    for line in build_all():
        print(f"  [reports] {line}")


STAGES: dict[str, Callable[[], None]] = {
    "ingest": _ingest,
    "external": _external,
    "silver": _silver,
    "core": _core,
    "weights": _with_connection(_weights),
    "marts": _marts,
    "analytics": _with_connection(_analytics),
    "quality": _with_connection(_quality),
    "insights": _with_connection(_insights),
    "reports": _reports,
}


def run(stages: list[str]) -> None:
    settings.load_env()
    settings.ensure_dirs()
    total = time.time()
    for stage in stages:
        t0 = time.time()
        print(f"▶ {stage}")
        STAGES[stage]()
        print(f"  ✓ {stage} ({time.time() - t0:.1f}s)")
    print(f"Pipeline finished in {time.time() - total:.1f}s -> {settings.WAREHOUSE_PATH}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stackscope", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run the pipeline")
    group = run_p.add_mutually_exclusive_group()
    group.add_argument("--from", dest="start", choices=STAGES, help="start at this stage")
    group.add_argument("--only", choices=STAGES, help="run a single stage")
    sub.add_parser("stages", help="list stages")
    args = parser.parse_args(argv)

    names = list(STAGES)
    if args.command == "stages":
        print("\n".join(names))
        return
    if args.only:
        run([args.only])
    else:
        run(names[names.index(args.start):] if args.start else names)


if __name__ == "__main__":
    sys.exit(main())
