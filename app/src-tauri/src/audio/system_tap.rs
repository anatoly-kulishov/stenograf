//! Захват системного звука через Core Audio process tap (macOS 14.4+).
//! Aggregate как в примере cidre `core-audio-record`: sub-device даёт clock,
//! без него IO proc не получает буферы (проверено на macOS 27).
//! Пока в системном выходе цифровая тишина, колбэк не зовётся и wav остаётся пустым.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::JoinHandle;

use cidre::{arc, av, cat, cf, core_audio as ca, os};
use ringbuf::traits::Producer;

use super::resample::{ring, spawn_wav_writer};

struct AudioContext {
    format: arc::R<av::AudioFormat>,
    producer: ringbuf::HeapProd<f32>,
    channels: usize,
}

pub struct SystemTap {
    _tap: ca::TapGuard,
    _ctx: Box<AudioContext>,
    device: Option<ca::hardware::StartedDevice<ca::AggregateDevice>>,
    stop: Arc<AtomicBool>,
    writer: Option<JoinHandle<Result<(), String>>>,
}

impl SystemTap {
    pub fn start(path: std::path::PathBuf) -> Result<Self, String> {
        let output = ca::System::default_output_device().map_err(|err| format!("выходное устройство: {err:?}"))?;
        let output_uid = output.uid().map_err(|err| format!("uid устройства: {err:?}"))?;

        let tap_desc = ca::TapDesc::with_stereo_global_tap_excluding_processes(&cidre::ns::Array::new());
        let tap = tap_desc.create_process_tap().map_err(|err| format!("process tap: {err:?}"))?;
        let asbd = tap.asbd().map_err(|err| format!("формат tap: {err:?}"))?;
        let format = av::AudioFormat::with_asbd(&asbd).ok_or("не удалось описать формат tap")?;
        let channels = asbd.channels_per_frame.max(1) as usize;

        let sub_device = cf::DictionaryOf::with_keys_values(
            &[ca::sub_device_keys::uid()],
            &[output_uid.as_type_ref()],
        );
        let sub_tap = cf::DictionaryOf::with_keys_values(
            &[ca::sub_device_keys::uid()],
            &[tap.uid().map_err(|err| format!("uid tap: {err:?}"))?.as_type_ref()],
        );
        let agg_desc = cf::DictionaryOf::with_keys_values(
            &[
                ca::aggregate_device_keys::is_private(),
                ca::aggregate_device_keys::is_stacked(),
                ca::aggregate_device_keys::tap_auto_start(),
                ca::aggregate_device_keys::name(),
                ca::aggregate_device_keys::main_sub_device(),
                ca::aggregate_device_keys::uid(),
                ca::aggregate_device_keys::sub_device_list(),
                ca::aggregate_device_keys::tap_list(),
            ],
            &[
                cf::Boolean::value_true().as_type_ref(),
                cf::Boolean::value_false(),
                cf::Boolean::value_true(),
                cf::str!(c"stenograf-audio-tap").as_type_ref(),
                &output_uid,
                &cf::Uuid::new().to_cf_string(),
                &cf::ArrayOf::from_slice(&[sub_device.as_ref()]),
                &cf::ArrayOf::from_slice(&[sub_tap.as_ref()]),
            ],
        );

        let (producer, consumer) = ring();
        let stop = Arc::new(AtomicBool::new(false));
        let writer = spawn_wav_writer(consumer, asbd.sample_rate as u32, path, stop.clone());
        let mut ctx = Box::new(AudioContext { format, producer, channels });

        let abort = |stop: Arc<AtomicBool>, writer: JoinHandle<Result<(), String>>, err: String| -> Result<Self, String> {
            stop.store(true, Ordering::Release);
            let _ = writer.join();
            Err(err)
        };

        let agg = match ca::AggregateDevice::with_desc(&agg_desc) {
            Ok(device) => device,
            Err(err) => return abort(stop, writer, format!("aggregate: {err:?}")),
        };
        let proc_id = match agg.create_io_proc_id(audio_proc, Some(&mut *ctx)) {
            Ok(id) => id,
            Err(err) => return abort(stop, writer, format!("io proc: {err:?}")),
        };
        let device = match ca::device_start(agg, Some(proc_id)) {
            Ok(device) => device,
            Err(err) => return abort(stop, writer, format!("start: {err:?}")),
        };

        Ok(Self { _tap: tap, _ctx: ctx, device: Some(device), stop, writer: Some(writer) })
    }

    pub fn stop(&mut self) -> Result<(), String> {
        self.stop.store(true, Ordering::Release);
        self.device.take();
        self.writer
            .take()
            .map(|handle| handle.join().unwrap_or_else(|_| Err("поток записи системного звука упал".into())))
            .transpose()?;
        Ok(())
    }
}

impl Drop for SystemTap {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}

extern "C" fn audio_proc(
    _device: ca::Device,
    _now: &cat::AudioTimeStamp,
    input_data: &cat::AudioBufList<1>,
    _input_time: &cat::AudioTimeStamp,
    _output_data: &mut cat::AudioBufList<1>,
    _output_time: &cat::AudioTimeStamp,
    ctx: Option<&mut AudioContext>,
) -> os::Status {
    let ctx = ctx.unwrap();
    if let Some(view) = av::AudioPcmBuf::with_buf_list_no_copy(&ctx.format, input_data, None) {
        if let Some(data) = view.data_f32_at(0) {
            push_downmix(&mut ctx.producer, data, ctx.channels);
            return os::Status::NO_ERR;
        }
    }

    let buffer = &input_data.buffers[0];
    if !buffer.data.is_null() && buffer.data_bytes_size > 0 {
        let count = buffer.data_bytes_size as usize / std::mem::size_of::<f32>();
        let data = unsafe { std::slice::from_raw_parts(buffer.data as *const f32, count) };
        push_downmix(&mut ctx.producer, data, ctx.channels);
    }
    os::Status::NO_ERR
}

fn push_downmix(producer: &mut ringbuf::HeapProd<f32>, data: &[f32], channels: usize) {
    if channels <= 1 {
        let _ = producer.push_slice(data);
        return;
    }
    for frame in data.chunks(channels) {
        if frame.len() < channels {
            break;
        }
        let mean = frame.iter().sum::<f32>() / channels as f32;
        let _ = producer.try_push(mean);
    }
}
