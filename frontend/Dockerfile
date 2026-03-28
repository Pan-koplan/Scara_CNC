# Было: FROM node:18-slim
# Стало (LTS 22):
FROM node:22-slim

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
