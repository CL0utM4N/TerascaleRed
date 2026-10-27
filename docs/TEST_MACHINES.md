# Test machines

What TerascaleRed is (or will be) tested on, and what's still wanted. The plan in [ROADMAP.md](ROADMAP.md)
(Phase 1) favours desktops: a socketed CPU, a PCIe slot for a working dGPU while the iGPU is tested headless, and
often a serial header. Laptops lack all three, so each laptop below lists what it can and can't be used for.

## In hand

| Machine | APU | iGPU | dGPU | Covers |
|---|---|---|---|---|
| Samsung Series 3 NP305V5A-S0BAU (laptop) | A8-3530MX (Llano, K10, 4 cores, 45 W) | Radeon HD 6620G, 400 SPs (Sumo; expected `1002:9641`) | To confirm: A8 variants of this model shipped with a switchable HD 6470M or HD 6630M | Llano |

### Samsung NP305V5A-S0BAU

**Use it for:**
- **Reference data from Linux:** the VBIOS from the ACPI VFCT table, `radeon` register dumps of a working display
  (DCE 4.1) and accelerator, and `lspci -nn` for the exact iGPU (and any dGPU) IDs. Sumo with 400 SPs is the
  full-size Llano GPU, the closest to the Redwood spoof target.
- **Llano bring-up once another target works:** the CPU needs SSSE3 emulation on every release since Lion
  ([CPU_AND_MACOS.md](CPU_AND_MACOS.md)), so a panic here may be the emulator rather than the kext. Prove the method
  on a target that needs no emulation first.

**Limits:**
- **CPU:** K10 (family 12h): no SSSE3, no SSE4.1, not covered by AMD Vanilla. El Capitan with an opemu AMD kernel is
  the quickest path.
- **No headless testing:** no PCIe slot for a working dGPU, and no serial header. The black box (NVRAM breadcrumb,
  panic report) and the per-boot disk log carry the diagnostics.
- **Switchable dGPU (if fitted):** on Llano laptops it's normally muxless, with no display outputs of its own, so it
  can't stand in as the working GPU. Turn it off with an SSDT (`_OFF`/`_PS3`) from the first boot, to keep it out of
  the logs and save power and heat.

To fill in: BIOS version, whether the BIOS offers UEFI boot, RAM, and the `lspci -nn` output.

## Wanted

| Priority | Target | Suggested hardware | Why |
|---|---|---|---|
| 1 | RS780/RS880 | AM3+ 760G or 880G board with an FX-4300/6300 | No CPU emulation, no shader work: the quickest proof of the CAIL-spoof method |
| 2 | Trinity/Richland | A10-5800K or A8-5600K on an FM2 board (or an A8-4500M/A10-4600M/A10-5750M laptop) | Piledriver cores: SSE4.2, AVX, AMD Vanilla. Hardest GPU (VLIW4, DCE 6.1) |
| 3 | Brazos | Any E-350/E-450 machine | El Capitan without emulation (Bobcat has SSSE3) |
| - | Llano | Covered by the Samsung above; an FM1 A75 desktop with UEFI would add headless testing | |

Reports from owners of any target are welcome: open an issue with the model, `lspci -nn` and (once there's a
release) the logs.
