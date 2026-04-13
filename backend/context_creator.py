from langchain_text_splitters import RecursiveCharacterTextSplitter
import io
from pypdf import PdfReader
from langchain_core.documents import Document

# 1. Initialize the splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000, 
    chunk_overlap=200, 
    separators=["\n\n", "\n", " ", "", "Chapter", "Section"]
)

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts text from a PDF file stream."""
    try:
        pdf_stream = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_stream)
        
        full_text = []
        num_pages = len(reader.pages)

        for i in range(num_pages):
            page = reader.pages[i]
            page_text = page.extract_text() or ""
            # Including page numbers helps the LLM cite specific parts of the document
            full_text.append(f"--- Page {i + 1} ---\n{page_text}\n\n")

        return "".join(full_text)
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        raise ValueError("Failed to extract text from PDF file.")

def create_context(documents):
    """Chunks text and adds metadata headers for context."""
    chunks = []
    for doc in documents:
        doc_chunks = text_splitter.split_text(doc['content'])
        # We attach Document ID and Title to every single chunk so the LLM knows the source
        chunks.extend([
            f"Document ID: {doc['id']}\nTitle: {doc['title']}\nContent: {chunk}\n\n" 
            for chunk in doc_chunks
        ])
    return chunks

def process_pdf_to_context(pdf_bytes: bytes, file_title: str):
    
    raw_text = extract_text_from_pdf(pdf_bytes)
    doc_chunks = text_splitter.split_text(raw_text)
    
    return [
        Document(
            page_content=chunk, 
            metadata={"title": file_title}
        ) for chunk in doc_chunks
    ]