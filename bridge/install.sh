#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "========================================"
echo "   雷达监测桥接器 - Linux/Mac 安装器 v2.0"
echo "========================================"
echo -e "${NC}"

# 检查系统类型
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    SYSTEM="Linux"
    INSTALL_CMD="sudo apt update && sudo apt install"
    if command -v yum &> /dev/null; then
        INSTALL_CMD="sudo yum install"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    SYSTEM="macOS"
    INSTALL_CMD="brew install"
else
    SYSTEM="Unknown"
fi

echo -e "${GREEN}🖥️  检测到系统: $SYSTEM${NC}"

# 检查 Python
echo -e "${BLUE}🔍 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未检测到 Python3，请先安装${NC}"
    echo "Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip"
    echo "CentOS/RHEL: sudo yum install python3 python3-pip"  
    echo "macOS: brew install python3"
    exit 1
fi

echo -e "${GREEN}✅ 检测到 Python3${NC}"
python3 --version

# 检查 pip
echo -e "${BLUE}🔍 检查 pip...${NC}"
if ! command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}⚠️  pip3 不可用，正在尝试安装...${NC}"
    python3 -m ensurepip --upgrade 2>/dev/null || {
        echo -e "${RED}❌ pip3 安装失败，请手动安装${NC}"
        exit 1
    }
fi

echo -e "${GREEN}✅ pip3 可用${NC}"
pip3 --version

# 升级pip
echo -e "${BLUE}🔄 升级 pip...${NC}"
python3 -m pip install --upgrade pip --user

# 检查串口权限
echo -e "${BLUE}🔍 检查串口权限...${NC}"
if [[ "$SYSTEM" == "Linux" ]]; then
    if ! groups | grep -q "dialout"; then
        echo -e "${YELLOW}⚠️  用户不在dialout组中${NC}"
        echo -e "${YELLOW}执行以下命令添加权限（需要重新登录生效）:${NC}"
        echo "sudo usermod -a -G dialout $USER"
        
        read -p "是否现在添加权限? (y/n): " add_permission
        if [[ $add_permission =~ ^[Yy]$ ]]; then
            sudo usermod -a -G dialout $USER
            echo -e "${GREEN}✅ 权限已添加，请注销后重新登录${NC}"
        fi
    else
        echo -e "${GREEN}✅ 串口权限正常${NC}"
    fi
fi

# 安装依赖
echo -e "${BLUE}📦 安装依赖包...${NC}"
pip3 install pyserial requests --user

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 依赖安装失败，尝试其他方法...${NC}"
    
    # 尝试系统包管理器
    if [[ "$SYSTEM" == "Linux" ]]; then
        echo -e "${YELLOW}尝试使用系统包管理器...${NC}"
        sudo apt install python3-serial python3-requests 2>/dev/null || \
        sudo yum install python3-pyserial python3-requests 2>/dev/null || {
            echo -e "${RED}❌ 依赖安装失败，请检查网络连接${NC}"
            exit 1
        }
    else
        echo -e "${RED}❌ 依赖安装失败，请检查网络连接${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ 依赖安装完成${NC}"

# 创建工作目录
INSTALL_DIR="$HOME/radar_bridge"
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

echo -e "${GREEN}📁 安装目录: $INSTALL_DIR${NC}"

# 下载桥接器（如果不存在）
if [ ! -f "local_bridge_standalone.py" ]; then
    echo -e "${BLUE}📥 下载桥接器文件...${NC}"
    
    if command -v curl &> /dev/null; then
        curl -L -o local_bridge_standalone.py "https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py"
    elif command -v wget &> /dev/null; then
        wget -O local_bridge_standalone.py "https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py"
    else
        echo -e "${RED}❌ 需要 curl 或 wget 来下载文件${NC}"
        echo "请手动下载: https://github.com/dochquaintperse-debug/radar-monitoring/blob/main/bridge/local_bridge_standalone.py"
        exit 1
    fi
    
    if [ $? -ne 0 ] || [ ! -f "local_bridge_standalone.py" ]; then
        echo -e "${RED}❌ 桥接器下载失败，请检查网络连接${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 桥接器下载完成${NC}"
fi

# 设置执行权限
chmod +x local_bridge_standalone.py

# 创建启动脚本
echo -e "${BLUE}📝 创建启动脚本...${NC}"
cat > run_bridge.sh << 'EOF'
#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
echo "================================================"
echo "           🎯 雷达数据桥接器 v2.0"
echo "================================================"
echo -e "${NC}"
echo
echo -e "${YELLOW}💡 使用提示:${NC}"
echo "  • 确保雷达设备已连接USB口"
echo "  • 输入云端网址时可省略 http:// 前缀"
echo "  • 按 Ctrl+C 可安全停止程序"
echo

python3 local_bridge_standalone.py

echo
echo -e "${GREEN}👋 程序已退出${NC}"
read -p "按 Enter 键继续..."
EOF

chmod +x run_bridge.sh

# 创建更新脚本
cat > update_bridge.sh << 'EOF'
#!/bin/bash
echo "🔄 更新桥接器..."

# 备份当前版本
if [ -f "local_bridge_standalone.py" ]; then
    cp local_bridge_standalone.py local_bridge_standalone.py.bak
fi

# 下载新版本
if command -v curl &> /dev/null; then
    curl -L -o local_bridge_standalone.py "https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py"
elif command -v wget &> /dev/null; then
    wget -O local_bridge_standalone.py "https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py"
fi

if [ -f "local_bridge_standalone.py" ] && [ -s "local_bridge_standalone.py" ]; then
    echo "✅ 更新成功"
    rm -f local_bridge_standalone.py.bak
    chmod +x local_bridge_standalone.py
else
    echo "❌ 更新失败，恢复备份"
    if [ -f "local_bridge_standalone.py.bak" ]; then
        mv local_bridge_standalone.py.bak local_bridge_standalone.py
    fi
fi

read -p "按 Enter 键继续..."
EOF

chmod +x update_bridge.sh

# 创建卸载脚本
cat > uninstall.sh << 'EOF'
#!/bin/bash
echo "⚠️  确定要卸载桥接器吗？"
read -p "输入 Y 确认卸载: " confirm

if [[ $confirm =~ ^[Yy]$ ]]; then
    echo "🗑️  卸载中..."
    pip3 uninstall pyserial requests -y
    cd ..
    rm -rf radar_bridge
    echo "✅ 卸载完成"
else
    echo "❌ 取消卸载"
fi

read -p "按 Enter 键继续..."
EOF

chmod +x uninstall.sh

# 创建桌面快捷方式（Linux）
if [[ "$SYSTEM" == "Linux" ]] && command -v xdg-user-dir &> /dev/null; then
    DESKTOP_DIR=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
    if [ -d "$DESKTOP_DIR" ]; then
        cat > "$DESKTOP_DIR/雷达桥接器.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=雷达桥接器
Comment=启动雷达数据桥接器
Exec=$INSTALL_DIR/run_bridge.sh
Icon=applications-internet
Terminal=true
Categories=Utility;
EOF
        chmod +x "$DESKTOP_DIR/雷达桥接器.desktop"
        echo -e "${GREEN}✅ 桌面快捷方式已创建${NC}"
    fi
fi

echo -e "${GREEN}"
echo "========================================"
echo "            🎉 安装完成！"
echo "========================================"
echo -e "${NC}"

echo -e "${BLUE}📁 安装目录: $INSTALL_DIR${NC}"
echo
echo -e "${BLUE}🚀 使用方法：${NC}"
echo "  1. 运行: ./run_bridge.sh 启动桥接器"
echo "  2. 运行: ./update_bridge.sh 更新程序"  
echo "  3. 运行: ./uninstall.sh 卸载程序"
echo
echo -e "${BLUE}🔗 云端地址示例：${NC}"
echo "  • your-app.onrender.com"
echo "  • localhost:8000 (本地测试)"
echo
echo -e "${YELLOW}📋 注意事项：${NC}"
echo "  • 请确保雷达设备已连接 USB 口"
echo "  • Linux 用户可能需要添加到 dialout 组"
echo "  • 首次运行需要输入云端网址"  
echo "  • 按 Ctrl+C 可停止程序"
echo

read -p "按 Enter 键继续..."
