import sys
import os
from pathlib import Path

# Add Agent_System root to sys.path to allow direct execution and module imports
# This ensures 'etl' and 'core' packages can be found
current_file = Path(__file__).resolve()
agent_system_root = current_file.parent.parent.parent
if str(agent_system_root) not in sys.path:
    sys.path.insert(0, str(agent_system_root))

from etl.config import GPU_MAPPING, SOURCE_DIRS
from core.config import DB_CONNECTION_STRING

def run(batch_size=50):
    print("🚀 Starting JSONL QA Ingestion Pipeline...")
    
    os.environ["CUDA_VISIBLE_DEVICES"] = GPU_MAPPING["jsonl"]
    
    try:
        from data_process.ingest_general_medical import UnifiedVectorDBLoader
        
        # Initialize Loader
        loader = UnifiedVectorDBLoader(
            db_connection_string=DB_CONNECTION_STRING,
            pdf_base_path=SOURCE_DIRS["general_pdf"], # Not used but required init arg
            jsonl_folder_path=SOURCE_DIRS["jsonl"],
            enable_ocr=False
        )
        
        # Run JSONL Load
        print(f"📂 Processing JSONL from {SOURCE_DIRS['jsonl']}")
        loader.load_jsonl_only(batch_size=batch_size)
        
        print("✅ JSONL Pipeline Completed.")
        
    except ImportError as e:
        print(f"❌ Error importing module: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
