import { useState } from "react";
import {
  BookOpen,
  Check,
  X,
  AlertTriangle,
  Folder,
  Pencil,
  Trash2,
  LayoutGrid,
  List as ListIcon,
  Search,
  MousePointerClick,
  Eye,
  Bookmark,
  Calculator,
  Type,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/**
 * Topic-based help center — see STYLE_GUIDE.md and the SigDoc onboarding
 * discovery pass. Each topic is a self-contained instructional section;
 * `initialTopic` lets a caller open the dialog directly on the tab most
 * relevant to the screen it's mounted on (e.g. the generation editor opens
 * straight to "Generar documentos").
 */
export type GuideTopic = "upload" | "organize" | "generate" | "computed";

interface TemplateGuideButtonProps {
  /** Which topic tab is active when the dialog opens. Defaults to "upload". */
  initialTopic?: GuideTopic;
  /** Icon-only trigger (with a `title` tooltip) for tight toolbars — e.g. the
   * generation editor's document header. */
  compact?: boolean;
}

export function TemplateGuideButton({
  initialTopic = "upload",
  compact = false,
}: TemplateGuideButtonProps) {
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState<GuideTopic>(initialTopic);

  function handleOpenChange(next: boolean) {
    setOpen(next);
    // Every open lands on the caller's most relevant topic, regardless of
    // wherever the user navigated to before closing it last time.
    if (next) setTopic(initialTopic);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button
            type="button"
            variant="outline"
            size={compact ? "icon-sm" : "sm"}
            title="Guía"
            aria-label={compact ? "Guía" : undefined}
          />
        }
      >
        <BookOpen className={compact ? "size-4" : "mr-2 size-4"} />
        {!compact && "Guía"}
      </DialogTrigger>
      <GuideDialogContent topic={topic} onTopicChange={setTopic} />
    </Dialog>
  );
}

function GuideDialogContent({
  topic,
  onTopicChange,
}: {
  topic: GuideTopic;
  onTopicChange: (topic: GuideTopic) => void;
}) {
  return (
    <DialogContent className="flex max-h-[85vh] flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
      <DialogHeader className="border-b border-[rgba(195,198,215,0.20)] px-6 py-5">
        <DialogTitle className="text-xl font-bold tracking-tight">
          Guía de SigDoc
        </DialogTitle>
        <DialogDescription>
          Aprenda a subir plantillas, organizarlas, generar documentos y
          configurar variables calculadas.
        </DialogDescription>
      </DialogHeader>

      <Tabs
        value={topic}
        onValueChange={(value) => onTopicChange(value as GuideTopic)}
        className="min-h-0 flex-1 gap-0"
      >
        <TabsList
          variant="line"
          className="h-auto w-full justify-start gap-1 rounded-none border-b border-[rgba(195,198,215,0.20)] bg-transparent px-6 py-0"
        >
          <TabsTrigger value="upload" className="py-2.5">
            Subir plantillas
          </TabsTrigger>
          <TabsTrigger value="organize" className="py-2.5">
            Organizar
          </TabsTrigger>
          <TabsTrigger value="generate" className="py-2.5">
            Generar documentos
          </TabsTrigger>
          <TabsTrigger value="computed" className="py-2.5">
            Variables calculadas
          </TabsTrigger>
        </TabsList>

        <div className="overflow-y-auto px-6 py-6">
          <TabsContent value="upload" className="flex flex-col gap-7">
            <UploadTopic />
          </TabsContent>
          <TabsContent value="organize" className="flex flex-col gap-7">
            <OrganizeTopic />
          </TabsContent>
          <TabsContent value="generate" className="flex flex-col gap-7">
            <GenerateTopic />
          </TabsContent>
          <TabsContent value="computed" className="flex flex-col gap-7">
            <ComputedTopic />
          </TabsContent>
        </div>
      </Tabs>
    </DialogContent>
  );
}

// ---------------------------------------------------------------------------
// (a) Subir plantillas — existing content, kept verbatim.
// ---------------------------------------------------------------------------

function UploadTopic() {
  return (
    <>
      {/* Variables básicas */}
      <section>
        <div className="sd-meta mb-2">Variables básicas</div>
        <p className="m-0 mb-3 leading-[1.55] text-[var(--fg-2)]">
          Use llaves dobles con espacios para definir una variable.
        </p>
        <CodeBlock>
          <>
            {"Estimado "}
            <CodeVar>{"{{ nombre }}"}</CodeVar>
            {",\n"}
            {"Por la presente se notifica que el monto de "}
            <CodeVar>{"{{ monto }}"}</CodeVar>
            {"\nfue aprobado el día "}
            <CodeVar>{"{{ fecha }}"}</CodeVar>
            {"."}
          </>
        </CodeBlock>
        <div className="mt-3 flex flex-col gap-1.5">
          <Rule type="do">
            Use espacios dentro de las llaves: <Mono>{"{{ nombre }}"}</Mono>
          </Rule>
          <Rule type="dont">
            No omita los espacios: <Mono tone="error">{"{{nombre}}"}</Mono> — podría no ser detectado
          </Rule>
        </div>
      </section>

      {/* Reglas de nombres */}
      <section>
        <div className="sd-meta mb-2">Reglas de nombres</div>
        <div className="flex flex-col gap-1.5">
          <Rule type="do">
            Minúsculas con guiones bajos: <Mono>{"{{ nombre_completo }}"}</Mono>
          </Rule>
          <Rule type="do">
            Nombres descriptivos: <Mono>{"{{ fecha_emision }}"}</Mono>
          </Rule>
          <Rule type="dont">
            Evite espacios en los nombres: <Mono tone="error">{"{{ nombre completo }}"}</Mono>
          </Rule>
          <Rule type="dont">
            Evite acentos y caracteres especiales: <Mono tone="error">{"{{ año }}"}</Mono>
          </Rule>
          <Rule type="do">
            Use solo ASCII: <Mono>{"{{ anio }}"}</Mono>
          </Rule>
        </div>
      </section>

      {/* Formato */}
      <section>
        <div className="sd-meta mb-2">Consejos de formato</div>
        <p className="m-0 mb-3 leading-[1.55] text-[var(--fg-2)]">
          El marcador hereda el formato del texto circundante en Word: negrita, fuente, tamaño, color y alineación se preservan.
        </p>
        <Banner variant="warn" icon={<AlertTriangle className="size-4 shrink-0" />}>
          <div>
            <strong className="font-semibold">Importante.</strong> Mantenga el mismo formato en toda la variable. Si parte de <Mono>{"{{ variable }}"}</Mono> está en negrita y parte no, Word la separa internamente y SigDoc no la detectará.
          </div>
        </Banner>
      </section>

      {/* Variables en tablas */}
      <section>
        <div className="sd-meta mb-2">Variables en tablas</div>
        <p className="m-0 mb-3 leading-[1.55] text-[var(--fg-2)]">
          Puede colocar variables dentro de celdas. Cada celda admite una o más.
        </p>
        <div className="overflow-hidden rounded-lg ring-1 ring-[rgba(195,198,215,0.30)]">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-muted)]">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-[var(--fg-1)]">Campo</th>
                <th className="px-3 py-2 text-left font-semibold text-[var(--fg-1)]">Valor</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Nombre", "{{ nombre }}"],
                ["Fecha", "{{ fecha }}"],
                ["Monto", "{{ monto }}"],
              ].map(([k, v]) => (
                <tr key={k} className="border-t border-[rgba(195,198,215,0.20)]">
                  <td className="px-3 py-2">{k}</td>
                  <td className="px-3 py-2 font-mono text-xs text-[var(--primary)]">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Headers/footers */}
      <section>
        <div className="sd-meta mb-2">Encabezados y pies de página</div>
        <p className="m-0 leading-[1.55] text-[var(--fg-2)]">
          Las variables también se detectan y reemplazan en encabezados y pies de página, igual que en el cuerpo.
        </p>
      </section>

      {/* Ejemplo */}
      <section>
        <div className="sd-meta mb-2">Ejemplo completo</div>
        <p className="m-0 mb-3 leading-[1.55] text-[var(--fg-2)]">
          Así se ve una plantilla de contrato típica:
        </p>
        <CodeBlock>{ExampleContract()}</CodeBlock>
        <p className="mt-2 text-xs text-[var(--fg-3)]">
          Esta plantilla tiene <strong>10 variables</strong> que SigDoc detectará automáticamente al subirla.
        </p>
      </section>

      {/* Checklist */}
      <section>
        <div className="sd-meta mb-2">Lista de verificación pre-subida</div>
        <ul className="flex flex-col gap-2 p-0">
          {[
            "Guarde el documento como .docx (no .doc ni .pdf).",
            "Use la sintaxis {{ variable }} con espacios dentro de las llaves.",
            "Use minúsculas_con_guiones_bajos para los nombres.",
            "Evite acentos y caracteres especiales en los nombres.",
            "Aplique formato uniforme a todo el marcador.",
            "Pruebe primero con una plantilla simple.",
          ].map((line) => (
            <li key={line} className="flex items-start gap-2 text-[var(--fg-2)]">
              <Check className="mt-0.5 size-4 shrink-0 text-[#059669]" />
              <span>{line}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// (b) Organizar — folders, rename, views, search/pagination.
// ---------------------------------------------------------------------------

function OrganizeTopic() {
  return (
    <>
      <section>
        <div className="sd-meta mb-2">Carpetas</div>
        <p className="m-0 mb-3 leading-[1.55] text-[var(--fg-2)]">
          Cada carpeta es personal — organiza sus propias plantillas y no
          afecta lo que ven otros usuarios. Las carpetas son de un único
          nivel: no admiten subcarpetas.
        </p>
        <div className="flex flex-col gap-1.5">
          <Rule type="do">
            Use <Folder className="mb-0.5 inline size-3.5" /> «Sin carpeta»
            para ver las plantillas que todavía no clasificó.
          </Rule>
          <Rule type="do">
            Al eliminar una carpeta: las plantillas no se eliminan; quedan
            sin carpeta.
          </Rule>
        </div>
      </section>

      <section>
        <div className="sd-meta mb-2">Renombrar y eliminar carpetas</div>
        <p className="m-0 leading-[1.55] text-[var(--fg-2)]">
          Pase el cursor sobre una carpeta en la barra lateral para ver los
          botones <Pencil className="mb-0.5 inline size-3.5" /> Renombrar y{" "}
          <Trash2 className="mb-0.5 inline size-3.5" /> Eliminar.
        </p>
      </section>

      <section>
        <div className="sd-meta mb-2">Vista de tarjetas o de tabla</div>
        <p className="m-0 leading-[1.55] text-[var(--fg-2)]">
          Alterne entre{" "}
          <LayoutGrid className="mb-0.5 inline size-3.5" /> vista de tarjetas
          y <ListIcon className="mb-0.5 inline size-3.5" /> vista de tabla con
          los botones junto al buscador. La preferencia se recuerda entre
          visitas.
        </p>
      </section>

      <section>
        <div className="sd-meta mb-2">Buscar y paginar</div>
        <p className="m-0 leading-[1.55] text-[var(--fg-2)]">
          <Search className="mb-0.5 inline size-3.5" /> Escriba en el buscador
          para filtrar por nombre. Los resultados se muestran de a 20
          plantillas por página; use los botones «Anterior» y «Siguiente»
          para navegar entre páginas.
        </p>
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// (c) Generar documentos — inline editing, preview, presets.
// ---------------------------------------------------------------------------

function GenerateTopic() {
  return (
    <>
      <section>
        <div className="sd-meta mb-2">Edición en línea</div>
        <p className="m-0 mb-3 leading-[1.55] text-[var(--fg-2)]">
          El documento se muestra tal como quedará, con cada marcador
          resaltado como una etiqueta.
        </p>
        <div className="flex flex-col gap-1.5">
          <Rule type="do">
            <MousePointerClick className="mb-0.5 inline size-3.5" /> Haga clic
            sobre un marcador para completarlo.
          </Rule>
          <Rule type="do">
            Presione <Mono>Enter</Mono> para confirmar el valor y avanzar
            automáticamente al siguiente marcador pendiente.
          </Rule>
        </div>
      </section>

      <section>
        <div className="sd-meta mb-2">Vista previa</div>
        <p className="m-0 leading-[1.55] text-[var(--fg-2)]">
          <Eye className="mb-0.5 inline size-3.5" /> «Vista previa» genera un
          PDF de borrador con marca de agua; el documento final, una vez
          generado, no la incluye.
        </p>
      </section>

      <section>
        <div className="sd-meta mb-2">Datos guardados (presets)</div>
        <p className="m-0 leading-[1.55] text-[var(--fg-2)]">
          <Bookmark className="mb-0.5 inline size-3.5" /> Use «Guardar datos»
          para conservar los valores ya completados y reutilizarlos la
          próxima vez que genere un documento con esta plantilla — útil para
          clientes recurrentes. Cárguelos desde el selector «Datos guardados»
          en la parte superior del editor.
        </p>
      </section>
    </>
  );
}

// ---------------------------------------------------------------------------
// (d) Variables calculadas — formulas + número a literal.
// ---------------------------------------------------------------------------

function ComputedTopic() {
  return (
    <>
      <section>
        <div className="sd-meta mb-2">Fórmulas</div>
        <p className="m-0 mb-3 leading-[1.55] text-[var(--fg-2)]">
          Una variable calculada de tipo <strong>Fórmula</strong> toma el
          valor de otra variable numérica (el origen) y le aplica un
          operador con una constante: <Mono>origen [operador] constante</Mono>. El resultado siempre se redondea a 2 decimales.
        </p>
        <CodeBlock>{"origen: monto = 1000\noperador: ×\noperando: 1.21\n\nresultado: 1210.00"}</CodeBlock>
        <div className="mt-3 flex flex-col gap-1.5">
          <Rule type="do">
            La variable de origen debe ser de tipo número (entero o decimal).
          </Rule>
          <Rule type="dont">
            No use <Mono tone="error">÷</Mono> con un operando igual a 0.
          </Rule>
        </div>
      </section>

      <section>
        <div className="sd-meta mb-2">Número a literal</div>
        <p className="m-0 mb-3 leading-[1.55] text-[var(--fg-2)]">
          <Type className="mb-0.5 inline size-3.5" /> Convierte un monto
          numérico en su expresión en letras, con los centavos como fracción.
          Requiere una variable de origen numérica.
        </p>
        <CodeBlock>{"1500.50 → UN MIL QUINIENTOS 50/100"}</CodeBlock>
      </section>

      <section>
        <div className="sd-meta mb-2">Cómo activarlas</div>
        <p className="m-0 leading-[1.55] text-[var(--fg-2)]">
          <Calculator className="mb-0.5 inline size-3.5" /> Abra la variable
          desde la pestaña Variables y active{" "}
          <strong className="font-semibold">Variable calculada</strong>. Una
          vez activada, el valor se calcula automáticamente al generar el
          documento y no podrá ingresarse manualmente.
        </p>
      </section>
    </>
  );
}

function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre className="m-0 overflow-x-auto whitespace-pre-wrap rounded-[10px] bg-[#0f172a] p-3.5 font-mono text-xs leading-[1.7] text-[#e0e7ff]">
      {children}
    </pre>
  );
}

function CodeVar({ children }: { children: React.ReactNode }) {
  return <span className="text-[#7dd3fc]">{children}</span>;
}

function Mono({ children, tone = "primary" }: { children: React.ReactNode; tone?: "primary" | "error" }) {
  return (
    <span
      className={`font-mono text-[12px] ${
        tone === "error" ? "text-[var(--destructive)]" : "text-[var(--primary)]"
      }`}
    >
      {children}
    </span>
  );
}

function Rule({ type, children }: { type: "do" | "dont"; children: React.ReactNode }) {
  const Icon = type === "do" ? Check : X;
  const color = type === "do" ? "text-[#059669]" : "text-[var(--destructive)]";
  return (
    <div className="flex items-start gap-2 text-[13px] text-[var(--fg-2)]">
      <Icon className={`mt-0.5 size-3.5 shrink-0 ${color}`} />
      <span>{children}</span>
    </div>
  );
}

function Banner({
  variant,
  icon,
  children,
}: {
  variant: "warn";
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  const tone =
    variant === "warn"
      ? "bg-[#fef3c7] text-[#78350f]"
      : "";
  return (
    <div className={`flex items-start gap-2.5 rounded-[10px] px-3.5 py-3 text-[13px] leading-[1.45] ${tone}`}>
      <span className="mt-px text-[#b45309]">{icon}</span>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function ExampleContract() {
  return `CONTRATO DE SERVICIOS

En la ciudad de {{ ciudad }}, a {{ fecha }},

ENTRE:
  {{ nombre_empresa }} (en adelante "La Empresa"),
  representada por {{ representante_legal }},
  con domicilio en {{ direccion_empresa }}

Y:
  {{ nombre_contratado }} (en adelante "El Contratado"),
  con documento de identidad {{ documento_identidad }}

Se acuerda lo siguiente:

1. El Contratado prestará servicios de {{ tipo_servicio }}
   por un período de {{ duracion_contrato }}.

2. La remuneración será de {{ monto_pago }} mensuales.

Firmas:

_____________________     _____________________
{{ nombre_empresa }}       {{ nombre_contratado }}`;
}
