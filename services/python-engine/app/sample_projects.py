from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

from .defaults import default_import_template, make_dictionary_entry
from .ingestion import import_files
from .project_store import create_project, save_project

FIRST_BUILTIN_SAMPLE_PROJECT_NAME = "示例项目 - 学术摘要机构主题"


def _sms_rows() -> list[dict[str, Any]]:
    texts = [
        ("ham", "Go until jurong point, crazy.. Available only in bugis n great world la e buffet... Cine there got amore wat..."),
        ("ham", "Nah I don't think he goes to usf, he lives around here though"),
        ("ham", "As per your request 'Melle Melle' has been set as your callertune for all callers. Press *9 to copy your friends callertune."),
        ("ham", "I'm gonna be home soon and I don't want to talk about this stuff anymore tonight, k? I've cried enough today."),
        ("spam", "Free entry in 2 a weekly comp to win FA Cup final tickets. Text FA to 87121 to receive entry question. T&C's apply."),
        ("spam", "WINNER!! As a valued network customer you have been selected to receive a £900 prize reward. To claim call 09061701461."),
        ("spam", "Had your mobile 11 months or more? You are entitled to update to the latest colour mobiles with camera for free."),
        ("spam", "URGENT! You have won a 1 week free membership in our £100,000 prize jackpot. Txt the word CLAIM to 81010 now."),
    ]
    rows: list[dict[str, Any]] = []
    for index, (label, text) in enumerate(texts, start=1):
        rows.append(
            {
                "doc_id": f"SMS-{index:03d}",
                "title": f"{label.upper()} message {index}",
                "raw_text": text,
                "source": "SMS Spam Collection",
                "category_or_tag": label,
                "keyword_field": label,
                "year": 2012 if label == "ham" else 2011,
            }
        )
    return rows


def _newsgroups_rows() -> list[dict[str, Any]]:
    return [
        {
            "doc_id": "NEWS-001",
            "title": "Re: Please Recommend 3D Graphics Library For Mac.",
            "raw_text": "I too would like a 3D graphics library. How much do C libraries cost anyway? Can you get the tools used by RenderMan at a reasonable cost? Sorry that I do not have answers, only more questions about practical graphics tooling.",
            "source": "20 Newsgroups",
            "category_or_tag": "comp.graphics",
            "keyword_field": "3d graphics; library",
            "year": 1993,
        },
        {
            "doc_id": "NEWS-002",
            "title": "Fast wireframe graphics",
            "raw_text": "I am working on a program to display 3D wireframe models while the user changes viewing parameters. I am considering the SRGP package, but I wonder whether there is another public-domain graphics package that would be faster for real-time performance on a Sun IPX.",
            "source": "20 Newsgroups",
            "category_or_tag": "comp.graphics",
            "keyword_field": "wireframe; realtime rendering",
            "year": 1993,
        },
        {
            "doc_id": "NEWS-003",
            "title": "Closed-curve intersection",
            "raw_text": "I would like a reference to an algorithm that can detect whether one closed curve bounded by Bezier curves lies completely within another closed curve bounded by Bezier curves. Any reliable computational geometry references would help.",
            "source": "20 Newsgroups",
            "category_or_tag": "comp.graphics",
            "keyword_field": "bezier curves; computational geometry",
            "year": 1993,
        },
        {
            "doc_id": "NEWS-004",
            "title": "Re: Toyota wagons",
            "raw_text": "Toyota has cornered the market on ugly station wagons. After seeing the new Camry sedan, I had thought Toyota would finally turn out something nicer looking, but the new wagon still looks awkward and overly bulky.",
            "source": "20 Newsgroups",
            "category_or_tag": "rec.autos",
            "keyword_field": "toyota; station wagon",
            "year": 1993,
        },
        {
            "doc_id": "NEWS-005",
            "title": "water in trunk of 89 Probe??",
            "raw_text": "Water gradually builds up in the trunk of my friend's 89 Ford Probe after a good thunderstorm. Is this a common problem, and where are the drain holes located for the hatch? We keep having to remove the spare and scoop out the water.",
            "source": "20 Newsgroups",
            "category_or_tag": "rec.autos",
            "keyword_field": "ford probe; maintenance",
            "year": 1993,
        },
        {
            "doc_id": "NEWS-006",
            "title": "Re: Dumbest automotive concepts of all time",
            "raw_text": "Wasn't the original intent of reverse lights to help the driver see while backing up? Side-mounted reverse lights may help other drivers notice movement, but I doubt warning nearby cars was their original purpose.",
            "source": "20 Newsgroups",
            "category_or_tag": "rec.autos",
            "keyword_field": "reverse lights; automotive design",
            "year": 1993,
        },
        {
            "doc_id": "NEWS-007",
            "title": "Re: Abyss: breathing fluids",
            "raw_text": "Could you use some sort of mechanical chest compression as an aid? Something like a portable iron lung might support breathing under unusual pressure conditions. In space, you already have to trust your suit anyway.",
            "source": "20 Newsgroups",
            "category_or_tag": "sci.space",
            "keyword_field": "breathing fluids; spacesuit",
            "year": 1993,
        },
        {
            "doc_id": "NEWS-008",
            "title": "Re: Shuttle Launch Question",
            "raw_text": "My understanding is that the expected errors are basically known bugs in the warning software. Rather than fix the code and risk new bugs, crews are told to ignore a few specific warning numbers before liftoff.",
            "source": "20 Newsgroups",
            "category_or_tag": "sci.space",
            "keyword_field": "shuttle launch; warning system",
            "year": 1993,
        },
        {
            "doc_id": "NEWS-009",
            "title": "Looking for a little research help",
            "raw_text": "I am writing a science fiction script and looking for help on questions regarding the Moon and Earth. I want the story to stay as scientifically accurate as possible instead of ignoring the basic facts about computers and orbital mechanics.",
            "source": "20 Newsgroups",
            "category_or_tag": "sci.space",
            "keyword_field": "science fiction; moon research",
            "year": 1993,
        },
    ]


def _openalex_rows() -> list[dict[str, Any]]:
    return [
        {
            "doc_id": "OA-001",
            "title": "Exploring students’ perspectives on Generative AI-assisted academic writing",
            "abstract": "The rapid development of generative artificial intelligence and large language models has reshaped academic writing support. This study examines opportunities and challenges of AI-assisted writing in higher education and argues that institutions must balance learning benefits, transparency, and integrity safeguards.",
            "source": "Education and Information Technologies",
            "institution": "Old Dominion University",
            "keyword_field": "generative ai; academic writing; higher education",
            "category_or_tag": "genai_writing",
            "year": 2024,
        },
        {
            "doc_id": "OA-002",
            "title": "The importance of transparency: Declaring the use of generative artificial intelligence in academic writing",
            "abstract": "Generative AI tools such as ChatGPT and Bard are increasingly used in research writing. This article reviews journal policies and shows that disclosure rules remain uneven, making transparency declarations an important governance requirement for academic publishing.",
            "source": "Journal of Nursing Scholarship",
            "institution": "RMIT Vietnam",
            "keyword_field": "generative ai; transparency; journal policy",
            "category_or_tag": "genai_writing",
            "year": 2023,
        },
        {
            "doc_id": "OA-003",
            "title": "Addressing the use of generative AI in academic writing",
            "abstract": "The rise of generative AI has been a disruptive force in academia. This paper discusses how students may rely on AI systems to complete writing tasks and reports an active learning intervention that helps learners critique, supervise, and responsibly use AI-generated text.",
            "source": "Computers and Education Artificial Intelligence",
            "institution": "Agder Research",
            "keyword_field": "generative ai; student learning; academic writing",
            "category_or_tag": "genai_writing",
            "year": 2024,
        },
        {
            "doc_id": "OA-004",
            "title": "Advancing Students’ Academic Excellence in Distance Education: Exploring the Potential of Generative AI Integration",
            "abstract": "This qualitative study explores how generative AI can improve academic writing skills in distance education. The findings emphasize human-AI collaboration, teaching design, and scaffolding strategies that can raise writing quality while preserving student agency.",
            "source": "Open Praxis",
            "institution": "University of South Africa",
            "keyword_field": "distance education; generative ai; writing support",
            "category_or_tag": "genai_writing",
            "year": 2024,
        },
        {
            "doc_id": "OA-005",
            "title": "Recycling of Lithium-Ion Batteries—Current State of the Art, Circular Economy, and Next Generation Recycling",
            "abstract": "Lithium-ion batteries have become a dominant energy storage technology, and their large-scale use makes recycling essential. This review analyses the current state of recycling technology, circular economy constraints, and the need to adapt processes to future cell chemistries.",
            "source": "Advanced Energy Materials",
            "institution": "University of Münster",
            "keyword_field": "lithium ion batteries; recycling; circular economy",
            "category_or_tag": "battery_recycling",
            "year": 2022,
        },
        {
            "doc_id": "OA-006",
            "title": "A Mini-Review on Metal Recycling from Spent Lithium Ion Batteries",
            "abstract": "The rapid growth of lithium ion batteries in electronics and electric vehicles has increased the amount of hazardous waste and valuable metals entering end-of-life streams. This review compares pyrometallurgy, hydrometallurgy, and related pretreatment approaches for efficient metal recovery.",
            "source": "Engineering",
            "institution": "Institute of Process Engineering",
            "keyword_field": "metal recycling; hydrometallurgy; spent batteries",
            "category_or_tag": "battery_recycling",
            "year": 2018,
        },
        {
            "doc_id": "OA-007",
            "title": "The future of automotive lithium-ion battery recycling: Charting a sustainable course",
            "abstract": "This paper looks beyond near-term electric vehicle growth to the period when large volumes of end-of-life batteries require treatment. It argues that coordinated technical, economic, and institutional planning is needed now to ensure lithium-ion battery recycling becomes commercially and environmentally sustainable.",
            "source": "Sustainable Materials and Technologies",
            "institution": "Argonne National Laboratory",
            "keyword_field": "automotive batteries; sustainable recycling; electric vehicles",
            "category_or_tag": "battery_recycling",
            "year": 2014,
        },
        {
            "doc_id": "OA-008",
            "title": "Progresses in Sustainable Recycling Technology of Spent Lithium-Ion Batteries",
            "abstract": "The increasing number of lithium-ion batteries creates environmental and safety pressures if waste is not properly managed. This review discusses why recycling is essential for sustainable development and compares major technologies for recycling and reusing spent batteries.",
            "source": "Energy & Environment Materials",
            "institution": "Northeast Normal University",
            "keyword_field": "sustainable recycling; battery waste; reuse",
            "category_or_tag": "battery_recycling",
            "year": 2021,
        },
    ]


BUILTIN_SAMPLE_PROJECTS: list[dict[str, Any]] = [
    {
        "slug": "sample-openalex-institutions",
        "name": FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
        "description": "开源数据集示例：基于 OpenAlex 小样本的学术摘要机构主题分析，适合查看特征词、关键词聚类、机构关键词与机构主题。",
        "source_profile": "literature",
        "source_filename": "openalex_institution_topics.csv",
        "rows": _openalex_rows(),
        "workflow_name": "学术摘要机构主题流",
        "import_template_overrides": {},
        "keep_node_types": {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "term_year_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "save_xlsx",
            "save_png",
            "save_html_report",
        },
        "node_config_overrides": {
            "feature_term_selection": {"feature_term_count": 120},
            "keyword_clustering": {"keyword_cluster_k": 2, "topic_model_k": 2},
            "institution_topic_analysis": {"topic_model_k": 2},
            "save_html_report": {"include_audit": True},
        },
        "dictionary_terms": {
            "phrase_lexicon": [
                ("generative ai", "generative_ai"),
                ("academic writing", "academic_writing"),
                ("lithium ion batteries", "lithium_ion_batteries"),
                ("battery recycling", "battery_recycling"),
                ("circular economy", "circular_economy"),
            ],
        },
        "dataset": {
            "name": "OpenAlex API subset",
            "url": "https://api.openalex.org/",
            "license": "CC0 / No Rights Reserved",
        },
    },
    {
        "slug": "sample-newsgroups-topics",
        "name": "示例项目 - 新闻组主题聚类",
        "description": "开源数据集示例：基于 20 Newsgroups 小样本的主题聚类与文档聚类，适合查看关键词聚类、文档散点与导出图表。",
        "source_profile": "generic",
        "source_filename": "twenty_newsgroups_topics.csv",
        "rows": _newsgroups_rows(),
        "workflow_name": "新闻组主题聚类流",
        "import_template_overrides": {
            "text_build": {"mode": "concat_fields", "fields": ["title", "raw_text"], "delimiter": "\n\n", "skip_empty": True},
        },
        "keep_node_types": {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "document_clustering",
            "save_csv",
            "save_png",
            "save_html_report",
        },
        "node_config_overrides": {
            "feature_term_selection": {"feature_term_count": 150},
            "keyword_clustering": {"keyword_cluster_k": 3, "topic_model_k": 3},
            "document_clustering": {"document_cluster_k": 3},
        },
        "dictionary_terms": {
            "phrase_lexicon": [
                ("3d graphics", "3d_graphics"),
                ("wireframe models", "wireframe_models"),
                ("space shuttle", "space_shuttle"),
            ],
        },
        "dataset": {
            "name": "20 Newsgroups subset",
            "url": "https://archive.ics.uci.edu/dataset/113/twenty+newsgroups",
            "license": "CC BY 4.0",
        },
    },
    {
        "slug": "sample-sms-cooccurrence",
        "name": "示例项目 - 短信词频与共现",
        "description": "开源数据集示例：基于 UCI SMS Spam Collection 小样本的词频、共现和导出流程，适合快速理解短文本工作流。",
        "source_profile": "generic",
        "source_filename": "sms_spam_collection.csv",
        "rows": _sms_rows(),
        "workflow_name": "短信词频共现流",
        "import_template_overrides": {
            "text_build": {"mode": "concat_fields", "fields": ["title", "raw_text"], "delimiter": "\n\n", "skip_empty": True},
        },
        "keep_node_types": {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "cooccurrence_analysis",
            "keyword_extraction",
            "save_csv",
            "save_png",
            "save_html_report",
        },
        "node_config_overrides": {
            "cooccurrence_analysis": {"cooccurrence_window": 3, "min_cooccurrence": 1},
            "keyword_extraction": {"top_k_per_doc": 5, "top_k_project": 40},
        },
        "dictionary_terms": {
            "phrase_lexicon": [
                ("claim code", "claim_code"),
                ("free membership", "free_membership"),
                ("prize reward", "prize_reward"),
            ],
        },
        "dataset": {
            "name": "SMS Spam Collection",
            "url": "https://archive.ics.uci.edu/dataset/228/sms+spam+collection",
            "license": "Research / public corpus aggregation",
        },
    },
]


def _append_dictionary_terms(manifest: dict[str, Any], dictionary_terms: dict[str, list[tuple[str, str | None]]]) -> None:
    for kind, rows in dictionary_terms.items():
        sheet = manifest["dictionary_set"]["sheets"].get(kind)
        if not isinstance(sheet, dict):
            continue
        existing_sources = {str(entry.get("source") or "").casefold() for entry in sheet.get("entries", [])}
        for source, target in rows:
            if str(source).casefold() in existing_sources:
                continue
            sheet["entries"].append(make_dictionary_entry(source, target, 0))


def _configure_workflow(manifest: dict[str, Any], *, workflow_name: str, keep_node_types: set[str], node_config_overrides: dict[str, dict[str, Any]]) -> None:
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    workflow["name"] = workflow_name
    workflow["nodes"] = [node for node in workflow["nodes"] if node.get("node_type") in keep_node_types]
    kept_node_ids = {str(node["node_id"]) for node in workflow["nodes"]}
    workflow["edges"] = [
        edge
        for edge in workflow["edges"]
        if str(edge.get("from_node")) in kept_node_ids and str(edge.get("to_node")) in kept_node_ids
    ]
    for node in workflow["nodes"]:
        patch = node_config_overrides.get(str(node.get("node_type")))
        if patch:
            node["config"] = {**dict(node.get("config") or {}), **patch}


def _write_sample_source(project_dir: Path, source_filename: str, rows: list[dict[str, Any]]) -> Path:
    seed_dir = project_dir / "metadata" / "sample_seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    source_path = seed_dir / source_filename
    pd.DataFrame(rows).to_csv(source_path, index=False, encoding="utf-8-sig")
    return source_path


def create_builtin_sample_projects() -> list[tuple[Path, dict[str, Any]]]:
    created: list[tuple[Path, dict[str, Any]]] = []

    for spec in BUILTIN_SAMPLE_PROJECTS:
        project_dir, manifest = create_project(str(spec["name"]), str(spec["description"]))
        manifest["import_template"] = default_import_template(str(spec["source_profile"]))
        manifest["import_template"] = {
            **manifest["import_template"],
            **dict(spec.get("import_template_overrides") or {}),
        }
        manifest.setdefault("settings", {})
        manifest["settings"]["sample_project"] = deepcopy(spec["dataset"])
        manifest["settings"]["sample_project"]["slug"] = spec["slug"]
        manifest["settings"]["sample_project"]["workflow_name"] = spec["workflow_name"]
        _append_dictionary_terms(manifest, dict(spec.get("dictionary_terms") or {}))
        _configure_workflow(
            manifest,
            workflow_name=str(spec["workflow_name"]),
            keep_node_types=set(spec["keep_node_types"]),
            node_config_overrides=dict(spec.get("node_config_overrides") or {}),
        )

        source_path = _write_sample_source(project_dir, str(spec["source_filename"]), list(spec["rows"]))
        corpus, source_files, _issues = import_files([source_path], manifest["import_template"], project_dir=project_dir)
        manifest["source_files"] = source_files
        save_project(project_dir, manifest, corpus)
        created.append((project_dir, manifest))

    return created
