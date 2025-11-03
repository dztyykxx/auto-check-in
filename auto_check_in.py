# -*- coding: utf-8 -*-
"""
使用 Playwright (无头浏览器) 自动登录西安交通大学统一身份认证并获取Token，
并根据获取到的Token自动执行锻炼打卡签到、签退操作。

使用前准备:
1. 安装 Playwright 和 requests:
   pip install playwright requests

2. 安装浏览器驱动 (仅首次运行时需要，会自动下载浏览器内核):
   playwright install
"""
import json
import time
import os
import datetime
import requests  # 导入requests库
import random  # 导入random库
import math  # 导入math库
from playwright.sync_api import sync_playwright

# ==============================================================================
# 1. 配置信息 (请根据实际情况修改)
# ==============================================================================
# 你的学号和密码
USERNAME = ""
PASSWORD = ""


# 登录流程的入口URL
START_URL = "https://org.xjtu.edu.cn/openplatform/oauth/authorize?appId=1740&redirectUri=https://ipahw.xjtu.edu.cn/sso/callback&responseType=code&scope=user_info&state=1234"

# --- 打卡相关配置 ---
# 日志文件路径
LOG_FILE_PATH = "check_in_log.json"
# 签到API
SIGN_IN_URL = "https://ipahw.xjtu.edu.cn/szjy-boot/api/v1/sportActa/signRun"
# 签退API
SIGN_OUT_URL = "https://ipahw.xjtu.edu.cn/szjy-boot/api/v1/sportActa/signOutTrain"

# 打卡地点经纬度 (示例：创新港田径场) - 中心点
LOCATION_LONGITUDE_CENTER = 108.66
LOCATION_LATITUDE_CENTER = 34.254
# 随机半径（米）
RANDOM_RADIUS_METERS = 50

# 签到和签退的最小间隔时间（小时）
MIN_DURATION_HOURS = 1


# ==============================================================================
# 2. 核心函数 - 登录 (Playwright)
# ==============================================================================

def login_and_get_token_with_playwright():
    """
    启动一个浏览器实例，模拟用户登录并从本地存储中获取最终的token。
    """
    with sync_playwright() as p:
        # 启动浏览器，headless=False 会显示浏览器界面，便于调试
        browser = None  # 先声明变量以确保 finally 块中可用
        try:
            # 推荐使用 headless=True (无头模式) 在后台运行
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                locale='zh-CN'  # 设置区域为中国大陆
            )
            page = context.new_page()

            # --- 步骤一：访问登录页面 ---
            print(" [1] 正在启动浏览器并访问登录页面...")
            page.goto(START_URL)

            # Playwright会自动处理重定向，等待页面加载到CAS登录页
            print("     页面已跳转至统一认证网关。")

            # --- 步骤二：定位元素并输入用户名和密码 ---
            print(" [2] 正在等待登录组件加载并输入账号密码...")

            # 定义所有需要的元素定位器
            username_input = page.locator('[placeholder="职工号/学号/手机号"]')
            password_input = page.locator('[placeholder="请输入登录密码"]')
            login_button = page.locator('button.login-btn').first

            # 等待登录按钮可见，以此作为整个组件加载完成的标志
            login_button.wait_for(state="visible", timeout=30000)
            print("     登录组件已加载。")

            # 填充账号和密码 (fill操作会自动等待元素变为可编辑状态)
            username_input.fill(USERNAME)
            password_input.fill(PASSWORD)
            print("     账号密码输入完成。")

            # --- 步骤三：点击登录按钮 ---
            print(" [3] 正在点击登录按钮...")
            login_button.click()

            # --- 步骤四：等待登录成功并跳转到目标平台 ---
            print(" [4] 等待登录成功后的最终跳转...")
            # 等待一个已知的目标URL，或者等待localStorage中的特定项出现
            # 这里我们简单等待几秒钟，让JS有足够时间写入localStorage
            time.sleep(3)  # 等待JS执行完毕

            # --- 步骤五：从 Local Storage 提取 Token ---
            print(" [5] 正在从浏览器本地存储中提取Token...")

            # 使用 page.evaluate() 执行JS来获取整个 localStorage
            all_storage_json = page.evaluate("() => JSON.stringify(localStorage)")

            if not all_storage_json or all_storage_json == '{}':
                print(" [警告] 浏览器本地存储为空！登录可能失败或未完成跳转。")
                return None

            print("     成功获取到本地存储内容。")

            try:
                all_storage_data = json.loads(all_storage_json)
                # 尝试从所有数据中找到我们需要的token
                token = all_storage_data.get('_token')

                if token:
                    print("     成功提取到 _token。")
                    print(token)
                    return token
                else:
                    print(" [错误] 在本地存储中未找到 '_token'。")
                    print("     所有本地存储内容如下：")
                    for key, value in all_storage_data.items():
                        print(f"     - Key: {key}, Value: {value[:50]}...")  # 打印部分值
                    return None

            except json.JSONDecodeError as e:
                print(f" [错误] 解析本地存储内容失败: {e}")
                print(f"   原始JSON字符串为：{all_storage_json}")
                return None

        except Exception as e:
            print(f" [严重错误] Playwright 执行过程中发生异常: {e}")
            return None

        finally:
            if browser and browser.is_connected():
                print("     [调试] 流程结束，关闭浏览器...")
                browser.close()


# ==============================================================================
# 3. 核心函数 - 打卡逻辑 (Requests)
# ==============================================================================

def get_randomized_location():
    """
    在中心点附近 RANDOM_RADIUS_METERS 米半径内生成一个随机坐标。
    使用简化的球面模型进行估算。
    """
    # 1 度的纬度大约等于 111111 米
    LAT_DEG_PER_METER = 1 / 111111
    # 1 度的经度大约等于 111111 * cos(纬度) 米
    LON_DEG_PER_METER = 1 / (111111 * math.cos(math.radians(LOCATION_LATITUDE_CENTER)))

    # 在 0 到 RANDOM_RADIUS_METERS 之间随机一个距离
    random_distance = random.uniform(0, RANDOM_RADIUS_METERS)
    # 0 到 2*pi 之间随机一个角度
    random_angle = random.uniform(0, 2 * math.pi)

    # 计算纬度偏移（米）
    lat_offset_meters = random_distance * math.sin(random_angle)
    # 计算经度偏移（米）
    lon_offset_meters = random_distance * math.cos(random_angle)

    # 转换为经纬度偏移（度）
    lat_offset_deg = lat_offset_meters * LAT_DEG_PER_METER
    lon_offset_deg = lon_offset_meters * LON_DEG_PER_METER

    # 计算最终坐标并格式化为字符串
    final_latitude = str(LOCATION_LATITUDE_CENTER + lat_offset_deg)
    final_longitude = str(LOCATION_LONGITUDE_CENTER + lon_offset_deg)

    # print(f"     [调试] 生成随机位置：(Lon: {final_longitude}, Lat: {final_latitude})")
    return final_longitude, final_latitude


def read_log():
    """读取本地日志文件"""
    if not os.path.exists(LOG_FILE_PATH):
        return {}  # 返回一个空字典
    try:
        with open(LOG_FILE_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # 文件损坏或为空
        return {}  # 返回一个空字典


def write_log(log_data):
    """写入日志文件"""
    try:
        with open(LOG_FILE_PATH, 'w') as f:
            json.dump(log_data, f, indent=4, ensure_ascii=False)  # ensure_ascii=False 保证中文正常显示
    except IOError as e:
        print(f" [错误] 写入日志文件失败: {e}")


def sign_in(token):
    """执行签到操作"""
    headers = {
        "Token": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }

    # 生成随机位置
    rand_lon, rand_lat = get_randomized_location()

    payload = {
        "sportType": 2,  # 2 代表自主锻炼
        "longitude": rand_lon,
        "latitude": rand_lat,
        "courseInfoId": "null"  # 保持和注释一致
    }
    try:
        response = requests.post(SIGN_IN_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()  # 如果 http 状态码不是 2xx，则抛出异常

        result = response.json()
        print(f"     [签到API响应] {result.get('msg')}")

        # 根据注释，code=0 或 success=true 代表成功
        if result.get('success') or result.get('code') == 0:
            return True
        elif not result.get('success') and result.get('msg') == "你今天已经获得了其他分数，请明天继续":  # 修正逻辑
            return True
        else:
            return False

    except requests.exceptions.RequestException as e:
        print(f" [错误] 调用签到API失败: {e}")
        return False


def sign_out(token):
    """执行签退操作"""
    headers = {
        "Token": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }

    # 生成随机位置
    rand_lon, rand_lat = get_randomized_location()

    payload = {
        "longitude": rand_lon,
        "latitude": rand_lat
    }
    try:
        response = requests.post(SIGN_OUT_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()

        result = response.json()
        print(f"     [签退API响应] {result.get('msg')}")

        # 根据注释，code=200 或 success=true 代表成功
        if result.get('success') or result.get('code') == 200:
            return True
        elif not result.get('success') and result.get('msg') == "你今天已有成绩！":  # 修正逻辑
            return True
        else:
            return False

    except requests.exceptions.RequestException as e:
        print(f" [错误] 调用签退API失败: {e}")
        return False


def perform_check_in(token):
    """
    执行打卡主逻辑：判断状态并执行相应操作
    """
    print("\n======= 开始执行自动打卡逻辑 =======")
    # 读取完整的历史日志
    log_data = read_log()
    now = datetime.datetime.now()
    today_str = now.strftime('%Y-%m-%d')

    # 获取今天的打卡记录，如果不存在则返回一个空字典
    today_log = log_data.get(today_str, {})

    last_sign_in_iso = today_log.get("sign_in")
    last_sign_out_iso = today_log.get("sign_out")

    # 1. 检查今天是否已签退
    if last_sign_out_iso:
        last_sign_out_time = datetime.datetime.fromisoformat(last_sign_out_iso)
        print(f" [状态] 今日已于 {last_sign_out_time.strftime('%H:%M:%S')} 完成签退。")
        print("==============================================")
        return

    # 2. 检查今天是否已签到
    if last_sign_in_iso:
        last_sign_in_time = datetime.datetime.fromisoformat(last_sign_in_iso)
        duration = now - last_sign_in_time
        duration_hours = duration.total_seconds() / 3600

        print(f" [状态] 今日已于 {last_sign_in_time.strftime('%H:%M:%S')} 签到。")
        print(f"     已持续 {duration_hours:.2f} 小时。")

        # 3. 检查是否满足签退时间
        if duration_hours >= MIN_DURATION_HOURS:
            print(" [操作] 已满足最小锻炼时长，正在尝试签退...")
            if sign_out(token):
                print("     签退成功！")
                # 更新今天的记录
                today_log["sign_out"] = now.isoformat()
                log_data[today_str] = today_log
                write_log(log_data)
            else:
                print("     签退失败。请检查API响应或日志。")
        else:
            print(f" [操作] 锻炼时长未满 {MIN_DURATION_HOURS} 小时，暂不签退。")

        print("==============================================")
        return

    # 4. 如果今天未签到
    print(f" [状态] 今日尚未签到。")
    print(" [操作] 正在尝试签到...")
    if sign_in(token):
        print("     签到成功！")
        # 创建今天的签到记录
        log_data[today_str] = {
            "sign_in": now.isoformat(),
            "sign_out": None
        }
        write_log(log_data)
    else:
        print("     签到失败。请检查API响应或日志。")

    print("==============================================")


# ==============================================================================
# 4. 执行主程序
# ==============================================================================
if __name__ == '__main__':
    print("======= 开始使用 Playwright 模拟登录流程 =======")

    if not USERNAME or not PASSWORD or USERNAME == "你的学号":
        print("\n[注意] 请先在脚本顶部配置信息中填写你的 USERNAME 和 PASSWORD！\n")
    else:
        token = login_and_get_token_with_playwright()
        print("==============================================")

        if token:
            print(f"\n[成功] 已成功获取Token (为保护隐私，仅显示部分):")
            print(f"{token[:15]}...{token[-15:]}")

            # --- 执行打卡逻辑 ---
            perform_check_in(token)

        else:
            print("\n[失败] 登录流程未能成功获取Token。")
