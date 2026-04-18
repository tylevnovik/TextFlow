from __future__ import annotations

import json
import pandas as pd

from app.defaults import default_import_template
from app.ingestion import import_files


def test_import_files_supports_csv_json_and_txt(scratch_dir):
    csv_path = scratch_dir / "sample.csv"
    csv_path.write_text(
        "title,abstract,year,institution\n文本工作台,这是第一篇摘要,2024,复旦大学\n",
        encoding="utf-8",
    )
    json_path = scratch_dir / "sample.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "title": "Patent analytics",
                    "abstract": "Battery recycling analytics reveals supply chain risks.",
                    "year": 2023,
                    "institution": "清华大学",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    txt_path = scratch_dir / "notes.txt"
    txt_path.write_text("Standalone text note for quick ingestion.", encoding="utf-8")
    xlsx_path = scratch_dir / "sample.xlsx"
    pd.DataFrame(
        [
            {
                "title": "Excel 标题",
                "abstract": "这是来自 xlsx 的摘要",
                "year": 2021,
                "institution": "南京大学",
            }
        ]
    ).to_excel(xlsx_path, index=False)

    corpus, source_files, validation_issues = import_files([csv_path, json_path, txt_path, xlsx_path], default_import_template())

    assert len(corpus) == 4
    assert len(source_files) == 4
    assert validation_issues == []
    assert corpus[0]["raw_text"]
    assert any(item["title"] == "notes" for item in corpus)
    assert any(item["title"] == "Excel 标题" for item in corpus)


def test_import_files_applies_field_mapping_and_text_build(scratch_dir):
    csv_path = scratch_dir / "mapped.csv"
    csv_path.write_text(
        "Title,Abstract,Published,Org,Notes,Kind\n术语治理,用于测试多字段拼接,2022,复旦大学,保留这列,literature\n",
        encoding="utf-8",
    )

    template = default_import_template("literature")
    template["field_mappings"] = [
        {"source_field": "Title", "target_field": "title"},
        {"source_field": "Abstract", "target_field": "raw_text"},
        {"source_field": "Published", "target_field": "year"},
        {"source_field": "Org", "target_field": "institution"},
        {"source_field": "Kind", "target_field": "source_type"},
    ]
    template["text_build"] = {
        "mode": "concat_fields",
        "fields": ["Title", "Abstract"],
        "delimiter": " | ",
        "skip_empty": True,
    }

    corpus, source_files, validation_issues = import_files([csv_path], template)

    assert len(corpus) == 1
    assert len(source_files) == 1
    assert validation_issues == []
    assert corpus[0]["title"] == "术语治理"
    assert corpus[0]["raw_text"] == "术语治理 | 用于测试多字段拼接"
    assert corpus[0]["year"] == 2022
    assert corpus[0]["institution"] == "复旦大学"
    assert corpus[0]["source_profile"] == "literature"
    assert corpus[0]["extra_metadata"]["Notes"] == "保留这列"
    assert corpus[0]["extra_metadata"]["source_type"] == "literature"
    assert corpus[0]["extra_metadata"]["_source_file_name"] == "mapped.csv"
    assert corpus[0]["extra_metadata"]["_source_row_index"] == 1


def test_import_files_skips_rows_missing_required_fields(scratch_dir):
    csv_path = scratch_dir / "required.csv"
    csv_path.write_text("UT,TI,AB,C1\nWOS-1,缺少摘要,,复旦大学\nWOS-2,完整记录,这里有摘要,上海交通大学\n", encoding="utf-8")

    template = default_import_template("wos")
    corpus, source_files, validation_issues = import_files([csv_path], template)

    assert len(corpus) == 1
    assert len(source_files) == 1
    assert len(validation_issues) == 1
    assert validation_issues[0]["reason"] == "missing_required_fields"
    assert validation_issues[0]["missing_fields"] == ["AB"]
