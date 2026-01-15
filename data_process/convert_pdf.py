import subprocess
from pathlib import Path
import shutil
import time
import signal
from contextlib import contextmanager

class TimeoutException(Exception):
    pass

@contextmanager
def timeout(seconds):
    """超時上下文管理器"""
    def signal_handler(signum, frame):
        raise TimeoutException("操作超時")
    
    # 設置信號處理
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def check_libreoffice():
    """檢查 LibreOffice 是否已安裝"""
    if shutil.which("libreoffice"):
        return True
    print("❌ LibreOffice 未安裝")
    print("請執行: sudo apt-get install libreoffice")
    return False

def kill_libreoffice_processes():
    """強制終止所有 LibreOffice 進程"""
    try:
        subprocess.run(["pkill", "-9", "soffice"], stderr=subprocess.DEVNULL)
        time.sleep(1)
    except:
        pass

def convert_single_doc(doc_file, timeout_seconds=30):
    """
    轉換單個文檔，帶超時處理
    """
    try:
        print(f"處理: {doc_file.name} ... ", end="", flush=True)
        
        # 使用 Popen 以便可以終止進程
        process = subprocess.Popen(
            [
                "libreoffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(doc_file.parent),
                str(doc_file.absolute())
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待進程完成，帶超時
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # 超時則終止進程
            process.kill()
            process.wait()
            print(f"⏱️  超時 ({timeout_seconds}秒)")
            return False, "timeout"
        
        # 檢查 PDF 是否創建成功
        pdf_file = doc_file.with_suffix('.pdf')
        
        if pdf_file.exists() and pdf_file.stat().st_size > 0:
            doc_file.unlink()  # 刪除原文件
            print(f"✅")
            return True, None
        else:
            print(f"❌ 轉換失敗")
            if stderr:
                print(f"   錯誤訊息: {stderr[:150]}")
            return False, stderr
            
    except Exception as e:
        print(f"❌ 異常: {str(e)[:100]}")
        return False, str(e)

def convert_docs_to_pdf(root_directory, timeout_per_file=30, skip_on_timeout=True):
    """
    使用 LibreOffice 在 Ubuntu 上轉換 DOC 到 PDF
    
    參數:
    - timeout_per_file: 每個文件的超時時間（秒）
    - skip_on_timeout: 超時後是否跳過繼續處理
    """
    if not check_libreoffice():
        return
    
    root_path = Path(root_directory)
    
    # 找到所有 .doc 文件
    doc_files = list(root_path.rglob("*.doc"))
    print(f"找到 {len(doc_files)} 個 .doc 文件\n")
    
    if not doc_files:
        print("沒有找到 .doc 文件")
        return
    
    # 先清理可能存在的 LibreOffice 進程
    print("清理殘留的 LibreOffice 進程...")
    kill_libreoffice_processes()
    
    success = 0
    failed = 0
    timeout_count = 0
    
    start_time = time.time()
    
    for i, doc_file in enumerate(doc_files, 1):
        print(f"[{i}/{len(doc_files)}] ", end="")
        
        result, error = convert_single_doc(doc_file, timeout_per_file)
        
        if result:
            success += 1
        else:
            failed += 1
            if error == "timeout":
                timeout_count += 1
                # 超時後清理 LibreOffice 進程
                kill_libreoffice_processes()
                
                if not skip_on_timeout:
                    print("\n⚠️  遇到超時，是否繼續？(yes/no): ", end="")
                    if input().lower() != 'yes':
                        break
        
        # 每10個文件清理一次
        if i % 10 == 0:
            kill_libreoffice_processes()
    
    elapsed = time.time() - start_time
    
    print(f"\n" + "="*50)
    print(f"完成！")
    print(f"成功: {success}")
    print(f"失敗: {failed}")
    print(f"超時: {timeout_count}")
    print(f"總耗時: {elapsed:.1f} 秒")
    print(f"平均每個: {elapsed/len(doc_files):.1f} 秒")
    print("="*50)

def main():
    root_directory = "./medical/DataSet/DataSet"
    
    print("⚠️  這會刪除所有 .doc 文件！")
    confirm = input("確定繼續? (輸入 'yes'): ")
    
    if confirm.lower() == 'yes':
        print("\n配置選項:")
        print("1. 每個文件超時時間（預設 30 秒）")
        timeout_input = input("輸入超時秒數（直接按 Enter 使用預設）: ").strip()
        timeout_seconds = int(timeout_input) if timeout_input else 30
        
        convert_docs_to_pdf(root_directory, timeout_per_file=timeout_seconds)
    else:
        print("已取消")

if __name__ == "__main__":
    main()