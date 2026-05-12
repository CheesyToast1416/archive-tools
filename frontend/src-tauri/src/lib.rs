use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::{Emitter, Manager, RunEvent, State};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct ConnectionInfo {
    pub port: u16,
    pub token: String,
}

pub struct AppState {
    /// Port + token populated after sidecar writes its first stdout line.
    pub connection: Mutex<Option<ConnectionInfo>>,
    /// Holds the child handle alive — dropping it would kill the sidecar.
    pub _sidecar: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
}

/// Called by the SvelteKit frontend to obtain the server address + auth token.
/// Returns None until the sidecar has written its handshake line.
#[tauri::command]
fn get_connection_info(state: State<AppState>) -> Option<ConnectionInfo> {
    state.connection.lock().unwrap().clone()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState {
            connection: Mutex::new(None),
            _sidecar: Mutex::new(None),
        })
        // Prevent double-launch: focus the existing window instead
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_notification::init())
        // Auto-save and restore window position + size
        .plugin(tauri_plugin_window_state::Builder::new().build())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![get_connection_info])
        .setup(|app| {
            let handle = app.handle().clone();

            let (mut rx, child) = handle
                .shell()
                .sidecar("archivetools-server")
                .expect("archivetools-server sidecar not configured")
                .spawn()
                .expect("failed to spawn archivetools-server sidecar");

            *app.state::<AppState>()._sidecar.lock().unwrap() = Some(child);

            let handle_clone = handle.clone();
            tauri::async_runtime::spawn(async move {
                let mut first_line = true;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            if first_line {
                                first_line = false;
                                let text = String::from_utf8_lossy(&bytes);
                                if let Ok(info) =
                                    serde_json::from_str::<ConnectionInfo>(text.trim())
                                {
                                    *handle_clone
                                        .state::<AppState>()
                                        .connection
                                        .lock()
                                        .unwrap() = Some(info.clone());

                                    // Start health-check loop once we have the port
                                    start_health_check(handle_clone.clone(), info);
                                }
                            }
                        }
                        CommandEvent::Terminated(_) => {
                            // Notify frontend if sidecar dies unexpectedly
                            let _ = handle_clone.emit("sidecar-unavailable", ());
                            break;
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building tauri application")
        .run(|_app, event| {
            // Graceful exit: sidecar terminates when AppState._sidecar is dropped
            if let RunEvent::ExitRequested { .. } = event {}
        });
}

/// Ping GET /health every 30 s. Emit "sidecar-unavailable" after 3 consecutive failures.
fn start_health_check(handle: tauri::AppHandle, info: ConnectionInfo) {
    tauri::async_runtime::spawn(async move {
        let url = format!("http://127.0.0.1:{}/health", info.port);
        let token = info.token.clone();
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .unwrap_or_default();
        let mut failures: u32 = 0;

        loop {
            tokio::time::sleep(Duration::from_secs(30)).await;
            let ok = client
                .get(&url)
                .header("Authorization", format!("Bearer {}", token))
                .send()
                .await
                .map(|r| r.status().is_success())
                .unwrap_or(false);

            if ok {
                failures = 0;
            } else {
                failures += 1;
                if failures >= 3 {
                    let _ = handle.emit("sidecar-unavailable", ());
                    break;
                }
            }
        }
    });
}
