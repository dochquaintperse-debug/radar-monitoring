#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "========================================"
echo "   雷达监测桥接器 - Linux/Mac 安装器"
echo "========================================"
echo -e "${NC}"

# 检查 Python
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
if ! command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}⚠️  pip3 不可用，正在尝试安装...${NC}"
    python3 -m ensurepip --upgrade 2>/dev/null || {
        echo -e "${RED}❌ pip3 安装失败，请手动安装${NC}"
        exit 1
    }
fi

echo -e "${GREEN}✅ pip3 可用${NC}"

# 安装依赖
echo -e "${BLUE}📦 安装依赖包...${NC}"
pip3 install pyserial requests

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 依赖安装失败，尝试使用用户模式安装...${NC}"
    pip3 install --user pyserial requests
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 依赖安装失败，请检查网络连接或手动安装${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ 依赖安装完成${NC}"

# 下载桥接器（如果不存在）
if [ ! -f "local_bridge_standalone.py" ]; then
    echo -e "${BLUE}📥 下载桥接器文件...${NC}"
    
    if command -v curl &> /dev/null; then
        curl -o local_bridge_standalone.py https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py
    elif command -v wget &> /dev/null; then
        wget -O local_bridge_standalone.py https://raw.githubusercontent.com/dochquaintperse-debug/radar-monitoring/main/bridge/local_bridge_standalone.py
    else
        echo -e "${RED}❌ 需要 curl 或 wget 来下载文件${NC}"
        exit 1
    fi
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 桥接器下载失败，请检查网络连接${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 桥接器下载完成${NC}"
fi

# 设置执行权限
chmod +x local_bridge_standalone.py

# 创建快捷启动脚本
cat > run_bridge.sh << 'EOF'
#!/bin/bash
echo "🚀 启动雷达桥接器..."
python3 local_bridge_standalone.py
EOF

chmod +x run_bridge.sh

echo -e "${GREEN}"
echo "========================================"
echo "            🎉 安装完成！"
echo "========================================"
echo -e "${NC}"

echo -e "${BLUE}📍 使用方法：${NC}"
echo "  1. 运行: ./run_bridge.sh 启动桥接器"
echo "  2. 或者直接运行: python3 local_bridge_standalone.py"
echo ""
echo -e "${YELLOW}📋 注意事项：${NC}"
echo "  • 请确保雷达设备已连接 USB 口"
echo "  • Linux 用户可能需要添加到 dialout 组:"
echo "    sudo usermod -a -G dialout \$USER"
echo "  • 首次运行需要输入云端网址"
echo "  • 按 Ctrl+C 可停止程序"
echo ""

read -p "按 Enter 键继续..."
