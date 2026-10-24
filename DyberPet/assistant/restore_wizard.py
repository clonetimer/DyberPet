"""Standalone offline restore wizard; never imports settings or starts PetWidget.

The main application must exit before the wizard acquires the same singleton
guard used by the regular GUI. The lock is retained until restore is complete.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout,
)

from .offline_restore import (
    data_directory, recover_interrupted_restore, restore_backup,
)
from .save_snapshot import BackupError, verify_backup


class RestoreWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.archive = None
        self._single_instance = None
        self.setWindowTitle("DyberPet · 安全恢复完整存档")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        self.notice = QLabel(
            "此窗口独立于桌宠运行。选择此前保存的完整 ZIP，校验通过后才可恢复。"
            "请确保原桌宠已经完全退出；否则程序会拒绝修改存档。", self)
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.target = QLabel("恢复位置：" + str(data_directory()), self)
        self.target.setWordWrap(True)
        layout.addWidget(self.target)
        self.selection = QLabel("尚未选择备份 ZIP", self)
        self.selection.setWordWrap(True)
        layout.addWidget(self.selection)
        self.summary = QLabel(
            "原数据将在恢复前生成 SHA-256 备份，并保留一份原始 data 目录。"
            "不会恢复或覆盖角色图集、语音或模型。", self)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        row = QHBoxLayout()
        self.browse = QPushButton("1. 选择并校验 ZIP", self)
        self.browse.clicked.connect(self.select_archive)
        self.commit = QPushButton("2. 确认恢复", self)
        self.commit.setEnabled(False)
        self.commit.clicked.connect(self.apply_restore)
        self.cancel = QPushButton("取消", self)
        self.cancel.clicked.connect(self.reject)
        row.addWidget(self.browse)
        row.addWidget(self.commit)
        row.addWidget(self.cancel)
        layout.addLayout(row)

    def select_archive(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 DyberPet 完整存档", str(Path.home()), "ZIP (*.zip)")
        if not path:
            return
        try:
            report = verify_backup(path)
        except (BackupError, OSError) as exc:
            self.archive = None
            self.commit.setEnabled(False)
            QMessageBox.warning(self, "备份校验失败", str(exc))
            return
        self.archive = path
        self.selection.setText("已校验：" + path)
        self.summary.setText(
            "包含：" + ", ".join(report["files"]) + "。"
            "不会覆盖角色资源；恢复前保留现有数据并创建独立备份。")
        self.commit.setEnabled(True)

    def apply_restore(self):
        if not self.archive:
            return
        answer = QMessageBox.question(
            self, "最终确认",
            "恢复将替换当前设置和养成记录。原数据会另行备份，"
            "但个人角色、语音和模型不会从 ZIP 中恢复。\n"
            "确定原桌宠已经退出并继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            from tendo import singleton
            # This is the same singleton name and executable used by the main app.
            # A running DyberPet process must hold it, so restore is refused.
            if self._single_instance is None:
                self._single_instance = singleton.SingleInstance()
        except Exception:
            QMessageBox.warning(
                self, "桌宠仍在运行",
                "尚未获得独占运行锁。请从系统托盘完全退出 DyberPet，"
                "再回到此窗口点击「确认恢复」。当前数据没有被修改。")
            return
        self.commit.setEnabled(False)
        try:
            recover_interrupted_restore(data_directory())
            result = restore_backup(self.archive, data_directory())
        except (OSError, BackupError, ValueError) as exc:
            self.commit.setEnabled(True)
            QMessageBox.critical(self, "恢复未成功", str(exc))
            return
        QMessageBox.information(
            self, "恢复成功",
            "已恢复：" + ", ".join(result["restored"])
            + "\n恢复前 ZIP：" + result["pre_restore_archive"]
            + "\n原始目录：" + result["pre_restore_directory"]
            + "\n可以重新启动 DyberPet。")
        self.accept()


def run_restore_wizard():
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = RestoreWizard()
    dialog.exec()
    return 0
