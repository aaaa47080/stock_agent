import sys
import os
import asyncio
from pathlib import Path

# Add Agent_System root to sys.path
current_file = Path(__file__).resolve()
agent_system_root = current_file.parent.parent.parent
if str(agent_system_root) not in sys.path:
    sys.path.insert(0, str(agent_system_root))

from etl.config import GPU_MAPPING

def run():
    print("🚀 Starting Health Image Ingestion Pipeline (Strict Mode)...")
    
    os.environ["CUDA_VISIBLE_DEVICES"] = GPU_MAPPING["images"]
    
    try:
        from data_process import ingest_health_images
        
        if hasattr(ingest_health_images, 'main'):
            # The main function in the script is async but the script wraps it in asyncio.run inside if __name__ == "__main__"
            # However, if we import it, we can call the async main directly if it's exposed, 
            # OR we need to see if main is the async function itself.
            # Looking at file content earlier: "async def main(): ... if __name__ ... asyncio.run(main())"
            # So ingest_health_images.main is an async function (coroutine function).
            
            asyncio.run(ingest_health_images.main())
        else:
            print("❌ Error: 'main' function not found in ingest_health_images")
            sys.exit(1)

        print("✅ Image Pipeline Completed.")
        
    except ImportError as e:
        print(f"❌ Error importing module: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
