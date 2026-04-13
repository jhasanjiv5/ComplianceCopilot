import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import ollama
from langchain_core.prompts import ChatPromptTemplate
from context_creator import process_pdf_to_context
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import OllamaLLM as Ollama
from typing import List
import traceback
import json
import uuid
from datetime import datetime

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    question: str

class FileUploadRequest(BaseModel):
    filename: str
    filepath: str

class BulkUploadRequest(BaseModel):
    files: list[FileUploadRequest]

template = """You are a QMS Compliance Assistant. 
    Based on the language of question answer in that language only (e.g., English, German, French), if the given language is not available, answer in English.
    Use only the provided context to answer.
    1. ALWAYS cite the Document line number or document title and Section/Chapter (e.g., "Per SOP-101, Section 4.2..., According to SOP-05, Section 3.2...") if available.
    2. Do not use outside knowledge.
    3. If the answer is not in the context, say "I don't know" instead of making something up.
    4. Be concise and to the point.
    5. If multiple documents are relevant, synthesize the information but still cite all sources.
    6. If the question is about a specific document, prioritize information from that document but still check others for relevant info.
    context: {context}
    Question: {question}
    Answer: 
    """

DB_DIR = "./chroma_db"
EMBEDDINGS = OllamaEmbeddings(model="gemma2", num_ctx=8192)

def format_docs(docs):
    return "\n\n".join(f"Source: {d.metadata['title']}\nContent: {d.page_content}" for d in docs)

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    try:
        all_documents = []
        for file in files:
            file_data = await file.read()
            
            docs = process_pdf_to_context(file_data, file.filename)
            all_documents.extend(docs)

            vector_db = Chroma.from_documents(
            documents = all_documents, 
            embedding = EMBEDDINGS, 
            persist_directory = DB_DIR
            )

            return {"message": f"Successfully indexed {len(all_documents)} chunks from {len(files)} files."}
        
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")     

@app.post("/api/qa")
async def query_ollama(query: PromptRequest):

    try:
        vector_db = Chroma(persist_directory=DB_DIR, embedding_function=EMBEDDINGS)

        retriever = vector_db.as_retriever(search_kwargs={"k": 15})
        
        llm = Ollama(model="gemma2", temperature=0, num_ctx=8192, num_threads=8) # Adjust temperature for more deterministic answers --> addressing model hallucinations

        prompt = ChatPromptTemplate.from_template(template)

        qa_chain = ({"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | llm | StrOutputParser())

        result = qa_chain.invoke(query.question)


        audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "trace_id": str(uuid.uuid4()),
        "vector_db_collection": DB_DIR,
        "model": llm.model,
        "temperature": llm.temperature,
        "parameters": {"temperature": 0},
        "user_question": query.question,
        "ai_response": result,
        "sources_used": [doc.metadata['title'] for doc in retriever.invoke(query.question)]
        }
        
        # Append to a local JSONL file (standard for audit trails)
        with open("./audit/audit_trail.jsonl", "a") as f:
            f.write(json.dumps(audit_entry) + "\n")
        


        return {"response": result}

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error querying Ollama: {str(e)}")       


if __name__ == "__main__":
   import uvicorn
   uvicorn.run(app, host="0.0.0.0", port=8000)
