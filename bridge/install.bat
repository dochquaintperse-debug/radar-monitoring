@echo off
chcp 65001 >nul
echo.
echo ========================================
echo    雷达监测桥接器 - Windows 安装器 v2.0
echo ========================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ✅ 管理员权限已获取
) else (
    echo ⚠️  建议以管理员身份运行以避免权限问题
)

:: 检查 Python
echo 🔍 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3.7+
    echo 📥 下载地址: https://www.python.org/downloads/
    echo.
    echo 💡 安装提示:
    echo   • 选择 "Add Python to PATH"
    echo   • 选择 "Install for all users"
    pause
    exit /b 1
)

echo ✅ 检测到 Python
python --version

:: 检查 pip
echo 🔍 检查 pip...
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip 不可用，正在尝试修复...
    python -m ensurepip --upgrade
    if errorlevel 1 (
        echo ❌ pip 修复失败，请重新安装 Python
        pause
        exit /b 1
    )
)

echo ✅ pip 可用
pip --version

:: 升级pip
echo 🔄 升级 pip...
python -m pip install --upgrade pip

:: 安装依赖
echo.
echo 📦 安装依赖包...
pip install pyserial requests

if errorlevel 1 (
    echo ❌ 依赖安装失败，尝试使用用户模式...
    pip install --user pyserial requests
    
    if errorlevel 1 (
        echo ❌ 依赖安装失败，请检查网络连接或尝试以下方法:
        echo   1. 使用国内镜像: pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pyserial requests
        echo   2. 检查防火墙设置
        echo   3. 尝试重新安装 Python
        pause
        exit /b 1
    )
)

echo ✅ 依赖安装完成

:: 创建工作目录
if not exist "radar_bridge" (
    mkdir radar_bridge
)
cd radar_bridge

:: 下载桥接器（如果不存在）
if not exist "local_bridge_standalone.py" (
    echo.
    echo 📥 下载桥接器文件...
    
    :: 使用curl下载（Windows 10+自带）
    curl --version >nul 2>&1
    if not errorlevel 1 (
        curl -L -o local_bridge_standalone.py "https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py"
    ) else (
        :: 使用PowerShell下载
        powershell -Command "try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py' -OutFile 'local_bridge_standalone.py' -UseBasicParsing } catch { Write-Host 'PowerShell下载失败' -ForegroundColor Red; exit 1 }"
    )
    
    if not exist "local_bridge_standalone.py" (
        echo ❌ 桥接器下载失败，请检查网络连接
        echo 💡 您也可以手动下载:
        echo    https://github.com/dochquaintperse-debug/radar-monitoring/blob/main/bridge/local_bridge_standalone.py
        pause
        exit /b 1
    )
    echo ✅ 桥接器下载完成
)

:: 创建增强的启动脚本
echo 📝 创建启动脚本...

echo @echo off > run_bridge.bat
echo chcp 65001 ^>nul >> run_bridge.bat
echo title 雷达数据桥接器 >> run_bridge.bat
echo echo. >> run_bridge.bat
echo echo ================================================ >> run_bridge.bat
echo echo           🎯 雷达数据桥接器 v2.0 >> run_bridge.bat
echo echo ================================================ >> run_bridge.bat
echo echo. >> run_bridge.bat
echo echo 💡 使用提示: >> run_bridge.bat
echo echo   • 确保雷达设备已连接USB口 >> run_bridge.bat
echo echo   • 输入云端网址时可省略 http:// 前缀 >> run_bridge.bat
echo echo   • 按 Ctrl+C 可安全停止程序 >> run_bridge.bat
echo echo. >> run_bridge.bat
echo python local_bridge_standalone.py >> run_bridge.bat
echo echo. >> run_bridge.bat
echo echo 👋 程序已退出 >> run_bridge.bat
echo pause >> run_bridge.bat

:: 创建一键更新脚本
echo 📝 创建更新脚本...
echo @echo off > update_bridge.bat
echo chcp 65001 ^>nul >> update_bridge.bat
echo echo 🔄 更新桥接器... >> update_bridge.bat
echo if exist "local_bridge_standalone.py.bak" del "local_bridge_standalone.py.bak" >> update_bridge.bat
echo if exist "local_bridge_standalone.py" ren "local_bridge_standalone.py" "local_bridge_standalone.py.bak" >> update_bridge.bat
echo curl -L -o local_bridge_standalone.py "https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py" >> update_bridge.bat
echo if exist "local_bridge_standalone.py" ( >> update_bridge.bat
echo     echo ✅ 更新成功 >> update_bridge.bat
echo     del "local_bridge_standalone.py.bak" >> update_bridge.bat
echo ^) else ( >> update_bridge.bat
echo     echo ❌ 更新失败，恢复备份 >> update_bridge.bat
echo     ren "local_bridge_standalone.py.bak" "local_bridge_standalone.py" >> update_bridge.bat
echo ^) >> update_bridge.bat
echo pause >> update_bridge.bat

:: 创建卸载脚本
echo @echo off > uninstall.bat
echo chcp 65001 ^>nul >> uninstall.bat
echo echo ⚠️  确定要卸载桥接器吗？ >> uninstall.bat
echo set /p confirm=输入 Y 确认卸载: >> uninstall.bat
echo if /i "%%confirm%%" NEQ "Y" exit /b 0 >> uninstall.bat
echo echo 🗑️  卸载中... >> uninstall.bat
echo pip uninstall pyserial requests -y >> uninstall.bat
echo cd .. >> uninstall.bat
echo rmdir /s /q radar_bridge >> uninstall.bat
echo echo ✅ 卸载完成 >> uninstall.bat
echo pause >> uninstall.bat

echo.
echo ========================================
echo            🎉 安装完成！
echo ========================================
echo.
echo 📁 安装目录: %cd%
echo.
echo 🚀 使用方法：
echo   1. 双击运行 'run_bridge.bat' 启动桥接器
echo   2. 双击运行 'update_bridge.bat' 更新程序  
echo   3. 双击运行 'uninstall.bat' 卸载程序
echo.
echo 🔗 云端地址示例：
echo   • your-app.onrender.com
echo   • localhost:8000 (本地测试)
echo.
echo 📋 注意事项：
echo   • 请确保雷达设备已连接 USB 口
echo   • Windows可能需要安装USB串口驱动
echo   • 首次运行需要输入云端网址
echo   • 按 Ctrl+C 可停止程序
echo.

pause
