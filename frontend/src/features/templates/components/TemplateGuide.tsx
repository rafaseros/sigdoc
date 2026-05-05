import { BookOpen, Check, X, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function TemplateGuideButton() {
  return (
    <Dialog>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>
        <BookOpen className="mr-2 size-4" />
        Guía de Plantillas
      </DialogTrigger>
      <GuideDialogContent />
    </Dialog>
  );
}

function GuideDialogContent() {
  return (
    <DialogContent className="max-h-[85vh] gap-0 overflow-y-auto p-0 sm:max-w-2xl">
      <DialogHeader className="border-b border-[rgba(195,198,215,0.20)] px-6 py-5">
        <DialogTitle className="text-xl font-bold tracking-tight">
          Cómo crear plantillas
        </DialogTitle>
        <DialogDescription>
          SigDoc utiliza documentos de Word (.docx) como plantillas. Aprenda a configurar marcadores variables.
        </DialogDescription>
      </DialogHeader>

      <div className="flex flex-col gap-7 px-6 py-6 text-sm">
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
              <thead className="bg-[var(--muted)]">
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
      </div>
    </DialogContent>
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
