import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Campaigns from "./pages/Campaigns";
import Customer from "./pages/Customer";
import GroupDetail from "./pages/GroupDetail";
import Groups from "./pages/Groups";
import KnowledgeBase from "./pages/KnowledgeBase";
import Overview from "./pages/Overview";
import Service from "./pages/Service";
import Worklist from "./pages/Worklist";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="worklist" element={<Worklist />} />
        <Route path="customer/:id" element={<Customer />} />
        <Route path="groups" element={<Groups />} />
        <Route path="group/:tuple" element={<GroupDetail />} />
        <Route path="campaign" element={<Campaigns />} />
        <Route path="kb" element={<KnowledgeBase />} />
        <Route path="service" element={<Service />} />
        <Route path="service/:id" element={<Service />} />
        <Route path="*" element={<p className="text-neutral-500">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
