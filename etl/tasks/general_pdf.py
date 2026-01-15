import sys
import os
from pathlib import Path

# Add Agent_System root to sys.path
current_file = Path(__file__).resolve()
agent_system_root = current_file.parent.parent.parent
if str(agent_system_root) not in sys.path:
    sys.path.insert(0, str(agent_system_root))

from etl.config import GPU_MAPPING, SOURCE_DIRS
from core.config import DB_CONNECTION_STRING

def run(pdf_batch_size=20):
    print("🚀 Starting General Medical PDF Ingestion Pipeline...")
    
    os.environ["CUDA_VISIBLE_DEVICES"] = GPU_MAPPING["general"]
    
    try:
        from data_process.ingest_general_medical import UnifiedVectorDBLoader, OCR_AVAILABLE
        
        enable_ocr = True
        if not OCR_AVAILABLE:
            print("⚠️ OCR not available, proceeding without OCR.")
            enable_ocr = False
            
        # Initialize Loader
        loader = UnifiedVectorDBLoader(
            db_connection_string=DB_CONNECTION_STRING,
            pdf_base_path=SOURCE_DIRS["general_pdf"],
            jsonl_folder_path=SOURCE_DIRS["jsonl"],
            enable_ocr=enable_ocr,
            force_ocr_all=False
        )
        
        # Run PDF Load
        print(f"📂 Processing PDFs from {SOURCE_DIRS['general_pdf']}")
        loader.load_pdf_only(batch_size=pdf_batch_size)
        
        print("✅ General PDF Pipeline Completed.")
        
    except ImportError as e:
        print(f"❌ Error importing module: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
