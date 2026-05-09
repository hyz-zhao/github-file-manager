#!/bin/bash
# GitHub文件管理器 - 打包脚本 (Linux/Mac)

echo "========================================"
echo "  GitHub文件管理器 - 打包脚本"
echo "========================================"
echo

echo "[1/4] 检查Python环境..."
python3 --version
if [ $? -ne 0 ]; then
    echo "错误：未找到Python，请先安装Python"
    exit 1
fi

echo
echo "[2/4] 安装依赖包..."
pip3 install -r requirements.txt

echo
echo "[3/4] 开始打包程序..."
pyinstaller --clean --noconfirm build.spec

echo
echo "[4/4] 打包完成！"
echo
echo "输出目录：dist/"
echo "可执行文件：dist/GitHub文件管理器"
echo
echo "========================================"
