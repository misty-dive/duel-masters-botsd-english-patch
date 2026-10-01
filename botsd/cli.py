from __future__ import annotations

import argparse
from pathlib import Path

from .build import build_release_image
from .cardinfo import build_embedded_cardinfo, load_spec as load_cardinfo_spec
from .cardfaces import build_card_faces, load_spec as load_cardface_spec
from .cardtext import (
    build_combined_list,
    build_externalized,
    check_patch_sites,
    materialize_translation_rows,
    parse_master_text,
    parse_retail_list_bytes,
    read_csv_rows,
)
from .datapack import apply_chunk_patch
from .dataqa import audit_repository_data, format_issues
from .decktext import patch_directory as patch_deck_text_directory
from .duelpts import build_issue2_fix, load_spec as load_duelpts_spec
from .errors import BotSDError, HashMismatchError
from .exec_strings import load_asset_spec as load_exec_string_spec
from .exec_strings import load_strings as load_exec_strings
from .exec_strings import patch_fixed_slots
from .extract import extract_release_components, verify_hash_manifest
from .flavor import import_flavor, load_json_cards, read_csv as read_flavor_csv, write_csv as write_flavor_csv
from .font_polish import patch_minimal_ascii_polish
from .fontlink import load_ue_spec, patch_reserved_ue
from .fullcard import build_full_card_images
from .gamefont import GameFont
from .graphic_residuals import build_all as build_graphic_residuals
from .hashing import sha256_bytes, sha256_path
from .iso9660 import Iso9660, patch_iso
from .keyboard import build_historical_v12_stage
from .localization import audit_manifest as audit_localization_manifest
from .localization import export_provenance
from .manifest import BASELINE, RETAIL_SHA256
from .ppf import build as build_ppf
from .ppf import verify as verify_ppf
from .qa_matrix import audit_qa_directory, format_qa_issues, summarize_playthrough
from .release import build_v13_release, build_v13_release_from_iso
from .ruleswrap import read_csv as read_wrap_csv, wrap_rule_tables, write_csv as write_wrap_csv
from .second_names import render_second_names
from .shop import load_booster_descriptions, patch_booster_descriptions
from .storytext import (
    apply_story_language,
    audit_story_language,
    build_story_catalog,
    load_story_choice_translations,
    load_story_dialogue_translations,
    write_story_catalog,
)
from .static_labels import build_all as build_static_labels
from .textqa import scan_csv_fields
from .ui_polish_v11 import build_all as build_ui_polish_v11
from .unpack import apply_second_name_patch, create_second_name_patch, verify_ui76, verify_ui82
from .v13 import build_directory as build_v13_directory
from .wait_title import build_title as build_wait_title_title
from .wait_title import build_wait as build_wait_title_wait
from .wait_title import load_spec as load_wait_title_spec
from .wait_title import load_strings as load_wait_title_strings


def cmd_manifest(_: argparse.Namespace) -> int:
    print(f"{BASELINE.serial} {BASELINE.release}")
    print(f"clean_iso_size={BASELINE.clean_iso_size}")
    print(f"clean_iso_sha256={BASELINE.clean_iso_sha256}")
    print(f"patched_iso_size={BASELINE.patched_iso_size}")
    print(f"full_ppf_sha256={BASELINE.full_ppf_sha256}")
    print(f"combined_text_pointers={BASELINE.combined_text_pointer_count}")
    for component in BASELINE.components:
        print(
            f"{component.name}: v1.3 size={component.v13.size} "
            f"sha256={component.v13.sha256} iso_offset=0x{component.iso_offset:X}"
        )
    return 0


def cmd_verify_file(args: argparse.Namespace) -> int:
    component = BASELINE.component(args.component)
    expected = component.v12 if args.version == "v1.2" else component.v13
    path = Path(args.path)
    if path.stat().st_size != expected.size:
        raise HashMismatchError(
            f"{component.name}: size {path.stat().st_size} != expected {expected.size}"
        )
    got = sha256_path(path)
    if got != expected.sha256:
        raise HashMismatchError(f"{component.name}: SHA-256 {got} != expected {expected.sha256}")
    print(f"PASS {component.name} {args.version} {got}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    report = build_release_image(
        args.source,
        args.patch,
        args.output,
        allow_unverified_patch=args.allow_unverified_patch,
    )
    print("BOTSD release-image build: PASS")
    print(f"source_sha256={report.source_sha256}")
    print(f"patch_sha256={report.patch_sha256}")
    print(f"output={Path(args.output)}")
    print(f"output_size={report.output_size}")
    print(f"ppf_records={report.ppf.records}")
    print(f"ppf_payload_bytes={report.ppf.payload_bytes}")
    return 0


def cmd_ppf_info(args: argparse.Namespace) -> int:
    stats = verify_ppf(args.patch)
    print(f"patch={args.patch}")
    print(f"sha256={sha256_path(args.patch)}")
    print(f"records={stats.records}")
    print(f"payload_bytes={stats.payload_bytes}")
    print(f"max_end={stats.max_end}")
    return 0


def cmd_ppf_create(args: argparse.Namespace) -> int:
    stats, changed = build_ppf(
        args.source,
        args.target,
        args.output,
        description=args.description,
    )
    print("PPF3 build: PASS")
    print(f"output={args.output}")
    print(f"sha256={sha256_path(args.output)}")
    print(f"records={stats.records}")
    print(f"payload_bytes={stats.payload_bytes}")
    print(f"changed_bytes={changed}")
    return 0


def cmd_iso_list(args: argparse.Namespace) -> int:
    image = Iso9660(args.iso)
    entries = image.entries()
    if args.basename:
        entry = image.find_unique_basename(args.basename)
        entries = (entry,)
    for entry in entries:
        kind = "dir" if entry.flags & 0x02 else "file"
        print(f"{kind:4s} LBA={entry.extent:8d} size={entry.size:9d} {entry.path}")
    return 0


def cmd_iso_patch(args: argparse.Namespace) -> int:
    rows = patch_iso(
        args.source,
        args.output,
        args.replacement,
        strict_core=not args.allow_nonretail,
    )
    print("ISO9660 patch: PASS")
    for row in rows:
        print(
            f"{row.path}: {row.mode}; LBA {row.old_lba}->{row.new_lba}; "
            f"size {row.old_size}->{row.new_size}; sha256={row.sha256}"
        )
    print(f"output_sha256={sha256_path(args.output)}")
    return 0




def cmd_shop_descriptions(args: argparse.Namespace) -> int:
    source = args.input_elf.read_bytes()
    records = load_booster_descriptions(args.translations)
    target = patch_booster_descriptions(source, records)
    args.output_elf.parent.mkdir(parents=True, exist_ok=True)
    args.output_elf.write_bytes(target)
    print(f"output={args.output_elf}")
    print(f"sha256={sha256_path(args.output_elf)}")
    return 0


def cmd_datapack_patch(args: argparse.Namespace) -> int:
    target, result = apply_chunk_patch(args.retail.read_bytes(), args.patch)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    print(f"output={args.output}")
    print(f"changed_chunks={','.join(str(v) for v in result.changed_chunks)}")
    print(f"sha256={result.sha256}")
    return 0


def cmd_deck_text(args: argparse.Namespace) -> int:
    rows = patch_deck_text_directory(args.input_dir, args.output_dir, args.translations)
    print(f"files={len(rows)}")
    for row in rows:
        print(
            f"{row.filename}: {row.source_sha256} -> {row.target_sha256} "
            f"({row.size} bytes)"
        )
    print("containment=PASS")
    return 0


def cmd_font_polish(args: argparse.Namespace) -> int:
    source = args.input.read_bytes()
    result = patch_minimal_ascii_polish(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result.data)
    print(f"output={args.output}")
    print(f"sha256={sha256_path(args.output)}")
    print(f"changed_members={','.join(result.changed_members)}")
    return 0


def cmd_font_ue_patch(args: argparse.Namespace) -> int:
    spec = load_ue_spec(args.spec)
    input_asset = str(spec["input_asset"])
    source = args.input.read_bytes()
    got = sha256_bytes(source)
    if not args.allow_unverified_input:
        expected = RETAIL_SHA256[input_asset]
        if got != expected:
            raise HashMismatchError(
                f"{input_asset}: SHA-256 {got} != expected retail {expected}"
            )
    target = patch_reserved_ue(source, spec_path=args.spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    print("FONTLINK reserved U-diaeresis patch: PASS")
    print(f"input_sha256={got}")
    print(f"output={args.output}")
    print(f"output_sha256={sha256_bytes(target)}")
    print(f"source_page={spec['source_page']}")
    print(f"target_page={spec['target_page']}")
    return 0


def cmd_keyboard_v12_stage(args: argparse.Namespace) -> int:
    result = build_historical_v12_stage(args.input_elf.read_bytes())
    args.output_elf.parent.mkdir(parents=True, exist_ok=True)
    args.output_elf.write_bytes(result.data)
    print("Historical v1.2 keyboard-mode stage: PASS")
    print(f"input_sha256={result.input_sha256}")
    print(f"output={args.output_elf}")
    print(f"output_sha256={result.output_sha256}")
    print(f"offset=0x{result.offset:X}")
    print(f"mode={result.old_mode}->{result.new_mode}")
    return 0


def cmd_static_labels(args: argparse.Namespace) -> int:
    results = build_static_labels(
        {"adv": args.adv, "advscn": args.advscn, "duelpts": args.duelpts},
        args.output_dir,
        args.font,
        args.spec,
        args.strings,
    )
    print("UI81 static-label build: PASS")
    for key in ("advscn", "adv", "duelpts"):
        print(f"[{key}]")
        for line in results[key].report_lines:
            print(line)
    return 0


def cmd_graphic_residuals(args: argparse.Namespace) -> int:
    results = build_graphic_residuals(
        {"lobby": args.lobby_in, "tour": args.tour_in, "deck": args.deck_in},
        {"lobby": args.lobby_out, "tour": args.tour_out, "deck": args.deck_out},
        args.spec,
    )
    print("UI82 residual-graphics build: PASS")
    for key in ("lobby", "tour", "deck"):
        print(f"[{key}]")
        for line in results[key].report_lines:
            print(line)
    return 0


def cmd_exec_residuals(args: argparse.Namespace) -> int:
    spec = load_exec_string_spec(args.spec)
    strings = load_exec_strings(args.strings)
    result = patch_fixed_slots(args.input_elf.read_bytes(), spec, strings)
    args.output_elf.parent.mkdir(parents=True, exist_ok=True)
    args.output_elf.write_bytes(result.data)
    print("UI82 offline executable residual build: PASS")
    for line in result.report_lines:
        print(line)
    return 0


def cmd_wait_title(args: argparse.Namespace) -> int:
    spec = load_wait_title_spec(args.spec)
    strings = load_wait_title_strings(args.strings)
    font = GameFont(args.fontlink)
    wait = build_wait_title_wait(args.wait_in.read_bytes(), font, spec["wait"], strings)
    title = build_wait_title_title(args.title_in.read_bytes(), spec["title"])
    args.wait_out.parent.mkdir(parents=True, exist_ok=True)
    args.title_out.parent.mkdir(parents=True, exist_ok=True)
    args.wait_out.write_bytes(wait.data)
    args.title_out.write_bytes(title.data)
    print("UI82 WAIT/TITLE build: PASS")
    for label, result in (("WAIT", wait), ("TITLE", title)):
        print(f"[{label}]")
        for line in result.report_lines:
            print(line)
    return 0


def cmd_ui_polish_v11(args: argparse.Namespace) -> int:
    result = build_ui_polish_v11(
        args.opt.read_bytes(),
        args.deck.read_bytes(),
        args.exe.read_bytes(),
        args.font,
        args.strings,
        spec_path=args.spec,
    )
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "OPT_UI11_POLISH.DAT").write_bytes(result.opt)
    (args.outdir / "DECK_UI11_POLISH.DAT").write_bytes(result.deck)
    (args.outdir / "SLPM_658.82_UI11_POLISH").write_bytes(result.executable)
    print("V1.1 UI polish build: PASS")
    for line in result.report_lines:
        print(line)
    return 0


def cmd_duelpts_fix(args: argparse.Namespace) -> int:
    result = build_issue2_fix(
        args.clean_duelpts.read_bytes(),
        args.v11_duelpts.read_bytes(),
        spec=load_duelpts_spec(args.spec) if args.spec else None,
        verify_hashes=not args.allow_nonretail,
    )
    args.output_duelpts.parent.mkdir(parents=True, exist_ok=True)
    args.output_duelpts.write_bytes(result.data)
    print("DUELPTS Issue #2 repair: PASS")
    for line in result.report_lines:
        print(line)
    return 0


def cmd_cardinfo_embed(args: argparse.Namespace) -> int:
    result = build_embedded_cardinfo(
        args.input_elf.read_bytes(),
        args.master_csv,
        spec=load_cardinfo_spec(args.spec) if args.spec else None,
    )
    args.output_elf.parent.mkdir(parents=True, exist_ok=True)
    args.output_elf.write_bytes(result.data)
    print("UI76 embedded Card Info build: PASS")
    for line in result.report_lines:
        print(line)
    return 0


def cmd_cardfaces_build(args: argparse.Namespace) -> int:
    rows = build_card_faces(
        args.unpack,
        args.inventory,
        args.fontlink,
        args.output,
        master_csv=args.master,
        spec=load_cardface_spec(args.spec) if args.spec else None,
        start=args.start,
        end=args.end,
        verify_retail=not args.allow_nonretail,
    )
    print("UI75 card-face build: PASS")
    print(f"cards={len(rows)}")
    if rows:
        print(f"min_compressed_headroom={min(row.metrics.compressed_headroom for row in rows)}")
        print(f"optimal_compressor_cards={sum(row.metrics.compression == 'optimal' for row in rows)}")
    return 0


def cmd_fullcard_build(args: argparse.Namespace) -> int:
    report = build_full_card_images(
        args.base_unpack,
        args.inventory,
        args.crosswalk,
        args.output,
        args.qa_dir,
        cache_dir=args.cache_dir,
        exception_dir=args.exception_dir,
        database=args.db,
        offline=args.offline,
        allow_unpinned_db=args.allow_unpinned_db,
        verify_retail=not args.allow_nonretail,
    )
    print("UI76 whole-card image build: PASS")
    print(f"output_sha256={report.output_sha256}")
    print(f"resources={report.resources}")
    print(f"changed_chunks={report.changed_chunks}")
    print(f"min_compressed_headroom={report.min_compressed_headroom}")
    print(f"min_source_colors={report.min_source_colors}")
    return 0


def cmd_unpack_render_second_names(args: argparse.Namespace) -> int:
    result = render_second_names(
        args.retail,
        args.inventory,
        args.fontlink,
        args.output_zip,
        qa_dir=args.qa_dir,
        report_csv=args.report,
        verify_retail=not args.allow_nonretail,
        verify_frozen_output=not args.allow_nonfrozen_output,
    )
    print("UI82 semantic second-name render: PASS")
    print(f"retail_sha256={result.retail_sha256}")
    print(f"payload_sha256={result.payload_sha256}")
    print(f"patch_zip_sha256={result.patch_zip_sha256}")
    print(f"chunks={result.chunks}")
    print(f"fallback_title_detectors={result.fallback_title_detectors}")
    print(f"changed_pixels_total={result.changed_pixels_total}")
    return 0


def cmd_unpack_create_second_names(args: argparse.Namespace) -> int:
    result = create_second_name_patch(
        args.retail,
        args.ui76,
        args.ui82,
        args.output_zip,
        inventory=args.inventory,
        verify_retail=not args.allow_nonretail,
    )
    print("UI82 second-name patch creation: PASS")
    print(f"retail_sha256={result.retail_sha256}")
    print(f"ui82_sha256={result.target_sha256}")
    print(f"payload_chunks={len(result.changed_chunks)}")
    return 0


def cmd_unpack_apply_second_names(args: argparse.Namespace) -> int:
    result = apply_second_name_patch(args.ui76, args.patch_zip, args.output)
    print("UI82 second-name UNPACK patch: PASS")
    print(f"input_sha256={result.retail_sha256}")
    print(f"output_sha256={result.target_sha256}")
    print(f"changed_chunks={len(result.changed_chunks)}")
    return 0


def cmd_unpack_verify_ui76(args: argparse.Namespace) -> int:
    result = verify_ui76(args.retail, args.compiled, args.inventory)
    print("UI76 frozen UNPACK verification: PASS")
    print(f"retail_sha256={result.retail_sha256}")
    print(f"compiled_sha256={result.target_sha256}")
    print(f"changed_chunks={len(result.changed_chunks)}")
    return 0


def cmd_unpack_verify_ui82(args: argparse.Namespace) -> int:
    result, delta = verify_ui82(args.retail, args.ui76, args.ui82, args.inventory, args.patch_zip)
    print("UI82 frozen UNPACK verification: PASS")
    print(f"retail_sha256={result.retail_sha256}")
    print(f"ui82_sha256={result.target_sha256}")
    print(f"ui82_changed_chunks={len(result.changed_chunks)}")
    print(f"ui76_to_ui82_delta={len(delta)}")
    return 0


def cmd_iso_verify_assets(args: argparse.Namespace) -> int:
    extracts: dict[str, str | Path] = {}
    for item in args.extract:
        if "=" not in item:
            raise ValueError(f"invalid --extract {item!r}; expected BASENAME=OUTPUT")
        name, output = item.split("=", 1)
        extracts[name] = Path(output)
    rows = verify_hash_manifest(args.iso, args.hashes, extracts)
    for row in rows:
        print(f"PASS {row.iso_path} size={row.size} sha256={row.sha256}")
        if row.output is not None:
            print(f"  extracted={row.output}")
    return 0


def cmd_extract_components(args: argparse.Namespace) -> int:
    rows = extract_release_components(args.iso, args.output_dir, version=args.version)
    print(f"BOTSD {args.version} component extraction: PASS")
    for row in rows:
        print(f"{row.name}: offset=0x{row.offset:X} size={row.size} sha256={row.sha256}")
    return 0


def cmd_v13_release_from_iso(args: argparse.Namespace) -> int:
    build = build_v13_release_from_iso(args.v12_iso, args.v12_full_ppf, args.output_dir)
    print("BOTSD v1.3 release build from public-v1.2 ISO: PASS")
    print(f"full={build.full.path}")
    print(f"full_sha256={build.full.sha256}")
    print(f"hotfix={build.hotfix.path}")
    print(f"hotfix_sha256={build.hotfix.sha256}")
    print(f"report={build.report}")
    return 0


def cmd_v13_components(args: argparse.Namespace) -> int:
    rows = build_v13_directory(args.v12_dir, args.output_dir)
    print("BOTSD v1.3 semantic maintenance build: PASS")
    for row in rows:
        print(
            f"{row.name}: {row.source_sha256} -> {row.target_sha256} "
            f"({row.size} bytes)"
        )
    return 0


def cmd_v13_release(args: argparse.Namespace) -> int:
    build = build_v13_release(args.v12_dir, args.v12_full_ppf, args.output_dir)
    print("BOTSD v1.3 release build: PASS")
    print(f"full={build.full.path}")
    print(f"full_sha256={build.full.sha256}")
    print(f"hotfix={build.hotfix.path}")
    print(f"hotfix_sha256={build.hotfix.sha256}")
    print(f"report={build.report}")
    return 0


def cmd_qa_summary(args: argparse.Namespace) -> int:
    summary = summarize_playthrough(args.matrix)
    print(f"rows={summary.rows}")
    for status, count in summary.by_status.items():
        print(f"status.{status}={count}")
    for area, count in summary.by_area.items():
        print(f"area.{area}={count}")
    return 0



def cmd_qa_audit(args: argparse.Namespace) -> int:
    issues = audit_qa_directory(args.qa_dir)
    for line in format_qa_issues(issues):
        print(line)
    print(f"issues={len(issues)}")
    return 1 if issues else 0


def cmd_localization_audit(args: argparse.Namespace) -> int:
    issues = audit_localization_manifest(args.manifest, args.root)
    for issue in issues:
        where = issue.dataset
        if issue.row is not None:
            where += f":{issue.row}"
        if issue.field:
            where += f":{issue.field}"
        print(f"error: {where}: {issue.message}")
    print(f"issues={len(issues)}")
    return 1 if issues else 0


def cmd_provenance_export(args: argparse.Namespace) -> int:
    count = export_provenance(args.manifest, args.output, args.root)
    print(f"rows={count}")
    print(f"output={args.output}")
    return 0


def cmd_text_audit(args: argparse.Namespace) -> int:
    findings = scan_csv_fields(args.csv, tuple(args.field), max_segment=args.max_segment)
    for finding in findings:
        print(
            f"{finding.kind}: {finding.source}:{finding.row}:{finding.field}: "
            f"{finding.text!r}"
        )
    print(f"findings={len(findings)}")
    return 1 if findings and args.fail_on_findings else 0


def cmd_combined_list(args: argparse.Namespace) -> int:
    display_rows = read_csv_rows(args.display)
    master_rows = read_csv_rows(args.master)
    display = materialize_translation_rows(display_rows, "list_index", BASELINE.display_text_count)
    master = materialize_translation_rows(master_rows, "master_text_id", BASELINE.master_text_count)
    raw = build_combined_list(display, master)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    print(f"output={args.output}")
    print(f"size={len(raw)}")
    print(f"sha256={sha256_path(args.output)}")
    return 0


def cmd_cardtext_check(args: argparse.Namespace) -> int:
    executable = args.executable.read_bytes()
    retail_list = args.list1.read_bytes()
    check_patch_sites(executable)
    display = parse_retail_list_bytes(retail_list)
    master = parse_master_text(executable)
    print(f"retail_display_pointers={len(display)}")
    print(f"meaningful_display_entries={BASELINE.display_text_count}")
    print(f"master_entries={len(master)}")
    print(f"combined_pointer_count={BASELINE.combined_text_pointer_count}")
    print("patch_sites=PASS")
    return 0


def cmd_cardtext_externalize(args: argparse.Namespace) -> int:
    result = build_externalized(
        args.executable.read_bytes(),
        args.list1.read_bytes(),
        args.master_csv,
        args.display_csv,
    )
    args.output_executable.parent.mkdir(parents=True, exist_ok=True)
    args.output_list1.parent.mkdir(parents=True, exist_ok=True)
    args.output_executable.write_bytes(result.executable)
    args.output_list1.write_bytes(result.combined_list)
    print(f"executable={args.output_executable}")
    print(f"executable_sha256={sha256_path(args.output_executable)}")
    print(f"list1={args.output_list1}")
    print(f"list1_size={len(result.combined_list)}")
    print(f"list1_sha256={sha256_path(args.output_list1)}")
    print("roundtrip=PASS")
    return 0


def cmd_scrpack_catalog(args: argparse.Namespace) -> int:
    rows, report = build_story_catalog(
        args.retail.read_bytes(),
        args.translated.read_bytes(),
    )
    count = write_story_catalog(args.output, rows)
    print("SCRPACK story-text catalog: PASS")
    print(f"output={args.output}")
    print(f"rows={count}")
    print(f"chunks={report.chunks}")
    print(f"translated_rows={report.translated_rows}")
    print(f"identical_rows={report.identical_rows}")
    return 0


def cmd_scrpack_language_audit(args: argparse.Namespace) -> int:
    dialogue = load_story_dialogue_translations(args.dialogue)
    choices = load_story_choice_translations(args.choices)
    data = args.translated.read_bytes()
    if not args.allow_nonfrozen_target:
        expected = BASELINE.component("SCRPACK.SDA").v12
        if len(data) != expected.size or sha256_path(args.translated) != expected.sha256:
            raise HashMismatchError("SCRPACK v1.2 target size/SHA-256 mismatch")
    report = audit_story_language(data, dialogue, choices)
    print("SCRPACK v1.2 language audit: PASS")
    print(f"dialogue_rows={report.dialogue_rows}")
    print(f"choice_rows={report.choice_rows}")
    print(f"dialogue_commands={report.dialogue_commands}")
    print(f"choice_commands={report.choice_commands}")
    print(f"chunks={report.chunks}")
    return 0


def cmd_scrpack_apply_language(args: argparse.Namespace) -> int:
    source = args.retail.read_bytes()
    if not args.allow_nonretail:
        expected_retail = RETAIL_SHA256["SCRPACK.SDA"]
        got = sha256_path(args.retail)
        if got != expected_retail:
            raise HashMismatchError(
                f"retail SCRPACK SHA-256 {got} != expected {expected_retail}"
            )
    dialogue = load_story_dialogue_translations(args.dialogue)
    choices = load_story_choice_translations(args.choices)
    target = apply_story_language(source, dialogue, choices)
    expected = BASELINE.component("SCRPACK.SDA").v12
    target_hash = sha256_bytes(target)
    if not args.allow_nonfrozen_output and (
        len(target) != expected.size or target_hash != expected.sha256
    ):
        raise HashMismatchError(
            f"generated SCRPACK differs from public v1.2: size={len(target)} sha256={target_hash}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    print("SCRPACK v1.2 language build: PASS")
    print(f"output={args.output}")
    print(f"size={len(target)}")
    print(f"sha256={target_hash}")
    print(f"dialogue_rows={len(dialogue)}")
    print(f"choice_rows={len(choices)}")
    return 0


def cmd_data_audit(args: argparse.Namespace) -> int:
    issues = audit_repository_data(args.data_dir)
    for line in format_issues(issues):
        print(line)
    errors = sum(issue.severity == "error" for issue in issues)
    print(f"issues={len(issues)}")
    print(f"errors={errors}")
    return 1 if errors else 0



def cmd_rules_wrap(args: argparse.Namespace) -> int:
    master_fields, master_rows = read_wrap_csv(args.master_in)
    display_fields, display_rows = read_wrap_csv(args.display_in)
    report = wrap_rule_tables(master_rows, display_rows)
    write_wrap_csv(args.master_out, master_fields, master_rows)
    write_wrap_csv(args.display_out, display_fields, display_rows)
    print("Card-rule word-wrap: PASS")
    print(f"rules_verified={report.rules_verified}")
    print(f"rules_with_added_wraps={report.rules_with_added_wraps}")
    print(f"new_linebreaks_inserted={report.new_linebreaks_inserted}")
    print(f"display_rows_synchronized={report.display_rows_synchronized}")
    print(f"max_line_cells_before={report.max_line_cells_before}")
    print(f"max_line_cells_after={report.max_line_cells_after}")
    print(f"max_wrapped_lines_per_rule={report.max_wrapped_lines_per_rule}")
    return 0


def cmd_flavor_import(args: argparse.Namespace) -> int:
    cards = load_json_cards(args.json)
    cross = read_flavor_csv(args.crosswalk)
    master = read_flavor_csv(args.master_in)
    display = read_flavor_csv(args.display_in)
    qa, report = import_flavor(
        cards, cross, master, display,
        unique_reprint_fallback=args.unique_reprint_fallback,
    )
    write_flavor_csv(args.master_out, master)
    write_flavor_csv(args.display_out, display)
    write_flavor_csv(args.qa_out, qa)
    print("BOTSD flavor import")
    for key, value in report.__dict__.items():
        print(f"{key}={value}")
    if args.strict and report.remaining_untranslated_source_flavor:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="botsd")
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("manifest", help="print the authoritative v1.3 baseline manifest")
    command.set_defaults(func=cmd_manifest)

    command = sub.add_parser("verify-file", help="verify a v1.2/v1.3 maintenance component")
    command.add_argument("component")
    command.add_argument("path")
    command.add_argument("--version", choices=("v1.2", "v1.3"), default="v1.3")
    command.set_defaults(func=cmd_verify_file)

    command = sub.add_parser(
        "build",
        help="build a verified v1.3 ISO from the clean retail ISO and the release PPF",
    )
    command.add_argument("--source", type=Path, required=True, help="clean Japanese SLPM-65882 ISO")
    command.add_argument("--patch", type=Path, required=True, help="full v1.3 release PPF")
    command.add_argument("--output", type=Path, required=True, help="output patched ISO")
    command.add_argument(
        "--allow-unverified-patch",
        action="store_true",
        help="development only: skip the published v1.3 PPF hash and component checks",
    )
    command.set_defaults(func=cmd_build)

    command = sub.add_parser("ppf-info", help="validate and summarize a PPF3 file")
    command.add_argument("patch", type=Path)
    command.set_defaults(func=cmd_ppf_info)

    command = sub.add_parser("ppf-create", help="create a PPF3 patch from two binary images")
    command.add_argument("source", type=Path)
    command.add_argument("target", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument("--description", default="Duel Masters BOTSD English patch")
    command.set_defaults(func=cmd_ppf_create)

    command = sub.add_parser(
        "shop-descriptions",
        help="patch booster descriptions while preserving price/image/index metadata",
    )
    command.add_argument("input_elf", type=Path)
    command.add_argument("output_elf", type=Path)
    command.add_argument(
        "--translations",
        type=Path,
        default=Path("localization/en/shop_boosters.json"),
    )
    command.set_defaults(func=cmd_shop_descriptions)

    command = sub.add_parser(
        "deck-text",
        help="localize fixed DECK/*.DAT text fields while preserving deck composition",
    )
    command.add_argument("input_dir", type=Path)
    command.add_argument("output_dir", type=Path)
    command.add_argument(
        "--translations",
        type=Path,
        default=Path("localization/en/deck_text.json"),
    )
    command.set_defaults(func=cmd_deck_text)

    command = sub.add_parser(
        "datapack-patch",
        help="apply a hash-gated fixed-size DATAPACK chunk patch",
    )
    command.add_argument("retail", type=Path)
    command.add_argument("patch", type=Path)
    command.add_argument("output", type=Path)
    command.set_defaults(func=cmd_datapack_patch)

    command = sub.add_parser(
        "iso-list", help="list ISO9660 entries without loading the ISO into RAM"
    )
    command.add_argument("iso", type=Path)
    command.add_argument("--basename", help="show one unique basename only")
    command.set_defaults(func=cmd_iso_list)

    command = sub.add_parser("iso-patch", help="streaming ISO9660 replacement/retarget patcher")
    command.add_argument("source", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument("replacement", type=Path, nargs="+")
    command.add_argument("--allow-nonretail", action="store_true")
    command.set_defaults(func=cmd_iso_patch)

    command = sub.add_parser(
        "font-ue-patch",
        help="build the reserved English U-diaeresis glyph in retail FONTLINK.PAC",
    )
    command.add_argument("input", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument(
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parent / "assets/font_ue.json",
    )
    command.add_argument("--allow-unverified-input", action="store_true")
    command.set_defaults(func=cmd_font_ue_patch)

    command = sub.add_parser(
        "font-polish",
        help="apply the semantic UI80 apostrophe/lowercase-l FONTLINK repair",
    )
    command.add_argument("input", type=Path)
    command.add_argument("output", type=Path)
    command.set_defaults(func=cmd_font_polish)

    command = sub.add_parser(
        "keyboard-v12-stage",
        help="apply the hash-gated historical v1.2 default keyboard mode-6 stage",
    )
    command.add_argument("input_elf", type=Path)
    command.add_argument("output_elf", type=Path)
    command.set_defaults(func=cmd_keyboard_v12_stage)

    command = sub.add_parser(
        "static-labels",
        help="build the UI81 static English labels from semantic geometry and language data",
    )
    command.add_argument("adv", type=Path)
    command.add_argument("advscn", type=Path)
    command.add_argument("duelpts", type=Path)
    command.add_argument("output_dir", type=Path)
    command.add_argument("--font", type=Path, required=True)
    command.add_argument(
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parent / "assets/static_labels_ui81.json",
    )
    command.add_argument(
        "--strings",
        type=Path,
        default=Path("localization/en/static_labels_ui81.json"),
    )
    command.set_defaults(func=cmd_static_labels)

    command = sub.add_parser(
        "graphic-residuals",
        help="build the UI82 LOBBY/TOUR/DECK residual graphics from accepted source pixels",
    )
    for name in ("lobby", "tour", "deck"):
        command.add_argument(f"--{name}-in", type=Path, required=True)
        command.add_argument(f"--{name}-out", type=Path, required=True)
    command.add_argument(
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parent / "assets/graphic_residuals_ui82.json",
    )
    command.set_defaults(func=cmd_graphic_residuals)

    command = sub.add_parser(
        "exec-residuals",
        help="apply the UI82 offline fixed-slot executable strings from language data",
    )
    command.add_argument("input_elf", type=Path)
    command.add_argument("output_elf", type=Path)
    command.add_argument(
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parent / "assets/offline_exec_residuals_ui82.json",
    )
    command.add_argument(
        "--strings",
        type=Path,
        default=Path("localization/en/offline_exec_residuals_ui82.json"),
    )
    command.set_defaults(func=cmd_exec_residuals)

    command = sub.add_parser(
        "wait-title",
        help="build the UI82 WAIT text and TITLE overlay removals from semantic sources",
    )
    command.add_argument("--wait-in", type=Path, required=True)
    command.add_argument("--wait-out", type=Path, required=True)
    command.add_argument("--title-in", type=Path, required=True)
    command.add_argument("--title-out", type=Path, required=True)
    command.add_argument("--fontlink", type=Path, required=True)
    command.add_argument(
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parent / "assets/wait_title_ui82.json",
    )
    command.add_argument(
        "--strings",
        type=Path,
        default=Path("localization/en/wait_title_ui82.json"),
    )
    command.set_defaults(func=cmd_wait_title)

    command = sub.add_parser(
        "ui-polish-v11",
        help="rebuild the v1.1 Options/Deck UI and executable cleanup from semantic specs",
    )
    command.add_argument("opt", type=Path)
    command.add_argument("deck", type=Path)
    command.add_argument("exe", type=Path)
    command.add_argument("outdir", type=Path)
    command.add_argument("--font", type=Path, default=Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"))
    command.add_argument("--strings", type=Path, default=Path("localization/en/ui_polish_v11.json"))
    command.add_argument("--spec", type=Path)
    command.set_defaults(func=cmd_ui_polish_v11)

    command = sub.add_parser(
        "duelpts-fix",
        help="rebuild the verified v1.2 duel-digit 6-9 / LEFT-label repair",
    )
    command.add_argument("clean_duelpts", type=Path)
    command.add_argument("v11_duelpts", type=Path)
    command.add_argument("output_duelpts", type=Path)
    command.add_argument("--spec", type=Path)
    command.add_argument("--allow-nonretail", action="store_true")
    command.set_defaults(func=cmd_duelpts_fix)

    command = sub.add_parser(
        "cardinfo-embed",
        help="repack the UI76 executable-resident Card Info rules/race table from master CSV",
    )
    command.add_argument("input_elf", type=Path)
    command.add_argument("master_csv", type=Path)
    command.add_argument("output_elf", type=Path)
    command.add_argument("--spec", type=Path)
    command.set_defaults(func=cmd_cardinfo_embed)

    command = sub.add_parser(
        "cardfaces-build",
        help="stream-build the UI75 677 large-card and thumbnail localization layers",
    )
    command.add_argument("unpack", type=Path)
    command.add_argument("inventory", type=Path)
    command.add_argument("fontlink", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument("--master", type=Path)
    command.add_argument("--spec", type=Path)
    command.add_argument("--start", type=int, default=0)
    command.add_argument("--end", type=int, default=BASELINE.card_resource_count)
    command.add_argument("--allow-nonretail", action="store_true")
    command.set_defaults(func=cmd_cardfaces_build)

    command = sub.add_parser(
        "fullcard-build",
        help="stream-build the accepted UI76 whole-card English image layer from pinned sources",
    )
    command.add_argument("base_unpack", type=Path)
    command.add_argument("inventory", type=Path)
    command.add_argument("crosswalk", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument("qa_dir", type=Path)
    command.add_argument("--cache-dir", type=Path, required=True)
    command.add_argument("--exception-dir", type=Path, required=True)
    command.add_argument("--db", type=Path)
    command.add_argument("--offline", action="store_true")
    command.add_argument("--allow-unpinned-db", action="store_true")
    command.add_argument("--allow-nonretail", action="store_true")
    command.set_defaults(func=cmd_fullcard_build)

    command = sub.add_parser(
        "unpack-render-second-names",
        help="semantically render the frozen 677-card UI82 second-name layer",
    )
    command.add_argument("retail", type=Path)
    command.add_argument("inventory", type=Path)
    command.add_argument("fontlink", type=Path)
    command.add_argument("output_zip", type=Path)
    command.add_argument("--qa-dir", type=Path)
    command.add_argument("--report", type=Path)
    command.add_argument("--allow-nonretail", action="store_true")
    command.add_argument("--allow-nonfrozen-output", action="store_true")
    command.set_defaults(func=cmd_unpack_render_second_names)

    command = sub.add_parser(
        "unpack-create-second-names",
        help="create the deterministic 677-chunk UI82 second-name patch ZIP",
    )
    command.add_argument("retail", type=Path)
    command.add_argument("ui76", type=Path)
    command.add_argument("ui82", type=Path)
    command.add_argument("output_zip", type=Path)
    command.add_argument("--inventory", type=Path)
    command.add_argument("--allow-nonretail", action="store_true")
    command.set_defaults(func=cmd_unpack_create_second_names)

    command = sub.add_parser(
        "unpack-apply-second-names",
        help="stream-apply the UI82 677-chunk second-card-sprite patch",
    )
    command.add_argument("ui76", type=Path)
    command.add_argument("patch_zip", type=Path)
    command.add_argument("output", type=Path)
    command.set_defaults(func=cmd_unpack_apply_second_names)

    command = sub.add_parser(
        "unpack-verify-ui76",
        help="stream-verify the frozen UI76 large/thumbnail card layers",
    )
    command.add_argument("retail", type=Path)
    command.add_argument("compiled", type=Path)
    command.add_argument("inventory", type=Path)
    command.set_defaults(func=cmd_unpack_verify_ui76)

    command = sub.add_parser(
        "unpack-verify-ui82",
        help="stream-verify UI76 card layers plus the UI82 second-name sprite layer",
    )
    command.add_argument("retail", type=Path)
    command.add_argument("ui76", type=Path)
    command.add_argument("ui82", type=Path)
    command.add_argument("inventory", type=Path)
    command.add_argument("patch_zip", type=Path)
    command.set_defaults(func=cmd_unpack_verify_ui82)

    command = sub.add_parser(
        "iso-verify-assets",
        help="verify a tab-separated basename/SHA-256 asset manifest against an ISO",
    )
    command.add_argument("iso", type=Path)
    command.add_argument("hashes", type=Path)
    command.add_argument("--extract", action="append", default=[], help="BASENAME=OUTPUT")
    command.set_defaults(func=cmd_iso_verify_assets)

    command = sub.add_parser(
        "extract-components",
        help="extract and verify the four public v1.2/v1.3 maintenance components",
    )
    command.add_argument("iso", type=Path)
    command.add_argument("output_dir", type=Path)
    command.add_argument("--version", choices=("v1.2", "v1.3"), default="v1.2")
    command.set_defaults(func=cmd_extract_components)

    command = sub.add_parser(
        "scrpack-catalog",
        help="export the retail/translated story-text corpus with stable chunk/command IDs",
    )
    command.add_argument("retail", type=Path)
    command.add_argument("translated", type=Path)
    command.add_argument("output", type=Path)
    command.set_defaults(func=cmd_scrpack_catalog)

    command = sub.add_parser(
        "scrpack-language-audit",
        help="audit the translation-only v1.2 story datasets against a translated SCRPACK",
    )
    command.add_argument("translated", type=Path)
    command.add_argument(
        "--dialogue",
        type=Path,
        default=Path("localization/en/story_dialogue_v12.csv"),
    )
    command.add_argument(
        "--choices",
        type=Path,
        default=Path("localization/en/story_choices_v12.csv"),
    )
    command.add_argument("--allow-nonfrozen-target", action="store_true")
    command.set_defaults(func=cmd_scrpack_language_audit)

    command = sub.add_parser(
        "scrpack-apply-language",
        help="rebuild the v1.2 SCRPACK story text from exact retail plus language datasets",
    )
    command.add_argument("retail", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument(
        "--dialogue",
        type=Path,
        default=Path("localization/en/story_dialogue_v12.csv"),
    )
    command.add_argument(
        "--choices",
        type=Path,
        default=Path("localization/en/story_choices_v12.csv"),
    )
    command.add_argument("--allow-nonretail", action="store_true")
    command.add_argument("--allow-nonfrozen-output", action="store_true")
    command.set_defaults(func=cmd_scrpack_apply_language)

    command = sub.add_parser(
        "v13-components",
        help="rebuild the exact v1.3 maintenance components from exact public-v1.2 files",
    )
    command.add_argument("v12_dir", type=Path)
    command.add_argument("output_dir", type=Path)
    command.set_defaults(func=cmd_v13_components)

    command = sub.add_parser(
        "v13-release",
        help="rebuild the exact published v1.3 full and v1.2-to-v1.3 PPFs",
    )
    command.add_argument("v12_dir", type=Path)
    command.add_argument("v12_full_ppf", type=Path)
    command.add_argument("output_dir", type=Path)
    command.set_defaults(func=cmd_v13_release)

    command = sub.add_parser(
        "v13-release-from-iso",
        help="rebuild the published v1.3 PPFs directly from an exact public-v1.2 ISO",
    )
    command.add_argument("v12_iso", type=Path)
    command.add_argument("v12_full_ppf", type=Path)
    command.add_argument("output_dir", type=Path)
    command.set_defaults(func=cmd_v13_release_from_iso)

    command = sub.add_parser("qa-summary", help="validate and summarize a playthrough QA matrix")
    command.add_argument("matrix", type=Path)
    command.set_defaults(func=cmd_qa_summary)

    command = sub.add_parser("qa-audit", help="validate all machine-readable QA matrices")
    command.add_argument("qa_dir", type=Path, help="directory containing QA CSV matrices")
    command.set_defaults(func=cmd_qa_audit)

    command = sub.add_parser(
        "localization-audit",
        help="validate language-dataset mappings without moving historical CSVs",
    )
    command.add_argument("manifest", type=Path)
    command.add_argument("--root", type=Path, default=Path("."), help="repository root")
    command.set_defaults(func=cmd_localization_audit)

    command = sub.add_parser(
        "provenance-export",
        help="export a conservative translation provenance/review worklist",
    )
    command.add_argument("manifest", type=Path)
    command.add_argument("--root", type=Path, default=Path("."), help="repository root")
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(func=cmd_provenance_export)

    command = sub.add_parser(
        "combined-list",
        help="rebuild the 4,058-pointer localized LIST_1.BIN from translation CSVs",
    )
    command.add_argument("--display", type=Path, required=True)
    command.add_argument("--master", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(func=cmd_combined_list)

    command = sub.add_parser(
        "cardtext-check",
        help="verify retail card-text structures and executable patch sites",
    )
    command.add_argument("executable", type=Path)
    command.add_argument("list1", type=Path)
    command.set_defaults(func=cmd_cardtext_check)

    command = sub.add_parser(
        "cardtext-externalize",
        help="externalize the embedded 2,376-entry master table into LIST_1.BIN",
    )
    command.add_argument("executable", type=Path)
    command.add_argument("list1", type=Path)
    command.add_argument("master_csv", type=Path)
    command.add_argument("display_csv", type=Path)
    command.add_argument("output_executable", type=Path)
    command.add_argument("output_list1", type=Path)
    command.set_defaults(func=cmd_cardtext_externalize)

    command = sub.add_parser(
        "rules-wrap",
        help="word-wrap English Card Info rules by replacing existing spaces with LF bytes",
    )
    command.add_argument("--master-in", type=Path, required=True)
    command.add_argument("--display-in", type=Path, required=True)
    command.add_argument("--master-out", type=Path, required=True)
    command.add_argument("--display-out", type=Path, required=True)
    command.set_defaults(func=cmd_rules_wrap)

    command = sub.add_parser(
        "flavor-import",
        help="import printing-specific official English flavor text using the verified card crosswalk",
    )
    command.add_argument("--json", type=Path, required=True)
    command.add_argument("--crosswalk", type=Path, required=True)
    command.add_argument("--master-in", type=Path, required=True)
    command.add_argument("--display-in", type=Path, required=True)
    command.add_argument("--master-out", type=Path, required=True)
    command.add_argument("--display-out", type=Path, required=True)
    command.add_argument("--qa-out", type=Path, required=True)
    command.add_argument("--unique-reprint-fallback", action="store_true")
    command.add_argument("--strict", action="store_true")
    command.set_defaults(func=cmd_flavor_import)

    command = sub.add_parser(
        "data-audit",
        help="validate release-critical localization datasets and English text fields",
    )
    command.add_argument("data_dir", type=Path)
    command.set_defaults(func=cmd_data_audit)

    command = sub.add_parser("text-audit", help="scan selected localization CSV fields")
    command.add_argument("csv", type=Path)
    command.add_argument(
        "--field", action="append", required=True, help="CSV field to audit; repeatable"
    )
    command.add_argument(
        "--max-segment",
        type=int,
        help="flag explicit line segments longer than this many characters",
    )
    command.add_argument("--fail-on-findings", action="store_true")
    command.set_defaults(func=cmd_text_audit)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        raise SystemExit(args.func(args))
    except (BotSDError, KeyError, FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
