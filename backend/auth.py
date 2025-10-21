import logging
from datetime import datetime
from fastapi import APIRouter, Request
from models import User, SessionLocal, pwd_context

logger = logging.getLogger("auth")
router = APIRouter()

@router.post("/register")
async def register_user(request: Request):
    try:
        data = await request.json()
        logger.info(f"Datos de registro recibidos: {data}")
        
        nombre = data.get("nombre")
        email = data.get("email")
        password = data.get("password")
        
        if not all([nombre, email, password]):
            logger.error(f"Campos faltantes en registro: {data}")
            return {"success": False, "message": "Todos los campos son requeridos"}
        
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
        
        if not email or not password:
            logger.error("Email o contraseña faltantes")
            return {"success": False, "message": "Email y contraseña son requeridos"}
        
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
