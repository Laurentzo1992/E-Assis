import LandingPage from "./LandingPage";
import Tarifs from "./Tarifs";
import Inscription from "./Inscription";
import Connexion from "./components/Connexion";
import Dashboard from "./components/Dashboard";
import EmailVerificationSent from "./components/EmailVerificationSent";
import ActivateAccount from "./components/ActivateAccount";
import PaymentReturn from "./components/PaymentReturn";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/Tarifs" element={<Tarifs />} />
        <Route path="/Inscription" element={<Inscription />} />
        <Route path="/Connexion" element={<Connexion />} />
        <Route path="/Dashboard" element={<Dashboard />} />
        <Route path="/email-verification-sent" element={<EmailVerificationSent />} />
        <Route path="/verification/:token" element={<ActivateAccount />} />
        <Route path="/paiement/retour" element={<PaymentReturn />} />
      </Routes>
    </Router>
  );
}
export default App;
