# Apple's TeraScale 1 drivers and the RS780/RS880 chipset GPUs (macOS 10.13.6)

TeraScale 1 never made it into an APU: AMD's first APUs (Llano, Brazos) were already TeraScale 2. It did go into
chipsets, as the northbridge GPU on AM2+/AM3/AM3+ boards:

| Chip | Chipsets | Marketing names | PCI IDs | GPU | Display |
|---|---|---|---|---|---|
| RS780 | 760G, 780G, 790GX | HD 3000/3100/3200/3300 | 1002:9610–9616 | R6xx VLIW5, 40 SPs | AVIVO, DCE 3.x |
| RS880 | 785G, 880G, 890GX | HD 4200/4250/4290 | 1002:9710–9715 | R6xx VLIW5, 40 SPs (an RS780 derivative) | AVIVO, DCE 3.x |

Both use system RAM, plus optional "sideport" memory on some boards. Static analysis of the 10.13.6 binaries in
OCLP's PatcherSupportPkg (`scripts/fetch_x3000.py` fetches them too); nothing checked on hardware.

## ATIRadeonX2000.kext (accelerator)

Matches 34 device IDs: R600, RV610 (`94C8`, `94C9`), RV630, RV635, RV670, RV710, RV730 and RV770. Hardware classes:
`IOATIR600Accelerator`, `ATIRadeonX2000Hardware`, `ATIRadeonX2000AMDRV6xxHardware` with `RV610`/`RV630`/`RV670`
subclasses, and `ATIRadeonX2000AMDR7xxHardware` with `RV710`/`RV730`/`RV770`. No chipset GPU.

**CAIL has the RS780 paths** (37 symbols), as `AMDRadeonX3000` has the APUs':
- `RS780_GoldenSettings`, `aRS780_GoldenRegisterSettings`, `RS780_HwConstants`, `RS780_program_more_register_to_defaults`
- memory: `RS780_GetIntegrateAsicFbMcBaseAddr` (the carve-out), `RS780Atom_ulNoBiosMemoryConfigAndSize`,
  `RS780_cailVidMemSizeUpdate`, `RS780_SetupUMASPInterleaving`/`RestoreUMASPInterleaving`/`AssertUMAInterleaving`
  and `rs780_calculate_sp_interleave_num_chunks` (UMA plus sideport), `rs780_write_nb_mc_ind_reg` (the memory
  controller sits in the northbridge)
- bring-up: `RS780_InitializeRefClkSource`, `RS780_Remove_Soft_Resets`, `RS780_Wait_For_FWV_End`, UVD set-up
- `Rs780Id`, `RS780AsicStateRegInfo_UVD`

RS880 isn't named. Linux treats it as an RS780 variant (same microcode, same code paths), so CAIL may too: to check
in `Rs780Id` and wherever CAIL picks the RS780 paths.

**Microcode.** Command-processor images are named by AMD codename, not chip: `BOOM`, `LAKA` and `SHAKA` (R6xx style,
PFP plus PM4) and `LUIGI`, `MARIO` and `WEKIVA` (R7xx style, F32 PFP/ME), with `AMDR6XX_UCODE`/`AMDR7XX_UCODE` RLC
images. Which, if any, is RS780's is unknown: compare each with linux-firmware's `radeon/RS780_pfp.bin` and
`RS780_me.bin`. The kext also embeds the newer CAIL tables (Sumo, Cayman, Kalindi, Bonaire, …), as X3000 does.

OCLP also carries a different `ATIRadeonX2000` under `10.13.6 TS1` (larger, 32k bytes differ), its build for newer
macOS; TerascaleRed uses the stock one.

## Display: AMD2400–4800Controller, AMDLegacySupport

- Every TeraScale 1 controller (`AMD2400Controller`, `2600`, `3800`, `4600`, `4800`) carries AMD's PowerPlay with a
  full RS780 back end: `PhwRS780_*` (DPM, voltage scaling, clock gating, deep sleep, HyperTransport link width and
  speed, sideport memory clock switching), `PhwDummy_InitSystemInfo_RS780`, `PHM_CF_IsRS780A12OrGreater`, and the
  RS780 MCU firmware (`rs780_MCU_firmware`, `rs780MemoryControllerSettings`).
- `AMDLegacySupport` matches RV610 (`94C8`), RV630, RV670, RV710, RV730 and RV770 IDs, and has ATOM BIOS classes for
  two display generations: `AtiAtomBiosDce31` and `AtiAtomBiosDce32`. Which chips Apple's
  code sends to `AtiAtomBiosDce31`, and whether it fits RS780/RS880's display engine, is the first display question.

## What it means

- **Spoof target:** RV610 (`94C8`): the same R6xx shader core with the same 40 shaders, matched by both
  `ATIRadeonX2000` and `AMDLegacySupport`.
- **No shader work.** RS780/RS880 run the R6xx ISA Apple's TeraScale 1 compiler already targets for RV610.
- **No CPU emulation, with the right board.** 760G and 880G boards for AM3+ take FX (Bulldozer/Piledriver, family
  15h: SSE4.2, AVX) CPUs, which OpenCore's AMD Vanilla patches support. With a Phenom II or Athlon II (K10) the
  SSSE3 problem comes back ([CPU_AND_MACOS.md](CPU_AND_MACOS.md)).
- **Firmware:** most boards of this era are legacy BIOS only, so OpenCore boots through its DuetPkg path; some later
  AM3+ boards have UEFI.
- **Payoff:** 40 shaders and Apple's TeraScale 1 OpenGL, High Sierra at most. This is the easiest TerascaleRed target
  to reach, not the most useful one.
