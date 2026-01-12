#!/usr/bin/env python3
"""
Google Gemini API Key 測試工具
"""

import google.generativeai as genai
import sys

def test_gemini_key(api_key, test_prompt="你好，請簡短回答：今天天氣如何？"):
    """
    測試 Google Gemini API Key 是否有效
    
    Args:
        api_key (str): Google API Key
        test_prompt (str): 測試提示語句
    
    Returns:
        tuple: (success: bool, response: str or error_message: str)
    """
    try:
        # 配置 API Key
        genai.configure(api_key=api_key)
        
        # 測試模型列表
        models_to_try = ["gemini-3-flash-preview"]
        
        for model_name in models_to_try:
            try:
                print(f"正在測試模型: {model_name}...")
                
                # 創建模型實例
                model = genai.GenerativeModel(model_name)
                
                # 生成內容
                response = model.generate_content(
                    test_prompt,
                    generation_config={
                        "temperature": 0.5,
                        "max_output_tokens": 100,
                    }
                )
                
                # 檢查響應
                if response.text:
                    print(f"✅ 模型 {model_name} 測試成功！")
                    return True, response.text
                else:
                    print(f"⚠️  模型 {model_name} 返回空響應，嘗試下一個模型...")
                    continue
                    
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️  模型 {model_name} 測試失敗: {error_msg}")
                
                # 檢查是否是內容被阻止的錯誤
                if "finish_reason" in error_msg and "2" in error_msg:
                    print(f"   提示：內容可能被審核系統阻止，但 API 連接正常")
                    continue
                elif "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
                    print(f"   錯誤：API Key 無效")
                    return False, "API Key 無效，請檢查 Key 是否正確。"
                elif "quota" in error_msg.lower() or "exceeded your current quota" in error_msg.lower():
                    print(f"   錯誤：配額已滿，請檢查您的計費詳情和用量限制。")
                    return False, "配額已滿，請檢查您的計費詳情和用量限制。"
                elif "access not configured" in error_msg.lower():
                    print(f"   錯誤：API 服務未啟用，請確保已在 Google Cloud Console 中啟用 Generative Language API。")
                    return False, "API 服務未啟用，請確保已在 Google Cloud Console 中啟用 Generative Language API。"
                else:
                    continue  # 繼續嘗試下一個模型
        
        # 如果所有模型都失敗
        return False, "所有測試模型都無法使用，請檢查您的 API Key 和服務配置。"
        
    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
            return False, "API Key 無效，請檢查 Key 是否正確。"
        elif "quota" in error_msg.lower():
            return False, "配額已滿，請檢查您的計費詳情和用量限制。"
        else:
            return False, f"API 測試失敗: {error_msg}"

def main():
    print("=" * 60)
    print("Google Gemini API Key 測試工具")
    print("=" * 60)
    
    # 獲取用戶輸入的 API Key
    api_key = input("請輸入您的 Google Gemini API Key: ").strip()
    
    if not api_key:
        print("❌ API Key 為空，退出測試。")
        return
    
    if len(api_key) < 5:
        print("❌ API Key 過短，請檢查輸入。")
        return
    
    print("\n開始測試 API Key...")
    
    # 執行測試
    success, result = test_gemini_key(api_key)
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 測試成功！")
        print(f"響應內容: {result}")
    else:
        print("❌ 測試失敗！")
        print(f"錯誤信息: {result}")
    print("=" * 60)

if __name__ == "__main__":
    main()