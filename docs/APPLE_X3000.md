# Apple's TeraScale 2 drivers (macOS 10.13.6)

What's in the kexts and bundles TerascaleRed adapts, from static analysis of the 10.13.6 binaries that OpenCore Legacy
Patcher's PatcherSupportPkg carries (`scripts/fetch_x3000.py` fetches them). Symbol names are as the binaries export
them. Nothing here has been checked on hardware yet.

## AMDRadeonX3000.kext (accelerator)

### What it matches

| Personality (`IOClass`) | `IOPCIMatch` (device IDs, vendor 1002) | GPU |
|---|---|---|
| `AMDCypressGraphicsAccelerator` | 6898, 6899 | Cypress (HD 5850/5870) |
| `AMDJuniperGraphicsAccelerator` | 68B8, 68B0, 68B1, 68A0, 68A1 | Juniper (HD 5750/5770) |
| `AMDRedwoodGraphicsAccelerator` | 68D8, 68C0, 68C1, 68D9 | Redwood (HD 5670) |
| `AMDCedarGraphicsAccelerator` | 68E0 | Cedar |
| `AMDBartsGraphicsAccelerator` | 6738, 6739, 6720, 6722 | Barts |
| `AMDTurksGraphicsAccelerator` | 6750, 6758, 6759, 6740, 6741, 6745 | Turks (6750M/6770M) |
| `AMDCaicosGraphicsAccelerator` | 6768, 6770, 6779, 6760, 6761 | Caicos (6490M) |
| `AMDLombokGraphicsAccelerator` | 6840, 6841 | "Lombok": Turks-family "Thames" mobile parts in Linux's list |

No APU, and no Cayman. Hardware classes: `AMDR8xxHardware` (base), `AMDNIHardware`, and one per GPU above.

**Lombok** is the template for adding a variant: `AMDLombokHardware` subclasses `AMDTurksHardware` and overrides only
`getATIChipConfigBit()` (returns `0x4000000`) and `readChipRevFromRegister()` (defaults to `0x32`), with a matching
`CAIL_DDI_CAPS_LOMBOK_A11`. A Devastator or Sumo class would look the same.

### CAIL: the APU paths are there

The kext embeds AMD's CAIL, shared with the GCN drivers (it also holds Bonaire, Baffin, Ellesmere, Fiji and Carrizo
microcode tables). For the TeraScale APUs and Cayman:

| | Llano | Brazos | Trinity/Richland | Cayman |
|---|---|---|---|---|
| Capability table | `CAIL_DDI_CAPS_SUMO_A0`, `_B0`; `SUPERSUMO_A0`, `_B0` | `WRESTLER_A0`, `_A1` | `DEVASTATOR_A0`; `SCRAPPER_LITE_A0` | `CAYMAN_A11` |
| Golden settings | `SUMO_GoldenSettings_A11`, `StrippedSUMO_…`, `SuperSUMO_…` (3- and 4-SIMD), `aDowngradeSuperSUMO_…` | `Wrestler_GoldenSettings_A11` | `DEVASTATOR_GoldenSettings_A0`, `SCRAPPER_GoldenSettings_A0` | `CAYMAN_GoldenSettings_A11` |
| RLC microcode | `Sumo_RLC` | (Linux uses Sumo's for Palm) | `Devastator_RLC` | `Cayman_RLC` |
| `Cail_<asic>_*` functions | 13 (`Cail_Sumo_*`) | none of its own | 31 (`Cail_Devastator_*`) | 42 (`Cail_Cayman_*`) |
| Harvest remap | `SumoHarvestRemapTbl` | | | `CaymanHarvestRemapTbl` |

Also: `init_rlc_clear_state_buffer_for_llano_trinity`, `get_clear_state_buffer_size_for_llano_trinity`,
`DevastatorEngineRunningStateRegInfo`, `CaymanEngineRunningStateRegInfo`, `Cayman_init_RLC_legacy_mode`,
`_sTrinityEyefinityNotsupportedDidTbl`, `APUNotSupportDualGraphicsBranding`.

The `Cail_Devastator_*` set covers what an APU bring-up needs: `InitializeClearStateBuffer`,
`GetClearStateAndRlcSaveRestoreRegisterListInfo`, `InitializeRlcHistoryBuffer`, `GetIntegrateAsicFbMcBaseAddr` (the
carve-out), `EnableCGPG`/`EnableDynamicMGPG` (clock and power gating), `EnableF32`, UVD/VCE clocks. `Cail_Sumo_*`
has the Llano equivalents plus `ulNoBiosMemoryConfigAndSize`.

This is the same bet KaberiRed makes on CAIL's Kalindi/Spectre paths: code shipped but never exercised on a Mac.
CarrizoRed's experience with Stoney (CAIL's embedded microcode byte-identical to linux-firmware's; power gating that
needed disabling) is the guide.

### What's missing

- **Command-processor microcode.** PFP/ME images exist only for the seven dGPUs (`CYPRESS_UCODE`, `JUNIPER_`,
  `REDWOOD_`, `CEDAR_`, `BARTS_`, `TURKS_`, `CAICOS_`, each with `aF32_PFP_Ucode` and `aF32_ME_Ucode`). The APUs
  need theirs from linux-firmware's `radeon/` directory (`SUMO_`, `SUMO2_`, `PALM_` and `ARUBA_` PFP/ME files),
  swapped in when the spoofed class loads its own.
- **Hardware classes and matching.** No `AMD<APU>Hardware` and no PCI match: the `device-id` spoof (or an injected
  personality) and Lilu routes do that job.
- To check: whether `Sumo_RLC`/`Devastator_RLC` match linux-firmware's `SUMO_rlc.bin`/`ARUBA_rlc.bin`.

## AMDRadeonX3000GLDriver.bundle (OpenGL)

- Renderer entries for Cayman (`glr_renderer_cayman_pro`, `_xt`, `_unknown`; "Radeon Cayman … Prototype" strings),
  `R800HwResourceConfigTableCayman` and `CaymanLoadContextRegPairs`: user-space state setup for Cayman exists.
- `ATIRadeonX3000SCLib.dylib`, the shader compiler: see [SCLIB_VLIW4.md](SCLIB_VLIW4.md).
- `Libraries/AMDil.dylib` (OpenCL front end to AMD IL) lists `cayman` and `trinity` among its targets.

## Display: AMD5000Controller / AMD6000Controller

| Kext | Display engine | Matches |
|---|---|---|
| `AMD5000Controller` | DCE 4 (Evergreen) | Cypress 6898/6899, Cedar 68E0/68E1, Redwood 68D8/68C0/68C1/68D9, Juniper 68B8/68B0/68B1 |
| `AMD6000Controller` | DCE 5 (Northern Islands) | Caicos 6768/6770/6779/6760/6761, Turks 6750/6758/6759/6740/6741/6745 |

Both carry AMD's PowerPlay with APU back ends: `PhwSumo_Initialize`, `PhwTrinity_Initialize`,
`PP_Sumo_Thermal_Initialize`, `PP_Trinity_Thermal_Initialize`, `PhwDummy_InitSystemInfo_Sumo`;
`AMD5000Controller` also has `CAIL_DDI_CAPS_SUMO_A0`. `AMD6000Controller` has Cayman CAC weights.

Llano and Brazos have DCE 4.1, so `AMD5000Controller` is their display driver. Trinity's DCE 6.1 is closest to the
GCN 1 parts' DCE 6.0 (`AMD7000Controller`, which also ships in High Sierra but belongs to the GCN accelerator); see
the roadmap's open questions.
