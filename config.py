# config.py
import os

# ==================== GitHub API 配置 ====================
# 替换为你的GitHub Personal Access Token（需开启repo权限）

GITHUB_TOKEN = "YOUR_GITHUB_PAT_HERE"
# API基础URL
GITHUB_API_BASE = "https://api.github.com"
# 请求头（带Token认证）
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "GitHub-Star-Top500-Crawler"  # 必须带User-Agent，否则会被拦截
}

# ==================== 爬取配置 ====================
# 目标：Star前500仓库
TOP_N = 500
# 每页获取数量（GitHub Search API最大100）
PER_PAGE = 100
# 分析活跃度的时间范围（天）
ACTIVITY_PERIOD_DAYS = 365
# 请求延迟（秒）：避免触发限流，指数退避会叠加
BASE_DELAY = 2
# 最大重试次数
MAX_RETRIES = 5

# ==================== 保存配置 ====================
# 数据保存根目录
OUTPUT_DIR = "github_top500_data"
# 最终数据文件名
FINAL_JSON_FILE = "github_top500_stars.json"
# 临时缓存文件（避免重复爬取）
CACHE_FILE = "crawler_cache.json"

# 创建输出目录
os.makedirs(OUTPUT_DIR, exist_ok=True)