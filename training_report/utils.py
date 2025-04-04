import pandas as pd
import os
from datetime import datetime


def convert_weight(weight):
    """
    Convert weight to a string with units.
    """
    if weight > 1000:
        return f"{weight / 1000:.2f} kg"
    else:
        return f"{weight:.2f} g"
    

def export_to_txt(data, filename, mode):
    """
    Export data to a TXT file.

    Args:
        data (dict): The data to be exported. Should include keys like 'hour', 'prompt', 'response', and 'tokens'.
        filename (str): The name of the TXT file to be created.
        mode (int): The mode of export. 
            - 1: Export to "image_without_context" directory.
            - 2: Export to "image_with_context" directory.

    Returns:
        str: The full file path of the created TXT file.

    """

    # Define the base directory for output
    base_dir = os.path.join("training_report", "static", "training_report", "output")

    # Define the output directory based on the mode
    if mode == 1:
        output_dir = os.path.join(base_dir, "image_without_context")
    elif mode == 2:
        output_dir = os.path.join(base_dir, "image_with_context")
    else:
        raise ValueError("Invalid mode. Use 1 for images or 2 for images with context.")

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Create the full path for the TXT file
    file_path = os.path.join(output_dir, filename)

    # Write the data to the TXT file
    with open(file_path, "a", encoding="utf-8") as txt_file:
        txt_file.write("\n")
        txt_file.write(f"Hour: {data.get('hour', 'N/A')}\n")
        txt_file.write(f"Prompt: {data.get('prompt', 'N/A')}\n")
        txt_file.write(f"Response: {data.get('response', 'N/A')}\n")
        txt_file.write(f"Tokens Used: {data.get('tokens', 'N/A')}\n")
        txt_file.write("-" * 50 + "\n")  # Add a separator for readability

    return file_path