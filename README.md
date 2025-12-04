# 🛍️ E-Commerce Backend Platform  
(Django + DRF + Redis + Celery + Razorpay + Docker + NGINX)

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Django](https://img.shields.io/badge/Django-4.2%2B-green)
![DRF](https://img.shields.io/badge/DRF-3.14%2B-red)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)

A production-ready, scalable e-commerce backend built with modern practices and microservice-ready architecture.

## 🚀 Overview

This project provides a complete e-commerce backend with:

- JWT Authentication
- Product catalog with Redis caching
- Shopping cart & checkout system
- Razorpay payment gateway with webhook verification
- Background tasks & scheduling using Celery
- Full containerization (Docker + NGINX)
- CI/CD via GitHub Actions

## 🏗️ Architecture

```
                  ┌──────────────┐
                  │   Clients    │
                  └──────┬───────┘
                         ↓
                ┌─────────────────┐
                │     NGINX       │ (Reverse Proxy)
                └───────┬─────────┘
                        ↓
        ┌───────────────┴────────────────┐
        │ Gunicorn + Django REST Framework│
        └───────┬──────────────────┬──────┘
                ↓                  ↓
        ┌────────────┐     ┌───────────────┐
        │ PostgreSQL │     │     Redis     │ (Cache + Celery Broker)
        └────────────┘     └───────┬───────┘
                                   ↓
                          ┌─────────────────┐
                          │ Celery Worker   │
                          │ + Celery Beat   │ (Async + Scheduled Tasks)
                          └─────────────────┘
                                   ↑
                          Razorpay Webhooks
```

## 🔥 Features

| Feature                                   | Status |
|-------------------------------------------|--------|
| User Authentication (JWT)                 | Done    |
| Role-based Access (Admin / Customer)      | Done    |
| Product CRUD API                          | Done    |
| Redis caching for products                | Done    |
| Shopping Cart & Checkout                  | Done    |
| Order Management                          | Done    |
| Razorpay Payment Gateway                  | Done    |
| Webhook for automatic payment confirmation| Done    |
| Celery async tasks (emails, cleanup)      | Done    |
| Scheduled jobs (auto-cancel unpaid orders)| Done    |
| Docker & Docker Compose                   | Done    |
| NGINX Reverse Proxy                       | Done    |
| CI Pipeline (GitHub Actions)              | Done    |

## 🧰 Tech Stack

| Category            | Technologies                              |
|---------------------|-------------------------------------------|
| Backend Framework   | Django, Django REST Framework             |
| Database            | PostgreSQL                                |
| Cache & Queue       | Redis                                     |
| Worker System       | Celery + Celery Beat                      |
| Payment Gateway     | Razorpay                                  |
| Containerization    | Docker, Docker Compose                    |
| Reverse Proxy       | NGINX                                     |
| CI/CD               | GitHub Actions                            |

## 🧪 API Authentication

Uses JWT (JSON Web Tokens)

- Login: `POST /api/users/login/`
- Use token: `Authorization: Bearer <access_token>`

## 📦 Setup Instructions

1. Clone the repository
```bash
git clone https://github.com/ArunKumar237/ecommerce-microservices-backend.git
cd ecommerce-microservices-backend
```

2. Create environment file
```bash
cp backend/.env.example backend/.env
```
Edit `backend/.env` with your real credentials (DB, Redis, Razorpay keys, etc.)

3. Run with Docker + NGINX
```bash
docker compose up --build
```

### Access URLs

| Service             | URL                        |
|---------------------|----------------------------|
| Backend API         | http://localhost:8000/api       |
| Django Admin        | http://localhost:8000/admin     |
| Swagger Docs        | http://localhost/api/docs (if available)  |
| NGINX (main entry)  | http://localhost:80/           |

## 💳 Payment Flow (Razorpay)

1. User creates order → status = `pending`
2. Frontend creates Razorpay order via backend API
3. Payment processed using Razorpay checkout widget
4. Razorpay sends webhook → backend verifies signature
5. Order status → `paid`, inventory reduced
6. Celery sends confirmation email

## ⏱ Scheduled Tasks (Celery Beat)

| Task                          | Schedule      | Description                     |
|-------------------------------|---------------|---------------------------------|
| Auto-cancel unpaid orders     | Every hour    | Protects inventory              |
| Send order confirmation email | On event      | Async delivery                  |
| Future extensions             | Extendable    | Microservice-ready              |

## ⚙️ CI Pipeline (GitHub Actions)

Runs on every push/PR:
- Install dependencies
- Spin up test DB + Redis
- Run full test suite
- Linting & migration checks

## 📬 Postman Collection (if available)

Complete API collection available at:  
`/docs/ECommerce_Postman_Collection.json`

## 🛣 Future Enhancements

- Elasticsearch for advanced product search
- Kubernetes deployment (Helm charts)
- ML-based recommendation engine
- Multi-vendor / marketplace support
- Microservices split (orders, users, products)

---

Ready for production. Built to scale.

Feel free to ⭐ the repo if you find it useful!
```