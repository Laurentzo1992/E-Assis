import React, { useState } from 'react';
import Select from 'react-select';
import { apiRequest } from '../../services/api';
import Button from '../ui/Button';

/**
 * @file ProfileForm.jsx
 * @description Formulaire pour la mise à jour des informations de l'entreprise.
 * Gère l'état local du formulaire, les interactions utilisateur (champs, sélecteurs),
 * et la logique de soumission des données à l'API.
 */
const ProfileForm = ({
  activeCompany,
  profileData,
  setProfileData,
  apiDomainesActivite,
  loadingDomaines,
  apiSecteursActivite,
  loadingSecteurs,
  showCustomAlert,
}) => {
  const [loading, setLoading] = useState(false);

  /**
   * Gère les changements sur les champs de type input.
   * @param {React.ChangeEvent<HTMLInputElement>} e - L'événement de changement.
   */
  const handleChange = (e) => {
    const { name, value } = e.target;
    setProfileData(prevData => ({ ...prevData, [name]: value }));
  };
  
  /**
   * Gère le changement du sélecteur de secteur d'activité.
   * @param {React.ChangeEvent<HTMLSelectElement>} e - L'événement de changement.
   */
  const handleSecteurChange = (e) => {
    const selectedId = e.target.value ? parseInt(e.target.value, 10) : null;
    const selectedSecteur = apiSecteursActivite.find(s => s.id === selectedId) || null;
    setProfileData(prevData => ({ ...prevData, secteurActivite: selectedSecteur }));
  };

  /**
   * Gère le changement du sélecteur multi-domaines (react-select).
   * @param {Array<Object>} selectedOptions - Les options sélectionnées.
   */
  const handleDomainesChange = (selectedOptions) => {
    const selectedIds = selectedOptions ? selectedOptions.map(opt => opt.value) : [];
    const selectedDomaines = apiDomainesActivite.filter(d => selectedIds.includes(d.id));
    setProfileData(prevData => ({ ...prevData, domainesActivite: selectedDomaines }));
  };

  /**
   * Gère la soumission du formulaire de mise à jour.
   * @param {React.FormEvent<HTMLFormElement>} e - L'événement de soumission.
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    // Préparation des données à envoyer à l'API
    const payload = {
      nom: profileData.nom,
      numero_identification: profileData.numeroIdentification,
      siret: profileData.siret,
      adresse: profileData.adresse,
      email: profileData.email,
      telephone: profileData.telephone,
      repnom: profileData.nomRepresentant,
      repprenom: profileData.prenomRepresentant,
      domaine_ids: profileData.domainesActivite.map(d => d.id),
      secteur_ids: profileData.secteurActivite ? [profileData.secteurActivite.id] : [],
    };

    try {
      const response = await apiRequest(`entreprise/entreprises/${activeCompany.id}/`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`Erreur : ${JSON.stringify(errorData)}`);
      }
      
      const updatedCompany = await response.json();
      
      // Mettre à jour l'état parent avec les nouvelles données
      setProfileData({
        nom: updatedCompany.nom || "",
        numeroIdentification: updatedCompany.numero_identification || "",
        siret: updatedCompany.siret || "",
        adresse: updatedCompany.adresse || "",
        email: updatedCompany.email || "",
        telephone: updatedCompany.telephone || "",
        nomRepresentant: updatedCompany.repnom || "",
        prenomRepresentant: updatedCompany.repprenom || "",
        secteurActivite: updatedCompany.secteurs?.[0] || null,
        domainesActivite: updatedCompany.domaines || [],
      });

      showCustomAlert("Profil mis à jour avec succès !", "success");
    } catch (error) {
      showCustomAlert(`Échec de la mise à jour : ${error.message}`, "danger");
    } finally {
      setLoading(false);
    }
  };

  // Convertit les domaines pour le format attendu par react-select
  const domaineOptions = apiDomainesActivite.map(d => ({ value: d.id, label: d.libelle }));
  const selectedDomaineValues = profileData.domainesActivite.map(d => ({ value: d.id, label: d.libelle }));

  return (
    <div className="card">
      <div className="card-header"><h5 className="mb-0">Informations de l'entreprise</h5></div>
      <div className="card-body">
        <form onSubmit={handleSubmit}>
          <div className="row">
            <div className="col-md-6 mb-3">
              <label htmlFor="nom" className="form-label">Nom de l'entreprise</label>
              <input type="text" id="nom" name="nom" className="form-control" value={profileData.nom || ""} onChange={handleChange} required />
            </div>
            <div className="col-md-6 mb-3">
               <label htmlFor="numeroIdentification" className="form-label">Numéro d'identification</label>
               <input type="text" id="numeroIdentification" name="numeroIdentification" className="form-control" value={profileData.numeroIdentification || ""} onChange={handleChange} required />
            </div>
          </div>
          <div className="mb-3">
            <label className="form-label">Secteur d'activité</label>
            <select className="form-select" value={profileData.secteurActivite?.id || ''} onChange={handleSecteurChange} disabled={loadingSecteurs}>
              <option value="">Sélectionner un secteur</option>
              {apiSecteursActivite.map(s => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </div>

          <div className="mb-3">
            <label className="form-label">Domaines d'activité</label>
            <Select
              isMulti
              options={domaineOptions}
              value={selectedDomaineValues}
              onChange={handleDomainesChange}
              isLoading={loadingDomaines}
              placeholder="Sélectionnez des domaines..."
              noOptionsMessage={() => "Aucun domaine disponible"}
              styles={{ menuPortal: base => ({ ...base, zIndex: 9999 }) }}
              menuPortalTarget={document.body}
            />
          </div>

          <Button type="submit" loading={loading} loadingText="Enregistrement...">
            Enregistrer les modifications
          </Button>
        </form>
      </div>
    </div>
  );
};

export default ProfileForm;