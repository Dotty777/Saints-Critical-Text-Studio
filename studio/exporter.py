"""Local (MD / JSON / TSV) & Optional Google Drive Exporter for Critical Text Editions."""

from __future__ import annotations
import csv
import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .catalog import CRITICAL_OUTPUT_ROOTS, DIVISIONS, GDRIVE_LANGUAGE_PARENTS, VERSIFICATION_NOTES, BookSpec
from .db import utc_now

LANGUAGE_PRIORITIES = {
    "greek": ("Priority 1 (Highest)", "Old Greek (LXX 43 Books) & Reasoned-Eclectic Greek NT (27 Books)"),
    "hebrew": ("Priority 2", "Tiberian Masoretic (Aleppo / Leningrad) & Open Ancient Hebrew Witnesses"),
    "latin": ("Priority 3", "Early Hieronymian Pandects (Amiatinus / Fuldensis), Vetus Latina & Sixto-Clementine"),
}


def ensure_repository_scaffold() -> Dict[str, Path]:
    """Create the 7-division in-Studio directory hierarchy and Edition READMEs for Greek, Hebrew, and Latin."""
    for lang, root in CRITICAL_OUTPUT_ROOTS.items():
        root.mkdir(parents=True, exist_ok=True)
        for div in DIVISIONS:
            (root / div["id"]).mkdir(parents=True, exist_ok=True)
        readme = root / "README.md"
        prio, desc = LANGUAGE_PRIORITIES[lang]
        fresh_readme = (
            f"# Saints {lang.title()} Critical Text\n\n"
            f"- **Priority Tier:** {prio}\n"
            f"- **Editorial Scope:** {desc}\n"
            f"- **Method:** Reasoned Eclecticism over open-license Tiers 1–4 witnesses (Tier 5 NonCommercial/copyrighted editions strictly quarantined).\n"
            f"- **Home Location:** Self-contained inside [Saints Critical Text Studio](../README.md) (`Saints-{lang.title()}-Critical-Text/`).\n\n"
            f"## File Formats per Chapter\n"
            f"- `*_Critical_Text.md` — Scholarly four-section critical edition (Witness Declaration, Continuous Critical Text, Apparatus & Disregarded Noise Log, Verse-by-Verse Rationale).\n"
            f"- `*_Critical_Text.json` — Full structured collation, apparatus, confidence scores, and provenance.\n"
            + _TSV_README_LINE
        )
        if readme.exists():
            old = readme.read_text(encoding="utf-8")
            if old.startswith("# Gemini ") or "Gemini Critical Text Studio" in old or _OLD_TSV_LINE in old:
                readme.write_text(fresh_readme, encoding="utf-8")
        else:
            readme.write_text(fresh_readme, encoding="utf-8")
    return CRITICAL_OUTPUT_ROOTS


# The TSV columns, as written by export_chapter_files (keep the two in step).
TSV_COLUMNS = ["Book", "Chapter", "Verse", "Critical_Text", "Confidence", "Substantive_Variants", "Human_Locked", "Analysis_Flags"]
_TSV_README_LINE = (
    "- `*_Critical_Text.tsv` — Clean tab-separated ("
    + ", ".join(f"`{c}`" for c in TSV_COLUMNS)
    + ") for downstream translation pipelines. `Substantive_Variants` counts apparatus entries (a whole-verse "
    "entry included); `Human_Locked` is 1 for human-verified verses; `Analysis_Flags` lists the internal-evidence "
    "findings and review flags of the verse.\n"
)
_OLD_TSV_LINE = (
    "- `*_Critical_Text.tsv` — Clean tab-separated (`Book`, `Chapter`, `Verse`, `Critical_Text`, `Confidence`, "
    "`Apparatus_Count`) for downstream translation pipelines.\n"
)


def export_chapter_files(
    language: str,
    book: BookSpec,
    chapter: int,
    admitted_witnesses: List[Dict[str, Any]],
    quarantined_witnesses: List[Dict[str, Any]],
    verse_rows: List[Dict[str, Any]],
    model_used: str,
    anchor_siglum: str = "",
    base_siglum: str = "",
    versification_notes: List[str] | None = None,
    apparatus_witnesses: List[Dict[str, Any]] | None = None,
) -> Tuple[Path, Path, Path]:
    """Write Markdown, JSON, and TSV files for a chapter into its canonical 7-division folder."""
    ensure_repository_scaffold()
    root = CRITICAL_OUTPUT_ROOTS[language.lower()]
    book_dir = root / book.division / book.folder_name
    book_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{book.folder_name}_{chapter:02d}_Critical_Text"
    md_path = book_dir / f"{stem}.md"
    json_path = book_dir / f"{stem}.json"
    tsv_path = book_dir / f"{stem}.tsv"

    now = utc_now()

    # 1. Build Markdown Critical Edition
    lines: List[str] = [
        f"# {book.title} {chapter:02d} — Saints {language.title()} Critical Text",
        "",
        f"**Division:** `{book.division}` · **Language:** `{language.title()}` · **Engine:** `{model_used}` · **Updated:** `{now}`",
        "",
        f"**Versification:** {VERSIFICATION_NOTES.get(language.lower(), '')}"
        + (f" Numbering anchor for this chapter: `{anchor_siglum}`." if anchor_siglum else "")
        + (f" Spelling and punctuation follow `{base_siglum}` where it attests the adopted reading." if base_siglum else ""),
        "",
        "**Sigla in the text:** `⟦ ⟧` = verse absent from (or bracketed by) witnesses that outweigh those containing it — printed for reference, probably not original. `(…)` before a Hebrew word = ketiv, followed by the qere.",
        "",
        "---",
        "",
        "## Section I — Admitted Witnesses & Gatekeeper Quarantine Declaration",
        "",
        "### Admitted Collation Witnesses (Open-Source Tiers 1–4)",
        "| Siglum | Witness Title | Tier | Weight | License | Text-Type |",
        "| :--- | :--- | :---: | :---: | :--- | :--- |",
    ]
    for w in admitted_witnesses:
        lines.append(
            f"| **{w['siglum']}** | {w['title']} | Tier {w['tier']} | `{w['weight']:.2f}` | {w['license']} | {w['text_type']} |"
        )

    if apparatus_witnesses:
        lines.extend(
            [
                "",
                "### Apparatus Witnesses (Majority / Ecclesiastical Editions — recorded, not voting)",
                "Collated against the adopted text and listed in the apparatus wherever they differ in substance; "
                "they do not vote on the text.",
                "",
                "| Siglum | Witness Title | Tier | License | Text-Type |",
                "| :--- | :--- | :---: | :--- | :--- |",
            ]
        )
        for w in apparatus_witnesses:
            lines.append(f"| **{w['siglum']}** | {w['title']} | Tier {w['tier']} | {w['license']} | {w['text_type']} |")

    if quarantined_witnesses:
        lines.extend(
            [
                "",
                "### Disregarded / Quarantined Sources (Excluded by AI Gatekeeper)",
                "| Source | Status | Reason Excluded from Open Critical Text |",
                "| :--- | :---: | :--- |",
            ]
        )
        for qw in quarantined_witnesses:
            summary = str(qw["gatekeeper_summary"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {qw['siglum']} | `{qw['status']}` | {summary} |")

    if versification_notes:
        lines.extend(["", "### Versification & Alignment Notes"])
        lines.extend(f"- {n}" for n in versification_notes)

    lines.extend(
        [
            "",
            "---",
            "",
            f"## Section II — Continuous {language.title()} Critical Text",
            "",
        ]
    )
    for vr in verse_rows:
        lock_tag = " *(Human Verified)*" if vr.get("human_locked") else ""
        lines.append(f"**{vr['verse']}** {vr['critical_text']}{lock_tag}")
    lines.extend(["", "---", "", "## Section III — Critical Apparatus & Disregarded Surface Noise", ""])

    has_any_app = False
    for vr in verse_rows:
        app_list = vr.get("apparatus", [])
        dis_list = vr.get("disregarded", [])
        if not app_list and not dis_list:
            continue
        has_any_app = True
        lines.append(f"### {book.title} {chapter}:{vr['verse']}")
        for a in app_list:
            vars_fmt = " ; ".join(
                f"**{v['reading']}** {' '.join(v['witnesses'])}" for v in a.get("variants", [])
            )
            lemma_wits = " ".join(a.get("lemma_witnesses", []))
            vtype = f" *({a['variant_type']})*" if a.get("variant_type") else ""
            credited = a.get("credited_witnesses") or []
            ctext = (f" *(not counted as omitting: {', '.join(credited)} — the words stand in a neighbouring unit)*"
                     if credited else "")
            lines.append(f"- **Apparatus:** `{a['lemma']}` {lemma_wits} **]** {vars_fmt}{vtype}{ctext}")
            for f in a.get("analysis", []) or []:
                lines.append(f"  - *{f.get('canon', 'analysis')}:* {f.get('note', '')}")
        for d in dis_list:
            d_forms = ", ".join(f"`{x}`" for x in d.get("disregarded_forms", []))
            d_wits = ", ".join(d.get("witnesses", []))
            lines.append(
                f"- *Disregarded Surface Variant:* kept `{d['kept_form']}` over {d_forms} ({d_wits}) — *{d['reason']}*"
            )
        lines.append("")

    if not has_any_app:
        lines.append("*No substantive or orthographic variants detected across admitted witnesses in this chapter.*")
        lines.append("")

    lines.extend(["---", "", "## Section IV — Verse-by-Verse Text-Critical Rationale & Witness Matrix", ""])
    for vr in verse_rows:
        lines.append(
            f"### Verse {vr['verse']} (Confidence: `{vr['confidence']:.1%}` · Source: `{vr['decision_source']}`)"
        )
        lines.append(f"- **Critical Text:** {vr['critical_text']}")
        refs = vr.get("witness_refs", {}) or {}
        for sig, wtxt in vr.get("witness_readings", {}).items():
            ref_note = f" *(numbered {refs[sig]} in this witness)*" if sig in refs else ""
            lines.append(f"  - `{sig}`{ref_note}: {wtxt}")
        for sig in vr.get("absent_witnesses", []) or []:
            lines.append(f"  - `{sig}`: — *(verse absent)*")
        locked = bool(vr.get("human_locked"))
        if vr.get("needs_review") and not locked:  # a human-verified verse has had its review
            lines.append("- **⚑ Needs human review** (see analysis below)")
        lines.append(f"- **Philological Rationale:** {vr['rationale']}")
        for f in vr.get("analysis", []) or []:
            canon = f.get("canon", "analysis")
            if locked and canon == "review flag":
                canon += " (on the machine text, before human verification)"
            lines.append(f"- *{canon}:* {f.get('note', '')}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    # 2. Build JSON
    json_payload = {
        "edition": f"Saints {language.title()} Critical Text",
        "language": language,
        "division": book.division,
        "book_slug": book.slug,
        "book_title": book.title,
        "usfm_code": book.usfm_code,
        "chapter": chapter,
        "model_used": model_used,
        "updated_at": now,
        "versification": VERSIFICATION_NOTES.get(language.lower(), ""),
        "versification_anchor": anchor_siglum,
        "orthographic_base": base_siglum,
        "versification_notes": list(versification_notes or []),
        "admitted_witnesses": [
            {
                "siglum": w["siglum"],
                "title": w["title"],
                "tier": w["tier"],
                "weight": w["weight"],
                "license": w["license"],
            }
            for w in admitted_witnesses
        ],
        "apparatus_witnesses": [
            {"siglum": w["siglum"], "title": w["title"], "tier": w["tier"], "license": w["license"],
             "role": "apparatus only (recorded, not voting)"}
            for w in (apparatus_witnesses or [])
        ],
        "verses": verse_rows,
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. Build TSV
    with tsv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(TSV_COLUMNS)
        for vr in verse_rows:
            writer.writerow(
                [
                    book.usfm_code,
                    chapter,
                    vr["verse"],
                    vr["critical_text"],
                    f"{vr['confidence']:.3f}",
                    len(vr.get("apparatus", [])),
                    1 if vr.get("human_locked") else 0,
                    _analysis_flags(vr),
                ]
            )

    return md_path, json_path, tsv_path


def _analysis_flags(vr: Dict[str, Any]) -> str:
    """Compact, sorted list of internal-evidence canons that fired in the verse (for the TSV)."""
    flags = {f.get("canon", "") for a in vr.get("apparatus", []) or [] for f in a.get("analysis", []) or []}
    flags |= {f.get("canon", "") for f in vr.get("analysis", []) or []}
    if vr.get("needs_review") and not vr.get("human_locked"):  # a human-verified verse has had its review
        flags.add("needs_review")
    if str(vr.get("critical_text", "")).startswith("⟦"):
        flags.add("bracketed_verse")
    # bookkeeping notes present on almost every unit say nothing about this verse in particular
    flags -= {"", "external: independent streams", "external: two-stream policy", "confidence", "review flag"}
    return ",".join(sorted(flags))


def _run_gdrive(args: List[str]) -> str:
    exe = shutil.which("gdrive")
    if not exe:
        raise RuntimeError(
            "No standalone 'gdrive' CLI found on system PATH. Your MD/JSON/TSV files are already saved locally on disk and can be dropped directly into Google Drive or synced via Google Drive for Desktop."
        )
    proc = subprocess.run(
        [exe, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gdrive {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def _ensure_gdrive_subfolder(parent_id: str, folder_name: str) -> str:
    out = _run_gdrive(["readonly", "ls", parent_id, "--json", "--max", "100"])
    items = json.loads(out) if out.startswith("[") else json.loads(out).get("files", [])
    for item in items:
        if item.get("name") == folder_name and "folder" in item.get("mimeType", item.get("type", "")):
            return str(item["id"])
    created = _run_gdrive(["mutate", "mkdir", folder_name, "--parent", parent_id])
    # Parse ID from output
    for tok in created.replace(":", " ").split():
        if len(tok) >= 20 and ("-" in tok or "_" in tok or tok.isalnum()):
            if not tok.startswith("http"):
                return tok
    # Re-list to be certain
    out2 = _run_gdrive(["readonly", "ls", parent_id, "--json", "--max", "100"])
    items2 = json.loads(out2) if out2.startswith("[") else json.loads(out2).get("files", [])
    for item in items2:
        if item.get("name") == folder_name:
            return str(item["id"])
    raise RuntimeError(f"Could not resolve created Drive folder '{folder_name}'.")


def sync_chapter_to_gdrive(
    language: str,
    book: BookSpec,
    chapter: int,
    md_path: Path,
    offline_locked: bool,
) -> Tuple[str, str]:
    """Upload or update the chapter Markdown as a clean Google Doc inside Saints Website on Drive."""
    if offline_locked:
        raise PermissionError(
            "Strict Offline Mode is LOCKED. Unlock Offline Mode before syncing to Google Drive."
        )
    lang_parent = GDRIVE_LANGUAGE_PARENTS[language.lower()]
    root_folder_name = f"Saints_{language.title()}_Critical_Text"
    crit_root_id = _ensure_gdrive_subfolder(lang_parent, root_folder_name)
    div_id = _ensure_gdrive_subfolder(crit_root_id, book.division)
    book_id = _ensure_gdrive_subfolder(div_id, book.folder_name)

    doc_title = md_path.stem
    out = _run_gdrive(["readonly", "ls", book_id, "--json", "--max", "100"])
    items = json.loads(out) if out.startswith("[") else json.loads(out).get("files", [])
    existing_id = ""
    for item in items:
        if item.get("name") in (doc_title, md_path.name):
            existing_id = str(item["id"])
            break

    if existing_id:
        _run_gdrive(["mutate", "update", existing_id, str(md_path), "--mime-type", "text/markdown"])
        file_id = existing_id
    else:
        up_out = _run_gdrive(
            [
                "mutate",
                "upload",
                str(md_path),
                "--parent",
                book_id,
                "--mime-type",
                "application/vnd.google-apps.document",
            ]
        )
        # Re-query to grab exact ID cleanly
        out2 = _run_gdrive(["readonly", "ls", book_id, "--json", "--max", "100"])
        items2 = json.loads(out2) if out2.startswith("[") else json.loads(out2).get("files", [])
        file_id = ""
        for item in items2:
            if doc_title in item.get("name", ""):
                file_id = str(item["id"])
                break
        if not file_id:
            raise RuntimeError(f"Uploaded to Drive ({up_out}), but could not look up file ID.")

    url = _run_gdrive(["readonly", "url", file_id]).strip()
    return file_id, url
