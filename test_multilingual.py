#!/usr/bin/env python3
"""
多語言 Prompt Template 測試腳本
測試所有 Agent 的多語言支援是否正常工作
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agents.prompt_registry import PromptRegistry
from datetime import datetime


def test_prompt_registry():
    """測試 PromptRegistry 的多語言支援"""
    print("=" * 70)
    print("測試 1: PromptRegistry 多語言支援")
    print("=" * 70)
    
    # 載入 prompts
    PromptRegistry.load()
    
    # 測試 crypto_agent system prompt
    print("\n[1.1] Crypto Agent System Prompt")
    print("-" * 50)
    
    for lang in ["zh-TW", "zh-CN", "en"]:
        prompt = PromptRegistry.get("crypto_agent", "system", lang)
        preview = prompt[:100].replace('\n', ' ')
        print(f"  {lang}: {preview}...")
        
        # 檢查是否包含時間變數
        if "{current_time_" in prompt or "當前時間" in prompt or "Current Time" in prompt:
            print(f"    ✓ 包含時間資訊")
        else:
            print(f"    ✗ 缺少時間資訊")
    
    # 測試渲染（帶時間）
    print("\n[1.2] Prompt Rendering with Time")
    print("-" * 50)
    
    for lang in ["zh-TW", "zh-CN", "en"]:
        try:
            prompt = PromptRegistry.render("crypto_agent", "system", lang, include_time=True)
            # 檢查是否包含實際時間
            now = datetime.now()
            if lang == "zh-TW":
                expected_time = now.strftime("%Y 年 %m 月 %d 日 %H:%M")
            elif lang == "zh-CN":
                expected_time = now.strftime("%Y 年 %m 月 %d 日 %H:%M")
            else:
                expected_time = now.strftime("%B %d, %Y %H:%M")
            
            if expected_time in prompt:
                print(f"  {lang}: ✓ 時間注入成功 ({expected_time})")
            else:
                print(f"  {lang}: ✗ 時間注入失敗")
                print(f"    預期包含：{expected_time}")
        except Exception as e:
            print(f"  {lang}: ✗ 渲染失敗 - {e}")
    
    print()


def test_all_templates():
    """測試所有 Prompt Templates"""
    print("=" * 70)
    print("測試 2: 所有 Prompt Templates 完整性")
    print("=" * 70)
    
    PromptRegistry.load()
    
    templates = {
        "crypto_agent": ["system", "analysis", "summarize"],
        "chat_agent": ["system", "response"],
        "tw_stock_agent": ["analysis"],
        "news_agent": ["summarize"],
        "tech_agent": ["analysis"],
    }
    
    languages = ["zh-TW", "zh-CN", "en"]
    
    for scope, keys in templates.items():
        print(f"\n[{scope}]")
        for key in keys:
            print(f"  {key}:")
            for lang in languages:
                try:
                    prompt = PromptRegistry.get(scope, key, lang)
                    if prompt:
                        # 檢查是否包含該語言的特徵
                        if lang == "zh-TW" and ("繁體" in prompt or "你是一個" in prompt or "你是 CryptoMind" in prompt):
                            print(f"    {lang}: ✓ OK")
                        elif lang == "zh-CN" and ("简体" in prompt or "你是一个" in prompt or "你是 CryptoMind" in prompt):
                            print(f"    {lang}: ✓ OK")
                        elif lang == "en" and ("English" in prompt or "You are" in prompt):
                            print(f"    {lang}: ✓ OK")
                        elif not prompt.strip():
                            print(f"    {lang}: ✗ 空模板")
                        else:
                            print(f"    {lang}: ✓ OK (未檢測語言特徵)")
                    else:
                        print(f"    {lang}: ✗ 無此模板")
                except Exception as e:
                    print(f"    {lang}: ✗ 錯誤 - {e}")
    
    print()


def test_time_variables():
    """測試時間變數注入"""
    print("=" * 70)
    print("測試 3: 時間變數注入")
    print("=" * 70)
    
    PromptRegistry.load()
    
    # 渲染帶時間的 prompt
    prompt = PromptRegistry.render("crypto_agent", "system", "zh-TW", include_time=True)
    
    expected_vars = [
        "current_time_tw",
        "current_date_tw",
        "timezone_tw",
    ]
    
    print("\n檢查時間變數注入:")
    now = datetime.now()
    
    # 繁體中文時間
    tw_time = now.strftime("%Y 年 %m 月 %d 日 %H:%M")
    if tw_time in prompt:
        print(f"  ✓ 繁體中文時間：{tw_time}")
    else:
        print(f"  ✗ 繁體中文時間缺失：預期 {tw_time}")
    
    # 時區
    if "台灣時間" in prompt or "UTC+8" in prompt:
        print(f"  ✓ 時區資訊存在")
    else:
        print(f"  ✗ 時區資訊缺失")
    
    print()


def test_agent_execution():
    """測試 Agent 執行（模擬）"""
    print("=" * 70)
    print("測試 4: Agent 執行模擬")
    print("=" * 70)
    
    from core.agents.models import SubTask
    
    # 模擬不同語言的任務
    test_cases = [
        {
            "name": "繁體中文任務",
            "task": SubTask(
                step=1,
                description="分析 BTC 價格",
                agent="chat",
                context={"language": "zh-TW", "history": ""}
            ),
            "expected_lang": "zh-TW"
        },
        {
            "name": "簡體中文任務",
            "task": SubTask(
                step=1,
                description="分析 BTC 价格",
                agent="chat",
                context={"language": "zh-CN", "history": ""}
            ),
            "expected_lang": "zh-CN"
        },
        {
            "name": "英文任務",
            "task": SubTask(
                step=1,
                description="Analyze BTC price",
                agent="chat",
                context={"language": "en", "history": ""}
            ),
            "expected_lang": "en"
        },
        {
            "name": "預設語言任務（未指定）",
            "task": SubTask(
                step=1,
                description="分析 BTC",
                agent="chat",
                context={}
            ),
            "expected_lang": "zh-TW"
        },
    ]
    
    print("\n檢查 Task Context 語言傳遞:")
    for tc in test_cases:
        task = tc["task"]
        lang = (task.context or {}).get("language", "zh-TW")
        expected = tc["expected_lang"]
        
        if lang == expected:
            print(f"  ✓ {tc['name']}: {lang}")
        else:
            print(f"  ✗ {tc['name']}: 預期 {expected}, 實際 {lang}")
    
    print()


def test_yaml_syntax():
    """測試 YAML 語法正確性"""
    print("=" * 70)
    print("測試 5: YAML 語法檢查")
    print("=" * 70)
    
    import yaml
    from pathlib import Path
    
    prompts_dir = Path(__file__).parent / "core" / "agents" / "prompts"
    
    yaml_files = list(prompts_dir.glob("*.yaml"))
    print(f"\n找到 {len(yaml_files)} 個 YAML 檔案:")
    
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            # 檢查結構
            if isinstance(data, dict):
                keys = list(data.keys())
                print(f"  ✓ {yaml_file.name}: {len(keys)} 個模板")
                
                # 檢查多語言結構
                for key, value in data.items():
                    if isinstance(value, dict):
                        langs = list(value.keys())
                        # 檢查是否為多語言（排除 description 等 metadata）
                        if "zh-TW" in langs or "zh-CN" in langs or "en" in langs:
                            print(f"      {key}: 多語言 ({', '.join(langs)})")
            else:
                print(f"  ⚠ {yaml_file.name}: 非字典結構")
                
        except yaml.YAMLError as e:
            print(f"  ✗ {yaml_file.name}: YAML 解析錯誤 - {e}")
        except Exception as e:
            print(f"  ✗ {yaml_file.name}: 錯誤 - {e}")
    
    print()


def main():
    """執行所有測試"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "多語言 Prompt Template 測試" + " " * 23 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    try:
        test_prompt_registry()
        test_all_templates()
        test_time_variables()
        test_agent_execution()
        test_yaml_syntax()
        
        print("=" * 70)
        print("測試完成！")
        print("=" * 70)
        print()
        
    except Exception as e:
        print(f"\n❌ 測試失敗：{e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
