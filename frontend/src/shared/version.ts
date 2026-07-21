/**
 * Single source of truth for the app version and the in-app changelog.
 *
 * `APP_VERSION` is the full semver rendered in badges and menus
 * (`v4.0.0`); each `CHANGELOG` entry uses the short `major.minor` form
 * rendered as `v4.0` section chips. Entries are ordered newest first —
 * `ChangelogDialog` renders the array as-is. All copy here is
 * user-facing Spanish (see STYLE_GUIDE.md, "Copy register").
 */

export interface AppVersionEntry {
  /** Short `major.minor` form, e.g. `"4.0"` — rendered as a `v4.0` chip. */
  version: string;
  /** One-line theme of the release. */
  title: string;
  /** Optional ISO date — omitted when the release date is not tracked. */
  date?: string;
  /** Concise user-facing highlights (3–6 per version). */
  items: string[];
}

export const APP_VERSION = "4.0.0";

export const CHANGELOG: AppVersionEntry[] = [
  {
    version: "4.0",
    title: "Documentos desde ejemplos y relacionados",
    items: [
      "Cree plantillas desde un documento ejemplo, seleccionando el texto",
      "Documentos relacionados por plantilla que comparten variables (ej. contrato + recibo)",
      "Generación conjunta de varios documentos a la vez",
      "Versión visible en cada documento generado",
      "Descarga de la plantilla de cualquier versión",
      "Adjunte documentos relacionados desde un ejemplo, reutilizando variables",
    ],
  },
  {
    version: "3.0",
    title: "Datos inteligentes",
    items: [
      "Datos guardados por plantilla para reutilizar valores",
      "Variables calculadas: fórmulas y monto en letras",
      "Vista previa del documento con marca de agua",
      "Editor de documento completo",
      "Guía de plantillas y ayudas en pantalla",
    ],
  },
  {
    version: "2.0",
    title: "Organización y colaboración",
    items: [
      "Plantillas privadas con compartir por usuario",
      "Límites de uso por plan",
      "Carpetas personales para organizar plantillas",
      "Renombrar y describir plantillas",
      "Vista de tabla y paginación",
    ],
  },
  {
    version: "1.0",
    title: "Base del sistema",
    items: [
      "Plantillas .docx con variables {{ }}",
      "Generación individual y masiva desde Excel",
      "Exportación a PDF",
      "Multi-empresa con roles: admin, creador y generador",
      "Auditoría de acciones",
    ],
  },
];
