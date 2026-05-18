"""GitHubSync 类单元测试"""

import pytest
from unittest.mock import patch, MagicMock
from file_manager import GitHubSync

class MockGithubException(Exception):
    """模拟 GithubException"""
    def __init__(self, status, data, headers=None):
        self.status = status
        self.data = data
        self.headers = headers or {}
        super().__init__(data.get('message', ''))

@pytest.fixture(autouse=True)
def mock_github_exception():
    """自动为所有测试 mock GithubException"""
    with patch("file_manager.GithubException", MockGithubException):
        yield


class TestGitHubSyncInit:
    """测试初始化状态"""

    def test_default_state(self):
        sync = GitHubSync()
        assert sync.github_token == ""
        assert sync.repo_name == ""
        assert sync.branch == "main"
        assert sync.github_api is None
        assert sync.repo is None
        assert sync.connected is False


class TestNotConnected:
    """测试未连接时的操作"""

    def test_push_file_not_connected(self):
        sync = GitHubSync()
        success, msg = sync.push_file("/tmp/f.txt", "f.txt")
        assert success is False
        assert "未连接" in msg

    def test_pull_file_not_connected(self):
        sync = GitHubSync()
        success, msg = sync.pull_file("f.txt", "/tmp/f.txt")
        assert success is False
        assert "未连接" in msg

    def test_delete_file_not_connected(self):
        sync = GitHubSync()
        success, msg = sync.delete_file("f.txt")
        assert success is False
        assert "未连接" in msg

    def test_get_file_list_not_connected(self):
        sync = GitHubSync()
        success, files, msg = sync.get_file_list()
        assert success is False
        assert files == []
        assert "未连接" in msg


class TestDisconnect:
    """测试断开连接"""

    def test_disconnect(self):
        sync = GitHubSync()
        sync.connected = True
        sync.github_api = MagicMock()
        sync.repo = MagicMock()
        sync.disconnect()
        assert sync.connected is False
        assert sync.github_api is None
        assert sync.repo is None


class TestConnect:
    """测试连接逻辑"""

    @patch("file_manager.GITHUB_AVAILABLE", True)
    @patch("file_manager.Github")
    def test_connect_success(self, mock_github_cls):
        mock_api = MagicMock()
        mock_repo = MagicMock()
        mock_github_cls.return_value = mock_api
        mock_api.get_repo.return_value = mock_repo
        mock_repo.get_branch.return_value = MagicMock()

        sync = GitHubSync()
        success, msg = sync.connect("ghp_token", "user/repo", "main")
        assert success is True
        assert "成功" in msg
        assert sync.connected is True

    @patch("file_manager.GITHUB_AVAILABLE", True)
    @patch("file_manager.Github")
    def test_connect_invalid_token(self, mock_github_cls):
        mock_api = MagicMock()
        mock_github_cls.return_value = mock_api
        mock_api.get_repo.side_effect = Exception("401 Unauthorized")

        sync = GitHubSync()
        success, msg = sync.connect("bad_token", "user/repo")
        assert success is False
        assert "令牌" in msg
        assert sync.connected is False

    @patch("file_manager.GITHUB_AVAILABLE", True)
    @patch("file_manager.Github")
    def test_connect_repo_not_found(self, mock_github_cls):
        mock_api = MagicMock()
        mock_github_cls.return_value = mock_api
        mock_api.get_repo.side_effect = Exception("404 Not Found")

        sync = GitHubSync()
        success, msg = sync.connect("ghp_token", "user/nonexistent")
        assert success is False
        assert "不存在" in msg

    @patch("file_manager.GITHUB_AVAILABLE", False)
    def test_connect_no_pygithub(self):
        sync = GitHubSync()
        success, msg = sync.connect("token", "user/repo")
        assert success is False
        assert "PyGitHub" in msg


class TestPushFile:
    """测试推送文件（mock GitHub API）"""

    @patch("file_manager.GITHUB_AVAILABLE", True)
    def test_push_new_file(self, tmp_path):
        sync = GitHubSync()
        sync.connected = True
        sync.branch = "main"
        sync.repo = MagicMock()
        sync.repo.get_contents.side_effect = MockGithubException(404, {"message": "Not Found"})
        sync.repo.create_file.return_value = MagicMock()

        src = tmp_path / "new.txt"
        src.write_text("content", encoding="utf-8")
        success, msg = sync.push_file(str(src), "new.txt")
        assert success is True
        assert "上传" in msg

    @patch("file_manager.GITHUB_AVAILABLE", True)
    def test_push_update_existing_file(self, tmp_path):
        sync = GitHubSync()
        sync.connected = True
        sync.branch = "main"
        sync.repo = MagicMock()
        mock_existing = MagicMock()
        mock_existing.sha = "abc123"
        sync.repo.get_contents.return_value = mock_existing
        sync.repo.update_file.return_value = MagicMock()

        src = tmp_path / "existing.txt"
        src.write_text("updated", encoding="utf-8")
        success, msg = sync.push_file(str(src), "existing.txt")
        assert success is True
        assert "更新" in msg
