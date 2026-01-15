import sys
import os
from pathlib import Path

# Add Agent_System root to sys.path
current_file = Path(__file__).resolve()
agent_system_root = current_file.parent.parent.parent
if str(agent_system_root) not in sys.path:
    sys.path.insert(0, str(agent_system_root))

from etl.config import GPU_MAPPING

def run():
    print("🚀 Starting Dialysis PDF Ingestion Pipeline...")
    
    # Ensure GPU setting
    os.environ["CUDA_VISIBLE_DEVICES"] = GPU_MAPPING["dialysis"]
    
    try:
        # Import the module
        from data_process import ingest_dialysis_pdf
        
        # Run main
        if hasattr(ingest_dialysis_pdf, 'main'):
            ingest_dialysis_pdf.main()
        else:
            print("❌ Error: 'main' function not found in ingest_dialysis_pdf")
            sys.exit(1)
            
        print("✅ Dialysis Pipeline Completed.")
        
    except ImportError as e:
        print(f"❌ Error importing module: {e}")
        print("Make sure you are running from Agent_System directory.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
