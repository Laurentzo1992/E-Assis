import React, { useState } from "react";
import ProfileForm from "../profile/ProfileForm";
import ChangePasswordForm from "../profile/ChangePasswordForm";
import Button from "../ui/Button";
import { apiRequest } from "../../services/api";

const ProfileSection = ({
  activeCompany,
  profileData,
  setProfileData,
  apiDomainesActivite,
  loadingDomaines,
  errorDomaines,
  apiSecteursActivite,
  loadingSecteurs,
  errorSecteurs,
  fetchDomaines,
  fetchSecteurs,
  refetchUserCompanies,
  showCustomAlert,
}) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [loadingDelete, setLoadingDelete] = useState(false);

  const handleDelete = async () => {
    setLoadingDelete(true);
    try {
      const response = await apiRequest(
        `entreprise/entreprises/${activeCompany.id}/`,
        { method: "DELETE" }
      );

      if (response.status !== 204) {
        throw new Error(`Suppression échouée. Statut : ${response.status}`);
      }

      // Après suppression, on rafraîchit la liste des entreprises
      await refetchUserCompanies();
      setShowDeleteConfirm(false);
      showCustomAlert("Entreprise supprimée avec succès.", "success");
      // Si la suppression a retiré l'entreprise active, forcer la mise à jour du profil
      // Demande au parent (hook) de recharger l'entreprise active via refetchUserCompanies
      // Le hook useActiveCompany va gérer la sélection de l'entreprise active après le refetch
    } catch (error) {
      showCustomAlert(
        `Erreur lors de la suppression : ${error.message}`,
        "danger"
      );
    } finally {
      setLoadingDelete(false);
    }
  };

  if (!activeCompany) {
    return (
      <div style={{ padding: "20px" }}>
        <div
          style={{
            backgroundColor: "#d1ecf1",
            border: "1px solid #bee5eb",
            padding: "10px",
            borderRadius: "5px",
            color: "#0c5460",
          }}
        >
          Veuillez sélectionner ou créer une entreprise pour gérer son profil.
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "20px" }}>
      {/* Header */}
      <div style={{ marginBottom: "20px" }}>
        <h2>Profil de l'entreprise</h2>
        <p style={{ color: "#6c757d" }}>
          Gestion des informations pour <strong>{activeCompany.nom}</strong>
        </p>
      </div>

      {/* Flex container */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "20px" }}>
        {/* Colonne principale */}
        <div style={{ flex: "1 1 60%" }}>
          <ProfileForm
            activeCompany={activeCompany}
            profileData={profileData}
            setProfileData={setProfileData}
            apiDomainesActivite={apiDomainesActivite}
            loadingDomaines={loadingDomaines}
            errorDomaines={errorDomaines}
            apiSecteursActivite={apiSecteursActivite}
            loadingSecteurs={loadingSecteurs}
            errorSecteurs={errorSecteurs}
            showCustomAlert={showCustomAlert}
            fetchDomaines={fetchDomaines}
            fetchSecteurs={fetchSecteurs}
          />
        </div>

        {/* Colonne actions */}
        <div
          style={{
            flex: "1 1 35%",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          {/* Changer le mot de passe */}
          <div
            style={{
              border: "1px solid #ced4da",
              borderRadius: "8px",
              padding: "15px",
              backgroundColor: "#fff",
            }}
          >
            <h5 style={{ marginBottom: "10px" }}>Changer le mot de passe</h5>
            <ChangePasswordForm showCustomAlert={showCustomAlert} />
          </div>

          {/* Zone de suppression */}
          <div
            style={{
              border: "1px solid #dc3545",
              borderRadius: "8px",
              padding: "15px",
              backgroundColor: "#f8d7da",
              color: "#721c24",
            }}
          >
            <h5 style={{ marginBottom: "10px" }}>Zone de danger</h5>
            <p>
              La suppression de <strong>{activeCompany.nom}</strong> est une
              action définitive et irréversible.
            </p>
            <Button
              variant="danger"
              className="w-100"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Supprimer cette entreprise
            </Button>
          </div>
        </div>
      </div>

      {/* Confirmation suppression */}
      {showDeleteConfirm && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.5)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 9999,
          }}
          onClick={() => setShowDeleteConfirm(false)}
        >
          <div
            style={{
              backgroundColor: "#fff",
              borderRadius: "8px",
              padding: "20px",
              width: "90%",
              maxWidth: "500px",
              boxShadow: "0 5px 15px rgba(0,0,0,0.3)",
              position: "relative",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginBottom: "15px", color: "#dc3545" }}>
              Confirmer la suppression
            </h3>
            <p>
              Êtes-vous sûr de vouloir supprimer définitivement l'entreprise{" "}
              <strong>{activeCompany.nom}</strong> ?
            </p>
            <div
              style={{
                backgroundColor: "#fff3cd",
                color: "#856404",
                border: "1px solid #ffeeba",
                borderRadius: "5px",
                padding: "10px",
                marginBottom: "20px",
              }}
            >
              Attention : cette action est irréversible et entraînera la
              suppression de toutes les données associées.
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "10px",
              }}
            >
              <Button
                variant="secondary"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={loadingDelete}
              >
                Annuler
              </Button>
              <Button
                variant="danger"
                onClick={handleDelete}
                loading={loadingDelete}
                loadingText="Suppression..."
              >
                Supprimer définitivement
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfileSection;
