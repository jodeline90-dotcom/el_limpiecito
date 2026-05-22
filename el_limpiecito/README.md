# 🧹 El Limpiecito — Tienda Online (PHP & MySQL)
---

## 📁 Estructura del Proyecto

```
el_limpiecito/
├── api/
│   ├── config.example.php       # Ejemplo de configuración (renombrar a config.php)
│   ├── db.php                   # Conexión a la base de datos usando PDO
│   ├── auth.php                 # Login, registro y sesiones de usuario
│   ├── productos.php            # Obtención y edición de productos
│   ├── carrito.php              # Gestión del carrito de compras
│   ├── pedidos.php              # Creación de pedidos y transacciones
│   ├── usuarios.php             # Direcciones y perfil de usuario
│   ├── admin.php                # Consultas para el panel de administración
│   ├── pagos.php                # Integración con Stripe
│   ├── helpers.php              # Respuestas JSON comunes y validaciones
│   └── index.php                # Enrutador principal de la API
├── frontend/
│   └── index.html               # SPA del frontend (HTML, CSS y JS integrado)
├── sql/
│   └── el_limpiecito_mysql.sql  # Script de base de datos MySQL (Tablas y datos iniciales)
└── README.md                    # Este archivo
```

---

## Guía de Instalación y Ejecución Local (XAMPP)

Para que el proyecto funcione en tu computadora local, sigue estos sencillos pasos:

### 1. Requisitos Previos
* Tener instalado **XAMPP** (con soporte para PHP 8.x y MySQL/MariaDB).
* Tener **Git** instalado (opcional, para clonar el repositorio).

### 2. Clonar y ubicar el proyecto
Clona este repositorio o descarga el código fuente y coloca la carpeta `el_limpiecito` dentro del directorio `htdocs` de tu servidor local XAMPP:
* **Windows:** `C:\xampp\htdocs\el_limpiecito`
* **macOS:** `/Applications/XAMPP/xamppfiles/htdocs/el_limpiecito`

### 3. Activar XAMPP
Abre el panel de control de XAMPP e inicia los siguientes servicios:
1. **Apache** (Servidor Web)
2. **MySQL** (Base de Datos)

### 4. Crear e importar la base de datos
1. Abre tu navegador e ingresa a **phpMyAdmin**: [http://localhost/phpmyadmin](http://localhost/phpmyadmin).
2. Crea una nueva base de datos con el nombre **`el limpiecito`** (con cotejamiento `utf8mb4_general_ci`).
3. Ve a la pestaña **Importar**, selecciona el archivo ubicado en:
   `el_limpiecito/sql/el_limpiecito_mysql.sql`
4. Haz clic en **Importar** (en la parte inferior) para cargar todas las tablas y datos de prueba.

### 5. Configurar credenciales
1. Entra a la carpeta `el_limpiecito/api/`.
2. Copia el archivo `config.example.php` y nómbralo **`config.php`**.
3. Abre `config.php` en un editor de texto y asegúrate de que las credenciales coincidan con las de tu base de datos de XAMPP (por defecto, en XAMPP el usuario es `root` y no tiene contraseña).
   ```php
   define('DB_HOST', '127.0.0.1');
   define('DB_USER', 'root');
   define('DB_PASS', '');
   define('DB_NAME', 'el limpiecito');
   ```

### 6. Ejecutar la aplicación
Una vez configurado todo, abre tu navegador favorito y accede a:
 [**http://localhost/el_limpiecito/frontend/index.html**](http://localhost/el_limpiecito/frontend/index.html)

El frontend detectará automáticamente la ruta relativa de la API (`/el_limpiecito/api/`) para comunicarse con la base de datos.

---

## Cuentas de Acceso de Prueba

El script SQL incluye cuentas de prueba precargadas para evaluar el funcionamiento del sistema:

* **Administrador (Panel de Control completo):**
  * **Usuario:** `admin@ellimpiecito.com`
  * **Contraseña:** `admin123`
* **Cliente (Tienda y pedidos):**
  * **Usuario:** `cliente@ellimpiecito.com`
  * **Contraseña:** `cliente123`
