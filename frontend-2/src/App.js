import logo from "./logo.svg";
import "./App.css";
import LandingPage from "./LandingPage";
import Inscription from "./Inscription";
import Connexion from "./components/Connexion";
import Dashboard from "./components/Dashboard";
import EmailVerificationSent from "./components/EmailVerificationSent";
import ActivateAccount from "./components/ActivateAccount";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/Inscription" element={<Inscription />} />
        <Route path="/Inscription" element={<Inscription />} />
        <Route path="/Connexion" element={<Connexion />} />
        <Route path="/Dashboard" element={<Dashboard />} />
        <Route path="/email-verification-sent" element={<EmailVerificationSent />} />
        <Route path="/verification/:token" element={<ActivateAccount />} />
      </Routes>
    </Router>
  );
}
export default App;
