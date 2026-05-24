from __future__ import annotations

from copy import deepcopy
from typing import Any

def profile_import_template(source_profile: str) -> dict[str, Any]:
    templates: dict[str, dict[str, Any]] = {
        "generic": {
            "name": "通用导入模板",
            "description": "适合 txt/csv/xlsx/json 的通用结构化文本导入。",
            "field_mappings": [
                {"source_field": "doc_id", "target_field": "doc_id", "required": False, "aliases": ["id", "document_id"]},
                {"source_field": "title", "target_field": "title", "required": False, "aliases": ["name", "subject"]},
                {"source_field": "abstract", "target_field": "raw_text", "required": False, "aliases": ["raw_text", "content", "text", "summary"]},
                {"source_field": "year", "target_field": "year", "required": False, "aliases": ["published", "publication_year"]},
                {"source_field": "source", "target_field": "source", "required": False, "aliases": ["journal", "origin"]},
                {"source_field": "author", "target_field": "author", "required": False, "aliases": ["authors", "creator"]},
                {"source_field": "institution", "target_field": "institution", "required": False, "aliases": ["org", "organization", "affiliation"]},
                {"source_field": "country_or_region", "target_field": "country_or_region", "required": False, "aliases": ["country", "region"]},
                {"source_field": "category_or_tag", "target_field": "category_or_tag", "required": False, "aliases": ["category", "tag"]},
                {"source_field": "keyword_field", "target_field": "keyword_field", "required": False, "aliases": ["keywords", "keyword"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["title", "abstract"], "delimiter": "\n\n", "skip_empty": True},
        },
        "literature": {
            "name": "文献导入模板",
            "description": "面向论文、报告和综述等文献数据。",
            "field_mappings": [
                {"source_field": "title", "target_field": "title", "required": True, "aliases": ["Title", "article_title"]},
                {"source_field": "abstract", "target_field": "raw_text", "required": True, "aliases": ["Abstract", "summary"]},
                {"source_field": "year", "target_field": "year", "required": False, "aliases": ["PY", "published", "publication_year"]},
                {"source_field": "source", "target_field": "source", "required": False, "aliases": ["journal", "SO"]},
                {"source_field": "author", "target_field": "author", "required": False, "aliases": ["authors", "AU"]},
                {"source_field": "institution", "target_field": "institution", "required": False, "aliases": ["org", "affiliation", "C1"]},
                {"source_field": "keyword_field", "target_field": "keyword_field", "required": False, "aliases": ["keywords", "DE"]},
                {"source_field": "category_or_tag", "target_field": "category_or_tag", "required": False, "aliases": ["category", "WC"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["title", "abstract"], "delimiter": "\n\n", "skip_empty": True},
        },
        "wos": {
            "name": "Web of Science 模板",
            "description": "预置 WoS 常见字段别名和主文本拼接策略。",
            "field_mappings": [
                {"source_field": "UT", "target_field": "doc_id", "required": True, "aliases": ["Accession Number", "UT (Unique WOS ID)"]},
                {"source_field": "TI", "target_field": "title", "required": True, "aliases": ["Article Title"]},
                {"source_field": "AB", "target_field": "raw_text", "required": True, "aliases": ["Abstract"]},
                {"source_field": "PY", "target_field": "year", "required": False, "aliases": ["Published Year", "Publication Year"]},
                {"source_field": "SO", "target_field": "source", "required": False, "aliases": ["Publication Name", "Source Title"]},
                {"source_field": "AU", "target_field": "author", "required": False, "aliases": ["Authors"]},
                {"source_field": "C1", "target_field": "institution", "required": False, "aliases": ["Addresses", "Affiliations"]},
                {"source_field": "DE", "target_field": "keyword_field", "required": False, "aliases": ["Author Keywords"]},
                {"source_field": "ID", "target_field": "keyword_field", "required": False, "aliases": ["Keywords Plus"]},
                {"source_field": "WC", "target_field": "category_or_tag", "required": False, "aliases": ["Web of Science Categories", "WoS Categories"]},
                {"source_field": "DOI", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "DT", "target_field": "extra_metadata", "required": False, "aliases": ["Document Type"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["TI", "AB", "DE", "ID"], "delimiter": "\n\n", "skip_empty": True},
        },
        "scopus": {
            "name": "Scopus 模板",
            "description": "预置 Scopus 常见字段别名和主文本拼接策略。",
            "field_mappings": [
                {"source_field": "EID", "target_field": "doc_id", "required": True, "aliases": ["EID"]},
                {"source_field": "Title", "target_field": "title", "required": True, "aliases": ["Article Title"]},
                {"source_field": "Abstract", "target_field": "raw_text", "required": True, "aliases": ["abstract"]},
                {"source_field": "Year", "target_field": "year", "required": False, "aliases": ["Publication Year"]},
                {"source_field": "Source title", "target_field": "source", "required": False, "aliases": ["Journal"]},
                {"source_field": "Authors", "target_field": "author", "required": False, "aliases": ["Author full names"]},
                {"source_field": "Affiliations", "target_field": "institution", "required": False, "aliases": ["Author affiliations"]},
                {"source_field": "Author Keywords", "target_field": "keyword_field", "required": False, "aliases": ["Index Keywords"]},
                {"source_field": "Index Keywords", "target_field": "keyword_field", "required": False, "aliases": ["Author Keywords"]},
                {"source_field": "Subject area", "target_field": "category_or_tag", "required": False, "aliases": ["Subject areas"]},
                {"source_field": "DOI", "target_field": "extra_metadata", "required": False, "aliases": []},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["Title", "Abstract", "Author Keywords", "Index Keywords"], "delimiter": "\n\n", "skip_empty": True},
        },
        "patent": {
            "name": "专利导入模板",
            "description": "适合公开文本、摘要、申请人和 IPC/主题字段。",
            "field_mappings": [
                {"source_field": "publication_number", "target_field": "doc_id", "required": True, "aliases": ["pn", "patent_no", "公开（公告）号"]},
                {"source_field": "title", "target_field": "title", "required": True, "aliases": ["invention_title", "标题", "专利名称"]},
                {"source_field": "abstract", "target_field": "raw_text", "required": True, "aliases": ["摘要", "abstract_text"]},
                {"source_field": "publication_year", "target_field": "year", "required": False, "aliases": ["year", "公开（公告）日"]},
                {"source_field": "applicant", "target_field": "institution", "required": False, "aliases": ["assignee", "申请人"]},
                {"source_field": "inventor", "target_field": "author", "required": False, "aliases": ["发明人"]},
                {"source_field": "ipc", "target_field": "category_or_tag", "required": False, "aliases": ["IPC", "IPC分类号"]},
                {"source_field": "keywords", "target_field": "keyword_field", "required": False, "aliases": ["主题词"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["title", "abstract", "keywords"], "delimiter": "\n\n", "skip_empty": True},
        },
        "incopat": {
            "name": "IncoPat 模板",
            "description": "预置 IncoPat 常见中文字段名与别名。",
            "field_mappings": [
                {"source_field": "公开（公告）号", "target_field": "doc_id", "required": True, "aliases": ["公开(公告)号", "申请号", "专利号", "公开号", "授权公告号", "首次公开号"]},
                {"source_field": "标题 (中文)", "target_field": "title", "required": True, "aliases": ["标题（中文）", "标题(中文)", "标题", "专利名称", "标题 (英文)", "标题（英文）", "标题(英文)", "标题（小语种原文）"]},
                {"source_field": "摘要 (中文)", "target_field": "raw_text", "required": True, "aliases": ["摘要（中文）", "摘要(中文)", "摘要", "摘要 (英文)", "摘要（英文）", "摘要(英文)", "摘要（小语种原文）", "首权翻译", "首项权利要求", "独立权利要求", "简介"]},
                {"source_field": "公开（公告）日", "target_field": "year", "required": False, "aliases": ["公开(公告)日", "申请日", "优先权日", "最早优先权日", "年份", "首次公开日", "授权公告日"]},
                {"source_field": "申请人", "target_field": "institution", "required": False, "aliases": ["标准化申请人", "当前权利人", "标准化当前权利人", "第一申请人", "专利权人", "申请人(翻译)", "申请人（翻译）"]},
                {"source_field": "发明人", "target_field": "author", "required": False, "aliases": ["第一发明(设计)人", "第一发明（设计）人", "发明(设计)人(其他)", "发明（设计）人（其他）", "Inventor"]},
                {"source_field": "公开国别", "target_field": "country_or_region", "required": False, "aliases": ["申请人国家/地区", "优先权国别", "同族国家/地区"]},
                {"source_field": "IPC", "target_field": "category_or_tag", "required": False, "aliases": ["IPC分类号", "IPC主分类-小组", "CPC"]},
                {"source_field": "技术功效短语", "target_field": "keyword_field", "required": False, "aliases": ["技术功效句", "用途", "关键词", "主题词"]},
                {"source_field": "引证专利", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "被引证专利", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "被引证次数", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "引证次数", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "技术功效1级", "target_field": "extra_metadata", "required": False, "aliases": ["技术功效2级", "技术功效3级"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["标题 (中文)", "标题 (英文)", "摘要 (中文)", "摘要 (英文)", "首权翻译", "首项权利要求", "独立权利要求", "技术功效句", "技术功效短语", "用途"], "delimiter": "\n\n", "skip_empty": True},
        },
        "business_reserved": {
            "name": "商业数据模板",
            "description": "预留给后续商业数据/行业报告导入。",
            "field_mappings": [
                {"source_field": "record_id", "target_field": "doc_id", "required": False, "aliases": ["id"]},
                {"source_field": "title", "target_field": "title", "required": True, "aliases": ["subject"]},
                {"source_field": "content", "target_field": "raw_text", "required": True, "aliases": ["raw_text", "text"]},
                {"source_field": "year", "target_field": "year", "required": False, "aliases": ["published_year"]},
                {"source_field": "company", "target_field": "institution", "required": False, "aliases": ["institution", "organization"]},
                {"source_field": "topic", "target_field": "category_or_tag", "required": False, "aliases": ["category"]},
                {"source_field": "keywords", "target_field": "keyword_field", "required": False, "aliases": ["tags"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["title", "content"], "delimiter": "\n\n", "skip_empty": True},
        },
    }
    return deepcopy(templates.get(source_profile, templates["generic"]))

def default_import_template(source_profile: str = "generic") -> dict[str, Any]:
    template = profile_import_template(source_profile)
    return {"id": f"template-{source_profile}", "source_profile": source_profile, **template}
