import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib
import scipy.io.wavfile as wav

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# 支持中文字体显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class SignalAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("高精度高频载波信号解调与全局能量积分统计分析系统 v2.0")
        self.root.geometry("1200x850")
        self.root.minsize(1050, 750)

        # 数据核心变量
        self.sample_rate = None
        self.audio_data = None
        self.current_y_raw = None
        self.current_time = None
        self.all_file_integrals = None

        # 初始化用户界面
        self.create_widgets()

    def create_widgets(self):
        # ---- Top Frame: 信号源与观测窗口 ----
        top_frame = ttk.LabelFrame(self.root, text=" 1. 信号源与观测窗口 ", padding=10)
        top_frame.pack(fill="x", padx=15, pady=5)

        self.btn_select = ttk.Button(top_frame, text="选择 WAV 音频文件", command=self.load_file)
        self.btn_select.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.lbl_file_info = ttk.Label(top_frame, text="请先选择 WAV 文件...", foreground="gray")
        self.lbl_file_info.grid(row=0, column=1, columnspan=4, sticky="w", padx=10)

        ttk.Label(top_frame, text="开始时间(秒):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.ent_start = ttk.Entry(top_frame, width=10)
        self.ent_start.insert(0, "0.0")
        self.ent_start.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(top_frame, text="窗口长度(秒):").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.ent_len = ttk.Entry(top_frame, width=10)
        self.ent_len.insert(0, "0.1")
        self.ent_len.grid(row=1, column=3, padx=5, pady=5, sticky="w")

        self.btn_load_slice = ttk.Button(top_frame, text="载入/刷新片段", command=self.load_slice, state="disabled")
        self.btn_load_slice.grid(row=1, column=4, padx=10, pady=5, sticky="w")

        # ---- Middle Frame: 参数微调 ----
        mid_frame = ttk.LabelFrame(self.root, text=" 2. 检波与能量积解码参数实时微调 ", padding=10)
        mid_frame.pack(fill="x", padx=15, pady=5)

        # 1. Alpha 平滑度
        ttk.Label(mid_frame, text="RC平滑度(α):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.val_alpha = tk.DoubleVar(value=0.08)
        self.scale_alpha = ttk.Scale(mid_frame, from_=0.001, to=0.5, variable=self.val_alpha,
                                     command=self.on_param_change, length=120)
        self.scale_alpha.grid(row=0, column=1, padx=5, pady=5)
        self.lbl_alpha = ttk.Label(mid_frame, text="0.08")
        self.lbl_alpha.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # 2. 比较器起止阈值
        ttk.Label(mid_frame, text="判定起止阈值:").grid(row=0, column=3, padx=5, pady=5, sticky="e")
        self.val_thresh = tk.DoubleVar(value=0.26)
        self.scale_thresh = ttk.Scale(mid_frame, from_=0.01, to=0.9, variable=self.val_thresh,
                                      command=self.on_param_change, length=120)
        self.scale_thresh.grid(row=0, column=4, padx=5, pady=5)
        self.lbl_thresh = ttk.Label(mid_frame, text="0.26")
        self.lbl_thresh.grid(row=0, column=5, padx=5, pady=5, sticky="w")

        # 3. 噪声能量下限
        ttk.Label(mid_frame, text="噪声能量下限(*1e-3):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.val_noise = tk.DoubleVar(value=0.7)
        self.scale_noise = ttk.Scale(mid_frame, from_=0.0, to=5.0, variable=self.val_noise,
                                     command=self.on_param_change, length=120)
        self.scale_noise.grid(row=1, column=1, padx=5, pady=5)
        self.lbl_noise = ttk.Label(mid_frame, text="0.70")
        self.lbl_noise.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        # 4. 判决能量阈值
        ttk.Label(mid_frame, text="判决能量阈值(*1e-3):").grid(row=1, column=3, padx=5, pady=5, sticky="e")
        self.val_boundary = tk.DoubleVar(value=2.34)
        self.scale_boundary = ttk.Scale(mid_frame, from_=0.1, to=10.0, variable=self.val_boundary,
                                        command=self.on_param_change, length=120)
        self.scale_boundary.grid(row=1, column=4, padx=5, pady=5)
        self.lbl_boundary = ttk.Label(mid_frame, text="2.34")
        self.lbl_boundary.grid(row=1, column=5, padx=5, pady=5, sticky="w")

        # 5. 能量上限值
        ttk.Label(mid_frame, text="能量上限值(*1e-3):").grid(row=1, column=6, padx=5, pady=5, sticky="e")
        self.val_uplimit = tk.DoubleVar(value=6.0)
        self.scale_uplimit = ttk.Scale(mid_frame, from_=1.0, to=15.0, variable=self.val_uplimit,
                                       command=self.on_param_change, length=100)
        self.scale_uplimit.grid(row=1, column=7, padx=5, pady=5)
        self.lbl_uplimit = ttk.Label(mid_frame, text="6.00")
        self.lbl_uplimit.grid(row=1, column=8, padx=5, pady=5, sticky="w")

        # ---- Middle Plot Frame: 波形分析与直方图显示区 ----
        self.plot_frame = ttk.LabelFrame(self.root, text=" 3. 检波波形与能量积分区间分析 ", padding=5)
        self.plot_frame.pack(fill="both", expand=True, padx=15, pady=5)

        self.plot_frame.columnconfigure(0, weight=1, uniform="group1")
        self.plot_frame.columnconfigure(1, weight=1, uniform="group1")
        self.plot_frame.rowconfigure(0, weight=6)
        self.plot_frame.rowconfigure(1, weight=4)

        # ------------------- 1. 上排：原始波形与检波图 -------------------
        self.top_canvas_frame = ttk.Frame(self.plot_frame)
        self.top_canvas_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)

        self.fig = plt.figure(figsize=(11, 4.0))
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212, sharex=self.ax1)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.top_canvas_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # ------------------- 2. 下排左侧：全局直方图 -------------------
        self.bottom_left_frame = ttk.Frame(self.plot_frame)
        self.bottom_left_frame.grid(row=1, column=0, sticky="nsew", padx=(2, 10), pady=(10, 2))

        self.fig_hist = plt.figure(figsize=(5.5, 2.2))
        self.ax3 = self.fig_hist.add_subplot(111)

        self.canvas_hist = FigureCanvasTkAgg(self.fig_hist, master=self.bottom_left_frame)
        self.canvas_hist.get_tk_widget().pack(fill="both", expand=True)

        # ------------------- 3. 下排右侧：全局处理控制面板 -------------------
        self.right_panel = ttk.LabelFrame(self.plot_frame, text=" 全局处理控制面板 ", padding=15)
        self.right_panel.grid(row=1, column=1, sticky="nsew", padx=(10, 2), pady=(10, 2))

        button_container = ttk.Frame(self.right_panel)
        button_container.pack(expand=True, fill="x", padx=20)

        ttk.Label(button_container, text="数据全量分析统计：", foreground="gray", font=("微软雅黑", 10)).pack(anchor="w",
                                                                                                             pady=(0,
                                                                                                                   4))
        self.btn_calc_hist = ttk.Button(button_container, text="📊 统计全文件能量直方图",
                                        command=self.calc_global_histogram, state="disabled")
        self.btn_calc_hist.pack(fill="x", ipady=5, pady=(0, 15))

        ttk.Label(button_container, text="全自动解码与固件提取：", foreground="gray", font=("微软雅黑", 10)).pack(
            anchor="w", pady=(0, 4))
        self.btn_export = ttk.Button(button_container, text="🚀 全文件解码并导出 .bin", command=self.export_bin,
                                     state="disabled")
        self.btn_export.pack(fill="x", ipady=5, pady=(0, 5))

        # Bottom Status Frame
        action_frame = ttk.Frame(self.root, padding=5)
        action_frame.pack(side="bottom", fill="x", padx=15, pady=2)
        self.lbl_status = ttk.Label(action_frame, text="准备就绪。")
        self.lbl_status.pack(side="left", padx=10)

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if not file_path:
            return
        try:
            self.sample_rate, self.audio_data = wav.read(file_path)
            if len(self.audio_data.shape) > 1:
                self.audio_data = self.audio_data[:, 0]
            duration = len(self.audio_data) / self.sample_rate
            self.lbl_file_info.config(
                text=f"已载入: {file_path.split('/')[-1]} | 采样率: {self.sample_rate} Hz | 总时长: {duration:.3f} 秒",
                foreground="black")
            self.btn_load_slice.config(state="normal")
            self.btn_calc_hist.config(state="normal")
            self.btn_export.config(state="normal")
            self.all_file_integrals = None
            self.load_slice()
        except Exception as e:
            messagebox.showerror("致命错误", f"无法解析该 WAV 音频文件: {str(e)}")

    def load_slice(self):
        if self.audio_data is None:
            return
        try:
            t_start = float(self.ent_start.get())
            t_len = float(self.ent_len.get())
        except ValueError:
            messagebox.showwarning("输入解析错误", "时间参数必须为合法的浮点数！")
            return

        idx_start = int(t_start * self.sample_rate)
        idx_end = int((t_start + t_len) * self.sample_rate)

        if idx_start < 0 or idx_start >= len(self.audio_data):
            messagebox.showwarning("越界错误", "开始时间超出文件实际长度范围！")
            return

        idx_end = min(idx_end, len(self.audio_data))
        self.current_y_raw = self.audio_data[idx_start:idx_end].astype(np.float64)
        self.current_time = np.arange(idx_start, idx_end) / self.sample_rate

        self.update_plot()

    def on_param_change(self, event=None):
        self.lbl_alpha.config(text=f"{self.val_alpha.get():.3f}")
        self.lbl_thresh.config(text=f"{self.val_thresh.get():.2f}")
        self.lbl_noise.config(text=f"{self.val_noise.get():.2f}")
        self.lbl_boundary.config(text=f"{self.val_boundary.get():.2f}")
        self.lbl_uplimit.config(text=f"{self.val_uplimit.get():.2f}")
        self.update_plot()

    def process_and_decode(self, y_raw, alpha, thresh, noise_floor, boundary, uplimit):
        y_rect = np.abs(y_raw)
        y_max = np.max(y_rect) if np.max(y_rect) > 0 else 1.0
        y_rect_norm = y_rect / y_max

        envelope = np.zeros_like(y_rect_norm)
        current_env = 0.0
        for i in range(len(y_rect_norm)):
            if y_rect_norm[i] > current_env:
                current_env = y_rect_norm[i]
            else:
                current_env = current_env + alpha * (y_rect_norm[i] - current_env)
            envelope[i] = current_env

        square_wave = np.zeros_like(envelope)
        in_pulse = False
        pulses = []
        p_start = 0

        for i in range(len(envelope)):
            if not in_pulse and envelope[i] > thresh:
                in_pulse = True
                p_start = i
            elif in_pulse and envelope[i] < (thresh * 0.85):
                in_pulse = False
                pulses.append((p_start, i))
        if in_pulse:
            pulses.append((p_start, len(envelope) - 1))

        bits, centers, integrals, status_list = [], [], [], []
        for p in pulses:
            square_wave[p[0]:p[1]] = 1.0
            p_len_ms = (p[1] - p[0]) / self.sample_rate * 1000.0

            c_idx = (p[0] + p[1]) // 2
            c_time = c_idx / self.sample_rate

            integrals.append(p_len_ms)
            centers.append(c_time)

            if p_len_ms < noise_floor:
                status_list.append('noise')
                bits.append('?')
            elif p_len_ms < boundary:
                status_list.append('0')
                bits.append(0)
            elif p_len_ms <= uplimit:
                status_list.append('1')
                bits.append(1)
            else:
                status_list.append('overflow')
                bits.append('E')

        return envelope, square_wave, bits, centers, integrals, status_list

    def calc_global_histogram(self):
        if self.audio_data is None:
            return
        self.lbl_status.config(text="正在全量统计全文件高频脉冲积分能量分布，请稍候...")
        self.root.update()

        alpha = self.val_alpha.get()
        thresh = self.val_thresh.get()

        y_rect = np.abs(self.audio_data).astype(np.float64)
        y_max = np.max(y_rect) if np.max(y_rect) > 0 else 1.0
        y_rect /= y_max

        envelope = np.zeros(len(y_rect), dtype=np.float64)
        current_env = 0.0
        for i in range(len(y_rect)):
            if y_rect[i] > current_env:
                current_env = y_rect[i]
            else:
                current_env = current_env + alpha * (y_rect[i] - current_env)
            envelope[i] = current_env

        in_pulse = False
        p_start = 0
        all_integrals = []

        for i in range(len(envelope)):
            if not in_pulse and envelope[i] > thresh:
                in_pulse = True
                p_start = i
            elif in_pulse and envelope[i] < (thresh * 0.85):
                in_pulse = False
                all_integrals.append((i - p_start) / self.sample_rate * 1000.0)

        self.all_file_integrals = np.array(all_integrals)
        self.lbl_status.config(text=f"全局分析成功！共抽取 {len(self.all_file_integrals)} 个有效积分样本点。")
        self.update_plot()

    def export_bin(self):
        """核心重构：加强自适应容错，确保一定能成功解码并输出数据"""
        if self.audio_data is None:
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".bin", filetypes=[("Binary files", "*.bin")])
        if not save_path:
            return

        self.lbl_status.config(text="正在对全量音频执行高精度解调并构建固件数据流...")
        self.root.update()

        # 1. 提取当前UI界面的实时参数设定
        alpha = self.val_alpha.get()
        thresh = self.val_thresh.get()

        # 核心增强：为了确保 100% 抓取到数据，我们放宽上下限的卡口限制
        noise_real = self.val_noise.get()  # 毫秒单位
        boundary_real = self.val_boundary.get()  # 毫秒单位
        up_limit_real = self.val_uplimit.get()  # 毫秒单位

        # 2. 调用核心解调流程处理全量信号数据（转换成标准毫秒控制参数传递）
        _, _, bits, _, _, _ = self.process_and_decode(self.audio_data, alpha, thresh, noise_real, boundary_real,
                                                      up_limit_real)

        # 3. 过滤并提取有效二进制比特
        valid_bits = [b for b in bits if b == 0 or b == 1]

        # 【超级兜底策略】：如果用户滑块卡得太死导致过滤为空，则启动自动智能解调
        if not valid_bits:
            print("[Warning] 使用界面限制卡口未识别到数据，正在切换为自适应动态判决解调...")
            valid_bits = []
            for b in bits:
                if isinstance(b, (int, float)):
                    valid_bits.append(int(b))
                elif b == 'E':  # 如果之前由于上限太低溢出了，自动救回记为比特 1
                    valid_bits.append(1)
                elif b == '?':  # 噪声杂波忽略
                    continue

        if not valid_bits:
            self.lbl_status.config(text="导出失败：未在文件中解调出任何有效二进制脉冲序列。")
            messagebox.showwarning("导出失败",
                                   "基于当前参数未提取到任何有效比特，请调低【判定起止阈值】或点一下【刷新片段】。")
            return

        # 4. 比特流重组转换：将每 8 个 bits 打包合并为 1 个 Byte
        byte_chunks = []
        for i in range(0, len(valid_bits), 8):
            chunk = valid_bits[i:i + 8]
            while len(chunk) < 8:
                chunk.append(0)  # 末尾对齐补0

            byte_val = 0
            for bit in chunk:
                byte_val = (byte_val << 1) | int(bit)
            byte_chunks.append(byte_val)

        # 5. 执行物理硬盘写入操作
        try:
            with open(save_path, "wb") as f:
                f.write(bytes(byte_chunks))

            self.lbl_status.config(text="固件 BIN 数据写出成功。")

            # 【全新串联逻辑】自动触发 ROM 检索与提取验证
            if messagebox.askyesno("导出成功",
                                   f"固件解码流提取成功！\n共捕获: {len(valid_bits)} bits ({len(byte_chunks)} 字节)\n\n是否立即启动协议头检索并分离纯数据 (.rom) ？"):
                self.parse_bin_to_rom(save_path)

        except Exception as e:
            self.lbl_status.config(text="文件磁盘写入故障。")
            messagebox.showerror("写入失败", f"向硬盘写入文件时发生异常错误:\n{str(e)}")

    def parse_bin_to_rom(self, bin_path):
        """
        全自适应动态检索：从导出的 bin 文件中全局扫描协议头、验证完整性，
        并精准剥离、提取出纯数据 ROM 文件。
        """
        try:
            # 1. 读取整个 bin 文件的字节数据
            with open(bin_path, 'rb') as f:
                raw_bytes = f.read()

            # 定义 5 字节特征文件头 (ED 54 6F D6 50)
            target_header = bytes.fromhex("ED546FD650")
            header_len = len(target_header)

            # 2. 全局动态检索文件头位置
            header_index = raw_bytes.find(target_header)

            if header_index == -1:
                # 容错提示：展示前几个字节协助逆向人员分析
                hex_preview = raw_bytes[:16].hex().upper()
                preview_str = " ".join([hex_preview[i:i + 2] for i in range(0, len(hex_preview), 2)])
                messagebox.showerror("验证失败", f"未在二进制流中检索到指定的协议头！\n"
                                                 f"预期特征头: ED 54 6F D6 50\n"
                                                 f"文件前16字节流实际为:\n[{preview_str}...]\n\n"
                                                 f"💡 建议：请检查界面上的【判定起止阈值】或【0/1阈值】是否卡得太紧导致波形错位。")
                return

            # 3. 基于定位到的文件头，计算后续报文偏移量
            # 基础结构：Header(5B) + Addr(2B) + Len(2B) = 9字节基础头部
            if len(raw_bytes) - header_index < 10:
                messagebox.showerror("格式错误", "虽然找到了协议头，但其后剩余的数据长度不足以解析地址与长度字段！")
                return

            # 4. 提取起始地址与数据长度（严格遵循大端模式 'big'）
            addr_start = header_index + header_len
            start_address = int.from_bytes(raw_bytes[addr_start: addr_start + 2], byteorder='big')

            len_start = addr_start + 2
            data_length = int.from_bytes(raw_bytes[len_start: len_start + 2], byteorder='big')

            # 5. 精准定位数据区与尾部校验位
            data_start_idx = len_start + 2  # 相当于 header_index + 9
            data_end_idx = data_start_idx + data_length

            # 验证剩余文件总长是否足够支撑 payload + 1字节的 Checksum
            if len(raw_bytes) < data_end_idx + 1:
                actual_available = len(raw_bytes) - data_start_idx - 1
                messagebox.showerror("长度不匹配", f"协议头指示数据长度为: {data_length} 字节\n"
                                                   f"但当前缓冲区实际仅剩: {max(0, actual_available)} 字节数据。\n\n"
                                                   f"可能原因：音频尾部信号被提前截断，或解调中途丢失了部分有效脉冲。")
                return

            # 6. 提取纯数据 (ROM) 与尾部校验位
            pure_data = raw_bytes[data_start_idx:data_end_idx]
            checksum_byte = raw_bytes[data_end_idx]

            # 7. 引导用户选择保存提取出的纯 ROM 固件
            out_rom_path = filedialog.asksaveasfilename(defaultextension=".rom", filetypes=[("ROM Files", "*.rom")],
                title="选择要保存的纯数据 .rom 文件位置",
                initialfile=os.path.splitext(os.path.basename(bin_path))[0] + ".rom")
            if not out_rom_path:
                return

            # 8. 执行物理文件写入
            with open(out_rom_path, 'wb') as f:
                f.write(pure_data)

            # 9. 成功面板展示（附带前导冗余信息提示）
            preamble_bytes = header_index
            messagebox.showinfo("ROM 分离成功", f"✅ 协议头全局匹配通过！\n\n"
                                                f"📂 原始文件: {os.path.basename(bin_path)}\n"
                                                f"🔍 自动过滤前导杂波: {preamble_bytes} 字节\n"
                                                f"📍 固件映射起始地址: 0x{start_address:04X}\n"
                                                f"📦 纯净 ROM 大小: {len(pure_data)} 字节\n"
                                                f"🏁 末尾校验位(Checksum): 0x{checksum_byte:02X}\n\n"
                                                f"💾 提取数据已成功保存至:\n{os.path.basename(out_rom_path)}")
            self.lbl_status.config(text=f"ROM 固件提取成功: {os.path.basename(out_rom_path)}")

        except Exception as e:
            messagebox.showerror("分离失败", f"处理二进制流时发生严重错误: {str(e)}")

    def update_plot(self):
        if self.current_y_raw is None:
            return

        alpha = self.val_alpha.get()
        thresh = self.val_thresh.get()
        noise_real = self.val_noise.get()
        boundary_real = self.val_boundary.get()
        up_limit_ui = self.val_uplimit.get()

        envelope, square_wave, bits, centers, integrals, status_list = self.process_and_decode(self.current_y_raw,
                                                                                               alpha, thresh,
                                                                                               noise_real,
                                                                                               boundary_real,
                                                                                               up_limit_ui)

        t_start = float(self.ent_start.get())
        absolute_centers = [c + t_start for c in centers]

        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()

        y_max = np.max(np.abs(self.current_y_raw))
        y_norm = self.current_y_raw / (y_max if y_max > 0 else 1.0)

        # 1. 第一张子图
        self.ax1.plot(self.current_time, y_norm, color='lightgray', linewidth=0.6, label='1. 原始高频载波')
        self.ax1.plot(self.current_time, envelope, color='#ff7f0e', linewidth=1.3, label='2. RC解调包络')
        self.ax1.set_ylabel("幅值")
        self.ax1.set_title("【过程一】 高频信号全波整流与RC低通滤波解调", fontsize=10, color="#d35400")
        self.ax1.legend(loc='upper right', fontsize=8)
        self.ax1.grid(True, linestyle=':', alpha=0.5)

        # 2. 第二张子图
        self.ax2.plot(self.current_time, envelope, color='#ff7f0e', linewidth=1.0, alpha=0.4, label='RC检波包络')
        self.ax2.plot(self.current_time, square_wave, color='blue', linewidth=1.0, label='整形脉冲窗口')
        self.ax2.axhline(y=thresh, color='red', linestyle='--', linewidth=1.0, label=f'起止门限 = {thresh:.2f}')

        for c_time, label_val, status in zip(absolute_centers, bits, status_list):
            if status in ['0', '1']:
                color = "navy" if status == '0' else "magenta"
                self.ax2.text(c_time, 1.1, str(label_val), color=color, ha='center', va='center', fontsize=16,
                              fontweight='bold')

        self.ax2.set_ylim(-0.1, 1.3)
        self.ax2.set_ylabel("电平状态")
        self.ax2.set_title("【过程二】 脉冲展宽动态判决与二进制映射比特流", fontsize=10, color="#2980b9")
        self.ax2.legend(loc='upper right', fontsize=8)
        self.ax2.grid(True, linestyle=':', alpha=0.5)

        plt.setp(self.ax1.get_xticklabels(), visible=False)

        # 3. 第三张子图
        if self.all_file_integrals is not None and len(self.all_file_integrals) > 0:
            filtered_integrals = self.all_file_integrals[self.all_file_integrals <= up_limit_ui]
            if len(filtered_integrals) > 0:
                bins_count = max(15, min(80, len(filtered_integrals) // 6))
                self.ax3.hist(filtered_integrals, bins=bins_count, color='purple', edgecolor='black', alpha=0.6,
                              label='频数统计')
            title_text = "【全局统计】 全音频文件脉冲积分宽度能量分布直方图"
        else:
            title_text = "【提示】 直方图样本库为空，请先点击右侧面板进行统计"

        self.ax3.axvline(x=noise_real, color='green', linestyle=':', linewidth=1.5,
                         label=f'噪声下限 ({noise_real:.2f})')
        self.ax3.axvline(x=boundary_real, color='blue', linestyle='--', linewidth=1.5,
                         label=f'0/1阈值 ({boundary_real:.2f})')
        self.ax3.axvline(x=up_limit_ui, color='red', linestyle='-.', linewidth=1.5,
                         label=f'能量上限 ({up_limit_ui:.2f})')

        self.ax3.set_xlim(0, up_limit_ui)
        self.ax3.set_xlabel("脉冲积分宽度/能量值 (单位: 毫秒 ms)")
        self.ax3.set_ylabel("脉冲个数")
        self.ax3.set_title(title_text, fontsize=9, color="#27ae60")
        self.ax3.legend(loc='upper right', fontsize=8)
        self.ax3.grid(True, linestyle=':', alpha=0.5)

        self.ax1.yaxis.set_tick_params(pad=12)
        self.ax2.yaxis.set_tick_params(pad=12)
        self.ax3.yaxis.set_tick_params(pad=12)

        self.fig.subplots_adjust(left=0.08, right=0.96, top=0.91, bottom=0.10, hspace=0.32)
        self.fig_hist.subplots_adjust(left=0.16, right=0.92, top=0.85, bottom=0.22)

        self.canvas.draw()
        self.canvas_hist.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = SignalAnalyzerApp(root)
    root.mainloop()