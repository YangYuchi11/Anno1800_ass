# -*- coding: utf-8 -*-
"""本地冒烟测试：验证依赖导入 + RapidOCR 离线识别中文供需行。"""
import os

import keyboard  # noqa: F401
import mss  # noqa: F401
import numpy as np
import pyautogui  # noqa: F401
import pyperclip  # noqa: F401
import win32gui  # noqa: F401
from PIL import Image, ImageDraw, ImageFont
from rapidocr_onnxruntime import RapidOCR

print("deps import: OK")

font_path = r"C:\Windows\Fonts\msyh.ttc"
if not os.path.exists(font_path):
    font_path = r"C:\Windows\Fonts\simhei.ttf"
font = ImageFont.truetype(font_path, 36)

img = Image.new("RGB", (760, 240), (20, 26, 36))
draw = ImageDraw.Draw(img)
draw.text((20, 40), "木材  需求 120  供给 86", font=font, fill=(235, 235, 235))
draw.text((20, 120), "啤酒  需求 40  供给 58", font=font, fill=(235, 235, 235))

engine = RapidOCR()
result, _ = engine(np.array(img))

print("OCR results:")
for box, text, score in result or []:
    print(f"  score={score:.3f} text={text!r}")
