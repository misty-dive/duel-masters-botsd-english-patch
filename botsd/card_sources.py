from __future__ import annotations

import csv
import hashlib
import shutil
import sqlite3
import subprocess
import time
import unicodedata
import urllib.request
from pathlib import Path
from collections.abc import Iterable

from .errors import HashMismatchError, VerificationError
from .hashing import sha256_path
from .manifest import BASELINE

DB_COMMIT = "e10343da98f1a02c33d5b866e3a82ea2968bf16f"
DB_BLOB_SHA1 = "2f109745d05d194ca9ec76c256455487dda42e02"
DB_URL = f"https://raw.githubusercontent.com/bmenneni/SimpleJavaDmdb/{DB_COMMIT}/duelmasters.db"
IMAGE_BASE_URL = "https://img.duelmasters.us"
ALLOWED_SOURCE_CLASSES = frozenset(
    {
        "official_webp",
        "community_proxy",
        "project_scanstyle_exception",
        "alternate_art_scanstyle_exception",
    }
)
EXCEPTION_SOURCE_CLASSES = frozenset(
    {"project_scanstyle_exception", "alternate_art_scanstyle_exception"}
)
MAPPING_FIELDS = (
    "seq",
    "resource_key",
    "canonical_key",
    "internal_id",
    "english_name",
    "set_label",
    "collector_label",
    "status",
    "source_class",
    "db_card_id",
    "db_name",
    "db_set",
    "db_coll_num",
    "source_file",
    "source_url",
    "source_sha256",
    "source_size",
    "source_colors",
    "compression",
    "compressed_headroom",
    "large_chunk",
    "small_chunk",
)


def git_blob_sha1(data: bytes) -> str:
    prefix = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(prefix + data).hexdigest()  # noqa: S324 - Git object identity, not security


def normalize_name(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(char for char in value if not unicodedata.combining(char)).casefold()
    return "".join(char for char in value if char.isalnum())


def download_file(url: str, destination: Path, *, min_size: int = 1000) -> None:
    """Download an explicitly requested/pinned development source.

    Downloads are never used by tests or release application. A cached file is reused when it
    already satisfies the minimum-size guard.
    """
    if destination.exists() and destination.stat().st_size >= min_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 BOTSD-English-patch/source-builder"}
    )
    error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as out:
                shutil.copyfileobj(response, out)
            if temporary.stat().st_size < min_size:
                raise VerificationError(f"download too small: {temporary}")
            temporary.replace(destination)
            return
        except Exception as exc:  # network fallback path
            error = exc
            temporary.unlink(missing_ok=True)
            time.sleep(1 + attempt)
    # Preserve the historical curl fallback for environments whose Python TLS stack is limited.
    proc = subprocess.run(
        [
            "curl",
            "-fL",
            "--retry",
            "3",
            "--connect-timeout",
            "20",
            "-A",
            "Mozilla/5.0 BOTSD-English-patch/source-builder",
            url,
            "-o",
            str(temporary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode or not temporary.exists() or temporary.stat().st_size < min_size:
        temporary.unlink(missing_ok=True)
        raise VerificationError(f"download failed {url}: {error}; curl: {proc.stderr.strip()}")
    temporary.replace(destination)


def ensure_database(
    cache_dir: Path,
    provided: Path | None = None,
    *,
    offline: bool = False,
    allow_unpinned: bool = False,
) -> Path:
    path = provided or (cache_dir / "duelmasters.db")
    if not path.exists():
        if offline:
            raise FileNotFoundError(f"offline and database absent: {path}")
        download_file(DB_URL, path, min_size=100_000)
    data = path.read_bytes()
    digest = git_blob_sha1(data)
    if digest != DB_BLOB_SHA1 and not allow_unpinned:
        raise HashMismatchError(
            f"card database Git blob SHA-1 {digest} != pinned {DB_BLOB_SHA1}"
        )
    return path


def database_rows(database: str | Path) -> list[dict[str, object]]:
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    try:
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT card_id, card_name, card_set, coll_num FROM CARD ORDER BY card_id"
            )
        ]
    finally:
        connection.close()
    if len(rows) < 900:
        raise VerificationError(f"English card database unexpectedly small: {len(rows)}")
    for row in rows:
        row["card_id"] = int(row["card_id"])
    return rows


def choose_candidate(
    candidates: Iterable[dict[str, object]], set_label: str
) -> tuple[dict[str, object] | None, str]:
    values = list(candidates)

    def card_id(row: dict[str, object]) -> int:
        return int(str(row["card_id"]))

    def official(row: dict[str, object]) -> bool:
        value = card_id(row)
        return value < 901 or 9000 < value < 9081

    def promo(row: dict[str, object]) -> bool:
        value = card_id(row)
        return 9000 < value < 9081

    if set_label.upper().startswith("DM-"):
        same = [
            row
            for row in values
            if str(row.get("card_set") or "").casefold() == set_label.casefold()
        ]
        if same:
            return min(same, key=card_id), (
                "official_set" if len(same) == 1 else "official_set_multi_lowest"
            )
        known = [row for row in values if official(row)]
        if known:
            return min(known, key=card_id), "official_set_mismatch"
        if values:
            return min(values, key=card_id), "community_set_mismatch"
        return None, "no_db_match"

    promos = [row for row in values if promo(row)]
    if promos:
        return min(promos, key=card_id), (
            "official_promo" if len(promos) == 1 else "official_promo_multi_lowest"
        )
    known = [row for row in values if card_id(row) < 901]
    if known:
        return min(known, key=card_id), (
            "official_tcg_reprint" if len(known) == 1 else "official_tcg_reprint_lowest"
        )
    if values:
        return min(values, key=card_id), "community_english_image"
    return None, "no_db_match"


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(handle)]


def build_mapping(
    inventory_path: str | Path,
    crosswalk_path: str | Path,
    database: str | Path,
) -> list[dict[str, object]]:
    inventory = _read_csv(inventory_path)
    if len(inventory) != BASELINE.card_resource_count:
        raise VerificationError(
            f"inventory rows={len(inventory)}; expected {BASELINE.card_resource_count}"
        )
    crosswalk_rows = _read_csv(crosswalk_path)
    crosswalk = {int(row["internal_id"]): row for row in crosswalk_rows}
    if len(crosswalk) != BASELINE.internal_card_count:
        raise VerificationError(
            f"crosswalk rows={len(crosswalk)}; expected {BASELINE.internal_card_count}"
        )

    by_name: dict[str, list[dict[str, object]]] = {}
    for card in database_rows(database):
        by_name.setdefault(normalize_name(str(card["card_name"])), []).append(card)

    output: list[dict[str, object]] = []
    for sequence, row in enumerate(inventory):
        internal_id = int(row["internal_id"])
        identity = crosswalk[internal_id]
        english_name = identity["official_english_name"]
        set_label = identity["set_label"]
        candidate, status = choose_candidate(by_name.get(normalize_name(english_name), []), set_label)
        mapped: dict[str, object] = {
            "seq": sequence,
            "resource_key": row["resource_key"],
            "canonical_key": row["canonical_key"],
            "internal_id": internal_id,
            "english_name": english_name,
            "set_label": set_label,
            "collector_label": identity["collector_label"],
            "status": status,
            "source_class": "",
            "source_file": "",
            "source_sha256": "",
            "source_size": "",
            "source_colors": "",
            "compression": "",
            "compressed_headroom": "",
            "large_chunk": int(row["large_chunk"]),
            "small_chunk": int(row["small_chunk"]),
        }
        if candidate is not None:
            db_id = int(str(candidate["card_id"]))
            mapped.update(
                db_card_id=db_id,
                db_name=str(candidate.get("card_name") or ""),
                db_set=str(candidate.get("card_set") or ""),
                db_coll_num=str(candidate.get("coll_num") or ""),
                source_url=f"{IMAGE_BASE_URL}/{db_id:04d}.webp",
                source_class=("community_proxy" if status.startswith("community_") else "official_webp"),
                source_file=f"images/{db_id:04d}.webp",
            )
        else:
            mapped.update(db_card_id="", db_name="", db_set="", db_coll_num="", source_url="")
        output.append(mapped)
    return output


def load_exception_manifest(exception_dir: str | Path) -> dict[str, tuple[dict[str, str], Path]]:
    root = Path(exception_dir)
    path = root / "manifest.csv"
    if not path.is_file():
        raise FileNotFoundError(f"exception manifest missing: {path}")
    rows = _read_csv(path)
    required = {
        "resource_key",
        "internal_id",
        "english_name",
        "source_class",
        "image_file",
        "image_sha256",
        "provenance",
    }
    if not rows or not required.issubset(rows[0]):
        raise VerificationError(f"exception manifest fields invalid; require {sorted(required)}")
    output: dict[str, tuple[dict[str, str], Path]] = {}
    for row in rows:
        key = row["resource_key"].strip()
        if not key or key in output:
            raise VerificationError(f"duplicate/empty exception resource key {key!r}")
        if row["source_class"] not in EXCEPTION_SOURCE_CLASSES:
            raise VerificationError(f"invalid exception source class {key}: {row['source_class']}")
        image = root / row["image_file"]
        if not image.is_file():
            raise FileNotFoundError(f"exception image missing {key}: {image}")
        digest = sha256_path(image)
        if digest.lower() != row["image_sha256"].lower():
            raise HashMismatchError(
                f"exception image SHA-256 {key}: {digest} != {row['image_sha256']}"
            )
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Pillow is required for card-image source validation") from exc
        with Image.open(image) as opened:
            if opened.size != (384, 512):
                raise VerificationError(
                    f"exception image dimensions {key}: {opened.size}; expected 384x512"
                )
        output[key] = (row, image)
    return output


def apply_exception_sources(
    mapping: list[dict[str, object]], exception_dir: str | Path
) -> dict[str, tuple[dict[str, str], Path]]:
    exceptions = load_exception_manifest(exception_dir)
    unresolved = [row for row in mapping if not row.get("db_card_id")]
    expected = {str(row["resource_key"]) for row in unresolved}
    if set(exceptions) != expected:
        raise VerificationError(
            "exception source set mismatch: "
            f"manifest-only={sorted(set(exceptions)-expected)} missing={sorted(expected-set(exceptions))}"
        )
    for mapped in unresolved:
        key = str(mapped["resource_key"])
        row, image = exceptions[key]
        if (
            int(row["internal_id"]) != int(str(mapped["internal_id"]))
            or row["english_name"] != mapped["english_name"]
        ):
            raise VerificationError(
                f"exception identity mismatch {key}: {row['internal_id']}/{row['english_name']!r}"
            )
        mapped["source_class"] = row["source_class"]
        mapped["source_file"] = row["image_file"]
        mapped["source_url"] = "local://UI76_EXCEPTION_IMAGES/" + row["image_file"]
        mapped["source_sha256"] = row["image_sha256"]
        mapped["source_size"] = "384x512"
        mapped["status"] = (
            "exact_project_scanstyle_alternate_art"
            if row["source_class"] == "alternate_art_scanstyle_exception"
            else "exact_project_scanstyle_exception"
        )
    return exceptions


def save_mapping(rows: Iterable[dict[str, object]], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MAPPING_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
