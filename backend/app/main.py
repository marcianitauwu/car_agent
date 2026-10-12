from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.api.chat import router as chat_router

app = FastAPI(title='Car Agents API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
app.include_router(chat_router)

@app.get('/')
def home():
    return RedirectResponse('/docs')

@app.get('/health')
def health():
    return {'status': 'ok', 'message': 'Hola Sami, si, el backend está funcionando correctamente.'}
