//! Python-ядро: JSON lines. В dev и в .app это один и тот же sidecar-скрипт.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use serde::Serialize;
use serde_json::{json, Value};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Clone, Serialize, serde::Deserialize)]
pub struct Turn {
    pub start: f64,
    pub speaker: String,
    pub text: String,
}

enum Reply {
    Progress { stage: String, pct: u64 },
    Result(Vec<Turn>),
    Error(String),
}

pub struct Sidecar {
    child: Mutex<CommandChild>,
    pending: Arc<Mutex<std::collections::HashMap<u64, tokio::sync::mpsc::UnboundedSender<Reply>>>>,
    next_id: AtomicU64,
}

impl Sidecar {
    pub fn spawn(app: &tauri::AppHandle) -> Result<Self, String> {
        let (mut events, child) = app
            .shell()
            .sidecar("stenograf-core")
            .map_err(|err| err.to_string())?
            .spawn()
            .map_err(|err| err.to_string())?;

        let pending: Arc<Mutex<std::collections::HashMap<u64, tokio::sync::mpsc::UnboundedSender<Reply>>>> =
            Arc::new(Mutex::new(std::collections::HashMap::new()));
        let (ready_tx, ready_rx) = std::sync::mpsc::channel();
        let pending_reader = pending.clone();
        tauri::async_runtime::spawn(async move {
            let mut buffer = String::new();
            while let Some(event) = events.recv().await {
                match event {
                    CommandEvent::Stdout(bytes) => {
                        // Плагин отдаёт строки уже без \n, но буфер нужен, если строка разрезана.
                        buffer.push_str(&String::from_utf8_lossy(&bytes));
                        if buffer.contains('\n') {
                            while let Some(pos) = buffer.find('\n') {
                                let line: String = buffer.drain(..=pos).collect();
                                handle_line(&line, &pending_reader, &ready_tx);
                            }
                        } else {
                            handle_line(&buffer, &pending_reader, &ready_tx);
                            buffer.clear();
                        }
                    }
                    CommandEvent::Stderr(bytes) => {
                        eprint!("{}", String::from_utf8_lossy(&bytes));
                    }
                    CommandEvent::Error(err) => eprintln!("sidecar: {err}"),
                    CommandEvent::Terminated(payload) => {
                        eprintln!("sidecar завершился: {payload:?}");
                        break;
                    }
                    _ => {}
                }
            }
        });

        ready_rx
            .recv_timeout(std::time::Duration::from_secs(60))
            .map_err(|_| "сайдкар не ответил ready за 60 с".to_string())?;

        Ok(Self { child: Mutex::new(child), pending, next_id: AtomicU64::new(1) })
    }

    pub async fn transcribe(&self, app: &tauri::AppHandle, mic: &str, system: &str) -> Result<Vec<Turn>, String> {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
        self.pending.lock().expect("pending").insert(id, tx);
        let line = json!({"id": id, "cmd": "transcribe", "mic": mic, "system": system}).to_string() + "\n";
        self.child.lock().expect("stdin").write(line.as_bytes()).map_err(|err| err.to_string())?;

        while let Some(reply) = rx.recv().await {
            match reply {
                Reply::Progress { stage, pct } => {
                    let _ = app.emit("transcribe-progress", json!({"stage": stage, "pct": pct}));
                }
                Reply::Result(turns) => return Ok(turns),
                Reply::Error(message) => return Err(message),
            }
        }
        Err("сайдкар закрыл ответ".into())
    }
}

fn handle_line(
    line: &str,
    pending: &Mutex<std::collections::HashMap<u64, tokio::sync::mpsc::UnboundedSender<Reply>>>,
    ready: &std::sync::mpsc::Sender<()>,
) {
    let Ok(value) = serde_json::from_str::<Value>(line.trim()) else { return };
    if value.get("event").and_then(Value::as_str) == Some("ready") {
        let _ = ready.send(());
        return;
    }
    let Some(id) = value.get("id").and_then(Value::as_u64) else { return };
    let reply = match value.get("event").and_then(Value::as_str) {
        Some("progress") => Reply::Progress {
            stage: value.get("stage").and_then(Value::as_str).unwrap_or("").to_string(),
            pct: value.get("pct").and_then(Value::as_u64).unwrap_or(0),
        },
        Some("result") => {
            let turns = serde_json::from_value(value.get("turns").cloned().unwrap_or(Value::Array(vec![]))).unwrap_or_default();
            Reply::Result(turns)
        }
        Some("error") => Reply::Error(value.get("message").and_then(Value::as_str).unwrap_or("ошибка ядра").into()),
        _ => return,
    };
    let finished = matches!(reply, Reply::Result(_) | Reply::Error(_));
    if let Some(tx) = pending.lock().expect("pending").get(&id) {
        let _ = tx.send(reply);
    }
    if finished {
        pending.lock().expect("pending").remove(&id);
    }
}

use tauri::Emitter;
