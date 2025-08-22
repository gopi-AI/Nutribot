import { useState } from "react";

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const sendMessage = () => {
    if (!input.trim()) return;
    setMessages([...messages, { text: input, sender: "user" }]);
    setInput("");
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { text: "🤖 Bot reply (demo)", sender: "bot" },
      ]);
    }, 600);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-r from-purple-500 to-indigo-600 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-4 flex flex-col space-y-4 animate-fadeIn">
        <h1 className="text-2xl font-bold text-center text-indigo-700">NutriBot</h1>
        <div className="flex-1 overflow-y-auto max-h-80 border rounded-lg p-2 space-y-2">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`p-2 rounded-lg text-sm ${
                m.sender === "user"
                  ? "bg-indigo-100 text-right"
                  : "bg-gray-200 text-left"
              }`}
            >
              {m.text}
            </div>
          ))}
        </div>
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="flex-1 border rounded-lg px-2 py-1"
            placeholder="Type a message..."
          />
          <button
            onClick={sendMessage}
            className="bg-indigo-600 text-white px-4 py-1 rounded-lg hover:bg-indigo-700 transition"
          >
            Send
          </button>
        </div>
      </div>
      <style jsx>{`
        .animate-fadeIn {
          animation: fadeIn 0.8s ease-in-out;
        }
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
