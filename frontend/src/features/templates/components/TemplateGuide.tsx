import { useState } from "react";
import { BookOpenIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function TemplateGuideButton() {
  return (
    <Dialog>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>
        <BookOpenIcon className="size-4 mr-2" />
        Guía de Plantillas
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Cómo Crear Plantillas</DialogTitle>
        </DialogHeader>
        <TemplateGuideContent />
      </DialogContent>
    </Dialog>
  );
}

export function TemplateGuideBanner() {
  const [dismissed, setDismissed] = useState(() => {
    return localStorage.getItem("sigdoc_guide_dismissed") === "true";
  });

  if (dismissed) return null;

  const handleDismiss = () => {
    localStorage.setItem("sigdoc_guide_dismissed", "true");
    setDismissed(true);
  };

  return (
    <div className="rounded-lg border bg-muted/50 p-4 relative">
      <button
        onClick={handleDismiss}
        className="absolute top-2 right-2 text-muted-foreground hover:text-foreground"
      >
        <XIcon className="size-4" />
      </button>
      <h3 className="font-semibold mb-1">¿Nuevo en SigDoc?</h3>
      <p className="text-sm text-muted-foreground mb-2">
        Aprenda a configurar sus plantillas de Word con variables para la generación automática de documentos.
      </p>
      <Dialog>
        <DialogTrigger render={<Button variant="outline" size="sm" />}>
          <BookOpenIcon className="size-4 mr-2" />
          Ver Guía de Plantillas
        </DialogTrigger>
        <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Cómo Crear Plantillas</DialogTitle>
          </DialogHeader>
          <TemplateGuideContent />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TemplateGuideContent() {
  return (
    <div className="space-y-6 text-sm">
      {/* Overview */}
      <section>
        <p className="text-muted-foreground">
          SigDoc utiliza documentos de Word (.docx) como plantillas. Se agregan
          marcadores especiales (variables) en el documento, y SigDoc los reemplaza
          con valores reales al generar el documento final.
        </p>
      </section>

      {/* Basic Variables */}
      <section>
        <h3 className="font-semibold text-base mb-2">Variables Básicas</h3>
        <p className="text-muted-foreground mb-3">
          Use llaves dobles con espacios para definir una variable:
        </p>
        <CodeBlock>
          {"Estimado {{ nombre }},\n\nPor la presente se notifica que el monto de {{ monto }}\nfue aprobado el día {{ fecha }}."}
        </CodeBlock>
        <div className="mt-3 space-y-1">
          <Rule type="do">Use espacios dentro de las llaves: {"{{ nombre }}"}</Rule>
          <Rule type="dont">No omita los espacios: {"{{nombre}}"} — podría no ser detectado</Rule>
        </div>
      </section>

      {/* Variable Names */}
      <section>
        <h3 className="font-semibold text-base mb-2">Reglas de Nombres de Variables</h3>
        <div className="space-y-1">
          <Rule type="do">Use minúsculas con guiones bajos: {"{{ nombre_completo }}"}</Rule>
          <Rule type="do">Use nombres descriptivos: {"{{ fecha_emision }}"}, {"{{ numero_contrato }}"}</Rule>
          <Rule type="dont">Evite espacios en los nombres: {"{{ nombre completo }}"}</Rule>
          <Rule type="dont">Evite caracteres especiales: {"{{ año }}"}, {"{{ dirección }}"}</Rule>
          <Rule type="do">Use solo ASCII: {"{{ anio }}"}, {"{{ direccion }}"}</Rule>
        </div>
      </section>

      {/* Formatting */}
      <section>
        <h3 className="font-semibold text-base mb-2">Consejos de Formato</h3>
        <p className="text-muted-foreground mb-3">
          El marcador de variable hereda el formato del texto circundante
          en Word. Esto significa:
        </p>
        <div className="space-y-2 text-muted-foreground">
          <p>
            <strong>Texto en negrita:</strong> Si pone {"{{ nombre }}"} en negrita en
            Word, el valor reemplazado también estará en negrita.
          </p>
          <p>
            <strong>Tamaño de fuente:</strong> La variable hereda la fuente, tamaño
            y color del estilo de Word aplicado.
          </p>
          <p>
            <strong>Alineación:</strong> La alineación centrada, derecha o justificada
            se preserva.
          </p>
        </div>

        <div className="mt-3 rounded-md bg-amber-500/10 border border-amber-500/20 p-3">
          <p className="font-medium text-amber-700 dark:text-amber-400 mb-1">
            Importante: Mismo formato para toda la variable
          </p>
          <p className="text-muted-foreground">
            Todo el marcador {"{{ variable }}"} debe tener el mismo
            formato. Si pone en negrita solo una parte (como{" "}
            <strong>{"{{ vari"}</strong>{"able }}"}) el sistema no lo detectará.
            Seleccione todo el marcador incluyendo las llaves y aplique
            el formato de manera uniforme.
          </p>
        </div>
      </section>

      {/* Tables */}
      <section>
        <h3 className="font-semibold text-base mb-2">Variables en Tablas</h3>
        <p className="text-muted-foreground mb-3">
          Puede colocar variables dentro de celdas de tabla. Cada celda puede contener una
          o más variables:
        </p>
        <div className="rounded-md border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Campo</th>
                <th className="px-3 py-2 text-left font-medium">Valor</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t">
                <td className="px-3 py-2">Nombre</td>
                <td className="px-3 py-2 font-mono text-xs">{"{{ nombre }}"}</td>
              </tr>
              <tr className="border-t">
                <td className="px-3 py-2">Fecha</td>
                <td className="px-3 py-2 font-mono text-xs">{"{{ fecha }}"}</td>
              </tr>
              <tr className="border-t">
                <td className="px-3 py-2">Monto</td>
                <td className="px-3 py-2 font-mono text-xs">{"{{ monto }}"}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Headers and Footers */}
      <section>
        <h3 className="font-semibold text-base mb-2">Encabezados y Pies de Página</h3>
        <p className="text-muted-foreground">
          Las variables también se pueden colocar en encabezados y pies de página.
          Serán detectadas y reemplazadas igual que las variables en el cuerpo del documento.
        </p>
      </section>

      {/* Example Template */}
      <section>
        <h3 className="font-semibold text-base mb-2">Ejemplo Completo</h3>
        <p className="text-muted-foreground mb-3">
          Así se ve una plantilla de contrato típica:
        </p>
        <CodeBlock>
{`CONTRATO DE SERVICIOS

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
{{ nombre_empresa }}       {{ nombre_contratado }}`}
        </CodeBlock>
        <p className="text-muted-foreground mt-2">
          Esta plantilla tiene <strong>10 variables</strong> que SigDoc
          detectará automáticamente al subirla.
        </p>
      </section>

      {/* Quick Checklist */}
      <section>
        <h3 className="font-semibold text-base mb-2">Lista de Verificación Pre-Subida</h3>
        <div className="space-y-2">
          <CheckItem>Guarde su documento como .docx (no .doc ni .pdf)</CheckItem>
          <CheckItem>Use la sintaxis {"{{ variable }}"} con espacios dentro de las llaves</CheckItem>
          <CheckItem>Use minúsculas_con_guiones_bajos para nombres de variables</CheckItem>
          <CheckItem>Evite caracteres especiales (acentos, ñ) en nombres de variables</CheckItem>
          <CheckItem>Aplique el formato de manera uniforme a todo el marcador</CheckItem>
          <CheckItem>Pruebe primero con una plantilla simple antes de las complejas</CheckItem>
        </div>
      </section>
    </div>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="rounded-md bg-muted p-3 text-xs font-mono whitespace-pre-wrap overflow-x-auto">
      {children}
    </pre>
  );
}

function Rule({ type, children }: { type: "do" | "dont"; children: React.ReactNode }) {
  return (
    <p className="text-muted-foreground">
      <span className={type === "do" ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"}>
        {type === "do" ? "✓" : "✗"}
      </span>{" "}
      {children}
    </p>
  );
}

function CheckItem({ children }: { children: React.ReactNode }) {
  return (
    <label className="flex items-start gap-2 text-muted-foreground">
      <span className="mt-0.5">☐</span>
      <span>{children}</span>
    </label>
  );
}
