import logging
import os
import httpx
from datetime import datetime
from fastapi import APIRouter, Request
from models import User, SessionLocal, pwd_context

logger = logging.getLogger("auth")
router = APIRouter()

# Cloudflare Turnstile Secret Key (desde variable de entorno)
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

async def verify_turnstile(token: str, ip: str = None) -> bool:
    """Verificar token de Cloudflare Turnstile"""
    if not TURNSTILE_SECRET_KEY:
        logger.warning("⚠️ TURNSTILE_SECRET_KEY no configurada, omitiendo verificación")
        return True  # Si no hay secret key, permitir (para desarrollo)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": TURNSTILE_SECRET_KEY,
                    "response": token,
                    "remoteip": ip
                }
            )
            result = response.json()
            logger.info(f"Turnstile verification result: {result}")
            return result.get("success", False)
    except Exception as e:
        logger.error(f"Error verificando Turnstile: {e}")
        return False

@router.post("/register")
async def register_user(request: Request):
    try:
        data = await request.json()
        logger.info(f"Datos de registro recibidos: {data}")
        
        nombre = data.get("nombre")
        email = data.get("email")
        password = data.get("password")
        turnstile_token = data.get("turnstile_token")
        
        if not all([nombre, email, password]):
            logger.error(f"Campos faltantes en registro: {data}")
            return {"success": False, "message": "Todos los campos son requeridos"}
        
        # Verificar Turnstile
        client_ip = request.client.host if request.client else None
        if not await verify_turnstile(turnstile_token, client_ip):
            logger.warning(f"Turnstile verification failed for register: {email}")
            return {"success": False, "message": "Verificación de seguridad fallida. Por favor, recarga la página."}
        
        # DEBUG: Ver password antes de procesarlo
        logger.info(f"🔍 Password ORIGINAL: len={len(password)}, bytes={len(password.encode('utf-8'))}")
        
        # Bcrypt tiene un límite de 72 BYTES - truncar INMEDIATAMENTE
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            logger.warning(f"⚠️ Password demasiado largo ({len(password_bytes)} bytes), truncando a 72 bytes")
            password_bytes = password_bytes[:72]
            password = password_bytes.decode('utf-8', errors='ignore')
            logger.info(f"✅ Password truncado: len={len(password)}, bytes={len(password.encode('utf-8'))}")
        else:
            logger.info(f"✅ Password dentro del límite: {len(password_bytes)} bytes")
        
        with SessionLocal() as db:
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                logger.warning(f"Email ya registrado: {email}")
                return {"success": False, "message": "El email ya está registrado"}
            
            try:
                logger.info(f"🔐 Intentando hashear password de {len(password)} chars / {len(password.encode('utf-8'))} bytes")
                hashed_password = pwd_context.hash(password)
                logger.info(f"✅ Password hasheado exitosamente")
                new_user = User(
                    nombre=nombre,
                    email=email,
                    password=hashed_password,
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                
                logger.info(f"Usuario registrado exitosamente: {email}")
                return {
                    "success": True, 
                    "message": "Usuario registrado exitosamente",
                    "user": {
                        "id": new_user.id,
                        "nombre": new_user.nombre,
                        "email": new_user.email
                    }
                }
            except Exception as e:
                db.rollback()
                logger.error(f"Error al crear usuario: {str(e)}")
                return {"success": False, "message": f"Error al crear usuario: {str(e)}"}
    except Exception as e:
        logger.error(f"Error general en registro: {str(e)}")
        return {"success": False, "message": f"Error general: {str(e)}"}

@router.post("/login")
async def login_user(request: Request):
    try:
        data = await request.json()
        logger.info(f"Datos de login recibidos: {data}")
        
        email = data.get("email")
        password = data.get("password")
        turnstile_token = data.get("turnstile_token")
        
        if not email or not password:
            logger.error("Email o contraseña faltantes")
            return {"success": False, "message": "Email y contraseña son requeridos"}
        
        # Verificar Turnstile
        client_ip = request.client.host if request.client else None
        if not await verify_turnstile(turnstile_token, client_ip):
            logger.warning(f"Turnstile verification failed for {email}")
            return {"success": False, "message": "Verificación de seguridad fallida. Por favor, recarga la página."}
        
        # Bcrypt tiene un límite de 72 BYTES - truncar INMEDIATAMENTE
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
            password = password_bytes.decode('utf-8', errors='ignore')
        
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()
            
            if not user:
                logger.warning(f"Usuario no encontrado: {email}")
                return {"success": False, "message": "Credenciales incorrectas"}
            
            try:
                if not pwd_context.verify(password, user.password):
                    logger.warning(f"Contraseña incorrecta para: {email}")
                    return {"success": False, "message": "Credenciales incorrectas"}
                
                # Log user permissions for debugging
                logger.info(f"Usuario encontrado: {user.email}, permisos: {user.permisos}")
                
                # Ensure permisos has a default value
                permisos = user.permisos if user.permisos is not None else 'usuario'
                
                logger.info(f"Login exitoso: {email}, permisos asignados: {permisos}")
                return {
                    "success": True,
                    "user": {
                        "id": user.id,
                        "nombre": user.nombre,
                        "email": user.email,
                        "permisos": permisos
                    }
                }
            except Exception as e:
                logger.error(f"Error al verificar contraseña: {str(e)}")
                return {"success": False, "message": f"Error en autenticación: {str(e)}"}
    except Exception as e:
        logger.error(f"Error general en login: {str(e)}")
        return {"success": False, "message": f"Error general: {str(e)}"}

@router.post("/verify-role")
async def verify_role(request: Request):
    """
    Endpoint para verificar el rol de un usuario desde el servidor.
    Evita que el frontend confíe únicamente en localStorage.
    """
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            logger.warning("Verificación de rol sin user_id")
            return {"success": False, "is_admin": False, "message": "user_id requerido"}
        
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.warning(f"Usuario no encontrado para verificación: {user_id}")
                return {"success": False, "is_admin": False, "message": "Usuario no encontrado"}
            
            is_admin = user.permisos == 'admin'
            logger.info(f"Verificación de rol - Usuario: {user.email}, Es admin: {is_admin}")
            
            return {
                "success": True,
                "is_admin": is_admin,
                "user_id": user.id,
                "permisos": user.permisos
            }
    except Exception as e:
        logger.error(f"Error en verificación de rol: {str(e)}")
        return {"success": False, "is_admin": False, "message": f"Error: {str(e)}"}
