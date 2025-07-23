# UXMCP Deployment Guide

## Overview
This guide covers the deployment configuration for UXMCP, including environment variables, network setup, and production considerations.

## Environment Configuration

### Frontend Configuration
The frontend uses Vite and requires the following environment variable:

```bash
VITE_API_URL=http://localhost:8000  # Development
VITE_API_URL=https://api.yourdomain.com  # Production
```

This variable is configured in:
- `docker-compose.yml` for Docker deployment
- `.env` file for local development
- Build-time environment for production builds

### Backend Configuration
```bash
MONGODB_URL=mongodb://mongo:27017     # Docker internal
DATABASE_NAME=uxmcp                   # Database name
MCP_SERVER_URL=http://api:8000/mcp    # MCP endpoint
LOG_LEVEL=INFO                        # Logging level
```

## Deployment Scenarios

### 1. Local Development (Docker Compose)
Current configuration in `docker-compose.yml`:
```yaml
frontend:
  environment:
    - VITE_API_URL=http://localhost:8000
```

### 2. Production Deployment

#### Frontend Build
For production, build the frontend with the correct API URL:
```bash
cd frontend
VITE_API_URL=https://api.yourdomain.com npm run build
```

#### Docker Production
Create a production `docker-compose.prod.yml`:
```yaml
version: "3.8"

services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URL=mongodb://mongo:27017
      - DATABASE_NAME=uxmcp
      - MCP_SERVER_URL=http://api:8000/mcp
      - LOG_LEVEL=INFO
    depends_on:
      - mongo
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    environment:
      - VITE_API_URL=https://api.yourdomain.com

  mongo:
    image: mongo:7
    environment:
      - MONGO_INITDB_DATABASE=uxmcp
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
  chromadb_data:
```

### 3. Cloud Deployment

#### Using Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://frontend:80;
    }

    location /api {
        rewrite ^/api(.*) $1 break;
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Environment Variables for Different Environments
Create environment-specific files:
- `.env.development`
- `.env.staging`
- `.env.production`

## Important Considerations

### CORS Configuration
If frontend and backend are on different domains, update CORS in `backend/app/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### SSL/HTTPS
For production:
1. Use HTTPS for both frontend and API
2. Update `VITE_API_URL` to use `https://`
3. Configure SSL certificates (Let's Encrypt recommended)

### Database Security
1. Add authentication to MongoDB
2. Use connection string with credentials:
   ```
   MONGODB_URL=mongodb://username:password@mongo:27017/uxmcp?authSource=admin
   ```

### API Security
1. Implement API authentication (currently not present)
2. Add rate limiting
3. Use environment variables for sensitive data

## Deployment Checklist

- [ ] Update `VITE_API_URL` to production API endpoint
- [ ] Configure CORS for production domain
- [ ] Set up SSL certificates
- [ ] Secure MongoDB with authentication
- [ ] Configure proper logging (LOG_LEVEL)
- [ ] Set up monitoring and alerts
- [ ] Configure backup strategy for MongoDB
- [ ] Test all endpoints with production URLs
- [ ] Verify WebSocket connections for SSE endpoints
- [ ] Set up health check endpoints

## Docker Build Commands

### Build for Production
```bash
# Build frontend with production API URL
docker build --build-arg VITE_API_URL=https://api.yourdomain.com -t uxmcp-frontend ./frontend

# Build backend
docker build -t uxmcp-backend ./backend
```

### Run Production Stack
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Monitoring

The application provides built-in logging at `/logs/app`. Configure external monitoring:
- Application logs: `/logs/app`
- Error logs: `/logs/app?level=ERROR`
- MongoDB metrics
- Container health checks

## Troubleshooting

### Frontend Cannot Connect to API
1. Check `VITE_API_URL` is correctly set
2. Verify CORS configuration
3. Check network connectivity
4. Verify API is accessible at the configured URL

### MongoDB Connection Issues
1. Check `MONGODB_URL` format
2. Verify MongoDB is running
3. Check authentication if enabled
4. Verify network connectivity between containers