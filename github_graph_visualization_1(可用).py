
#500个项目的图
#某项目的4级分支图


import json
import os
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from config import OUTPUT_DIR

# 全局样式配置
plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans", "Arial"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.figsize"] = (25, 20)
plt.rcParams["figure.dpi"] = 100
plt.rcParams["axes.facecolor"] = "#f8f9fa"
plt.rcParams["savefig.facecolor"] = "#f8f9fa"

# 编程语言配色
LANGUAGE_COLORS = {
    "JavaScript": "#F0DB4F",
    "Python": "#3776AB",
    "Java": "#007396",
    "TypeScript": "#007ACC",
    "C++": "#00599C",
    "C#": "#239120",
    "Go": "#00ADD8",
    "Rust": "#DEA584",
    "PHP": "#777BB4",
    "Ruby": "#CC342D",
    "Unknown": "#808080"
}

class GitHubGraphVisualizer:
    def __init__(self, data_path=None):
        """初始化：加载优化后的数据"""
        self.data_path = data_path or os.path.join(OUTPUT_DIR, "optimized_github_top500.json")
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"数据文件不存在：{self.data_path}")
        
        # 加载并预处理数据（添加缺失值兜底）
        with open(self.data_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        
        # 数据清洗：确保所有字段存在且有默认值
        self.repo_data = []
        for repo in raw_data:
            cleaned_repo = {
                "id": repo.get("id", 0),
                "full_name": repo.get("full_name", ""),
                "owner": repo.get("owner", ""),
                "name": repo.get("name", ""),
                "topics": repo.get("topics", []),
                # 核心字段：activity_score 兜底为0
                "activity_score": float(repo.get("activity_score", 0.0)),
                "star_count": int(repo.get("star_count", 0)),
                "language": repo.get("language", "Unknown"),
                "fork_count": int(repo.get("fork_count", 0))
            }
            self.repo_data.append(cleaned_repo)
        
        # 构建快速查询映射
        self.repo_map = {repo["full_name"]: repo for repo in self.repo_data}
        self.topic_to_repos = self._build_topic_mapping()
        
        print(f"✅ 数据加载完成：{len(self.repo_data)} 个仓库，{len(self.topic_to_repos)} 个标签")

    def _build_topic_mapping(self):
        """构建 标签 → 仓库列表 的映射"""
        topic_map = {}
        for repo in self.repo_data:
            for topic in repo["topics"]:
                if topic not in topic_map:
                    topic_map[topic] = []
                topic_map[topic].append(repo["full_name"])
        return topic_map

    def _build_full_graph(self):
        """构建全量图（严格限制规模）"""
        G = nx.Graph()
        max_edges = 1000
        edge_count = 0

        # 1. 添加节点（所有500个仓库，字段名统一+兜底）
        for repo in self.repo_data:
            G.add_node(
                repo["full_name"],
                # 统一用 activity_score，兜底为0
                activity=repo["activity_score"],
                star=repo["star_count"],
                lang=repo["language"]
            )

        # 2. 添加边（仅保留共享标签≥2的仓库）
        added_edges = set()
        for topic, repos in self.topic_to_repos.items():
            if len(repos) > 8:
                repos = repos[:8]
            for i in range(len(repos)):
                for j in range(i+1, len(repos)):
                    if edge_count >= max_edges:
                        break
                    r1, r2 = repos[i], repos[j]
                    edge_key = tuple(sorted([r1, r2]))
                    if edge_key not in added_edges:
                        t1 = set(self.repo_map[r1]["topics"])
                        t2 = set(self.repo_map[r2]["topics"])
                        shared = len(t1 & t2)
                        if shared >= 2:
                            G.add_edge(r1, r2, weight=shared)
                            added_edges.add(edge_key)
                            edge_count += 1
                if edge_count >= max_edges:
                    break

        print(f"✅ 全量图构建完成：{G.number_of_nodes()} 节点，{G.number_of_edges()} 边")
        return G

    def _build_4level_graph(self, start_repo):
        """构建4级分支图（限制总节点≤150）"""
        if start_repo not in self.repo_map:
            raise ValueError(f"仓库 {start_repo} 不存在！")

        G = nx.Graph()
        visited = set()
        current_level = {start_repo}
        levels = 4
        max_nodes = 150

        # 逐层扩展
        for level in range(levels + 1):
            if not current_level or len(visited) >= max_nodes:
                break
            
            next_level = set()
            for repo_name in current_level:
                if repo_name in visited:
                    continue
                visited.add(repo_name)
                
                # 获取仓库数据（兜底处理）
                repo = self.repo_map.get(repo_name, {
                    "activity_score": 0.0,
                    "star_count": 0,
                    "language": "Unknown",
                    "topics": []
                })

                # 添加当前节点（字段名统一+兜底）
                G.add_node(
                    repo_name,
                    activity=repo["activity_score"],
                    star=repo["star_count"],
                    lang=repo["language"],
                    level=level
                )

                # 找到下一级节点
                for topic in repo["topics"][:5]:
                    related_repos = self.topic_to_repos.get(topic, [])[:5]
                    for rr in related_repos:
                        if rr not in visited and len(visited) < max_nodes:
                            next_level.add(rr)
                            G.add_edge(repo_name, rr, weight=1)

            current_level = next_level

        print(f"✅ 4级分支图构建完成：{G.number_of_nodes()} 节点，{G.number_of_edges()} 边")
        return G

    def _plot_graph(self, G, title, is_4level=False):
        """核心绘制函数（添加完整异常处理）"""
        try:
            # 1. 计算布局
            if is_4level:
                pos = nx.fruchterman_reingold_layout(G, iterations=150, scale=25, seed=42, k=3)
            else:
                pos = nx.fruchterman_reingold_layout(G, iterations=100, scale=30, seed=42, k=4)

            # 2. 提取节点样式数据（完整兜底）
            node_sizes = []
            node_colors = []
            labels = {}

            for node in G.nodes:
                attrs = G.nodes[node]
                # 兜底：activity缺失则设为0
                activity = float(attrs.get("activity", 0.0))
                size = max(min(activity * 10, 1000), 200)
                node_sizes.append(size)
                
                # 兜底：lang缺失则设为Unknown
                lang = attrs.get("lang", "Unknown")
                color = LANGUAGE_COLORS.get(lang, "#808080")
                node_colors.append(color)
                
                # 标签处理
                star = int(attrs.get("star", 0))
                if is_4level or star > 150000:
                    labels[node] = node.split("/")[-1][:12]

            # 3. 提取边样式数据
            edge_weights = [G.edges[edge].get("weight", 1) for edge in G.edges]
            edge_widths = [max(w * 0.5, 0.2) for w in edge_weights]

            # 4. 创建画布
            fig, ax = plt.subplots(figsize=(25, 20) if is_4level else (30, 25))
            ax.set_facecolor("#f8f9fa")

            # 5. 绘制边
            nx.draw_networkx_edges(
                G, pos, ax=ax,
                width=edge_widths,
                edge_color="#d1d1d1",
                alpha=0.6
            )

            # 6. 绘制节点
            nx.draw_networkx_nodes(
                G, pos, ax=ax,
                node_size=node_sizes,
                node_color=node_colors,
                alpha=0.95,
                edgecolors="#2c3e50",
                linewidths=1.2
            )

            # 7. 绘制标签
            if labels:
                nx.draw_networkx_labels(
                    G, pos, ax=ax,
                    labels=labels,
                    font_size=11 if is_4level else 12,
                    font_weight="bold",
                    font_color="#2c3e50",
                    bbox=dict(
                        boxstyle="round,pad=0.3",
                        facecolor="white",
                        alpha=0.85,
                        edgecolor="#e0e0e0"
                    )
                )

            # 8. 美化配置
            ax.set_title(
                title,
                fontsize=26 if is_4level else 30,
                fontweight="bold",
                pad=40,
                color="#2c3e50"
            )
            ax.axis("off")

            # 9. 添加图例
            lang_legend = [
                plt.Line2D([0], [0], marker='o', color='w',
                           markerfacecolor=color, markersize=14,
                           label=lang, markeredgecolor="#2c3e50", markeredgewidth=1.2)
                for lang, color in LANGUAGE_COLORS.items() if lang != "Unknown"
            ]
            activity_legend = [
                plt.Line2D([0], [0], marker='o', color='w',
                           markerfacecolor="#888888", markersize=8,
                           label="活跃度低", markeredgecolor="#2c3e50", markeredgewidth=1.2),
                plt.Line2D([0], [0], marker='o', color='w',
                           markerfacecolor="#888888", markersize=18,
                           label="活跃度中", markeredgecolor="#2c3e50", markeredgewidth=1.2),
                plt.Line2D([0], [0], marker='o', color='w',
                           markerfacecolor="#888888", markersize=28,
                           label="活跃度高", markeredgecolor="#2c3e50", markeredgewidth=1.2)
            ]

            ax.legend(
                handles=lang_legend + activity_legend,
                loc="upper right",
                fontsize=12,
                title="图例",
                title_fontsize=14,
                frameon=True,
                facecolor="white",
                edgecolor="#e0e0e0",
                shadow=True
            )

            # 10. 保存图片
            safe_title = title.replace("/", "_").replace(" ", "_").replace("：", "_")
            save_path = os.path.join(OUTPUT_DIR, f"{safe_title}.png")
            plt.savefig(
                save_path,
                dpi=300,
                bbox_inches="tight",
                pad_inches=0.5
            )
            print(f"✅ 图片已保存：{save_path}")

            # 显示图片
            plt.show()
            plt.close()
            
        except Exception as e:
            print(f"❌ 绘制失败：{str(e)}")
            # 打印详细错误信息（便于调试）
            import traceback
            traceback.print_exc()
            plt.close()

    def plot_full_graph(self):
        """绘制全量图"""
        try:
            print("\n🔨 开始构建全量图...")
            G = self._build_full_graph()
            self._plot_graph(
                G,
                title="GitHub Star前500仓库标签关联图（节点大小=活跃度）",
                is_4level=False
            )
        except Exception as e:
            print(f"❌ 全量图绘制失败：{str(e)}")

    def plot_4level_graph(self, start_repo):
        """绘制4级分支图"""
        try:
            print(f"\n🔨 开始构建 {start_repo} 的4级分支图...")
            G = self._build_4level_graph(start_repo)
            self._plot_graph(
                G,
                title=f"GitHub仓库 {start_repo} 4级标签关联分支图",
                is_4level=True
            )
        except ValueError as e:
            print(f"❌ {e}")
        except Exception as e:
            print(f"❌ 绘制失败：{str(e)}")

def main():
    # 初始化可视化器
    try:
        visualizer = GitHubGraphVisualizer()
    except FileNotFoundError as e:
        print(f"❌ 错误：{e}")
        print("⚠️ 请先运行 optimize_cache.py 生成优化数据！")
        return

    # 1. 绘制全量图
    visualizer.plot_full_graph()

    # 2. 交互式绘制4级分支图
    print("\n===== 4级分支图生成 =====")
    print("📌 示例仓库：")
    sample_repos = list(visualizer.repo_map.keys())[:8]
    for i, repo in enumerate(sample_repos, 1):
        print(f"   {i}. {repo}")

    while True:
        repo_input = input("\n请输入仓库全名（输入q退出）：").strip()
        if repo_input.lower() == "q":
            print("👋 退出程序")
            break
        if not repo_input:
            print("⚠️ 请输入有效仓库名！")
            continue
        visualizer.plot_4level_graph(repo_input)

if __name__ == "__main__":
    main()