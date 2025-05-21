# Cleem Server

Backend server for Cleem mobile application.

## Features

- User authentication with Google OAuth
- Food nutrition analysis with image recognition
- Water and weight tracking
- File uploads to AWS S3
- RESTful API using FastAPI

## Tech Stack

- Python 3.9+
- FastAPI
- SQLAlchemy
- PostgreSQL
- AWS S3
- Docker
- Nginx

## Getting Started

### Prerequisites

- Python 3.9 or higher
- PostgreSQL
- AWS Account (for S3)
- Google OAuth credentials

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Cleem224/cleem-server.git
cd cleem-server
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your configuration (see `.env.example`).

5. Run the server:
```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000/docs

## Deployment

For production deployment, use the provided `deploy.sh` script:

```bash
./deploy.sh
```

## API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## License

This project is licensed under the MIT License - see the LICENSE file for details. 