# DualSense output: rumble, adaptive triggers, lightbar (ml2106/ml2107)

## Özet (sahibi için)

Oyunun DualSense'e yazdığı her şey artık gerçek kola gidiyor -- iOS'un izin
verdiği kadarıyla:

- **Titreşim (rumble):** oyunun iki motor değeri (büyük/düşük frekans sol,
  küçük/yüksek frekans sağ) CoreHaptics ile kolun sol ve sağ tutamağında
  sürekli titreşim olarak çalınıyor; şiddet motor değerini izliyor, değer 0
  olunca duruyor.
- **Adaptif tetikler (L2/R2):** Sony'nin tetik efektleri (feedback, weapon,
  vibration, bölgesel/çok noktalı varyantlar, bow, galloping, machine) en
  yakın `GCDualSenseAdaptiveTrigger` moduna çevriliyor.
- **Işık çubuğu rengi** ve **oyuncu LED'leri** (1-4) uygulanıyor.
- **XInput titreşimi:** DualSense modunda olmayan, normal XInput oyunlarının
  titreşimi de (XInputSetState) artık kolda hissediliyor (64-bit oyunlar;
  32-bit oyunlar için i386 farm'ın bir kez yeniden derlenmesi gerekiyor).
- **Olmayanlar (iOS izin vermiyor):** ses tabanlı "HD haptics" (PC'de oyun
  bunları kolun USB ses kanallarına ses olarak gönderir; iOS'ta uygulamanın
  kolun ses arabirimine erişimi yok), kolun hoparlörü, mikrofonu, mikrofon
  LED'i, LED parlaklığı/animasyonları, Apple'ın modlarında karşılığı olmayan
  tetik parametreleri (bow'un geri tepme kuvveti, galloping ritmi).
- **Kapatmak için:** oyunun ayarında veya madeira.cfg'de
  `env.MADEIRA_PAD_OUTPUT = 0` (hepsi kapalı), `hid` (yalnız DualSense
  çıktısı), `xinput` (yalnız XInput titreşimi). Varsayılan: açık.
- **God of War testi:** oyunun dosyasında `env.MADEIRA_PAD_MODE = dualsense`
  (veya Session menüsü > Controller > DirectInput / HID), Madeira'yı kapatıp
  aç. Oyunda vuruş/darbe anında titreşim, menüde/eylemde tetik direnci, ışık
  çubuğu renginin değişmesi beklenir. Logda `[hidpad-out]` satırlarına bak
  (aşağıda "Device test plan").
- **Önemli bilinmeyen:** sanal kol USB'li (kablolu) bir DualSense gibi
  görünüyor. Sony'nin PC portları kablolu DualSense'te titreşimi çoğunlukla
  ses kanalı üzerinden (HD haptics) gönderir. Bizim sanal kolumuzun ses
  arabirimi yok; oyun bu durumda klasik motor titreşimine düşerse
  hissedeceksin, düşmezse log'da "no rumble bit" sayacı yüksek çıkar. O
  zaman bir sonraki adım kolu Bluetooth DualSense gibi göstermek (çözücü
  bunun için hazır; aşağıda "USB or Bluetooth").

## How it works

```
game (libScePad / SDL / hidapi)                game (XInput)
  WriteFile / IOCTL_HID_SET_OUTPUT_REPORT        XInputSetState(i, &vib)
        |                                              |  xinput1_x (tools/patch-wine-xinput-vibration.py)
        v                                              v
wineserver: build/wineserver/hidpad_ios.c      win32u: NtUserGetGamepadState(i, op 2, &vib)
  hidpad_dualsense_output()                      build/win32u-unix/driver_ios.c ios_gamepad_query
  (build/hidpad/hidpad_reports.h)                      |
  [hidpad-out] ml2106 log                              |
        v                                              v
   winios_hidpad_set_output()               winios_gamepad_set_vibration(i, left, right)
        \______________ app/Madeira/Winios/WiniosGamepad.c ______________/
                    on a change: the app's notify hook (any thread)
                                   |
                     one dispatch to the main thread (coalesced)
                                   v
         app/Madeira/PadOutput.m  (mapping: Winios/WiniosPadEffects.h)
           CoreHaptics engines from GCController.haptics (left/right handle)
           GCDualSenseAdaptiveTrigger, GCDeviceLight, GCController.playerIndex
           [hidpad-out] ml2107 log
```

Everything runs in the app's own process (the wineserver and win32u's unix
side are in-process), so the hand-over is a mutex-protected snapshot with a
serial, as for input. The writers call a notify hook only when the state
changed; the hook schedules at most one main-thread pass at a time, which reads
the newest state and applies only what differs from what it applied before.
There is no timer and no polling: when the game sends nothing, nothing runs.

Session wiring (`app/Madeira/GamepadInput.swift`): `beginPadSession` (before
the wineserver starts) reads `env.MADEIRA_PAD_OUTPUT` and calls
`madeira_pad_output_configure(xinput, hid)`; `refreshControllers` reports the
physical pad of each XInput slot (`madeira_pad_output_set_slot`; slot 0 is also
the HID pad's player 1); app inactive/background stops all motors and turns
the adaptive triggers off, becoming active again re-applies the game's last
state (`madeira_pad_output_set_active`).

When the game closes its last handle to the HID pad (quit or crash) the
wineserver zeroes the rumble and sets both trigger effects to off; when an
XInput game process ends normally, xinput's DLL_PROCESS_DETACH stops its
motors. The lightbar and player LEDs stay as the game left them.

## What the game writes: the DualSense output report

Sources: Linux `drivers/hid/hid-playstation.c` (`struct
dualsense_output_report_common`, `DS_OUTPUT_VALID_FLAG*`, `player_ids`), SDL
`src/joystick/hidapi/SDL_hidapi_ps5.c` (`DS5EffectsState_t`,
`HIDAPI_DriverPS5_UpdateEffects`), both read at master on 2026-10-01, and the
community "SetStateData" layout (Nielk1 / controllers wiki, from memory, for
the power-reduction byte only).

| Transport | Report | Length | Common block | Extra |
| --- | --- | --- | --- | --- |
| USB | `0x02` | 48 (Linux sends 63) | `[1..47]` | -- |
| Bluetooth | `0x31` | 78 | `[3..49]` | `[1]` sequence << 4, `[2]` 0x10, CRC-32 of `0xA2` + `[0..73]` at `[74..77]` |

Common block offsets (`c[n]`):

| Offset | Field | Used here |
| --- | --- | --- |
| 0 | valid_flag0: 0x01 compatible vibration, 0x02 haptics select, 0x04 R2 effect, 0x08 L2 effect, 0x10-0x80 audio volumes/control | rumble if 0x01 or 0x02; triggers |
| 1 | valid_flag1: 0x01 mic LED, 0x02 power save/mute, 0x04 lightbar, 0x08 release LEDs, 0x10 player LEDs, 0x20 haptics low-pass, 0x40 motor power level | mic LED (log), lightbar, player LEDs, power level; low-pass logged |
| 2 / 3 | motor_right (small, high frequency) / motor_left (large, low frequency) | rumble |
| 4..7 | headphone, speaker, mic volume, audio control | no (no audio on iOS) |
| 8 | mic LED (0 off, 1 on, 2 pulse) | logged only |
| 10..20 / 21..31 | R2 / L2 trigger effect (mode + 10 parameters) | triggers |
| 36 | power reduction: low nibble triggers, high nibble rumble, 0-7 = 12.5 % steps | scales strengths |
| 38 | valid_flag2: 0x01 LED brightness, 0x02 lightbar setup, 0x04 improved rumble emulation ("vibration v2", firmware 2.24+) | rumble if 0x04 |
| 41 / 42 | lightbar setup / LED brightness | no |
| 43 | player LEDs, bits 0-4 (0x20 = instant) | playerIndex |
| 44..46 | lightbar red, green, blue | GCDeviceLight |

Rumble counts when any of the three rumble bits is set: Linux sets haptics
select with either rumble flag, SDL uses valid_flag2 0x04 alone on firmware
2.24+, which our feature report 0x20 announces (update version 0x0224). Before
ml2106 only valid_flag0 was looked at.

Trigger effect blocks (Nielk1's TriggerEffectGenerator, the encoder of
libScePad's modes that DSX and DS4Windows follow):

| Mode | Name | Parameters | iOS mode |
| --- | --- | --- | --- |
| 0x05 (0x00) | off | -- | `setModeOff` |
| 0x21 | feedback | `[1..2]` 10-zone mask, `[3..6]` 3 bits/zone = strength-1 | one strength from a start zone on: `setModeFeedbackWithStartPosition:resistiveStrength:` (zone/9, strength/8); any other pattern: `setModeFeedbackWithResistiveStrengths:` (10 positions) |
| 0x25 | weapon | `[1..2]` start+end zone bits, `[3]` strength-1 | `setModeWeaponWithStartPosition:endPosition:resistiveStrength:` |
| 0x26 | vibration | zone mask, 3 bits/zone = amplitude-1, `[9]` Hz | `setModeVibrationWithStartPosition:amplitude:frequency:` (Hz/255) or `setModeVibrationWithAmplitudes:frequency:` |
| 0x22 | bow | start+end, strength-1, snap force-1 | weapon (no snap-back on iOS) |
| 0x23 | galloping | start+end, feet timing, Hz | vibration at 0.5 amplitude (no rhythm on iOS) |
| 0x27 | machine | start+end, amplitudes A/B (0-7), Hz, period | vibration at max(A,B)/7 |
| 0x01 / 0x11 | simple / limited feedback | position 0-255, strength 0-255 / 0-10 | feedback |
| 0x02 / 0x12 | simple / limited weapon | start, end, strength | weapon |
| 0x06 | simple vibration | Hz, amplitude, position | vibration |
| 0xfc-0xfe | debug / calibration | -- | left as is |

The positional modes (iOS 15.4+) are sent with `objc_msgSend` behind
`respondsToSelector:` using a struct identical to Apple's (`float values[10]`),
so `PadOutput.m` does not depend on their exact SDK spelling; without them the
single-value mode closest to the pattern is used (the log says so).

## USB or Bluetooth, and what Sony's ports read

The virtual pad is a **wired (USB) DualSense**: `HID#VID_054C&PID_0CE6&MI_03`,
the controller's 273-byte USB report descriptor, input report 0x01 (64 bytes),
output report 0x02 (48 bytes), feature reports 0x05 (calibration), 0x09
(pairing address) and 0x20 (firmware 0x0224) answered with content, every other
feature report read as zeros, feature writes accepted and ignored. Phase 1's
device test showed God of War accepts this (PlayStation prompts).

Over USB, Sony's PC ports are widely reported to send their **haptics as
audio** (not verified here) to the pad's USB
audio interface (4 channels; 3 and 4 drive the actuators) and use the output
report for triggers and LEDs; motor rumble is the fallback without that audio
path, and the path a Bluetooth pad gets. Our device has no audio interface (and
an iOS app cannot reach the real pad's), so it depends on libScePad whether a
game then falls back to motor rumble (which we play) or sends nothing.
`hidpad_ios.c` counts it: the `[hidpad-out] ml2106 N effects reports: rumble
a, no rumble bit b, ...` tally. Many reports with "no rumble bit" and none
with rumble while the game shakes the screen means the game expects audio
haptics.

The next lever in that case is presenting the pad as a **Bluetooth DualSense**
(`HID\{00001124-...}_VID&0002054C_PID&0CE6`, BT report descriptor, input 0x31
with CRC, output 0x31): over Bluetooth Sony's ports use motor rumble, and the
decoder already accepts 0x31 output reports with their CRC (host-tested). Not
done here: it needs the controller's Bluetooth report descriptor byte for byte,
new input report framing and registry paths, and a device test; whether a
given port keeps adaptive triggers over Bluetooth varies by game.

## Mapping, feature by feature

| Game feature | iOS | Notes |
| --- | --- | --- |
| Rumble (motor pair, "rumble emulation") | CoreHaptics: one continuous event per handle engine (`GCHapticsLocalityLeftHandle` = large/low motor, sharpness 0.2; `RightHandle` = small/high, 0.6); intensity control = motor/255 x power reduction; stop at 0 | pads without separate handles: one engine at max(left, right) |
| XInput rumble | same engines, wLeft/RightMotorSpeed / 65535 | slot by slot; HID player 1 takes the max of both |
| Adaptive triggers | closest `GCDualSenseAdaptiveTrigger` mode (table above) | positions 0..1 of travel; strengths/amplitudes 0..1 |
| Trigger power reduction | strengths x (1 - n/8) | |
| Lightbar colour | `GCController.light.color` | brightness/fade not exposed |
| Player LEDs | `GCController.playerIndex` (Sony patterns 0x04/0x0a/0x15/0x1b -> 1-4; others by lit count, max 4) | arbitrary patterns impossible |
| Mic LED | -- | logged once; no API |
| HD haptics (audio channels 3/4) | -- | no API: an app cannot open the pad's audio interface; GameController/CoreHaptics take haptic patterns, not the game's audio stream |
| Haptics low-pass filter flag | -- | logged ("haptics low-pass") |
| Speaker, headset, mic, volumes | -- | no API |

## Switches

| Key | Default | Effect |
| --- | --- | --- |
| `env.MADEIRA_PAD_OUTPUT` | on | `0`/`off`: nothing goes to the pad, XInput reports no motors; `hid`: only the DualSense's output reports; `xinput`: only XInput rumble. Game file > madeira.cfg > environment; read at session start. |
| `env.MADEIRA_PAD_MODE` | XInput | `hid`/`dualsense` makes the virtual DualSense whose output this applies (phase 1, `docs/CONTROLLERS.md`). |
| `MADEIRA_XINPUT_RUMBLE_BUILD` (CI env) | 1 | `0`: `tools/build-wine-extra-dlls.sh` keeps upstream's xinput DLLs. |

Nothing changes for input: the input reports, XInput states and God of War's
controller path are untouched. With output off the only difference from
before is the log line.

## Logs

- `[hidpad-out] ml2106 session env.MADEIRA_PAD_OUTPUT=1 xinput-rumble=1
  dualsense-output=1` (app, session start) and `[hidpad-out] ml2106 session
  output: xinput-rumble=1 hid=1` (PadOutput.m).
- `[hidpad-out] ml2106 #n via write|ioctl report 0x2: flags f0/f1/f2 rumble L.. R..
  power .. | L2 <mode> <11 bytes> | R2 <mode> <11 bytes> | lightbar rrggbb
  players .. mic ..` for the first 12 effects reports, then a tally at 100,
  1000, 10000 ... reports (wineserver).
- `[hidpad-out] ml2107 slot 0 haptics: left + right handle engines` (first
  rumble on a pad), `ml2107 slot 0 rumble low 0.50 high 0.20` (first 8 non-zero
  levels), `ml2107 L2: sony feedback (0x21) -> feedback start 0.33 ...` (first
  16 trigger changes), `ml2107 lightbar ...`, `ml2107 player LEDs 04 ->
  playerIndex 1`, a pass tally at 100, 1000, ...; failures: `ml2107 slot N
  haptics <step> failed: <reason>` (3 max), `haptic engine N stopped/reset`.
- `[hidpad-out] ml2106 last handle closed: rumble stopped, triggers off`.

## Device test plan

Needs an IPA built from this (native code changed: wineserver, win32u, app;
plus the rebuilt arm64ec xinput DLLs). DualSense paired over Bluetooth before
the start.

1. **God of War (HID).** Game sheet > madeira-bcd: controller > Controller API
   = DirectInput / HID (or `env.MADEIRA_PAD_MODE = dualsense` in its file);
   quit Madeira, start again, start God of War.
   - Log at start: `[hid-pad] ml2100 session mode=... kind=dualsense`,
     `[hidpad-out] ml2106 session ... dualsense-output=1`, `ml2101 device
     dualsense ...`, then `[hidpad-out] ml2106 #1 via ...` lines.
   - Feel/see: menus and combat -- triggers stiffen or buzz (`ml2107 L2:/R2:`
     lines), rumble on hits, throws and recalls (`ml2107 slot 0 rumble`),
     a lightbar colour set by the game (`ml2107 lightbar`, if it sets one),
     player LED (`player LEDs 04 -> playerIndex 1`).
   - If there is no rumble: send the tally line (`ml2106 N effects reports:
     rumble a, no rumble bit b, triggers c ...`). b >> a = the game wants audio
     haptics over USB (see "USB or Bluetooth").
   - Home button / app switcher: rumble stops, triggers go slack; back in the
     game they come back with the next report (or at once for triggers).
   - Quit the game: `last handle closed: rumble stopped, triggers off`.
   - Input must be exactly as before (buttons, sticks, PS prompts).
2. **Any XInput game with rumble** (default mode, e.g. a racing or shooter
   game): rumble on impacts; log `[hidpad-out] ml2106 session ...
   xinput-rumble=1`, `ml2107 slot 0 haptics: ...`, `ml2107 slot 0 rumble
   ...`. CI log notice `xinput with host rumble (ml2106): replaced 4 shipped
   DLLs`.
3. **Off switch:** `env.MADEIRA_PAD_OUTPUT = 0` in God of War's file: no
   `ml2107` lines, no rumble, triggers free; input unchanged.

## Verified on the host (2026-10-01)

- `tests/host/check-pad-output.py` (new; clang and gcc): USB reports as Linux
  (rumble v1) and SDL (v2, valid_flag2 only) write them, a triggers-only
  report keeps the motors, LEDs/power reduction, a Bluetooth 0x31 report
  framed as SDL frames it (CRC-32 known answer, seed 0xA2; a flipped CRC bit
  is rejected), every trigger mode produced by a C transcription of Nielk1's
  generator decoded to the expected iOS mode and values, rumble/XInput levels,
  player LED mapping, the notify transport; and the wiring PadOutput.m /
  Xcode project / bridging header / GamepadInput.swift / driver_ios.c /
  build script, plus the xinput patch applied (twice: idempotent) to the wine
  submodule's `dlls/xinput1_3/main.c`.
- `tests/host/check-gamepad.py` (extended): op 2 stores the motors, notifies
  once per change, ignores empty slots; caps report motors only while the app
  plays them.
- `tests/host/check-hidpad.py`: still PASS (descriptors, input/feature/output
  reports through Wine's hidparse + hid.dll).
- `hidpad_ios.c` syntax-checked against the pinned wine/server headers with
  CI's forced includes (stub config.h); the patched xinput `main.c`
  syntax-checked for x86_64, i686 and aarch64 mingw targets against the wine
  headers; `PadOutput.m` syntax-checked with ARC against stub
  GameController/CoreHaptics headers written from the SDK API (catches this
  file's own mistakes, not SDK spelling).
- `ConfigCatalog.generated.swift` regenerated with the pinned submodules (the
  same method reproduces HEAD's committed catalog byte for byte first).
- **Not checked:** compiling the Swift and ObjC against the real iOS SDK, the
  arm64ec xinput build in CI, anything on a device.

## Durum 2026-10-02 -- duraklatıldı (sahibi: "dualsense şimdilik yeterli")

- **Çalışıyor (build 336, sahibi doğruladı, GoT logu 17:21:41):** titreşim
  (rumble), adaptif tetikler (R2 feedback 0x21, vibration 0x26), ışık çubuğu,
  oyuncu LED'i; kol girişi zaten çalışıyordu. Sanal kol USB'li göründüğü
  halde oyun motor titreşimine düşüyor (1000 raporun 992'sinde rumble biti),
  yani Bluetooth görünümüne gerek kalmadı.
- **Build 336 düzeltmesi (PadOutput.m):** iOS bir oyun kolunda "advanced"
  oynatıcıyı "Couldn't communicate with a helper application" ile
  reddediyor ve bu motorun bağlantısını bozuyordu; build 335'te sonraki basit
  oynatıcı da aynı motorda düşüyor, üç hatadan sonra titreşim oturum boyunca
  kapanıyordu (GoW logu 16:38:12). Artık yalnızca basit oynatıcı, her
  denemede yeni motor, hata olursa 2/4/8/15 sn arayla yeniden deneme, iki
  erken hatada tek motora geçiş, 8 hatada vazgeçme.
- **Hissedilen şey basit titreşim**, PS5'teki ses tabanlı "haptic feedback"
  değil: o, PC'de kolun USB ses kanalından gidiyor (kablo şart); sanal
  kolumuzun ses kısmı yok.
- **God of War:** tetiklere efekt göndermiyor (yalnız "off"); 336'daki
  titreşim GoW'da cihazda henüz denenmedi (çalışması bekleniyor).
- **Sonra (sahibinin kararı, GTA'dan sonra):** gerçek haptic projesi --
  sanal DualSense'e 4 kanallı "Wireless Controller" ses aygıtı eklemek ve
  kanal 3/4'ü anlık olarak Core Haptics'e çevirmek; iOS'ta denenmemiş,
  gecikme/kalite bilinmiyor.
- **Küçük açıklar:** sağ tutamak motoru henüz hiç istenmedi (test
  edilmedi); basit oynatıcı 25 sn'de bir yeniden başlatılıyor (kısa bir
  kesinti hissedilebilir); 32-bit XInput oyunları için i386 farm'ın
  xinput yaması; mikrofon LED'i için API yok.

## Open

- Device test (above). Tune: motor sharpness, linear vs curved intensity,
  vibration frequency scale (Hz/255) once felt.
- If God of War sends no motor rumble on the USB presentation: Bluetooth
  presentation (`dualsense-bt` identity), see above.
- 32-bit XInput games: the i386 farm's xinput is unpatched; applying
  `tools/patch-wine-xinput-vibration.py` in `build/wine-i386/build.sh`
  (before `make`, restored after) changes the farm's cache key and so rebuilds
  the whole farm once.
- WM_INPUT, touch coordinates, gyro (phase 3 of the HID pad) unchanged.

## HANDOFF paragraph (for docs/HANDOFF.md, "DualSense / DirectInput (second agent)")

* **2026-10-01 (Claude, DualSense output agent, worktree branch, local only:
  not pushed, no CI run).** Phase 2 -- the game's output reaches the real
  pad -- done in code, not device-tested. Doc: `docs/dualsense-output.md`.
  Found: the wineserver already parsed output report 0x02 into
  `winios_hidpad_get_output`, but only rumble with valid_flag0 bits (SDL's
  firmware-2.24 "vibration v2" sets valid_flag2 0x04 alone and was missed),
  and nothing on iOS read it; XInputSetState on a host pad returned
  ERROR_SUCCESS and dropped the motors (xinput1_3 main.c), caps said "no
  motors". Built (ml2106/ml2107): decoder for USB 0x02 and Bluetooth 0x31
  (CRC-32 seed 0xA2) with all three rumble bits and the power-reduction byte
  (`build/hidpad/hidpad_reports.h`); bounded `[hidpad-out]` log + tally and
  rumble/trigger reset on the last handle close (`hidpad_ios.c`); notify hook +
  XInput vibration snapshot (`WiniosGamepad.[ch]`); win32u op 2 and motor
  caps (`driver_ios.c`); xinput patch (`tools/patch-wine-xinput-vibration.py`,
  SetState/Enable/process detach) applied by `tools/build-wine-extra-dlls.sh`,
  which now rebuilds arm64ec xinput1_1-1_4 and replaces the shipped copies
  (only exception to "never replaces"); trigger/rumble/LED mapping
  (`app/Madeira/Winios/WiniosPadEffects.h`); apply layer `app/Madeira/PadOutput.m`
  (CoreHaptics left/right handle engines, GCDualSenseAdaptiveTrigger incl.
  positional modes via objc_msgSend, GCDeviceLight, playerIndex; main thread,
  event-driven, stops/resets on background), wired from GamepadInput.swift;
  Xcode project + bridging header; switch `env.MADEIRA_PAD_OUTPUT` (default
  on; 0 / hid / xinput) in the catalog. Host: check-pad-output (new),
  check-gamepad, check-hidpad PASS; hidpad_ios.c / patched xinput / PadOutput.m
  syntax-checked; catalog current. **Open:** device test (God of War
  `env.MADEIRA_PAD_MODE = dualsense`: `[hidpad-out] ml2106 #n`, `ml2107
  L2:/R2:`, `slot 0 rumble`, `lightbar`; an XInput game: `ml2107 slot 0
  rumble`); if GoW's tally shows only "no rumble bit" (audio haptics over USB)
  -> Bluetooth presentation; 32-bit xinput needs the i386 farm rebuilt with
  the patch. Impossible on iOS: audio HD haptics, speaker, mic, mic LED, LED
  brightness, bow snap force / galloping rhythm.
