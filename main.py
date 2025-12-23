# main.py
import time
from github_crawler import GitHubTopCrawler
from github_utils import save_json, load_json, logger
from config import TOP_N, CACHE_FILE, FINAL_JSON_FILE

def main():
    # 初始化爬虫
    crawler = GitHubTopCrawler()
    
    # 1. 获取Star前500仓库列表
    logger.info("========== 开始爬取GitHub Star前{}仓库列表 ==========".format(TOP_N))
    top_repos = crawler.get_top_star_repos()
    if not top_repos:
        logger.error("获取仓库列表失败，终止程序")
        return
    
    # 保存仓库列表（断点续爬基础）
    save_json(top_repos, "github_top_repos_list.json")
    
    # 2. 爬取每个仓库的详细数据（支持断点续爬）
    logger.info("========== 开始爬取仓库详细数据 ==========")
    cache_data = load_json(CACHE_FILE)  # 缓存已爬取的数据
    final_data = []
    
    for idx, repo in enumerate(top_repos, 1):
        full_name = repo["full_name"]
        logger.info(f"[{idx}/{TOP_N}] 开始爬取：{full_name}")
        
        # 断点续爬：如果已爬取，直接使用缓存
        if full_name in cache_data:
            logger.info(f"{full_name}已爬取，使用缓存数据")
            final_data.append(cache_data[full_name])
            continue
        
        try:
            # 爬取详细数据
            repo_detail = crawler.get_repo_details(repo["owner"], repo["repo_name"])
            final_data.append(repo_detail)
            
            # 更新缓存
            cache_data[full_name] = repo_detail
            save_json(cache_data, CACHE_FILE)
            
            # 控制请求频率（避免限流）
            time.sleep(1)
        
        except Exception as e:
            logger.error(f"爬取{full_name}失败：{e}")
            continue
    
    # 3. 保存最终数据（结构化，便于后续处理）
    logger.info("========== 爬取完成，保存最终数据 ==========")
    output_data = {
        "crawler_info": {
            "crawl_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "top_n": TOP_N,
            "success_count": len(final_data),
            "fail_count": TOP_N - len(final_data),
            "analysis_period_days": crawler.ACTIVITY_PERIOD_DAYS if hasattr(crawler, "ACTIVITY_PERIOD_DAYS") else ACTIVITY_PERIOD_DAYS
        },
        "repos_data": final_data  # 核心数据：列表形式，每个元素是一个仓库的完整数据
    }
    
    save_json(output_data, FINAL_JSON_FILE)
    logger.info("========== 所有操作完成 ==========")

if __name__ == "__main__":
    main()