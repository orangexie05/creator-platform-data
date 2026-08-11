#!/usr/bin/env python3
"""Collect Douyin Creator Center work metrics with an isolated Playwright session."""
from __future__ import annotations

import argparse
import asyncio
import csv
import getpass
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")
CREATOR_HOME_URL = "https://creator.douyin.com/"
CONTENT_MANAGE_URL = "https://creator.douyin.com/creator-micro/content/manage"
WORK_LIST_URL = "https://creator.douyin.com/janus/douyin/creator/pc/work_list"
QR_RENDER_DELAY_MS = 4000
QR_CLIP_PADDING = 16
SMS_OPTION_LABELS = ("发送短信验证",)
SMS_SEND_LABELS = ("发送短信", "发送验证码", "获取验证码")
SMS_CODE_SELECTOR = (
    'input[placeholder*="验证码"], input[autocomplete="one-time-code"], '
    'input[name*="code"], input[type="tel"]'
)
HEADERS = [
    "platform", "account_key", "current_account_name", "data_date", "work_id",
    "publish_title", "content", "publish_time", "views", "avg_watch_seconds",
    "cover_ctr", "likes", "comments", "shares", "favorites", "completion_rate",
    "completion_rate_5s", "new_followers", "fan_view_share", "collected_at",
]


class CollectionError(RuntimeError):
    pass


def _load_qr_vision_checker():
    for helper in (
        Path(__file__).with_name("qr_vision.py"),
        Path(__file__).resolve().parents[1] / "qr_vision.py",
    ):
        if helper.is_file():
            spec = importlib.util.spec_from_file_location("qr_vision", helper)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            return module.image_has_qr_like_pattern
    raise CollectionError("qr_vision.py is missing; cannot validate login QR image")


image_has_qr_like_pattern = _load_qr_vision_checker()


def work_list_url(cursor: str, page_size: int = 12) -> str:
    """Build a Creator Center work-list URL without account-specific state."""
    query = urlencode({
        "status": 0,
        "count": page_size,
        "max_cursor": cursor,
        "scene": "star_atlas",
        "device_platform": "android",
        "aid": 1128,
    })
    return f"{WORK_LIST_URL}?{query}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Douyin Creator Center work snapshots using a local Playwright profile"
    )
    parser.add_argument("--profile-dir", required=True, type=Path,
                        help="Dedicated Playwright user-data directory for Douyin login")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--login-image", type=Path,
                        help="Where to save the login page screenshot containing the QR code")
    parser.add_argument("--login-timeout-seconds", type=int, default=300)
    parser.add_argument("--snapshot-date", help="YYYY-MM-DD; defaults to Asia/Shanghai today")
    parser.add_argument("--page-size", type=int, default=12)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--account-name",
                        help="Optional account name override when the Creator Center page cannot expose it")
    parser.add_argument("--account-key", default="",
                        help="Stable caller-defined account key for multi-account snapshots")
    parser.add_argument("--browser-channel",
                        help="Optional Playwright browser channel, for example chrome")
    parser.add_argument("--headless", action="store_true",
                        help="Run without a visible browser after a successful interactive login")
    return parser.parse_args()


def scalar(value: Any) -> Any:
    return "" if value is None else value


def percent(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(number) <= 1:
        number *= 100
    return f"{number:.2f}%"


def timestamp(value: Any) -> str:
    try:
        raw = int(float(value))
    except (TypeError, ValueError):
        return ""
    if raw > 10_000_000_000:
        raw //= 1000
    return datetime.fromtimestamp(raw, TZ).strftime("%Y-%m-%d %H:%M:%S")


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def work_items(payload: Any) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for item in walk_dicts(payload):
        metrics = item.get("metrics")
        work_id = item.get("id")
        if work_id and isinstance(metrics, dict) and "view_count" in metrics:
            found[str(work_id)] = item
    return list(found.values())


def pagination(payload: Any) -> tuple[bool, str]:
    if isinstance(payload, dict) and "has_more" in payload:
        return bool(payload["has_more"]), str(payload.get("max_cursor") or "")
    for item in walk_dicts(payload):
        if "has_more" in item:
            return bool(item["has_more"]), str(item.get("max_cursor", item.get("cursor", "")) or "")
    return False, ""


def row(account_key: str, account_name: str, item: dict[str, Any],
        snapshot_date: str, collected_at: str) -> dict[str, Any]:
    metrics = item.get("metrics") or {}
    content = str(item.get("description") or "").replace("\t", " ").replace("\n", " ").strip()
    return {
        "platform": "douyin",
        "account_key": account_key,
        "current_account_name": account_name,
        "data_date": snapshot_date,
        "work_id": scalar(item.get("id")),
        "publish_title": "",
        "content": content,
        "publish_time": timestamp(item.get("create_time")),
        "views": scalar(metrics.get("view_count")),
        "avg_watch_seconds": scalar(metrics.get("avg_view_second")),
        "cover_ctr": percent(metrics.get("cover_click_rate")),
        "likes": scalar(metrics.get("like_count")),
        "comments": scalar(metrics.get("comment_count")),
        "shares": scalar(metrics.get("share_count")),
        "favorites": scalar(metrics.get("favorite_count")),
        "completion_rate": percent(metrics.get("completion_rate")),
        "completion_rate_5s": percent(metrics.get("completion_rate_5s")),
        "new_followers": scalar(metrics.get("subscribe_count")),
        "fan_view_share": percent(metrics.get("fan_view_proportion")),
        "collected_at": collected_at,
    }


def rows_from_items(account_key: str, account_name: str, items: list[dict[str, Any]], snapshot_date: str,
                    collected_at: str) -> list[dict[str, Any]]:
    return [
        row(account_key, account_name, item, snapshot_date, collected_at)
        for item in sorted(items, key=lambda item: item.get("create_time") or 0, reverse=True)
    ]


async def page_is_logged_in(page: Any) -> bool:
    for text in ("作品管理", "内容管理", "数据中心"):
        try:
            if await page.get_by_text(text, exact=True).count() > 0:
                return True
        except Exception:
            continue
    return False


async def wait_for_qr_login(page: Any) -> None:
    await page.get_by_text("扫码登录", exact=True).wait_for(state="visible", timeout=8000)
    await page.wait_for_timeout(QR_RENDER_DELAY_MS)


async def select_sms_verification_option(page: Any, already_selected: bool = False) -> bool:
    if already_selected:
        return True
    for label in SMS_OPTION_LABELS:
        option = page.get_by_text(label, exact=True)
        if await option.count() == 0:
            continue
        try:
            await option.first.click()
        except Exception:
            continue
        print(
            json.dumps(
                {
                    "status": "sms_verification_option_selected",
                    "message": "已进入短信身份验证页面",
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return True
    return False


async def handle_sms_challenge(page: Any, already_sent: bool = False) -> bool:
    """Click the SMS send action once and let the user enter the code in the browser."""
    if already_sent:
        return True

    for label in SMS_SEND_LABELS:
        sender = page.get_by_text(label, exact=True)
        if await sender.count() == 0:
            continue
        try:
            await sender.first.click()
        except Exception:
            continue
        print(
            json.dumps(
                {
                    "status": "sms_verification_required",
                    "message": "本次登录需要短信验证码，已点击发送验证码，请将本次验证码发给我",
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return True
    return False


async def can_probe_login_api(page: Any) -> bool:
    try:
        return await page.get_by_text("扫码登录", exact=True).count() == 0
    except Exception:
        return False


async def enter_sms_code(page: Any, code: str) -> None:
    fields = page.locator(SMS_CODE_SELECTOR)
    count = await fields.count()
    if count == 0:
        raise CollectionError("sms_code_input_not_found")

    if count == 1:
        field = fields.first
        await field.fill(code)
        await field.press("Enter")
        return

    digits = re.sub(r"\D", "", code)
    if len(digits) < count:
        raise CollectionError("sms_code_input_count_exceeds_code_length")
    for index, digit in enumerate(digits[:count]):
        await fields.nth(index).fill(digit)
    await fields.nth(count - 1).press("Enter")


async def read_sms_code(timeout_seconds: int) -> str:
    print(
        json.dumps(
            {
                "status": "sms_code_input_required",
                "message": "请将本次短信验证码发给我；验证码只用于当前登录，不会打印或保存",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        code = await asyncio.wait_for(
            asyncio.to_thread(getpass.getpass, ""),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise CollectionError("Timed out waiting for the SMS verification code") from exc
    code = re.sub(r"\s+", "", code)
    if not re.fullmatch(r"\d{4,8}", code):
        raise CollectionError("SMS verification code must contain 4-8 digits")
    return code


def padded_clip(rect: dict[str, Any], viewport: dict[str, Any], padding: int = QR_CLIP_PADDING) -> dict[str, Any]:
    x = max(0, float(rect["x"]) - padding)
    y = max(0, float(rect["y"]) - padding)
    right = min(float(viewport["width"]), float(rect["x"]) + float(rect["width"]) + padding)
    bottom = min(float(viewport["height"]), float(rect["y"]) + float(rect["height"]) + padding)
    return {
        "x": x,
        "y": y,
        "width": max(1, right - x),
        "height": max(1, bottom - y),
    }


async def login_qr_clip(page: Any) -> dict[str, Any] | None:
    candidate = await page.evaluate(
        """() => {
            const elements = Array.from(document.querySelectorAll("canvas,img,svg,div"));
            const candidates = [];
            for (const element of elements) {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                if (style.visibility === "hidden" || style.display === "none") continue;
                if (rect.width < 120 || rect.height < 120 || rect.width > 420 || rect.height > 420) continue;
                const ratio = rect.width / rect.height;
                if (ratio < 0.75 || ratio > 1.35) continue;
                const text = (element.textContent || "").trim();
                if (text.length > 20) continue;
                candidates.push({
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                    area: rect.width * rect.height,
                });
            }
            candidates.sort((left, right) => right.area - left.area);
            const best = candidates[0];
            if (!best) return null;
            return {
                rect: best,
                viewport: { width: window.innerWidth, height: window.innerHeight },
            };
        }"""
    )
    if not candidate:
        return None
    return padded_clip(candidate["rect"], candidate["viewport"])


async def save_login_image(page: Any, login_image: Path) -> bool:
    clip = await login_qr_clip(page)
    if not clip:
        raise CollectionError("login_qr_not_found: QR element was not found")
    await page.screenshot(path=str(login_image), clip=clip)
    if not image_has_qr_like_pattern(login_image):
        try:
            login_image.unlink()
        except FileNotFoundError:
            pass
        raise CollectionError("login_qr_not_found: QR vision check failed")
    return True


async def login_session_is_ready(page: Any) -> bool:
    if await page_is_logged_in(page):
        return True
    try:
        result = await page.evaluate(
            """async (endpoint) => {
                try {
                    const response = await fetch(endpoint, { credentials: 'include' });
                    if (response.status !== 200) return false;
                    const payload = await response.json();
                    return payload.status_code === 0 || payload.status_code === "0";
                } catch {
                    return false;
                }
            }""",
            work_list_url("0", 1),
        )
    except Exception:
        return False
    return bool(result)


async def wait_for_login(page: Any, login_image: Path, timeout_seconds: int) -> None:
    await wait_for_qr_login(page)
    login_image.parent.mkdir(parents=True, exist_ok=True)
    qr_cropped = await save_login_image(page, login_image)
    print(
        json.dumps(
            {
                "status": "login_required",
                "qr_image": str(login_image.resolve()),
                "qr_cropped": qr_cropped,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    sms_option_selected = False
    sms_sent = False
    while asyncio.get_running_loop().time() < deadline:
        await page.wait_for_timeout(1500)
        if not sms_option_selected:
            sms_option_selected = await select_sms_verification_option(page, already_selected=False)
        if sms_option_selected and not sms_sent:
            sms_sent = await handle_sms_challenge(page, already_sent=False)
            if sms_sent:
                await enter_sms_code(page, await read_sms_code(timeout_seconds))
        if await page_is_logged_in(page):
            return
        if await can_probe_login_api(page) and await login_session_is_ready(page):
            return
    raise CollectionError("Timed out waiting for a Douyin Creator Center QR login")


async def request_json(page: Any, url: str) -> dict[str, Any]:
    result = await page.evaluate(
        """async (endpoint) => {
            const response = await fetch(endpoint, { credentials: 'include' });
            return { status: response.status, text: await response.text() };
        }""",
        url,
    )
    if result["status"] != 200:
        raise CollectionError(f"Creator Center returned HTTP {result['status']}")
    try:
        payload = json.loads(result["text"])
    except json.JSONDecodeError as exc:
        raise CollectionError("Creator Center returned a non-JSON response") from exc
    if payload.get("status_code") not in (0, "0", None):
        raise CollectionError(f"Creator Center returned status_code={payload['status_code']}")
    return payload


async def collect_items(page: Any, page_size: int, max_pages: int) -> list[dict[str, Any]]:
    cursor = "0"
    visited: set[str] = set()
    collected: dict[str, dict[str, Any]] = {}
    for _ in range(max_pages):
        if cursor in visited:
            raise CollectionError("Creator Center pagination cursor repeated")
        visited.add(cursor)
        payload = await request_json(page, work_list_url(cursor, page_size))
        page_items = work_items(payload)
        if not page_items:
            if not collected:
                raise CollectionError("No work metrics found for the logged-in Creator Center account")
            break
        for item in page_items:
            collected[str(item["id"])] = item
        has_more, next_cursor = pagination(payload)
        if not has_more:
            return list(collected.values())
        if not next_cursor:
            raise CollectionError("Creator Center indicated more rows without a pagination cursor")
        cursor = next_cursor
    raise CollectionError(f"Stopped after max_pages={max_pages}")


async def discover_account_name(page: Any, supplied_name: str | None) -> str:
    if supplied_name:
        return supplied_name
    await page.goto(CREATOR_HOME_URL, wait_until="domcontentloaded", timeout=30000)
    try:
        await page.get_by_text(re.compile(r"抖音号[：:]")).first.wait_for(state="visible", timeout=10000)
    except Exception:
        await page.wait_for_timeout(1500)
    lines = [line.strip() for line in (await page.locator("body").inner_text()).splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if re.match(r"抖音号[：:]", line) and index > 0:
            candidate = lines[index - 1]
            if candidate and not re.fullmatch(r"[0-9]+", candidate):
                return candidate
    raise CollectionError("Could not determine account name; rerun with --account-name")


def write_snapshot(output: Path, rows: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


async def collect(args: argparse.Namespace) -> tuple[str, list[dict[str, Any]]]:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise CollectionError("Playwright is not installed; install it before running this skill") from exc

    args.profile_dir.mkdir(parents=True, exist_ok=True)
    login_image = args.login_image or args.output.with_suffix(".login.png")
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(args.profile_dir),
            channel=args.browser_channel,
            headless=args.headless,
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(CONTENT_MANAGE_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(800)
            if not await page_is_logged_in(page):
                await wait_for_login(page, login_image, args.login_timeout_seconds)
            account_name = await discover_account_name(page, args.account_name)
            await page.goto(CONTENT_MANAGE_URL, wait_until="domcontentloaded", timeout=30000)
            return account_name, await collect_items(page, args.page_size, args.max_pages)
        finally:
            await context.close()


def main() -> int:
    args = parse_args()
    now = datetime.now(TZ)
    snapshot_date = args.snapshot_date or now.date().isoformat()
    try:
        account_name, items = asyncio.run(collect(args))
    except CollectionError as exc:
        print(f"[douyin-creator-snapshot] ERROR: {exc}")
        return 2
    rows = rows_from_items(args.account_key, account_name, items, snapshot_date, now.strftime("%Y-%m-%d %H:%M:%S"))
    write_snapshot(args.output, rows)
    print(f"[douyin-creator-snapshot] collected={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
