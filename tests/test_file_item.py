"""FileItem 类单元测试"""

import pytest
from file_manager import FileItem


class TestFileItemInit:
    """测试 FileItem 初始化"""

    def test_default_init(self):
        item = FileItem(
            file_id="abc123",
            file_name="test.txt",
            file_type=".txt",
            file_size=1024,
            local_path="/tmp/test.txt"
        )
        assert item.id == "abc123"
        assert item.file_name == "test.txt"
        assert item.file_type == ".txt"
        assert item.file_size == 1024
        assert item.github_path == ""
        assert item.sync_status == "未同步"
        assert item.is_folder is False

    def test_folder_init(self):
        item = FileItem(
            file_id="folder1",
            file_name="my_folder",
            file_type="",
            file_size=0,
            local_path="/tmp/my_folder",
            is_folder=True
        )
        assert item.is_folder is True


class TestFormatSize:
    """测试 format_size 方法"""

    def test_bytes(self):
        item = FileItem("1", "f.txt", ".txt", 500, "/tmp/f.txt")
        assert item.format_size() == "500.00 B"

    def test_kilobytes(self):
        item = FileItem("1", "f.txt", ".txt", 2048, "/tmp/f.txt")
        assert item.format_size() == "2.00 KB"

    def test_megabytes(self):
        item = FileItem("1", "f.txt", ".txt", 5 * 1024 * 1024, "/tmp/f.txt")
        assert item.format_size() == "5.00 MB"

    def test_gigabytes(self):
        item = FileItem("1", "f.txt", ".txt", 2 * 1024 ** 3, "/tmp/f.txt")
        assert item.format_size() == "2.00 GB"

    def test_folder_returns_placeholder(self):
        item = FileItem("1", "dir", "", 0, "/tmp/dir", is_folder=True)
        assert item.format_size() == "<文件夹>"


class TestSerialization:
    """测试 to_dict / from_dict 序列化"""

    def test_roundtrip(self):
        original = FileItem(
            file_id="x1",
            file_name="doc.md",
            file_type=".md",
            file_size=2048,
            local_path="/data/doc.md",
            github_path="docs/doc.md",
            update_time="2025-01-01 12:00:00",
            sync_status="已同步",
            is_folder=False
        )
        d = original.to_dict()
        restored = FileItem.from_dict(d)
        assert restored.id == original.id
        assert restored.file_name == original.file_name
        assert restored.file_type == original.file_type
        assert restored.file_size == original.file_size
        assert restored.local_path == original.local_path
        assert restored.github_path == original.github_path
        assert restored.sync_status == original.sync_status
        assert restored.is_folder == original.is_folder

    def test_from_dict_missing_keys(self):
        d = {"id": "1", "file_name": "a.txt"}
        item = FileItem.from_dict(d)
        assert item.id == "1"
        assert item.file_name == "a.txt"
        assert item.file_size == 0
        assert item.sync_status == "未同步"


class TestIsTextFile:
    """测试 is_text_file 方法"""

    @pytest.mark.parametrize("ext", [".txt", ".md", ".py", ".js", ".html", ".json", ".yaml", ".sql"])
    def test_text_extensions(self, ext):
        item = FileItem("1", f"file{ext}", ext, 100, f"/tmp/file{ext}")
        assert item.is_text_file() is True

    @pytest.mark.parametrize("ext", [".jpg", ".png", ".exe", ".zip", ".mp4", ".pdf"])
    def test_binary_extensions(self, ext):
        item = FileItem("1", f"file{ext}", ext, 100, f"/tmp/file{ext}")
        assert item.is_text_file() is False

    def test_folder_not_text(self):
        item = FileItem("1", "dir", "", 0, "/tmp/dir", is_folder=True)
        assert item.is_text_file() is False


class TestGetCategory:
    """测试 get_category 方法"""

    def test_folder(self):
        item = FileItem("1", "dir", "", 0, "/tmp/dir", is_folder=True)
        assert item.get_category() == "文件夹"

    @pytest.mark.parametrize("ext,expected", [
        (".txt", "文档"), (".md", "文档"), (".pdf", "文档"),
        (".py", "代码"), (".js", "代码"), (".java", "代码"),
        (".jpg", "图片"), (".png", "图片"),
        (".zip", "压缩包"), (".rar", "压缩包"),
        (".exe", "其他"), (".mp3", "其他"),
    ])
    def test_categories(self, ext, expected):
        item = FileItem("1", f"file{ext}", ext, 100, f"/tmp/file{ext}")
        assert item.get_category() == expected


class TestGetIcon:
    """测试 get_icon 方法"""

    def test_folder_icon(self):
        item = FileItem("1", "dir", "", 0, "/tmp/dir", is_folder=True)
        assert item.get_icon() == "📁"

    def test_doc_icon(self):
        item = FileItem("1", "readme.md", ".md", 100, "/tmp/readme.md")
        assert item.get_icon() == "📄"

    def test_code_icon(self):
        item = FileItem("1", "app.py", ".py", 100, "/tmp/app.py")
        assert item.get_icon() == "💻"
