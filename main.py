import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient, exceptions
from dotenv import load_dotenv
import uvicorn

# Load environment variables from Azure App Service or .env file
load_dotenv()

# Azure Blob Storage Configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")

# Cosmos DB Configuration
COSMOS_DB_CONNECTION_STRING = os.getenv("COSMOS_DB_CONNECTION_STRING")
DATABASE_NAME = os.getenv("DATABASE_NAME")
CONTAINER_NAME = os.getenv("CONTAINER_NAME")

# Initialize Cosmos DB Client
cosmos_client = CosmosClient.from_connection_string(COSMOS_DB_CONNECTION_STRING)
database = cosmos_client.get_database_client(DATABASE_NAME)
container = database.get_container_client(CONTAINER_NAME)

# Initialize Blob Storage Client
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
blob_container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

# FastAPI app instance
app = FastAPI()

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific frontend URLs for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data model for response
class UserSubmission(BaseModel):
    name: str
    email: str
    company: str
    file_url: str  # Store uploaded file URL

# Root API
@app.get("/test")
def read_root():
    return {"message": "This is vinu george app!"}

# Upload file & submit user data
@app.post("/submit/")
async def submit_response(
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        # Generate unique filename
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        # Upload file to Azure Blob Storage
        blob_client = blob_container_client.get_blob_client(unique_filename)
        blob_client.upload_blob(file.file, overwrite=True)

        # Get file URL
        file_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{unique_filename}"

        # Store data in Cosmos DB
        new_item = {
            "id": str(uuid.uuid4()),  
            "name": name,
            "email": email,
            "company": company,
            "file_url": file_url,  # Store uploaded file URL
        }
        container.create_item(new_item)

        return {"message": "Data submitted successfully!", "data": new_item}

    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get all responses
@app.get("/responses/")
def get_responses():
    items = list(container.read_all_items())
    return {"data": items}

# Get a specific response
@app.get("/response/{response_id}")
def get_response(response_id: str):
    try:
        response = container.read_item(item=response_id, partition_key=response_id)
        return response
    except exceptions.CosmosHttpResponseError:
        raise HTTPException(status_code=404, detail="Response not found")

# Update a response
@app.put("/update/{response_id}")
def update_response(response_id: str, response: UserSubmission):
    try:
        updated_item = {
            "id": response_id,
            "name": response.name,
            "email": response.email,
            "company": response.company,
            "file_url": response.file_url
        }
        container.replace_item(item=response_id, body=updated_item)
        return {"message": "Survey response updated successfully!", "data": updated_item}
    except exceptions.CosmosHttpResponseError:
        raise HTTPException(status_code=500, detail="Failed to update response")

# Delete a response
@app.delete("/delete/{response_id}")
def delete_response(response_id: str):
    try:
        container.delete_item(item=response_id, partition_key=response_id)
        return {"message": "Survey response deleted successfully!"}
    except exceptions.CosmosHttpResponseError:
        raise HTTPException(status_code=404, detail="Response not found")

# Main entry point for local testing
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
