#!/usr/bin/env python3
"""Collect Xiaohongshu Creator Center note analytics with Playwright."""
from __future__ import annotations

import argparse
import asyncio
import csv
import importlib.util
import json
import re
from datetime import datetime, time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")
LOGIN_URL = "https://creator.xiaohongshu.com/login"
DATA_URL = "https://creator.xiaohongshu.com/statistics/data-analysis"
NOTE_DETAIL_URL = "https://creator.xiaohongshu.com/statistics/note-detail"
NOTE_LIST_URL = "https://creator.xiaohongshu.com/api/galaxy/creator/datacenter/note/analyze/list"
QR_RENDER_DELAY_MS = 1000
QR_CLIP_PADDING = 16
HEADERS = [
    "platform", "account_key", "account_name", "data_date", "content_id", "title",
    "content", "publish_time", "exposure", "views", "cover_ctr", "likes",
    "comments", "favorites", "new_followers", "shares", "avg_watch_seconds",
    "danmaku", "two_second_exit_rate", "completion_rate", "exposure_fan_share",
    "views_fan_share", "cover_ctr_fan_share", "avg_watch_fan_seconds",
    "completion_fan_share", "two_second_exit_fan_share", "likes_fan_share",
    "comments_fan_share", "favorites_fan_share", "shares_fan_share",
    "collected_at",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Xiaohongshu Creator Center note analytics snapshots"
    )
    parser.add_argument("--profile-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start-date", required=True, help="Publish start date, YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Publish end date, YYYY-MM-DD")
    parser.add_argument("--snapshot-date", help="YYYY-MM-DD; defaults to Asia/Shanghai today")
    parser.add_argument("--login-image", type=Path)
    parser.add_argument("--login-timeout-seconds", type=int, default=300)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--note-type", type=int, default=0,
                        help="Xiaohongshu note type filter; 0 means all")
    parser.add_argument("--account-name",
                        help="Optional account name override when the page cannot expose it")
    parser.add_argument("--account-key", default="",
                        help="Stable caller-defined account key for multi-account snapshots")
    parser.add_argument("--include-details", action="store_true",
                        help="Open each note detail page and collect completion/2-second exit metrics")
    parser.add_argument("--browser-channel",
                        help="Optional Playwright browser channel, for example chrome")
    parser.add_argument("--headless", action="store_true")
    return parser.parse_args()


def date_ms(date_text: str, end: bool = False) -> int:
    parsed = datetime.strptime(date_text, "%Y-%m-%d").date()
    clock = time(23, 59, 59) if end else time(0, 0, 0)
    return int(datetime.combine(parsed, clock, TZ).timestamp() * 1000)


def note_list_url(start_date: str, end_date: str, page_num: int, page_size: int = 10,
                  note_type: int = 0) -> str:
    query = urlencode({
        "post_begin_time": date_ms(start_date, end=False),
        "post_end_time": date_ms(end_date, end=True),
        "type": note_type,
        "page_size": page_size,
        "page_num": page_num,
    })
    return f"{NOTE_LIST_URL}?{query}"


def list_url_matches(url: str, start_date: str, end_date: str, page_num: int,
                     page_size: int, note_type: int) -> bool:
    parsed = urlparse(url)
    if parsed.scheme + "://" + parsed.netloc + parsed.path != NOTE_LIST_URL:
        return False
    query = parse_qs(parsed.query)

    def one(key: str) -> str:
        values = query.get(key, [])
        return values[0] if values else ""

    expected = {
        "post_begin_time": str(date_ms(start_date, end=False)),
        "post_end_time": str(date_ms(end_date, end=True)),
        "type": str(note_type),
        "page_size": str(page_size),
        "page_num": str(page_num),
    }
    return all(one(key) == value for key, value in expected.items())


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def note_id(item: dict[str, Any]) -> Any:
    for key in ("note_id", "noteId", "id", "noteIdStr"):
        if item.get(key):
            return item[key]
    return ""


def note_items(payload: Any) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for item in walk(payload):
        item_id = note_id(item)
        if not item_id:
            continue
        keys = set(item)
        metricish = {
            "exposure", "exposure_count", "imp", "view", "view_count", "watch",
            "cover_click_rate", "like", "like_count", "comment", "comment_count",
            "collect", "collect_count", "favorite_count", "share", "share_count",
        }
        if keys.intersection(metricish):
            found[str(item_id)] = item
    return list(found.values())


def pagination_has_more(payload: Any, page_num: int, page_size: int, collected_count: int) -> bool:
    for item in walk(payload):
        for key in ("has_more", "hasMore"):
            if key in item:
                return bool(item[key])
        total = item.get("total")
        if isinstance(total, int):
            return page_num * page_size < total
    return collected_count >= page_size


def first_value(item: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return default


def percent(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped.endswith("%") else stripped
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(number) <= 1:
        number *= 100
    return f"{number:.2f}%"


def seconds(value: Any) -> Any:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", value)
        return match.group(1) if match else ""
    return value


def timestamp(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}", value):
        return value
    try:
        raw = int(float(value))
    except (TypeError, ValueError):
        return ""
    if raw > 10_000_000_000:
        raw //= 1000
    return datetime.fromtimestamp(raw, TZ).strftime("%Y-%m-%d %H:%M:%S")


DETAIL_LABELS = {
    "曝光数": ("exposure", "exposure_fan_share"),
    "观看数": ("views", "views_fan_share"),
    "封面点击率": ("cover_ctr", "cover_ctr_fan_share"),
    "平均观看时长": ("avg_watch_seconds", "avg_watch_fan_seconds"),
    "完播率": ("completion_rate", "completion_fan_share"),
    "2秒退出率": ("two_second_exit_rate", "two_second_exit_fan_share"),
    "涨粉数": ("new_followers", ""),
    "点赞数": ("likes", "likes_fan_share"),
    "评论数": ("comments", "comments_fan_share"),
    "收藏数": ("favorites", "favorites_fan_share"),
    "分享数": ("shares", "shares_fan_share"),
}


def parse_fan_value(text: str) -> str:
    if "粉丝" not in text:
        return ""
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)(秒|%)?", text)
    if not match:
        return ""
    value = match.group(1)
    return f"{value}%" if match.group(2) == "%" else value


def normalize_detail_value(key: str, value: str) -> str:
    if key.endswith("_rate") or key.endswith("_ctr"):
        return percent(value)
    if key.endswith("_seconds"):
        return str(seconds(value))
    return value


def parse_detail_lines(lines: list[str]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for index, line in enumerate(lines):
        if line not in DETAIL_LABELS or index + 1 >= len(lines):
            continue
        key, fan_key = DETAIL_LABELS[line]
        metrics[key] = normalize_detail_value(key, lines[index + 1])
        if fan_key and index + 2 < len(lines):
            metrics[fan_key] = parse_fan_value(lines[index + 2])
    return metrics


def row_from_note(account_key: str, account_name: str, item: dict[str, Any], detail: dict[str, Any],
                  snapshot_date: str, collected_at: str) -> dict[str, Any]:
    merged = dict(detail)
    return {
        "platform": "xiaohongshu",
        "account_key": account_key,
        "account_name": account_name,
        "data_date": snapshot_date,
        "content_id": str(note_id(item)),
        "title": first_value(item, ("title", "note_title", "display_title")),
        "content": first_value(item, ("desc", "description", "content")),
        "publish_time": timestamp(first_value(item, ("post_time", "postTime", "publish_time", "publishTime"))),
        "exposure": first_value(item, ("exposure", "exposure_count", "imp"), merged.get("exposure", "")),
        "views": first_value(item, ("view", "view_count", "watch", "watch_count"), merged.get("views", "")),
        "cover_ctr": percent(first_value(item, ("cover_click_rate", "coverClickRate"), merged.get("cover_ctr", ""))),
        "likes": first_value(item, ("like", "like_count", "likes"), merged.get("likes", "")),
        "comments": first_value(item, ("comment", "comment_count", "comments"), merged.get("comments", "")),
        "favorites": first_value(item, ("collect", "collect_count", "favorite_count"), merged.get("favorites", "")),
        "new_followers": first_value(item, ("follow", "follow_count", "fans_inc"), merged.get("new_followers", "")),
        "shares": first_value(item, ("share", "share_count", "shares"), merged.get("shares", "")),
        "avg_watch_seconds": seconds(first_value(
            item, ("avg_watch_duration", "avg_view_second", "avg_watch_seconds"),
            merged.get("avg_watch_seconds", ""),
        )),
        "danmaku": first_value(item, ("danmaku", "danmaku_count", "bullet_count")),
        "two_second_exit_rate": merged.get("two_second_exit_rate", ""),
        "completion_rate": merged.get("completion_rate", ""),
        "exposure_fan_share": merged.get("exposure_fan_share", ""),
        "views_fan_share": merged.get("views_fan_share", ""),
        "cover_ctr_fan_share": merged.get("cover_ctr_fan_share", ""),
        "avg_watch_fan_seconds": merged.get("avg_watch_fan_seconds", ""),
        "completion_fan_share": merged.get("completion_fan_share", ""),
        "two_second_exit_fan_share": merged.get("two_second_exit_fan_share", ""),
        "likes_fan_share": merged.get("likes_fan_share", ""),
        "comments_fan_share": merged.get("comments_fan_share", ""),
        "favorites_fan_share": merged.get("favorites_fan_share", ""),
        "shares_fan_share": merged.get("shares_fan_share", ""),
        "collected_at": collected_at,
    }


async def page_is_logged_in(page: Any) -> bool:
    try:
        return await page.get_by_text("数据看板", exact=True).count() > 0
    except Exception:
        return False


def padded_clip(rect: dict[str, Any], viewport: dict[str, Any], padding: int = QR_CLIP_PADDING) -> dict[str, Any]:
    x = max(0, float(rect["x"]) - padding)
    y = max(0, float(rect["y"]) - padding)
    right = min(float(viewport["width"]), float(rect["x"]) + float(rect["width"]) + padding)
    bottom = min(float(viewport["height"]), float(rect["y"]) + float(rect["height"]) + padding)
    return {"x": x, "y": y, "width": max(1, right - x), "height": max(1, bottom - y)}


def choose_qr_rect(
    candidates: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    viewport: dict[str, Any],
) -> dict[str, Any] | None:
    usable: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            width = float(candidate["width"])
            height = float(candidate["height"])
            x = float(candidate["x"])
            y = float(candidate["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if width < 120 or height < 120 or width > 420 or height > 420:
            continue
        ratio = width / height
        if ratio < 0.75 or ratio > 1.35:
            continue
        if y < 0 or x < 0:
            continue
        usable.append(candidate)
    if not usable:
        return None

    def center(rect: dict[str, Any]) -> tuple[float, float]:
        return (
            float(rect["x"]) + float(rect["width"]) / 2,
            float(rect["y"]) + float(rect["height"]) / 2,
        )

    label_rects = [
        label for label in labels
        if any(keyword in str(label.get("text", "")) for keyword in ("APP扫一扫登录", "扫码登录", "扫一扫登录"))
    ]

    if label_rects:
        def score(candidate: dict[str, Any]) -> tuple[float, float]:
            cx, cy = center(candidate)
            distances = []
            for label in label_rects:
                lx, ly = center(label)
                distance = abs(cx - lx) + abs(cy - ly)
                if float(candidate["y"]) + float(candidate["height"]) < float(label["y"]):
                    distance += 5000
                distances.append(distance)
            return min(distances), -float(candidate.get("area", 0))

        return min(usable, key=score)

    viewport_width = float(viewport.get("width", 0) or 0)
    def fallback_score(candidate: dict[str, Any]) -> tuple[int, float]:
        center_x, _ = center(candidate)
        right_side_bonus = 0 if not viewport_width or center_x >= viewport_width * 0.35 else 1
        return right_side_bonus, -float(candidate.get("area", 0))

    return min(usable, key=fallback_score)


async def qr_clip(page: Any) -> dict[str, Any] | None:
    data = await page.evaluate(
        """() => {
            const elements = Array.from(document.querySelectorAll("canvas,img,svg"));
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
                    tag: element.tagName,
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                    area: rect.width * rect.height,
                    text,
                });
            }
            const labels = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                const text = (walker.currentNode.textContent || "").trim();
                if (!/APP扫一扫登录|扫码登录|扫一扫登录/.test(text)) continue;
                const parent = walker.currentNode.parentElement;
                if (!parent) continue;
                const rect = parent.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;
                labels.push({ text, x: rect.x, y: rect.y, width: rect.width, height: rect.height });
            }
            return { candidates, labels, viewport: { width: window.innerWidth, height: window.innerHeight } };
        }"""
    )
    if not data:
        return None
    rect = choose_qr_rect(data["candidates"], data["labels"], data["viewport"])
    if not rect:
        return None
    return padded_clip(rect, data["viewport"])


async def switch_to_qr_login(page: Any) -> None:
    # The QR toggle is a folded corner on the login card and may not have text.
    await page.evaluate(
        """() => {
            const imgs = Array.from(document.querySelectorAll("img"));
            const target = imgs.find(img => img.className && String(img.className).includes("css-wemwzq"));
            if (target) target.click();
        }"""
    )
    await page.wait_for_timeout(QR_RENDER_DELAY_MS)


async def wait_for_login(page: Any, login_image: Path, timeout_seconds: int) -> None:
    await switch_to_qr_login(page)
    login_image.parent.mkdir(parents=True, exist_ok=True)
    await save_login_image(page, login_image)
    print(json.dumps({"status": "login_required", "qr_image": str(login_image.resolve())}, ensure_ascii=False),
          flush=True)
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        await page.wait_for_timeout(1500)
        if await page_is_logged_in(page):
            return
    raise CollectionError("Timed out waiting for Xiaohongshu Creator Center QR login")


async def save_login_image(page: Any, login_image: Path) -> bool:
    clip = await qr_clip(page)
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


async def request_json(page: Any, url: str) -> dict[str, Any]:
    result = await page.evaluate(
        """async (endpoint) => {
            const response = await fetch(endpoint, {
                credentials: 'include',
                headers: { accept: 'application/json, text/plain, */*' },
            });
            return { status: response.status, text: await response.text() };
        }""",
        url,
    )
    if result["status"] != 200:
        raise CollectionError(f"Xiaohongshu returned HTTP {result['status']}")
    try:
        return json.loads(result["text"])
    except json.JSONDecodeError as exc:
        raise CollectionError("Xiaohongshu returned a non-JSON response") from exc


async def response_json(response: Any) -> dict[str, Any]:
    text = await response.text()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CollectionError("Xiaohongshu returned a non-JSON response") from exc


async def type_date(page: Any, placeholder: str, value: str) -> None:
    field = page.locator(f'input[placeholder="{placeholder}"]').first
    await field.click()
    await page.keyboard.press("ControlOrMeta+A")
    await page.keyboard.type(value)
    await page.keyboard.press("Enter")


async def collect_first_frontend_page(page: Any, args: argparse.Namespace) -> dict[str, Any]:
    async with page.expect_response(
        lambda response: list_url_matches(
            response.url,
            args.start_date,
            args.end_date,
            1,
            args.page_size,
            args.note_type,
        ),
        timeout=20000,
    ) as response_info:
        await type_date(page, "开始时间", args.start_date)
        await type_date(page, "结束时间", args.end_date)
    response = await response_info.value
    if response.status != 200:
        raise CollectionError(f"Xiaohongshu returned HTTP {response.status}")
    return await response_json(response)


async def click_next_page(page: Any, page_num: int) -> bool:
    locators = [
        page.get_by_role("button", name=re.compile(r"下一页|Next|›|>")),
        page.locator("button").filter(has_text=re.compile(r"下一页|›|>")),
        page.locator('[aria-label*="下一页"], [aria-label*="Next"]'),
    ]
    for locator in locators:
        try:
            count = await locator.count()
            for index in range(count):
                candidate = locator.nth(index)
                if await candidate.is_visible() and await candidate.is_enabled():
                    await candidate.click()
                    return True
        except Exception:
            continue

    exact_page = page.get_by_text(str(page_num), exact=True)
    try:
        if await exact_page.count():
            await exact_page.first.click()
            return True
    except Exception:
        return False
    return False


async def collect_next_frontend_page(page: Any, args: argparse.Namespace, page_num: int) -> dict[str, Any] | None:
    async with page.expect_response(
        lambda response: list_url_matches(
            response.url,
            args.start_date,
            args.end_date,
            page_num,
            args.page_size,
            args.note_type,
        ),
        timeout=15000,
    ) as response_info:
        clicked = await click_next_page(page, page_num)
        if not clicked:
            return None
    response = await response_info.value
    if response.status != 200:
        raise CollectionError(f"Xiaohongshu returned HTTP {response.status}")
    return await response_json(response)


async def collect_list_items(page: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    collected: dict[str, dict[str, Any]] = {}
    payload = await collect_first_frontend_page(page, args)
    items = note_items(payload)
    for item in items:
        collected[str(note_id(item))] = item
    if not pagination_has_more(payload, 1, args.page_size, len(items)):
        return list(collected.values())

    for page_num in range(1, args.max_pages + 1):
        if page_num == 1:
            continue
        payload = await collect_next_frontend_page(page, args, page_num)
        if payload is None:
            break
        items = note_items(payload)
        for item in items:
            collected[str(note_id(item))] = item
        if not pagination_has_more(payload, page_num, args.page_size, len(items)):
            break
    return list(collected.values())


async def collect_detail(page: Any, item: dict[str, Any]) -> dict[str, Any]:
    item_id = note_id(item)
    if not item_id:
        return {}
    await page.goto(f"{NOTE_DETAIL_URL}?noteId={item_id}", wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)
    lines = [line.strip() for line in (await page.locator("body").inner_text()).splitlines() if line.strip()]
    return parse_detail_lines(lines)


async def discover_account_name(page: Any, supplied_name: str | None) -> str:
    if supplied_name:
        return supplied_name
    await page.goto(DATA_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1000)
    lines = [line.strip() for line in (await page.locator("body").inner_text()).splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line in {"发布笔记", "首页"} and index > 0:
            candidate = lines[index - 1]
            if candidate and candidate != "创作服务平台":
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
        raise CollectionError("Playwright is not installed") from exc

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
            await page.goto(DATA_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1000)
            if not await page_is_logged_in(page):
                await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                await wait_for_login(page, login_image, args.login_timeout_seconds)
                await page.goto(DATA_URL, wait_until="domcontentloaded", timeout=30000)
            account_name = await discover_account_name(page, args.account_name)
            items = await collect_list_items(page, args)
            details: dict[str, dict[str, Any]] = {}
            if args.include_details:
                for item in items:
                    details[str(note_id(item))] = await collect_detail(page, item)
            return account_name, [
                row_from_note(
                    args.account_key,
                    account_name,
                    item,
                    details.get(str(note_id(item)), {}),
                    args.snapshot_date or datetime.now(TZ).date().isoformat(),
                    datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
                )
                for item in items
            ]
        finally:
            await context.close()


def main() -> int:
    args = parse_args()
    try:
        _, rows = asyncio.run(collect(args))
    except CollectionError as exc:
        print(f"[xiaohongshu-creator-data] ERROR: {exc}")
        return 2
    write_snapshot(args.output, rows)
    print(f"[xiaohongshu-creator-data] collected={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
