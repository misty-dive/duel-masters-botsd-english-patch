from __future__ import annotations

import csv
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import BASELINE

PUNCT = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
    "\u00a0": " ",
}


@dataclass(frozen=True)
class FlavorImportReport:
    json_cards: int
    flavor_rows: int
    source_flavor: int
    no_source_flavor: int
    preserved_existing: int
    imported: int
    remaining_untranslated_source_flavor: int
    unresolved_name: int
    unresolved_printing: int
    unresolved_non_tcg: int
    unresolved_encoding: int


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def repair_mojibake(text: str) -> str:
    if not text:
        return ""
    markers = ("Ã", "Â", "â", "€", "œ", "™", "�")
    for _ in range(3):
        before = sum(text.count(marker) for marker in markers)
        if not before:
            break
        try:
            candidate = text.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if sum(candidate.count(marker) for marker in markers) >= before:
            break
        text = candidate
    return unicodedata.normalize("NFC", text)


def clean_text(text: str) -> str:
    text = html.unescape(repair_mojibake(text or ""))
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    for source, target in PUNCT.items():
        text = text.replace(source, target)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(text.split()).strip()


def norm_name(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", clean_text(text)).split()).casefold()


def norm_name_relaxed(text: str) -> str:
    text = unicodedata.normalize("NFKD", clean_text(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def set_number(text: str) -> int | None:
    match = re.search(r"\bDM[- ]?(\d{1,2})\b", text or "", re.I)
    return int(match.group(1)) if match else None


def promo_code_from_mapping_source(text: str) -> str | None:
    match = re.search(r"\b([A-Z]\d+[A-Za-z]?/Y\d+)\b", text or "", re.I)
    return match.group(1).casefold() if match else None


def flavor_of(printing: dict[str, Any]) -> str:
    return clean_text(str(printing.get("flavor", "")))


def exact_set_printings(card: dict[str, Any], dm_no: int) -> list[dict[str, Any]]:
    return [
        printing
        for printing in card.get("printings", [])
        if set_number(str(printing.get("set", ""))) == dm_no
    ]


def _all_unique_flavors(card: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    values: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for printing in card.get("printings", []):
        flavor = flavor_of(printing)
        if flavor:
            values[flavor].append(printing)
    return values


def choose_for_numbered_set(
    card: dict[str, Any], dm_no: int, unique_reprint_fallback: bool
) -> tuple[dict[str, Any], str, str]:
    same = exact_set_printings(card, dm_no)
    if len(same) == 1:
        flavor = flavor_of(same[0])
        if flavor:
            return same[0], flavor, "same_set"
        if unique_reprint_fallback:
            values = _all_unique_flavors(card)
            if len(values) == 1:
                value, printings = next(iter(values.items()))
                return printings[0], value, "same_set_no_flavor_unique_reprint"
        return same[0], "", "same_set_has_no_english_flavor"
    if len(same) > 1:
        flavored = [(p, flavor_of(p)) for p in same if flavor_of(p)]
        distinct = {flavor for _, flavor in flavored}
        if len(distinct) == 1 and flavored:
            return flavored[0][0], flavored[0][1], "same_set_multiple_same_flavor"
        if len(flavored) == 1:
            return flavored[0][0], flavored[0][1], "same_set_single_flavored"
        return {}, "", f"ambiguous_same_set_printings:{len(same)}"
    if unique_reprint_fallback:
        values = _all_unique_flavors(card)
        if len(values) == 1:
            value, printings = next(iter(values.items()))
            return printings[0], value, "no_same_set_unique_reprint"
    return {}, "", "no_matching_printing"


def choose_for_special(
    card: dict[str, Any], mapping_source: str, unique_reprint_fallback: bool
) -> tuple[dict[str, Any], str, str]:
    printings = list(card.get("printings", []))
    code = promo_code_from_mapping_source(mapping_source)
    if code:
        matches = [
            p
            for p in printings
            if code in str(p.get("id", "")).strip().casefold()
            or code in str(p.get("set", "")).casefold()
        ]
        flavored = [(p, flavor_of(p)) for p in matches if flavor_of(p)]
        if len(flavored) == 1:
            return flavored[0][0], flavored[0][1], "promo_code"
        if len(flavored) > 1 and len({f for _, f in flavored}) == 1:
            return flavored[0][0], flavored[0][1], "promo_code_same_flavor"
        if matches:
            return matches[0], "", "promo_code_has_no_flavor"

    promo = [p for p in printings if re.search(r"promo", str(p.get("set", "")), re.I)]
    flavored = [(p, flavor_of(p)) for p in promo if flavor_of(p)]
    if len(flavored) == 1:
        return flavored[0][0], flavored[0][1], "unique_promotional_flavor"
    if len(flavored) > 1 and len({f for _, f in flavored}) == 1:
        return flavored[0][0], flavored[0][1], "promotional_same_flavor"

    if unique_reprint_fallback:
        values = _all_unique_flavors(card)
        if len(values) == 1:
            value, fps = next(iter(values.items()))
            return fps[0], value, "special_unique_flavor_any_printing"
    return {}, "", "special_printing_ambiguous_or_no_flavor"


def card_internal_id(master_row: dict[str, str]) -> str:
    match = re.match(r"\s*(\d+):", master_row.get("cards", ""))
    if not match:
        raise ValueError(
            "cannot recover internal card id from master row "
            f"{master_row.get('master_text_id')}: {master_row.get('cards')!r}"
        )
    return match.group(1)


def cp932_ok(text: str) -> tuple[bool, str]:
    if "~" in text:
        return False, "literal_tilde_reserved"
    mapped = text.replace("Ü", "~")
    try:
        mapped.encode("cp932", "strict")
    except UnicodeEncodeError as exc:
        return False, f"encoding_blocked:{mapped[exc.start:exc.end]!r}"
    return True, ""


def load_json_cards(path: Path) -> list[dict[str, Any]]:
    root = json.loads(path.read_text(encoding="utf-8-sig"))
    cards = root.get("cards", []) if isinstance(root, dict) else root
    if not isinstance(cards, list) or not cards:
        raise ValueError("JSON contains no card list")
    return [card for card in cards if isinstance(card, dict)]


def import_flavor(
    cards_raw: list[dict[str, Any]],
    cross_rows: list[dict[str, str]],
    master: list[dict[str, str]],
    display: list[dict[str, str]],
    *,
    unique_reprint_fallback: bool = False,
) -> tuple[list[dict[str, str]], FlavorImportReport]:
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_name_relaxed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in cards_raw:
        if card.get("name"):
            by_name[norm_name(str(card["name"]))].append(card)
            by_name_relaxed[norm_name_relaxed(str(card["name"]))].append(card)

    cross = {row["internal_id"]: row for row in cross_rows}
    if len(cross) != BASELINE.internal_card_count:
        raise ValueError(
            f"expected {BASELINE.internal_card_count} crosswalk rows, found {len(cross)}"
        )
    if (
        len(master) != BASELINE.master_text_count
        or len(display) != BASELINE.display_text_count
    ):
        raise ValueError(
            f"unexpected translation table sizes: master={len(master)} display={len(display)}"
        )

    display_by_id = {int(row["list_index"]): row for row in display}
    qa: list[dict[str, str]] = []
    stats: Counter[str] = Counter()
    flavor_rows = [row for row in master if "flavor" in (row.get("roles") or "").casefold()]
    stats["flavor_rows"] = len(flavor_rows)

    for row in flavor_rows:
        mid = int(row["master_text_id"])
        iid = card_internal_id(row)
        if iid not in cross:
            raise ValueError(f"master flavor {mid} references unknown card id {iid}")
        identity = cross[iid]
        source = row.get("source_japanese", "")
        existing = row.get("translation", "")
        qa_row = {
            "master_text_id": str(mid),
            "internal_id": iid,
            "resource_key": identity.get("resource_key", ""),
            "set_label": identity.get("set_label", ""),
            "english_name": identity.get("official_english_name", ""),
            "crosswalk_status": identity.get("status", ""),
            "status": "",
            "printing": "",
            "flavor": "",
        }

        if not source:
            stats["no_source_flavor"] += 1
            qa_row["status"] = "no_source_flavor"
            qa.append(qa_row)
            continue
        stats["source_flavor"] += 1

        if existing:
            ok, why = cp932_ok(existing)
            if not ok:
                raise ValueError(f"existing flavor master {mid} is not game-encodable: {why}")
            stats["preserved_existing"] += 1
            qa_row["status"] = "preserved_existing"
            qa_row["flavor"] = existing
            qa.append(qa_row)
            continue

        if not identity.get("status", "").startswith("printed_english_name_mapped"):
            stats["unresolved_non_tcg"] += 1
            qa_row["status"] = "unresolved_non_tcg_requires_manual_translation"
            qa.append(qa_row)
            continue

        candidates = by_name.get(norm_name(identity["official_english_name"]), [])
        join_mode = "exact_name"
        if not candidates:
            candidates = by_name_relaxed.get(norm_name_relaxed(identity["official_english_name"]), [])
            join_mode = "relaxed_name"
        if len(candidates) != 1:
            stats["unresolved_name"] += 1
            qa_row["status"] = f"name_candidates:{len(candidates)}"
            qa.append(qa_row)
            continue

        card = candidates[0]
        dm = set_number(identity.get("set_label", ""))
        if dm is not None:
            printing, flavor, mode = choose_for_numbered_set(
                card, dm, unique_reprint_fallback
            )
        else:
            printing, flavor, mode = choose_for_special(
                card, identity.get("mapping_source", ""), unique_reprint_fallback
            )

        qa_row["printing"] = str(printing.get("set", "")) if printing else ""
        qa_row["status"] = mode if join_mode == "exact_name" else f"{join_mode}:{mode}"
        qa_row["flavor"] = flavor
        if not flavor:
            stats["unresolved_printing"] += 1
            qa.append(qa_row)
            continue

        ok, why = cp932_ok(flavor)
        if not ok:
            stats["unresolved_encoding"] += 1
            qa_row["status"] = why
            qa.append(qa_row)
            continue

        row["translation"] = flavor
        list_index = row.get("list_index", "").strip()
        if list_index:
            index = int(list_index)
            if index not in display_by_id:
                raise ValueError(f"master flavor {mid} references unknown display list index {index}")
            old = display_by_id[index].get("translation", "")
            if old and old != flavor:
                raise ValueError(f"display flavor conflict at list index {index}: {old!r} vs {flavor!r}")
            display_by_id[index]["translation"] = flavor
        stats["imported"] += 1
        qa.append(qa_row)

    unresolved = [
        row for row in flavor_rows if row.get("source_japanese", "") and not row.get("translation", "")
    ]
    return qa, FlavorImportReport(
        json_cards=len(cards_raw),
        flavor_rows=stats["flavor_rows"],
        source_flavor=stats["source_flavor"],
        no_source_flavor=stats["no_source_flavor"],
        preserved_existing=stats["preserved_existing"],
        imported=stats["imported"],
        remaining_untranslated_source_flavor=len(unresolved),
        unresolved_name=stats["unresolved_name"],
        unresolved_printing=stats["unresolved_printing"],
        unresolved_non_tcg=stats["unresolved_non_tcg"],
        unresolved_encoding=stats["unresolved_encoding"],
    )
