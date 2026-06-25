import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { lazy, Suspense } from "react";

const ExecutiveDashboard = lazy(() => import("./features/executive/ExecutiveDashboard").then(m => ({ default: m.ExecutiveDashboard })));
const Dashboard = lazy(() => import("./features/dashboard/Dashboard").then(m => ({ default: m.Dashboard })));
const IdentityDetail = lazy(() => import("./features/detail/IdentityDetail").then(m => ({ default: m.IdentityDetail })));
const TrustGraphView = lazy(() => import("./features/graph/TrustGraphView").then(m => ({ default: m.TrustGraphView })));
const FindingsPage = lazy(() => import("./features/findings/FindingsPage").then(m => ({ default: m.FindingsPage })));
const CompliancePage = lazy(() => import("./features/compliance/CompliancePage").then(m => ({ default: m.CompliancePage })));
const TrustDebtPage = lazy(() => import("./features/trust-debt/TrustDebtPage").then(m => ({ default: m.TrustDebtPage })));
const BlastPathPage = lazy(() => import("./features/blast-path/BlastPathPage").then(m => ({ default: m.BlastPathPage })));

function Loading() {
  return (
    <div className="flex justify-center items-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Suspense fallback={<Loading />}><ExecutiveDashboard /></Suspense>} />
        <Route path="/identities" element={<Suspense fallback={<Loading />}><Dashboard /></Suspense>} />
        <Route path="/identity/:id" element={<Suspense fallback={<Loading />}><IdentityDetail /></Suspense>} />
        <Route path="/graph" element={<Suspense fallback={<Loading />}><TrustGraphView /></Suspense>} />
        <Route path="/findings" element={<Suspense fallback={<Loading />}><FindingsPage /></Suspense>} />
        <Route path="/compliance" element={<Suspense fallback={<Loading />}><CompliancePage /></Suspense>} />
        <Route path="/trust-debt" element={<Suspense fallback={<Loading />}><TrustDebtPage /></Suspense>} />
        <Route path="/blast-path" element={<Suspense fallback={<Loading />}><BlastPathPage /></Suspense>} />
      </Route>
    </Routes>
  );
}

export default App;
