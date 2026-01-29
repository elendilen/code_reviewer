import sys
import os

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.performance.perf_workflow import create_performance_subgraph


def generate_graph_visualization() -> None:
    print("Generating performance subgraph visualization...")
    app = create_performance_subgraph()

    try:
        graph = app.get_graph()
        png_data = graph.draw_mermaid_png()

        output_file = "performance_workflow_graph.png"
        with open(output_file, "wb") as f:
            f.write(png_data)

        print(f"Graph visualization saved to {output_file}")

    except Exception as e:
        print(f"Error generating PNG: {e}")
        print("Attempting to print Mermaid syntax instead...")
        try:
            print("\nMermaid Syntax:")
            print(app.get_graph().draw_mermaid())
        except Exception as e2:
            print(f"Could not generate mermaid syntax: {e2}")


if __name__ == "__main__":
    generate_graph_visualization()
