# github_crawler.py
import requests
from config import GITHUB_API_BASE, HEADERS, ACTIVITY_PERIOD_DAYS, TOP_N, PER_PAGE
from github_utils import retry_decorator, format_datetime, logger

class GitHubTopCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.check_rate_limit()  # 初始化时检查API限额

    def check_rate_limit(self):
        """检查GitHub API剩余请求数（避免超限）"""
        try:
            resp = self.session.get(f"{GITHUB_API_BASE}/rate_limit")
            resp.raise_for_status()
            limit_data = resp.json()
            core_limit = limit_data["rate"]["limit"]
            core_remaining = limit_data["rate"]["remaining"]
            core_reset = format_datetime(limit_data["rate"]["reset"])
            logger.info(f"API限额：{core_remaining}/{core_limit}，重置时间：{core_reset}")
            if core_remaining < 100:
                logger.warning(f"API剩余请求数不足（{core_remaining}），建议稍后再爬")
            return core_remaining
        except Exception as e:
            logger.error(f"检查API限额失败：{e}")
            return 0

    # github_crawler.py 中修改 get_top_star_repos 方法的 search_url
    @retry_decorator()
    def get_top_star_repos(self):
        """获取GitHub Star前N仓库列表（按stars降序）"""
        repos = []
        pages = (TOP_N + PER_PAGE - 1) // PER_PAGE  # 计算需要的页数
        
        for page in range(1, pages + 1):
            # 修复：将 stars:>* 改为 stars:>0（合法语法），并编码URL参数
            import urllib.parse  # 新增：URL编码避免特殊字符问题
            search_query = urllib.parse.quote("stars:>0")  # 编码搜索条件
            search_url = (
                f"{GITHUB_API_BASE}/search/repositories"
                f"?q={search_query}&sort=stars&order=desc&per_page={PER_PAGE}&page={page}"
            )
            logger.info(f"爬取第{page}页仓库列表：{search_url}")
            
            resp = self.session.get(search_url)
            resp.raise_for_status()
            data = resp.json()
            
            if not data.get("items"):
                logger.warning(f"第{page}页无数据，终止爬取")
                break
            
            # 提取基础信息（用于后续爬取详情）
            for item in data["items"]:
                repos.append({
                    "owner": item["owner"]["login"],
                    "repo_name": item["name"],
                    "full_name": item["full_name"],
                    "star_count": item["stargazers_count"],
                    "fork_count": item["forks_count"],
                    "html_url": item["html_url"],
                    "language": item["language"],
                    "created_at": format_datetime(item["created_at"]),
                    "updated_at": format_datetime(item["updated_at"])
                })
            
            if len(repos) >= TOP_N:
                break
        
        # 截断到TOP_N
        top_repos = repos[:TOP_N]
        logger.info(f"成功获取{len(top_repos)}个Star前{TOP_N}仓库")
        return top_repos

    @retry_decorator()
    def get_repo_details(self, owner, repo_name):
        """爬取单个仓库的详细数据"""
        # 1. 基础详情（标签、许可证、描述等）
        detail_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}"
        resp = self.session.get(detail_url)
        resp.raise_for_status()
        detail_data = resp.json()
        
        # 2. 爬取活跃度相关数据（提交、PR、Issue、贡献者）
        activity_data = self.get_repo_activity(owner, repo_name)
        
        # 3. 整合所有数据（结构化，便于后续处理）
        full_data = {
            # 核心标识
            "basic_info": {
                "owner": owner,
                "repo_name": repo_name,
                "full_name": detail_data["full_name"],
                "repo_id": detail_data["id"],
                "html_url": detail_data["html_url"],
                "description": detail_data["description"],
                "language": detail_data["language"],
                "topics": detail_data.get("topics", []),  # 标签
                "license": detail_data.get("license", {}).get("name") if detail_data.get("license") else None
            },
            # 量化指标
            "metrics": {
                "star_count": detail_data["stargazers_count"],
                "fork_count": detail_data["forks_count"],
                "subscriber_count": detail_data["subscribers_count"],  # 订阅数（近似引用数）
                "open_issues_count": detail_data["open_issues_count"],
                "watchers_count": detail_data["watchers_count"],
                "size_kb": detail_data["size"],  # 仓库大小（KB）
                "commit_count": detail_data.get("commits_count", 0)  # 总提交数（基础）
            },
            # 时间维度
            "timeline": {
                "created_at": format_datetime(detail_data["created_at"]),
                "updated_at": format_datetime(detail_data["updated_at"]),
                "pushed_at": format_datetime(detail_data["pushed_at"])
            },
            # 活跃度数据
            "activity": activity_data,
            # 综合得分（便于可视化）
            "activity_score": activity_data.get("activity_score", 0)
        }
        
        logger.info(f"成功爬取{owner}/{repo_name}详细数据")
        return full_data

    @retry_decorator()
    def get_repo_activity(self, owner, repo_name):
        """爬取仓库活跃度数据（最近ACTIVITY_PERIOD_DAYS天）"""
        # 1. 最近一年提交数
        commit_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/commits?per_page=1"
        resp = self.session.get(commit_url)
        if resp.status_code == 200:
            # 从响应头获取总页数（提交数≈页数*30，因为per_page=30）
            last_page = resp.headers.get("Link", "").split('page=')[-1].split('>')[0] if "Link" in resp.headers else 1
            commits_total = int(last_page) * 30
        else:
            commits_total = 0
        
        # 2. PR数据（合并数/打开数）
        pr_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/pulls?state=all&per_page=1"
        resp = self.session.get(pr_url)
        prs_total = int(resp.headers.get("Link", "").split('page=')[-1].split('>')[0]) if "Link" in resp.headers else 0
        prs_merged = sum(1 for pr in self.session.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/pulls?state=closed").json() if pr.get("merged_at"))
        
        # 3. Issue数据（关闭数/打开数）
        issue_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/issues?state=all&per_page=1"
        resp = self.session.get(issue_url)
        issues_total = int(resp.headers.get("Link", "").split('page=')[-1].split('>')[0]) if "Link" in resp.headers else 0
        issues_closed = sum(1 for issue in self.session.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/issues?state=closed").json() if not issue.get("pull_request"))
        
        # 4. 贡献者数
        contributor_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo_name}/contributors?per_page=1"
        resp = self.session.get(contributor_url)
        contributors_total = int(resp.headers.get("Link", "").split('page=')[-1].split('>')[0]) if "Link" in resp.headers else 0
        
        # 整合活跃度数据
        activity_data = {
            "commits_total": commits_total,
            "prs_total": prs_total,
            "prs_merged": prs_merged,
            "issues_total": issues_total,
            "issues_closed": issues_closed,
            "issues_open": issues_total - issues_closed,
            "contributors_total": contributors_total,
            "analysis_period_days": ACTIVITY_PERIOD_DAYS
        }
        
        # 计算活跃度得分
        from github_utils import calculate_activity_score
        activity_data["activity_score"] = calculate_activity_score(activity_data)
        
        return activity_data