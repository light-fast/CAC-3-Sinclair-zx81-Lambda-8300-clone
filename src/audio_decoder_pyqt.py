import os
import struct
import numpy as np
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QLineEdit, QPushButton, QComboBox, QSlider,
                             QGroupBox, QFileDialog, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtGui import QFont

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from scipy.io import wavfile

# 设置 Matplotlib 支持中文
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "Arial Unicode MS",
]
plt.rcParams["axes.unicode_minus"] = False


class AudioDecoderFrame(QWidget):
    """独立的音频解码与信号分析组件类"""

    def __init__(self, parent=None, root_app=None):
        super().__init__(parent)
        self.root_app = root_app
        self.settings = QSettings("CAC3Tools", "PyQtVersion")

        # 信号基础数据
        self.raw = None
        self.t = None
        self.fs = None
        self.total_time = 0
        self.filename = None
        self._updating = False

        # 解码参数
        self.noise_thresh = 0.14
        self.rc_alpha = 0.1
        self.low_bond = 0.2
        self.bit_thresh = 2.4
        self.high_bond = 4.0
        self.min_gap = 0.0004
        self.area_thresh = 1.2

        self.envelope_type = "rc"
        self.bit_decision_method = "width"

        # 处理窗口参数
        self.data_start = 0.0
        self.data_window = 0.1

        # 数据缓存
        self.raw_widths = np.array([])
        self.raw_areas = np.array([])
        self.raw_centers = np.array([])
        self.widths = np.array([])
        self.areas = np.array([])
        self.bits = np.array([])
        self.bit_wave = np.zeros(0)
        self.bit_centers = np.array([])
        self.envelope = np.zeros(0)
        self.binary_wave = np.zeros(0)

        # 直方图缓存
        self.hist_widths = None
        self.hist_areas = None
        self.hist_data_valid = False

        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 左侧 Matplotlib 绘图区
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.ax_orig = self.fig.add_subplot(3, 1, 1)
        self.ax_rect = self.fig.add_subplot(3, 1, 2, sharex=self.ax_orig)
        self.ax_area = self.fig.add_subplot(3, 1, 3, sharex=self.ax_orig)

        self.canvas = FigureCanvas(self.fig)
        left_layout.addWidget(self.canvas)
        
        toolbar = NavigationToolbar(self.canvas, left_widget)
        left_layout.addWidget(toolbar)

        main_layout.addWidget(left_widget, 2)

        # 右侧控制面板
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(5, 5, 5, 5)
        control_layout.setSpacing(5)

        self.filename_label = QLabel("未加载文件")
        self.filename_label.setFont(QFont("Consolas", 9, QFont.Bold))
        self.filename_label.setWordWrap(True)
        control_layout.addWidget(self.filename_label)

        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Consolas", 8))
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray;")
        control_layout.addWidget(self.info_label)

        # 窗口参数设置
        window_frame = QGroupBox("窗口参数")
        window_layout = QHBoxLayout()
        
        window_layout.addWidget(QLabel("数据起始:"))
        self.data_start_var = QLineEdit("0.0")
        self.data_start_var.setFixedWidth(60)
        self.data_start_var.editingFinished.connect(self.on_window_params_changed)
        window_layout.addWidget(self.data_start_var)
        
        window_layout.addWidget(QLabel("窗口:"))
        self.data_window_var = QLineEdit("0.1")
        self.data_window_var.setFixedWidth(60)
        self.data_window_var.editingFinished.connect(self.on_window_params_changed)
        window_layout.addWidget(self.data_window_var)
        
        window_frame.setLayout(window_layout)
        control_layout.addWidget(window_frame)

        # 包络模式选择
        env_frame = QGroupBox("包络类型")
        env_layout = QHBoxLayout()
        
        env_layout.addWidget(QLabel("包络类型:"))
        self.env_combo = QComboBox()
        self.env_combo.addItems(["RC包络", "峰值包络"])
        self.env_combo.setCurrentText("RC包络")
        self.env_combo.currentTextChanged.connect(self.on_envelope_type_changed)
        env_layout.addWidget(self.env_combo)
        
        env_frame.setLayout(env_layout)
        control_layout.addWidget(env_frame)

        # 判决模式选择
        decision_frame = QGroupBox("0/1判断方法")
        decision_layout = QHBoxLayout()
        
        decision_layout.addWidget(QLabel("判断方法:"))
        self.decision_combo = QComboBox()
        self.decision_combo.addItems(["宽度阈值", "积分面积"])
        self.decision_combo.setCurrentText("宽度阈值")
        self.decision_combo.currentTextChanged.connect(self.on_decision_method_changed)
        decision_layout.addWidget(self.decision_combo)
        
        decision_frame.setLayout(decision_layout)
        control_layout.addWidget(decision_frame)

        # 参数滑块与输入框
        self.params_frame = QGroupBox("解码参数")
        params_layout = QVBoxLayout()
        
        self.params = [
            ("噪声幅度", "noise_thresh", 0, 0.5, 0.14, 0.005),
            ("RC α", "rc_alpha", 0.001, 0.5, 0.1, 0.001),
            ("最小宽度", "low_bond", 0, 3.0, 0.2, 0.01),
            ("0/1阈值", "bit_thresh", 0, 5.0, 2.4, 0.01),
            ("最大宽度", "high_bond", 0.5, 10.0, 4.0, 0.01),
            ("合并间隔", "min_gap", 0.1, 5, 0.4, 0.1),
        ]
        self.slider_attrs = {}
        self.slider_vars = {}
        self.entry_vars = {}
        self.sliders = {}
        self.entries = {}
        self.param_frames = {}

        for idx, (label, attr, vmin, vmax, vinit, step) in enumerate(self.params):
            param_row = QHBoxLayout()
            
            lbl = QLabel(label)
            lbl.setFixedWidth(80)
            param_row.addWidget(lbl)

            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(int(vmin * 1000))
            slider.setMaximum(int(vmax * 1000))
            slider.setValue(int(vinit * 1000))
            slider.valueChanged.connect(lambda val, a=attr: self.on_slider_changed(a, val))
            param_row.addWidget(slider, 1)
            self.sliders[attr] = slider

            entry = QLineEdit(f"{vinit:.3f}" if attr != "min_gap" else f"{vinit:.1f}")
            entry.setFixedWidth(50)
            entry.editingFinished.connect(lambda a=attr: self.on_entry_enter(a))
            param_row.addWidget(entry)
            self.entries[attr] = entry

            params_layout.addLayout(param_row)

            self.slider_attrs[attr] = {
                "label": label,
                "vmin": vmin,
                "vmax": vmax,
                "vinit": vinit,
                "step": step,
            }

        self.params_frame.setLayout(params_layout)
        control_layout.addWidget(self.params_frame)

        # 操作按钮区
        btn_frame = QGroupBox("操作")
        btn_layout = QVBoxLayout()
        
        self.btn_load = QPushButton("载入 WAV 音频")
        self.btn_load.clicked.connect(self.load_new_file)
        btn_layout.addWidget(self.btn_load)
        
        self.btn_reset = QPushButton("重置解码参数")
        self.btn_reset.clicked.connect(self.reset)
        btn_layout.addWidget(self.btn_reset)
        
        self.btn_save = QPushButton("保存为 BIN 文件")
        self.btn_save.clicked.connect(self.save_bin)
        btn_layout.addWidget(self.btn_save)
        
        self.btn_export = QPushButton("生成 ROM 文件")
        self.btn_export.clicked.connect(self.export_rom)
        btn_layout.addWidget(self.btn_export)
        
        btn_frame.setLayout(btn_layout)
        control_layout.addWidget(btn_frame)

        # 直方图预览
        hist_frame = QGroupBox("全文件脉冲分布直方图")
        hist_layout = QVBoxLayout()

        self.hist_fig = Figure(figsize=(4, 2), dpi=80)
        self.hist_fig.subplots_adjust(left=0.12, right=0.95, top=0.90, bottom=0.20)
        self.hist_ax = self.hist_fig.add_subplot(111)
        self.hist_ax.text(
            0.5, 0.5, "点击下方按钮刷新",
            ha="center", va="center", transform=self.hist_ax.transAxes
        )
        self.hist_ax.set_title("分布直方图")

        self.hist_canvas = FigureCanvas(self.hist_fig)
        hist_layout.addWidget(self.hist_canvas)
        
        self.btn_refresh_hist = QPushButton("刷新直方图")
        self.btn_refresh_hist.clicked.connect(self.refresh_histogram)
        hist_layout.addWidget(self.btn_refresh_hist)
        
        hist_frame.setLayout(hist_layout)
        control_layout.addWidget(hist_frame, 1)

        main_layout.addWidget(control_widget, 1)

        # 快捷联动事件
        self.ax_orig.callbacks.connect("xlim_changed", self.on_xlim_change)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.mpl_connect("button_release_event", self.on_button_release)

    # ---------- 事件处理与图形控制 ----------
    def on_envelope_type_changed(self, text):
        self.envelope_type = "rc" if text == "RC包络" else "peak"
        self.hist_data_valid = False
        if self.raw is not None:
            self.update_all_and_plot()
            self.update_histogram()

    def on_decision_method_changed(self, text):
        self.bit_decision_method = "width" if text == "宽度阈值" else "area"
        self.hist_data_valid = False
        if self.bit_decision_method == "width":
            self._update_slider_for_width()
            self.ax_area.set_ylabel("脉冲宽度")
        else:
            self._update_slider_for_area()
            self.ax_area.set_ylabel("脉冲面积 (幅度·ms)")
            self.ax_area.set_title("脉冲面积随时间分布")
        if self.raw is not None:
            self.refresh_histogram()
            self.plot_all()

    def _update_slider_for_width(self):
        self._apply_slider_config("low_bond", "最小宽度", 0, 3.0, 0.2, 0.01)
        self._apply_slider_config("bit_thresh", "0/1阈值", 0, 5.0, 2.4, 0.01)
        self._apply_slider_config("high_bond", "最大宽度", 0.5, 10.0, 4.0, 0.01)
        self.low_bond = 0.2
        self.bit_thresh = 2.4
        self.high_bond = 4.0
        self.area_thresh = self.bit_thresh
        self.sliders["bit_thresh"].setValue(int(2.4 * 1000))
        self.entries["bit_thresh"].setText("2.400")

    def _update_slider_for_area(self):
        self._apply_slider_config("low_bond", "最小面积", 0, 1.0, 0.5, 0.01)
        self._apply_slider_config("bit_thresh", "面积阈值", 0, 3.0, 1.2, 0.01)
        self._apply_slider_config("high_bond", "最大面积", 0.5, 4.0, 2.0, 0.01)
        self.low_bond = 0.5
        self.bit_thresh = 1.2
        self.high_bond = 2.0
        self.area_thresh = self.bit_thresh
        self.sliders["bit_thresh"].setValue(int(1.2 * 1000))
        self.entries["bit_thresh"].setText("1.200")

    def _apply_slider_config(self, attr, label, vmin, vmax, vinit, step):
        slider = self.sliders[attr]
        slider.setMinimum(int(vmin * 1000))
        slider.setMaximum(int(vmax * 1000))
        slider.setValue(int(vinit * 1000))
        self.entries[attr].setText(f"{vinit:.3f}")
        self.slider_attrs[attr]["vmin"] = vmin
        self.slider_attrs[attr]["vmax"] = vmax
        self.slider_attrs[attr]["vinit"] = vinit
        self.slider_attrs[attr]["label"] = label

    def on_window_params_changed(self):
        try:
            start = float(self.data_start_var.text())
            window = float(self.data_window_var.text())
            if window <= 0:
                window = 0.1
            self.data_start = start
            self.data_window = window
            if self.raw is not None:
                self.update_all_and_plot()
        except ValueError:
            pass

    def on_slider_changed(self, attr, value):
        val = value / 1000.0
        if attr == "min_gap":
            self.entries[attr].setText(f"{val:.1f}")
            setattr(self, attr, val)
        else:
            self.entries[attr].setText(f"{val:.3f}")
            setattr(self, attr, val)
            if attr == "bit_thresh" and self.bit_decision_method == "area":
                self.area_thresh = val
        self.update_all_and_plot()
        self.plot_histogram()
        self.canvas.draw_idle()
        self.hist_canvas.draw_idle()

    def on_entry_enter(self, attr):
        try:
            val = float(self.entries[attr].text())
            slider = self.sliders[attr]
            vmin = slider.minimum() / 1000.0
            vmax = slider.maximum() / 1000.0
            if val < vmin:
                val = vmin
            elif val > vmax:
                val = vmax
            slider.setValue(int(val * 1000))
            if attr == "min_gap":
                setattr(self, attr, val)
            else:
                setattr(self, attr, val)
                if attr == "bit_thresh" and self.bit_decision_method == "area":
                    self.area_thresh = val
            if attr == "min_gap":
                self.entries[attr].setText(f"{val:.1f}")
            else:
                self.entries[attr].setText(f"{val:.3f}")
            self.update_all_and_plot()
            self.plot_histogram()
            self.canvas.draw_idle()
            self.hist_canvas.draw_idle()
        except ValueError:
            pass

    def on_xlim_change(self, event):
        if self.raw is not None and not self._updating:
            QTimer.singleShot(10, self.plot_all)

    def on_scroll(self, event):
        if event.inaxes is None:
            return
        ax = event.inaxes
        xmin, xmax = ax.get_xlim()
        scale = 0.9 if event.button == "up" else 1.1
        center = (xmin + xmax) / 2
        new_w = (xmax - xmin) * scale
        ax.set_xlim(center - new_w / 2, center + new_w / 2)
        self.plot_all()

    def on_button_release(self, event):
        if self.raw is not None:
            self.canvas.draw_idle()

    # ---------- 音频分析算法 ----------
    def load_file(self, filename):
        fs, data = wavfile.read(filename)
        self.fs = fs
        if len(data.shape) > 1:
            channels = data.shape[1]
            data = data[:, 0]
        else:
            channels = 1
        self.raw = data.astype(np.float64)
        self.raw /= np.max(np.abs(self.raw)) + 1e-8
        self.t = np.arange(len(self.raw)) / fs
        self.total_time = len(self.raw) / fs
        self.filename = filename
        self.filename_label.setText(os.path.basename(filename))
        self.info_label.setText(
            f"采样率: {fs} Hz | 声道: {channels} | 时长: {self.total_time:.2f} s"
        )
        self.data_start = 0.0
        self.data_window = min(0.1, self.total_time)
        self.data_start_var.setText("0.0")
        self.data_window_var.setText(f"{self.data_window:.3f}")
        self.hist_data_valid = False
        self.update_all_and_plot()
        self.update_histogram()

    def rc_filter(self, data, alpha):
        filtered = np.zeros_like(data)
        for i in range(len(data)):
            filtered[i] = alpha * data[i] + (1 - alpha) * (filtered[i - 1] if i > 0 else 0)
        return filtered

    def peak_envelope(self, data, smooth_ms=0.15):
        window_samples = int(smooth_ms / 1000.0 * self.fs)
        if window_samples < 1:
            window_samples = 1
        max_vals = np.zeros_like(data)
        half = window_samples // 2
        for i in range(len(data)):
            start = max(0, i - half)
            end = min(len(data), i + half + 1)
            max_vals[i] = np.max(data[start:end])
        return max_vals

    def get_envelope(self, rect):
        if self.envelope_type == "rc":
            return self.rc_filter(rect, self.rc_alpha)
        else:
            return self.peak_envelope(rect)

    def detect_bursts_by_envelope(self, data, thresh, min_gap_sec):
        rect = np.abs(data)
        envelope = self.get_envelope(rect)
        binary = (envelope > thresh).astype(np.float64)
        widths, centers, binary_out, starts, ends = (
            self._merge_bursts_with_indices(binary, envelope, min_gap_sec)
        )
        areas = []
        for s, e in zip(starts, ends):
            area = np.sum(envelope[s:e]) * (1000.0 / self.fs)
            areas.append(area)
        areas = np.array(areas)
        return widths, centers, areas, envelope, binary_out, thresh

    def _merge_bursts_with_indices(self, binary, signal, min_gap_sec):
        diff = np.diff(binary.astype(np.int8))
        start_idx = np.where(diff == 1)[0] + 1
        end_idx = np.where(diff == -1)[0] + 1
        if binary[0] == 1:
            start_idx = np.concatenate(([0], start_idx))
        if binary[-1] == 1:
            end_idx = np.concatenate((end_idx, [len(binary)]))
        if len(start_idx) != len(end_idx):
            min_len = min(len(start_idx), len(end_idx))
            start_idx = start_idx[:min_len]
            end_idx = end_idx[:min_len]
        merged_starts = []
        merged_ends = []
        for i in range(len(start_idx)):
            if i == 0:
                merged_starts.append(start_idx[i])
                merged_ends.append(end_idx[i])
            else:
                gap = start_idx[i] - merged_ends[-1]
                if gap / self.fs <= min_gap_sec:
                    merged_ends[-1] = end_idx[i]
                else:
                    merged_starts.append(start_idx[i])
                    merged_ends.append(end_idx[i])
        widths = []
        centers = []
        binary_out = np.zeros_like(binary)
        for s, e in zip(merged_starts, merged_ends):
            duration_s = (e - s) / self.fs
            duration_ms = duration_s * 1000.0
            widths.append(duration_ms)
            centers.append(((s + e) / 2) / self.fs)
            binary_out[s:e] = 1
        return (
            np.array(widths),
            np.array(centers),
            binary_out,
            np.array(merged_starts),
            np.array(merged_ends),
        )

    def update_all_and_plot(self):
        if self.raw is None or self._updating:
            return
        self._updating = True
        try:
            win_start = max(self.data_start, 0.0)
            win_end = min(self.data_start + self.data_window, self.total_time)
            if win_start >= win_end:
                self.raw_widths = np.array([])
                self.raw_areas = np.array([])
                self.raw_centers = np.array([])
                self.widths = np.array([])
                self.areas = np.array([])
                self.bits = np.array([])
                self.bit_wave = np.zeros(len(self.raw))
                self.bit_centers = np.array([])
                self.envelope = np.zeros(len(self.raw))
                self.binary_wave = np.zeros(len(self.raw))
                self.plot_all()
                self.canvas.draw_idle()
                return

            start_idx = int(win_start * self.fs)
            end_idx = int(win_end * self.fs)
            start_idx = max(0, start_idx)
            end_idx = min(len(self.raw), end_idx)
            data_slice = self.raw[start_idx:end_idx]

            (
                raw_widths,
                raw_centers_rel,
                raw_areas,
                envelope,
                binary,
                actual_thresh,
            ) = self.detect_bursts_by_envelope(
                data_slice, self.noise_thresh, self.min_gap
            )
            self.current_thresh = actual_thresh

            abs_centers = raw_centers_rel + win_start
            self.raw_widths = raw_widths
            self.raw_areas = raw_areas
            self.raw_centers = abs_centers

            if self.bit_decision_method == "width":
                valid_mask = (raw_widths > self.low_bond) & (raw_widths < self.high_bond)
            else:
                valid_mask = (raw_areas > self.low_bond) & (raw_areas < self.high_bond)

            if len(raw_widths) > 0:
                self.widths = raw_widths[valid_mask]
                self.areas = raw_areas[valid_mask]
                self.bit_centers = abs_centers[valid_mask]
            else:
                self.widths = np.array([])
                self.areas = np.array([])
                self.bit_centers = np.array([])

            if self.bit_decision_method == "width":
                bits = np.zeros(len(raw_widths))
                for i, w in enumerate(raw_widths):
                    bits[i] = 1 if w >= self.bit_thresh else 0
                valid_bits = bits[valid_mask] if len(raw_widths) > 0 else np.array([])
            else:
                bits = np.zeros(len(raw_areas))
                for i, a in enumerate(raw_areas):
                    bits[i] = 1 if a >= self.area_thresh else 0
                valid_bits = bits[valid_mask] if len(raw_areas) > 0 else np.array([])

            self.bits = valid_bits

            full_envelope = np.zeros(len(self.raw))
            full_envelope[start_idx:end_idx] = envelope
            self.envelope = full_envelope
            full_binary = np.zeros(len(self.raw))
            full_binary[start_idx:end_idx] = binary
            self.binary_wave = full_binary

            bit_wave = np.zeros(len(self.raw))
            if len(self.bit_centers) > 0:
                half_width = int(0.0005 * self.fs)
                for i, center in enumerate(self.bit_centers):
                    idx = int(center * self.fs)
                    start = max(0, idx - half_width)
                    end = min(len(self.raw), idx + half_width)
                    bit_wave[start:end] = 1.0 if self.bits[i] == 1 else -1.0
            self.bit_wave = bit_wave

            self.plot_all()
            self.ax_orig.set_xlim(win_start, win_end)
            self.canvas.draw_idle()
        finally:
            self._updating = False

    def plot_all(self):
        if self.raw is None:
            return
        xlim = self.ax_orig.get_xlim()
        win_start = max(self.data_start, xlim[0])
        win_end = min(self.data_start + self.data_window, xlim[1])
        if win_start >= win_end:
            self.ax_orig.clear()
            self.ax_rect.clear()
            self.ax_area.clear()
            return

        start_idx = int((win_start) * self.fs)
        end_idx = int((win_end) * self.fs)
        start_idx = max(0, start_idx)
        end_idx = min(len(self.raw), end_idx)
        t_slice = self.t[start_idx:end_idx]
        raw_slice = self.raw[start_idx:end_idx]

        self.ax_orig.clear()
        self.ax_orig.plot(t_slice, raw_slice, "b-", lw=0.6, label="原始信号")
        if len(self.bit_wave) > 0:
            bit_slice = self.bit_wave[start_idx:end_idx]
            self.ax_orig.plot(t_slice, bit_slice, "g-", lw=1.5, alpha=0.7, label="解码 0/1")
        self.ax_orig.set_ylabel("幅度")
        self.ax_orig.legend(loc="upper right")
        self.ax_orig.grid(alpha=0.3)
        self.ax_orig.set_title("原始信号与解码结果")

        self.ax_rect.clear()
        rect_slice = np.abs(raw_slice)
        self.ax_rect.plot(t_slice, rect_slice, "c-", lw=0.5, alpha=0.3, label="整流")
        env_slice = self.envelope[start_idx:end_idx]
        env_label = "峰值包络" if self.envelope_type == "peak" else "RC包络"
        self.ax_rect.plot(t_slice, env_slice, "m-", lw=1.5, label=env_label)
        if hasattr(self, "current_thresh"):
            self.ax_rect.axhline(
                y=self.current_thresh,
                color="r",
                linestyle="--",
                alpha=0.5,
                label=f"阈值 {self.current_thresh:.3f}",
            )
        binary_slice = self.binary_wave[start_idx:end_idx]
        if np.any(binary_slice):
            binary_display = 0.5 + binary_slice
            self.ax_rect.step(
                t_slice, binary_display, "r-", lw=1.2, where="post", label="二值化方波"
            )
        self.ax_rect.set_ylabel("幅度")
        self.ax_rect.legend(loc="upper right")
        self.ax_rect.grid(alpha=0.3)
        self.ax_rect.set_title("包络检波与二值化方波")

        self.ax_area.clear()
        if self.bit_decision_method == "width":
            data_values = self.raw_widths
            ylabel = "脉冲宽度"
            xlim_cur = self.ax_area.get_xlim()
            if xlim_cur[0] != xlim_cur[1]:
                self.ax_area.plot(xlim_cur, [self.low_bond, self.low_bond], "b--", label="最小宽度")
                self.ax_area.plot(xlim_cur, [self.bit_thresh, self.bit_thresh], "r--", label="0/1阈值")
                self.ax_area.plot(xlim_cur, [self.high_bond, self.high_bond], "g--", label="最大宽度")
            ymax = max(np.max(data_values), 0.01) if len(data_values) > 0 else 5.0
            self.ax_area.set_ylim(0, ymax * 1.2)
        else:
            data_values = self.raw_areas
            ylabel = "脉冲面积 (幅度·ms)"
            xlim_cur = self.ax_area.get_xlim()
            if xlim_cur[0] != xlim_cur[1]:
                self.ax_area.plot(xlim_cur, [self.low_bond, self.low_bond], "b--", label="最小面积")
                self.ax_area.plot(xlim_cur, [self.area_thresh, self.area_thresh], "r--", label="面积阈值")
                self.ax_area.plot(xlim_cur, [self.high_bond, self.high_bond], "g--", label="最大面积")
            ymax = max(np.max(data_values), 0.01) if len(data_values) > 0 else 5.0
            self.ax_area.set_ylim(0, ymax * 1.2)

        if len(self.raw_centers) > 0:
            mask = (self.raw_centers >= win_start) & (self.raw_centers <= win_end)
            centers_vis = self.raw_centers[mask]
            values_vis = data_values[mask]
            if len(centers_vis) > 0:
                self.ax_area.stem(
                    centers_vis, values_vis, basefmt=" ", linefmt="gray", markerfmt="rx",
                    label=f"全部检测 ({len(centers_vis)}个)"
                )
        if len(self.bit_centers) > 0:
            mask = (self.bit_centers >= win_start) & (self.bit_centers <= win_end)
            centers_bit = self.bit_centers[mask]
            if self.bit_decision_method == "width":
                values_bit = self.widths[mask] if len(self.widths) > 0 else np.array([])
            else:
                values_bit = self.areas[mask] if len(self.areas) > 0 else np.array([])
            if len(centers_bit) > 0:
                self.ax_area.stem(
                    centers_bit, values_bit, basefmt=" ", linefmt="k-", markerfmt="ko",
                    label=f"有效位 ({len(centers_bit)}个)"
                )

        self.ax_area.set_xlabel("时间 (秒)")
        self.ax_area.set_ylabel(ylabel)
        self.ax_area.legend(loc="upper right")
        self.ax_area.grid(alpha=0.3)
        self.ax_area.set_title(f"脉冲{ylabel}随时间分布")

        self.fig.tight_layout(pad=0.5, h_pad=0.3, w_pad=0.3)
        self.canvas.draw_idle()

    # ---------- 直方图方法 ----------
    def refresh_histogram(self):
        if self.raw is None:
            return
        widths, _, areas, _, _, _ = self.detect_bursts_by_envelope(
            self.raw, self.noise_thresh, self.min_gap
        )
        self.hist_widths = widths
        self.hist_areas = areas
        self.hist_data_valid = True
        self.plot_histogram()

    def plot_histogram(self):
        if self.raw is None:
            return
        if not self.hist_data_valid:
            self.hist_ax.clear()
            self.hist_ax.text(
                0.5, 0.5, "请点击「刷新直方图」按钮",
                ha="center", va="center", transform=self.hist_ax.transAxes
            )
            self.hist_ax.set_title("无有效数据")
            self.hist_fig.tight_layout(pad=0.5)
            self.hist_canvas.draw_idle()
            return

        if self.bit_decision_method == "width":
            data = self.hist_widths
            xlabel = "脉冲宽度"
            low = self.low_bond
            high = self.high_bond
            thresh = self.bit_thresh
            valid_mask = (data > low) & (data < high)
        else:
            data = self.hist_areas
            xlabel = "脉冲面积 (幅度·ms)"
            low = self.low_bond
            high = self.high_bond
            thresh = self.area_thresh
            valid_mask = (data > low) & (data < high)

        filtered = data[valid_mask] if len(data) > 0 else np.array([])

        self.hist_ax.clear()
        if len(data) == 0 or len(filtered) == 0:
            self.hist_ax.text(
                0.5, 0.5, "无有效数据",
                ha="center", va="center", transform=self.hist_ax.transAxes
            )
            self.hist_ax.set_title("无有效数据")
        else:
            self.hist_ax.hist(filtered, bins=50, alpha=0.7, color="green", edgecolor="black")
            x_max = high * 1.1 if high > 0 else 1.0
            self.hist_ax.set_xlim(left=0, right=x_max)
            self.hist_ax.axvline(x=low, color="blue", linestyle="--", linewidth=2, label=f"下界 {low:.2f}")
            self.hist_ax.axvline(x=thresh, color="red", linestyle="--", linewidth=2, label=f"阈值 {thresh:.2f}")
            self.hist_ax.axvline(x=high, color="purple", linestyle="--", linewidth=2, label=f"上界 {high:.2f}")
            self.hist_ax.set_xlabel(xlabel)
            self.hist_ax.set_ylabel("频次")
            self.hist_ax.set_title("全文件脉冲分布")
            self.hist_ax.legend()
            self.hist_ax.grid(alpha=0.3)
        self.hist_fig.tight_layout(pad=0.5)
        self.hist_canvas.draw_idle()

    def update_histogram(self):
        self.plot_histogram()

    # ---------- 格式转换辅助 ----------
    def _auto_export_rom(self, bin_file, show_message=True):
        try:
            with open(bin_file, "rb") as f:
                data = f.read()
        except Exception as e:
            msg = f"无法读取文件：{e}"
            if show_message:
                QMessageBox.critical(self, "ROM生成失败", msg)
            return False, msg

        if len(data) < 9:
            msg = "文件长度不足 9 字节"
            if show_message:
                QMessageBox.critical(self, "ROM生成失败", msg)
            return False, msg

        header = data[:5]
        expected = bytes([0xED, 0x54, 0x6F, 0xD6, 0x50])
        if header != expected:
            msg = f"文件头不匹配！期望: {expected.hex().upper()}, 实际: {header.hex().upper()}"
            if show_message:
                QMessageBox.critical(self, "ROM生成失败", msg)
            return False, msg

        start_addr = struct.unpack(">H", data[5:7])[0]
        data_len = struct.unpack(">H", data[7:9])[0]
        if len(data) < 9 + data_len:
            msg = f"文件长度不足，预期数据长度 {data_len}"
            if show_message:
                QMessageBox.critical(self, "ROM生成失败", msg)
            return False, msg

        raw_data = data[9 : 9 + data_len]
        base, _ = os.path.splitext(bin_file)
        rom_file = base + ".rom"
        try:
            with open(rom_file, "wb") as f:
                f.write(raw_data)
            msg = f"ROM 文件已成功导出：{rom_file}\n起始地址: 0x{start_addr:04X}\n有效数据包长度: {data_len} 字节"
            if show_message:
                QMessageBox.information(self, "ROM生成成功", msg)
            return True, msg
        except Exception as e:
            msg = f"保存 ROM 文件失败：{e}"
            if show_message:
                QMessageBox.critical(self, "ROM生成失败", msg)
            return False, msg

    # ---------- UI 回调 ----------
    def load_new_file(self):
        last_dir = self.settings.value("last_audio_directory", os.getcwd())
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择 WAV 磁带音频文件", last_dir, "WAV files (*.wav);;All files (*.*)"
        )
        if filename:
            self.settings.setValue("last_audio_directory", os.path.dirname(filename))
            self.load_file(filename)

    def reset(self):
        if self.raw is None:
            return
        defaults = {"noise_thresh": 0.14, "rc_alpha": 0.1, "min_gap": 0.4}
        for attr, val in defaults.items():
            self.sliders[attr].setValue(int(val * 1000))
            if attr == "min_gap":
                self.entries[attr].setText(f"{val:.1f}")
                setattr(self, attr, val / 1000.0)
            else:
                self.entries[attr].setText(f"{val:.3f}")
                setattr(self, attr, val)
        self.data_start = 0.0
        self.data_window = min(0.1, self.total_time)
        self.data_start_var.setText("0.0")
        self.data_window_var.setText(f"{self.data_window:.3f}")
        self.env_combo.setCurrentText("RC包络")
        self.envelope_type = "rc"
        self.decision_combo.setCurrentText("宽度阈值")
        self.bit_decision_method = "width"
        self._update_slider_for_width()
        self.hist_data_valid = False
        self.update_all_and_plot()
        self.update_histogram()

    def save_bin(self):
        if self.raw is None:
            QMessageBox.warning(self, "提示", "请先加载 WAV 音频文件！")
            return

        start_abs = self.data_start
        start_idx = int(start_abs * self.fs)
        if start_idx < 0:
            start_idx = 0
        if start_idx >= len(self.raw):
            QMessageBox.critical(self, "错误", "数据起始位置已超出文件总长度！")
            return

        data_slice = self.raw[start_idx:]
        widths, centers, areas, envelope, binary, _ = (
            self.detect_bursts_by_envelope(data_slice, self.noise_thresh, self.min_gap)
        )

        if self.bit_decision_method == "width":
            valid_mask = (widths > self.low_bond) & (widths < self.high_bond)
            valid_widths = widths[valid_mask]
            bits = [1 if w >= self.bit_thresh else 0 for w in valid_widths]
        else:
            valid_mask = (areas > self.low_bond) & (areas < self.high_bond)
            valid_areas = areas[valid_mask]
            bits = [1 if a >= self.area_thresh else 0 for a in valid_areas]

        if not bits:
            QMessageBox.warning(self, "警告", "未检测到符合条件的有效脉冲数据！")
            return

        byte_list = []
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                if i + j < len(bits) and bits[i + j] == 1:
                    byte |= 1 << (7 - j)
            byte_list.append(byte)

        out_file, _ = QFileDialog.getSaveFileName(
            self, "保存解码结果为 BIN 文件", "", "Binary files (*.bin);;All files (*.*)"
        )
        if out_file:
            with open(out_file, "wb") as f:
                f.write(bytes(byte_list))

            rom_success, rom_msg = self._auto_export_rom(out_file, show_message=False)

            main_msg = (
                f"检测脉冲总数: {len(widths)}\n"
                f"有效 Bit 数: {len(bits)}\n"
                f"生成字节数: {len(byte_list)} 字节\n\n"
                f"ROM 联动导出: {'成功' if rom_success else '跳过/失败'}\n"
                f"说明: {rom_msg}"
            )
            QMessageBox.information(self, "保存及 ROM 转换处理完成", main_msg)

    def export_rom(self):
        bin_file, _ = QFileDialog.getOpenFileName(
            self, "选择 BIN 文件转换为 ROM", "", "BIN files (*.bin);;All files (*.*)"
        )
        if bin_file:
            self._auto_export_rom(bin_file, show_message=True)


# 支持单文件独立运行测试
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("音频解码器独立测试窗口")
    window.setGeometry(100, 100, 1100, 750)
    
    decoder = AudioDecoderFrame(window)
    layout = QVBoxLayout(window)
    layout.addWidget(decoder)
    
    window.show()
    sys.exit(app.exec_())
