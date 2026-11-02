## Ejecución Pruebas de Calidad

### 1. Pruebas Funcionales (CA1 - Automáticas con Pytest):
Estas pruebas validan la lógica interna de las Historias de Usuario (Inventario, Historial y Seguridad).

- Activa el entorno virtual e instala las dependencias necesarias:
```pip install pytest pytest-asyncio httpx pytest-html```

- Desde la raíz del proyecto, ejecuta la suite con este comando para actualizar el reporte:
```python -m pytest tests/ -v --html=tests/evidencia_QA_CA1.html --self-contained-html```

- El resultado detallado se puede visualizar abriendo el archivo `evidencia_QA_CA1.html` en cualquier navegador.

### 2. Pruebas de Integración (CA2 - Contratos con Postman)
Estas pruebas validan la comunicación, contratos de datos y flujos del microservicio.

- Asegúrate de tener el servidor backend corriendo con:
```uvicorn main:app --reload```

- Abre postman e importa el archivo `tests/TicketU - QA Integracion.postman_collection.json`

- Uitliza el Collection Runner para ejecutar la carpeta completa. Las peticiones están configuradas para validar códigos de estado, reglas de negocio e integridad de los esquemas.
