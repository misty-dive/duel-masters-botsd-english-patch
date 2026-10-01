from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .errors import HashMismatchError, VerificationError
from .extract import extract_release_components
from .hashing import sha256_path
from .manifest import BASELINE, V12_FULL_PPF_SHA256
from .ppf import PPFRecord, PPFStats, header, iter_records, range_payload, verify, write_record
from .v13 import COMPONENT_ORDER, build_component

V13_FULL_PPF_NAME = "Duel_Masters_Birth_of_Super_Dragon_English_v1.3.ppf"
V13_HOTFIX_NAME = "BOTSD_v1.2_to_v1.3_hotfix.ppf"
RELEASE_HASHES_NAME = "RELEASE_HASHES_v1.3.txt"


@dataclass(frozen=True)
class ReleaseArtifact:
    path: Path
    sha256: str
    size: int
    stats: PPFStats


@dataclass(frozen=True)
class V13ReleaseBuild:
    full: ReleaseArtifact
    hotfix: ReleaseArtifact
    report: Path


def _diff_records(old: bytes, new: bytes, absolute_base: int) -> list[PPFRecord]:
    if len(old) != len(new):
        raise ValueError("v1.3 maintenance components must remain same-size")
    out: list[PPFRecord] = []
    i = 0
    while i < len(old):
        if old[i] == new[i]:
            i += 1
            continue
        start = i
        payload = bytearray()
        while i < len(old) and old[i] != new[i] and len(payload) < 0xFF:
            payload.append(new[i])
            i += 1
        out.append(PPFRecord(absolute_base + start, bytes(payload)))
    return out


def _validate_public_v12_layout(v12_ppf: Path, components: dict[str, bytes]) -> None:
    # These three localized components are fully covered by the public v1.2 PPF.
    for name in ("SCRPACK.SDA", "TCHANGE.IMG", "DECK.DAT"):
        component = BASELINE.component(name)
        got, mask = range_payload(v12_ppf, component.iso_offset, len(components[name]))
        if not all(mask):
            raise VerificationError(f"{name}: official v1.2 PPF does not fully cover file range")
        if got != components[name]:
            raise VerificationError(f"{name}: v1.2 PPF bytes do not match exact component")

    # The executable includes retail-identical gaps. Validate every byte that the public
    # v1.2 PPF does cover, then prove every v1.3 executable edit lies in covered space.
    name = "SLPM_658.82"
    component = BASELINE.component(name)
    source = components[name]
    got, mask = range_payload(v12_ppf, component.iso_offset, len(source))
    covered = sum(mask)
    if covered < 1_000_000:
        raise VerificationError(f"{name}: unexpectedly low public-v1.2 PPF coverage: {covered}")
    for index, flag in enumerate(mask):
        if flag and got[index] != source[index]:
            raise VerificationError(f"{name}: v1.2 PPF mismatch at relative 0x{index:X}")
    target = build_component(name, source)
    for index, (before, after) in enumerate(zip(source, target, strict=True)):
        if before != after and not mask[index]:
            raise VerificationError(
                f"{name}: v1.3 edit at relative 0x{index:X} is not covered by v1.2 full PPF"
            )


def _build_hotfix(
    v12_components: dict[str, bytes],
    v13_components: dict[str, bytes],
    output: Path,
) -> list[PPFRecord]:
    records: list[PPFRecord] = []
    for name in COMPONENT_ORDER:
        component = BASELINE.component(name)
        records.extend(
            _diff_records(v12_components[name], v13_components[name], component.iso_offset)
        )
    records.sort(key=lambda row: row.offset)
    previous_end = -1
    for row in records:
        if row.offset < previous_end:
            raise VerificationError("generated hotfix records overlap")
        previous_end = row.end

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write(header("Duel Masters BOTSD v1.2 to v1.3"))
        for row in records:
            write_record(stream, row.offset, row.payload)
    verify(output)
    return records


def _merge_full_ppf(v12_ppf: Path, overlay_records: list[PPFRecord], output: Path) -> PPFStats:
    overlay: dict[int, int] = {}
    for record in overlay_records:
        for index, value in enumerate(record.payload):
            position = record.offset + index
            if position in overlay:
                raise VerificationError("v1.3 overlay byte overlap")
            overlay[position] = value

    remaining = dict(overlay)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write(header("Duel Masters BOTSD English v1.3"))
        for record in iter_records(v12_ppf):
            payload = bytearray(record.payload)
            for index in range(len(payload)):
                position = record.offset + index
                if position in remaining:
                    payload[index] = remaining.pop(position)
            write_record(stream, record.offset, bytes(payload))

        # v1.3 currently has no remaining bytes because every edit is already within
        # a v1.2 full-patch record. Keep this general for later maintenance releases.
        positions = sorted(remaining)
        i = 0
        while i < len(positions):
            start = positions[i]
            payload = bytearray([remaining[start]])
            i += 1
            while (
                i < len(positions)
                and positions[i] == start + len(payload)
                and len(payload) < 0xFF
            ):
                payload.append(remaining[positions[i]])
                i += 1
            write_record(stream, start, bytes(payload))
    return verify(output)


def _verify_full_targets(full_ppf: Path, v13_components: dict[str, bytes]) -> None:
    for name in ("SCRPACK.SDA", "TCHANGE.IMG", "DECK.DAT"):
        component = BASELINE.component(name)
        wanted = v13_components[name]
        got, mask = range_payload(full_ppf, component.iso_offset, len(wanted))
        if not all(mask) or got != wanted:
            raise VerificationError(f"full v1.3 PPF target verification failed for {name}")

    component = BASELINE.component("SLPM_658.82")
    wanted = v13_components["SLPM_658.82"]
    got, mask = range_payload(full_ppf, component.iso_offset, len(wanted))
    for index, flag in enumerate(mask):
        if flag and got[index] != wanted[index]:
            raise VerificationError(
                f"full v1.3 PPF executable mismatch at relative 0x{index:X}"
            )


def build_v13_release(
    v12_dir: str | Path,
    v12_full_ppf: str | Path,
    output_dir: str | Path,
) -> V13ReleaseBuild:
    source_dir = Path(v12_dir)
    previous_ppf = Path(v12_full_ppf)
    outdir = Path(output_dir)

    if sha256_path(previous_ppf) != V12_FULL_PPF_SHA256:
        raise HashMismatchError("official v1.2 full PPF SHA-256 mismatch")
    v12_stats = verify(previous_ppf)

    v12: dict[str, bytes] = {}
    v13: dict[str, bytes] = {}
    for name in COMPONENT_ORDER:
        path = source_dir / name
        if not path.is_file():
            raise FileNotFoundError(path)
        source = path.read_bytes()
        # build_component performs exact public-v1.2 size/hash guards.
        target = build_component(name, source)
        v12[name] = source
        v13[name] = target

    _validate_public_v12_layout(previous_ppf, v12)

    outdir.mkdir(parents=True, exist_ok=True)
    hotfix_path = outdir / V13_HOTFIX_NAME
    full_path = outdir / V13_FULL_PPF_NAME
    overlay = _build_hotfix(v12, v13, hotfix_path)
    full_stats = _merge_full_ppf(previous_ppf, overlay, full_path)
    hotfix_stats = verify(hotfix_path)
    _verify_full_targets(full_path, v13)

    # This is a known property of the published v1.3 release and protects the exact
    # historical release artifact during repository refactors.
    if full_stats != v12_stats or full_path.stat().st_size != previous_ppf.stat().st_size:
        raise VerificationError("unexpected v1.3 full-PPF footprint change")

    full_hash = sha256_path(full_path)
    hotfix_hash = sha256_path(hotfix_path)
    if full_path.stat().st_size != BASELINE.full_ppf_size or full_hash != BASELINE.full_ppf_sha256:
        raise VerificationError(
            f"full v1.3 PPF differs from published release: size={full_path.stat().st_size} "
            f"sha256={full_hash}"
        )
    if (
        hotfix_path.stat().st_size != BASELINE.hotfix_from_v12_size
        or hotfix_hash != BASELINE.hotfix_from_v12_sha256
    ):
        raise VerificationError(
            f"v1.2->v1.3 hotfix differs from published release: size={hotfix_path.stat().st_size} "
            f"sha256={hotfix_hash}"
        )

    report_path = outdir / RELEASE_HASHES_NAME
    lines = [
        "Duel Masters: Birth of the Super Dragon — English v1.3 release hashes",
        "",
        f"Official v1.2 full PPF SHA-256: {V12_FULL_PPF_SHA256}",
        "",
        V13_FULL_PPF_NAME,
        f"  size: {full_path.stat().st_size}",
        f"  SHA-256: {full_hash}",
        f"  records: {full_stats.records}",
        f"  payload bytes: {full_stats.payload_bytes}",
        "",
        V13_HOTFIX_NAME,
        f"  size: {hotfix_path.stat().st_size}",
        f"  SHA-256: {hotfix_hash}",
        f"  records: {hotfix_stats.records}",
        f"  payload bytes: {hotfix_stats.payload_bytes}",
        "",
        "v1.3 maintenance components:",
    ]
    for name in COMPONENT_ORDER:
        component = BASELINE.component(name)
        changed = sum(
            len(record.payload)
            for record in overlay
            if component.iso_offset <= record.offset < component.iso_offset + component.v13.size
        )
        lines.append(
            f"  {name}: ISO_offset=0x{component.iso_offset:X} LBA={component.iso_offset // 2048} "
            f"size={component.v13.size} changed_bytes={changed} "
            f"v1.3_sha256={component.v13.sha256}"
        )
    lines += [
        "",
        "Verification:",
        "  official v1.2 PPF hash/structure=PASS",
        "  public-v1.2 component guards=PASS",
        "  verified public-v1.2 file locations=PASS",
        "  semantic v1.3 component reconstruction=PASS",
        "  v1.3 full PPF target verification=PASS",
        "  v1.3 hotfix records sorted/non-overlapping=PASS",
        "  full v1.3 PPF footprint equals official v1.2 PPF footprint=PASS",
        "  published v1.3 PPF/hotfix hashes reproduced exactly=PASS",
        "  RESULT=PASS",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return V13ReleaseBuild(
        full=ReleaseArtifact(
            full_path, full_hash, full_path.stat().st_size, full_stats
        ),
        hotfix=ReleaseArtifact(
            hotfix_path, hotfix_hash, hotfix_path.stat().st_size, hotfix_stats
        ),
        report=report_path,
    )


def build_v13_release_from_iso(
    v12_iso: str | Path,
    v12_full_ppf: str | Path,
    output_dir: str | Path,
) -> V13ReleaseBuild:
    """Rebuild the published v1.3 release directly from an exact public-v1.2 ISO.

    Component extraction is streaming and hash/location guarded; the temporary component
    directory is removed automatically after the published PPFs are reproduced.
    """
    with TemporaryDirectory(prefix="botsd-v12-components-") as temp:
        extract_release_components(v12_iso, temp, version="v1.2")
        return build_v13_release(temp, v12_full_ppf, output_dir)
