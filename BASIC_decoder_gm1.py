import os
import tkinter as tk
from tkinter import filedialog, ttk

# ✅ Lambda 8300 官方权威字符映射表 (0x00 - 0x7F)
LAMBDA8300_CHAR_MAP = {0x00: " ", 0x01: "▘", 0x02: "▝", 0x03: "▀", 0x04: "▖", 0x05: "▌", 0x06: "▞", 0x07: "▛",
    0x09: "◤", 0x0A: "◥", 0x0B: '"', 0x0D: "$", 0x10: "(", 0x11: ")", 0x12: ">", 0x13: "<", 0x14: "=", 0x15: "+",
    0x16: "-", 0x17: "*", 0x18: "/", 0x19: ";", 0x1A: ",", 0x1B: ".", 0x1C: "0", 0x1D: "1", 0x1E: "2", 0x1F: "3",
    0x20: "4", 0x21: "5", 0x22: "6", 0x23: "7", 0x24: "8", 0x25: "9", 0x26: "A", 0x27: "B", 0x28: "C", 0x29: "D",
    0x2A: "E", 0x2B: "F", 0x2C: "G", 0x2D: "H", 0x2E: "I", 0x2F: "J", 0x30: "K", 0x31: "L", 0x32: "M", 0x33: "N",
    0x34: "O", 0x35: "P", 0x36: "Q", 0x37: "R", 0x38: "S", 0x39: "T", 0x3A: "U", 0x3B: "V", 0x3C: "W", 0x3D: "X",
    0x3E: "Y", 0x3F: "Z", 0x40: "THEN", 0x41: "TO", 0x42: "STEP", 0x43: "RND", 0x44: "INKEY$", 0x45: "PI", }

# ✅ Lambda 8300 官方高位关键字 Token 映射表 (0xC0 - 0xFF)
LAMBDA8300_TOKENS = {0xC0: "CODE", 0xC1: "VAL", 0xC2: "LEN", 0xC3: "SIN", 0xC4: "COS", 0xC5: "TAN", 0xC6: "ASN",
    0xC7: "ACS", 0xC8: "ATN", 0xC9: "LOG", 0xCA: "EXP", 0xCB: "INT", 0xCC: "SQR", 0xCD: "SGN", 0xCE: "ABS",
    0xCF: "PEEK", 0xD0: "USR", 0xD1: "STR$", 0xD2: "CHR$", 0xD3: "NOT", 0xD4: "AT", 0xD5: "TAB", 0xD6: "**", 0xD7: "OR",
    0xD8: "AND", 0xD9: "<=", 0xDA: ">=", 0xDB: "<>", 0xDC: "TEMPO", 0xDD: "MUSIC", 0xDE: "SOUND", 0xDF: "BEEP",
    0xE0: "NOBEEP", 0xE1: "LPRINT", 0xE2: "LLIST", 0xE3: "STOP", 0xE4: "SLOW", 0xE5: "FAST", 0xE6: "NEW",
    0xE7: "SCROLL", 0xE8: "CONT", 0xE9: "DIM", 0xEA: "REM", 0xEB: "FOR", 0xEC: "GOTO", 0xED: "GOSUB", 0xEE: "INPUT",
    0xEF: "LOAD", 0xF0: "LIST", 0xF1: "LET", 0xF2: "PAUSE", 0xF3: "NEXT", 0xF4: "POKE", 0xF5: "PRINT", 0xF6: "PLOT",
    0xF7: "RUN", 0xF8: "SAVE", 0xF9: "RAND", 0xFA: "IF", 0xFB: "CLS", 0xFC: "UNPLOT", 0xFD: "CLEAR", 0xFE: "RETURN",
    0xFF: "COPY"}


def decode_lambda_byte(byte_val):
    is_inverse = bool(byte_val & 0x80)
    code = byte_val & 0x7F
    if code in LAMBDA8300_CHAR_MAP:
        return LAMBDA8300_CHAR_MAP[code], is_inverse
    elif 32 <= code <= 126:
        return chr(code), is_inverse
    return " ", is_inverse


def parse_basic_program(data, start_idx):
    basic_lines = []
    curr = start_idx

    while curr + 4 <= len(data):
        line_num = (data[curr] << 8) | data[curr + 1]
        if line_num == 0 or line_num > 9999:
            break

        line_len = data[curr + 2] | (data[curr + 3] << 8)
        if line_len <= 0 or curr + 4 + line_len > len(data):
            break

        line_bytes = data[curr + 4: curr + 4 + line_len]
        curr += 4 + line_len

        tokens = []
        i = 0
        while i < len(line_bytes):
            b = line_bytes[i]
            if b == 0x76:
                break
            elif b == 0x7E:
                i += 6
                continue
            elif b in LAMBDA8300_TOKENS:
                tokens.append(f" {LAMBDA8300_TOKENS[b]} ")
            elif b in LAMBDA8300_CHAR_MAP:
                val = LAMBDA8300_CHAR_MAP[b]
                if len(val) > 1 and val.isupper():
                    tokens.append(f" {val} ")
                else:
                    tokens.append(val)
            else:
                ch, _ = decode_lambda_byte(b)
                tokens.append(ch)
            i += 1

        raw_code = "".join(tokens)
        formatted_chars = []
        for j, char in enumerate(raw_code):
            if j > 0:
                prev = raw_code[j - 1]
                if (prev.isdigit() and char.isalpha()) or (prev.isalpha() and char.isdigit()):
                    formatted_chars.append(" ")
            formatted_chars.append(char)

        clean_code = "".join(formatted_chars)
        clean_code = " ".join(clean_code.split())
        basic_lines.append(f"{line_num} {clean_code}")

    return basic_lines


def process_cac3_bin(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        if not data:
            return "错误：文件为空", "", None, []

        fn_end_idx = -1
        filename_chars = []
        for idx, byte in enumerate(data):
            ch, _ = decode_lambda_byte(byte)
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

        if ff_idx == -1:
            return parsed_name, "未找到 0xFF 校验点", None, []

        vbuf_start_idx = ff_idx + 1 + 116
        sys_info = f"0xFF位置: 0x{ff_idx:04X} | 视频缓冲起点: 0x{vbuf_start_idx:04X}"

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
                    ch, is_inv = decode_lambda_byte(b)
                    current_line.append((ch, is_inv))
            curr += 1

        while len(screen_matrix) < 24:
            screen_matrix.append([(" ", False)] * 32)

        basic_start_idx = curr
        basic_code_lines = parse_basic_program(data, basic_start_idx)

        return parsed_name, sys_info, screen_matrix, basic_code_lines

    except Exception as e:
        return f"解析错误: {str(e)}", "", None, []


class Lambda8300App:
    def __init__(self, root):
        self.root = root
        self.root.title("Lambda 8300 BIN 智能解码工具")
        self.root.geometry("680x600")
        self.root.minsize(550, 450)

        # ✅ 核心修正 1：允许窗口自由缩放改变大小
        self.root.resizable(True, True)

        self.crt_win = None
        self.crt_canvas = None
        self.screen_matrix = None

        # 全局 Frame 布局支持随窗口自适应扩展
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # 1. 顶栏文件选择容器
        file_frame = ttk.Frame(main_frame)
        file_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        file_frame.columnconfigure(1, weight=1)  # 允许路径输入框水平拉伸

        ttk.Label(file_frame, text="选择 BIN 文件: ").grid(row=0, column=0, sticky=tk.W)
        self.file_path_var = tk.StringVar()
        self.entry_path = ttk.Entry(file_frame, textvariable=self.file_path_var)
        self.entry_path.grid(row=0, column=1, sticky=tk.EW, padx=5)

        # ✅ 核心修正 2：修复“载入 BIN 文件”按钮显示不全的问题
        self.btn_browse = ttk.Button(file_frame, text="载入 BIN 文件", command=self.load_and_decode)
        self.btn_browse.grid(row=0, column=2, sticky=tk.E)

        # 2. 磁带头与系统状态容器
        info_group = ttk.LabelFrame(main_frame, text=" 磁带头与系统状态 ", padding="8")
        info_group.grid(row=1, column=0, sticky=tk.EW, pady=5)
        info_group.columnconfigure(1, weight=1)

        ttk.Label(info_group, text="SAVE 文件名:").grid(row=0, column=0, sticky=tk.W)
        self.lbl_filename = ttk.Label(info_group, text="---", font=("Consolas", 11, "bold"), foreground="#1E90FF")
        self.lbl_filename.grid(row=0, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_group, text="偏移地址:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.lbl_sys_info = ttk.Label(info_group, text="---", font=("Consolas", 9), foreground="#2E8B57")
        self.lbl_sys_info.grid(row=1, column=1, sticky=tk.W, padx=10)

        self.btn_show_crt = ttk.Button(info_group, text="📺 显示 CRT 视频缓冲区", state=tk.DISABLED,
                                       command=self.show_crt_window)
        self.btn_show_crt.grid(row=0, column=2, rowspan=2, sticky=tk.E, padx=5)

        # 3. BASIC 代码展示区 (填满剩余全部空间)
        code_group = ttk.LabelFrame(main_frame, text=" 📜 解码出来的 BASIC 源码 ", padding="8")
        code_group.grid(row=3, column=0, sticky=tk.NSEW, pady=5)
        code_group.rowconfigure(0, weight=1)
        code_group.columnconfigure(0, weight=1)

        code_scroll = ttk.Scrollbar(code_group)
        code_scroll.grid(row=0, column=1, sticky=tk.NS)

        self.txt_basic_code = tk.Text(code_group, font=("Consolas", 12, "bold"), bg="#181818", fg="#00FF66",
                                      yscrollcommand=code_scroll.set, wrap=tk.WORD)
        self.txt_basic_code.grid(row=0, column=0, sticky=tk.NSEW)
        code_scroll.config(command=self.txt_basic_code.yview)

    def load_and_decode(self):
        fn = filedialog.askopenfilename(title="选择 Lambda 8300 BIN 文件",
                                        filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")])
        if not fn: return
        self.file_path_var.set(fn)

        parsed_name, sys_info, screen_matrix, basic_code_lines = process_cac3_bin(fn)

        self.lbl_filename.config(text=f'"{parsed_name}"')
        self.lbl_sys_info.config(text=sys_info if sys_info else "解析失败")

        self.txt_basic_code.config(state=tk.NORMAL)
        self.txt_basic_code.delete("1.0", tk.END)
        if basic_code_lines:
            for line in basic_code_lines:
                self.txt_basic_code.insert(tk.END, line + "\n")
        else:
            self.txt_basic_code.insert(tk.END, "--- 未找到 valid BASIC 语句 ---")
        self.txt_basic_code.config(state=tk.DISABLED)

        self.screen_matrix = screen_matrix
        if screen_matrix:
            self.btn_show_crt.config(state=tk.NORMAL)
            if self.crt_win is not None and tk.Toplevel.winfo_exists(self.crt_win):
                self.draw_crt_display()

    def show_crt_window(self):
        if not self.screen_matrix: return

        if self.crt_win is not None and tk.Toplevel.winfo_exists(self.crt_win):
            self.draw_crt_display()
            self.crt_win.lift()
        else:
            self.crt_win = tk.Toplevel(self.root)
            self.crt_win.title("Lambda 8300 CRT Display (32 x 24)")
            self.crt_win.geometry("540x440")
            self.crt_win.configure(bg="#0D0D0D")
            self.crt_win.resizable(False, False)

            tk.Label(self.crt_win, text="--- LAMBDA 8300 CRT DISPLAY BUFFER ---", font=("Consolas", 10, "bold"),
                     bg="#0D0D0D", fg="#00FF66").pack(pady=6)

            self.crt_canvas = tk.Canvas(self.crt_win, width=32 * 16, height=24 * 16, bg="#000000", highlightthickness=0)
            self.crt_canvas.pack(padx=10, pady=5)

            self.draw_crt_display()

    def draw_crt_display(self):
        if not self.crt_canvas or not self.screen_matrix: return
        self.crt_canvas.delete("all")

        for r, line in enumerate(self.screen_matrix):
            for c, (ch, is_inv) in enumerate(line):
                bg_color = "#00FF66" if is_inv else "#000000"
                fg_color = "#000000" if is_inv else "#00FF66"
                self.crt_canvas.create_rectangle(c * 16, r * 16, (c + 1) * 16, (r + 1) * 16, fill=bg_color,
                                                 outline=bg_color)
                if ch.strip():
                    self.crt_canvas.create_text(c * 16 + 8, r * 16 + 8, text=ch, fill=fg_color,
                                                font=("Consolas", 11, "bold"))


if __name__ == "__main__":
    root = tk.Tk()
    app = Lambda8300App(root)
    root.mainloop()