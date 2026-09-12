# -*- coding: utf-8 -*-
"""
AI新闻漫画日报 - 微信Bot
- 收到关键词触发Dify工作流
- 用HTML/CSS+Playwright把新闻文字+编辑漫画合成报纸图片
- 每天早上8点自动推送
"""
import asyncio
import contextlib
import json
import os
import random
import re
import sys
import tempfile
import textwrap
import time
from datetime import datetime, timedelta
from io import BytesIO

import httpx
from wechat_bot import Bot, Filter
from newspaper_render import render_newspaper

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ============ 配置 ============
DIFY_API_URL = "https://api.dify.ai/v1/workflows/run"
DIFY_API_KEY = os.environ.get("DIFY_API_KEY", "")
DIFY_TIMEOUT = 180

KEYWORDS = ["新闻", "ai新闻", "AI新闻", "漫画", "日报", "今日", "看看", "来一条"]

SCHEDULE_HOUR = 8
SCHEDULE_MINUTE = 0

IMG_DIR = os.path.join(tempfile.gettempdir(), "ai_news_comic")
os.makedirs(IMG_DIR, exist_ok=True)

# ============ 字体 ============
FONT_HEI = r"C:\Windows\Fonts\simhei.ttf"
FONT_SONG = r"C:\Windows\Fonts\simsun.ttc"
FONT_YAHEI_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_YAHEI = r"C:\Windows\Fonts\msyh.ttc"


def get_font(size, font_type="hei"):
    paths = {
        "hei": FONT_HEI,
        "song": FONT_SONG,
        "yahei_bold": FONT_YAHEI_BOLD,
        "yahei": FONT_YAHEI,
    }
    path = paths.get(font_type, FONT_HEI)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_paper_texture(w, h):
    """生成复古纸张纹理背景（快速版）"""
    # 用小尺寸生成噪声再放大，速度快很多
    scale = 4
    small_w, small_h = w // scale, h // scale
    noise = Image.effect_noise((small_w, small_h), 12).convert('L')
    noise = noise.resize((w, h), Image.BILINEAR)
    base = Image.new('RGB', (w, h), (242, 237, 228))
    # 将噪声叠加到基色上
    import numpy as np
    base_arr = np.array(base).astype(np.int16)
    noise_arr = np.array(noise).astype(np.int16) - 128
    result = np.clip(base_arr + noise_arr[:, :, None] // 3, 0, 255).astype(np.uint8)
    return Image.fromarray(result)


# ============ 文字换行 ============
def wrap_text(text, font, max_width, draw):
    """按像素宽度换行中文文本"""
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph.strip():
            lines.append('')
            continue
        current = ''
        for char in paragraph:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width:
                if current:
                    lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
    return lines


# ============ Dify工作流 ============
async def run_dify_workflow():
    async with httpx.AsyncClient(timeout=DIFY_TIMEOUT, trust_env=False) as client:
        resp = await client.post(
            DIFY_API_URL,
            headers={"Authorization": f"Bearer {DIFY_API_KEY}", "Content-Type": "application/json"},
            json={"inputs": {}, "response_mode": "blocking", "user": f"wechat-bot-{int(time.time())}"},
        )
        data = resp.json()

    if data.get("data", {}).get("status") != "succeeded":
        error = data.get("data", {}).get("error", data.get("message", "未知错误"))
        raise Exception(f"工作流运行失败: {error[:200]}")

    return parse_outputs(data["data"]["outputs"])


def parse_outputs(outputs):
    text = outputs.get("result", "")
    title_match = re.search(r'\[(.+?)\]', text)
    title = title_match.group(1) if title_match else "今日AI新闻"

    # Extract labels from LABELS: JSON
    labels = []
    labels_match = re.search(r'LABELS:\s*(\[.+\])', text, re.DOTALL)
    if labels_match:
        try:
            labels = json.loads(labels_match.group(1))
        except:
            labels = []
    # Remove LABELS line from text
    text = re.sub(r'\n?LABELS:.*', '', text, flags=re.DOTALL)

    # Extract industry
    industry = ""
    industry_match = re.search(r'INDUSTRY:\s*(.+?)(?:\n|$)', text)
    if industry_match:
        industry = industry_match.group(1).strip()
    text = re.sub(r'\n?INDUSTRY:.*', '', text)

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    content_lines = []

    for line in lines:
        if line.startswith("[Image") or line.startswith("["):
            continue
        else:
            content_lines.append(line)

    news_raw = ""
    what_is_it = ""
    impact = ""

    if len(content_lines) >= 3:
        impact = content_lines[-1]
        what_is_it = content_lines[-2]
        news_raw = "\n".join(content_lines[:-2])
    elif len(content_lines) == 2:
        what_is_it = content_lines[0]
        impact = content_lines[1]
    elif len(content_lines) == 1:
        news_raw = content_lines[0]

    image_url = ""
    comic = outputs.get("comic_image", [])
    if comic and isinstance(comic, list) and len(comic) > 0:
        if isinstance(comic[0], dict):
            image_url = comic[0].get("url", "") or comic[0].get("remote_url", "")
        elif isinstance(comic[0], str):
            image_url = comic[0]

    return {
        "title": title,
        "news_raw": news_raw,
        "what_is_it": what_is_it,
        "impact": impact,
        "industry": industry,
        "labels": labels,
        "image_url": image_url,
    }


# ============ 在插图上叠加文字标注 ============
def overlay_labels(image, labels):
    """在插图上叠加文字标注，labels是[{text, position}]的列表"""
    from PIL import ImageDraw as ID
    img = image.copy().convert("RGBA")
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ID.Draw(overlay)

    W, H = img.size
    font = get_font(32, "hei")
    margin = 30
    pad_x, pad_y = 16, 10

    position_map = {
        'top-left': (margin, margin, 'left', 'top'),
        'top-center': (W // 2, margin, 'center', 'top'),
        'top-right': (W - margin, margin, 'right', 'top'),
        'center-left': (margin, H // 2, 'left', 'middle'),
        'center-right': (W - margin, H // 2, 'right', 'middle'),
        'bottom-left': (margin, H - margin, 'left', 'bottom'),
        'bottom-center': (W // 2, H - margin, 'center', 'bottom'),
        'bottom-right': (W - margin, H - margin, 'right', 'bottom'),
    }

    for label in labels:
        text = label.get('text', '')
        pos = label.get('position', 'top-left')
        if not text or pos not in position_map:
            continue

        x, y, anchor_h, anchor_v = position_map[pos]
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        if anchor_h == 'center':
            rx = x - tw // 2 - pad_x
        elif anchor_h == 'right':
            rx = x - tw - pad_x * 2
        else:
            rx = x

        if anchor_v == 'middle':
            ry = y - th // 2 - pad_y
        elif anchor_v == 'bottom':
            ry = y - th - pad_y * 2
        else:
            ry = y

        # 半透明深色背景
        draw.rounded_rectangle(
            [rx, ry, rx + tw + pad_x * 2, ry + th + pad_y * 2],
            radius=8, fill=(26, 26, 26, 210)
        )
        # 文字
        draw.text((rx + pad_x, ry + pad_y - 2), text, fill=(255, 255, 255, 255), font=font)

    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


# ============ 合成报纸风格新闻卡片 ============
def create_news_card(result, comic_image):
    """合成报纸卡片：图片（含报头标注）+ 下方文字内容"""
    W = 1080
    PADDING = 45
    CONTENT_W = W - PADDING * 2

    INK = "#1A1A1A"
    RED_ACCENT = "#B22222"
    GRAY = "#555555"
    PAPER = (242, 237, 228)

    section_font = get_font(28, "hei")
    body_font = get_font(26, "song")
    footer_font = get_font(22, "song")

    tmp = Image.new('RGB', (W, 100), PAPER)
    tmp_draw = ImageDraw.Draw(tmp)

    # 计算高度
    y = 0
    # 图片
    img_w = W
    img_h = int(comic_image.height * img_w / comic_image.width)
    y += img_h
    y += 20

    # 讯息内容
    news_lines = wrap_text(result.get('news_raw', ''), body_font, CONTENT_W - 30, tmp_draw)
    news_h = 50 + len(news_lines) * 38 + 15
    y += news_h + 15

    # 一句话总结
    what_lines = wrap_text(result.get('what_is_it', ''), body_font, CONTENT_W - 30, tmp_draw)
    what_h = 50 + len(what_lines) * 38 + 15
    y += what_h + 15

    # 影响分析
    impact_lines = wrap_text(result.get('impact', ''), body_font, CONTENT_W - 30, tmp_draw)
    impact_h = 50 + len(impact_lines) * 38 + 15
    y += impact_h + 15

    # 行业意义
    industry_text = result.get('industry', '')
    industry_lines = wrap_text(industry_text, body_font, CONTENT_W - 30, tmp_draw) if industry_text else []
    industry_h = (50 + len(industry_lines) * 38 + 15) if industry_lines else 0
    y += industry_h + 20

    # footer
    y += 40

    total_h = y

    # 创建纸张纹理背景
    card = make_paper_texture(W, total_h)
    draw = ImageDraw.Draw(card)

    y = 0

    # === 插图（含AI日报报头和标注）===
    img_resized = comic_image.resize((img_w, img_h), Image.LANCZOS)
    card.paste(img_resized, (0, 0))
    y = img_h + 20

    # === 讯息内容 ===
    draw.rectangle([PADDING, y, W - PADDING, y + news_h], outline=INK, width=1)
    draw.text((PADDING + 15, y + 12), "【讯息内容】", fill=INK, font=section_font)
    ty = y + 52
    for line in news_lines:
        draw.text((PADDING + 15, ty), line, fill=INK, font=body_font)
        ty += 38
    y += news_h + 15

    # === 一句话总结 ===
    draw.rectangle([PADDING, y, W - PADDING, y + what_h], outline=INK, width=1)
    draw.text((PADDING + 15, y + 12), "【一句话总结】", fill=RED_ACCENT, font=section_font)
    ty = y + 52
    for line in what_lines:
        draw.text((PADDING + 15, ty), line, fill=INK, font=body_font)
        ty += 38
    y += what_h + 15

    # === 影响分析 ===
    draw.rectangle([PADDING, y, W - PADDING, y + impact_h], outline=INK, width=1)
    draw.text((PADDING + 15, y + 12), "【影响分析】", fill=RED_ACCENT, font=section_font)
    ty = y + 52
    for line in impact_lines:
        draw.text((PADDING + 15, ty), line, fill=INK, font=body_font)
        ty += 38
    y += impact_h + 15

    # === 行业意义 ===
    if industry_lines:
        draw.rectangle([PADDING, y, W - PADDING, y + industry_h], outline=INK, width=1)
        draw.text((PADDING + 15, y + 12), "【行业意义】", fill=INK, font=section_font)
        ty = y + 52
        for line in industry_lines:
            draw.text((PADDING + 15, ty), line, fill=GRAY, font=body_font)
            ty += 38
        y += industry_h + 20

    # === 底部 ===
    draw.line([PADDING, y, W - PADDING, y], fill=INK, width=1)
    y += 10
    footer = "—— 拥抱AI  智启未来  AI日报 ——"
    bbox = draw.textbbox((0, 0), footer, font=footer_font)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) / 2, y), footer, fill=GRAY, font=footer_font)

    return card


# ============ 发送结果 ============
async def send_news_result(bot, send_text_fn, send_image_fn):
    try:
        await send_text_fn("正在搜集今日AI新闻并生成漫画，约30秒，请稍候...")
        print(f"[{datetime.now()}] 开始调用Dify工作流...", flush=True)

        result = await run_dify_workflow()
        print(f"[{datetime.now()}] Dify完成: {result['title']}", flush=True)

        if not result['image_url']:
            raise Exception("漫画图片生成失败")

        # 下载漫画图片到临时文件
        print(f"[{datetime.now()}] 下载漫画图片...", flush=True)
        comic_path = os.path.join(IMG_DIR, f"comic_{int(time.time())}.png")
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.get(result['image_url'])
            if resp.status_code != 200:
                raise Exception(f"图片下载失败: HTTP {resp.status_code}")
            with open(comic_path, 'wb') as f:
                f.write(resp.content)
        print(f"[{datetime.now()}] 图片下载完成", flush=True)

        # 用HTML/CSS+Playwright合成报纸
        print(f"[{datetime.now()}] 合成AI日报报纸...", flush=True)
        card_path = os.path.join(IMG_DIR, f"news_card_{int(time.time())}.png")
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: render_newspaper(result, comic_path, card_path)
        )
        print(f"[{datetime.now()}] 报纸已生成: {os.path.getsize(card_path)//1024}KB", flush=True)

        # 发送图片
        await send_image_fn(card_path, caption="")

        # 清理临时文件
        for p in [comic_path, card_path]:
            try:
                os.remove(p)
            except:
                pass

        print(f"[{datetime.now()}] 发送完成", flush=True)

    except Exception as e:
        error_msg = f"抱歉，生成失败了：{str(e)[:100]}\n请稍后再试。"
        try:
            await send_text_fn(error_msg)
        except:
            pass
        print(f"Error: {e}", flush=True)
        import traceback
        traceback.print_exc()


# ============ 主程序 ============
def load_bot_config():
    config = {}
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wechat_bot_token.txt")
    if os.path.exists(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    config[key.strip()] = val.strip()
    return config


async def main():
    config = load_bot_config()
    token = config.get("token", "")
    if not token:
        print("错误：未找到bot token，请先运行 wechat_login.py 扫码登录", flush=True)
        return

    bot = Bot(
        token=token,
        account_id=config.get("account_id", ""),
        base_url=config.get("base_url", "https://ilinkai.weixin.qq.com"),
        user_id=config.get("user_id", ""),
        use_current_user=False,
    )

    last_push_date = None

    @bot.on_message(Filter.text())
    async def handle_message(ctx):
        nonlocal last_push_date
        text = ctx.text.strip()
        if not any(kw in text for kw in KEYWORDS):
            return
        print(f"[{datetime.now()}] 收到触发: {text}", flush=True)
        await send_news_result(bot, send_text_fn=ctx.reply, send_image_fn=ctx.reply_image)

    async def schedule_push():
        nonlocal last_push_date
        await asyncio.sleep(10)
        print(f"[{datetime.now()}] 定时任务启动，每天{SCHEDULE_HOUR}:{SCHEDULE_MINUTE:02d}推送", flush=True)
        while True:
            now = datetime.now()
            target = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_s = (target - now).total_seconds()
            print(f"[{datetime.now()}] 下次推送: {target.strftime('%m-%d %H:%M')}，等待{wait_s/3600:.1f}h", flush=True)
            await asyncio.sleep(wait_s)

            today = target.date()
            if last_push_date != today:
                print(f"[{datetime.now()}] 开始定时推送...", flush=True)
                try:
                    owner_id = bot.owner_user_id
                    if owner_id:
                        await send_news_result(
                            bot,
                            send_text_fn=lambda t: bot.send_text(to=owner_id, text=t),
                            send_image_fn=lambda p, caption="": bot.send_image(to=owner_id, file_path=p, caption=caption),
                        )
                        last_push_date = today
                except Exception as e:
                    print(f"定时推送失败: {e}", flush=True)

    schedule_task = asyncio.create_task(schedule_push())

    print("=" * 50, flush=True)
    print("AI新闻四宫格漫画日报 - 微信Bot已启动", flush=True)
    print(f"Bot账号: {bot.account_id}", flush=True)
    print(f"定时推送: 每天{SCHEDULE_HOUR}:{SCHEDULE_MINUTE:02d}", flush=True)
    print(f"关键词: {', '.join(KEYWORDS)}", flush=True)
    print("=" * 50, flush=True)

    try:
        await bot.run_async()
    finally:
        schedule_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await schedule_task


if __name__ == "__main__":
    asyncio.run(main())
