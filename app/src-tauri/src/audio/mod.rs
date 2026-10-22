mod mic;
mod recorder;
mod resample;
mod system_tap;

pub use recorder::Recorder;

pub fn probe_recorder() -> Result<String, String> {
    recorder::probe_recorder()
}
