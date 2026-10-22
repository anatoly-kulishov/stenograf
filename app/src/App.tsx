import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import "./App.css";

interface Turn {
  start: number;
  speaker: string;
  text: string;
}

const STAGE: Record<string, string> = {
  load: "Читаю аудио",
  vad: "Делю на фразы",
  asr: "Распознаю речь",
  diarize: "Различаю голоса",
  done: "Готово",
};

function speakerName(speaker: string): string {
  if (speaker === "me") return "Я";
  return speaker.replace("speaker-", "Спикер ");
}

function stamp(start: number): string {
  const total = Math.floor(start);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function App() {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);

  useEffect(() => {
    const progress = listen<{ stage: string; pct: number }>("transcribe-progress", (event) => {
      const label = STAGE[event.payload.stage] ?? event.payload.stage;
      setStage(`${label} ${event.payload.pct}%`);
    });
    const flag = listen<boolean>("recording", (event) => setRecording(event.payload));
    return () => {
      progress.then((drop) => drop());
      flag.then((drop) => drop());
    };
  }, []);

  async function toggle() {
    setError("");
    try {
      if (!recording) {
        await invoke("start_recording");
        setTurns([]);
        setStage("");
        return;
      }
      setBusy(true);
      setStage("Останавливаю запись");
      const next = await invoke<Turn[]>("stop_recording");
      setTurns(next);
      setStage("");
    } catch (err) {
      setError(String(err));
      setRecording(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="root">
      <header className="bar">
        <div>
          <h1>Stenograf</h1>
          <p className="hint">Запись остаётся на этом компьютере. Скажите собеседникам, что ведёте заметки.</p>
        </div>
        <button className={recording ? "rec on" : "rec"} disabled={busy} onClick={toggle}>
          <span className="dot" />
          {recording ? "Стоп" : "Запись"}
        </button>
      </header>

      {recording && <p className="live">Идёт запись. Микрофон - это вы, системный звук - собеседники.</p>}
      {stage && <p className="live">{stage}</p>}
      {error && <p className="err">{error}</p>}

      <ol className="turns">
        {turns.map((turn) => (
          <li key={`${turn.start}-${turn.speaker}`}>
            <time>{stamp(turn.start)}</time>
            <strong>{speakerName(turn.speaker)}</strong>
            <span>{turn.text}</span>
          </li>
        ))}
      </ol>
    </main>
  );
}

export default App;
