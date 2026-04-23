import { Routes, Route } from "react-router-dom";
import Layout from "@/components/Layout";
import Home from "@/pages/Home";
import PlayerHub from "@/pages/PlayerHub";
import TeamAnalyzer from "@/pages/TeamAnalyzer";
import ADPExplorer from "@/pages/ADPExplorer";
import CombosExplorer from "@/pages/CombosExplorer";
import PlayerScoring from "@/pages/PlayerScoring";
import HistoryBrowser from "@/pages/HistoryBrowser";
import Leaderboard from "@/pages/Leaderboard";
import Admin from "@/pages/Admin";
import Articles from "@/pages/Articles";
import Podcasts from "@/pages/Podcasts";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/players" element={<PlayerHub />} />
        <Route path="/players/:playerId" element={<PlayerHub />} />
        <Route path="/teams" element={<TeamAnalyzer />} />
        <Route path="/teams/:draftId" element={<TeamAnalyzer />} />
        <Route path="/adp" element={<ADPExplorer />} />
        <Route path="/combos" element={<CombosExplorer />} />
        <Route path="/scoring" element={<PlayerScoring />} />
        <Route path="/history" element={<HistoryBrowser />} />
        <Route path="/history/:moduleId" element={<HistoryBrowser />} />
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="/articles" element={<Articles />} />
        <Route path="/articles/:slug" element={<Articles />} />
        <Route path="/podcasts" element={<Podcasts />} />
        <Route path="/admin/*" element={<Admin />} />
      </Routes>
    </Layout>
  );
}
