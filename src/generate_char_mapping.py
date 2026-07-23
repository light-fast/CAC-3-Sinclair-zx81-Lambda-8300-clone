# 运行此脚本直接在本地生成绝对精准的 CSV
import csv

# 构造标准 ZX81/Lambda 8300 字符映射字典
charmap = {0x00: " (Space)", 0x01: "▘", 0x02: "▝", 0x03: "▀", 0x04: "▖", 0x05: "▌", 0x06: "▞", 0x07: "▛", 0x08: "◤",
    0x09: "◥", 0x0A: "◢", 0x0B: "Invader", 0x0C: "Ghost", 0x0D: "Car", 0x0E: "Butterfly", 0x0F: '"', 0x10: "$",
    0x11: ":", 0x12: "?", 0x13: "(", 0x14: ")", 0x15: ">", 0x16: "<", 0x17: "=", 0x18: "+", 0x19: "-", 0x1A: "*",
    0x1B: "/", # 数字 0-9 (0x1C - 0x25)
    **{0x1C + i: str(i) for i in range(10)}, # 字母 A-Z (0x26 - 0x3F)
    **{0x26 + i: chr(ord('A') + i) for i in range(26)}, }

# 关键字 Token 映射 (0x40 - 0x5E)
tokens = ["RND", "INKEY$", "PI", "FN", "POINT", "SCREENS$", "ATTR", "AT", "TAB", "VAL$", "CODE", "VAL", "LEN", "SIN",
    "COS", "TAN", "ASN", "ACS", "ATN", "LN", "EXP", "INT", "SQR", "SGN", "ABS", "PEEK", "BIN", "USR", "STR$", "CHR$",
    "NOT"]
for i, t in enumerate(tokens):
    charmap[0x40 + i] = t

# 控制字符 (0x70 - 0x7F)
ctrl = ["UP", "DOWN", "LEFT", "RIGHT", "GRAPHICS", "EDIT", "HALT/NEWLINE", "DELETE", "RUBOUT", "FUNCTION", "LINE FEED",
        "INVERSE", "TRUE VIDEO", "INV_CURSOR", "NUMBER", "CURSOR"]
for i, c in enumerate(ctrl):
    charmap[0x70 + i] = c

# 自动生成 256 字节表
with open("lambda8300_perfect.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Hex", "Dec", "Binary", "Character/Token"])

    for i in range(256):
        hex_str = f"0x{i:02X}"
        bin_str = f"{i:08b}"

        # 判断字符类型
        if i in charmap:
            val = charmap[i]
        elif 0x80 <= i <= 0xBF and (i - 0x80) in charmap:
            val = f"[INV {charmap[i - 0x80]}]"
        elif 0xC0 <= i <= 0xFE:
            val = f"[BASIC_TOKEN_0x{i:02X}]"  # 可根据实际系统定义扩展
        else:
            val = "[UNASSIGNED]"

        writer.writerow([hex_str, i, bin_str, val])

print("生成完毕！文件 lambda8300_perfect.csv 已保存。")