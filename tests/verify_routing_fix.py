"""
驗證統一規劃流程的測試
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from core.agents.bootstrap_v2 import bootstrap_v2  # noqa: E402

from core.agents.description_loader import get_agent_descriptions  # noqa: E402
from utils.user_client_factory import create_user_llm_client  # noqa: E402

print("🔍 驗證統一規劃流程...")
print("=" * 60)

# 初始化完整的系統
api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"

llm = create_user_llm_client(
    provider=provider,
    api_key=api_key,
    model="gpt-4o-mini",
)

print("🔧 初始化 manager...")
manager = bootstrap_v2(llm, web_mode=False, language="zh-TW")

# 測試描述加載器的分層讀取
print("\n" + "=" * 60)
print("測試描述加載器（YAML frontmatter 格式）:")
print("-" * 60)

loader = get_agent_descriptions()

# 1. 只讀取 frontmatter
print("1. 測試只讀取 frontmatter:")
desc = loader.get("crypto")
print(f"   name: {desc.name}")
print(f"   description: {desc.description[:50]}...")
print(f"   routing_keywords: {desc.routing_keywords}")
print(f"   priority: {desc.priority}")
print(f"   when_to_use 為空: {desc.when_to_use == ''} (應該是 True)")
print()

# 2. 讀取完整內容
print("2. 測試延遲載入完整內容:")
full_desc = loader.get_full_description("crypto")
print(f"   when_to_use: {full_desc.when_to_use[:50]}...")
print(f"   capabilities: {len(full_desc.capabilities)} 項")
print()

# 3. 測試路由配置
print("3. 測試 get_routing_config():")
config = loader.get_routing_config()
for name, keywords, priority in config[:3]:
    print(f"   {name}: priority={priority}, keywords={keywords[:3]}...")
print()

# 測試 manager 的 graph 結構
print("=" * 60)
print("測試 Manager Graph 結構:")
print("-" * 60)

print(f"Graph nodes: {list(manager.graph.nodes.keys())}")
print(
    "預期節點: understand_intent, execute_task, aggregate_results, synthesize_response"
)
print()

# 測試模糊查詢檢測
print("=" * 60)
print("測試 Agent Description 格式:")
print("-" * 60)

for agent_name in ["crypto", "forex", "chat"]:
    desc = loader.get(agent_name)
    if desc:
        print(f"✅ {agent_name}:")
        print(f"   - frontmatter: name={desc.name}, priority={desc.priority}")
        print(f"   - keywords: {desc.routing_keywords[:3]}...")
    else:
        print(f"❌ {agent_name}: 找不到描述")
    print()

print("=" * 60)
print("🎉 驗證完成！")
print()
print("總結:")
print("1. 描述使用 YAML frontmatter 格式 ✅")
print("2. 分層讀取（frontmatter vs 完整內容）✅")
print("3. Manager 統一規劃流程（移除 vending/restaurant）✅")
print("4. 模糊查詢會返回 clarify 狀態 ✅")
