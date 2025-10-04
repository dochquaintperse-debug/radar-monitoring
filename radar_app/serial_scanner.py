import serial
import serial.tools.list_ports
import time
from .radar_protocol import (
    SERIAL_PARAMS,
    build_locking_cmd,
    EXPECTED_LOCK_RESPONSE
)

class SerialScanner:
    @staticmethod
    def get_available_ports():
        """获取可用串口"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports if "USB" in port.description or "COM" in port.device]
    
    @staticmethod
    def test_port(port):
        """测试端口是否为R60ABD1传感器（操作1）"""
        ser = None
        try:
            ser = serial.Serial(
                port=port,
                baudrate=SERIAL_PARAMS["baud_rate"],
                bytesize=SERIAL_PARAMS["bytesize"],
                stopbits=SERIAL_PARAMS["stopbits"],
                parity=SERIAL_PARAMS["parity"],
                timeout=SERIAL_PARAMS["timeout"]
            )
            
            # 发送锁定指令检测传感器（操作1）
            lock_cmd = build_locking_cmd()
            for _ in range(3):
                ser.write(lock_cmd)
                time.sleep(1.0)
                if ser.in_waiting > 0:
                    raw_response = ser.read(ser.in_waiting)
                    print(f"[扫描阶段] 端口 {port} 响应: {raw_response.hex()}")
                    # 关键：检查预期响应是否是原始响应的子串
                    if EXPECTED_LOCK_RESPONSE in raw_response:  # 必须是这行，而非 ==
                        return {
                           "port": port,
                           "sensor_id": f"R60ABD1_BREATH_{port}",
                           "success": True
                        }
            return {"port": port, "success": False}
        except serial.SerialException as e:
            print(f"串口 {port} 测试失败: {e}")
            return {"port": port, "success": False}
        finally:
            if ser and ser.is_open:
                ser.close()
    
    @staticmethod
    def find_sensors():
        """寻找R60ABD1传感器（操作1：找到第一个后停止）"""
        ports = SerialScanner.get_available_ports()
        sensors = []
        for port in ports:
            result = SerialScanner.test_port(port)
            if result["success"]:
                sensors.append(result)
                break  # 找到第一个匹配的传感器后停止枚举（操作1）
        return sensors