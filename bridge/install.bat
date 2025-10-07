@echo off
chcp 65001 >nul
echo.
echo ========================================
echo    雷达监测桥接器 - Windows 安装器
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3.7+
    echo 📥 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ 检测到 Python
python --version

:: 检查 pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip 不可用，正在尝试修复...
    python -m ensurepip --upgrade
)

echo ✅ pip 可用

:: 创建虚拟环境（可选）
echo.
echo 📦 安装依赖包...
pip install pyserial requests

if errorlevel 1 (
    echo ❌ 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)

echo ✅ 依赖安装完成

:: 下载桥接器（如果不存在）
if not exist "local_bridge_standalone.py" (
    echo.
    echo 📥 下载桥接器文件...
    powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py' -OutFile 'local_bridge_standalone.py'"
    
    if errorlevel 1 (
        echo ❌ 桥接器下载失败，请检查网络连接
        pause
        exit /b 1
    )
    echo ✅ 桥接器下载完成
)

:: 创建快捷启动脚本
echo @echo off > run_bridge.bat
echo chcp 65001 ^>nul >> run_bridge.bat
echo echo 🚀 启动雷达桥接器... >> run_bridge.bat
echo python local_bridge_standalone.py >> run_bridge.bat
echo pause >> run_bridge.bat

echo.
echo ========================================
echo            🎉 安装完成！
echo ========================================
echo.
echo 📍 使用方法：
echo   1. 双击运行 'run_bridge.bat' 启动桥接器
echo   2. 或者在命令行运行: python local_bridge_standalone.py
echo.
echo 📋 注意事项：
echo   • 请确保雷达设备已连接 USB 口
echo   • 首次运行需要输入云端网址
echo   • 按 Ctrl+C 可停止程序
echo.

pause
