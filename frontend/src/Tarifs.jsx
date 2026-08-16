import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import { Check } from "lucide-react";
import { fetchTarif } from "./services/tarif";
import "./style.css";

export default function Tarifs() {
  const { t } = useTranslation();
  const [tarif, setTarif] = useState(null);
  const avantages = t("tarifs.included.avantages", { returnObjects: true });

  useEffect(() => {
    fetchTarif()
      .then(setTarif)
      .catch((error) => console.error("Erreur lors du chargement du tarif :", error));
  }, []);

  return (
    <>
      <Navbar />

      <section className="py-5" style={{ background: "#f8f9ff" }}>
        <div className="container py-4">
          <div className="text-center mb-5">
            <h1 className="titleColor">{t("tarifs.title")}</h1>
            <p className="text-muted fs-5">{t("tarifs.subtitle")}</p>
          </div>

          <div className="row justify-content-center">
            <div className="col-lg-5 col-md-8 mb-4">
              <div className="card h-100 shadow-sm">
                <div className="card-body p-4 text-center">
                  <h3 className="titleColor">{t("tarifs.freeTrial.title")}</h3>
                  <p className="display-6 fw-bold mb-0">
                    {tarif
                      ? t("tarifs.freeTrial.daysValue", { count: tarif.essai_gratuit_jours })
                      : "…"}
                  </p>
                  <p className="text-muted">{t("tarifs.freeTrial.note")}</p>
                  <Link className="btn btn-cta w-100 mt-3" to="/inscription">
                    {t("tarifs.freeTrial.cta")}
                  </Link>
                </div>
              </div>
            </div>

            <div className="col-lg-5 col-md-8 mb-4">
              <div className="card h-100 shadow" style={{ border: "2px solid var(--orange)" }}>
                <div className="card-body p-4 text-center">
                  <h3 className="titleColor">{t("tarifs.annual.title")}</h3>
                  <p className="display-6 fw-bold mb-0">
                    {tarif ? `${Number(tarif.prix_annuel).toLocaleString("fr-FR")} ${tarif.devise}` : "…"}
                  </p>
                  <p className="text-muted">{t("tarifs.annual.perCompanyPerYear")}</p>
                  <Link className="btn btn-cta w-100 mt-3" to="/inscription">
                    {t("tarifs.annual.cta")}
                  </Link>
                </div>
              </div>
            </div>
          </div>

          <div className="row justify-content-center mt-4">
            <div className="col-lg-8">
              <div className="card shadow-sm">
                <div className="card-body p-4">
                  <h5 className="titleColor mb-3">{t("tarifs.included.title")}</h5>
                  <ul className="list-unstyled mb-0">
                    {avantages.map((avantage) => (
                      <li key={avantage} className="d-flex align-items-start mb-2">
                        <Check size={20} className="text-success me-2 flex-shrink-0 mt-1" />
                        <span>{avantage}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <p className="text-muted text-center mt-3">{t("tarifs.paymentNote")}</p>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
