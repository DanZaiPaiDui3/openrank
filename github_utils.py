# github_utils.py
import json
import time
import logging
from datetime import datetime, timedelta
from functools import wraps
from config import OUTPUT_DIR, MAX_RETRIES, BASE_DELAY
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"{OUTPUT_DIR}/crawler.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def retry_decorator(max_retries=MAX_RETRIES, base_delay=BASE_DELAY):
    """指数退避重试装饰器：处理API限流/网络异常"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    delay = base_delay * (2 ** retries)  # 指数退避：2→4→8→16→32秒
                    logger.warning(f"调用{func.__name__}失败（第{retries}次）：{str(e)[:100]}，{delay}秒后重试")
                    time.sleep(delay)
                    if retries == max_retries:
                        logger.error(f"调用{func.__name__}失败（达到最大重试次数）：{str(e)}")
                        raise
            return None
        return wrapper
    return decorator

# github_utils.py 中修改 format_datetime 函数
def format_datetime(input_data):
    """
    格式化时间：兼容ISO字符串/UNIX时间戳（int/float）
    :param input_data: ISO字符串（2025-12-23T10:00:00Z）或时间戳（1766465355）
    :return: 标准时间字符串（YYYY-MM-DD HH:MM:SS）或None
    """
    if input_data is None:
        return None
    
    # 处理UNIX时间戳（int/float）
    if isinstance(input_data, (int, float)):
        try:
            dt = datetime.fromtimestamp(input_data)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"时间戳格式化失败：{input_data}，错误：{e}")
            return None
    
    # 处理ISO字符串（原逻辑）
    if isinstance(input_data, str):
        try:
            # GitHub时间格式：2025-12-23T10:00:00Z
            dt = datetime.strptime(input_data, "%Y-%m-%dT%H:%M:%SZ")
            return dt.strftime("%Y-%m-%d %H:%M:%S")  # 兼容MySQL DATETIME格式
        except Exception as e:
            logger.error(f"ISO时间格式化失败：{input_data}，错误：{e}")
            return None
    
    # 其他类型
    logger.error(f"不支持的时间类型：{type(input_data)}，值：{input_data}")
    return None

def save_json(data, file_name, indent=2, ensure_ascii=False):
    """保存数据为JSON文件（便于后续处理）"""
    file_path = os.path.join(OUTPUT_DIR, file_name)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        logger.info(f"数据已保存到：{file_path}")
        return file_path
    except Exception as e:
        logger.error(f"保存JSON失败：{e}")
        return None

def load_json(file_name):
    """加载JSON文件（用于缓存/断点续爬）"""
    file_path = os.path.join(OUTPUT_DIR, file_name)
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载JSON失败：{e}")
        return {}

def calculate_activity_score(activity_data):
    """计算仓库活跃度得分（0-100，便于后续可视化）"""
    # 权重：提交数(40%) + PR合并数(20%) + Issue处理数(20%) + 贡献者数(20%)
    commits = activity_data.get("commits_total", 0)
    prs_merged = activity_data.get("prs_merged", 0)
    issues_resolved = activity_data.get("issues_closed", 0) - activity_data.get("issues_open", 0)
    contributors = activity_data.get("contributors_total", 0)
    
    # 归一化（避免数值过大）
    commits_score = min(commits / 1000, 1) * 40
    prs_score = min(prs_merged / 100, 1) * 20
    issues_score = min(max(issues_resolved / 50, 0), 1) * 20
    contributors_score = min(contributors / 100, 1) * 20
    
    total_score = round(commits_score + prs_score + issues_score + contributors_score, 2)
    return total_score