#!/usr/bin/env python3
"""
Import printing-specific English flavor text into BOTSD's existing master/display
card-text CSVs without requiring the obsolete bosd_card_database.csv join file.

Source format: Latepate64/duel-masters-json DuelMastersCards.json.
The current project crosswalk is the authority for card identity.

Rules:
- Preserve any existing non-empty flavor translation.
- For retail cards with an official English printing, prefer the same numbered
  DM set (DM-01..DM-12).
- For Special/Promo cards, prefer an explicitly identified promotional printing
  from mapping_source where possible
  otherwise require an unambiguous flavor.
- Never borrow a different printing's flavor unless --unique-reprint-fallback is
  enabled and every non-empty flavor for that English card is byte-identical.
- Rows with no Japanese flavor source are treated as no-flavor rows and do not
  count as unresolved.
- All output is CP932/font-patch checked. Literal '~' is reserved by the project
  font patch
  Unicode Ü is represented internally as '~' by the game builder.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

PUNCT = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
}


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def repair_mojibake(s: str) -> str:
    if not s:
        return ""
    markers = ("Ã", "Â", "â", "€", "œ", "™", "�")
    for _ in range(3):
        before = sum(s.count(m) for m in markers)
        if not before:
            break
        try:
            cand = s.encode("cp1252").decode("utf-8")
        except Exception:
            break
        if sum(cand.count(m) for m in markers) >= before:
            break
        s = cand
    return unicodedata.normalize("NFC", s)


def clean_text(s: str) -> str:
    s = html.unescape(repair_mojibake(s or ""))
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Flavor text is displayed as wrapped prose, not explicit rule clauses.
    s = " ".join(s.split())
    return s.strip()


def norm_name(s: str) -> str:
    s = clean_text(s)
    # Treat typographic width variations as identity-equivalent.
    s = unicodedata.normalize("NFKC", s)
    return " ".join(s.split()).casefold()

def norm_name_relaxed(s: str) -> str:
    # Secondary join key for verified names whose public database spelling only
    # differs in accents/punctuation (e.g. Über/Uber). It is used only when the
    # exact normalized key has no match and only when the result is unique.
    s = clean_text(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def set_number(s: str):
    m = re.search(r"\bDM[- ]?(\d{1,2})\b", s or "", re.I)
    return int(m.group(1)) if m else None


def promo_code_from_mapping_source(s: str):
    # Examples in the project crosswalk: Promotional P7/Y2, D2a/Y3, S3/Y1.
    m = re.search(r"\b([A-Z]\d+[A-Za-z]?/Y\d+)\b", s or "", re.I)
    return m.group(1).casefold() if m else None


def printing_id(p: dict) -> str:
    return str(p.get("id", "")).strip().casefold()


def flavor_of(p: dict) -> str:
    return clean_text(str(p.get("flavor", "")))


def exact_set_printings(card: dict, dm_no: int):
    return [p for p in card.get("printings", []) if set_number(str(p.get("set", ""))) == dm_no]


def choose_for_numbered_set(card: dict, dm_no: int, unique_reprint_fallback: bool):
    same = exact_set_printings(card, dm_no)
    if len(same) == 1:
        f = flavor_of(same[0])
        if f:
            return same[0], f, "same_set"
        # Do not silently substitute a reprint unless it is provably identical
        # across all non-empty printings.
        if unique_reprint_fallback:
            vals = defaultdict(list)
            for p in card.get("printings", []):
                f2 = flavor_of(p)
                if f2:
                    vals[f2].append(p)
            if len(vals) == 1:
                f2, ps = next(iter(vals.items()))
                return ps[0], f2, "same_set_no_flavor_unique_reprint"
        return same[0], "", "same_set_has_no_english_flavor"
    if len(same) > 1:
        flavored = [(p, flavor_of(p)) for p in same if flavor_of(p)]
        distinct = {f for _, f in flavored}
        if len(distinct) == 1 and flavored:
            return flavored[0][0], flavored[0][1], "same_set_multiple_same_flavor"
        if len(flavored) == 1:
            return flavored[0][0], flavored[0][1], "same_set_single_flavored"
        return {}, "", f"ambiguous_same_set_printings:{len(same)}"
    if unique_reprint_fallback:
        vals = defaultdict(list)
        for p in card.get("printings", []):
            f = flavor_of(p)
            if f:
                vals[f].append(p)
        if len(vals) == 1:
            f, ps = next(iter(vals.items()))
            return ps[0], f, "no_same_set_unique_reprint"
    return {}, "", "no_matching_printing"


def choose_for_special(card: dict, mapping_source: str, unique_reprint_fallback: bool):
    ps = list(card.get("printings", []))
    code = promo_code_from_mapping_source(mapping_source)
    if code:
        matches = [p for p in ps if code in printing_id(p) or code in str(p.get("set", "")).casefold()]
        flavored = [(p, flavor_of(p)) for p in matches if flavor_of(p)]
        if len(flavored) == 1:
            return flavored[0][0], flavored[0][1], "promo_code"
        if len(flavored) > 1 and len({f for _, f in flavored}) == 1:
            return flavored[0][0], flavored[0][1], "promo_code_same_flavor"
        if matches:
            return matches[0], "", "promo_code_has_no_flavor"

    # Prefer any printing whose set/id visibly says promo/promotional.
    promo = [p for p in ps if re.search(r"promo", str(p.get("set", "")), re.I)]
    flavored = [(p, flavor_of(p)) for p in promo if flavor_of(p)]
    if len(flavored) == 1:
        return flavored[0][0], flavored[0][1], "unique_promotional_flavor"
    if len(flavored) > 1 and len({f for _, f in flavored}) == 1:
        return flavored[0][0], flavored[0][1], "promotional_same_flavor"

    # Last safe fallback: all non-empty printings agree on the exact flavor.
    if unique_reprint_fallback:
        vals = defaultdict(list)
        for p in ps:
            f = flavor_of(p)
            if f:
                vals[f].append(p)
        if len(vals) == 1:
            f, fps = next(iter(vals.items()))
            return fps[0], f, "special_unique_flavor_any_printing"
    return {}, "", "special_printing_ambiguous_or_no_flavor"


def card_internal_id(master_row: dict) -> str:
    m = re.match(r"\s*(\d+):", master_row.get("cards", ""))
    if not m:
        raise ValueError(f"cannot recover internal card id from master row {master_row.get('master_text_id')}: {master_row.get('cards')!r}")
    return m.group(1)


def cp932_ok(text: str):
    if "~" in text:
        return False, "literal_tilde_reserved"
    mapped = text.replace("Ü", "~")
    try:
        mapped.encode("cp932", "strict")
    except UnicodeEncodeError as e:
        return False, f"encoding_blocked:{mapped[e.start:e.end]!r}"
    return True, ""


def main():
    """Run the command-line patch/verification workflow."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, required=True)
    ap.add_argument("--crosswalk", type=Path, required=True)
    ap.add_argument("--master-in", type=Path, required=True)
    ap.add_argument("--display-in", type=Path, required=True)
    ap.add_argument("--master-out", type=Path, required=True)
    ap.add_argument("--display-out", type=Path, required=True)
    ap.add_argument("--qa-out", type=Path, required=True)
    ap.add_argument("--summary-out", type=Path)
    ap.add_argument("--unique-reprint-fallback", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit nonzero if any non-empty Japanese flavor remains untranslated")
    a = ap.parse_args()

    root = json.loads(a.json.read_text(encoding="utf-8-sig"))
    cards_raw = root.get("cards", []) if isinstance(root, dict) else root
    if not isinstance(cards_raw, list) or not cards_raw:
        raise ValueError("JSON contains no card list")

    by_name = defaultdict(list)
    by_name_relaxed = defaultdict(list)
    for c in cards_raw:
        if isinstance(c, dict) and c.get("name"):
            by_name[norm_name(str(c["name"]))].append(c)
            by_name_relaxed[norm_name_relaxed(str(c["name"]))].append(c)

    cross_rows = read_csv(a.crosswalk)
    cross = {r["internal_id"]: r for r in cross_rows}
    if len(cross) != 673:
        raise ValueError(f"expected 673 crosswalk rows, found {len(cross)}")

    master = read_csv(a.master_in)
    display = read_csv(a.display_in)
    mt = {int(r["master_text_id"]): r for r in master}
    dt = {int(r["list_index"]): r for r in display}
    if len(master) != 2376 or len(display) != 1682:
        raise ValueError(f"unexpected translation table sizes: master={len(master)} display={len(display)}")

    qa = []
    stats = Counter()
    flavor_rows = [r for r in master if "flavor" in (r.get("roles") or "").casefold()]
    stats["flavor_rows"] = len(flavor_rows)

    for r in flavor_rows:
        mid = int(r["master_text_id"])
        iid = card_internal_id(r)
        if iid not in cross:
            raise ValueError(f"master flavor {mid} references unknown card id {iid}")
        x = cross[iid]
        src = r.get("source_japanese", "")
        existing = r.get("translation", "")
        row = {
            "master_text_id": str(mid),
            "internal_id": iid,
            "resource_key": x.get("resource_key", ""),
            "set_label": x.get("set_label", ""),
            "english_name": x.get("official_english_name", ""),
            "crosswalk_status": x.get("status", ""),
            "status": "",
            "printing": "",
            "flavor": "",
        }

        if not src:
            stats["no_source_flavor"] += 1
            row["status"] = "no_source_flavor"
            qa.append(row)
            continue
        stats["source_flavor"] += 1

        if existing:
            ok, why = cp932_ok(existing)
            if not ok:
                raise ValueError(f"existing flavor master {mid} is not game-encodable: {why}")
            stats["preserved_existing"] += 1
            row["status"] = "preserved_existing"
            row["flavor"] = existing
            qa.append(row)
            continue

        # Only the verified printed-English card identities are candidates for
        # official TCG flavor import. Game-original/OCG-only rows should have
        # manual localization already present in the project CSV.
        if not x.get("status", "").startswith("printed_english_name_mapped"):
            stats["unresolved_non_tcg"] += 1
            row["status"] = "unresolved_non_tcg_requires_manual_translation"
            qa.append(row)
            continue

        cands = by_name.get(norm_name(x["official_english_name"]), [])
        join_mode = "exact_name"
        if not cands:
            cands = by_name_relaxed.get(norm_name_relaxed(x["official_english_name"]), [])
            join_mode = "relaxed_name"
        if len(cands) != 1:
            stats["unresolved_name"] += 1
            row["status"] = f"name_candidates:{len(cands)}"
            qa.append(row)
            continue
        card = cands[0]
        label = x.get("set_label", "")
        dm = set_number(label)
        if dm is not None:
            p, flavor, mode = choose_for_numbered_set(card, dm, a.unique_reprint_fallback)
        else:
            p, flavor, mode = choose_for_special(card, x.get("mapping_source", ""), a.unique_reprint_fallback)

        row["printing"] = str(p.get("set", "")) if p else ""
        row["status"] = mode if join_mode == "exact_name" else f"{join_mode}:{mode}"
        row["flavor"] = flavor
        if not flavor:
            stats["unresolved_printing"] += 1
            qa.append(row)
            continue

        ok, why = cp932_ok(flavor)
        if not ok:
            stats["unresolved_encoding"] += 1
            row["status"] = why
            qa.append(row)
            continue

        r["translation"] = flavor
        li_s = r.get("list_index", "").strip()
        if li_s:
            li = int(li_s)
            if li not in dt:
                raise ValueError(f"master flavor {mid} references unknown display list index {li}")
            old = dt[li].get("translation", "")
            if old and old != flavor:
                raise ValueError(f"display flavor conflict at list index {li}: {old!r} vs {flavor!r}")
            dt[li]["translation"] = flavor
        stats["imported"] += 1
        qa.append(row)

    write_csv(a.master_out, master)
    write_csv(a.display_out, display)
    write_csv(a.qa_out, qa)

    unresolved = []
    for r in flavor_rows:
        if r.get("source_japanese", "") and not r.get("translation", ""):
            unresolved.append(r)
    stats["remaining_untranslated_source_flavor"] = len(unresolved)
    stats["translated_source_flavor"] = stats["source_flavor"] - len(unresolved)

    summary = [
        "BOTSD flavor import v2",
        f"JSON cards: {len(cards_raw)}",
        f"Flavor master rows: {stats['flavor_rows']}",
        f"Rows with Japanese source flavor: {stats['source_flavor']}",
        f"Rows with no source flavor: {stats['no_source_flavor']}",
        f"Existing English preserved: {stats['preserved_existing']}",
        f"Official English flavor imported: {stats['imported']}",
        f"Remaining untranslated source flavor: {stats['remaining_untranslated_source_flavor']}",
        f"Unresolved name joins: {stats['unresolved_name']}",
        f"Unresolved printing/flavor: {stats['unresolved_printing']}",
        f"Unresolved non-TCG rows: {stats['unresolved_non_tcg']}",
        f"Encoding-blocked: {stats['unresolved_encoding']}",
    ]
    text = "\n".join(summary) + "\n"
    print(text, end="")
    if a.summary_out:
        a.summary_out.write_text(text, encoding="utf-8")

    if a.strict and unresolved:
        print(f"ERROR: {len(unresolved)} non-empty Japanese flavor rows remain untranslated. See {a.qa_out}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
