FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Sur un volume monte depuis l'hote Windows/Mac, les evenements natifs du systeme de fichiers ne
# remontent pas jusqu'au conteneur Linux - sans repasser en polling, le live-reload ne se declenche
# jamais. react-scripts 5 (webpack 5) utilise watchpack (WATCHPACK_POLLING, defini dans
# docker-compose.yml) pour son propre watcher de compilation ; CHOKIDAR_USEPOLLING reste ici pour
# les outils annexes (ex. eslint) qui s'appuient sur chokidar directement.
ENV CHOKIDAR_USEPOLLING=true

EXPOSE 3000

CMD ["npm", "start"]
