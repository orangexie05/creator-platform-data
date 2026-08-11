#!/usr/bin/env python3
"""Run creator-platform collectors for multiple configured accounts."""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")


class ConfigError(RuntimeError):
    pass


class Account:
    def __init__(
        self,
        *,
        platform: str,
        account_key: str,
        account_name: str,
        profile_dir: Path,
        start_date: str | None = None,
        end_date: str | None = None,
        include_details: bool = False,
        browser_channel: str | None = None,
    ) -> None:
        self.platform = platform
        self.account_key = account_key
        self.account_name = account_name
        self.profile_dir = profile_dir
        self.start_date = start_date
        self.end_date = end_date
        self.include_details = include_details
        self.browser_channel = browser_channel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Douyin/Xiaohongshu creator metrics for multiple local browser profiles"
    )
    parser.add_argument("--config", required=True, type=Path,
                        help="Path to accounts.yaml; do not commit real account configs")
    parser.add_argument("--output-dir", default=Path("outputs"), type=Path)
    parser.add_argument("--snapshot-date",
                        help="Snapshot date, YYYY-MM-DD; defaults to Asia/Shanghai today")
    parser.add_argument("--start-date",
                        help="Default Xiaohongshu publish start date, YYYY-MM-DD")
    parser.add_argument("--end-date",
                        help="Default Xiaohongshu publish end date, YYYY-MM-DD")
    parser.add_argument("--python", default=sys.executable,
                        help="Python executable used to run each collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without running collectors")
    return parser.parse_args()


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def load_account_dicts(config_path: Path) -> list[dict[str, Any]]:
    accounts: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_accounts = False

    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.strip() == "accounts:":
            in_accounts = True
            continue
        if not in_accounts:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current is not None:
                accounts.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped:
                key, sep, value = stripped.partition(":")
                if not sep:
                    raise ConfigError(f"Invalid account item line: {raw_line}")
                current[key.strip()] = parse_scalar(value)
            continue
        if current is None:
            raise ConfigError("Account properties must appear under an account item")
        key, sep, value = stripped.partition(":")
        if not sep:
            raise ConfigError(f"Invalid account property line: {raw_line}")
        current[key.strip()] = parse_scalar(value)

    if current is not None:
        accounts.append(current)
    if not accounts:
        raise ConfigError("No accounts found in config")
    return accounts


def expand_profile_dir(value: str) -> Path:
    return Path(value).expanduser()


def load_accounts(config_path: Path) -> list[Account]:
    account_dicts = load_account_dicts(config_path)
    accounts: list[Account] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_profiles: dict[Path, str] = {}

    for index, item in enumerate(account_dicts, start=1):
        missing = [key for key in ("platform", "account_key", "account_name", "profile_dir") if not item.get(key)]
        if missing:
            raise ConfigError(f"Account #{index} is missing required fields: {', '.join(missing)}")

        platform = str(item["platform"])
        if platform not in {"douyin", "xiaohongshu"}:
            raise ConfigError(f"Unsupported platform for account #{index}: {platform}")

        account_key = str(item["account_key"])
        stable_key = (platform, account_key)
        if stable_key in seen_keys:
            raise ConfigError(f"Duplicate platform/account_key: {platform}/{account_key}")
        seen_keys.add(stable_key)

        profile_dir = expand_profile_dir(str(item["profile_dir"]))
        if profile_dir in seen_profiles:
            raise ConfigError(
                f"profile_dir must be unique; {platform}/{account_key} shares {profile_dir} "
                f"with {seen_profiles[profile_dir]}"
            )
        seen_profiles[profile_dir] = f"{platform}/{account_key}"

        accounts.append(Account(
            platform=platform,
            account_key=account_key,
            account_name=str(item["account_name"]),
            profile_dir=profile_dir,
            start_date=str(item["start_date"]) if item.get("start_date") else None,
            end_date=str(item["end_date"]) if item.get("end_date") else None,
            include_details=bool(item.get("include_details", False)),
            browser_channel=str(item["browser_channel"]) if item.get("browser_channel") else None,
        ))

    return accounts


def collector_script(script_root: Path, platform: str) -> Path:
    if platform == "douyin":
        candidates = [
            script_root / "douyin" / "collect_snapshot.py",
            script_root / "collect_douyin.py",
        ]
    elif platform == "xiaohongshu":
        candidates = [
            script_root / "xiaohongshu" / "collect_xiaohongshu.py",
            script_root / "collect_xiaohongshu.py",
        ]
    else:
        raise ConfigError(f"Unsupported platform: {platform}")

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ConfigError(f"Collector script not found for platform: {platform}")


def build_command(
    *,
    account: Account,
    python_executable: str,
    output_dir: Path,
    snapshot_date: str,
    login_stamp: str,
    script_root: Path,
) -> list[str]:
    script = collector_script(script_root, account.platform)
    output = output_dir / f"{account.platform}-{account.account_key}-{snapshot_date}.tsv"
    login_image = output_dir / f"{account.platform}-{account.account_key}-login-{login_stamp}.png"
    command = [
        python_executable,
        str(script),
        "--profile-dir", str(account.profile_dir),
        "--output", str(output),
        "--login-image", str(login_image),
        "--snapshot-date", snapshot_date,
        "--account-key", account.account_key,
        "--account-name", account.account_name,
    ]
    if account.browser_channel:
        command.extend(["--browser-channel", account.browser_channel])
    if account.platform == "xiaohongshu":
        if not account.start_date or not account.end_date:
            raise ConfigError(f"Xiaohongshu account {account.account_key} requires start_date and end_date")
        command.extend(["--start-date", account.start_date, "--end-date", account.end_date])
        if account.include_details:
            command.append("--include-details")
    return command


def run_all(args: argparse.Namespace) -> int:
    snapshot_date = args.snapshot_date or datetime.now(TZ).date().isoformat()
    login_stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    accounts = load_accounts(args.config)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    script_root = Path(__file__).resolve().parent

    failures = 0
    for account in accounts:
        if account.platform == "xiaohongshu":
            account.start_date = account.start_date or args.start_date
            account.end_date = account.end_date or args.end_date
        try:
            command = build_command(
                account=account,
                python_executable=args.python,
                output_dir=args.output_dir,
                snapshot_date=snapshot_date,
                login_stamp=login_stamp,
                script_root=script_root,
            )
        except ConfigError as exc:
            print(f"[creator-platform-data] ERROR {account.platform}/{account.account_key}: {exc}")
            failures += 1
            continue

        print(f"[creator-platform-data] RUN {account.platform}/{account.account_key}")
        if args.dry_run:
            print(" ".join(command))
            continue
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            failures += 1
            print(
                f"[creator-platform-data] ERROR {account.platform}/{account.account_key}: "
                f"collector exited {result.returncode}"
            )

    return 1 if failures else 0


def main() -> int:
    try:
        return run_all(parse_args())
    except ConfigError as exc:
        print(f"[creator-platform-data] ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
