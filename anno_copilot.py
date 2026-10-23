#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《纪元1800》全自动贸易指挥中心 (Anno 1800 Trade Copilot) - Full-Stack Production Build
功能热键：
- [F7]  在 Ctrl+Q 界面自动顺着左侧列表依次点击多个岛屿，全自动批量扫描全图供需
- [F8]  在 Ctrl+Q 界面对当前选中岛屿执行【多页滚轮自动截图 + OCR 供需差额合并识别】
- [F9]  启动交互式分辨率坐标与截图框校准向导（适配 1080P / 2K / 4K 任意无边框窗口）
- [F10] 一键清空当前选中船只的 6 个货仓残留杂物（自动拖拽丢入海中并回车确认）
- [Web] http://127.0.0.1:18000 贸易指挥看板，支持智能航线配对与一键 RPA 写入游戏
"""

import json
import os
import re
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import keyboard
import mss
import numpy as np
import pyautogui
import pyperclip
from PIL import Image, ImageDraw, ImageFont

pyautogui.PAUSE = 0.08
pyautogui.FAILSAFE = True

# 打包为 exe 后，配置与数据固定写在 exe 所在目录，避免依赖当前工作目录
BASE_DIR = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
CONFIG_FILE = os.path.join(BASE_DIR, "anno_coords_config.json")
DATA_FILE = os.path.join(BASE_DIR, "anno_islands_data.json")

try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
    OCR_AVAILABLE = True
except ImportError:
    ocr_engine = None
    OCR_AVAILABLE = False


def run_selftest():
    """离线自检：验证 OCR 引擎与模型文件可用（打包产物排障用）。"""
    if not OCR_AVAILABLE:
        print("SELFTEST FAIL: rapidocr_onnxruntime 不可用")
        return False
    font = None
    for fp in (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\msyh.ttc"):
        try:
            font = ImageFont.truetype(fp, 36)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    img = Image.new("RGB", (820, 140), (20, 26, 36))
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), "DEMAND 120 SUPPLY 86", font=font, fill=(235, 235, 235))
    result, _ = ocr_engine(np.array(img))
    texts = [text for _, text, _ in (result or [])]
    ok = any("120" in t and "86" in t for t in texts)
    print("SELFTEST:", "OK" if ok else "FAIL", texts)
    return ok

# =====================================================================
# 1. 纪元1800 核心物资字典与图标库
# =====================================================================
GOODS_CATALOG = [
    {"id": "timber",    "name": "木材",       "tier": "建材",   "icon": "🪵"},
    {"id": "bricks",    "name": "砖块",       "tier": "建材",   "icon": "🧱"},
    {"id": "steel",     "name": "钢梁",       "tier": "建材",   "icon": "🏗️"},
    {"id": "windows",   "name": "窗户",       "tier": "建材",   "icon": "🪟"},
    {"id": "concrete",  "name": "钢筋混凝土", "tier": "建材",   "icon": "🏛️"},
    {"id": "fish",      "name": "鱼",         "tier": "农夫",   "icon": "🐟"},
    {"id": "work_cl",   "name": "工作服",     "tier": "农夫",   "icon": "👕"},
    {"id": "schnapps",  "name": "烈酒",       "tier": "农夫",   "icon": "🍶"},
    {"id": "sausages",  "name": "香肠",       "tier": "工人",   "icon": "🌭"},
    {"id": "bread",     "name": "面包",       "tier": "工人",   "icon": "🍞"},
    {"id": "soap",      "name": "肥皂",       "tier": "工人",   "icon": "🧼"},
    {"id": "beer",      "name": "啤酒",       "tier": "工人",   "icon": "🍺"},
    {"id": "canned",    "name": "罐头食品",   "tier": "工匠",   "icon": "🥫"},
    {"id": "sewing",    "name": "缝纫机",     "tier": "工匠",   "icon": "🧵"},
    {"id": "fur_coats", "name": "皮草大衣",   "tier": "工匠",   "icon": "🧥"},
    {"id": "rum",       "name": "朗姆酒",     "tier": "工匠",   "icon": "🍹"},
    {"id": "glasses",   "name": "眼镜",       "tier": "工程师", "icon": "👓"},
    {"id": "coffee",    "name": "咖啡",       "tier": "工程师", "icon": "☕"},
    {"id": "lightbulb", "name": "灯泡",       "tier": "工程师", "icon": "💡"},
    {"id": "penny_far", "name": "高轮自行车", "tier": "工程师", "icon": "🚲"},
    {"id": "pocket_w",  "name": "怀表",       "tier": "工程师", "icon": "⏱️"},
    {"id": "champagne", "name": "香槟",       "tier": "投资者", "icon": "🍾"},
    {"id": "cigars",    "name": "雪茄",       "tier": "投资者", "icon": "🚬"},
    {"id": "chocolate", "name": "巧克力",     "tier": "投资者", "icon": "🍫"},
    {"id": "jewelry",   "name": "珠宝",       "tier": "投资者", "icon": "💎"},
    {"id": "gramophon", "name": "留声机",     "tier": "投资者", "icon": "📻"},
    {"id": "steam_car", "name": "蒸汽马车",   "tier": "投资者", "icon": "🚗"},
    {"id": "fried_pl",  "name": "炸香蕉",     "tier": "新世界", "icon": "🍌"},
    {"id": "ponchos",   "name": "羊驼毛斗篷", "tier": "新世界", "icon": "🧥"},
    {"id": "tortillas", "name": "玉米饼",     "tier": "新世界", "icon": "🌮"},
    {"id": "bowler_h",  "name": "圆顶礼帽",   "tier": "新世界", "icon": "🎩"}
]

NAME_TO_ID = {item["name"]: item["id"] for item in GOODS_CATALOG}
NAME_TO_ID["罐头"] = "canned"
NAME_TO_ID["混凝土"] = "concrete"
NAME_TO_ID["自行车"] = "penny_far"

# =====================================================================
# 2. 默认坐标配置 (基于 1920x1080 基准，可通过 F9 校准覆盖)
# =====================================================================
DEFAULT_COORDS = {
    "ctrl_q_island_box": [130, 180, 420, 260],
    "ctrl_q_list_box":   [550, 220, 1450, 920],
    "ctrl_q_first_island_row": [260, 310],
    "ctrl_q_island_row_step":  52,

    "btn_create_route":     [260, 940],
    "btn_confirm_trade":    [260, 880],
    "input_island_search":  [250, 220],
    "item_first_island":    [250, 285],
    "slot_station1_good1":  [820, 360],
    "input_good_search":    [820, 395],
    "item_first_good":      [820, 445],
    "slot_station2_good1":  [820, 580],
    "btn_station2_throw":   [760, 625],
    "input_route_name":     [600, 180],

    "ship_slot_1": [1540, 930],
    "ship_slot_2": [1600, 930],
    "ship_slot_3": [1660, 930],
    "ship_slot_4": [1720, 930],
    "ship_slot_5": [1780, 930],
    "ship_slot_6": [1840, 930],
    "sea_drop_point": [960, 500]
}

DEFAULT_ISLANDS = [
    {
        "id": "isl_1",
        "name": "皇冠瀑布",
        "region": "旧世界/海角",
        "items": {"beer": -14, "coffee": -12, "rum": -8, "champagne": -6, "sausages": -10, "soap": 6}
    },
    {
        "id": "isl_2",
        "name": "麦香谷",
        "region": "旧世界/海角",
        "items": {"beer": 18, "sausages": 12, "bread": 10, "schnapps": 8, "steel": -6}
    },
    {
        "id": "isl_3",
        "name": "铁锤堡",
        "region": "旧世界/海角",
        "items": {"steel": 12, "concrete": 10, "champagne": 8, "glasses": 6}
    },
    {
        "id": "isl_4",
        "name": "圣克鲁斯",
        "region": "新世界",
        "items": {"coffee": 15, "rum": 12, "chocolate": 8}
    }
]


def load_coords():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = DEFAULT_COORDS.copy()
                merged.update(data)
                return merged
        except Exception:
            pass
    return DEFAULT_COORDS.copy()


def save_coords(coords):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(coords, f, ensure_ascii=False, indent=2)


def load_islands():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    save_islands(DEFAULT_ISLANDS)
    return DEFAULT_ISLANDS


def save_islands(islands):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(islands, f, ensure_ascii=False, indent=2)


COORDS = load_coords()
ISLANDS_STATE = load_islands()


# =====================================================================
# 3. 窗口聚焦与键鼠 RPA 引擎 (一键建航线 & F10 一键抛货)
# =====================================================================
def focus_anno_window():
    try:
        import win32gui
        hwnd = win32gui.FindWindow(None, "Anno 1800")
        if hwnd:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.25)
            return True
    except ImportError:
        pass
    pyautogui.click(960, 10)
    time.sleep(0.2)
    return True


def paste_text(text):
    pyperclip.copy(str(text))
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.12)


def execute_create_route_macro(route_payload):
    global COORDS
    COORDS = load_coords()

    from_isl = route_payload.get("from_island", "")
    to_isl = route_payload.get("to_island", "")
    good_name = route_payload.get("good_name", "")
    throw_flag = route_payload.get("throw_overboard", True)
    route_name = route_payload.get("route_name", f"[{good_name}] {from_isl}->{to_isl}")

    print(f"\n[RPA 引擎] 正在自动创建贸易航线: {route_name} ...")
    focus_anno_window()

    pyautogui.hotkey("ctrl", "r")
    time.sleep(0.45)

    pyautogui.click(*COORDS["btn_create_route"])
    time.sleep(0.2)
    pyautogui.click(*COORDS["btn_confirm_trade"])
    time.sleep(0.3)

    pyautogui.click(*COORDS["input_island_search"])
    paste_text(from_isl)
    time.sleep(0.2)
    pyautogui.click(*COORDS["item_first_island"])
    time.sleep(0.25)

    pyautogui.click(*COORDS["input_island_search"])
    paste_text(to_isl)
    time.sleep(0.2)
    pyautogui.click(*COORDS["item_first_island"])
    time.sleep(0.25)

    pyautogui.click(*COORDS["slot_station1_good1"])
    time.sleep(0.2)
    pyautogui.click(*COORDS["input_good_search"])
    paste_text(good_name)
    time.sleep(0.2)
    pyautogui.click(*COORDS["item_first_good"])
    time.sleep(0.25)

    pyautogui.click(*COORDS["slot_station2_good1"])
    time.sleep(0.2)

    if throw_flag:
        pyautogui.click(*COORDS["btn_station2_throw"])
        time.sleep(0.15)

    pyautogui.click(*COORDS["input_route_name"])
    paste_text(route_name)
    pyautogui.press("enter")

    print(f"[RPA 引擎] ✅ 航线 [{route_name}] 创建完成！请手动指派货船。")
    return {"status": "ok", "msg": f"已在游戏内建立航线：{route_name}"}


def dump_ship_cargo_macro():
    global COORDS
    COORDS = load_coords()
    print("\n[F10 抛货助手] 正在清空当前选中船只的 6 个货仓槽位...")
    sea_x, sea_y = COORDS["sea_drop_point"]

    for i in range(1, 7):
        sx, sy = COORDS[f"ship_slot_{i}"]
        pyautogui.moveTo(sx, sy, duration=0.05)
        pyautogui.mouseDown()
        pyautogui.moveTo(sea_x, sea_y, duration=0.08)
        pyautogui.mouseUp()
        time.sleep(0.06)
        pyautogui.press("enter")
        time.sleep(0.06)

    print("[F10 抛货助手] ✅ 船只杂物清理完毕！")


# =====================================================================
# 4. F8 & F7：Ctrl+Q 多页自动滚轮截图与 OCR 供需差额合并解析
# =====================================================================
def grab_screen_region(bbox):
    left, top, right, bottom = bbox
    with mss.mss() as sct:
        monitor = {
            "left": int(left),
            "top": int(top),
            "width": int(right - left),
            "height": int(bottom - top)
        }
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        return np.array(img)


def parse_single_page_goods(list_img):
    list_res, _ = ocr_engine(list_img)
    page_items = {}
    all_seen_goods = set()

    if not list_res:
        return page_items, all_seen_goods

    rows = []
    for box, text, score in list_res:
        y_center = (box[0][1] + box[2][1]) / 2.0
        x_center = (box[0][0] + box[2][0]) / 2.0
        placed = False
        for r in rows:
            if abs(r["y"] - y_center) < 22:
                r["tokens"].append((x_center, text.strip()))
                placed = True
                break
        if not placed:
            rows.append({"y": y_center, "tokens": [(x_center, text.strip())]})

    for r in rows:
        tokens = sorted(r["tokens"], key=lambda x: x[0])
        row_text = " ".join([t[1] for t in tokens])

        matched_good_id = None
        for g_name, g_id in NAME_TO_ID.items():
            if g_name in row_text:
                matched_good_id = g_id
                break

        if matched_good_id:
            all_seen_goods.add(matched_good_id)
            nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", row_text)]
            if len(nums) >= 2:
                demand, supply = nums[0], nums[1]
                delta = round(supply - demand, 1)
                page_items[matched_good_id] = delta if abs(delta) >= 0.5 else 0.0

    return page_items, all_seen_goods


def scan_ctrl_q_screen(max_pages=3, scroll_clicks=-700):
    global COORDS, ISLANDS_STATE
    COORDS = load_coords()

    print("\n[F8 多页扫描引擎] 正在启动 Ctrl+Q 自动滚轮采样...")
    if not OCR_AVAILABLE:
        print("⚠️ 未检测到 rapidocr_onnxruntime，请先执行 pip install -r requirements.txt")
        return None

    isl_img = grab_screen_region(COORDS["ctrl_q_island_box"])
    isl_res, _ = ocr_engine(isl_img)
    detected_island_name = None
    if isl_res:
        for line in isl_res:
            txt = line[1].strip()
            if len(txt) >= 2 and not txt.isdigit():
                detected_island_name = txt
                break

    if not detected_island_name:
        detected_island_name = f"扫描岛屿_{int(time.time()) % 1000}"

    l_left, l_top, l_right, l_bottom = COORDS["ctrl_q_list_box"]
    center_x = int((l_left + l_right) / 2)
    center_y = int((l_top + l_bottom) / 2)
    pyautogui.moveTo(center_x, center_y, duration=0.1)
    pyautogui.scroll(2500)
    time.sleep(0.25)

    merged_items = {}
    cumulative_seen = set()

    for page_idx in range(1, max_pages + 1):
        print(f"   📸 正在扫描 [{detected_island_name}] 第 {page_idx}/{max_pages} 页...")
        list_img = grab_screen_region(COORDS["ctrl_q_list_box"])
        page_items, page_seen = parse_single_page_goods(list_img)

        new_discovered = page_seen - cumulative_seen
        if page_idx > 1 and len(new_discovered) == 0:
            print("   ⏹️ 列表已滚到底部，提前结束翻页。")
            break

        merged_items.update(page_items)
        cumulative_seen.update(page_seen)

        if page_idx < max_pages:
            pyautogui.scroll(scroll_clicks)
            time.sleep(0.32)

    final_items = {k: v for k, v in merged_items.items() if abs(v) >= 0.5}
    print(f"[F8 扫描完成] 岛屿: 【{detected_island_name}】 | 有效差额 ({len(final_items)} 项): {final_items}")

    found = False
    for isl in ISLANDS_STATE:
        if isl["name"] == detected_island_name:
            isl["items"] = final_items
            found = True
            break
    if not found:
        ISLANDS_STATE.append({
            "id": f"isl_{int(time.time())}_{len(ISLANDS_STATE)}",
            "name": detected_island_name,
            "region": "旧世界/海角",
            "items": final_items
        })

    save_islands(ISLANDS_STATE)
    return detected_island_name


def batch_scan_all_islands(island_count=5):
    global COORDS
    COORDS = load_coords()
    print(f"\n[F7 批量全图扫描] 即将自动遍历左侧前 {island_count} 个岛屿...")
    base_x, base_y = COORDS["ctrl_q_first_island_row"]
    step_y = COORDS.get("ctrl_q_island_row_step", 52)

    seen_names = set()
    for idx in range(island_count):
        target_y = base_y + idx * step_y
        pyautogui.click(base_x, target_y)
        time.sleep(0.35)
        isl_name = scan_ctrl_q_screen()
        if isl_name in seen_names:
            print("⏹️ 检测到重复岛屿名，左侧岛屿列表已遍历完毕！")
            break
        if isl_name:
            seen_names.add(isl_name)

    print("🎉 [F7 批量全图扫描] 全部岛屿供需已同步至网页看板！")


# =====================================================================
# 5. F9 快捷键：交互式分辨率坐标与 Ctrl+Q 截图区域校准向导
# =====================================================================
def run_calibration_wizard():
    global COORDS
    print("\n" + "=" * 65)
    print("🎯 启动【纪元1800 分辨率坐标与 OCR 截图框校准向导】")
    print("操作说明：请根据提示将鼠标悬停在游戏对应位置，4 秒倒计时结束自动记录")
    print("=" * 65)

    point_steps = [
        ("btn_create_route",     "打开贸易航线(Ctrl+R)，将鼠标放在左下角【创建新航线】按钮上"),
        ("btn_confirm_trade",    "点击创建后，将鼠标放在弹出的【贸易航线】选项上"),
        ("input_island_search",  "进入航线编辑后，将鼠标放在左侧【岛屿搜索输入框】内"),
        ("item_first_island",    "将鼠标放在搜索框下方的【第一个岛屿列表项】位置"),
        ("slot_station1_good1",  "将鼠标放在第1站点(出发岛)的第1个【+号 装载物资槽位】上"),
        ("input_good_search",    "点开+号后，将鼠标放在物资弹窗的【搜索输入框】内"),
        ("item_first_good",      "将鼠标放在筛选出的【第一个物资图标】上"),
        ("slot_station2_good1",  "将鼠标放在第2站点(目标岛)的第1个【卸载槽位】上"),
        ("btn_station2_throw",   "将鼠标放在第2站点下方【无法卸载时丢入海中(自动抛货)】小图标上"),
        ("input_route_name",     "将鼠标放在顶部的【航线名称文本框】上")
    ]

    for key, desc in point_steps:
        print(f"\n👉 校准点 ({key}): {desc}")
        for sec in [4, 3, 2, 1]:
            print(f"   倒计时 {sec} 秒...", end="\r")
            time.sleep(1)
        x, y = pyautogui.position()
        COORDS[key] = [x, y]
        print(f"   ✅ 已记录坐标: [{x}, {y}]          ")

    print("\n👉 接下来校准 Ctrl+Q 统计面板的 OCR 截图范围（请先按 Ctrl+Q 打开生产统计面板）：")
    print("   1. 请将鼠标放在左侧【当前选中岛屿名字】的【左上角】...")
    time.sleep(4)
    ix1, iy1 = pyautogui.position()
    print("   2. 请将鼠标放在左侧【当前选中岛屿名字】的【右下角】...")
    time.sleep(4)
    ix2, iy2 = pyautogui.position()
    COORDS["ctrl_q_island_box"] = [min(ix1, ix2), min(iy1, iy2), max(ix1, ix2), max(iy1, iy2)]
    print(f"   ✅ 岛屿名区域已锁定: {COORDS['ctrl_q_island_box']}")

    print("   3. 请将鼠标放在中间【物资列表区域】的【左上角】（包含物资名与右侧绿/蓝条数字）...")
    time.sleep(4)
    lx1, ly1 = pyautogui.position()
    print("   4. 请将鼠标放在中间【物资列表区域】的【右下角】...")
    time.sleep(4)
    lx2, ly2 = pyautogui.position()
    COORDS["ctrl_q_list_box"] = [min(lx1, lx2), min(ly1, ly2), max(lx1, lx2), max(ly1, ly2)]
    print(f"   ✅ 物资列表区域已锁定: {COORDS['ctrl_q_list_box']}")

    save_coords(COORDS)
    print("\n🎉 校准全部完成！配置已保存至 anno_coords_config.json。\n")


# =====================================================================
# 6. 内嵌单页 Web 看板 HTML
# =====================================================================
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>纪元1800 全自动贸易指挥中心 (Copilot)</title>
<style>
  :root {
    --bg: #0f141c; --card: #18202c; --border: #2c3a4f;
    --gold: #d4af37; --gold-hover: #f3cc52;
    --green: #10b981; --red: #ef4444; --text: #e2e8f0; --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: "Microsoft YaHei", sans-serif; }
  body { background: var(--bg); color: var(--text); padding: 20px; }
  header {
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 2px solid var(--gold); padding-bottom: 14px; margin-bottom: 20px;
    flex-wrap: wrap; gap: 12px;
  }
  .title-box h1 { color: var(--gold); font-size: 22px; letter-spacing: 1px; }
  .title-box p { color: var(--muted); font-size: 13px; margin-top: 4px; }
  .hotkey-bar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .badge {
    background: #1e293b; border: 1px solid var(--gold); color: var(--gold);
    padding: 6px 10px; border-radius: 6px; font-size: 12px; font-weight: bold;
  }
  .btn {
    background: var(--gold); color: #000; border: none; padding: 8px 14px;
    border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 13px; transition: 0.15s;
  }
  .btn:hover { background: var(--gold-hover); transform: translateY(-1px); }
  .btn-outline { background: transparent; color: var(--gold); border: 1px solid var(--gold); }
  .btn-outline:hover { background: rgba(212,175,55,0.15); }
  .layout { display: grid; grid-template-columns: 1.35fr 1fr; gap: 22px; }
  .panel { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }
  .panel-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 15px; border-bottom: 1px solid var(--border); padding-bottom: 10px;
  }
  .island-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 14px; }
  .island-card { background: #131a24; border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
  .island-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
  .island-name { font-size: 16px; font-weight: bold; color: var(--gold); }
  .region-tag { font-size: 11px; color: var(--muted); background: #1e293b; padding: 2px 8px; border-radius: 4px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; min-height: 30px; }
  .chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
  .chip.surplus { background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16,185,129,0.4); }
  .chip.deficit { background: rgba(239, 68, 68, 0.16); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
  .route-card {
    background: #131a24; border: 1px solid var(--border); border-left: 4px solid var(--gold);
    border-radius: 8px; padding: 12px 14px; margin-bottom: 12px;
    display: flex; justify-content: space-between; align-items: center; gap: 10px;
  }
  .route-title { font-size: 15px; font-weight: bold; margin-bottom: 4px; }
  .route-sub { font-size: 12px; color: var(--muted); }
  .modal-mask {
    position: fixed; inset: 0; background: rgba(0,0,0,0.75);
    display: none; justify-content: center; align-items: center; z-index: 999;
  }
  .modal {
    background: var(--card); border: 1px solid var(--gold); border-radius: 10px;
    width: 780px; max-height: 85vh; overflow-y: auto; padding: 20px;
  }
  .goods-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }
  .good-row {
    background: #131a24; border: 1px solid var(--border); border-radius: 6px;
    padding: 8px 10px; display: flex; justify-content: space-between; align-items: center;
  }
  .good-row input {
    width: 65px; background: #0f141c; color: #fff; border: 1px solid var(--border);
    border-radius: 4px; padding: 4px 6px; text-align: center; font-weight: bold;
  }
  .toast {
    position: fixed; bottom: 24px; right: 24px; background: #10b981; color: #000;
    padding: 12px 20px; border-radius: 8px; font-weight: bold; display: none; z-index: 1000;
  }
</style>
</head>
<body>

<header>
  <div class="title-box">
    <h1>⚓ 《纪元1800》全自动贸易与供需指挥中心</h1>
    <p>本地 Python RPA 引擎在线 | 支持多页滚轮 OCR 扫描 & 网页端一键自动建航线</p>
  </div>
  <div class="hotkey-bar">
    <span class="badge">F7：批量扫全图岛屿</span>
    <span class="badge">F8：多页扫描当前岛屿</span>
    <span class="badge">F9：校准分辨率坐标</span>
    <span class="badge">F10：一键抛空选中船只杂物</span>
    <button class="btn btn-outline" onclick="triggerScanFromWeb()">📸 3秒后扫描游戏</button>
    <button class="btn" onclick="openAddIsland()">+ 新增岛屿</button>
  </div>
</header>

<div class="layout">
  <div class="panel">
    <div class="panel-header">
      <h3>🏝️ 岛屿产出盈余 / 消费缺口 (单位: 吨/分钟 t/min)</h3>
      <span style="font-size:12px;color:var(--muted)" id="sync-status">实时同步中...</span>
    </div>
    <div class="island-grid" id="island-list"></div>
  </div>

  <div class="panel">
    <div class="panel-header">
      <h3>⛵ 智能贸易航线推荐 & 一键写入游戏</h3>
      <label style="font-size:12px;color:var(--muted);cursor:pointer;">
        <input type="checkbox" id="chk-throw" checked> 默认开启满仓自动抛货
      </label>
    </div>
    <div id="route-list"></div>
  </div>
</div>

<div class="modal-mask" id="edit-modal">
  <div class="modal">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <h3 style="color:var(--gold)">编辑岛屿物资差额 (+为可出口盈余，-为需进口缺口)</h3>
      <button class="btn btn-outline" onclick="closeModal()">保存并关闭</button>
    </div>
    <div style="margin-bottom:12px;display:flex;gap:10px;">
      <input id="edit-isl-name" placeholder="岛屿名称 (需与游戏内一致)" style="flex:1;padding:7px;background:#0f141c;color:#fff;border:1px solid var(--border);border-radius:4px;">
      <input id="edit-isl-region" placeholder="所属区域 (如: 旧世界/新世界)" style="width:180px;padding:7px;background:#0f141c;color:#fff;border:1px solid var(--border);border-radius:4px;">
    </div>
    <div class="goods-grid" id="modal-goods-grid"></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let CATALOG = [];
let ISLANDS = [];
let currentEditIndex = -1;

function showToast(msg, isError=false) {
  const t = document.getElementById('toast');
  t.style.background = isError ? '#ef4444' : '#10b981';
  t.style.color = isError ? '#fff' : '#000';
  t.innerText = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3200);
}

async function fetchState() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    CATALOG = data.catalog;
    ISLANDS = data.islands;
    renderIslands();
    renderRoutes();
    document.getElementById('sync-status').innerText = '已同步 (' + new Date().toLocaleTimeString() + ')';
  } catch (e) {
    document.getElementById('sync-status').innerText = '等待本地服务响应...';
  }
}

async function saveStateToServer() {
  await fetch('/api/save_islands', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({islands: ISLANDS})
  });
  renderIslands();
  renderRoutes();
}

function getGoodMeta(id) {
  return CATALOG.find(g => g.id === id) || {id, name: id, icon: '📦'};
}

function renderIslands() {
  const box = document.getElementById('island-list');
  box.innerHTML = '';
  ISLANDS.forEach((isl, idx) => {
    const entries = Object.entries(isl.items || {}).filter(([k, v]) => Math.abs(v) >= 0.5);
    const chipsHtml = entries.length === 0
      ? '<span style="color:var(--muted);font-size:12px;">暂无盈余或缺口记录</span>'
      : entries.map(([gid, val]) => {
          const g = getGoodMeta(gid);
          const cls = val > 0 ? 'surplus' : 'deficit';
          const sign = val > 0 ? '+' : '';
          return `<span class="chip ${cls}">${g.icon} ${g.name} ${sign}${val}</span>`;
        }).join('');

    box.innerHTML += `
      <div class="island-card">
        <div class="island-top">
          <div>
            <span class="island-name">${isl.name}</span>
            <span class="region-tag">${isl.region || '旧世界'}</span>
          </div>
          <div style="display:flex;gap:6px;">
            <button class="btn btn-outline" style="padding:4px 8px;font-size:12px;" onclick="openEditIsland(${idx})">⚙️ 配置</button>
            <button class="btn btn-outline" style="padding:4px 8px;font-size:12px;border-color:#ef4444;color:#f87171;" onclick="deleteIsland(${idx})">✕</button>
          </div>
        </div>
        <div class="chips">${chipsHtml}</div>
      </div>
    `;
  });
}

function renderRoutes() {
  const routeBox = document.getElementById('route-list');
  routeBox.innerHTML = '';
  const routes = [];

  CATALOG.forEach(good => {
    const suppliers = [];
    const consumers = [];
    ISLANDS.forEach(isl => {
      const val = parseFloat((isl.items || {})[good.id] || 0);
      if (val > 0) suppliers.push({name: isl.name, rem: val});
      if (val < 0) consumers.push({name: isl.name, need: Math.abs(val)});
    });

    let sIdx = 0, cIdx = 0;
    while (sIdx < suppliers.length && cIdx < consumers.length) {
      const s = suppliers[sIdx];
      const c = consumers[cIdx];
      const flow = Math.round(Math.min(s.rem, c.need) * 10) / 10;
      if (flow > 0) {
        routes.push({
          good_id: good.id,
          good_name: good.name,
          good_icon: good.icon,
          from_island: s.name,
          to_island: c.name,
          rate: flow,
          recommended_load: Math.max(50, Math.ceil(flow * 8 / 10) * 10)
        });
      }
      s.rem -= flow;
      c.need -= flow;
      if (s.rem <= 0.01) sIdx++;
      if (c.need <= 0.01) cIdx++;
    }
  });

  if (routes.length === 0) {
    routeBox.innerHTML = '<p style="color:var(--muted);font-size:13px;">当前没有需要跨岛调配的贸易航线。</p>';
    return;
  }

  routes.forEach(r => {
    const routeName = `[${r.good_name}${r.rate}t] ${r.from_island}->${r.to_island}`;
    routeBox.innerHTML += `
      <div class="route-card">
        <div>
          <div class="route-title">${r.good_icon} ${r.good_name}：${r.from_island} ➔ ${r.to_island}</div>
          <div class="route-sub">建议调配速率: <b style="color:#34d399">${r.rate} 吨/分</b> | 建议单趟装载: <b>${r.recommended_load} 吨</b></div>
        </div>
        <button class="btn" onclick='applyRouteToGame(${JSON.stringify({
          from_island: r.from_island,
          to_island: r.to_island,
          good_name: r.good_name,
          amount: r.recommended_load,
          route_name: routeName
        })})'>🚀 一键写入游戏</button>
      </div>
    `;
  });
}

async function applyRouteToGame(payload) {
  payload.throw_overboard = document.getElementById('chk-throw').checked;
  showToast('正在切回《纪元1800》自动创建航线，请勿移动鼠标...');
  const res = await fetch('/api/apply_route', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  showToast(data.msg, data.status !== 'ok');
}

async function triggerScanFromWeb() {
  showToast('3秒后将自动滚轮扫描游戏 Ctrl+Q 面板，请立即切回游戏画面！');
  setTimeout(async () => {
    await fetch('/api/scan_ctrl_q', {method: 'POST'});
    await fetchState();
    showToast('✅ 多页扫描完成，岛屿数据已更新！');
  }, 3000);
}

function openEditIsland(idx) {
  currentEditIndex = idx;
  const isl = ISLANDS[idx];
  document.getElementById('edit-isl-name').value = isl.name;
  document.getElementById('edit-isl-region').value = isl.region || '旧世界';
  const grid = document.getElementById('modal-goods-grid');
  grid.innerHTML = '';
  CATALOG.forEach(g => {
    const val = (isl.items && isl.items[g.id]) ? isl.items[g.id] : 0;
    grid.innerHTML += `
      <div class="good-row">
        <span>${g.icon} ${g.name}</span>
        <input type="number" step="1" data-gid="${g.id}" value="${val}">
      </div>
    `;
  });
  document.getElementById('edit-modal').style.display = 'flex';
}

function openAddIsland() {
  ISLANDS.push({id: 'isl_' + Date.now(), name: '新岛屿', region: '旧世界', items: {}});
  openEditIsland(ISLANDS.length - 1);
}

function closeModal() {
  if (currentEditIndex >= 0) {
    const isl = ISLANDS[currentEditIndex];
    isl.name = document.getElementById('edit-isl-name').value.trim() || '未命名岛屿';
    isl.region = document.getElementById('edit-isl-region').value.trim() || '旧世界';
    const inputs = document.querySelectorAll('#modal-goods-grid input');
    const newItems = {};
    inputs.forEach(inp => {
      const v = parseFloat(inp.value || 0);
      if (Math.abs(v) >= 0.5) newItems[inp.dataset.gid] = v;
    });
    isl.items = newItems;
    saveStateToServer();
  }
  document.getElementById('edit-modal').style.display = 'none';
}

function deleteIsland(idx) {
  ISLANDS.splice(idx, 1);
  saveStateToServer();
}

fetchState();
setInterval(fetchState, 3000);
</script>
</body>
</html>
"""


# =====================================================================
# 7. 本地 HTTP 服务与全局热键守护线程
# =====================================================================
class CopilotHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
        elif self.path == "/api/state":
            self._send_json({"catalog": GOODS_CATALOG, "islands": ISLANDS_STATE})
        else:
            self.send_error(404)

    def do_POST(self):
        global ISLANDS_STATE
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if self.path == "/api/save_islands":
            ISLANDS_STATE = body.get("islands", ISLANDS_STATE)
            save_islands(ISLANDS_STATE)
            self._send_json({"status": "ok"})
        elif self.path == "/api/apply_route":
            res = execute_create_route_macro(body)
            self._send_json(res)
        elif self.path == "/api/scan_ctrl_q":
            scan_ctrl_q_screen()
            self._send_json({"status": "ok"})


def start_hotkey_listener():
    keyboard.add_hotkey("f7", lambda: threading.Thread(target=batch_scan_all_islands, daemon=True).start())
    keyboard.add_hotkey("f8", lambda: threading.Thread(target=scan_ctrl_q_screen, daemon=True).start())
    keyboard.add_hotkey("f9", lambda: threading.Thread(target=run_calibration_wizard, daemon=True).start())
    keyboard.add_hotkey("f10", lambda: threading.Thread(target=dump_ship_cargo_macro, daemon=True).start())
    keyboard.wait()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if run_selftest() else 1)

    print("=" * 68)
    print("⚓ 《纪元1800》全自动贸易指挥中心 (Anno 1800 Trade Copilot) 已启动")
    print("=" * 68)
    print("🌐 本地指挥看板地址: http://127.0.0.1:18000")
    print("-" * 68)
    print("⌨️ 游戏内全局热键：")
    print("  • [F7]  在 Ctrl+Q 界面自动顺着左侧列表依次点击岛屿，全图批量扫描")
    print("  • [F8]  在 Ctrl+Q 界面对当前选中岛屿执行【多页滚轮自动截图 + 合并识别】")
    print("  • [F9]  启动分辨率坐标与截图框校准向导（首次使用按一次即可）")
    print("  • [F10] 一键清空当前选中船只的 6 个货仓残留杂物")
    print("  • [紧急中断] 自动点击期间将鼠标猛甩到屏幕左上角 (0,0) 即可立即终止")
    print("=" * 68)

    threading.Thread(target=start_hotkey_listener, daemon=True).start()
    if "--no-browser" not in sys.argv:
        webbrowser.open("http://127.0.0.1:18000")

    server = HTTPServer(("127.0.0.1", 18000), CopilotHTTPHandler)
    server.serve_forever()
