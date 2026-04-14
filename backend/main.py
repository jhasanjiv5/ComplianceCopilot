import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

template = """You are a quality process document question answering digital assistant. . 
    Based on the language of the question, answer in that language only (e.g., English, German, French); if the given language is not available, answer in English.
    Use only the provided context to answer.
    1. ALWAYS cite the Document line number or document title and Section/Chapter (e.g., "Per SOP-101, Section 4.2..., According to SOP-05, Section 3.2...") if available.
    2. Do not use outside knowledge.
    3. If the answer is not in the context, say "I don't know" instead of making something up.
    4. Be concise and to the point.
    5. If multiple documents are relevant, synthesize the information but still cite all sources.
    6. If the question is about a specific document, prioritize information from that document, but still check others for relevant info.
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
        # Retrieval of relevant context from ChromaDB based on the question
        vector_db = Chroma(persist_directory=DB_DIR, embedding_function=EMBEDDINGS)

        # Configuration of the retriever with parameters to control the number of retrieved documents, which can help in providing sufficient context while avoiding overwhelming the LLM and potentially reducing hallucinations by focusing on the most relevant information
        # Adjusting 'k' allows us to find a balance between providing enough context for accurate answers and not overwhelming the model with too much information, which can lead to confusion and hallucinations. In practice, you may want to experiment with different values of 'k' to find the optimal number of documents that provides sufficient context without causing information overload for the LLM.
        # specifically, k= 15 means find the 15 chunks in the database that are mathematically most similar to the user's question and give them to the LLM.
        retriever = vector_db.as_retriever(search_kwargs={"k": 15}) # "filter": {"status": "Active"} # <--- This is the key to filtering by metadata, you can adjust the filter criteria based on your metadata schema and the specific use case. For example, if you have a "category" field in your metadata, you could filter by category like this: "filter": {"category": "SOP"}.
        
        # LLM configuration with parameters to reduce hallucinations and improve factuality
        # fro production rather use e.g., ChatOpenAI() so it points to vLLM server running the model, which is more efficient and cost effective than using the API. For development and testing, you can use the API directly.
        llm = Ollama(model="gemma2", temperature=0, num_ctx=8192, num_threads=8) # Adjust temperature for more deterministic answers --> addressing model hallucinations

        # Augmentation of the prompt with explicit instructions to cite sources and avoid hallucinations, along with formatting the retrieved documents for better comprehension by the LLM
        prompt = ChatPromptTemplate.from_template(template)

        # RAG chain that integrates retrieval, prompt formatting, and LLM response generation, with an output parser to ensure the response is in the desired format
        qa_chain = ({"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | llm | StrOutputParser())

        # Generation of the answer using the RAG chain, which will utilize the retrieved context and the LLM to produce a response that is grounded in the provided documents, while adhering to the instructions to minimize hallucinations and cite sources appropriately
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
