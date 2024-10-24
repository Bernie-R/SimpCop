import sys
import os

# Add the 'libs' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
libs_dir = os.path.join(current_dir, 'libs')
sys.path.insert(0, libs_dir)

# Now you can import packages from 'libs'
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTreeView, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QFileSystemModel, QAbstractItemView, QPushButton,
    QFileDialog, QLabel, QComboBox, QCheckBox, QHeaderView, QToolTip
)
from PyQt5.QtCore import Qt, QDir, QModelIndex
from PyQt5.QtGui import QClipboard, QFont
from PyQt5.QtCore import QFileSystemWatcher

class CheckableFileSystemModel(QFileSystemModel):
    def __init__(self, extensions):
        super().__init__()
        self.checked_indexes = set()
        self.extensions = extensions

    def flags(self, index):
        return super().flags(index) | Qt.ItemIsUserCheckable

    def data(self, index, role):
        if role == Qt.CheckStateRole and index.column() == 0:
            return Qt.Checked if index in self.checked_indexes else Qt.Unchecked
        if role == Qt.DisplayRole and index.column() != 0:
            return None  # Hide other columns
        return super().data(index, role)

    def setData(self, index, value, role):
        if role == Qt.CheckStateRole and index.column() == 0:
            if value == Qt.Checked:
                self.checked_indexes.add(index)
            else:
                self.checked_indexes.discard(index)
            self.dataChanged.emit(index, index)
            self.update_children(index, value)
            self.update_parent(index)
            return True
        return super().setData(index, value, role)

    def update_children(self, index, value):
        for i in range(self.rowCount(index)):
            child = self.index(i, 0, index)
            if self.isDir(child):
                continue  # Skip directories
            self.setData(child, value, Qt.CheckStateRole)

    def update_parent(self, index):
        parent = index.parent()
        if parent.isValid():
            checked = 0
            total = 0
            for i in range(self.rowCount(parent)):
                child = self.index(i, 0, parent)
                if not self.isDir(child):
                    total += 1
                    if child in self.checked_indexes:
                        checked += 1
            if total > 0:
                if checked == total:
                    self.checked_indexes.add(parent)
                elif checked == 0:
                    self.checked_indexes.discard(parent)
                else:
                    # Partial check state can be represented differently if needed
                    self.checked_indexes.add(parent)  # Keeping as checked for simplicity
                self.dataChanged.emit(parent, parent)
                self.update_parent(parent)

    def is_checked(self, index):
        return index in self.checked_indexes

    def index_valid(self, index):
        file_info = self.fileInfo(index)
        return file_info.isDir() or file_info.suffix().lower() in self.extensions

    def get_all_file_indexes(self):
        """Retrieve all file indexes in the model."""
        root = self.index(self.rootPath())
        files = []
        stack = [root]
        while stack:
            parent = stack.pop()
            for i in range(self.rowCount(parent)):
                child = self.index(i, 0, parent)
                if self.isDir(child):
                    stack.append(child)
                else:
                    if self.index_valid(child):
                        files.append(child)
        return files

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Code File Selector")

        self.base_directory = None

        hbox = QHBoxLayout(self)
        splitter = QSplitter()
        hbox.addWidget(splitter)

        self.extensions = [
            'py', 'js', 'ts', 'svelte', 'css', 'html', 'json', 'txt',
            'md', 'xml', 'yml', 'yaml', 'sql', 'jsx', 'tsx', 'php',
            'rb', 'java', 'c', 'cpp', 'cs', 'sh', 'bash', 'go',
            'rs', 'swift', 'kt', 'r', 'dart', 'scala', 'ini',
            'env', 'toml', 'scss', 'less', 'pl', 'lua', 'ps1',
            'vb', 'bat', 'coffee',
        ]

        self.model = CheckableFileSystemModel(self.extensions)

        # Left Side Layout
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Tree Label
        tree_label = QLabel("File Selector")
        left_layout.addWidget(tree_label)

        # Select Base Directory Button
        self.select_base_dir_btn = QPushButton("Select Base Directory")
        self.select_base_dir_btn.clicked.connect(self.select_base_directory)
        left_layout.addWidget(self.select_base_dir_btn)

        # **New: Add Select All and Deselect All Files Buttons**
        button_layout = QHBoxLayout()

        self.select_all_files_btn = QPushButton("Select All Files")
        self.select_all_files_btn.clicked.connect(self.select_all_files)
        button_layout.addWidget(self.select_all_files_btn)

        self.deselect_all_files_btn = QPushButton("Deselect All Files")
        self.deselect_all_files_btn.clicked.connect(self.deselect_all_files)
        button_layout.addWidget(self.deselect_all_files_btn)

        left_layout.addLayout(button_layout)

        # File Tree View
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.tree.clicked.connect(self.tree_item_clicked)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().hideSection(1)  # Hide Size
        self.tree.header().hideSection(2)  # Hide Type
        self.tree.header().hideSection(3)  # Hide Date Modified
        left_layout.addWidget(self.tree)

        splitter.addWidget(left_widget)

        # Right Side Layout
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Tasktype Selection with Checkbox
        tasktype_layout = QHBoxLayout()
        self.tasktype_checkbox = QCheckBox("Include Tasktype")
        self.tasktype_checkbox.setChecked(True)
        tasktype_label = QLabel("Tasktype:")
        self.tasktype_combo = QComboBox()
        self.load_tasktypes()
        self.tasktype_checkbox.stateChanged.connect(self.update_final_prompt)
        self.tasktype_combo.currentIndexChanged.connect(self.update_final_prompt)
        tasktype_layout.addWidget(self.tasktype_checkbox)
        tasktype_layout.addWidget(tasktype_label)
        tasktype_layout.addWidget(self.tasktype_combo)
        right_layout.addLayout(tasktype_layout)

        # Presets Selection with Checkbox
        presets_layout = QHBoxLayout()
        self.presets_checkbox = QCheckBox("Include Preset")
        self.presets_checkbox.setChecked(True)
        presets_label = QLabel("Preset:")
        self.presets_combo = QComboBox()
        self.load_presets()
        self.presets_checkbox.stateChanged.connect(self.update_final_prompt)
        self.presets_combo.currentIndexChanged.connect(self.update_final_prompt)
        presets_layout.addWidget(self.presets_checkbox)
        presets_layout.addWidget(presets_label)
        presets_layout.addWidget(self.presets_combo)
        right_layout.addLayout(presets_layout)

        # Task Instruction Label
        task_instruction_label = QLabel("Task Instruction")
        right_layout.addWidget(task_instruction_label)

        # Task Instruction Text Edit
        self.task_instruction = QTextEdit()
        self.task_instruction.setPlaceholderText("Task Instruction (Raw Prompt)")
        self.task_instruction.textChanged.connect(self.update_final_prompt)
        right_layout.addWidget(self.task_instruction)

        # **New: Difficulty Level Indicator**
        difficulty_layout = QHBoxLayout()
        self.difficulty_label = QLabel("Difficulty Level: ")
        self.difficulty_value_label = QLabel("Easy")  # Default
        self.difficulty_value_label.setStyleSheet("font-weight: bold;")
        # Set tooltip
        self.difficulty_value_label.setToolTip("Low risk of hallucinating")
        difficulty_layout.addWidget(self.difficulty_label)
        difficulty_layout.addWidget(self.difficulty_value_label)
        difficulty_layout.addStretch()  # Push the label to the left
        right_layout.addLayout(difficulty_layout)

        # Final Prompt Label and Token Count
        final_prompt_layout = QHBoxLayout()
        final_prompt_label = QLabel("Final Prompt")
        self.token_count_label = QLabel("Estimated Tokens: 0 / 128000 (0%)")
        self.token_count_label.setToolTip("Estimated number of tokens based on word count")
        final_prompt_layout.addWidget(final_prompt_label)
        final_prompt_layout.addStretch()
        final_prompt_layout.addWidget(self.token_count_label)
        right_layout.addLayout(final_prompt_layout)

        # Final Prompt Text Edit
        self.final_prompt = QTextEdit()
        right_layout.addWidget(self.final_prompt)

        # Set stretch factors
        right_layout.setStretchFactor(self.task_instruction, 1)
        right_layout.setStretchFactor(self.final_prompt, 2)

        # Copy Button
        self.copy_button = QPushButton("Copy Output")
        self.copy_button.clicked.connect(self.copy_output)
        right_layout.addWidget(self.copy_button)

        splitter.addWidget(right_widget)

        # File System Watcher for live updates
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.fileChanged.connect(self.file_changed)

        # Load last directory if exists
        self.load_last_directory()

        # Apply Stylesheet
        self.apply_stylesheet()

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                font-family: Arial;
                font-size: 12pt;
            }
            QTreeView {
                background-color: #f0f0f0;
            }
            QTextEdit {
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #007ACC;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #005F9E;
            }
            QLabel {
                font-weight: bold;
            }
        """)

    def select_base_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Base Directory", QDir.homePath())
        if directory:
            self.base_directory = directory
            self.model.setRootPath(directory)
            self.tree.setRootIndex(self.model.index(directory))
            self.model.checked_indexes.clear()
            self.update_file_watcher()
            self.update_final_prompt()
            self.save_last_directory(directory)

    def load_presets(self):
        self.presets = {}
        self.presets_combo.clear()
        presets_dir = os.path.join(os.path.dirname(sys.argv[0]), 'presets')
        if os.path.isdir(presets_dir):
            for filename in os.listdir(presets_dir):
                if filename.endswith('.txt'):
                    filepath = os.path.join(presets_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        preset_name = os.path.splitext(filename)[0]
                        self.presets[preset_name] = content
                    except Exception as e:
                        print(f"Error reading preset {filename}: {e}")
            self.presets_combo.addItems(self.presets.keys())

    def load_tasktypes(self):
        self.tasktypes = {}
        self.tasktype_combo.clear()
        tasktypes_dir = os.path.join(os.path.dirname(sys.argv[0]), 'tasktype')
        if os.path.isdir(tasktypes_dir):
            for filename in os.listdir(tasktypes_dir):
                if filename.endswith('.txt'):
                    filepath = os.path.join(tasktypes_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        tasktype_name = os.path.splitext(filename)[0]
                        self.tasktypes[tasktype_name] = content
                    except Exception as e:
                        print(f"Error reading tasktype {filename}: {e}")
            self.tasktype_combo.addItems(self.tasktypes.keys())

    def tree_item_clicked(self, index: QModelIndex):
        self.update_file_watcher()
        self.update_final_prompt()

    def update_file_watcher(self):
        # Remove all paths from watcher
        self.file_watcher.removePaths(self.file_watcher.files())

        # Add currently selected files to watcher
        paths_to_watch = []
        for index in self.model.checked_indexes:
            if self.model.isDir(index):
                continue
            file_path = self.model.filePath(index)
            if os.path.isfile(file_path):
                paths_to_watch.append(file_path)
        if paths_to_watch:
            self.file_watcher.addPaths(paths_to_watch)

    def file_changed(self, path):
        # File has changed, update the final prompt
        self.update_final_prompt()

    def update_final_prompt(self):
        content_list = []

        # Include Tasktype at the top if checkbox is checked
        if self.tasktype_checkbox.isChecked():
            tasktype_name = self.tasktype_combo.currentText()
            if tasktype_name and tasktype_name in self.tasktypes:
                content_list.append(f"<!-- Tasktype: {tasktype_name} -->")
                content_list.append(self.tasktypes[tasktype_name])

        # Include Task Instruction
        content_list.append(f"<!-- Task Instruction -->")
        content_list.append(self.task_instruction.toPlainText())

        # Include selected files
        files_content = []
        selected_file_count = 0  # For difficulty level
        if self.base_directory:
            for index in self.model.checked_indexes.copy():  # Use copy to avoid modification during iteration
                if self.model.isDir(index):
                    continue
                if not self.model.index_valid(index):
                    continue
                file_path = self.model.filePath(index)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    relative_path = os.path.relpath(file_path, self.base_directory)
                    header = f"<!-- {relative_path} -->"
                    footer = f"<!-- end of {relative_path} -->"
                    files_content.append(f"{header}\n{content}\n{footer}")
                    selected_file_count += 1
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
            if files_content:
                content_list.append("<!-- Selected Files -->")
                content_list.append('\n\n'.join(files_content))

        # Include Preset at the bottom if checkbox is checked
        if self.presets_checkbox.isChecked():
            preset_name = self.presets_combo.currentText()
            if preset_name and preset_name in self.presets:
                content_list.append(f"<!-- Preset: {preset_name} -->")
                content_list.append(self.presets[preset_name])

        final_prompt_content = '\n\n'.join(content_list)

        self.final_prompt.setPlainText(final_prompt_content)

        # **New: Update Difficulty Level**
        self.update_difficulty_level(selected_file_count)

        # **New: Update Token Count**
        self.update_token_count(final_prompt_content)

    def copy_output(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.final_prompt.toPlainText())

    def save_last_directory(self, directory):
        config_file = os.path.join(os.path.dirname(sys.argv[0]), 'last_directory.txt')
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(directory)
        except Exception as e:
            print(f"Error saving last directory: {e}")

    def load_last_directory(self):
        config_file = os.path.join(os.path.dirname(sys.argv[0]), 'last_directory.txt')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    directory = f.read().strip()
                if os.path.isdir(directory):
                    self.base_directory = directory
                    self.model.setRootPath(directory)
                    self.tree.setRootIndex(self.model.index(directory))
                    self.update_final_prompt()
            except Exception as e:
                print(f"Error loading last directory: {e}")

    # **New: Select All Files Method**
    def select_all_files(self):
        if not self.base_directory:
            return
        file_indexes = self.model.get_all_file_indexes()
        for index in file_indexes:
            self.model.setData(index, Qt.Checked, Qt.CheckStateRole)
        self.update_final_prompt()

    # **New: Deselect All Files Method**
    def deselect_all_files(self):
        if not self.base_directory:
            return
        file_indexes = self.model.get_all_file_indexes()
        for index in file_indexes:
            self.model.setData(index, Qt.Unchecked, Qt.CheckStateRole)
        self.update_final_prompt()

    # **New: Update Difficulty Level**
    def update_difficulty_level(self, file_count):
        if file_count <= 2:
            level = "Easy"
            tooltip = "Low risk of hallucinating"
            color = "green"
        elif 3 <= file_count <= 5:
            level = "Moderate"
            tooltip = "Slight risk of hallucinating"
            color = "orange"
        else:
            level = "Hard"
            tooltip = "High risk of hallucinating"
            color = "red"

        self.difficulty_value_label.setText(level)
        self.difficulty_value_label.setToolTip(tooltip)
        self.difficulty_value_label.setStyleSheet(f"font-weight: bold; color: {color};")

    # **New: Update Token Count**
    def update_token_count(self, text):
        word_count = len(text.split())
        estimated_tokens = int(word_count * 1.2)
        max_tokens = 128000
        percentage = (estimated_tokens / max_tokens) * 100 if max_tokens else 0
        percentage = min(percentage, 100)  # Cap at 100%

        self.token_count_label.setText(f"Estimated Tokens: {estimated_tokens} / {max_tokens} ({percentage:.2f}%)")

    # **Optional: Override closeEvent to save state if needed**
    # def closeEvent(self, event):
    #     # Implement if you need to save state on close
    #     event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
