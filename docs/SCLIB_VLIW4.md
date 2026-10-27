# VLIW4 in Apple's TeraScale 2 shader compiler

Trinity/Richland's GPU (Aruba) is TeraScale 3: VLIW4, like Cayman (HD 69xx). Apple never shipped a VLIW4 Mac, and
its OpenGL driver compiles shaders for VLIW5, which uses a fifth "T" (transcendental) slot that VLIW4 doesn't have.
This page records what is left of VLIW4 support in `ATIRadeonX3000SCLib.dylib` (10.13.6, inside
`AMDRadeonX3000GLDriver.bundle`) and the patches that re-enable it. `scripts/sclib_hooks.py` reproduces all of it from
the binary. Static analysis only: not yet run on a Mac.

## What VLIW4 needs from a compiler

From Cayman's ISA and Mesa's r600 back end:

1. **ALU groups of four.** A transcendental (`RECIP_IEEE`, `RSQ`, `SIN`, `LOG`, …) has no T slot to go to: it is issued
   in the x, y and z slots together (result written once), and the integer multiplies in all four.
2. **Program end.** Evergreen/NI end a program with the end-of-program bit on the last CF instruction; Cayman uses a
   separate `CF_END` instruction.
3. **Vertex fetch.** Cayman drops the vertex cache, so vertex fetches go through texture clauses (to confirm against
   Mesa and the ISA document).
4. Smaller rules: bank-swizzle and constant-read restrictions change with the missing T slot.

## What the binary has

There is one target class, `Cypress` (on `Pele`, AMD's R6xx–R8xx base, on `HwLimits`). AMD's Cayman class is gone,
unlike `libSC` in CarrizoRed's case, which kept a Stoney back end no Mac used. But the generic code still consults
the target object (at assembler + `0x2c8`, compiler + `0x738`) through virtual calls:

| Hook | vtable slot | `HwLimits` | `Pele`/`Cypress` | Read by (on the target object) |
|---|---|---|---|---|
| `HasTransUnit()` | `0x340` | false (`0x1bd60`) | true (`0x1bd70`) | `NumSlotsForInst`, `AssembleIRList` (3 sites), `AssembleNormalInst`, `R600SchedModel::CheckFlexibleScalarInContext` |
| "Cayman" (unnamed) | `0x308` | false | false | `FinishShaderMain` |

**`HasTransUnit() == false` is Cayman's rule 1, intact:**
- `NumSlotsForInst`: an instruction with the transcendental flag takes 4 slots, or 3 depending on the destination's
  write mask; opcodes `0xf7`/`0xf9` (the integer multiplies, by their treatment) always 4.
- `AssembleIRList`: the same instructions reserve slots xyz (`0x7`) or xyzw (`0xf`), and the slot loop runs
  `4 + HasTransUnit()` slots.

**The `0x308` hook is rule 2:** in `FinishShaderMain`, true appends a CF instruction whose opcode comes from the
low-level assembler's `TgtCfOpcodeEnd()` (slot `0xe50`); false sets the end-of-program bit through `SetEEndOfProgram`
(slot `0x6f8`). `TgtCfOpcodeEnd()` returns 0 in `R600LowLevelAssem`, and `R800LowLevelAssem` doesn't override it:
the Cayman class supplied the real opcode.

Other leftovers: `HwLimits::HasTransUnit`/`Pele::HasTransUnit` by name, `R900` IL expansions (`DDIV_IL_EXPANSION_R900`,
`DIV_PRECISE_IL_EXPANSION_R900`, `DRCP_DBL_IL_EXPANSION_R900`), and `TgtCfOpcodeTc`/`TgtCfOpcodeVc` hooks in the
low-level assembler (rule 3's switch, probably).

(An earlier reading took `0x308` calls in `EmitCF` and `FillBankSwizzles` for the same hook. They go through the
low-level assembler object at target + `0x19a0`, a different vtable: a different method.)

## The patches (10.13.6)

`python scripts/sclib_hooks.py <ATIRadeonX3000SCLib.dylib>` finds these from symbols and disassembly, checks them, and
prints unique find/replace byte strings for the x86_64 slice:

| # | What | Address | Old → new |
|---|---|---|---|
| 1 | `Cypress` vtable, `HasTransUnit` slot → the shared return-false function | `0x2437b8` | `0x1bd70` → `0x1bd60` |
| 2 | `Cypress` vtable, Cayman slot → the shared return-true function | `0x243780` | `0x1bd60` → `0x1bd70` |
| 3 | `FinishShaderMain`: `call [rax+0xe50]` → `mov eax, 0x20; nop` | `0x187020` | `ff90500e0000` → `b82000000090` |

The return-0 and return-1 functions are each shared by dozens of methods (the linker folded identical code), so
patches 1 and 2 repoint vtable entries rather than edit functions. In the file the entries hold unslid addresses that
dyld rebases, so the new values need no adjustment. Patch 3 replaces the virtual call rather than the shared
return-0 function it reaches.

**`0x20` for `CF_END` is from memory of Mesa's Cayman opcode table: check it against AMD's Cayman ISA document before
relying on it** (`--cf-end` overrides it).

## What's not covered

- **Vertex fetch (rule 3).** The `TgtCfOpcodeTc`/`Vc` hooks suggest the switch exists; which hook selects it isn't
  traced yet.
- **Whatever else the Cayman class overrode**: the opcode table (`Pele::InitOpTable`), kcache and constant rules, GPR
  limits. Unknown until compiled output is checked.
- **Whether the target object is always a `Cypress`.** It is the only target class with these vtables, so it should be.

What the patches miss can be fixed at submission time, the way CarrizoRed fixes Stoney's interpolation hazard
(rewriting shaders in GPU memory before each command buffer runs): a far smaller job than translating VLIW5 to VLIW4.

## Checking compiled output without Trinity hardware

The compiler can run without the GPU it compiles for executing anything: OpenCL on High Sierra should compile through
the same SC (`libCLVMAMDilPlugin.dylib` sits in the same bundle as `ATIRadeonX3000SCLib`), and `clGetProgramInfo(CL_PROGRAM_BINARIES)` returns the
ISA without running it. On a High Sierra machine with any TeraScale 2 GPU (a cheap HD 5000/6000 card will do), load
the patched library (`--write`, SIP off), compile a set of kernels, and disassemble the binaries: four-slot ALU
groups, transcendentals in xyz, a `CF_END` at the end, and how vertex fetches come out. **Don't run** the patched
compiler's output on a VLIW5 GPU: `CF_END` isn't a VLIW5 opcode.
