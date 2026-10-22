use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::JoinHandle;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, Stream};
use ringbuf::traits::Producer;

use super::resample::{ring, spawn_wav_writer};

pub struct MicCapture {
    _stream: Stream,
    stop: Arc<AtomicBool>,
    writer: Option<JoinHandle<Result<(), String>>>,
}

impl MicCapture {
    pub fn start(path: std::path::PathBuf) -> Result<Self, String> {
        let host = cpal::default_host();
        let device = host
            .default_input_device()
            .ok_or("нет микрофона по умолчанию")?;
        let config = device.default_input_config().map_err(|err| err.to_string())?;
        let channels = config.channels();
        let rate = config.sample_rate().0;
        let (mut producer, consumer) = ring();
        let stop = Arc::new(AtomicBool::new(false));
        let writer = spawn_wav_writer(consumer, rate, path, stop.clone());

        let stream = match config.sample_format() {
            SampleFormat::F32 => device.build_input_stream(
                &config.into(),
                move |data: &[f32], _| push_mono(&mut producer, data, channels),
                |err| eprintln!("mic: {err}"),
                None,
            ),
            SampleFormat::I16 => device.build_input_stream(
                &config.into(),
                move |data: &[i16], _| {
                    let floats: Vec<f32> = data.iter().map(|sample| f32::from(*sample) / 32768.0).collect();
                    push_mono(&mut producer, &floats, channels);
                },
                |err| eprintln!("mic: {err}"),
                None,
            ),
            other => return Err(format!("формат микрофона {other} не поддержан")),
        }
        .map_err(|err| err.to_string())?;

        if let Err(err) = stream.play() {
            stop.store(true, Ordering::Release);
            let _ = writer.join();
            return Err(err.to_string());
        }
        Ok(Self { _stream: stream, stop, writer: Some(writer) })
    }

    pub fn stop(&mut self) -> Result<(), String> {
        self.stop.store(true, Ordering::Release);
        self.writer.take().map(|handle| handle.join().unwrap_or_else(|_| Err("поток записи микрофона упал".into()))).transpose()?;
        Ok(())
    }
}

impl Drop for MicCapture {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}

fn push_mono(producer: &mut ringbuf::HeapProd<f32>, data: &[f32], channels: u16) {
    if channels <= 1 {
        let _ = producer.push_slice(data);
        return;
    }
    let width = channels as usize;
    for frame in data.chunks(width) {
        let mean = frame.iter().sum::<f32>() / width as f32;
        let _ = producer.try_push(mean);
    }
}
