"""
基于控制流的 Z80 反汇编模块
从起始地址开始反汇编，遇到跳转时跳到相应地址继续，用控制流图记录所有分支并遍历。
"""

import re
from collections import deque
from typing import Set, Dict, List, Tuple
from z80dis import z80
from basic_decoder import decode_cac3_byte


class ControlFlowNode:
    """控制流节点，代表一个基本块"""
    def __init__(self, start_addr: int):
        self.start_addr = start_addr
        self.instructions = []  # [(addr, hex_bytes, inst_str)]
        self.successors = []  # 后继节点地址列表
        self.is_entry = False
        self.is_exit = False
    
    def add_instruction(self, addr: int, hex_bytes: str, inst_str: str):
        self.instructions.append((addr, hex_bytes, inst_str))
    
    def add_successor(self, addr: int):
        if addr not in self.successors:
            self.successors.append(addr)


class FlowDisassembler:
    """基于控制流的反汇编器"""
    
    def __init__(self, data: bytes, base_addr: int = 0x0000, cold_code_scan: bool = True):
        self.data = data
        self.base_addr = base_addr
        self.data_len = len(data)
        self.cold_code_scan = cold_code_scan
        
        # 控制流图
        self.nodes: Dict[int, ControlFlowNode] = {}
        self.visited: Set[int] = set()
        
        # 待处理的工作队列
        self.worklist = deque()
        
        # 跳转指令模式
        self.jump_patterns = {
            'JP': self._parse_absolute_jump,
            'JR': self._parse_relative_jump,
            'CALL': self._parse_absolute_jump,
            'DJNZ': self._parse_relative_jump,
            'RET': self._parse_return,
            'RETI': self._parse_return,
            'RETN': self._parse_return,
            'RST': self._parse_rst,
        }
    
    def _format_instruction(self, inst_str: str) -> str:
        """格式化指令字符串：大写，逗号后加空格"""
        inst_upper = inst_str.upper()
        formatted = re.sub(r',\s*', ', ', inst_upper)
        return formatted
    
    def _parse_absolute_jump(self, inst_str: str, current_addr: int) -> List[int]:
        """解析绝对跳转指令 (JP, CALL)"""
        targets = []
        # 匹配 JP $XXXX 或 CALL $XXXX 或 JP CC, $XXXX 或 JP 0XXXX 或 CALL 0XXXX
        match = re.search(r'[0$]X([0-9A-Fa-f]{4})', inst_str)
        if match:
            target = int(match.group(1), 16)
            targets.append(target)
        return targets
    
    def _parse_relative_jump(self, inst_str: str, current_addr: int) -> List[int]:
        """解析相对跳转指令 (JR, DJNZ)"""
        targets = []
        # 相对跳转已经在 z80dis 中解析为绝对地址
        match = re.search(r'[0$]X([0-9A-Fa-f]{4})', inst_str)
        if match:
            target = int(match.group(1), 16)
            targets.append(target)
        return targets
    
    def _parse_return(self, inst_str: str, current_addr: int) -> List[int]:
        """解析返回指令 (RET, RETI, RETN)"""
        # 返回指令没有静态目标，标记为退出点
        return []
    
    def _parse_rst(self, inst_str: str, current_addr: int) -> List[int]:
        """解析 RST 指令"""
        targets = []
        # RST 指令的目标地址通常是 0X00, 0X08, 0X10, 0X18, 0X20, 0X28, 0X30, 0X38
        match = re.search(r'[0$]X([0-9A-Fa-f]{2})', inst_str)
        if match:
            target = int(match.group(1), 16)
            targets.append(target)
        return targets
    
    def _get_jump_targets(self, inst_str: str, current_addr: int) -> Tuple[List[int], bool]:
        """
        获取跳转指令的目标地址
        返回: (目标地址列表, 是否是条件跳转)
        """
        targets = []
        is_conditional = False
        
        # 检查是否是条件跳转
        conditions = ['NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M']
        for cond in conditions:
            if f'{cond},' in inst_str.upper():
                is_conditional = True
                break
        
        # 解析跳转目标
        for mnemonic, parser in self.jump_patterns.items():
            if inst_str.upper().startswith(mnemonic):
                targets = parser(inst_str, current_addr)
                break
        
        return targets, is_conditional
    
    def _is_unconditional_jump(self, inst_str: str) -> bool:
        """判断是否是无条件跳转"""
        inst_upper = inst_str.upper()
        if inst_upper.startswith('JP ') and ',' not in inst_upper:
            return True
        if inst_upper.startswith('JR ') and ',' not in inst_upper:
            return True
        if inst_upper.startswith('CALL ') and ',' not in inst_upper:
            return True
        if inst_upper in ['RET', 'RETI', 'RETN']:
            return True
        if inst_upper.startswith('RST'):
            return True
        return False
    
    def _disassemble_basic_block(self, start_addr: int, add_successors: bool = True) -> ControlFlowNode:
        """
        反汇编一个基本块（从 start_addr 开始，直到遇到跳转指令）
        """
        # 如果起始地址已经被访问过，返回空节点
        if start_addr in self.visited:
            node = ControlFlowNode(start_addr)
            return node
        
        node = ControlFlowNode(start_addr)
        addr = start_addr
        offset = addr - self.base_addr
        # 记录当前基本块中处理的地址，避免重复添加
        block_addresses = set()
        
        while offset < self.data_len and offset >= 0:
            if addr in self.visited and addr != start_addr:
                # 已经访问过的地址（非起始地址），停止当前基本块
                break
            
            self.visited.add(addr)
            block_addresses.add(addr)
            
            try:
                # 反汇编指令
                raw_inst = z80.disasm(self.data[offset:], addr)
                inst_str = self._format_instruction(raw_inst)
                
                decoded = z80.decode(self.data[offset:], addr)
                inst_len = decoded.len
                
                # 机器码
                hex_bytes = ' '.join(f'{b:02X}' for b in self.data[offset:offset + inst_len])
                
                # 添加到节点
                node.add_instruction(addr, hex_bytes, inst_str)
                
                # 检查是否是跳转指令
                targets, is_conditional = self._get_jump_targets(inst_str, addr)
                
                # 检查是否是无条件跳转
                is_unconditional = self._is_unconditional_jump(inst_str)
                
                if targets or inst_str.upper() in ['RET', 'RETI', 'RETN']:
                    # 是跳转指令，结束基本块
                    for target in targets:
                        node.add_successor(target)
                        # 只在需要时添加跳转目标到工作列表
                        if add_successors:
                            if target not in self.visited and target not in block_addresses:
                                self.worklist.append(target)
                    
                    # 如果是返回指令，标记为退出点
                    if inst_str.upper() in ['RET', 'RETI', 'RETN']:
                        node.is_exit = True
                        break
                    
                    # 对于跳转指令（包括无条件跳转），也要添加下一条顺序地址到工作列表
                    # 这样可以继续处理跳转指令后面的代码（可能是数据或其他函数）
                    fallthrough = addr + inst_len
                    # 检查是否已经访问过、已经在节点中、或在当前块中
                    if add_successors:
                        if fallthrough not in self.nodes and fallthrough not in self.visited and fallthrough not in block_addresses:
                            node.add_successor(fallthrough)
                            self.worklist.append(fallthrough)
                    
                    # 结束当前基本块
                    break
                
                # 继续下一条指令
                addr += inst_len
                offset += inst_len
                
            except Exception as e:
                # 解码失败，添加错误信息并继续
                node.add_instruction(addr, '??', f'; 解码失败: {e}')
                addr += 1
                offset += 1
        
        self.nodes[start_addr] = node
        return node
    
    def disassemble(self, start_addr: int = None) -> Dict[int, ControlFlowNode]:
        """
        执行控制流反汇编
        
        参数:
            start_addr: 起始地址，如果为 None 则使用 base_addr
        
        返回:
            控制流图字典 {start_addr: ControlFlowNode}
        """
        if start_addr is None:
            start_addr = self.base_addr
        
        # 清空状态
        self.nodes.clear()
        self.visited.clear()
        self.worklist.clear()
        
        # 添加起始地址到工作列表
        self.worklist.append(start_addr)
        
        # 处理工作列表
        while self.worklist:
            addr = self.worklist.popleft()
            
            # 转换为数据偏移
            offset = addr - self.base_addr
            
            # 检查地址是否有效
            if offset < 0 or offset >= self.data_len:
                # 超出范围的地址，创建一个错误节点并显示
                if addr not in self.nodes:
                    node = ControlFlowNode(addr)
                    node.add_instruction(addr, '??', f'; 跳转目标超出数据范围 (偏移: {offset}, 数据长度: {self.data_len})')
                    node.is_exit = True
                    self.nodes[addr] = node
                continue
            
            # 检查是否已经处理过
            if addr in self.nodes:
                continue
            
            # 反汇编基本块
            self._disassemble_basic_block(addr)
        
        # 二次扫描：在未反汇编的数据区寻找潜在的冷代码入口
        if self.cold_code_scan:
            self._scan_and_disassemble_cold_code()
        
        return self.nodes
    
    def _find_unassembled_ranges(self) -> List[Tuple[int, int]]:
        """
        找出所有未被反汇编的数据地址范围
        
        返回:
            [(start_addr, end_addr), ...] 未被反汇编的连续地址范围
        """
        unassembled_ranges = []
        
        # 收集所有指令覆盖的地址范围
        covered_addrs = set()
        for node in self.nodes.values():
            for inst_addr, hex_bytes, inst_str in node.instructions:
                inst_len = len(hex_bytes.split()) if hex_bytes != '??' else 1
                for i in range(inst_len):
                    covered_addrs.add(inst_addr + i)
        
        # 所有地址范围
        all_addrs = set(range(self.base_addr, self.base_addr + self.data_len))
        
        # 未被指令覆盖的地址
        unvisited = all_addrs - covered_addrs
        
        if not unvisited:
            return unassembled_ranges
        
        # 将未访问的地址排序并分组为连续范围
        sorted_unvisited = sorted(unvisited)
        
        start = sorted_unvisited[0]
        prev = start
        
        for addr in sorted_unvisited[1:]:
            if addr == prev + 1:
                # 连续地址
                prev = addr
            else:
                # 不连续，结束当前范围
                unassembled_ranges.append((start, prev))
                start = addr
                prev = addr
        
        # 添加最后一个范围
        unassembled_ranges.append((start, prev))
        
        return unassembled_ranges
    
    def _check_ascii_density(self, addr: int, check_bytes: int = 16) -> bool:
        """
        检查给定地址后的ASCII文本密度
        
        参数:
            addr: 要检查的地址
            check_bytes: 要检查的字节数（默认16）
        
        返回:
            bool: 如果ASCII字符占比超过60%则返回True（认为是文本数据）
        """
        offset = addr - self.base_addr
        
        # 确保地址在有效范围内
        if offset < 0 or offset >= self.data_len:
            return False
        
        # 计算实际可检查的字节数
        actual_check = min(check_bytes, self.data_len - offset)
        
        if actual_check == 0:
            return False
        
        # 统计可打印ASCII字符数量
        printable_count = 0
        for i in range(actual_check):
            byte_val = self.data[offset + i]
            # 可打印ASCII范围：0x20-0x7E（空格到波浪号）
            if 0x20 <= byte_val <= 0x7E:
                printable_count += 1
        
        # 计算密度
        density = printable_count / actual_check
        
        # 如果密度超过60%，认为是文本数据
        return density > 0.6
    
    def _check_code_continuity(self, addr: int, min_instructions: int = 8) -> bool:
        """
        检查从给定地址开始的代码连续性
        
        参数:
            addr: 要检查的地址
            min_instructions: 最小需要连续反汇编的指令数（默认8）
        
        返回:
            bool: 如果代码连续性满足要求则返回True
        """
        offset = addr - self.base_addr
        
        # 确保地址在有效范围内
        if offset < 0 or offset >= self.data_len:
            return False
        
        # 尝试连续反汇编指令
        current_addr = addr
        current_offset = offset
        instruction_count = 0
        has_valid_ending = False
        
        for _ in range(min_instructions + 5):  # 多检查几条以寻找合法结尾
            if current_offset >= self.data_len:
                break
            
            try:
                # 尝试反汇编
                decoded = z80.decode(self.data[current_offset:], current_addr)
                inst_len = decoded.len
                
                if inst_len == 0 or current_offset + inst_len > self.data_len:
                    break
                
                # 获取指令字节
                inst_bytes = self.data[current_offset:current_offset + inst_len]
                
                # 检查是否是合法的结尾指令
                # RET (C9), RETI (ED 4D), RETN (ED 45), 无条件JP (C3)
                if inst_bytes[0] == 0xC9:  # RET
                    has_valid_ending = True
                    break
                if len(inst_bytes) >= 2 and inst_bytes[0] == 0xED and inst_bytes[1] in [0x4D, 0x45]:  # RETI/RETN
                    has_valid_ending = True
                    break
                if inst_bytes[0] == 0xC3:  # JP
                    has_valid_ending = True
                    break
                
                instruction_count += 1
                current_addr += inst_len
                current_offset += inst_len
                
            except Exception:
                # 反汇编失败，不连续
                break
        
        # 如果有合法结尾，或者连续反汇编了足够多的指令，则认为是有效代码
        return has_valid_ending or instruction_count >= min_instructions
    
    def _detect_code_patterns(self, addr: int) -> bool:
        """
        检测给定地址是否可能是代码入口点
        
        参数:
            addr: 要检查的地址
        
        返回:
            bool: 如果地址看起来像代码入口点则返回True
        """
        offset = addr - self.base_addr
        
        # 确保地址在有效范围内
        if offset < 0 or offset >= self.data_len - 1:
            return False
        
        # 检查是否有足够的数据来分析
        if offset + 3 > self.data_len:
            return False
        
        # 第一道门槛：ASCII文本密度检测
        # 如果该区域看起来像文本数据，直接否决
        if self._check_ascii_density(addr, check_bytes=16):
            return False
        
        # 获取当前字节和后续几个字节
        b0 = self.data[offset]
        b1 = self.data[offset + 1] if offset + 1 < self.data_len else 0
        b2 = self.data[offset + 2] if offset + 2 < self.data_len else 0
        b3 = self.data[offset + 3] if offset + 3 < self.data_len else 0
        
        # 特征1: RET指令 (C9) - 常见的函数结尾
        if b0 == 0xC9:
            # 第二道门槛：连续性验证
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征2: 条件RET (C0, C8, D0, D8, E0, E8, F0, F8)
        if b0 in [0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0, 0xF8]:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征3: PUSH指令 (C5, D5, E5, F5, DD E5, FD E5)
        if b0 in [0xC5, 0xD5, 0xE5, 0xF5]:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        if (b0 == 0xDD or b0 == 0xFD) and b1 == 0xE5:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征4: POP指令 (C1, D1, E1, F1, DD E1, FD E1)
        if b0 in [0xC1, 0xD1, 0xE1, 0xF1]:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        if (b0 == 0xDD or b0 == 0xFD) and b1 == 0xE1:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征5: CALL指令 (CD xx xx, 或条件CALL C4 xx xx, CC xx xx, D4 xx xx, DC xx xx, E4 xx xx, EC xx xx, F4 xx xx, FC xx xx)
        if b0 == 0xCD or b0 in [0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC]:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征6: JP指令 (C3 xx xx, 或条件JP C2 xx xx, CA xx xx, DA xx xx, D2 xx xx, E2 xx xx, EA xx xx, F2 xx xx, FA xx xx 等)
        if b0 == 0xC3 or b0 in [0xC2, 0xCA, 0xDA, 0xD2, 0xE2, 0xEA, 0xF2, 0xFA]:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征7: JR指令 (18 xx, 或条件JR 20 xx, 28 xx, 30 xx, 38 xx)
        if b0 == 0x18 or b0 in [0x20, 0x28, 0x30, 0x38]:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征8: LD指令对 - 常见的函数开头模式
        # LD HL, xxxx (21 xx xx)
        if b0 == 0x21:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        # LD DE, xxxx (11 xx xx)
        if b0 == 0x11:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        # LD BC, xxxx (01 xx xx)
        if b0 == 0x01:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        # LD SP, xxxx (31 xx xx)
        if b0 == 0x31:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征9: IX/IY 相关指令 - 常见的结构化代码
        if b0 == 0xDD or b0 == 0xFD:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        # 特征10: RST指令 (C7, CF, D7, DF, E7, EF, F7, FF)
        if b0 in [0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF]:
            if self._check_code_continuity(addr, min_instructions=8):
                return True
            return False
        
        return False
    
    def _scan_and_disassemble_cold_code(self) -> None:
        """
        在未反汇编的数据区扫描潜在代码入口并反汇编它们
        不添加跳转目标到工作列表，避免污染控制流
        """
        unassembled_ranges = self._find_unassembled_ranges()
        
        for start, end in unassembled_ranges:
            # 跳过太小的区域（小于3字节，不太可能是代码）
            if end - start + 1 < 3:
                continue
            
            # 扫描该范围内的每个地址
            for addr in range(start, end + 1):
                # 跳过已经处理过的地址
                if addr in self.nodes or addr in self.visited:
                    continue
                
                # 使用代码模式检测
                if self._detect_code_patterns(addr):
                    # 反汇编基本块，但不添加跳转目标
                    node = self._disassemble_basic_block(addr, add_successors=False)
                    # 标记为冷代码入口
                    if node.instructions:
                        node.instructions[0] = (node.instructions[0][0], node.instructions[0][1], 
                                               f"; [COLD CODE ENTRY] {node.instructions[0][2]}")
    
    def generate_output(self) -> str:
        """
        生成反汇编输出文本
        
        返回:
            格式化的反汇编文本
        """
        lines = []
        
        # 文件头
        lines.append("; Z80 CONTROL FLOW DISASSEMBLY")
        lines.append(f"; BASE ADDRESS: {self.base_addr:04X}")
        lines.append(f"; TOTAL BYTES: {self.data_len}")
        lines.append(f"; ADDRESS RANGE: ${self.base_addr:04X} - ${self.base_addr + self.data_len - 1:04X}")
        lines.append(f"; BASIC BLOCKS: {len(self.nodes)}")
        lines.append(f"; PROCESSED ADDRESSES: {len(self.visited)}")
        lines.append("")
        
        # 按地址排序输出基本块
        sorted_addrs = sorted(self.nodes.keys())
        
        for addr in sorted_addrs:
            node = self.nodes[addr]
            
            # 跳过空的基本块（没有指令的块）
            if not node.instructions:
                continue
            
            # 基本块标记
            lines.append(f"; === BASIC BLOCK AT {addr:04X} ===")
            if node.is_entry:
                lines.append("; ENTRY POINT")
            if node.is_exit:
                lines.append("; EXIT POINT")
            if node.successors:
                succ_str = ', '.join(f'{s:04X}' for s in node.successors)
                lines.append(f"; SUCCESSORS: {succ_str}")
            lines.append("")
            
            # 输出指令
            for inst_addr, hex_bytes, inst_str in node.instructions:
                line = f"{inst_addr:04X}:  {hex_bytes:<20}  {inst_str}"
                lines.append(line)
            
            lines.append("")
        
        # 输出未被反汇编的数据区
        unassembled_ranges = self._find_unassembled_ranges()
        
        if unassembled_ranges:
            lines.append("; ========================================")
            lines.append("; UNASSEMBLED DATA AREAS")
            lines.append("; ========================================")
            lines.append(f"; TOTAL UNASSEMBLED BYTES: {sum(end - start + 1 for start, end in unassembled_ranges)}")
            lines.append("")
            
            for start, end in unassembled_ranges:
                lines.append(f"; === DATA AREA ${start:04X} - ${end:04X} ===")
                lines.append(f"; SIZE: {end - start + 1} BYTES")
                lines.append("")
                
                # 按每行16字节输出数据，显示十六进制和字符
                addr = start
                while addr <= end:
                    offset = addr - self.base_addr
                    # 计算当前行能输出的字节数
                    remaining = end - addr + 1
                    bytes_per_line = min(16, remaining)
                    
                    # 获取数据字节
                    data_bytes = self.data[offset:offset + bytes_per_line]
                    end_addr = addr + bytes_per_line - 1
                    
                    range_str = f"{addr:04X}-{end_addr:04X}"
                    hex_label = f"[{range_str}]  HEX : "
                    char_label = f"[{range_str}] CHAR : "
                    
                    # 十六进制字符串
                    hex_cells = [f" {b:02X}" for b in data_bytes]
                    hex_str = "".join(hex_cells)
                    
                    # 字符字符串
                    char_cells = []
                    for b in data_bytes:
                        try:
                            ch, _ = decode_cac3_byte(b)
                            ch = ch.strip()
                            if len(ch) > 1:
                                ch = ch[0]
                            elif len(ch) == 0:
                                ch = "."
                        except:
                            ch = "."
                        char_cells.append(f"{ch:>3s}")
                    
                    char_str = "".join(char_cells)
                    
                    lines.append(f"{hex_label}{hex_str}")
                    lines.append(f"{char_label}{char_str}")
                    
                    addr += bytes_per_line
                
                lines.append("")
        
        return '\n'.join(lines)
    
    def save_output(self, output_file: str):
        """保存反汇编结果到文件"""
        asm_text = self.generate_output()
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(asm_text)


def disassemble_z80_flow(data: bytes, base_addr: int = 0x0000, 
                         start_addr: int = None, output_file: str = None,
                         cold_code_scan: bool = True) -> str:
    """
    基于控制流的 Z80 反汇编函数
    
    参数:
        data (bytes): 二进制 ROM 数据
        base_addr (int): 基地址（默认 0x0000）
        start_addr (int, optional): 起始反汇编地址，如果为 None 则使用 base_addr
        output_file (str, optional): 输出文件路径
        cold_code_scan (bool): 是否进行冷代码扫描（默认 True）
    
    返回:
        str: 反汇编文本
    """
    if not isinstance(data, bytes):
        raise TypeError("data 必须是 bytes 类型")
    if not data:
        return "; 空数据，无反汇编结果"
    
    # 创建反汇编器
    disassembler = FlowDisassembler(data, base_addr, cold_code_scan)
    
    # 执行反汇编
    disassembler.disassemble(start_addr)
    
    # 生成输出
    asm_text = disassembler.generate_output()
    
    # 保存到文件
    if output_file:
        disassembler.save_output(output_file)
    
    return asm_text


if __name__ == "__main__":
    # 测试示例
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python z80_flow_disasm.py <rom_file> [base_addr] [start_addr] [output_file]")
        sys.exit(1)
    
    rom_file = sys.argv[1]
    base_addr = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x0000
    start_addr = int(sys.argv[3], 16) if len(sys.argv) > 3 else None
    output_file = sys.argv[4] if len(sys.argv) > 4 else None
    
    with open(rom_file, 'rb') as f:
        data = f.read()
    
    result = disassemble_z80_flow(data, base_addr, start_addr, output_file)
    
    if not output_file:
        print(result)
