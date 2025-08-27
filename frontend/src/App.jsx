import React, { useEffect, useRef, useState } from 'react'
import ChatMessage from './components/ChatMessage.jsx'
import NutritionCard from './components/NutritionCard.jsx'
import { sendChat, health } from './api.js'

export default function App(){
  const [messages,setMessages] = useState([
    { role:'bot', content:'Hi! I\'m NutriBot. Ask me for nutrition facts (e.g., "Apple 100g"), meal planning, or science-backed diet advice.' }
  ])
  const [input,setInput] = useState('')
  const [loading,setLoading] = useState(false)
  const endRef = useRef(null)

  useEffect(()=>{ endRef.current?.scrollIntoView({behavior:'smooth'}) }, [messages, loading])
  useEffect(()=>{ health().catch(()=>{}) }, [])

  const onSend = async () => {
    const text = input.trim()
    if(!text) return
    setMessages(prev => [...prev, { role:'user', content:text }])
    setInput('')
    setLoading(true)
    try{
      const res = await sendChat(text)
      if(res.type === 'nutrition'){
        setMessages(prev => [...prev, { role:'bot', content: res.text || 'Here are the nutrition facts:' , nutrition: res.data }])
      } else {
        setMessages(prev => [...prev, { role:'bot', content: res.text }])
      }
    }catch(e){
      setMessages(prev => [...prev, { role:'bot', content: 'Sorry, something went wrong. Please try again.' }])
    }finally{
      setLoading(false)
    }
  }

  const onKey = (e)=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); onSend() } }

  return (
    <div className="container container-narrow py-4">
      <div className="d-flex align-items-center mb-3">
        <div className="me-2" style={{width:10,height:10, background:'#6cf0ff', borderRadius:4, boxShadow:'0 0 18px #6cf0ff'}}></div>
        <h4 className="header m-0">Nutritional Chatbot</h4>
        <span className="ms-2 small text-secondary">RAG • USDA • FastAPI</span>
      </div>

      <div className="app-card p-3">
        <div className="d-flex flex-column" style={{minHeight:'55vh'}}>
          {messages.map((m,i)=> (
            <div key={i}>
              <ChatMessage role={m.role} content={m.content} />
              {m.nutrition && <NutritionCard data={m.nutrition} />}
            </div>
          ))}
          {loading && (
            <div className="message bot me-auto">
              <div className="small text-uppercase" style={{opacity:.7}}>NutriBot</div>
              <div className="typing">
                <span className="dot"></span>
                <span className="dot"></span>
                <span className="dot"></span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="input-group mt-3 input-bar p-1">
          <input className="form-control" placeholder="Ask Nutribot" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={onKey}/>
          <button className="btn btn-success" onClick={onSend}>Send</button>
        </div>
      </div>
    </div>
  )
}