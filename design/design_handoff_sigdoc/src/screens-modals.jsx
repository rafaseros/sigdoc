// SigDoc — Modals & Guide

const GuideDialog = ({ open, onClose }) => (
  <Dialog open={open} onClose={onClose} title="Cómo Crear Plantillas" description="SigDoc utiliza documentos de Word (.docx) como plantillas. Aprenda a configurar marcadores variables." width={680} footer={<Button variant="grad" onClick={onClose}>Entendido</Button>}>
    <div style={{display:"flex", flexDirection:"column", gap:18}}>
      <section>
        <div className="eyebrow" style={{marginBottom:8}}>Variables básicas</div>
        <p style={{fontSize:13.5, color:"#434655", lineHeight:1.55, margin:"0 0 10px"}}>Use llaves dobles con espacios para definir una variable.</p>
        <div style={{background:"#0f172a", color:"#e0e7ff", padding:"14px 16px", borderRadius:10, fontFamily:"var(--font-mono)", fontSize:12.5, lineHeight:1.7}}>
          Estimado <span style={{color:"#7dd3fc"}}>{"{{ nombre }}"}</span>,<br/>
          Por la presente se notifica que el monto de <span style={{color:"#7dd3fc"}}>{"{{ monto }}"}</span><br/>
          fue aprobado el día <span style={{color:"#7dd3fc"}}>{"{{ fecha }}"}</span>.
        </div>
        <div style={{marginTop:10, display:"flex", flexDirection:"column", gap:6}}>
          <div style={{display:"flex", gap:10, alignItems:"center", fontSize:13}}><CheckIcon size={14} style={{color:"#059669"}}/>Use espacios dentro de las llaves: <span className="mono" style={{color:"#004ac6"}}>{"{{ nombre }}"}</span></div>
          <div style={{display:"flex", gap:10, alignItems:"center", fontSize:13}}><XIcon size={14} style={{color:"#ba1a1a"}}/>No omita los espacios: <span className="mono" style={{color:"#ba1a1a"}}>{"{{nombre}}"}</span> — podría no ser detectado</div>
        </div>
      </section>
      <section>
        <div className="eyebrow" style={{marginBottom:8}}>Reglas de nombres</div>
        <div style={{display:"flex", flexDirection:"column", gap:6, fontSize:13}}>
          <div style={{display:"flex", gap:10, alignItems:"center"}}><CheckIcon size={14} style={{color:"#059669"}}/>Minúsculas con guiones bajos: <span className="mono" style={{color:"#004ac6"}}>{"{{ nombre_completo }}"}</span></div>
          <div style={{display:"flex", gap:10, alignItems:"center"}}><CheckIcon size={14} style={{color:"#059669"}}/>Nombres descriptivos: <span className="mono" style={{color:"#004ac6"}}>{"{{ fecha_emision }}"}</span></div>
          <div style={{display:"flex", gap:10, alignItems:"center"}}><XIcon size={14} style={{color:"#ba1a1a"}}/>Evite espacios y caracteres especiales o acentos</div>
        </div>
      </section>
      <Banner variant="warn" icon={<AlertCircleIcon size={16} style={{color:"#b45309"}}/>}>
        <strong>Importante:</strong> mantenga el mismo formato (negrita, fuente, color) en toda la variable. Si parte de la variable está en negrita y parte no, Word la separa internamente y SigDoc no la detectará.
      </Banner>
    </div>
  </Dialog>
);

const DeleteDialog = ({ open, onClose, template, onConfirm }) => (
  <Dialog open={open} onClose={onClose} title="Eliminar Plantilla" footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button variant="danger-solid" icon={<TrashIcon size={13}/>} onClick={onConfirm}>Eliminar permanentemente</Button></>}>
    <Banner variant="err" icon={<AlertCircleIcon size={16} style={{color:"#ba1a1a"}}/>}>
      <strong>Esta acción no se puede deshacer.</strong> Se eliminarán todas las versiones, configuraciones de variables y historiales asociados.
    </Banner>
    <p style={{fontSize:13.5, color:"#434655", lineHeight:1.55, margin:"14px 0 8px"}}>¿Está seguro de que desea eliminar la plantilla <strong>"{template?.nombre}"</strong>?</p>
    <Field label={<>Para confirmar, escriba <span className="mono" style={{color:"#ba1a1a"}}>ELIMINAR</span></>}>
      <Input placeholder="ELIMINAR"/>
    </Field>
  </Dialog>
);

const ShareDialog = ({ open, onClose, template }) => (
  <Dialog open={open} onClose={onClose} title="Compartir Plantilla" description={`Comparta "${template?.nombre || ""}" con otros usuarios de su organización. Podrán ver y generar documentos, pero no modificar la plantilla.`} footer={<Button variant="outline" onClick={onClose}>Cerrar</Button>}>
    <Field label="Agregar usuario por correo">
      <div style={{display:"flex", gap:8}}>
        <Input placeholder="correo@ejemplo.com"/>
        <Button variant="grad" icon={<PlusIcon size={13}/>}>Compartir</Button>
      </div>
    </Field>
    <div style={{marginTop:18}}>
      <div className="eyebrow" style={{marginBottom:8}}>Usuarios con acceso ({window.SHARED_WITH.length})</div>
      <div style={{display:"flex", flexDirection:"column", gap:8}}>
        {window.SHARED_WITH.map(s => (
          <div key={s.email} style={{display:"flex", alignItems:"center", gap:10, padding:"10px 12px", background:"#f7f9fb", borderRadius:10}}>
            <Avatar name={s.email} size="sm"/>
            <div style={{flex:1, minWidth:0}}>
              <div style={{fontSize:13, fontWeight:500}}>{s.email}</div>
              <div className="tiny">Compartida el {s.fecha}</div>
            </div>
            <Pill variant="ok">{s.acceso}</Pill>
            <IconButton icon={<TrashIcon size={13}/>} title="Revocar" style={{color:"#ba1a1a"}}/>
          </div>
        ))}
      </div>
    </div>
  </Dialog>
);

const UploadDialog = ({ open, onClose, onUploaded }) => {
  const [step, setStep] = React.useState("select");
  const [drag, setDrag] = React.useState(false);
  const [filename, setFilename] = React.useState("");
  React.useEffect(() => { if (open) { setStep("select"); setFilename(""); } }, [open]);
  const pick = () => { setFilename("contrato_servicios_v2.docx"); setStep("validating"); setTimeout(()=>setStep("valid"), 700); };
  const Footer = step === "valid"
    ? <><Button variant="outline" onClick={onClose}>Cancelar</Button><Button variant="grad" icon={<UploadIcon size={13}/>} onClick={()=>{onUploaded?.(filename); onClose?.();}}>Subir Plantilla</Button></>
    : <Button variant="outline" onClick={onClose}>Cancelar</Button>;
  return (
    <Dialog open={open} onClose={onClose} title="Subir Nueva Plantilla" description="Suba un archivo .docx con marcadores tipo {{ variable }}. El archivo se valida automáticamente." footer={Footer} width={620}>
      {step === "select" && (
        <div className={`dz ${drag?"dz-over":""}`}
          onDragOver={(e)=>{e.preventDefault(); setDrag(true);}} onDragLeave={()=>setDrag(false)}
          onDrop={(e)=>{e.preventDefault(); setDrag(false); pick();}} onClick={pick}>
          <UploadIcon size={32} style={{color: drag ? "#004ac6" : "#515f74"}}/>
          <div style={{fontSize:14, fontWeight:600}}>{drag ? "Suelte aquí" : "Arrastre y suelte un archivo .docx"}</div>
          <div className="tiny">o haga clic para buscar · máx. 10 MB</div>
        </div>
      )}
      {step === "validating" && (
        <div style={{display:"flex", flexDirection:"column", alignItems:"center", padding:"30px 0", gap:10}}>
          <LoaderIcon size={28} className="spin" style={{color:"#004ac6"}}/>
          <div style={{fontSize:14, fontWeight:500}}>Validando {filename}…</div>
        </div>
      )}
      {step === "valid" && (
        <div style={{display:"flex", flexDirection:"column", gap:14}}>
          <Banner variant="ok" icon={<CheckCircleIcon size={16} style={{color:"#059669"}}/>}>
            <strong>Plantilla válida</strong> — 12 variable(s) detectada(s) en <span className="mono" style={{fontSize:12}}>{filename}</span>
          </Banner>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
            <Field label="Nombre"><Input defaultValue="Contrato de Servicios"/></Field>
            <Field label="Tipo de documento">
              <Select defaultValue="contrato">
                <option value="contrato">Contrato</option><option value="acuerdo">Acuerdo</option>
                <option value="carta">Carta</option><option value="anexo">Anexo</option>
              </Select>
            </Field>
          </div>
          <Field label="Descripción (opcional)"><Textarea placeholder="¿Para qué se usa esta plantilla?"/></Field>
          <label style={{display:"flex", alignItems:"center", gap:8, fontSize:13, cursor:"pointer"}}>
            <input type="checkbox" defaultChecked/> Compartir con todo el equipo
          </label>
        </div>
      )}
    </Dialog>
  );
};

Object.assign(window, { GuideDialog, DeleteDialog, ShareDialog, UploadDialog });
