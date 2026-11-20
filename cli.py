"""Headless CLI for Saints Critical Text Studio (For Automation, Developers & AI Agents).

Examples:
    python cli.py status
    python cli.py library
    python cli.py reexport
    python cli.py collate --lang greek --book genesis --chapters 1-3
    python cli.py collate --lang greek --book matthew --chapters 1
    python cli.py gatekeep --lang greek --siglum "MS-Test" --title "Test Fragment" --file sample.txt
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from typing import List

# Ensure UTF-8 stdout on Windows consoles for Greek & Hebrew output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from studio.catalog import BOOKS_BY_SLUG
from studio.engine import CriticalTextEngine


def _parse_chapter_range(spec: str, max_ch: int) -> List[int]:
    if spec.lower() == "all":
        return list(range(1, max_ch + 1))
    out: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [c for c in out if 1 <= c <= max_ch]


def main() -> int:
    parser = argparse.ArgumentParser(description="Saints Critical Text Studio — Offline CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show registered witnesses and Gatekeeper statuses across Greek, Hebrew, and Latin")
    sub.add_parser("library", help="Show saved Saints Critical Text chapters inside the Studio home")
    sub.add_parser("reexport", help="Re-export all saved chapters to their in-Studio Saints-*-Critical-Text homes")

    p_col = sub.add_parser("collate", help="Collate and adjudicate one or more chapters offline")
    p_col.add_argument("--lang", required=True, choices=["greek", "hebrew", "latin"])
    p_col.add_argument("--book", required=True, help="Book slug, e.g. genesis, matthew, psalms")
    p_col.add_argument("--chapters", default="1", help="Chapter number, range (e.g. 1-5), or 'all'")
    p_col.add_argument("--sync-drive", action="store_true", help="Also sync output Markdown to Google Drive (requires unlock)")
    p_col.add_argument("--allow-network", action="store_true", help="Unlock cloud reviews for this run only (API usage may incur charges)")
    p_col.add_argument(
        "--brain",
        choices=["offline_philological", "textual_analysis", "openai_review", "local_ollama", "cloud_gemini"],
        help="Brain for this run only (default: the one saved in settings)",
    )

    p_gk = sub.add_parser("gatekeep", help="Evaluate and register a new witness file via the AI Gatekeeper")
    p_gk.add_argument("--lang", required=True, choices=["greek", "hebrew", "latin"])
    p_gk.add_argument("--siglum", required=True)
    p_gk.add_argument("--title", required=True)
    p_gk.add_argument("--scope", default="OT/NT", choices=["OT", "NT", "OT/NT"])
    p_gk.add_argument("--license", default="")
    p_gk.add_argument("--file", required=True)

    p_sc = sub.add_parser("concordance", help="Build, search and export The Saints Concordance (lemmas and roots)")
    p_sc.add_argument("action", choices=["stats", "seed", "index", "search", "export"],
                      help="seed = rebuild everything; index = rebuild all or --book; search; stats; export")
    p_sc.add_argument("--query", default="", help="Search term for 'search' (e.g., headwater, beginning, H7225, ἀρχ)")
    p_sc.add_argument("--book", default="", help="Optional book slug for 'index' (e.g., genesis)")
    p_sc.add_argument("--max-chapters", type=int, default=0, help="Testing: only the first N chapters per language (0 = all)")
    p_sc.add_argument("--lang", default="all", help="Language filter for 'search' (heb, arc, grc, lat)")
    p_sc.add_argument("--limit", type=int, default=25, help="Result limit for 'search'")
    p_sc.add_argument("--stepbible-dir", default="", help="(ignored; kept for compatibility)")
    p_sc.add_argument("--out-dir", default="", help="Optional output folder for 'export'")

    args = parser.parse_args()
    engine = CriticalTextEngine()

    if args.cmd == "status":
        for lang in ("greek", "hebrew", "latin"):
            rows = engine.list_witnesses(lang)
            admitted = [r for r in rows if r["status"] == "ADMITTED"]
            blocked = [r for r in rows if r["status"] != "ADMITTED"]
            print(f"\n=== {lang.upper()} ({len(admitted)} Admitted, {len(blocked)} Quarantined/Disregarded) ===")
            for r in rows:
                print(f"  [{r['status']:21s}] Tier {r['tier']} | w={r['weight']:.2f} | {r['siglum']:26s} | {r['title']}")
        return 0

    if args.cmd == "library":
        for lang in ("greek", "hebrew", "latin"):
            s = engine.get_edition_home_summary(lang)
            print(
                f"\n=== {s['edition_title']} ({s['saved_chapter_count']}/{s['total_chapters_in_canon']} chapters, "
                f"{s['saved_verse_count']} verses) ===\n  Home: {s['home_path']}"
            )
            for row in s["saved_chapters"]:
                print(
                    f"  - {row['book_title']} {int(row['chapter']):02d} ({row['verse_count']} vv., "
                    f"{row['variant_verse_count']} apparatus) -> {row['local_md_path']}"
                )
        return 0

    if args.cmd == "reexport":
        n = engine.reexport_all_saved_chapters()
        print(f"Re-exported {n} saved Saints Critical Text chapter(s) inside Saints-Critical-Text-Studio.")
        return 0

    if args.cmd == "collate":
        slug = args.book.lower()
        if slug not in BOOKS_BY_SLUG:
            print(f"Unknown book slug '{slug}'. Available slugs include: {', '.join(list(BOOKS_BY_SLUG)[:15])}...", file=sys.stderr)
            return 2
        book = BOOKS_BY_SLUG[slug]
        chapters = _parse_chapter_range(args.chapters, book.chapters)
        if not chapters:
            print(f"No valid chapters in '{args.chapters}' ({book.title} has {book.chapters}).", file=sys.stderr)
            return 2
        if args.brain:
            engine.config.provider_id = args.brain
        if args.allow_network:
            engine.config.offline_locked = False
        failures = 0
        for ch in chapters:
            try:
                data = engine.collate_and_adjudicate(args.lang, slug, ch, preserve_human_locks=True)
            except (LookupError, ValueError) as exc:
                failures += 1
                print(f"[SKIP] {args.lang.upper()} {book.title} {ch:02d}: {exc}", file=sys.stderr)
                continue
            bracketed = sum(1 for v in data["verses"] if v["critical_text"].startswith("⟦"))
            review = [str(v["verse"]) for v in data["verses"] if v.get("needs_review")]
            print(
                f"[OK] {args.lang.upper()} {book.title} {ch:02d}: {data['verse_count']} verses, "
                f"{data['variant_verse_count']} with apparatus"
                + (f", {bracketed} bracketed ⟦ ⟧" if bracketed else "")
                + (f", review: v{','.join(review)}" if review else "")
                + f" -> {data['local_md_path']}"
            )
            if args.sync_drive:
                print("     --sync-drive given: Offline Lock lifted for this run only.")
                engine.config.offline_locked = False
                fid, url = engine.sync_saved_chapter_to_drive(args.lang, slug, ch)
                print(f"     Synced to Google Drive: {url} ({fid})")
        return 1 if failures else 0

    if args.cmd == "gatekeep":
        wid, verdict = engine.ingest_new_witness(
            language=args.lang,
            siglum=args.siglum,
            title=args.title,
            testament_scope=args.scope,
            declared_license=args.license,
            source_file=Path(args.file),
        )
        print(
            json.dumps(
                {
                    "witness_id": wid,
                    "decision": verdict.decision,
                    "tier": verdict.tier_assigned,
                    "weight": verdict.recommended_weight,
                    "summary": verdict.summary,
                    "reasons": verdict.reasons,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.cmd == "concordance":
        if args.action == "stats":
            print(json.dumps(engine.get_concordance_stats(), indent=2, ensure_ascii=False))
        elif args.action == "seed":
            sb = Path(args.stepbible_dir) if args.stepbible_dir else None
            print(json.dumps(engine.seed_concordance_lexicons(stepbible_root=sb), indent=2, ensure_ascii=False))
        elif args.action == "index":
            bslug = args.book.strip().lower() or None
            if bslug and bslug not in BOOKS_BY_SLUG:
                print(f"Unknown book slug: {bslug!r}", file=sys.stderr)
                return 2
            print(json.dumps(engine.index_concordance_chapters(book_slug=bslug, max_chapters=args.max_chapters), indent=2, ensure_ascii=False))
        elif args.action == "search":
            res = engine.search_concordance(query=args.query, lang_filter=args.lang, limit=args.limit)
            print(json.dumps(res, indent=2, ensure_ascii=False))
        elif args.action == "export":
            out = Path(args.out_dir) if args.out_dir else None
            print(json.dumps(engine.export_concordance_pack(out_dir=out), indent=2, ensure_ascii=False))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
