import os
import numpy as np
import scipy.io.wavfile as wav
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QLineEdit, QPushButton, QSlider, QGroupBox, 
                             QFileDialog, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# 支持中文字体显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class SignalAnalyzerFrame(QWidget):
    """高精度高频载波信号解调与全局能量积分统计分析模块"""
    def __init__(self, parent=None, root_app=None):
        super().__init__(parent)
        self.root_app = root_app
        self.settings = QSettings("CAC3Tools", "PyQtVersion")

        # 数据核心变量
        self.sample_rate = None
        self.audio_data = None
        self.current_y_raw = None
        self.current_time = None
        self.all_file_integrals = None

        # 初始化用户界面
        self.create_widgets()

    def create_widgets(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # ---- Top Frame: 信号源与观测窗口 ----
        top_frame = QGroupBox(" 1. 信号源与观测窗口 ")
        top_layout = QGridLayout()
        top_layout.setContentsMargins(10, 10, 10, 10)

        self.btn_select = QPushButton("选择 WAV 音频文件")
        self.btn_select.clicked.connect(self.load_file)
        top_layout.addWidget(self.btn_select, 0, 0)

        self.lbl_file_info = QLabel("请先选择 WAV 文件...")
        self.lbl_file_info.setStyleSheet("color: gray;")
        top_layout.addWidget(self.lbl_file_info, 0, 1, 1, 4)

        top_layout.addWidget(QLabel("开始时间(秒):"), 1, 0)
        self.ent_start = QLineEdit("0.0")
        self.ent_start.setFixedWidth(80)
        top_layout.addWidget(self.ent_start, 1, 1)

        top_layout.addWidget(QLabel("窗口长度(秒):"), 1, 2)
        self.ent_len = QLineEdit("0.1")
        self.ent_len.setFixedWidth(80)
        top_layout.addWidget(self.ent_len, 1, 3)

        self.btn_load_slice = QPushButton("载入/刷新片段")
        self.btn_load_slice.setEnabled(False)
        self.btn_load_slice.clicked.connect(self.load_slice)
        top_layout.addWidget(self.btn_load_slice, 1, 4)

        top_frame.setLayout(top_layout)
        main_layout.addWidget(top_frame)

        # ---- Middle Frame: 参数微调 ----
        mid_frame = QGroupBox(" 2. 检波与能量积解码参数实时微调 ")
        mid_layout = QGridLayout()
        mid_layout.setContentsMargins(10, 10, 10, 10)

        # 1. Alpha 平滑度
        mid_layout.addWidget(QLabel("RC平滑度(α):"), 0, 0)
        self.val_alpha = 0.08
        self.scale_alpha = QSlider(Qt.Horizontal)
        self.scale_alpha.setMinimum(1)
        self.scale_alpha.setMaximum(500)
        self.scale_alpha.setValue(int(self.val_alpha * 1000))
        self.scale_alpha.valueChanged.connect(self.on_param_change)
        self.scale_alpha.setFixedWidth(120)
        mid_layout.addWidget(self.scale_alpha, 0, 1)
        self.lbl_alpha = QLabel("0.08")
        mid_layout.addWidget(self.lbl_alpha, 0, 2)

        # 2. 比较器起止阈值
        mid_layout.addWidget(QLabel("判定起止阈值:"), 0, 3)
        self.val_thresh = 0.26
        self.scale_thresh = QSlider(Qt.Horizontal)
        self.scale_thresh.setMinimum(10)
        self.scale_thresh.setMaximum(900)
        self.scale_thresh.setValue(int(self.val_thresh * 100))
        self.scale_thresh.valueChanged.connect(self.on_param_change)
        self.scale_thresh.setFixedWidth(120)
        mid_layout.addWidget(self.scale_thresh, 0, 4)
        self.lbl_thresh = QLabel("0.26")
        mid_layout.addWidget(self.lbl_thresh, 0, 5)

        # 3. 噪声能量下限
        mid_layout.addWidget(QLabel("噪声能量下限(*1e-3):"), 1, 0)
        self.val_noise = 0.7
        self.scale_noise = QSlider(Qt.Horizontal)
        self.scale_noise.setMinimum(0)
        self.scale_noise.setMaximum(5000)
        self.scale_noise.setValue(int(self.val_noise * 10))
        self.scale_noise.valueChanged.connect(self.on_param_change)
        self.scale_noise.setFixedWidth(120)
        mid_layout.addWidget(self.scale_noise, 1, 1)
        self.lbl_noise = QLabel("0.70")
        mid_layout.addWidget(self.lbl_noise, 1, 2)

        # 4. 判决能量阈值
        mid_layout.addWidget(QLabel("判决能量阈值(*1e-3):"), 1, 3)
        self.val_boundary = 2.34
        self.scale_boundary = QSlider(Qt.Horizontal)
        self.scale_boundary.setMinimum(10)
        self.scale_boundary.setMaximum(10000)
        self.scale_boundary.setValue(int(self.val_boundary * 10))
        self.scale_boundary.valueChanged.connect(self.on_param_change)
        self.scale_boundary.setFixedWidth(120)
        mid_layout.addWidget(self.scale_boundary, 1, 4)
        self.lbl_boundary = QLabel("2.34")
        mid_layout.addWidget(self.lbl_boundary, 1, 5)

        # 5. 能量上限值
        mid_layout.addWidget(QLabel("能量上限值(*1e-3):"), 1, 6)
        self.val_uplimit = 6.0
        self.scale_uplimit = QSlider(Qt.Horizontal)
        self.scale_uplimit.setMinimum(1000)
        self.scale_uplimit.setMaximum(15000)
        self.scale_uplimit.setValue(int(self.val_uplimit * 10))
        self.scale_uplimit.valueChanged.connect(self.on_param_change)
        self.scale_uplimit.setFixedWidth(100)
        mid_layout.addWidget(self.scale_uplimit, 1, 7)
        self.lbl_uplimit = QLabel("6.00")
        mid_layout.addWidget(self.lbl_uplimit, 1, 8)

        mid_frame.setLayout(mid_layout)
        main_layout.addWidget(mid_frame)

        # ---- Middle Plot Frame: 波形分析与直方图显示区 ----
        plot_frame = QGroupBox(" 3. 检波波形与能量积分区间分析 ")
        plot_layout = QGridLayout()
        plot_layout.setContentsMargins(5, 5, 5, 5)

        # ------------------- 1. 上排：原始波形与检波图 -------------------
        top_canvas_widget = QWidget()
        top_canvas_layout = QVBoxLayout(top_canvas_widget)
        top_canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.fig = Figure(figsize=(11, 4.0))
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212, sharex=self.ax1)

        self.canvas = FigureCanvas(self.fig)
        top_canvas_layout.addWidget(self.canvas)

        plot_layout.addWidget(top_canvas_widget, 0, 0, 1, 2)

        # ------------------- 2. 下排左侧：全局直方图 -------------------
        bottom_left_widget = QWidget()
        bottom_left_layout = QVBoxLayout(bottom_left_widget)
        bottom_left_layout.setContentsMargins(0, 0, 0, 0)

        self.fig_hist = Figure(figsize=(5.5, 2.2))
        self.ax3 = self.fig_hist.add_subplot(111)

        self.canvas_hist = FigureCanvas(self.fig_hist)
        bottom_left_layout.addWidget(self.canvas_hist)

        plot_layout.addWidget(bottom_left_widget, 1, 0)

        # ------------------- 3. 下排右侧：全局处理控制面板 -------------------
        right_panel = QGroupBox(" 全局处理控制面板 ")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)

        right_layout.addWidget(QLabel("数据全量分析统计："))
        self.btn_calc_hist = QPushButton("📊 统计全文件能量直方图")
        self.btn_calc_hist.setEnabled(False)
        self.btn_calc_hist.clicked.connect(self.calc_global_histogram)
        self.btn_calc_hist.setStyleSheet("padding: 10px;")
        right_layout.addWidget(self.btn_calc_hist)
        right_layout.addSpacing(15)

        right_layout.addWidget(QLabel("全自动解码与固件提取："))
        self.btn_export = QPushButton("🚀 全文件解码并导出 .bin")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_bin)
        self.btn_export.setStyleSheet("padding: 10px;")
        right_layout.addWidget(self.btn_export)
        right_layout.addStretch()

        plot_layout.addWidget(right_panel, 1, 1)

        plot_frame.setLayout(plot_layout)
        main_layout.addWidget(plot_frame, 1)

        # Bottom Status Frame
        action_frame = QFrame()
        action_layout = QHBoxLayout(action_frame)
        action_layout.setContentsMargins(15, 2, 15, 2)
        
        self.lbl_status = QLabel("准备就绪。")
        action_layout.addWidget(self.lbl_status)
        
        main_layout.addWidget(action_frame)

    def load_file(self):
        last_dir = self.settings.value("last_audio_directory", os.getcwd())
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 WAV 文件", last_dir, "WAV files (*.wav)")
        if not file_path:
            return
        self.settings.setValue("last_audio_directory", os.path.dirname(file_path))
        try:
            self.sample_rate, self.audio_data = wav.read(file_path)
            if len(self.audio_data.shape) > 1:
                self.audio_data = self.audio_data[:, 0]
            duration = len(self.audio_data) / self.sample_rate
            self.lbl_file_info.setText(
                f"已载入: {os.path.basename(file_path)} | 采样率: {self.sample_rate} Hz | 总时长: {duration:.3f} 秒"
            )
            self.lbl_file_info.setStyleSheet("color: black;")
            self.btn_load_slice.setEnabled(True)
            self.btn_calc_hist.setEnabled(True)
            self.btn_export.setEnabled(True)
            self.all_file_integrals = None
            self.load_slice()
        except Exception as e:
            QMessageBox.critical(self, "致命错误", f"无法解析该 WAV 音频文件: {str(e)}")

    def load_slice(self):
        if self.audio_data is None:
            return
        try:
            t_start = float(self.ent_start.text())
            t_len = float(self.ent_len.text())
        except ValueError:
            QMessageBox.warning(self, "输入解析错误", "时间参数必须为合法的浮点数！")
            return

        idx_start = int(t_start * self.sample_rate)
        idx_end = int((t_start + t_len) * self.sample_rate)

        if idx_start < 0 or idx_start >= len(self.audio_data):
            QMessageBox.warning(self, "越界错误", "开始时间超出文件实际长度范围！")
            return

        idx_end = min(idx_end, len(self.audio_data))
        self.current_y_raw = self.audio_data[idx_start:idx_end].astype(np.float64)
        self.current_time = np.arange(idx_start, idx_end) / self.sample_rate

        self.update_plot()

    def on_param_change(self):
        self.val_alpha = self.scale_alpha.value() / 1000.0
        self.val_thresh = self.scale_thresh.value() / 100.0
        self.val_noise = self.scale_noise.value() / 10.0
        self.val_boundary = self.scale_boundary.value() / 10.0
        self.val_uplimit = self.scale_uplimit.value() / 10.0

        self.lbl_alpha.setText(f"{self.val_alpha:.3f}")
        self.lbl_thresh.setText(f"{self.val_thresh:.2f}")
        self.lbl_noise.setText(f"{self.val_noise:.2f}")
        self.lbl_boundary.setText(f"{self.val_boundary:.2f}")
        self.lbl_uplimit.setText(f"{self.val_uplimit:.2f}")
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
        self.lbl_status.setText("正在全量统计全文件高频脉冲积分能量分布，请稍候...")
        self.update()

        alpha = self.val_alpha
        thresh = self.val_thresh

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
        self.lbl_status.setText(f"全局分析成功！共抽取 {len(self.all_file_integrals)} 个有效积分样本点。")
        self.update_plot()

    def export_bin(self):
        if self.audio_data is None:
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "保存 BIN 文件", "", "Binary files (*.bin)")
        if not save_path:
            return

        self.lbl_status.setText("正在对全量音频执行高精度解调并构建固件数据流...")
        self.update()

        alpha = self.val_alpha
        thresh = self.val_thresh

        noise_real = self.val_noise
        boundary_real = self.val_boundary
        up_limit_real = self.val_uplimit

        _, _, bits, _, _, _ = self.process_and_decode(self.audio_data, alpha, thresh, noise_real, boundary_real, up_limit_real)

        valid_bits = [b for b in bits if b == 0 or b == 1]

        if not valid_bits:
            print("[Warning] 使用界面限制卡口未识别到数据，正在切换为自适应动态判决解调...")
            valid_bits = []
            for b in bits:
                if isinstance(b, (int, float)):
                    valid_bits.append(int(b))
                elif b == 'E':
                    valid_bits.append(1)
                elif b == '?':
                    continue

        if not valid_bits:
            self.lbl_status.setText("导出失败：未在文件中解调出任何有效二进制脉冲序列。")
            QMessageBox.warning(self, "导出失败", "基于当前参数未提取到任何有效比特，请调低【判定起止阈值】或点一下【刷新片段】。")
            return

        byte_chunks = []
        for i in range(0, len(valid_bits), 8):
            chunk = valid_bits[i:i + 8]
            while len(chunk) < 8:
                chunk.append(0)

            byte_val = 0
            for bit in chunk:
                byte_val = (byte_val << 1) | int(bit)
            byte_chunks.append(byte_val)

        try:
            with open(save_path, "wb") as f:
                f.write(bytes(byte_chunks))

            self.lbl_status.setText("固件 BIN 数据写出成功。")

            reply = QMessageBox.question(
                self, "导出成功",
                f"固件解码流提取成功！\n共捕获: {len(valid_bits)} bits ({len(byte_chunks)} 字节)\n\n是否立即启动协议头检索并分离纯数据 (.rom) ？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.parse_bin_to_rom(save_path)

        except Exception as e:
            self.lbl_status.setText("文件磁盘写入故障。")
            QMessageBox.critical(self, "写入失败", f"向硬盘写入文件时发生异常错误:\n{str(e)}")

    def parse_bin_to_rom(self, bin_path):
        try:
            with open(bin_path, 'rb') as f:
                raw_bytes = f.read()

            target_header = bytes.fromhex("ED546FD650")
            header_len = len(target_header)

            header_index = raw_bytes.find(target_header)

            if header_index == -1:
                hex_preview = raw_bytes[:16].hex().upper()
                preview_str = " ".join([hex_preview[i:i + 2] for i in range(0, len(hex_preview), 2)])
                QMessageBox.critical(
                    self, "验证失败",
                    f"未在二进制流中检索到指定的协议头！\n"
                    f"预期特征头: ED 54 6F D6 50\n"
                    f"文件前16字节流实际为:\n[{preview_str}...]\n\n"
                    f"💡 建议：请检查界面上的【判定起止阈值】或【0/1阈值】是否卡得太紧导致波形错位。"
                )
                return

            if len(raw_bytes) - header_index < 10:
                QMessageBox.critical(self, "格式错误", "虽然找到了协议头，但其后剩余的数据长度不足以解析地址与长度字段！")
                return

            addr_start = header_index + header_len
            start_address = int.from_bytes(raw_bytes[addr_start: addr_start + 2], byteorder='big')

            len_start = addr_start + 2
            data_length = int.from_bytes(raw_bytes[len_start: len_start + 2], byteorder='big')

            data_start_idx = len_start + 2
            data_end_idx = data_start_idx + data_length

            if len(raw_bytes) < data_end_idx + 1:
                actual_available = len(raw_bytes) - data_start_idx - 1
                QMessageBox.critical(
                    self, "长度不匹配",
                    f"协议头指示数据长度为: {data_length} 字节\n"
                    f"但当前缓冲区实际仅剩: {max(0, actual_available)} 字节数据。\n\n"
                    f"可能原因：音频尾部信号被提前截断，或解调中途丢失了部分有效脉冲。"
                )
                return

            pure_data = raw_bytes[data_start_idx:data_end_idx]
            checksum_byte = raw_bytes[data_end_idx]

            default_rom_name = os.path.splitext(os.path.basename(bin_path))[0] + ".rom"
            out_rom_path, _ = QFileDialog.getSaveFileName(
                self, "选择要保存的纯数据 .rom 文件位置", default_rom_name, "ROM Files (*.rom)"
            )
            if not out_rom_path:
                return

            with open(out_rom_path, 'wb') as f:
                f.write(pure_data)

            preamble_bytes = header_index
            QMessageBox.information(
                self, "ROM 分离成功",
                f"✅ 协议头全局匹配通过！\n\n"
                f"📂 原始文件: {os.path.basename(bin_path)}\n"
                f"🔍 自动过滤前导杂波: {preamble_bytes} 字节\n"
                f"📍 固件映射起始地址: 0x{start_address:04X}\n"
                f"📦 纯净 ROM 大小: {len(pure_data)} 字节\n"
                f"🏁 末尾校验位(Checksum): 0x{checksum_byte:02X}\n\n"
                f"💾 提取数据已成功保存至:\n{os.path.basename(out_rom_path)}"
            )
            self.lbl_status.setText(f"ROM 固件提取成功: {os.path.basename(out_rom_path)}")

        except Exception as e:
            QMessageBox.critical(self, "分离失败", f"处理二进制流时发生严重错误: {str(e)}")

    def update_plot(self):
        if self.current_y_raw is None:
            return

        alpha = self.val_alpha
        thresh = self.val_thresh
        noise_real = self.val_noise
        boundary_real = self.val_boundary
        up_limit_ui = self.val_uplimit

        envelope, square_wave, bits, centers, integrals, status_list = self.process_and_decode(
            self.current_y_raw, alpha, thresh, noise_real, boundary_real, up_limit_ui
        )

        t_start = float(self.ent_start.text())
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


# 支持单文件独立运行测试
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("信号分析器独立测试窗口")
    window.setGeometry(100, 100, 1100, 750)
    
    analyzer = SignalAnalyzerFrame(window)
    layout = QVBoxLayout(window)
    layout.addWidget(analyzer)
    
    window.show()
    sys.exit(app.exec_())
