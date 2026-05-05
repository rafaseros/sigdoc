// Mock paragraph contexts — each variable appears in real document fragments,
// some with multiple variables in the same paragraph (highlight one, mute the rest).
const VARIABLE_CONTEXTS = {
  nombre_empresa: [
    { pagina: 1, parrafo: 1, texto: "Entre {{ nombre_empresa }}, con NIT {{ numero }}, domiciliada en {{ direccion }} de la ciudad de {{ ciudad }}, representada legalmente por {{ nombre_representante }}, en adelante 'LA EMPRESA'." },
    { pagina: 1, parrafo: 4, texto: "{{ nombre_empresa }} se compromete a abonar el monto pactado a la cuenta indicada en la cláusula séptima." },
    { pagina: 2, parrafo: 1, texto: "El presente acuerdo de capacitación celebrado entre CAINCO y {{ nombre_empresa }} tendrá vigencia desde la fecha de firma." },
    { pagina: 2, parrafo: 7, texto: "En caso de incumplimiento, {{ nombre_empresa }} reconoce la jurisdicción de los tribunales ordinarios de {{ ciudad }}." },
    { pagina: 3, parrafo: 2, texto: "Se hace entrega de una copia del presente documento a {{ nombre_empresa }} para los fines consiguientes." },
    { pagina: 3, parrafo: 5, texto: "{{ nombre_empresa }} declara conocer y aceptar el reglamento interno de CAINCO Academy." },
    { pagina: 4, parrafo: 1, texto: "Firma autorizada en representación de {{ nombre_empresa }}: {{ nombre_representante }}." },
  ],
  numero: [
    { pagina: 1, parrafo: 1, texto: "Entre {{ nombre_empresa }}, con NIT {{ numero }}, domiciliada en {{ direccion }} de la ciudad de {{ ciudad }}." },
    { pagina: 1, parrafo: 3, texto: "Matrícula de comercio {{ numero }} vigente y registrada ante FUNDEMPRESA." },
  ],
  ciudad: [
    { pagina: 1, parrafo: 1, texto: "Entre {{ nombre_empresa }}, con NIT {{ numero }}, domiciliada en {{ direccion }} de la ciudad de {{ ciudad }}, representada legalmente por {{ nombre_representante }}." },
    { pagina: 4, parrafo: 2, texto: "Firmado en {{ ciudad }}, a los {{ dia_mes_ano }}." },
  ],
  direccion: [
    { pagina: 1, parrafo: 1, texto: "Entre {{ nombre_empresa }}, con NIT {{ numero }}, domiciliada en {{ direccion }} de la ciudad de {{ ciudad }}." },
  ],
  nombre_representante: [
    { pagina: 1, parrafo: 1, texto: "Entre {{ nombre_empresa }}, representada legalmente por {{ nombre_representante }}." },
  ],
  nombre_instructor: [
    { pagina: 2, parrafo: 3, texto: "El curso será impartido por {{ nombre_instructor }}, instructor certificado por CAINCO Academy." },
  ],
  nombre_curso: [
    { pagina: 2, parrafo: 2, texto: "Objeto del contrato: capacitación bajo el programa {{ nombre_curso }}." },
  ],
  fecha_ini: [
    { pagina: 2, parrafo: 4, texto: "El curso {{ nombre_curso }} dará inicio el {{ fecha_ini }} a las {{ hora }}." },
  ],
  hora: [
    { pagina: 2, parrafo: 4, texto: "El curso {{ nombre_curso }} dará inicio el {{ fecha_ini }} a las {{ hora }}." },
  ],
  monto_bs_usd: [
    { pagina: 3, parrafo: 1, texto: "Monto total: {{ monto_numeral }} {{ monto_bs_usd }} ({{ monto_literal }})." },
  ],
  monto_numeral: [
    { pagina: 3, parrafo: 1, texto: "Monto total: {{ monto_numeral }} {{ monto_bs_usd }} ({{ monto_literal }})." },
  ],
  monto_literal: [
    { pagina: 3, parrafo: 1, texto: "Monto total: {{ monto_numeral }} {{ monto_bs_usd }} ({{ monto_literal }})." },
  ],
  numero_cuenta_bancaria: [
    { pagina: 3, parrafo: 3, texto: "Depósito en cuenta {{ caja_ahorro_corriente }} N° {{ numero_cuenta_bancaria }} del {{ nombre_banco }}." },
  ],
  nombre_banco: [
    { pagina: 3, parrafo: 3, texto: "Depósito en cuenta {{ caja_ahorro_corriente }} N° {{ numero_cuenta_bancaria }} del {{ nombre_banco }}." },
  ],
  caja_ahorro_corriente: [
    { pagina: 3, parrafo: 3, texto: "Depósito en cuenta {{ caja_ahorro_corriente }} N° {{ numero_cuenta_bancaria }} del {{ nombre_banco }}." },
  ],
  dia_mes_ano: [
    { pagina: 4, parrafo: 2, texto: "Firmado en {{ ciudad }}, a los {{ dia_mes_ano }}." },
  ],
  fecha: [
    { pagina: 1, parrafo: 2, texto: "El presente documento se emite con fecha {{ fecha }}." },
  ],
};

// Renders a paragraph with all {{ variables }} highlighted; the "active" one
// uses a stronger style, the others are muted chips.
const ParagraphPreview = ({ texto, active }) => {
  const parts = texto.split(/(\{\{\s*[a-z_]+\s*\}\})/gi);
  return (
    <p style={{margin:0, fontSize:13, lineHeight:1.65, color:"#191c1e"}}>
      {parts.map((part, i) => {
        const m = part.match(/\{\{\s*([a-z_]+)\s*\}\}/i);
        if (!m) return <span key={i}>{part}</span>;
        const varName = m[1];
        const isActive = varName === active;
        return (
          <span
            key={i}
            className={`var-chip ${isActive ? "var-chip-active" : "var-chip-muted"}`}
            title={isActive ? `Variable seleccionada: ${varName}` : `Otra variable: ${varName}`}
          >
            {`{{ ${varName} }}`}
          </span>
        );
      })}
    </p>
  );
};

// SigDoc — Template detail screen (2 variants — tabs vs sidebar)

// Variables tab — master/detail with paragraph contexts
const VariablesTabContent = () => {
  const vars = window.TEMPLATE_VARIABLES;
  const [selected, setSelected] = React.useState(vars[0].name);
  const [query, setQuery] = React.useState("");
  const filtered = vars.filter(v => v.name.toLowerCase().includes(query.toLowerCase()));
  const active = vars.find(v => v.name === selected) || vars[0];
  const contexts = (window.VARIABLE_CONTEXTS || {})[active.name] || [];

  const tipoVariant = (t) => t==="fecha" ? "accent-soft" : t==="número" ? "ok" : "secondary";

  return (
    <div className="vars-layout">
      {/* Left rail — variable list */}
      <div className="card" style={{padding:0, display:"flex", flexDirection:"column", overflow:"hidden", maxHeight:"calc(100vh - 280px)"}}>
        <div style={{padding:"12px 14px", borderBottom:"1px solid rgba(195,198,215,0.25)"}}>
          <div className="h4" style={{marginBottom:8}}>Variables detectadas</div>
          <Search value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar variable…"/>
          <div className="tiny" style={{marginTop:8}}>{vars.length} marcadores · click para ver párrafos</div>
        </div>
        <div style={{flex:1, overflowY:"auto"}}>
          {filtered.map(v => (
            <div
              key={v.name}
              className={`var-row ${selected===v.name ? "active" : ""}`}
              onClick={()=>setSelected(v.name)}
            >
              <span className="mono var-row-name">{`{{ ${v.name} }}`}</span>
              <Pill variant={tipoVariant(v.tipo)} style={{height:18, fontSize:10.5, padding:"0 7px"}}>{v.tipo}</Pill>
              <Pill variant="outline" style={{height:18, fontSize:10.5, padding:"0 7px"}}>{v.apariciones}×</Pill>
            </div>
          ))}
        </div>
      </div>

      {/* Right pane — variable details + paragraph contexts */}
      <div style={{display:"flex", flexDirection:"column", gap:14}}>
        <div className="card" style={{padding:18}}>
          <div style={{display:"flex", alignItems:"flex-start", justifyContent:"space-between", gap:12, marginBottom:12}}>
            <div style={{minWidth:0}}>
              <div style={{display:"flex", alignItems:"center", gap:8, marginBottom:6}}>
                <span className="mono" style={{fontSize:15, color:"#004ac6", fontWeight:600}}>{`{{ ${active.name} }}`}</span>
                <Pill variant={tipoVariant(active.tipo)}>{active.tipo}</Pill>
                <Pill variant="accent-soft">{active.apariciones} apariciones</Pill>
              </div>
              <div className="tiny" style={{color:"#434655", fontSize:12.5}}>{active.hint}</div>
            </div>
            <Button variant="outline" size="sm" icon={<EditIcon size={13}/>}>Editar</Button>
          </div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
            <Field label="Tipo de dato">
              <Select defaultValue={active.tipo}>
                <option value="texto">texto</option>
                <option value="número">número</option>
                <option value="fecha">fecha</option>
                <option value="moneda">moneda</option>
              </Select>
            </Field>
            <Field label="Mensaje de ayuda">
              <Input defaultValue={active.hint}/>
            </Field>
          </div>
        </div>

        <div className="card" style={{padding:0}}>
          <div style={{padding:"12px 18px", borderBottom:"1px solid rgba(195,198,215,0.25)", display:"flex", alignItems:"center", justifyContent:"space-between"}}>
            <div>
              <div className="h4">Aparece en {contexts.length} párrafo{contexts.length===1?"":"s"}</div>
              <div className="tiny" style={{marginTop:2}}>
                <span className="var-legend var-legend-active"/> seleccionada
                <span className="var-legend var-legend-muted" style={{marginLeft:14}}/> otras variables del párrafo
              </div>
            </div>
          </div>
          <div style={{display:"flex", flexDirection:"column"}}>
            {contexts.length === 0 ? (
              <div style={{padding:"30px 18px", textAlign:"center"}} className="tiny">No hay vista previa de párrafos para esta variable.</div>
            ) : contexts.map((ctx, i) => (
              <div key={i} className="paragraph-row">
                <div className="paragraph-loc">
                  <span className="mono" style={{fontSize:11, color:"#515f74"}}>p.{ctx.pagina}</span>
                  <span className="tiny">¶ {ctx.parrafo}</span>
                </div>
                <div style={{flex:1, minWidth:0}}>
                  <ParagraphPreview texto={ctx.texto} active={active.name}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// SigDoc — Template detail screen (2 variants — tabs vs sidebar)

const TemplateDetailScreen = ({ variant = "A", template, onBack, onGenerate, onBulk, onShare, onDelete, onGuide }) => {
  const [tab, setTab] = React.useState("info");
  const t = template || window.TEMPLATES[4];

  const tabs = [
    { id:"info",      label:"Información", icon:<InfoIcon size={14}/> },
    { id:"variables", label:"Variables",   icon:<CodeIcon size={14}/>, count: window.TEMPLATE_VARIABLES.length },
    { id:"versiones", label:"Versiones",   icon:<HistoryIcon size={14}/>, count: window.VERSIONS.length },
    { id:"shared",    label:"Compartido",  icon:<ShareIcon size={14}/>, count: window.SHARED_WITH.length },
    { id:"docs",      label:"Documentos",  icon:<FileTextIcon size={14}/>, count: window.DOCUMENTS_GEN.length },
  ];

  const Header = (
    <div style={{marginBottom:20}}>
      <button className="btn btn-ghost btn-sm" onClick={onBack} style={{marginBottom:10, marginLeft:-8}}>
        <ArrowLeftIcon size={14}/>Volver a Plantillas
      </button>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:16}}>
        <div style={{display:"flex", alignItems:"center", gap:14}}>
          <span style={{width:48, height:48, borderRadius:12, background:"linear-gradient(135deg, #dbe1ff, #b4c5ff)", color:"#004ac6", display:"inline-flex", alignItems:"center", justifyContent:"center", flexShrink:0}}>
            <FileTextIcon size={22}/>
          </span>
          <div>
            <div style={{display:"flex", alignItems:"center", gap:8, marginBottom:6}}>
              <Pill variant="outline">{t.version}</Pill>
              <Pill variant="secondary">{t.tipo}</Pill>
              {t.shared && <Pill variant="accent-soft">Compartida</Pill>}
            </div>
            <h1 className="h2" style={{maxWidth:680}}>{t.nombre}</h1>
            <div className="tiny" style={{marginTop:6}}>{t.desc}</div>
          </div>
        </div>
        <div className="action-row">
          <Button variant="ghost" className="is-primary" icon={<SparklesIcon size={14}/>} onClick={onGenerate}>Generar Documento</Button>
          <Button variant="ghost" icon={<FileSpreadsheetIcon size={14}/>} onClick={onBulk}>Generación Masiva</Button>
          <Button variant="ghost" icon={<ShareIcon size={14}/>} onClick={onShare}>Compartir</Button>
          <Button variant="ghost" className="is-danger" icon={<TrashIcon size={14}/>} onClick={onDelete}>Eliminar</Button>
        </div>
      </div>
    </div>
  );

  const InfoTab = (
    <div style={{display:"grid", gridTemplateColumns: variant === "B" ? "1fr" : "1.6fr 1fr", gap:18}}>
      <div style={{display:"flex", flexDirection:"column", gap:18}}>
        <div className="card" style={{padding:0}}>
          <div style={{padding:"14px 18px", borderBottom:"1px solid rgba(195,198,215,0.25)", display:"flex", justifyContent:"space-between", alignItems:"center"}}>
            <div className="h4">Información de la Plantilla</div>
            <Button variant="ghost" size="sm" icon={<EditIcon size={13}/>}>Editar metadatos</Button>
          </div>
          <div style={{padding:"4px 0"}}>
            {[
              ["Versión actual", <Pill variant="accent-soft">{t.version}</Pill>],
              ["Tipo de documento", t.tipo],
              ["Creado", "27 abr 2026, 01:46 a.m."],
              ["Actualizado", "27 abr 2026, 01:48 a.m."],
              ["Tamaño del archivo", t.size],
              ["Total de versiones", t.versiones],
              ["Variables detectadas", `${t.vars} marcadores`],
              ["Autor", <span style={{display:"inline-flex", alignItems:"center", gap:8}}><Avatar name={t.autor} size="sm"/>{t.autor}</span>],
            ].map(([k,v], i) => (
              <div key={i} style={{display:"flex", padding:"10px 18px", borderTop: i ? "1px solid rgba(195,198,215,0.15)" : "none"}}>
                <div style={{flex:"0 0 200px", fontSize:12.5, color:"#515f74"}}>{k}</div>
                <div style={{flex:1, fontSize:13.5, color:"#191c1e", fontWeight:500}}>{v}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card" style={{padding:18}}>
          <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12}}>
            <div className="h4">Actividad reciente</div>
            <span className="tiny">últimos 7 días</span>
          </div>
          <div style={{display:"flex", flexDirection:"column"}}>
            {[
              { icon:<SparklesIcon size={13}/>, text:"Generación individual", who:"karol.zabala", when:"hoy, 14:59", tone:"#065f46", bg:"#d1fae5" },
              { icon:<DownloadIcon size={13}/>, text:"Descarga en PDF",        who:"karol.zabala", when:"29 abr, 22:33", tone:"#004ac6", bg:"#dbe1ff" },
              { icon:<UploadIcon size={13}/>,   text:"Subida v3 — vigencia",   who:"rafael.gallegos", when:"27 abr, 01:48", tone:"#b45309", bg:"#fef3c7" },
              { icon:<ShareIcon size={13}/>,    text:"Compartida con devrafaseros", who:"karol.zabala", when:"27 abr, 06:42", tone:"#004ac6", bg:"#dbe1ff" },
            ].map((row, i) => (
              <div key={i} style={{display:"flex", alignItems:"center", gap:12, padding:"9px 0", borderTop: i ? "1px dashed rgba(195,198,215,0.30)" : "none"}}>
                <span style={{width:28, height:28, borderRadius:8, background:row.bg, color:row.tone, display:"inline-flex", alignItems:"center", justifyContent:"center", flexShrink:0}}>{row.icon}</span>
                <div style={{flex:1, minWidth:0}}>
                  <div style={{fontSize:13, fontWeight:500}}>{row.text}</div>
                  <div className="tiny">{row.who} · {row.when}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{display:"flex", flexDirection:"column", gap:18}}>
        <div className="card" style={{padding:0, overflow:"hidden"}}>
          <div style={{
            position:"relative", height:180,
            background:"repeating-linear-gradient(45deg, #f7f9fb 0 12px, #eceef0 12px 13px)",
            borderBottom:"1px solid rgba(195,198,215,0.25)",
            display:"flex", alignItems:"center", justifyContent:"center",
          }}>
            <span style={{
              padding:"6px 12px", background:"rgba(255,255,255,0.85)",
              border:"1px solid rgba(195,198,215,0.40)", borderRadius:8,
              fontFamily:"var(--font-mono)", fontSize:11.5, color:"#515f74",
            }}>preview · {t.version}</span>
            <span className="mono" style={{position:"absolute", bottom:10, left:14, fontSize:11, color:"#515f74"}}>{t.size}</span>
          </div>
          <div style={{padding:"12px 16px", display:"flex", gap:8}}>
            <Button variant="outline" size="sm" icon={<DownloadIcon size={13}/>}>Descargar .docx</Button>
            <Button variant="ghost" size="sm" icon={<HistoryIcon size={13}/>} onClick={()=>setTab("versiones")}>Ver versiones</Button>
          </div>
        </div>

        <div className="card" style={{padding:18}}>
          <div className="h4" style={{marginBottom:12}}>Resumen de uso</div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10}}>
            <div className="usage-stat">
              <div className="usage-num">42</div>
              <div className="usage-lbl">documentos generados</div>
            </div>
            <div className="usage-stat">
              <div className="usage-num">{window.SHARED_WITH.length}</div>
              <div className="usage-lbl">usuarios con acceso</div>
            </div>
            <div className="usage-stat">
              <div className="usage-num">{t.versiones}</div>
              <div className="usage-lbl">versiones publicadas</div>
            </div>
            <div className="usage-stat">
              <div className="usage-num">{t.vars}</div>
              <div className="usage-lbl">variables detectadas</div>
            </div>
          </div>
          <div style={{marginTop:14, paddingTop:14, borderTop:"1px solid rgba(195,198,215,0.20)"}}>
            <Banner variant="info" icon={<BookIcon size={14} style={{color:"#1e3a8a"}}/>}>
              <div style={{fontSize:12.5}}>¿Dudas con marcadores <span className="mono" style={{color:"#004ac6"}}>{"{{ var }}"}</span>? <span style={{color:"#004ac6", fontWeight:600, cursor:"pointer"}} onClick={onGuide}>Ver Guía</span></div>
            </Banner>
          </div>
        </div>
      </div>
    </div>
  );

  const VariablesTab = <VariablesTabContent/>;

  const VersionsTab = (
    <div>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14}}>
        <div>
          <div className="h3">Historial de versiones</div>
          <div className="tiny" style={{marginTop:2}}>Cada versión preserva variables y archivo original. Puede revertir en cualquier momento.</div>
        </div>
        <Button variant="grad" icon={<UploadIcon size={14}/>}>Subir Nueva Versión</Button>
      </div>
      <div style={{display:"flex", flexDirection:"column", gap:10}}>
        {window.VERSIONS.map(v => (
          <div key={v.v} className="card" style={{padding:16, display:"flex", gap:14, alignItems:"center"}}>
            <span style={{width:42, height:42, borderRadius:10, background: v.current ? "linear-gradient(135deg,#004ac6,#2563eb)" : "#eceef0", color: v.current ? "#fff" : "#515f74", display:"inline-flex", alignItems:"center", justifyContent:"center", fontWeight:700, fontSize:13, letterSpacing:"-0.02em"}}>{v.v}</span>
            <div style={{flex:1, minWidth:0}}>
              <div style={{display:"flex", alignItems:"center", gap:8, marginBottom:3}}>
                <span style={{fontSize:14, fontWeight:600}}>{v.v}</span>
                {v.current && <Pill variant="ok">Actual</Pill>}
                <span className="tiny">· {v.size} · {v.vars} variables</span>
              </div>
              <div className="tiny" style={{marginBottom:4}}>{v.notes}</div>
              <div style={{fontSize:11.5, color:"#515f74"}}>Subida por {v.uploadedBy} · {v.fecha}</div>
            </div>
            <div style={{display:"flex", gap:6}}>
              <IconButton icon={<DownloadIcon size={14}/>} title="Descargar"/>
              {!v.current && <Button variant="outline" size="sm">Restaurar</Button>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const SharedTab = (
    <div className="card-floating" style={{padding:0}}>
      <div style={{padding:"14px 18px", borderBottom:"1px solid rgba(195,198,215,0.25)", display:"flex", justifyContent:"space-between", alignItems:"center"}}>
        <div>
          <div className="h4">Compartido con</div>
          <div className="tiny" style={{marginTop:2}}>Usuarios que pueden ver y generar desde esta plantilla.</div>
        </div>
        <Button variant="grad" size="sm" icon={<ShareIcon size={13}/>} onClick={onShare}>Compartir</Button>
      </div>
      <table className="tbl tbl-compact">
        <thead><tr><th>Usuario</th><th>Acceso</th><th>Compartido el</th><th style={{width:90}}/></tr></thead>
        <tbody>
          {window.SHARED_WITH.map(s => (
            <tr key={s.email}>
              <td><div style={{display:"flex", alignItems:"center", gap:10}}><Avatar name={s.email} size="sm"/><span style={{fontWeight:500}}>{s.email}</span></div></td>
              <td><Pill variant="secondary">{s.acceso}</Pill></td>
              <td className="muted">{s.fecha}</td>
              <td><Button variant="ghost" size="sm" style={{color:"#ba1a1a"}} icon={<TrashIcon size={13}/>}>Revocar</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const DocsTab = (
    <div className="card-floating" style={{padding:0}}>
      <div style={{padding:"14px 18px", borderBottom:"1px solid rgba(195,198,215,0.25)"}}>
        <div className="h4">Documentos generados</div>
        <div className="tiny" style={{marginTop:2}}>Historial de descargas y generaciones a partir de esta plantilla.</div>
      </div>
      <table className="tbl tbl-compact">
        <thead><tr><th>Archivo</th><th>Tipo</th><th>Generado por</th><th>Fecha</th><th style={{width:170}}/></tr></thead>
        <tbody>
          {window.DOCUMENTS_GEN.map(d => (
            <tr key={d.id}>
              <td><div style={{display:"flex", alignItems:"center", gap:10}}>
                <span style={{width:30, height:30, borderRadius:8, background: d.tipo==="Masiva"?"#d1fae5":"#dbe1ff", color: d.tipo==="Masiva"?"#065f46":"#004ac6", display:"inline-flex", alignItems:"center", justifyContent:"center"}}>
                  {d.tipo==="Masiva" ? <FileSpreadsheetIcon size={14}/> : <FileTextIcon size={14}/>}
                </span>
                <div>
                  <div style={{fontWeight:500}}>{d.archivo}</div>
                  <div className="tiny">{d.size}{d.count ? ` · ${d.count} documentos` : ""}</div>
                </div>
              </div></td>
              <td><Pill variant={d.tipo==="Masiva"?"ok":"accent-soft"}>{d.tipo}</Pill></td>
              <td><div style={{display:"flex", alignItems:"center", gap:8}}><Avatar name={d.autor} size="sm"/><span style={{fontSize:12.5}}>{d.autor.split("@")[0]}</span></div></td>
              <td className="muted">{d.fecha}</td>
              <td><Button variant="success" size="sm" icon={<DownloadIcon size={13}/>}>Descargar</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const tabContent = { info: InfoTab, variables: VariablesTab, versiones: VersionsTab, shared: SharedTab, docs: DocsTab }[tab];

  if (variant === "B") {
    // Sidebar layout — sections on left, content on right
    return (
      <div>
        {Header}
        <div style={{display:"grid", gridTemplateColumns:"220px 1fr", gap:24, alignItems:"flex-start"}}>
          <div style={{display:"flex", flexDirection:"column", gap:2, position:"sticky", top:80}}>
            {tabs.map(t => (
              <span key={t.id} className={`side-link ${tab===t.id?"active":""}`} onClick={()=>setTab(t.id)}>
                {t.icon}
                <span style={{flex:1}}>{t.label}</span>
                {t.count!=null && <Pill variant={tab===t.id?"accent-soft":"secondary"} style={{height:18, fontSize:10.5, padding:"0 7px"}}>{t.count}</Pill>}
              </span>
            ))}
          </div>
          <div>{tabContent}</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {Header}
      <Tabs tabs={tabs} active={tab} onChange={setTab}/>
      {tabContent}
    </div>
  );
};

Object.assign(window, { TemplateDetailScreen, VARIABLE_CONTEXTS });
