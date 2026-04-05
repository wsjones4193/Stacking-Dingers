import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/components/Layout";
import PlayerHub from "@/pages/PlayerHub";
import TeamAnalyzer from "@/pages/TeamAnalyzer";
import ADPExplorer from "@/pages/ADPExplorer";
import HistoryBrowser from "@/pages/HistoryBrowser";
import Admin from "@/pages/Admin";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/players" replace />} />
        <Route path="/players" element={<PlayerHub />} />
        <Route path="/players/:playerId" element={<PlayerHub />} />
        <Route path="/teams" element={<TeamAnalyzer />} />
        <Route path="/teams/:draftId" element={<TeamAnalyzer />} />
        <Route path="/adp" element={<ADPExplorer />} />
        <Route path="/history" element={<HistoryBrowser />} />
        <Route path="/history/:moduleId" element={<HistoryBrowser />} />
        <Route path="/admin/*" element={<Admin />} />
      </Routes>
    </Layout>
  );
}
