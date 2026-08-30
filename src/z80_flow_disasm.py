"""
基于控制流的 Z80 反汇编模块
从起始地址开始反汇编，遇到跳转时跳到相应地址继续，用控制流图记录所有分支并遍历。
"""

import re
from collections import deque
from typing import Set, Dict, List, Tuple
from z80dis import z80


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
    
    def __init__(self, data: bytes, base_addr: int = 0x0000):
        self.data = data
        self.base_addr = base_addr
        self.data_len = len(data)
        
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
    
    def _disassemble_basic_block(self, start_addr: int) -> ControlFlowNode:
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
                        # 只添加未访问过且不在当前块中的跳转目标到工作列表
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
        
        return self.nodes
    
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
        lines.append(f"; PROCRESSED ADDRESSES: {sorted(self.nodes.keys())}")
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
        
        return '\n'.join(lines)
    
    def save_output(self, output_file: str):
        """保存反汇编结果到文件"""
        asm_text = self.generate_output()
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(asm_text)


def disassemble_z80_flow(data: bytes, base_addr: int = 0x0000, 
                         start_addr: int = None, output_file: str = None) -> str:
    """
    基于控制流的 Z80 反汇编函数
    
    参数:
        data (bytes): 二进制 ROM 数据
        base_addr (int): 基地址（默认 0x0000）
        start_addr (int, optional): 起始反汇编地址，如果为 None 则使用 base_addr
        output_file (str, optional): 输出文件路径
    
    返回:
        str: 反汇编文本
    """
    if not isinstance(data, bytes):
        raise TypeError("data 必须是 bytes 类型")
    if not data:
        return "; 空数据，无反汇编结果"
    
    # 创建反汇编器
    disassembler = FlowDisassembler(data, base_addr)
    
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
