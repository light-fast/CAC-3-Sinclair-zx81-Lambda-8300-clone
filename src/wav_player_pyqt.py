import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGroupBox, QFileDialog, QLineEdit)


class WAVPlayerDialog(QDialog):
    """WAV文件选择对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WAV文件选择")
        self.resize(500, 150)
        self.setModal(True)
        
        self.filename = None
        
        # 构建UI
        self._build_ui()
        
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 文件选择区域
        file_frame = QGroupBox("文件选择")
        file_layout = QHBoxLayout()
        
        file_layout.addWidget(QLabel("WAV文件:"))
        self.file_path_var = QLineEdit()
        self.file_path_var.setReadOnly(True)
        file_layout.addWidget(self.file_path_var)
        
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(self.btn_browse)
        
        file_frame.setLayout(file_layout)
        main_layout.addWidget(file_frame)
        
        # 确认和取消按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_confirm = QPushButton("确定")
        self.btn_confirm.clicked.connect(self.confirm)
        self.btn_confirm.setEnabled(False)
        button_layout.addWidget(self.btn_confirm)
        
        main_layout.addLayout(button_layout)
    
    def browse_file(self):
        """浏览并选择WAV文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择WAV文件", "", "WAV文件 (*.wav);;所有文件 (*.*)"
        )
        if filename:
            self.filename = filename
            self.file_path_var.setText(filename)
            self.btn_confirm.setEnabled(True)
    
    def confirm(self):
        """确认选择，返回文件路径"""
        if self.filename is None:
            return
        self.accept()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        event.accept()
    
    def get_filename(self):
        """获取选择的文件名"""
        return self.filename
