from basic_decoder import decode_cac3_byte


def format_hex_and_char_bytes(raw_bytes, base_address=0):
    """格式化为十六进制与字符双行对照"""
    lines = []
    for i in range(0, len(raw_bytes), 16):
        chunk = raw_bytes[i: i + 16]
        start_addr = base_address + i
        end_addr = start_addr + len(chunk) - 1

        range_str = f"{start_addr:04X}-{end_addr:04X}"
        hex_label = f" [{range_str}]  HEX : "
        char_label = f" [{range_str}] CHAR : "

        hex_cells = [f" {b:02X}" for b in chunk]
        hex_str = "".join(hex_cells)

        char_cells = []
        for b in chunk:
            ch, _ = decode_cac3_byte(b)
            ch = ch.strip()
            if len(ch) > 1:
                ch = ch[0]
            elif len(ch) == 0:
                ch = "."

            char_cells.append(f"{ch:>3s}")

        char_str = "".join(char_cells)

        lines.append(f"{hex_label}{hex_str}")
        lines.append(f"{char_label}{char_str}")

    return "\n".join(lines)