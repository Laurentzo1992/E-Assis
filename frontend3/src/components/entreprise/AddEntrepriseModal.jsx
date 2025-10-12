import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Select from "react-select";
import { apiRequest } from "../../services/api";
import Button from "../ui/Button";

const customSelectStyles = {
  control: (base, state) => ({
    ...base,
    border: state.isFocused ? "1px solid #86b7fe" : "1px solid #ccc",
    boxShadow: state.isFocused ? "0 0 0 0.25rem rgba(13,110,253,0.25)" : "none",
    "&:hover": { borderColor: state.isFocused ? "#86b7fe" : "#888" },
  }),
  menuPortal: (base) => ({ ...base, zIndex: 9999 }),
  menu: (base) => ({ ...base, maxHeight: "300px" }),
};

const AddEntrepriseModal = ({
  onClose,
  onSuccess,
  apiDomainesActivite,
  loadingDomaines,
  apiSecteursActivite,
  loadingSecteurs,
  showCustomAlert,
}) => {
  const [formData, setFormData] = useState({
    nom: "",
    numeroIdentification: "",
    siret: "",
    telephone: "",
    email: "",
    nomRepresentant: "",
    prenomRepresentant: "",
    adresse: "",
    secteurId: null,
    domaineIds: [],
  });
  const [loading, setLoading] = useState(false);

  // Ferme le modal au clic sur ESC
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleDomainesChange = (selectedOptions) => {
    setFormData((prev) => ({
      ...prev,
      domaineIds: selectedOptions
        ? selectedOptions.map((opt) => opt.value)
        : [],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    // Workaround pour récupérer les valeurs actuelles du DOM (utile si le navigateur
    // a rempli les champs via autofill ou si l'utilisateur a collé du texte sans
    // déclencher un event React). On lit d'abord les éléments du formulaire puis
    // on tombe sur l'état React si l'élément est introuvable.
    const formEl = e.target;
    const currentValues = {
      nom: formEl.elements["nom"] ? formEl.elements["nom"].value : formData.nom,
      numeroIdentification: formEl.elements["numeroIdentification"]
        ? formEl.elements["numeroIdentification"].value
        : formData.numeroIdentification,
      siret: formEl.elements["siret"]
        ? formEl.elements["siret"].value
        : formData.siret,
      telephone: formEl.elements["telephone"]
        ? formEl.elements["telephone"].value
        : formData.telephone,
      email: formEl.elements["email"]
        ? formEl.elements["email"].value
        : formData.email,
      nomRepresentant: formEl.elements["nomRepresentant"]
        ? formEl.elements["nomRepresentant"].value
        : formData.nomRepresentant,
      prenomRepresentant: formEl.elements["prenomRepresentant"]
        ? formEl.elements["prenomRepresentant"].value
        : formData.prenomRepresentant,
      adresse: formEl.elements["adresse"]
        ? formEl.elements["adresse"].value
        : formData.adresse,
      secteurId: formEl.elements["secteurId"]
        ? formEl.elements["secteurId"].value || null
        : formData.secteurId,
      domaineIds: formData.domaineIds,
    };

    // Met à jour l'état React pour rester synchronisé avec le DOM
    setFormData((prev) => ({ ...prev, ...currentValues }));

    const payload = {
      nom: currentValues.nom,
      numero_identification: currentValues.numeroIdentification,
      siret: currentValues.siret,
      telephone: currentValues.telephone,
      email: currentValues.email,
      repnom: currentValues.nomRepresentant,
      repprenom: currentValues.prenomRepresentant,
      adresse: currentValues.adresse,
      secteur_ids: currentValues.secteurId ? [currentValues.secteurId] : [],
      domaine_ids: currentValues.domaineIds,
    };

    try {
      const response = await apiRequest("entreprise/entreprises/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errorData = await response.json();
        const errorMessages = Object.entries(errorData)
          .map(([field, messages]) => `${field}: ${messages.join(", ")}`)
          .join("\n");
        throw new Error(errorMessages);
      }

      const newCompany = await response.json();
      onSuccess(newCompany);
    } catch (error) {
      showCustomAlert(`Échec de la création : ${error.message}`, "danger");
      setLoading(false);
    }
  };

  const domaineOptions = apiDomainesActivite.map((d) => ({
    value: d.id,
    label: d.libelle,
  }));

  const modalContent = (
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
        zIndex: 1000,
      }}
      onClick={onClose} // fermeture au clic sur l'overlay
    >
      <div
        style={{
          backgroundColor: "#fff",
          borderRadius: "8px",
          width: "90%",
          maxWidth: "700px",
          maxHeight: "90%",
          overflowY: "auto",
          padding: "20px",
          position: "relative",
        }}
        onClick={(e) => e.stopPropagation()} // empêche la fermeture au clic à l'intérieur
      >
        <h2 style={{ marginBottom: "15px" }}>Créer votre entreprise</h2>
        <p style={{ color: "#666" }}>
          Renseignez les informations de votre entreprise pour commencer. Les
          champs marqués d'un * sont obligatoires.
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 45%" }}>
              <label>Nom de l'entreprise *</label>
              <input
                autoComplete="organization"
                type="text"
                name="nom"
                value={formData.nom}
                onChange={handleChange}
                required
                style={{ width: "100%", padding: "8px", marginTop: "5px" }}
              />
            </div>
            <div style={{ flex: "1 1 45%" }}>
              <label>Numéro d'identification *</label>
              <input
                autoComplete="off"
                type="text"
                name="numeroIdentification"
                value={formData.numeroIdentification}
                onChange={handleChange}
                required
                style={{ width: "100%", padding: "8px", marginTop: "5px" }}
              />
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: "10px",
              flexWrap: "wrap",
              marginTop: "10px",
            }}
          >
            <div style={{ flex: "1 1 45%" }}>
              <label>SIRET *</label>
              <input
                autoComplete="off"
                type="text"
                name="siret"
                value={formData.siret}
                onChange={handleChange}
                required
                style={{ width: "100%", padding: "8px", marginTop: "5px" }}
              />
            </div>
            <div style={{ flex: "1 1 45%" }}>
              <label>Téléphone</label>
              <input
                autoComplete="tel"
                type="tel"
                name="telephone"
                value={formData.telephone}
                onChange={handleChange}
                style={{ width: "100%", padding: "8px", marginTop: "5px" }}
              />
            </div>
          </div>

          <div style={{ marginTop: "10px" }}>
            <label>Secteur d'activité *</label>
            <select
              name="secteurId"
              value={formData.secteurId || ""}
              onChange={handleChange}
              required
              disabled={loadingSecteurs}
              style={{ width: "100%", padding: "8px", marginTop: "5px" }}
            >
              <option value="" disabled>
                Sélectionner un secteur
              </option>
              {apiSecteursActivite.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nom}
                </option>
              ))}
            </select>
          </div>

          <div style={{ marginTop: "10px" }}>
            <label>Domaines d'activité *</label>
            <Select
              isMulti
              options={domaineOptions}
              value={domaineOptions.filter((opt) =>
                formData.domaineIds.includes(opt.value)
              )}
              onChange={handleDomainesChange}
              isLoading={loadingDomaines}
              placeholder="Sélectionnez un ou plusieurs domaines..."
              noOptionsMessage={() => "Aucun domaine trouvé"}
              styles={customSelectStyles}
              menuPortalTarget={document.body}
              menuPosition="fixed"
            />
          </div>

          <div style={{ display: "none" }} aria-hidden>
            {/* Champs cachés pour aider l'autofill et la lecture DOM si nécessaire */}
            <input
              name="nomRepresentant"
              value={formData.nomRepresentant}
              readOnly
            />
            <input
              name="prenomRepresentant"
              value={formData.prenomRepresentant}
              readOnly
            />
            <input name="email" value={formData.email} readOnly />
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: "10px",
              marginTop: "20px",
            }}
          >
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={loading}
            >
              Annuler
            </Button>
            <Button type="submit" loading={loading} loadingText="Création...">
              Créer l'entreprise
            </Button>
          </div>
        </form>
      </div>
    </div>
  );

  return createPortal(
    modalContent,
    document.getElementById("react-modals-root")
  );
};

export default AddEntrepriseModal;
