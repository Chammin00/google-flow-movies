# DEAD CHANNEL 13 — v2.0 *Dandadan* / *Yu Yu Hakusho* Sakuga Rebuild Blueprint

**Scene:** *Rain on the Glass — The 13-Second Catwalk Brawl* (`16:9`, `24fps` master with selective `12fps` on-twos melee accents)  
**Target Style:** 1990s hand-inked cel sakuga fusing *Yu Yu Hakusho* (Dark Tournament B&W *Kurokoma* / *Hakukoma* impact frames, stark ink speed-lines), *Dandadan* (extreme 14mm fisheye distortions, rapid duotone color-script snaps), and *Cowboy Bebop* (wet-steel rain lighting & smoky noir close-ups).

---

## 1. The 4 Fight-Speed & Sakuga Mechanics

1. **Micro-Cut Compression (`0.4s–2.2s` Cuts Instead of `6s–8s` Holds)**
   - Generative video models lose kinetic silhouette discipline after `~2.5s`, producing floaty drift.
   - Cutting **on the apex of the strike** and slicing combat into `0.35s–1.8s` bursts prevents visual stagnation and forces the viewer's eye to track momentum continuously across angles.
2. **Start -> End Key-Pose (*Genga*) Choreography + Extreme Lenses**
   - Pairing locked **Start Keyframe -> End Keyframe** anchors in Google Flow constrains anatomy, costume continuity, and physical trajectory across every beat.
   - Replacing eye-level medium-wides with **14mm ultra-wide fisheye chase shots**, extreme Dutch tilts, and whip-pans exaggerates foreground limb speed and depth parallax (*Yutapon* flying concrete/glass debris cubes past the camera).
3. **Non-Linear *Tame-Tsume* Timing, `12fps` On-Twos, Hit-Stops & Duotone Snaps**
   - **Speed Ramping (*Tame-Tsume*):** Accelerate wind-ups across `1.5x -> 2.7x` so punches whip into the target.
   - **Step on Twos (`12fps`):** Drop peak close-quarters exchanges to held pairs (`on_twos=True`) to restore crisp cel snap instead of smooth AI interpolation.
   - **Hit-Stop + *Hakukoma* / *Kurokoma* (`3–5` frames):** Freeze the collision frame behind 1 inverted high-contrast white-on-black ink frame (`Hakukoma`), 1 stark black-on-white silhouette ink frame (`Kurokoma`) with radial speed-lines, and `2–3` chromatic-split shake frames (`±6px`, `rgb_split=6`).
   - ***Dandadan* Color-Script Flips:** Snap-grade ability activations into stark high-contrast ink duotones (`dandadan_cyan` for *Zero Beat*; `dandadan_crimson` for *Dead-Fire* + *Pulse-Shot* overload) before snapping back to full color on impact release.
4. **Vacuum-Silence Audio Contrast (`0.20s–0.22s` Drop) + Native Japanese Lip-Sync**
   - Drop **both music and ambient rain to near-zero (`0.03x`)** for `0.20s–0.22s` right before major collisions so the human ear registers maximum dynamic contrast when the sub-bass sweep (`120Hz -> 30Hz`), metallic blade overtone, and CRT shatter detonate.
   - Lock spoken dialogue shots (`1.0x` playback) with **quoted Japanese lines inside the generation prompt** so mouth flaps and jaw cadence match the Japanese audio natively, and use editorial cutaways (oscilloscope waveforms, smoking taped knuckles) whenever dialogue overlaps rapid combat cuts.

---

## 2. Complete 12-Beat Sakuga Shot List

| Beat | Target Cut Length | Lens / Camera Motion | Start -> End Keyframe Action | Timing & VFX Treatment | Audio / Native JP Lip-Sync Cue | Status |
| :---: | :---: | :--- | :--- | :--- | :--- | :---: |
| **B01** | `1.0s` | Black card snap | `DEAD CHANNEL 13 // 02:13 AM` | `24fps`, crisp cut-out | Sub-bass clock tick -> rain surge | In Cut |
| **B02** | `0.7s` | Low-angle Dutch `MS` push-in | Renji southpaw stance -> front-foot rainwater splash kick toward Masato | `1.5x -> 2.2x` ramp, `12fps` on-twos at kick apex | Heavy downpour + sharp water-whip SFX | V1 Base |
| **B03** | `1.2s` | **14mm Ultra-Wide Fisheye Chase** (`sakuga_kf1`) | Coiled crouch -> Renji lunges fists-first straight at the lens in cobalt smear trails while Masato frame-skips backward | `1.5x -> 2.2x`, `12fps` on-twos, `3`-frame mid-combo impact flash | Rapid boxing glove air-snaps + puddle splash | **Generated Live (`v2_01`)** |
| **B04** | `0.8s` | Overhead 45° whip-tilt on falling rain | Raindrops stretch vertically -> lock dead silent in suspended crystal beads | `1.4x`, hard snap to **`dandadan_cyan`** duotone (`0.45s`) | `Masato (JP):` 「ゼロ・ビート。」 (*"Zero Beat."*) + **0.20s Vacuum Silence Drop** | V1 + Duotone FX |
| **B05** | `0.9s` | Tight axial punch-in on Masato's palm -> CRT wall | Gloved finger snap -> Renji rocketing backward through exploding stacked CRTs | **4f Hit-Stop** (`Hakukoma`/`Kurokoma` + cyan radial lines) -> `2.2x` `on-twos`, `14px` shake, `rgb_split=6` | Finger snap + reversed suction + `105Hz->32Hz` sub drop + CRT glass burst | V1 + Sakuga FX |
| **B06** | `0.5s` | Extreme foreground dash wipe | Stray sparks & water curtain wipe leftward into neon static flash (`2f` cyan `#38BDF8`) | `2.4x` `on-twos`, `2`-frame cyan flash bridge | Tape transport engage click + high-pass whoosh | Bridge Beat |
| **B07** | `3.5s` | Control booth whip-pan (`MCU`) + green CRT waveform | White-coated Toma throws Phase-Tape brass lever -> tight on **Sora calling coordinates into headset mic** as window glass shatters behind | Locked **`1.0x` playback speed** during speech for native Japanese mouth sync (editorial oscilloscope overlay optional on alternate cuts) | **`v2_02` Native JP Lip-Sync:** Sora: 「左かかと二歩後ろ！着地でロックが切れる！」 (*"Two steps behind your left heel! His lock drops when he lands!"*) | **Generated Live (`v2_02`)** |
| **B08** | `0.4s` | Overhead stained-glass skylight tilt (`2f` white flash) | Rainbow stained-glass prism fractures inward -> downward drop silhouette of Kuroha | `2.0x`, `2`-frame pure white flash bridge | Blade scabbard draw (`2920Hz` ring) + incoming wind roar | Bridge Beat |
| **B09** | `1.3s` | **Extreme Dutch Climax Close-Up** (`sakuga_kf2`) | Kuroha swings obsidian-violet flame wakizashi -> collides with Renji's cobalt lightning punch against Masato's cracking crimson shield | `1.5x -> 2.3x` `on-twos`, **`0.22s` Vacuum Silence** -> **5f Hit-Stop** (`Hakukoma`/`Kurokoma`) -> **`dandadan_crimson`** snap | `120Hz->30Hz` sub-bass crater + metallic FM blade parry + glass roar | **Generated Live (`v2_03`)** |
| **B10** | `1.4s` | 180° low orbital whip around triple-clash center | Crimson shield fractures -> multi-colored stained-glass shockwave blasts roof upward (`Yutapon` cubes flying past camera) | `2.0x` color release (`shake 14 -> 0`), hard intercut back to `v2_03` slash follow-through | Twin lightning-fire detonation + cascading rainbow glass rain | Hybrid (`cut_04` + `v2_03`) |
| **B11** | `4.5s` | Slow wet-steel push-in (`MS`) | Cobalt static mist curling off Renji's white-taped knuckles -> broken shades in rainbow puddle, Masato's smoldering pinstripe lapel | Locked **`1.0x` playback speed** for native Japanese mouth & smirk alignment | **`v2_04` Native JP Lip-Sync:** Renji: 「あんたの時計、ちょっと遅れてるぜ、スーツ野郎。」 (*"Guess your clock runs a little slow, suit."*) | **Generated Live (`v2_04`)** |
| **B12** | `1.6s` | End card smash | `DEAD CHANNEL 13 // END` | `24fps`, clean fade-out | Muted brass jazz chord tail in steady night rain | In Cut |

---

## 3. Live Showcase Verification Scope (`DEAD_CHANNEL_13_OPTION2_SAKUGA_REBUILD_JP_SUB.mp4`)

To prove the full v2.0 pipeline end-to-end without inflating generation latency, **2 new keyframes** (`Nano Banana 2`) and **4 new video clips** (`Omni 1.2 Flash`) were produced live in Google Flow for the Option 2 Showcase:
1. `frames_v2/sakuga_kf1_fisheye_blitz.webp` -> `videos_v2/v2_01_fisheye_blitz.mp4` (**14mm Fisheye Melee Blitz**)
2. `frames/cut_03_canon.webp` -> `videos_v2/v2_02_sora_native_jp.mp4` (**Sora Native Japanese Lip-Sync**)
3. `frames_v2/sakuga_kf2_blade_clash_sakuga.webp` -> `videos_v2/v2_03_blade_clash_sakuga.mp4` (**Extreme Dutch Blade & Lightning Clash**)
4. `frames/cut_05_canon.webp` -> `videos_v2/v2_04_renji_native_jp.mp4` (**Renji Native Japanese Lip-Sync**)
