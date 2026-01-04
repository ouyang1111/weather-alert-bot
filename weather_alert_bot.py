#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机场天气最高温预测提醒程序
用于信息提醒，不做任何交易决策
"""

import os
import json
import time
import math
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

# ==================== 配置区域 ====================
# 请在这里填入你的 Telegram Bot Token 和 Chat ID

# 你的 Telegram Bot Token（从 BotFather 获取）
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '请在这里填入你的Token')

# 你的 Chat ID（从 @userinfobot 获取）
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '6826881653')

# 企业微信机器人 Webhook URL（可选，如果不需要可以留空）
# 获取方式：在企业微信群中添加机器人，获取 Webhook URL
WECHAT_WEBHOOK_URL = os.getenv('WECHAT_WEBHOOK_URL', '')

# 检查间隔（分钟）- 可以设置为 30 或 60
CHECK_INTERVAL_MINUTES = 60

# ==================== 机场坐标（固定，不要修改）====================
AIRPORTS = {
    '纽约 LGA': {
        'lat': 40.7769, 
        'lon': -73.8740, 
        'code': 'LGA', 
        'name_cn': '纽约', 
        'wunderground_code': 'KLGA',
        'wunderground_url': 'https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA',
        'windy_url': 'https://www.windy.com/40.775/-73.873?36.855,-73.873,5,p:cities'
    },
    '多伦多 YYZ': {
        'lat': 43.6777, 
        'lon': -79.6248, 
        'code': 'YYZ', 
        'name_cn': '多伦多', 
        'wunderground_code': 'CYYZ',
        'wunderground_url': 'https://www.wunderground.com/history/daily/ca/mississauga/CYYZ',
        'windy_url': 'https://www.windy.com/43.678/-79.629?43.231,-79.319,9,p:cities'
    },
    '伦敦 LCY': {
        'lat': 51.5053, 
        'lon': 0.0553, 
        'code': 'LCY', 
        'name_cn': '伦敦', 
        'wunderground_code': 'EGLC',
        'wunderground_url': 'https://www.wunderground.com/history/daily/gb/london/EGLC',
        'windy_url': 'https://www.windy.com/51.505/0.053?51.503,0.065,15,p:cities'
    },
    '首尔 ICN': {
        'lat': 37.4602, 
        'lon': 126.4407, 
        'code': 'ICN', 
        'name_cn': '首尔', 
        'wunderground_code': 'RKSI',
        'wunderground_url': 'https://www.wunderground.com/history/daily/kr/incheon/RKSI',
        'windy_url': 'https://www.windy.com/37.464/126.440?37.214,126.440,9,p:cities'
    },
}

# ==================== API 配置 ====================
API_BASE_URL = 'https://api.open-meteo.com/v1/forecast'
HISTORICAL_API_URL = 'https://archive-api.open-meteo.com/v1/archive'

# ==================== 状态文件路径（用于保存上次检查的数据）====================
STATE_FILE = 'weather_state.json'


def celsius_to_fahrenheit(celsius: float) -> float:
    """将摄氏度转换为华氏度"""
    return (celsius * 9/5) + 32


def meters_per_second_to_miles_per_hour(mps: float) -> float:
    """将米/秒转换为英里/小时"""
    return mps * 2.237


def wind_direction_to_arrow(angle: float) -> str:
    """
    根据风向角度获取箭头符号
    箭头表示风从哪个方向来（比如西北风，风从西北来，箭头指向东南）
    
    Args:
        angle: 风向角度（0-360度，0度表示北风）
    
    Returns:
        箭头符号
    """
    # 将角度标准化到0-360范围
    angle = angle % 360
    
    # 定义8个主要方向的箭头（风从该方向来）
    # 北风(0°) → ↓, 东北风(45°) → ↘, 东风(90°) → →, 东南风(135°) → ↗
    # 南风(180°) → ↑, 西南风(225°) → ↖, 西风(270°) → ←, 西北风(315°) → ↙
    if 0 <= angle < 22.5 or angle >= 337.5:
        return '↓'  # 北风
    elif 22.5 <= angle < 67.5:
        return '↘'  # 东北风
    elif 67.5 <= angle < 112.5:
        return '→'  # 东风
    elif 112.5 <= angle < 157.5:
        return '↗'  # 东南风
    elif 157.5 <= angle < 202.5:
        return '↑'  # 南风
    elif 202.5 <= angle < 247.5:
        return '↖'  # 西南风
    elif 247.5 <= angle < 292.5:
        return '←'  # 西风
    else:  # 292.5 <= angle < 337.5
        return '↙'  # 西北风


def wind_direction_to_name(angle: float) -> str:
    """
    将风向角度转换为方向名称（带箭头）
    
    Args:
        angle: 风向角度（0-360度，0度表示北风）
    
    Returns:
        方向名称（如：北风↓、东北风↘、东风→等）
    """
    # 将角度标准化到0-360范围
    angle = angle % 360
    
    # 定义16个方向
    directions = [
        (0, 11.25, '北风'),
        (11.25, 33.75, '北东北风'),
        (33.75, 56.25, '东北风'),
        (56.25, 78.75, '东东北风'),
        (78.75, 101.25, '东风'),
        (101.25, 123.75, '东东南风'),
        (123.75, 146.25, '东南风'),
        (146.25, 168.75, '南东南风'),
        (168.75, 191.25, '南风'),
        (191.25, 213.75, '南西南风'),
        (213.75, 236.25, '西南风'),
        (236.25, 258.75, '西西南风'),
        (258.75, 281.25, '西风'),
        (281.25, 303.75, '西西北风'),
        (303.75, 326.25, '西北风'),
        (326.25, 348.75, '北西北风'),
        (348.75, 360, '北风'),
    ]
    
    for start, end, name in directions:
        if start <= angle < end or (start == 348.75 and angle >= 348.75):
            # 添加箭头符号
            arrow = wind_direction_to_arrow(angle)
            return f"{name}{arrow}"
    
    return '北风↓'


def get_weathercode_description(code: int) -> str:
    """
    根据 WMO 天气代码返回天气状况描述
    
    Args:
        code: WMO 天气代码
    
    Returns:
        天气状况描述（如：晴天、多云、小雨等）
    """
    weather_codes = {
        0: '晴天',
        1: '大部分晴天',
        2: '部分多云',
        3: '阴天',
        45: '雾',
        48: '沉积霜雾',
        51: '小雨',
        53: '中雨',
        55: '大雨',
        56: '冻雨（小雨）',
        57: '冻雨（大雨）',
        61: '小雨',
        63: '中雨',
        65: '大雨',
        66: '冻雨',
        67: '冻雨',
        71: '小雪',
        73: '中雪',
        75: '大雪',
        77: '雪粒',
        80: '小阵雨',
        81: '中阵雨',
        82: '大阵雨',
        85: '小阵雪',
        86: '大阵雪',
        95: '雷暴',
        96: '雷暴伴冰雹',
        99: '雷暴伴大冰雹',
    }
    return weather_codes.get(code, '未知')


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
            'hourly': 'temperature_2m,winddirection_10m,windspeed_10m,windgusts_10m,precipitation,weathercode,cloudcover',
            'timezone': 'auto',
        }
        
        # 增加超时时间并添加重试
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(API_BASE_URL, params=params, timeout=20)
                response.raise_for_status()
                break
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"   ⚠️ 请求超时，重试中... ({attempt + 1}/{max_retries})")
                    continue
                else:
                    raise
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"   ⚠️ 请求失败，重试中... ({attempt + 1}/{max_retries})")
                    continue
                else:
                    raise
        
        data = response.json()
        return data
    except Exception as e:
        print(f"获取天气数据失败: {e}")
        return None


def get_historical_weather(latitude: float, longitude: float, start_date: str, end_date: str) -> Optional[Dict]:
    """
    从 Open-Meteo 历史API获取历史天气数据
    
    Args:
        latitude: 纬度
        longitude: 经度
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
    
    Returns:
        包含历史天气数据的字典，如果失败返回 None
    """
    try:
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'start_date': start_date,
            'end_date': end_date,
            'hourly': 'temperature_2m',
            'timezone': 'auto',
        }
        
        # 增加超时时间并添加重试
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.get(HISTORICAL_API_URL, params=params, timeout=20)
                response.raise_for_status()
                break
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    continue
                else:
                    raise
            except Exception as e:
                if attempt < max_retries - 1:
                    continue
                else:
                    raise
        
        data = response.json()
        return data
    except Exception as e:
        print(f"获取历史天气数据失败: {e}")
        return None


def get_last_year_same_date_temp(latitude: float, longitude: float, target_date: str) -> Optional[float]:
    """
    获取去年同一天的最高温度
    
    Args:
        latitude: 纬度
        longitude: 经度
        target_date: 目标日期 (YYYY-MM-DD)
    
    Returns:
        去年同一天的最高温度（摄氏度），如果失败返回 None
    """
    try:
        # 计算去年同一天的日期
        target = datetime.strptime(target_date, '%Y-%m-%d')
        last_year_date = target.replace(year=target.year - 1)
        last_year_str = last_year_date.strftime('%Y-%m-%d')
        
        # 获取历史数据
        historical_data = get_historical_weather(latitude, longitude, last_year_str, last_year_str)
        if historical_data is None:
            return None
        
        hourly_data = historical_data.get('hourly', {})
        times = hourly_data.get('time', [])
        temperatures = hourly_data.get('temperature_2m', [])
        
        if not times or not temperatures:
            return None
        
        # 筛选出当天的温度数据
        day_temps = []
        for i, time_str in enumerate(times):
            if time_str.startswith(last_year_str):
                temp = temperatures[i]
                if temp is not None:
                    day_temps.append(temp)
        
        if not day_temps:
            return None
        
        return max(day_temps)
    except Exception as e:
        print(f"获取去年同一天温度失败: {e}")
        return None


def get_historical_temp_range(latitude: float, longitude: float, target_date: str, years: int = 5) -> Optional[Dict]:
    """
    获取过去N年同一天的温度范围
    
    Args:
        latitude: 纬度
        longitude: 经度
        target_date: 目标日期 (YYYY-MM-DD)
        years: 查询的年数（默认5年）
    
    Returns:
        包含 min_temp, max_temp, avg_temp 的字典，如果失败返回 None
    """
    try:
        target = datetime.strptime(target_date, '%Y-%m-%d')
        temps = []
        
        # 获取过去N年同一天的温度
        for year_offset in range(1, years + 1):
            historical_date = target.replace(year=target.year - year_offset)
            historical_str = historical_date.strftime('%Y-%m-%d')
            
            historical_data = get_historical_weather(latitude, longitude, historical_str, historical_str)
            if historical_data is None:
                continue
            
            hourly_data = historical_data.get('hourly', {})
            times = hourly_data.get('time', [])
            temperatures = hourly_data.get('temperature_2m', [])
            
            if not times or not temperatures:
                continue
            
            # 筛选出当天的温度数据
            day_temps = []
            for i, time_str in enumerate(times):
                if time_str.startswith(historical_str):
                    temp = temperatures[i]
                    if temp is not None:
                        day_temps.append(temp)
            
            if day_temps:
                max_temp = max(day_temps)
                temps.append(max_temp)
        
        if not temps:
            return None
        
        return {
            'min_temp': min(temps),
            'max_temp': max(temps),
            'avg_temp': sum(temps) / len(temps),
            'years_count': len(temps)
        }
    except Exception as e:
        print(f"获取历史温度范围失败: {e}")
        return None


def get_today_weather_details(weather_data: Dict) -> Optional[Dict]:
    """
    从天气数据中提取当天的详细天气信息
    
    Args:
        weather_data: API 返回的天气数据
    
    Returns:
        包含当天天气详细信息的字典，如果失败返回 None
        包含：max_temp, wind_direction, wind_speed, precipitation_periods, weather_conditions
    """
    try:
        hourly_data = weather_data.get('hourly', {})
        times = hourly_data.get('time', [])
        temperatures = hourly_data.get('temperature_2m', [])
        wind_directions = hourly_data.get('winddirection_10m', [])
        wind_speeds = hourly_data.get('windspeed_10m', [])
        wind_gusts = hourly_data.get('windgusts_10m', [])
        precipitations = hourly_data.get('precipitation', [])
        weathercodes = hourly_data.get('weathercode', [])
        cloudcovers = hourly_data.get('cloudcover', [])
        
        if not times or not temperatures:
            return None
        
        # 获取当前日期（UTC）
        now = datetime.utcnow()
        today_str = now.strftime('%Y-%m-%d')
        
        # 筛选出当天的数据
        today_data = []
        for i, time_str in enumerate(times):
            if time_str.startswith(today_str):
                temp = temperatures[i] if i < len(temperatures) else None
                wind_dir = wind_directions[i] if i < len(wind_directions) else None
                wind_speed = wind_speeds[i] if i < len(wind_speeds) else None
                wind_gust = wind_gusts[i] if i < len(wind_gusts) else None
                precip = precipitations[i] if i < len(precipitations) else None
                wcode = weathercodes[i] if i < len(weathercodes) else None
                cloudcover = cloudcovers[i] if i < len(cloudcovers) else None
                
                if temp is not None:
                    today_data.append({
                        'time': time_str,
                        'temp': temp,
                        'wind_direction': wind_dir,
                        'wind_speed': wind_speed,
                        'wind_gust': wind_gust,
                        'precipitation': precip if precip is not None else 0,
                        'weathercode': wcode,
                        'cloudcover': cloudcover
                    })
        
        if not today_data:
            return None
        
        # 计算最高温度
        max_temp = max(item['temp'] for item in today_data)
        
        # 计算平均风向和风速（使用加权平均，权重为风速）
        valid_wind_data = [(item['wind_direction'], item['wind_speed']) 
                          for item in today_data 
                          if item['wind_direction'] is not None and item['wind_speed'] is not None]
        
        if valid_wind_data:
            # 计算平均风向（考虑圆形角度）
            sin_sum = sum(wind_speed * math.sin(math.radians(wind_dir)) for wind_dir, wind_speed in valid_wind_data)
            cos_sum = sum(wind_speed * math.cos(math.radians(wind_dir)) for wind_dir, wind_speed in valid_wind_data)
            avg_wind_direction = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
            
            # 计算平均风速
            total_speed = sum(wind_speed for _, wind_speed in valid_wind_data)
            avg_wind_speed = total_speed / len(valid_wind_data) if valid_wind_data else 0
        else:
            avg_wind_direction = None
            avg_wind_speed = 0
        
        # 找出有降水的时段
        precipitation_periods = []
        current_period = None
        
        for item in today_data:
            if item['precipitation'] > 0:
                time_obj = datetime.strptime(item['time'], '%Y-%m-%dT%H:%M')
                hour = time_obj.hour
                
                # 判断是雨还是雪（根据天气代码）
                is_snow = item['weathercode'] in [71, 73, 75, 77, 85, 86]
                precip_type = '雪' if is_snow else '雨'
                
                if current_period is None:
                    current_period = {
                        'start_hour': hour,
                        'end_hour': hour,
                        'type': precip_type,
                        'max_precip': item['precipitation']
                    }
                elif current_period['type'] == precip_type and hour == current_period['end_hour'] + 1:
                    current_period['end_hour'] = hour
                    current_period['max_precip'] = max(current_period['max_precip'], item['precipitation'])
                else:
                    if current_period:
                        precipitation_periods.append(current_period)
                    current_period = {
                        'start_hour': hour,
                        'end_hour': hour,
                        'type': precip_type,
                        'max_precip': item['precipitation']
                    }
        
        if current_period:
            precipitation_periods.append(current_period)
        
        # 获取最常见的天气状况
        weather_conditions = {}
        for item in today_data:
            if item['weathercode'] is not None:
                desc = get_weathercode_description(item['weathercode'])
                weather_conditions[desc] = weather_conditions.get(desc, 0) + 1
        
        most_common_weather = max(weather_conditions.items(), key=lambda x: x[1])[0] if weather_conditions else '未知'
        
        # 计算最大阵风
        max_gust = 0
        valid_gusts = [item['wind_gust'] for item in today_data if item.get('wind_gust') is not None]
        if valid_gusts:
            max_gust = max(valid_gusts)
        
        # 计算平均云量
        valid_cloudcovers = [item['cloudcover'] for item in today_data if item.get('cloudcover') is not None]
        avg_cloudcover = sum(valid_cloudcovers) / len(valid_cloudcovers) if valid_cloudcovers else 0
        
        return {
            'max_temp': max_temp,
            'wind_direction': avg_wind_direction,
            'wind_speed': avg_wind_speed,
            'max_gust': max_gust,
            'cloudcover': avg_cloudcover,
            'precipitation_periods': precipitation_periods,
            'weather_condition': most_common_weather,
            'all_weather_conditions': list(weather_conditions.keys())
        }
    except Exception as e:
        print(f"解析天气详细信息失败: {e}")
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


def get_wunderground_temp(airport_code: str) -> Optional[float]:
    """
    从 Wunderground 获取机场当天最高温度
    
    Args:
        airport_code: 机场代码（ICAO格式，如KLGA）
    
    Returns:
        当天最高温度（摄氏度），如果失败返回 None
    """
    try:
        # 使用 OpenWeatherMap API 作为 Wunderground 的替代
        # 因为它提供机场级别的数据，且免费可用
        # 注意：这里使用OpenWeatherMap作为Wunderground的数据源
        api_key = os.getenv('OPENWEATHER_API_KEY', '')
        if not api_key:
            # 如果没有API密钥，尝试使用公开的天气API
            # 使用 wttr.in 作为替代（它使用多个数据源包括Wunderground）
            url = f'https://wttr.in/{airport_code}?format=j1'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # 获取当天的最高温度
                if 'weather' in data and len(data['weather']) > 0:
                    today = data['weather'][0]
                    max_temp_c = today.get('maxtempC')
                    if max_temp_c:
                        return float(max_temp_c)
    except Exception as e:
        print(f"获取 Wunderground 温度失败: {e}")
    
    return None


def get_windy_temp(airport_code: str, latitude: float, longitude: float) -> Optional[float]:
    """
    从 Windy 获取机场当天最高温度
    
    Args:
        airport_code: 机场代码（ICAO格式）
        latitude: 纬度
        longitude: 经度
    
    Returns:
        当天最高温度（摄氏度），如果失败返回 None
    """
    try:
        # Windy API 需要注册，这里使用替代方案
        # 使用 Open-Meteo API（与主数据源相同，但作为Windy的参考）
        # 或者使用其他公开API
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'hourly': 'temperature_2m',
            'timezone': 'auto',
            'forecast_days': 1,
        }
        
        response = requests.get('https://api.open-meteo.com/v1/forecast', params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            hourly_data = data.get('hourly', {})
            times = hourly_data.get('time', [])
            temperatures = hourly_data.get('temperature_2m', [])
            
            if times and temperatures:
                # 获取当天的最高温度
                today = datetime.utcnow().strftime('%Y-%m-%d')
                today_temps = []
                for i, time_str in enumerate(times):
                    if time_str.startswith(today):
                        temp = temperatures[i]
                        if temp is not None:
                            today_temps.append(temp)
                
                if today_temps:
                    return max(today_temps)
    except Exception as e:
        print(f"获取 Windy 温度失败: {e}")
    
    return None


def get_future_days_weather(weather_data: Dict, days: int = 3) -> Dict[str, Dict]:
    """
    从天气数据中提取未来N天的完整天气信息
    
    Args:
        weather_data: API 返回的天气数据
        days: 要获取的未来天数（默认3天）
    
    Returns:
        字典，键为日期字符串（YYYY-MM-DD），值为包含该天完整天气信息的字典
        包含：max_temp, wind_direction, wind_speed, max_gust, precipitation_periods, weather_condition, cloudcover
    """
    result = {}
    try:
        hourly_data = weather_data.get('hourly', {})
        times = hourly_data.get('time', [])
        temperatures = hourly_data.get('temperature_2m', [])
        wind_directions = hourly_data.get('winddirection_10m', [])
        wind_speeds = hourly_data.get('windspeed_10m', [])
        wind_gusts = hourly_data.get('windgusts_10m', [])
        precipitations = hourly_data.get('precipitation', [])
        weathercodes = hourly_data.get('weathercode', [])
        cloudcovers = hourly_data.get('cloudcover', [])
        
        if not times or not temperatures:
            return result
        
        # 获取当前日期（UTC）
        now = datetime.utcnow()
        
        # 获取未来N天的日期
        for day_offset in range(1, days + 1):
            future_date = now + timedelta(days=day_offset)
            future_date_str = future_date.strftime('%Y-%m-%d')
            
            # 筛选出当天的所有数据
            day_data = []
            for i, time_str in enumerate(times):
                if time_str.startswith(future_date_str):
                    temp = temperatures[i] if i < len(temperatures) else None
                    wind_dir = wind_directions[i] if i < len(wind_directions) else None
                    wind_speed = wind_speeds[i] if i < len(wind_speeds) else None
                    wind_gust = wind_gusts[i] if i < len(wind_gusts) else None
                    precip = precipitations[i] if i < len(precipitations) else None
                    wcode = weathercodes[i] if i < len(weathercodes) else None
                    cloudcover = cloudcovers[i] if i < len(cloudcovers) else None
                    
                    if temp is not None:
                        day_data.append({
                            'time': time_str,
                            'temp': temp,
                            'wind_direction': wind_dir,
                            'wind_speed': wind_speed,
                            'wind_gust': wind_gust,
                            'precipitation': precip if precip is not None else 0,
                            'weathercode': wcode,
                            'cloudcover': cloudcover
                        })
            
            if day_data:
                # 计算最高温度
                max_temp = max(item['temp'] for item in day_data)
                
                # 计算平均风向和风速
                valid_wind_data = [(item['wind_direction'], item['wind_speed']) 
                                  for item in day_data 
                                  if item['wind_direction'] is not None and item['wind_speed'] is not None]
                
                if valid_wind_data:
                    sin_sum = sum(wind_speed * math.sin(math.radians(wind_dir)) for wind_dir, wind_speed in valid_wind_data)
                    cos_sum = sum(wind_speed * math.cos(math.radians(wind_dir)) for wind_dir, wind_speed in valid_wind_data)
                    avg_wind_direction = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
                    total_speed = sum(wind_speed for _, wind_speed in valid_wind_data)
                    avg_wind_speed = total_speed / len(valid_wind_data)
                else:
                    avg_wind_direction = None
                    avg_wind_speed = 0
                
                # 计算最大阵风
                valid_gusts = [item['wind_gust'] for item in day_data if item.get('wind_gust') is not None]
                max_gust = max(valid_gusts) if valid_gusts else 0
                
                # 计算平均云量
                valid_cloudcovers = [item['cloudcover'] for item in day_data if item.get('cloudcover') is not None]
                avg_cloudcover = sum(valid_cloudcovers) / len(valid_cloudcovers) if valid_cloudcovers else 0
                
                # 找出有降水的时段
                precipitation_periods = []
                current_period = None
                
                for item in day_data:
                    if item['precipitation'] > 0:
                        time_obj = datetime.strptime(item['time'], '%Y-%m-%dT%H:%M')
                        hour = time_obj.hour
                        
                        is_snow = item['weathercode'] in [71, 73, 75, 77, 85, 86]
                        precip_type = '雪' if is_snow else '雨'
                        
                        if current_period is None:
                            current_period = {
                                'start_hour': hour,
                                'end_hour': hour,
                                'type': precip_type,
                                'max_precip': item['precipitation']
                            }
                        elif current_period['type'] == precip_type and hour == current_period['end_hour'] + 1:
                            current_period['end_hour'] = hour
                            current_period['max_precip'] = max(current_period['max_precip'], item['precipitation'])
                        else:
                            if current_period:
                                precipitation_periods.append(current_period)
                            current_period = {
                                'start_hour': hour,
                                'end_hour': hour,
                                'type': precip_type,
                                'max_precip': item['precipitation']
                            }
                
                if current_period:
                    precipitation_periods.append(current_period)
                
                # 获取最常见的天气状况
                weather_conditions = {}
                for item in day_data:
                    if item['weathercode'] is not None:
                        desc = get_weathercode_description(item['weathercode'])
                        weather_conditions[desc] = weather_conditions.get(desc, 0) + 1
                
                most_common_weather = max(weather_conditions.items(), key=lambda x: x[1])[0] if weather_conditions else '未知'
                
                result[future_date_str] = {
                    'max_temp': max_temp,
                    'wind_direction': avg_wind_direction,
                    'wind_speed': avg_wind_speed,
                    'max_gust': max_gust,
                    'cloudcover': avg_cloudcover,
                    'precipitation_periods': precipitation_periods,
                    'weather_condition': most_common_weather
                }
        
        return result
    except Exception as e:
        print(f"解析未来天气数据失败: {e}")
        return result


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


def send_wechat_message(message: str) -> bool:
    """
    通过企业微信机器人发送消息
    
    Args:
        message: 要发送的消息内容（Markdown格式）
    
    Returns:
        发送成功返回 True，失败返回 False
    """
    if not WECHAT_WEBHOOK_URL or WECHAT_WEBHOOK_URL == '':
        return False
    
    try:
        data = {
            'msgtype': 'markdown',
            'markdown': {
                'content': message
            }
        }
        
        response = requests.post(WECHAT_WEBHOOK_URL, json=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('errcode') == 0:
            return True
        else:
            print(f"企业微信返回错误: {result.get('errmsg', '未知错误')}")
            return False
    except Exception as e:
        print(f"发送企业微信消息失败: {e}")
        return False


def get_beijing_time() -> str:
    """获取北京时间（UTC+8）"""
    beijing_tz = timezone(timedelta(hours=8))
    beijing_time = datetime.now(beijing_tz)
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')


def get_utc_time() -> str:
    """获取 UTC 时间"""
    utc_time = datetime.utcnow()
    return utc_time.strftime('%Y-%m-%d %H:%M:%S')


def get_est_time() -> str:
    """获取美东时间（EST/EDT，UTC-5 或 UTC-4）"""
    try:
        # 使用 zoneinfo 处理夏令时（Python 3.9+）
        from zoneinfo import ZoneInfo
        est_time = datetime.now(ZoneInfo('America/New_York'))
        return est_time.strftime('%Y-%m-%d %H:%M:%S')
    except ImportError:
        # 如果 zoneinfo 不可用，使用固定 UTC-5（EST）
        est_tz = timezone(timedelta(hours=-5))
        est_time = datetime.now(est_tz)
        return est_time.strftime('%Y-%m-%d %H:%M:%S')


def get_korea_time() -> str:
    """获取韩国时间（KST，UTC+9）"""
    korea_tz = timezone(timedelta(hours=9))
    korea_time = datetime.now(korea_tz)
    return korea_time.strftime('%Y-%m-%d %H:%M:%S')


def format_temperature_message_wechat(airport: str, max_temp: float, last_year_temp: Optional[float] = None, 
                                      historical_range: Optional[Dict] = None, future_days: Optional[Dict] = None,
                                      wunderground_temp: Optional[float] = None, windy_temp: Optional[float] = None,
                                      weather_details: Optional[Dict] = None) -> str:
    """
    格式化温度提醒消息（企业微信 Markdown 格式）
    
    Args:
        airport: 机场名称
        max_temp: 最高温度（摄氏度）
        last_year_temp: 去年同一天的最高温度
        historical_range: 历史温度范围数据
        future_days: 未来3天的天气预报数据，格式为 {日期: {'max_temp': 温度, 'last_year_temp': 去年温度}}
    
    Returns:
        格式化后的消息（Markdown格式）
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
    
    # 获取三个时区的时间
    beijing_time = get_beijing_time()
    est_time = get_est_time()
    korea_time = get_korea_time()
    
    # 获取当前日期（用于显示去年日期）
    today = datetime.now()
    last_year_date = today.replace(year=today.year - 1)
    last_year_str = last_year_date.strftime('%Y年%m月%d日')
    
    message = f"""# 🌡️ 机场天气最高温预测提醒

**📍 机场:** {airport_display}  
**🕐 更新时间（北京时间 UTC+8）:** {beijing_time}  
**🕐 更新时间（美东时间 EST/EDT）:** {est_time}  
**🕐 更新时间（韩国时间 KST UTC+9）:** {korea_time}

## 📊 当天预测最高温度
**{max_temp:.1f}°C / {max_temp_f:.1f}°F** (Open-Meteo)

## 🌐 其他数据源对比
"""
    
    # 添加Wunderground温度
    if wunderground_temp is not None:
        wunderground_temp_f = celsius_to_fahrenheit(wunderground_temp)
        message += f"• **Wunderground:** {wunderground_temp:.1f}°C / {wunderground_temp_f:.1f}°F\n"
    else:
        message += "• **Wunderground:** 数据暂不可用\n"
    
    # 添加Windy温度
    if windy_temp is not None:
        windy_temp_f = celsius_to_fahrenheit(windy_temp)
        message += f"• **Windy:** {windy_temp:.1f}°C / {windy_temp_f:.1f}°F\n"
    else:
        message += "• **Windy:** 数据暂不可用\n"
    
    # 添加天气详细信息
    if weather_details:
        message += "\n## 🌤️ 天气详细信息\n"
        
        # 风向和风速
        if weather_details.get('wind_direction') is not None:
            wind_dir_name = wind_direction_to_name(weather_details['wind_direction'])
            wind_speed_mph = meters_per_second_to_miles_per_hour(weather_details.get('wind_speed', 0))
            message += f"• **风向:** {wind_dir_name}\n"
            message += f"• **风速:** {wind_speed_mph:.1f} 英里/小时\n"
        else:
            message += "• **风向:** 数据暂不可用\n"
            message += "• **风速:** 数据暂不可用\n"
        
        # 最大阵风
        max_gust = weather_details.get('max_gust', 0)
        if max_gust > 0:
            max_gust_mph = meters_per_second_to_miles_per_hour(max_gust)
            message += f"• **最大阵风:** {max_gust_mph:.1f} 英里/小时\n"
        else:
            message += "• **最大阵风:** 数据暂不可用\n"
        
        # 云量
        cloudcover = weather_details.get('cloudcover', 0)
        message += f"• **云量:** {cloudcover:.0f}%\n"
        
        # 天气状况
        weather_condition = weather_details.get('weather_condition', '未知')
        message += f"• **天气状况:** {weather_condition}\n"
        
        # 降水信息
        precip_periods = weather_details.get('precipitation_periods', [])
        if precip_periods:
            message += "• **降水时段:**\n"
            for period in precip_periods:
                start_hour = period['start_hour']
                end_hour = period['end_hour']
                precip_type = period['type']
                if start_hour == end_hour:
                    message += f"  - {start_hour:02d}:00 有{precip_type}\n"
                else:
                    message += f"  - {start_hour:02d}:00 至 {end_hour:02d}:00 有{precip_type}\n"
        else:
            message += "• **降水:** 无降水\n"
    
    message += f"""
## 📈 三个参考值
• {ref_minus:.1f}°C / {ref_minus_f:.1f}°F (最高温 -1°C)  
• {ref_center:.1f}°C / {ref_center_f:.1f}°F (最高温)  
• {ref_plus:.1f}°C / {ref_plus_f:.1f}°F (最高温 +1°C)"""
    
    # 添加去年同一天的温度对比
    if last_year_temp is not None:
        last_year_temp_f = celsius_to_fahrenheit(last_year_temp)
        diff = max_temp - last_year_temp
        diff_f = celsius_to_fahrenheit(abs(diff))
        diff_symbol = "↑" if diff > 0 else "↓" if diff < 0 else "="
        
        message += f"""

## 📅 历史对比
• **{last_year_str}:** {last_year_temp:.1f}°C / {last_year_temp_f:.1f}°F  
• **今年对比去年:** {diff_symbol} {abs(diff):.1f}°C / {diff_f:.1f}°F"""
    
    # 添加历史温度区间
    if historical_range:
        min_temp = historical_range['min_temp']
        max_temp_hist = historical_range['max_temp']
        avg_temp = historical_range['avg_temp']
        years_count = historical_range['years_count']
        
        min_temp_f = celsius_to_fahrenheit(min_temp)
        max_temp_hist_f = celsius_to_fahrenheit(max_temp_hist)
        avg_temp_f = celsius_to_fahrenheit(avg_temp)
        
        message += f"""

## 📊 过去{years_count}年同一天温度区间
• **最低:** {min_temp:.1f}°C / {min_temp_f:.1f}°F  
• **最高:** {max_temp_hist:.1f}°C / {max_temp_hist_f:.1f}°F  
• **平均:** {avg_temp:.1f}°C / {avg_temp_f:.1f}°F"""
    
    # 添加未来3天的天气预报
    if future_days and isinstance(future_days, dict):
        message += "\n\n## 📅 未来3天天气预报"
        for date_str in sorted(future_days.keys()):
            day_data = future_days.get(date_str, {})
            if not isinstance(day_data, dict):
                continue
            future_max_temp = day_data.get('max_temp', 0)
            last_year_temp_future = day_data.get('last_year_temp', None)
            wind_direction = day_data.get('wind_direction', None)
            wind_speed = day_data.get('wind_speed', 0)
            max_gust = day_data.get('max_gust', 0)
            cloudcover = day_data.get('cloudcover', 0)
            weather_condition = day_data.get('weather_condition', '未知')
            precip_periods = day_data.get('precipitation_periods', [])
            
            # 格式化日期显示
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                date_display = date_obj.strftime('%m月%d日')
                last_year_date_display = date_obj.replace(year=date_obj.year - 1).strftime('%Y年%m月%d日')
            except:
                date_display = date_str
                last_year_date_display = None
            
            future_max_temp_f = celsius_to_fahrenheit(future_max_temp)
            
            message += f"\n\n### {date_display}"
            
            # 温度
            if last_year_temp_future is not None:
                last_year_temp_future_f = celsius_to_fahrenheit(last_year_temp_future)
                message += f"\n• **最高温度:** {future_max_temp:.1f}°C / {future_max_temp_f:.1f}°F (去年{last_year_date_display}: {last_year_temp_future:.1f}°C / {last_year_temp_future_f:.1f}°F)"
            else:
                message += f"\n• **最高温度:** {future_max_temp:.1f}°C / {future_max_temp_f:.1f}°F"
            
            # 风向和风速
            if wind_direction is not None:
                wind_dir_name = wind_direction_to_name(wind_direction)
                wind_speed_mph = meters_per_second_to_miles_per_hour(wind_speed)
                message += f"\n• **风向:** {wind_dir_name}"
                message += f"\n• **风速:** {wind_speed_mph:.1f} 英里/小时"
            else:
                message += "\n• **风向:** 数据暂不可用"
                message += "\n• **风速:** 数据暂不可用"
            
            # 最大阵风
            if max_gust > 0:
                max_gust_mph = meters_per_second_to_miles_per_hour(max_gust)
                message += f"\n• **最大阵风:** {max_gust_mph:.1f} 英里/小时"
            else:
                message += "\n• **最大阵风:** 数据暂不可用"
            
            # 云量
            message += f"\n• **云量:** {cloudcover:.0f}%"
            
            # 天气状况
            message += f"\n• **天气状况:** {weather_condition}"
            
            # 降水信息
            if precip_periods:
                message += "\n• **降水时段:**"
                for period in precip_periods:
                    start_hour = period['start_hour']
                    end_hour = period['end_hour']
                    precip_type = period['type']
                    if start_hour == end_hour:
                        message += f"\n  - {start_hour:02d}:00 有{precip_type}"
                    else:
                        message += f"\n  - {start_hour:02d}:00 至 {end_hour:02d}:00 有{precip_type}"
            else:
                message += "\n• **降水:** 无降水"
    
    # 获取 Wunderground 和 Windy 网址（从配置中直接读取）
    wunderground_url = airport_info.get('wunderground_url', 'https://www.wunderground.com')
    windy_url = airport_info.get('windy_url', 'https://www.windy.com')
    
    message += f"""

## 🔗 相关网站链接
• [Wunderground 天气]({wunderground_url})  
• [Windy 天气]({windy_url})
    
⚠️ *本程序仅用于信息提醒，不做任何交易决策*"""
    
    return message


def format_temperature_message(airport: str, max_temp: float, last_year_temp: Optional[float] = None, 
                                historical_range: Optional[Dict] = None, future_days: Optional[Dict] = None,
                                wunderground_temp: Optional[float] = None, windy_temp: Optional[float] = None,
                                weather_details: Optional[Dict] = None) -> str:
    """
    格式化温度提醒消息
    
    Args:
        airport: 机场名称
        max_temp: 最高温度（摄氏度）
        last_year_temp: 去年同一天的最高温度
        historical_range: 历史温度范围数据
        future_days: 未来3天的天气预报数据，格式为 {日期: {'max_temp': 温度, 'last_year_temp': 去年温度}}
    
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
    
    # 获取三个时区的时间
    beijing_time = get_beijing_time()
    est_time = get_est_time()
    korea_time = get_korea_time()
    
    # 获取当前日期（用于显示去年日期）
    today = datetime.now()
    last_year_date = today.replace(year=today.year - 1)
    last_year_str = last_year_date.strftime('%Y年%m月%d日')
    
    message = f"""
🌡️ <b>机场天气最高温预测提醒</b>

📍 <b>机场:</b> {airport_display}
🕐 <b>更新时间（北京时间 UTC+8）:</b> {beijing_time}
🕐 <b>更新时间（美东时间 EST/EDT）:</b> {est_time}
🕐 <b>更新时间（韩国时间 KST UTC+9）:</b> {korea_time}

📊 <b>当天预测最高温度:</b>
   {max_temp:.1f}°C / {max_temp_f:.1f}°F (Open-Meteo)

🌐 <b>其他数据源对比:</b>"""
    
    # 添加Wunderground温度
    if wunderground_temp is not None:
        wunderground_temp_f = celsius_to_fahrenheit(wunderground_temp)
        message += f"\n   • <b>Wunderground:</b> {wunderground_temp:.1f}°C / {wunderground_temp_f:.1f}°F"
    else:
        message += "\n   • <b>Wunderground:</b> 数据暂不可用"
    
    # 添加Windy温度
    if windy_temp is not None:
        windy_temp_f = celsius_to_fahrenheit(windy_temp)
        message += f"\n   • <b>Windy:</b> {windy_temp:.1f}°C / {windy_temp_f:.1f}°F"
    else:
        message += "\n   • <b>Windy:</b> 数据暂不可用"
    
    # 添加天气详细信息
    if weather_details:
        message += "\n\n🌤️ <b>天气详细信息:</b>"
        
        # 风向和风速
        if weather_details.get('wind_direction') is not None:
            wind_dir_name = wind_direction_to_name(weather_details['wind_direction'])
            wind_speed_mph = meters_per_second_to_miles_per_hour(weather_details.get('wind_speed', 0))
            message += f"\n   • <b>风向:</b> {wind_dir_name}"
            message += f"\n   • <b>风速:</b> {wind_speed_mph:.1f} 英里/小时"
        else:
            message += "\n   • <b>风向:</b> 数据暂不可用"
            message += "\n   • <b>风速:</b> 数据暂不可用"
        
        # 最大阵风
        max_gust = weather_details.get('max_gust', 0)
        if max_gust > 0:
            max_gust_mph = meters_per_second_to_miles_per_hour(max_gust)
            message += f"\n   • <b>最大阵风:</b> {max_gust_mph:.1f} 英里/小时"
        else:
            message += "\n   • <b>最大阵风:</b> 数据暂不可用"
        
        # 云量
        cloudcover = weather_details.get('cloudcover', 0)
        message += f"\n   • <b>云量:</b> {cloudcover:.0f}%"
        
        # 天气状况
        weather_condition = weather_details.get('weather_condition', '未知')
        message += f"\n   • <b>天气状况:</b> {weather_condition}"
        
        # 降水信息
        precip_periods = weather_details.get('precipitation_periods', [])
        if precip_periods:
            message += "\n   • <b>降水时段:</b>"
            for period in precip_periods:
                start_hour = period['start_hour']
                end_hour = period['end_hour']
                precip_type = period['type']
                if start_hour == end_hour:
                    message += f"\n     - {start_hour:02d}:00 有{precip_type}"
                else:
                    message += f"\n     - {start_hour:02d}:00 至 {end_hour:02d}:00 有{precip_type}"
        else:
            message += "\n   • <b>降水:</b> 无降水"
    
    message += f"""

📈 <b>三个参考值:</b>
   • {ref_minus:.1f}°C / {ref_minus_f:.1f}°F (最高温 -1°C)
   • {ref_center:.1f}°C / {ref_center_f:.1f}°F (最高温)
   • {ref_plus:.1f}°C / {ref_plus_f:.1f}°F (最高温 +1°C)"""
    
    # 添加去年同一天的温度对比
    if last_year_temp is not None:
        last_year_temp_f = celsius_to_fahrenheit(last_year_temp)
        diff = max_temp - last_year_temp
        diff_f = celsius_to_fahrenheit(abs(diff))
        diff_symbol = "↑" if diff > 0 else "↓" if diff < 0 else "="
        
        message += f"""

📅 <b>历史对比:</b>
   • {last_year_str}: {last_year_temp:.1f}°C / {last_year_temp_f:.1f}°F
   • 今年对比去年: {diff_symbol} {abs(diff):.1f}°C / {diff_f:.1f}°F"""
    
    # 添加历史温度区间
    if historical_range:
        min_temp = historical_range['min_temp']
        max_temp_hist = historical_range['max_temp']
        avg_temp = historical_range['avg_temp']
        years_count = historical_range['years_count']
        
        min_temp_f = celsius_to_fahrenheit(min_temp)
        max_temp_hist_f = celsius_to_fahrenheit(max_temp_hist)
        avg_temp_f = celsius_to_fahrenheit(avg_temp)
        
        message += f"""

📊 <b>过去{years_count}年同一天温度区间:</b>
   • 最低: {min_temp:.1f}°C / {min_temp_f:.1f}°F
   • 最高: {max_temp_hist:.1f}°C / {max_temp_hist_f:.1f}°F
   • 平均: {avg_temp:.1f}°C / {avg_temp_f:.1f}°F"""
    
    # 添加未来3天的天气预报
    if future_days and isinstance(future_days, dict):
        message += "\n\n📅 <b>未来3天天气预报:</b>"
        for date_str in sorted(future_days.keys()):
            day_data = future_days.get(date_str, {})
            if not isinstance(day_data, dict):
                continue
            future_max_temp = day_data.get('max_temp', 0)
            last_year_temp_future = day_data.get('last_year_temp', None)
            wind_direction = day_data.get('wind_direction', None)
            wind_speed = day_data.get('wind_speed', 0)
            max_gust = day_data.get('max_gust', 0)
            cloudcover = day_data.get('cloudcover', 0)
            weather_condition = day_data.get('weather_condition', '未知')
            precip_periods = day_data.get('precipitation_periods', [])
            
            # 格式化日期显示
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                date_display = date_obj.strftime('%m月%d日')
                last_year_date_display = date_obj.replace(year=date_obj.year - 1).strftime('%Y年%m月%d日')
            except:
                date_display = date_str
                last_year_date_display = None
            
            future_max_temp_f = celsius_to_fahrenheit(future_max_temp)
            
            message += f"\n\n   <b>{date_display}:</b>"
            
            # 温度
            if last_year_temp_future is not None:
                last_year_temp_future_f = celsius_to_fahrenheit(last_year_temp_future)
                message += f"\n     • <b>最高温度:</b> {future_max_temp:.1f}°C / {future_max_temp_f:.1f}°F (去年{last_year_date_display}: {last_year_temp_future:.1f}°C / {last_year_temp_future_f:.1f}°F)"
            else:
                message += f"\n     • <b>最高温度:</b> {future_max_temp:.1f}°C / {future_max_temp_f:.1f}°F"
            
            # 风向和风速
            if wind_direction is not None:
                wind_dir_name = wind_direction_to_name(wind_direction)
                wind_speed_mph = meters_per_second_to_miles_per_hour(wind_speed)
                message += f"\n     • <b>风向:</b> {wind_dir_name}"
                message += f"\n     • <b>风速:</b> {wind_speed_mph:.1f} 英里/小时"
            else:
                message += "\n     • <b>风向:</b> 数据暂不可用"
                message += "\n     • <b>风速:</b> 数据暂不可用"
            
            # 最大阵风
            if max_gust > 0:
                max_gust_mph = meters_per_second_to_miles_per_hour(max_gust)
                message += f"\n     • <b>最大阵风:</b> {max_gust_mph:.1f} 英里/小时"
            else:
                message += "\n     • <b>最大阵风:</b> 数据暂不可用"
            
            # 云量
            message += f"\n     • <b>云量:</b> {cloudcover:.0f}%"
            
            # 天气状况
            message += f"\n     • <b>天气状况:</b> {weather_condition}"
            
            # 降水信息
            if precip_periods:
                message += "\n     • <b>降水时段:</b>"
                for period in precip_periods:
                    start_hour = period['start_hour']
                    end_hour = period['end_hour']
                    precip_type = period['type']
                    if start_hour == end_hour:
                        message += f"\n       - {start_hour:02d}:00 有{precip_type}"
                    else:
                        message += f"\n       - {start_hour:02d}:00 至 {end_hour:02d}:00 有{precip_type}"
            else:
                message += "\n     • <b>降水:</b> 无降水"
    
    # 获取 Wunderground 和 Windy 网址（从配置中直接读取）
    wunderground_url = airport_info.get('wunderground_url', 'https://www.wunderground.com')
    windy_url = airport_info.get('windy_url', 'https://www.windy.com')
    
    message += f"""

🔗 <b>相关网站链接:</b>
   • <a href="{wunderground_url}">Wunderground 天气</a>
   • <a href="{windy_url}">Windy 天气</a>
    
⚠️ <i>本程序仅用于信息提醒，不做任何交易决策</i>"""
    
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


def check_and_send_alerts(force_send: bool = False):
    """
    检查所有机场的天气并发送提醒
    
    Args:
        force_send: 如果为 True，强制发送所有机场的消息（用于手动触发）
    """
    # 加载上次的状态
    state = load_state()
    last_max_temps = state.get('last_max_temps', {airport: None for airport in AIRPORTS.keys()})
    last_check_date = state.get('last_check_date')
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    is_new_day = (last_check_date != current_date)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始检查天气...")
    if force_send:
        print("  🔔 强制发送模式：将发送所有机场的消息")
    
    # 更新当前最高温度
    current_max_temps = {}
    
    for airport, coords in AIRPORTS.items():
        print(f"正在检查 {airport}...")
        
        # 获取天气数据（带重试）
        weather_data = None
        max_retries = 2
        for retry in range(max_retries):
            weather_data = get_weather_forecast(coords['lat'], coords['lon'])
            if weather_data is not None:
                break
            if retry < max_retries - 1:
                print(f"  ⚠️ 获取 {airport} 天气数据失败，重试中... ({retry + 1}/{max_retries})")
                time.sleep(2)  # 等待2秒后重试
        
        if weather_data is None:
            print(f"  ❌ 获取 {airport} 天气数据失败（已重试{max_retries}次）")
            continue
        
        # 获取当天最高温度和天气详细信息
        max_temp = get_today_max_temp(weather_data)
        if max_temp is None:
            print(f"  ❌ 解析 {airport} 温度数据失败")
            continue
        
        # 获取天气详细信息
        weather_details = get_today_weather_details(weather_data)
        if weather_details:
            print(f"  ✅ {airport} 天气详细信息已获取")
            if weather_details.get('wind_direction') is not None:
                wind_dir_name = wind_direction_to_name(weather_details['wind_direction'])
                wind_speed_mph = meters_per_second_to_miles_per_hour(weather_details.get('wind_speed', 0))
                print(f"  ✅ 风向: {wind_dir_name}, 风速: {wind_speed_mph:.1f} 英里/小时")
            print(f"  ✅ 天气状况: {weather_details.get('weather_condition', '未知')}")
            precip_periods = weather_details.get('precipitation_periods', [])
            if precip_periods:
                print(f"  ✅ 有 {len(precip_periods)} 个降水时段")
            else:
                print(f"  ✅ 无降水")
        else:
            print(f"  ⚠️ 获取 {airport} 天气详细信息失败")
        
        current_max_temps[airport] = max_temp
        print(f"  ✅ {airport} 当天最高温度: {max_temp:.1f}°C")
        
        # 获取Wunderground和Windy的温度
        wunderground_temp = None
        windy_temp = None
        
        try:
            airport_info = AIRPORTS.get(airport, {})
            wunderground_code = airport_info.get('wunderground_code', '')
            
            if wunderground_code:
                print(f"  🌐 正在获取 Wunderground 数据...")
                wunderground_temp = get_wunderground_temp(wunderground_code)
                if wunderground_temp is not None:
                    print(f"  ✅ Wunderground 温度: {wunderground_temp:.1f}°C")
                else:
                    print(f"  ⚠️ Wunderground 数据获取失败")
            
            # 获取 Windy 温度数据
            print(f"  🌐 正在获取 Windy 数据...")
            windy_temp = get_windy_temp('', coords['lat'], coords['lon'])
            if windy_temp is not None:
                print(f"  ✅ Windy 温度: {windy_temp:.1f}°C")
            else:
                print(f"  ⚠️ Windy 数据获取失败")
        except Exception as e:
            print(f"  ⚠️ 获取其他数据源失败: {e}")
        
        # 获取历史数据
        today_str = datetime.now().strftime('%Y-%m-%d')
        last_year_temp = None
        historical_range = None
        
        try:
            print(f"  📅 正在获取 {airport} 历史数据...")
            last_year_temp = get_last_year_same_date_temp(coords['lat'], coords['lon'], today_str)
            if last_year_temp is not None:
                print(f"  ✅ 去年同一天温度: {last_year_temp:.1f}°C")
            
            historical_range = get_historical_temp_range(coords['lat'], coords['lon'], today_str, years=5)
            if historical_range:
                print(f"  ✅ 过去{historical_range['years_count']}年温度区间: {historical_range['min_temp']:.1f}°C - {historical_range['max_temp']:.1f}°C")
        except Exception as e:
            print(f"  ⚠️ 获取历史数据失败: {e}")
        
        # 获取未来3天的天气预报
        future_days = {}
        try:
            print(f"  🔮 正在获取 {airport} 未来3天天气预报...")
            future_days_raw = get_future_days_weather(weather_data, days=3)
            
            # 为每一天获取去年同一天的温度
            for date_str, day_weather in future_days_raw.items():
                last_year_temp_future = None
                try:
                    last_year_temp_future = get_last_year_same_date_temp(coords['lat'], coords['lon'], date_str)
                except Exception as e:
                    print(f"    ⚠️ 获取 {date_str} 去年温度失败: {e}")
                
                # 合并天气信息和去年温度
                day_weather['last_year_temp'] = last_year_temp_future
                future_days[date_str] = day_weather
            
            if future_days:
                print(f"  ✅ 已获取未来3天天气预报")
        except Exception as e:
            print(f"  ⚠️ 获取未来3天天气预报失败: {e}")
        
        # 判断是否需要发送通知
        should_send = False
        
        # 强制发送模式（手动触发时）
        if force_send:
            should_send = True
            print(f"  🔔 强制发送模式：将发送消息")
        
        # 条件1：每天第一次计算完成
        elif is_new_day:
            should_send = True
            print(f"  📅 新的一天，发送首次提醒")
        
        # 条件2：预测最高温发生变化
        elif last_max_temps.get(airport) is not None:
            if abs(max_temp - last_max_temps[airport]) > 0.1:  # 温度变化超过0.1度
                should_send = True
                print(f"  🔄 温度变化: {last_max_temps[airport]:.1f}°C → {max_temp:.1f}°C")
        
        # 如果是第一次运行（所有值都是 None）
        elif last_max_temps.get(airport) is None:
            should_send = True
            print(f"  🆕 首次运行，发送提醒")
        
        # 发送通知
        if should_send:
            # 发送到 Telegram
            telegram_message = format_temperature_message(airport, max_temp, last_year_temp, historical_range, future_days, wunderground_temp, windy_temp, weather_details)
            telegram_success = send_telegram_message(telegram_message)
            
            # 发送到企业微信（如果配置了）
            wechat_success = False
            if WECHAT_WEBHOOK_URL and WECHAT_WEBHOOK_URL != '':
                wechat_message = format_temperature_message_wechat(airport, max_temp, last_year_temp, historical_range, future_days, wunderground_temp, windy_temp, weather_details)
                wechat_success = send_wechat_message(wechat_message)
            
            # 打印发送结果
            results = []
            if telegram_success:
                results.append("Telegram")
            if wechat_success:
                results.append("企业微信")
            
            if results:
                print(f"  ✅ 已发送 {airport} 提醒消息到: {', '.join(results)}")
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
    
    # 检查是否是手动触发（通过环境变量判断）
    # GitHub Actions 手动触发时会设置 GITHUB_EVENT_NAME=workflow_dispatch
    is_manual_trigger = os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    
    # 执行检查（手动触发时强制发送）
    check_and_send_alerts(force_send=is_manual_trigger)


if __name__ == '__main__':
    main()

