import { useState } from 'react';
import './App.css';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import ReactMarkdown from 'react-markdown';
//import dotenv from 'dotenv';
//dotenv.config();


//const service_path = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function App() {
  const [input, setInput] = useState('')
  const [files, setFiles] = useState([])
  const [response, setResponse] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)


  const handleFileUpload = async () => {
    if (files.length === 0) return alert("Select files first!");
    setUploading(true)

    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    try {
      const result = await axios.post(`http://localhost:8000/api/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      setResponse("Context created successfully. You can now ask questions based on the uploaded documents.")
      setResponse(result.data.message)
    } catch (error) {
      setResponse(`Error: ${error.message}`)
    }
    setUploading(false)
  }


  const handleQuestion = async () => {
    if (!input) return;
    setLoading(true)
    try {
      const answer = await axios.post(`http://localhost:8000/api/qa`, {question: input})
      setResponse("Answer retrieved. Checking compliance...")
      setResponse(answer.data.response)
    } catch (error) {
      setResponse(`Error: ${error.message}`)
    }
    setLoading(false)
  }


  return (
    <div className="hero">
  <h2>Quality Process Digital Assistant System</h2>
  <h4>
    A RAG-based solution designed to processes one or more quality process documents (PDF).
  </h4>
  
  <div className="input-group"> 
     <input type="file" multiple className="form-control"
      onChange={(e) => {
      // Convert FileList to a real Array so .forEach() works later
      if (e.target.files) {
        setFiles(Array.from(e.target.files));
      }
    }} 
    />
    <button className="btn btn-primary" onClick={handleFileUpload} disabled={uploading}>
      {uploading ? 'Uploading...' : 'Upload'}
    </button>
    </div>

  <div className="input-group">
    <input className="form-control"
      value={input} 
      onChange={(e) => setInput(e.target.value)} 
      placeholder="Enter your question here..."
    />
    <button className="btn btn-primary" onClick={handleQuestion} disabled={loading}>
      {loading ? 'Thinking...' : 'Get an Answer'}
    </button>
  </div>

  <div className="hero-content">
    <h3>Answer:</h3>
    <div className="board-content">
      <ReactMarkdown>
        {response || "The answer will appear here..."}
      </ReactMarkdown>
    </div>
  </div>
</div>

  )
}

export default App
