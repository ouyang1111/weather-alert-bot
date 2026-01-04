#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机场天气最高温预测提醒程序
用于信息提醒，不做任何交易决策
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

# ==================== 配置区域 ====================
# 请在这里填入你的 Telegram Bot Token 和 Chat ID

# 你的 Telegram Bot Token（从 BotFather 获取）
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '请在这里填入你的Token')

# 你的 Chat ID（从 @userinfobot 获取）
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '6826881653')

# 检查间隔（分钟）- 可以设置为 30 或 60
CHECK_INTERVAL_MINUTES = 60

# ==================== 机场坐标（固定，不要修改）====================
AIRPORTS = {
    '纽约 LGA': {'lat': 40.7769, 'lon': -73.8740, 'code': 'LGA', 'name_cn': '纽约'},
    '多伦多 YYZ': {'lat': 43.6777, 'lon': -79.6248, 'code': 'YYZ', 'name_cn': '多伦多'},
    '伦敦 LCY': {'lat': 51.5053, 'lon': 0.0553, 'code': 'LCY', 'name_cn': '伦敦'},
    '首尔 ICN': {'lat': 37.4602, 'lon': 126.4407, 'code': 'ICN', 'name_cn': '首尔'},
}

# ==================== API 配置 ====================
API_BASE_URL = 'https://api.open-meteo.com/v1/forecast'

# ==================== 状态文件路径（用于保存上次检查的数据）====================
STATE_FILE = 'weather_state.json'


def celsius_to_fahrenheit(celsius: float) -> float:
    """将摄氏度转换为华氏度"""
    return (celsius * 9/5) + 32


def get_weather_forecast(latitude: float, longitude: float) -> Optional[Dict]:
    """
    从 Open-Meteo API 获取天气预测数据
    
    Args:
        latitude: 纬度
        longitude: 经度
    
    Returns:
        包含天气数据的字典，如果失败返回 None
    """
    try:
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'hourly': 'temperature_2m',
            'timezone': 'auto',
        }
        
        response = requests.get(API_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        return data
    except Exception as e:
        print(f"获取天气数据失败: {e}")
        return None


def get_today_max_temp(weather_data: Dict) -> Optional[float]:
    """
    从天气数据中提取当天（0:00-23:59）的最高温度
    
    Args:
        weather_data: API 返回的天气数据
    
    Returns:
        当天最高温度（摄氏度），如果失败返回 None
    """
    try:
        hourly_data = weather_data.get('hourly', {})
        times = hourly_data.get('time', [])
        temperatures = hourly_data.get('temperature_2m', [])
        
        if not times or not temperatures:
            return None
        
        # 获取当前日期（UTC）
        now = datetime.utcnow()
        today_str = now.strftime('%Y-%m-%d')
        
        # 筛选出当天的温度数据
        today_temps = []
        for i, time_str in enumerate(times):
            if time_str.startswith(today_str):
                temp = temperatures[i]
                if temp is not None:
                    today_temps.append(temp)
        
        if not today_temps:
            return None
        
        # 返回最高温度
        return max(today_temps)
    except Exception as e:
        print(f"解析温度数据失败: {e}")
        return None


def send_telegram_message(message: str) -> bool:
    """
    通过 Telegram Bot 发送消息
    
    Args:
        message: 要发送的消息内容
    
    Returns:
        发送成功返回 True，失败返回 False
    """
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        
        return True
    except Exception as e:
        print(f"发送 Telegram 消息失败: {e}")
        return False


def get_beijing_time() -> str:
    """获取北京时间（UTC+8）"""
    beijing_tz = timezone(timedelta(hours=8))
    beijing_time = datetime.now(beijing_tz)
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')


def format_temperature_message(airport: str, max_temp: float) -> str:
    """
    格式化温度提醒消息
    
    Args:
        airport: 机场名称
        max_temp: 最高温度（摄氏度）
    
    Returns:
        格式化后的消息
    """
    # 获取机场代码和中文名称
    airport_info = AIRPORTS.get(airport, {})
    airport_code = airport_info.get('code', '')
    airport_name_cn = airport_info.get('name_cn', '')
    
    # 格式化机场显示：代码 中文名称 代码（例如：LCY 伦敦 LCY）
    if airport_code and airport_name_cn:
        airport_display = f"{airport_code} {airport_name_cn} {airport_code}"
    else:
        airport_display = airport
    
    max_temp_f = celsius_to_fahrenheit(max_temp)
    
    # 计算三个参考值
    ref_minus = max_temp - 1
    ref_center = max_temp
    ref_plus = max_temp + 1
    
    ref_minus_f = celsius_to_fahrenheit(ref_minus)
    ref_center_f = celsius_to_fahrenheit(ref_center)
    ref_plus_f = celsius_to_fahrenheit(ref_plus)
    
    # 获取北京时间
    beijing_time = get_beijing_time()
    
    message = f"""
🌡️ <b>机场天气最高温预测提醒</b>

📍 <b>机场:</b> {airport_display}
🕐 <b>更新时间（北京时间）:</b> {beijing_time}

📊 <b>当天预测最高温度:</b>
   {max_temp:.1f}°C / {max_temp_f:.1f}°F

📈 <b>三个参考值:</b>
   • {ref_minus:.1f}°C / {ref_minus_f:.1f}°F (最高温 -1°C)
   • {ref_center:.1f}°C / {ref_center_f:.1f}°F (最高温)
   • {ref_plus:.1f}°C / {ref_plus_f:.1f}°F (最高温 +1°C)

⚠️ <i>本程序仅用于信息提醒，不做任何交易决策</i>
"""
    return message.strip()


def load_state() -> Dict:
    """从文件加载上次检查的状态"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"加载状态文件失败: {e}")
    
    # 返回默认状态
    return {
        'last_max_temps': {airport: None for airport in AIRPORTS.keys()},
        'last_check_date': None
    }


def save_state(state: Dict):
    """保存当前状态到文件"""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存状态文件失败: {e}")


def check_and_send_alerts():
    """检查所有机场的天气并发送提醒"""
    # 加载上次的状态
    state = load_state()
    last_max_temps = state.get('last_max_temps', {airport: None for airport in AIRPORTS.keys()})
    last_check_date = state.get('last_check_date')
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    is_new_day = (last_check_date != current_date)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始检查天气...")
    
    # 更新当前最高温度
    current_max_temps = {}
    
    for airport, coords in AIRPORTS.items():
        print(f"正在检查 {airport}...")
        
        # 获取天气数据
        weather_data = get_weather_forecast(coords['lat'], coords['lon'])
        if weather_data is None:
            print(f"  ❌ 获取 {airport} 天气数据失败")
            continue
        
        # 获取当天最高温度
        max_temp = get_today_max_temp(weather_data)
        if max_temp is None:
            print(f"  ❌ 解析 {airport} 温度数据失败")
            continue
        
        current_max_temps[airport] = max_temp
        print(f"  ✅ {airport} 当天最高温度: {max_temp:.1f}°C")
        
        # 判断是否需要发送通知
        should_send = False
        
        # 条件1：每天第一次计算完成
        if is_new_day:
            should_send = True
            print(f"  📅 新的一天，发送首次提醒")
        
        # 条件2：预测最高温发生变化
        elif last_max_temps.get(airport) is not None:
            if abs(max_temp - last_max_temps[airport]) > 0.1:  # 温度变化超过0.1度
                should_send = True
                print(f"  🔄 温度变化: {last_max_temps[airport]:.1f}°C → {max_temp:.1f}°C")
        
        # 如果是第一次运行（所有值都是 None）
        if last_max_temps.get(airport) is None:
            should_send = True
            print(f"  🆕 首次运行，发送提醒")
        
        # 发送通知
        if should_send:
            message = format_temperature_message(airport, max_temp)
            if send_telegram_message(message):
                print(f"  ✅ 已发送 {airport} 提醒消息")
            else:
                print(f"  ❌ 发送 {airport} 提醒消息失败")
    
    # 保存当前状态
    new_state = {
        'last_max_temps': current_max_temps,
        'last_check_date': current_date
    }
    save_state(new_state)
    
    print(f"检查完成！\n")


def main():
    """主程序"""
    print("=" * 60)
    print("机场天气最高温预测提醒程序")
    print("=" * 60)
    
    # 检查配置
    if TELEGRAM_BOT_TOKEN == '请在这里填入你的Token' or not TELEGRAM_BOT_TOKEN:
        print("❌ 错误: 请先配置 TELEGRAM_BOT_TOKEN")
        print("   请在 GitHub Actions Secrets 中设置 TELEGRAM_BOT_TOKEN")
        return
    
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == '请在这里填入你的Chat ID':
        print("❌ 错误: 请先配置 TELEGRAM_CHAT_ID")
        print("   请在 GitHub Actions Secrets 中设置 TELEGRAM_CHAT_ID")
        return
    
    # 执行检查
    check_and_send_alerts()


if __name__ == '__main__':
    main()


