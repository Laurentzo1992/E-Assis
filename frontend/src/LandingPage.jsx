import React, { useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import businessMan from "./assets/undraw_business-decisions_3x2a.svg";
import winner from "./assets/undraw_winners_fre4.svg";

import { Link } from "react-router-dom";
import { fetchTarif } from "./services/tarif";

import "./style.css";

export default function LandingPage() {
  const [tarif, setTarif] = useState(null);

  useEffect(() => {
    fetchTarif()
      .then(setTarif)
      .catch((error) => console.error("Erreur lors du chargement du tarif :", error));
  }, []);

  return (
    <>
      <Navbar />
      <main className="my-3">
        <section id="tarifs" className="py-5" style={{ background: "#f8f9ff" }}>
          <div className="container py-4">
            <div className="text-center mb-5">
              <h2 className="titleColor">Un tarif simple, par entreprise</h2>
              <p className="text-muted fs-5">
                Essayez gratuitement, puis continuez avec un abonnement annuel sans surprise.
              </p>
            </div>

            <div className="row justify-content-center">
              <div className="col-lg-5 col-md-8 mb-4">
                <div className="card h-100 shadow-sm">
                  <div className="card-body p-4 text-center">
                    <h3 className="titleColor">Essai gratuit</h3>
                    <p className="display-6 fw-bold mb-0">
                      {tarif ? `${tarif.essai_gratuit_jours} jours` : "…"}
                    </p>
                    <p className="text-muted">Sans engagement, sans carte bancaire</p>
                    <Link className="btn btn-cta w-100 mt-3" to="/Inscription">
                      Commencer gratuitement
                    </Link>
                  </div>
                </div>
              </div>

              <div className="col-lg-5 col-md-8 mb-4">
                <div className="card h-100 shadow" style={{ border: "2px solid var(--orange)" }}>
                  <div className="card-body p-4 text-center">
                    <h3 className="titleColor">Abonnement annuel</h3>
                    <p className="display-6 fw-bold mb-0">
                      {tarif ? `${Number(tarif.prix_annuel).toLocaleString("fr-FR")} ${tarif.devise}` : "…"}
                    </p>
                    <p className="text-muted">par entreprise, par an</p>
                    <Link className="btn btn-cta w-100 mt-3" to="/Inscription">
                      Démarrer mon essai
                    </Link>
                  </div>
                </div>
              </div>
            </div>

            <p className="text-muted text-center mb-0">
              Paiement sécurisé par Mobile Money (Orange Money, Moov Money) ou carte bancaire.{" "}
              <Link to="/Tarifs">Voir le détail des avantages inclus</Link>.
            </p>
          </div>
        </section>

        <h2 className="titleColor text-center mt-5">Notre mission</h2>
        <section className="mb-5 sectionColor1 text-white fw-bold position-relative container-fluid">
          <div className="container-fluid">
            <div className="row">
              <div className=" col-12 col-md-4">
                <img
                  src={businessMan}
                  alt="mission"
                  className="img-fluid MissionImg"
                />
              </div>

              <div
                className=" col-12 col-md-8
               existense"
              >
                <p>
                  Nous facilitons l'accès des entreprises burkinabè aux marchés
                  publics, en diffusant en temps réel des appels d'offres
                  clairs, ciblés et accessibles.
                </p>
              </div>
            </div>
          </div>

        </section>

        <section className="mb-5 text-center sectionColor2">
          <div className="container-fluid">
            <h2 className="titleColor2 text-center ">Notre vision</h2>
            <div className="row align-items-center">
              <div className=" col-12 col-lg-8 vision-text-container me-5">
                <div className="vision-content">
                  <p className="vision-text ">
                    Augmenter le nombre d'opportunités pour toutes les
                    entreprises du Burkina Faso, en rendant chaque appel d'offre
                    accessible en un clic.
                  </p>
                </div>
              </div>

              <div className=" col-12  col-lg-3  vision-image-container">
                <div className="vision-image-wrapper">
                  <img
                    src={winner}
                    alt="vision"
                    className="img-fluid VisionImg"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
        <h2 className="titleColor text-center mt-5 fs-2 mb-5">
          Pourquoi choisir notre solution ?
        </h2>

        <section id="fonctionnalites" className="mb-5 features-section">
          <div className="container-fluid">
            <div className="row mt-4 justify-content-center">
              <div className="col-lg-4 col-md-6 mb-4">
                <div className="feature-card">
                  <div className="feature-icon">
                    <svg
                      width="48"
                      height="48"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M12 1L3 5V11C3 16.55 6.84 21.74 12 23C17.16 21.74 21 16.55 21 11V5L12 1Z"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M9 12L11 14L15 10"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                  <h3 className="feature-title">Sécurité des données</h3>
                  <p className="feature-description">
                    Vos informations sont protégées avec des standards élevés et
                    un stockage chiffré.
                  </p>
                </div>
              </div>

              <div className="col-lg-4 col-md-6 mb-4">
                <div className="feature-card">
                  <div className="feature-icon">
                    <svg
                      width="48"
                      height="48"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <circle
                        cx="12"
                        cy="12"
                        r="3"
                        stroke="#003865"
                        strokeWidth="2"
                      />
                      <path
                        d="M12 1V5"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                      <path
                        d="M12 19V23"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                      <path
                        d="M4.22 4.22L7.05 7.05"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                      <path
                        d="M16.95 16.95L19.78 19.78"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                      <path
                        d="M1 12H5"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                      <path
                        d="M19 12H23"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                      <path
                        d="M4.22 19.78L7.05 16.95"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                      <path
                        d="M16.95 7.05L19.78 4.22"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                    </svg>
                  </div>
                  <h3 className="feature-title">Veille automatique</h3>
                  <p className="feature-description">
                    Un système intelligent surveille pour vous les opportunités
                    selon vos critères personnalisés.
                  </p>
                </div>
              </div>

              <div className="col-lg-4 col-md-6 mb-4">
                <div className="feature-card">
                  <div className="feature-icon">
                    <svg
                      width="48"
                      height="48"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M3 3V21H21"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M9 9L12 6L16 10L20 6"
                        stroke="#003865"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <circle cx="20" cy="6" r="2" fill="#ef5b0c" />
                      <circle cx="16" cy="10" r="2" fill="#ef5b0c" />
                      <circle cx="12" cy="6" r="2" fill="#ef5b0c" />
                      <circle cx="9" cy="9" r="2" fill="#ef5b0c" />
                    </svg>
                  </div>
                  <h3 className="feature-title">Statistiques & alertes</h3>
                  <p className="feature-description">
                    Visualisez les tendances, recevez des alertes en temps réel
                    et prenez des décisions basées sur les données.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
        <svg
          viewBox="0 0 2704 509"
          width="100%"
          height="auto"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="paintSvg"
        >
          <path
            d="M0.877182 12.8287C2.10524 31.6944 3.50873 32.9521 27.0172 35.8448C56.3151 39.618 65.9641 47.4158 71.4026 72.067C74.7359 86.7822 78.2446 93.3223 84.9112 97.347C90.1743 100.617 103.332 103.132 114.56 103.132C124.735 103.132 130.7 107.409 135.261 117.848C143.858 137.845 144.384 150.045 139.121 205.636C134.033 259.089 133.156 282.608 135.437 299.335C139.647 329.143 147.191 339.582 164.559 339.582C188.419 339.582 198.594 312.793 193.682 262.862C190.524 229.91 190.875 167.527 194.383 155.453C199.12 139.355 203.857 132.94 215.26 127.658C229.12 121.369 233.681 116.464 239.471 101.12C242.102 93.8253 245.962 85.6502 247.892 83.009C252.628 76.4689 263.154 72.1927 284.382 68.2938C296.487 66.0299 304.382 63.7661 311.75 60.2445C332.803 50.1828 342.101 55.4651 348.943 81.2483C353.68 99.7366 357.89 107.786 365.434 113.194C378.065 122.25 389.644 120.74 403.328 108.038C417.889 94.4542 424.907 92.6934 434.731 99.7366C442.1 105.019 445.608 113.32 448.942 133.318C455.082 168.785 457.538 171.803 484.029 174.822C499.467 176.583 503.151 178.344 506.485 185.764C511.397 196.58 512.976 208.906 514.555 247.769C515.607 275.062 517.011 288.771 518.941 295.436C525.607 317.321 538.414 331.533 552.449 332.916C570.519 334.551 582.449 323.232 589.641 297.449C591.922 289.148 592.448 276.697 592.624 226.388C592.975 164.635 593.677 156.711 599.641 150.171L602.624 146.901L620.869 147.781L639.29 148.662L646.658 143.128C650.693 140.109 657.36 134.324 661.57 130.425C674.202 118.225 686.307 115.081 696.658 121.369C708.236 128.412 712.447 144.511 714.201 190.543C715.429 223.621 715.605 224.753 720.166 231.545C738.061 259.214 772.797 255.19 781.218 224.627C782.621 219.219 782.972 210.038 782.095 193.562C780.165 158.598 782.621 153.441 806.13 141.996C819.112 135.707 820.867 133.695 827.182 117.973C835.779 96.7181 843.147 89.2976 854.901 89.2976C868.585 89.2976 875.252 94.9573 881.041 111.308C886.655 127.155 891.743 133.695 901.041 136.965C905.251 138.474 909.988 139.606 911.743 139.606C917.532 139.606 924.725 135.959 934.023 128.035C949.286 115.206 952.093 114.452 960.338 120.866C970.689 128.79 971.04 131.305 970.865 201.234C970.689 271.54 968.058 348.512 965.426 367.881C964.373 374.798 962.093 388.381 960.163 398.066C954.198 429.509 952.795 440.576 952.795 457.178C952.97 494.029 963.496 506.48 995.25 507.864C1006.3 508.367 1009.81 507.99 1015.6 505.852C1038.93 497.299 1046.65 473.654 1039.99 430.137C1028.93 358.322 1029.46 364.736 1029.64 281.099C1029.81 176.205 1031.39 165.515 1048.23 159.101C1059.11 154.95 1063.32 158.598 1071.74 179.098C1077.35 192.933 1082.62 197.461 1093.49 197.461C1102.09 197.461 1112.62 193.813 1118.58 188.783C1123.67 184.381 1126.3 176.96 1127.7 161.616C1129.46 140.99 1132.09 137.845 1149.46 135.707C1167.88 133.318 1173.67 127.784 1177.7 108.792C1180.34 95.8377 1184.72 88.7945 1191.56 86.2791C1199.46 83.2606 1204.55 83.7637 1217.35 88.6687C1223.67 91.0584 1231.21 93.0707 1234.19 93.0707C1237 93.0707 1245.77 91.0584 1253.32 88.6687C1273.14 82.506 1279.81 81.8771 1285.42 85.9018C1291.56 90.3038 1294.72 99.4851 1297.7 121.998C1299.11 132.689 1301.21 143.757 1302.61 146.398C1305.77 153.189 1312.79 156.585 1323.14 156.459C1331.39 156.459 1333.49 155.831 1357.53 146.398C1368.58 142.121 1374.19 142.876 1380.33 149.416C1387 156.334 1391.56 168.282 1393.67 184.632C1395.77 200.731 1395.07 213.937 1389.81 255.819C1385.77 289.022 1385.6 304.24 1389.28 315.56C1394.02 330.652 1403.67 338.324 1418.05 338.324C1432.96 338.324 1442.44 330.904 1449.98 313.17C1453.84 303.863 1453.84 302.731 1454.19 237.079C1454.37 149.039 1455.07 145.14 1473.67 130.299C1484.37 121.747 1485.95 119.105 1491.91 100.491C1497.17 83.5121 1501.38 75.9659 1508.4 70.935C1511.91 68.4196 1514.37 67.9165 1524.02 67.9165C1535.42 67.9165 1535.42 67.9165 1544.89 74.5824C1555.42 81.8771 1558.05 86.5306 1562.79 104.893C1567.7 124.514 1574.72 132.06 1587.87 132.06C1597 132.06 1602.44 134.449 1605.07 139.606C1607.87 145.014 1608.05 163.377 1605.77 176.96C1602.44 195.952 1608.75 210.918 1623.14 218.213C1629.63 221.483 1632.08 221.986 1642.43 221.986C1666.12 221.986 1670.33 217.081 1672.43 187.022C1674.89 153.567 1681.38 143.379 1706.64 133.695C1725.42 126.526 1731.21 122.25 1735.59 112.188C1737.52 107.786 1739.1 103.132 1739.1 102C1739.1 97.4727 1744.71 84.6441 1748.4 80.7451C1754.19 74.5824 1765.24 71.3123 1780.15 71.3123C1802.43 71.3123 1810.33 75.9659 1814.54 90.9326C1818.4 105.396 1824.54 110.679 1837.7 110.679C1844.71 110.679 1849.98 108.163 1859.98 100.24C1869.62 92.8192 1875.59 92.3161 1883.66 98.4789C1896.29 108.038 1902.26 135.204 1905.76 199.725C1908.4 247.769 1905.59 289.274 1895.06 357.819C1887.34 408.253 1894.19 436.929 1916.29 444.853C1926.82 448.752 1937.69 448.626 1949.1 444.601C1964.54 439.067 1972.78 427.245 1976.99 404.983C1980.15 388.004 1980.15 374.169 1976.82 345.619C1970.33 287.387 1968.92 269.905 1967.87 235.821C1966.64 197.335 1968.4 173.061 1973.31 161.364C1974.71 157.843 1978.75 152.183 1982.08 148.787C2002.08 128.915 2001.03 131.179 2005.59 101.372C2007.69 88.2914 2012.43 81.4998 2023.13 76.2174C2031.73 71.9412 2042.78 70.6835 2048.39 73.3247C2050.68 74.3308 2056.29 80.2421 2060.85 86.5306C2071.2 100.617 2076.82 104.642 2085.94 104.767C2095.06 104.893 2102.6 102 2117.17 92.8192C2137.17 80.2421 2143.48 79.6132 2149.62 89.6749C2157.52 102.755 2158.39 126.777 2152.08 160.358C2150.32 170.043 2149.62 181.739 2149.97 193.059C2150.5 209.786 2150.85 211.044 2155.94 218.968C2162.78 229.281 2169.97 233.306 2181.2 233.306C2186.81 233.306 2191.02 232.299 2196.29 229.784C2215.06 220.728 2219.8 200.102 2213.48 153.567C2211.9 142.121 2211.02 127.029 2211.37 120.112C2211.9 109.169 2212.78 106.402 2217.52 99.2335C2223.48 89.9265 2229.8 85.9018 2244.01 81.8771C2249.09 80.3679 2259.62 76.0916 2267.34 72.3185C2278.74 66.6588 2282.08 65.6526 2284.71 66.6588C2286.46 67.4134 2288.57 68.5453 2289.27 69.3C2289.79 70.0546 2290.32 81.8771 2290.15 95.5862C2289.79 123.885 2291.72 130.425 2303.13 138.348C2308.39 141.996 2310.67 142.625 2319.79 143.128C2331.9 143.757 2337.16 141.996 2342.6 135.456C2347.16 130.173 2349.09 122.627 2352.07 98.7304C2356.29 65.0238 2362.43 56.9744 2385.93 54.7105C2404.35 52.9497 2412.95 59.6156 2416.28 78.6071C2421.2 104.893 2424.18 110.05 2436.81 112.943C2446.64 115.206 2452.78 113.068 2466.99 102.504C2478.92 93.4481 2483.83 92.4419 2489.97 97.0954C2495.58 101.372 2498.21 105.522 2502.07 115.961C2508.56 133.318 2510.14 149.416 2510.14 194.945C2509.97 236.827 2508.56 258.208 2502.95 306.253C2501.55 318.704 2499.62 335.683 2498.74 344.11C2494.88 383.602 2507.69 401.084 2540.49 401.21C2549.97 401.21 2552.07 400.833 2555.58 398.066C2569.44 387.249 2571.02 343.607 2559.97 262.862C2549.62 186.393 2556.63 121.621 2575.58 119.734C2577.69 119.483 2585.58 121.369 2593.3 123.759C2612.42 130.047 2622.07 130.047 2630.84 123.885C2639.79 117.596 2642.6 109.924 2642.6 91.3099C2642.77 71.6896 2644.88 59.6156 2649.26 55.4651C2653.3 51.5663 2659.26 49.3024 2672.25 46.9127C2684.7 44.5231 2690.84 41.3788 2695.4 34.8387C2699.44 29.3047 2703.82 13.9607 2704 5.28247V9.15527e-05H1352.09H0L0.877182 12.8287Z"
            fill="url(#paint0_radial_76_185)"
          />
          <defs>
            <radialGradient
              id="paint0_radial_76_185"
              cx="0"
              cy="0"
              r="1"
              gradientUnits="userSpaceOnUse"
              gradientTransform="translate(1352 254.031) rotate(180) scale(1352 254.031)"
            >
              <stop stop-color="#EF5B0C" />
              <stop offset="0.5" stop-color="#784A39" />
              <stop offset="1" stop-color="#003865" />
            </radialGradient>
          </defs>
        </svg>
      </main>

      <Footer />
    </>
  );
}
