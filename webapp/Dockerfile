# webapp/Dockerfile (Development Version)

FROM oven/bun:1

WORKDIR /app

# Copy package.json and bun.lock
COPY package.json bun.lock ./

# Install dependencies
# Use --production=false if you have devDependencies needed at runtime
# Or just run `bun install` which installs all by default
RUN bun install

# Copy the rest of the application source code
# This is less critical if using volumes, but good for initial setup
COPY . .

# Expose the Vite development server port
EXPOSE 5173

# Start the development server
# Use --host to expose it outside the container
CMD ["bun", "run", "dev", "--host"] 

# Remove previous build/Nginx stages
# # Stage 1: Build the React application using Bun
# FROM oven/bun:1 as builder
# ... build steps ...

# # Stage 2: Serve the static files using Nginx
# FROM nginx:1.25-alpine
# ... nginx steps ... 