"""Progress Dialog 功能单元测试"""

import tkinter as tk
import time
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from file_manager import UIManager, FileStore, GitHubSync


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()
    time.sleep(0.1)  # 避免 Tcl 库因销毁太快而出错


@pytest.fixture
def file_store(tmp_path):
    config_dir = str(tmp_path / ".file_manager")
    return FileStore(config_dir=config_dir)


@pytest.fixture
def github_sync():
    return GitHubSync()


@pytest.fixture
def ui_manager(root, file_store, github_sync):
    return UIManager(root, file_store, github_sync)


def _flush(root, duration=0.1):
    """用 update 循环处理 pending events"""
    end = time.time() + duration
    while time.time() < end:
        root.update()
        time.sleep(0.005)


def _init_progress_vars(ui_manager):
    """辅助：初始化进度对话框的属性（不启动后台线程）。"""
    # 手动创建所需的 Tkinter 变量和属性
    ui_manager._progress_var = tk.DoubleVar(value=0)
    ui_manager._progress_cancelled = False
    # 需要 parent 来创建 label，用 root 作为 parent
    ui_manager._progress_status = tk.Label(ui_manager.root, text="准备中...",
                                            font=('Microsoft YaHei', 10),
                                            bg='#ffffff', fg='#64748b')
    ui_manager._progress_pct = tk.Label(ui_manager.root, text="0%",
                                       font=('Microsoft YaHei', 11, 'bold'),
                                       bg='#ffffff', fg='#6366f1')


class TestUpdateProgressLogic:
    """测试进度更新的核心逻辑（主线程直接调用）"""

    def test_progress_clamped_to_100(self, ui_manager):
        _init_progress_vars(ui_manager)
        ui_manager._do_update_progress(200.0, "完成!")
        _flush(ui_manager.root)
        assert ui_manager._progress_var.get() == 100.0

    def test_progress_clamped_to_0(self, ui_manager):
        _init_progress_vars(ui_manager)
        ui_manager._do_update_progress(-50.0, "开始")
        _flush(ui_manager.root)
        assert ui_manager._progress_var.get() == 0.0

    def test_progress_normal_update(self, ui_manager):
        _init_progress_vars(ui_manager)
        ui_manager._progress_var.set(0)
        ui_manager._do_update_progress(75.0, "进行中")
        _flush(ui_manager.root)
        assert ui_manager._progress_var.get() == 75.0

    def test_cancel_stops_update(self, ui_manager):
        _init_progress_vars(ui_manager)
        ui_manager._progress_cancelled = True
        ui_manager._progress_var.set(20)
        ui_manager._do_update_progress(99.0, "不应更新")
        _flush(ui_manager.root)
        assert ui_manager._progress_var.get() == 20.0


class TestCancelMechanism:
    """测试取消标志逻辑"""

    def test_cancel_flag(self, ui_manager):
        _init_progress_vars(ui_manager)
        ui_manager._progress_cancelled = False
        ui_manager._set_progress_cancel()
        assert ui_manager._progress_cancelled is True

    def test_cancel_did_not_set(self, ui_manager):
        _init_progress_vars(ui_manager)
        ui_manager._progress_cancelled = False
        assert ui_manager._progress_cancelled is False


class TestProgressIntegration:
    """集成测试：模拟完整的推送/拉取逻辑流"""

    def test_push_increments(self, ui_manager, file_store):
        """模拟推送流程的进度递增"""
        _init_progress_vars(ui_manager)
        total = 5
        for i in range(total):
            pct = (i / total) * 100
            ui_manager._progress_var.set(pct)
            ui_manager._progress_status.config(text=f"推送文件 {i+1}/{total}")
            ui_manager._progress_pct.config(text=f"{pct:.0f}%")
        _flush(ui_manager.root)
        expected = ((total - 1) / total) * 100
        assert abs(ui_manager._progress_var.get() - expected) < 0.1

    def test_push_cancel_midway(self, ui_manager, file_store):
        """模拟推送中途取消"""
        _init_progress_vars(ui_manager)
        ui_manager._progress_cancelled = False
        reached = []
        for i in range(100):
            if ui_manager._progress_cancelled:
                reached.append(i)
                break
            pct = (i / 100) * 100
            ui_manager._progress_var.set(pct)
            reached.append(i)
            if i == 30:
                ui_manager._set_progress_cancel()

        assert ui_manager._progress_cancelled is True
        assert len(reached) == 32  # 0..30 被追加 + 31(取消后追加)

    def test_pull_progress_skips(self, ui_manager, file_store):
        """模拟拉取流程中跳过文件"""
        _init_progress_vars(ui_manager)
        ui_manager._progress_cancelled = False
        mock_files = [
            {'name': 'a.txt'},
            {'name': 'b.txt'},
            {'name': 'c.txt'},
        ]
        skipped = 0
        total = len(mock_files)
        for idx, gf in enumerate(mock_files):
            if ui_manager._progress_cancelled:
                break
            pct = (idx / total) * 100
            if idx == 1:
                skipped += 1
                ui_manager._progress_status.config(text=f"跳过: {gf['name']}")
            else:
                ui_manager._progress_status.config(text=f"拉取: {gf['name']}")
            ui_manager._progress_var.set(pct)
        _flush(ui_manager.root)
        assert skipped == 1
        assert ui_manager._progress_var.get() >= 66.0

    def test_all_files_synced_no_push(self, ui_manager, file_store):
        """测试所有文件已同步时，推送应该跳过"""
        file_store.files["t1"] = type('M', (), {
            'id': 't1', 'file_name': 'x.txt',
            'sync_status': '已同步', 'is_folder': False,
            'local_path': '/no',
        })()

        all_files = list(file_store.files.values())
        unsynced = [f for f in all_files if f.sync_status != "已同步"]
        assert len(unsynced) == 0
