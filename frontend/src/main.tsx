import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <div className="bot-fixed-container">
      <div className="bot-bubble">Go ahead ask me your questions about the QMS?</div>
      <img 
        src="https://cdn-icons-png.flaticon.com/512/4712/4712035.png" 
        alt="AI Assistant" 
        className="bot-img" 
      />
    </div>
  </StrictMode>,
)
