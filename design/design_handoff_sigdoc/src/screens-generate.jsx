// SigDoc — Generation screens (individual + bulk)

const GenerateIndividualScreen = ({ variant = "A", template, onBack }) => {
  const t = template || window.TEMPLATES[4];
  const vars = window.TEMPLATE_VARIABLES;
  const [values, setValues] = React.useState(() => {
    const o = {};
    vars.forEach(v => o[v.name] = "");
    o["nombre_empresa"] = "Cainco Academy S.A.";
    o["numero"] = "00457821";
    o["ciudad"] = "Santa Cruz de la Sierra";
    o["nombre_curso"] = "Excel Avanzado para Empresas";
    return o;
  });
  const [active, setActive] = React.useState("nombre_empresa");
  const setVal = (k, v) => setValues(o => ({...o, [k]: v}));
  const filled = vars.filter(v => values[v.name]?.trim()).length;
  const pct = Math.round(filled / vars.length * 100);

  const Chip = ({ name }) => (
    <span className={`var-chip ${values[name]?.trim() ? "filled" : ""} ${active === name ? "active" : ""}`} onClick={()=>setActive(name)}>
      {values[name]?.trim() || `{{ ${name} }}`}
    </span>
  );

  const FormPanel = (
    <div style={{display:"flex", flexDirection:"column", height:"100%"}}>
      <div style={{padding:"16px 18px", borderBottom:"1px solid rgba(195,198,215,0.20)"}}>
        <div className="h4" style={{marginBottom:8}}>Complete las variables</div>
        <div style={{display:"flex", alignItems:"center", gap:10, fontSize:12.5, color:"#515f74"}}>
          <span style={{flex:1, height:6, borderRadius:999, background:"#eceef0", overflow:"hidden"}}>
            <span style={{display:"block", height:"100%", width:`${pct}%`, background:"linear-gradient(135deg, #004ac6, #2563eb)", transition:"width 200ms"}}/>
          </span>
          <span style={{fontWeight:600, color:"#191c1e"}}>{filled}/{vars.length}</span>
        </div>
      </div>
      <div style={{flex:1, overflowY:"auto", padding:"12px 18px"}}>
        {vars.map(v => (
          <div key={v.name} className="field" style={{marginBottom:14, padding: active===v.name ? "10px 12px" : "0", borderRadius: 10, background: active===v.name ? "rgba(219,225,255,0.30)" : "transparent", transition:"all 150ms"}}>
            <label className="label" style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
              <span><span className="mono" style={{color:"#004ac6"}}>{v.name}</span> <span style={{color:"#8a8e9a", fontSize:11, marginLeft:4}}>· {v.tipo}</span></span>
              <span style={{fontSize:10.5, color:"#8a8e9a"}}>{v.apariciones}× en doc</span>
            </label>
            <input className="input" placeholder={v.hint} value={values[v.name]} onChange={e=>setVal(v.name, e.target.value)} onFocus={()=>setActive(v.name)}/>
          </div>
        ))}
      </div>
      <div style={{padding:"14px 18px", borderTop:"1px solid rgba(195,198,215,0.20)", background:"#f7f9fb", display:"flex", gap:8, justifyContent:"space-between", alignItems:"center"}}>
        <div className="tiny">{filled === vars.length ? "Listo para generar" : `Faltan ${vars.length - filled} variables`}</div>
        <div style={{display:"flex", gap:8}}>
          <Button variant="outline" size="sm">Guardar borrador</Button>
          <Button variant="grad" size="sm" icon={<DownloadIcon size={13}/>} disabled={filled < vars.length}>Generar Documento</Button>
        </div>
      </div>
    </div>
  );

  const PreviewPanel = (
    <div className="doc-preview">
      <h4 style={{textAlign:"center", marginBottom:24, fontSize:15}}>CONTRATO DE PRESTACIÓN DE SERVICIOS DE CAPACITACIÓN</h4>
      <p>Entre <Chip name="nombre_empresa"/>, con Matrícula de Comercio Nº <Chip name="numero"/>, con domicilio legal en la ciudad de <Chip name="ciudad"/>, calle <Chip name="direccion"/>, representada legalmente por <Chip name="nombre_representante"/> (en adelante "LA EMPRESA"), por una parte; y CAINCO ACADEMY S.A. con NIT <Chip name="numero"/>, por la otra (en adelante "CAINCO ACADEMY"), se conviene celebrar el presente contrato.</p>
      <p style={{textAlign:"left", fontWeight:600, marginTop:14}}>PRIMERA. OBJETO DEL CONTRATO.</p>
      <p>CAINCO ACADEMY se obliga a impartir el curso <Chip name="nombre_curso"/> al instructor designado <Chip name="nombre_instructor"/>, con inicio el día <Chip name="fecha_ini"/> a las <Chip name="hora"/> horas, debiéndose cumplir con la carga horaria pactada.</p>
      <p style={{textAlign:"left", fontWeight:600, marginTop:14}}>SEGUNDA. CONTRAPRESTACIÓN.</p>
      <p>El monto total del servicio asciende a la suma de <Chip name="monto_bs_usd"/> <Chip name="monto_numeral"/> (<Chip name="monto_literal"/>), pagaderos a la cuenta Nº <Chip name="numero_cuenta_bancaria"/> del banco <Chip name="nombre_banco"/>, modalidad <Chip name="caja_ahorro_corriente"/>.</p>
      <p style={{textAlign:"left", fontWeight:600, marginTop:14}}>TERCERA. VIGENCIA.</p>
      <p>El presente contrato entrará en vigencia desde el <Chip name="dia_mes_ano"/> y se regirá por la normativa boliviana vigente. Santa Cruz de la Sierra, <Chip name="fecha"/>.</p>
    </div>
  );

  return (
    <div>
      <button className="btn btn-ghost btn-sm" onClick={onBack} style={{marginBottom:10, marginLeft:-8}}>
        <ArrowLeftIcon size={14}/>Volver al detalle
      </button>
      <div className="page-header" style={{marginBottom:18}}>
        <div>
          <div className="eyebrow">Generación individual</div>
          <h1 className="h2" style={{marginTop:6}}>Generar Documento</h1>
          <div className="page-subtitle">Desde la plantilla "{t.nombre}" ({t.version})</div>
        </div>
        <div style={{display:"flex", gap:8}}>
          <Button variant="outline" icon={<EyeIcon size={14}/>}>Vista previa</Button>
          <Button variant="grad" icon={<DownloadIcon size={14}/>} disabled={filled < vars.length}>Generar Documento</Button>
        </div>
      </div>

      {variant === "B" ? (
        // Top-bottom layout
        <div style={{display:"flex", flexDirection:"column", gap:18}}>
          <div className="card-floating" style={{padding:18}}>
            <div className="h4" style={{marginBottom:12}}>Variables ({filled}/{vars.length})</div>
            <div style={{display:"grid", gridTemplateColumns:"repeat(3, 1fr)", gap:12}}>
              {vars.slice(0, 9).map(v => (
                <Field key={v.name} label={<><span className="mono" style={{color:"#004ac6"}}>{v.name}</span></>}>
                  <Input placeholder={v.hint} value={values[v.name]} onChange={e=>setVal(v.name, e.target.value)}/>
                </Field>
              ))}
            </div>
          </div>
          <div className="card-floating" style={{padding:0}}>
            <div style={{padding:"12px 18px", borderBottom:"1px solid rgba(195,198,215,0.20)", display:"flex", justifyContent:"space-between"}}><div className="h4">Vista previa</div><Pill variant="ok">en vivo</Pill></div>
            <div style={{padding:24}}>{PreviewPanel}</div>
          </div>
        </div>
      ) : (
        // Side-by-side
        <div className="card-floating" style={{padding:0, display:"grid", gridTemplateColumns:"380px 1fr", height:"calc(100vh - 240px)", minHeight:600}}>
          {FormPanel}
          <div style={{borderLeft:"1px solid rgba(195,198,215,0.25)", background:"#f7f9fb", overflowY:"auto", padding:32}}>
            {PreviewPanel}
          </div>
        </div>
      )}
    </div>
  );
};

const GenerateBulkScreen = ({ variant = "A", template, onBack }) => {
  const t = template || window.TEMPLATES[4];
  const [step, setStep] = React.useState(0);
  const [drag, setDrag] = React.useState(false);
  const [filename, setFilename] = React.useState("");

  const steps = ["Descargar plantilla Excel", "Subir Excel completado", "Revisar y generar"];

  return (
    <div>
      <button className="btn btn-ghost btn-sm" onClick={onBack} style={{marginBottom:10, marginLeft:-8}}>
        <ArrowLeftIcon size={14}/>Volver al detalle
      </button>
      <div className="page-header" style={{marginBottom:24}}>
        <div>
          <div className="eyebrow">Generación masiva</div>
          <h1 className="h2" style={{marginTop:6}}>Genere múltiples documentos en bloque</h1>
          <div className="page-subtitle">Desde la plantilla "{t.nombre}" ({t.version}) — máximo 100 documentos por lote.</div>
        </div>
      </div>

      <div className="stepper">
        {steps.map((s, i) => (
          <React.Fragment key={i}>
            <div className={`step ${i === step ? "is-active" : ""} ${i < step ? "is-done" : ""}`}>
              <span className="step-num">{i < step ? <CheckIcon size={13}/> : i + 1}</span>
              <span className="step-label">{s}</span>
            </div>
            {i < steps.length - 1 && <div className={`step-bar ${i < step ? "is-done" : ""}`}/>}
          </React.Fragment>
        ))}
      </div>

      <div style={{display:"flex", flexDirection:"column", gap:14, maxWidth:880}}>
        <div className="card" style={{padding:20, opacity: step === 0 ? 1 : 0.6}}>
          <div style={{display:"flex", alignItems:"center", gap:14, marginBottom:10}}>
            <span style={{width:36, height:36, borderRadius:9, background: step >= 1 ? "#d1fae5" : "#dbe1ff", color: step >= 1 ? "#059669" : "#004ac6", display:"inline-flex", alignItems:"center", justifyContent:"center", fontWeight:700}}>
              {step >= 1 ? <CheckIcon size={16}/> : "1"}
            </span>
            <div style={{flex:1}}>
              <div className="h4">Descargar plantilla Excel</div>
              <div className="tiny" style={{marginTop:3}}>Archivo con {window.TEMPLATE_VARIABLES.length} columnas — una por variable. Complete cada fila con los datos de un documento.</div>
            </div>
            <Button variant="outline" icon={<DownloadIcon size={14}/>} onClick={()=>setStep(1)} disabled={step !== 0}>Descargar Plantilla Excel</Button>
          </div>
        </div>

        <div className="card" style={{padding:20, opacity: step === 1 ? 1 : (step > 1 ? 0.6 : 0.5), pointerEvents: step < 1 ? "none" : "auto"}}>
          <div style={{display:"flex", alignItems:"center", gap:14, marginBottom:14}}>
            <span style={{width:36, height:36, borderRadius:9, background: step >= 2 ? "#d1fae5" : (step === 1 ? "linear-gradient(135deg,#004ac6,#2563eb)" : "#eceef0"), color: step >= 2 ? "#059669" : (step === 1 ? "#fff" : "#515f74"), display:"inline-flex", alignItems:"center", justifyContent:"center", fontWeight:700, boxShadow: step === 1 ? "0 2px 8px rgba(0,74,198,0.30)" : "none"}}>{step >= 2 ? <CheckIcon size={16}/> : "2"}</span>
            <div style={{flex:1}}>
              <div className="h4">Subir Excel Completado</div>
              <div className="tiny" style={{marginTop:3}}>Arrastre el archivo .xlsx o haga clic para buscar.</div>
            </div>
          </div>
          {filename ? (
            <div style={{display:"flex", alignItems:"center", gap:10, padding:"12px 14px", background:"#d1fae5", borderRadius:10}}>
              <FileSpreadsheetIcon size={18} style={{color:"#059669"}}/>
              <div style={{flex:1, fontSize:13}}><strong>{filename}</strong> — 18 filas detectadas</div>
              <Button variant="ghost" size="sm" onClick={()=>{setFilename(""); setStep(1);}}>Cambiar archivo</Button>
              <Button variant="grad" size="sm" onClick={()=>setStep(2)}>Continuar</Button>
            </div>
          ) : (
            <div className={`dz ${drag?"dz-over":""}`}
              onDragOver={(e)=>{e.preventDefault(); setDrag(true);}}
              onDragLeave={()=>setDrag(false)}
              onDrop={(e)=>{e.preventDefault(); setDrag(false); setFilename("contratos_lote_mayo.xlsx"); setStep(2);}}
              onClick={()=>{setFilename("contratos_lote_mayo.xlsx"); setStep(2);}}>
              <FileSpreadsheetIcon size={32} style={{color: drag ? "#004ac6" : "#515f74"}}/>
              <div style={{fontSize:14, fontWeight:500, color: drag ? "#004ac6" : "#191c1e"}}>{drag ? "Suelte el archivo aquí" : "Arrastre y suelte el archivo .xlsx"}</div>
              <div className="tiny">o haga clic para buscar</div>
            </div>
          )}
        </div>

        <div className="card" style={{padding:20, opacity: step === 2 ? 1 : 0.5}}>
          <div style={{display:"flex", alignItems:"center", gap:14, marginBottom:14}}>
            <span style={{width:36, height:36, borderRadius:9, background: step === 2 ? "linear-gradient(135deg,#004ac6,#2563eb)" : "#eceef0", color: step === 2 ? "#fff" : "#515f74", display:"inline-flex", alignItems:"center", justifyContent:"center", fontWeight:700}}>3</span>
            <div style={{flex:1}}>
              <div className="h4">Revisar y generar</div>
              <div className="tiny" style={{marginTop:3}}>Verifique los datos antes de generar el lote completo.</div>
            </div>
          </div>
          {step === 2 && (
            <>
              <Banner variant="ok" icon={<CheckCircleIcon size={16} style={{color:"#059669"}}/>}>
                <strong>Excel válido</strong> — 18 filas detectadas, todas las columnas mapean a variables de la plantilla.
              </Banner>
              <div style={{display:"flex", justifyContent:"space-between", marginTop:14}}>
                <Button variant="outline" onClick={()=>{setStep(1); setFilename("");}}>Volver</Button>
                <Button variant="success" icon={<SparklesIcon size={14}/>}>Generar 18 Documentos</Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { GenerateIndividualScreen, GenerateBulkScreen });
