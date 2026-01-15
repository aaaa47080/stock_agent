import pandas as pd
from pathlib import Path
import json
import re

class ExcelToJsonlConverter:
    def __init__(self, source_folder, output_folder):
        self.source_folder = Path(source_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
    def clean_text(self, text):
        """清理文字內容"""
        if pd.isna(text) or text is None:
            return ""
        text = str(text).strip()
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def find_excel_files(self):
        """搜尋所有xlsx檔案"""
        return [f for f in self.source_folder.rglob('*.xlsx') if not f.name.startswith('~$')]
    
    def extract_qa_from_excel(self, file_path):
        """從Excel提取問答對"""
        qa_pairs = []
        
        try:
            excel_file = pd.ExcelFile(file_path, engine='openpyxl')
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
                df.columns = [str(col).strip() for col in df.columns]
                
                # 識別欄位
                question_col = answer_col = title_col = keyword_col = reference_col = None
                
                for col in df.columns:
                    col_lower = col.lower()
                    if '問題' in col:
                        question_col = col
                    elif '回答' in col or '答案' in col:
                        answer_col = col
                    elif '標題' in col or '主題' in col:
                        title_col = col
                    elif '關鍵字' in col:
                        keyword_col = col
                    elif '參考資料' in col:
                        reference_col = col
                
                print(f"   工作表 '{sheet_name}': 問題欄={question_col}, 答案欄={answer_col}")
                
                # 處理每一行
                for idx, row in df.iterrows():
                    question = self.clean_text(row.get(question_col, ''))
                    answer = self.clean_text(row.get(answer_col, ''))
                    
                    if question and answer:  # 只保留有問題和答案的資料
                        qa_pairs.append({
                            'source_file': file_path.name,
                            'sheet_name': sheet_name,
                            'row_index': idx + 2,
                            'title': self.clean_text(row.get(title_col, '')),
                            'question': question,
                            'answer': answer,
                            'keywords': self.clean_text(row.get(keyword_col, '')),
                            'reference': self.clean_text(row.get(reference_col, ''))
                        })
                        
        except Exception as e:
            print(f"   讀取檔案失敗: {str(e)}")
            
        return qa_pairs
    
    def create_jsonl_file(self, qa_pairs, source_filename):
        """創建JSONL檔案"""
        # 修正檔案名稱生成邏輯
        safe_filename = source_filename.replace('.xlsx', '')
        safe_filename = re.sub(r'[^\w\s\-\u4e00-\u9fff]', '_', safe_filename)  # 保留中文字符
        safe_filename = re.sub(r'_+', '_', safe_filename)  # 合併多個底線
        safe_filename = safe_filename.strip('_')  # 移除開頭結尾的底線
        
        if not safe_filename:  # 如果檔名為空，使用預設名稱
            safe_filename = f"excel_file_{hash(source_filename) % 10000}"
            
        output_path = self.output_folder / f"{safe_filename}.jsonl"
        
        print(f"   創建JSONL: {output_path.name} ({len(qa_pairs)} 個問答對)")
        
        success_count = 0
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, qa in enumerate(qa_pairs):
                    try:
                        # 確保所有值都是字符串
                        safe_qa = {k: str(v) if v is not None else "" for k, v in qa.items()}
                        
                        json_obj = {
                            'id': f"{safe_qa['source_file']}_{safe_qa['sheet_name']}_{safe_qa['row_index']}",
                            'text': f"問題: {safe_qa['question']}\n答案: {safe_qa['answer']}",
                            'metadata': {
                                'source_file': safe_qa['source_file'],
                                'sheet_name': safe_qa['sheet_name'],
                                'title': safe_qa['title'],
                                'keywords': safe_qa['keywords'],
                                'reference': safe_qa['reference']
                            }
                        }
                        
                        # 寫入JSONL
                        f.write(json.dumps(json_obj, ensure_ascii=False) + '\n')
                        f.flush()
                        success_count += 1
                        
                        if (i + 1) % 10 == 0:
                            print(f"      已處理 {i + 1}/{len(qa_pairs)}")
                            
                    except Exception as e:
                        print(f"      第 {i+1} 個問答對失敗: {str(e)}")
                        
        except Exception as e:
            print(f"   檔案寫入失敗: {str(e)}")
            return False
            
        print(f"   ✅ 成功寫入 {success_count} 個問答對")
        return success_count > 0
    
    def validate_jsonl_file(self, jsonl_path):
        """驗證JSONL檔案"""
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            valid_count = 0
            for i, line in enumerate(lines, 1):
                try:
                    json.loads(line.strip())
                    valid_count += 1
                except:
                    print(f"   第 {i} 行JSON格式錯誤")
            
            print(f"   驗證結果: {valid_count}/{len(lines)} 行有效")
            return valid_count == len(lines)
            
        except Exception as e:
            print(f"   驗證失敗: {str(e)}")
            return False
    
    def convert_all(self):
        """轉換所有Excel檔案為JSONL"""
        print(f"🔄 開始轉換Excel為JSONL")
        print(f"📂 來源: {self.source_folder}")
        print(f"📂 輸出: {self.output_folder}")
        print("-" * 50)
        
        excel_files = self.find_excel_files()
        print(f"📁 找到 {len(excel_files)} 個Excel檔案")
        
        total_qa = 0
        success_files = 0
        
        for i, file_path in enumerate(excel_files, 1):
            print(f"\n[{i}/{len(excel_files)}] {file_path.name}")
            
            try:
                qa_pairs = self.extract_qa_from_excel(file_path)
                
                if qa_pairs:
                    print(f"   提取到 {len(qa_pairs)} 個問答對")
                    
                    if self.create_jsonl_file(qa_pairs, file_path.name):
                        # 驗證生成的檔案 - 修正檔案名稱生成邏輯
                        safe_filename = file_path.name.replace('.xlsx', '')
                        safe_filename = re.sub(r'[^\w\s\-\u4e00-\u9fff]', '_', safe_filename)
                        safe_filename = re.sub(r'_+', '_', safe_filename).strip('_')
                        if not safe_filename:
                            safe_filename = f"excel_file_{hash(file_path.name) % 10000}"
                        
                        jsonl_path = self.output_folder / f"{safe_filename}.jsonl"
                        self.validate_jsonl_file(jsonl_path)
                        
                        total_qa += len(qa_pairs)
                        success_files += 1
                else:
                    print("   ⚠️  沒有找到問答對")
                    
            except Exception as e:
                print(f"   ❌ 轉換失敗: {str(e)}")
        
        print(f"\n📊 完成! 成功轉換 {success_files} 個檔案，總計 {total_qa} 個問答對")

def main():
    # 設定路徑
    source_folder = r"/home/danny/AI-agent/DataSet"
    output_folder = r"/home/danny/AI-agent/RAG_JSONL"
    
    if not Path(source_folder).exists():
        print(f"❌ 來源路徑不存在: {source_folder}")
        return
    
    converter = ExcelToJsonlConverter(source_folder, output_folder)
    converter.convert_all()

if __name__ == "__main__":
    main()