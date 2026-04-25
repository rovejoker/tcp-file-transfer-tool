# -*- coding: utf-8 -*-
"""
测试单IP连接数限制功能
"""

import socket
import time
import sys
import json

def test_connection_limit():
    """测试单IP连接数限制"""
    server_host = '127.0.0.1'
    server_port = 2983
    max_connections = 5  # 与服务器配置一致
    
    connections = []
    success_count = 0
    fail_count = 0
    
    print("=" * 60)
    print("    测试单IP连接数限制功能")
    print("=" * 60)
    print("服务器地址: {0}:{1}".format(server_host, server_port))
    print("最大连接数限制: {0}".format(max_connections))
    print()
    
    # 顺序建立连接（max_connections + 3 个，期望前 max_connections 个成功，后3个失败）
    for index in range(1, max_connections + 4):
        print("正在尝试连接 #{0}...".format(index), end=" ")
        sys.stdout.flush()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((server_host, server_port))
            
            # 等待服务器处理（增加等待时间）
            time.sleep(0.8)
            
            # 使用 select 检测是否有数据可读
            import select
            readable, _, _ = select.select([sock], [], [], 1)
            
            if readable:
                # 有数据可读，尝试接收
                try:
                    data = sock.recv(4096)
                    if data:
                        # 检查是否是拒绝响应
                        try:
                            response = json.loads(data.decode('utf-8'))
                            if response.get('status') == 'error' and '连接数超过限制' in response.get('message', ''):
                                sock.close()
                                fail_count += 1
                                print("被拒绝（超过连接数限制）")
                                continue
                        except:
                            pass
                except Exception:
                    pass
            
            # 尝试发送数据来验证连接是否仍然有效
            try:
                sock.send(b'')
                # 如果能发送，连接正常
                connections.append((index, sock))
                success_count += 1
                print("成功")
            except (ConnectionResetError, BrokenPipeError, OSError):
                sock.close()
                fail_count += 1
                print("被拒绝（连接已关闭）")
                
        except socket.timeout:
            fail_count += 1
            print("超时")
        except ConnectionRefusedError:
            fail_count += 1
            print("被拒绝（服务器未启动）")
        except Exception as e:
            fail_count += 1
            print("失败: {0}".format(str(e)))
        
        # 间隔
        time.sleep(0.3)
    
    print()
    print("=" * 60)
    print("测试结果:")
    print("成功连接: {0} 个".format(success_count))
    print("失败连接: {0} 个".format(fail_count))
    print()
    
    # 验证是否正确限制
    if success_count == max_connections and fail_count == 3:
        print("✓ 测试通过：成功限制了单IP连接数")
        print("  - 前 {0} 个连接成功".format(max_connections))
        print("  - 超出限制的 {0} 个连接被拒绝".format(fail_count))
        result = True
    else:
        print("✗ 测试失败：连接数限制未正常工作")
        print("  - 期望成功: {0}, 实际成功: {1}".format(max_connections, success_count))
        print("  - 期望失败: 3, 实际失败: {0}".format(fail_count))
        print()
        print("注意：请检查服务器日志确认连接是否被拒绝")
        result = False
    
    # 等待观察
    print()
    print("等待3秒观察连接状态...")
    time.sleep(3)
    
    # 关闭所有连接
    print()
    print("正在关闭连接...")
    for index, sock in connections:
        try:
            sock.close()
            print("  关闭连接 #{0}".format(index))
        except Exception:
            pass
    
    print()
    print("测试完成")
    return result

if __name__ == "__main__":
    try:
        test_connection_limit()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(0)