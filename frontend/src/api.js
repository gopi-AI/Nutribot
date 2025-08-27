import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' }
})

export async function sendChat(message){
  const res = await api.post('/chat', { message })
  return res.data
}

export async function health(){
  const res = await api.get('/health')
  return res.data
}