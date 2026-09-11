import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTextEdit, QFileDialog, 
                             QMessageBox, QGroupBox, QFrame, QSplitter)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from hex_viewer_pyqt import format_hex_and_char_bytes
from basic_decoder import process_cac3_p
from z80_disasm import disassemble_z80_bytes


class PViewerFrame(QWidget):
    """P 文件浏览器 - 左右分屏显示二进制内容和解码内容"""

    def __init__(self, parent=None, root_app=None):
        super().__init__(parent)
        self.root_app = root_app
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        # 顶部控制区
        top_frame = QFrame()
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_layout.addWidget(QLabel("选择 P 文件: "))
        
        self.file_path_var = QLineEdit()
        self.file_path_var.setReadOnly(True)
        top_layout.addWidget(self.file_path_var, 1)
        
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self.load_file)
        top_layout.addWidget(self.btn_browse)
        
        layout.addWidget(top_frame)

        # 分屏显示区
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：二进制内容
        left_group = QGroupBox(" 二进制内容 (十六进制与字符) ")
        left_layout = QVBoxLayout(left_group)
        left_layout.setContentsMargins(2, 2, 2, 2)

        self.txt_hex_display = QTextEdit()
        self.txt_hex_display.setReadOnly(True)
        self.txt_hex_display.setFont(QFont("Consolas", 10))
        self.txt_hex_display.setStyleSheet("background-color: #1E1E1E; color: #FFD700;")
        left_layout.addWidget(self.txt_hex_display)
        
        splitter.addWidget(left_group)

        # 右侧：解码内容
        right_group = QGroupBox(" 解码内容 ")
        right_layout = QVBoxLayout(right_group)
        right_layout.setContentsMargins(2, 2, 2, 2)

        self.txt_decoded_display = QTextEdit()
        self.txt_decoded_display.setReadOnly(True)
        self.txt_decoded_display.setFont(QFont("Consolas", 10, QFont.Bold))
        self.txt_decoded_display.setStyleSheet("background-color: #121212; color: #00E5FF;")
        right_layout.addWidget(self.txt_decoded_display)
        
        splitter.addWidget(right_group)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)

        # 底部信息区
        info_frame = QFrame()
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_info = QLabel("准备就绪。请选择 .p 文件进行查看。")
        info_layout.addWidget(self.lbl_info)
        
        self.lbl_file_type = QLabel("")
        info_layout.addWidget(self.lbl_file_type)
        
        layout.addWidget(info_frame)

    def detect_file_type(self, data):
        """根据文件头检测文件类型"""
        if len(data) < 9:
            return "unknown", "未知文件类型"
        
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
        last_dir = self.root_app.get_last_directory() if self.root_app else os.getcwd()
        fn, _ = QFileDialog.getOpenFileName(
            self, "选择 P 文件", last_dir,
            "P Files (*.p);;All Files (*.*)"
        )
        if not fn:
            return
        self.file_path_var.setText(fn)
        if self.root_app:
            self.root_app.save_last_directory(fn)

        try:
            with open(fn, "rb") as f:
                data = f.read()

            # 显示二进制内容
            formatted_dump = format_hex_and_char_bytes(data, base_address=0)
            self.txt_hex_display.setText(formatted_dump if formatted_dump else "--- 文件内容为空 ---")

            # 检测文件类型并解码
            file_type, type_name = self.detect_file_type(data)
            self.lbl_file_type.setText(f"文件类型: {type_name}")

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
            self.txt_decoded_display.setText(decoded_text)

            self.lbl_info.setText(
                f"文件: {os.path.basename(fn)} | 大小: {len(data)} 字节"
            )

        except Exception as e:
            QMessageBox.critical(self, "读取错误", f"无法读取或处理文件:\n{str(e)}")
            self.lbl_info.setText("读取失败。")
