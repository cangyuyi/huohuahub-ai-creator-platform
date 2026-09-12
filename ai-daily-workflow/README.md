# AI 日报工作流

> 每日自动搜集 AI 新闻 → AI 主编筛选解读 → 生成《经济学人》风格编辑漫画 → 复古报纸三栏排版 → 微信个人 Bot 推送

## 架构

### Dify 云版工作流（8 节点）

1. **定时触发器** — 每天 8:00 AM (Asia/Shanghai)
2. **Google 搜索** — `AI 人工智能 大模型 最新新闻 今天`, lang=zh, country=cn
3. **AI 新闻主编** (deepseek-chat, temp=0.5)
   - 按影响力 40% / 稀缺性 20% / 趋势 20% / 传播 20% 评分筛选
   - 输出：title, news_raw, what_is_it, impact, industry, story_visual, labels
4. **解析新闻 JSON** — Python 代码节点
5. **漫画导演** (deepseek-chat, temp=0.3)
   - story_visual → 英文图片 prompt
   - 横向构图，The Economist / NYT / FT editorial cartoon 风格
6. **新闻漫画** (通义千问 qwen-image-2.0-pro, 1280×720)
7. **整理图片与文字** — 代码节点
8. **结束**

### 微信 Bot（Python）

- 框架：wechat-ilink-bot（微信官方 iLink Bot API）
- 触发：关键词（新闻/AI新闻/漫画/日报等）+ 每天 8:00 定时推送
- 排版：HTML/CSS + Playwright 渲染为 PNG
  - 报头：日期（左）、AI日报（中）、标语（右）
  - 横向通栏编辑漫画
  - 三栏：讯息内容 | 一句话总结+影响分析 | 行业意义

## 文件说明

| 文件 | 说明 |
|------|------|
| `ai_news_bot.py` | Bot 主程序（Dify 调用 + HTML 排版 + 微信收发） |
| `newspaper_render.py` | HTML/CSS 报纸排版 + Playwright 截图 |
| `wechat_login.py` | 扫码登录获取 token |
| `test_single.py` | Dify 工作流 API 测试 |
| `workflow.yaml` | Dify 工作流配置（早期版本，已过时） |
| `启动Bot.bat` / `扫码登录.bat` | 双击启动 |
| `sample_output.png` | 输出样例 |

## 快速开始

### 1. 安装依赖

```bash
pip install httpx playwright wechat-ilink-bot Pillow qrcode numpy
playwright install chromium
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 DIFY_API_KEY
```

### 3. 微信 Bot 登录

```bash
python wechat_login.py
# 用微信扫码确认，自动生成 wechat_bot_token.txt
```

### 4. 启动 Bot

```bash
python ai_news_bot.py
```

## 迭代记录

### V1（早期版本）
- 四宫格漫画日报，workflow.yaml 为该版本配置
- 问题：四宫格信息量分散，漫画风格不统一

### V2（2026-08-23 重构）
- 重构为双 LLM 节点（主编 + 导演）
- 横向编辑漫画（The Economist 风格），替代四宫格
- HTML 三栏排版，Playwright 渲染
- 复古报纸纹理背景

## 踩坑记录

- **HTTP 节点 JSON 转义**：Dify HTTP 节点 body 模板替换会破坏含换行符的 JSON（返回 400），用 Code 节点 Python `json.dumps()` 预序列化解决
- **Playwright 中文字体**：Windows 下需指定系统字体路径（simhei.ttf / msyh.ttc），否则中文渲染为方框
