@echo off
chcp 65001 >nul
echo ========================================
echo   GitHub文件管理器 - 打包脚本
echo ========================================
echo.

echo [1/4] 检查Python环境...
python --version
if errorlevel 1 (
    echo 错误：未找到Python，请先安装Python
    pause
    exit /b 1
)

echo.
echo [2/4] 安装依赖包...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo [3/4] 开始打包程序...
pyinstaller --clean --noconfirm build.spec

echo.
echo [4/4] 打包完成！
echo.
echo 输出目录：dist\
echo 可执行文件：dist\GitHub文件管理器.exe
echo.
echo ========================================
pause
