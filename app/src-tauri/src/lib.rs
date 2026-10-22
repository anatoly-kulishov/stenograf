mod audio;
mod sidecar;

use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Emitter, Manager};

use audio::Recorder;

pub use audio::probe_recorder;
use sidecar::{Sidecar, Turn};

#[tauri::command]
fn start_recording(recorder: tauri::State<'_, Recorder>, app: tauri::AppHandle) -> Result<(), String> {
    recorder.start()?;
    if let Some(tray) = app.tray_by_id("main") {
        let _ = tray.set_tooltip(Some("Stenograf: идёт запись"));
    }
    let _ = app.emit("recording", true);
    Ok(())
}

#[tauri::command]
async fn stop_recording(app: tauri::AppHandle, recorder: tauri::State<'_, Recorder>) -> Result<Vec<Turn>, String> {
    let paths = recorder.stop()?;
    if let Some(tray) = app.tray_by_id("main") {
        let _ = tray.set_tooltip(Some("Stenograf"));
    }
    let _ = app.emit("recording", false);
    let sidecar = app.state::<Sidecar>();
    sidecar
        .transcribe(
            &app,
            paths.mic.to_string_lossy().as_ref(),
            paths.system.to_string_lossy().as_ref(),
        )
        .await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let sidecar = Sidecar::spawn(app.handle())?;
            app.manage(sidecar);
            app.manage(Recorder::new());

            let show = MenuItem::with_id(app, "show", "Открыть Stenograf", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show])?;
            let icon = app.default_window_icon().cloned();
            let mut tray = TrayIconBuilder::with_id("main").tooltip("Stenograf").menu(&menu);
            if let Some(icon) = icon {
                tray = tray.icon(icon);
            }
            tray.on_menu_event(|app, event| {
                if event.id() == "show" {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
            })
            .build(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![start_recording, stop_recording])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
