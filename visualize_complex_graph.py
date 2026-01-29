import sys
import os

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.graph.workflow import create_workflow

def generate_graph_visualization():
    print("Generating complex workflow graph...")
    app = create_workflow()
    
    try:
        # Get the graph object
        graph = app.get_graph()
        
        # Draw mermaid png
        png_data = graph.draw_mermaid_png()
        
        output_file = "complex_workflow_graph.png"
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
