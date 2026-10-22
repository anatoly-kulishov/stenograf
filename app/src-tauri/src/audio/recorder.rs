//! Захват живёт на отдельном потоке: cpal и Core Audio не Send, а команды Tauri - да.

use std::fs;
use std::path::PathBuf;
use std::sync::mpsc::{self, Sender};
use std::time::{SystemTime, UNIX_EPOCH};

use super::mic::MicCapture;
use super::system_tap::SystemTap;

pub struct Recording {
    pub mic: PathBuf,
    pub system: PathBuf,
}

struct Active {
    mic: MicCapture,
    system: SystemTap,
    paths: Recording,
}

impl Active {
    fn start() -> Result<Self, String> {
        let dir = std::env::temp_dir().join(format!("stenograf-{}", millis()));
        fs::create_dir_all(&dir).map_err(|err| err.to_string())?;
        let paths = Recording { mic: dir.join("mic.wav"), system: dir.join("system.wav") };
        let mic = MicCapture::start(paths.mic.clone())?;
        let system = SystemTap::start(paths.system.clone())?;
        Ok(Self { mic, system, paths })
    }

    fn finish(mut self) -> Result<Recording, String> {
        self.mic.stop()?;
        self.system.stop()?;
        Ok(self.paths)
    }
}

enum Job {
    Start(Sender<Result<(), String>>),
    Stop(Sender<Result<Recording, String>>),
}

pub struct Recorder {
    tx: Sender<Job>,
}

impl Recorder {
    pub fn new() -> Self {
        let (tx, rx) = mpsc::channel();
        std::thread::Builder::new()
            .name("stenograf-audio".into())
            .spawn(move || {
                let mut active: Option<Active> = None;
                while let Ok(job) = rx.recv() {
                    match job {
                        Job::Start(reply) => {
                            let result = if active.is_some() {
                                Err("запись уже идёт".into())
                            } else {
                                match Active::start() {
                                    Ok(session) => {
                                        active = Some(session);
                                        Ok(())
                                    }
                                    Err(err) => Err(err),
                                }
                            };
                            let _ = reply.send(result);
                        }
                        Job::Stop(reply) => {
                            let result = match active.take() {
                                Some(session) => session.finish(),
                                None => Err("запись не запущена".into()),
                            };
                            let _ = reply.send(result);
                        }
                    }
                }
            })
            .expect("поток записи");
        Self { tx }
    }

    pub fn start(&self) -> Result<(), String> {
        let (reply_tx, reply_rx) = mpsc::channel();
        self.tx.send(Job::Start(reply_tx)).map_err(|err| err.to_string())?;
        reply_rx.recv().map_err(|err| err.to_string())?
    }

    pub fn stop(&self) -> Result<Recording, String> {
        let (reply_tx, reply_rx) = mpsc::channel();
        self.tx.send(Job::Stop(reply_tx)).map_err(|err| err.to_string())?;
        reply_rx.recv().map_err(|err| err.to_string())?
    }
}

#[cfg(test)]
mod tests {
    #[test]
    #[ignore = "нужны микрофон и разрешение на захват системного звука"]
    fn records_one_second() {
        let dir = std::env::temp_dir().join("stenograf-spike");
        std::fs::create_dir_all(&dir).unwrap();
        let mic_path = dir.join("mic.wav");
        let system_path = dir.join("system.wav");
        let mut mic = super::super::mic::MicCapture::start(mic_path.clone()).expect("mic");
        let mut system = super::super::system_tap::SystemTap::start(system_path.clone()).expect("system");
        std::thread::sleep(std::time::Duration::from_secs(2));
        mic.stop().expect("mic stop");
        system.stop().expect("system stop");
        let paths = super::Recording { mic: mic_path, system: system_path };

        for path in [&paths.mic, &paths.system] {
            let mut reader = hound::WavReader::open(path).expect("wav");
            let samples: Vec<f32> = reader.samples::<f32>().map(|item| item.unwrap_or(0.0)).collect();
            let energy = samples.iter().map(|sample| sample * sample).sum::<f32>() / samples.len().max(1) as f32;
            eprintln!("{} rate={} n={} rms={:.5}", path.display(), reader.spec().sample_rate, samples.len(), energy.sqrt());
            // Системный tap молчит, пока в выходе тишина: cargo test это не гарантирует.
            if path.ends_with("mic.wav") {
                assert!(samples.len() > 8_000, "{} слишком короткий", path.display());
            }
        }
    }
}

pub fn probe_recorder() -> Result<String, String> {
    let recorder = Recorder::new();
    recorder.start()?;
    std::thread::sleep(std::time::Duration::from_secs(2));
    let paths = recorder.stop()?;
    let mut lines = Vec::new();
    for path in [&paths.mic, &paths.system] {
        let reader = hound::WavReader::open(path).map_err(|err| err.to_string())?;
        lines.push(format!("{} samples={} rate={}", path.display(), reader.len(), reader.spec().sample_rate));
    }
    Ok(lines.join("\n"))
}

fn millis() -> u128 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|dur| dur.as_millis()).unwrap_or(0)
}
