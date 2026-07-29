# ==========================================
# CAC-3 字符与 Token 映射表
# ==========================================
CAC3_CHAR_MAP = {
    0x00: " ", 0x01: "▘", 0x02: "▝", 0x03: "▀", 0x04: "▖", 0x05: "▌", 0x06: "▞", 0x07: "▛",
    0x08: "🚗", 0x09: "◤", 0x0A: "◥", 0x0B: '"', 0x0C: "🕷️", 0x0D: "$", 0x0E: "🦋", 0x0F: "👾",
    0x10: "(", 0x11: ")", 0x12: ">", 0x13: "<", 0x14: "=", 0x15: "+", 0x16: "-", 0x17: "*",
    0x18: "/", 0x19: ";", 0x1A: ",", 0x1B: ".", 0x1C: "0", 0x1D: "1", 0x1E: "2", 0x1F: "3",
    0x20: "4", 0x21: "5", 0x22: "6", 0x23: "7", 0x24: "8", 0x25: "9", 0x26: "A", 0x27: "B",
    0x28: "C", 0x29: "D", 0x2A: "E", 0x2B: "F", 0x2C: "G", 0x2D: "H", 0x2E: "I", 0x2F: "J",
    0x30: "K", 0x31: "L", 0x32: "M", 0x33: "N", 0x34: "O", 0x35: "P", 0x36: "Q", 0x37: "R",
    0x38: "S", 0x39: "T", 0x3A: "U", 0x3B: "V", 0x3C: "W", 0x3D: "X", 0x3E: "Y", 0x3F: "Z",
    0x40: "THEN", 0x41: "TO", 0x42: "STEP", 0x43: "RND", 0x44: "INKEY$", 0x45: "PI",
}

CAC3_TOKENS = {
    0xC0: "CODE", 0xC1: "VAL", 0xC2: "LEN", 0xC3: "SIN", 0xC4: "COS", 0xC5: "TAN", 0xC6: "ASN",
    0xC7: "ACS", 0xC8: "ATN", 0xC9: "LOG", 0xCA: "EXP", 0xCB: "INT", 0xCC: "SQR", 0xCD: "SGN", 0xCE: "ABS",
    0xCF: "PEEK", 0xD0: "USR", 0xD1: "STR$", 0xD2: "CHR$", 0xD3: "NOT", 0xD4: "AT", 0xD5: "TAB", 0xD6: "**", 0xD7: "OR",
    0xD8: "AND", 0xD9: "<=", 0xDA: ">=", 0xDB: "<>", 0xDC: "TEMPO", 0xDD: "MUSIC", 0xDE: "SOUND", 0xDF: "BEEP",
    0xE0: "NOBEEP", 0xE1: "LPRINT", 0xE2: "LLIST", 0xE3: "STOP", 0xE4: "SLOW", 0xE5: "FAST", 0xE6: "NEW",
    0xE7: "SCROLL", 0xE8: "CONT", 0xE9: "DIM", 0xEA: "REM", 0xEB: "FOR", 0xEC: "GOTO", 0xED: "GOSUB", 0xEE: "INPUT",
    0xEF: "LOAD", 0xF0: "LIST", 0xF1: "LET", 0xF2: "PAUSE", 0xF3: "NEXT", 0xF4: "POKE", 0xF5: "PRINT", 0xF6: "PLOT",
    0xF7: "RUN", 0xF8: "SAVE", 0xF9: "RAND", 0xFA: "IF", 0xFB: "CLS", 0xFC: "UNPLOT", 0xFD: "CLEAR", 0xFE: "RETURN",
    0xFF: "COPY"
}


def decode_cac3_byte(byte_val):
    """解析单个字节并返回字符与其反显状态（限制为标准 ASCII 以确保严格等宽）"""
    is_inverse = bool(byte_val & 0x80)
    code = byte_val & 0x7F

    if code in CAC3_CHAR_MAP:
        val = CAC3_CHAR_MAP[code]
        if any(ord(c) > 127 for c in val):
            return ".", is_inverse
        return val, is_inverse
    elif 32 <= code <= 126:
        return chr(code), is_inverse

    return ".", is_inverse


def parse_basic_program(data, start_idx):
    """解析 BASIC 程序段（精确区分引号内外的空格与 Token 格式化）"""
    basic_lines = []
    curr = start_idx

    while curr + 4 <= len(data):
        line_num = (data[curr] << 8) | data[curr + 1]

        if line_num == 0 or line_num > 9999:
            break

        line_len = data[curr + 2] | (data[curr + 3] << 8)
        if line_len <= 0 or curr + 4 + line_len > len(data):
            break

        line_bytes = data[curr + 4 : curr + 4 + line_len]
        curr += 4 + line_len

        tokens = []
        i = 0
        in_quotes = False  # 引号状态标记

        while i < len(line_bytes):
            b = line_bytes[i]

            # 0x76 行结束符
            if b == 0x76:
                break
            # 0x7E 浮点数常数跟在 Token 后面的 5 字节浮点数数据，跳过
            elif b == 0x7E:
                i += 6
                continue

            # 检测双引号 (0x0B)
            if b == 0x0B:
                in_quotes = not in_quotes
                tokens.append('"')
                i += 1
                continue

            # 1. 如果在双引号内部：严格按字符映射还原，保留所有原始空格，不做任何 Token 解析
            if in_quotes:
                if b in CAC3_CHAR_MAP:
                    tokens.append(CAC3_CHAR_MAP[b])
                else:
                    ch, _ = decode_cac3_byte(b)
                    tokens.append(ch)

            # 2. 如果在双引号外部：进行 Token 匹配与合理的格式化空格补充
            else:
                if b in CAC3_TOKENS:
                    token_str = CAC3_TOKENS[b]
                    # 前面如果不为空且不是空格，补一个空格
                    if tokens and not tokens[-1].endswith(" "):
                        tokens.append(" ")
                    tokens.append(token_str)
                    # Token 后面补一个空格
                    tokens.append(" ")
                elif b in CAC3_CHAR_MAP:
                    val = CAC3_CHAR_MAP[b]
                    # 如果是 4x 区域的多字符 Token (如 THEN, TO, STEP)
                    if len(val) > 1 and val.isupper():
                        if tokens and not tokens[-1].endswith(" "):
                            tokens.append(" ")
                        tokens.append(val)
                        tokens.append(" ")
                    else:
                        tokens.append(val)
                else:
                    ch, _ = decode_cac3_byte(b)
                    tokens.append(ch)

            i += 1

        raw_code = "".join(tokens)

        # 针对引号外部的代码进行多余连续空格的归一化（但绝对不触碰引号内部）
        final_parts = []
        part_in_quotes = False
        # 按双引号分割段落：偶数索引是代码，奇数索引是字符串字面量
        segments = raw_code.split('"')

        for idx, seg in enumerate(segments):
            if idx % 2 == 0:
                # 引号外部：清理多余的连续空格（如 "PRINT   AT" -> "PRINT AT"）
                import re

                clean_seg = re.sub(r" +", " ", seg)
                final_parts.append(clean_seg)
            else:
                # 引号内部：保留原样，包括连续空格
                final_parts.append(f'"{seg}"')

        clean_code = "".join(final_parts).strip()

        if clean_code:
            basic_lines.append(f"{line_num} {clean_code}")

    return basic_lines


def process_cac3_bin(file_path, hex_formatter_func):
    """解析 BIN 文件的主入口（传入 16进制格式化函数）"""
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        if not data:
            return "错误：文件为空", "", "", None, []

        fn_end_idx = -1
        filename_chars = []
        for idx, byte in enumerate(data):
            ch, _ = decode_cac3_byte(byte)
            filename_chars.append(ch)
            if byte & 0x80:
                fn_end_idx = idx
                break

        parsed_name = "".join(filename_chars) if fn_end_idx != -1 else "未命名"

        ff_idx = -1
        search_start = fn_end_idx + 1 if fn_end_idx != -1 else 0
        for i in range(search_start, len(data)):
            if data[i] == 0xFF:
                ff_idx = i
                break

        sys_start = ff_idx + 1 if ff_idx != -1 else 0
        vbuf_start_idx = sys_start + 116

        sys_info = f"0xFF标志: {'0x%04X' % ff_idx if ff_idx != -1 else '未找到'} | 系统区: 0x{sys_start:04X} | 显存: 0x{vbuf_start_idx:04X}"

        sys_bytes = data[sys_start: sys_start + 116]
        sys_bytes_dump = hex_formatter_func(sys_bytes)

        screen_matrix = []
        curr = vbuf_start_idx
        lines_found = 0
        current_line = []

        while curr < len(data) and lines_found < 24:
            b = data[curr]
            if b == 0x76:
                lines_found += 1
                while len(current_line) < 32:
                    current_line.append((" ", False))
                screen_matrix.append(current_line)
                current_line = []
            else:
                if len(current_line) < 32:
                    ch, is_inv = decode_cac3_byte(b)
                    current_line.append((ch, is_inv))
            curr += 1

        while len(screen_matrix) < 24:
            screen_matrix.append([(" ", False)] * 32)

        basic_start_idx = curr
        basic_code_lines = parse_basic_program(data, basic_start_idx)

        if not basic_code_lines:
            for candidate_idx in range(116, len(data) - 4):
                if candidate_idx == basic_start_idx:
                    continue
                test_num = (data[candidate_idx] << 8) | data[candidate_idx + 1]
                test_len = data[candidate_idx + 2] | (data[candidate_idx + 3] << 8)
                if 1 <= test_num <= 9999 and 0 < test_len < 2048:
                    trial_lines = parse_basic_program(data, candidate_idx)
                    if len(trial_lines) > 0:
                        basic_code_lines = trial_lines
                        sys_info += f" | 自动重定位: 0x{candidate_idx:04X}"
                        break

        return parsed_name, sys_info, sys_bytes_dump, screen_matrix, basic_code_lines

    except Exception as e:
        import traceback
        traceback.print_exc()
        return "解析失败", f"错误: {str(e)}", "", None, []