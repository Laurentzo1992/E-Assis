import React, { useState } from 'react';
import { apiRequest } from '../../services/api';
import Button from '../ui/Button';

/**
 * @file ChangePasswordForm.jsx
 * @description
 */
const ChangePasswordForm = ({ showCustomAlert }) => {
  const [passwords, setPasswords] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setPasswords(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (passwords.new_password !== passwords.confirm_password) {
      showCustomAlert("Les nouveaux mots de passe ne correspondent pas.", "danger");
      return;
    }
    setLoading(true);
    try {
      const response = await apiRequest('auth/change-password/', {
        method: 'POST',
        body: JSON.stringify({
          old_password: passwords.old_password,
          new_password: passwords.new_password,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || JSON.stringify(errorData));
      }

      showCustomAlert("Mot de passe mis à jour avec succès !", "success");
      setPasswords({ old_password: '', new_password: '', confirm_password: '' }); // Réinitialiser les champs
    } catch (error) {
      showCustomAlert(`Échec de la mise à jour : ${error.message}`, "danger");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="mb-3">
        <label className="form-label">Mot de passe actuel</label>
        <input
          type="password"
          name="old_password"
          className="form-control"
          value={passwords.old_password}
          onChange={handleChange}
          required
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Nouveau mot de passe</label>
        <input
          type="password"
          name="new_password"
          className="form-control"
          value={passwords.new_password}
          onChange={handleChange}
          required
        />
      </div>
      <div className="mb-3">
        <label className="form-label">Confirmer le nouveau mot de passe</label>
        <input
          type="password"
          name="confirm_password"
          className="form-control"
          value={passwords.confirm_password}
          onChange={handleChange}
          required
        />
      </div>
      <Button type="submit" className="w-100" loading={loading} loadingText="Mise à jour...">
        Mettre à jour
      </Button>
    </form>
  );
};

export default ChangePasswordForm;