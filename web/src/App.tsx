import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Customer from "./pages/Customer";
import Groups from "./pages/Groups";
import Service from "./pages/Service";
import Worklist from "./pages/Worklist";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Worklist />} />
        <Route path="customer/:id" element={<Customer />} />
        <Route path="groups" element={<Groups />} />
        <Route path="service" element={<Service />} />
        <Route path="service/:id" element={<Service />} />
        <Route path="*" element={<p className="text-neutral-500">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
