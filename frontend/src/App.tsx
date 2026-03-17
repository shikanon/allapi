import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Console from "@/pages/Console";
import { RequireAuth } from "@/routes/RequireAuth";

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route
          path="/console"
          element={
            <RequireAuth>
              <Console />
            </RequireAuth>
          }
        />
      </Routes>
    </Router>
  );
}
