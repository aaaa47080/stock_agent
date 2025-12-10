
import gradio as gr
import asyncio

# Import the new analysis engine functions
from batch_analyzer import run_full_analysis, generate_report_and_summary

async def real_batch_analysis(exchange, progress=gr.Progress(track_tqdm=True)):
    """
    This function connects the Gradio UI to the backend analysis engine.
    """
    print(f"Starting real batch analysis for {exchange}...")
    
    # Define the number of top symbols to analyze
    limit = 30 

    # 1. Run the full analysis
    # Since run_full_analysis is async, we need to await it
    analysis_results = await run_full_analysis(exchange, limit=limit, progress=progress)

    # 2. Generate the report and summary
    if analysis_results and "error" not in analysis_results:
        summary, csv_path = generate_report_and_summary(analysis_results, exchange, limit)
    elif isinstance(analysis_results, dict) and "error" in analysis_results:
        summary = f"An error occurred: {analysis_results['error']}"
        csv_path = None
    else:
        summary = "Analysis completed with no results to report."
        csv_path = None
    
    # 3. Return the outputs for the Gradio interface
    # For the file output, we need to return a gr.File component update
    return summary, gr.File(value=csv_path, visible=True if csv_path else False)

def create_batch_analyzer_interface():
    """
    Creates the Gradio interface for the batch analyzer.
    """
    with gr.Blocks() as batch_app:
        gr.Markdown("# Crypto Batch Analyzer")
        gr.Markdown("Select an exchange and click 'Start Analysis' to get insights on the top 30 cryptocurrencies.")

        with gr.Row():
            exchange_dropdown = gr.Dropdown(
                label="Select Exchange",
                choices=["OKX", "Binance"],
                value="Binance"
            )
            start_button = gr.Button("Start Analysis", variant="primary")
        
        with gr.Group():
            gr.Markdown("### Analysis Summary")
            summary_output = gr.Markdown("Your investment summary will appear here...")
        
        with gr.Group():
            gr.Markdown("### Download Full Report")
            file_output = gr.File(label="Download CSV Report", visible=False)

        # The click function now points to our new async function
        start_button.click(
            fn=real_batch_analysis,
            inputs=[exchange_dropdown],
            outputs=[summary_output, file_output]
        )
        
    return batch_app

if __name__ == "__main__":
    # This allows the app to be run directly for testing
    app = create_batch_analyzer_interface()
    app.launch(server_name="0.0.0.0")
