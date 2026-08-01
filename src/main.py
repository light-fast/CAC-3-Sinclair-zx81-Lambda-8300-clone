import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 导入底层解码与编码模块
from audio_decoder import AudioDecoderFrame
from basic_decoder import process_cac3_bin
from basic_encoder import basic_to_wav, encode_basic_text_to_cac3_bin
from hex_viewer import format_hex_and_char_bytes
from signal_analyzer import SignalAnalyzerFrame
from z80_disasm import disassemble_z80_bytes


# ==========================================
# 1. BASIC 解码工作区 UI (BIN -> BASIC)
# ==========================================
class BasicDecoderFrame(ttk.Frame):

    def __init__(self, parent, root_app):
        super().__init__(parent, padding="10")
        self.root_app = root_app

        self.crt_win = None
        self.crt_canvas = None
        self.screen_matrix = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        file_frame = ttk.Frame(self)
        file_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="选择 BIN 文件: ").grid(
            row=0, column=0, sticky=tk.W
        )
        self.file_path_var = tk.StringVar()
        self.entry_path = ttk.Entry(file_frame, textvariable=self.file_path_var)
        self.entry_path.grid(row=0, column=1, sticky=tk.EW, padx=5)

        self.btn_browse = ttk.Button(
            file_frame, text="载入 BIN 文件", command=self.load_and_decode
        )
        self.btn_browse.grid(row=0, column=2, sticky=tk.E)

        info_group = ttk.LabelFrame(
            self, text=" 磁带头与系统状态 ", padding="8"
        )
        info_group.grid(row=1, column=0, sticky=tk.EW, pady=5)
        info_group.columnconfigure(1, weight=1)

        ttk.Label(info_group, text="SAVE 文件名:").grid(
            row=0, column=0, sticky=tk.W
        )
        self.lbl_filename = ttk.Label(
            info_group,
            text="---",
            font=("Consolas", 11, "bold"),
            foreground="#1E90FF",
        )
        self.lbl_filename.grid(row=0, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_group, text="偏移地址:").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        self.lbl_sys_info = ttk.Label(
            info_group,
            text="---",
            font=("Consolas", 9),
            foreground="#2E8B57",
        )
        self.lbl_sys_info.grid(row=1, column=1, sticky=tk.W, padx=10)

        self.btn_show_crt = ttk.Button(
            info_group,
            text="📺 显示 CRT 视频缓冲区",
            state=tk.DISABLED,
            command=self.show_crt_window,
        )
        self.btn_show_crt.grid(row=0, column=2, rowspan=2, sticky=tk.E, padx=5)

        paned_window = tk.PanedWindow(
            self,
            orient=tk.VERTICAL,
            sashrelief=tk.RAISED,
            sashwidth=6,
            bg="#D0D0D0",
        )
        paned_window.grid(row=2, column=0, sticky=tk.NSEW, pady=5)

        sys_group = ttk.LabelFrame(
            paned_window, text=" 116 字节系统变量 (HEX 与 CAC-3 字符对照) "
        )

        txt_container = ttk.Frame(sys_group)
        txt_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        sys_scroll = ttk.Scrollbar(txt_container)
        sys_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        sys_xscroll = ttk.Scrollbar(txt_container, orient=tk.HORIZONTAL)
        sys_xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.txt_sys_bytes = tk.Text(
            txt_container,
            font=("Consolas", 10),
            bg="#1E1E1E",
            fg="#FFD700",
            height=8,
            yscrollcommand=sys_scroll.set,
            xscrollcommand=sys_xscroll.set,
            wrap=tk.NONE,
        )
        self.txt_sys_bytes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sys_scroll.config(command=self.txt_sys_bytes.yview)
        sys_xscroll.config(command=self.txt_sys_bytes.xview)

        paned_window.add(sys_group, height=180, minsize=80)

        code_group = ttk.LabelFrame(
            paned_window, text=" 📜 解码出来的 BASIC 源码 ", padding="8"
        )
        code_group.rowconfigure(0, weight=1)
        code_group.columnconfigure(0, weight=1)

        code_scroll = ttk.Scrollbar(code_group)
        code_scroll.grid(row=0, column=1, sticky=tk.NS)

        self.txt_basic_code = tk.Text(
            code_group,
            font=("Consolas", 11, "bold"),
            bg="#181818",
            fg="#00FF66",
            yscrollcommand=code_scroll.set,
            wrap=tk.WORD,
        )
        self.txt_basic_code.grid(row=0, column=0, sticky=tk.NSEW)
        code_scroll.config(command=self.txt_basic_code.yview)

        paned_window.add(code_group, minsize=120)

    def load_and_decode(self):
        fn = filedialog.askopenfilename(
            title="选择 CAC-3 BIN 文件",
            filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")],
        )
        if not fn:
            return
        self.file_path_var.set(fn)

        (
            parsed_name,
            sys_info,
            sys_bytes_dump,
            screen_matrix,
            basic_code_lines,
        ) = process_cac3_bin(fn, format_hex_and_char_bytes)

        self.lbl_filename.config(text=f'"{parsed_name}"')
        self.lbl_sys_info.config(text=sys_info if sys_info else "解析失败")

        self.txt_sys_bytes.config(state=tk.NORMAL)
        self.txt_sys_bytes.delete("1.0", tk.END)
        self.txt_sys_bytes.insert(
            tk.END,
            sys_bytes_dump if sys_bytes_dump else "--- 无系统变量数据 ---",
        )
        self.txt_sys_bytes.config(state=tk.DISABLED)

        self.txt_basic_code.config(state=tk.NORMAL)
        self.txt_basic_code.delete("1.0", tk.END)
        if basic_code_lines:
            for line in basic_code_lines:
                self.txt_basic_code.insert(tk.END, line + "\n")
        else:
            self.txt_basic_code.insert(
                tk.END, "--- 未找到 valid BASIC 语句 ---"
            )
        self.txt_basic_code.config(state=tk.DISABLED)

        self.screen_matrix = screen_matrix
        if screen_matrix:
            self.btn_show_crt.config(state=tk.NORMAL)
            if self.crt_win is not None and tk.Toplevel.winfo_exists(
                self.crt_win
            ):
                self.draw_crt_display()

    def show_crt_window(self):
        if not self.screen_matrix:
            return

        if self.crt_win is not None and tk.Toplevel.winfo_exists(self.crt_win):
            self.draw_crt_display()
            self.crt_win.lift()
        else:
            self.crt_win = tk.Toplevel(self)
            self.crt_win.title("CAC-3 CRT Display (32 x 24)")
            self.crt_win.geometry("540x440")
            self.crt_win.configure(bg="#0D0D0D")
            self.crt_win.resizable(False, False)

            tk.Label(
                self.crt_win,
                text="--- CAC-3 CRT DISPLAY BUFFER ---",
                font=("Consolas", 10, "bold"),
                bg="#0D0D0D",
                fg="#00FF66",
            ).pack(pady=6)

            self.crt_canvas = tk.Canvas(
                self.crt_win,
                width=32 * 16,
                height=24 * 16,
                bg="#000000",
                highlightthickness=0,
            )
            self.crt_canvas.pack(padx=10, pady=5)

            self.draw_crt_display()

    def draw_crt_display(self):
        if not self.crt_canvas or not self.screen_matrix:
            return
        self.crt_canvas.delete("all")

        for r, line in enumerate(self.screen_matrix):
            for c, (ch, is_inv) in enumerate(line):
                bg_color = "#00FF66" if is_inv else "#000000"
                fg_color = "#000000" if is_inv else "#00FF66"
                self.crt_canvas.create_rectangle(
                    c * 16,
                    r * 16,
                    (c + 1) * 16,
                    (r + 1) * 16,
                    fill=bg_color,
                    outline=bg_color,
                )
                if ch.strip():
                    self.crt_canvas.create_text(
                        c * 16 + 8,
                        r * 16 + 8,
                        text=ch,
                        fill=fg_color,
                        font=("Consolas", 11, "bold"),
                    )


# ==========================================
# 2. 独立模块：BASIC 源码 转 BIN 文件 (BASIC -> BIN)
# ==========================================
class BasicToBinFrame(ttk.Frame):

    def __init__(self, parent, root_app):
        super().__init__(parent, padding="10")
        self.root_app = root_app

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        cfg_frame = ttk.LabelFrame(self, text=" BIN 导出参数 ", padding="8")
        cfg_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))

        ttk.Label(cfg_frame, text="SAVE 文件名:").pack(
            side=tk.LEFT, padx=5
        )
        self.var_save_name = tk.StringVar(value="TEST")
        self.entry_save_name = ttk.Entry(
            cfg_frame, textvariable=self.var_save_name, width=12
        )
        self.entry_save_name.pack(side=tk.LEFT, padx=5)

        self.btn_convert = ttk.Button(
            cfg_frame,
            text="⚡ 生成并导出 BIN 文件",
            command=self.convert_to_bin,
        )
        self.btn_convert.pack(side=tk.RIGHT, padx=5)

        editor_group = ttk.LabelFrame(
            self, text=" 📝 输入 BASIC 源码 ", padding="8"
        )
        editor_group.grid(row=1, column=0, sticky=tk.NSEW, pady=5)
        editor_group.rowconfigure(0, weight=1)
        editor_group.columnconfigure(0, weight=1)

        scroll = ttk.Scrollbar(editor_group)
        scroll.grid(row=0, column=1, sticky=tk.NS)

        self.txt_editor = tk.Text(
            editor_group,
            font=("Consolas", 11),
            bg="#1E1E1E",
            fg="#00E5FF",
            insertbackground="#FFFFFF",
            yscrollcommand=scroll.set,
            wrap=tk.NONE,
        )
        self.txt_editor.grid(row=0, column=0, sticky=tk.NSEW)
        scroll.config(command=self.txt_editor.yview)

        sample_code = (
            "10 REM CAC-3 / LAMBDA 8300 TEST\n"
            "20 CLS\n"
            '30 PRINT "********************************"\n'
            '40 PRINT "*  WELCOME TO CAC-3 / LAMBDA   *"\n'
            '50 PRINT "********************************"\n'
            "60 LET PX=2\n"
            "65 LET PY=2\n"
            '70 PRINT AT PY,PX; "*"\n'
            "80 STOP"
        )
        self.txt_editor.insert(tk.END, sample_code)

    def convert_to_bin(self):
        basic_text = self.txt_editor.get("1.0", tk.END).strip()
        if not basic_text:
            messagebox.showwarning("警告", "请输入 BASIC 代码！")
            return

        save_name = self.var_save_name.get().strip() or "TEST"

        try:
            fn_bin = filedialog.asksaveasfilename(
                title="保存 CAC-3 BIN 文件",
                initialfile=f"{save_name.lower()}.bin",
                filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")],
            )
            if not fn_bin:
                return

            bin_data = encode_basic_text_to_cac3_bin(
                basic_text, save_filename=save_name
            )
            with open(fn_bin, "wb") as f:
                f.write(bin_data)

            messagebox.showinfo(
                "导出成功",
                f"✓ BIN 文件生成完成！\n路径: {fn_bin}\n大小: {len(bin_data):,} 字节",
            )
        except Exception as e:
            messagebox.showerror("导出失败", f"错误详情:\n{str(e)}")


# ==========================================
# 3. 独立模块：BIN 文件 转 WAV 音频 (BIN -> WAV)
# ==========================================
class BinToWavFrame(ttk.Frame):

    def __init__(self, parent, root_app):
        super().__init__(parent, padding="10")
        self.root_app = root_app

        self.columnconfigure(0, weight=1)

        # 1. 选择 BIN 输入文件
        input_group = ttk.LabelFrame(self, text=" 输入 BIN 文件 ", padding="10")
        input_group.grid(row=0, column=0, sticky=tk.EW, pady=5)
        input_group.columnconfigure(1, weight=1)

        ttk.Label(input_group, text="选择 BIN 文件: ").grid(
            row=0, column=0, sticky=tk.W
        )
        self.var_bin_path = tk.StringVar()
        self.entry_bin_path = ttk.Entry(
            input_group, textvariable=self.var_bin_path
        )
        self.entry_bin_path.grid(row=0, column=1, sticky=tk.EW, padx=5)

        self.btn_browse_bin = ttk.Button(
            input_group, text="浏览...", command=self.browse_bin_file
        )
        self.btn_browse_bin.grid(row=0, column=2, sticky=tk.E)

        # 2. 采样率与参数设置
        param_group = ttk.LabelFrame(
            self, text=" WAV 音频调制参数 ", padding="10"
        )
        param_group.grid(row=1, column=0, sticky=tk.EW, pady=5)

        ttk.Label(param_group, text="采样率 (Sample Rate):").grid(
            row=0, column=0, sticky=tk.W, padx=5
        )
        self.var_sample_rate = tk.StringVar(value="44100")
        self.combo_sample_rate = ttk.Combobox(
            param_group,
            textvariable=self.var_sample_rate,
            values=["22050", "44100", "48000"],
            width=10,
        )
        self.combo_sample_rate.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(param_group, text="载波频率 (Hz):").grid(
            row=0, column=2, sticky=tk.W, padx=(20, 5)
        )
        self.var_carrier_freq = tk.StringVar(value="1200")
        self.entry_carrier_freq = ttk.Entry(
            param_group, textvariable=self.var_carrier_freq, width=8
        )
        self.entry_carrier_freq.grid(row=0, column=3, sticky=tk.W, padx=5)

        # 3. 转换动作按钮
        act_group = ttk.Frame(self, padding="10")
        act_group.grid(row=2, column=0, sticky=tk.EW, pady=10)

        self.btn_convert_wav = ttk.Button(
            act_group, text="🎵 开始转换并保存 WAV 音频", command=self.convert_bin_to_wav
        )
        self.btn_convert_wav.pack(fill=tk.X, ipady=5)

    def browse_bin_file(self):
        fn = filedialog.askopenfilename(
            title="选择 BIN 二进制文件",
            filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")],
        )
        if fn:
            self.var_bin_path.set(fn)

    def convert_bin_to_wav(self):
        bin_path = self.var_bin_path.get().strip()
        if not bin_path or not os.path.exists(bin_path):
            messagebox.showwarning("警告", "请选择有效的 BIN 文件！")
            return

        try:
            sr = int(self.var_sample_rate.get())
            cf = float(self.var_carrier_freq.get())
        except ValueError:
            messagebox.showerror("参数错误", "采样率和载波频率必须是有效的数字！")
            return

        # 建议 SaveAs 路径
        default_wav_name = os.path.splitext(os.path.basename(bin_path))[0] + ".wav"
        fn_wav = filedialog.asksaveasfilename(
            title="保存 CAC-3 WAV 音频文件",
            initialfile=default_wav_name,
            filetypes=[("WAV Audio Files", "*.wav"), ("All Files", "*.*")],
        )
        if not fn_wav:
            return

        try:
            # 读取 BIN 数据并调用 basic_encoder 里的声音合成方法
            with open(bin_path, "rb") as f:
                bin_data = f.read()

            from basic_encoder import generate_audio_from_bytes, wavfile

            audio = generate_audio_from_bytes(
                bin_data, sample_rate=sr, carrier_freq=cf
            )
            audio_int16 = (audio * 32767).astype("int16")
            wavfile.write(fn_wav, sr, audio_int16)

            duration = len(audio) / sr
            messagebox.showinfo(
                "转换成功",
                f"✓ WAV 磁带音频合成完成！\n路径: {fn_wav}\n时长: {duration:.2f} 秒\n采样率: {sr} Hz",
            )
        except Exception as e:
            messagebox.showerror("生成 WAV 失败", f"错误详情:\n{str(e)}")


# ==========================================
# 4. ROM/BIN 文件浏览器 UI
# ==========================================
class HexViewerFrame(ttk.Frame):

    def __init__(self, parent, root_app):
        super().__init__(parent, padding="10")
        self.root_app = root_app

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top_frame = ttk.Frame(self)
        top_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        top_frame.columnconfigure(1, weight=1)

        ttk.Label(top_frame, text="选择 ROM/BIN 文件: ").grid(
            row=0, column=0, sticky=tk.W
        )
        self.file_path_var = tk.StringVar()
        self.entry_path = ttk.Entry(top_frame, textvariable=self.file_path_var)
        self.entry_path.grid(row=0, column=1, sticky=tk.EW, padx=5)

        self.btn_browse = ttk.Button(
            top_frame, text="打开文件", command=self.load_rom_file
        )
        self.btn_browse.grid(row=0, column=2, sticky=tk.E)

        info_frame = ttk.LabelFrame(self, text=" 文件属性 ", padding="5")
        info_frame.grid(row=1, column=0, sticky=tk.EW, pady=5)
        info_frame.columnconfigure(3, weight=1)

        ttk.Label(info_frame, text="文件大小:").grid(
            row=0, column=0, sticky=tk.W, padx=5
        )
        self.lbl_file_size = ttk.Label(
            info_frame,
            text="0 字节",
            font=("Consolas", 10, "bold"),
            foreground="#1E90FF",
        )
        self.lbl_file_size.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(info_frame, text="总行数 (16B/行):").grid(
            row=0, column=2, sticky=tk.W, padx=(20, 5)
        )
        self.lbl_total_lines = ttk.Label(
            info_frame,
            text="0 行",
            font=("Consolas", 10, "bold"),
            foreground="#2E8B57",
        )
        self.lbl_total_lines.grid(row=0, column=3, sticky=tk.W, padx=5)

        viewer_group = ttk.LabelFrame(
            self, text=" ROM / BIN 数据内容 (HEX 与 CAC-3 字符对照) "
        )
        viewer_group.grid(row=2, column=0, sticky=tk.NSEW, pady=5)

        txt_container = ttk.Frame(viewer_group)
        txt_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        sys_scroll = ttk.Scrollbar(txt_container)
        sys_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        sys_xscroll = ttk.Scrollbar(txt_container, orient=tk.HORIZONTAL)
        sys_xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.txt_hex_display = tk.Text(
            txt_container,
            font=("Consolas", 10),
            bg="#1E1E1E",
            fg="#FFD700",
            yscrollcommand=sys_scroll.set,
            xscrollcommand=sys_xscroll.set,
            wrap=tk.NONE,
        )
        self.txt_hex_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sys_scroll.config(command=self.txt_hex_display.yview)
        sys_xscroll.config(command=self.txt_hex_display.xview)

    def load_rom_file(self):
        fn = filedialog.askopenfilename(
            title="选择 ROM/BIN 文件",
            filetypes=[
                ("ROM & BIN Files", "*.rom;*.bin"),
                ("All Files", "*.*"),
            ],
        )
        if not fn:
            return
        self.file_path_var.set(fn)

        try:
            with open(fn, "rb") as f:
                data = f.read()

            file_len = len(data)
            total_lines = (file_len + 15) // 16

            self.lbl_file_size.config(
                text=f"{file_len:,} 字节 (0x{file_len:04X})"
            )
            self.lbl_total_lines.config(text=f"{total_lines:,} 行")

            formatted_dump = format_hex_and_char_bytes(data, base_address=0)

            self.txt_hex_display.config(state=tk.NORMAL)
            self.txt_hex_display.delete("1.0", tk.END)
            self.txt_hex_display.insert(
                tk.END,
                formatted_dump if formatted_dump else "--- 文件内容为空 ---",
            )
            self.txt_hex_display.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("读取错误", f"无法读取文件:\n{str(e)}")


# ==========================================
# 5. ROM 反汇编器 UI
# ==========================================
class DisassemblerFrame(ttk.Frame):

    def __init__(self, parent, root_app):
        super().__init__(parent, padding="10")
        self.root_app = root_app

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top_frame = ttk.Frame(self)
        top_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        top_frame.columnconfigure(1, weight=1)

        ttk.Label(top_frame, text="选择 ROM/BIN 文件: ").grid(
            row=0, column=0, sticky=tk.W
        )
        self.file_path_var = tk.StringVar()
        self.entry_path = ttk.Entry(top_frame, textvariable=self.file_path_var)
        self.entry_path.grid(row=0, column=1, sticky=tk.EW, padx=5)

        self.btn_browse = ttk.Button(
            top_frame, text="反汇编文件", command=self.load_and_disassemble
        )
        self.btn_browse.grid(row=0, column=2, sticky=tk.E)

        config_frame = ttk.LabelFrame(self, text=" 反汇编选项 ", padding="5")
        config_frame.grid(row=1, column=0, sticky=tk.EW, pady=5)

        ttk.Label(
            config_frame, text="基址 (Hex, 如 0000 或 0200): $"
        ).pack(side=tk.LEFT, padx=5)
        self.var_base_addr = tk.StringVar(value="0000")
        self.entry_base_addr = ttk.Entry(
            config_frame, textvariable=self.var_base_addr, width=8
        )
        self.entry_base_addr.pack(side=tk.LEFT, padx=5)

        # Added export button here
        self.btn_save = ttk.Button(
            config_frame,
            text="💾 导出到文本文件",
            command=self.save_to_file,
            state=tk.DISABLED,
        )
        self.btn_save.pack(side=tk.RIGHT, padx=5)

        self.lbl_status = ttk.Label(
            config_frame,
            text="准备就绪",
            font=("Consolas", 10),
            foreground="#1E90FF",
        )
        self.lbl_status.pack(side=tk.LEFT, padx=20)

        dis_group = ttk.LabelFrame(
            self, text=" Z80 反汇编代码输出 (地址 : 机器码 : 指令) "
        )
        dis_group.grid(row=2, column=0, sticky=tk.NSEW, pady=5)

        txt_container = ttk.Frame(dis_group)
        txt_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        sys_scroll = ttk.Scrollbar(txt_container)
        sys_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        sys_xscroll = ttk.Scrollbar(txt_container, orient=tk.HORIZONTAL)
        sys_xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.txt_disasm = tk.Text(
            txt_container,
            font=("Consolas", 10, "bold"),
            bg="#121212",
            fg="#00E5FF",
            yscrollcommand=sys_scroll.set,
            xscrollcommand=sys_xscroll.set,
            wrap=tk.NONE,
        )
        self.txt_disasm.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sys_scroll.config(command=self.txt_disasm.yview)
        sys_xscroll.config(command=self.txt_disasm.xview)

    def load_and_disassemble(self):
        fn = filedialog.askopenfilename(
            title="选择 ROM/BIN 文件",
            filetypes=[
                ("ROM & BIN Files", "*.rom;*.bin"),
                ("All Files", "*.*"),
            ],
        )
        if not fn:
            return
        self.file_path_var.set(fn)

        try:
            base_str = self.var_base_addr.get().strip()
            base_addr = int(base_str, 16) if base_str else 0x0000
        except ValueError:
            messagebox.showerror(
                "格式错误",
                "起始基址请输入有效的十六进制数值（例如 0000 或 0200）",
            )
            return

        try:
            with open(fn, "rb") as f:
                data = f.read()

            if not data:
                messagebox.showwarning("警告", "选择的文件为空！")
                return

            disassembled_code = disassemble_z80_bytes(data, base_addr=base_addr)

            self.lbl_status.config(
                text=f"成功反汇编 {len(data):,} 字节 | 起始地址: ${base_addr:04X}"
            )

            self.txt_disasm.config(state=tk.NORMAL)
            self.txt_disasm.delete("1.0", tk.END)
            self.txt_disasm.insert(tk.END, disassembled_code)
            self.txt_disasm.config(state=tk.DISABLED)

            # Enable save button
            self.btn_save.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("反汇编出错", f"读取或解析文件失败:\n{str(e)}")

    def save_to_file(self):
        content = self.txt_disasm.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("警告", "没有可导出的反汇编内容！")
            return

        fn = filedialog.asksaveasfilename(
            title="保存反汇编结果",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if fn:
            try:
                with open(fn, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("成功", f"文件已保存至:\n{fn}")
            except Exception as e:
                messagebox.showerror("保存失败", f"无法写入文件:\n{str(e)}")

# ==========================================
# 6. 主应用程序入口与菜单控制
# ==========================================
class MainApplication(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("CAC-3 综合开发工具套件")
        self.geometry("1100x850")
        self.minsize(800, 650)

        # 全局配置放大版按钮样式
        self.style = ttk.Style()
        self.style.configure(
            "Big.TButton",
            font=("Microsoft YaHei UI", 12, "bold"),
            padding=10,
        )

        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.current_frame = None

        self._build_menu()
        self.show_home_page()

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="返回主页", command=self.show_home_page)
        file_menu.add_separator()
        file_menu.add_command(label="退出程序", command=self.quit)
        menubar.add_cascade(label="文件 (File)", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(
            label="BASIC 解码 (BIN -> 源码)",
            command=self.load_basic_decoder_module,
        )
        tools_menu.add_command(
            label="BASIC 编码 (BASIC -> BIN)",
            command=self.load_basic_to_bin_module,
        )
        tools_menu.add_command(
            label="BIN 转 WAV 音频 (BIN -> WAV)",
            command=self.load_bin_to_wav_module,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="ROM/BIN 文件浏览器", command=self.load_hex_viewer_module
        )
        tools_menu.add_command(
            label="ROM 反汇编 (Z80)", command=self.load_disassembler_module
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="🌊 音频信号分析与解调-1",
            command=self.load_signal_analyzer_module,
        )
        tools_menu.add_command(
            label="🎵 音频信号分析与解调-2",
            command=self.load_audio_decoder_module,
        )
        menubar.add_cascade(label="工具 (Tools)", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label="关于",
            command=lambda: messagebox.showinfo(
                "关于", "CAC-3 综合开发分析套件\n版本: v2.7"
            ),
        )
        menubar.add_cascade(label="帮助 (Help)", menu=help_menu)

        self.config(menu=menubar)

    def switch_frame(self, frame_class, *args):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame_class(self.container, self, *args)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

    def show_home_page(self):
        if self.current_frame is not None:
            self.current_frame.destroy()

        home_frame = ttk.Frame(self.container, padding="20")
        home_frame.pack(fill=tk.BOTH, expand=True)

        welcome_label = ttk.Label(
            home_frame,
            text="欢迎使用 CAC-3 工具箱",
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        welcome_label.pack(pady=(10, 5))

        sub_label = ttk.Label(
            home_frame,
            text="请选择下方功能模块进入操作：",
            font=("Microsoft YaHei UI", 11),
            foreground="#555555",
        )
        sub_label.pack(pady=(0, 15))

        # 功能按钮区域 - 垂直排列单列
        btn_container = ttk.Frame(home_frame)
        btn_container.pack(expand=True)

        # 7 个独立功能按钮配置
        buttons_spec = [
            ("📜 BASIC 解码 (BIN -> 源码)", self.load_basic_decoder_module),
            ("⚡ BASIC 编码 (BASIC -> BIN)", self.load_basic_to_bin_module),
            ("🎵 BIN 转 WAV (BIN -> WAV)", self.load_bin_to_wav_module),
            ("🔍 ROM / BIN 文件浏览器", self.load_hex_viewer_module),
            ("⚙️ ROM 反汇编器 (Z80)", self.load_disassembler_module),
            ("🌊 音频信号分析与解调-1", self.load_signal_analyzer_module),
            ("🎵 音频信号分析与解调-2", self.load_audio_decoder_module),
        ]

        # 统一设置为宽度 35，上下内边距 ipady=6，字号加大
        for text, cmd in buttons_spec:
            btn = ttk.Button(
                btn_container,
                text=text,
                command=cmd,
                style="Big.TButton",
                width=35,
            )
            btn.pack(pady=6, ipady=4)

        self.current_frame = home_frame

    def load_basic_decoder_module(self):
        self.switch_frame(BasicDecoderFrame)

    def load_basic_to_bin_module(self):
        self.switch_frame(BasicToBinFrame)

    def load_bin_to_wav_module(self):
        self.switch_frame(BinToWavFrame)

    def load_hex_viewer_module(self):
        self.switch_frame(HexViewerFrame)

    def load_disassembler_module(self):
        self.switch_frame(DisassemblerFrame)

    def load_signal_analyzer_module(self):
        self.switch_frame(SignalAnalyzerFrame)

    def load_audio_decoder_module(self):
        self.switch_frame(AudioDecoderFrame)


if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()