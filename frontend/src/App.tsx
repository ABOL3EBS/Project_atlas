import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ChatScreen } from "./components/chat/ChatScreen";
import { KnowledgeBaseScreen } from "./components/knowledge-base/KnowledgeBaseScreen";
import { AppShell } from "./components/layout/AppShell";
import { SettingsScreen } from "./components/settings/SettingsScreen";
import { AppProvider } from "./context/AppContext";
import { ChatProvider } from "./context/ChatContext";

export function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <ChatProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<Navigate to="/chat" replace />} />
              <Route path="/chat" element={<ChatScreen />} />
              <Route path="/knowledge-base" element={<KnowledgeBaseScreen />} />
              <Route path="/settings" element={<SettingsScreen />} />
              <Route path="*" element={<Navigate to="/chat" replace />} />
            </Route>
          </Routes>
        </ChatProvider>
      </AppProvider>
    </BrowserRouter>
  );
}