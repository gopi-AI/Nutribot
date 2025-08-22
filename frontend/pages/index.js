import { useState } from "react";

export default function Home() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const newMessages = [...messages, { role: "user", content: input }];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("https://your-fastapi-backend-url/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: input })
      });

      const data = await res.json();
      setMessages([...newMessages, { role: "bot", content: data.answer }]);
    } catch (err) {
      setMessages([...newMessages, { role: "bot", content: "Error connecting to server." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-6">
      <div className="w-full max-w-2xl bg-white rounded-2xl shadow-lg p-6">
        <h1 className="text-2xl font-bold mb-4 text-center">Nutrition Chatbot</h1>
        <div className="h-80 overflow-y-auto border rounded-lg p-3 mb-4 bg-gray-50">
          {messages.map((m, i) => (
            <div key={i} className={`mb-2 ${m.role === "user" ? "text-blue-600" : "text-green-600"}`}>
              <b>{m.role === "user" ? "You:" : "Bot:"}</b> {m.content}
            </div>
          ))}
          {loading && <div className="text-gray-500">Bot is typing...</div>}
        </div>
        <form onSubmit={sendMessage} className="flex">
          <input
            type="text"
            className="flex-1 border rounded-l-lg px-3 py-2 focus:outline-none"
            placeholder="Ask about diet..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="submit" className="bg-blue-500 text-white px-4 py-2 rounded-r-lg hover:bg-blue-600">
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
