#!/usr/bin/env python3
"""
Finds the VLIW4 (Cayman) hooks left in Apple's TeraScale 2 shader compiler and builds the patches that turn them on.

Apple's ATIRadeonX3000SCLib.dylib (inside AMDRadeonX3000GLDriver.bundle) is AMD's shader compiler with a single
target class, Cypress (on Pele, AMD's R6xx-R8xx base). AMD's Cayman target class was stripped, but the generic code
still asks the target object about it through virtual calls:

  HasTransUnit()      ALU group packing (AssembleIRList, NumSlotsForInst, ...): false = 4 slots, transcendentals
                      replicated across xyz, or xyzw for the integer multiplies (Cayman's rule)
  "Cayman" hook       program end (FinishShaderMain): true = end the program with a CF_END instruction
                      instead of setting the end-of-program bit on the last CF instruction
  TgtCfOpcodeEnd()    the CF_END opcode, returned by the low-level assembler: 0 in every class present

This script finds those slots from symbols and disassembly (so it works on any build that keeps the symbols), checks
that they are what they appear to be, and prints three patches:

  1. Cypress vtable, HasTransUnit slot  -> the function that returns false
  2. Cypress vtable, Cayman-hook slot   -> the function that returns true
  3. FinishShaderMain: `call [rax + TgtCfOpcodeEnd slot]` -> `mov eax, CF_END; nop`

The return-0 and return-1 functions are each shared by dozens of methods (the linker folded identical code), so the
patches repoint vtable entries instead of editing those functions.

Usage (Python 3, `pip install capstone`; works on Windows):
    python scripts/sclib_hooks.py <ATIRadeonX3000SCLib.dylib>                   report and patches
    python scripts/sclib_hooks.py <dylib> --json patches.json                    also write them as JSON
    python scripts/sclib_hooks.py <dylib> --write patched.dylib                  write a patched copy (testing only)
    python scripts/sclib_hooks.py <dylib> --cf-end 0x20                          CF_END opcode to use (default 0x20)

Status: found statically on 10.13.6 (17G66 and later builds ship the same binary through OCLP). Not yet run on a Mac.
The CF_END value 0x20 is from memory of Mesa's Cayman tables: check it against AMD's Cayman ISA document.
"""

import argparse
import json
import re
import struct
import sys
from pathlib import Path

import capstone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from macho import MachO  # noqa: E402

SYM = {
    'vt_hwlimits': '__ZTV8HwLimits',
    'vt_pele': '__ZTV4Pele',
    'vt_cypress': '__ZTV7Cypress',
    'hw_trans': '__ZNK8HwLimits12HasTransUnitEv',
    'pele_trans': '__ZNK4Pele12HasTransUnitEv',
    'numslots': '__Z15NumSlotsForInstP8CompilerP6IRInst',
    'finish': '__ZN20R600MachineAssembler16FinishShaderMainEb',
    'ma_cfend': '__ZN20R600MachineAssembler14TgtCfOpcodeEndEv',
    'ma_eop': '__ZN20R600MachineAssembler16SetEEndOfProgramER6CFSlotj',
}

# The target object (Cypress) sits at assembler + 0x2c8 and compiler + 0x738 (AssembleIRList, NumSlotsForInst on
# 10.13.6). The low-level assembler hangs off it at + 0x19a0; calls through that object use other vtables.


def fat_slice_offset(path):
    d = open(path, 'rb').read(4096)
    if struct.unpack_from('>I', d, 0)[0] != 0xcafebabe:
        return 0
    for i in range(struct.unpack_from('>I', d, 4)[0]):
        cpu, _, off, _, _ = struct.unpack_from('>iiIII', d, 8 + 20 * i)
        if cpu == 0x01000007:
            return off
    raise SystemExit('no x86_64 slice')


class Lib:
    def __init__(self, path):
        self.m = MachO(path)
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True
        missing = [v for v in SYM.values() if v not in self.m.syms]
        if missing:
            raise SystemExit('symbols missing (different build?): ' + ', '.join(missing))
        self.a = {k: self.m.syms[v] for k, v in SYM.items()}

    def vt(self, key, slot_off):
        """Entry at byte offset slot_off past the vtable's address point (vtable symbol + 16)."""
        addr = self.a[key] + 16 + slot_off
        return addr, struct.unpack('<Q', self.m.read(addr, 8))[0] & 0xffffffffff

    def file_off(self, addr):
        for seg, sn, a, size, foff, *_ in self.m.sects:
            if a <= addr < a + size:
                return foff + addr - a
        raise ValueError(hex(addr))

    def insns(self, key):
        a, end = self.m.funcrange(SYM.get(key, key))
        return list(self.md.disasm(self.m.read(a, end - a), a))

    def indirect_calls(self, key):
        """(insn, displacement, base register) for every `call/jmp [reg + disp]`."""
        out = []
        for ins in self.insns(key):
            if ins.mnemonic not in ('call', 'jmp') or len(ins.operands) != 1:
                continue
            op = ins.operands[0]
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base and not op.mem.index:
                out.append((ins, op.mem.disp, ins.reg_name(op.mem.base)))
        return out

    def target_calls(self, key):
        """Displacements of virtual calls on the target object (assembler + 0x2c8 or compiler + 0x738)."""
        ins_list = self.insns(key)
        offs = set()
        for i, ins in enumerate(ins_list):
            if ins.mnemonic != 'call' or len(ins.operands) != 1 or ins.operands[0].type != capstone.x86.X86_OP_MEM:
                continue
            # Look back a few instructions for `mov rdi, [rX + 0x2c8]`.
            for prev in ins_list[max(0, i - 4):i]:
                if prev.mnemonic == 'mov' and prev.op_str.startswith('rdi,'):
                    if re.search(r'\[r\w+ \+ 0x(2c8|738)\]', prev.op_str):
                        offs.add(ins.operands[0].mem.disp)
                    break
        return offs


def find_slots(lib):
    rep = []
    # 1. HasTransUnit: the slot where HwLimits has its own HasTransUnit and Pele has its own, and that
    #    NumSlotsForInst calls.
    numslots_offs = {d for _, d, _ in lib.indirect_calls('numslots')}
    trans = [off for off in range(0, 0x900, 8)
             if lib.vt('vt_hwlimits', off)[1] == lib.a['hw_trans'] and lib.vt('vt_pele', off)[1] == lib.a['pele_trans']
             and off in numslots_offs]
    if len(trans) != 1:
        raise SystemExit(f'HasTransUnit slot not unique: {[hex(t) for t in trans]}')
    trans = trans[0]
    rep.append(f'HasTransUnit: vtable slot {trans:#x} (HwLimits -> {lib.a["hw_trans"]:#x} returns false, '
               f'Pele -> {lib.a["pele_trans"]:#x} returns true)')
    cyp_trans = lib.vt('vt_cypress', trans)[1]
    rep.append(f'  Cypress has {cyp_trans:#x} ({"true" if cyp_trans == lib.a["pele_trans"] else "?"})')

    # 3 first: TgtCfOpcodeEnd. R600MachineAssembler::TgtCfOpcodeEnd tail-jumps to the low-level assembler's method.
    jumps = [d for ins, d, _ in lib.indirect_calls('ma_cfend') if ins.mnemonic == 'jmp']
    if len(jumps) != 1:
        raise SystemExit('cannot read TgtCfOpcodeEnd forwarding')
    cfend = jumps[0]
    finish = lib.insns('finish')
    sites = [ins for ins in finish if ins.mnemonic == 'call' and len(ins.operands) == 1
             and ins.operands[0].type == capstone.x86.X86_OP_MEM and ins.operands[0].mem.disp == cfend]
    if len(sites) != 1:
        raise SystemExit(f'FinishShaderMain calls TgtCfOpcodeEnd {len(sites)} times, expected 1')
    site = sites[0]

    # 2. Cayman hook: the last virtual call on the target object before that site. Its result chooses between
    #    a CF_END instruction (true) and the end-of-program bit set through SetEEndOfProgram (false).
    hook = None
    for i, ins in enumerate(finish):
        if ins.address >= site.address:
            break
        if ins.mnemonic == 'call' and len(ins.operands) == 1 and ins.operands[0].type == capstone.x86.X86_OP_MEM:
            for prev in reversed(finish[max(0, i - 4):i]):
                if prev.mnemonic == 'mov' and prev.op_str.startswith('rdi,'):
                    if re.search(r'\[r\w+ \+ 0x2c8\]', prev.op_str):
                        hook = ins.operands[0].mem.disp
                    break
    if hook is None:
        raise SystemExit('Cayman hook not found in FinishShaderMain')
    cayman = hook
    # SetEEndOfProgram forwards with `mov rax, [rax + slot]; jmp rax`: the last memory load in it.
    eop = [ins.operands[1].mem.disp for ins in lib.insns('ma_eop')
           if ins.mnemonic == 'mov' and len(ins.operands) == 2 and ins.operands[1].type == capstone.x86.X86_OP_MEM][-1:]
    eop_used = bool(eop) and any(d == eop[0] for _, d, _ in lib.indirect_calls('finish'))
    cyp_cay = lib.vt('vt_cypress', cayman)[1]
    rep.append(f'Cayman hook: target slot {cayman:#x}, read by FinishShaderMain before the CF_END path; Cypress has '
               f'{cyp_cay:#x} ({"false" if cyp_cay == lib.a["hw_trans"] else "?"}); the other path sets the '
               f'end-of-program bit (low-level slot {eop[0] if eop else 0:#x}, {"seen" if eop_used else "NOT seen"})')
    rep.append(f'TgtCfOpcodeEnd: low-level assembler slot {cfend:#x}, called once in FinishShaderMain at '
               f'{site.address:#x}')
    return trans, cayman, cfend, site, rep


def unique_window(lib, addr, n, before=8, after=8):
    """Bytes around [addr, addr+n) that occur once in the slice, growing the window until unique."""
    data = lib.m.d
    fo = lib.file_off(addr)
    while True:
        lo, hi = fo - before, fo + n + after
        if data.count(data[lo:hi]) == 1:
            return lo, hi
        before += 8
        after += 8
        if before > 128:
            raise SystemExit(f'no unique window at {addr:#x}')


def build_patches(lib, trans, cayman, site, cf_end):
    patches = []

    def add(name, addr, old, new):
        assert len(old) == len(new)
        if lib.m.read(addr, len(old)) != old:
            raise SystemExit(f'{name}: bytes at {addr:#x} are not what was expected')
        lo, hi = unique_window(lib, addr, len(old))
        fo = lib.file_off(addr)
        find = lib.m.d[lo:hi]
        repl = find[:fo - lo] + new + find[fo - lo + len(new):]
        patches.append({'name': name, 'vmaddr': addr, 'slice_offset': fo, 'find': find.hex(), 'replace': repl.hex(),
                        'old': old.hex(), 'new': new.hex()})

    a_t, v_t = lib.vt('vt_cypress', trans)
    add('Cypress::HasTransUnit -> false', a_t, struct.pack('<Q', v_t), struct.pack('<Q', lib.a['hw_trans']))
    a_c, v_c = lib.vt('vt_cypress', cayman)
    add('Cypress Cayman hook -> true', a_c, struct.pack('<Q', v_c), struct.pack('<Q', lib.a['pele_trans']))
    if site.size != 6 or site.bytes[:2] != b'\xff\x90':
        raise SystemExit(f'unexpected call encoding at {site.address:#x}: {site.bytes.hex()}')
    add(f'FinishShaderMain: CF_END opcode = {cf_end:#x}', site.address, bytes(site.bytes),
        b'\xb8' + struct.pack('<I', cf_end) + b'\x90')
    return patches


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('dylib')
    ap.add_argument('--json')
    ap.add_argument('--write')
    ap.add_argument('--cf-end', type=lambda s: int(s, 0), default=0x20)
    args = ap.parse_args()

    lib = Lib(args.dylib)
    trans, cayman, cfend, site, rep = find_slots(lib)
    print('\n'.join(rep))
    print('\nFunctions calling these slots on the target object:')
    for name in sorted(n for n in lib.m.syms if n.startswith(('__ZN20R600MachineAssembler', '__ZN14R600SchedModel',
                                                               '__Z15NumSlots', '__Z23NumSlots'))):
        offs = lib.target_calls(name)
        hits = [label for label, o in (('HasTransUnit', trans), ('Cayman hook', cayman)) if o in offs]
        if hits:
            print(f'  {name}: {", ".join(hits)}')

    patches = build_patches(lib, trans, cayman, site, args.cf_end)
    print('\nPatches (x86_64 slice; find/replace are unique in the slice):')
    for p in patches:
        print(f'  {p["name"]}\n    at {p["vmaddr"]:#x} (slice +{p["slice_offset"]:#x}): {p["old"]} -> {p["new"]}\n'
              f'    find    {p["find"]}\n    replace {p["replace"]}')
    if args.json:
        Path(args.json).write_text(json.dumps(patches, indent=2) + '\n')
        print(f'\nwrote {args.json}')
    if args.write:
        data = bytearray(Path(args.dylib).read_bytes())
        base = fat_slice_offset(args.dylib)
        for p in patches:
            fo = base + p['slice_offset']
            old, new = bytes.fromhex(p['old']), bytes.fromhex(p['new'])
            assert data[fo:fo + len(old)] == old
            data[fo:fo + len(new)] = new
        Path(args.write).write_bytes(data)
        print(f'wrote {args.write} (code signature now invalid: test with SIP off)')


if __name__ == '__main__':
    main()
