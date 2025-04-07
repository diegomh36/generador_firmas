import json
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
    Export data to a JSON file, handling multiple analysis entries correctly.

    Args:
        data (dict): The data to be exported. Should include 'response'.
        filename (str): The name of the file to be created.
        mode (int): The mode of export. 
            - 1: Export to "image_without_context" directory.
            - 2: Export to "image_with_context" directory.

    Returns:
        str: The full file path of the created file.
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

    # Create the full path for the file
    file_path = os.path.join(output_dir, filename)
    
    # Limpiar delimitadores de código Markdown de la respuesta
    response_text = data.get('response', 'N/A')
    # Eliminar delimitadores de código JSON si existen
    response_text = response_text.replace('```json', '').replace('```', '')
    # Eliminar espacios en blanco al principio y al final
    response_text = response_text.strip()
    
    # Parsear el nuevo análisis como JSON
    try:
        new_analysis = json.loads(response_text)
        
        # Añadir un timestamp único al nuevo análisis para diferenciar entradas
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_analysis["timestamp"] = timestamp
        
        # Leer el archivo existente si existe, o crear una estructura nueva
        all_analyses = []
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            try:
                with open(file_path, "r", encoding="utf-8") as json_file:
                    content = json_file.read()
                    if content:
                        all_analyses = json.loads(content)
                        if not isinstance(all_analyses, list):
                            all_analyses = [all_analyses]
            except json.JSONDecodeError:
                # Si el archivo existe pero no es un JSON válido, empezamos de nuevo
                all_analyses = []
        
        # Añadir el nuevo análisis a la lista
        all_analyses.append(new_analysis)
        
        # Escribir todos los análisis al archivo como un array JSON
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(all_analyses, indent=2, ensure_ascii=False, fp=json_file)
        
        return file_path
    
    except json.JSONDecodeError as e:
        # Si hay un error al parsear el JSON, guardar la respuesta en un archivo de texto
        error_file = file_path.replace('.json', '_error.txt')
        with open(error_file, "w", encoding="utf-8") as txt_file:
            txt_file.write(f"Error parsing JSON: {str(e)}\n\nRaw response:\n{response_text}")
        
        return error_file