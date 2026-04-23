from __future__ import annotations

from html import escape
import json
import math
import os
from pathlib import Path
from typing import Any, Callable

import matplotlib
import numpy as np
import pandas as pd
from PIL import ImageDraw, ImageFont
from wordcloud import WordCloud

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

from .runtime_support import build_run_params_snapshot

DEFAULT_CHART_DPI = 320
CLUSTER_POINT_LABEL_LIMIT = 180
CHART_BACKGROUND = "#f7f1e6"
CHART_CARD = "#fffaf3"
WATERMARK_DEFAULT_TEXT = "TextFlow Studio"
FULL_CORPUS_SNAPSHOT_DOC_LIMIT = 80
FULL_CORPUS_SNAPSHOT_CHAR_LIMIT = 120_000
CORPUS_PREVIEW_TEXT_LIMIT = 240
FONT_FAMILY_CANDIDATES = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "PingFang SC",
    "Source Han Sans SC",
    "WenQuanYi Zen Hei",
    "DejaVu Sans",
]
FONT_PATH_CANDIDATES = [
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
]


def resolve_cjk_font_path() -> str | None:
    env_font = os.environ.get("TEXTFLOW_FONT_PATH")
    if env_font:
        candidate = Path(env_font).expanduser()
        if candidate.exists():
            return str(candidate)

    for candidate in FONT_PATH_CANDIDATES:
        if candidate.exists():
            return str(candidate)

    for family in FONT_FAMILY_CANDIDATES:
        try:
            matched = font_manager.findfont(FontProperties(family=family), fallback_to_default=False)
        except Exception:
            continue
        if matched and Path(matched).exists():
            return matched

    try:
        fallback = font_manager.findfont(FontProperties(family="DejaVu Sans"))
    except Exception:
        return None
    return fallback if fallback and Path(fallback).exists() else None


def configure_matplotlib_fonts() -> tuple[str | None, FontProperties | None]:
    font_path = resolve_cjk_font_path()
    font_name: str | None = None
    font_prop: FontProperties | None = None
    if font_path:
        try:
            font_manager.fontManager.addfont(font_path)
        except Exception:
            pass
        try:
            font_prop = FontProperties(fname=font_path)
            font_name = font_prop.get_name()
        except Exception:
            font_prop = None
            font_name = None

    sans_serif_fonts = [*( [font_name] if font_name else [] ), *FONT_FAMILY_CANDIDATES]
    deduped_fonts: list[str] = []
    for family in sans_serif_fonts:
        if family and family not in deduped_fonts:
            deduped_fonts.append(family)
    plt.rcParams["font.sans-serif"] = deduped_fonts
    plt.rcParams["axes.unicode_minus"] = False
    return font_path, font_prop


CJK_FONT_PATH, CJK_FONT_PROP = configure_matplotlib_fonts()

REPORT_CHART_CATALOG = [
    {
        "filename": "frequency_top_terms.png",
        "title": "高频词 Top 15",
        "description": "快速确认当前语料最突出的核心词项。",
    },
    {
        "filename": "project_keywords.png",
        "title": "项目关键词得分",
        "description": "对比项目级关键词的相对权重，便于汇报摘要。",
    },
    {
        "filename": "keyword_wordcloud.png",
        "title": "关键词词云",
        "description": "从整体上查看关键词分布和主题集中区。",
    },
    {
        "filename": "institution_topic_heatmap.png",
        "title": "机构 × 主题热力图",
        "description": "定位哪些机构与哪些主题绑定最紧。",
    },
    {
        "filename": "document_clusters.png",
        "title": "文档聚类分布",
        "description": "查看文档在主题空间中的分组与离散程度。",
    },
]

REPORT_RESULT_TITLES = {
    "frequency_table": "高频词概览",
    "term_document_table": "词项-文档关系预览",
    "term_year_table": "词项年份关系预览",
    "cooccurrence_table": "共现关系预览",
    "selected_feature_terms": "特征词预览",
    "keyword_result": "关键词概览",
    "keyword_cluster_result": "关键词聚类预览",
    "institution_keyword_cooccurrence": "机构-关键词关系预览",
    "institution_topic_cooccurrence": "机构-主题关系预览",
    "clustering_result": "文档聚类预览",
    "audit_table": "规则审计预览",
}


def chart_config(export_params: dict[str, Any] | None) -> dict[str, Any]:
    export_params = export_params if isinstance(export_params, dict) else {}
    dpi = int(export_params.get("chart_dpi", DEFAULT_CHART_DPI) or DEFAULT_CHART_DPI)
    dpi = max(160, min(dpi, 600))
    watermark_text = str(export_params.get("watermark_text") or WATERMARK_DEFAULT_TEXT).strip() or WATERMARK_DEFAULT_TEXT
    return {
        "dpi": dpi,
        "watermark_enabled": bool(export_params.get("watermark_enabled", False)),
        "watermark_text": watermark_text,
    }


def humanize_term(term: str) -> str:
    return str(term).replace("_", " ").strip()


def chart_font(size: int) -> ImageFont.ImageFont:
    if CJK_FONT_PATH:
        try:
            return ImageFont.truetype(CJK_FONT_PATH, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def add_plot_watermark(fig: plt.Figure, text: str) -> None:
    kwargs: dict[str, Any] = {}
    if CJK_FONT_PROP is not None:
        kwargs["fontproperties"] = CJK_FONT_PROP
    fig.text(
        0.985,
        0.02,
        text,
        ha="right",
        va="bottom",
        fontsize=12,
        color="#1e2228",
        alpha=0.18,
        **kwargs,
    )


def apply_image_watermark(image, text: str):
    overlay = image.convert("RGBA")
    drawing = ImageDraw.Draw(overlay)
    font_size = max(24, int(min(image.size) * 0.035))
    font = chart_font(font_size)
    bbox = drawing.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = image.size[0] - width - 44
    y = image.size[1] - height - 32
    drawing.text((x, y), text, font=font, fill=(30, 34, 40, 58))
    return overlay.convert("RGB")


def finalize_plot(fig: plt.Figure, output_path: Path, config: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if config["watermark_enabled"]:
        add_plot_watermark(fig, config["watermark_text"])
    fig.tight_layout()
    fig.savefig(output_path, dpi=config["dpi"], bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def build_html_report(manifest: dict[str, Any], corpus: list[dict[str, Any]], result_bundle: dict[str, Any]) -> str:
    def rows_for(key: str) -> list[dict[str, Any]]:
        rows = result_bundle.get(key, [])
        return rows if isinstance(rows, list) else []

    def format_value(value: Any) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, float):
            return f"{value:.4f}".rstrip("0").rstrip(".")
        if isinstance(value, list):
            rendered = [format_value(item) for item in value if item not in (None, "")]
            return " / ".join(rendered[:6]) if rendered else "—"
        return str(value)

    def safe(value: Any) -> str:
        return escape(format_value(value))

    def render_table(columns: list[tuple[str, str]], rows: list[dict[str, Any]], limit: int = 12) -> str:
        limited_rows = rows[:limit]
        header = "".join(f"<th>{escape(label)}</th>" for _, label in columns)
        body = "".join(
            "<tr>" + "".join(f"<td>{safe(row.get(key))}</td>" for key, _ in columns) + "</tr>"
            for row in limited_rows
        )
        return f"""
        <div class="table-wrap">
          <table>
            <thead><tr>{header}</tr></thead>
            <tbody>{body}</tbody>
          </table>
        </div>
        """

    def auto_columns(rows: list[dict[str, Any]], limit: int = 6) -> list[tuple[str, str]]:
        ordered_keys: list[str] = []
        for row in rows[:5]:
            if not isinstance(row, dict):
                continue
            for key in row.keys():
                if key not in ordered_keys:
                    ordered_keys.append(str(key))
                if len(ordered_keys) >= limit:
                    break
            if len(ordered_keys) >= limit:
                break
        return [(key, key.replace("_", " ")) for key in ordered_keys]

    latest_run = manifest.get("run_history", [])[-1] if manifest.get("run_history") else None
    frequency_rows = rows_for("frequency_table")
    keyword_rows = rows_for("keyword_result")
    cooccurrence_rows = rows_for("cooccurrence_table")
    topic_rows = rows_for("institution_topic_cooccurrence")
    cluster_rows = rows_for("clustering_result")
    audit_rows = rows_for("audit_table")
    feature_rows = rows_for("selected_feature_terms")
    chart_cards = result_bundle.get("report_chart_cards", [])
    chart_cards = chart_cards if isinstance(chart_cards, list) else []

    year_values = sorted(
        {
            int(item["year"])
            for item in corpus
            if isinstance(item, dict) and isinstance(item.get("year"), int)
        }
    )
    institutions = sorted(
        {
            str(item.get("institution")).strip()
            for item in corpus
            if isinstance(item, dict) and str(item.get("institution") or "").strip()
        }
    )
    sources = sorted(
        {
            str(item.get("source")).strip()
            for item in corpus
            if isinstance(item, dict) and str(item.get("source") or "").strip()
        }
    )
    project_keywords = [
        row for row in keyword_rows if isinstance(row, dict) and str(row.get("scope") or "") == "project"
    ][:12]
    keyword_doc_count = len(
        {
            str(row.get("doc_id"))
            for row in keyword_rows
            if isinstance(row, dict) and str(row.get("scope") or "") == "doc" and row.get("doc_id")
        }
    )
    cluster_count = len(
        {
            int(row["cluster_id"])
            for row in cluster_rows
            if isinstance(row, dict) and row.get("cluster_id") is not None
        }
    )
    audit_summary: dict[tuple[str, str], int] = {}
    for row in audit_rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("rule_type") or "unknown"), str(row.get("action") or "unknown"))
        audit_summary[key] = audit_summary.get(key, 0) + 1
    audit_summary_rows = [
        {"rule_type": rule_type, "action": action, "hits": hits}
        for (rule_type, action), hits in sorted(audit_summary.items(), key=lambda item: item[1], reverse=True)
    ]

    highlights: list[tuple[str, str]] = []
    if frequency_rows:
        top_term = frequency_rows[0]
        highlights.append(
            (
                "词频主词项",
                f"{format_value(top_term.get('term'))}，TF {format_value(top_term.get('tf'))}，DF {format_value(top_term.get('df'))}",
            )
        )
    if project_keywords:
        top_keyword = project_keywords[0]
        highlights.append(
            (
                "项目关键词",
                f"{format_value(top_keyword.get('keyword'))}，得分 {format_value(top_keyword.get('score'))}",
            )
        )
    if cooccurrence_rows:
        top_pair = cooccurrence_rows[0]
        highlights.append(
            (
                "最强共现组合",
                f"{format_value(top_pair.get('term_a'))} × {format_value(top_pair.get('term_b'))}，共现 {format_value(top_pair.get('cooccurrence_count'))}",
            )
        )
    if topic_rows:
        top_topic = topic_rows[0]
        highlights.append(
            (
                "机构主题热点",
                f"{format_value(top_topic.get('institution'))} - {format_value(top_topic.get('topic_label'))}，共现 {format_value(top_topic.get('cooccurrence_count'))}",
            )
        )
    if audit_summary_rows:
        top_audit = audit_summary_rows[0]
        highlights.append(
            (
                "规则命中最多的动作",
                f"{format_value(top_audit.get('rule_type'))} / {format_value(top_audit.get('action'))}，共 {format_value(top_audit.get('hits'))} 次",
            )
        )

    meta_cards = [
        ("文档数", str(len(corpus)), "本次报告覆盖的文档总量"),
        (
            "结果表",
            str(sum(1 for key, rows in result_bundle.items() if key != "report_chart_cards" and isinstance(rows, list) and rows)),
            "本次真正写入报告的数据块",
        ),
        ("图表数", str(len(chart_cards)), "成功生成且可嵌入 HTML 的图表"),
        ("机构数", str(len(institutions)), "语料中出现的机构数"),
        ("来源数", str(len(sources)), "语料来源字段的去重个数"),
        ("年份范围", f"{year_values[0]} - {year_values[-1]}" if year_values else "未提供", "语料中可识别的年份范围"),
    ]
    workflow_label = (
        str(latest_run.get("workflow_name") or "")
        if latest_run
        else str(manifest.get("active_workflow_id") or "")
    ) or "默认工作流"
    meta_html = "".join(
        f"""
        <div class="meta-card">
          <strong>{escape(label)}</strong>
          <span>{escape(value)}</span>
          <small>{escape(description)}</small>
        </div>
        """
        for label, value, description in meta_cards
    )

    sections: list[str] = []
    if highlights:
        sections.append(
            """
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Core Findings</p>
            <h2>核心发现</h2>
          </div>
        </div>
        <div class="insight-grid">
"""
            + "".join(
                f"""
          <article class="insight-card">
            <strong>{escape(title)}</strong>
            <p>{escape(detail)}</p>
          </article>
          """
                for title, detail in highlights
            )
            + """
        </div>
      </section>
"""
        )

    if frequency_rows:
        sections.append(
            f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Frequency</p>
            <h2>高频词概览</h2>
          </div>
          <span class="pill">Top {min(len(frequency_rows), 12)}</span>
        </div>
        {render_table([("term", "词项"), ("tf", "TF"), ("df", "DF"), ("ratio", "占比")], frequency_rows)}
      </section>
"""
        )

    if project_keywords:
        sections.append(
            f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Keywords</p>
            <h2>关键词概览</h2>
          </div>
          <span class="pill">覆盖 {keyword_doc_count} 篇文档</span>
        </div>
        {render_table([("keyword", "关键词"), ("score", "得分"), ("rank", "排名")], project_keywords)}
      </section>
"""
        )

    if cooccurrence_rows:
        sections.append(
            f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Co-occurrence</p>
            <h2>共现关系预览</h2>
          </div>
        </div>
        {render_table([("term_a", "词项 A"), ("term_b", "词项 B"), ("cooccurrence_count", "共现次数"), ("score", "得分")], cooccurrence_rows)}
      </section>
"""
        )

    if topic_rows:
        sections.append(
            f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Institution Topic</p>
            <h2>机构 × 主题热点</h2>
          </div>
        </div>
        {render_table([("institution", "机构"), ("topic_label", "主题"), ("cooccurrence_count", "共现次数"), ("year", "年份")], topic_rows)}
      </section>
"""
        )

    if feature_rows:
        sections.append(
            f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Features</p>
            <h2>特征词预览</h2>
          </div>
        </div>
        {render_table([("term", "词项"), ("score", "得分"), ("selected", "已选中"), ("source", "来源")], feature_rows)}
      </section>
"""
        )

    if cluster_rows:
        sections.append(
            f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Document Clusters</p>
            <h2>文档聚类预览</h2>
          </div>
          <span class="pill">{cluster_count} 个簇</span>
        </div>
        {render_table([("doc_id", "文档 ID"), ("cluster_id", "簇"), ("title", "标题"), ("year", "年份")], cluster_rows)}
      </section>
"""
        )

    handled_keys = {
        "report_chart_cards",
        "frequency_table",
        "keyword_result",
        "cooccurrence_table",
        "institution_topic_cooccurrence",
        "selected_feature_terms",
        "clustering_result",
        "audit_table",
    }
    for key, rows in result_bundle.items():
        if key in handled_keys or not isinstance(rows, list) or not rows:
            continue
        columns = auto_columns(rows)
        if not columns:
            continue
        sections.append(
            f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Result Preview</p>
            <h2>{escape(REPORT_RESULT_TITLES.get(key, key.replace('_', ' ')))}</h2>
          </div>
        </div>
        {render_table(columns, rows)}
      </section>
"""
        )

    if chart_cards:
        chart_html = "".join(
            f"""
          <article class="chart-card">
            <img src="{escape(str(card.get('relative_path') or ''))}" alt="{escape(str(card.get('title') or '图表'))}" />
            <div>
              <strong>{escape(str(card.get('title') or '图表'))}</strong>
              <p>{escape(str(card.get('description') or ''))}</p>
            </div>
          </article>
            """
            for card in chart_cards
            if isinstance(card, dict) and card.get("relative_path")
        )
        if chart_html:
            sections.append(
                f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Charts</p>
            <h2>图表导出</h2>
          </div>
        </div>
        <div class="chart-grid">
          {chart_html}
        </div>
      </section>
"""
            )

    if audit_rows:
        sections.append(
            f"""
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Audit Trail</p>
            <h2>规则审计摘要</h2>
          </div>
        </div>
        {render_table([("rule_type", "规则类型"), ("action", "动作"), ("hits", "命中次数")], audit_summary_rows, limit=10)}
        <div class="section-divider"></div>
        {render_table([("doc_id", "文档 ID"), ("source_term", "原词"), ("target_term", "目标词"), ("rule_type", "规则"), ("action", "动作")], audit_rows, limit=12)}
      </section>
"""
        )

    if not sections:
        sections.append(
            """
      <section>
        <div class="section-head">
          <div>
            <p class="eyebrow">Summary</p>
            <h2>本次报告没有可展示的分析结果</h2>
          </div>
        </div>
        <p>当前只写入了运行快照，未生成可嵌入的分析表或图表。请检查工作流是否接入了分析节点与输出节点。</p>
      </section>
"""
        )

    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>{escape(str(manifest['name']))} - TextFlow Report</title>
    <style>
      body {{ font-family: 'Segoe UI', sans-serif; margin: 0; background: #f7f1e6; color: #1e2228; }}
      main {{ max-width: 1080px; margin: 0 auto; padding: 32px; }}
      section {{ background: rgba(255,255,255,0.85); border-radius: 20px; padding: 24px; margin-bottom: 20px; }}
      h1, h2 {{ font-family: Georgia, serif; }}
      p {{ line-height: 1.7; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ padding: 10px; border-bottom: 1px solid rgba(30,34,40,0.12); text-align: left; }}
      .hero p {{ margin: 0 0 12px; }}
      .eyebrow {{ text-transform: uppercase; letter-spacing: 0.08em; font-size: 12px; color: #8d5f16; }}
      .meta {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
      .meta-card {{ background: #fffaf3; padding: 14px; border-radius: 14px; display: flex; flex-direction: column; gap: 6px; }}
      .meta-card strong {{ font-size: 12px; color: #8d5f16; }}
      .meta-card span {{ font-size: 22px; font-weight: 700; }}
      .meta-card small {{ color: rgba(30,34,40,0.7); }}
      .section-head {{ display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 14px; }}
      .pill {{ display: inline-flex; align-items: center; padding: 6px 10px; border-radius: 999px; background: #fff4db; color: #8d5f16; font-size: 12px; }}
      .insight-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
      .insight-card {{ background: #fffaf3; padding: 16px; border-radius: 16px; }}
      .insight-card strong {{ display: block; margin-bottom: 8px; }}
      .table-wrap {{ overflow-x: auto; }}
      .chart-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
      .chart-card {{ background: #fffaf3; border-radius: 16px; overflow: hidden; }}
      .chart-card img {{ width: 100%; display: block; background: #fffaf3; }}
      .chart-card div {{ padding: 14px; }}
      .chart-card strong {{ display: block; margin-bottom: 6px; }}
      .chart-card p {{ margin: 0; color: rgba(30,34,40,0.76); }}
      .section-divider {{ height: 1px; background: rgba(30,34,40,0.08); margin: 18px 0; }}
      @media (max-width: 860px) {{
        .meta,
        .insight-grid,
        .chart-grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <p>TextFlow Studio Report</p>
        <h1>{escape(str(manifest['name']))}</h1>
        <p>{escape(str(manifest.get('description') or ''))}</p>
        <p><strong>本次处理对象</strong><br />{escape(str(latest_run['run_scope_summary'] if latest_run else '项目内全部资料'))}</p>
        <p><strong>本次输出包</strong><br />{escape(str(latest_run['output_summary'] if latest_run else '表格与图表'))}</p>
        <p><strong>工作流</strong><br />{escape(workflow_label)}</p>
        <div class="meta">
          {meta_html}
        </div>
      </section>
      {''.join(sections)}
    </main>
  </body>
</html>"""


def save_frequency_chart(frequency_table: list[dict[str, Any]], output_path: Path, config: dict[str, Any]) -> None:
    if not frequency_table:
        return
    terms = [humanize_term(row["term"]) for row in frequency_table[:15]]
    values = [row["tf"] for row in frequency_table[:15]]
    fig, ax = plt.subplots(figsize=(12, 7), facecolor=CHART_BACKGROUND)
    ax.set_facecolor(CHART_CARD)
    ax.barh(terms[::-1], values[::-1], color="#d6a84f")
    ax.set_xlabel("TF")
    ax.set_title("高频词 Top 15")
    finalize_plot(fig, output_path, config)


def save_keyword_chart(keyword_rows: list[dict[str, Any]], output_path: Path, config: dict[str, Any]) -> None:
    project_keywords = sorted(
        [row for row in keyword_rows if row.get("scope") == "project"],
        key=lambda row: row.get("rank", 9999),
    )[:15]
    if not project_keywords:
        return

    labels = [humanize_term(str(row["keyword"])) for row in project_keywords]
    values = [float(row["score"]) for row in project_keywords]
    fig, ax = plt.subplots(figsize=(12, 7), facecolor=CHART_BACKGROUND)
    ax.set_facecolor(CHART_CARD)
    ax.barh(labels[::-1], values[::-1], color="#18705a")
    ax.set_xlabel("Score")
    ax.set_title("项目级关键词")
    finalize_plot(fig, output_path, config)


def keyword_frequencies(
    frequency_table: list[dict[str, Any]],
    keyword_rows: list[dict[str, Any]],
) -> dict[str, float]:
    project_keywords = [row for row in keyword_rows if row.get("scope") == "project"]
    if project_keywords:
        return {
            humanize_term(str(row["keyword"])): max(float(row["score"]), 0.001)
            for row in project_keywords[:120]
            if str(row["keyword"]).strip()
        }
    return {
        humanize_term(str(row["term"])): max(float(row["tf"]), 0.001)
        for row in frequency_table[:160]
        if str(row["term"]).strip()
    }


def save_wordcloud(
    frequency_table: list[dict[str, Any]],
    keyword_rows: list[dict[str, Any]],
    output_path: Path,
    config: dict[str, Any],
) -> None:
    frequencies = keyword_frequencies(frequency_table, keyword_rows)
    if not frequencies:
        return

    width = max(1800, int(7.2 * config["dpi"]))
    height = max(1200, int(4.8 * config["dpi"]))
    cloud = WordCloud(
        width=width,
        height=height,
        background_color=CHART_BACKGROUND,
        font_path=CJK_FONT_PATH,
        prefer_horizontal=0.92,
        collocations=False,
        max_words=160,
        color_func=lambda *_args, **_kwargs: np.random.choice(["#1e2228", "#8d5f16", "#18705a", "#913f4d"]),
    ).generate_from_frequencies(frequencies)
    image = cloud.to_image()
    if config["watermark_enabled"]:
        image = apply_image_watermark(image, config["watermark_text"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, dpi=(config["dpi"], config["dpi"]))


def save_institution_topic_heatmap(
    topic_rows: list[dict[str, Any]],
    output_path: Path,
    config: dict[str, Any],
) -> None:
    if not topic_rows:
        return

    df = pd.DataFrame(topic_rows)
    if df.empty:
        return
    grouped = (
        df.groupby(["institution", "topic_label"], as_index=False)["cooccurrence_count"]
        .sum()
        .sort_values("cooccurrence_count", ascending=False)
    )
    institutions = (
        grouped.groupby("institution")["cooccurrence_count"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .index
        .tolist()
    )
    topics = (
        grouped.groupby("topic_label")["cooccurrence_count"]
        .sum()
        .sort_values(ascending=False)
        .head(8)
        .index
        .tolist()
    )
    pivot = (
        grouped[grouped["institution"].isin(institutions) & grouped["topic_label"].isin(topics)]
        .pivot(index="institution", columns="topic_label", values="cooccurrence_count")
        .fillna(0)
        .reindex(index=institutions, columns=topics, fill_value=0)
    )
    if pivot.empty:
        return

    width = max(8, len(pivot.columns) * 1.45)
    height = max(5, len(pivot.index) * 0.8 + 2)
    fig, ax = plt.subplots(figsize=(width, height), facecolor=CHART_BACKGROUND)
    ax.set_facecolor(CHART_CARD)
    image = ax.imshow(pivot.to_numpy(), cmap="YlOrBr", aspect="auto")
    ax.set_title("机构 × 主题热力图")
    ax.set_xticks(np.arange(len(pivot.columns)), labels=[humanize_term(column) for column in pivot.columns], rotation=24, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)), labels=list(pivot.index))
    plt.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    if pivot.shape[0] * pivot.shape[1] <= 80:
        for row_index in range(pivot.shape[0]):
            for column_index in range(pivot.shape[1]):
                value = int(pivot.iat[row_index, column_index])
                if value:
                    ax.text(column_index, row_index, str(value), ha="center", va="center", color="#1e2228", fontsize=9)
    finalize_plot(fig, output_path, config)


def save_cluster_chart(cluster_rows: list[dict[str, Any]], output_path: Path, config: dict[str, Any]) -> None:
    if not cluster_rows:
        return
    df = pd.DataFrame(cluster_rows)
    fig, ax = plt.subplots(figsize=(8, 8), facecolor=CHART_BACKGROUND)
    ax.set_facecolor(CHART_CARD)
    ax.scatter(df["x"], df["y"], c=df["cluster_id"], cmap="Set2", s=88, alpha=0.85)
    if len(df) <= CLUSTER_POINT_LABEL_LIMIT:
        for row in df.itertuples(index=False):
            ax.text(row.x, row.y, row.doc_id, fontsize=8)
        ax.set_title("文档聚类分布")
    else:
        cluster_centers = df.groupby("cluster_id", as_index=False)[["x", "y"]].mean()
        cluster_sizes = df.groupby("cluster_id").size().to_dict()
        for row in cluster_centers.itertuples(index=False):
            ax.text(
                row.x,
                row.y,
                f"簇 {int(row.cluster_id)} ({cluster_sizes.get(int(row.cluster_id), 0)})",
                fontsize=9,
                fontweight="bold",
                ha="center",
                va="center",
                bbox={"boxstyle": "round,pad=0.24", "facecolor": "#fffaf3", "edgecolor": "#d6a84f", "alpha": 0.9},
            )
        ax.set_title("文档聚类分布（大语料已省略点标签）")
    finalize_plot(fig, output_path, config)


def write_json_snapshot(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def _truncate_snapshot_text(value: Any, limit: int = CORPUS_PREVIEW_TEXT_LIMIT) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def build_corpus_snapshot(corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_raw_chars = sum(len(str(item.get("raw_text") or "")) for item in corpus if isinstance(item, dict))
    include_full_text = len(corpus) <= FULL_CORPUS_SNAPSHOT_DOC_LIMIT and total_raw_chars <= FULL_CORPUS_SNAPSHOT_CHAR_LIMIT
    rows: list[dict[str, Any]] = []
    for item in corpus:
        if not isinstance(item, dict):
            continue
        snapshot_row = {
            "doc_id": item.get("doc_id") or item.get("id"),
            "title": item.get("title"),
            "year": item.get("year"),
            "source": item.get("source"),
            "institution": item.get("institution"),
            "country_or_region": item.get("country_or_region"),
            "category_or_tag": item.get("category_or_tag"),
            "status": item.get("status"),
            "raw_hash": item.get("raw_hash"),
            "token_count": len(item.get("tokens") or []),
            "filtered_token_count": len(item.get("filtered_tokens") or []),
            "phrase_hit_count": len(item.get("phrase_hits") or []),
            "extra_metadata": item.get("extra_metadata") or {},
        }
        if include_full_text:
            snapshot_row["raw_text"] = item.get("raw_text") or ""
        else:
            snapshot_row["raw_text_preview"] = _truncate_snapshot_text(item.get("raw_text"))
        rows.append(snapshot_row)
    return rows


def emit_export_progress(progress_callback: Callable[[float, str], None] | None, fraction: float, message: str) -> None:
    if progress_callback is None:
        return
    progress_callback(min(max(fraction, 0.0), 1.0), message)


def result_bundle_table_entries(result_bundle: dict[str, Any]) -> list[tuple[str, list[Any]]]:
    return [
        (key, rows)
        for key, rows in result_bundle.items()
        if key != "report_files" and isinstance(rows, list) and rows
    ]


def write_run_outputs(
    project_dir: Path,
    run_id: str,
    project_manifest: dict[str, Any],
    workflow_definition: dict[str, Any],
    runtime_profile: dict[str, Any],
    corpus: list[dict[str, Any]],
    result_bundle: dict[str, Any],
    run_record: dict[str, Any],
    export_selection: dict[str, set[str]] | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[str]:
    def build_report_chart_cards() -> list[dict[str, str]]:
        cards: list[dict[str, str]] = []
        for chart in REPORT_CHART_CATALOG:
            chart_path = charts_dir / chart["filename"]
            if not chart_path.exists():
                continue
            cards.append(
                {
                    "relative_path": f"../charts/{chart['filename']}",
                    "title": chart["title"],
                    "description": chart["description"],
                }
            )
        return cards

    run_root = project_dir / "runs" / run_id
    outputs_dir = run_root / "outputs"
    charts_dir = run_root / "charts"
    report_dir = run_root / "report"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    export_params = runtime_profile.get("export", {}) if isinstance(runtime_profile, dict) else {}
    enabled_steps = runtime_profile.get("enabled_steps") if isinstance(runtime_profile, dict) else None
    export_step_enabled = True if enabled_steps is None else "export" in set(enabled_steps)
    include_audit = export_params.get("include_audit", True)
    config = chart_config(export_params)
    exported_files: list[str] = []

    exportable_tables = {
        key: rows
        for key, rows in result_bundle.items()
        if key != "report_files" and (include_audit or key != "audit_table") and isinstance(rows, list)
    }
    if export_selection:
        csv_or_xlsx_tables = set(export_selection.get("csv_tables", set())) | set(export_selection.get("xlsx_tables", set()))
        html_result_keys = set(export_selection.get("html_result_keys", set()))
        selected_tables = csv_or_xlsx_tables | html_result_keys
        if include_audit and export_selection.get("include_audit"):
            selected_tables.add("audit_table")
        if selected_tables:
            exportable_tables = {key: rows for key, rows in exportable_tables.items() if key in selected_tables}
    html_result_keys = set(export_selection.get("html_result_keys", set())) if export_selection else set()
    report_result_bundle = {
        key: rows
        for key, rows in result_bundle.items()
        if key != "report_files" and (include_audit or key != "audit_table") and isinstance(rows, list)
    }
    if export_selection and (html_result_keys or export_selection.get("include_audit")):
        allowed_report_keys = set(html_result_keys)
        if include_audit and export_selection.get("include_audit"):
            allowed_report_keys.add("audit_table")
        report_result_bundle = {
            key: rows
            for key, rows in report_result_bundle.items()
            if key in allowed_report_keys
        }

    emit_export_progress(progress_callback, 0.05, "正在写出参数快照")
    write_json_snapshot(run_root / "params_snapshot.json", build_run_params_snapshot(workflow_definition, runtime_profile))
    emit_export_progress(progress_callback, 0.12, "正在写出日志快照")
    write_json_snapshot(run_root / "logs.json", run_record["logs"])
    (run_root / "logs.txt").write_text(
        "\n".join(
            f"{entry['timestamp']} [{entry['level']}] {entry['step']}: {entry['message']}"
            for entry in run_record["logs"]
        ),
        encoding="utf-8",
    )
    emit_export_progress(progress_callback, 0.22, "正在写出语料快照")
    write_json_snapshot(run_root / "corpus_snapshot.json", build_corpus_snapshot(corpus))

    if export_step_enabled and export_params.get("export_csv", True):
        emit_export_progress(progress_callback, 0.35, "正在导出 CSV")
        for key, rows in exportable_tables.items():
            csv_path = outputs_dir / f"{key}.csv"
            pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
            exported_files.append(str(csv_path.relative_to(project_dir).as_posix()))

    if export_step_enabled and export_params.get("export_xlsx", True) and exportable_tables:
        emit_export_progress(progress_callback, 0.55, "正在导出 XLSX")
        xlsx_path = outputs_dir / "analysis_bundle.xlsx"
        with pd.ExcelWriter(xlsx_path) as writer:
            for key, rows in exportable_tables.items():
                pd.DataFrame(rows).to_excel(writer, sheet_name=key[:31], index=False)
        exported_files.append(str(xlsx_path.relative_to(project_dir).as_posix()))

    if export_step_enabled and export_params.get("export_png", True):
        emit_export_progress(progress_callback, 0.72, "正在渲染 PNG 图表")
        png_selection = set(export_selection.get("png_charts", set())) if export_selection else set()
        frequency_chart = charts_dir / "frequency_top_terms.png"
        keyword_chart = charts_dir / "project_keywords.png"
        wordcloud_chart = charts_dir / "keyword_wordcloud.png"
        topic_heatmap = charts_dir / "institution_topic_heatmap.png"
        cluster_chart = charts_dir / "document_clusters.png"
        if not png_selection or "frequency_top_terms" in png_selection:
            save_frequency_chart(result_bundle["frequency_table"], frequency_chart, config)
        if not png_selection or "project_keywords" in png_selection:
            save_keyword_chart(result_bundle["keyword_result"], keyword_chart, config)
        if not png_selection or "keyword_wordcloud" in png_selection:
            save_wordcloud(result_bundle["frequency_table"], result_bundle["keyword_result"], wordcloud_chart, config)
        if not png_selection or "institution_topic_heatmap" in png_selection:
            save_institution_topic_heatmap(result_bundle["institution_topic_cooccurrence"], topic_heatmap, config)
        if not png_selection or "document_clusters" in png_selection:
            save_cluster_chart(result_bundle["clustering_result"], cluster_chart, config)
        for chart_path in [frequency_chart, keyword_chart, wordcloud_chart, topic_heatmap, cluster_chart]:
            if chart_path.exists():
                exported_files.append(str(chart_path.relative_to(project_dir).as_posix()))

    if export_step_enabled and export_params.get("export_html_report", True):
        emit_export_progress(progress_callback, 0.9, "正在生成 HTML 报告")
        html_report = report_dir / "report.html"
        html_report.write_text(
            build_html_report(
                project_manifest,
                corpus,
                {
                    **report_result_bundle,
                    "report_chart_cards": build_report_chart_cards(),
                },
            ),
            encoding="utf-8",
        )
        exported_files.append(str(html_report.relative_to(project_dir).as_posix()))

    emit_export_progress(progress_callback, 1.0, "导出阶段已完成")

    return exported_files
