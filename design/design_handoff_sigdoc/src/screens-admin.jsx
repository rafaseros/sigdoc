// SigDoc — Users + Audit screens

const UsersScreen = ({ variant = "A" }) => {
  const [users, setUsers] = React.useState(() => window.USERS);
  const total = users.length;
  const admins = users.filter(u=>u.rol==="Admin").length;
  const activos = users.filter(u=>u.estado==="Activo").length;
  const [query, setQuery] = React.useState("");
  const [createOpen, setCreateOpen] = React.useState(false);
  const [editUser, setEditUser] = React.useState(null);
  const [bajaUser, setBajaUser] = React.useState(null);
  const [toast, setToast] = React.useState(null);
  const showToast = (msg, kind="ok") => { setToast({msg,kind}); setTimeout(()=>setToast(null), 2400); };

  const filtered = users.filter(u => u.nombre.toLowerCase().includes(query.toLowerCase()) || u.email.toLowerCase().includes(query.toLowerCase()));

  const roleColor = (rol) => rol === "Admin" ? "accent" : rol === "Creador" ? "accent-soft" : "secondary";

  const handleCreate = ({ nombre, email, rol }) => {
    const newU = {
      id: "u" + (users.length + 1),
      email, nombre, rol,
      estado: "Activo",
      creado: "hoy",
      ultimo: "—",
      plantillas: 0,
    };
    setUsers([...users, newU]);
    showToast(`Usuario "${nombre}" creado. Invitación enviada a ${email}.`);
  };
  const handleSave = (updated) => {
    setUsers(users.map(u => u.id === updated.id ? updated : u));
    showToast(`Cambios guardados en "${updated.nombre}".`);
  };
  const handleBaja = (user, { mode }) => {
    if (mode === "delete") {
      setUsers(users.filter(u => u.id !== user.id));
      showToast(`Usuario "${user.nombre}" eliminado permanentemente.`, "err");
    } else {
      setUsers(users.map(u => u.id === user.id ? { ...u, estado: "Inactivo" } : u));
      showToast(`Usuario "${user.nombre}" desactivado.`, "ok");
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="eyebrow">Administración</div>
          <div className="page-title-row" style={{marginTop:6}}>
            <h1 className="h1">Usuarios</h1>
            <Pill variant="accent-soft">{total}</Pill>
          </div>
          <div className="page-subtitle">Gestione cuentas, roles y permisos del sistema. Solo administradores pueden crear o eliminar usuarios.</div>
        </div>
        <Button variant="grad" icon={<UserPlusIcon size={14}/>} onClick={()=>setCreateOpen(true)}>Crear Usuario</Button>
      </div>

      {variant === "B" && (
        <div className="stat-grid">
          <div className="stat"><div className="stat-label">Usuarios totales</div><div className="stat-value">{total}</div><div className="tiny">{activos} activos</div><div className="stat-icon"><UsersIcon size={16}/></div></div>
          <div className="stat"><div className="stat-label">Administradores</div><div className="stat-value">{admins}</div><div className="tiny">acceso total</div><div className="stat-icon"><ShieldIcon size={16}/></div></div>
          <div className="stat"><div className="stat-label">Creadores</div><div className="stat-value">{users.filter(u=>u.rol==="Creador").length}</div><div className="tiny">suben plantillas</div><div className="stat-icon"><EditIcon size={16}/></div></div>
          <div className="stat"><div className="stat-label">Generadores</div><div className="stat-value">{users.filter(u=>u.rol==="Generador").length}</div><div className="tiny">solo generan documentos</div><div className="stat-icon"><SparklesIcon size={16}/></div></div>
        </div>
      )}

      <div style={{display:"flex", justifyContent:"space-between", margin:"4px 0 14px", gap:12}}>
        <Search value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar por nombre o correo…" style={{width:340}}/>
        <div style={{display:"flex", gap:8}}>
          <Button variant="outline" size="sm" icon={<FilterIcon size={13}/>}>Filtrar por rol</Button>
        </div>
      </div>

      <div className="card-floating">
        <table className="tbl">
          <thead><tr>
            <th style={{width:"32%"}}>Usuario</th>
            <th>Rol</th>
            <th>Estado</th>
            <th>Plantillas</th>
            <th>Última actividad</th>
            <th>Creado</th>
            <th style={{width:120}}>Acciones</th>
          </tr></thead>
          <tbody>
            {filtered.map(u => (
              <tr key={u.id}>
                <td>
                  <div style={{display:"flex", alignItems:"center", gap:12}}>
                    <Avatar name={u.nombre}/>
                    <div>
                      <div style={{fontWeight:600}}>{u.nombre}</div>
                      <div className="tiny mono" style={{marginTop:2}}>{u.email}</div>
                    </div>
                  </div>
                </td>
                <td><Pill variant={roleColor(u.rol)}>{u.rol}</Pill></td>
                <td><Pill variant={u.estado==="Activo"?"ok":"secondary"} dot>{u.estado}</Pill></td>
                <td><span style={{fontWeight:500}}>{u.plantillas}</span> <span className="tiny">creadas</span></td>
                <td className="muted">{u.ultimo}</td>
                <td className="muted">{u.creado}</td>
                <td>
                  <div style={{display:"flex", gap:4}}>
                    <IconButton icon={<EditIcon size={14}/>} title="Editar" onClick={()=>setEditUser(u)}/>
                    <IconButton icon={<KeyIcon size={14}/>} title="Resetear contraseña" onClick={()=>showToast(`Enlace de reseteo enviado a ${u.email}`)}/>
                    <IconButton icon={<TrashIcon size={14}/>} title="Dar de baja" onClick={()=>setBajaUser(u)} style={{color:"#ba1a1a"}}/>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <CreateUserDialog
        open={createOpen}
        onClose={()=>setCreateOpen(false)}
        onCreated={handleCreate}
      />
      <EditUserDialog
        open={!!editUser}
        user={editUser}
        onClose={()=>setEditUser(null)}
        onSaved={handleSave}
      />
      <DeactivateUserDialog
        open={!!bajaUser}
        user={bajaUser}
        onClose={()=>setBajaUser(null)}
        onConfirm={(payload)=>handleBaja(bajaUser, payload)}
      />

      {toast && (
        <div style={{
          position:"fixed", top:24, right:24, zIndex:9999,
          background: toast.kind==="ok" ? "#d1fae5" : "#ffdad6",
          color: toast.kind==="ok" ? "#065f46" : "#93000a",
          padding:"10px 16px", borderRadius:10, fontSize:13.5, fontWeight:500,
          boxShadow:"0 4px 16px rgba(25,28,30,0.10)",
          display:"flex", alignItems:"center", gap:8,
        }}>
          {toast.kind === "ok" ? <CheckCircleIcon size={16}/> : <AlertCircleIcon size={16}/>}
          {toast.msg}
        </div>
      )}
    </div>
  );
};

const AuditScreen = ({ variant = "A" }) => {
  const [filter, setFilter] = React.useState("all");
  const audit = window.AUDIT;
  const filtered = filter === "all" ? audit : audit.filter(a=>a.action===filter);

  const ActionPill = ({ action }) => {
    const k = window.ACTION_KINDS[action] || { label: action, variant: "secondary" };
    return <Pill variant={k.variant}>{k.label}</Pill>;
  };

  // Group by `grupo`
  const grouped = filtered.reduce((acc, row) => {
    (acc[row.grupo] = acc[row.grupo] || []).push(row);
    return acc;
  }, {});

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="eyebrow">Seguridad</div>
          <h1 className="h1" style={{marginTop:6}}>Auditoría</h1>
          <div className="page-subtitle">Registro inmutable de todas las acciones realizadas en el sistema. Las entradas no pueden modificarse ni eliminarse.</div>
        </div>
        <div style={{display:"flex", gap:8}}>
          <Button variant="outline" icon={<DownloadIcon size={14}/>}>Exportar CSV</Button>
        </div>
      </div>

      {variant === "B" && (
        <div className="stat-grid">
          <div className="stat"><div className="stat-label">Eventos hoy</div><div className="stat-value">{audit.filter(a=>a.grupo==="Hoy").length}</div><div className="stat-delta">+12% vs ayer</div><div className="stat-icon"><ClockIcon size={16}/></div></div>
          <div className="stat"><div className="stat-label">Inicios de sesión</div><div className="stat-value">{audit.filter(a=>a.action==="login").length}</div><div className="tiny">en 7 días</div><div className="stat-icon"><LoginIcon size={16}/></div></div>
          <div className="stat"><div className="stat-label">Documentos generados</div><div className="stat-value">{audit.filter(a=>a.action==="generate"||a.action==="bulk"||a.action==="download").length}</div><div className="tiny">acciones de generación</div><div className="stat-icon"><SparklesIcon size={16}/></div></div>
          <div className="stat"><div className="stat-label">Cambios admin</div><div className="stat-value">{audit.filter(a=>["user_create","user_update","password_reset"].includes(a.action)).length}</div><div className="tiny">creación/edición usuarios</div><div className="stat-icon"><ShieldIcon size={16}/></div></div>
        </div>
      )}

      {/* Filter bar */}
      <div className="filter-bar">
        <Field label="Acción" style={{width:200}}>
          <select className="input" value={filter} onChange={e=>setFilter(e.target.value)}>
            <option value="all">Todas las acciones</option>
            {Object.entries(window.ACTION_KINDS).map(([k,v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </Field>
        <Field label="Usuario" style={{width:240}}>
          <Input placeholder="Buscar por correo…"/>
        </Field>
        <Field label="Desde" style={{width:160}}>
          <Input type="text" placeholder="dd/mm/aaaa"/>
        </Field>
        <Field label="Hasta" style={{width:160}}>
          <Input type="text" placeholder="dd/mm/aaaa"/>
        </Field>
        <div style={{flex:1}}/>
        <Button variant="ghost" size="sm">Limpiar</Button>
        <Button variant="grad" icon={<FilterIcon size={13}/>}>Aplicar Filtros</Button>
      </div>

      {/* Quick filter chips */}
      <div style={{display:"flex", gap:6, flexWrap:"wrap", marginBottom:14}}>
        {[["all","Todas"],["login","Sesiones"],["generate","Generaciones"],["upload","Subidas"],["user_create","Cambios de usuario"],["template_delete","Eliminaciones"]].map(([k,l]) => (
          <span key={k} className={`tab-pill ${filter===k?"active":""}`} onClick={()=>setFilter(k)}>{l}</span>
        ))}
      </div>

      {variant === "B" ? (
        // Timeline grouped by day
        <div style={{display:"flex", flexDirection:"column", gap:24}}>
          {Object.entries(grouped).map(([grupo, rows]) => (
            <div key={grupo}>
              <div className="eyebrow" style={{marginBottom:10}}>{grupo} <span style={{color:"#a0a4af", marginLeft:8}}>· {rows.length} eventos</span></div>
              <div className="card-floating" style={{padding:0}}>
                {rows.map((r, i) => {
                  const k = window.ACTION_KINDS[r.action] || {};
                  return (
                    <div key={i} style={{display:"grid", gridTemplateColumns:"110px 1fr 220px 120px", gap:14, padding:"14px 18px", borderTop: i ? "1px solid rgba(195,198,215,0.18)" : "none", alignItems:"center"}}>
                      <div className="tiny" style={{fontVariantNumeric:"tabular-nums"}}>{r.fecha.split(",")[1]?.trim() || r.fecha}</div>
                      <div>
                        <div style={{display:"flex", alignItems:"center", gap:10, marginBottom:3}}>
                          <ActionPill action={r.action}/>
                          <span style={{fontWeight:500, fontSize:13}}>{r.detalles}</span>
                        </div>
                        <div className="tiny mono">recurso: {r.recurso}</div>
                      </div>
                      <div style={{display:"flex", alignItems:"center", gap:8}}>
                        <Avatar name={r.usuario} size="sm"/>
                        <span className="tiny" style={{fontWeight:500}}>{r.usuario.split("@")[0]}</span>
                      </div>
                      <div className="tiny mono" style={{textAlign:"right"}}>{r.ip}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card-floating">
          <table className="tbl tbl-compact">
            <thead><tr>
              <th style={{width:160}}>Fecha</th>
              <th>Usuario</th>
              <th>Acción</th>
              <th>Recurso</th>
              <th>Detalles</th>
              <th style={{width:110}}>IP</th>
            </tr></thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr key={i}>
                  <td className="muted" style={{fontVariantNumeric:"tabular-nums", fontSize:12.5}}>{r.fecha}</td>
                  <td><div style={{display:"flex", alignItems:"center", gap:8}}><Avatar name={r.usuario} size="sm"/><span className="mono" style={{fontSize:12}}>{r.usuario}</span></div></td>
                  <td><ActionPill action={r.action}/></td>
                  <td><Pill variant="secondary">{r.recurso}</Pill></td>
                  <td className="tiny" style={{maxWidth:380, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{r.detalles}</td>
                  <td className="mono" style={{fontSize:11.5, color:"#515f74"}}>{r.ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

Object.assign(window, { UsersScreen, AuditScreen });
