from __future__ import annotations

PROJECT_FILENAME = "project.json"
PROJECT_DATABASE_FILENAME = "project.db"
CORPUS_FILENAME = "metadata/corpus.json"
CORPUS_VIEWS_FILENAME = "metadata/corpus_views.json"
INGESTION_SPECS_FILENAME = "metadata/ingestion_specs.json"
WORKSPACE_FILENAME = "workspace.json"
WORKSPACE_ENV_VAR = "TEXTFLOW_WORKSPACE_ROOT"
PROJECT_TEMPLATES_DIRNAME = "project_templates"
IMPORT_TEMPLATES_DIRNAME = "import_templates"
PROJECT_PACKAGE_EXTENSION = ".tfproj"
RESULT_PREVIEW_DEFAULT_LIMIT = 500
RESULT_PREVIEW_LIMITS = {
    "audit_table": 100,
}
PERSISTED_CORPUS_FIELDS = (
    "id",
    "doc_id",
    "source_profile",
    "language",
    "title",
    "raw_text",
    "year",
    "source",
    "author",
    "institution",
    "country_or_region",
    "category_or_tag",
    "keyword_field",
    "extra_metadata",
    "status",
    "raw_hash",
)
