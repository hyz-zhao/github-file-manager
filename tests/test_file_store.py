"""FileStore 类单元测试"""

import json
import os
import pytest
from file_manager import FileStore


@pytest.fixture
def store(tmp_path):
    """创建隔离的 FileStore 实例"""
    config_dir = str(tmp_path / ".file_manager")
    return FileStore(config_dir=config_dir)


class TestTokenEncryption:
    """测试令牌加密/解密"""

    def test_encrypt_decrypt_roundtrip(self, store):
        token = "ghp_ABC123xyz"
        encrypted = store._encrypt_token(token)
        assert encrypted != token
        decrypted = store._decrypt_token(encrypted)
        assert decrypted == token

    def test_encrypt_empty(self, store):
        assert store._encrypt_token("") == ""

    def test_decrypt_empty(self, store):
        assert store._decrypt_token("") == ""

    def test_decrypt_invalid(self, store):
        assert store._decrypt_token("not-valid-base64!!!") == ""


class TestConfigPersistence:
    """测试配置加载/保存"""

    def test_save_and_load_config(self, store):
        store.save_config(
            token="ghp_test",
            repo_name="user/repo",
            branch="develop",
            auto_sync=True
        )
        assert os.path.exists(store.config_path)

        store2 = FileStore(config_dir=store.config_dir)
        store2.load_config()
        assert store2.github_config['token'] == "ghp_test"
        assert store2.github_config['repo_name'] == "user/repo"
        assert store2.github_config['branch'] == "develop"
        assert store2.github_config['auto_sync'] is True

    def test_load_nonexistent_config(self, store):
        result = store.load_config()
        assert result is False

    def test_save_partial_config(self, store):
        store.save_config(token="ghp_a")
        assert store.github_config['token'] == "ghp_a"
        store.save_config(repo_name="u/r")
        assert store.github_config['token'] == "ghp_a"
        assert store.github_config['repo_name'] == "u/r"


class TestFileOperations:
    """测试文件操作"""

    def test_add_file(self, store, tmp_path):
        src = tmp_path / "test.txt"
        src.write_text("hello", encoding="utf-8")
        success, msg, item = store.add_file(str(src))
        assert success is True
        assert item is not None
        assert item.file_name == "test.txt"
        assert item.file_size == 5

    def test_add_nonexistent_file(self, store):
        success, msg, item = store.add_file("/nonexistent/file.txt")
        assert success is False
        assert item is None

    def test_delete_file(self, store, tmp_path):
        src = tmp_path / "to_delete.txt"
        src.write_text("delete me", encoding="utf-8")
        _, _, item = store.add_file(str(src))
        success, msg = store.delete_file(item.id)
        assert success is True
        assert item.id not in store.files

    def test_rename_file(self, store, tmp_path):
        src = tmp_path / "old_name.txt"
        src.write_text("content", encoding="utf-8")
        _, _, item = store.add_file(str(src))
        success, msg = store.rename_file(item.id, "new_name.txt")
        assert success is True
        assert store.files[item.id].file_name == "new_name.txt"

    def test_rename_empty_name(self, store, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("x", encoding="utf-8")
        _, _, item = store.add_file(str(src))
        success, msg = store.rename_file(item.id, "")
        assert success is False


class TestFolderOperations:
    """测试文件夹操作"""

    def test_create_folder(self, store):
        success, msg, item = store.create_folder("my_folder")
        assert success is True
        assert item.is_folder is True
        assert item.file_name == "my_folder"

    def test_create_duplicate_folder(self, store):
        store.create_folder("dup")
        success, msg, item = store.create_folder("dup")
        assert success is False

    def test_create_empty_name_folder(self, store):
        success, msg, item = store.create_folder("")
        assert success is False


class TestSearch:
    """测试搜索功能"""

    def test_search_all(self, store, tmp_path):
        src = tmp_path / "search_test.txt"
        src.write_text("content", encoding="utf-8")
        store.add_file(str(src))
        results = store.search("", "全部")
        assert len(results) >= 1

    def test_search_by_keyword(self, store, tmp_path):
        src = tmp_path / "unique_name.xyz"
        src.write_text("content", encoding="utf-8")
        store.add_file(str(src))
        results = store.search("unique_name", "全部")
        assert any(f.file_name == "unique_name.xyz" for f in results)

    def test_search_no_match(self, store, tmp_path):
        src = tmp_path / "abc.txt"
        src.write_text("content", encoding="utf-8")
        store.add_file(str(src))
        results = store.search("zzz_nonexistent_zzz", "全部")
        assert len(results) == 0


class TestFilePersistence:
    """测试文件索引持久化"""

    def test_save_and_load_files(self, store, tmp_path):
        src = tmp_path / "persist.txt"
        src.write_text("data", encoding="utf-8")
        store.add_file(str(src))

        store2 = FileStore(config_dir=store.config_dir)
        store2.load_files()
        assert any(f.file_name == "persist.txt" for f in store2.files.values())
