from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_DETAILS = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "ticketu_entradas_db")

client = None
database = None

async def connect_to_mongo():
    global client, database
    try:
        print(f"Conectando a MongoDB en: {MONGO_DETAILS}")
        client = AsyncIOMotorClient(MONGO_DETAILS)
        database = client[DB_NAME]
        print(f"Conexión exitosa a la base de datos: {DB_NAME}")
    except Exception as e:
        print(f"Error conectando a MongoDB: {e}")

async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("Conexión a MongoDB cerrada.")

def get_database():
    return database
