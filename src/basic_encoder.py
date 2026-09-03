import numpy as np
import scipy.io.wavfile as wavfile
import ctypes
import struct
import math

# ==========================================
# 1. 字符与 Token 编码表
# ==========================================
BASIC_TOKENS = {
    # 4x 区域 (单字节关键字)
    "THEN": 0x40, "TO": 0x41, "STEP": 0x42, "RND": 0x43, "INKEY$": 0x44, "PI": 0x45,

    # Cx 区域 (数学/字符串函数)
    "CODE": 0xC0, "VAL": 0xC1, "LEN": 0xC2, "SIN": 0xC3, "COS": 0xC4, "TAN": 0xC5, "ASN": 0xC6, "ACS": 0xC7,
    "ATN": 0xC8, "LOG": 0xC9, "EXP": 0xCA, "INT": 0xCB, "SQR": 0xCC, "SGN": 0xCD, "ABS": 0xCE, "PEEK": 0xCF,

    # Dx 区域 (逻辑与运算符)
    "USR": 0xD0, "STR$": 0xD1, "CHR$": 0xD2, "NOT": 0xD3, "AT": 0xD4, "TAB": 0xD5, "**": 0xD6, "OR": 0xD7, "AND": 0xD8,
    "<=": 0xD9, ">=": 0xDA, "<>": 0xDB, "TEMPO": 0xDC, "MUSIC": 0xDD, "SOUND": 0xDE, "BEEP": 0xDF,

    # Ex 区域 (控制指令)
    "NOBEEP": 0xE0, "LPRINT": 0xE1, "LLIST": 0xE2, "STOP": 0xE3, "SLOW": 0xE4, "FAST": 0xE5, "NEW": 0xE6,
    "SCROLL": 0xE7, "CONT": 0xE8, "DIM": 0xE9, "REM": 0xEA, "FOR": 0xEB, "GOTO": 0xEC, "GOSUB": 0xED, "INPUT": 0xEE,
    "LOAD": 0xEF,

    # Fx 区域 (主语句指令)
    "LIST": 0xF0, "LET": 0xF1, "PAUSE": 0xF2, "NEXT": 0xF3, "POKE": 0xF4, "PRINT": 0xF5, "PLOT": 0xF6, "RUN": 0xF7,
    "SAVE": 0xF8, "RAND": 0xF9, "IF": 0xFA, "CLS": 0xFB, "UNPLOT": 0xFC, "CLEAR": 0xFD, "RETURN": 0xFE, "COPY": 0xFF
}

SYMBOL_MAP = {
    '"': 0x0B, '$': 0x0D, '(': 0x10, ')': 0x11, '>': 0x12, '<': 0x13, '=': 0x14, '+': 0x15, '-': 0x16,
    '*': 0x17, '/': 0x18, ';': 0x19, ',': 0x1A, '.': 0x1B
}

class CAC3SysVariables(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        # # 0x4000 - 0x4008 (Saved = No)
        # ('ERR_NR', ctypes.c_uint8),           # 0x4000
        # ('FLAGS', ctypes.c_uint8),            # 0x4001
        # ('ERR_SP', ctypes.c_uint16),          # 0x4002
        # ('RAMTOP', ctypes.c_uint16),          # 0x4004
        # ('MODE', ctypes.c_uint8),             # 0x4006
        # ('PPC', ctypes.c_uint16),             # 0x4007

        # 0x4009 - 0x407C (Saved = Yes)
        ('VERSN', ctypes.c_uint8),            # 0x4009, FFH
        ('NXTLIN', ctypes.c_uint16),           # 0x400A, 407DH
        ('PROGRAM', ctypes.c_uint16),          # 0x400C, 4396H
        ('NXTLIN1', ctypes.c_uint16),           # 0x400E, 407EH
        ('VARS', ctypes.c_uint16),            # 0x4010, end of basic + 1
        ('DEST', ctypes.c_uint16),            # 0x4012, 0000H
        ('E_LINE', ctypes.c_uint16),          # 0x4014, (0x4010) + 1
        ('CH_ADD', ctypes.c_uint16),          # 0x4016
        ('X_PTR', ctypes.c_uint16),           # 0x4018
        ('STKBOT', ctypes.c_uint16),          # 0x401A
        ('STKEND', ctypes.c_uint16),          # 0x401C
        ('BERG', ctypes.c_uint8),             # 0x401E
        ('MEM', ctypes.c_uint16),             # 0x401F
        ('NUMIT', ctypes.c_uint8),            # 0x4021
        ('DF_SZ', ctypes.c_uint8),            # 0x4022
        ('S_TOP', ctypes.c_uint16),           # 0x4023
        ('LAST_K', ctypes.c_uint16),          # 0x4025
        ('BOUNCE', ctypes.c_uint8),           # 0x4027
        ('MARGIN', ctypes.c_uint8),           # 0x4028
        ('E-PPC', ctypes.c_uint16),           # 0x4029
        ('OLDPPC', ctypes.c_uint16),          # 0x402B
        ('FLAGX', ctypes.c_uint8),            # 0x402D
        ('STRLEN', ctypes.c_uint16),          # 0x402E
        ('T_ADDR', ctypes.c_uint16),          # 0x4030
        ('SEED', ctypes.c_uint16),            # 0x4032
        ('FRAMES', ctypes.c_uint16),          # 0x4034
        ('COORDS_X', ctypes.c_uint8),         # 0x4036 (x-coordinate)
        ('COORDS_Y', ctypes.c_uint8),         # 0x4037 (y-coordinate)
        ('PR_CC', ctypes.c_uint8),            # 0x4038
        ('S_POSN_COL', ctypes.c_uint8),       # 0x4039 (column)
        ('S_POSN_LINE', ctypes.c_uint8),      # 0x403A (line)
        ('CDFLAG', ctypes.c_uint8),           # 0x403B
        ('PRBUFF', ctypes.c_uint8 * 33),      # 0x403C (33 bytes)
        ('MEMBOT', ctypes.c_uint8 * 30),      # 0x405D (30 bytes)
        ('BLINK', ctypes.c_uint16),           # 0x407B (2 bytes)
    ]


def encode_char(c: str) -> int:
    """单个字符转换为 Lambda 8300 字节码"""
    c_upper = c.upper()
    if c_upper == ' ':
        return 0x00
    elif '0' <= c_upper <= '9':
        return 0x1C + (ord(c_upper) - ord('0'))
    elif 'A' <= c_upper <= 'Z':
        return 0x26 + (ord(c_upper) - ord('A'))
    elif c_upper in SYMBOL_MAP:
        return SYMBOL_MAP[c_upper]
    return 0x00


def encode_number(num_str: str) -> bytearray:
    """将数字字符串转换为 ZX81 浮点数格式（0x7E + 5 字节 = 6 字节）"""
    try:
        value = float(num_str)
    except ValueError:
        # 如果解析失败，返回 0
        value = 0.0
    
    # ZX81 浮点数格式：6 字节
    # 字节 0: 0x7E (浮点数标记)
    # 字节 1-5: 指数和尾数

    
    # 使用 IEEE 754 双精度作为中间表示
    # 然后转换为 ZX81 格式（简化版本）
    if value < 0:
        sign = 0x80
        value = -value
    else:
        sign = 0x00
    
    # 计算指数（以 2 为底）
    if value > 0:
        exponent = math.floor(math.log2(value))
        mantissa = value / (2 ** exponent)
    else:
        exponent = 0
        mantissa = 0.0
    
    # ZX81 指数偏移为 128
    exponent_byte = (exponent + 128) & 0xFF
    
    # 尾数转换为 4 字节（简化）
    mantissa_bytes = bytearray(struct.pack('>f', mantissa))
    
    result = bytearray([0x7E])
    result.append(exponent_byte | sign)
    result.extend(mantissa_bytes[0:4])
    
    return result


def encode_basic_statement(code_str: str) -> bytearray:
    """编码单条 BASIC 语句文本"""
    stmt_bytes = bytearray()
    in_quotes = False
    i = 0

    while i < len(code_str):
        ch = code_str[i]

        if ch == ' ' and not in_quotes:
            i += 1
            continue

        if ch == '"':
            in_quotes = not in_quotes
            stmt_bytes.append(0x0B)
            i += 1
            continue

        if in_quotes:
            stmt_bytes.append(encode_char(ch))
            i += 1
        else:
            # First, try to match tokens (keywords)
            matched = False
            for token_str in sorted(BASIC_TOKENS.keys(), key=len, reverse=True):
                if code_str[i:].upper().startswith(token_str):
                    next_idx = i + len(token_str)
                    if token_str.isalpha():
                        if next_idx < len(code_str) and code_str[next_idx].isalnum():
                            continue

                    stmt_bytes.append(BASIC_TOKENS[token_str])
                    i += len(token_str)
                    matched = True
                    break

            if not matched:
                # If no token matched, check for number
                if ch.isdigit() or (ch == '.' and i + 1 < len(code_str) and code_str[i + 1].isdigit()):
                    # Parse number
                    num_str = ''
                    while i < len(code_str) and (code_str[i].isdigit() or code_str[i] == '.'):
                        num_str += code_str[i]
                        i += 1
                    
                    # For all numbers, output character form first, then floating point
                    for digit in num_str:
                        stmt_bytes.append(encode_char(digit))
                    stmt_bytes.extend(encode_number(num_str))
                    continue
                else:
                    # Encode as regular character
                    stmt_bytes.append(encode_char(ch))
                    i += 1

    stmt_bytes.append(0x76)  # 行尾换行符
    return stmt_bytes


def encode_basic_text_to_cac3_bin(basic_text: str, save_filename: str = "") -> bytes:
    """构造完整的 CAC-3 二进制 BIN 镜像"""
    # 1. 文件名头
    header_bytes = bytearray()
    clean_name = save_filename.upper().strip() if save_filename else "UNNAMED"

    for idx, ch in enumerate(clean_name):
        code = encode_char(ch)
        if idx == len(clean_name) - 1:
            code |= 0x80  # 最后一个字符最高位置 1
        header_bytes.append(code)

    # header_bytes.append(0xFF)

    # 2. 构造 BASIC 程序段
    lines = basic_text.strip().splitlines()
    body_bytes = bytearray()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split(maxsplit=1)
        if not parts[0].isdigit():
            continue

        line_num = int(parts[0])
        code_str = parts[1] if len(parts) > 1 else ""

        stmt_bytes = encode_basic_statement(code_str)

        line_num_bytes = line_num.to_bytes(2, byteorder='big')
        line_len_bytes = len(stmt_bytes).to_bytes(2, byteorder='little')

        body_bytes.extend(line_num_bytes)
        body_bytes.extend(line_len_bytes)
        body_bytes.extend(stmt_bytes)

    body_bytes.append(0xFF)  # 程序结尾符
    body_bytes.append(0x80)

    # 3. 系统变量区 (116 字节)

    sys_vars = bytearray(116)
    struct_vars = CAC3SysVariables.from_buffer(sys_vars)

    # sys_vars[0x00] = 0xFF  # BASIC FILE FLAG
    # sys_vars[0x01:0x03] = (0x407D).to_bytes(2, byteorder='little')  # D_FILE
    # sys_vars[0x03:0x05] = (0x4396).to_bytes(2, byteorder='little')  # PROG
    # sys_vars[0x05:0x07] = (0x407E).to_bytes(2, byteorder='little')  # DF_CC
    #
    # vars_addr = 0x4396 + len(body_bytes)
    # sys_vars[0x06:0x08] = vars_addr.to_bytes(2, byteorder='little')  # VARS
    #
    # sys_vars[0x52] = 0x76
    # sys_vars[0x73] = 0x76

    struct_vars.VERSN = 0xFF
    struct_vars.NXTLIN = 0x407D
    struct_vars.PROGRAM = 0x4396
    struct_vars.NXTLIN1 = 0x407E
    struct_vars.VARS = 0x4396 + len(body_bytes) -1 # vars_addr.to_bytes(2, byteorder='little')
    struct_vars.DEST = 0x0000
    struct_vars.E_LINE = struct_vars.VARS + 1

    struct_vars.PRBUFF.raw = b'\x00' * 32 + b'\x76'
    struct_vars.MEMBOT.raw =  b'\x00' * 30
    struct_vars.BLINK = 0x0000

    # 4. 视频缓冲区 (793 字节)
    vbuf_bytes = bytearray()
    vbuf_bytes.append(0x76)
    for _ in range(24):
        vbuf_bytes.extend(b'\x00' * 32)
        vbuf_bytes.append(0x76)

    return bytes(header_bytes + sys_vars + vbuf_bytes + body_bytes)

# ==========================================
# 2. WAV 音频生成模块
# ==========================================
def generate_audio_from_bytes(data: bytes, sample_rate: int = 44100, carrier_freq: float = 1200.0, amplitude: float = 0.8) -> np.ndarray:
    """根据 CAC-3 磁带协议生成音频信号"""
    audio = []

    # 引导头（Leader Tone），便于磁带机同步锁相，大约输出 2 秒高频载波脉冲
    leader_pulse_count = 3000
    p_high_samples = int(150e-6 * sample_rate)
    p_low_samples = int(150e-6 * sample_rate)

    t_high = np.arange(p_high_samples) / sample_rate
    high_burst = amplitude * np.sin(2 * np.pi * carrier_freq * t_high)
    low_burst = np.zeros(p_low_samples, dtype=np.float32)

    for _ in range(leader_pulse_count):
        audio.extend(high_burst)
        audio.extend(low_burst)

    # 1300 μs 间隔样本数
    silence_samples = int(1300e-6 * sample_rate)
    silence_gap = np.zeros(silence_samples, dtype=np.float32)

    # 数据位编码
    for byte in data:
        for bit_idx in range(8):
            bit = (byte >> (7 - bit_idx)) & 1
            num_pulses = 4 if bit == 0 else 9

            for _ in range(num_pulses):
                audio.extend(high_burst)
                audio.extend(low_burst)

            audio.extend(silence_gap)

    # 尾部静音缓冲 (0.5s)
    audio.extend(np.zeros(int(0.5 * sample_rate), dtype=np.float32))

    return np.array(audio, dtype=np.float32)


def basic_to_wav(basic_code: str, output_wav_file: str, save_filename: str = "TEST", sample_rate: int = 44100, carrier_freq: float = 1200.0):
    """主转换流程：BASIC 文本 -> 二进制数据 -> WAV 文件"""
    binary_data = encode_basic_text_to_cac3_bin(basic_code, save_filename=save_filename)

    if not binary_data:
        raise ValueError("BASIC 转换得到的二进制数据为空")

    audio = generate_audio_from_bytes(binary_data, sample_rate=sample_rate, carrier_freq=carrier_freq)

    # 量化至 16-bit PCM 范围
    audio_int16 = (audio * 32767).astype(np.int16)

    # 保存为 WAV 文件
    wavfile.write(output_wav_file, sample_rate, audio_int16)

    duration = len(audio) / sample_rate
    return len(binary_data), duration


# ==========================================
# 测试运行
# ==========================================
if __name__ == "__main__":
    sample_code = (
        '10 REM CAC-3 AUDIO GENERATOR\n'
        '20 CLS\n'
        '30 PRINT "HELLO FROM TAPE!"\n'
        '40 STOP'
    )

    bin_len, wav_dur = basic_to_wav(
        basic_code=sample_code,
        output_wav_file="output.wav",
        save_filename="HELLO",
        sample_rate=44100,
        carrier_freq=1200.0
    )

    print(f"转换成功！")
    print(f"二进制数据大小: {bin_len} 字节")
    print(f"生成 WAV 时长: {wav_dur:.2f} 秒")