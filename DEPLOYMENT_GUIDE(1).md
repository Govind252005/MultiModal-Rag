# 🚀 Complete Free Deployment Guide — Multimodal Offline RAG

> **Goal:** One public URL, always-on, accessible from anywhere (phone, laptop, anyone you share the link with), completely free forever.

---

## ⚡ TL;DR — Best Free Setup

| Layer | Platform | Cost |
|---|---|---|
| Full backend + LLM + DB | **Oracle Cloud Free Tier (A1)** | $0 forever |
| Kubernetes (optional) | **Oracle OKE or k3s on the same VM** | $0 forever |
| Frontend CDN (optional) | **Cloudflare Pages** | $0 forever |
| HTTPS + custom domain | **Cloudflare (free plan)** | $0 forever |

**Why Oracle A1?** It gives you **4 OCPUs + 24 GB RAM + 200 GB SSD** for free, forever. No other free tier comes close for ML workloads. Every competitor (Railway, Render, Fly.io, Koyeb) gives only 512 MB RAM — not enough for even one of your ML models.

---

## 📋 What You're Deploying

```
Internet
   │
   ▼
Nginx (reverse proxy + SSL)
   ├── /          ──────────► React Frontend (SPA)
   └── /api/      ──────────► FastAPI Backend
                                  ├── CLIP model              (~1 GB RAM)
                                  ├── BLIP captioning         (~1 GB RAM)
                                  ├── PaddleOCR                 (~500 MB)
                                  ├── faster-whisper          (~500 MB)
                                  ├── sentence-transformers   (~500 MB)
                                  └── ChromaDB embedded (file-based)

Ollama (internal)
   └── qwen3:8b                (~5 GB RAM)

Redis (cache, optional)          (~100 MB)
```

Total RAM used: ~9–11 GB of your free 24 GB ✅

---

## 🏗️ PART 1 — Oracle Cloud Free Account Setup

### Step 1: Create Oracle Cloud Account

1. Go to → **https://cloud.oracle.com/free**
2. Click **"Start for free"**
3. Fill in your name, email, region (choose closest to you)
4. Enter a credit card (required for verification — you will **NOT** be charged for Always Free resources)
5. Wait for email verification and account activation (can take 10–60 minutes)

> ⚠️ **Important:** During signup, select a **Home Region** carefully — you cannot change it later. Choose the region nearest to you (e.g., `ap-mumbai-1` for India).

---

### Step 2: Create a Free VM Instance (A1 Ampere)

1. Log into **https://cloud.oracle.com**
2. Go to **Compute → Instances → Create Instance**
3. Configure:
   - **Name:** `rag-server`
   - **Image:** Ubuntu 22.04 (ARM64 / aarch64)
   - **Shape:** Click "Change Shape" → Select **VM.Standard.A1.Flex**
   - **OCPUs:** Set to **4**
   - **Memory (GB):** Set to **24**
   - **Boot Volume:** Set to **100 GB** (free up to 200 GB total)
4. **SSH Keys:**
   - Click "Generate a key pair for me"
   - Download both the private key (`.key`) and public key (`.key.pub`)
   - Save the private key somewhere safe
5. Click **Create**
6. Wait 2–3 minutes for the instance to start
7. Note the **Public IP address** shown on the instance page

---

### Step 3: Open Firewall Ports

1. On your instance page → Click your **VCN (Virtual Cloud Network)**
2. Go to **Security Lists → Default Security List**
3. Click **"Add Ingress Rules"** and add:

| Source CIDR | Protocol | Port | Description |
|---|---|---|---|
| 0.0.0.0/0 | TCP | 80 | HTTP |
| 0.0.0.0/0 | TCP | 443 | HTTPS |
| 0.0.0.0/0 | TCP | 22 | SSH (already exists) |

4. Click **"Save Changes"**

---

### Step 4: SSH into Your Server

**On Linux / macOS / WSL / Git Bash:**
```bash
# Set correct permissions on your key file
chmod 400 ~/Downloads/rag-server.key

# Connect
ssh -i ~/Downloads/rag-server.key ubuntu@YOUR_PUBLIC_IP
```

**On Windows (PowerShell):**
```powershell
# Connect using built-in OpenSSH
ssh -i C:\Users\YourName\Downloads\rag-server.key ubuntu@YOUR_PUBLIC_IP
```

> Replace `YOUR_PUBLIC_IP` with the IP from Step 2.

---

### Step 5: Install Docker on the Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (no sudo needed for docker)
sudo usermod -aG docker ubuntu

# Install Docker Compose plugin
sudo apt install -y docker-compose-plugin

# Log out and back in for group change to take effect
exit
```

Reconnect SSH, then verify:
```bash
docker --version
docker compose version
```

---

### Step 6: Open OS-level Firewall (Ubuntu)

Oracle's OS-level firewall (iptables) also blocks ports. Run:
```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT

# Make these rules survive reboot
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
```

---

## 🐳 PART 2 — Deploy Your Project with Docker Compose

### Step 7: Upload Your Project to the Server

**Option A — Git (Recommended):**
```bash
# On the Oracle server:
sudo apt install -y git

# If your project is on GitHub:
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd "Minor Project"

# If not on GitHub yet, push it first from your local machine:
# git init && git add . && git commit -m "initial" && git remote add origin https://github.com/... && git push
```

**Option B — SCP (Direct upload from your Windows machine):**
```bash
# Run this on YOUR LOCAL machine (Git Bash or PowerShell):
scp -i ~/Downloads/rag-server.key -r "C:/Users/Govind/Claude/Projects/Minor Project" ubuntu@YOUR_PUBLIC_IP:~/
```

---

### Step 8: Install Ollama on the Server

```bash
# Install Ollama (runs as a system service)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model (this downloads ~4.5 GB — takes 5–15 min on Oracle's network)
ollama pull qwen3:8b

# Verify it works
ollama list
```

> Ollama runs as a system service automatically on port 11434. It survives reboots.

---

### Step 9: Update docker-compose.yml for Server Deployment

On the server, open your docker-compose.yml:
```bash
nano "Minor Project/docker-compose.yml"
```

Replace with this production-ready version:

```yaml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_HOST=http://host.docker.internal:11434
      - DEVICE=cpu
      - OCR_ENGINE=Paddleocr
      - WHISPER_MODEL=medium
      - WARMUP_ON_STARTUP=1
      - CACHE_ENABLED=0
    volumes:
      - rag_storage:/app/storage
      - rag_data:/app/data
    extra_hosts:
      - "host.docker.internal:host-gateway"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "3000:80"
    depends_on:
      - backend

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
    volumes:
      - ./nginx-prod.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
      - frontend

volumes:
  rag_storage:
  rag_data:
```

---

### Step 10: Create Production Nginx Config

```bash
cat > "Minor Project/nginx-prod.conf" << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 500M;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;

    # Serve frontend
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Proxy API to backend
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
        proxy_read_timeout 600s;
    }
}
EOF
```

---

### Step 11: Build and Start Everything

```bash
cd "Minor Project"

# Build all images (first time takes 10–20 min for ML dependencies)
docker compose build

# Start all services in background
docker compose up -d

# Watch logs to confirm startup
docker compose logs -f

# You should see:
# backend_1  | [startup] embedding models warm.
# frontend_1 | Configuration complete; ready for start up
```

Your app is now live at: **http://YOUR_PUBLIC_IP**

---

## 🌐 PART 3 — Free Custom Domain + HTTPS with Cloudflare

### Step 12: Get a Free Domain

Options:
- **Freenom** — free `.tk`, `.ml`, `.ga` domains (freenom.com)
- **Duck DNS** — free subdomain like `myrag.duckdns.org` (duckdns.org) — easiest
- **Your own domain** — if you already have one

**Easiest: DuckDNS (2 minutes):**
```bash
# On the Oracle server — set up auto-update of your DuckDNS IP:
sudo apt install -y curl

# Replace YOUR_TOKEN and YOUR_DOMAIN below:
echo "*/5 * * * * curl -s 'https://www.duckdns.org/update?domains=YOUR_DOMAIN&token=YOUR_TOKEN&ip=' > /dev/null" | crontab -

# Your app is now at: http://YOUR_DOMAIN.duckdns.org
```

---

### Step 13: Enable HTTPS with Let's Encrypt (Free SSL)

```bash
# Install Certbot
sudo snap install --classic certbot

# Get a free SSL cert — replace YOUR_DOMAIN
sudo certbot --nginx -d YOUR_DOMAIN.duckdns.org

# Certbot auto-renews — no action needed
```

> After this, your app is live at: **https://YOUR_DOMAIN.duckdns.org** ✅

---

## ☸️ PART 4 — Kubernetes Deployment (Optional, Advanced)

If you want to use Kubernetes instead of plain Docker Compose:

### Option A: k3s (Lightweight Kubernetes on your Oracle VM)

```bash
# Install k3s on the Oracle server
curl -sfL https://get.k3s.io | sh -

# Verify k3s is running
sudo kubectl get nodes

# You should see your node with STATUS: Ready
```

**Create Kubernetes manifests:**
```bash
mkdir -p k8s
```

**k8s/backend-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rag-backend
  template:
    metadata:
      labels:
        app: rag-backend
    spec:
      containers:
      - name: backend
        image: rag-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: OLLAMA_HOST
          value: "http://host.docker.internal:11434"
        - name: DEVICE
          value: "cpu"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "6Gi"
            cpu: "3"
        volumeMounts:
        - name: storage
          mountPath: /app/storage
        - name: data
          mountPath: /app/data
      volumes:
      - name: storage
        hostPath:
          path: /opt/rag/storage
      - name: data
        hostPath:
          path: /opt/rag/data
---
apiVersion: v1
kind: Service
metadata:
  name: rag-backend
spec:
  selector:
    app: rag-backend
  ports:
  - port: 8000
    targetPort: 8000
```

**k8s/frontend-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rag-frontend
  template:
    metadata:
      labels:
        app: rag-frontend
    spec:
      containers:
      - name: frontend
        image: rag-frontend:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "256Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: rag-frontend
spec:
  selector:
    app: rag-frontend
  ports:
  - port: 80
    targetPort: 80
```

**Deploy to k3s:**
```bash
# Build Docker images on the server
cd "Minor Project"
docker build -t rag-backend:latest ./backend
docker build -t rag-frontend:latest ./frontend

# Import images into k3s
docker save rag-backend:latest | sudo k3s ctr images import -
docker save rag-frontend:latest | sudo k3s ctr images import -

# Apply manifests
sudo kubectl apply -f k8s/

# Check pods are running
sudo kubectl get pods

# Check services
sudo kubectl get services
```

---

### Option B: Oracle OKE (Managed Kubernetes — Free)

1. In Oracle Cloud Console → **Developer Services → Kubernetes Clusters (OKE)**
2. Click **"Create Cluster"** → Quick Create
3. **Shape:** VM.Standard.A1.Flex (uses your A1 allocation)
4. **Node count:** 1, **OCPUs:** 4, **Memory:** 24 GB
5. Click Create (takes ~10 minutes)
6. Download kubeconfig and use kubectl as normal

---

## 📱 PART 5 — Access from Phone / Anywhere

After completing Part 3 (HTTPS setup), your app is accessible at:

```
https://YOUR_DOMAIN.duckdns.org
```

- ✅ Open this on your **phone browser** — fully works
- ✅ Share this link with **anyone** — they can use your project
- ✅ The server **never sleeps** — always available
- ✅ Works on **any network** — home WiFi, mobile data, office

The React frontend is mobile-responsive — it works on small screens.

---

## 🔧 PART 6 — Server Management Commands

Run these on the Oracle server via SSH:

```bash
# View all running containers
docker compose ps

# See live logs
docker compose logs -f

# See logs for one service only
docker compose logs -f backend

# Restart a service
docker compose restart backend

# Stop everything
docker compose down

# Start everything
docker compose up -d

# Update after code changes
git pull                      # pull latest code
docker compose build backend  # rebuild backend image
docker compose up -d          # redeploy

# Check disk usage
df -h

# Check RAM usage
free -h

# Check CPU usage
htop   # (install with: sudo apt install htop)

# Check Ollama
ollama list                          # list downloaded models
ollama ps                            # show running models
curl http://localhost:11434/api/tags # API check
```

---

## 🆓 PART 7 — Free Tier Comparison Table

| Platform | RAM | Always-On | Docker | K8s | GPU | Can Run Ollama | Storage |
|---|---|---|---|---|---|---|---|
| **Oracle Cloud A1** ⭐ | **24 GB** | ✅ | ✅ | ✅ OKE/k3s | ❌ | ✅ | 200 GB |
| Hugging Face Spaces | 2–16 GB | ❌ Sleeps | ✅ | ❌ | Shared | ❌ (sleeps) | 50 GB ephemeral |
| Google Cloud Run | 8 GB | ❌ Scale-to-zero | ✅ | ❌ | ❌ | ❌ | None |
| Fly.io | 256 MB | ❌ | ✅ | ❌ | ❌ | ❌ | 3 GB |
| Railway | 512 MB | ❌ | ✅ | ❌ | ❌ | ❌ | Ephemeral |
| Render | 512 MB | ❌ Sleeps | ✅ | ❌ | ❌ | ❌ | Ephemeral |
| Koyeb | 512 MB | ✅ | ✅ | ❌ | ❌ | ❌ | None |
| Local + Cloudflare Tunnel | Your PC | If PC is on | ✅ | ❌ | ✅ if GPU | ✅ + GPU | Your HDD |

---

## 🌩️ PART 8 — Alternative: Cloudflare Tunnel (If You Have a Gaming PC)

If you have a local machine with decent RAM (16+ GB) and want **GPU acceleration**:

```bash
# 1. Install cloudflared on your Windows machine
# Download from: https://github.com/cloudflare/cloudflared/releases
# (cloudflared-windows-amd64.msi)

# 2. Login to Cloudflare (creates ~/.cloudflared/cert.pem)
cloudflared tunnel login

# 3. Create a named tunnel
cloudflared tunnel create rag-tunnel

# 4. Create config file at C:\Users\YourName\.cloudflared\config.yml:
# tunnel: <TUNNEL_ID_FROM_STEP_3>
# credentials-file: C:\Users\YourName\.cloudflared\<TUNNEL_ID>.json
# ingress:
#   - hostname: rag.yourdomain.com
#     service: http://localhost:80
#   - service: http_status:404

# 5. Route traffic
cloudflared tunnel route dns rag-tunnel rag.yourdomain.com

# 6. Start tunnel (run Docker Compose first)
docker compose up -d
cloudflared tunnel run rag-tunnel
```

Your app is now at: **https://rag.yourdomain.com** — accessible from anywhere, with your GPU powering it.

---

## 📝 PART 9 — Quick Reference: All Setup Steps in Order

1. Create Oracle Cloud account (cloud.oracle.com/free)
2. Create VM: A1 Flex, 4 OCPU, 24 GB RAM, Ubuntu 22.04 ARM64
3. Open ports 80 and 443 in VCN Security List
4. SSH into server
5. `sudo apt update && sudo apt upgrade -y`
6. Install Docker: `curl -fsSL https://get.docker.com | sh`
7. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
8. `ollama pull qwen3:8b`
9. Upload project (git clone or scp)
10. Update docker-compose.yml (production version above)
11. Create nginx-prod.conf (above)
12. `docker compose build`
13. `docker compose up -d`
14. Test: `http://YOUR_PUBLIC_IP` ✅
15. Set up DuckDNS (free subdomain)
16. `sudo snap install --classic certbot`
17. `sudo certbot --nginx -d YOUR_DOMAIN.duckdns.org`
18. Test: `https://YOUR_DOMAIN.duckdns.org` ✅ (share this link!)
19. (Optional) Install k3s and deploy K8s manifests

---

## ⚠️ Important Notes

### ARM Architecture (Oracle A1 is ARM64)
Your Docker images must support `linux/arm64`. Most modern Python packages do, but:
- If a pip install fails with architecture errors, add `--extra-index-url https://pypi.org/simple` or find ARM wheels
- PaddleOCR, CLIP, faster-whisper, sentence-transformers all support ARM64
- For ARM: use `pip install torch --index-url https://download.pytorch.org/whl/cpu`

### LLM Speed on CPU-Only Oracle A1
- qwen3:8b generates at **~1–4 tokens/second** on ARM CPU (no GPU)
- This is usable for RAG (you wait 10–30 seconds for an answer) but not blazing fast
- For faster answers: use a smaller model — `ollama pull qwen3:4b` (~2 GB, ~3–7 tok/s)

### Auto-Restart on Reboot
```bash
# Enable Docker to start on boot
sudo systemctl enable docker

# Add restart: always to all services in docker-compose.yml (already done above)

# Ollama starts automatically as a systemd service after installation
sudo systemctl enable ollama
```

### Monitor Your Free Tier Usage
- Oracle Console → **Governance → Limits, Quotas, and Usage**
- Always Free resources are marked — you will never be charged for them
- Only pay attention if you accidentally create paid resources (A1.Flex with ≤4 OCPU + ≤24 GB RAM is free)

---

## 🎉 Final Result

After following this guide, you will have:

- ✅ **One public URL** (e.g., `https://myrag.duckdns.org`) accessible from anywhere
- ✅ **HTTPS / SSL** — secure connection, green lock in browser
- ✅ **Always-on** — Oracle A1 never sleeps or shuts down
- ✅ **Full Docker deployment** — reproducible, easy to update
- ✅ **Kubernetes ready** — deploy with k3s or Oracle OKE on the same free VM
- ✅ **Mobile friendly** — open on your phone and demo to anyone
- ✅ **$0/month** — Oracle Always Free tier, Cloudflare free plan, Let's Encrypt SSL
- ✅ **All features working** — login, file upload, PDF/image/audio ingestion, AI answers with citations, multimodal search

> **Share your project:** Send `https://myrag.duckdns.org` to your teacher, teammate, or interviewer — they can register, upload files, and use the full system from their phone or browser.
