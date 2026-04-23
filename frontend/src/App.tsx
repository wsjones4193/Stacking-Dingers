import { Routes, Route } from "react-router-dom";
import Layout from "@/components/Layout";
import Home from "@/pages/Home";
import PlayerHub from "@/pages/PlayerHub";
import TeamAnalyzer from "@/pages/TeamAnalyzer";
import ADPExplorer from "@/pages/ADPExplorer";
import CombosExplorer from "@/pages/CombosExplorer";
import HistoryBrowser from "@/pages/HistoryBrowser";
import Leaderboard from "@/pages/Leaderboard";
import Admin from "@/pages/Admin";
import Articles from "@/pages/Articles";
import Podcasts from "@/pages/Podcasts";
import SoccerHome from "@/pages/soccer/SoccerHome";
import SoccerPlayerHub from "@/pages/soccer/SoccerPlayerHub";
import SoccerAdpExplorer from "@/pages/soccer/SoccerAdpExplorer";
import SoccerOdds from "@/pages/soccer/SoccerOdds";
import SoccerRankings from "@/pages/soccer/SoccerRankings";
import SoccerProjectedXI from "@/pages/soccer/SoccerProjectedXI";

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
        <Route path="/history" element={<HistoryBrowser />} />
        <Route path="/history/:moduleId" element={<HistoryBrowser />} />
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="/articles" element={<Articles />} />
        <Route path="/articles/:slug" element={<Articles />} />
        <Route path="/podcasts" element={<Podcasts />} />
        <Route path="/admin/*" element={<Admin />} />
        {/* Soccer — The World Pup */}
        <Route path="/soccer" element={<SoccerHome />} />
        <Route path="/soccer/players" element={<SoccerPlayerHub />} />
        <Route path="/soccer/players/:playerId" element={<SoccerPlayerHub />} />
        <Route path="/soccer/adp" element={<SoccerAdpExplorer />} />
        <Route path="/soccer/odds" element={<SoccerOdds />} />
        <Route path="/soccer/rankings" element={<SoccerRankings />} />
        <Route path="/soccer/xi" element={<SoccerProjectedXI />} />
      </Routes>
    </Layout>
  );
}
