
import asyncio
import operator
from typing import Annotated, TypedDict, Union
from langgraph.graph import StateGraph, END
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import MemorySaver

class State(TypedDict):
    value: str
    history: Annotated[list[str], operator.add]

async def node_a(state: State):
    print(f"--- Node A: value={state.get('value')} ---")
    return {"history": ["A"]}

async def node_b(state: State):
    print(f"--- Node B: value={state.get('value')} ---")
    # Interrupt here
    ans = interrupt("pause")
    print(f"--- Node B Resumed: ans={ans} ---")
    return {"history": ["B"]}

async def node_c(state: State):
    print(f"--- Node C ---")
    return {"history": ["C"]}

def build_graph():
    workflow = StateGraph(State)
    workflow.add_node("node_a", node_a)
    workflow.add_node("node_b", node_b)
    workflow.add_node("node_c", node_c)
    
    workflow.set_entry_point("node_a")
    workflow.add_edge("node_a", "node_b")
    workflow.add_edge("node_b", "node_c")
    workflow.add_edge("node_c", END)
    
    return workflow.compile(checkpointer=MemorySaver())

async def main():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_thread"}}
    
    print("\n=== Run 1: Start and Pause at B ===")
    # Initial run
    async for event in graph.astream({"value": "run1", "history": []}, config):
        pass
    
    state = graph.get_state(config)
    print(f"State after Run 1: next={state.next}")
    
    print("\n=== Run 2: New Request (Force Restart to A) ===")
    # Simulate new user request with Command(goto="node_a")
    # This matches what we did in analysis.py
    
    command = Command(
        goto="node_a",
        update={
            "value": "run2_new_value",
            "history": [] # Try to clear history? TypedDict might not support clearing list via update if it uses add
            # But let's see if 'value' updates and we go to A.
        }
    )
    
    try:
        async for event in graph.astream(command, config):
            kind = event.get("type", "unknown")
            if "node_a" in event:
                print(f"Event from node_a: {event['node_a']}")
            if "node_b" in event:
                print(f"Event from node_b: {event['node_b']}")
                
        state = graph.get_state(config)
        print(f"State after Run 2: history={state.values['history']}")
        
        # Verify we went A -> B (and paused again)
        # And value should be run2_new_value
        if state.values["value"] == "run2_new_value":
            print("SUCCESS: State updated correctly.")
        else:
            print(f"FAILURE: Value mismatch. Got {state.values['value']}")
            
        # History should contain A (from run 2)
        # Note: since history uses operator.add, it might append?
        # If we passed "history": [], it appends empty list?
        # But we want to ensure 'node_a' executed.
        if "A" in state.values["history"][-2:]: # Recent history
            print("SUCCESS: Node A executed.")
        else:
            print("FAILURE: Node A did not execute.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
