# TerascaleRed

A [Lilu](https://github.com/acidanthera/Lilu) plugin that aims to bring macOS graphics (display, then OpenGL
acceleration) to AMD's TeraScale APUs by adapting **Apple's own TeraScale 2 drivers**: the ones macOS High Sierra and
earlier ship for the Radeon HD 5000/6000 GPUs of the 2010–2011 iMacs and MacBook Pros. It's the third of the family:
[CarrizoRed](https://github.com/CL0utM4N/CarrizoRed) does the same for Carrizo/Stoney with Apple's Polaris drivers,
and [KaberiRed](https://github.com/CL0utM4N/KaberiRed) for the GCN 2 APUs with Apple's Bonaire drivers.

**Status: Phase 0 (research and skeleton).** Nothing works yet. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Targets

| Family | Products | PCI IDs | GPU | Display | CPU cores |
|---|---|---|---|---|---|
| Llano ("SUMO"/"SUPERSUMO" in Apple's CAIL) | A4/A6/A8-3xxx, E2-3200 | 1002:9640–964F | TeraScale 2 (VLIW5), up to 400 SPs | DCE 4.1 | K10: **no SSSE3, no SSE4.1** |
| Brazos ("WRESTLER") | E-350/450, C-50/60, E1/E2-1xxx | 1002:9802–980A | TeraScale 2 (VLIW5), 80 SPs | DCE 4.1 | Bobcat: SSSE3, no SSE4.1 |
| Trinity/Richland ("DEVASTATOR"/"SCRAPPER") | A4/A6/A8/A10-5xxx and -6xxx | 1002:9900–99A4 | TeraScale 3 (VLIW4), up to 384 SPs | DCE 6.1 | Piledriver: SSE4.2, AVX |

Exact IDs are in [TerascaleRed/kern_asic.hpp](TerascaleRed/kern_asic.hpp), from Linux's `drm_pciids.h`.

## Why it looks possible

Static analysis of High Sierra 10.13.6's drivers ([docs/APPLE_X3000.md](docs/APPLE_X3000.md)):

- **The accelerator kext already knows these APUs.** `AMDRadeonX3000`'s CAIL has capability tables, golden register
  settings and RLC microcode for Sumo/SuperSumo, Wrestler, Devastator/Scrapper and Cayman, plus 13 `Cail_Sumo_*`,
  31 `Cail_Devastator_*` and 42 `Cail_Cayman_*` functions and a clear-state builder named for Llano and Trinity. No
  Mac ever used them; they came with AMD's code. Missing: command-processor (PFP/ME) microcode for the APUs, and any
  hardware class or PCI match for them.
- **The display controllers carry their PowerPlay.** `AMD5000Controller` and `AMD6000Controller` both have
  `PhwSumo_Initialize` and `PhwTrinity_Initialize`.
- **The shader compiler still has the VLIW4 logic** Trinity needs ([docs/SCLIB_VLIW4.md](docs/SCLIB_VLIW4.md)).
  Apple stripped AMD's Cayman target class from `ATIRadeonX3000SCLib`, but the generic code still asks the target
  `HasTransUnit()` and packs ALU groups Cayman's way when it answers false, and still emits a `CF_END` instruction
  when a second hook says so. Three small patches turn both on; `scripts/sclib_hooks.py` finds and builds them.

## How

As in CarrizoRed and KaberiRed: the iGPU's `device-id` is spoofed to a TeraScale 2 dGPU Apple supports (Redwood for
Llano, the closest match with the same 400 VLIW5 shaders; Turks for Trinity), so Apple's controller and
`AMDRadeonX3000` match it, and every difference between that dGPU and the APU is patched with Lilu routes. AMD's CAIL
inside the accelerator reads the real device ID and should take its own Sumo/Devastator paths.

Trinity's display engine is DCE 6.1, the GCN 1 generation's, while its GPU is TeraScale 3: that split (Apple's DCE 6
controller ships beside `AMDRadeonX3000` in High Sierra, but one `device-id` can't match both) is an open design
question in the roadmap.

## macOS versions

Apple's TeraScale 2 drivers end with High Sierra 10.13.6 (OpenCore Legacy Patcher root-patches them onto later
releases). The CPU narrows it further ([docs/CPU_AND_MACOS.md](docs/CPU_AND_MACOS.md)):

- **Trinity/Richland:** any macOS the GPU work allows, with OpenCore's AMD Vanilla patches (family 15h).
- **Brazos:** El Capitan 10.11, the last release that supported CPUs without SSE4.1, needs no emulation.
- **Llano:** needs SSSE3 emulation on any release since Lion. El Capitan with an existing opemu AMD kernel is the
  quickest path; a Lilu-based emulator is a later goal.

The kext is built for 10.11 and later and **without SSSE3** (`-mno-ssse3`), since it can run before any emulator.

## Building

There's no Mac needed: GitHub Actions builds the kext on a macOS runner (`.github/workflows/build.yml`). On a Mac:

```
./scripts/bootstrap.sh   # fetches Lilu (debug) and MacKernelSDK
make DEBUG=1             # build/Debug/TerascaleRed.kext
```

## Tools (Windows-friendly, Python 3)

| Script | What it does |
|---|---|
| `scripts/fetch_x3000.py` | Fetches High Sierra 10.13.6's TeraScale 2 drivers from OCLP's PatcherSupportPkg (needs git; no Mac) |
| `scripts/sclib_hooks.py` | Finds the VLIW4 hooks in `ATIRadeonX3000SCLib.dylib` and prints the patches, or writes a patched copy (`pip install capstone`) |
| `scripts/macho.py` | Lists symbols of, and disassembles functions in, Apple binaries (from KaberiRed) |

Apple's binaries are never committed: keep them outside the repository (`fetch_x3000.py` defaults to
`../TerascaleRed-RE/10.13.6`).

## Boot arguments

| Argument | Effect |
|---|---|
| `-troff` / `-trdbg` / `-trbeta` | Lilu's: disable, debug logging, run on unsupported macOS (outside 10.11–10.13) |
| `-trnommio` | Don't read the GPU's registers at start-up |

## Licence

BSD 3-Clause, see [LICENSE](LICENSE). Register offsets, PCI IDs and hardware facts come from Linux's `radeon` driver
(MIT). No code from NootedRed or LegacyRed is used.
