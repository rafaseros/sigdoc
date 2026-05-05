# Handoff: SigDoc — Rediseño de gestión de plantillas y usuarios

## Overview
SigDoc es una aplicación interna de Clínica Foianini / CAINCO para gestionar plantillas `.docx` con marcadores `{{ variable }}` y generar documentos individuales o por lotes desde Excel.

Este paquete contiene el rediseño de las pantallas principales:
- Login
- Lista de plantillas (con búsqueda y subida)
- Detalle de plantilla (Información, Variables, Versiones, Compartido, Documentos)
- Generación individual y masiva
- Administración de Usuarios (con CRUD completo: crear, editar, baja)
- Auditoría
- Diálogos modales (subir, compartir, eliminar plantilla; crear, editar, dar de baja usuarios; guía de marcadores)

## About the Design Files
Los archivos en este bundle son **referencias de diseño creadas en HTML/React (Babel inline)** — prototipos que muestran el look-and-feel y comportamiento esperado. **No son código de producción para copiar directamente.**

El trabajo es **recrear estos diseños en tu repositorio existente** usando los patrones, librería de componentes y stack que ya tengas (probablemente React/Next.js, Vue, o lo que corresponda). Si tu codebase ya tiene un design system, adáptalo; si no, este handoff puede servir como base.

Los componentes están escritos como funciones React simples sin librerías externas — solo CSS plano. Esto facilita la portabilidad: la lógica y estructura son claras, solo hay que migrar los estilos a Tailwind / CSS Modules / styled-components / lo que uses.

## Fidelity
**High-fidelity (hifi).** Los mocks tienen colores exactos, tipografía Geist, espaciado y radios definidos, estados hover/active, validaciones y diff en vivo. Recréalos pixel-perfect usando los componentes y tokens existentes en tu codebase, o reutiliza el CSS plano provisto si vas a empezar de cero.

## Pantallas

### 1. Login (`src/screens-login.jsx`)
Formulario centrado con email + contraseña. Variante A: card con halos brand. Variante B: split panel con manifiesto de marca a la izquierda.

### 2. Plantillas (`src/screens-templates.jsx`)
Lista de plantillas. Variante A: tabla con columna autor + banner de onboarding. Variante B: grilla de tarjetas con stats arriba.
- Búsqueda en vivo por nombre
- Botón "Subir Plantilla" → abre `UploadDialog`
- Click en plantilla → navega al detalle

### 3. Detalle de Plantilla (`src/screens-detail.jsx`)
Header común con: badge de versión, tipo, nombre, descripción, autor, y action row con `Generar Documento` / `Generación Masiva` / `Compartir` / `Eliminar`.

Variante A: tabs horizontales. Variante B: sidebar lateral.

**Tabs:**
- **Información** — 2 columnas: detalles + actividad reciente | preview placeholder + resumen de uso (4 stats: documentos generados, usuarios con acceso, versiones, variables) + acceso a Guía. **Sin duplicar los CTAs del header.**
- **Variables** — Master/detail. Lista buscable a la izquierda; al seleccionar una variable, muestra a la derecha un editor (tipo + hint) y los **párrafos contextuales** donde aparece. La variable activa se resalta con chip ámbar; otras variables del mismo párrafo aparecen en chip gris muted.
- **Versiones** — Lista de versiones con badges de "Actual", autor, fecha, notas. Botones Descargar / Restaurar.
- **Compartido** — Tabla de usuarios con acceso, botón Compartir.
- **Documentos** — Historial de documentos generados (individual / masiva) con botón Descargar.

### 4. Generación Individual (`src/screens-generate.jsx`)
Formulario con todas las variables agrupadas por tipo + preview en vivo del documento.

### 5. Generación Masiva (`src/screens-generate.jsx`)
Stepper de 4 pasos: descargar template Excel → subir Excel → revisar → generar.

### 6. Usuarios (`src/screens-admin.jsx`)
Tabla de usuarios. Variante B agrega 4 stat cards arriba.
- Buscador
- Botón "Crear Usuario" → `CreateUserDialog`
- Por fila: editar (`EditUserDialog`), resetear contraseña (toast), dar de baja (`DeactivateUserDialog`)
- Toasts de feedback al completar acciones

### 7. Auditoría (`src/screens-admin.jsx`)
Variante A: tabla compacta con filtros. Variante B: stats arriba + timeline agrupada por día (Hoy / Esta semana / La semana pasada).

## Interacciones clave

### Diálogo: Crear Usuario (`CreateUserDialog`)
- Nombre + email (validación email regex)
- **Selector de rol como cards** (Admin / Creador / Generador) con icono, label y descripción
- Toggles: enviar invitación por correo (default ON), generar contraseña temporal (default OFF)
- Submit deshabilitado hasta que nombre ≥ 3 chars y email válido
- Loader spinner durante submit, luego onCreated callback

### Diálogo: Editar Usuario (`EditUserDialog`)
- Card de identidad (avatar + nombre + email + creado/última actividad)
- Editar nombre, rol (mismo card-picker), estado (segmented: Activa / Inactiva con descripciones)
- Email **no editable** (es ID permanente)
- **Diff en vivo de cambios pendientes** — muestra `Campo: anterior → nuevo` con strikethrough rojo y nuevo valor verde
- Acciones extra: resetear contraseña, cerrar sesiones activas
- Submit deshabilitado si no hay cambios

### Diálogo: Baja de Usuario (`DeactivateUserDialog`)
- Card de identidad + rol pill
- **Selector entre 2 modos:**
  - **Desactivar** (recomendado, tono ámbar): bloquea login, conserva plantillas, reversible
  - **Eliminar permanentemente** (tono rojo): borra cuenta, requiere reasignar plantillas, irreversible
- Si modo=eliminar y el usuario tiene plantillas → banner de error + Select obligatorio para reasignarlas a otro usuario activo
- Motivo de baja (Select)
- Confirmación: tipear `DESACTIVAR` o `ELIMINAR` según modo
- Botón rojo `danger-solid` solo en modo eliminar

### Variables tab — Resaltado contextual
- Mock data en `VARIABLE_CONTEXTS`: por cada variable, lista de párrafos `{ pagina, parrafo, texto }`
- Componente `ParagraphPreview` parsea el texto con regex `/(\{\{\s*[a-z_]+\s*\}\})/gi`
- Variable activa → clase `var-chip-active` (ámbar con sombra y borde)
- Otras variables → clase `var-chip-muted` (gris)

## Design Tokens

### Colores
```css
/* Brand */
--brand-primary: #004ac6;        /* azul principal CAINCO */
--brand-primary-hover: #003ea6;
--brand-secondary: #2563eb;      /* gradiente con primary */
--brand-soft: #dbe1ff;           /* fondos suaves */
--brand-soft-2: #b4c5ff;

/* Foreground */
--fg-1: #191c1e;                 /* texto principal */
--fg-2: #434655;                 /* texto secundario */
--fg-3: #515f74;                 /* texto muted */
--fg-4: #a0a4af;                 /* texto disabled */

/* Background */
--bg-page: linear-gradient(135deg, #f7f9fb 0%, #e0e7ff 100%);
--bg-surface: #ffffff;
--bg-subtle: #f7f9fb;
--bg-muted: #f2f4f6;
--border: rgba(195,198,215,0.30);

/* Semantic */
--success-bg: #d1fae5;  --success-fg: #065f46;  --success-solid: #059669;
--warn-bg:    #fef3c7;  --warn-fg:    #78350f;  --warn-solid:    #b45309;
--error-bg:   #ffdad6;  --error-fg:   #93000a;  --error-solid:   #ba1a1a;

/* Highlight (variable activa) */
--highlight-bg: linear-gradient(135deg, #fef3c7, #fde68a);
--highlight-border: #f59e0b;
```

### Tipografía
- **Sans:** `Geist` (Google Fonts), 300/400/500/600/700
- **Mono:** `Geist Mono`, 400/500
- Tamaños: 11px (tiny), 12.5px (small), 13.5px (body), 14px (label), 15-16px (h4), 18-20px (h3), 22-28px (h1/h2)

### Espaciado / Radius
- Border radius: 7px (small), 8px (default), 10-12px (cards), 999px (pills)
- Spacing común: 6, 8, 10, 12, 14, 18, 24
- Sombras: `0 4px 16px rgba(25,28,30,0.10)` (modal), `0 4px 12px rgba(0,74,198,0.30)` (botón gradient)

### Botones
- `btn-grad` — gradient azul, sombra brand (acción primaria)
- `btn-outline` — fondo blanco, borde sutil
- `btn-ghost` — transparente, hover azul
- `btn-danger` / `btn-danger-solid` — rojo

## State Management
Todo el state es local con `useState`. En tu app real usarás:
- React Query / SWR para fetch de plantillas/usuarios/auditoría
- Server actions o API routes para crear/editar/dar de baja usuarios
- Toasts via `sonner` o tu librería preferida

## Assets
- **Fonts:** Geist + Geist Mono (Google Fonts CDN)
- **Iconos:** SVG inline estilo Lucide en `src/icons.jsx` — reemplaza por `lucide-react` en tu proyecto
- **Sin imágenes** — todo es HTML/CSS

## Archivos incluidos en este bundle
- `SigDoc Redesign.html` — entry point del prototipo
- `src/` — todos los componentes JSX
- `assets/colors_and_type.css` — tokens base
- `src/app.css` — estilos del rediseño completo

## Recomendación de implementación con Claude Code

1. Clona tu repo y abre Claude Code en la raíz.
2. Pega el contenido de este folder en `docs/design/sigdoc-redesign/`.
3. Pídele a Claude Code:
   ```
   Lee docs/design/sigdoc-redesign/README.md y los archivos JSX/CSS.
   Implementa primero el módulo de Usuarios (UsersScreen + 3 diálogos)
   usando los componentes existentes de mi proyecto. Mantén la fidelidad
   visual de los mocks pero usa mi librería de UI (shadcn/MUI/etc).
   ```
4. Itera pantalla por pantalla. La de mayor complejidad lógica es **Variables tab** (parsing de párrafos con regex) — empieza por ahí si quieres validar el approach.
