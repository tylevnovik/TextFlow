from __future__ import annotations

import json
import pandas as pd

from app.domain.defaults import default_import_template
from app.ingestion.importers import dataframe_from_source, import_files


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


def test_incopat_import_template_matches_realistic_xlsx_headers_and_fallbacks(scratch_dir):
    xlsx_path = scratch_dir / "incopat.xlsx"
    pd.DataFrame(
        [
            {
                "标题（中文）": "得到稀土类金属的薄叶片如镝",
                "摘要（中文）": None,
                "首权翻译": "备用中文首权翻译",
                "申请人": "Produits Chim Terres Rares Soc",
                "公开（公告）号": "FR948039A",
                "公开（公告）日": pd.Timestamp("1949-07-20"),
                "发明人": "Trombe Felix",
                "IPC": "C22B59/00",
                "公开国别": "法国",
            },
            {
                "标题（中文）": "缺少可用正文",
                "摘要（中文）": None,
                "首权翻译": None,
                "申请人": "Missing Text Corp",
                "公开（公告）号": "FR000000A",
                "公开（公告）日": pd.Timestamp("1950-01-01"),
                "发明人": "No Body",
                "IPC": "C22B59/00",
                "公开国别": "法国",
            },
        ]
    ).to_excel(xlsx_path, index=False)

    corpus, source_files, validation_issues = import_files([xlsx_path], default_import_template("incopat"))

    assert len(corpus) == 1
    assert len(source_files) == 1
    assert len(validation_issues) == 1
    assert validation_issues[0]["reason"] == "missing_required_fields"
    assert validation_issues[0]["missing_fields"] == ["摘要 (中文)"]
    assert corpus[0]["doc_id"] == "FR948039A"
    assert corpus[0]["title"] == "得到稀土类金属的薄叶片如镝"
    assert corpus[0]["raw_text"] == "得到稀土类金属的薄叶片如镝\n\n备用中文首权翻译"
    assert "nan" not in corpus[0]["raw_text"].lower()
    assert corpus[0]["year"] == 1949
    assert corpus[0]["institution"] == "Produits Chim Terres Rares Soc"
    assert corpus[0]["author"] == "Trombe Felix"
    assert corpus[0]["country_or_region"] == "法国"
    assert corpus[0]["category_or_tag"] == "C22B59/00"


def test_import_files_normalizes_unmapped_timestamp_metadata_for_json_storage(scratch_dir):
    xlsx_path = scratch_dir / "timestamp-metadata.xlsx"
    pd.DataFrame(
        [
            {
                "title": "带时间元数据的记录",
                "abstract": "需要确保未映射日期列也能安全写入项目。",
                "published": pd.Timestamp("2024-03-15 09:30:00"),
                "reviewed_at": pd.Timestamp("2024-04-01 18:45:00"),
            }
        ]
    ).to_excel(xlsx_path, index=False)

    template = default_import_template()
    template["field_mappings"] = [
        {"source_field": "title", "target_field": "title"},
        {"source_field": "abstract", "target_field": "raw_text"},
    ]

    corpus, source_files, validation_issues = import_files([xlsx_path], template)

    assert len(corpus) == 1
    assert len(source_files) == 1
    assert validation_issues == []
    assert corpus[0]["extra_metadata"]["published"] == "2024-03-15T09:30:00"
    assert corpus[0]["extra_metadata"]["reviewed_at"] == "2024-04-01T18:45:00"


def test_wos_import_template_maps_title_abstract_keywords_and_metadata(scratch_dir):
    path = scratch_dir / "wos.csv"
    path.write_text(
        "UT,TI,AB,DE,ID,AU,C1,PY,SO,WC,DT,DOI\n"
        "WOS:1,Rare earth recycling,Recovery of dysprosium.,rare earth; recycling,critical materials,Li; Wang,University A,2024,Journal A,Materials Science,Article,10.1/demo\n",
        encoding="utf-8-sig",
    )

    corpus, _sources, issues = import_files([path], default_import_template("wos"))

    assert issues == []
    assert corpus[0]["doc_id"] == "WOS:1"
    assert corpus[0]["raw_text"] == "Rare earth recycling\n\nRecovery of dysprosium.\n\nrare earth; recycling\n\ncritical materials"
    assert corpus[0]["author"] == "Li; Wang"
    assert corpus[0]["institution"] == "University A"
    assert corpus[0]["year"] == 2024
    assert corpus[0]["category_or_tag"] == "Materials Science"
    assert corpus[0]["extra_metadata"]["DOI"] == "10.1/demo"


def test_wos_import_template_maps_full_export_headers(scratch_dir):
    path = scratch_dir / "wos-full-export.csv"
    path.write_text(
        "UT (Unique WOS ID),Article Title,Abstract,Author Keywords,Keywords Plus,Authors,Addresses,Publication Year,Source Title,WoS Categories,Document Type,DOI\n"
        "WOS:0001,Rare earth partitioning,Partitioning text.,rare earth; partitioning,elements,Chi R,\"Wuhan Inst; Tsinghua Univ\",2005,Rare Metals,Materials Science,Article,10.3/demo\n",
        encoding="utf-8-sig",
    )

    corpus, _sources, issues = import_files([path], default_import_template("wos"))

    assert issues == []
    assert corpus[0]["doc_id"] == "WOS:0001"
    assert corpus[0]["title"] == "Rare earth partitioning"
    assert corpus[0]["raw_text"] == "Rare earth partitioning\n\nPartitioning text.\n\nrare earth; partitioning\n\nelements"
    assert corpus[0]["author"] == "Chi R"
    assert corpus[0]["institution"] == "Wuhan Inst; Tsinghua Univ"
    assert corpus[0]["year"] == 2005
    assert corpus[0]["source"] == "Rare Metals"
    assert corpus[0]["category_or_tag"] == "Materials Science"


def test_scopus_import_template_maps_common_export_headers(scratch_dir):
    path = scratch_dir / "scopus.csv"
    path.write_text(
        "EID,Title,Abstract,Author Keywords,Index Keywords,Authors,Affiliations,Year,Source title,DOI,Subject area,Document Type\n"
        "2-s2.0-1,Rare earth separation,Separation process text.,rare earth; separation,critical material,Smith J,Institute B,2023,Source B,10.2/demo,Chemistry,Article\n",
        encoding="utf-8-sig",
    )

    corpus, _sources, issues = import_files([path], default_import_template("scopus"))

    assert issues == []
    assert corpus[0]["doc_id"] == "2-s2.0-1"
    assert "rare earth; separation" in corpus[0]["raw_text"]
    assert corpus[0]["source_profile"] == "scopus"


def test_dataframe_from_source_routes_legacy_xls_to_read_excel(monkeypatch, scratch_dir):
    xls_path = scratch_dir / "legacy-wos.xls"
    xls_path.write_bytes(b"placeholder")
    calls = []

    def fake_read_excel(path, *args, **kwargs):
        calls.append(path)
        return pd.DataFrame([{"UT": "WOS:1", "TI": "Title", "AB": "Abstract"}])

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    frame = dataframe_from_source(xls_path)

    assert calls == [xls_path]
    assert frame.loc[0, "UT"] == "WOS:1"
