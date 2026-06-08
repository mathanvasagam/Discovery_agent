FROM node:18-alpine

WORKDIR /app

# Copy package descriptors and install dependencies
COPY package*.json ./
RUN npm install

# Copy frontend source files
COPY . .

# Expose port 5173 for Vite dev server
EXPOSE 5173

# Run Vite with host binding so it's accessible outside the container
CMD ["npm", "run", "dev", "--", "--host"]
