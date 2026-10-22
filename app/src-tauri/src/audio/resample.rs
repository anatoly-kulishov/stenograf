use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::JoinHandle;
use std::time::Duration;

use ringbuf::traits::{Consumer, Observer, Split};
use ringbuf::{HeapCons, HeapRb};
use rubato::{FastFixedIn, PolynomialDegree, Resampler};

const CHUNK: usize = 1024;
pub const TARGET_RATE: u32 = 16_000;

pub fn spawn_wav_writer(
    mut consumer: HeapCons<f32>,
    input_rate: u32,
    path: std::path::PathBuf,
    stop: Arc<AtomicBool>,
) -> JoinHandle<Result<(), String>> {
    std::thread::spawn(move || {
        let spec = hound::WavSpec {
            channels: 1,
            sample_rate: TARGET_RATE,
            bits_per_sample: 32,
            sample_format: hound::SampleFormat::Float,
        };
        let mut writer = hound::WavWriter::create(&path, spec).map_err(|err| err.to_string())?;
        let mut resampler = FastFixedIn::<f32>::new(
            f64::from(TARGET_RATE) / f64::from(input_rate.max(1)),
            1.1,
            PolynomialDegree::Cubic,
            CHUNK,
            1,
        )
        .map_err(|err| err.to_string())?;

        let mut pending: Vec<f32> = Vec::with_capacity(CHUNK * 4);
        loop {
            while let Some(sample) = consumer.try_pop() {
                pending.push(sample);
            }
            while pending.len() >= CHUNK {
                let chunk: Vec<f32> = pending.drain(..CHUNK).collect();
                write_resampled(&mut resampler, &mut writer, chunk)?;
            }
            if stop.load(Ordering::Acquire) && consumer.occupied_len() == 0 {
                break;
            }
            std::thread::sleep(Duration::from_millis(10));
        }

        if !pending.is_empty() {
            let padded = CHUNK;
            pending.resize(padded, 0.0);
            write_resampled(&mut resampler, &mut writer, pending.clone())?;
        }
        writer.finalize().map_err(|err| err.to_string())?;
        Ok(())
    })
}

fn write_resampled(
    resampler: &mut FastFixedIn<f32>,
    writer: &mut hound::WavWriter<std::io::BufWriter<std::fs::File>>,
    chunk: Vec<f32>,
) -> Result<(), String> {
    let output = resampler
        .process(&[chunk], None)
        .map_err(|err| err.to_string())?;
    for sample in &output[0] {
        writer.write_sample(*sample).map_err(|err| err.to_string())?;
    }
    Ok(())
}

pub fn ring() -> (ringbuf::HeapProd<f32>, HeapCons<f32>) {
    HeapRb::<f32>::new(CHUNK * 256).split()
}
