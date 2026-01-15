import argparse
from etl.tasks import dialysis_pdf, general_pdf, health_images, jsonl_qa

def main():
    parser = argparse.ArgumentParser(description="Unified ETL Pipeline Runner")
    parser.add_argument("task", choices=["dialysis", "general", "images", "jsonl", "all"], 
                        help="""The ETL task to run:
                        - general: Public Health PDF Text + Infectious Disease PDF Text
                        - dialysis: Dialysis Education (Text + Tables)
                        - jsonl: Infectious Disease QA
                        - images: Public Health + Infectious Disease Images
                        - all: Run all pipelines sequentially
                        """)
    parser.add_argument("--batch-size", type=int, default=None, 
                        help="Batch size for processing (where applicable)")

    args = parser.parse_args()
    
    print(f"🔧 ETL Runner: Task '{args.task}' selected.")

    if args.task == "dialysis":
        dialysis_pdf.run()
    elif args.task == "general":
        batch = args.batch_size if args.batch_size else 20
        general_pdf.run(pdf_batch_size=batch)
    elif args.task == "images":
        health_images.run()
    elif args.task == "jsonl":
        batch = args.batch_size if args.batch_size else 50
        jsonl_qa.run(batch_size=batch)
    elif args.task == "all":
        print("⚠️ Running ALL pipelines sequentially...")
        # Order matters for resource usage, though they are sequential.
        # JSONL is lightest.
        jsonl_qa.run()
        general_pdf.run()
        dialysis_pdf.run()
        health_images.run()
        
if __name__ == "__main__":
    main()
