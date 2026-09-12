# -*- coding: utf-8 -*-
"""HTML/CSS newspaper rendering using Playwright - 3-column layout"""
import os
import base64
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

def image_to_data_url(path):
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    if ext == 'jpg': ext = 'jpeg'
    return f"data:image/{ext};base64,{data}"

def format_impact(impact):
    """Parse impact text into HTML with bullet points for two perspectives."""
    # Try splitting by labels (handle both \n separated and same-line)
    pattern = r'(对普通人|普通用户)[：:]\s*(.+?)\s*(?:对AI产品经理|AI产品经理)[：:]\s*(.+)'
    m = re.search(pattern, impact, re.DOTALL)
    if m:
        p1_text = m.group(2).strip().rstrip('。') + '。'
        p2_text = m.group(3).strip().rstrip('。') + '。'
        return f'''<div class="impact-item"><span class="bullet">&#9679;</span><strong>对普通人：</strong>{p1_text}</div>
<div class="impact-item"><span class="bullet">&#9679;</span><strong>对AI产品经理：</strong>{p2_text}</div>'''
    # Fallback: split by newlines
    lines = [l.strip() for l in impact.split('\n') if l.strip()]
    return '<br>'.join(lines)

def render_newspaper(result, comic_path, output_path, width=900):
    """Render AI日报 newspaper card to PNG using Playwright."""
    
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    date_str = f"{now.year}年{now.month}月{now.day}日"
    weekday = weekdays[now.weekday()]
    
    title = result.get('title', '今日AI新闻')
    news_raw = result.get('news_raw', '')
    what_is_it = result.get('what_is_it', '')
    impact = result.get('impact', '')
    industry = result.get('industry', '')
    
    impact_html = format_impact(impact)
    
    # Extract source if present in news_raw
    source_html = ''
    source_match = re.search(r'[。\n]\s*来源[：:](.+?)(?:\n|$)', news_raw)
    if not source_match:
        source_match = re.search(r'来源[：:](.+?)(?:\n|$)', news_raw)
    if source_match:
        source_text = source_match.group(1).strip()
        news_raw = news_raw[:source_match.start()].rstrip('。\n') + '。'
        source_html = f'<div class="source">&#9998; 来源：{source_text}</div>'
    
    img_url = image_to_data_url(comic_path)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700;900&family=Noto+Sans+SC:wght@400;700;900&display=swap');
  
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  
  body {{
    width: {width}px;
    background: #ede6d6;
    font-family: 'Noto Serif SC', 'SimSun', serif;
    color: #1a1a1a;
    padding: 28px 32px 24px;
    background-image: 
      radial-gradient(ellipse at 30% 20%, rgba(139,119,82,0.08) 0%, transparent 50%),
      radial-gradient(ellipse at 70% 80%, rgba(139,119,82,0.06) 0%, transparent 40%);
  }}
  
  body::before {{
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 999;
  }}
  
  /* === Masthead === */
  .masthead {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 2px 0 6px;
  }}
  .masthead-left {{
    font-size: 14px;
    line-height: 1.6;
    color: #222;
    font-family: 'Noto Serif SC', serif;
  }}
  .masthead-center {{
    text-align: center;
    flex: 1;
  }}
  .masthead-center h1 {{
    font-family: 'Noto Serif SC', 'SimSun', serif;
    font-size: 72px;
    font-weight: 900;
    letter-spacing: 16px;
    padding-left: 16px;
    line-height: 1;
    color: #111;
  }}
  .masthead-right {{
    font-size: 15px;
    line-height: 1.5;
    text-align: right;
    color: #222;
    font-family: 'Noto Serif SC', serif;
    font-weight: 600;
  }}
  .masthead-right .underline {{
    display: inline-block;
    border-bottom: 1.5px solid #333;
    padding-bottom: 1px;
  }}
  
  .thick-line {{
    border-top: 4px solid #111;
    height: 0;
    margin: 4px 0 2px;
  }}
  .thin-line {{
    border-top: 1.5px solid #111;
    height: 0;
    margin-bottom: 10px;
  }}
  
  /* === Headline === */
  .headline {{
    text-align: center;
    font-family: 'Noto Sans SC', 'SimHei', sans-serif;
    font-size: 30px;
    font-weight: 900;
    padding: 8px 0 10px;
    line-height: 1.35;
    color: #111;
  }}
  
  /* === Comic banner === */
  .comic-wrap {{
    border: 2px solid #1a1a1a;
    padding: 3px;
    background: #fff;
    margin-bottom: 12px;
  }}
  .comic-wrap img {{
    width: 100%;
    display: block;
  }}
  
  /* === Three columns === */
  .columns {{
    display: flex;
    gap: 0;
    border: 1.5px solid #1a1a1a;
  }}
  .col {{
    padding: 12px 14px;
  }}
  .col-left {{
    flex: 1.15;
    border-right: 1.5px solid #1a1a1a;
  }}
  .col-mid {{
    flex: 1;
    border-right: 1.5px solid #1a1a1a;
  }}
  .col-right {{
    flex: 0.95;
  }}
  
  .section-title {{
    font-family: 'Noto Sans SC', 'SimHei', sans-serif;
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 7px;
    padding-bottom: 4px;
    border-bottom: 2px solid #1a1a1a;
    display: inline-block;
  }}
  .section-body {{
    font-size: 14px;
    line-height: 1.75;
    color: #1a1a1a;
    text-align: justify;
  }}
  .section-body + .section-title {{
    margin-top: 14px;
  }}
  
  .impact-item {{
    font-size: 13.5px;
    line-height: 1.7;
    margin-bottom: 8px;
    text-align: justify;
  }}
  .impact-item:last-child {{ margin-bottom: 0; }}
  .impact-item .bullet {{
    color: #1a1a1a;
    margin-right: 3px;
  }}
  
  .source {{
    font-size: 11.5px;
    color: #777;
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px dashed #bbb;
    line-height: 1.5;
  }}
  
  .col-right .section-body {{
    color: #333;
    font-size: 13.5px;
  }}
  
  /* Footer */
  .footer {{
    text-align: center;
    font-size: 11px;
    color: #999;
    padding-top: 8px;
    letter-spacing: 2px;
  }}
</style>
</head>
<body>

<!-- Masthead -->
<div class="masthead">
  <div class="masthead-left">{date_str}<br>{weekday}</div>
  <div class="masthead-center"><h1>AI日报</h1></div>
  <div class="masthead-right">
    <span class="underline">洞察AI前沿</span><br>
    <span class="underline">把握智能未来</span>
  </div>
</div>

<div class="thick-line"></div>
<div class="thin-line"></div>

<!-- Headline -->
<div class="headline">{title}</div>

<!-- Comic banner -->
<div class="comic-wrap">
  <img src="{img_url}" alt="comic">
</div>

<!-- Three columns -->
<div class="columns">
  <div class="col col-left">
    <div class="section-title">【讯息内容】</div>
    <div class="section-body">{news_raw}</div>
    {source_html}
  </div>
  <div class="col col-mid">
    <div class="section-title">【一句话总结】</div>
    <div class="section-body">{what_is_it}</div>
    
    <div class="section-title">【影响分析】</div>
    {impact_html}
  </div>
  <div class="col col-right">
    <div class="section-title">【行业意义】</div>
    <div class="section-body">{industry}</div>
  </div>
</div>

<div class="footer">—— 拥抱AI · 智启未来 · AI日报 ——</div>

</body>
</html>"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 800})
        page.set_content(html, wait_until='networkidle')
        page.wait_for_timeout(2000)
        page.screenshot(path=output_path, full_page=True)
        browser.close()
    
    return output_path


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    result = {
        "title": "中国开源大模型生态全球领跑，每10次下载6次来自中国",
        "news_raw": '21世纪经济报道深度分析指出，国产开源大模型已成长为全球人工智能开源生态的核心供给方。行业统计显示，当前全球每10次大模型下载中，就有6次来自中国研发的模型，我国开源模型累计下载量已突破100亿次，居全球首位。以月之暗面Kimi K3为代表的2.8万亿参数开源模型正在重构全球AI开放秩序。来源：硅谷推翻\u201c闭源安全叙事\u201d，2.8万亿参数中国大模型重构AI开放秩序 - 今日头条',
        "what_is_it": "中国开源大模型累计下载量突破100亿次，占据全球60%下载份额，从单点技术突破进入生态整体繁荣新阶段。",
        "impact": '对普通人：开源模型的繁荣意味着更多免费、可定制的AI工具可供选择，用户不再局限于少数闭源平台；企业和个人开发者可以基于开源模型打造更贴合本土需求的应用。\n对AI产品经理：开源生态成熟降低了AI产品的技术门槛和成本，产品经理可以更多关注场景创新和用户体验而非底层模型能力；但同时也意味着模型能力差异化缩小，产品竞争将更多转向数据、场景和运营。',
        "industry": '这标志着全球AI竞争格局正在从\u201c美国闭源领先\u201d向\u201c中美双轨并行\u201d演变，开源路线正在成为中国AI产业实现弯道超车的核心路径，AI主权和产业自主可控能力显著提升。',
    }
    
    comic = r"D:\dify-ai-news-workflow\test_pure_cartoon.png"
    out = r"D:\dify-ai-news-workflow\test_3col.png"
    render_newspaper(result, comic, out)
    print(f"Saved: {out}, {os.path.getsize(out)//1024}KB")
