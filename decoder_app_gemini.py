import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scipy.io import wavfile

# 支持中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class OOKDecoderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OOK 信号包络数值积分二进制解码器 v2.5")
        self.root.geometry("1150x880")

        # 数据变量
        self.wav_path = None
        self.sample_rate = None
        self.data_read = None
        self.total_duration = 0.0
        self.is_stereo = False

        # 当前加载的片段数据
        self.current_y_raw = None
        self.current_time = None

        self.create_widgets()

    def create_widgets(self):
        # ---- Top Frame: 文件加载与窗口设置 ----
        top_frame = ttk.LabelFrame(self.root, text=" 1. 信号源与观测窗口 ", padding=10)
        top_frame.pack(fill="x", padx=15, pady=5)

        self.btn_select = ttk.Button(top_frame, text="选择 WAV 音频文件", command=self.load_file)
        self.btn_select.grid(row=0, column=0, padx=5, pady=5)

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
        self.btn_load_slice.grid(row=1, column=4, padx=20, pady=5)

        # ---- Middle Frame: 参数微调 ----
        mid_frame = ttk.LabelFrame(self.root, text=" 2. 检波与能量积解码参数实时微调 ", padding=10)
        mid_frame.pack(fill="x", padx=15, pady=5)

        # 1. Alpha 平滑度 (默认 0.08)
        ttk.Label(mid_frame, text="RC平滑度(α):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.val_alpha = tk.DoubleVar(value=0.08)
        self.scale_alpha = ttk.Scale(mid_frame, from_=0.001, to=0.5, variable=self.val_alpha,
                                     command=self.on_param_change, length=180)
        self.scale_alpha.grid(row=0, column=1, padx=5, pady=5)
        self.lbl_alpha = ttk.Label(mid_frame, text="0.08")
        self.lbl_alpha.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # 2. 比较器起止阈值 (默认 0.34)
        ttk.Label(mid_frame, text="判定起止阈值:").grid(row=0, column=3, padx=5, pady=5, sticky="e")
        self.val_thresh = tk.DoubleVar(value=0.34)
        self.scale_thresh = ttk.Scale(mid_frame, from_=0.01, to=0.9, variable=self.val_thresh,
                                      command=self.on_param_change, length=180)
        self.scale_thresh.grid(row=0, column=4, padx=5, pady=5)
        self.lbl_thresh = ttk.Label(mid_frame, text="0.34")
        self.lbl_thresh.grid(row=0, column=5, padx=5, pady=5, sticky="w")

        # 3. 噪声能量下限 (默认 0.70)
        ttk.Label(mid_frame, text="噪声能量下限(*1e-3):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.val_noise = tk.DoubleVar(value=0.7)
        self.scale_noise = ttk.Scale(mid_frame, from_=0.0, to=5.0, variable=self.val_noise,
                                     command=self.on_param_change, length=180)
        self.scale_noise.grid(row=1, column=1, padx=5, pady=5)
        self.lbl_noise = ttk.Label(mid_frame, text="0.70")
        self.lbl_noise.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        # 4. 判决能量阈值 (默认 1.50)
        ttk.Label(mid_frame, text="判决能量阈值(*1e-3):").grid(row=1, column=3, padx=5, pady=5, sticky="e")
        self.val_boundary = tk.DoubleVar(value=1.5)
        self.scale_boundary = ttk.Scale(mid_frame, from_=0.1, to=10.0, variable=self.val_boundary,
                                        command=self.on_param_change, length=180)
        self.scale_boundary.grid(row=1, column=4, padx=5, pady=5)
        self.lbl_boundary = ttk.Label(mid_frame, text="1.50")
        self.lbl_boundary.grid(row=1, column=5, padx=5, pady=5, sticky="w")

        # 5. 能量上限值 (默认 5.00)
        ttk.Label(mid_frame, text="能量上限值(*1e-3):").grid(row=1, column=6, padx=5, pady=5, sticky="e")
        self.val_uplimit = tk.DoubleVar(value=5.0)
        self.scale_uplimit = ttk.Scale(mid_frame, from_=1.0, to=15.0, variable=self.val_uplimit,
                                       command=self.on_param_change, length=150)
        self.scale_uplimit.grid(row=1, column=7, padx=5, pady=5)
        self.lbl_uplimit = ttk.Label(mid_frame, text="5.00")
        self.lbl_uplimit.grid(row=1, column=8, padx=5, pady=5, sticky="w")

        # ---- Bottom Frame: 双子图显示 ----
        self.plot_frame = ttk.LabelFrame(self.root, text=" 3. 检波波形与能量积分区间分析 ", padding=5)
        self.plot_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # 创建双子图
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(10, 5.0), sharex=True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # ---- Action Frame: 全局导出 ----
        action_frame = ttk.Frame(self.root, padding=5)
        action_frame.pack(fill="x", padx=15, pady=10)

        self.btn_export = ttk.Button(action_frame, text="🚀 开始全文件能量解码并导出 .bin 文件", command=self.export_bin,
                                     state="disabled")
        self.btn_export.pack(side="right", padx=10)

        self.lbl_status = ttk.Label(action_frame, text="准备就绪。")
        self.lbl_status.pack(side="left", padx=10)

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("WAV Audio", "*.wav")])
        if not file_path:
            return

        self.wav_path = file_path
        self.sample_rate, self.data_read = wavfile.read(self.wav_path, mmap=True)
        n_samples = len(self.data_read)
        self.total_duration = n_samples / self.sample_rate
        self.is_stereo = len(self.data_read.shape) > 1

        file_name = os.path.basename(file_path)
        self.lbl_file_info.config(
            text=f"文件: {file_name} | 采样率: {self.sample_rate}Hz | 总长: {self.total_duration:.2f} 秒"
        )

        self.btn_load_slice.config(state="normal")
        self.btn_export.config(state="normal")
        self.load_slice()

    def load_slice(self):
        if self.data_read is None:
            return
        try:
            t_start = float(self.ent_start.get())
            t_len = float(self.ent_len.get())
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的数字！")
            return

        t_end = t_start + t_len
        if t_start >= self.total_duration:
            messagebox.showerror("时间越界", f"起始时间不能大于总时长 {self.total_duration:.2f} 秒")
            return

        idx_start = int(t_start * self.sample_rate)
        idx_end = int(t_end * self.sample_rate)
        n_samples = len(self.data_read)
        if idx_end > n_samples:
            idx_end = n_samples
            t_end = n_samples / self.sample_rate

        y_slice = self.data_read[idx_start:idx_end]
        if self.is_stereo:
            y_slice = np.mean(y_slice, axis=1)

        self.current_y_raw = y_slice
        self.current_time = np.linspace(t_start, t_end, num=len(y_slice))

        self.lbl_status.config(text=f"已成功加载段落: {t_start:.2f}s - {t_end:.2f}s")
        self.update_plot()

    def process_and_decode(self, y, alpha, thresh, noise_energy_thresh, boundary_energy_thresh, uplimit_energy_thresh):
        rectified = np.abs(y)
        max_val = np.max(rectified)
        if max_val > 0:
            rectified = rectified / max_val

        envelope = np.zeros_like(rectified)
        current = 0.0
        for i in range(len(rectified)):
            if rectified[i] > current:
                current = rectified[i]
            else:
                current = alpha * rectified[i] + (1 - alpha) * current
            envelope[i] = current

        # 利用阈值找到脉冲的有效提取区间
        square_wave = np.where(envelope >= thresh, 1, 0)
        diff = np.diff(square_wave)
        rising_edges = np.where(diff == 1)[0] + 1
        falling_edges = np.where(diff == -1)[0] + 1

        if len(rising_edges) > 0 and len(falling_edges) > 0:
            if falling_edges[0] < rising_edges[0]:
                falling_edges = falling_edges[1:]
            min_len = min(len(rising_edges), len(falling_edges))
            rising_edges = rising_edges[:min_len]
            falling_edges = falling_edges[:min_len]

        decoded_bits = []
        pulse_centers = []
        pulse_integrals = []
        pulse_status = []  # 脉冲分类状态：'noise', '0', '1', 'discard'

        for r, f in zip(rising_edges, falling_edges):
            pulse_slice = envelope[r:f]
            if len(pulse_slice) == 0:
                continue

            if hasattr(np, 'trapezoid'):
                integral_val = np.trapezoid(pulse_slice) / self.sample_rate
            else:
                integral_val = np.trapz(pulse_slice) / self.sample_rate

            center_time = ((r + f) / 2.0) / self.sample_rate

            # 四级决策树
            if integral_val < noise_energy_thresh:
                pulse_status.append('noise')
                decoded_bits.append("噪声")
            elif integral_val > uplimit_energy_thresh:
                pulse_status.append('discard')
                decoded_bits.append("丢弃")
            else:
                bit = 1 if integral_val >= boundary_energy_thresh else 0
                pulse_status.append(str(bit))
                decoded_bits.append(bit)

            pulse_integrals.append(integral_val)
            pulse_centers.append(center_time)

        return envelope, square_wave, decoded_bits, pulse_centers, pulse_integrals, pulse_status

    def on_param_change(self, *args):
        alpha = self.val_alpha.get()
        thresh = self.val_thresh.get()
        noise_ui = self.val_noise.get()
        boundary_ui = self.val_boundary.get()
        uplimit_ui = self.val_uplimit.get()

        # 安全逻辑保障
        if boundary_ui < noise_ui:
            self.val_boundary.set(noise_ui)
            boundary_ui = noise_ui
        if uplimit_ui < boundary_ui:
            self.val_uplimit.set(boundary_ui)
            uplimit_ui = boundary_ui

        self.lbl_alpha.config(text=f"{alpha:.2f}")
        self.lbl_thresh.config(text=f"{thresh:.2f}")
        self.lbl_noise.config(text=f"{noise_ui:.2f}")
        self.lbl_boundary.config(text=f"{boundary_ui:.2f}")
        self.lbl_uplimit.config(text=f"{uplimit_ui:.2f}")

        self.update_plot()

    def update_plot(self):
        if self.current_y_raw is None:
            return

        alpha = self.val_alpha.get()
        thresh = self.val_thresh.get()
        noise_real = self.val_noise.get() / 1000.0
        boundary_real = self.val_boundary.get() / 1000.0
        uplimit_real = self.val_uplimit.get() / 1000.0

        envelope, square_wave, bits, centers, integrals, status_list = self.process_and_decode(
            self.current_y_raw, alpha, thresh, noise_real, boundary_real, uplimit_real
        )

        t_start = float(self.ent_start.get())
        absolute_centers = [c + t_start for c in centers]

        self.ax1.clear()
        self.ax2.clear()

        y_norm = self.current_y_raw / (
            np.max(np.abs(self.current_y_raw)) if np.max(np.abs(self.current_y_raw)) > 0 else 1.0)

        # 1. 上方子图
        self.ax1.plot(self.current_time, y_norm, color='lightgray', linewidth=0.6, label='1. 原始高频载波')
        self.ax1.plot(self.current_time, envelope, color='#ff7f0e', linewidth=1.3, label='2. RC检波包络 (放电轨迹)')
        self.ax1.set_ylabel("幅值")
        self.ax1.set_title("【过程一】 RC 滤波检波：提取信号包络", fontsize=10, color="#d35400")
        self.ax1.legend(loc='upper right', fontsize=8)
        self.ax1.grid(True, linestyle=':', alpha=0.5)

        # 2. 下方子图
        self.ax2.plot(self.current_time, envelope, color='#ff7f0e', linewidth=1.0, alpha=0.5, label='RC检波包络')
        self.ax2.plot(self.current_time, square_wave, color='blue', linewidth=1.0, label='脉冲提取窗 (Vth起止)')
        self.ax2.axhline(y=thresh, color='red', linestyle='--', linewidth=1.0, label=f'起止门限 = {thresh:.2f}')

        # 3. 标注解码信息 (粗体，1为洋红magenta, 0为藏青navy，无外圈，无引号)
        for c_time, label_val, status in zip(absolute_centers, bits, status_list):
            if status in ['0', '1']:
                annot_text = str(label_val)

                # 0 用 navy（藏青），1 用 magenta（洋红）
                color = "navy" if status == '0' else "magenta"

                # 居中放置在 y = 0.5 的水平高度，字体加粗，字号放大至 16
                self.ax2.text(
                    c_time, 1.1, annot_text,
                    color=color,
                    ha='center',
                    va='center',
                    fontsize=18,
                    fontweight='bold'
                )

        self.ax2.set_ylim(-0.1, 1.3)
        self.ax2.set_xlabel("时间 (秒)")
        self.ax2.set_ylabel("电平状态")
        self.ax2.set_title("【过程二】 能量带通积分过滤解码机制 (仅显示有效比特)", fontsize=10, color="#2980b9")
        self.ax2.legend(loc='upper right', fontsize=8)
        self.ax2.grid(True, linestyle=':', alpha=0.5)

        self.fig.tight_layout()
        self.canvas.draw()

    def export_bin(self):
        if not self.wav_path:
            return

        out_bin_path = filedialog.asksaveasfilename(
            defaultextension=".bin",
            filetypes=[("Binary Files", "*.bin")],
            title="选择要保存的 .bin 文件位置"
        )
        if not out_bin_path:
            return

        alpha = self.val_alpha.get()
        thresh = self.val_thresh.get()
        noise_real = self.val_noise.get() / 1000.0
        boundary_real = self.val_boundary.get() / 1000.0
        uplimit_real = self.val_uplimit.get() / 1000.0

        self.lbl_status.config(text="正在进行全信号积分能量解调并写入 bin...")
        self.root.update_idletasks()

        try:
            sample_rate, data_read = wavfile.read(self.wav_path, mmap=True)
            n_samples = len(data_read)
            is_stereo = len(data_read.shape) > 1

            # 1. 转换为单声道并进行全局归一化
            y_all = data_read
            if is_stereo:
                y_all = np.mean(y_all, axis=1)

            y_all = y_all.astype(np.float32)
            max_val = np.max(np.abs(y_all))
            if max_val > 0:
                y_all = y_all / max_val  # 统一以全文件最大值归一化

            # 2. 全局 RC 滤波检波 (保证状态连续)
            self.lbl_status.config(text="正在进行全局 RC 滤波检波...")
            self.root.update_idletasks()

            envelope = np.zeros_like(y_all)
            rectified = np.abs(y_all)
            current = 0.0
            for i in range(len(rectified)):
                if rectified[i] > current:
                    current = rectified[i]
                else:
                    current = alpha * rectified[i] + (1 - alpha) * current
                envelope[i] = current

            # 3. 寻找脉冲边缘
            square_wave = np.where(envelope >= thresh, 1, 0)
            diff = np.diff(square_wave)
            rising_edges = np.where(diff == 1)[0] + 1
            falling_edges = np.where(diff == -1)[0] + 1

            # 边缘对齐
            if len(rising_edges) > 0 and len(falling_edges) > 0:
                if falling_edges[0] < rising_edges[0]:
                    falling_edges = falling_edges[1:]
                min_len = min(len(rising_edges), len(falling_edges))
                rising_edges = rising_edges[:min_len]
                falling_edges = falling_edges[:min_len]

            # 4. 基于全局包络进行区间能量积分
            decoded_bits = []
            noise_count = 0
            discard_count = 0

            for r, f in zip(rising_edges, falling_edges):
                # 直接从已经计算好的全局包络中切片，不再重复归一化和RC计算
                pulse_slice = envelope[r:f]
                if len(pulse_slice) == 0:
                    continue

                if hasattr(np, 'trapezoid'):
                    integral_val = np.trapezoid(pulse_slice) / sample_rate
                else:
                    integral_val = np.trapz(pulse_slice) / sample_rate

                if integral_val < noise_real:
                    noise_count += 1
                elif integral_val > uplimit_real:
                    discard_count += 1
                else:
                    bit = 1 if integral_val >= boundary_real else 0
                    decoded_bits.append(bit)

            # 5. 保存为 .bin 文件 (保持原逻辑不变)
            if len(decoded_bits) == 0:
                messagebox.showwarning("警告", "未检测到任何有效能量脉冲，导出取消。")
                return

            bit_array = np.array(decoded_bits, dtype=np.uint8)
            remainder = len(bit_array) % 8
            if remainder != 0:
                padding = 8 - remainder
                bit_array = np.append(bit_array, np.zeros(padding, dtype=np.uint8))

            bytes_data = np.packbits(bit_array)
            with open(out_bin_path, 'wb') as f:
                f.write(bytes_data.tobytes())

            self.lbl_status.config(text=f"已成功导出到: {os.path.basename(out_bin_path)}")

            # 【新加逻辑】自动触发 ROM 提取和协议验证
            if messagebox.askyesno("提示", "BIN 文件导出成功！是否立即验证文件头并分离纯数据（ROM）？"):
                self.parse_bin_to_rom(out_bin_path)

            messagebox.showinfo("成功", f"解调并导出成功！\n"
                                        f"有效比特数 (0/1): {len(decoded_bits)}\n"
                                        f"高频噪声过滤数: {noise_count}\n"
                                        f"异常超限丢弃数: {discard_count}\n"
                                        f"输出文件大小: {os.path.getsize(out_bin_path)} 字节")
            self.lbl_status.config(text=f"已成功导出到: {os.path.basename(out_bin_path)}")

        except Exception as e:
            messagebox.showerror("发生错误", f"导出失败: {str(e)}")
            self.lbl_status.config(text="导出失败。")

    def parse_bin_to_rom(self, bin_path):
        """
        从导出的 bin 文件中验证文件头、提取地址和长度，分离出纯数据并保存为 .rom
        """
        try:
            # 1. 读取整个 bin 文件的字节数据
            with open(bin_path, 'rb') as f:
                raw_bytes = f.read()

            # 2. 基础长度检查
            # 5字节头 + 2字节地址 + 2字节长度 + 至少1字节数据 + 1字节结尾校验 = 11 字节
            if len(raw_bytes) < 11:
                messagebox.showerror("格式错误", f"文件太小（仅 {len(raw_bytes)} 字节），不符合协议格式！")
                return

            # 3. 验证 5 字节文件头 (ED 54 6F D6 50)
            expected_header = bytes.fromhex("ED546FD650")
            actual_header = raw_bytes[0:5]

            if actual_header != expected_header:
                messagebox.showerror("验证失败",
                    f"文件头不匹配！\n预期: ED546FD650\n实际: {actual_header.hex().upper()}")
                return

            # 4. 提取起始地址 (第5、6字节，大端模式或小端模式，这里先按大端高位在前解析)
            # 如果你的硬件是小端模式，请把 'big' 改为 'little'
            start_address = int.from_bytes(raw_bytes[5:7], byteorder='big')

            # 5. 提取数据长度 (第7、8字节)
            data_length = int.from_bytes(raw_bytes[7:9], byteorder='big')

            # 6. 计算实际应该存在的数据范围
            # 从第10个字节开始（索引为9），长度为 data_length
            data_start_idx = 9
            data_end_idx = data_start_idx + data_length

            # 检查文件总长是否足够（包含最后1个校验字节）
            if len(raw_bytes) < data_end_idx + 1:
                messagebox.showerror("长度不匹配", f"头信息解析长度为 {data_length} 字节，但文件实际数据不足！\n"
                                                   f"文件总长: {len(raw_bytes)} 字节，期望至少: {data_end_idx + 1} 字节。")
                return

            # 7. 提取纯数据与校验位
            pure_data = raw_bytes[data_start_idx:data_end_idx]
            checksum_byte = raw_bytes[data_end_idx]  # 紧跟在数据后面的最后1字节

            # 8. 弹窗让用户选择保存 .rom 文件的路径
            out_rom_path = filedialog.asksaveasfilename(defaultextension=".rom", filetypes=[("ROM Files", "*.rom")],
                title="选择要保存的纯数据 .rom 文件位置",
                initialfile=os.path.splitext(os.path.basename(bin_path))[0] + ".rom")
            if not out_rom_path:
                return

            # 9. 写入纯数据到 .rom 文件
            with open(out_rom_path, 'wb') as f:
                f.write(pure_data)

            # 10. 提示成功信息，并打印出解析出来的关键参数
            messagebox.showinfo("ROM 分离成功", f"✅ 协议头验证通过！\n\n"
                                                f"📂 原始文件: {os.path.basename(bin_path)}\n"
                                                f"📍 起始地址: 0x{start_address:04X}\n"
                                                f"📦 数据长度: {data_length} 字节 (实际提取: {len(pure_data)} 字节)\n"
                                                f"🏁 末尾校验位: 0x{checksum_byte:02X}\n\n"
                                                f"💾 已成功保存纯数据至:\n{os.path.basename(out_rom_path)}")

        except Exception as e:
            messagebox.showerror("分离失败", f"处理二进制流时发生错误: {str(e)}")

if __name__ == "__main__":
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('vista')

    app = OOKDecoderApp(root)
    root.mainloop()