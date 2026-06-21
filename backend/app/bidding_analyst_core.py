from __future__ import annotations

import os
from datetime import date, datetime
from html import escape
from pathlib import Path

from docx import Document


BASE = Path("/Users/zhangwj/Documents/Codex/2026-06-21/b")
TENDER = Path(os.environ.get("BIDDING_ANALYST_TENDER", "/Users/zhangwj/Downloads/20250729_招标文件_信息安全供应链安全检测平台项目（发售稿）.docx"))
SCA = Path(os.environ.get("BIDDING_ANALYST_SCA", "/Users/zhangwj/Downloads/SCA.docx"))
OUT = Path(os.environ.get("BIDDING_ANALYST_OUT", str(BASE / "outputs" / "信息安全供应链安全检测平台项目_标书分析报告_2026-06-21.html")))


def cell_text(cell) -> str:
    return " ".join(cell.text.split())


def table_rows(doc: Document, index: int) -> list[list[str]]:
    return [[cell_text(c) for c in row.cells] for row in doc.tables[index].rows]


tender_doc = Document(TENDER)
sca_doc = Document(SCA)
conformity_rows = table_rows(tender_doc, 70)[1:]
business_rows = table_rows(tender_doc, 71)[1:]
technical_rows = table_rows(tender_doc, 72)[1:]
sca_rows = table_rows(sca_doc, 0)[1:]

test_screenshot_rows = []
for i in range(5, 49):
    rows = table_rows(tender_doc, i)
    item = {"index": i - 4, "purpose": "", "steps": "", "expected": "", "location": "第三章 货物和服务需求 / 测试用例"}
    for row in rows:
        if not row:
            continue
        key = row[0]
        val = row[1] if len(row) > 1 else ""
        if "测试目的" in key:
            item["purpose"] = val
        elif "测试步骤" in key:
            item["steps"] = val
        elif "测试结果" in key:
            item["expected"] = val
    if item["purpose"]:
        test_screenshot_rows.append(item)


CHAPTER_PAGES = {
    "第一章 投标邀请书": "目录第2页",
    "第二章 投标人须知及前附表": "目录第5页",
    "第三章 货物和服务需求": "目录第22页",
    "第四章 合同条款及合同附件": "目录第27页",
    "第五章 投标文件格式": "目录第42页",
    "第六章 评标办法": "目录第62页",
}


score_assessment = {
    1: (1, 1, "SCA 明确覆盖加粗核心语言，但未覆盖 R、Clojure、Lua、elixir、Dart 等完整清单。"),
    2: (0, 1, "SCA 覆盖 Maven/Gradle/pip/npm/Yarn/Composer/gomod 等核心项，但未见 distutils、setuptools、pnpm、Bower。"),
    3: (0, 1, "未见“不少于15种主流特征文件”的逐项证明。"),
    4: (0, 1, "SCA 有组件信息和 SBOM 描述，但未直接写明“开源代码溯源分析”。"),
    5: (1, 1, "SCA 明确支持识别组件是否被篡改，并支持 SBOM 篡改验证。"),
    6: (1, 1, "SCA 明确支持组件/文件依赖树、引用路径、间接组件层级路径。"),
    7: (1, 1, "SCA 明确支持恶意组件、供应链投毒风险扫描。"),
    8: (1, 1, "SCA 明确支持许可证识别、许可证兼容性和许可冲突分析。"),
    9: (0, 1, "未见文件粒度哈希匹配及指定语言范围的证明。"),
    10: (0, 1, "SCA 覆盖大量二进制格式，但未完整覆盖评分表列明的全部格式，如 ipa、ear、txz、zst、nupkg、Macho 等。"),
    11: (0, 1, "SCA 覆盖 rpm/deb/dmg/pkg/msi/cab 等，未见 NSIS、install4j、InnoSetup、vib 等完整证明。"),
    12: (0, 1, "SCA 覆盖 elf/PE、jar/apk/aar 等，未见 dylib、ear、Go 无扩展二进制、Dex、IPA 等完整证明。"),
    13: (0, 1, "SCA 覆盖 ext2/ext4/squashfs/vhd 等，未完整覆盖 QCOW2、NTFS、VDI、VMDK、VHDX、WIM 等。"),
    14: (0, 1, "未见密钥、设备敏感信息、个人身份信息扫描能力证明。"),
    15: (0, 1, "SCA 覆盖部分固件格式，但未见 Android Sparse、xcd、UEFI 等完整证明。"),
    16: (0, 1, "SCA 提到镜像扫描和分层信息，未见 manifest、Docker History、镜像ID等评分要求逐项证明。"),
    17: (0, 1, "未见镜像文件权限、大小、链接目标、MD5、存放路径等逐项展示证明。"),
    18: (1, 1, "SCA 明确提到镜像分层信息，建议用截图坐实基础层/指令层/空层级展示。"),
    19: (0, 1, "SCA 有 SBOM 生成/解析，但未完整覆盖 DSDX、SWID、Excel 上传扫描等评分清单。"),
    20: (1, 1, "SCA 明确支持导出 CycloneDX、SPDX、SWID 等 SBOM 格式。"),
    21: (1, 1, "SCA 明确支持组件审计和误报处理，可支撑 SBOM 资产审计。"),
    22: (0, 0, "SCA 中组件版本数 9700w+、许可证近2000种，低于评分表 1亿、3000 的满分阈值；漏洞可达分析等指标未见。"),
    23: (0, 1, "SCA 仅明确 CVE/CNVD/CNNVD/CWE 信息，未完整覆盖 NVD、GitHub 等加粗来源。"),
    24: (1, 1, "SCA 明确支持离线和在线更新数据库。"),
    25: (0, 1, "未见每月至少一次更新、紧急/高危/投毒情报12小时内更新的 SLA 承诺。"),
    26: (0, 1, "SCA 覆盖 Nexus、Artifactory、云效，但未见 coding、蓝鲸制品库、简单云制品库。"),
    27: (1, 1, "SCA 明确支持组件安全版本基线管理。"),
    28: (1, 1, "SCA 明确支持黑白名单、许可证风险等级、自定义策略等管理能力。"),
    29: (1, 1, "SCA 明确支持自定义质量门禁策略和风险组件扣分策略。"),
    30: (1, 1, "SCA 明确支持手动和自动数据备份。"),
    31: (0, 1, "SCA 仅写明自定义登录页、报告 LOGO 和组织架构信息，未完整覆盖评分表的全部界面配置项。"),
    32: (4, 8, "SCA 功能覆盖较多，但尚不是完整平台能力介绍方案，缺少场景化说明和界面截图。"),
    33: (0, 3, "SCA 未提供平台部署、运维、后期运营和应急响应完整方案。"),
}


def quote(text: str) -> str:
    return f"<blockquote>{escape(text)}</blockquote>"


def badge(text: str, cls: str = "") -> str:
    return f'<span class="badge {cls}">{escape(text)}</span>'


def checkbox(label: str) -> str:
    return f'<label class="check"><input type="checkbox"> <span>{escape(label)}</span></label>'


def row(cells: list[str], tag: str = "td") -> str:
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


def render_table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    head = row([escape(h) for h in headers], "th")
    body = "\n".join(row(r) for r in rows)
    return f'<div class="table-wrap"><table class="{cls}"><thead>{head}</thead><tbody>{body}</tbody></table></div>'


def render_technical_cards(items: list[dict[str, str]]) -> str:
    cards = []
    for item in items:
        cards.append(
            f"""
            <article class="score-detail-card">
              <header>
                <span class="index-pill">{escape(item["index"])}</span>
                <h3>{escape(item["name"])}</h3>
                <strong>{escape(item["full"])} 分</strong>
              </header>
              <div class="compact-meta">
                <div><span>测算</span><strong>{escape(item["score"])}</strong></div>
                <div><span>当前失分</span><strong>{escape(item["loss"])}</strong></div>
                <div><span>置信度</span>{badge(item["confidence"], "soft")}</div>
              </div>
              <p><b>我方响应依据：</b>{escape(item["basis"])}</p>
              <details>
                <summary>评分规则原文</summary>
                {quote(item["rule"])}
              </details>
              <p><b>补强建议：</b>{escape(item["advice"])}</p>
            </article>
            """
        )
    return '<div class="detail-list">' + "\n".join(cards) + "</div>"


def render_screenshot_cards(items: list[dict[str, str]]) -> str:
    cards = []
    for item in items:
        cards.append(
            f"""
            <article class="evidence-card">
              <header>
                <span class="index-pill">{escape(str(item["index"]))}</span>
                <h3>测试截图</h3>
                {badge("高优先级", "high")}
              </header>
              <p><b>招标文件位置：</b>第三章 货物和服务需求 / 测试用例，目录第22页起</p>
              <p><b>截图应体现：</b>{escape(item["steps"])}</p>
              <details open>
                <summary>原文/测试目的</summary>
                {quote(item["purpose"])}
              </details>
              <div class="card-foot">
                <span>建议放置：技术响应文件 / 产品功能截图与测试截图</span>
                {checkbox("已准备")}
              </div>
            </article>
            """
        )
    return '<div class="evidence-list">' + "\n".join(cards) + "</div>"


def status_for_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = date(2026, 6, 21)
    if dt < today:
        return f"已截止（截至 2026-06-21 已过去 {(today - dt).days} 天）"
    return f"剩余 {(dt - today).days} 天"


risks = [
    {
        "title": "★重要技术条款负偏离",
        "loc": "第三章 货物和服务需求 / 第六章 符合性评审，目录第22页、第62页",
        "quote": "本技术规格书中，在条款前面打上“★”号为重要条款，投标人的投标内容和提供的产品应满足或优于该重要条款。若投标人的投标文件中对招标文件中标注“★”的重要条款存在负偏离的，将作否决投标处理；对未标注“★”的一般技术要求存在10处（含）以上负偏离的，将视作不符合技术要求，并不予通过初步评审。",
        "req": "逐条响应所有 ★ 技术条款；一般技术条款负偏离必须控制在 10 处以下，建议按“无偏离/正偏离”组织。",
        "level": "致命",
    },
    {
        "title": "未提交或保证金不合规",
        "loc": "第二章 14.1、14.3、14.4 / 第六章 4.5，目录第5页、第62页",
        "quote": "凡没有根据本须知第14.1、14.3条的规定提交投标保证金的投标，视为非响应性投标，其投标将被否决。",
        "req": "投标截止前到账或随投标文件递交合规保函；金额人民币 20,000.00 元。",
        "level": "致命",
    },
    {
        "title": "报价超过最高限价或维保比例超限",
        "loc": "第二章前附表 11.9 / 第六章 4.5，目录第5页、第62页",
        "quote": "最高投标限价：本次招标设置最高投标限价，限价金额为1,500,000.00元（含税），保修期满后维保费用的比例不超过本次投标价的8%。超过最高投标限价的将作否决投标处理。",
        "req": "含税投标总价不得超过 150 万元；保修期满后维保费用比例不得超过本次投标价 8%。",
        "level": "致命",
    },
    {
        "title": "签章/授权不完整",
        "loc": "第二章 16.3.3 / 第六章 4.5，目录第5页、第62页",
        "quote": "投标文件未经投标人盖章和法定代表人或其授权代表签名或盖章，或签字人无法定代表人的有效授权书；",
        "req": "封面、投标书、偏离表、授权书等需按格式签字盖章；授权代表签署时必须附授权书。",
        "level": "致命",
    },
    {
        "title": "资格证明文件缺失或不满足资格要求",
        "loc": "第一章资格要求 / 第二章13 / 第六章4.5，目录第2页、第5页、第62页",
        "quote": "未按招标文件第二章“投标人须知”第13条规定提交资格证明文件，或资格证明文件证明投标人不满足第一章“投标邀请书”规定的合格投标人的资格要求的；",
        "req": "营业执照、制造商专项授权、信用/裁判文书查询材料、财务/税收/社保证明等必须齐全。",
        "level": "致命",
    },
    {
        "title": "IP/账户异常一致",
        "loc": "第一章资格要求 / 第二章前附表43，目录第2页、第5页",
        "quote": "递交文件的投标人之间在本项目过程中登陆，报名、下载/递交招标文件、开标解密等任何一个环节存在IP地址异常一致的，或者支付平台服务费、保证金等付款行为的银行账户一致的，不得通过符合性审查，且招标人有权对投标人涉嫌违规的这些行为按法律法规进一步审查、追究责任。",
        "req": "报名、下载、保证金支付、递交、解密等环节避免与其他投标人共用异常 IP 或账户。",
        "level": "致命",
    },
    {
        "title": "备选方案或附加条件报价",
        "loc": "第二章前附表11.5、11.6，目录第5页",
        "quote": "备选方案：不允许投标人提交备选方案，否则其投标文件将被否决。报价的附加条件：不接受附加条件的报价。",
        "req": "只提交一个明确报价；不得附带报价生效条件、替代方案或保留条款。",
        "level": "严重",
    },
]

star_requirements = [
    "投标方提供的软硬一体化设备，需支持信创cpu、操作系统和数据库；投标方提供两台一软硬体化设备，单台设备如下配置：CPU≥64核、内存≥128G、存储≥2T",
    "产品后续可根据业务增长的需要对设备进行扩容以达到更高的业务处理性能。后续硬件采购单价不得超过本期相应性能对应的硬件采购单价",
    "支持分析识别项目中不兼容的特定许可证和条款，管理此冲突并降低许可证侵权的风险",
    "支持GitLab、SVN进行集成，对相关代码仓库的开源组件风险进行检测",
    "支持devops、GitLab CI、Jenkins、Coding流水线集成，通过插件或pipeline或Shell脚本方式精确匹配或正则表达式匹配多个检测目标，自定义解析深度，结合构建时自定义定制的扫描基线，对于超出质量红线的目标进行实时的阻断。",
    "支持与AD/LDAP单点登录平台对接",
    "可根据扫描的项目形成台账，支持项目级管理能力，包括但不限于项目的基本操作：添加项目、编辑项目、删除项目、查看项目详情等，可编辑配置项目的基本信息、项目负责人、管理项目成员等信息",
    "支持自定义添加许可证黑白名单，并在集成部署模块配置许可证黑白名单的门禁质量规则",
    "支持每条扫描记录都有独立且唯一的检测标识",
    "支持生成Word、PDF、Excel格式分析报告，报告内容包括数据统计、开源组件信息、漏洞信息、组件来源、建议版本、修复建议、影响分",
    "支持全量的API接口开放，系统的所有功能都可够通过API 调用的方式实现，便于与其它系统的集成",
]

non_screenshot_materials = [
    ("资格", "营业执照", "第二章前附表9.2、13.2", "营业执照复印件 / 营业执照正本扫描件", "资格证明文件", "高"),
    ("资格", "制造商专项授权", "第一章二、第二章13.2、第五章格式十四", "投标人为代理商的，须提供所投产品制造商出具的针对本项目的专项授权。", "资格证明文件", "高"),
    ("资格", "信用中国信用报告", "第二章前附表9.2、13.2", "投标截止时间前7天内投标人的“信用中国”网站查询的信用报告打印件。", "资格证明文件", "高"),
    ("资格", "裁判文书网查询截图", "第二章前附表9.2、13.2", "中国裁判文书网查询投标人及其法定代表人行贿犯罪结果页面截图文件。", "资格证明文件", "高"),
    ("资格", "审计报告", "第二章前附表9.2", "投标人2022年-2024年经第三方机构出具的审计报告。", "资格证明文件", "中"),
    ("资格", "纳税证明", "第二章前附表9.2", "投标截止日期之前12个月内任意3个月依法缴纳税收的证明。", "资格证明文件", "中"),
    ("资格", "社保证明", "第二章前附表9.2", "投标截止日期之前36个月完整的依法缴纳社保证明，须体现缴纳社保人数和金额。", "资格证明文件", "中"),
    ("商务评分", "项目案例合同复印件", "第六章商务评分", "每具备一个投标产品在国内应用案例得1分，合同金额不低于80万元。", "商务评分证明", "高"),
    ("商务评分", "项目经理证明材料", "第六章商务评分", "本科、PMP、CISP、两个安全项目管理经验证明、近6个月社保。", "商务评分证明", "高"),
    ("签章", "法定代表人授权书/证明书", "第五章格式十", "授权书必须盖章，法定代表人和被授权人均须签字。", "授权与签章文件", "高"),
    ("报价", "投标分项报价表", "第五章格式六", "填写不含税、税率、含税单价/合价、保修期满后维保费用比例、保修期。", "报价文件", "高"),
    ("合同", "合同条款响应/偏离表", "第五章格式十八", "无差异说明表示完全响应；不得中标后对合同条款提出额外修改变动。", "合同响应文件", "高"),
]

today = date(2026, 6, 21)
deadline = date(2025, 8, 12)

tech_conservative = sum(v[0] for v in score_assessment.values())
tech_expected = sum(v[1] for v in score_assessment.values())
tech_full = 50
business_conservative = 0
business_expected = 2
business_full = 10
non_price_conservative = tech_conservative + business_conservative
non_price_expected = tech_expected + business_expected
non_price_full = tech_full + business_full

technical_detail_rows = []
technical_detail_items = []
for r in technical_rows:
    idx = int(r[0])
    full = float(r[3])
    cons, exp, basis = score_assessment[idx]
    loss = full - cons
    conf = "已核验" if cons == full and full <= 1 else "部分核验" if cons > 0 else "待确认"
    if idx in (32, 33):
        conf = "主观估算"
    advice = "补齐功能截图、参数表、产品手册或方案章节；未覆盖项需确认产品真实能力。"
    technical_detail_items.append(
        {
            "index": r[0],
            "name": r[1],
            "full": r[3],
            "rule": r[2],
            "basis": basis,
            "score": f"{cons:g} / {exp:g} / {full:g}",
            "loss": f"{loss:g}",
            "confidence": conf,
            "advice": advice,
        }
    )
    technical_detail_rows.append(
        [
            escape(r[0]),
            escape(r[1]),
            escape(r[3]),
            quote(r[2]),
            escape(basis),
            f"{cons:g} / {exp:g} / {full:g}",
            f"{loss:g}",
            badge(conf, "soft"),
            escape(advice),
        ]
    )

scoring_rows = [
    [escape("报价评分"), quote("报价评分=评标基准价/评标价*40"), escape("40"), escape("评标基准价为有效评标价最低价；未提供报价，不能给无条件精确分。")],
    [escape("商务评分"), quote("商务评分满分 10 分。项目经验6分、项目经理2分、合同条款1分、付款条件1分。"), escape("10"), escape("案例合同、项目经理证书和无偏离承诺是核心。")],
    [escape("技术评分"), quote("技术评分满分 50 分。"), escape("50"), escape("客观功能项多为满足即得分；平台能力和运营能力为主观档位评分。")],
]

business_detail_rows = []
for r in business_rows:
    expected = "0 / 待确认 / " + r[3]
    if r[0] in ("3", "4"):
        expected = "0 / 1 / " + r[3]
    business_detail_rows.append(
        [
            escape(r[0]),
            escape(r[1]),
            escape(r[3]),
            quote(r[2]),
            escape("SCA.docx 未提供该商务证明材料。"),
            escape(expected),
            badge("待确认", "soft"),
            escape("补充相应合同、人员证书/社保、商务条款及付款条件无偏离承诺。"),
        ]
    )

framework = [
    ("h2", "一、投标函及报价文件"),
    ("h3", "1.1 投标文件封面"),
    ("h3", "1.2 投标书"),
    ("h3", "1.3 开标一览表"),
    ("h3", "1.4 投标分项报价表"),
    ("h3", "1.5 投标保证金证明材料"),
    ("h2", "二、商务响应文件"),
    ("h3", "2.1 商务条款响应/偏离表"),
    ("h3", "2.2 合同条款响应/偏离表"),
    ("h3", "2.3 付款条件响应说明"),
    ("h3", "2.4 其他声明函"),
    ("h2", "三、资格证明文件"),
    ("h3", "3.1 营业执照"),
    ("h3", "3.2 制造商资格声明或贸易公司资格声明"),
    ("h3", "3.3 制造商授权书"),
    ("h3", "3.4 信用中国信用报告"),
    ("h3", "3.5 中国裁判文书网查询截图"),
    ("h3", "3.6 审计报告"),
    ("h3", "3.7 纳税证明"),
    ("h3", "3.8 社保证明"),
    ("h3", "3.9 法定代表人证明书"),
    ("h3", "3.10 法定代表人授权委托书"),
    ("h2", "四、技术响应文件"),
    ("h3", "4.1 货物说明一览表"),
    ("h3", "4.2 技术规格响应/偏离表"),
    ("h3", "4.3 ★重要技术条款响应"),
    ("h3", "4.4 一般技术条款响应"),
    ("h3", "4.5 产品功能截图与测试截图"),
    ("h3", "4.6 产品参数、手册与证明材料"),
    ("h2", "五、项目经验与人员材料"),
    ("h3", "5.1 投标产品国内应用案例"),
    ("h3", "5.2 类似项目业绩合同复印件"),
    ("h3", "5.3 项目经理材料"),
    ("h3", "5.4 拟派主要服务人员情况表"),
    ("h2", "六、服务建议书"),
    ("h3", "6.1 平台能力介绍方案"),
    ("h3", "6.2 实施部署方案"),
    ("h3", "6.3 运维售后服务方案"),
    ("h3", "6.4 应急响应方案"),
    ("h3", "6.5 服务承诺与优惠措施"),
    ("h2", "七、评分索引与其他材料"),
    ("h3", "7.1 评分索引表"),
    ("h3", "7.2 投标人认为需要提交的其他资料"),
]

framework_html = "\n".join(f"<{tag}>{escape(text)}</{tag}>" for tag, text in framework)

timeline_items = [
    ("招标文件领取开始", "2025-07-22", "东航集团集采实施平台报名/下载", "normal"),
    ("招标文件领取截止", "2025-07-30", "领取期已结束", "important"),
    ("投标截止", "2025-08-12", "2025-08-12 09:30 北京时间", "critical"),
    ("开标时间", "2025-08-12", "2025-08-12 09:30 北京时间，需在线解密", "critical"),
]

timeline_html = "\n".join(
    f"""
    <li class="{cls}">
      <span class="dot"></span>
      <div><strong>{escape(name)}</strong><time>{escape(day)}</time><p>{escape(note)}；{escape(status_for_date(day))}</p></div>
    </li>
    """
    for name, day, note, cls in timeline_items
)

screenshot_rows = []
for item in test_screenshot_rows:
    screenshot_rows.append(
        [
            escape(str(item["index"])),
            escape("测试截图"),
            escape("第三章 货物和服务需求 / 测试用例，目录第22页起"),
            quote(item["purpose"]),
            escape(item["steps"]),
            escape("技术响应文件 / 产品功能截图与测试截图"),
            checkbox("已准备"),
        ]
    )

non_screenshot_rows_html = [
    [
        escape(str(i)),
        escape(kind),
        escape(loc),
        quote(req),
        escape(name),
        escape(place),
        badge(priority, "high" if priority == "高" else "soft"),
        checkbox("已准备"),
    ]
    for i, (kind, name, loc, req, place, priority) in enumerate(non_screenshot_materials, 1)
]

risk_cards = "\n".join(
    f"""
    <article class="risk-card {'risk-fatal' if r['level']=='致命' else 'risk-warning'}">
      <h3>{escape(r['title'])} {badge(r['level'], 'fatal' if r['level']=='致命' else 'warn')}</h3>
      <dl>
        <dt>招标文件位置</dt><dd>{escape(r['loc'])}</dd>
        <dt>原文引用</dt><dd>{quote(r['quote'])}</dd>
        <dt>合规要求</dt><dd>{escape(r['req'])}</dd>
      </dl>
    </article>
    """
    for r in risks
)

star_rows = [
    [
        escape(str(i)),
        quote(req),
        escape("第三章 货物和服务需求，目录第22页起"),
        escape("逐条响应且不得负偏离；建议配对应测试截图。"),
        checkbox("已核对"),
    ]
    for i, req in enumerate(star_requirements, 1)
]

loss_items = [
    ("报价评分", "40分", "缺报价及竞争报价，无法计算价格分。", "确定投标含税/不含税价、免费运维期、保修期后维保比例；按公式做价格场景测算。"),
    ("项目经验", "6分", "未提供国内应用案例合同复印件，且合同金额需不低于80万元。", "准备最多6个投标产品国内案例，每个合同金额不低于80万元。"),
    ("平台能力", "约6分", "SCA是功能清单，不是完整平台能力介绍方案。", "补充平台架构、使用场景、页面截图、用户体验说明和功能闭环。"),
    ("运营能力", "约5分", "未提供部署、运维、后期运营、应急响应完整方案。", "编写实施部署、运维巡检、知识库更新、应急响应、服务SLA。"),
    ("项目经理", "2分", "未提供本科、PMP、CISP、两项安全项目管理经验证明、近6个月社保。", "锁定项目经理并补齐证书、经验证明和社保。"),
    ("知识库容量", "2分", "SCA指标与评分表阈值存在差距或缺项。", "确认是否可提供1亿组件版本、3000许可证、可达分析数量、投毒组件版本证明。"),
]

loss_cards = "\n".join(
    f"""
    <article class="loss-card">
      <h3>{escape(name)} <span>{escape(score)}</span></h3>
      <p>{escape(reason)}</p>
      <label><input type="checkbox"> {escape(action)}</label>
    </article>
    """
    for name, score, reason, action in loss_items
)

bonus_cards = "\n".join(
    f"""
    <article class="bonus-card">
      <h3>{escape(r[1])} <span class="score-pill">{escape(r[3])} 分</span></h3>
      <p><strong>招标文件位置：</strong>第六章 评标办法，目录第62页</p>
      {quote(r[2])}
      <p><strong>满分条件：</strong>{escape('按评分标准提交完整证明材料。')}</p>
      <div class="material-list">
        {checkbox('证明材料已准备')}
        {checkbox('已放入评分索引')}
        {checkbox('已加盖公章或按格式签字')}
      </div>
    </article>
    """
    for r in business_rows
)

checklist_groups = {
    "A. 废标条款核查": [f"{r['title']}已满足" for r in risks],
    "B. 内容完整性": ["商务投标文件 9.2 所列材料齐全", "技术投标文件 9.3 所列材料齐全", "投标文件按规定顺序编排"],
    "C. 数据一致性": ["线上报价与纸质扫描件报价一致", "投标书总价与分项报价表一致", "项目名称、项目编号、投标人名称全篇一致"],
    "D. 格式规范": ["技术规格响应/偏离表逐条填写", "商务条款响应/偏离表填写无偏离或列明偏离", "纸质投标文件逐页连续页码"],
    "E. 签章完整性": ["封面、投标书、偏离表、授权书签字盖章齐全", "授权代表签署时附法定代表人授权书和证明书", "手工修改处签字盖章"],
    "F. 封装要求": ["正本1套、副本4套", "整册胶装且不易脱落", "外层信封密封、封口贴封条并盖公章"],
    "G. 截图与证明材料完整性": ["所有测试截图均放入技术响应章节", "信用中国、裁判文书网材料在有效时间内", "评分项证明材料已建立索引"],
}

checklist_html = "\n".join(
    f"""
    <details open>
      <summary>{escape(group)}</summary>
      <div class="check-grid">{''.join(checkbox(item) for item in items)}</div>
    </details>
    """
    for group, items in checklist_groups.items()
)

todo_cols = {
    "紧急：影响资格/废标": ["缴纳或开具投标保证金", "确认报价不超过150万元且维保比例不超过8%", "逐条核对所有★技术条款无负偏离", "补齐营业执照、授权书、信用/裁判文书材料"],
    "重要：影响得分": ["准备6个80万元以上国内应用案例", "准备项目经理本科/PMP/CISP/经验证明/社保", "撰写平台能力介绍方案", "撰写部署运维和应急响应方案"],
    "锦上添花：加分材料": ["补充产品手册、检测报告、知识库指标证明", "补充界面截图和场景化说明", "整理评分索引表"],
    "截图/证明": ["生成所有测试截图", "生成信用中国信用报告", "生成裁判文书网查询截图", "扫描证书、合同关键页、社保和审计报告"],
}

todo_html = "\n".join(
    f"""
    <div class="todo-col">
      <h3>{escape(title)}</h3>
      {''.join(f'<div class="todo-item">{checkbox(item)}</div>' for item in items)}
    </div>
    """
    for title, items in todo_cols.items()
)

technical_cards_html = render_technical_cards(technical_detail_items)
screenshot_cards_html = render_screenshot_cards(test_screenshot_rows)

strengthen_rows = [
    ["立即处理", "★重要技术条款", "否决风险", "无法用分值弥补", "逐条制作响应表和测试截图", "产品经理/售前", "投标截止前"],
    ["立即处理", "报价评分", "待计算", "最高40分", "确定报价和维保比例，做价格策略测算", "商务/销售", "报价定稿前"],
    ["高收益补强", "项目经验", "0分", "6分", "准备6个国内应用案例合同复印件，合同金额不低于80万元", "销售/交付", "装订前"],
    ["高收益补强", "平台能力", "4分", "约6分", "补平台能力介绍方案、截图、场景和用户体验说明", "售前", "技术册定稿前"],
    ["高收益补强", "运营能力", "0分", "5分", "补部署、运维、运营、应急响应方案", "交付/售后", "技术册定稿前"],
    ["中收益补强", "项目经理", "0分", "2分", "补本科、PMP、CISP、两项安全项目经验、6个月社保", "项目办/人事", "装订前"],
    ["中收益补强", "知识库容量/来源", "0分", "4分", "确认并补充阈值证明、截图或厂商证明", "产品/厂商", "技术册定稿前"],
]

strengthen_html = render_table(
    ["分组", "关联评分项", "当前预计", "可追回", "补强动作", "负责人", "截止"],
    [[escape(x) for x in r] + [] for r in strengthen_rows],
)


html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>信息安全供应链安全检测平台项目 招标文件分析报告</title>
  <style>
    :root {{
      --ink:#17202a; --muted:#657383; --line:#dde5ee; --paper:#f6f8fb; --card:#ffffff;
      --blue:#0f609b; --green:#247a55; --red:#b42318; --amber:#a65f00; --violet:#6842a0;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Arial,sans-serif; }}
    .report-hero {{ padding:42px min(6vw,72px) 30px; color:#fff; background:linear-gradient(130deg,#12344d,#155e63 58%,#6b4f1d); }}
    .report-hero h1 {{ margin:0 0 10px; font-size:34px; letter-spacing:0; }}
    .report-hero p {{ margin:4px 0; color:#dbe9f3; }}
    .toc {{ position:sticky; top:0; z-index:5; display:flex; gap:8px; overflow:auto; padding:10px min(6vw,72px); background:#fff; border-bottom:1px solid var(--line); }}
    .toc a {{ white-space:nowrap; color:#245; text-decoration:none; padding:6px 10px; border-radius:6px; }}
    .toc a:hover {{ background:#eef4f9; }}
    main {{ max-width:1240px; margin:0 auto; padding:26px 20px 56px; }}
    .section {{ margin:22px 0; padding:24px; background:var(--card); border:1px solid var(--line); border-radius:8px; box-shadow:0 8px 24px rgba(18,52,77,.06); }}
    .section h2 {{ margin:0 0 16px; font-size:24px; }}
    .grid {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); }}
    .metric {{ padding:16px; border:1px solid var(--line); border-radius:8px; background:#fbfdff; }}
    .metric span {{ display:block; color:var(--muted); font-size:13px; }}
    .metric strong {{ font-size:24px; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; background:#eef4f7; color:#26465f; font-size:12px; font-weight:700; }}
    .badge.fatal,.badge.high {{ background:#fee4e2; color:var(--red); }}
    .badge.warn {{ background:#fff1d6; color:var(--amber); }}
    .badge.soft {{ background:#eaf3ff; color:var(--blue); }}
    .risk-card,.bonus-card,.loss-card {{ margin:12px 0; padding:16px; border-radius:8px; border:1px solid var(--line); background:#fff; }}
    .risk-fatal {{ border-left:6px solid var(--red); }}
    .risk-warning {{ border-left:6px solid var(--amber); }}
    .risk-card h3,.bonus-card h3,.loss-card h3 {{ margin:0 0 8px; font-size:18px; }}
    dl {{ display:grid; grid-template-columns:120px 1fr; gap:8px 12px; margin:0; }}
    dt {{ color:var(--muted); font-weight:700; }}
    dd {{ margin:0; }}
    blockquote {{ margin:6px 0; padding:10px 12px; border-left:4px solid #9fb8ca; background:#f4f8fb; color:#263844; max-height:160px; overflow:auto; }}
    .score-bars {{ display:grid; gap:10px; margin:14px 0; }}
    .score-row {{ display:grid; grid-template-columns:120px 1fr 70px; align-items:center; gap:12px; }}
    .bar {{ height:12px; background:#e8eef3; border-radius:999px; overflow:hidden; }}
    .bar i {{ display:block; height:100%; background:linear-gradient(90deg,var(--blue),var(--green)); }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:8px; }}
    table {{ width:100%; border-collapse:collapse; background:#fff; }}
    th,td {{ padding:10px 12px; border-bottom:1px solid var(--line); vertical-align:top; min-width:90px; }}
    th {{ background:#edf4f7; text-align:left; position:sticky; top:0; }}
    details {{ border:1px solid var(--line); border-radius:8px; padding:12px; margin:12px 0; background:#fcfdff; }}
    summary {{ cursor:pointer; font-weight:800; }}
    .timeline {{ list-style:none; padding:0; margin:0; border-left:2px solid #c7d7e4; }}
    .timeline li {{ position:relative; margin:0 0 18px 18px; padding:0 0 0 18px; }}
    .timeline .dot {{ position:absolute; left:-26px; top:4px; width:14px; height:14px; border-radius:50%; background:var(--blue); border:3px solid #fff; box-shadow:0 0 0 2px #c7d7e4; }}
    .timeline .critical .dot {{ background:var(--red); }}
    .timeline time {{ display:block; color:var(--muted); }}
    .check {{ display:flex; gap:8px; align-items:flex-start; margin:7px 0; }}
    .check input {{ margin-top:5px; }}
    .check-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:4px 14px; }}
    .progress {{ height:12px; background:#e8eef3; border-radius:999px; overflow:hidden; margin:10px 0; }}
    .progress span {{ display:block; height:100%; width:0%; background:linear-gradient(90deg,var(--green),#5aa874); }}
    .todo-board {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px; }}
    .todo-col {{ border:1px solid var(--line); border-radius:8px; background:#fff; padding:14px; }}
    .todo-col h3 {{ margin-top:0; }}
    .todo-item {{ padding:10px 0; border-top:1px dashed var(--line); }}
    .section-heading {{ display:flex; justify-content:space-between; align-items:center; gap:12px; }}
    button {{ border:0; border-radius:6px; background:var(--blue); color:#fff; padding:8px 12px; cursor:pointer; }}
    .word-framework {{ padding:14px; background:#fbfdff; border:1px dashed #9fb8ca; border-radius:8px; }}
    .word-framework h2 {{ margin:14px 0 8px; font-size:20px; }}
    .word-framework h3 {{ margin:8px 0; font-size:16px; }}
    .word-framework h4 {{ margin:6px 0 6px 18px; font-size:15px; }}
    .score-pill {{ float:right; padding:2px 8px; border-radius:999px; background:#eaf6ef; color:var(--green); font-size:13px; }}
    .material-list {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:4px 12px; }}
    .detail-list,.evidence-list {{ display:grid; gap:12px; margin-top:12px; }}
    .score-detail-card,.evidence-card {{ border:1px solid var(--line); border-radius:8px; background:#fff; padding:14px; min-width:0; }}
    .score-detail-card header,.evidence-card header {{ display:grid; grid-template-columns:auto 1fr auto; gap:10px; align-items:center; margin-bottom:10px; }}
    .score-detail-card h3,.evidence-card h3 {{ margin:0; font-size:16px; overflow-wrap:anywhere; }}
    .index-pill {{ display:inline-flex; align-items:center; justify-content:center; min-width:28px; height:28px; padding:0 8px; border-radius:999px; background:#eaf3ff; color:var(--blue); font-weight:800; }}
    .compact-meta {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; margin:10px 0; }}
    .compact-meta div {{ padding:8px 10px; border-radius:8px; background:#f5f8fb; }}
    .compact-meta span {{ display:block; color:var(--muted); font-size:12px; }}
    .score-detail-card p,.evidence-card p {{ margin:8px 0; overflow-wrap:anywhere; }}
    .card-foot {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px; margin-top:10px; color:var(--muted); }}
    .loss-card h3 span {{ color:var(--red); float:right; }}
    .notice {{ padding:12px 14px; border-left:5px solid var(--amber); background:#fff8e8; border-radius:8px; }}
    @media print {{
      body {{ background:#fff; }}
      .toc, button {{ display:none; }}
      .section {{ break-inside:avoid; box-shadow:none; }}
      blockquote {{ max-height:none; overflow:visible; }}
      th {{ position:static; }}
    }}
  </style>
</head>
<body>
  <header class="report-hero">
    <h1>信息安全供应链安全检测平台项目 招标文件分析报告</h1>
    <p>分析日期：2026-06-21 | 分析人：标书阅读专员 AI | 招标文件来源：20250729_招标文件_信息安全供应链安全检测平台项目（发售稿）.docx</p>
    <p>方案材料：SCA.docx | 重要说明：招标文件日期为 2025 年，所有投标关键节点截至 2026-06-21 均已截止。</p>
  </header>
  <nav class="toc">
    <a href="#overview">速览</a><a href="#timeline">时间</a><a href="#risks">废标</a><a href="#scoring">评分</a><a href="#score-simulation">测算</a><a href="#qualification">资质</a><a href="#price">价格</a><a href="#bonus">加分</a><a href="#evidence-materials">材料</a><a href="#binding">装订</a><a href="#bid-framework">框架</a><a href="#checklist">自检</a><a href="#todo">Todo</a><a href="#strengthen">补强</a><a href="#advice">建议</a>
  </nav>
  <main>
    <section id="overview" class="section">
      <h2>一、项目基本信息速览</h2>
      <div class="grid">
        <div class="metric"><span>项目名称</span><strong>信息安全供应链安全检测平台项目</strong></div>
        <div class="metric"><span>项目编号</span><strong>2540C0701064</strong></div>
        <div class="metric"><span>招标人</span><strong>中国东方航空股份有限公司</strong></div>
        <div class="metric"><span>预算/最高限价</span><strong>150万元含税</strong></div>
        <div class="metric"><span>交货期</span><strong>中标通知书后1个月内完成设备备货</strong></div>
        <div class="metric"><span>质保期</span><strong>不少于3年</strong></div>
      </div>
      <p class="notice">当前最优先不是“写漂亮”，而是先稳住三件事：★技术条款无负偏离、报价不超限且维保比例合规、资格/保证金/签章材料齐全。</p>
    </section>

    <section id="timeline" class="section">
      <h2>二、关键时间节点</h2>
      <ul class="timeline">{timeline_html}</ul>
    </section>

    <section id="risks" class="section">
      <h2>三、废标条款清单（按风险等级排列）</h2>
      {risk_cards}
      <details open>
        <summary>★重要技术条款逐项核查</summary>
        {render_table(["序号", "★条款原文", "位置", "合规动作", "状态"], star_rows)}
      </details>
    </section>

    <section id="scoring" class="section">
      <h2>四、评分标准详解</h2>
      <div class="score-bars">
        <div class="score-row"><span>报价评分</span><div class="bar"><i style="width:40%"></i></div><strong>40分</strong></div>
        <div class="score-row"><span>商务评分</span><div class="bar"><i style="width:10%"></i></div><strong>10分</strong></div>
        <div class="score-row"><span>技术评分</span><div class="bar"><i style="width:50%"></i></div><strong>50分</strong></div>
      </div>
      {render_table(["评分大类", "规则原文", "满分", "拿分策略"], scoring_rows)}
      <details open><summary>商务评分明细</summary>{render_table(["序号","评分项","满分","评分规则","我方材料","保守/预期/满分","置信度","补强建议"], business_detail_rows)}</details>
      <details><summary>技术评分明细</summary>{technical_cards_html}</details>
    </section>

    <section id="score-simulation" class="section">
      <h2>五、我方方案得分测算</h2>
      <div class="grid">
        <div class="metric"><span>满分</span><strong>100分</strong></div>
        <div class="metric"><span>已可保守核验（不含价格）</span><strong>{non_price_conservative}/60分</strong></div>
        <div class="metric"><span>预期补材后（不含价格）</span><strong>{non_price_expected}/60分</strong></div>
        <div class="metric"><span>满分潜力（不含价格）</span><strong>60/60分</strong></div>
        <div class="metric"><span>技术保守测算</span><strong>{tech_conservative}/50分</strong></div>
        <div class="metric"><span>技术预期测算</span><strong>{tech_expected}/50分</strong></div>
      </div>
      <p class="notice">价格分因未提供投标报价和竞争报价，不能给无条件精确分。若我方评标价为最低有效评标价，价格分为40分；若我方评标价为最低价的1.10倍，价格分约36.36分；若为1.20倍，价格分约33.33分。</p>
      <details open><summary>逐项测算明细</summary>{technical_cards_html}</details>
      <details open><summary>失分排行与追回动作</summary><div class="grid">{loss_cards}</div></details>
    </section>

    <section id="qualification" class="section">
      <h2>六、资质门槛清单</h2>
      {render_table(["序号","类别","招标文件位置","原文要求","材料/条件","建议放置章节","优先级","状态"], non_screenshot_rows_html)}
    </section>

    <section id="price" class="section">
      <h2>七、价格限制与报价策略参考</h2>
      <div class="grid">
        <div class="metric"><span>最高投标限价</span><strong>1,500,000.00元含税</strong></div>
        <div class="metric"><span>保证金</span><strong>20,000.00元</strong></div>
        <div class="metric"><span>维保比例限制</span><strong>不超过投标价8%</strong></div>
        <div class="metric"><span>价格分公式</span><strong>基准价/评标价*40</strong></div>
      </div>
      {quote("评标价=经纠正计算错误的最终有效不含税报价+五年不含税运维成本（含报价人本项目总报价内所含的免费运维年限）。评标基准价=所有有效评标价的最低价。报价评分=评标基准价/评标价*40。")}
      <p>报价策略上，需同时控制三条线：含税总价不超过150万元、保修期满后维保比例不超过8%、免费运维期和五年不含税运维成本对评标价的影响要提前测算。</p>
    </section>

    <section id="bonus" class="section">
      <h2>八、加分机会与满分材料清单</h2>
      <div class="grid">{bonus_cards}</div>
    </section>

    <section id="evidence-materials" class="section">
      <h2>九、截图与证明材料清单</h2>
      <details open><summary>9.1 需提供截图的条款</summary>{screenshot_cards_html}</details>
      <details open><summary>9.2 非截图类证明材料</summary>{render_table(["序号","材料类型","招标文件位置/页码","原文要求","需准备材料","建议放置章节","优先级","状态"], non_screenshot_rows_html)}</details>
    </section>

    <section id="binding" class="section">
      <h2>十、装订封装要求</h2>
      <div class="grid">
        <div class="metric"><span>纸质文件</span><strong>正本1套，副本4套</strong></div>
        <div class="metric"><span>装订</span><strong>逐页页码，整册胶装</strong></div>
        <div class="metric"><span>密封</span><strong>封口贴封条并盖公章</strong></div>
        <div class="metric"><span>电子文件</span><strong>平台递交并加密/解密</strong></div>
      </div>
      {quote("纸质投标文件每份内页须按序加注页码，整册胶装装订牢固可靠且不能轻易脱落。如因装订问题而出现漏页或缺页，由此产生的一切后果由投标人自行承担。")}
      {quote("投标人应将投标文件密封（封口加贴封条，盖投标人公章），并标明项目编号、采购项目名称。")}
    </section>

    <section id="bid-framework" class="section">
      <div class="section-heading"><h2>十一、投标文件框架（可直接复制到 Word）</h2><button type="button" data-copy-target="framework-content">复制框架</button></div>
      <div id="framework-content" class="word-framework">{framework_html}</div>
    </section>

    <section id="checklist" class="section checklist-panel">
      <h2>十二、投标文件自检 Checklist</h2>
      <div><strong id="check-count">0/0</strong> 已完成</div><div class="progress"><span id="check-progress"></span></div>
      {checklist_html}
    </section>

    <section id="todo" class="section">
      <h2>十三、素材准备 TodoList</h2>
      <div class="todo-board">{todo_html}</div>
    </section>

    <section id="strengthen" class="section">
      <h2>十四、得分补强行动清单</h2>
      {strengthen_html}
    </section>

    <section id="advice" class="section">
      <h2>十五、综合分析与建议</h2>
      <p>这份 SCA 材料的技术底子不差，但目前更适合作为产品能力底稿，还不能直接当作投标响应文件。建议先把 ★ 条款与测试截图做成一张“硬核对表”，再围绕评分表重写技术响应，而不是把功能清单原样贴进去。</p>
      <p>算分上，当前能较稳落地的是技术客观项的一部分，保守按已提供材料约 {tech_conservative}/50 分；如果补齐截图、参数和方案，技术预期可到约 {tech_expected}/50 分。商务和价格是更大的不确定来源：报价未给，商务证明未给，因此总分不能直接精确确认。</p>
      <p><strong>免责声明：</strong>本报告由 AI 辅助生成，所有关键条款请以招标文件原文为准，建议人工复核后使用。</p>
    </section>
  </main>
  <script>
    function updateProgress() {{
      const checks = Array.from(document.querySelectorAll('input[type="checkbox"]'));
      const done = checks.filter(c => c.checked).length;
      const total = checks.length;
      const pct = total ? Math.round(done / total * 100) : 0;
      const bar = document.getElementById('check-progress');
      const count = document.getElementById('check-count');
      if (bar) bar.style.width = pct + '%';
      if (count) count.textContent = done + '/' + total;
    }}
    document.addEventListener('change', updateProgress);
    updateProgress();
    document.querySelectorAll('[data-copy-target]').forEach(btn => {{
      btn.addEventListener('click', async () => {{
        const el = document.getElementById(btn.dataset.copyTarget);
        const text = Array.from(el.querySelectorAll('h2,h3,h4')).map(x => x.textContent).join('\\n');
        try {{
          await navigator.clipboard.writeText(text);
          btn.textContent = '已复制';
          setTimeout(() => btn.textContent = '复制框架', 1400);
        }} catch (e) {{
          const range = document.createRange();
          range.selectNodeContents(el);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
          btn.textContent = '请手动复制';
        }}
      }});
    }});
  </script>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print(OUT)
