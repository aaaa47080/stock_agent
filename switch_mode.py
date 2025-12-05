#!/usr/bin/env python3
"""
模式切換工具
快速切換單一模型、多模型、委員會模式
"""

import sys
from pathlib import Path

# 預設配置模板
TEMPLATES = {
    "single": """# 單一模型模式
ENABLE_MULTI_MODEL_DEBATE = False
ENABLE_COMMITTEE_MODE = False

# 單一模型（僅用於測試）
BULL_MODEL = "openai:gpt-4o"
BEAR_MODEL = "openai:gpt-4o"
TRADER_MODEL = "openai:gpt-4o"
SYNTHESIS_MODEL = "openai:gpt-4o"

BULL_COMMITTEE_MODELS = []
BEAR_COMMITTEE_MODELS = []
""",

    "multi": """# 多模型辯論模式
ENABLE_MULTI_MODEL_DEBATE = True
ENABLE_COMMITTEE_MODE = False

# 多頭研究員
BULL_MODEL = "openai:gpt-4o"

# 空頭研究員
BEAR_MODEL = "openai:o4-mini"

# 交易員
TRADER_MODEL = "openai:o4-mini"

# 綜合模型（委員會模式用）
SYNTHESIS_MODEL = "openai:gpt-4o"

BULL_COMMITTEE_MODELS = []
BEAR_COMMITTEE_MODELS = []
""",

    "committee_premium": """# 委員會模式 - 頂級配置
ENABLE_MULTI_MODEL_DEBATE = True
ENABLE_COMMITTEE_MODE = True

# 多頭委員會（三大商業模型）
BULL_COMMITTEE_MODELS = [
    "openai:gpt-4o",
    "openrouter:anthropic/claude-3.5-sonnet",
    "openrouter:google/gemini-pro-1.5",
]

# 空頭委員會
BEAR_COMMITTEE_MODELS = [
    "openai:o4-mini",
    "openrouter:anthropic/claude-3-opus",
    "openrouter:google/gemini-flash-1.5",
]

# 綜合模型
SYNTHESIS_MODEL = "openai:gpt-4o"

# 單一模型配置（委員會模式下不使用）
BULL_MODEL = "openai:gpt-4o"
BEAR_MODEL = "openai:o4-mini"
TRADER_MODEL = "openai:o4-mini"
""",

    "committee_balanced": """# 委員會模式 - 平衡配置
ENABLE_MULTI_MODEL_DEBATE = True
ENABLE_COMMITTEE_MODE = True

# 多頭委員會（平衡成本與質量）
BULL_COMMITTEE_MODELS = [
    "openai:gpt-4o-mini",
    "openrouter:anthropic/claude-3-haiku",
    "openrouter:qwen/qwen-2.5-72b-instruct",
]

# 空頭委員會
BEAR_COMMITTEE_MODELS = [
    "openai:gpt-4o-mini",
    "openrouter:meta-llama/llama-3.1-70b-instruct",
    "openrouter:deepseek/deepseek-chat",
]

# 綜合模型
SYNTHESIS_MODEL = "openai:gpt-4o-mini"

# 單一模型配置（委員會模式下不使用）
BULL_MODEL = "openai:gpt-4o"
BEAR_MODEL = "openai:o4-mini"
TRADER_MODEL = "openai:o4-mini"
""",

    "committee_opensource": """# 委員會模式 - 全開源配置
ENABLE_MULTI_MODEL_DEBATE = True
ENABLE_COMMITTEE_MODE = True

# 多頭委員會（全開源模型）
BULL_COMMITTEE_MODELS = [
    "openrouter:meta-llama/llama-3.1-70b-instruct",
    "openrouter:qwen/qwen-2.5-72b-instruct",
    "openrouter:deepseek/deepseek-chat",
]

# 空頭委員會
BEAR_COMMITTEE_MODELS = [
    "openrouter:meta-llama/llama-3.1-70b-instruct",
    "openrouter:qwen/qwen-2.5-72b-instruct",
    "openrouter:deepseek/deepseek-chat",
]

# 綜合模型
SYNTHESIS_MODEL = "openrouter:meta-llama/llama-3.1-70b-instruct"

# 單一模型配置（委員會模式下不使用）
BULL_MODEL = "openai:gpt-4o"
BEAR_MODEL = "openai:o4-mini"
TRADER_MODEL = "openai:o4-mini"
"""
}

CONFIG_HEADER = '''"""
簡化的多模型配置
使用簡潔的 "provider:model" 格式
"""

# ============================================================================
# 基礎配置
# ============================================================================

'''

def show_menu():
    """顯示選單"""
    print("\n" + "="*70)
    print("🔧 模式切換工具")
    print("="*70)
    print("\n請選擇配置模式:\n")
    print("  1. 單一模型模式 (最經濟，速度最快)")
    print("  2. 多模型辯論模式 (推薦日常使用)")
    print("  3. 委員會模式 - 頂級配置 (質量最高，成本較高)")
    print("  4. 委員會模式 - 平衡配置 (平衡成本與質量)")
    print("  5. 委員會模式 - 全開源配置 (最經濟的委員會)")
    print("  6. 查看當前配置")
    print("  0. 退出")
    print("\n" + "="*70)

def get_template_key(choice):
    """根據選擇獲取模板鍵"""
    mapping = {
        "1": "single",
        "2": "multi",
        "3": "committee_premium",
        "4": "committee_balanced",
        "5": "committee_opensource",
    }
    return mapping.get(choice)

def write_config(template_key):
    """寫入配置文件"""
    config_file = Path("config_simple.py")

    if config_file.exists():
        # 備份現有配置
        backup_file = Path("config_simple.py.backup")
        backup_file.write_text(config_file.read_text())
        print(f"\n📦 已備份當前配置到: {backup_file}")

    # 寫入新配置
    content = CONFIG_HEADER + TEMPLATES[template_key]
    config_file.write_text(content)
    print(f"✅ 配置已更新到: {template_key}")

    # 顯示配置摘要
    print("\n正在生成配置摘要...")
    try:
        from model_parser import print_config_summary
        print_config_summary()
    except Exception as e:
        print(f"⚠️ 無法顯示配置摘要: {e}")

def show_current_config():
    """顯示當前配置"""
    try:
        from model_parser import print_config_summary
        print_config_summary()
    except Exception as e:
        print(f"\n❌ 無法讀取當前配置: {e}")
        print("請確保 config_simple.py 存在且格式正確。")

def main():
    """主程序"""
    while True:
        show_menu()
        choice = input("\n請輸入選項 (0-6): ").strip()

        if choice == "0":
            print("\n👋 再見！")
            break

        elif choice == "6":
            show_current_config()
            input("\n按 Enter 繼續...")

        elif choice in ["1", "2", "3", "4", "5"]:
            template_key = get_template_key(choice)

            # 確認
            mode_names = {
                "1": "單一模型模式",
                "2": "多模型辯論模式",
                "3": "委員會模式 - 頂級配置",
                "4": "委員會模式 - 平衡配置",
                "5": "委員會模式 - 全開源配置",
            }

            print(f"\n確定要切換到 [{mode_names[choice]}] 嗎?")
            confirm = input("輸入 'y' 確認，其他鍵取消: ").strip().lower()

            if confirm == 'y':
                write_config(template_key)
                input("\n按 Enter 繼續...")
            else:
                print("\n❌ 已取消")
                input("\n按 Enter 繼續...")

        else:
            print("\n❌ 無效的選項，請重新選擇")
            input("\n按 Enter 繼續...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序已中斷，再見！")
        sys.exit(0)
