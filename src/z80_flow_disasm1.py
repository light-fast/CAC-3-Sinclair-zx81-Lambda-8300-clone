"""
基于控制流的 Z80 反汇编模块 (v3)
修复:
  [FIX-P0-1] CALL / RST 的 fall-through 丢失
  [FIX-P0-2] DJNZ 的 fall-through 丢失
  [FIX-P0-3] 条件 RET (RET Z / RET NZ / ...) 未识别
  [FIX-P0-4] covered_bytes 不含 opcode 导致冷代码扫描重复反汇编
  [FIX-P0-5] 硬件向量 0010 与已内联的 0008 块重复输出
  [FIX-P0-6] 冷代码扫描只从"特征点"起始 → 段首 001B-001E 丢失
  [FIX-P1-a] _check_code_continuity 把 0xC3 (JP) 误当作函数收尾
  [FIX-P1-b] is_entry 从未被置为 True
  [FIX-P2  ] 跳转目标正则放宽（$XXXX / 0xXXXX / XXXXh / #XXXX）
"""

import re
from collections import deque
from typing import Set, Dict, List, Tuple

from z80dis import z80
from basic_decoder import decode_cac3_byte


# Z80 标准硬件向量入口 (RESET + 8 个 RST)
Z80_HARDWARE_VECTORS = [
    0x0000, 0x0008, 0x0010, 0x0018,
    0x0020, 0x0028, 0x0030, 0x0038,
]

# 兼容多种汇编器地址格式：$XXXX / 0xXXXX / XXXXh / #XXXX
_ADDR_RE = re.compile(
    r'(?:0[xX]|\$|#)([0-9A-Fa-f]{1,4})\b'
    r'|([0-9A-Fa-f]{1,4})[hH]\b'
)

_COND_CODES = ('NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M')
_COND_RET_RE = re.compile(r'^RET\s+(' + '|'.join(_COND_CODES) + r')\b')
_CALL_LIKE_RE = re.compile(r'^(CALL|RST)\b')


class ControlFlowNode:
    """控制流节点，代表一个基本块"""

    def __init__(self, start_addr: int):
        self.start_addr = start_addr
        self.instructions = []      # [(addr, hex_bytes, inst_str)]
        self.successors = []        # 后继节点地址列表
        self.is_entry = False
        self.is_exit = False

    def add_instruction(self, addr: int, hex_bytes: str, inst_str: str):
        self.instructions.append((addr, hex_bytes, inst_str))

    def add_successor(self, addr: int):
        if addr not in self.successors:
            self.successors.append(addr)


class FlowDisassembler:
    """基于控制流的反汇编器 (v3)"""

    def __init__(self, data: bytes, base_addr: int = 0x0000):
        self.data = data
        self.base_addr = base_addr
        self.data_len = len(data)

        self.nodes: Dict[int, ControlFlowNode] = {}
        self.visited: Set[int] = set()          # opcode 起始地址
        self.covered_bytes: Set[int] = set()    # 操作数（不含 opcode）的字节地址

        self.worklist = deque()

        self.jump_patterns = {
            'JP':    self._parse_absolute_jump,
            'JR':    self._parse_relative_jump,
            'CALL':  self._parse_absolute_jump,
            'DJNZ':  self._parse_relative_jump,
            'RET':   self._parse_return,
            'RETI':  self._parse_return,
            'RETN':  self._parse_return,
            'RST':   self._parse_rst,
        }

    # ---------- 指令字符串解析 ----------

    @staticmethod
    def _format_instruction(inst_str: str) -> str:
        return re.sub(r',\s*', ', ', inst_str.upper())

    @staticmethod
    def _extract_addr(inst_str: str):
        m = _ADDR_RE.search(inst_str)
        if not m:
            return None
        return int(m.group(1) or m.group(2), 16)

    def _parse_absolute_jump(self, inst_str: str, current_addr: int) -> List[int]:
        if '(' in inst_str:  # 排除 JP (HL) / JP (IX) / JP (IY)
            return []
        addr = self._extract_addr(inst_str)
        return [addr] if addr is not None else []

    def _parse_relative_jump(self, inst_str: str, current_addr: int) -> List[int]:
        addr = self._extract_addr(inst_str)
        return [addr] if addr is not None else []

    def _parse_return(self, inst_str: str, current_addr: int) -> List[int]:
        return []

    def _parse_rst(self, inst_str: str, current_addr: int) -> List[int]:
        addr = self._extract_addr(inst_str)
        return [addr] if addr is not None else []

    def _get_jump_targets(self, inst_str: str, current_addr: int) -> Tuple[List[int], bool]:
        targets: List[int] = []
        is_conditional = False
        inst_upper = inst_str.upper()

        for cond in _COND_CODES:
            if f'{cond},' in inst_upper:
                is_conditional = True
                break

        # [FIX-P0-2 / P0-3] 无逗号式条件型
        if _COND_RET_RE.match(inst_upper):
            is_conditional = True
        if inst_upper.startswith('DJNZ'):
            is_conditional = True

        for mnemonic, parser in self.jump_patterns.items():
            if inst_upper.startswith(mnemonic):
                targets = parser(inst_str, current_addr)
                break

        return targets, is_conditional

    @staticmethod
    def _is_unconditional_jump(inst_str: str) -> bool:
        inst_upper = inst_str.upper().strip()
        if inst_upper.startswith('JP ') and ',' not in inst_upper:
            return True
        if inst_upper in ('JP (HL)', 'JP (IX)', 'JP (IY)'):
            return True
        if inst_upper.startswith('JR ') and ',' not in inst_upper:
            return True
        if inst_upper.startswith('CALL ') and ',' not in inst_upper:
            return True
        if inst_upper in ('RET', 'RETI', 'RETN'):
            return True
        if inst_upper.startswith('RST'):
            return True
        return False

    # ---------- 基本块反汇编 ----------

    def _disassemble_basic_block(
        self, start_addr: int, add_successors: bool = True
    ) -> ControlFlowNode:
        node = ControlFlowNode(start_addr)
        addr = start_addr
        offset = addr - self.base_addr
        block_addresses: Set[int] = set()

        while 0 <= offset < self.data_len:
            if addr in self.covered_bytes:
                break
            if addr in block_addresses:
                break

            self.visited.add(addr)
            block_addresses.add(addr)

            try:
                raw_inst = z80.disasm(self.data[offset:], addr)
                inst_str = self._format_instruction(raw_inst)

                decoded = z80.decode(self.data[offset:], addr)
                inst_len = max(1, decoded.len)

                for i in range(1, inst_len):
                    self.covered_bytes.add(addr + i)

                hex_bytes = ' '.join(
                    f'{b:02X}' for b in self.data[offset:offset + inst_len]
                )
                node.add_instruction(addr, hex_bytes, inst_str)

                inst_upper = inst_str.upper().strip()

                # [FIX-P0-3] 条件 RET：exit + fall-through
                if _COND_RET_RE.match(inst_upper):
                    node.is_exit = True
                    fallthrough = addr + inst_len
                    node.add_successor(fallthrough)
                    if (add_successors
                            and fallthrough not in self.visited
                            and fallthrough not in block_addresses):
                        self.worklist.append(fallthrough)
                    break

                targets, is_conditional = self._get_jump_targets(inst_str, addr)
                is_unconditional = self._is_unconditional_jump(inst_str)
                is_indirect = inst_upper in ('JP (HL)', 'JP (IX)', 'JP (IY)')
                is_call_like = bool(_CALL_LIKE_RE.match(inst_upper))

                if targets or is_unconditional or is_indirect or is_call_like:
                    for target in targets:
                        node.add_successor(target)
                        if (add_successors
                                and target not in self.visited
                                and target not in block_addresses):
                            self.worklist.append(target)

                    if inst_upper in ('RET', 'RETI', 'RETN') or is_indirect:
                        node.is_exit = True
                        break

                    # [FIX-P0-1] 条件跳转 + 调用类 (CALL/RST) 都要 fall-through
                    if is_conditional or is_call_like:
                        fallthrough = addr + inst_len
                        node.add_successor(fallthrough)
                        if (add_successors
                                and fallthrough not in self.visited
                                and fallthrough not in block_addresses):
                            self.worklist.append(fallthrough)
                    break

                addr += inst_len
                offset += inst_len

            except Exception as e:
                node.add_instruction(addr, '??', f'; 解码失败: {e}')
                addr += 1
                offset += 1

        self.nodes[start_addr] = node
        return node

    # ---------- 控制流遍历 ----------

    def disassemble(self, start_addr: int = None) -> Dict[int, ControlFlowNode]:
        if start_addr is None:
            start_addr = self.base_addr

        self.nodes.clear()
        self.visited.clear()
        self.covered_bytes.clear()
        self.worklist.clear()

        if self.base_addr == 0x0000:
            for vec in Z80_HARDWARE_VECTORS:
                if vec < self.data_len:
                    self.worklist.append(vec)
        else:
            self.worklist.append(start_addr)

        while self.worklist:
            addr = self.worklist.popleft()
            offset = addr - self.base_addr

            if offset < 0 or offset >= self.data_len:
                if addr not in self.nodes:
                    node = ControlFlowNode(addr)
                    node.add_instruction(addr, '??', '; 跳转目标超出数据范围')
                    node.is_exit = True
                    self.nodes[addr] = node
                continue

            if addr in self.nodes:
                continue

            # [FIX-P0-5] 已被其它块内联的地址（如 0010 与 0008 重叠）不再重复建块
            if addr in self.visited:
                continue

            self._disassemble_basic_block(addr)

        # [FIX-P1-b] 标记入口点
        entries = Z80_HARDWARE_VECTORS if self.base_addr == 0x0000 else [start_addr]
        for e in entries:
            if e in self.nodes:
                self.nodes[e].is_entry = True

        self._scan_and_disassemble_cold_code()
        return self.nodes

    # ---------- 冷代码扫描 ----------

    def _find_unassembled_ranges(self) -> List[Tuple[int, int]]:
        all_addrs = set(range(self.base_addr, self.base_addr + self.data_len))
        # [FIX-P0-4] opcode(visited) ∪ 操作数(covered_bytes)
        covered = self.visited | self.covered_bytes
        unvisited = all_addrs - covered

        if not unvisited:
            return []

        sorted_unvisited = sorted(unvisited)
        start = sorted_unvisited[0]
        prev = start
        ranges = []
        for addr in sorted_unvisited[1:]:
            if addr == prev + 1:
                prev = addr
            else:
                ranges.append((start, prev))
                start = addr
                prev = addr
        ranges.append((start, prev))
        return ranges

    def _check_ascii_density(self, addr: int, check_bytes: int = 16) -> bool:
        offset = addr - self.base_addr
        if offset < 0 or offset >= self.data_len:
            return False
        actual_check = min(check_bytes, self.data_len - offset)
        if actual_check == 0:
            return False
        printable_count = sum(
            1 for i in range(actual_check) if 0x20 <= self.data[offset + i] <= 0x7E
        )
        return (printable_count / actual_check) > 0.6

    def _check_code_continuity(self, addr: int, min_instructions: int = 6) -> bool:
        """[FIX-P1-a] 收尾信号: RET (0xC9) / JP (HL) (0xE9)；不再把 JP (0xC3) 当收尾。"""
        offset = addr - self.base_addr
        if offset < 0 or offset >= self.data_len:
            return False

        current_addr = addr
        current_offset = offset
        instruction_count = 0
        has_valid_ending = False

        for _ in range(min_instructions + 4):
            if current_offset >= self.data_len:
                break
            try:
                decoded = z80.decode(self.data[current_offset:], current_addr)
                inst_len = decoded.len
                if inst_len == 0 or current_offset + inst_len > self.data_len:
                    break
                b0 = self.data[current_offset]
                if b0 == 0xC9:            # RET
                    has_valid_ending = True
                    break
                if b0 == 0xE9:            # JP (HL)
                    has_valid_ending = True
                    break
                instruction_count += 1
                current_addr += inst_len
                current_offset += inst_len
            except Exception:
                break

        return has_valid_ending or instruction_count >= min_instructions

    def _detect_code_patterns(self, addr: int) -> bool:
        offset = addr - self.base_addr
        if offset < 0 or offset >= self.data_len - 3:
            return False
        if self._check_ascii_density(addr, check_bytes=16):
            return False

        b0 = self.data[offset]
        b1 = self.data[offset + 1]

        if b0 == 0xC9:
            return self._check_code_continuity(addr, min_instructions=3)
        if b0 in (0xC5, 0xD5, 0xE5, 0xF5):
            return self._check_code_continuity(addr, min_instructions=6)
        if (b0 == 0xDD or b0 == 0xFD) and b1 == 0xE5:
            return self._check_code_continuity(addr, min_instructions=6)
        if b0 == 0xCD or b0 in (0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC):
            return self._check_code_continuity(addr, min_instructions=6)
        if b0 == 0xC3 or b0 in (0x18, 0x20, 0x28, 0x30, 0x38):
            return self._check_code_continuity(addr, min_instructions=6)
        if b0 in (0x21, 0x11, 0x01, 0x31):
            return self._check_code_continuity(addr, min_instructions=6)

        return False

    def _scan_and_disassemble_cold_code(self) -> None:
        """[FIX-P0-6] 优先从 range 起点向前扩展，覆盖候选入口点；否则回退到逐点扫描。"""
        for start, end in self._find_unassembled_ranges():
            if end - start + 1 < 2:
                continue

            # 找出 range 内所有入口候选点
            candidate_starts = [
                a for a in range(start, end + 1)
                if a not in self.visited
                and a not in self.covered_bytes
                and self._detect_code_patterns(a)
            ]
            if not candidate_starts:
                continue

            # 起点是文本数据 → 不做向前扩展，回退到逐点扫描
            if self._check_ascii_density(start, check_bytes=min(16, end - start + 1)):
                for addr in candidate_starts:
                    self._try_cold_block(addr)
                continue

            # 从 range 起点向前扩展
            saved_visited = set(self.visited)
            saved_covered = set(self.covered_bytes)
            node = self._disassemble_basic_block(start, add_successors=False)

            covered = [
                a for a in candidate_starts if a in self.visited
            ]

            # 至少覆盖到一个候选点，且起点头部不是解码失败
            ok = (
                bool(covered)
                and node
                and node.instructions
                and '解码失败' not in node.instructions[0][2]
            )

            if ok:
                inst_addr, hex_bytes, inst_str = node.instructions[0]
                node.instructions[0] = (
                    inst_addr, hex_bytes,
                    f"; [COLD CODE ENTRY] {inst_str}"
                )
            else:
                # 回滚
                self.visited = saved_visited
                self.covered_bytes = saved_covered
                self.nodes.pop(start, None)
                for addr in candidate_starts:
                    self._try_cold_block(addr)

    def _try_cold_block(self, addr: int) -> None:
        """单点冷代码反汇编（原策略）"""
        if addr in self.visited or addr in self.covered_bytes:
            return
        node = self._disassemble_basic_block(addr, add_successors=False)
        if node and node.instructions:
            inst_addr, hex_bytes, inst_str = node.instructions[0]
            node.instructions[0] = (
                inst_addr, hex_bytes,
                f"; [COLD CODE ENTRY] {inst_str}"
            )

    # ---------- 输出 ----------

    def generate_output(self) -> str:
        lines = [
            "; Z80 CONTROL FLOW DISASSEMBLY (v3)",
            f"; BASE ADDRESS: {self.base_addr:04X}",
            f"; TOTAL BYTES: {self.data_len}",
            f"; BASIC BLOCKS: {len(self.nodes)}\n",
        ]

        for addr in sorted(self.nodes.keys()):
            node = self.nodes[addr]
            if not node.instructions:
                continue

            lines.append(f"; === BASIC BLOCK AT {addr:04X} ===")
            if node.is_entry:
                lines.append("; ENTRY POINT")
            if node.is_exit:
                lines.append("; EXIT POINT")
            if node.successors:
                lines.append(
                    f"; SUCCESSORS: {', '.join(f'{s:04X}' for s in node.successors)}"
                )
            lines.append("")

            for inst_addr, hex_bytes, inst_str in node.instructions:
                lines.append(f"{inst_addr:04X}:  {hex_bytes:<20}  {inst_str}")
            lines.append("")

        unassembled_ranges = self._find_unassembled_ranges()
        if unassembled_ranges:
            lines.append(
                "; ========================================\n"
                "; UNASSEMBLED DATA AREAS\n"
                "; ========================================\n"
            )
            for start, end in unassembled_ranges:
                lines.append(
                    f"; === DATA AREA ${start:04X} - ${end:04X} ===\n"
                    f"; SIZE: {end - start + 1} BYTES\n"
                )
                addr = start
                while addr <= end:
                    offset = addr - self.base_addr
                    n = min(16, end - addr + 1)
                    data_bytes = self.data[offset:offset + n]

                    hex_str = "".join([f" {b:02X}" for b in data_bytes])
                    char_cells = []
                    for b in data_bytes:
                        try:
                            ch, _ = decode_cac3_byte(b)
                            ch = ch.strip() if ch.strip() else "."
                            if len(ch) > 1:
                                ch = ch[0]
                        except Exception:
                            ch = "."
                        char_cells.append(f"{ch:>3s}")

                    lines.append(f"[{addr:04X}]  HEX :{hex_str}")
                    lines.append(f"[{addr:04X}] CHAR :{''.join(char_cells)}")
                    addr += n
                lines.append("")
        return '\n'.join(lines)

    def save_output(self, output_file: str):
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_output())


def disassemble_z80_flow(
    data: bytes,
    base_addr: int = 0x0000,
    start_addr: int = None,
    output_file: str = None,
) -> str:
    if not isinstance(data, bytes):
        raise TypeError("data 必须是 bytes 类型")
    if not data:
        return "; 空数据，无反汇编结果"

    d = FlowDisassembler(data, base_addr)
    d.disassemble(start_addr)
    text = d.generate_output()
    if output_file:
        d.save_output(output_file)
    return text


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python z80_flow_disasm.py <rom_file> "
              "[base_addr] [start_addr] [output_file]")
        sys.exit(1)

    rom_file_path = sys.argv[1]
    base_address = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x0000
    start_address = int(sys.argv[3], 16) if len(sys.argv) > 3 else None
    out_file_path = sys.argv[4] if len(sys.argv) > 4 else None

    with open(rom_file_path, 'rb') as f:
        rom_bytes = f.read()

    result = disassemble_z80_flow(rom_bytes, base_address, start_address, out_file_path)
    if not out_file_path:
        print(result)