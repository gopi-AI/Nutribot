import React from 'react'

export default function ChatMessage({ role, content }){
  const isUser = role === 'user'
  return (
    <div className={`message ${isUser ? 'user ms-auto' : 'bot me-auto'}`}>
      <div className="small text-uppercase" style={{opacity:.7}}>
        {isUser ? 'You' : 'NutriBot'}
      </div>
      <div style={{whiteSpace:'pre-wrap'}}>{content}</div>
    </div>
  )
}