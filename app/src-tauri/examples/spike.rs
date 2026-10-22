/// Ручная проверка захвата. Пока играет системный звук, обе дорожки должны быть ненулевыми.
fn main() {
    match stenograf_lib::probe_recorder() {
        Ok(summary) => println!("{summary}"),
        Err(err) => {
            eprintln!("{err}");
            std::process::exit(1);
        }
    }
}
