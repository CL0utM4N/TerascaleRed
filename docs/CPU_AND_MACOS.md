# CPU cores and macOS versions

The GPU decides the newest macOS TerascaleRed can use (High Sierra 10.13.6 ships the last TeraScale 1 and 2 drivers). The
CPU cores decide the oldest, and whether emulation is needed at all.

| Platform | Cores (family) | SSE3 | SSSE3 | SSE4.1/4.2 | AVX |
|---|---|---|---|---|---|
| Llano | K10 "Husky" (12h) | yes | **no** | **no** (SSE4a only) | no |
| Brazos | Bobcat (14h) | yes | yes | **no** (SSE4a only) | no |
| Trinity/Richland | Piledriver (15h) | yes | yes | yes | yes |
| RS780/RS880 boards with FX | Bulldozer/Piledriver (15h) | yes | yes | yes | yes |
| RS780/RS880 boards with Phenom II/Athlon II | K10 (10h) | yes | **no** | **no** | no |

What macOS expects:
- **Since Lion (10.7), SSSE3.** The old AMD kernels for K10 (Phenom, Llano) carried opemu, an SSE3/SSSE3 emulator
  that traps the invalid-opcode fault; `corecrypto` uses `PSHUFB` (SSSE3) early in boot.
- **El Capitan (10.11) is the last release that supported CPUs without SSE4.1:** it still ran on 2007 Merom Macs.
  Sierra and later dropped them; MouSSE (a kext emulating a few SSE4.2 instructions for Penryn Mac Pros) exists
  because later drivers use them.
- **OpenCore's AMD Vanilla patches** cover family 15h and later only. Llano (12h) and Brazos (14h) need other kernel
  patches or a custom kernel.

## Per target

- **Trinity/Richland:** no emulation; AMD Vanilla patches; macOS limited only by the GPU work.
- **RS780/RS880:** the GPU is on the motherboard, so the CPU is a choice. AM3+ 760G/880G boards take FX CPUs: no
  emulation, AMD Vanilla patches. With K10, the same as Llano.
- **Brazos:** El Capitan with AMD kernel patches, no emulation. High Sierra would need SSE4.1 emulation for whatever
  uses it (unknown).
- **Llano:** SSSE3 emulation on any release since Lion, plus SSE4.1 on Sierra and later. Quickest: **El Capitan with
  an existing opemu AMD kernel** (published El Capitan kernels with OpEmu3 exist). High Sierra on K10 is effectively
  abandoned: the AMD High Sierra kernels targeted CPUs with SSE4.1.

## A Lilu emulator instead of a custom kernel

MouSSE shows a kext can trap invalid opcodes in both kernel and user mode and emulate instructions, from El Capitan
through Monterey (closed source; it loads early by sorting first, "AAA"). A Lilu plugin routing XNU's invalid-opcode
handling to an opemu port (open source, Sinetek/AnV) would let Llano boot a vanilla kernel with OpenCore patches, so
Lilu's symbol solving and the CarrizoRed-style tracing keep working. Costs: each trapped instruction takes thousands
of cycles (libraries that check CPUID pick SSE2/3 paths; code that assumes SSSE3 crawls), and the hook must be live
before `corecrypto` runs.

## The kext itself

`TerascaleRed.kext` is built with `-mno-ssse3` (KaberiRed's flags have `-mssse3`) and for macOS 10.11, so it never
needs the emulator it may run before.

## Sources

- K10 lacks SSSE3: [15h.org: K10](https://15h.org/index.php/K10)
- SSSE3 since Lion, emulation is a kernel matter: [OSXLatitude](https://osxlatitude.com/forums/topic/6655-dell-precision-670-paxville-bios-a07-gt210-black-screen-ml-m/page/8)
- OpEmu3 kernels for non-SSSE3 AMD CPUs up to El Capitan: [InsanelyMac](https://www.insanelymac.com/forum/topic/302641-guide-installing-os-x-108-1012-under-vmware-workstation-8-9-10-player-6-with-amd-host-cpu/)
- `corecrypto` and `PSHUFB`: [Running OS X under KVM on AMD](https://www.ulduzsoft.com/?p=857)
- AMD Sierra/High Sierra kernels for CPUs with SSE4.1: [InsanelyMac](https://www.insanelymac.com/forum/topic/312714-amd-macos-1012x-sierra-kernel-testing-release-for-help-use-the-help-topic/page-30)
- MouSSE: [MacRumors](https://forums.macrumors.com/threads/2206682)
