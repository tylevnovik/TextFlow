#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::fs;
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

use reqwest::Client;
use rfd::FileDialog;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{Emitter, Manager};
use tokio::time::sleep;

#[derive(Debug, Deserialize)]
struct CreateProjectInput {
    name: String,
    description: String,
}

#[derive(Debug, Deserialize)]
struct DuplicateProjectInput {
    project_id: String,
    name: Option<String>,
}

#[derive(Default)]
struct EngineState {
    inner: Mutex<Option<EngineProcess>>,
}

struct EngineProcess {
    child: Child,
    base_url: String,
}

#[derive(Debug, Deserialize)]
struct TaskTicket {
    task_id: String,
}

#[derive(Debug, Deserialize)]
struct TaskSnapshot {
    action: String,
    status: String,
    progress: f64,
    message: String,
    detail: Option<Value>,
    result: Option<Value>,
    error: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct EngineProgressEvent {
    action: String,
    status: String,
    progress: f64,
    message: String,
    detail: Option<Value>,
}

fn workspace_root_from_manifest_dir(manifest_dir: &Path) -> Result<PathBuf, String> {
    manifest_dir
        .ancestors()
        .nth(3)
        .map(Path::to_path_buf)
        .ok_or_else(|| format!("failed to resolve workspace root from {}", manifest_dir.display()))
}

fn workspace_root() -> Result<PathBuf, String> {
    workspace_root_from_manifest_dir(Path::new(env!("CARGO_MANIFEST_DIR")))
}

fn engine_dir() -> Result<PathBuf, String> {
    Ok(workspace_root()?.join("services").join("python-engine"))
}

fn dev_sidecar_path() -> Result<PathBuf, String> {
    let dist_dir = engine_dir()?.join("dist");
    let onedir_path = dist_dir.join("textflow-engine").join("textflow-engine.exe");
    if onedir_path.exists() {
        return Ok(onedir_path);
    }
    Ok(dist_dir.join("textflow-engine.exe"))
}

fn venv_python_path() -> Result<PathBuf, String> {
    Ok(engine_dir()?.join(".venv").join("Scripts").join("python.exe"))
}

#[cfg(test)]
fn find_named_file(root: &Path, file_name: &str) -> Option<PathBuf> {
    let entries = fs::read_dir(root).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_file()
            && path
                .file_name()
                .and_then(|value| value.to_str())
                .map(|value| value.eq_ignore_ascii_case(file_name))
                .unwrap_or(false)
        {
            return Some(path);
        }

        if path.is_dir() {
            if let Some(found) = find_named_file(&path, file_name) {
                return Some(found);
            }
        }
    }
    None
}

fn collect_named_files(root: &Path, file_name: &str, results: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_file()
            && path
                .file_name()
                .and_then(|value| value.to_str())
                .map(|value| value.eq_ignore_ascii_case(file_name))
                .unwrap_or(false)
        {
            results.push(path.clone());
        }

        if path.is_dir() {
            collect_named_files(&path, file_name, results);
        }
    }
}

fn sidecar_candidate_score(path: &Path) -> usize {
    let mut score = 0;
    if path
        .parent()
        .and_then(|parent| parent.file_name())
        .and_then(|value| value.to_str())
        .map(|value| value.eq_ignore_ascii_case("textflow-engine"))
        .unwrap_or(false)
    {
        score += 10;
    }
    if path.to_string_lossy().contains("services") {
        score += 3;
    }
    score + path.components().count()
}

fn preferred_sidecar_path(root: &Path) -> Option<PathBuf> {
    let mut candidates = Vec::new();
    collect_named_files(root, "textflow-engine.exe", &mut candidates);
    candidates
        .into_iter()
        .max_by_key(|path| sidecar_candidate_score(path))
}

fn bundled_sidecar_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    if let Ok(resource_dir) = app.path().resource_dir() {
        if let Some(found) = preferred_sidecar_path(&resource_dir) {
            return Some(found);
        }
    }

    if let Ok(exe_path) = env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            if let Some(found) = preferred_sidecar_path(parent) {
                return Some(found);
            }
        }
    }

    None
}

fn app_workspace_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let path = app
        .path()
        .app_local_data_dir()
        .map_err(|error| format!("failed to resolve app workspace dir: {error}"))?;
    fs::create_dir_all(&path).map_err(|error| format!("failed to create app workspace dir: {error}"))?;
    Ok(path)
}

fn reserve_port() -> Result<u16, String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|error| format!("failed to reserve engine port: {error}"))?;
    let port = listener
        .local_addr()
        .map_err(|error| format!("failed to read reserved engine port: {error}"))?
        .port();
    drop(listener);
    Ok(port)
}

fn build_engine_command(app: &tauri::AppHandle, port: u16) -> Result<Command, String> {
    let engine_dir = engine_dir()?;
    let workspace_dir = app_workspace_dir(app)?;
    let matplotlib_cache_dir = workspace_dir.join("cache").join("matplotlib");
    fs::create_dir_all(&matplotlib_cache_dir)
        .map_err(|error| format!("failed to prepare matplotlib cache dir: {error}"))?;
    let dev_sidecar = dev_sidecar_path()?;
    let venv_python = venv_python_path()?;

    let mut command = if cfg!(debug_assertions) && venv_python.exists() {
        let mut command = Command::new(venv_python);
        command
            .current_dir(&engine_dir)
            .arg("main.py")
            .arg("serve")
            .arg("127.0.0.1")
            .arg(port.to_string());
        command
    } else if dev_sidecar.exists() {
        let mut command = Command::new(dev_sidecar);
        command
            .current_dir(&engine_dir)
            .arg("serve")
            .arg("127.0.0.1")
            .arg(port.to_string());
        command
    } else if let Some(sidecar) = bundled_sidecar_path(app).filter(|path| path.exists()) {
        let mut command = Command::new(sidecar);
        command
            .current_dir(&workspace_dir)
            .arg("serve")
            .arg("127.0.0.1")
            .arg(port.to_string());
        command
    } else if venv_python.exists() {
        let mut command = Command::new(venv_python);
        command
            .current_dir(&engine_dir)
            .arg("main.py")
            .arg("serve")
            .arg("127.0.0.1")
            .arg(port.to_string());
        command
    } else {
        let resource_dir = app.path().resource_dir().ok();
        let current_exe = env::current_exe().ok();
        return Err(format!(
            "Python engine unavailable. Checked dev sidecar: {}; bundled resources under: {}; current exe: {}; venv python: {}",
            dev_sidecar.display(),
            resource_dir
                .as_ref()
                .map(|path| path.display().to_string())
                .unwrap_or_else(|| "<unavailable>".to_string()),
            current_exe
                .as_ref()
                .map(|path| path.display().to_string())
                .unwrap_or_else(|| "<unavailable>".to_string()),
            venv_python.display()
        ));
    };

    command
        .env("TEXTFLOW_WORKSPACE_ROOT", workspace_dir)
        .env("MPLCONFIGDIR", matplotlib_cache_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }

    Ok(command)
}

fn process_is_running(process: &mut EngineProcess) -> Result<bool, String> {
    match process
        .child
        .try_wait()
        .map_err(|error| format!("failed to inspect python engine process: {error}"))?
    {
        None => Ok(true),
        Some(_) => Ok(false),
    }
}

fn start_engine_process(app: &tauri::AppHandle) -> Result<EngineProcess, String> {
    let port = reserve_port()?;
    let mut command = build_engine_command(app, port)?;
    let child = command
        .spawn()
        .map_err(|error| format!("failed to start python engine: {error}"))?;
    Ok(EngineProcess {
        child,
        base_url: format!("http://127.0.0.1:{port}"),
    })
}

fn warm_engine_process(app: &tauri::AppHandle, state: &EngineState) -> Result<(), String> {
    let mut guard = state.inner.lock().map_err(|_| "engine state lock poisoned".to_string())?;
    let needs_start = match guard.as_mut() {
        Some(process) => !process_is_running(process)?,
        None => true,
    };

    if !needs_start {
        return Ok(());
    }

    if let Some(mut stale_process) = guard.take() {
        let _ = stale_process.child.kill();
    }
    *guard = Some(start_engine_process(app)?);
    Ok(())
}

async fn wait_for_engine_ready(base_url: &str) -> Result<(), String> {
    let client = Client::new();
    let health_url = format!("{base_url}/health");
    for _ in 0..40 {
        if let Ok(response) = client.get(&health_url).send().await {
            if response.status().is_success() {
                return Ok(());
            }
        }
        sleep(Duration::from_millis(200)).await;
    }
    Err("python engine did not become ready in time".to_string())
}

async fn ensure_engine_ready(app: &tauri::AppHandle, state: &EngineState) -> Result<String, String> {
    warm_engine_process(app, state)?;
    let base_url = {
        let guard = state.inner.lock().map_err(|_| "engine state lock poisoned".to_string())?;
        guard
            .as_ref()
            .map(|process| process.base_url.clone())
            .ok_or_else(|| "python engine is not available".to_string())?
    };
    wait_for_engine_ready(&base_url).await?;
    Ok(base_url)
}

async fn engine_request(
    app: &tauri::AppHandle,
    state: &EngineState,
    action: &str,
    payload: Value,
) -> Result<Value, String> {
    let base_url = ensure_engine_ready(app, state).await?;
    let client = Client::new();
    let ticket = client
        .post(format!("{base_url}/tasks/start"))
        .json(&json!({
            "action": action,
            "payload": payload,
        }))
        .send()
        .await
        .map_err(|error| format!("failed to queue python task: {error}"))?
        .error_for_status()
        .map_err(|error| format!("failed to queue python task: {error}"))?
        .json::<TaskTicket>()
        .await
        .map_err(|error| format!("invalid task ticket from python engine: {error}"))?;

    loop {
        let snapshot = client
            .get(format!("{base_url}/tasks/{}", ticket.task_id))
            .send()
            .await
            .map_err(|error| format!("failed to poll python task: {error}"))?
            .error_for_status()
            .map_err(|error| format!("failed to poll python task: {error}"))?
            .json::<TaskSnapshot>()
            .await
            .map_err(|error| format!("invalid task status from python engine: {error}"))?;

        let event = EngineProgressEvent {
            action: snapshot.action.clone(),
            status: snapshot.status.clone(),
            progress: snapshot.progress,
            message: snapshot.message.clone(),
            detail: snapshot.detail.clone(),
        };
        let _ = app.emit("engine-progress", event);

        match snapshot.status.as_str() {
            "completed" => {
                return snapshot
                    .result
                    .ok_or_else(|| "python task completed without a result payload".to_string())
            }
            "failed" => {
                return Err(snapshot
                    .error
                    .unwrap_or_else(|| "python task failed without details".to_string()))
            }
            _ => sleep(Duration::from_millis(300)).await,
        }
    }
}

fn shutdown_engine_process(state: &EngineState) {
    if let Ok(mut guard) = state.inner.lock() {
        if let Some(mut process) = guard.take() {
            let _ = process.child.kill();
            let _ = process.child.wait();
        }
    }
}

fn open_path_with_default_app(path: &Path) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        let mut command = if path.is_dir() {
            let mut cmd = Command::new("explorer");
            cmd.arg(path);
            cmd
        } else {
            let mut cmd = Command::new("cmd");
            cmd.arg("/C").arg("start").arg("").arg(path);
            cmd.creation_flags(0x08000000);
            cmd
        };
        command
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("failed to open path {}: {}", path.display(), error))
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(path)
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("failed to open path {}: {}", path.display(), error))
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        Command::new("xdg-open")
            .arg(path)
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("failed to open path {}: {}", path.display(), error))
    }
}

fn reveal_path_in_file_manager(path: &Path) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        if path.is_dir() {
            return Command::new("explorer")
                .arg(path)
                .spawn()
                .map(|_| ())
                .map_err(|error| format!("failed to open folder {}: {}", path.display(), error));
        }

        Command::new("explorer")
            .arg(format!("/select,{}", path.display()))
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("failed to reveal file {}: {}", path.display(), error))
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg("-R")
            .arg(path)
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("failed to reveal file {}: {}", path.display(), error))
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let folder = if path.is_dir() {
            path.to_path_buf()
        } else {
            path.parent()
                .map(Path::to_path_buf)
                .unwrap_or_else(|| path.to_path_buf())
        };
        Command::new("xdg-open")
            .arg(folder)
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("failed to reveal file {}: {}", path.display(), error))
    }
}

#[tauri::command]
async fn load_workspace(app: tauri::AppHandle, state: tauri::State<'_, EngineState>) -> Result<Value, String> {
    engine_request(&app, &state, "load-workspace", json!({})).await
}

#[tauri::command]
async fn create_project(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    input: CreateProjectInput,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "create-project",
        json!({
            "name": input.name,
            "description": input.description
        }),
    )
    .await
}

#[tauri::command]
async fn open_project(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
) -> Result<Value, String> {
    engine_request(&app, &state, "open-project", json!({ "project_id": project_id })).await
}

#[tauri::command]
async fn duplicate_project(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    input: DuplicateProjectInput,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "duplicate-project",
        json!({
            "project_id": input.project_id,
            "name": input.name
        }),
    )
    .await
}

#[tauri::command]
async fn delete_project(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
) -> Result<Value, String> {
    engine_request(&app, &state, "delete-project", json!({ "project_id": project_id })).await
}

#[tauri::command]
async fn import_project_files(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    file_paths: Vec<String>,
    import_template: Option<Value>,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "import-project-files",
        json!({
            "project_id": project_id,
            "file_paths": file_paths,
            "import_template": import_template
        }),
    )
    .await
}

#[tauri::command]
async fn run_workflow(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
) -> Result<Value, String> {
    engine_request(&app, &state, "run-workflow", json!({ "project_id": project_id })).await
}

#[tauri::command]
async fn save_experiment_spec(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    experiment: Value,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "save-experiment-spec",
        json!({
            "project_id": project_id,
            "experiment": experiment
        }),
    )
    .await
}

#[tauri::command]
async fn list_experiment_specs(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
) -> Result<Value, String> {
    engine_request(&app, &state, "list-experiment-specs", json!({ "project_id": project_id })).await
}

#[tauri::command]
async fn run_experiment_matrix(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    experiment_id: String,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "run-experiment-matrix",
        json!({
            "project_id": project_id,
            "experiment_id": experiment_id
        }),
    )
    .await
}

#[tauri::command]
async fn compare_runs(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    left_run_id: String,
    right_run_id: String,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "compare-runs",
        json!({
            "project_id": project_id,
            "left_run_id": left_run_id,
            "right_run_id": right_run_id
        }),
    )
    .await
}

#[tauri::command]
async fn save_ingestion_spec(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    spec: Value,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "save-ingestion-spec",
        json!({
            "project_id": project_id,
            "spec": spec
        }),
    )
    .await
}

#[tauri::command]
async fn list_ingestion_specs(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
) -> Result<Value, String> {
    engine_request(&app, &state, "list-ingestion-specs", json!({ "project_id": project_id })).await
}

#[tauri::command]
async fn create_corpus_view(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    view: Value,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "create-corpus-view",
        json!({
            "project_id": project_id,
            "view": view
        }),
    )
    .await
}

#[tauri::command]
async fn update_corpus_view(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    view: Value,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "update-corpus-view",
        json!({
            "project_id": project_id,
            "view": view
        }),
    )
    .await
}

#[tauri::command]
async fn delete_corpus_view(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    view_id: String,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "delete-corpus-view",
        json!({
            "project_id": project_id,
            "view_id": view_id
        }),
    )
    .await
}

#[tauri::command]
async fn load_artifact_preview(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    artifact_id: String,
    limit: Option<u64>,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "load-artifact-preview",
        json!({
            "project_id": project_id,
            "artifact_id": artifact_id,
            "limit": limit
        }),
    )
    .await
}

#[tauri::command]
async fn load_artifact_payload(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    artifact_id: String,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "load-artifact-payload",
        json!({
            "project_id": project_id,
            "artifact_id": artifact_id
        }),
    )
    .await
}

#[tauri::command]
async fn list_run_artifacts(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    run_id: Option<String>,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "list-run-artifacts",
        json!({
            "project_id": project_id,
            "run_id": run_id
        }),
    )
    .await
}

#[tauri::command]
async fn export_project(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    formats: Vec<String>,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "export-project",
        json!({
            "project_id": project_id,
            "formats": formats
        }),
    )
    .await
}

#[tauri::command]
async fn export_project_backup(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    path: Option<String>,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "export-project-backup",
        json!({
            "project_id": project_id,
            "path": path
        }),
    )
    .await
}

#[tauri::command]
async fn save_project(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project: Value,
) -> Result<Value, String> {
    engine_request(&app, &state, "save-project", project).await
}

#[tauri::command]
async fn import_project_package(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    path: String,
) -> Result<Value, String> {
    engine_request(&app, &state, "import-project-package", json!({ "path": path })).await
}

#[tauri::command]
async fn update_corpus_document(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    document: Value,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "update-corpus-document",
        json!({
            "project_id": project_id,
            "document": document
        }),
    )
    .await
}

#[tauri::command]
async fn delete_corpus_document(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    doc_id: String,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "delete-corpus-document",
        json!({
            "project_id": project_id,
            "doc_id": doc_id
        }),
    )
    .await
}

#[tauri::command]
async fn import_dictionary_sheet(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    kind: String,
    path: String,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "import-dictionary-sheet",
        json!({
            "project_id": project_id,
            "kind": kind,
            "path": path
        }),
    )
    .await
}

#[tauri::command]
async fn create_review_task(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    task: Value,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "create-review-task",
        json!({
            "project_id": project_id,
            "task": task
        }),
    )
    .await
}

#[tauri::command]
async fn list_review_tasks(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    status: Option<String>,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "list-review-tasks",
        json!({
            "project_id": project_id,
            "status": status
        }),
    )
    .await
}

#[tauri::command]
async fn resolve_review_task(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    review_id: String,
    resolution: Value,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "resolve-review-task",
        json!({
            "project_id": project_id,
            "review_id": review_id,
            "resolution": resolution
        }),
    )
    .await
}

#[tauri::command]
async fn export_dictionary_sheet(
    app: tauri::AppHandle,
    state: tauri::State<'_, EngineState>,
    project_id: String,
    kind: String,
    table_id: String,
    path: String,
) -> Result<Value, String> {
    engine_request(
        &app,
        &state,
        "export-dictionary-sheet",
        json!({
            "project_id": project_id,
            "kind": kind,
            "table_id": table_id,
            "path": path
        }),
    )
    .await
}

#[tauri::command]
fn pick_files() -> Result<Vec<String>, String> {
    let files = FileDialog::new()
        .add_filter("Text data", &["txt", "csv", "xlsx", "json"])
        .set_title("选择要导入的文本文件")
        .pick_files()
        .unwrap_or_default();

    Ok(files
        .into_iter()
        .map(|path| path.to_string_lossy().to_string())
        .collect())
}

#[tauri::command]
fn pick_json_file() -> Result<Option<String>, String> {
    Ok(FileDialog::new()
        .add_filter("JSON", &["json"])
        .set_title("选择 JSON 文件")
        .pick_file()
        .map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
fn save_json_file_path(default_file_name: Option<String>) -> Result<Option<String>, String> {
    let dialog = FileDialog::new()
        .add_filter("JSON", &["json"])
        .set_title("保存 JSON 文件");
    let dialog = if let Some(file_name) = default_file_name {
        dialog.set_file_name(&file_name)
    } else {
        dialog
    };
    Ok(dialog
        .save_file()
        .map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
fn pick_project_package_file() -> Result<Option<String>, String> {
    Ok(FileDialog::new()
        .add_filter("TextFlow Project", &["tfproj"])
        .set_title("选择 .tfproj 项目包")
        .pick_file()
        .map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
fn save_project_package_path(default_file_name: Option<String>) -> Result<Option<String>, String> {
    let dialog = FileDialog::new()
        .add_filter("TextFlow Project", &["tfproj"])
        .set_title("保存 .tfproj 项目包");
    let dialog = if let Some(file_name) = default_file_name {
        dialog.set_file_name(&file_name)
    } else {
        dialog
    };
    Ok(dialog
        .save_file()
        .map(|path| path.to_string_lossy().to_string()))
}

#[tauri::command]
fn open_path(path: String) -> Result<(), String> {
    open_path_with_default_app(Path::new(&path))
}

#[tauri::command]
fn reveal_path(path: String) -> Result<(), String> {
    reveal_path_in_file_manager(Path::new(&path))
}

fn main() {
    tauri::Builder::default()
        .manage(EngineState::default())
        .setup(|app| {
            let handle = app.handle().clone();
            let state = handle.state::<EngineState>();
            let _ = warm_engine_process(&handle, &state);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            load_workspace,
            create_project,
            open_project,
            duplicate_project,
            delete_project,
            import_project_files,
            run_workflow,
            save_experiment_spec,
            list_experiment_specs,
            run_experiment_matrix,
            compare_runs,
            save_ingestion_spec,
            list_ingestion_specs,
            create_corpus_view,
            update_corpus_view,
            delete_corpus_view,
            load_artifact_preview,
            load_artifact_payload,
            list_run_artifacts,
            export_project,
            export_project_backup,
            save_project,
            import_project_package,
            update_corpus_document,
            delete_corpus_document,
            import_dictionary_sheet,
            create_review_task,
            list_review_tasks,
            resolve_review_task,
            export_dictionary_sheet,
            pick_files,
            pick_json_file,
            save_json_file_path,
            pick_project_package_file,
            save_project_package_path,
            open_path,
            reveal_path
        ])
        .build(tauri::generate_context!())
        .expect("error while building textflow desktop")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                let state = app.state::<EngineState>();
                shutdown_engine_process(&state);
            }
        });
}

#[cfg(test)]
mod tests {
    use super::{find_named_file, workspace_root_from_manifest_dir};
    use std::fs;
    use std::path::{Path, PathBuf};

    #[test]
    fn workspace_root_resolves_repo_root_from_src_tauri_dir() {
        let manifest_dir = Path::new(r"C:\repo\TextFlow\apps\desktop\src-tauri");
        let root = workspace_root_from_manifest_dir(manifest_dir).expect("root should resolve");
        assert_eq!(root, PathBuf::from(r"C:\repo\TextFlow"));
    }

    #[test]
    fn find_named_file_discovers_nested_sidecar() {
        let root = std::env::temp_dir().join(format!("textflow-tauri-test-{}", std::process::id()));
        let nested_dir = root
            .join("_up_")
            .join("_up_")
            .join("_up_")
            .join("services")
            .join("python-engine")
            .join("dist");
        let sidecar = nested_dir.join("textflow-engine.exe");
        fs::create_dir_all(&nested_dir).expect("nested dirs should be created");
        fs::write(&sidecar, b"stub").expect("sidecar file should be created");

        let found = find_named_file(&root, "textflow-engine.exe");
        assert_eq!(found, Some(sidecar.clone()));

        let _ = fs::remove_file(&sidecar);
        let _ = fs::remove_dir_all(&root);
    }
}
