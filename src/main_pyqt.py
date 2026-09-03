import os
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QLabel, QLineEdit, QPushButton, QTextEdit, 
                             QFrame, QSplitter, QFileDialog, QMessageBox, QComboBox,
                             QGroupBox, QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSettings
from PyQt5.QtGui import QFont, QColor, QPalette, QTextCursor

# 导入底层解码与编码模块
from basic_decoder import process_cac3_bin
from basic_encoder import basic_to_wav, encode_basic_text_to_cac3_bin
from hex_viewer_pyqt import format_hex_and_char_bytes
from z80_disasm import disassemble_z80_bytes
from z80_flow_disasm import disassemble_z80_flow

# Import PyQt versions of analyzer modules
from audio_decoder_pyqt import AudioDecoderFrame
from signal_analyzer_pyqt import SignalAnalyzerFrame


# ==========================================
# 1. BASIC 解码工作区 UI (BIN -> BASIC)
# ==========================================
class BasicDecoderFrame(QWidget):

    def __init__(self, parent=None, root_app=None):
        super().__init__(parent)
        self.root_app = root_app
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # File selection frame
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("选择 BIN 文件: "))
        
        self.file_path_var = QLineEdit()
        self.file_path_var.setReadOnly(True)
        file_layout.addWidget(self.file_path_var, 1)
        
        self.btn_browse = QPushButton("载入 BIN 文件")
        self.btn_browse.clicked.connect(self.load_and_decode)
        file_layout.addWidget(self.btn_browse)
        
        layout.addLayout(file_layout)

        # Info group
        info_group = QGroupBox(" 磁带头与系统状态 ")
        info_layout = QGridLayout()
        info_layout.setContentsMargins(8, 8, 8, 8)
        
        info_layout.addWidget(QLabel("SAVE 文件名:"), 0, 0)
        self.lbl_filename = QLabel("---")
        self.lbl_filename.setFont(QFont("Consolas", 11, QFont.Bold))
        self.lbl_filename.setStyleSheet("color: #1E90FF;")
        info_layout.addWidget(self.lbl_filename, 0, 1, 1, 2)
        
        info_layout.addWidget(QLabel("偏移地址:"), 1, 0)
        self.lbl_sys_info = QLabel("---")
        self.lbl_sys_info.setFont(QFont("Consolas", 9))
        self.lbl_sys_info.setStyleSheet("color: #2E8B57;")
        info_layout.addWidget(self.lbl_sys_info, 1, 1, 1, 2)
        
        self.btn_show_crt = QPushButton("📺 显示 CRT 视频缓冲区")
        self.btn_show_crt.setEnabled(False)
        self.btn_show_crt.clicked.connect(self.show_crt_window)
        info_layout.addWidget(self.btn_show_crt, 0, 2, 2, 1)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Splitter for paned views
        splitter = QSplitter(Qt.Vertical)
        
        # System variables group
        sys_group = QGroupBox(" 116 字节系统变量 (HEX 与 CAC-3 字符对照) ")
        sys_layout = QVBoxLayout()
        
        self.txt_sys_bytes = QTextEdit()
        self.txt_sys_bytes.setFont(QFont("Consolas", 10))
        self.txt_sys_bytes.setStyleSheet("background-color: #1E1E1E; color: #FFD700;")
        self.txt_sys_bytes.setReadOnly(True)
        self.txt_sys_bytes.setMaximumHeight(180)
        sys_layout.addWidget(self.txt_sys_bytes)
        
        sys_group.setLayout(sys_layout)
        splitter.addWidget(sys_group)

        # BASIC code group
        code_group = QGroupBox(" 📜 解码出来的 BASIC 源码 ")
        code_layout = QVBoxLayout()
        
        self.txt_basic_code = QTextEdit()
        self.txt_basic_code.setFont(QFont("Consolas", 11, QFont.Bold))
        self.txt_basic_code.setStyleSheet("background-color: #181818; color: #00FF66;")
        self.txt_basic_code.setReadOnly(True)
        code_layout.addWidget(self.txt_basic_code)
        
        code_group.setLayout(code_layout)
        splitter.addWidget(code_group)
        
        layout.addWidget(splitter, 1)

        # CRT window variables
        self.crt_win = None
        self.screen_matrix = None

    def load_and_decode(self):
        last_dir = self.root_app.get_last_directory() if self.root_app else os.getcwd()
        fn, _ = QFileDialog.getOpenFileName(
            self, "选择 CAC-3 BIN 文件", last_dir, 
            "Binary Files (*.bin);;All Files (*.*)"
        )
        if not fn:
            return
        self.file_path_var.setText(fn)
        if self.root_app:
            self.root_app.save_last_directory(fn)

        (
            parsed_name,
            sys_info,
            sys_bytes_dump,
            screen_matrix,
            basic_code_lines,
        ) = process_cac3_bin(fn, format_hex_and_char_bytes)

        self.lbl_filename.setText(f'"{parsed_name}"')
        self.lbl_sys_info.setText(sys_info if sys_info else "解析失败")

        # Limit display to prevent crashes
        if sys_bytes_dump and len(sys_bytes_dump) > 50000:
            self.txt_sys_bytes.setText(sys_bytes_dump[:50000] + "\n\n... (数据过长，已截断显示)")
        else:
            self.txt_sys_bytes.setText(sys_bytes_dump if sys_bytes_dump else "--- 无系统变量数据 ---")

        if basic_code_lines:
            basic_text = "\n".join(basic_code_lines)
            if len(basic_text) > 50000:
                self.txt_basic_code.setText(basic_text[:50000] + "\n\n... (代码过长，已截断显示)")
            else:
                self.txt_basic_code.setText(basic_text)
        else:
            self.txt_basic_code.setText("--- 未找到 valid BASIC 语句 ---")

        self.screen_matrix = screen_matrix
        if screen_matrix:
            self.btn_show_crt.setEnabled(True)
            if self.crt_win is not None:
                self.draw_crt_display()

    def show_crt_window(self):
        if not self.screen_matrix:
            return

        if self.crt_win is None:
            self.crt_win = CrtWindow(self.screen_matrix)
            self.crt_win.show()
        else:
            self.crt_win.update_screen(self.screen_matrix)
            self.crt_win.raise_()
            self.crt_win.activateWindow()

    def draw_crt_display(self):
        if self.crt_win:
            self.crt_win.update_screen(self.screen_matrix)


class CrtCanvas(QWidget):
    def __init__(self, screen_matrix):
        super().__init__()
        self.screen_matrix = screen_matrix
        self.setFixedSize(512, 384)
        self.setStyleSheet("background-color: #000000;")

    def update_screen(self, screen_matrix):
        self.screen_matrix = screen_matrix
        self.update()

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor, QFont
        from PyQt5.QtCore import QPoint
        
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))
        
        if not self.screen_matrix:
            return
            
        for r, line in enumerate(self.screen_matrix):
            for c, (ch, is_inv) in enumerate(line):
                bg_color = QColor("#00FF66") if is_inv else QColor("#000000")
                fg_color = QColor("#000000") if is_inv else QColor("#00FF66")
                
                painter.fillRect(c * 16, r * 16, 16, 16, bg_color)
                
                if ch.strip():
                    painter.setPen(fg_color)
                    painter.setFont(QFont("Consolas", 11, QFont.Bold))
                    painter.drawText(QPoint(c * 16 + 8, r * 16 + 12), ch)


class CrtWindow(QWidget):
    def __init__(self, screen_matrix):
        super().__init__()
        self.screen_matrix = screen_matrix
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("CAC-3 CRT Display (32 x 24)")
        self.setGeometry(100, 100, 540, 440)
        self.setStyleSheet("background-color: #0D0D0D;")
        self.setFixedSize(540, 440)

        layout = QVBoxLayout(self)
        
        label = QLabel("--- CAC-3 CRT DISPLAY BUFFER ---")
        label.setFont(QFont("Consolas", 10, QFont.Bold))
        label.setStyleSheet("color: #00FF66; background-color: #0D0D0D;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        self.crt_canvas = CrtCanvas(self.screen_matrix)
        layout.addWidget(self.crt_canvas, 0, Qt.AlignCenter)

    def update_screen(self, screen_matrix):
        self.screen_matrix = screen_matrix
        self.crt_canvas.update_screen(screen_matrix)


# ==========================================
# 2. 独立模块：BASIC 源码 转 BIN 文件 (BASIC -> BIN)
# ==========================================
class BasicToBinFrame(QWidget):

    def __init__(self, parent=None, root_app=None):
        super().__init__(parent)
        self.root_app = root_app
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Configuration frame
        cfg_group = QGroupBox(" BIN 导出参数 ")
        cfg_layout = QHBoxLayout()
        
        cfg_layout.addWidget(QLabel("SAVE 文件名:"))
        
        self.var_save_name = QLineEdit("TEST")
        self.var_save_name.setFixedWidth(100)
        cfg_layout.addWidget(self.var_save_name)
        
        cfg_layout.addStretch()
        
        self.btn_convert = QPushButton("⚡ 生成并导出 BIN 文件")
        self.btn_convert.clicked.connect(self.convert_to_bin)
        cfg_layout.addWidget(self.btn_convert)
        
        cfg_group.setLayout(cfg_layout)
        layout.addWidget(cfg_group)

        # Editor group
        editor_group = QGroupBox(" 📝 输入 BASIC 源码 ")
        editor_layout = QVBoxLayout()
        
        self.txt_editor = QTextEdit()
        self.txt_editor.setFont(QFont("Consolas", 11))
        self.txt_editor.setStyleSheet("background-color: #1E1E1E; color: #00E5FF;")
        
        sample_code = (
            "10 REM CAC-3 / LAMBDA 8300 TEST\n"
            "20 CLS\n"
            '30 PRINT "********************************"\n'
            '40 PRINT "*  WELCOME TO CAC-3 / LAMBDA   *"\n'
            '50 PRINT "********************************"\n'
            "60 LET PX=2\n"
            "65 LET PY=2\n"
            '70 PRINT AT PY,PX; "*"\n'
            "90 A=10\n"
            "100 FOR I=1 TO 10\n"
            "110 NEXT I\n"
        )
        self.txt_editor.setText(sample_code)
        
        editor_layout.addWidget(self.txt_editor)
        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group, 1)

    def convert_to_bin(self):
        basic_text = self.txt_editor.toPlainText().strip()
        if not basic_text:
            QMessageBox.warning(self, "警告", "请输入 BASIC 代码！")
            return

        save_name = self.var_save_name.text().strip() or "TEST"

        last_dir = self.root_app.get_last_directory() if self.root_app else os.getcwd()
        fn, _ = QFileDialog.getSaveFileName(
            self, "保存 CAC-3 BIN 文件", os.path.join(last_dir, f"{save_name.lower()}.bin"),
            "Binary Files (*.bin);;All Files (*.*)"
        )
        if not fn:
            return
        
        if self.root_app:
            self.root_app.save_last_directory(fn)

        try:
            bin_data = encode_basic_text_to_cac3_bin(basic_text, save_filename=save_name)
            with open(fn, "wb") as f:
                f.write(bin_data)

            QMessageBox.information(
                self, "导出成功",
                f"✓ BIN 文件生成完成！\n路径: {fn}\n大小: {len(bin_data):,} 字节"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"错误详情:\n{str(e)}")


# ==========================================
# 3. 独立模块：BIN 文件 转 WAV 音频 (BIN -> WAV)
# ==========================================
class BinToWavFrame(QWidget):

    def __init__(self, parent=None, root_app=None):
        super().__init__(parent)
        self.root_app = root_app
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Input file group
        input_group = QGroupBox(" 输入 BIN 文件 ")
        input_layout = QHBoxLayout()
        
        input_layout.addWidget(QLabel("选择 BIN 文件: "))
        
        self.var_bin_path = QLineEdit()
        self.var_bin_path.setReadOnly(True)
        input_layout.addWidget(self.var_bin_path, 1)
        
        self.btn_browse_bin = QPushButton("浏览...")
        self.btn_browse_bin.clicked.connect(self.browse_bin_file)
        input_layout.addWidget(self.btn_browse_bin)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Parameters group
        param_group = QGroupBox(" WAV 音频调制参数 ")
        param_layout = QHBoxLayout()
        
        param_layout.addWidget(QLabel("采样率:"))
        self.var_sample_rate = QComboBox()
        self.var_sample_rate.addItems(["22050", "44100", "48000"])
        self.var_sample_rate.setCurrentText("44100")
        param_layout.addWidget(self.var_sample_rate)
        
        param_layout.addWidget(QLabel("载波频率:"))
        self.var_carrier_freq = QLineEdit("1200")
        self.var_carrier_freq.setFixedWidth(80)
        param_layout.addWidget(self.var_carrier_freq)
        
        param_layout.addStretch()
        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

        # Convert button
        self.btn_convert_wav = QPushButton("🎵 开始转换并保存 WAV 音频")
        self.btn_convert_wav.clicked.connect(self.convert_bin_to_wav)
        self.btn_convert_wav.setStyleSheet("padding: 10px;")
        layout.addWidget(self.btn_convert_wav)

    def browse_bin_file(self):
        last_dir = self.root_app.get_last_directory() if self.root_app else os.getcwd()
        fn, _ = QFileDialog.getOpenFileName(
            self, "选择 BIN 二进制文件", last_dir,
            "Binary Files (*.bin);;All Files (*.*)"
        )
        if fn:
            self.var_bin_path.setText(fn)
            if self.root_app:
                self.root_app.save_last_directory(fn)

    def convert_bin_to_wav(self):
        bin_path = self.var_bin_path.text().strip()
        if not bin_path or not os.path.exists(bin_path):
            QMessageBox.warning(self, "警告", "请选择有效的 BIN 文件！")
            return

        try:
            sr = int(self.var_sample_rate.currentText())
            cf = float(self.var_carrier_freq.text())
        except ValueError:
            QMessageBox.critical(self, "参数错误", "采样率和载波频率必须是有效的数字！")
            return

        default_wav_name = os.path.splitext(os.path.basename(bin_path))[0] + ".wav"
        last_dir = self.root_app.get_last_directory() if self.root_app else os.getcwd()
        fn_wav, _ = QFileDialog.getSaveFileName(
            self, "保存 CAC-3 WAV 音频文件", os.path.join(last_dir, default_wav_name),
            "WAV Audio Files (*.wav);;All Files (*.*)"
        )
        if not fn_wav:
            return
        
        if self.root_app:
            self.root_app.save_last_directory(fn_wav)

        try:
            with open(bin_path, "rb") as f:
                bin_data = f.read()

            from basic_encoder import generate_audio_from_bytes, wavfile

            audio = generate_audio_from_bytes(bin_data, sample_rate=sr, carrier_freq=cf)
            audio_int16 = (audio * 32767).astype("int16")
            wavfile.write(fn_wav, sr, audio_int16)

            duration = len(audio) / sr
            QMessageBox.information(
                self, "转换成功",
                f"✓ WAV 磁带音频合成完成！\n路径: {fn_wav}\n时长: {duration:.2f} 秒\n采样率: {sr} Hz"
            )
        except Exception as e:
            QMessageBox.critical(self, "生成 WAV 失败", f"错误详情:\n{str(e)}")


# ==========================================
# 4. ROM/BIN 文件浏览器 UI (同屏分屏主控)
# ==========================================
class HexViewerPanel(QFrame):
    def __init__(self, file_path, parent=None, parent_frame=None):
        super().__init__(parent)
        self.file_path = file_path
        self.parent_frame = parent_frame  # Reference to parent HexViewerFrame for sync
        try:
            self.init_ui()
            # Delay file processing to prevent crash during initialization
            QTimer.singleShot(100, self._process_and_display_file)
        except Exception as e:
            print(f"Error initializing HexViewerPanel: {e}")

    def init_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Info frame
        info_group = QGroupBox(f" {os.path.basename(self.file_path)} ")
        info_layout = QHBoxLayout()
        
        info_layout.addWidget(QLabel("大小:"))
        self.lbl_file_size = QLabel("0 B")
        self.lbl_file_size.setFont(QFont("Consolas", 9, QFont.Bold))
        self.lbl_file_size.setStyleSheet("color: #1E90FF;")
        info_layout.addWidget(self.lbl_file_size)
        
        info_layout.addWidget(QLabel("首字节偏移:"))
        self.var_offset = QLineEdit("0")
        self.var_offset.setFixedWidth(80)
        info_layout.addWidget(self.var_offset)
        
        info_layout.addStretch()
        
        self.btn_reload = QPushButton("🔄 刷新")
        self.btn_reload.clicked.connect(self.reload_file)
        info_layout.addWidget(self.btn_reload)
        
        self.btn_close = QPushButton("❌ 关闭")
        self.btn_close.clicked.connect(self.close)
        info_layout.addWidget(self.btn_close)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Hex display
        self.txt_hex_display = QTextEdit()
        self.txt_hex_display.setFont(QFont("Consolas", 10))
        self.txt_hex_display.setStyleSheet("background-color: #1E1E1E; color: #FFD700;")
        self.txt_hex_display.setReadOnly(True)
        self.txt_hex_display.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        
        # Set consistent selection color
        palette = self.txt_hex_display.palette()
        palette.setColor(QPalette.Highlight, QColor(51, 153, 255))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.txt_hex_display.setPalette(palette)
        
        layout.addWidget(self.txt_hex_display, 1)
        
        # Connect events for sync
        self.txt_hex_display.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.txt_hex_display.selectionChanged.connect(self.on_selection_changed)
        self.txt_hex_display.cursorPositionChanged.connect(self.on_cursor_changed)
        self.txt_hex_display.mousePressEvent = self.on_mouse_click
        self.txt_hex_display.mouseReleaseEvent = self.on_mouse_release
        self.txt_hex_display.focusInEvent = self.on_focus_in

        # Status bar for position display
        self.status_label = QLabel("当前位置: --")
        self.status_label.setFont(QFont("Consolas", 9))
        self.status_label.setStyleSheet("background-color: #ecf0f1; padding: 2px;")
        layout.addWidget(self.status_label)

    def reload_file(self):
        if os.path.exists(self.file_path):
            self._process_and_display_file()
        else:
            QMessageBox.warning(self, "警告", "文件不存在或已被移动！")

    def _process_and_display_file(self):
        offset_str = self.var_offset.text().strip()
        offset = 0
        if offset_str:
            try:
                if offset_str.lower().startswith('0x'):
                    offset = int(offset_str, 16)
                else:
                    try:
                        offset = int(offset_str)
                    except ValueError:
                        offset = int(offset_str, 16)
            except ValueError:
                QMessageBox.critical(self, "格式错误", "偏移量请输入有效的十进制或十六进制数值！")
                return

        try:
            # Check file size before reading to prevent memory issues
            file_size = os.path.getsize(self.file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                QMessageBox.warning(self, "文件过大", f"文件大小 ({file_size:,} 字节) 超过 10MB 限制，可能导致性能问题。")
            
            with open(self.file_path, "rb") as f:
                data = f.read()

            total_size = len(data)

            if offset > 0 and offset >= total_size:
                QMessageBox.warning(self, "警告", f"偏移量 ({offset}) 已超出或等于文件总大小 ({total_size})！")
                return

            display_data = data[offset:]
            display_len = len(display_data)

            self.lbl_file_size.setText(f"{display_len:,} B (0x{display_len:04X})")

            # Limit display to prevent crashes with very large files
            max_display_size = 50000  # 50KB limit for display (reduced for safety)
            if display_len > max_display_size:
                display_data = display_data[:max_display_size]
                try:
                    formatted_dump = format_hex_and_char_bytes(display_data, base_address=0)
                    self.txt_hex_display.setText(formatted_dump + f"\n\n... (文件过大，仅显示前 {max_display_size} 字节)")
                except Exception as e:
                    # Fallback to simple hex display if formatting fails
                    hex_str = ' '.join(f'{b:02X}' for b in display_data)
                    self.txt_hex_display.setText(f"格式化失败，显示原始十六进制:\n{hex_str}\n\n... (文件过大，仅显示前 {max_display_size} 字节)")
            else:
                try:
                    formatted_dump = format_hex_and_char_bytes(display_data, base_address=0)
                    self.txt_hex_display.setText(formatted_dump if formatted_dump else "--- 文件内容为空 ---")
                except Exception as e:
                    # Fallback to simple hex display if formatting fails
                    hex_str = ' '.join(f'{b:02X}' for b in display_data)
                    self.txt_hex_display.setText(f"格式化失败，显示原始十六进制:\n{hex_str}")

        except MemoryError:
            QMessageBox.critical(self, "内存错误", "文件过大导致内存不足，请尝试较小的文件或增加偏移量。")
        except Exception as e:
            QMessageBox.critical(self, "读取错误", f"无法读取或处理文件:\n{str(e)}")

    # Sync methods
    def on_scroll(self, value):
        """Handle scroll event for sync"""
        if self.parent_frame and hasattr(self.parent_frame, 'on_panel_scroll'):
            self.parent_frame.on_panel_scroll(self, value)

    def on_selection_changed(self):
        """Handle selection change for sync"""
        cursor = self.txt_hex_display.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            self.update_position_display(start)
        if self.parent_frame and hasattr(self.parent_frame, 'on_panel_selection_changed'):
            self.parent_frame.on_panel_selection_changed(self)

    def on_cursor_changed(self):
        """Handle cursor position change"""
        cursor = self.txt_hex_display.textCursor()
        pos = cursor.position()
        self.update_position_display(pos)
        if self.parent_frame and hasattr(self.parent_frame, 'on_panel_cursor_changed'):
            self.parent_frame.on_panel_cursor_changed(self)

    def update_position_display(self, pos):
        """Update position display based on cursor position - show current byte value"""
        try:
            text = self.txt_hex_display.toPlainText()
            lines = text.split('\n')
            
            # Find which line the cursor is on
            line_num = 0
            char_count = 0
            for i, line in enumerate(lines):
                if char_count + len(line) >= pos:
                    line_num = i
                    break
                char_count += len(line) + 1  # +1 for newline
            
            if line_num >= len(lines):
                self.status_label.setText("相对偏移: -- | 字节内容: --")
                return
            
            line = lines[line_num]
            char_pos_in_line = pos - char_count
            
            # Check if this is a HEX line or CHAR line
            is_hex_line = "HEX :" in line
            
            if not is_hex_line:
                # If on CHAR line, find the corresponding HEX line (previous line)
                if line_num > 0 and "HEX :" in lines[line_num - 1]:
                    line_num = line_num - 1
                    line = lines[line_num]
                    # Recalculate char position in the HEX line
                    # The CHAR line has same structure, so use same position
                    is_hex_line = True
                else:
                    self.status_label.setText("相对偏移: -- | 字节内容: --")
                    return
            
            # Calculate byte offset in the HEX line
            # Format: "[0000-000F]  HEX :  00 11 22 ..."
            # Label part: "[0000-000F]  HEX : " = 18 characters
            # Each hex byte takes 3 characters: " 00"
            hex_label_end = line.find("HEX :") + 6  # "HEX :" is 6 chars
            hex_part = line[hex_label_end:]
            
            # Calculate which byte position the cursor is at
            if char_pos_in_line <= hex_label_end:
                byte_offset = 0
            else:
                relative_pos = char_pos_in_line - hex_label_end
                # Each byte is 3 chars: space + 2 hex digits
                # Use floor division but handle byte boundaries
                byte_offset = relative_pos // 3
                # If cursor is exactly at a byte boundary (position 3, 6, 9, etc.)
                # it should still be considered as the previous byte
                if relative_pos % 3 == 0 and relative_pos > 0:
                    byte_offset = (relative_pos - 1) // 3
                if byte_offset >= 16:
                    byte_offset = 15
            
            # Get the byte value
            hex_bytes = hex_part.split()
            if byte_offset < len(hex_bytes):
                byte_value = hex_bytes[byte_offset]
                
                # Calculate absolute offset
                # Each HEX line represents 16 bytes, and there are 2 lines per 16 bytes (HEX + CHAR)
                # So line_num // 2 gives the 16-byte block number
                block_num = line_num // 2
                relative_offset = block_num * 16 + byte_offset
                
                # Add user offset
                offset_str = self.var_offset.text().strip()
                try:
                    if offset_str.startswith('0x') or offset_str.startswith('0X'):
                        base_offset = int(offset_str, 16)
                    elif offset_str.endswith('h'):
                        base_offset = int(offset_str[:-1], 16)
                    else:
                        base_offset = int(offset_str)
                except ValueError:
                    base_offset = 0
                
                total_offset = base_offset + relative_offset
                self.status_label.setText(f"相对偏移: 0x{relative_offset:X} ({relative_offset})" +
                                          f" | 字节内容: 0x{byte_value} ({int(byte_value, 16)})")
            else:
                self.status_label.setText("相对偏移: -- | 字节内容: --")
        except Exception as e:
            self.status_label.setText(f"相对偏移: -- | 字节内容: -- (错误: {str(e)})")

    def on_mouse_click(self, event):
        """Handle mouse click"""
        QTextEdit.mousePressEvent(self.txt_hex_display, event)
        if self.parent_frame and hasattr(self.parent_frame, 'set_active_panel'):
            self.parent_frame.set_active_panel(self)

    def on_mouse_release(self, event):
        """Handle mouse release"""
        QTextEdit.mouseReleaseEvent(self.txt_hex_display, event)
        if self.parent_frame and hasattr(self.parent_frame, 'set_active_panel'):
            self.parent_frame.set_active_panel(self)

    def on_focus_in(self, event):
        """Handle focus in"""
        QTextEdit.focusInEvent(self.txt_hex_display, event)
        if self.parent_frame and hasattr(self.parent_frame, 'set_active_panel'):
            self.parent_frame.set_active_panel(self)

    def set_selection(self, start_pos, end_pos):
        """Set text selection"""
        cursor = self.txt_hex_display.textCursor()
        cursor.setPosition(start_pos)
        cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
        self.txt_hex_display.setTextCursor(cursor)


class HexViewerFrame(QWidget):

    def __init__(self, parent=None, root_app=None):
        super().__init__(parent)
        self.root_app = root_app
        
        # Sync settings
        self.sync_scroll = False
        self.sync_selection = False
        self.selection_source = None
        self.last_selection_range = None
        self.syncing_selection = False
        self.active_panel = None
        self.panels = []
        
        # Selection poll timer
        self.selection_timer = QTimer()
        self.selection_timer.timeout.connect(self.poll_selection)
        self.selection_timer.start(50)
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Top frame
        top_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("➕ 载入并并排比对 ROM/BIN 文件")
        self.btn_add.clicked.connect(self.add_new_file)
        top_layout.addWidget(self.btn_add)
        
        # Sync controls
        self.chk_sync_scroll = QPushButton("🔗 同步滑动")
        self.chk_sync_scroll.setCheckable(True)
        self.chk_sync_scroll.clicked.connect(self.toggle_sync_scroll)
        top_layout.addWidget(self.chk_sync_scroll)
        
        self.chk_sync_selection = QPushButton("🔗 同步选中")
        self.chk_sync_selection.setCheckable(True)
        self.chk_sync_selection.clicked.connect(self.toggle_sync_selection)
        top_layout.addWidget(self.chk_sync_selection)
        
        top_layout.addWidget(QLabel("（提示：你可以拖动面板之间的空白处来调整大小）"))
        top_layout.addStretch()
        
        layout.addLayout(top_layout)

        # Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.splitter, 1)

    def add_new_file(self):
        last_dir = self.root_app.get_last_directory() if self.root_app else os.getcwd()
        fn, _ = QFileDialog.getOpenFileName(
            self, "选择 ROM/BIN 文件", last_dir,
            "ROM & BIN Files (*.rom *.bin);;All Files (*.*)"
        )
        if not fn:
            return

        if self.root_app:
            self.root_app.save_last_directory(fn)

        new_panel = HexViewerPanel(fn, parent_frame=self)
        self.splitter.addWidget(new_panel)
        self.panels.append(new_panel)

    def toggle_sync_scroll(self, checked):
        """Toggle sync scrolling"""
        self.sync_scroll = checked

    def toggle_sync_selection(self, checked):
        """Toggle sync selection"""
        self.sync_selection = checked
        if not checked:
            self.selection_source = None
            self.last_selection_range = None

    def set_active_panel(self, panel):
        """Set the active panel for selection sync"""
        self.active_panel = panel

    def on_panel_scroll(self, source_panel, value):
        """Handle scroll event for sync"""
        if not self.sync_scroll:
            return

        for panel in self.panels:
            if panel != source_panel:
                panel.txt_hex_display.verticalScrollBar().setValue(value)

    def on_panel_selection_changed(self, panel):
        """Handle selection change for sync"""
        if not self.sync_selection:
            return

        cursor = panel.txt_hex_display.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            current_range = (start, end)

            if self.selection_source is None:
                self.selection_source = panel
                self.last_selection_range = current_range
                if not self.syncing_selection:
                    self.sync_selection_to_all(panel)
            elif self.selection_source == panel:
                if current_range != self.last_selection_range:
                    self.last_selection_range = current_range
                    if not self.syncing_selection:
                        self.sync_selection_to_all(panel)
            else:
                self.selection_source = panel
                self.last_selection_range = current_range
                if not self.syncing_selection:
                    self.sync_selection_to_all(panel)
        else:
            if self.selection_source == panel:
                self.selection_source = None
                self.last_selection_range = None
                if not self.syncing_selection:
                    self.clear_selection_all(panel)

    def on_panel_cursor_changed(self, panel):
        """Handle cursor position change"""
        pass  # Can be used for position display

    def poll_selection(self):
        """Poll for selection changes"""
        if not self.sync_selection or self.active_panel is None:
            return

        cursor = self.active_panel.txt_hex_display.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            current_range = (start, end)

            if self.selection_source is None:
                self.selection_source = self.active_panel
                self.last_selection_range = current_range
                if not self.syncing_selection:
                    self.sync_selection_to_all(self.active_panel)
            elif self.selection_source == self.active_panel:
                if current_range != self.last_selection_range:
                    self.last_selection_range = current_range
                    if not self.syncing_selection:
                        self.sync_selection_to_all(self.active_panel)
            else:
                self.selection_source = self.active_panel
                self.last_selection_range = current_range
                if not self.syncing_selection:
                    self.sync_selection_to_all(self.active_panel)
        else:
            if self.selection_source == self.active_panel:
                self.selection_source = None
                self.last_selection_range = None
                if not self.syncing_selection:
                    self.clear_selection_all(self.active_panel)

    def sync_selection_to_all(self, source_panel):
        """Sync selection from source to all other panels"""
        self.syncing_selection = True

        try:
            cursor = source_panel.txt_hex_display.textCursor()
            if not cursor.hasSelection():
                return

            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            for panel in self.panels:
                if panel != source_panel:
                    panel.set_selection(start, end)
        finally:
            self.syncing_selection = False

    def clear_selection_all(self, source_panel):
        """Clear selection in all panels except source"""
        for panel in self.panels:
            if panel != source_panel:
                cursor = panel.txt_hex_display.textCursor()
                cursor.clearSelection()
                panel.txt_hex_display.setTextCursor(cursor)


# ==========================================
# 5. ROM 反汇编器 UI
# ==========================================
class DisassemblerFrame(QWidget):

    def __init__(self, parent=None, root_app=None):
        super().__init__(parent)
        self.root_app = root_app
        self.loaded_data = None  # Store loaded file data for reuse
        self.loaded_file_path = None  # Store loaded file path
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Top frame
        top_layout = QHBoxLayout()
        
        top_layout.addWidget(QLabel("选择 ROM/BIN 文件: "))
        
        self.file_path_var = QLineEdit()
        self.file_path_var.setReadOnly(True)
        top_layout.addWidget(self.file_path_var, 1)
        
        self.btn_browse = QPushButton("反汇编文件")
        self.btn_browse.clicked.connect(self.load_and_disassemble)
        top_layout.addWidget(self.btn_browse)
        
        layout.addLayout(top_layout)

        # Config frame
        config_group = QGroupBox(" 反汇编选项 ")
        config_layout = QHBoxLayout()
        
        config_layout.addWidget(QLabel("基址: $"))
        self.var_base_addr = QLineEdit("0000")
        self.var_base_addr.setFixedWidth(80)
        config_layout.addWidget(self.var_base_addr)
        
        config_layout.addWidget(QLabel("起始地址: $"))
        self.var_start_addr = QLineEdit("")
        self.var_start_addr.setPlaceholderText("默认基址")
        self.var_start_addr.setFixedWidth(80)
        config_layout.addWidget(self.var_start_addr)
        
        config_layout.addWidget(QLabel("模式:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["线性反汇编", "控制流反汇编"])
        self.combo_mode.currentTextChanged.connect(self.on_mode_changed)
        config_layout.addWidget(self.combo_mode)
        
        config_layout.addStretch()
        
        self.lbl_status = QLabel("准备就绪")
        self.lbl_status.setFont(QFont("Consolas", 10))
        self.lbl_status.setStyleSheet("color: #1E90FF;")
        config_layout.addWidget(self.lbl_status)
        
        self.btn_save = QPushButton("💾 导出到文本文件")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_to_file)
        config_layout.addWidget(self.btn_save)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Disassembly output
        dis_group = QGroupBox(" Z80 反汇编代码输出 (地址 : 机器码 : 指令) ")
        dis_layout = QVBoxLayout()
        
        self.txt_disasm = QTextEdit()
        self.txt_disasm.setFont(QFont("Consolas", 10, QFont.Bold))
        self.txt_disasm.setStyleSheet("background-color: #121212; color: #00E5FF;")
        self.txt_disasm.setReadOnly(True)
        dis_layout.addWidget(self.txt_disasm)
        
        dis_group.setLayout(dis_layout)
        layout.addWidget(dis_group, 1)

    def on_mode_changed(self, mode):
        """Handle mode change - auto-refresh if data is loaded"""
        if self.loaded_data is not None:
            self.perform_disassembly()

    def perform_disassembly(self):
        """Perform disassembly with current settings and loaded data"""
        if self.loaded_data is None:
            return

        try:
            base_str = self.var_base_addr.text().strip()
            base_addr = int(base_str, 16) if base_str else 0x0000
        except ValueError:
            QMessageBox.critical(
                self, "格式错误",
                "起始基址请输入有效的十六进制数值（例如 0000 或 0200）"
            )
            return

        try:
            start_str = self.var_start_addr.text().strip()
            start_addr = int(start_str, 16) if start_str else None
        except ValueError:
            QMessageBox.critical(
                self, "格式错误",
                "起始地址请输入有效的十六进制数值（例如 0000 或 0200）"
            )
            return

        data = self.loaded_data

        # Check which mode to use
        mode = self.combo_mode.currentText()
        
        if mode == "控制流反汇编":
            disassembled_code = disassemble_z80_flow(data, base_addr=base_addr, start_addr=start_addr)
            mode_str = "控制流"
        else:
            disassembled_code = disassemble_z80_bytes(data, base_addr=base_addr)
            mode_str = "线性"

        # No truncation for either mode - display full output

        start_display = f"${start_addr:04X}" if start_addr else f"${base_addr:04X}"
        self.lbl_status.setText(f"成功{mode_str}反汇编 {len(data):,} 字节 | 起始地址: {start_display}")
        self.txt_disasm.setText(disassembled_code)
        self.btn_save.setEnabled(True)

    def load_and_disassemble(self):
        last_dir = self.root_app.get_last_directory() if self.root_app else os.getcwd()
        fn, _ = QFileDialog.getOpenFileName(
            self, "选择 ROM/BIN 文件", last_dir,
            "ROM & BIN Files (*.rom *.bin);;All Files (*.*)"
        )
        if not fn:
            return
        self.file_path_var.setText(fn)
        
        if self.root_app:
            self.root_app.save_last_directory(fn)

        try:
            with open(fn, "rb") as f:
                data = f.read()

            if not data:
                QMessageBox.warning(self, "警告", "选择的文件为空！")
                return

            # Store loaded data for reuse
            self.loaded_data = data
            self.loaded_file_path = fn

            # Perform disassembly
            self.perform_disassembly()

        except Exception as e:
            QMessageBox.critical(self, "反汇编出错", f"读取或解析文件失败:\n{str(e)}")

    def save_to_file(self):
        content = self.txt_disasm.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "警告", "没有可导出的反汇编内容！")
            return

        last_dir = self.root_app.get_last_directory() if self.root_app else os.getcwd()
        fn, _ = QFileDialog.getSaveFileName(
            self, "保存反汇编结果", os.path.join(last_dir, ""),
            "Text Files (*.txt);;All Files (*.*)"
        )
        if fn:
            if self.root_app:
                self.root_app.save_last_directory(fn)
            try:
                with open(fn, "w", encoding="utf-8") as f:
                    f.write(content)
                QMessageBox.information(self, "成功", f"文件已保存至:\n{fn}")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"无法写入文件:\n{str(e)}")


# ==========================================
# 6. 主应用程序入口与菜单控制
# ==========================================
class MainApplication(QMainWindow):

    def __init__(self):
        super().__init__()
        self.current_widget = None
        self.settings = QSettings("CAC3Tools", "PyQtVersion")
        self.init_ui()

    def get_last_directory(self):
        """获取上次使用的目录"""
        return self.settings.value("last_directory", os.getcwd())

    def save_last_directory(self, directory):
        """保存最后使用的目录"""
        if directory:
            self.settings.setValue("last_directory", os.path.dirname(directory))

    def init_ui(self):
        self.setWindowTitle("CAC-3 综合开发工具套件")
        self.setGeometry(100, 100, 1100, 850)
        self.setMinimumSize(800, 650)

        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)

        # Create menu bar
        self._build_menu()
        
        # Show home page
        self.show_home_page()

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件 (File)")
        file_menu.addAction("返回主页", self.show_home_page)
        file_menu.addSeparator()
        file_menu.addAction("退出程序", self.close)

        tools_menu = menubar.addMenu("工具 (Tools)")
        tools_menu.addAction("BASIC 解码 (BIN -> 源码)", self.load_basic_decoder_module)
        tools_menu.addAction("BASIC 编码 (BASIC -> BIN)", self.load_basic_to_bin_module)
        tools_menu.addAction("BIN 转 WAV 音频 (BIN -> WAV)", self.load_bin_to_wav_module)
        tools_menu.addSeparator()
        tools_menu.addAction("ROM/BIN 文件浏览器", self.load_hex_viewer_module)
        tools_menu.addAction("ROM 反汇编 (Z80)", self.load_disassembler_module)
        tools_menu.addSeparator()
        tools_menu.addAction("🌊 音频信号分析与解调-1", self.load_signal_analyzer_module)
        tools_menu.addAction("🎵 音频信号分析与解调-2", self.load_audio_decoder_module)

        help_menu = menubar.addMenu("帮助 (Help)")
        help_menu.addAction("关于", self.show_about)

    def show_about(self):
        QMessageBox.information(self, "关于", "CAC-3 综合开发分析套件\n版本: v2.7 (PyQt)")

    def switch_widget(self, widget_class, *args):
        if self.current_widget is not None:
            self.central_layout.removeWidget(self.current_widget)
            self.current_widget.deleteLater()
        
        self.current_widget = widget_class(self.central_widget, self, *args)
        self.central_layout.addWidget(self.current_widget)

    def show_home_page(self):
        if self.current_widget is not None:
            self.central_layout.removeWidget(self.current_widget)
            self.current_widget.deleteLater()

        home_widget = QWidget()
        home_layout = QVBoxLayout(home_widget)
        home_layout.setContentsMargins(20, 20, 20, 20)
        home_layout.setSpacing(10)

        welcome_label = QLabel("欢迎使用 CAC-3 工具箱")
        welcome_label.setFont(QFont("Microsoft YaHei UI", 18, QFont.Bold))
        welcome_label.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(welcome_label)

        sub_label = QLabel("请选择下方功能模块进入操作：")
        sub_label.setFont(QFont("Microsoft YaHei UI", 11))
        sub_label.setStyleSheet("color: #555555;")
        sub_label.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(sub_label)

        # Button container
        btn_container = QWidget()
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setAlignment(Qt.AlignCenter)
        
        # Function buttons
        buttons_spec = [
            ("📜 BASIC 解码 (BIN -> 源码)", self.load_basic_decoder_module),
            ("⚡ BASIC 编码 (BASIC -> BIN)", self.load_basic_to_bin_module),
            ("🎵 BIN 转 WAV (BIN -> WAV)", self.load_bin_to_wav_module),
            ("🔍 ROM / BIN 文件浏览器", self.load_hex_viewer_module),
            ("⚙️ ROM 反汇编器 (Z80)", self.load_disassembler_module),
            ("🌊 音频信号分析与解调-1", self.load_signal_analyzer_module),
            ("🎵 音频信号分析与解调-2", self.load_audio_decoder_module),
        ]

        for text, cmd in buttons_spec:
            btn = QPushButton(text)
            btn.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
            btn.setFixedWidth(350)
            btn.setStyleSheet("padding: 10px;")
            btn.clicked.connect(cmd)
            btn_layout.addWidget(btn)
        
        home_layout.addWidget(btn_container, 1)

        self.current_widget = home_widget
        self.central_layout.addWidget(self.current_widget)

    def load_basic_decoder_module(self):
        self.switch_widget(BasicDecoderFrame)

    def load_basic_to_bin_module(self):
        self.switch_widget(BasicToBinFrame)

    def load_bin_to_wav_module(self):
        self.switch_widget(BinToWavFrame)

    def load_hex_viewer_module(self):
        self.switch_widget(HexViewerFrame)

    def load_disassembler_module(self):
        self.switch_widget(DisassemblerFrame)

    def load_signal_analyzer_module(self):
        self.switch_widget(SignalAnalyzerFrame)

    def load_audio_decoder_module(self):
        self.switch_widget(AudioDecoderFrame)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    font = QFont()
    font.setPointSize(9)
    QApplication.setFont(font)

    window = MainApplication()
    window.show()
    sys.exit(app.exec_())
