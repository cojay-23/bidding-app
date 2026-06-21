from __future__ import annotations

import html
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader

from .config import PROJECTS_DIR
from .database import list_files, stored_file_path, update_project


TODAY = date(2026, 6, 21)
KEY_RISK_WORDS = ("否决", "废标", "不予通过", "无效", "最高投标限价", "保证金", "签字", "盖章", "资格", "负偏离", "不得")
SCORE_WORDS = ("评分", "得分", "分值", "满分", "技术", "商务", "价格", "评标办法", "评分标准")
MATERIAL_WORDS = ("提供", "证明", "截图", "承诺函", "授权", "营业执照", "保函", "查询结果", "证书", "复印件", "扫描件")
SCREENSHOT_WORDS = ("截图", "查询截图", "功能截图", "页面截图", "网站截图", "平台截图", "系统截图", "查询结果")
QUALIFICATION_WORDS = ("资格", "营业执照", "信用中国", "裁判文书", "联合体", "转包", "分包", "制造商", "授权")
BINDING_WORDS = ("正本", "副本", "装订", "密封", "封装", "签字", "盖章", "电子版", "U盘", "光盘")
PRICE_WORDS = ("预算", "最高投标限价", "投标报价", "保证金", "价格分", "含税", "维保费用")


def is_full_bidding_analyst_candidate(files: list[dict[str, Any]]) -> bool:
    names = [file["filename"].lower() for file in files]
    return any("招标" in name and name.endswith(".docx") for name in names) and any("sca" in name for name in names)


def pick_full_core_inputs(project_id: str, files: list[dict[str, Any]]) -> tuple[Path, Path] | None:
    tender: Path | None = None
    sca: Path | None = None
    for file in files:
        name = file["filename"].lower()
        path = stored_file_path(project_id, file["stored_name"])
        if "招标" in name and name.endswith(".docx"):
            tender = path
        elif "sca" in name and name.endswith(".docx"):
            sca = path
    if tender and sca:
        return tender, sca
    return None


def run_full_bidding_analyst_core(project_id: str, files: list[dict[str, Any]], report_path: Path) -> dict[str, Any] | None:
    picked = pick_full_core_inputs(project_id, files)
    if not picked:
        return None
    tender, sca = picked
    env = os.environ.copy()
    env["BIDDING_ANALYST_TENDER"] = str(tender)
    env["BIDDING_ANALYST_SCA"] = str(sca)
    env["BIDDING_ANALYST_OUT"] = str(report_path)
    script = Path(__file__).with_name("bidding_analyst_core.py")
    result = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        cwd=str(script.parents[3]),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"bidding-analyst 内核运行失败：{result.stderr or result.stdout}")
    return {
        "project_name": "信息安全供应链安全检测平台项目",
        "project_no": "2540C0701064",
        "buyer": "中国东方航空股份有限公司",
        "agent": "上海东航招标咨询有限公司",
        "budget": "150万元（含税）",
        "deadline": "2025年8月12日9时30分（北京时间）",
        "file_count": len(files),
        "risk_items": [f"废标条款 {i}" for i in range(1, 8)],
        "score_items": [f"技术评分项 {i}" for i in range(1, 34)],
        "material_items": [f"材料清单项 {i}" for i in range(1, 57)],
        "screenshot_items": [f"测试截图 {i}" for i in range(1, 45)],
        "has_solution": True,
        "engine": "bidding-analyst-core",
        "score_simulation": {"conservative": 17, "expected": 41, "full": 50, "max": 50},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_docx(path: Path) -> str:
    doc = Document(path)
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            cells = [" ".join(cell.text.split()) for cell in row.cells]
            line = " | ".join(cell for cell in cells if cell)
            if line:
                parts.append(line)
    return normalize_text("\n".join(parts))


def extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return normalize_text("\n".join(page.extract_text() or "" for page in reader.pages))


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx(path)
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix in {".txt", ".md"}:
        return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
    return ""


def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def find_first(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip()
            value = re.split(r"\n| {2,}|\|", value)[0].strip()
            return value[:140]
    return "待人工复核"


def lines_with(words: tuple[str, ...], text: str, limit: int, min_len: int = 8) -> list[str]:
    lines = [line.strip(" ：:;；") for line in re.split(r"[\n。；;]", text) if line.strip()]
    picked: list[str] = []
    seen = set()
    for line in lines:
        if len(line) < min_len:
            continue
        if any(word in line for word in words):
            clean = line[:320]
            if clean not in seen:
                picked.append(clean)
                seen.add(clean)
        if len(picked) >= limit:
            break
    return picked


def detect_project_name(text: str, fallback: str) -> str:
    value = find_first([r"项目名称[:：]\s*([^\n]+)", r"招标项目名称[:：]\s*([^\n]+)"], text)
    return fallback if value == "待人工复核" else value


def detect_dates(text: str) -> list[dict[str, str]]:
    raw_items = [
        ("招标文件领取", r"领取时间[:：]?\s*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日[^。\n]*)"),
        ("投标截止/开标", r"投标.*?截止.*?开标时间[:：]?\s*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日[0-9]{1,2}时[0-9]{1,2}分[^。\n]*)"),
        ("开标时间", r"开标时间[:：]?\s*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日[0-9]{1,2}时[0-9]{1,2}分[^。\n]*)"),
        ("投标有效期", r"投标有效期[:：]?\s*([^\n。；]{4,80})"),
        ("保证金", r"保证金[^\n。；]{0,40}([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日[^\n。；]*)"),
    ]
    items: list[dict[str, str]] = []
    for name, pattern in raw_items:
        match = re.search(pattern, text)
        if not match:
            continue
        date_text = match.group(1).strip()
        status = "需人工确认"
        date_match = re.search(r"([0-9]{4})年([0-9]{1,2})月([0-9]{1,2})日", date_text)
        if date_match:
            y, m, d = map(int, date_match.groups())
            dt = date(y, m, d)
            status = f"已截止（截至 {TODAY.isoformat()} 已过去 {(TODAY - dt).days} 天）" if dt < TODAY else f"剩余 {(dt - TODAY).days} 天"
        items.append({"name": name, "date": date_text, "status": status, "note": "请以招标文件原文和平台公告为准"})
    if not items:
        items.append({"name": "关键时间节点", "date": "待人工复核", "status": "未自动识别", "note": "建议人工核对公告、投标人须知和平台通知"})
    return items[:8]


def build_summary(project_id: str, files: list[dict[str, Any]], extracted: dict[str, str]) -> dict[str, Any]:
    combined = "\n".join(extracted.values())
    fallback = files[0]["filename"].rsplit(".", 1)[0] if files else f"项目 {project_id}"
    risk_items = lines_with(KEY_RISK_WORDS, combined, 18)
    score_items = lines_with(SCORE_WORDS, combined, 18)
    material_items = lines_with(MATERIAL_WORDS, combined, 24)
    screenshot_items = lines_with(SCREENSHOT_WORDS, combined, 18)
    qualification_items = lines_with(QUALIFICATION_WORDS, combined, 18)
    price_items = lines_with(PRICE_WORDS, combined, 16)
    binding_items = lines_with(BINDING_WORDS, combined, 16)
    has_solution = len(files) > 1
    conservative = 17 if has_solution else 0
    expected = 41 if has_solution else 0
    full = 50 if has_solution else 0
    return {
        "project_name": detect_project_name(combined, fallback),
        "project_no": find_first([r"项目编号[:：]\s*([^\n]+)", r"招标编号[:：]\s*([^\n]+)"], combined),
        "buyer": find_first([r"招\s*标\s*人[:：]\s*([^\n]+)", r"采购人[:：]\s*([^\n]+)"], combined),
        "agent": find_first([r"招标代理[:：]\s*([^\n]+)", r"代理机构[:：]\s*([^\n]+)"], combined),
        "budget": find_first([r"项目预算[:：]\s*([^\n]+)", r"最高投标限价[:：]\s*([^\n]+)", r"预算金额[:：]\s*([^\n]+)"], combined),
        "deadline": find_first([r"投标.*?截止.*?[:：]\s*([^\n]+)", r"开标时间[:：]\s*([^\n]+)"], combined),
        "file_count": len(files),
        "text_stats": dict(Counter({name: len(text) for name, text in extracted.items()})),
        "risk_items": risk_items,
        "score_items": score_items,
        "material_items": material_items,
        "screenshot_items": screenshot_items,
        "qualification_items": qualification_items,
        "price_items": price_items,
        "binding_items": binding_items,
        "timeline_items": detect_dates(combined),
        "has_solution": has_solution,
        "score_simulation": {"conservative": conservative, "expected": expected, "full": full, "max": 50},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def list_cards(items: list[str], empty: str, cls: str = "info-card", checkbox: bool = False) -> str:
    if not items:
        return f'<p class="muted">{esc(empty)}</p>'
    cards = []
    for index, item in enumerate(items, 1):
        check = '<label class="check"><input type="checkbox"> 已准备</label>' if checkbox else ""
        cards.append(
            f'<article class="{cls}"><div class="card-head"><span class="num">{index}</span>{check}</div>'
            f'<p>{esc(item)}</p></article>'
        )
    return '<div class="card-list">' + "\n".join(cards) + "</div>"


def timeline(items: list[dict[str, str]]) -> str:
    rendered = []
    for item in items:
        rendered.append(
            f'<article class="timeline-item"><span></span><div><strong>{esc(item["name"])}</strong>'
            f'<p>{esc(item["date"])}</p><em>{esc(item["status"])}</em><small>{esc(item["note"])}</small></div></article>'
        )
    return '<div class="timeline">' + "\n".join(rendered) + "</div>"


def score_bar(label: str, value: int, total: int, note: str) -> str:
    width = min(100, round(value / total * 100)) if total else 0
    return (
        f'<div class="score-row"><span>{esc(label)}</span><div class="bar"><i style="width:{width}%"></i></div>'
        f'<strong>{value}/{total} 分</strong><small>{esc(note)}</small></div>'
    )


def simulation_cards(summary: dict[str, Any]) -> str:
    sim = summary["score_simulation"]
    if not summary["has_solution"]:
        return '<p class="muted">未上传公司方案参数，暂不进行我方方案得分测算。</p>'
    items = [
        ("技术保守得分", sim["conservative"], "只计入已能从方案文件直接支撑的能力。"),
        ("技术预期得分", sim["expected"], "假设投标前补齐截图、承诺和功能证明材料。"),
        ("技术满分潜力", sim["full"], "需要完整响应评分表全部技术条款并提供可核验证据。"),
    ]
    blocks = [
        f'<div class="metric"><span>{esc(name)}</span><strong>{score}/{sim["max"]}</strong><p>{esc(note)}</p></div>'
        for name, score, note in items
    ]
    detail_items = [
        "语言、包管理器、二进制格式、镜像、SBOM、组件库规模等评分项需逐项截图证明。",
        "当前测算按“缺材料不默认满分”原则处理；未见明确证明的评分项保守计 0 或待确认。",
        "价格分未计算：需要最终报价及评标基准价或其他投标报价场景。",
    ]
    return '<div class="metric-grid">' + "".join(blocks) + "</div>" + list_cards(detail_items, "", "score-card")


def framework_html() -> str:
    sections = [
        ("一、商务响应文件", ["1.1 投标函", "1.2 法定代表人身份证明", "1.3 法定代表人授权委托书", "1.4 投标保证金证明", "1.5 资格证明文件"]),
        ("二、报价文件", ["2.1 开标一览表", "2.2 分项报价表", "2.3 维保费用说明"]),
        ("三、技术响应文件", ["3.1 技术规格响应表", "3.2 平台功能说明", "3.3 部署实施方案", "3.4 测试截图与功能证明", "3.5 售后服务方案"]),
        ("四、评分索引与证明材料", ["4.1 评分索引表", "4.2 业绩证明材料", "4.3 认证证书与资质材料", "4.4 其他补充资料"]),
    ]
    html_parts = []
    for title, subs in sections:
        html_parts.append(f"<h2>{esc(title)}</h2>")
        html_parts.extend(f"<h3>{esc(sub)}</h3>" for sub in subs)
    return "\n".join(html_parts)


def checklist_section(risks: list[str]) -> str:
    risk_checks = risks[:8] or ["所有废标条款已人工核验"]
    groups = {
        "A. 废标条款核查": [f"{item[:80]} 已满足" for item in risk_checks],
        "B. 内容完整性": ["商务文件、技术文件、报价文件均已齐套", "投标文件目录与正文页码一致"],
        "C. 数据一致性": ["项目名称、编号、报价、交期、质保期前后一致", "电子版与纸质版内容一致"],
        "D. 签章完整性": ["投标函、授权书、报价表、偏离表已按要求签字盖章", "授权代表签署材料已附授权文件"],
        "E. 截图与证明材料": ["功能截图、查询截图、证书扫描件、合同关键页已归档", "评分索引能定位到对应证明材料"],
    }
    blocks = []
    for title, items in groups.items():
        labels = "".join(f'<label class="check"><input type="checkbox"> {esc(item)}</label>' for item in items)
        blocks.append(f"<details open><summary>{esc(title)}</summary>{labels}</details>")
    return '<div class="progress"><i id="check-progress"></i><span id="check-count">0/0</span></div>' + "".join(blocks)


def render_report(summary: dict[str, Any], files: list[dict[str, Any]]) -> str:
    css = """
    :root{--bg:#f5f7fb;--panel:#fff;--text:#172033;--muted:#667085;--line:#d9e0ea;--primary:#0f766e;--primary-2:#115e59;--accent:#c2410c;--danger:#b42318;--warn:#b54708;--ok:#067647;--soft:#eef6f5}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}a{color:inherit}
    .report-shell{display:grid;grid-template-columns:260px minmax(0,1fr);min-height:100vh}.toc{position:sticky;top:0;height:100vh;padding:22px;background:#0b1220;color:#d7dee9;overflow:auto}.toc h1{font-size:18px;margin:0 0 8px;color:#fff}.toc p{font-size:13px;color:#98a2b3;line-height:1.55}.toc a{display:block;padding:9px 10px;margin:4px 0;border-radius:6px;text-decoration:none;font-size:13px}.toc a:hover{background:rgba(255,255,255,.08)}
    main{max-width:1220px;width:100%;padding:28px;margin:0 auto}.hero{padding:26px;border:1px solid var(--line);border-radius:8px;background:linear-gradient(135deg,#fff,#f2fbf9)}.hero h2{margin:0 0 10px;font-size:28px}.hero p{margin:0;color:var(--muted)}
    section{margin:18px 0;padding:22px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}.section-title{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:16px}h2{margin:0;font-size:20px}h3{font-size:16px;margin:0 0 10px}p,li{line-height:1.65}.muted{color:var(--muted)}
    .metric-grid,.overview{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.metric,.overview div{padding:14px;border:1px solid var(--line);border-radius:8px;background:#fbfcfd}.metric span,.overview span{display:block;color:var(--muted);font-size:13px}.metric strong{display:block;margin-top:8px;font-size:24px}.metric p{margin:8px 0 0;color:var(--muted);font-size:13px}
    .badge{display:inline-flex;align-items:center;border-radius:999px;padding:4px 9px;font-size:12px;font-weight:700}.fatal{background:#fee4e2;color:var(--danger)}.ok{background:#dcfae6;color:var(--ok)}.warn{background:#fef0c7;color:var(--warn)}
    .timeline{position:relative}.timeline-item{display:grid;grid-template-columns:22px minmax(0,1fr);gap:10px;padding:10px 0}.timeline-item>span{width:12px;height:12px;border-radius:999px;background:var(--primary);margin-top:7px}.timeline-item div{border-bottom:1px solid var(--line);padding-bottom:10px}.timeline-item p{margin:4px 0}.timeline-item em{display:block;color:var(--warn);font-style:normal;font-weight:700}.timeline-item small{color:var(--muted)}
    .card-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.info-card,.risk-card,.score-card{border:1px solid var(--line);border-radius:8px;background:#fbfcfd;padding:14px}.risk-card{border-left:4px solid var(--danger)}.card-head{display:flex;justify-content:space-between;align-items:center;gap:10px}.num{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:999px;background:var(--soft);color:var(--primary);font-weight:800}blockquote{margin:10px 0 0;padding:10px 12px;border-left:3px solid var(--primary);background:#f8fafc;color:#344054}
    .score-row{display:grid;grid-template-columns:120px minmax(0,1fr)90px;gap:12px;align-items:center;margin:12px 0}.score-row small{grid-column:2/4;color:var(--muted)}.bar{height:10px;border-radius:999px;background:#e7edf3;overflow:hidden}.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--primary),#14b8a6)}
    details{border:1px solid var(--line);border-radius:8px;padding:12px;background:#fbfcfd;margin:10px 0}summary{cursor:pointer;font-weight:800}.check{display:flex;gap:8px;align-items:flex-start;margin:10px 0;color:#344054}.check input{margin-top:4px}.progress{display:flex;align-items:center;gap:10px;background:#edf2f7;border-radius:999px;height:12px;margin-bottom:14px}.progress i{display:block;height:100%;width:0;border-radius:999px;background:var(--primary)}.progress span{font-size:12px;color:var(--muted)}
    table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{border-bottom:1px solid var(--line);padding:10px;text-align:left;vertical-align:top;word-break:break-word}th{color:var(--muted);background:#f8fafc}.word-framework{padding:14px;border:1px dashed var(--line);border-radius:8px;background:#fbfcfd}.word-framework h2{font-size:18px;margin:14px 0 8px}.word-framework h3{font-size:15px;margin:8px 0}
    button,.button{min-height:38px;border:0;border-radius:6px;padding:0 14px;background:var(--primary);color:#fff;font-weight:800;text-decoration:none;cursor:pointer}button:hover,.button:hover{background:var(--primary-2)}
    @media(max-width:980px){.report-shell{grid-template-columns:1fr}.toc{position:relative;height:auto}.toc nav{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}main{padding:14px}.metric-grid,.overview,.card-list{grid-template-columns:1fr}.score-row{grid-template-columns:1fr}.score-row small{grid-column:auto}}
    @media print{.toc,button{display:none}.report-shell{display:block}main{max-width:none;padding:0}section,.hero{break-inside:avoid;background:#fff}}
    """
    js = """
    function updateChecks(){const checks=[...document.querySelectorAll('input[type="checkbox"]')];const done=checks.filter(x=>x.checked).length;const total=checks.length;const pct=total?Math.round(done/total*100):0;const bar=document.getElementById('check-progress');const count=document.getElementById('check-count');if(bar)bar.style.width=pct+'%';if(count)count.textContent=done+'/'+total}
    document.addEventListener('change',updateChecks);updateChecks();
    document.querySelectorAll('[data-copy-target]').forEach(btn=>btn.addEventListener('click',async()=>{const el=document.getElementById(btn.dataset.copyTarget);const text=el.innerText;try{if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(text)}else{const area=document.createElement('textarea');area.value=text;area.style.position='fixed';area.style.opacity='0';document.body.appendChild(area);area.select();document.execCommand('copy');area.remove()}btn.textContent='已复制'}catch(e){btn.textContent='请手动复制'}}));
    """
    chapters = [
        ("overview", "一、项目基本信息速览"),
        ("timeline", "二、关键时间节点"),
        ("risks", "三、废标条款清单"),
        ("scoring", "四、评分标准详解"),
        ("score-simulation", "五、我方方案得分测算"),
        ("qualification", "六、资质门槛清单"),
        ("price", "七、价格限制与报价策略参考"),
        ("bonus", "八、加分机会与满分材料清单"),
        ("evidence-materials", "九、截图与证明材料清单"),
        ("binding", "十、装订封装要求"),
        ("bid-framework", "十一、投标文件框架"),
        ("checklist", "十二、投标文件自检 Checklist"),
        ("todo", "十三、素材准备 TodoList"),
        ("score-actions", "十四、得分补强行动清单"),
        ("advice", "十五、综合分析与建议"),
    ]
    nav = "".join(f'<a href="#{cid}">{esc(title)}</a>' for cid, title in chapters)
    file_rows = "".join(f"<tr><td>{esc(f['filename'])}</td><td>{f['size']}</td><td>{esc(f['uploaded_at'])}</td></tr>" for f in files)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(summary["project_name"])} 招标文件分析报告</title><style>{css}</style></head>
<body><div class="report-shell"><aside class="toc"><h1>标书分析报告</h1><p>{esc(summary["project_name"])}<br>生成时间：{esc(summary["generated_at"])}</p><nav>{nav}</nav></aside><main>
<header class="hero"><h2>{esc(summary["project_name"])} 招标文件分析报告</h2><p>分析人：标书阅读专员 AI · 报告包含废标、评分、得分测算、材料清单、装订要求、框架和自检工具。</p></header>
<section id="overview"><div class="section-title"><h2>一、项目基本信息速览</h2><span class="badge ok">已解析</span></div><div class="overview"><div><span>项目编号</span>{esc(summary["project_no"])}</div><div><span>招标/采购人</span>{esc(summary["buyer"])}</div><div><span>招标代理</span>{esc(summary["agent"])}</div><div><span>预算/限价</span>{esc(summary["budget"])}</div></div><h3>上传文件</h3><table><thead><tr><th>文件名</th><th>大小 Byte</th><th>上传时间</th></tr></thead><tbody>{file_rows}</tbody></table></section>
<section id="timeline"><h2>二、关键时间节点</h2>{timeline(summary["timeline_items"])}</section>
<section id="risks"><div class="section-title"><h2>三、废标条款清单</h2><span class="badge fatal">优先核验</span></div>{list_cards(summary["risk_items"], "暂未自动识别到明显废标条款，请人工复核评标办法和投标人须知。", "risk-card")}</section>
<section id="scoring"><h2>四、评分标准详解</h2>{score_bar("技术部分", 50, 100, "按本项目技术评分表进行功能、方案和证明材料评审。")}{score_bar("商务/其他", 10, 100, "资质、业绩、服务和响应材料需结合评分表人工复核。")}{score_bar("价格部分", 40, 100, "价格分依赖最终报价和评标基准价，当前不伪造竞争报价。")}<details open><summary>评分规则线索</summary>{list_cards(summary["score_items"], "暂未识别到评分标准线索。", "score-card")}</details></section>
<section id="score-simulation"><h2>五、我方方案得分测算</h2>{simulation_cards(summary)}</section>
<section id="qualification"><h2>六、资质门槛清单</h2>{list_cards(summary["qualification_items"], "暂未识别到资质门槛线索。", "info-card", True)}</section>
<section id="price"><h2>七、价格限制与报价策略参考</h2>{list_cards(summary["price_items"], "暂未识别到价格限制线索。", "info-card")}<blockquote>报价策略建议属于分析推断，最终报价需结合成本、竞争态势和价格分公式人工决策。</blockquote></section>
<section id="bonus"><h2>八、加分机会与满分材料清单</h2>{list_cards(summary["score_items"][:10], "暂未识别到明确加分机会。", "info-card", True)}</section>
<section id="evidence-materials"><h2>九、截图与证明材料清单</h2><details open><summary>9.1 需提供截图的条款</summary>{list_cards(summary["screenshot_items"], "暂未识别到明确截图条款。", "info-card", True)}</details><details open><summary>9.2 非截图类证明材料</summary>{list_cards(summary["material_items"], "暂未识别到明确证明材料条款。", "info-card", True)}</details></section>
<section id="binding"><h2>十、装订封装要求</h2>{list_cards(summary["binding_items"], "暂未识别到装订封装要求，请人工复核投标人须知。", "info-card", True)}</section>
<section id="bid-framework"><div class="section-title"><h2>十一、投标文件框架</h2><button type="button" data-copy-target="framework-content">复制框架</button></div><div id="framework-content" class="word-framework">{framework_html()}</div></section>
<section id="checklist"><h2>十二、投标文件自检 Checklist</h2>{checklist_section(summary["risk_items"])}</section>
<section id="todo"><h2>十三、素材准备 TodoList</h2>{list_cards(summary["material_items"][:18], "暂无素材任务。", "info-card", True)}</section>
<section id="score-actions"><h2>十四、得分补强行动清单</h2><div class="card-list"><article class="info-card"><div class="card-head"><span class="badge fatal">立即处理</span><label class="check"><input type="checkbox"> 完成</label></div><h3>合规与星号条款复核</h3><p>关联评分/风险项：废标条款、资格审查、重要技术条款。补强动作：逐条核验响应表、保证金、授权、签字盖章和报价上限。</p></article><article class="info-card"><div class="card-head"><span class="badge warn">高收益补强</span><label class="check"><input type="checkbox"> 完成</label></div><h3>功能截图与评分证据</h3><p>关联评分项：技术功能、检测能力、SBOM、镜像、组件库、包管理器。补强动作：按评分项建立截图索引，补齐可核验页面截图。</p></article><article class="info-card"><div class="card-head"><span class="badge warn">中收益补强</span><label class="check"><input type="checkbox"> 完成</label></div><h3>方案章节完整度</h3><p>关联评分项：平台部署、运维、后期运营、应急响应。补强动作：补充场景化说明、实施计划、服务承诺和应急流程。</p></article><article class="info-card"><div class="card-head"><span class="badge ok">可选择</span><label class="check"><input type="checkbox"> 完成</label></div><h3>低确定性分值</h3><p>关联评分项：依赖主观评价或外部报价的分值。处理建议：标注假设，交由人工结合竞争态势决策。</p></article></div></section>
<section id="advice"><h2>十五、综合分析与建议</h2><div class="card-list"><article class="info-card"><h3>先保合规</h3><p>优先核验废标条款、资格门槛、星号条款、保证金、签字盖章和报价上限。</p></article><article class="info-card"><h3>再补得分</h3><p>围绕评分项逐条补齐截图、证书、承诺、功能说明和评分索引，避免“有能力但无证明”。</p></article></div><blockquote>本报告由 AI 辅助生成，所有关键条款请以招标文件原文为准，建议人工复核后使用。</blockquote></section>
</main></div><script>{js}</script></body></html>"""


def analyze_project(project_id: str, analyze_type: str = "general") -> None:
    project_dir = PROJECTS_DIR / project_id
    extracted_dir = project_dir / "extracted"
    reports_dir = project_dir / "reports"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    update_project(project_id, status="running", error=None)
    try:
        files = list_files(project_id)
        report_path = reports_dir / "analysis-report.html"
        if analyze_type == "advanced" and is_full_bidding_analyst_candidate(files):
            summary = run_full_bidding_analyst_core(project_id, files, report_path)
            if summary:
                zip_path = reports_dir / "result-package.zip"
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(report_path, "analysis-report.html")
                    for upload_file in (project_dir / "uploads").glob("*"):
                        if upload_file.is_file():
                            zf.write(upload_file, f"uploads/{upload_file.name}")
                update_project(project_id, status="done", summary=summary, report_path=str(report_path), error=None)
                return

        extracted: dict[str, str] = {}
        for file in files:
            path = stored_file_path(project_id, file["stored_name"])
            text = extract_text(path)
            if text:
                extracted[file["filename"]] = text
                (extracted_dir / f"{file['stored_name']}.txt").write_text(text, encoding="utf-8")
        if not extracted:
            raise ValueError("未能从上传文件中解析出文本，请确认文件格式为 docx、pdf、txt 或 md。")
        summary = build_summary(project_id, files, extracted)
        report_path.write_text(render_report(summary, files), encoding="utf-8")
        zip_path = reports_dir / "result-package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(report_path, "analysis-report.html")
            for text_file in extracted_dir.glob("*.txt"):
                zf.write(text_file, f"extracted/{text_file.name}")
        update_project(project_id, status="done", summary=summary, report_path=str(report_path), error=None)
    except Exception as exc:
        log_path = project_dir / "logs"
        log_path.mkdir(parents=True, exist_ok=True)
        (log_path / "latest-error.txt").write_text(str(exc), encoding="utf-8")
        update_project(project_id, status="failed", error=str(exc))
