import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from hex_viewer import format_hex_and_char_bytes
from basic_decoder import process_cac3_p
from z80_disasm import disassemble_z80_bytes


class PViewerFrame(ttk.Frame):
    """P 文件浏览器 - 左右分屏显示二进制内容和解码内容"""

    def __init__(self, parent, root_app):
        super().__init__(parent, padding="5")
        self.root_app = root_app

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # 顶部控制区
        top_frame = ttk.Frame(self)
        top_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 0))
        top_frame.columnconfigure(1, weight=1)

        ttk.Label(top_frame, text="选择 P 文件: ").grid(
            row=0, column=0, sticky=tk.W
        )
        self.file_path_var = tk.StringVar()
        self.entry_path = ttk.Entry(top_frame, textvariable=self.file_path_var)
        self.entry_path.grid(row=0, column=1, sticky=tk.EW, padx=5)

        self.btn_browse = ttk.Button(
            top_frame, text="浏览...", command=self.load_file
        )
        self.btn_browse.grid(row=0, column=2, sticky=tk.E)

        # 分屏显示区
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.grid(row=1, column=0, sticky=tk.NSEW, pady=0)

        # 左侧：二进制内容
        left_frame = ttk.LabelFrame(
            paned_window, text=" 二进制内容 (十六进制与字符) ", padding="2"
        )
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)

        v_scroll_left = ttk.Scrollbar(left_frame)
        v_scroll_left.grid(row=0, column=1, sticky=tk.NS)

        self.txt_hex_display = tk.Text(
            left_frame,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg="#1E1E1E",
            fg="#FFD700",
            yscrollcommand=v_scroll_left.set,
        )
        self.txt_hex_display.grid(row=0, column=0, sticky=tk.NSEW)
        v_scroll_left.config(command=self.txt_hex_display.yview)

        paned_window.add(left_frame, weight=1)

        # 右侧：解码内容
        right_frame = ttk.LabelFrame(
            paned_window, text=" 解码内容 ", padding="2"
        )
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)

        v_scroll_right = ttk.Scrollbar(right_frame)
        v_scroll_right.grid(row=0, column=1, sticky=tk.NS)

        self.txt_decoded_display = tk.Text(
            right_frame,
            wrap=tk.WORD,
            font=("Consolas", 10, "bold"),
            bg="#121212",
            fg="#00E5FF",
            yscrollcommand=v_scroll_right.set,
        )
        self.txt_decoded_display.grid(row=0, column=0, sticky=tk.NSEW)
        v_scroll_right.config(command=self.txt_decoded_display.yview)

        paned_window.add(right_frame, weight=1)

        # 底部信息区
        info_frame = ttk.Frame(self)
        info_frame.grid(row=2, column=0, sticky=tk.EW, pady=(0, 0))

        self.lbl_info = ttk.Label(
            info_frame, text="准备就绪。请选择 .p 文件进行查看。"
        )
        self.lbl_info.pack(side=tk.LEFT, padx=5)

        self.lbl_file_type = ttk.Label(info_frame, text="")
        self.lbl_file_type.pack(side=tk.LEFT, padx=5)

    def detect_file_type(self, data):
        """根据文件头检测文件类型"""
        if len(data) < 9:
            return "unknown", "未知文件类型"
        
        # 检查是否为 BASIC 文件 (basicToP)
        # BASIC 文件通常以文件名头开始，后面跟着系统变量
        # 文件名格式：每个字符的最高位为0，最后一个字符最高位为1
        # 系统变量区域通常有特定的结构
        
        # 检查是否为 Z80 机器码文件 (wToVP)
        # wToVP 文件通常包含 ROM 头部特征: ED 54 6F D6 50
        if data[:5] == bytes.fromhex("ED546FD650"):
            return "z80", "Z80 机器码 (wToVP)"
        
        # 检查 BASIC 文件特征
        # BASIC 文件通常以可打印字符开始（文件名）
        # 尝试解析文件名头
        filename_chars = []
        for i in range(min(10, len(data))):
            byte = data[i]
            if byte & 0x80:
                # 最后一个字符
                filename_chars.append(chr(byte & 0x7F))
                break
            else:
                filename_chars.append(chr(byte))
        
        if filename_chars and all(32 <= ord(c) <= 126 for c in filename_chars):
            return "basic", "BASIC 程序 (basicToP)"
        
        return "unknown", "未知文件类型"

    def load_file(self):
        fn = filedialog.askopenfilename(
            title="选择 P 文件",
            filetypes=[("P Files", "*.p"), ("All Files", "*.*")],
        )
        if not fn:
            return
        self.file_path_var.set(fn)

        try:
            with open(fn, "rb") as f:
                data = f.read()

            # 显示二进制内容
            formatted_dump = format_hex_and_char_bytes(data, base_address=0)
            self.txt_hex_display.config(state=tk.NORMAL)
            self.txt_hex_display.delete("1.0", tk.END)
            self.txt_hex_display.insert(tk.END, formatted_dump if formatted_dump else "--- 文件内容为空 ---")
            self.txt_hex_display.config(state=tk.DISABLED)

            # 检测文件类型并解码
            file_type, type_name = self.detect_file_type(data)
            self.lbl_file_type.config(text=f"文件类型: {type_name}")

            decoded_text = ""
            if file_type == "basic":
                # BASIC 解码
                try:
                    parsed_name, sys_info, sys_bytes_dump, screen_matrix, basic_code_lines = \
                        process_cac3_p(fn, format_hex_and_char_bytes)
                    
                    decoded_text = f"=== BASIC 程序解码结果 ===\n\n"
                    decoded_text += f"文件名: {parsed_name}\n"
                    decoded_text += f"系统信息: {sys_info}\n\n"
                    decoded_text += f"=== BASIC 源码 ===\n"
                    decoded_text += "\n".join(basic_code_lines)
                except Exception as e:
                    decoded_text = f"BASIC 解码失败: {str(e)}"
            
            elif file_type == "z80":
                # Z80 反汇编
                try:
                    # 跳过 ROM 头部，从实际代码开始
                    # ROM 头部格式: ED 54 6F D6 50 + 2字节地址 + 2字节长度
                    if len(data) >= 9:
                        start_addr = int.from_bytes(data[5:7], byteorder='big')
                        data_len = int.from_bytes(data[7:9], byteorder='big')
                        code_data = data[9:9+data_len]
                        decoded_text = disassemble_z80_bytes(code_data, base_addr=start_addr)
                    else:
                        decoded_text = disassemble_z80_bytes(data, base_addr=0x0000)
                except Exception as e:
                    decoded_text = f"Z80 反汇编失败: {str(e)}"
            
            else:
                decoded_text = "无法识别的文件类型，无法解码。"

            # 显示解码内容
            self.txt_decoded_display.config(state=tk.NORMAL)
            self.txt_decoded_display.delete("1.0", tk.END)
            self.txt_decoded_display.insert(tk.END, decoded_text)
            self.txt_decoded_display.config(state=tk.DISABLED)

            self.lbl_info.config(
                text=f"文件: {fn} | 大小: {len(data)} 字节"
            )

        except Exception as e:
            messagebox.showerror("读取错误", f"无法读取或处理文件:\n{str(e)}")
            self.lbl_info.config(text="读取失败。")
