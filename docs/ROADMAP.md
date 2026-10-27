# Roadmap

## Phase 0: research and skeleton (now)

- [x] Find Apple's TeraScale 2 drivers without a Mac (`scripts/fetch_x3000.py`, from OCLP's PatcherSupportPkg)
- [x] Inventory APU and Cayman support in `AMDRadeonX3000`, the GL driver and the display controllers
  ([APPLE_X3000.md](APPLE_X3000.md))
- [x] Find the VLIW4 hooks in the shader compiler and build the patches (`scripts/sclib_hooks.py`,
  [SCLIB_VLIW4.md](SCLIB_VLIW4.md))
- [x] Kext skeleton: finds the iGPU by config space, logs PCI info and registers (syntax-checked against Lilu and
  MacKernelSDK headers, and built by CI)
- [x] First CI build (10.11 deployment target, `-mno-ssse3`)
- [ ] Confirm Cayman's `CF_END` opcode and vertex-fetch rule against AMD's Cayman ISA document
- [ ] Compare `Sumo_RLC`/`Devastator_RLC` with linux-firmware's `SUMO_rlc.bin`/`ARUBA_rlc.bin`
- [ ] Get El Capitan 10.11.6's copies of the same drivers (an installer extractor for pre-Big Sur installers; the
  scripts find everything by symbol, so they should carry over)

## Phase 1: observe on hardware

Test machines (desktops: socketed, a PCIe slot for a working dGPU while the iGPU is tested headless, often a serial
header):
- **Trinity/Richland:** A10-5800K or A8-5600K on an FM2 board. Easiest CPU (no emulation), hardest GPU.
- **Llano:** A8-3850/3870K on an FM1 A75 board with UEFI. Closest GPU to an Apple one (Redwood), hardest CPU.

Goals: OpenCore EFI per machine, the kext loads, the iGPU is found, registers read sanely (carve-out, address config,
the GOP's scanout); a black box ported from CarrizoRed/KaberiRed (trace ring, NVRAM breadcrumb, panic report).

## Phase 2: display

- **Llano/Brazos (DCE 4.1):** spoof Redwood (or Cedar) for `AMD5000Controller`; patch display limits (pipes, PLLs),
  the "VRAM" carve-out, the VBIOS source (ACPI VFCT into `ATY,bin_image`, as KaberiRed does).
- **Trinity (DCE 6.1):** `AMD7000Controller` (DCE 6.0) is the nearest display driver, but it belongs to the GCN
  accelerator and matches GCN IDs. Options: an injected personality matching Aruba's real ID for both drivers;
  routing `AMD6000Controller` (DCE 5) onto DCE 6.1 registers; framebuffer only at first.

## Phase 3: accelerator bring-up

- Spoof Redwood (Llano) / Turks (Trinity) for `AMDRadeonX3000`; check CAIL takes the Sumo/Devastator paths from the
  real device ID.
- Swap in the APUs' PFP/ME microcode; UMA (no dedicated VRAM); PowerPlay through `PhwSumo`/`PhwTrinity`; power
  gating off if it hangs (as on Stoney).
- Display-only fallback with the accelerator blocked (`-trnoaccel`, to add).

## Phase 4: shaders

- **VLIW5 (Llano, Brazos):** none expected beyond Redwood's code paths.
- **VLIW4 (Trinity):** apply the three `ATIRadeonX3000SCLib` patches (page-patched as CarrizoRed patches `libSC`);
  check compiled output through OpenCL program binaries on any TeraScale 2 machine first; fix what's left (vertex
  fetch, anything else the stripped Cayman class overrode) in the compiler or at submission time.

## Phase 5: CPU

- A Lilu SSSE3 (and SSE4.1) emulator from opemu, so Llano runs a vanilla kernel ([CPU_AND_MACOS.md](CPU_AND_MACOS.md)).

## Open questions

- Does CAIL's Sumo/Devastator code run cleanly on real hardware? Never exercised on a Mac.
- Which High Sierra driver class can carry Trinity's DCE 6.1 display beside a TeraScale accelerator?
- What else did the Cayman SC class override?
- Brazos on High Sierra: what needs SSE4.1?
