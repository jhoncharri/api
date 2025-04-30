from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
import mysql.connector
from mysql.connector import Error
import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from typing import List


load_dotenv()

app = FastAPI()


origins = [
    "http://localhost:5173", "capacitor://localhost", "https://localhost" 
]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
 

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la base de datos
db_config = {
    'host': 'bk2kuavuvta1268uzb4r-mysql.services.clever-cloud.com',
    'user': 'us311bbvz2s54cxs',
    'password': 'ZELlAvXOk0vaXSWApYcF',
    'database': 'bk2kuavuvta1268uzb4r'
}

SECRET_KEY = os.getenv("SECRET_KEY", "tu_clave_secreta")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 5  # Expiración del token en minutos

# Función para generar un token JWT
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Función para verificar el token
def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    


# Modelos de datos
class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    
    # Modelos de datos
class UpdateProfileRequest(BaseModel):
    name: str = None  
    newPassword: str = None  
    phone: str
    city: str
    address: str
    bio: str
    
class Message(BaseModel):
    sender: str
    message: str
    timestamp: str
    id: str

class ConversationRequest(BaseModel):
    conversation: List[Message]

# Ruta de login
@app.post("/login")
async def login(request: LoginRequest):
    print(request)
    email = request.email
    password = request.password

    try:
        with mysql.connector.connect(**db_config) as conn:
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM login WHERE email = %s AND password = %s"
            cursor.execute(query, (email, password))
            user = cursor.fetchone()

            if user:
                access_token_expires = timedelta(hours=1)
                access_token = create_access_token(
                    data={"sub": user["email"], "rol":user["rol"]},  # Solo el email
                    expires_delta=access_token_expires
                )
                print ("---------------------------",user["rol"])
                return {
                    "rol": user["rol"],
                    "success": True,
                    "message": "Inicio de sesión exitoso",
                    "redirect": "/administrador",
                    "access_token": access_token
                }
            else:
                raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# Ruta de signup
@app.post("/signup")
async def signup(request: SignupRequest):
    name = request.name
    email = request.email
    password = request.password

    try:
        # Usar with para garantizar que se cierre correctamente la conexión y el cursor
        with mysql.connector.connect(**db_config) as conn:
            cursor = conn.cursor()

            # Verificar si el email ya está registrado
            check_query = "SELECT email FROM login WHERE email = %s"
            cursor.execute(check_query, (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                raise HTTPException(status_code=400, detail="El correo ya está registrado")

            # Insertar nuevo usuario con contraseña en texto plano
            insert_query = "INSERT INTO login (name, email, password) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, (name, email, password))
            conn.commit()

            return {"success": True, "message": "Usuario registrado exitosamente", "redirect": "http://localhost:5173/login"}
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
   

# Ruta para obtener el perfil
@app.get("/profile")
async def get_profile(payload: dict = Depends(verify_token)):
    user_email = payload["sub"] # Obtener el email del payload del JWT

    try:
        with mysql.connector.connect(**db_config) as conn:
            cursor = conn.cursor(dictionary=True)
            # Consulta para obtener los datos del perfil
            query = "SELECT name, email, password, phone, city, address, bio FROM login WHERE email = %s"
            cursor.execute(query, (user_email,))
            user_profile = cursor.fetchone()

            if user_profile:
                return {
                    "success": True,
                    "profile": user_profile
                }
            else:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# Ruta para actualizar el perfil
@app.post("/update-profile")
async def update_profile(request: UpdateProfileRequest, payload: dict = Depends(verify_token)):
    user_email = payload["sub"]  # Obtener el email del payload del JWT

    try:
        with mysql.connector.connect(**db_config) as conn:
            cursor = conn.cursor(dictionary=True)  # Asegúrate de que el cursor devuelva diccionarios

            # Consulta para obtener los datos actuales del usuario
            query = "SELECT name, password, phone, city, address, bio FROM login WHERE email = %s"
            cursor.execute(query, (user_email,))
            current_data = cursor.fetchone()

            if not current_data:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            # Verificar si hay cambios en los datos
            is_data_changed = False
            if request.name and request.name != current_data['name']:
                is_data_changed = True
            if request.newPassword and request.newPassword != current_data['password']:
                is_data_changed = True
            if request.phone and request.phone != current_data['phone']:
                is_data_changed = True
            if request.city and request.city != current_data['city']:
                is_data_changed = True
            if request.address and request.address != current_data['address']:
                is_data_changed = True
            if request.bio and request.bio != current_data['bio']:
                is_data_changed = True

            if not is_data_changed:
                return {"success": False, "message": "No se detectaron cambios en el perfil."}

            # Si se proporciona una nueva contraseña, la actualizamos
            if request.newPassword:
                update_query = """
                    UPDATE login 
                    SET name = %s, password = %s, phone = %s, city = %s, address = %s, bio = %s 
                    WHERE email = %s
                """
                cursor.execute(update_query, (request.name, request.newPassword, request.phone, request.city, request.address, request.bio, user_email))
            else:
                update_query = """
                    UPDATE login 
                    SET name = %s, phone = %s, city = %s, address = %s, bio = %s 
                    WHERE email = %s
                """
                cursor.execute(update_query, (request.name, request.phone, request.city, request.address, request.bio, user_email))

            conn.commit()

            # Verificar si alguna fila fue afectada
            if cursor.rowcount > 0:
                return {"success": True, "message": "Perfil actualizado correctamente"}
            else:
                return {"success": False, "message": "No se pudo actualizar el perfil. Los datos no cambiaron."}

    except Error as e:
        print(f"Error de base de datos: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        print(f"Error interno: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    
@app.post("/contact")
async def contact(
    firstname: str = Form(...),
    lastname: str = Form(...),
    email: EmailStr = Form(...),
    phone: str = Form(None),
    message: str = Form(...),
    
):

    try:
        # Guardar mensaje en la base de datos
        with mysql.connector.connect(**db_config) as conn:
            cursor = conn.cursor()
            insert_query = """
                INSERT INTO contact_messages (
                    firstname, lastname, email, phone, message
                ) VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(
                insert_query,
                (firstname, lastname, email, phone, message)
            )
            conn.commit()

        return {"success": True, "message": "Tu mensaje ha sido enviado exitosamente"}
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# Ruta para iniciar una nueva conversación
@app.post("/new-conversation")
async def new_conversation(payload: dict = Depends(verify_token)):
    user_email = payload["sub"]  # Obtener el email del payload del JWT
    
    try:
        # Limpiar el estado del chatbot aquí si es necesario
        # Aquí puedes agregar lógica adicional para "resetear" el chatbot, como limpiar su memoria de respuestas anteriores

        # Retornar un estado inicial vacío (puedes modificar este comportamiento)
        return {"success": True, "message": "Nueva conversación iniciada. ¿En qué te puedo ayudar?"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al iniciar la nueva conversación: {str(e)}")


@app.post("/validate-token")
async def validate_token(token: str = Depends(oauth2_scheme)):
    try:
        # Verificar el token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"success": True, "message": "Token válido"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


@app.post("/save-conversation")
async def save_conversation(
    conversation: ConversationRequest,
    payload: dict = Depends(verify_token)
):
    try:
        # Verificar si el token contiene 'sub' (usualmente el correo del usuario)
        if "sub" not in payload:
            raise HTTPException(status_code=401, detail="El token no contiene el campo 'sub'")

        user_email = payload["sub"]
        print("Email obtenido del token:", user_email)

        # Formatear la conversación
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conversation_text = ""
        for message in conversation.conversation:
            conversation_text += f"{message.sender}: {message.message}\n"

        # Conexión y operaciones con la base de datos
        with mysql.connector.connect(**db_config) as conn:
            cursor = conn.cursor()

            # Buscar user_id desde el email
            cursor.execute("SELECT user_id FROM login WHERE email = %s", (user_email,))
            result = cursor.fetchone()
            if result is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado en la base de datos")

            user_id = result[0]

            # Insertar la conversación
            cursor.execute(
                "INSERT INTO conversations (user_id, sender, message, timestamp) VALUES (%s, %s, %s, %s)",
                (user_id, user_email, conversation_text, timestamp)
            )
            conn.commit()

        return {"success": True, "message": "La conversación ha sido guardada exitosamente."}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


    
    
@app.get("/get-conversations")
async def get_conversations(payload: dict = Depends(verify_token)):
    try:
        # Verificar si el payload tiene el campo 'sub' (usuario autenticado)
        if "sub" not in payload:
            raise HTTPException(status_code=401, detail="El token no contiene el campo 'sub'")

        user_email = payload["sub"]  # Obtener el email del payload del JWT
        print("Email obtenido del token:", user_email)

        # Recuperar todas las conversaciones desde la base de datos
        with mysql.connector.connect(**db_config) as conn:
            cursor = conn.cursor()

            # Eliminar el filtro por usuario (sender), para obtener todas las conversaciones
            cursor.execute("SELECT * FROM conversations ORDER BY timestamp DESC")
            rows = cursor.fetchall()

        # Retornar las conversaciones en formato JSON
        conversations = [
            {"id": row[0], "sender": row[1], "message": row[2], "timestamp": row[3]} for row in rows
        ]
        return {"conversations": conversations}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.delete("/delete-conversation/{convo_id}")
async def delete_conversation(convo_id: int, payload: dict = Depends(verify_token)):
    try:
        # Verificar si el payload tiene el campo 'sub' (usuario autenticado)
        if "sub" not in payload:
            raise HTTPException(status_code=401, detail="El token no contiene el campo 'sub'")

        user_email = payload["sub"]  # Obtener el email del payload del JWT
        print("Email obtenido del token:", user_email)

        # Recuperar la conversación a eliminar desde la base de datos para verificar si pertenece al usuario
        with mysql.connector.connect(**db_config) as conn:
            cursor = conn.cursor()

            # Verificar si la conversación existe y si el 'sender' coincide con el usuario
            cursor.execute("SELECT * FROM conversations WHERE id = %s", (convo_id,))
            convo = cursor.fetchone()

            if not convo:
                raise HTTPException(status_code=404, detail="Conversación no encontrada")
            
            if convo[1] != user_email:  # convo[1] es el 'sender' (email del usuario)
                raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta conversación")

            # Eliminar la conversación de la base de datos
            cursor.execute("DELETE FROM conversations WHERE id = %s", (convo_id,))
            conn.commit()

        return {"message": "Conversación eliminada con éxito"}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")



@app.get("/chatbot")
async def chatbot_endpoint(payload: dict = Depends(verify_token)):
    try:
        user_email = payload.get("sub", "desconocido")  # Ejemplo de obtener información del token
        return {"message": f"Hola {user_email}, el chatbot está funcionando correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    

