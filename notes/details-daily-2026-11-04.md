# Details — 2026-11-04

Researched from the live pages (both fetched directly, 200) for the two new records added 2026-11-04.

## Details

### voxl
- Details: voxl is a low-latency desktop streaming tool for the browser, written in Rust by Tembo. It streams an X11 display, a macOS screen, or a Windows desktop as H.264 video over a WebSocket to a small web client that decodes with WebCodecs, and it carries input, clipboard, audio, microphone, and file and folder transfer plus dynamic resolution. The project publishes its own benchmarks showing 60 FPS with 12–99 ms median latency on a CPU-only VM, against under 8 FPS for noVNC, though those numbers are the project's own measurements and not independently verified. It installs with cargo install voxl-server and prints a sign-in link for the display it streams, which makes it a quick way to give a remote machine — including an agent sandbox — a browser-reachable desktop.

### sable
- Details: Sable (Small-field Argument for Bit-exact LLM Execution) is a system from moonmath-ai that proves a language model with committed weights produced a given reply to a given prompt, bit for bit. It has two parts: an exact integer version of the model in which every rounding, normalization, softmax, and sampling decision is fixed by its inputs, and a sumcheck-based proof system over the 31-bit KoalaBear field that lets a client verify every token — including where generation stopped — without the GPU that ran the model. The repository includes the prover, the cost model, the specification, and the full paper, with measured proving times of roughly 85–670 seconds for 32B-class models on a single RTX PRO 6000 GPU and verification in 19–56 seconds on one CPU core. It is aimed at verifiable inference: proving that a provider actually ran the model it claims, and it is slated for deployment on Zro's Dolly models.
