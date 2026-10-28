import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/app-shell/AppShell";
import { Ads } from "./pages/Ads";
import { AIConsole } from "./pages/AIConsole";
import { CampaignDetail } from "./pages/CampaignDetail";
import { Competitors } from "./pages/Competitors";
import { CreativeLab } from "./pages/CreativeLab";
import { DataHealth } from "./pages/DataHealth";
import { Experiments } from "./pages/Experiments";
import { Funnel } from "./pages/Funnel";
import { LiveMonitor } from "./pages/LiveMonitor";
import { NotificationsPage } from "./pages/NotificationsPage";
import { Overview } from "./pages/Overview";
import { Recommendations } from "./pages/Recommendations";
import { RecommendationCase } from "./pages/RecommendationCase";
import { SearchIntelligence } from "./pages/SearchIntelligence";
import { Settings } from "./pages/Settings";
import { EnvironmentOverview } from "./pages/EnvironmentOverview";
import { ProfileDetail } from "./pages/ProfileDetail";
import { RuleConsole } from "./pages/RuleConsole";
import { ScopeProvider } from "./domain/scope";
import { CommandCenter } from "./pages/CommandCenter";
import { Accounts } from "./pages/Accounts";
import { AccountDetail } from "./pages/AccountDetail";
import { Reviews } from "./pages/Reviews";
import { ReviewDetail } from "./pages/ReviewDetail";
import { ContentIntelligence } from "./pages/ContentIntelligence";
import { ContentDetail } from "./pages/ContentDetail";
import { FocusMonitors } from "./pages/FocusMonitors";
import { Connections } from "./pages/Connections";
import { ApprovalQueue } from "./pages/execution/ApprovalQueue";
import { ExecutionQueue } from "./pages/execution/ExecutionQueue";
import { ExecutionDetail } from "./pages/execution/ExecutionDetail";
import { ExecutionPolicies } from "./pages/execution/ExecutionPolicies";
import { KillSwitch } from "./pages/execution/KillSwitch";
import { InstagramOverview } from "./pages/InstagramOverview";
import { InstagramAudience } from "./pages/InstagramAudience";
import { InstagramContent } from "./pages/InstagramContent";
import { InstagramDataHealth } from "./pages/InstagramDataHealth";
import { InstagramInsights } from "./pages/InstagramInsights";

export default function App() {
  return (
    <ScopeProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<CommandCenter />} />
          <Route path="/command-center" element={<Navigate to="/overview" replace />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/accounts/:id" element={<AccountDetail />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/reviews/:reviewId" element={<ReviewDetail />} />
          <Route path="/content" element={<ContentIntelligence />} />
          <Route path="/content/assets/:assetId" element={<ContentDetail />} />
          <Route path="/content/publications/:publicationId" element={<ContentDetail />} />
          <Route path="/instagram" element={<InstagramOverview />} />
          <Route path="/instagram/content" element={<InstagramContent />} />
          <Route path="/instagram/audience" element={<InstagramAudience />} />
          <Route path="/instagram/insights" element={<InstagramInsights />} />
          <Route path="/instagram/data-health" element={<InstagramDataHealth />} />
          <Route path="/focus" element={<FocusMonitors />} />
          <Route path="/settings/connections" element={<Connections />} />
          <Route path="/connections" element={<Navigate to="/settings/connections" replace />} />
          <Route path="/execution/approvals" element={<ApprovalQueue />} />
          <Route path="/execution/queue" element={<ExecutionQueue />} />
          <Route path="/execution/intents/:intentId" element={<ExecutionDetail />} />
          <Route path="/execution/jobs/:jobId" element={<ExecutionDetail />} />
          <Route path="/execution/policies" element={<ExecutionPolicies />} />
          <Route path="/execution/kill-switch" element={<KillSwitch />} />
          <Route path="/legacy/overview" element={<Overview />} />
          <Route path="/live" element={<LiveMonitor />} />
          <Route path="/ads" element={<Ads />} />
          <Route path="/ads/campaigns/:id" element={<CampaignDetail />} />
          <Route path="/creative" element={<CreativeLab />} />
          <Route path="/search" element={<SearchIntelligence />} />
          <Route path="/funnel" element={<Funnel />} />
          <Route path="/competitors" element={<Competitors />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/recommendations/:id" element={<RecommendationCase />} />
          <Route path="/experiments" element={<Experiments />} />
          <Route path="/data-health" element={<DataHealth />} />
          <Route path="/ai-console" element={<AIConsole />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/notifications" element={<NotificationsPage />} />
        </Route>
        <Route path="/environment" element={<EnvironmentOverview />} />
        <Route path="/profiles/:id" element={<ProfileDetail />} />
        <Route path="/rule-console" element={<RuleConsole />} />
      </Routes>
    </ScopeProvider>
  );
}
