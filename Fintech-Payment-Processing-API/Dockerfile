# Use a lightweight Python image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Copy dependency file first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project into the container
COPY . .

# Tell Docker that the API listens on port 8000
EXPOSE 8000

# Start FastAPI with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]