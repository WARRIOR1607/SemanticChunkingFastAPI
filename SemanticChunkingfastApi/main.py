from fastapi import FastAPI, UploadFile, File, Form
import PyPDF2
import os
import requests
from semantic_router.encoders import OpenAIEncoder
from semantic_chunkers import StatisticalChunker
import shutil

# Inicializar la aplicación FastAPI
app = FastAPI()

# Asignar la clave API directamente (Nota: no es seguro para producción)
os.environ["OPENAI_API_KEY"] = "sk-fG9Yow9Bmw82TGjSqBqQ5LMf24D7S6TaEaWp4gySNvT3BlbkFJfOjG0hoVHsHXzDwglaVN66JKJ6RKE02k9GhZGliCEA"

# Inicializar el encoder y el chunker
encoder = OpenAIEncoder(name="text-embedding-3-small")
chunker = StatisticalChunker(encoder=encoder)

@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...), nombreKnowledge: str = Form(...)):
    all_content = ""

    # Procesar cada archivo subido
    for file in files:
        content = ""
        with open(file.filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        with open(file.filename, 'rb') as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    content += page_text

        # Agregar contenido de cada archivo
        all_content += f"Contenido de {file.filename}:\n{content}\n{'-'*50}\n"

        # Eliminar archivo temporal
        os.remove(file.filename)

    # Realizar el proceso de chunking
    chunks = chunker(docs=[all_content])

    # Guardar los resultados en un archivo de texto
    with open('resultadoschunk.txt', 'w', encoding='utf-8') as f:
        for i, chunk in enumerate(chunks[0]):
            f.write(" ".join(chunk.splits) + "\n")
            f.write("\n" + "-"*50 + "\n")

    # Realizar la petición a la API externa para crear un dataset
    url = 'https://iaumentada.virtual.uniandes.edu.co/v1/datasets'
    headers = {
        'Authorization': 'Bearer dataset-BptkAi7cokCSxswy6uFItCK6',
        'Content-Type': 'application/json'
    }
    data = {
        "name": nombreKnowledge,
        "permission": "all_team_members"
    }
    response = requests.post(url, headers=headers, json=data, verify=False)

    if response.status_code == 200:
        dataset_id = response.json().get("id")
        if dataset_id:
            # Realizar la segunda petición para crear un documento basado en el dataset
            document_url = f'https://iaumentada.virtual.uniandes.edu.co/v1/datasets/{dataset_id}/document/create_by_file'
            files = {
                'file': ('resultadoschunk.txt', open('resultadoschunk.txt', 'rb'))
            }
            form_data = {
                'data': '{"indexing_technique":"high_quality","process_rule":{"rules":{"pre_processing_rules":[{"id":"remove_extra_spaces","enabled":false},{"id":"remove_urls_emails","enabled":false}],"segmentation":{"separator":"--------------------------------------------------","max_tokens":800}},"mode":"custom"}}'
            }
            document_response = requests.post(document_url, headers={'Authorization': 'Bearer dataset-BptkAi7cokCSxswy6uFItCK6'}, files=files, data=form_data, verify=False)

            if document_response.status_code == 200:
                return {"message": f"Archivos procesados y documento creado exitosamente en el dataset {dataset_id}", "document_response": document_response.json()}
            else:
                return {"message": f"Archivos procesados, pero hubo un error al crear el documento.", "status_code": document_response.status_code, "response_text": document_response.text}
        else:
            return {"message": "Archivos procesados, pero no se pudo obtener el ID del dataset."}
    else:
        return {"message": f"Archivos procesados, pero hubo un error en la solicitud a la API externa.", "status_code": response.status_code, "response_text": response.text}

@app.get("/")
def index():
    return {"message": "Bienvenido a la API de chunking de PDF"}
