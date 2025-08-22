import { useState } from "react";
import ChatWindow from "../components/ChatWindow";

export default function Home() {
  return (
    <div className="flex h-screen items-center justify-center bg-gray-100">
      <ChatWindow />
    </div>
  );
}
