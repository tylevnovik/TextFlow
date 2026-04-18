from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from PIL import ImageDraw, ImageFont
from wordcloud import WordCloud

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

DEFAULT_CHART_DPI = 320
CHART_BACKGROUND = "#f7f1e6"
CHART_CARD = "#fffaf3"
WATERMARK_DEFAULT_TEXT = "TextFlow Studio"
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


def chart_config(manifest: dict[str, Any]) -> dict[str, Any]:
    export_params = manifest["pipeline"].get("export", {})
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
    top_terms = result_bundle["frequency_table"][:10]
    topics = result_bundle["institution_topic_cooccurrence"][:8]
    audit_rows = result_bundle["audit_table"][:10]
    png_enabled = manifest["pipeline"].get("export", {}).get("export_png", True)
    latest_run = manifest.get("run_history", [])[-1] if manifest.get("run_history") else None

    top_terms_rows = "".join(
        f"<tr><td>{row['term']}</td><td>{row['tf']}</td><td>{row['df']}</td><td>{row['ratio']:.4f}</td></tr>"
        for row in top_terms
    )
    topic_rows = "".join(
        f"<li><strong>{row['institution']}</strong> - {row['topic_label']} ({row['cooccurrence_count']})</li>"
        for row in topics
    )
    audit_table = "".join(
        f"<tr><td>{row['doc_id']}</td><td>{row['source_term']}</td><td>{row.get('target_term', '')}</td><td>{row['rule_type']}</td><td>{row['action']}</td></tr>"
        for row in audit_rows
    )

    chart_section = (
        """
      <section>
        <h2>图表导出</h2>
        <div class="chart-grid">
          <img src="../charts/frequency_top_terms.png" alt="高频词图表" />
          <img src="../charts/keyword_wordcloud.png" alt="关键词词云" />
          <img src="../charts/project_keywords.png" alt="项目关键词图" />
          <img src="../charts/institution_topic_heatmap.png" alt="机构主题热力图" />
        </div>
      </section>
"""
        if png_enabled
        else ""
    )

    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>{manifest['name']} - TextFlow Report</title>
    <style>
      body {{ font-family: 'Segoe UI', sans-serif; margin: 0; background: #f7f1e6; color: #1e2228; }}
      main {{ max-width: 1080px; margin: 0 auto; padding: 32px; }}
      section {{ background: rgba(255,255,255,0.85); border-radius: 20px; padding: 24px; margin-bottom: 20px; }}
      h1, h2 {{ font-family: Georgia, serif; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ padding: 10px; border-bottom: 1px solid rgba(30,34,40,0.12); text-align: left; }}
      .meta {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
      .meta div {{ background: #fffaf3; padding: 12px; border-radius: 12px; }}
      .chart-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
      .chart-grid img {{ width: 100%; border-radius: 16px; background: #fffaf3; }}
    </style>
  </head>
  <body>
    <main>
      <section>
        <p>TextFlow Studio Report</p>
        <h1>{manifest['name']}</h1>
        <p>{manifest['description']}</p>
        <p><strong>本次处理对象</strong><br />{latest_run['run_scope_summary'] if latest_run else '项目内全部资料'}</p>
        <p><strong>本次输出包</strong><br />{latest_run['output_summary'] if latest_run else '表格与图表'}</p>
        <div class="meta">
          <div><strong>文档数</strong><br />{len(corpus)}</div>
          <div><strong>运行次数</strong><br />{len(manifest.get('run_history', []))}</div>
          <div><strong>默认语言</strong><br />{manifest['settings']['default_language']}</div>
        </div>
      </section>
      <section>
        <h2>核心词频结果</h2>
        <table>
          <thead><tr><th>Term</th><th>TF</th><th>DF</th><th>Ratio</th></tr></thead>
          <tbody>{top_terms_rows}</tbody>
        </table>
      </section>
      <section>
        <h2>机构 × 主题摘要</h2>
        <ul>{topic_rows}</ul>
      </section>
      {chart_section}
      <section>
        <h2>规则审计摘要</h2>
        <table>
          <thead><tr><th>Doc</th><th>Source</th><th>Target</th><th>Rule</th><th>Action</th></tr></thead>
          <tbody>{audit_table}</tbody>
        </table>
      </section>
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
    for _, row in df.iterrows():
        ax.text(row["x"], row["y"], row["doc_id"], fontsize=8)
    ax.set_title("文档聚类分布")
    finalize_plot(fig, output_path, config)


def write_run_outputs(
    project_dir: Path,
    run_id: str,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    result_bundle: dict[str, Any],
    run_record: dict[str, Any],
) -> list[str]:
    run_root = project_dir / "runs" / run_id
    outputs_dir = run_root / "outputs"
    charts_dir = run_root / "charts"
    report_dir = run_root / "report"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    export_params = manifest["pipeline"].get("export", {})
    enabled_steps = manifest["pipeline"].get("enabled_steps")
    export_step_enabled = True if enabled_steps is None else "export" in set(enabled_steps)
    include_audit = export_params.get("include_audit", True)
    config = chart_config(manifest)
    exported_files: list[str] = []

    exportable_tables = {
        key: rows
        for key, rows in result_bundle.items()
        if key != "report_files" and (include_audit or key != "audit_table") and isinstance(rows, list)
    }

    (run_root / "params_snapshot.json").write_text(
        json.dumps(manifest["pipeline"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_root / "logs.json").write_text(
        json.dumps(run_record["logs"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_root / "logs.txt").write_text(
        "\n".join(
            f"{entry['timestamp']} [{entry['level']}] {entry['step']}: {entry['message']}"
            for entry in run_record["logs"]
        ),
        encoding="utf-8",
    )
    (run_root / "corpus_snapshot.json").write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if export_step_enabled and export_params.get("export_csv", True):
        for key, rows in exportable_tables.items():
            csv_path = outputs_dir / f"{key}.csv"
            pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
            exported_files.append(str(csv_path.relative_to(project_dir).as_posix()))

    if export_step_enabled and export_params.get("export_xlsx", True) and exportable_tables:
        xlsx_path = outputs_dir / "analysis_bundle.xlsx"
        with pd.ExcelWriter(xlsx_path) as writer:
            for key, rows in exportable_tables.items():
                pd.DataFrame(rows).to_excel(writer, sheet_name=key[:31], index=False)
        exported_files.append(str(xlsx_path.relative_to(project_dir).as_posix()))

    if export_step_enabled and export_params.get("export_png", True):
        frequency_chart = charts_dir / "frequency_top_terms.png"
        keyword_chart = charts_dir / "project_keywords.png"
        wordcloud_chart = charts_dir / "keyword_wordcloud.png"
        topic_heatmap = charts_dir / "institution_topic_heatmap.png"
        cluster_chart = charts_dir / "document_clusters.png"
        save_frequency_chart(result_bundle["frequency_table"], frequency_chart, config)
        save_keyword_chart(result_bundle["keyword_result"], keyword_chart, config)
        save_wordcloud(result_bundle["frequency_table"], result_bundle["keyword_result"], wordcloud_chart, config)
        save_institution_topic_heatmap(result_bundle["institution_topic_cooccurrence"], topic_heatmap, config)
        save_cluster_chart(result_bundle["clustering_result"], cluster_chart, config)
        for chart_path in [frequency_chart, keyword_chart, wordcloud_chart, topic_heatmap, cluster_chart]:
            if chart_path.exists():
                exported_files.append(str(chart_path.relative_to(project_dir).as_posix()))

    if export_step_enabled and export_params.get("export_html_report", True):
        html_report = report_dir / "report.html"
        html_report.write_text(build_html_report(manifest, corpus, result_bundle), encoding="utf-8")
        exported_files.append(str(html_report.relative_to(project_dir).as_posix()))

    return exported_files
