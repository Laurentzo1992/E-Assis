import React from 'react';
import ReactDOM from 'react-dom/client';
// Bundle npm plutot que CDN (public/index.html avant ce correctif) : un CDN externe est un point
// de defaillance en plus, surtout sur un reseau mobile lent/instable - constate en reel, la nav
// (classes/JS Bootstrap) restait totalement sans mise en forme quand le CDN ne se chargeait pas,
// alors que le CSS custom (bundle avec l'app) s'appliquait normalement.
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap/dist/js/bootstrap.bundle.min.js';
import './index.css';
import './i18n';
import App from './App';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
