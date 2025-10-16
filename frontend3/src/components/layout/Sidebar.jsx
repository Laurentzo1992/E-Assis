import React, { useState } from "react";
import { apiRequest } from "../../services/api";
import { FileText, Bell, User, LogOut, PlusCircle } from "lucide-react";

/**
 * @file Sidebar.jsx
 * @description Composant final pour la barre latérale.
 * Gère la navigation entre les sections et le changement d'entreprise active.
 */
const Sidebar = ({
  userCompanies,
  activeCompany,
  setActiveCompany,
  onAddCompanyClick,
  activeSection,
  setActiveSection,
  sidebarOpen,
  setSidebarOpen,
  onLogout,
  showCustomAlert,
}) => {
  const [isChangingCompany, setIsChangingCompany] = useState(false);

  const handleCompanyChange = async (e) => {
    const selectedId = parseInt(e.target.value);
    if (!selectedId || selectedId === activeCompany?.id) return;

    setIsChangingCompany(true);
    try {
      const response = await apiRequest("entreprise/entreprises/set-active/", {
        method: "POST",
        body: JSON.stringify({ entreprise_id: selectedId }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(JSON.stringify(errorData));
      }

      const updatedActiveCompany = await response.json();
      setActiveCompany(updatedActiveCompany);

      showCustomAlert("Entreprise active changée avec succès !", "success");
      setSidebarOpen(false);
    } catch (error) {
      console.error("Erreur lors du changement d'entreprise active:", error);
      showCustomAlert(
        `Échec du changement d'entreprise : ${error.message}`,
        "danger"
      );
    } finally {
      setIsChangingCompany(false);
    }
  };

  return (
    <>
      {/* Overlay */}
      <div
        className={`sidebar-overlay ${sidebarOpen ? "show" : ""}`}
        onClick={() => setSidebarOpen(false)}
      ></div>

      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? "show" : ""}`}>
        <div className="sidebar-header d-flex justify-content-between align-items-center">
          <h4>VeilleMarches Pro</h4>
          <button
            className="btn-close-sidebar d-md-none"
            onClick={() => setSidebarOpen(false)}
          >
            ✕
          </button>
        </div>

        <div className="sidebar-content">
          {/* Sélecteur d'entreprise */}
          <div className="mb-3 text-center">
            {userCompanies.length > 0 ? (
              <>
                <p className="text-muted mb-1">Entreprise active :</p>
                <select
                  className="form-select mb-2"
                  value={activeCompany ? activeCompany.id : ""}
                  onChange={handleCompanyChange}
                  disabled={isChangingCompany}
                >
                  <option value="">Sélectionner une entreprise</option>
                  {userCompanies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.nom}
                    </option>
                  ))}
                </select>
                {isChangingCompany && (
                  <div
                    className="spinner-border spinner-border-sm"
                    role="status"
                  >
                    <span className="visually-hidden">Loading...</span>
                  </div>
                )}
              </>
            ) : (
              <p className="text-muted mb-1">Aucune entreprise trouvée.</p>
            )}
          </div>

          {/* Bouton Ajouter une entreprise */}
          <button
            className="btn btn-cta w-100 mb-4 d-flex align-items-center justify-content-center gap-2"
            onClick={() => {
              setSidebarOpen(false); // ferme la sidebar
              onAddCompanyClick(); // ouvre le modal
            }}
          >
            <PlusCircle size={18} />
            Ajouter une entreprise
          </button>

          {/* Navigation */}
          <nav className="sidebar-nav">
            <a
              href="#"
              className={`nav-link d-flex align-items-center justify-content-center gap-2 ${
                activeSection === "veille" ? "active" : ""
              }`}
              onClick={() => {
                setActiveSection("veille");
                setSidebarOpen(false);
              }}
            >
              <FileText size={18} />
              Veille & Documents
            </a>

            <a
              href="#"
              className={`nav-link d-flex align-items-center justify-content-center gap-2 ${
                activeSection === "alertes" ? "active" : ""
              }`}
              onClick={() => {
                setActiveSection("alertes");
                setSidebarOpen(false);
              }}
            >
              <Bell size={18} />
              Alertes & Résultats
            </a>

            <a
              href="#"
              className={`nav-link d-flex align-items-center justify-content-center gap-2 ${
                activeSection === "profil" ? "active" : ""
              }`}
              onClick={() => {
                setActiveSection("profil");
                setSidebarOpen(false);
              }}
            >
              <User size={18} />
              Profil
            </a>
          </nav>
        </div>

        {/* Footer */}
        <div className="sidebar-footer mt-auto">
          <button
            className="btn btn-outline-light w-100 d-flex align-items-center justify-content-center gap-2"
            onClick={onLogout}
          >
            <LogOut size={18} />
            Déconnexion
          </button>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
