import json
import os
from config import OUTPUT_DIR, CACHE_FILE

def optimize_cache():
    """将原始缓存文件重构为更易操作的格式（提取图分析核心字段）"""
    # 加载原始缓存
    cache_path = os.path.join(OUTPUT_DIR, CACHE_FILE)
    if not os.path.exists(cache_path):
        print(f"❌ 缓存文件不存在：{cache_path}")
        return
    
    with open(cache_path, "r", encoding="utf-8") as f:
        raw_cache = json.load(f)
    
    # 重构为列表+标准化字段（便于遍历/过滤/关联）
    optimized_data = []
    for full_name, repo_data in raw_cache.items():
        # 提取图分析核心字段
        core_data = {
            "id": repo_data["basic_info"]["repo_id"],  # 唯一标识
            "full_name": full_name,  # 仓库全名（如 freeCodeCamp/freeCodeCamp）
            "owner": repo_data["basic_info"]["owner"],
            "name": repo_data["basic_info"]["repo_name"],
            "topics": repo_data["basic_info"]["topics"] or [],  # 标签（空列表兜底）
            "activity_score": repo_data["activity_score"],  # 活跃度（节点大小依据）
            "star_count": repo_data["metrics"]["star_count"],  # 备用维度
            "language": repo_data["basic_info"]["language"] or "Unknown",  # 节点颜色依据
            "fork_count": repo_data["metrics"]["fork_count"]  # 备用维度
        }
        optimized_data.append(core_data)
    
    # 保存优化后的数据（JSON Lines格式 + 普通JSON格式，双版本）
    # 1. 列表式JSON（便于整体读取）
    optimized_json_path = os.path.join(OUTPUT_DIR, "optimized_github_top500.json")
    with open(optimized_json_path, "w", encoding="utf-8") as f:
        json.dump(optimized_data, f, indent=2, ensure_ascii=False)
    
    # 2. JSON Lines格式（便于逐行读取/大数据量）
    optimized_jl_path = os.path.join(OUTPUT_DIR, "optimized_github_top500.jl")
    with open(optimized_jl_path, "w", encoding="utf-8") as f:
        for item in optimized_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    print(f"✅ 缓存优化完成！")
    print(f"   - 列表式JSON：{optimized_json_path}")
    print(f"   - JSON Lines：{optimized_jl_path}")
    print(f"   - 包含 {len(optimized_data)} 个仓库")
    return optimized_data

if __name__ == "__main__":
    optimize_cache()