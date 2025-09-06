import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

// Import des pages et composants
import LandingPage from './LandingPage';
import Inscription from './Inscription';
import Connexion from './components/Connexion';
// Import du Dashboard
import DashboardPage from './pages/DashboardPage';

import EmailVerificationSent from './components/EmailVerificationSent';
import ActivateAccount from './components/ActivateAccount';
import DemandeResetPassword from './components/DemandeResetPassword';
import ResetPassword from './components/ResetPassword';
import ProtectedRoute from './components/auth/ProtectedRoute';
import MarcheDetailPage from './pages/MarcheDetailPage';
import "./App.css";

function App() {
  return (
    <Router>
      <Routes>
        {/* --- Routes Publiques --- */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/Inscription" element={<Inscription />} />
        <Route path="/Connexion" element={<Connexion />} />
        <Route path="/email-verification-sent" element={<EmailVerificationSent />} />
        <Route path="/verification/:token" element={<ActivateAccount />} />
        <Route path="/mot-de-passe-oublie" element={<DemandeResetPassword />} />
        <Route path="/reset-password/:token" element={<ResetPassword />} />

        {/* --- Route Protégée --- */}
        {/* Cette structure indique que toutes les routes imbriquées à l'intérieur de ProtectedRoute
            nécessitent une authentification. */}
        <Route element={<ProtectedRoute />}>
          <Route path="/Dashboard" element={<DashboardPage />} />
          <Route path="/marche/:marcheId" element={<MarcheDetailPage />} />
        </Route>

        {/* --- Route de Fallback (page non trouvée) --- */}
        <Route path="*" element={<h1>404 - Page Non Trouvée</h1>} /> 
        {/* Ou redirigez vers la page d'accueil : <Route path="*" element={<Navigate to="/" />} /> */}
      </Routes>
    </Router>
  );
}

export default App;