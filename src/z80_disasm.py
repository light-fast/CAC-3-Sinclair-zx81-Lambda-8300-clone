
import re
from z80dis import z80

def _format_instruction(inst_str: str) -> str:
    """
    将反汇编字符串转为大写，并规范逗号后的空格。
    例: "ld hl,0x8000" -> "LD HL, 0x8000"
    """
    # 1. 整个字符串转大写（包括助记符、寄存器、数字中的字母）
    inst_upper = inst_str.upper()

    # 2. 将逗号（及后面任意空白）替换为 ", "
    #    r',\s*' 匹配逗号及后面零个或多个空白字符，替换为 ', '
    formatted = re.sub(r',\s*', ', ', inst_upper)
    return formatted


def disassemble_z80_bytes(data, base_addr=0x0000, output_file=None):
    """
    对 Z80 二进制数据进行反汇编，返回大写、逗号后有空格的文本。

    参数:
        data (bytes): 二进制 ROM 数据
        base_addr (int): 起始地址（默认 0x0000）
        output_file (str, optional): 若指定，则将结果写入该文件

    返回:
        str: 反汇编文本
    """
    if not isinstance(data, bytes):
        raise TypeError("data 必须是 bytes 类型")
    if not data:
        return "; 空数据，无反汇编结果"

    lines = []
    addr = base_addr
    offset = 0
    total = len(data)

    # 文件头（地址已是大写）
    lines.append(f"; Z80 DISASSEMBLY")
    lines.append(f"; START ADDRESS: {base_addr:04X}")
    lines.append(f"; TOTAL BYTES: {total}")
    lines.append("")

    while offset < total:
        try:
            # 原始反汇编字符串（可能小写）
            raw_inst = z80.disasm(data[offset:], addr)
            # 应用格式：大写 + 逗号空格
            inst_str = _format_instruction(raw_inst)

            decoded = z80.decode(data[offset:], addr)
            inst_len = decoded.len

            # 机器码（大写十六进制，每个字节两位）
            hex_bytes = ' '.join(f'{b:02X}' for b in data[offset:offset + inst_len])
            # 地址（大写四位）
            line = f"{addr:04X}:  {hex_bytes:<20}  {inst_str}"
            lines.append(line)

            addr += inst_len
            offset += inst_len
        except Exception as e:
            lines.append(f"{addr:04X}:  ??  ; 解码失败: {e}")
            addr += 1
            offset += 1

    asm_text = '\n'.join(lines)
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(asm_text)
    return asm_text

#
# def disassemble_z80_bytes(data, base_addr=0x0000, output_file=None):
#     """全面精确解译的 Z80 反汇编引擎"""
#     regs_r = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
#     regs_rp = ["BC", "DE", "HL", "SP"]
#     regs_rp2 = ["BC", "DE", "HL", "AF"]
#     cc = ["NZ", "Z", "NC", "C", "PO", "PE", "P", "M"]
#     alu_ops = [
#         "ADD A,",
#         "ADC A,",
#         "SUB ",
#         "SBC A,",
#         "AND ",
#         "XOR ",
#         "OR ",
#         "CP ",
#     ]
#     rot_ops = ["RLC", "RRC", "RL", "RR", "SLA", "SRA", "SLL", "SRL"]
#
#     disassembled_lines = []
#     pc = 0
#     length = len(data)
#
#     def to_signed(val):
#         return val - 256 if val > 127 else val
#
#     def fmt_offset(d_val):
#         s = to_signed(d_val)
#         return f"+${s:02X}" if s >= 0 else f"-${abs(s):02X}"
#
#     while pc < length:
#         addr = base_addr + pc
#         b0 = data[pc]
#         bytes_consumed = 1
#         inst_str = ""
#
#         # --- 1. 处理 IX (DD) / IY (FD) 前缀开头的复合指令 ---
#         if (b0 == 0xDD or b0 == 0xFD) and pc + 1 < length:
#             idx_name = "IX" if b0 == 0xDD else "IY"
#             b1 = data[pc + 1]
#
#             if b1 == 0xCB and pc + 3 < length:
#                 offset_val = data[pc + 2]
#                 b3 = data[pc + 3]
#                 bytes_consumed = 4
#
#                 r_idx = b3 & 0x07
#                 op_type = (b3 >> 6) & 0x03
#                 bit_idx = (b3 >> 3) & 0x07
#                 off_str = fmt_offset(offset_val)
#
#                 if op_type == 0:
#                     op_name = rot_ops[bit_idx]
#                     inst_str = f"{op_name} ({idx_name}{off_str})"
#                 elif op_type == 1:
#                     inst_str = f"BIT {bit_idx}, ({idx_name}{off_str})"
#                 elif op_type == 2:
#                     inst_str = f"RES {bit_idx}, ({idx_name}{off_str})"
#                 elif op_type == 3:
#                     inst_str = f"SET {bit_idx}, ({idx_name}{off_str})"
#
#             elif b1 == 0x21 and pc + 3 < length:
#                 val = data[pc + 2] | (data[pc + 3] << 8)
#                 inst_str = f"LD {idx_name}, ${val:04X}"
#                 bytes_consumed = 4
#             elif b1 == 0x22 and pc + 3 < length:
#                 val = data[pc + 2] | (data[pc + 3] << 8)
#                 inst_str = f"LD (${val:04X}), {idx_name}"
#                 bytes_consumed = 4
#             elif b1 == 0x2A and pc + 3 < length:
#                 val = data[pc + 2] | (data[pc + 3] << 8)
#                 inst_str = f"LD {idx_name}, (${val:04X})"
#                 bytes_consumed = 4
#             elif b1 == 0x23:
#                 inst_str = f"INC {idx_name}"
#                 bytes_consumed = 2
#             elif b1 == 0x2B:
#                 inst_str = f"DEC {idx_name}"
#                 bytes_consumed = 2
#             elif b1 == 0xE5:
#                 inst_str = f"PUSH {idx_name}"
#                 bytes_consumed = 2
#             elif b1 == 0xE1:
#                 inst_str = f"POP {idx_name}"
#                 bytes_consumed = 2
#             elif b1 == 0xE9:
#                 inst_str = f"JP ({idx_name})"
#                 bytes_consumed = 2
#             elif b1 == 0xF9:
#                 inst_str = f"LD SP, {idx_name}"
#                 bytes_consumed = 2
#             elif (b1 & 0xC7) == 0x46 and pc + 2 < length and b1 != 0x76:
#                 r_idx = (b1 >> 3) & 0x07
#                 off_str = fmt_offset(data[pc + 2])
#                 inst_str = f"LD {regs_r[r_idx]}, ({idx_name}{off_str})"
#                 bytes_consumed = 3
#             elif (b1 & 0xF8) == 0x70 and pc + 2 < length and b1 != 0x76:
#                 r_idx = b1 & 0x07
#                 off_str = fmt_offset(data[pc + 2])
#                 inst_str = f"LD ({idx_name}{off_str}), {regs_r[r_idx]}"
#                 bytes_consumed = 3
#             elif b1 == 0x36 and pc + 3 < length:
#                 off_str = fmt_offset(data[pc + 2])
#                 val = data[pc + 3]
#                 inst_str = f"LD ({idx_name}{off_str}), ${val:02X}"
#                 bytes_consumed = 4
#             elif (b1 & 0xF8) == 0x86 and pc + 2 < length:
#                 op_idx = (b1 >> 3) & 0x07
#                 off_str = fmt_offset(data[pc + 2])
#                 inst_str = f"{alu_ops[op_idx]}({idx_name}{off_str})"
#                 bytes_consumed = 3
#
#         # --- 2. 基础标准 Z80 指令与逻辑 ---
#         if not inst_str:
#             if b0 == 0x00:
#                 inst_str = "NOP"
#             elif b0 == 0x76:
#                 inst_str = "HALT"
#             elif b0 == 0x23:
#                 inst_str = "INC HL"
#             elif b0 == 0x2B:
#                 inst_str = "DEC HL"
#             elif b0 == 0x03:
#                 inst_str = "INC BC"
#             elif b0 == 0x13:
#                 inst_str = "INC DE"
#             elif b0 == 0x33:
#                 inst_str = "INC SP"
#             elif b0 == 0x0B:
#                 inst_str = "DEC BC"
#             elif b0 == 0x1B:
#                 inst_str = "DEC DE"
#             elif b0 == 0x3B:
#                 inst_str = "DEC SP"
#
#             elif b0 == 0x2A and pc + 2 < length:
#                 target = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"LD HL, (${target:04X})"
#                 bytes_consumed = 3
#             elif b0 == 0x22 and pc + 2 < length:
#                 target = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"LD (${target:04X}), HL"
#                 bytes_consumed = 3
#             elif b0 == 0x32 and pc + 2 < length:
#                 target = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"LD (${target:04X}), A"
#                 bytes_consumed = 3
#             elif b0 == 0x3A and pc + 2 < length:
#                 target = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"LD A, (${target:04X})"
#                 bytes_consumed = 3
#
#             elif b0 == 0xC3 and pc + 2 < length:
#                 target = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"JP ${target:04X}"
#                 bytes_consumed = 3
#             elif b0 == 0xCD and pc + 2 < length:
#                 target = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"CALL ${target:04X}"
#                 bytes_consumed = 3
#             elif b0 == 0xC9:
#                 inst_str = "RET"
#             elif b0 == 0xD3 and pc + 1 < length:
#                 port = data[pc + 1]
#                 inst_str = f"OUT (${port:02X}), A"
#                 bytes_consumed = 2
#             elif b0 == 0xDB and pc + 1 < length:
#                 port = data[pc + 1]
#                 inst_str = f"IN A, (${port:02X})"
#                 bytes_consumed = 2
#             elif (b0 & 0xC7) == 0x06 and pc + 1 < length:
#                 r_idx = (b0 >> 3) & 0x07
#                 val = data[pc + 1]
#                 inst_str = f"LD {regs_r[r_idx]}, ${val:02X}"
#                 bytes_consumed = 2
#             elif (b0 & 0xCF) == 0x01 and pc + 2 < length:
#                 rp_idx = (b0 >> 4) & 0x03
#                 val = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"LD {regs_rp[rp_idx]}, ${val:04X}"
#                 bytes_consumed = 3
#             elif (b0 & 0xC0) == 0x40:
#                 r1 = (b0 >> 3) & 0x07
#                 r2 = b0 & 0x07
#                 inst_str = f"LD {regs_r[r1]}, {regs_r[r2]}"
#             elif (b0 & 0xC0) == 0x80:
#                 op_idx = (b0 >> 3) & 0x07
#                 r_idx = b0 & 0x07
#                 inst_str = f"{alu_ops[op_idx]}{regs_r[r_idx]}"
#             elif (b0 & 0xC7) == 0xC6 and pc + 1 < length:
#                 op_idx = (b0 >> 3) & 0x07
#                 val = data[pc + 1]
#                 inst_str = f"{alu_ops[op_idx]}${val:02X}"
#                 bytes_consumed = 2
#             elif (b0 & 0xC7) == 0xC2 and pc + 2 < length:
#                 cc_idx = (b0 >> 3) & 0x07
#                 target = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"JP {cc[cc_idx]}, ${target:04X}"
#                 bytes_consumed = 3
#             elif (b0 & 0xC7) == 0xC4 and pc + 2 < length:
#                 cc_idx = (b0 >> 3) & 0x07
#                 target = data[pc + 1] | (data[pc + 2] << 8)
#                 inst_str = f"CALL {cc[cc_idx]}, ${target:04X}"
#                 bytes_consumed = 3
#             elif (b0 & 0xC7) == 0xC0:
#                 cc_idx = (b0 >> 3) & 0x07
#                 inst_str = f"RET {cc[cc_idx]}"
#             elif (b0 & 0xCF) == 0xC5:
#                 rp_idx = (b0 >> 4) & 0x03
#                 inst_str = f"PUSH {regs_rp2[rp_idx]}"
#             elif (b0 & 0xCF) == 0xC1:
#                 rp_idx = (b0 >> 4) & 0x03
#                 inst_str = f"POP {regs_rp2[rp_idx]}"
#             elif b0 == 0x18 and pc + 1 < length:
#                 target = addr + 2 + to_signed(data[pc + 1])
#                 inst_str = f"JR ${target:04X}"
#                 bytes_consumed = 2
#             elif (b0 & 0xE7) == 0x20 and pc + 1 < length:
#                 cc_idx = (b0 >> 3) & 0x03
#                 target = addr + 2 + to_signed(data[pc + 1])
#                 inst_str = f"JR {cc[cc_idx]}, ${target:04X}"
#                 bytes_consumed = 2
#             elif (b0 & 0xC7) == 0xC7:
#                 p_val = b0 & 0x38
#                 inst_str = f"RST ${p_val:02X}"
#             elif b0 == 0xED and pc + 1 < length:
#                 b1 = data[pc + 1]
#                 bytes_consumed = 2
#                 inst_str = f"NOP (ED ${b1:02X})"
#             elif b0 == 0xCB and pc + 1 < length:
#                 b1 = data[pc + 1]
#                 bytes_consumed = 2
#                 r_idx = b1 & 0x07
#                 op_type = (b1 >> 6) & 0x03
#                 bit_idx = (b1 >> 3) & 0x07
#                 if op_type == 0:
#                     inst_str = f"{rot_ops[bit_idx]} {regs_r[r_idx]}"
#                 elif op_type == 1:
#                     inst_str = f"BIT {bit_idx}, {regs_r[r_idx]}"
#                 elif op_type == 2:
#                     inst_str = f"RES {bit_idx}, {regs_r[r_idx]}"
#                 elif op_type == 3:
#                     inst_str = f"SET {bit_idx}, {regs_r[r_idx]}"
#             else:
#                 inst_str = f"DB ${b0:02X}"
#
#         hex_bytes = " ".join(
#             f"{data[pc + j]:02X}" for j in range(bytes_consumed)
#         )
#         disassembled_lines.append(f"${addr:04X}:  {hex_bytes:<12s}  {inst_str}")
#
#         pc += bytes_consumed
#
#     result = "\n".join(disassembled_lines)
#
#     # Save to file if output_file is specified
#     if output_file:
#         with open(output_file, "w", encoding="utf-8") as f:
#             f.write(result)
#
#     return result