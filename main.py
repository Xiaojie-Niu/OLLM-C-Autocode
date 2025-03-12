import sys
import os
import configparser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QPushButton, QComboBox, QMessageBox, QProgressBar,
    QTextEdit, QFileDialog, QTabWidget, QLineEdit, QGroupBox,
    QGridLayout, QScrollArea, QSplitter, QHBoxLayout, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from processor import TextProcessor

class ProcessingThread(QThread):
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    # 添加新的信号，用于实时更新预览
    preview_signal = pyqtSignal(str, str, str)  # prompt, human_code, model_code

    def __init__(self, file_path: str, save_path: str, mode: str, api_settings: dict, prompt: str, delay_seconds: int):
        super().__init__()
        self.file_path = file_path
        self.save_path = save_path
        self.mode = mode
        self.api_settings = api_settings
        self.prompt = prompt
        self.delay_seconds = delay_seconds
        self.processor = TextProcessor(api_settings, self.update_progress)

    def update_progress(self, current: int, total: int):
        self.progress_signal.emit(current, total)

    def run(self):
        try:
            # 修改processor类以传递预览信号和延时设置
            self.processor.set_preview_callback(self.send_preview)
            self.processor.set_delay_seconds(self.delay_seconds)
            results = self.processor.process_file(
                self.file_path, 
                self.save_path,
                self.mode, 
                self.prompt
            )
            self.finished_signal.emit(results)
        except Exception as e:
            self.error_signal.emit(str(e))

    def send_preview(self, prompt: str, human_code: str, model_code: str):
        self.preview_signal.emit(prompt, human_code, model_code)

class CodingSystemGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("编码系统")
        self.setMinimumSize(1200, 900)  # 增加窗口尺寸以容纳预览

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        tabs.addTab(self.create_main_tab(), "主要功能")
        tabs.addTab(self.create_settings_tab(), "设置")

    def create_main_tab(self):
        widget = QWidget()
        main_layout = QVBoxLayout(widget)

        # 创建水平分割器，左侧是操作区，右侧是预览区
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧操作区
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 文件选择区域
        file_group = self.create_file_group()
        left_layout.addWidget(file_group)

        # 提示词编辑区域
        prompt_group = self.create_prompt_group()
        left_layout.addWidget(prompt_group)

        # 任务控制区域
        task_group = self.create_task_group()
        left_layout.addWidget(task_group)

        # 进度显示区域
        progress_group = self.create_progress_group()
        left_layout.addWidget(progress_group)
        
        splitter.addWidget(left_widget)
        
        # 右侧预览区
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        preview_group = self.create_preview_group()
        right_layout.addWidget(preview_group)
        splitter.addWidget(right_widget)
        
        # 设置分割器的初始大小
        splitter.setSizes([600, 600])

        return widget

    def create_file_group(self):
        group = QGroupBox("文件选择")
        layout = QGridLayout()

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        browse_button = QPushButton("选择文件")
        browse_button.clicked.connect(self.browse_file)

        self.save_path_edit = QLineEdit()
        self.save_path_edit.setReadOnly(True)
        save_browse_button = QPushButton("保存位置")
        save_browse_button.clicked.connect(self.browse_save_location)

        layout.addWidget(QLabel("输入文件:"), 0, 0)
        layout.addWidget(self.file_path_edit, 0, 1)
        layout.addWidget(browse_button, 0, 2)
        layout.addWidget(QLabel("保存位置:"), 1, 0)
        layout.addWidget(self.save_path_edit, 1, 1)
        layout.addWidget(save_browse_button, 1, 2)

        group.setLayout(layout)
        return group

    def create_prompt_group(self):
        group = QGroupBox("提示词编辑")
        layout = QVBoxLayout()

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("选择文件后将自动加载提示词，您也可以手动编辑...")
        self.prompt_edit.setMinimumHeight(150)
        layout.addWidget(self.prompt_edit)

        group.setLayout(layout)
        return group

    def create_task_group(self):
        group = QGroupBox("任务控制")
        layout = QGridLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["校准", "编码"])

        # 添加延时设置控件
        layout.addWidget(QLabel("结果显示延时(秒):"), 0, 0)
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setMinimum(1)
        self.delay_spinbox.setMaximum(10)
        self.delay_spinbox.setValue(3)  # 默认3秒
        layout.addWidget(self.delay_spinbox, 0, 1)

        layout.addWidget(QLabel("任务模式:"), 1, 0)
        layout.addWidget(self.mode_combo, 1, 1)
        
        self.start_button = QPushButton("开始处理")
        self.start_button.clicked.connect(self.start_processing)
        layout.addWidget(self.start_button, 1, 2)

        group.setLayout(layout)
        return group

    def create_progress_group(self):
        group = QGroupBox("处理进度和结果")
        layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.status_label = QLabel("就绪")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)
        scroll.setWidget(self.results_display)
        scroll.setMinimumHeight(200)  # 减小高度以适应预览区

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("处理结果:"))
        layout.addWidget(scroll)

        group.setLayout(layout)
        return group
        
    def create_preview_group(self):
        """创建预览区域"""
        group = QGroupBox("实时预览")
        layout = QVBoxLayout()
        
        # 提示词预览
        layout.addWidget(QLabel("发送给模型的提示词:"))
        self.prompt_preview = QTextEdit()
        self.prompt_preview.setReadOnly(True)
        self.prompt_preview.setMinimumHeight(300)
        layout.addWidget(self.prompt_preview)
        
        # 编码结果预览
        results_layout = QHBoxLayout()
        
        # 人工编码
        human_layout = QVBoxLayout()
        human_layout.addWidget(QLabel("人工编码:"))
        self.human_code_preview = QLineEdit()
        self.human_code_preview.setReadOnly(True)
        human_layout.addWidget(self.human_code_preview)
        results_layout.addLayout(human_layout)
        
        # 模型编码
        model_layout = QVBoxLayout()
        model_layout.addWidget(QLabel("模型编码:"))
        self.model_code_preview = QLineEdit()
        self.model_code_preview.setReadOnly(True)
        model_layout.addWidget(self.model_code_preview)
        results_layout.addLayout(model_layout)
        
        layout.addLayout(results_layout)
        
        group.setLayout(layout)
        return group

    def create_settings_tab(self):
        widget = QWidget()
        layout = QGridLayout(widget)

        # API设置
        layout.addWidget(QLabel("API Base URL:"), 0, 0)
        self.base_url_edit = QLineEdit()
        layout.addWidget(self.base_url_edit, 0, 1)

        layout.addWidget(QLabel("API Key:"), 1, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.api_key_edit, 1, 1)

        layout.addWidget(QLabel("Model name:"), 2, 0)
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setText("gpt-4-0613")
        layout.addWidget(self.model_name_edit, 2, 1)

        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button, 3, 1)

        layout.setRowStretch(4, 1)
        return widget

    def browse_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            "选择Excel文件", 
            "", 
            "Excel Files (*.xlsx *.xls)"
        )
        if file_name:
            self.file_path_edit.setText(file_name)
            self.load_prompt_from_file(file_name)

    def browse_save_location(self):
        save_path = QFileDialog.getExistingDirectory(
            self, 
            "选择保存位置", 
            "", 
            QFileDialog.Option.ShowDirsOnly
        )
        if save_path:
            self.save_path_edit.setText(save_path)

    def load_prompt_from_file(self, file_path):
        try:
            processor = TextProcessor(
                {
                    'base_url': self.base_url_edit.text(), 
                    'api_key': self.api_key_edit.text(),
                    'model': self.model_name_edit.text()
                },
                lambda x, y: None
            )
            coding_results, code_df, notes = processor.read_excel_data(file_path)
            if len(coding_results) > 0:
                prompt = processor.generate_prompt(code_df, notes, "[文本]")
                self.prompt_edit.setText(prompt)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载提示词失败: {str(e)}")

    def start_processing(self):
        if not self.validate_inputs():
            return

        # 清空之前的结果显示
        self.results_display.clear()
        self.results_display.append("准备开始处理...")
        
        # 清空预览区
        self.prompt_preview.clear()
        self.human_code_preview.clear()
        self.model_code_preview.clear()

        # 获取用户设置的延时时间
        delay_seconds = self.delay_spinbox.value()

        self.processing_thread = ProcessingThread(
            self.file_path_edit.text(),
            self.save_path_edit.text(),
            'calibrate' if self.mode_combo.currentText() == "校准" else "encode",
            {
                'base_url': self.base_url_edit.text(),
                'api_key': self.api_key_edit.text(),
                'model': self.model_name_edit.text()
            },
            self.prompt_edit.toPlainText(),
            delay_seconds  # 传递延时设置
        )

        self.processing_thread.progress_signal.connect(self.update_progress)
        self.processing_thread.finished_signal.connect(self.show_results)
        self.processing_thread.error_signal.connect(self.show_error)
        self.processing_thread.preview_signal.connect(self.update_preview)

        self.start_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("处理中...")
        self.processing_thread.start()

    def validate_inputs(self):
        if not self.file_path_edit.text():
            QMessageBox.warning(self, "警告", "请选择输入文件")
            return False
        if not self.save_path_edit.text():
            QMessageBox.warning(self, "警告", "请选择保存位置")
            return False
        if not self.base_url_edit.text() or not self.api_key_edit.text():
            QMessageBox.warning(self, "警告", "请在设置中输入API信息")
            return False
        return True

    def update_progress(self, current, total):
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.status_label.setText(f"处理中... {progress}%")

    def update_preview(self, prompt, human_code, model_code):
        """更新预览区域的内容"""
        self.prompt_preview.setText(prompt)
        self.human_code_preview.setText(human_code)
        self.model_code_preview.setText(model_code)
        
        # 设置文本颜色来突出显示变化
        if model_code == "处理中...":
            self.model_code_preview.setStyleSheet("color: blue;")
        elif human_code != "N/A" and model_code == human_code:
            self.model_code_preview.setStyleSheet("color: green;")
        elif human_code != "N/A" and model_code != human_code:
            self.model_code_preview.setStyleSheet("color: red;")
        else:
            self.model_code_preview.setStyleSheet("color: black;")

    def show_results(self, results):
        self.start_button.setEnabled(True)
        self.progress_bar.setValue(100)

        # 清空之前的结果显示
        self.results_display.clear()

        # 显示实时处理结果
        display_text = []
        display_text.append(f"正在处理文件...\n")
        display_text.append(f"文件包含 {results['total']} 条待编码文本\n")

        # 添加每条文本的处理结果
        for output_lines in results['realtime_outputs']:
            display_text.extend(output_lines)
            display_text.append("-" * 50)

        # 添加总体统计信息
        display_text.extend([
            "\n总体统计：",
            "=" * 50,
            f"准确率: {results['accuracy']:.4f}" if 'accuracy' in results else "",
            f"总处理数: {results['processed']}/{results['total']}",
            f"处理时间: {results['time']:.2f}秒",
            f"\n结果已保存至: {results['save_file']}"
        ])

        # 更新显示
        self.results_display.setText("\n".join(display_text))
        self.status_label.setText("处理完成")

        # 显示简要统计弹窗
        brief_result = (
            f"处理完成\n"
            f"{'准确率: ' + f'{results['accuracy']:.2%}\\n' if 'accuracy' in results else ''}"
            f"处理时间: {results['time']:.1f}秒\n"
            f"总处理数: {results['processed']}/{results['total']}\n"
            f"\n结果文件：\n{results['save_file']}"
        )
        QMessageBox.information(self, "完成", brief_result)

    def show_error(self, error_msg):
        self.start_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("处理失败")
        self.results_display.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", f"处理出错: {error_msg}")

    def load_settings(self):
        config = configparser.ConfigParser()
        if os.path.exists('config.ini'):
            config.read('config.ini')
            self.base_url_edit.setText(config.get('API', 'base_url', fallback=''))
            self.api_key_edit.setText(config.get('API', 'api_key', fallback=''))
            self.model_name_edit.setText(config.get('API', 'model', fallback='gpt-4-0613'))

    def save_settings(self):
        try:
            config = configparser.ConfigParser()
            config['API'] = {
                'base_url': self.base_url_edit.text(),
                'api_key': self.api_key_edit.text(),
                'model': self.model_name_edit.text()
            }
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
            QMessageBox.information(self, "成功", "设置已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = CodingSystemGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
