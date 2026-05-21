#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_BASE_ID = "info.sioyek.sioyek"
DEFAULT_SUFFIX_PREFIX = "coexist"
MAX_COEXIST_VARIANTS = 12


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build arbitrary coexist Android APK variants for Sioyek."
    )
    parser.add_argument(
        "--count",
        type=int,
        help="Number of APK variants to build. Generates deterministic application IDs.",
    )
    parser.add_argument(
        "--application-id",
        dest="application_ids",
        action="append",
        default=[],
        help="Explicit application ID to build. May be passed multiple times.",
    )
    parser.add_argument(
        "--include-base",
        action="store_true",
        help="When used with --count, build the base application ID as the first variant.",
    )
    parser.add_argument(
        "--base-id",
        default=DEFAULT_BASE_ID,
        help=f"Base Android application ID. Default: {DEFAULT_BASE_ID}",
    )
    parser.add_argument(
        "--suffix-prefix",
        default=DEFAULT_SUFFIX_PREFIX,
        help=f"Suffix prefix for generated application IDs. Default: {DEFAULT_SUFFIX_PREFIX}",
    )
    parser.add_argument(
        "--android-source-dir",
        default="android",
        help="Path to the Android package source directory template.",
    )
    parser.add_argument(
        "--deployment-settings",
        default="android-sioyek-deployment-settings.json",
        help="Path to the androiddeployqt deployment settings JSON.",
    )
    parser.add_argument(
        "--androiddeployqt",
        default="/home/k10876/sioyek-build/Qt/6.7.3/gcc_64/bin/androiddeployqt",
        help="Path to the androiddeployqt executable.",
    )
    parser.add_argument(
        "--staged-libs-dir",
        default="android-build/libs",
        help="Directory containing the already staged Android native libraries.",
    )
    parser.add_argument(
        "--icon-set-dir",
        default="android/coexist_icons",
        help="Directory containing pre-generated icon sets for base and coexist variants.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="build_apk/coexist",
        help="Directory where the final APK artifacts will be copied.",
    )
    parser.add_argument(
        "--work-dir",
        default="build_apk/coexist-work",
        help="Directory for temporary per-variant package sources and build outputs.",
    )
    parser.add_argument(
        "--mode",
        choices=["debug", "release"],
        default="debug",
        help="Build mode passed to androiddeployqt.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the work and artifact directories before building.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned variants without invoking androiddeployqt.",
    )
    return parser.parse_args()


def ensure_application_ids(args):
    application_ids = list(args.application_ids)

    if args.count is not None:
        if args.count <= 0:
            raise ValueError("--count must be greater than zero")
        generated_ids = []
        if args.include_base:
            generated_ids.append(args.base_id)
        start_index = 1
        while len(generated_ids) < args.count:
            generated_ids.append(f"{args.base_id}.{args.suffix_prefix}{start_index}")
            start_index += 1
        application_ids.extend(generated_ids)

    if not application_ids:
        raise ValueError("Provide --count or at least one --application-id")

    deduped = []
    seen = set()
    for app_id in application_ids:
        normalized = app_id.strip()
        if not normalized:
            raise ValueError("Application IDs must not be empty")
        if normalized in seen:
            raise ValueError(f"Duplicate application ID: {normalized}")
        seen.add(normalized)
        deduped.append(normalized)

    coexist_count = sum(1 for app_id in deduped if app_id != args.base_id)
    if coexist_count > MAX_COEXIST_VARIANTS:
        raise ValueError(
            f"At most {MAX_COEXIST_VARIANTS} coexist variants are supported, got {coexist_count}"
        )

    return deduped


def variant_name(base_id: str, application_id: str) -> str:
    if application_id == base_id:
        return "base"
    if application_id.startswith(base_id + "."):
        return application_id[len(base_id) + 1 :]
    return application_id.replace(".", "-")


def update_gradle_properties(path: Path, application_id: str):
    lines = path.read_text().splitlines()
    filtered = [line for line in lines if not line.startswith("sioyekApplicationId=")]
    filtered.append(f"sioyekApplicationId={application_id}")
    path.write_text("\n".join(filtered) + "\n")


def ensure_gradle_wrapper_executable(package_source_dir: Path):
    gradlew_path = package_source_dir / "gradlew"
    if gradlew_path.exists():
        gradlew_path.chmod(gradlew_path.stat().st_mode | 0o755)


def seed_output_libs(staged_libs_dir: Path, output_dir: Path):
    if not staged_libs_dir.is_dir():
        raise FileNotFoundError(f"Staged libs dir not found: {staged_libs_dir}")
    destination = output_dir / "libs"
    shutil.copytree(staged_libs_dir, destination, dirs_exist_ok=True)


def copy_icon_set(package_source_dir: Path, icon_set_dir: Path, icon_key: str):
    source_root = icon_set_dir / icon_key
    if not source_root.is_dir():
        raise FileNotFoundError(f"Icon set not found: {source_root}")

    for source_icon in source_root.glob("drawable-*/icon.png"):
        destination = package_source_dir / "res" / source_icon.parent.name / "icon.png"
        if not destination.parent.is_dir():
            raise FileNotFoundError(f"Icon destination directory not found: {destination.parent}")
        shutil.copy2(source_icon, destination)


def write_deployment_settings(template: dict, package_source_dir: Path, destination: Path):
    payload = dict(template)
    payload["android-package-source-directory"] = str(package_source_dir.resolve())
    destination.write_text(json.dumps(payload, indent=3) + "\n")


def find_built_apk(output_dir: Path, package_source_dir: Path, mode: str) -> Path:
    search_roots = [
        output_dir / "build/outputs/apk" / mode,
        output_dir,
        package_source_dir / "build/outputs/apk" / mode,
        package_source_dir,
    ]
    candidates = []
    for root in search_roots:
        if root.exists():
            candidates.extend(root.glob("*.apk"))
            candidates.extend(root.glob("**/*.apk"))
    unique_candidates = sorted({candidate.resolve() for candidate in candidates})
    if not unique_candidates:
        raise FileNotFoundError(
            f"No APK produced under {output_dir} or {package_source_dir}"
        )
    return unique_candidates[-1]


def run_command(command, cwd: Path, log_path: Path):
    result = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_path.write_text(result.stdout)
    if result.stdout:
        preview_lines = result.stdout.splitlines()
        head = preview_lines[:40]
        tail = preview_lines[-40:] if len(preview_lines) > 40 else []
        for line in head:
            print(line)
        if tail and tail != head:
            print("...")
            for line in tail:
                print(line)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}\nLog: {log_path}"
        )


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    android_source_dir = (repo_root / args.android_source_dir).resolve()
    deployment_settings_path = (repo_root / args.deployment_settings).resolve()
    androiddeployqt_path = Path(args.androiddeployqt).resolve()
    staged_libs_dir = (repo_root / args.staged_libs_dir).resolve()
    icon_set_dir = (repo_root / args.icon_set_dir).resolve()
    artifacts_dir = (repo_root / args.artifacts_dir).resolve()
    work_dir = (repo_root / args.work_dir).resolve()

    if not android_source_dir.is_dir():
        raise FileNotFoundError(f"Android source dir not found: {android_source_dir}")
    if not deployment_settings_path.is_file():
        raise FileNotFoundError(f"Deployment settings JSON not found: {deployment_settings_path}")
    if not androiddeployqt_path.is_file():
        raise FileNotFoundError(f"androiddeployqt not found: {androiddeployqt_path}")
    if not staged_libs_dir.is_dir():
        raise FileNotFoundError(f"Staged libs dir not found: {staged_libs_dir}")
    if not icon_set_dir.is_dir():
        raise FileNotFoundError(f"Icon set dir not found: {icon_set_dir}")

    application_ids = ensure_application_ids(args)

    if args.clean:
        shutil.rmtree(artifacts_dir, ignore_errors=True)
        shutil.rmtree(work_dir, ignore_errors=True)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    deployment_template = json.loads(deployment_settings_path.read_text())

    print("Planned variants:")
    for application_id in application_ids:
        print(f"- {application_id}")

    if args.dry_run:
        return 0

    coexist_index = 0

    for application_id in application_ids:
        name = variant_name(args.base_id, application_id)
        if application_id == args.base_id:
            icon_key = "base"
        else:
            coexist_index += 1
            icon_key = f"{coexist_index:02d}"

        variant_root = work_dir / name
        package_source_dir = variant_root / "android"
        output_dir = variant_root / "android-build"
        deployment_json_path = variant_root / "deployment-settings.json"
        build_log_path = variant_root / "androiddeployqt.log"

        shutil.rmtree(variant_root, ignore_errors=True)
        variant_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(android_source_dir, package_source_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        update_gradle_properties(package_source_dir / "gradle.properties", application_id)
        ensure_gradle_wrapper_executable(package_source_dir)
        copy_icon_set(package_source_dir, icon_set_dir, icon_key)
        seed_output_libs(staged_libs_dir, output_dir)
        write_deployment_settings(deployment_template, package_source_dir, deployment_json_path)

        apk_target_path = output_dir / f"sioyek-{name}.apk"
        command = [
            str(androiddeployqt_path),
            "--input",
            str(deployment_json_path),
            "--output",
            str(output_dir),
            "--apk",
            str(apk_target_path),
            f"--{args.mode}",
            "--gradle",
        ]

        print(f"\n=== Building {application_id} ===")
        run_command(command, repo_root, build_log_path)

        built_apk = find_built_apk(output_dir, package_source_dir, args.mode)
        artifact_path = artifacts_dir / f"sioyek-{name}.apk"
        shutil.copy2(built_apk, artifact_path)
        print(f"Saved {artifact_path}")

    print(f"\nArtifacts available in {artifacts_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
