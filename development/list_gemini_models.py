"""
列出可用的 Google Gemini 模型
"""
import os
from dotenv import load_dotenv

load_dotenv()

try:
    import google.generativeai as genai

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ 未找到 GOOGLE_API_KEY 環境變量")
        exit(1)

    genai.configure(api_key=api_key)

    print("=" * 70)
    print("可用的 Google Gemini 模型")
    print("=" * 70)

    models = genai.list_models()
    gemini_models = []

    for model in models:
        # 只顯示支持 generateContent 的模型
        if 'generateContent' in model.supported_generation_methods:
            gemini_models.append(model)
            print(f"\n✅ {model.name}")
            print(f"   顯示名稱: {model.display_name}")
            print(f"   描述: {model.description}")
            print(f"   支持的方法: {', '.join(model.supported_generation_methods)}")

    print("\n" + "=" * 70)
    print("推薦配置（複製到 config.py）:")
    print("=" * 70)

    if gemini_models:
        # 找到最常用的模型
        recommended = None
        for model in gemini_models:
            model_name = model.name.replace("models/", "")
            if "gemini-1.5-flash" in model_name.lower():
                recommended = model_name
                break
            elif "gemini-1.5-pro" in model_name.lower():
                recommended = model_name
            elif "gemini-pro" in model_name.lower() and not recommended:
                recommended = model_name

        if recommended:
            print(f'\n推薦模型: "{recommended}"')
            print(f'\n配置示例:')
            print(f'{{"provider": "google_gemini", "model": "{recommended}"}}')
        else:
            print(f'\n使用第一個可用模型:')
            model_name = gemini_models[0].name.replace("models/", "")
            print(f'{{"provider": "google_gemini", "model": "{model_name}"}}')

        print(f'\n所有可用模型名稱:')
        for model in gemini_models:
            model_name = model.name.replace("models/", "")
            print(f'  - "{model_name}"')

    else:
        print("\n⚠️  沒有找到支持 generateContent 的模型")
        print("   請檢查 API 密鑰權限")

except ImportError:
    print("❌ Google Generative AI SDK 未安裝")
    print("   運行: pip install google-generativeai")
except Exception as e:
    print(f"❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
