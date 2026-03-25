# Generative Documentary Pipeline

Open source toolkit for producing AI-narrated documentary films.

## What it does

Takes a script, renders narration via ElevenLabs TTS, generates abstract visualization
shots via fal.ai/Replicate, and assembles the final film via ffmpeg.

## Components

- `build_film.py` — ffmpeg assembly engine. Cuts source clips, normalizes,
  layers VO, handles segment concat with micro-gap prevention.
- `generate_video.py` — Async generative video via Replicate (Kling 3.0).
  Fires predictions in parallel, polls until complete, downloads and normalizes.

## Films produced with this pipeline

- "The Thinking Game" (7:52) — Demis Hassabis documentary reaction
- "The System Couldn't Measure Me" (7:47) — Leo Guinan, with Kling-generated
  P vs NP visualization sequences
- "Fermat — The Margin" (in production) — first-person narration by Pierre de Fermat

## Dependencies

    pip install replicate elevenlabs

    ffmpeg (brew install ffmpeg)

## Usage

    # Set your keys
    export REPLICATE_API_TOKEN=your_key
    export ELEVENLABS_API_KEY=your_key

    # Generate visualization shots
    python pipeline/generate_video.py

    # Assemble film
    python pipeline/build_film.py

## License

MIT. Use it, fork it, make films.
