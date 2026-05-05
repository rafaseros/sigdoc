// SigDoc — Templates list screen (2 variants)

const TemplatesScreen = ({ variant = "A", onOpenTemplate, onUpload, onGuide, query, setQuery }) => {
  const filtered = window.TEMPLATES.filter(t => t.nombre.toLowerCase().includes((query||"").toLowerCase()));
  const total = window.TEMPLATES.length;
  const totalShared = window.TEMPLATES.filter(t=>t.shared).length;
  const totalVars = window.TEMPLATES.reduce((s,t)=>s+t.vars,0);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="eyebrow">Mis plantillas</div>
          <div className="page-title-row" style={{marginTop:6}}>
            <h1 className="h1">Plantillas</h1>
            <Pill variant="accent-soft">{total}</Pill>
          </div>
          <div className="page-subtitle">Documentos .docx con marcadores variables, listos para generar contratos en bloque o uno a uno.</div>
        </div>
        <div style={{display:"flex", gap:8}}>
          <Button variant="outline" icon={<BookIcon size={14}/>} onClick={onGuide}>Guía de Plantillas</Button>
          <Button variant="grad" icon={<UploadIcon size={14}/>} onClick={onUpload}>Subir Plantilla</Button>
        </div>
      </div>

      {variant === "B" && (
        <div className="stat-grid">
          <div className="stat">
            <div className="stat-label">Plantillas</div>
            <div className="stat-value">{total}</div>
            <div className="stat-delta">+2 esta semana</div>
            <div className="stat-icon"><FolderIcon size={16}/></div>
          </div>
          <div className="stat">
            <div className="stat-label">Compartidas</div>
            <div className="stat-value">{totalShared}</div>
            <div className="tiny">con miembros del equipo</div>
            <div className="stat-icon"><ShareIcon size={16}/></div>
          </div>
          <div className="stat">
            <div className="stat-label">Variables totales</div>
            <div className="stat-value">{totalVars}</div>
            <div className="tiny">a lo largo de plantillas</div>
            <div className="stat-icon"><CodeIcon size={16}/></div>
          </div>
          <div className="stat">
            <div className="stat-label">Documentos generados</div>
            <div className="stat-value">147</div>
            <div className="stat-delta">+34 este mes</div>
            <div className="stat-icon"><SparklesIcon size={16}/></div>
          </div>
        </div>
      )}

      {variant === "A" && (
        <Banner variant="info" icon={<InfoIcon size={16} style={{color:"#1e3a8a"}}/>}>
          <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", gap:12, width:"100%"}}>
            <div>
              <strong>¿Nuevo en SigDoc?</strong> Aprenda a configurar plantillas de Word con variables para automatizar la generación.
            </div>
            <Button variant="outline" size="sm" icon={<BookIcon size={13}/>} onClick={onGuide}>Ver Guía</Button>
          </div>
        </Banner>
      )}

      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", margin:"20px 0 12px", gap:12}}>
        <div style={{display:"flex", gap:8, alignItems:"center"}}>
          <Search value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar plantillas..." style={{width:320}}/>
          <Button variant="outline" size="sm" icon={<FilterIcon size={13}/>}>Filtros</Button>
        </div>
        <div className="tiny">{filtered.length} de {total} plantillas</div>
      </div>

      {variant === "B" ? (
        // CARDS variant
        <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(320px, 1fr))", gap:14}}>
          {filtered.map(t => (
            <div key={t.id} className="card" style={{padding:18, cursor:"pointer", transition:"all 150ms"}} onClick={()=>onOpenTemplate?.(t)}>
              <div style={{display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:12}}>
                <div style={{width:38, height:38, borderRadius:10, background:"#dbe1ff", color:"#004ac6", display:"inline-flex", alignItems:"center", justifyContent:"center"}}>
                  <FileTextIcon size={18}/>
                </div>
                <div style={{display:"flex", gap:6}}>
                  <Pill variant="outline">{t.version}</Pill>
                  {t.shared && <Pill variant="accent-soft">Compartida</Pill>}
                </div>
              </div>
              <h3 className="h4" style={{marginBottom:4, fontSize:14.5, lineHeight:1.3}}>{t.nombre}</h3>
              <div className="tiny" style={{marginBottom:14, lineHeight:1.5, minHeight:36}}>{t.desc}</div>
              <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", paddingTop:12, borderTop:"1px solid rgba(195,198,215,0.20)", fontSize:11.5, color:"#515f74"}}>
                <span><CodeIcon size={11} style={{verticalAlign:"-2px", marginRight:4, color:"#004ac6"}}/>{t.vars} variables</span>
                <span>{t.fecha}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card-floating">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{width:"38%"}}>Nombre</th>
                <th>Tipo</th>
                <th style={{width:110}}>Variables</th>
                <th style={{width:90}}>Versión</th>
                <th>Autor</th>
                <th style={{width:140}}>Actualizado</th>
                <th style={{width:60}}/>
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => (
                <tr key={t.id} style={{cursor:"pointer"}} onClick={()=>onOpenTemplate?.(t)}>
                  <td>
                    <div style={{display:"flex", alignItems:"center", gap:10}}>
                      <span style={{width:30, height:30, borderRadius:8, background:"#dbe1ff", color:"#004ac6", display:"inline-flex", alignItems:"center", justifyContent:"center", flexShrink:0}}><FileTextIcon size={14}/></span>
                      <div style={{minWidth:0}}>
                        <div style={{fontWeight:600, color:"#191c1e", display:"flex", alignItems:"center", gap:8}}>
                          {t.nombre}
                          {t.shared && <Pill variant="accent-soft" style={{height:18, fontSize:10}}>Compartida</Pill>}
                        </div>
                        <div className="tiny" style={{marginTop:2, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis", maxWidth:340}}>{t.desc}</div>
                      </div>
                    </div>
                  </td>
                  <td><Pill variant="secondary">{t.tipo}</Pill></td>
                  <td><Pill variant="accent-soft">{t.vars} vars</Pill></td>
                  <td><Pill variant="outline">{t.version}</Pill></td>
                  <td>
                    <div style={{display:"flex", alignItems:"center", gap:8}}>
                      <Avatar name={t.autor} size="sm"/>
                      <span style={{fontSize:12.5, color:"#515f74"}}>{t.autor.split("@")[0]}</span>
                    </div>
                  </td>
                  <td className="muted" style={{fontSize:12.5}}>{t.fecha}</td>
                  <td><IconButton icon={<EyeIcon size={14}/>} title="Abrir"/></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

Object.assign(window, { TemplatesScreen });
